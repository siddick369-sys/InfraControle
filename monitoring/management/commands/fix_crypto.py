from django.core.management.base import BaseCommand
from monitoring.models import CryptoManager, EquipementReseau


class Command(BaseCommand):
    help = 'Régénère les mots de passe chiffrés invalides'

    def add_arguments(self, parser):
        parser.add_argument('--new-key', action='store_true', help='Génère une nouvelle clé Fernet')

    def handle(self, *args, **options):
        if options['new_key']:
            new_key = CryptoManager.regenerate_key()
            self.stdout.write(self.style.WARNING(f"Nouvelle clé: {new_key}"))
            self.stdout.write("Ajoutez-la à settings.FERNET_KEY et redémarrez")
            return

        # Vérifier les équipements avec mots de passe invalides
        equipements = EquipementReseau.objects.exclude(mot_de_passe_ssh_chiffre__isnull=True)
        invalides = []
        
        for eq in equipements:
            if not eq.has_valid_ssh_password():
                invalides.append(eq)
                self.stdout.write(self.style.ERROR(f"✗ {eq.adresse_ip}: mot de passe invalide"))
        
        if invalides:
            self.stdout.write(self.style.WARNING(f"\n{len(invalides)} équipements à réparer:"))
            self.stdout.write("Utilisez l'admin Django pour re-saisir les mots de passe")
        else:
            self.stdout.write(self.style.SUCCESS("✓ Tous les mots de passe sont valides"))