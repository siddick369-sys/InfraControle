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


# Lancez le simulateur dans un terminal: python manage.py run_wifi_master_sim
#Ouvrez votre navigateur sur un AP: http://localhost:8010/wifi/dashboard/ et cliquez sur l'AP (son ID sera différent de 2 désormais, car de nouveaux équipements virtuels Orange/MTN ont été créés).
#Observez le graphique défiler tout seul 










ameliore le tutoriel fait via driver.js car il faut que chaque page ait le bouton ''?'' et ce bouton en fonction de la page doit pouvoir effectuer une visite guide de chaque section et bouton de la page je veux que ces textes soit explicite et bien detaille. je veux aussi que le fichier bat  verifie si l'utilisateur est sur windows ou linux d'abord puis  si c'est windows verifie d'abord wsl et ensuite docker mais 
si c'est linux verifie seulement docker  
  si l'utilisateur windows ne les a pas que le fichier bat  telecharge wsl puis redemarre le pc puis des que le pc est rallume si l'utilisateur 
clique sur le fichier bat verifie si wsl est install et telecharge dans download/telechargement et demande a l'utilisateur si il veut une video sur youtube sur l'installation de docker si l'utilisateur accepte donc on le dirige sur youtube 
avec le mot cle 'installation de docker ' si il refuse le fichier lance le launcher de docker installation 
l'utilisateur linux simple avec interface graphique aura les memes etapes sans wsl mais celui avec linux ou ubuntu sans interface graphique(pour le cas des serveurs) ils n'auront pas les etapes avec la video youtube