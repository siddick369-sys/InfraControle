import time
from django.shortcuts import render

# Create your views here.


from .decorators import *
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

import threading, random

from .middleware import BotDefenseMiddleware
from .utils import alerte_admin

from .models import Profil, CodeVerification, JournalActivite
from django.contrib.auth.models import User
from datetime import timedelta


from django.core.cache import cache
from django.conf import settings

from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.core.cache import cache
from core.models import JournalActivite
from core.middleware import BotDefenseMiddleware
from core.utils import alerte_admin  # si tu as une fonction d’alerte admin
import time


@csrf_protect
def inscription_view(request):
    """Vue sécurisée d’inscription avec anti-bot, anti-bruteforce et stealth token."""
    
    if request.user.is_authenticated:
        return redirect('profile')

    ip = request.META.get('REMOTE_ADDR')
    cache_key = f"register_attempts_{ip}"
    attempts = cache.get(cache_key, 0)

    # 🧱 Protection brute-force
    if attempts >= 5:
        messages.error(request, "🚫 Trop de tentatives d’inscription. Réessayez plus tard.")
        return redirect('connexion')

    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        honeypot = request.POST.get('website')

        # 🪤 Détection bot simple (champ caché rempli)
        if honeypot:
            JournalActivite.objects.create(action="Bot détecté sur inscription", ip=ip, resultat="échec")
            alerte_admin(
                action="Tentative bot sur inscription",
                ip=ip,
                details=f"Bot détecté sur formulaire d’inscription pour utilisateur {username}"
            )
            messages.error(request, "🤖 Activité suspecte détectée.")
            return redirect('inscription')

        # 🔒 Vérification mots de passe
        if password1 != password2:
            messages.error(request, "❌ Les mots de passe ne correspondent pas.")
            cache.set(cache_key, attempts + 1, timeout=600)
            return redirect('inscription')

        # ⚠️ Email déjà utilisé
        if User.objects.filter(email=email).exists():
            messages.warning(request, "⚠️ Cet email existe déjà.")
            return redirect('connexion')

        # ✅ Création du compte
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.is_active = True
        user.save()

        JournalActivite.objects.create(utilisateur=user, action="Création de compte", resultat="succès", ip=ip)
        cache.delete(cache_key)

        messages.success(request, "✅ Compte créé avec succès. Vérifiez votre email pour activer votre compte.")
        return redirect('verification_compte')

    # 🧩 Retourne les champs stealth au template (GET ou POST échoué)
    
    # 🧠 Génération des champs anti-bot stealth à chaque affichage
    stealth = BotDefenseMiddleware.generate_stealth_fields(request)

    return render(request, 'auth/inscription.html', stealth)

from django_otp import devices_for_user

@csrf_protect
def connexion_view(request):
    if request.user.is_authenticated:
        return redirect('profile')

    ip = request.META.get('REMOTE_ADDR')
    cache_key = f"login_attempts_{ip}"
    attempts = cache.get(cache_key, 0)

    if attempts >= settings.MAX_FAILED_ATTEMPTS:
        messages.error(request, f"🚫 Trop de tentatives. Réessayez dans {settings.BLOCK_TIME_MINUTES} minutes.")
        return redirect('connexion')

    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        honeypot = request.POST.get('website')

        if honeypot:
            JournalActivite.objects.create(action="Bot détecté sur login", ip=ip, resultat="échec")
            messages.error(request, "🤖 Activité suspecte détectée.")
            return redirect('connexion')

        user = authenticate(request, username=username, password=password)

        if user:
            profil = getattr(user, 'profil', None)
            if profil and not profil.est_autorise:
                messages.warning(request, "🚫 Compte non vérifié. Vérifiez votre email.")
                return redirect('verification_compte')

            # 🧩 Vérifie si l’utilisateur a un device OTP confirmé
            devices = [d for d in devices_for_user(user) if getattr(d, "confirmed", True)]
            if devices:
                request.session['pending_2fa_user'] = user.id
                return redirect('verification_2fa')

            # 🔓 Sinon connexion normale
            login(request, user)
            cache.delete(cache_key)
            JournalActivite.objects.create(utilisateur=user, action="Connexion réussie", resultat="succès", ip=ip)
            messages.success(request, f"👋 Bienvenue {user.username} !")
            return redirect('profile')

        # ❌ Échec
        attempts += 1
        cache.set(cache_key, attempts, timeout=settings.BLOCK_TIME_MINUTES * 60)
        JournalActivite.objects.create(action=f"Tentative de connexion échouée ({username})", resultat="échec", ip=ip)
        messages.error(request, f"❌ Identifiants incorrects. ({attempts}/{settings.MAX_FAILED_ATTEMPTS})")

    return render(request, 'auth/connexion.html')
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import threading
from django.utils import timezone
from django.core.cache import cache
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from core.models import User, CodeVerification, JournalActivite

