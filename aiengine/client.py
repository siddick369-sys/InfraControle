from decouple import config
import requests
import json
import logging
import time

logger = logging.getLogger("ai")

def _appel_groq(prompt: str, is_json=False, timeout=45, retries=3):
    """
    Appel spécifique API Groq via REST (llama-3.3-70b-versatile)
    """
    key = config("GROQ_API_KEY", default=None)
    if not key:
        logger.error("[IA] GROQ_API_KEY non configurée.")
        return None
    
    model = config("GROQ_MODEL", default="llama-3.3-70b-versatile")
    
    for attempt in range(retries):
        try:
            logger.info(f"[IA] Appel Groq ({model}) - Tentative {attempt+1}/{retries}...")
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            }
            if is_json:
                payload["response_format"] = {"type": "json_object"}

            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=timeout
            )
            if response.status_code == 200:
                res_json = response.json()
                return res_json["choices"][0]["message"]["content"]
            
            logger.error(f"[IA] Erreur Groq {response.status_code}: {response.text}")
            if response.status_code >= 500:
                time.sleep(2)
                continue
            return None
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return None
        except Exception as e:
            logger.error(f"[IA] Exception inattendue: {e}")
            return None
    return None

def appeler_ia(prompt: str, is_json=False, timeout=45):
    """
    Appel direct à l'IA Oracle via Groq.
    """
    return _appel_groq(prompt, is_json=is_json, timeout=timeout)