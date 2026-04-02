from django.urls import re_path
from monitoring.consumers import *

websocket_urlpatterns = [
    re_path(r"ws/terminal/(?P<equipement_id>\d+)/$", SSHConsumer.as_asgi()),
]


from monitoring.models import EquipementReseau
from monitoring.smart_monitor import analyser_un_equipement

# Ajoutez .first() à la fin pour avoir l'objet et non la liste
mon_pc = EquipementReseau.objects.filter(adresse_ip="10.22.59.98").first()

if mon_pc:
    resultat = analyser_un_equipement(mon_pc)
    print(resultat)
else:
    print("Équipement non trouvé.")