@csrf_protect
def renvoi_code(request):
    """Permet de renvoyer un code OTP avant connexion, sécurisé contre le spam."""
    ip = request.META.get("REMOTE_ADDR", "unknown")

    if request.method == "POST":
        email = request.POST.get("email")
        honeypot = request.POST.get("website")

        if honeypot:
            JournalActivite.objects.create(
                utilisateur=None,
                action="Bot détecté sur renvoi OTP",
                resultat="échec",
                ip=ip
            )
            messages.error(request, "🤖 Activité suspecte détectée.")
            return redirect("connexion")

        # Vérifie que l'utilisateur existe
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "❌ Aucun utilisateur trouvé avec cet email.")
            return redirect("renvoi_code")

        cache_key = f"otp_resent_{user.id}_{ip}"
        last_sent = cache.get(cache_key)

        # Anti-spam (1 envoi / 60 secondes)
        if last_sent and (timezone.now() - last_sent).seconds < 60:
            messages.warning(request, "🕒 Vous devez attendre avant de demander un nouveau code.")
            JournalActivite.objects.create(utilisateur=user, action="Renvoi OTP trop fréquent", resultat="échec", ip=ip)
            return redirect("verification_compte")

        # Récupère ou crée un nouveau code
        code_obj, created = CodeVerification.objects.get_or_create(user=user)
        code_obj.generer_nouveau_code()
        cache.set(cache_key, timezone.now(), timeout=120)

        # Envoi d’email asynchrone
        def envoyer_email():
            try:
                contexte = {'username': user.username, 'code': code_obj.code}
                message_html = render_to_string('emails/verification_code.html', contexte)
                message_texte = f"Votre nouveau code de vérification : {code_obj.code}"

                email = EmailMultiAlternatives(
                    subject="🔐 Nouveau code de vérification InfraControl",
                    body=message_texte,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email],
                )
                email.attach_alternative(message_html, "text/html")
                email.send(fail_silently=True)
            except Exception as e:
                print(f"[Erreur email renvoi OTP] {e}")

        threading.Thread(target=envoyer_email).start()

        JournalActivite.objects.create(utilisateur=user, action="Renvoi code OTP", resultat="succès", ip=ip)
        messages.success(request, "✅ Nouveau code envoyé par email.")
        return redirect("verification_compte")

    return render(request, "auth/renvoi_code.html")
from django.core.cache import cache
from django.conf import settings
from datetime import timedelta
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone
from core.models import CodeVerification, JournalActivite, Profil
from django.contrib.auth.models import User

@csrf_protect
def verification_view(request):
    """Vérification du compte par code OTP avant connexion."""
    if request.user.is_authenticated:
        return redirect('profile')

    ip = request.META.get('REMOTE_ADDR', 'unknown')
    honeypot = request.POST.get('website')

    if honeypot:
        JournalActivite.objects.create(
            utilisateur=None,
            action="Tentative bot sur vérification OTP",
            resultat="échec",
            ip=ip
        )
        messages.error(request, "🤖 Activité suspecte détectée.")
        return redirect('connexion')

    if request.method == "POST":
        email = request.POST.get("email")
        code_saisi = request.POST.get("code")

        # Vérifie l’email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "❌ Aucun utilisateur trouvé avec cet email.")
            return redirect("verification_compte")

        cache_key = f"otp_attempts_{user.id}_{ip}"
        attempts = cache.get(cache_key, 0)

        if attempts >= 5:
            messages.error(request, "🚫 Trop de tentatives. Attendez 5 minutes avant de réessayer.")
            JournalActivite.objects.create(utilisateur=user, action="Blocage tentative OTP", resultat="trop de tentatives", ip=ip)
            return redirect("connexion")

        # Anti-refresh (3 secondes)
        last_try = cache.get(f"otp_last_try_{user.id}")
        if last_try and (timezone.now() - last_try).seconds < 3:
            messages.warning(request, "⏱ Veuillez patienter avant de réessayer.")
            return redirect("verification_compte")
        cache.set(f"otp_last_try_{user.id}", timezone.now(), timeout=60)

        # Récupération du code
        code_obj = get_object_or_404(CodeVerification, user=user)

        # Vérifie expiration
        if code_obj.est_expire():
            messages.error(request, "⏰ Ce code a expiré. Cliquez sur 'Renvoyer le code'.")
            JournalActivite.objects.create(utilisateur=user, action="Code OTP expiré", resultat="échec", ip=ip)
            return redirect("renvoi_code")

        # Vérifie code
        if code_saisi == code_obj.code:
            profil = Profil.objects.get(user=user)
            profil.est_autorise = True
            profil.save()
            code_obj.delete()
            cache.delete(cache_key)

            JournalActivite.objects.create(utilisateur=user, action="Vérification du compte réussie", resultat="succès", ip=ip)
            messages.success(request, "✅ Vérification réussie ! Vous pouvez maintenant vous connecter.")
            return redirect("connexion")

        # Mauvais code
        code_obj.tentative += 1
        code_obj.save()
        attempts += 1
        cache.set(cache_key, attempts, timeout=300)

        JournalActivite.objects.create(utilisateur=user, action="Échec vérification OTP", resultat="échec", ip=ip)
        messages.error(request, f"❌ Code incorrect ({code_obj.tentative}/5).")
        return redirect("verification_compte")

    return render(request, "auth/verification.html")

@verifie_compte_non_gele
@login_required
def profile_view(request):
    profil = request.user.profil
    return render(request, 'auth/profile.html', {'profil': profil})


