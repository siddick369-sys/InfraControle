import os
import django
import sys
import logging

# Configuration de Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from django.conf import settings
from aiengine.client import _appel_groq

def test_groq_keys():
    logging.basicConfig(level=logging.INFO)
    print("--- TEST CLES GROQ ---")
    
    # 1. Test clé ENV (Incidents)
    print(f"\n1. Test de la cle Incidents (via settings)")
    res_env = _appel_groq("Dis bonjour")
    if res_env:
        print("OK: Cle Incidents FONCTIONNE")
    else:
        print("KO: Cle Incidents ECHOUE (verifiez .env)")

    # 2. Test clé Reports (Hardcodée dans ai_report.py)
    from reports.services.ai_report import GROQ_API_KEY, GROQ_MODEL
    import requests
    print(f"\n2. Test de la cle Reports (Hardcodee)")
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            timeout=10
        )
        if response.status_code == 200:
            print("OK: Cle Reports FONCTIONNE")
        else:
            print(f"KO: Cle Reports ECHOUE: {response.status_code} {response.text}")
    except Exception as e:
        print(f"KO: Erreur test cle Reports: {e}")

if __name__ == "__main__":
    test_groq_keys()
