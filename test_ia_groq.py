import os
import django
import sys

# Configuration de Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from aiengine.client import appeler_ia

def test_ia():
    print("--- TEST IA HYBRIDE (GROQ) ---")
    prompt = "Dis 'Bonjour Infracontrol' de manière concise."
    
    reponse = appeler_ia("llama3.1:latest", prompt)
    
    if reponse:
        print(f"RÉPONSE REÇUE:\n{reponse}")
        if "Bonjour Infracontrol" in reponse:
            print("\n✅ TEST RÉUSSI")
        else:
            print("\n⚠️ RÉPONSE INATTENDUE")
    else:
        print("\n❌ TEST ÉCHOUÉ (Pas de réponse)")

if __name__ == "__main__":
    test_ia()
