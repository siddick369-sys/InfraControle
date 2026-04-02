from monitoring.models import WifiIncident, WifiClient
from monitoring.ssh_utils import ssh_connect


CANAL_24G = [1, 6, 11]
CANAL_5G = [36, 40, 44, 48]


def changer_canal(radio):
    canal = (CANAL_5G if radio.bande == "5" else CANAL_24G)[0]

    ssh = ssh_connect(radio.ap.equipement)
    ssh.exec_command(f"iw dev wlan{radio.bande} set channel {canal}")
    ssh.close()

    WifiIncident.objects.create(
        ap=radio.ap,
        radio=radio,
        type_incident="canal_sature",
        description=f"Changement automatique vers canal {canal}",
    )


def repartir_clients(ap):
    radios = list(ap.radios.all())
    if len(radios) < 2:
        return

    clients = WifiClient.objects.filter(radio__ap=ap)

    for i, client in enumerate(clients):
        client.radio = radios[i % len(radios)]
        client.save(update_fields=["radio"])

    WifiIncident.objects.create(
        ap=ap,
        type_incident="debit_faible",
        description="Répartition automatique des clients Wi-Fi",
    )


def auto_maintenance_wifi(ap):
    for radio in ap.radios.all():
        if radio.taux_utilisation and radio.taux_utilisation > 90:
            changer_canal(radio)

    if WifiClient.objects.filter(radio__ap=ap).count() > ap.nb_clients_max:
        repartir_clients(ap)