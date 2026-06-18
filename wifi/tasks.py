import random
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from .models import AccessPoint, WifiMetric, WifiAlert, WifiClient


# ────────────────────────────────────────────────
# Scoring de confiance par type d'appareil
# ────────────────────────────────────────────────
DEVICE_SCORES = {
    'iPhone 15 Pro': 95, 'Samsung Galaxy S23': 92, 'MacBook Air M2': 90,
    'Smart TV LG': 85, 'iPad Pro': 93, 'PlayStation 5': 88,
    'Chromecast Ultra': 80, 'Alexa Echo': 78, 'Raspberry Pi': 55,
    'Kali Linux / Attaquant': 5, 'Unknown Device': 30,
}

SAFE_DEVICES = ['iPhone 15 Pro', 'Samsung Galaxy S23', 'MacBook Air M2',
                'Smart TV LG', 'iPad Pro', 'PlayStation 5',
                'Chromecast Ultra', 'Alexa Echo']


def _get_hourly_client_count():
    """Variation horaire réaliste : peu la nuit, pic le soir."""
    hour = datetime.now().hour
    if 0 <= hour < 7:
        return random.randint(2, 5)     # Nuit
    elif 7 <= hour < 12:
        return random.randint(6, 12)    # Matin
    elif 12 <= hour < 18:
        return random.randint(8, 15)    # Après-midi
    else:
        return random.randint(12, 25)   # Soirée (pic)


@shared_task
def collect_wifi_metrics():
    """
    Simule la collecte de métriques pour tous les APs.
    Inclut simulation DDoS (CPU spike + trafic ×100).
    """
    aps = AccessPoint.objects.all()
    if not aps.exists():
        return "Aucun point d'accès trouvé."

    for ap in aps:
        is_ddos = random.random() < 0.05  # 5% chance DDoS

        # 1. État de l'AP
        if random.random() < 0.05:
            ap.statut = 'down'
        else:
            ap.statut = 'up'

        # 2. Ressources (DDoS = CPU 95-99%)
        if is_ddos and ap.statut == 'up':
            ap.cpu_usage = round(random.uniform(95, 99.9), 1)
            ap.ram_usage = round(random.uniform(85, 98), 1)
        else:
            ap.cpu_usage = round(random.uniform(5, 65), 1)
            ap.ram_usage = round(random.uniform(20, 70), 1)
        ap.save()

        # 3. Métriques (DDoS = trafic ×100)
        tx_mult = 100 if is_ddos else 1
        clients_2ghz = random.randint(3, 20)
        clients_5ghz = random.randint(5, 35)

        WifiMetric.objects.create(
            access_point=ap,
            clients_2ghz=clients_2ghz,
            clients_5ghz=clients_5ghz,
            channel_utilization=round(random.uniform(10, 95 if is_ddos else 60), 1),
            traffic_tx_bytes=random.randint(1000000, 100000000) * tx_mult,
            traffic_rx_bytes=random.randint(1000000, 100000000) * tx_mult,
        )

        # 4. Alerte DDoS
        if is_ddos:
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="DDOS_WIFI", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap,
                    type_alerte="DDOS_WIFI",
                    description=f"Attaque DDoS WiFi détectée sur {ap.nom} ! Trafic anormal ×100, CPU à {ap.cpu_usage}%.",
                    severite='high'
                )

    return f"Collecte terminée pour {aps.count()} APs."


