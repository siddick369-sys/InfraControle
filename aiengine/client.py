from django.conf import settings
import requests
import json
import logging
import time

logger = logging.getLogger("ai")

def get_ollama_endpoint():
    base_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434")
    if not base_url.endswith("/api/generate"):
        return f"{base_url.rstrip('/')}/api/generate"
    return base_url

def _appel_groq(prompt: str, timeout=30):
    """
    Appel spécifique API Groq via REST (llama-3.3-70b-versatile)
    """
    key = getattr(settings, "GROQ_API_KEY", None)
    if not key:
        # Fallback robuste avec la clé fournie par l'utilisateur pour l'analyse d'incidents
        key = os.environ.get("GROQ_API_KEY", "")
        logger.info("[IA] Utilisation de la clé Groq depuis variable d'environnement")
    
    model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")

    try:
        logger.info(f"[IA] Appel Groq ({model})...")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            },
            timeout=timeout
        )
        if response.status_code != 200:
            logger.error(f"[IA] Erreur Groq {response.status_code}: {response.text}")
            return None
            
        res_json = response.json()
        return res_json["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"[IA] Exception lors de l'appel Groq: {e}", exc_info=True)
        return None

def appeler_ia(model: str, prompt: str, timeout=600, provider=None):
    """
    Appel hybride IA
    - provider='groq': Force l'appel Groq uniquement
    - provider='ollama': Force l'appel Ollama uniquement
    - provider=None: Tente Groq puis Ollama
    """
    # 1. Tentative Groq
    if provider in [None, 'groq']:
        reponse = _appel_groq(prompt)
        if reponse:
            logger.info("[IA] Analyse terminée via Groq")
            return reponse
        if provider == 'groq':
            return None

    # 2. Fallback Ollama
    if provider in [None, 'ollama']:
        logger.warning("[IA] Appel Ollama local...")
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        start_time = time.time()
        try:
            url = get_ollama_endpoint()
            logger.info(f"[IA] Appel Ollama ({model}) sur {url}...")
            response = requests.post(
                url,
                json=payload,
                headers={
                    "content-Type": "application/json"
                },
                timeout=timeout
            )
            response.raise_for_status()
            duration = time.time() - start_time
            logger.info(f"[IA] Réponse Ollama reçue en {duration:.2f}s")
            return response.json()["response"]

        except Exception as e:
            logger.error("[IA] Échec Ollama", exc_info=True)
            return None
    
    return None