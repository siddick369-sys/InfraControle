import random
from celery import shared_task
from django.utils import timezone
from .models import AccessPoint, WifiMetric, WifiAlert, WifiClient

@shared_task
def collect_wifi_metrics():
    """
    Simule la collecte de métriques pour tous les points d'accès actifs.
    Génère des données réalistes pour le CPU, la RAM, les clients et le trafic.
    """
    aps = AccessPoint.objects.all()
    if not aps.exists():
        return "Aucun point d'accès trouvé."

    for ap in aps:
        # 1. Simuler l'état de l'AP
        if random.random() < 0.05: # 5% de chance qu'un AP tombe
            ap.statut = 'down'
        else:
            ap.statut = 'up'
        
        # 2. Simuler les ressources
        ap.cpu_usage = round(random.uniform(5, 95), 1)
        ap.ram_usage = round(random.uniform(20, 80), 1)
        ap.save()

        # 3. Créer une nouvelle métrique
        clients_2ghz = random.randint(5, 30)
        clients_5ghz = random.randint(10, 50)
        
        WifiMetric.objects.create(
            access_point=ap,
            clients_2ghz=clients_2ghz,
            clients_5ghz=clients_5ghz,
            channel_utilization=round(random.uniform(10, 60), 1),
            traffic_tx_bytes=random.randint(1000000, 100000000),
            traffic_rx_bytes=random.randint(1000000, 100000000),
        )

    return f"Collecte terminée pour {aps.count()} points d'accès."

@shared_task
def check_wifi_health():
    """
    Vérifie l'état de santé des APs et génère des alertes si nécessaire.
    """
    aps = AccessPoint.objects.all()
    alert_count = 0

    for ap in aps:
        # Alerte si l'AP est hors ligne
        if ap.statut == 'down':
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="AP_DOWN", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap,
                    type_alerte="AP_DOWN",
                    description=f"Le point d'accès {ap.nom} ({ap.adresse_ip}) ne répond plus.",
                    severite='high'
                )
                alert_count += 1
        
        # Alerte si le CPU est trop élevé
        if ap.cpu_usage > 90:
            if not WifiAlert.objects.filter(access_point=ap, type_alerte="CPU_CRITICAL", est_resolu=False).exists():
                WifiAlert.objects.create(
                    access_point=ap,
                    type_alerte="CPU_CRITICAL",
                    description=f"Utilisation CPU critique sur {ap.nom} : {ap.cpu_usage}%",
                    severite='high'
                )
                alert_count += 1
                
    return f"Vérification santé terminée. {alert_count} nouvelles alertes créées."

@shared_task
def simulate_wifi_clients():
    """
    Simule la présence de clients sur les APs.
    """
    aps = AccessPoint.objects.filter(statut='up')
    if not aps.exists():
        return "Pas d'APs actifs."

    # Liste de types d'appareils
    devices = ['iPhone 15', 'Samsung S23', 'MacBook Pro', 'Dell XPS', 'iPad Air']
    
    for ap in aps:
        # On simule 5 clients par AP pour la démo
        for i in range(5):
            mac = f"00:1A:2B:3C:4D:{random.randint(10, 99)}"
            WifiClient.objects.update_or_create(
                mac_adresse=mac,
                defaults={
                    'adresse_ip': f"192.168.10.{random.randint(100, 250)}",
                    'device_type': random.choice(devices),
                    'access_point_actuel': ap,
                    'rssi': random.randint(-80, -30),
                    'snr': random.randint(10, 40)
                }
            )
    
    return "Simulation clients WiFi terminée."
