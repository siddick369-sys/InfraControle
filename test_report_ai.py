import os
import django
import sys
from datetime import timedelta
from django.utils import timezone

# Configuration de Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from reports.services.pdf_generator import generer_rapport_executif

import traceback

def test_generation():
    # Configure stdout for UTF-8 on Windows
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass

    print("--- TEST GENERATION RAPPORT Administratif IA (GROQ) ---")
    
    date_fin = timezone.now().date()
    date_debut = date_fin - timedelta(days=7)
    
    try:
        rapport = generer_rapport_executif(date_debut, date_fin)
        print(f"\n[SUCCESS] Rapport {rapport.id} genere avec succes!")
        print("-" * 40)
        print(rapport.analyse_ia[:500] + "...\n[TRONQUE]")
        print("-" * 40)
    except Exception as e:
        print(f"\n[ERROR] lors de la generation: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_generation()
