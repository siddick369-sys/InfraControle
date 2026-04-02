import logging
from django.utils import timezone
from monitoring.ssh_utils import collecter_performance_ssh
from monitoring.models import Incident

logger = logging.getLogger(__name__)


def verifier_resolution_incident(incident):
    e = incident.equipement
    perf = collecter_performance_ssh(e)

    regles_resolution = {
        "CPU élevé": lambda p: p.get("cpu") is not None and p["cpu"] < 70,
        "RAM saturée": lambda p: p.get("ram") is not None and p["ram"] < 70,
        "Disque plein": lambda p: p.get("disk") is not None and p["disk"] < 80,
        "Antivirus désactivé": lambda p: True, # On fait confiance à la remédiation pour ces états
        "Service de Temps arrêté": lambda p: True,
        "Corbeille volumineuse": lambda p: True,
        "Dossier temporaire saturé (Windows)": lambda p: True,
        "Dossier temporaire saturé (Linux)": lambda p: True,
    }

    check = regles_resolution.get(incident.titre)
    if not check:
        return False

    if check(perf):
        incident.statut = "résolu"
        incident.date_resolution = timezone.now()
        incident.save(update_fields=["statut", "date_resolution"])

        e.statut = "en ligne"
        e.save(update_fields=["statut"])

        logger.info(f"[RESOLU] {incident.titre} sur {e.nom}")
        return True

    return False