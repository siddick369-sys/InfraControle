from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ActionRemediation, HistoriqueRemediation, AnomalieRegle
from .services.engine import executer_remediation

@login_required
def remediation_dashboard(request):
    actions = ActionRemediation.objects.all()
    regles = AnomalieRegle.objects.all()
    historique = HistoriqueRemediation.objects.all().order_by('-date_action')[:20]
    return render(request, 'remediation/dashboard.html', {
        'actions': actions,
        'regles': regles,
        'historique': historique
    })

@login_required
def lancer_remediation(request, action_id, equipement_id):
    executer_remediation(equipement_id, action_id)
    return redirect('remediation:dashboard')

@login_required
def ajouter_regle(request):
    if request.method == 'POST':
        nom = request.POST.get('nom')
        cmd_detection = request.POST.get('cmd_detection')
        cmd_remediation = request.POST.get('cmd_remediation')
        os_cible = request.POST.get('os_cible', 'linux')
        
        if nom and cmd_detection and cmd_remediation:
            AnomalieRegle.objects.create(
                nom=nom,
                cmd_detection=cmd_detection,
                cmd_remediation=cmd_remediation,
                os_cible=os_cible
            )
            return JsonResponse({'status': 'success', 'message': 'Règle ajoutée avec succès.'})
        return JsonResponse({'status': 'error', 'message': 'Veuillez remplir tous les champs.'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=405)
