from datetime import timezone
import json
from celery import shared_task
from .context import construire_contexte_incident
from .client import appeler_ia
from monitoring.models import Incident, AnalyseIA
from .orchestrator import analyser_incident_ia
import logging
logger = logging.getLogger("ai")
# aiengine/tasks.py
# aiengine/tasks.py
@shared_task(
    name="aiengine.tasks.analyser_incident",
    time_limit=1200,
    soft_time_limit=1000,
)
def analyser_incident_task(incident_id):
    from monitoring.models import Incident, AnalyseIA
    from .orchestrator import analyser_incident_ia, sauvegarder_resultat_ia
    import logging

    logger = logging.getLogger("ai")

    try:
        incident = Incident.objects.get(id=incident_id)

        # ⛔ Anti-doublon
        if hasattr(incident, "analyse_ia"):
            return "Analyse déjà existante"

        # Marqueur UI
        incident.analyse_ia_en_cours = True
        incident.save(update_fields=["analyse_ia_en_cours"])

        analyse = analyser_incident_ia(incident, provider='ollama')
        if not analyse:
            return "Échec analyse IA"

        sauvegarder_resultat_ia(incident, analyse)

        return "Analyse IA terminée (Ollama)"

    except Exception as e:
        logger.error(f"[IA] Erreur incident {incident_id}: {e}", exc_info=True)
        return "Erreur IA"

    finally:
        Incident.objects.filter(id=incident_id).update(
            analyse_ia_en_cours=False
        )
        
@shared_task(name="aiengine.tasks.analyser_incidents_critiques")
def analyser_incidents_critiques():
    """
    Analyse IA automatique des incidents critiques ouverts
    """

    incidents = Incident.objects.filter(
        statut="ouvert",
        niveau="critique"
    )

    total = 0

    for incident in incidents:
        if not hasattr(incident, "analyse_ia"):
            analyser_incident_task.delay(incident.id)
            total += 1

    logger.info(f"[IA] Analyses critiques lancées: {total}")
    return total
@shared_task(name="aiengine.tasks.analyser_incidents_recurrents")
def analyser_incidents_recurrents():
    """
    Analyse IA des incidents récurrents (>= 3 occurrences)
    """

    incidents = Incident.objects.filter(statut="ouvert")
    total = 0

    for incident in incidents:
        occurrences = Incident.objects.filter(
            equipement=incident.equipement,
            titre=incident.titre
        ).count()

        if occurrences >= 3 and not hasattr(incident, "analyse_ia"):
            analyser_incident_task.delay(incident.id)
            total += 1

    logger.info(f"[IA] Analyses récurrentes lancées: {total}")
    return total


@shared_task(name="aiengine.tasks.analyse_preventive_globale")
def analyse_preventive_globale():
    """
    Analyse IA préventive hebdomadaire
    (prépare rapports / recommandations)
    """

    incidents = Incident.objects.filter(
        statut="résolu",
        date_resolution__gte=timezone.now() - timezone.timedelta(days=7)
    )

    total = 0

    for incident in incidents:
        if not hasattr(incident, "analyse_ia"):
            analyser_incident_task.delay(incident.id)
            total += 1

    logger.info(f"[IA] Analyse préventive lancée: {total}")
    return total
from celery import shared_task
from monitoring.models import RapportExecutif
from .reports import construire_contexte_hebdomadaire
from aiengine.utils import generer_analyse_executive
from .factory import generer_pdf


@shared_task(name="monitoring.tasks.generer_rapport_executif")
def generer_rapport_executif(mode_pdf="auto"):
    """
    Génère un rapport exécutif + PDF
    mode_pdf = auto | exec | secours
    """

    # 🧠 Construction du contexte
    contexte, debut, fin = construire_contexte_hebdomadaire()

    # 🤖 Analyse IA
    analyse = generer_analyse_executive(contexte)

    # 🧾 Création rapport DB
    rapport = RapportExecutif.objects.create(
        date_debut=debut,
        date_fin=fin,
        resume_global="Analyse générée par IA",
        analyse_ia=analyse,
        nb_incidents=contexte.get("nb_incidents", 0),
        nb_equipements_impactes=contexte.get("nb_equipements", 0),
        genere=False,
    )

    # 📄 Génération PDF (hybride ReportLab / Weasy)
    generer_pdf(rapport, mode=mode_pdf)

    rapport.genere = True
    rapport.save(update_fields=["genere"])

    return rapport.id