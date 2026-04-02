from django.utils import timezone
from monitoring.models import Maintenance
from monitoring.models import Maintenance, Incident

def est_en_maintenance(equipement):
    """
    Un équipement est en maintenance si :
    - une maintenance active existe
    ET
    - au moins un incident est encore ouvert
    """
    maintenance_active = Maintenance.objects.filter(
        equipement=equipement,
        active=True
    ).exists()

    incident_ouvert = Incident.objects.filter(
        equipement=equipement,
        statut="ouvert"
    ).exists()

    return maintenance_active and incident_ouvert