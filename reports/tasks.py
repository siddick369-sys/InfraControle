"""
reports/tasks.py — Tâches programmées pour les rapports.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .services.pdf_generator import generer_rapport_executif

@shared_task(name='reports.tasks.hebdo_executif')
def generer_rapport_hebdomadaire():
    """Génère automatiquement le rapport des 7 derniers jours."""
    date_fin = timezone.now().date()
    date_debut = date_fin - timedelta(days=7)
    
    rapport = generer_rapport_executif(date_debut, date_fin)
    return f"Rapport ID {rapport.id} généré avec succès."