@shared_task
def check_wifi_health():
    """
    Vérifie l'état de santé des APs et génère des alertes.
    Détecte : AP_DOWN, CPU_CRITICAL, INTRUSION_BRUTE_FORCE, DEAUTH_ATTACK, ARP_POISONING.
    """
    aps = AccessPoint.objects.all()
    alert_count = 0

    for ap in aps:
        # AP hors ligne
        if ap.statut == 'down':
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="AP_DOWN", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap, type_alerte="AP_DOWN",
                    description=f"Le point d'accès {ap.nom} ({ap.adresse_ip}) ne répond plus.",
                    severite='high'
                )
                alert_count += 1

        # CPU critique
        if ap.cpu_usage > 90:
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="CPU_CRITICAL", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap, type_alerte="CPU_CRITICAL",
                    description=f"Utilisation CPU critique sur {ap.nom} : {ap.cpu_usage}%",
                    severite='high'
                )
                alert_count += 1

        # Intrusion Brute-Force (Kali Linux)
        intrus = ap.clients_connectes.filter(device_type__icontains="Kali Linux", est_bloque=False).first()
        if intrus:
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="INTRUSION_BRUTE_FORCE", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap, type_alerte="INTRUSION_BRUTE_FORCE",
                    description=f"⚠️ Tentative de craquage WPA3 par brute-force depuis {intrus.mac_adresse} ({intrus.adresse_ip})",
                    severite='high'
                )
                alert_count += 1

        # Deauth Attack (RSSI -999)
        deauth_victim = ap.clients_connectes.filter(rssi__lte=-200, est_bloque=False).first()
        if deauth_victim:
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="DEAUTH_ATTACK", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap, type_alerte="DEAUTH_ATTACK",
                    description=f"Attaque de désauthentification détectée ! Client {deauth_victim.mac_adresse} expulsé de force.",
                    severite='high'
                )
                alert_count += 1

        # ARP Poisoning (client avec IP de la passerelle)
        arp_spoof = ap.clients_connectes.filter(adresse_ip="192.168.1.1", est_bloque=False).first()
        if arp_spoof:
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="ARP_POISONING", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap, type_alerte="ARP_POISONING",
                    description=f"🔴 Attaque Man-in-the-Middle ! L'appareil {arp_spoof.mac_adresse} usurpe l'IP de la passerelle (192.168.1.1).",
                    severite='high'
                )
                alert_count += 1

    return f"Vérification santé terminée. {alert_count} nouvelles alertes créées."


@shared_task
def simulate_wifi_clients():
    """
    Simule la présence de clients réalistes + injections d'attaques variées.
    """
    aps = AccessPoint.objects.filter(statut='up')
    if not aps.exists():
        return "Pas d'APs actifs."

    client_count = _get_hourly_client_count()

    for ap in aps:
        # ── Clients légitimes ──
        for i in range(client_count):
            mac = f"00:1A:2B:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}"
            device = random.choice(SAFE_DEVICES)
            WifiClient.objects.update_or_create(
                mac_adresse=mac,
                defaults={
                    'adresse_ip': f"192.168.1.{random.randint(100, 250)}",
                    'device_type': device,
                    'access_point_actuel': ap,
                    'rssi': random.randint(-70, -25),
                    'snr': random.randint(18, 42),
                    'score_confiance': DEVICE_SCORES.get(device, 75),
                    'est_bloque': False,
                }
            )

        # ── Injection Kali Linux / Brute-Force (10%) ──
        if random.random() < 0.10:
            hacker_mac = f"DE:AD:BE:EF:{random.randint(10,99)}:{random.randint(10,99)}"
            WifiClient.objects.update_or_create(
                mac_adresse=hacker_mac,
                defaults={
                    'adresse_ip': "192.168.1.99",
                    'device_type': "Kali Linux / Attaquant",
                    'access_point_actuel': ap,
                    'rssi': random.randint(-92, -85),
                    'snr': random.randint(3, 10),
                    'score_confiance': 5,
                    'est_bloque': False,
                }
            )

        # ── Rogue Access Point (3%) ──
        if random.random() < 0.03:
            rogue_mac = f"RO:GU:E0:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}"
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="ROGUE_AP", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap, type_alerte="ROGUE_AP",
                    description=f"🛑 Point d'accès jumeau détecté ! Un AP inconnu ({rogue_mac}) diffuse le même SSID que {ap.nom}.",
                    severite='high'
                )

        # ── Deauth Attack (5%) ──
        if random.random() < 0.05:
            victim = ap.clients_connectes.filter(est_bloque=False).exclude(device_type__icontains="Kali").first()
            if victim:
                victim.rssi = -999
                victim.snr = 0
                victim.score_confiance = 20
                victim.save()

        # ── ARP Poisoning (3%) ──
        if random.random() < 0.03:
            arp_mac = f"AR:PP:01:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}"
            WifiClient.objects.update_or_create(
                mac_adresse=arp_mac,
                defaults={
                    'adresse_ip': "192.168.1.1",  # Usurpe la passerelle !
                    'device_type': "Unknown Device",
                    'access_point_actuel': ap,
                    'rssi': random.randint(-80, -70),
                    'snr': random.randint(8, 15),
                    'score_confiance': 10,
                    'est_bloque': False,
                }
            )

    return "Simulation complète. Injecteur d'intrusions multi-vecteurs exécuté."
