from datetime import timedelta
from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings


# ======================================================
# 1️⃣  PROFIL UTILISATEUR & ROLES
# ======================================================
class Profil(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrateur'),
        ('TECH', 'Technicien Réseau'),
        ('VIEWER', 'Consultation'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='VIEWER')
    telephone = models.CharField(max_length=20, blank=True,null=True)
    photo = models.ImageField(upload_to='photos_utilisateurs/', null=True, blank=True)
    est_autorise = models.BooleanField(default=False, help_text="L'utilisateur a été validé par l'administrateur")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)
    est_gelé = models.BooleanField(default=False)
    date_suppression_programmee = models.DateTimeField(null=True, blank=True)

    def programmer_suppression(self):
        """Marque le compte comme gelé et programme la suppression dans 7 jours."""
        self.est_gelé = True
        self.date_suppression_programmee = timezone.now() + timedelta(days=7)
        self.save()

    def annuler_suppression(self):
        """Annule la suppression et dé-gèle le compte."""
        self.est_gelé = False
        self.date_suppression_programmee = None
        self.save()

    def doit_etre_supprime(self):
        """Vérifie si le délai de suppression est passé."""
        return self.est_gelé and self.date_suppression_programmee and timezone.now() > self.date_suppression_programmee

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def est_admin(self):
        return self.role == "ADMIN"

    @property
    def est_tech(self):
        return self.role == "TECH"


# ======================================================
# 2️⃣  JOURNAL D’ACTIVITÉS (AUDIT)
# ======================================================
class JournalActivite(models.Model):
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    ip = models.GenericIPAddressField(null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)
    resultat = models.CharField(max_length=50, blank=True)
    details = models.TextField(blank=True, null=True)  # ✅ nouveau pour stocker fingerprint ou logs avancés

    class Meta:
        ordering = ['-date_action']

    def __str__(self):
        user = self.utilisateur.username if self.utilisateur else "Système"
        return f"{user} - {self.action} ({self.date_action.strftime('%Y-%m-%d %H:%M')})"


# ======================================================
# 3️⃣  VÉRIFICATION D’UTILISATEUR (Email + OTP)
# ======================================================
import random

class CodeVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='code_verification')
    code = models.CharField(max_length=6)
    expire_le = models.DateTimeField()
    tentative = models.IntegerField(default=0)
    derniere_envoi = models.DateTimeField(auto_now=True)

    def est_expire(self):
        return timezone.now() > self.expire_le

    def __str__(self):
        return f"Code pour {self.user.username} - expire {self.expire_le.strftime('%H:%M')}"
    
    def generer_nouveau_code(self):
        self.code = str(random.randint(100000, 999999))
        self.expire_le = timezone.now() + timezone.timedelta(minutes=10)
        self.derniere_envoi = timezone.now()
        self.save(update_fields=["code", "expire_le", "derniere_envoi"])
        return self.code


# ======================================================
# 4️⃣  SIGNALS : création automatique du profil + envoi du code OTP
# ======================================================

import random
import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

import random
import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings

@receiver(post_save, sender=User)
def creer_profil_et_code(sender, instance, created, **kwargs):
    if created:
        # Crée le profil utilisateur
        profil = Profil.objects.create(user=instance)
        CodeVerification.objects.filter(user=instance).delete()

        # Génère le code OTP
        code = CodeVerification.objects.create(
            user=instance,
            code=str(random.randint(100000, 999999)),
            expire_le=timezone.now() + timezone.timedelta(minutes=10)
        )

        # Envoi d’email asynchrone (thread)
        def envoyer_emails():
            try:
                # === Email de vérification de compte ===
                contexte_verif = {'username': instance.username, 'code': code.code}
                html_verif = render_to_string('emails/verification_code.html', contexte_verif)
                text_verif = f"Bonjour {instance.username},\n\nVotre code de vérification est : {code.code}\nCe code expire dans 10 minutes."

                email_verif = EmailMultiAlternatives(
                    subject="Vérification de votre compte InfraControl",
                    body=text_verif,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[instance.email],
                )
                email_verif.attach_alternative(html_verif, "text/html")
                email_verif.send(fail_silently=True)

                # === Email de bienvenue ===
                contexte_bienvenue = {'username': instance.username}
                html_bienvenue = render_to_string('emails/welcome_user.html', contexte_bienvenue)
                text_bienvenue = f"Bienvenue sur InfraControl, {instance.username} !\n\nVotre compte a bien été créé. Veuillez vérifier votre email pour activer votre compte."

                email_bienvenue = EmailMultiAlternatives(
                    subject="Bienvenue sur InfraControl 🎉",
                    body=text_bienvenue,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[instance.email],
                )
                email_bienvenue.attach_alternative(html_bienvenue, "text/html")
                email_bienvenue.send(fail_silently=True)

            except Exception as e:
                print(f"[Erreur envoi email création compte] {e}")

        threading.Thread(target=envoyer_emails).start()