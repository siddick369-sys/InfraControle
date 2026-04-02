import os
import django
import random

# Initialisation de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from wifi.models import AccessPoint
from wifi.tasks import collect_wifi_metrics, simulate_wifi_clients, check_wifi_health

def run_test():
    print("🚀 Démarrage du test de monitoring WiFi...")

    # 1. Création d'un point d'accès de test s'il n'existe pas
    ap, created = AccessPoint.objects.get_or_create(
        mac_adresse="AA:BB:CC:DD:EE:FF",
        defaults={
            'nom': "AP-TEST-LAB",
            'adresse_ip': "192.168.10.50",
            'modele': "Ubiquiti UniFi 6 Pro",
            'statut': 'up'
        }
    )
    if created:
        print(f"✅ AP de test créé : {ap.nom}")
    else:
        print(f"ℹ️ AP de test existant : {ap.nom}")

    # 2. Exécution des tâches de simulation
    print("📊 Collecte des métriques...")
    res_metrics = collect_wifi_metrics()
    print(f"   -> {res_metrics}")

    print("👥 Simulation des clients...")
    res_clients = simulate_wifi_clients()
    print(f"   -> {res_clients}")

    print("🚨 Vérification de la santé...")
    res_health = check_wifi_health()
    print(f"   -> {res_health}")

    print("\n✨ Test terminé ! Vous pouvez maintenant voir les données sur http://localhost:8000/wifi/dashboard/")

if __name__ == "__main__":
    run_test()
