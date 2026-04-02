from monitoring.models import WifiStat, WifiClient, WifiRadio


def extraire_features_wifi(ap):
    stat = WifiStat.objects.filter(ap=ap).order_by("-date_releve").first()
    clients = WifiClient.objects.filter(radio__ap=ap)
    radios = WifiRadio.objects.filter(ap=ap)

    return {
        "nb_clients": stat.nb_clients if stat else 0,
        "canal_sature": stat.canal_sature if stat else False,
        "debit_total": stat.debit_total_mbps if stat else 0,
        "clients_faible_rssi": clients.filter(rssi__lt=-75).count(),
        "clients_instables": clients.filter(roaming=True).count(),
        "radios_bruitees": radios.filter(bruit_dbm__gt=-85).count(),
        "radios_total": radios.count(),
    }