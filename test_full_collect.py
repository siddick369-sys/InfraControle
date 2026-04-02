import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "InfraContol.settings")
django.setup()

from monitoring.models import EquipementReseau
from monitoring.stat_collector import collecter_stat_complete

# On teste sur le premier équipement
eq = EquipementReseau.objects.first()
if eq:
    print(f"Test global pour {eq.nom}...")
    stat = collecter_stat_complete(eq)
    if stat:
        print(f"Stat enregistrée : CPU={stat.cpu_usage}%, RAM={stat.ram_usage}%, Temp={stat.temperature_c}°C")
    else:
        print("Échec de la collecte.")
else:
    print("Aucun équipement.")
