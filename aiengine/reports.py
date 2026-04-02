from django.utils import timezone
from datetime import timedelta

from monitoring.models import Incident, EquipementReseau


def construire_contexte_hebdomadaire():
    fin = timezone.now()
    debut = fin - timedelta(days=7)

    incidents = Incident.objects.filter(
        date_debut__range=(debut, fin)
    )

    equipements = EquipementReseau.objects.filter(
        incident__in=incidents
    ).distinct()

    contexte = {
        "periode": {
            "debut": debut.isoformat(),
            "fin": fin.isoformat(),
        },
        "incidents": [
            {
                "titre": i.titre,
                "statut": i.statut,
                "equipement": i.equipement.nom,
            }
            for i in incidents
        ],
        "nb_incidents": incidents.count(),
        "nb_equipements": equipements.count(),
    }

    return contexte, debut.date(), fin.date()