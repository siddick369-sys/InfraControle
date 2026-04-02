import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import SessionFormation, MessageInvestigation
from monitoring.models import Incident, AnalyseIA, EquipementReseau
from aiengine.client import appeler_ia
from aiengine.prompts import (
    prompt_sandbox_briefing,
    prompt_sandbox_chat,
    prompt_sandbox_evaluation,
    prompt_generate_fictitious_incident
)
from aiengine.orchestrator import _safe_json

@login_required
def generer_scenario_ia_view(request):
    """Génère un scénario d'entraînement fictif via IA si aucun incident réel n'existe."""
    equipements = EquipementReseau.objects.filter(actif=True)
    if not equipements.exists():
        messages.warning(request, "Impossible de générer un test : aucun équipement actif n'a été trouvé.")
        return redirect('training:dashboard')
        
    # Préparer les données des équipements pour l'IA
    equip_data = []
    for e in equipements:
        equip_data.append({
            "id": e.id,
            "nom": e.nom,
            "type": e.type_equipement,
            "ip": e.adresse_ip
        })
        
    try:
        prompt = prompt_generate_fictitious_incident(equip_data)
        reponse_ia = appeler_ia(model="llama-3.3-70b-versatile", prompt=prompt)
        data = _safe_json(reponse_ia)
        
        if not data or "erreur" in data or not data.get('equipement_id'):
            messages.error(request, "L'IA a rencontré un problème lors de la création du scénario. Merci de réessayer.")
            return redirect('training:dashboard')
            
        # Création de l'incident fictif
        equipement = get_object_or_404(EquipementReseau, id=data.get('equipement_id'))
        
        incident = Incident.objects.create(
            equipement=equipement,
            titre=data.get('titre', 'Anomalie simulée'),
            description=data.get('description', 'Incident généré par IA pour entraînement.'),
            niveau=data.get('niveau', 'avertissement'),
            categorie=data.get('categorie', 'autre'),
            statut='résolu',
            date_resolution=timezone.now()
        )
        
        # Création de l'analyse associée
        AnalyseIA.objects.create(
            incident=incident,
            cause_racine=data.get('cause_racine', 'Cause non déterminée'),
            categorie=data.get('categorie', 'infra'),
            solution_humaine=data.get('solution_humaine', 'Action non spécifiée'),
            explication_simple=data.get('explication_simple', 'Simulation EdTech'),
            confiance=1.0
        )
        messages.success(request, f"Nouveau test généré avec succès : {incident.titre}")
        
    except Exception as e:
        print(f"Erreur génération IA: {e}")
        messages.error(request, f"Erreur système lors de la génération : {str(e)}")
        
    return redirect('training:dashboard')

def _get_incident_context(incident):
    """Récupère le contexte historique de l'incident pour la Sandbox."""
    try:
        analyse = incident.analyseia
        return {
            "equipement": incident.equipement.nom,
            "ip": incident.equipement.adresse_ip,
            "type": incident.equipement.type_equipement,
            "titre_panne": incident.titre,
            "description": incident.description,
            "cause_reelle": analyse.cause_racine,
            "solution_historique": analyse.solution_humaine,
            "remediation_auto": analyse.remediation_auto
        }
    except Exception:
        return {
            "equipement": incident.equipement.nom,
            "titre_panne": incident.titre,
            "description": incident.description,
            "cause_reelle": "Inconnue",
            "solution_historique": "Intervention manuelle requise."
        }

@login_required
def training_dashboard(request):
    sessions = SessionFormation.objects.filter(user=request.user).order_by('-date_debut')
    incidents_disponibles = Incident.objects.filter(statut='résolu').order_by('-date_resolution')[:20]
    
    return render(request, 'training/training.html', {
        'sessions': sessions,
        'incidents': incidents_disponibles
    })

