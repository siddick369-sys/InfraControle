from django.http import HttpResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from django.views.decorators.csrf import csrf_exempt
# monitoring/views.py
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from monitoring.models import (
    EquipementReseau,
    StatReseau,
    Incident,
    Maintenance,
)

def equipement_metrics_api(request, equipement_id):
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)

    stats = (
        StatReseau.objects
        .filter(equipement=equipement)
        .order_by("date_releve")[:200]
    )

    incidents = Incident.objects.filter(
        equipement=equipement
    ).order_by("date_debut")

    maintenances = Maintenance.objects.filter(
        equipement=equipement
    )

    data = {
        "labels": [s.date_releve.strftime("%H:%M") for s in stats],
        "cpu": [s.cpu_usage for s in stats],
        "ram": [s.ram_usage for s in stats],
        "disk": [s.disk_usage for s in stats],

        "incidents": [
            {
                "time": i.date_debut.strftime("%H:%M"),
                "titre": i.titre,
                "niveau": i.niveau,
            }
            for i in incidents
        ],

        "maintenance": [
            {
                "start": m.debut.strftime("%H:%M"),
                "end": m.fin.strftime("%H:%M"),
            }
            for m in maintenances
        ],
    }

    return JsonResponse(data)