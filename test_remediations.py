import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
django.setup()

from monitoring.remediation_engine import REMEDIATIONS

new_anomalies = [
    "Inodes critiques", "Incident OOM (Dmesg)", "Mémoire partagée saturée",
    "Attaque Bruteforce SSH détectée", "Désynchronisation NTP", "Service Cron arrêté",
    "Espace Root critique", "Limite fichiers ouverts", "Dépôts inaccessibles",
    "Accès Root SSH autorisé", "Service DHCP down", "Service DNS down",
    "Antivirus arrêté", "Journal d'événements down", "Planificateur de tâches down",
    "Fuite Mémoire Paginée", "Espace disque C: critique", "File d'attente CPU élevée",
    "Connexions TCP Windows saturées", "Sessions RDP Fantômes",
    "CPU Équipement Réseau saturé", "Instabilité Interface (Flapping)",
    "Changement de topologie (STP)", "Session BGP inactive", "Voisin OSPF inactif",
    "Incompatibilité Duplex", "Spoofing d'adresse MAC (Flapping)",
    "RAM Équipement Réseau saturée", "Attaque Pare-feu (Logs)"
]

print("--- TESTING REMEDIATIONS SYNTAX ---")
missing = []
for title in new_anomalies:
    if title not in REMEDIATIONS:
        missing.append(title)
    else:
        plan = REMEDIATIONS[title]
        assert isinstance(plan, dict), f"Plan for {title} is not a dict"
        for os_type, levels in plan.items():
            assert os_type in ["linux", "windows"], f"Unknown OS type {os_type} in {title}"
            for level, cmds in levels.items():
                assert level in ["soft", "hard"], f"Unknown level {level} in {title}"
                assert isinstance(cmds, list), f"Commands for {title}/{os_type}/{level} must be a list"
                for cmd in cmds:
                    assert isinstance(cmd, str), f"Command is not a string in {title}"

if missing:
    print(f"ERROR: Missing remediations for: {missing}")
else:
    print("SUCCESS: All new anomalies have valid remediation definitions.")
