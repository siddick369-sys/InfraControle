"""
reports/views.py — Vues pour les rapports exécutifs
RapportExecutif reste dans monitoring.models
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

from monitoring.models import RapportExecutif


@login_required
def rapports_liste(request):
    """Liste de tous les rapports exécutifs."""
    rapports = RapportExecutif.objects.all().order_by('-cree_le')
    
    context = {
        'rapports': rapports,
    }
    return render(request, 'reports/rapports.html', context)


@login_required
def rapport_detail(request, pk):
    """Détail d'un rapport exécutif."""
    rapport = get_object_or_404(RapportExecutif, pk=pk)
    
    context = {
        'rapport': rapport,
    }
    return render(request, 'reports/rapport_detail.html', context)


@login_required
def generer_rapport(request):
    """Génère un nouveau rapport exécutif."""
    from reports.services.pdf_generator import generer_rapport_executif
    import logging
    logger = logging.getLogger('monitoring')
    
    jours = int(request.GET.get('jours', 7))
    date_fin = timezone.now().date()
    date_debut = date_fin - timedelta(days=jours)
    
    logger.info(f"[REPORT] Demande de génération : {date_debut} -> {date_fin}")
    
    try:
        rapport = generer_rapport_executif(date_debut, date_fin)
        logger.info(f"[REPORT] Succès ! ID={rapport.id}")
        return JsonResponse({
            'success': True,
            'rapport_id': rapport.id,
            'message': f'Rapport généré pour la période {date_debut} → {date_fin}'
        })
    except Exception as e:
        import traceback
        logger.error(f"[REPORT] Échec : {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc() if settings.DEBUG else None
        }, status=500)


@login_required
def telecharger_pdf(request, pk):
    """Télécharge le PDF d'un rapport."""
    rapport = get_object_or_404(RapportExecutif, pk=pk)
    
    if not rapport.fichier_pdf:
        # Générer le PDF s'il n'existe pas
        from reports.services.pdf_generator import generer_pdf_rapport
        generer_pdf_rapport(rapport)
    
    if rapport.fichier_pdf:
        response = HttpResponse(
            rapport.fichier_pdf.read(),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="rapport_{rapport.date_debut}_{rapport.date_fin}.pdf"'
        return response
    
    return HttpResponse("Erreur: PDF non disponible", status=500)
