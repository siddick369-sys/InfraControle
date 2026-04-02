

from django.utils import timezone
from monitoring.models import Maintenance

def maintenance_globale(request):
    maintenances = Maintenance.objects.filter(
        active=True,
        debut__lte=timezone.now(),
        fin__gte=timezone.now()
    )
    return {"maintenances_actives": maintenances}