@verifie_compte_non_gele
@login_required
@csrf_protect
def edit_profile(request):
    profil = request.user.profil

    if request.method == "POST":
        profil.telephone = request.POST.get('telephone')
        profil.photo = request.FILES.get('photo') or profil.photo
        profil.save()
        JournalActivite.objects.create(utilisateur=request.user, action="Mise à jour du profil", resultat="succès")
        messages.success(request, "✅ Profil mis à jour avec succès.")
        return redirect('profile')

    return render(request, 'auth/edit_profile.html', {'profil': profil})


from django.core.cache import cache
from django.conf import settings
from datetime import timedelta

@verifie_compte_non_gele
@login_required
@csrf_protect
def deconnexion_view(request):
    user = request.user
    ip = request.META.get('REMOTE_ADDR', 'unknown')

    # Clés cache anti-brute-force et anti-flood
    cache_key_attempts = f"logout_attempts_{user.id}_{ip}"
    cache_key_last = f"logout_last_try_{user.id}_{ip}"

    attempts = cache.get(cache_key_attempts, 0)
    last_try = cache.get(cache_key_last)

    # Blocage temporaire si trop de tentatives
    if attempts >= 5:
        messages.error(request, "🚫 Trop de tentatives. Réessayez dans 10 minutes.")
        JournalActivite.objects.create(utilisateur=user, action="Blocage déconnexion (bruteforce)", resultat="échec", ip=ip)
        return redirect('profile')

    # Anti-flood : 2 secondes minimum entre 2 essais
    if last_try and (timezone.now() - last_try).seconds < 2:
        messages.warning(request, "🕒 Merci d’attendre un instant avant de réessayer.")
        return redirect('deconnexion')

    if request.method == "POST":
        # Honeypot anti-bot
        if request.POST.get('website'):
            JournalActivite.objects.create(utilisateur=user, action="Tentative de bot sur déconnexion", resultat="échec", ip=ip)
            messages.error(request, "🤖 Activité suspecte détectée.")
            return redirect('profile')

        password = request.POST.get('password', '')

        # Vérifie le mot de passe
        if user.check_password(password):
            JournalActivite.objects.create(utilisateur=user, action="Déconnexion", resultat="succès", ip=ip)
            logout(request)
            cache.delete(cache_key_attempts)
            messages.success(request, "✅ Déconnexion réussie.")
            return redirect('connexion')
        else:
            attempts += 1
            cache.set(cache_key_attempts, attempts, timeout=600)  # 10 min
            cache.set(cache_key_last, timezone.now(), timeout=60)
            JournalActivite.objects.create(utilisateur=user, action="Échec mot de passe déconnexion", resultat="échec", ip=ip)
            messages.error(request, f"❌ Mot de passe incorrect ({attempts}/5).")
            return redirect('deconnexion')

    return render(request, 'auth/deconnexion.html')


@verifie_compte_non_gele
@csrf_protect
def reset_password_final_view(request):
    """Étape 3 : Définir un nouveau mot de passe après validation OTP"""
    ip = request.META.get('REMOTE_ADDR', 'unknown')

    if request.method == "POST":
        email = request.POST.get('email')
        new_password = request.POST.get('password1')
        confirm_password = request.POST.get('password2')
        honeypot = request.POST.get('website')

        if honeypot:
            JournalActivite.objects.create(action="Bot détecté sur reset final", ip=ip, resultat="échec")
            messages.error(request, "🤖 Activité suspecte détectée.")
            return redirect('connexion')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "Compte introuvable.")
            return redirect('demande_reset')

        verified = cache.get(f"reset_verified_{user.id}", False)
        if not verified:
            messages.error(request, "⚠️ Code OTP non validé.")
            return redirect('verification_reset')

        if new_password != confirm_password:
            messages.error(request, "❌ Les mots de passe ne correspondent pas.")
            return redirect('reset_password_final')

        # Protection contre les mots de passe faibles
        if len(new_password) < 8 or new_password.isdigit():
            messages.error(request, "🚫 Mot de passe trop faible.")
            return redirect('reset_password_final')

        # Change le mot de passe
        user.set_password(new_password)
        user.save()
        cache.delete(f"reset_verified_{user.id}")

        JournalActivite.objects.create(utilisateur=user, action="Changement mot de passe réussi", resultat="succès", ip=ip)
        messages.success(request, "✅ Mot de passe réinitialisé avec succès. Vous pouvez vous connecter.")
        return redirect('connexion')

    return render(request, 'auth/reset_final.html')


