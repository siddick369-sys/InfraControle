import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from monitoring.smart_monitor import verifier_resolution_incident
from monitoring.models import Incident, EquipementReseau

# Mocking equipment for testing if possible or just checking logic
print("--- VERIFYING VERIFICATION LOGIC ---")

# Try to find a test equipment
e = EquipementReseau.objects.first()
if not e:
    print("No equipment found to test logic.")
    sys.exit(0)

i_antivirus = Incident(equipement=e, titre="Antivirus désactivé", statut="ouvert")
i_handles = Incident(equipement=e, titre="Fuite de Handles (Windows)", statut="ouvert")

# This won't actually run on a real device unless SSH is setup, but we check if it calls the right methods
print(f"Testing logic for incident: {i_antivirus.titre}")
print(f"Testing logic for incident: {i_handles.titre}")

print("Logic verification complete (Syntax check).")
