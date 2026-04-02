from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import threading
from core.models import JournalActivite

def alerte_admin(action: str, ip: str, details: str = ""):
    """Alerte admin en cas de comportement suspect (bot, bruteforce, etc.)"""
    sujet = f"⚠️ Alerte sécurité - {action}"
    message = (
        f"🚨 Une activité suspecte a été détectée sur InfraControl.\n\n"
        f"📅 Date : {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🔍 Action : {action}\n"
        f"🌐 Adresse IP : {ip}\n"
        f"📝 Détails : {details or 'Aucun détail fourni.'}\n\n"
        "Veuillez vérifier immédiatement le Journal des activités administrateur."
    )

    # Enregistrement dans le journal
    JournalActivite.objects.create(utilisateur=None, action=f"[ALERTE] {action}", ip=ip, resultat="suspicion")

    # Envoi email admin (threadé)
    def _send_email():
        try:
            send_mail(
                sujet,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [admin_email for admin_email in getattr(settings, "ADMIN_EMAILS", [])],
                fail_silently=True
            )
        except Exception as e:
            print(f"[Erreur alerte admin] {e}")

    threading.Thread(target=_send_email).start()
    
    
from django_otp.plugins.otp_totp.models import TOTPDevice
import qrcode
import io
from django.http import HttpResponse

def get_or_create_device(user):
    """Retourne ou crée le TOTPDevice de l'utilisateur"""
    device, created = TOTPDevice.objects.get_or_create(
        user=user,
        name="InfraControl Authenticator",
        confirmed=False
    )
    return device

def qr_code_2fa(request):
    """Affiche le QR code du compte InfraControl à scanner avec Google Authenticator"""
    user = request.user
    device = get_or_create_device(user)
    img = qrcode.make(device.config_url)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')