from django.utils import timezone
from monitoring.models import (
    WifiAccessPoint,
    WifiRadio,
    WifiClient,
    WifiStat
)

from django.utils import timezone
from monitoring.models import WifiRadio, WifiClient, WifiStat


def enregistrer_wifi(ap, data):
    """
    Persist Wi-Fi
    SAFE même si data est vide
    """

    if not data:
        return

    radios_map = {}

    # =========================
    # 📡 RADIOS
    # =========================
    for r in data.get("radios", []):
        bande = r.get("bande")
        if not bande:
            continue

        radio, _ = WifiRadio.objects.update_or_create(
            ap=ap,
            bande=bande,
            defaults={
                "canal": r.get("canal", 1),
                "largeur_canal_mhz": r.get("largeur", 20),
                "puissance_tx_dbm": r.get("tx_power", 20),
                "bruit_dbm": r.get("noise"),
                "radio_active": True,
                "taux_utilisation": r.get("utilisation"),
            }
        )
        radios_map[bande] = radio

    # =========================
    # 👥 CLIENTS
    # =========================
    for c in data.get("clients", []):
        WifiClient.objects.update_or_create(
            mac=c["mac"],
            defaults={
                "ip": c.get("ip"),
                "fabricant": c.get("vendor", ""),
                "type_device": c.get("type", "autre"),
                "ssid": c.get("ssid"),
                "radio": radios_map.get(c.get("bande")),
                "rssi": c.get("rssi", -90),
                "snr": c.get("snr"),
                "tx_rate_mbps": c.get("tx"),
                "rx_rate_mbps": c.get("rx"),
                "roaming": c.get("roaming", False),
                "connecte_depuis": timezone.now(),
                "dernier_paquet": timezone.now(),
            }
        )

    # =========================
    # 📊 STATS
    # =========================
    for radio in radios_map.values():
        clients = WifiClient.objects.filter(radio=radio)

        WifiStat.objects.create(
            ap=ap,
            radio=radio,
            date_releve=timezone.now(),
            nb_clients=clients.count(),
            debit_total_mbps=sum(
                (c.tx_rate_mbps or 0) + (c.rx_rate_mbps or 0)
                for c in clients
            ),
            canal_sature=(
                radio.taux_utilisation is not None
                and radio.taux_utilisation > 90
            ),
        )

    ap.dernier_scan = timezone.now()
    ap.save(update_fields=["dernier_scan"])