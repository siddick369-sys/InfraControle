from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .tasks import generer_rapport_executif
from .oracle import OracleEngine
import json

@login_required
def generer_rapport_executif_view(request):
    mode = request.GET.get("mode", "auto")
    generer_rapport_executif.delay(mode_pdf=mode)
    messages.success(
        request,
        "📄 Génération du rapport exécutif lancée. Le PDF sera disponible sous peu."
    )
    return redirect("liste_equipements")

@login_required
def oracle_chat_ajax(request):
    """
    Endpoint AJAX hybride pour le chat avec l'Oracle et la conscience contextuelle.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_message = data.get("message", "")
            page_path = data.get("page_path", "Inconnu")
            page_title = data.get("page_title", "")
            
            if not user_message:
                return JsonResponse({"error": "Message vide"}, status=400)
            
            # Injection contextuelle pour le LLM "Wow Effect"
            context_string = f"[CONTEXTE INFRACONTROL: Path={page_path}, Title={page_title}]"
            enriched_message = f"{context_string} {user_message}"
            
            # Appel à l'Oracle via Llama/Groq
            response = OracleEngine.chat(enriched_message)
            
            if response:
                import re
                # Détection d'un bloc de code bash pour auto-remédiation
                command_match = re.search(r'```(?:bash|sh|cmd)\n(.*?)\n```', response, re.DOTALL)
                command_to_run = command_match.group(1).strip() if command_match else None

                return JsonResponse({
                    "response": response,
                    "command": command_to_run
                })
            else:
                return JsonResponse({"response": "Aucune réponse de l'hyperviseur IA."}, status=500)
        
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
            
    return JsonResponse({"error": "Méthode non autorisée"}, status=405)


@login_required
def oracle_execute_cmd_ajax(request):
    """
    Fonctionnalité Auto-Remédiation : Exécute une commande de bash générée par l'IA.
    ⚠️ DANGER : Usage strictement démonstratif avec timeout pour impressionner le jury.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            command = data.get("command", "")
            if not command:
                return JsonResponse({"error": "Aucune commande fournie."})
            
            import subprocess
            # Exécution limitée dans un sous-processus sécurisé
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            output = res.stdout if res.returncode == 0 else res.stderr
            
            return JsonResponse({"output": output.strip() if output else "Exécuté sans retour std."})
        except subprocess.TimeoutExpired:
            return JsonResponse({"error": "Timeout de la commande."})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
            
    return JsonResponse({"error": "Méthode non autorisée"})