@verifie_compte_non_gele
@csrf_protect
def verification_reset_view(request):
    """Étape 2 : Vérification du code OTP avant changement de mot de passe"""
    ip = request.META.get('REMOTE_ADDR', 'unknown')

    if request.method == "POST":
        email = request.POST.get('email')
        code = request.POST.get('code')
        honeypot = request.POST.get('website')

        if honeypot:
            JournalActivite.objects.create(action="Bot détecté sur vérif reset", ip=ip, resultat="échec")
     
    
            messages.error(request, "🤖 Activité suspecte détectée.")
            return redirect('connexion')

        try:
            user = User.objects.get(email=email)
            code_obj = CodeVerification.objects.get(user=user)
        except (User.DoesNotExist, CodeVerification.DoesNotExist):
            messages.error(request, "Compte ou code invalide.")
            return redirect('verification_reset')

        if code_obj.est_expire():
            messages.error(request, "⏰ Code expiré. Recommencez la procédure.")
            return redirect('demande_reset')

        if code_obj.code == code:
            cache.set(f"reset_verified_{user.id}", True, timeout=600)
            JournalActivite.objects.create(utilisateur=user, action="Code OTP validé pour reset", resultat="succès", ip=ip)
            return redirect('reset_password_confirm', token=code_obj.code)
        else:
            code_obj.tentative += 1
            code_obj.save()
            JournalActivite.objects.create(utilisateur=user, action="Code OTP incorrect reset", resultat="échec", ip=ip)
            messages.error(request, "❌ Code invalide.")
            return redirect('verification_reset')

    return render(request, 'auth/reset_verification.html')


from django.core.cache import cache
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

@verifie_compte_non_gele
@csrf_protect
def demande_reset_view(request):
    """Étape 1 : Saisie de l'email pour recevoir un code de réinitialisation"""
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    cache_key = f"reset_attempts_{ip}"
    attempts = cache.get(cache_key, 0)

    if attempts >= 5:
        messages.error(request, "🚫 Trop de tentatives. Réessayez dans 15 minutes.")
        return redirect('connexion')

    if request.method == "POST":
        email = request.POST.get('email')
        honeypot = request.POST.get('website')

        # 🧱 Anti-bot honeypot
        if honeypot:
            JournalActivite.objects.create(
                action="Bot détecté sur demande reset", ip=ip, resultat="échec"
            )
            messages.error(request, "🤖 Activité suspecte détectée.")
            return redirect('connexion')

        # 🧍 Vérifie si l'utilisateur existe
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            cache.set(cache_key, attempts + 1, timeout=900)
            messages.error(request, "Aucun compte trouvé avec cet email.")
            JournalActivite.objects.create(
                action="Tentative reset email inexistant", ip=ip, resultat="échec"
            )
            return redirect('demande_reset')

        # 🕒 Anti-flood (1 demande toutes les 60 secondes)
        cache_key_cooldown = f"reset_cooldown_{user.id}"
        last_sent = cache.get(cache_key_cooldown)
        if last_sent and (timezone.now() - last_sent).seconds < 60:
            messages.warning(request, "🕒 Vous devez attendre avant une nouvelle demande.")
            return redirect('connexion')

        # 🔐 Création / mise à jour du code OTP
        code_obj, _ = CodeVerification.objects.update_or_create(
            user=user,
            defaults={
                'code': str(random.randint(100000, 999999)),
                'expire_le': timezone.now() + timezone.timedelta(minutes=10),
                'tentative': 0,
            }
        )

        # 💾 Stocke l'ID utilisateur dans la session pour la prochaine étape
        request.session['reset_user_id'] = user.id

        # ✉️ Envoi de l'email (asynchrone sécurisé)
        def envoyer_email():
            try:
                contexte = {'username': user.username, 'code': code_obj.code}
                html_message = render_to_string('emails/reset_code.html', contexte)
                msg = EmailMultiAlternatives(
                    subject="Réinitialisation de mot de passe - InfraControl",
                    body=f"Bonjour {user.username},\n\nVotre code de réinitialisation est : {code_obj.code}\nCe code expire dans 10 minutes.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email],
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=False)
            except Exception as e:
                print(f"[ERREUR EMAIL RESET] {e}")

        threading.Thread(target=envoyer_email).start()

        # 🔁 Anti-spam : délai entre deux envois
        cache.set(cache_key_cooldown, timezone.now(), timeout=300)

        # 🗂️ Journalisation
        JournalActivite.objects.create(
            utilisateur=user,
            action="Demande de réinitialisation du mot de passe",
            resultat="succès",
            ip=ip
        )

        messages.success(request, "✅ Un code de réinitialisation vous a été envoyé par email.")
        return redirect('verification_reset')

    return render(request, 'auth/reset_demande.html')

from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib.auth.decorators import login_required
from django_otp import devices_for_user
from django.utils import timezone
from .utils import get_or_create_device
import qrcode
import io
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings
from core.models import JournalActivite
import qrcode
import io
import base64
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render, redirect
from django.contrib import messages
from django_otp.plugins.otp_totp.models import TOTPDevice
from core.models import JournalActivite
import qrcode, io, base64
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render, redirect
from django.contrib import messages
from core.models import JournalActivite
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import JournalActivite # Assurez-vous que l'import est correct
import qrcode
import io
import base64

