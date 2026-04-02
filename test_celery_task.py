import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from monitoring.models import Incident
from aiengine.tasks import analyser_incident_task

def test():
    incident = Incident.objects.filter(statut="ouvert").last()
    if not incident:
        incident = Incident.objects.last()
        
    print(f"Lancement de la tache pour {incident.id}")
    res = analyser_incident_task(incident.id)
    print(f"Resultat de la tache: {res}")

if __name__ == "__main__":
    test()
