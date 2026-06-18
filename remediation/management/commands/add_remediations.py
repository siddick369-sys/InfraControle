from django.core.management.base import BaseCommand
from remediation.models import AnomalieRegle

class Command(BaseCommand):
    help = 'Ajoute les remédiations par défaut dans la base de données'

    def handle(self, *args, **kwargs):
        remediations = [
            {
                'nom': 'Surcharge CPU (Linux)',
                'cmd_detection': 'top -bn1 | grep load',
                'cmd_remediation': 'killall -9 stress',
                'os_cible': 'linux'
            },
            {
                'nom': 'Erreur Service Nginx (Linux)',
                'cmd_detection': 'systemctl status nginx | grep failed',
                'cmd_remediation': 'systemctl restart nginx',
                'os_cible': 'linux'
            },
            {
                'nom': 'Redémarrage Spooler Impression (Windows)',
                'cmd_detection': 'sc query spooler | find "STOPPED"',
                'cmd_remediation': 'net start spooler',
                'os_cible': 'windows'
            }
        ]

        count = 0
        for r in remediations:
            regle, created = AnomalieRegle.objects.get_or_create(
                nom=r['nom'],
                defaults={
                    'cmd_detection': r['cmd_detection'],
                    'cmd_remediation': r['cmd_remediation'],
                    'os_cible': r['os_cible']
                }
            )
            if created:
                count += 1
                self.stdout.write(self.style.SUCCESS(f"Remédiation '{r['nom']}' ajoutée avec succès."))
            else:
                self.stdout.write(self.style.WARNING(f"Remédiation '{r['nom']}' existe déjà."))

        self.stdout.write(self.style.SUCCESS(f"Opération terminée. {count} nouvelles règles ajoutées."))
