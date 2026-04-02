import os
import django
import sys

# Configuration de Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from monitoring.models import Incident
from aiengine.orchestrator import analyser_incident_ia

def test():
    # Prendre le dernier incident ouvert
    incident = Incident.objects.filter(statut="ouvert").last()
    if not incident:
        incident = Incident.objects.last()
        
    res = f"Test sur incident ID: {incident.id} - {incident.titre}\n"
    
    # Simuler le fonctionnement de la tache Celery
    try:
        analyse = analyser_incident_ia(incident)
        res += "RESTULTAT BRUT ORCHESTRATEUR:\n"
        res += str(analyse)
    except Exception as e:
        res += f"Erreur fatale: {e}\n"
        
    with open("check_ai_result.txt", "w", encoding="utf-8") as f:
        f.write(res)

if __name__ == "__main__":
    test()
