"""
monitoring/services/network_service.py — Logique métier pour la supervision réseau.
"""
import logging
from monitoring.models import EquipementReseau, StatReseau, Incident

logger = logging.getLogger('monitoring')

def verifier_sante_equipement(equipement):
    """Effectue un ping et récupère les stats de base."""
    # Simulation de ping
    logger.info(f"Vérification de {equipement.adresse_ip}")
    # Logique réelle ici (import d'un utilitaire de ping)
    pass

def creer_incident_si_besoin(equipement, titre, niveau, description):
    """Crée un incident s'il n'en existe pas déjà un ouvert pour ce problème."""
    incident, created = Incident.objects.get_or_create(
        equipement=equipement,
        titre=titre,
        statut='ouvert',
        defaults={
            'niveau': niveau,
            'description': description
        }
    )
    return incident, created