@verifie_compte_non_gele
@login_required
@csrf_protect
def activer_2fa_view(request):
    user = request.user
    ip = request.META.get('REMOTE_ADDR')
    
    # On cherche d'abord s'il y a déjà un device en attente de confirmation
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()

    if request.method == "POST":
        code = request.POST.get("code")
        
        # S'il n'y a pas de device en attente lors du POST, c'est une erreur
        if not device:
            messages.error(request, "Erreur de session. Veuillez recharger la page.")
            return redirect("activer_2fa")

        # On vérifie le token sur le device existant
        if device.verify_token(code):
            device.confirmed = True
            device.save()
            
            # (Optionnel) Supprimer les autres devices non confirmés pour faire propre
            TOTPDevice.objects.filter(user=user, confirmed=False).exclude(id=device.id).delete()
            
            JournalActivite.objects.create(
                utilisateur=user, 
                action="Activation 2FA", 
                resultat="succès", 
                ip=ip
            )
            messages.success(request, "✅ Double authentification activée avec succès !")
            return redirect("profile")
        else:
            messages.error(request, "❌ Code incorrect. Veuillez réessayer.")

    # --- Logique GET (ou si le POST a échoué) ---
    
    # Si aucun device non confirmé n'existe, on en crée un nouveau
    if not device:
        # Nettoyage préventif
        TOTPDevice.objects.filter(user=user, confirmed=False).delete()
        device = TOTPDevice.objects.create(user=user, name="InfraControl-2FA", confirmed=False)

    # Génère le QR code depuis l'URI TOTP du device MAINTENU
    otp_uri = device.config_url
    qr = qrcode.make(otp_uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, "auth/activer_2fa.html", {"qr_code_base64": qr_code_base64})
from django.contrib.auth import get_user_model
User = get_user_model()

@verifie_compte_non_gele
def verification_2fa(request):
    user_id = request.session.get('pending_2fa_user')
    if not user_id:
        return redirect('connexion')

    user = User.objects.get(id=user_id)
    device = next(devices_for_user(user))

    if request.method == "POST":
        code = request.POST.get("code")
        if device.verify_token(code):
            login(request, user)
            del request.session['pending_2fa_user']
            messages.success(request, "✅ Vérification 2FA réussie.")
            JournalActivite.objects.create(utilisateur=user, action="Connexion 2FA réussie", resultat="succès")
            return redirect('profile')
        else:
            messages.error(request, "❌ Code invalide.")

    return render(request, 'auth/verification_2fa.html')


@verifie_compte_non_gele
@csrf_protect
def confirm_reset_2fa(request):
    """Vérifie le code reçu par email et désactive le 2FA si valide."""
    if request.method == "POST":
        email = request.POST.get("email")
        code_saisi = request.POST.get("code")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "❌ Compte introuvable.")
            return redirect("confirm_reset_2fa")

        cache_key = f"reset2fa_{user.id}"
        code_en_cache = cache.get(cache_key)

        if code_en_cache and code_en_cache == code_saisi:
            # Suppression des devices 2FA
            from django_otp.plugins.otp_totp.models import TOTPDevice
            TOTPDevice.objects.filter(user=user).delete()
            cache.delete(cache_key)

            JournalActivite.objects.create(
                utilisateur=user,
                action="Réinitialisation 2FA réussie",
                resultat="succès",
                ip=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, "✅ Votre double authentification a été réinitialisée. Vous pouvez vous reconnecter.")
            return redirect("connexion")
        else:
            messages.error(request, "❌ Code invalide ou expiré.")

    return render(request, "auth/confirm_reset_2fa.html")


from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.conf import settings
import threading
from .models import Profil, JournalActivite
from django.contrib.auth.models import User

