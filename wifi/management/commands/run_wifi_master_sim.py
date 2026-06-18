import time
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from wifi.models import AccessPoint, WifiMetric, WifiClient, WifiAlert

class Command(BaseCommand):
    help = 'Simulateur WiFi surpuissant - Animation en temps réel'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Lancement du simulateur WiFi Master..."))
        
        # 1. Seeding des APs si nécessaire
        ap_configs = [
            ("Orange-Fibre-9C6D", "00:1A:2B:3C:4D:01", "192.168.10.1", "Huawei HG8245H5"),
            ("MTN-4G-MiFi-B8F0", "00:1A:2B:3C:4D:02", "192.168.8.1", "ZTE MF927U"),
        ]
        
        aps = []
        for nom, mac, ip, mod in ap_configs:
            ap, created = AccessPoint.objects.get_or_create(
                mac_adresse=mac,
                defaults={'nom': nom, 'adresse_ip': ip, 'modele': mod, 'statut': 'up'}
            )
            aps.append(ap)
            if created:
                self.stdout.write(f"  + Création AP: {nom}")
        
        # Nettoyage des APs en trop
        AccessPoint.objects.exclude(mac_adresse__in=["00:1A:2B:3C:4D:01", "00:1A:2B:3C:4D:02"]).delete()

        # 2. Pool de clients typiques au Cameroun
        clients_pool = [
            ("Tecno Spark 10", "AC:DE:48:00:11:22"),
            ("Infinix Note 30", "BC:DF:49:00:33:44"),
            ("Itel P40", "CC:E0:50:00:55:66"),
            ("Samsung Galaxy A14", "DC:E1:51:00:77:88"),
            ("Redmi Note 12", "EC:E2:52:00:99:AA"),
            ("iPhone 13 Pro", "FC:E3:53:00:BB:CC"),
            ("Huawei Y9", "0C:E4:54:00:DD:EE"),
            ("HP ProBook 450", "1C:E5:55:00:FF:00"),
        ]

        # 3. Boucle temps réel
        iteration = 0
        try:
            while True:
                iteration += 1
                self.stdout.write(f"\n--- Mise à jour #{iteration} ({timezone.now().strftime('%H:%M:%S')}) ---")
                
                for ap in aps:
                    # Simulation état AP (98% de chance d'être UP)
                    if random.random() < 0.02:
                        ap.statut = 'down'
                        self.stdout.write(self.style.WARNING(f"  [!] {ap.nom} est tombé !"))
                    else:
                        ap.statut = 'up'
                    
                    # Simulation CPU/RAM (fluctuation douce)
                    ap.cpu_usage = max(5, min(98, ap.cpu_usage + random.uniform(-5, 5)))
                    ap.ram_usage = max(20, min(95, ap.ram_usage + random.uniform(-2, 2)))
                    ap.save()

                    if ap.statut == 'up':
                        # Métriques
                        last_metric = ap.metrics.first()
                        tx_inc = random.randint(50000, 5000000)
                        rx_inc = random.randint(100000, 10000000)
                        
                        tx_total = (last_metric.traffic_tx_bytes if last_metric else 0) + tx_inc
                        rx_total = (last_metric.traffic_rx_bytes if last_metric else 0) + rx_inc

                        metric = WifiMetric.objects.create(
                            access_point=ap,
                            clients_2ghz=random.randint(4, 12),
                            clients_5ghz=random.randint(1, 6),
                            channel_utilization=round(random.uniform(5, 75), 1),
                            traffic_tx_bytes=tx_total,
                            traffic_rx_bytes=rx_total
                        )
                        
                        # Alerte thermique
                        if ap.cpu_usage > 92:
                            WifiAlert.objects.create(
                                access_point=ap,
                                type_alerte="Surchauffe AP",
                                description=f"Température critique sur {ap.nom} (CPU: {ap.cpu_usage}%)",
                                severite='high'
                            )

                    # Simuler clients (Roaming)
                    # Chaque client a une chance de roamer sur un autre AP
                    for device_nom, mac in clients_pool:
                        if random.random() < 0.3: # 30% de chance de bouger/reconnecter
                            WifiClient.objects.update_or_create(
                                mac_adresse=mac,
                                defaults={
                                    'adresse_ip': f"192.168.10.{random.randint(100, 254)}",
                                    'device_type': device_nom,
                                    'access_point_actuel': random.choice(aps) if random.random() > 0.1 else None,
                                    'rssi': random.randint(-85, -35),
                                    'snr': random.randint(5, 45)
                                }
                            )

                self.stdout.write(f"  OK. Prochaine mise à jour dans 5s...")
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.ERROR("\n🛑 Simulateur arrêté."))
