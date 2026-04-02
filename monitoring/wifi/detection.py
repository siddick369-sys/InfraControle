from monitoring.models import (
    WifiStat,
    WifiClient,
    WifiIncident,
    WifiAccessPoint
)


def detecter_incidents_wifi(obj):
    """
    Détecte les incidents Wi-Fi
    Accepte :
    - WifiAccessPoint
    - EquipementReseau (ayant un wifi_ap)
    Retourne une liste d'anomalies détectées
    """

    # ==========================
    # 🔐 RÉSOLUTION DE L’AP
    # ==========================
    if isinstance(obj, WifiAccessPoint):
        ap = obj
    elif hasattr(obj, "wifi_ap"):
        ap = obj.wifi_ap
    else:
        return []

    anomalies = []

    # ==========================
    # 📊 DERNIÈRES STATS
    # ==========================
    stats = (
        WifiStat.objects
        .filter(ap=ap)
        .order_by("-date_releve")
        .first()
    )

    if not stats:
        return anomalies

    # ==========================
    # 🔴 SURCHARGE CLIENTS
    # ==========================
    if stats.nb_clients > ap.nb_clients_max:
        WifiIncident.objects.create(
            ap=ap,
            radio=None,
            ssid=None,
            type_incident="debit_faible",
            description=(
                f"Surcharge Wi-Fi : {stats.nb_clients} clients "
                f"(max {ap.nb_clients_max})"
            )
        )
        anomalies.append("clients")

    # ==========================
    # 🟠 RSSI FAIBLE
    # ==========================
    mauvais_clients = WifiClient.objects.filter(
        radio__ap=ap,
        rssi__lt=-75
    )

    if mauvais_clients.exists():
        WifiIncident.objects.create(
            ap=ap,
            radio=None,
            ssid=None,
            type_incident="debit_faible",
            description=(
                f"{mauvais_clients.count()} clients avec RSSI < -75 dBm"
            )
        )
        anomalies.append("rssi")

    # ==========================
    # 🔴 INTERFÉRENCES RADIO
    # ==========================
    radios_bruyantes = ap.radios.filter(
        bruit_dbm__isnull=False,
        bruit_dbm__gt=-80
    )

    if radios_bruyantes.exists():
        WifiIncident.objects.create(
            ap=ap,
            radio=radios_bruyantes.first(),
            ssid=None,
            type_incident="interference",
            description="Bruit radio élevé détecté"
        )
        anomalies.append("interference")

    # ==========================
    # 🔴 RADIO ACTIVE SANS CLIENT
    # ==========================
    radios_actives = ap.radios.filter(radio_active=True)
    clients_connectes = WifiClient.objects.filter(radio__ap=ap)

    if radios_actives.exists() and not clients_connectes.exists():
        WifiIncident.objects.create(
            ap=ap,
            radio=None,
            ssid=None,
            type_incident="radio_down",
            description="Radios actives mais aucun client connecté"
        )
        anomalies.append("radio")

    return anomalies