@login_required
def lancer_sandbox(request, incident_id):
    incident = get_object_or_404(Incident, id=incident_id)
    session = SessionFormation.objects.create(
        user=request.user, 
        incident_source=incident,
        titre_scenario=f"Sandbox: {incident.titre}"
    )
    return redirect('training:sandbox_view', session_id=session.id)

@login_required
def sandbox_view(request, session_id):
    session = get_object_or_404(SessionFormation, id=session_id, user=request.user)
    incident = session.incident_source
    
    # Générer le Briefing au premier chargement si vide
    if not session.description_scenario and incident:
        context = _get_incident_context(incident)
        try:
            prompt = prompt_sandbox_briefing(context)
            briefing = appeler_ia(model="llama-3.3-70b-versatile", prompt=prompt)
            session.description_scenario = briefing or "Alerte reçue: Incident critique sur " + incident.equipement.nom
            session.save()
            
            # Message de bienvenue du chatbot
            MessageInvestigation.objects.create(
                session=session,
                role='assistant',
                contenu="Console d'investigation active. Je suis à votre disposition pour extraire des logs ou diagnostiquer. Que voulez-vous vérifier ?"
            )
        except Exception as e:
            session.description_scenario = "Erreur de génération du briefing."
            session.save()
    
    return render(request, 'training/sandbox.html', {
        'session': session,
        'messages': session.messages.all()
    })

@csrf_exempt
@login_required
def sandbox_chat_api(request, session_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    session = get_object_or_404(SessionFormation, id=session_id, user=request.user)
    
    try:
        data = json.loads(request.body)
        user_msg = data.get('message', '').strip()
        
        if not user_msg:
            return JsonResponse({'error': 'Message vide'}, status=400)
            
        # Sauvegarde du message user
        MessageInvestigation.objects.create(session=session, role='user', contenu=user_msg)
        
        # Contexte et Prompt
        context = _get_incident_context(session.incident_source) if session.incident_source else {}
        historique = list(session.messages.all().order_by('date_creation'))[-10:] # 10 derniers messages
        
        prompt = prompt_sandbox_chat(historique, context)
        reponse_ia = appeler_ia(model="llama-3.3-70b-versatile", prompt=prompt)
        
        if reponse_ia:
            MessageInvestigation.objects.create(session=session, role='assistant', contenu=reponse_ia)
            return JsonResponse({'status': 'success', 'reply': reponse_ia})
        else:
            return JsonResponse({'error': 'L\'IA n\'a pas répondu'}, status=500)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required
def sandbox_validate_api(request, session_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    session = get_object_or_404(SessionFormation, id=session_id, user=request.user)
    
    if session.statut != 'en_cours':
        return JsonResponse({'error': 'Session déjà terminée'}, status=400)
        
    try:
        data = json.loads(request.body)
        commande = data.get('commande', '').strip()
        
        if not commande:
            return JsonResponse({'error': 'Commande vide'}, status=400)
            
        session.tentatives_cli += 1
        
        # Contexte et Prompt
        context = _get_incident_context(session.incident_source) if session.incident_source else {}
        prompt = prompt_sandbox_evaluation(commande, context)
        
        reponse_brute = appeler_ia(model="llama-3.3-70b-versatile", prompt=prompt)
        eval_data = _safe_json(reponse_brute)
        
        est_correct = eval_data.get('est_correct', False)
        debriefing = eval_data.get('debriefing', 'Pas de debriefing.')
        
        if est_correct:
            session.statut = 'termine_succes'
            session.score = max(0, 100 - (session.tentatives_cli - 1) * 10)
            session.date_fin = timezone.now()
        else:
            if session.tentatives_cli >= 5: # Max 5 tentatives
                session.statut = 'termine_echec'
                session.date_fin = timezone.now()
                
        session.save()
        
        return JsonResponse({
            'status': 'success',
            'est_correct': est_correct,
            'debriefing': debriefing,
            'session_statut': session.statut,
            'tentatives': session.tentatives_cli,
            'score': session.score
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
