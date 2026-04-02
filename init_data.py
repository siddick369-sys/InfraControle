"""
init_data.py — Initialisation des données pour les nouvelles apps.
À lancer via: python manage.py shell < init_data.py
"""
from training.models import ScenarioFormation
from remediation.models import ActionRemediation

# Scénarios de formation
scenarios = [
    {
        'titre': 'wifi_sature',
        'description': 'Le canal Wi-Fi est saturé par des interférences. Proposez une solution.',
        'difficulte': 1
    },
    {
        'titre': 'container_crash',
        'description': "Un conteneur critique (Postgres) vient de s'arrêter brutalement.",
        'difficulte': 2
    },
    {
        'titre': 'cpu_eleve',
        'description': 'Le CPU du serveur web dépasse 95% de charge. Identifiez la cause.',
        'difficulte': 2
    },
    {
        'titre': 'perte_reseau',
        'description': "L'accès au routeur principal est perdu. Diagnostiquez la coupure.",
        'difficulte': 3
    },
]

for s in scenarios:
    ScenarioFormation.objects.get_or_create(titre=s['titre'], defaults=s)

# Actions de remédiation
actions = [
    {'nom': 'Redémarrer Service', 'description': 'Relance un service système via SSH.', 'automatique': False},
    {'nom': 'Redémarrer Container', 'description': 'Relance un conteneur Docker.', 'automatique': True},
    {'nom': 'Nettoyage Disque', 'description': 'Supprime les fichiers logs anciens (>30j).', 'automatique': True},
    {'nom': 'Changement Canal WiFi', 'description': 'Bascule sur le canal optimal détecté.', 'automatique': True},
]

for a in actions:
    ActionRemediation.objects.get_or_create(nom=a['nom'], defaults=a)

print("Initialisation réussie.")
