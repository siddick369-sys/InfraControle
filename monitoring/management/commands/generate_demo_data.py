from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from monitoring.models import EquipementReseau  # adapte "reseau" au nom de ton app


class Command(BaseCommand):
    help = "Crée quelques équipements fictifs pour tests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Username du créateur (par défaut: premier user trouvé).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recrée les équipements même s'ils existent déjà (sinon: skip).",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        username = options["user"]
        force = options["force"]

        if username:
            user = User.objects.filter(username=username).first()
        else:
            user = User.objects.first()

        if not user:
            self.stderr.write(self.style.ERROR(
                "Aucun utilisateur trouvé. Crée d'abord un user (ex: createsuperuser)."
            ))
            return

        equipements = [
            ("Routeur principal", "routeur", "192.168.1.1"),
            ("Serveur web", "serveur", "192.168.1.10"),
            ("Switch étage 2", "switch", "192.168.2.5"),
        ]

        created_count = 0
        skipped_count = 0

        for nom, typ, ip in equipements:
            if not force and EquipementReseau.objects.filter(nom=nom, adresse_ip=ip).exists():
                skipped_count += 1
                self.stdout.write(self.style.WARNING(f"Skip: {nom} ({ip}) existe déjà."))
                continue

            e = EquipementReseau(
                nom=nom,
                type_equipement=typ,
                adresse_ip=ip,
                utilisateur_ssh="admin",
                localisation="Salle serveur",
                cree_par=user,
            )
            e.set_mot_de_passe_ssh("admin123")
            e.save()
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"Créé: {nom} ({ip})"))

        self.stdout.write(self.style.SUCCESS(
            f"Terminé. Créés: {created_count}, ignorés: {skipped_count}."
        ))