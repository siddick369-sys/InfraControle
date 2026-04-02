import os
import django
import sys
from datetime import timedelta
from unittest.mock import patch

# Charger Django
sys.path.append('c:/Users/USER/Desktop/DRH/InfraContol')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from monitoring.models import EquipementReseau, Maintenance, Incident
from monitoring.smart_monitor import analyser_un_equipement
from monitoring.tasks import verifier_statut_equipements
from django.utils import timezone
from django.contrib.auth.models import User

def test_maintenance_logic():
    print("=== TEST LOGIQUE MAINTENANCE ===")
    
    eq = EquipementReseau.objects.first()
    user = User.objects.first()
    
    if not eq or not user:
        print("[WARN] Aucun equipement ou utilisateur trouve.")
        return

    # Nettoyage initial des maintenances actives
    Maintenance.objects.filter(equipement=eq, active=True).update(active=False)

    # 1. Test Skip Monitoring
    print("\n[1] Test Skip Monitoring en maintenance")
    Maintenance.objects.create(
        equipement=eq, debut=timezone.now(), fin=timezone.now()+timedelta(hours=1), active=True, raison="Test"
    )
    
    res = analyser_un_equipement(eq)
    if res.get('statut') == 'maintenance':
        print("[OK] L'analyse a bien ignore l'equipement en maintenance.")
    else:
        print(f"[FAIL] L'analyse n'a pas ignore l'equipement. Res: {res}")

    # 2. Test Auto-Maintenance sur echec critique
    print("\n[2] Test Auto-Maintenance sur echec critique de remediation")
    # On enleve la maintenance manuelle
    Maintenance.objects.filter(equipement=eq, active=True).update(active=False)
    
    # On simule un incident critique qui echoue
    with patch('monitoring.smart_monitor.collecter_ping_jitter', return_value=(10, 2, 0)):
        with patch('monitoring.smart_monitor.collecter_performance_ssh', return_value={'cpu_usage': 99}):
            with patch('monitoring.smart_monitor.appliquer_remediation', return_value=True): # Remediation tentee
                with patch('monitoring.smart_monitor.verifier_resolution_incident', return_value=False): # Mais echouee
                    analyser_un_equipement(eq)
    
    # Verifier si une maintenance automatique a ete creee
    auto_maint = Maintenance.objects.filter(equipement=eq, active=True, raison__icontains="automatique").exists()
    if auto_maint:
        print("[OK] Maintenance automatique creee avec succes apres echec critique.")
    else:
        print("[FAIL] Aucune maintenance automatique n'a ete creee.")

    # 3. Test Skip Status Check in Tasks
    print("\n[3] Test Skip Status Check dans les taches Celery")
    with patch('monitoring.tasks.subprocess.run') as mock_ping:
        verifier_statut_equipements()
        # Si eq est en maintenance, mock_ping ne devrait pas etre appele pour son IP
        # (Sauf si d'autres equipements existent, donc on check les appels)
        called_ips = [args[0][2] if len(args[0]) > 2 else "" for args, kwargs in mock_ping.call_args_list]
        if eq.adresse_ip not in called_ips:
            print(f"[OK] L'IP {eq.adresse_ip} a ete ignoree par verifier_statut_equipements.")
        else:
            print(f"[FAIL] L'IP {eq.adresse_ip} a ete scannée malgre la maintenance.")

    # Nettoyage
    Maintenance.objects.filter(equipement=eq, active=True).update(active=False)
    print("\nTests termines.")

if __name__ == "__main__":
    test_maintenance_logic()
