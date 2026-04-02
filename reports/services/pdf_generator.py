"""
reports/services/pdf_generator.py — Génération de rapports PDF et synthèse IA via ReportLab.
"""
import logging
from django.utils import timezone
from aiengine.pdf import generer_pdf_reportlab
from monitoring.models import Incident, RapportExecutif

logger = logging.getLogger('monitoring')

from reports.services.ai_report import generer_rapport_groq

def generer_rapport_executif(date_debut, date_fin):
    """
    Crée un objet RapportExecutif et prépare le PDF via ReportLab.
    """
    # 1. Collecte des données pour la période (Simplifiée pour la base, l'IA fait les détails)
    incidents = Incident.objects.filter(date_debut__range=[date_debut, date_fin])
    nb_incidents = incidents.count()
    nb_equipements_impactes = incidents.values('equipement').distinct().count()
    
    # 2. Synthèse simplifiée de base
    resume_global = f"Rapport automatique pour la période du {date_debut} au {date_fin}.\n" \
                    f"Total incidents : {nb_incidents}.\n" \
                    f"Équipements réseaux impactés : {nb_equipements_impactes}."
                    
    # 3. Génération du contenu textuel complet via Groq IA
    analyse_ia_texte = generer_rapport_groq(date_debut, date_fin)
    
    # 4. Création de l'instance
    rapport = RapportExecutif.objects.create(
        date_debut=date_debut,
        date_fin=date_fin,
        resume_global=resume_global,
        nb_incidents=nb_incidents,
        nb_equipements_impactes=nb_equipements_impactes,
        analyse_ia=analyse_ia_texte # Le markdown généré
    )
    
    # 5. Génération du PDF via ReportLab (Optionnel / En arrière-plan si besoin d'attendre)
    try:
        generer_pdf_reportlab(rapport)
        logger.info(f"Rapport PDF (ReportLab) généré pour ID {rapport.pk}")
    except Exception as e:
        logger.error(f"Erreur génération PDF ReportLab pour rapport {rapport.pk}: {e}")
    
    return rapport
