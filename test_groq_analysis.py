import os
import django
import sys
import logging

# Configuration de Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from monitoring.models import Incident
from aiengine.orchestrator import analyser_incident_ia, sauvegarder_resultat_ia

def test_analysis():
    logging.basicConfig(level=logging.INFO)
    incident = Incident.objects.first()
    if not incident:
        print("Aucun incident")
        return

    print(f"Test sur incident #{incident.id}")
    analyse_brute = analyser_incident_ia(incident, provider='groq')
    print("Analyse Brute:")
    print(analyse_brute)
    
    obj = sauvegarder_resultat_ia(incident, analyse_brute)
    if obj:
        print("SAUVEGARDE REUSSIE")
    else:
        print("SAUVEGARDE ECHOUEE")

if __name__ == "__main__":
    test_analysis()
