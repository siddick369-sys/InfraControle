# aiengine/orchestrator.py
import json
import logging
from django.utils import timezone

from monitoring.models import Incident
from aiengine.client import appeler_ia
from aiengine.context import construire_contexte_incident
from aiengine.prompts import (
    prompt_cause_racine,
    prompt_remediation,
    prompt_formation_junior,
)

logger = logging.getLogger("ai")


# ============================================================
# 🧠 ORCHESTRATEUR PRINCIPAL
# ============================================================
def analyser_incident_ia(
    incident: Incident,
    *,
    analyse_cause=True,
    plan_remediation=True,
    mode_formation=False,
    rapport_executif=False,
    modele="llama3.1:latest",
    provider=None
):
    """
    Orchestrateur IA central Infracontrole
    """

    logger.info(f"[IA] Analyse incident #{incident.id} (provider={provider})")

    # ==========================
    # 🧾 CONTEXTE
    # ==========================
    contexte = construire_contexte_incident(incident)

    resultats = {
        "incident_id": incident.id,
        "analyse_effectuee_le": timezone.now().isoformat(),
    }

    # ==========================
    # 🧠 CAUSE RACINE
    # ==========================
    if analyse_cause:
        try:
            prompt = prompt_cause_racine(contexte)
            reponse = appeler_ia(modele, prompt, provider=provider)
            resultats["cause_racine"] = _safe_json(reponse)
        except Exception as e:
            logger.error("[IA] Erreur cause racine", exc_info=True)
            resultats["cause_racine"] = {"erreur": str(e)}

    # ==========================
    # 🛠 PLAN REMÉDIATION
    # ==========================
    if plan_remediation:
        try:
            prompt = prompt_remediation(contexte)
            reponse = appeler_ia(modele, prompt, provider=provider)
            resultats["remediation"] = _safe_json(reponse)
        except Exception as e:
            logger.error("[IA] Erreur remédiation", exc_info=True)
            resultats["remediation"] = {"erreur": str(e)}

    # ==========================
    # 🎓 MODE FORMATION
    # ==========================
    if mode_formation:
        try:
            prompt = prompt_formation_junior(contexte)
            reponse = appeler_ia(modele, prompt, provider=provider)
            resultats["formation"] = _safe_json(reponse)
        except Exception as e:
            logger.error("[IA] Erreur formation", exc_info=True)
            resultats["formation"] = {"erreur": str(e)}

    # ==========================
    # 📊 RAPPORT EXÉCUTIF
    # ==========================
    
    # ==========================
    # 💾 PERSISTENCE
    # ==========================
    incident.save()

    return resultats


# ============================================================
# 🧰 UTILITAIRE JSON SAFE
# ============================================================
def _safe_json(reponse):
    """
    Sécurise les réponses IA (JSON strict attendu)
    """
    if not reponse:
        return {"erreur": "Pas de réponse de l'IA"}

    if isinstance(reponse, dict):
        return reponse

    try:
        start = reponse.find("{")
        end = reponse.rfind("}")
        if start != -1 and end != -1:
            json_str = reponse[start:end+1]
        else:
            json_str = reponse
        return json.loads(json_str.strip())
    except Exception as e:
        logger.error(f"[IA] Échec parsing JSON: {e} | Raw: {reponse[:200]}")
        return {
            "raw": reponse,
            "erreur": f"JSON invalide: {str(e)}"
        }

def sauvegarder_resultat_ia(incident, analyse):
    """
    Transforme le dictionnaire brut de l'orchestrateur en objet AnalyseIA en base.
    """
    from monitoring.models import AnalyseIA
    
    if not analyse:
        logger.warning(f"[IA] Tentative de sauvegarde d'une analyse vide pour incident #{incident.id}")
        return None

    cause_data = analyse.get("cause_racine", {})
    remed_data = analyse.get("remediation", {})
    form_data = analyse.get("formation", {})

    # Validation minimale : il faut au moins une cause principale
    if not cause_data.get("cause_principale") or "erreur" in cause_data:
        logger.warning(f"[IA] Données insuffisantes pour incident #{incident.id}: {cause_data}")
        return None

    # Mapping de la confiance (robuste)
    conf_raw = str(cause_data.get("niveau_confiance", "")).lower().strip()
    conf_map = {
        "faible": 0.3, "low": 0.3,
        "moyen": 0.6, "medium": 0.6,
        "eleve": 0.9, "élevé": 0.9, "high": 0.9, "haut": 0.9
    }
    conf_val = conf_map.get(conf_raw, 0.5)

    # Solution humaine
    plan = remed_data.get("plan_remediation", [])
    if isinstance(plan, list):
        solution_txt = "\n".join([f"{step.get('etape')}. {step.get('action')}" for step in plan])
    else:
        solution_txt = str(plan)

    # Commandes auto
    commands = []
    if isinstance(plan, list):
        commands = [step.get('commande') for step in plan if step.get('type') == 'automatique' and step.get('commande')]
    remediation_auto_txt = "; ".join(commands) if commands else ""

    # Persistence
    try:
        AnalyseIA.objects.filter(incident=incident).delete()
        obj = AnalyseIA.objects.create(
            incident=incident,
            cause_racine=cause_data.get("cause_principale"),
            categorie=cause_data.get("categorie", "infra"),
            solution_humaine=solution_txt or "Aucune étape spécifique proposée.",
            remediation_auto=remediation_auto_txt,
            explication_simple=form_data.get("explication_simple", "Pas d'explication simplifiée disponible."),
            confiance=conf_val,
        )
        logger.info(f"[IA] Analyse incident #{incident.id} sauvegardée avec succès.")
        return obj
    except Exception as e:
        logger.error(f"[IA] Erreur lors de la sauvegarde DB pour incident #{incident.id}: {e}")
        return None
