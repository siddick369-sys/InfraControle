import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging

from monitoring.utils.maintenance import est_en_maintenance

logger = logging.getLogger("monitoring.alerts")


def _send_health_alert_email(stat):
    """
    [DÉSACTIVÉ] - La logique d'envoi est centralisée dans la tâche de résumé.
    """
    logger.info(f"[EMAIL SKIP] Envoi direct désactivé pour {stat.equipement.nom}")
    pass

def envoyer_alerte_health(stat):
    equipement = stat.equipement

    # ⛔ 1️⃣ Maintenance → JAMAIS d’alerte
    if est_en_maintenance(equipement):
        logger.info(f"[MAINTENANCE] {equipement.nom} — alerte bloquée")
        return
    
    if not equipement.alertes_email_active:
        logger.info(f"[ALERTE BLOQUÉE] Alertes désactivées pour {equipement.nom}")
        return

    # ⛔ 2️⃣ Score OK → rien à faire
    if stat.health_score is None or stat.health_score >= 50:
        return

    # ⏳ 3️⃣ Cooldown (Géré par la tâche de résumé via Incident)
    # On crée l'incident s'il n'existe pas déjà en statut ouvert
    from monitoring.models import Incident
    
    incident, created = Incident.objects.get_or_create(
        equipement=equipement,
        titre=f"Problème de santé (Score: {stat.health_score}%)",
        statut="ouvert",
        defaults={
            "description": f"Le score de santé de l'équipement est descendu à {stat.health_score}%.",
            "niveau": "critique",
            "categorie": "sante",
            "cree_par": equipement.cree_par,
        }
    )

    if created:
        logger.warning(f"[INCIDENT SANTE] Nouvel incident créé pour {equipement.nom}")
    else:
        logger.debug(f"[INCIDENT SANTE] Incident déjà ouvert pour {equipement.nom}")
