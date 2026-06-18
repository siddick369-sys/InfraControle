"""
remediation/services/engine.py — Exécution des actions correctives.
"""
import logging
import subprocess
from monitoring.models import EquipementReseau
from ..models import ActionRemediation, HistoriqueRemediation

logger = logging.getLogger('monitoring')

def executer_remediation(equipement_id, action_id, incident=None):
    """Exécute une commande de remédiation localement (pour démo Windows)."""
    equipement = EquipementReseau.objects.get(id=equipement_id)
    action = ActionRemediation.objects.get(id=action_id)
    
    logger.info(f"Exécution de la remédiation '{action.nom}' en local (démo)")
    
    statut = 'echec'
    sortie = ""
    try:
        # Exécution réelle locale pour démonstration sur le PC de test (Windows)
        # On utilise subprocess.run
        result = subprocess.run(
            action.script,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        sortie = result.stdout if result.returncode == 0 else result.stderr
        statut = 'succes' if result.returncode == 0 else 'echec'
        
        if not sortie.strip():
            sortie = "Commande exécutée avec succès (aucune sortie standard)." if statut == 'succes' else f"Échec: code de retour {result.returncode}"
    except Exception as e:
        sortie = f"Erreur d'exécution locale: {str(e)}"
    
    # Création historique
    HistoriqueRemediation.objects.create(
        equipement=equipement,
        incident=incident,
        action=action,
        statut=statut,
        sortie_log=sortie
    )
    return True

def restart_service(equipement, service_name):
    """Redémarre un service spécifique."""
    pass

def restart_container(container_id):
    """Redémarre un conteneur via Docker API."""
    pass
