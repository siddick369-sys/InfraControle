from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from core.models import JournalActivite
@shared_task
def purge_old_logs():
    """
    Supprime les logs BDD de plus de 90 jours.
    Note: Les fichiers logs (monitoring.log) sont gérés automatiquement 
    par la rotation dans settings.py (backupCount=90).
    """
    limite = timezone.now() - timedelta(days=90)
    
    # Nettoyage BDD
    deleted, _ = JournalActivite.objects.filter(date_action__lt=limite).delete()
    
    print(f"[Celery] 🔁 Purge BDD effectuée : {deleted} entrées supprimées.")
    # Le fichier log se nettoie tout seul lors de l'écriture des logs par Django
    
    return deleted
from celery import shared_task
from django.contrib.auth.models import User

@shared_task
def purge_comptes_supprimes():
    from django.utils import timezone
    from core.models import Profil
    comptes = Profil.objects.filter(est_gelé=True, date_suppression_programmee__lte=timezone.now())

    for profil in comptes:
        user = profil.user
        user.delete()
        print(f"[Purge] Compte {user.username} supprimé définitivement.")