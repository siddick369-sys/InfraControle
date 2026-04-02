import os
import sys
import django
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "InfraContol.settings")
django.setup()

# Set up logging to console
logger = logging.getLogger('monitoring')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

from monitoring.models import EquipementReseau
from monitoring.smart_monitor import analyser_un_equipement

eq = EquipementReseau.objects.first()
if eq:
    print(f"Testing equipement: {eq.nom} ({eq.adresse_ip})")
    print("Testing analyser_un_equipement...")
    res = analyser_un_equipement(eq)
    print("Result:", res)
else:
    print("No EquipementReseau found in DB.")
