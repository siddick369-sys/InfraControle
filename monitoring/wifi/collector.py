from django.utils import timezone
from monitoring.models import (
    WifiAccessPoint,
    WifiRadio,
    WifiClient,
    WifiStat,
)
from .ssh import collect_radios_ssh, collect_clients_ssh
from .snmp import collect_radio_snmp
from .parser import parse_station_dump
from django.utils import timezone
from monitoring.models import (
    WifiAccessPoint,
    WifiRadio,
    WifiClient,
    WifiStat,
)
from .ssh import collect_radios_ssh, collect_clients_ssh
from .parser import parse_station_dump

from django.utils import timezone
from monitoring.models import WifiAccessPoint, WifiRadio, WifiClient, WifiStat
from .ssh import collect_radios_ssh, collect_clients_ssh
from .parser import parse_station_dump


def collect_wifi(equipement):
    """
    Collecte Wi-Fi robuste
    NE CRASH JAMAIS
    """

    # ⛔ Pas un AP Wi-Fi
    try:
        ap = equipement.wifi_ap
    except WifiAccessPoint.DoesNotExist:
        return None

    radios_data = collect_radios_ssh(equipement) or []
    clients_raw = collect_clients_ssh(equipement) or []

    radios_map = {}

    # =====================
    # 📡 RADIOS
    # =====================
    for r in radios_data:
        interface = r.get("interface")
        if not interface:
            continue

        bande = "2.4"
        if "5" in interface:
            bande = "5"
        elif "6" in interface:
            bande = "6"

        radio, _ = WifiRadio.objects.update_or_create(
            ap=ap,
            bande=bande,
            defaults={
                "canal": r.get("canal", 1),
                "largeur_canal_mhz": r.get("largeur", 20),
                "puissance_tx_dbm": r.get("tx_power", 20),
                "bruit_dbm": r.get("bruit"),
                "taux_utilisation": r.get("utilisation"),
                "radio_active": True,
            }
        )

        radios_map[interface] = radio

    # =====================
    # 👥 CLIENTS
    # =====================
    for block in clients_raw:
        interface = block.get("interface")
        radio = radios_map.get(interface)
        if not radio:
            continue

        clients = parse_station_dump(block.get("raw"))

        for c in clients:
            WifiClient.objects.update_or_create(
                mac=c["mac"],
                defaults={
                    "radio": radio,
                    "ssid": None,
                    "rssi": c.get("rssi", -90),
                    "tx_rate_mbps": c.get("tx_mbps"),
                    "rx_rate_mbps": c.get("rx_mbps"),
                    "connecte_depuis": timezone.now(),
                    "dernier_paquet": timezone.now(),
                }
            )

    # =====================
    # 📊 STATS
    # =====================
    for radio in radios_map.values():
        nb_clients = WifiClient.objects.filter(radio=radio).count()

        WifiStat.objects.create(
            ap=ap,
            radio=radio,
            nb_clients=nb_clients,
            debit_total_mbps=0,
            canal_sature=(
                radio.taux_utilisation is not None
                and radio.taux_utilisation > 90
            ),
        )

    ap.dernier_scan = timezone.now()
    ap.save(update_fields=["dernier_scan"])

    return True