@verifie_compte_non_gele
@csrf_protect
def reset_2fa_request(request):
    """Permet à l'utilisateur de demander une réinitialisation 2FA (via email sécurisé)"""
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "❌ Aucun compte associé à cet email.")
            return redirect("reset_2fa_request")

        # Génération d’un code temporaire
        code = get_random_string(8).upper()
        cache_key = f"reset2fa_{user.id}"
        cache.set(cache_key, code, timeout=600)  # valable 10 min

        # Envoi de l’email asynchrone
        def envoyer_mail_reset():
            try:
                contexte = {"user": user, "code": code}
                html_message = render_to_string("emails/reset_2fa_email.html", contexte)
                msg = EmailMultiAlternatives(
                    subject="🔐 Réinitialisation 2FA - InfraControl",
                    body=f"Votre code de réinitialisation : {code}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=True)
            except Exception as e:
                print(f"[Erreur email reset_2fa] {e}")

        threading.Thread(target=envoyer_mail_reset).start()
        
        ap = request.META.get('REMOTE_ADDR')
        alerte_admin("Demande reset 2fa",ap, details=email )

        JournalActivite.objects.create(
            utilisateur=user,
            action="Demande de réinitialisation 2FA",
            resultat="En attente de vérification",
            ip=request.META.get('REMOTE_ADDR')
        )

        messages.info(request, "📧 Un code de vérification a été envoyé à votre adresse email.")
        return redirect("confirm_reset_2fa")

    return render(request, "auth/reset_2fa_request.html")


from django.contrib.auth.decorators import login_required
from core.models import JournalActivite

from monitoring.models import EquipementReseau, Incident, Maintenance
from remediation.models import HistoriqueRemediation

@verifie_compte_non_gele
@login_required
def dashboard_view(request):
    # Fetching metrics for the Global Dashboard
    total_equipements = EquipementReseau.objects.count()
    equipements_hors_ligne = EquipementReseau.objects.filter(statut='hors ligne').count()
    incidents_ouverts = Incident.objects.filter(statut='ouvert').count()
    maintenances_actives = Maintenance.objects.filter(active=True).count()
    
    activites = JournalActivite.objects.all().order_by('-date_action')[:8]
    derniers_incidents = Incident.objects.all().order_by('-date_debut')[:5]
    dernieres_remediations = HistoriqueRemediation.objects.all().order_by('-date_action')[:5]
    
    context = {
        'activites': activites,
        'total_equipements': total_equipements,
        'equipements_hors_ligne': equipements_hors_ligne,
        'incidents_ouverts': incidents_ouverts,
        'maintenances_actives': maintenances_actives,
        'derniers_incidents': derniers_incidents,
        'dernieres_remediations': dernieres_remediations,
    }
    return render(request, 'core/dashboard.html', context)


# core/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from core.models import JournalActivite
from datetime import timedelta


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def logs_dashboard_view(request):
    """
    Tableau de bord d'analyse des logs d'activité.
    Réservé aux administrateurs.
    """

    # --- Filtres ---
    filtre_jour = request.GET.get("jours", 7)
    try:
        nb_jours = int(filtre_jour)
    except ValueError:
        nb_jours = 7

    date_limite = timezone.now() - timedelta(days=nb_jours)
    logs = JournalActivite.objects.filter(date_action__gte=date_limite)

    # --- Statistiques globales ---
    total_logs = logs.count()
    connexions_reussies = logs.filter(action__icontains="connexion", resultat__icontains="succès").count()
    connexions_echouees = logs.filter(action__icontains="connexion", resultat__icontains="échec").count()
    bots_detectes = logs.filter(action__icontains="bot").count()
    verifications = logs.filter(action__icontains="vérification").count()

    # --- Regroupement par jour pour le graphique ---
    stats_journalieres = (
        logs.annotate(jour=TruncDate("date_action"))
        .values("jour")
        .annotate(total=Count("id"))
        .order_by("jour")
    )

    chart_labels = [entry["jour"].strftime("%d/%m") for entry in stats_journalieres]
    chart_values = [entry["total"] for entry in stats_journalieres]

    # --- Top utilisateurs actifs ---
    top_users = (
        logs.values("utilisateur__username")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    contexte = {
        "total_logs": total_logs,
        "connexions_reussies": connexions_reussies,
        "connexions_echouees": connexions_echouees,
        "bots_detectes": bots_detectes,
        "verifications": verifications,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "top_users": top_users,
        "filtre_jour": nb_jours,
    }

    return render(request, "admin/logs_dashboard.html", contexte)


import subprocess, platform, time
from django.http import JsonResponse
from core.models import JournalActivite

@verifie_compte_non_gele
def test_ping(request):
    """Teste la connectivité réseau (ping vers une IP ou un domaine)."""
    cible = request.GET.get("host", "8.8.8.8")  # par défaut : Google DNS
    start = time.time()
    system = platform.system().lower()

    try:
        cmd = ["ping", "-n", "1", cible] if "windows" in system else ["ping", "-c", "1", cible]
        resultat = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        success = resultat.returncode == 0
        duration = round((time.time() - start) * 1000, 2)  # ms

        JournalActivite.objects.create(
            utilisateur=request.user if request.user.is_authenticated else None,
            action=f"Test ping vers {cible}",
            resultat="succès" if success else "échec",
            ip=request.META.get("REMOTE_ADDR"),
        )

        return JsonResponse({
            "host": cible,
            "status": "reachable" if success else "unreachable",
            "response_time_ms": duration
        })
    except Exception as e:
        JournalActivite.objects.create(
            utilisateur=request.user if request.user.is_authenticated else None,
            action=f"Test ping vers {cible}",
            resultat=f"erreur : {e}",
            ip=request.META.get("REMOTE_ADDR"),
        )
        return JsonResponse({"error": str(e)}, status=500)
    
    
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse
from core.models import JournalActivite
import requests, threading

def test_alerte(request):
    """Test d’envoi d’une alerte de sécurité (mail + webhook)."""
    try:
        # ✅ Envoi email admin
        send_mail(
            subject="🛑 Test Alerte InfraControl",
            message="Ceci est un test d’alerte — tout fonctionne ✅",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin[1] for admin in settings.ADMINS],
            fail_silently=True,
        )

        # ✅ Envoi webhook Slack / Brevo / Teams
        def envoyer_webhook():
            payload = {
                "text": "🚨 *Test d’alerte InfraControl* : la notification fonctionne bien !",
                "username": "InfraBot",
                "icon_emoji": ":satellite:"
            }
            try:
                requests.post(settings.WEBHOOK_ALERT_URL, json=payload, timeout=5)
            except Exception as e:
                print(f"[Webhook erreur] {e}")

        threading.Thread(target=envoyer_webhook).start()

        # ✅ Log système
        JournalActivite.objects.create(
            utilisateur=request.user if request.user.is_authenticated else None,
            action="Test alerte système",
            resultat="succès",
            ip=request.META.get("REMOTE_ADDR"),
        )

        return JsonResponse({"status": "ok", "message": "Alerte envoyée avec succès"})
    except Exception as e:
        JournalActivite.objects.create(
            utilisateur=request.user if request.user.is_authenticated else None,
            action="Test alerte système",
            resultat=f"échec : {e}",
            ip=request.META.get("REMOTE_ADDR"),
        )
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
    
    
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import time

@csrf_exempt
def set_form_start_time(request):
    """Enregistre le moment où l'utilisateur a reçu le formulaire."""
    request.session["form_start_time"] = time.time()
    return JsonResponse({"status": "ok"})


from django.contrib.auth.decorators import login_required
from core.models import JournalActivite

@login_required
def dashboard_view(request):
    activites = JournalActivite.objects.filter(utilisateur=request.user).order_by('-date_action')[:10]
    return render(request, 'core/dashboard.html', {'activites': activites})


import io
import qrcode
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django_otp.plugins.otp_totp.models import TOTPDevice

@login_required
def qr_code_2fa(request):
    if not user.is_authenticated:
        return HttpResponse(status=403)
    """
    Génère le QR Code TOTP pour Google Authenticator / Authy.
    """
    user = request.user

    # Vérifie s’il a déjà un device 2FA, sinon crée-le
    device, created = TOTPDevice.objects.get_or_create(user=user, name="default")

    # Génère l’URL d’enregistrement compatible Google Authenticator
    otp_url = device.config_url

    # Génère le QR code
    qr = qrcode.make(otp_url)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(buffer.getvalue(), content_type="image/png")


from django.contrib.auth.decorators import login_required
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate
from core.models import JournalActivite

@csrf_protect
@login_required
def desactiver_2fa(request):
    """
    Désactive la double authentification après vérification du mot de passe.
    """
    user = request.user
    ip = request.META.get("REMOTE_ADDR")

    if request.method == "POST":
        password = request.POST.get("password")

        # Vérifie que l'utilisateur est bien le propriétaire du compte
        user_auth = authenticate(username=user.username, password=password)
        if not user_auth:
            messages.error(request, "❌ Mot de passe incorrect.")
            JournalActivite.objects.create(
                utilisateur=user,
                action="Tentative de désactivation 2FA",
                resultat="mot de passe incorrect",
                ip=ip
            )
            return redirect("desactiver_2fa")

        # Supprime tous les dispositifs 2FA liés à cet utilisateur
        TOTPDevice.objects.filter(user=user).delete()

        JournalActivite.objects.create(
            utilisateur=user,
            action="Désactivation de la double authentification",
            resultat="succès",
            ip=ip
        )

        messages.success(request, "✅ Double authentification désactivée avec succès.")
        return redirect("profile")

    return render(request, "auth/desactiver_2fa.html", {"user": user})

from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.cache import cache
from core.models import CodeVerification, JournalActivite
from django.contrib.auth.models import User

@csrf_protect
def verification_reset(request):
    """Vérifie le code envoyé par e-mail avant la réinitialisation du mot de passe."""
    ip = request.META.get('REMOTE_ADDR', 'unknown')

    # 🧱 Anti-bot honeypot
    if request.method == "POST" and request.POST.get('website'):
        JournalActivite.objects.create(
            action="Bot détecté sur vérification reset",
            ip=ip,
            resultat="échec"
        )
        messages.error(request, "🤖 Activité suspecte détectée.")
        return redirect('connexion')

    # Vérifie la session utilisateur
    user_id = request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, "⚠️ Session expirée. Veuillez recommencer la procédure.")
        return redirect('demande_reset')

    user = get_object_or_404(User, id=user_id)
    cache_key = f"reset_attempts_{user.id}_{ip}"
    attempts = cache.get(cache_key, 0)

    # 🚫 Trop de tentatives
    if attempts >= 5:
        messages.error(request, "🚫 Trop de tentatives échouées. Réessayez plus tard.")
        return redirect('connexion')

    if request.method == "POST":
        code_saisi = request.POST.get('code')
        code_obj = get_object_or_404(CodeVerification, user=user)

        # Vérifie expiration
        if code_obj.est_expire():
            messages.error(request, "⏰ Ce code a expiré. Veuillez en demander un nouveau.")
            JournalActivite.objects.create(
                utilisateur=user,
                action="Code reset expiré",
                resultat="échec",
                ip=ip
            )
            code_obj.delete()
            return redirect('demande_reset')

        # Vérifie correspondance du code
        if code_saisi == code_obj.code:
            # ✅ Succès

            request.session['can_reset_password'] = True
            cache.delete(cache_key)

            JournalActivite.objects.create(
                utilisateur=user,
                action="Code de réinitialisation validé",
                resultat="succès",
                ip=ip
            )

            messages.success(request, "✅ Code validé ! Vous pouvez maintenant définir un nouveau mot de passe.")
            return redirect('reset_password_confirm', token=code_obj.code)

        # ❌ Échec
        attempts += 1
        cache.set(cache_key, attempts, timeout=300)
        code_obj.tentative += 1
        code_obj.save()

        JournalActivite.objects.create(
            utilisateur=user,
            action="Échec de vérification code reset",
            resultat="échec",
            ip=ip
        )
        messages.error(request, f"❌ Code incorrect ({attempts}/5).")

    return render(request, 'auth/verification_reset.html')
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import make_password
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
@csrf_protect
def reset_password_confirm_view(request, token):
    """
    Étape finale : l’utilisateur entre un nouveau mot de passe après validation du code OTP.
    """
    ip = request.META.get('REMOTE_ADDR', 'unknown')

    # Vérifie si l'utilisateur a bien le droit de changer son mot de passe
    if not request.session.get('can_reset_password'):
        messages.error(request, "⚠️ Session expirée ou non autorisée.")
        return redirect('demande_reset')

    # Vérifie que le token correspond à un utilisateur valide
    code_obj = CodeVerification.objects.filter(code=token).first()
    if not code_obj:
        messages.error(request, "❌ Lien invalide ou expiré.")
        return redirect('demande_reset')

    user = code_obj.user

    # Vérifie que le code n'est pas expiré
    if code_obj.est_expire():
        messages.error(request, "⏰ Ce lien a expiré. Veuillez recommencer la procédure.")
        code_obj.delete()
        return redirect('demande_reset')

    if request.method == "POST":
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        honeypot = request.POST.get('website')

        # 🧱 Protection anti-bot
        if honeypot:
            JournalActivite.objects.create(
                utilisateur=user,
                action="Bot détecté sur reset password",
                resultat="échec",
                ip=ip
            )
            messages.error(request, "🤖 Activité suspecte détectée.")
            return redirect('connexion')

        # ✅ Validation basique
        if not password1 or not password2:
            messages.error(request, "⚠️ Tous les champs sont obligatoires.")
            return redirect('reset_password_confirm', token=token)

        if password1 != password2:
            messages.error(request, "❌ Les mots de passe ne correspondent pas.")
            return redirect('reset_password_confirm', token=token)

        if len(password1) < 8:
            messages.warning(request, "⚠️ Le mot de passe doit contenir au moins 8 caractères.")
            return redirect('reset_password_confirm', token=token)

        # 🔐 Mise à jour du mot de passe
        user.password = make_password(password1)
        user.save()

        # ✅ Supprime le code après succès
        code_obj.delete()

        # Maintient la session si l’utilisateur est connecté
        update_session_auth_hash(request, user)

        JournalActivite.objects.create(
            utilisateur=user,
            action="Réinitialisation du mot de passe réussie",
            resultat="succès",
            ip=ip
        )

        # Nettoyage session
        request.session.pop('can_reset_password', None)

        messages.success(request, "✅ Votre mot de passe a été modifié avec succès. Vous pouvez maintenant vous connecter.")
        return redirect('connexion')

    return render(request, 'auth/reset_password_confirm.html', {'token': token, 'user': user})


