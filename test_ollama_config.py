import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from aiengine.client import get_ollama_endpoint

print(f"Current OLLAMA_URL in settings: {settings.OLLAMA_URL}")
print(f"Resolved endpoint: {get_ollama_endpoint()}")

expected = f"{settings.OLLAMA_URL.rstrip('/')}/api/generate"
if get_ollama_endpoint() == expected:
    print("SUCCESS: Endpoint resolution is correct.")
else:
    print(f"FAILURE: Expected {expected}, got {get_ollama_endpoint()}")
