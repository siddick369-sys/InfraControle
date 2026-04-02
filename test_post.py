import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from monitoring.models import Incident

def test():
    c = Client()
    # auth 
    user = User.objects.filter(is_superuser=True).first()
    if user:
        c.force_login(user)

    incident = Incident.objects.filter(statut="ouvert").last()
    if not incident:
        incident = Incident.objects.last()

    print(f"Test requete POST sur /monitoring/incidents/{incident.id}/analyse-ia/")
    response = c.post(f"/monitoring/incidents/{incident.id}/analyse-ia/")
    print(f"Status: {response.status_code}")
    print(f"Content: {response.content.decode('utf-8')}")

if __name__ == "__main__":
    test()