@login_required
@csrf_protect
def recuperer_compte_view(request):
    profil = request.user.profil
    if profil.est_gelé:
        profil.annuler_suppression()

        # Envoi d’un mail de confirmation
        def envoyer_email():
            try:
                contexte = {'username': request.user.username}
                html_message = render_to_string('emails/compte_reactive.html', contexte)
                msg = EmailMultiAlternatives(
                    subject="✅ Votre compte InfraControl a été réactivé",
                    body="Votre compte a été récupéré avec succès.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[request.user.email],
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=True)
            except Exception as e:
                print(f"[Erreur email réactivation] {e}")

        threading.Thread(target=envoyer_email).start()

        messages.success(request, "✅ Votre compte a été restauré avec succès.")
        return redirect('profile')
    else:
        messages.info(request, "Votre compte n’est pas en attente de suppression.")
        return redirect('profile')
    
    
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import threading

@login_required
@csrf_protect
def supprimer_compte_view(request):
    user = request.user
    profil = user.profil
    ip = request.META.get('REMOTE_ADDR', 'unknown')

    if request.method == "POST":
        profil.programmer_suppression()

        # Envoi de l’e-mail de confirmation (asynchrone)
        def envoyer_email():
            try:
                contexte = {
                    'username': user.username,
                    'date_suppression': profil.date_suppression_programmee.strftime('%d/%m/%Y %H:%M')
                }
                html_message = render_to_string('emails/compte_suppression_programme.html', contexte)
                msg = EmailMultiAlternatives(
                    subject="Votre compte InfraControl sera supprimé bientôt ❄️",
                    body=f"Votre compte a été programmé pour suppression le {profil.date_suppression_programmee}.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email],
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=True)
            except Exception as e:
                print(f"[Erreur envoi email suppression] {e}")

        threading.Thread(target=envoyer_email).start()

        # Journalisation
        JournalActivite.objects.create(
            utilisateur=user,
            action="Demande de suppression de compte",
            resultat="succès",
            ip=ip
        )

        logout(request)
        messages.warning(request, "🧊 Votre compte a été gelé. Vous pouvez le récupérer dans les 7 prochains jours.")
        return redirect('connexion')

    return redirect('profile')

@login_required
def page_compte_gele_view(request):
    """Page affichée si l’utilisateur tente d’accéder alors que son compte est gelé."""
    profil = request.user.profil
    if not profil.est_gelé:
        return redirect('profile')

    # Si le compte est gelé, on affiche la page spéciale
    return render(request, 'auth/compte_gele.html', {
        'date_suppression': profil.date_suppression_programmee
    })