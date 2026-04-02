import time, hmac, hashlib, base64, random, string
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden


class BotDefenseMiddleware(MiddlewareMixin):
    """
    Middleware anti-bot furtif adaptatif :
    - Bloque bots IA et automatisés
    - En mode DEBUG, se contente de LOGUER les tentatives
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        try:
            # On cible uniquement les formulaires sensibles
            if request.method == "POST" and any(p in request.path for p in ["connexion", "inscription", "reset", "verification"]):
                dynamic_key = request.session.get("_stealth_key")
                trap_name = request.session.get("_trap_field")
                token = request.POST.get(dynamic_key)
                trap_value = request.POST.get(trap_name)
                start_time = request.session.get("form_start_time")

                # --- MODE DEBUG : on affiche seulement les alertes ---
                if settings.DEBUG:
                    print("⚠️ [DEBUG BotDefense] Vérification humaine simulée")
                    if not token:
                        print("⚠️ [DEBUG] Token manquant → ignoré (mode dev)")
                    if not start_time:
                        print("⚠️ [DEBUG] Aucun délai enregistré → ignoré (mode dev)")
                    if trap_value != "ok":
                        print("⚠️ [DEBUG] Champ invisible non rempli → ignoré (mode dev)")
                    return None

                # --- MODE PRODUCTION : sécurité stricte ---
                # Vérifie délai humain minimal
                if not start_time or time.time() - start_time < 2.3:
                    return self._block_request(request, "Soumission trop rapide (bot probable)")

                # Vérifie le champ honeypot
                if trap_value != "ok":
                    return self._block_request(request, "Champ invisible incorrect")

                # Vérifie le token signé
                if not token or not self._verify_token(token, dynamic_key):
                    return self._block_request(request, "Token non valide ou falsifié")

        except Exception as e:
            print(f"[Middleware Error] {e}")
            # En mode debug, on ne bloque pas
            if not settings.DEBUG:
                return self._block_request(request, f"Erreur interne sécurité: {e}")

        return None


    def _block_request(self, request, raison):
        """Blocage + log en base"""
        from core.models import JournalActivite

        JournalActivite.objects.create(
            utilisateur=request.user if request.user.is_authenticated else None,
            action="Tentative bot détectée (stealth)",
            resultat=raison,
            ip=request.META.get('REMOTE_ADDR'),
        )

        return HttpResponseForbidden("🚫 Vérification humaine échouée (Stealth mode activé).")


    def _verify_token(self, token, dynamic_key):
        """Vérifie la validité du token signé"""
        try:
            msg, signature = token.split(":")
            secret_key = (settings.SECRET_KEY + (dynamic_key or "")).encode()
            expected = hmac.new(secret_key, msg.encode(), hashlib.sha256).digest()
            return hmac.compare_digest(base64.urlsafe_b64encode(expected).decode(), signature)
        except Exception:
            return False


    @staticmethod
    def generate_stealth_fields(request):
        """Crée des noms de champs et tokens uniques à chaque chargement"""
        key_name = "_" + ''.join(random.choices(string.ascii_lowercase, k=8))
        trap_name = "fld_" + ''.join(random.choices(string.ascii_lowercase, k=10))
        timestamp = str(int(time.time()))
        secret_key = (settings.SECRET_KEY + key_name).encode()

        signature = hmac.new(secret_key, timestamp.encode(), hashlib.sha256).digest()
        token = f"{timestamp}:{base64.urlsafe_b64encode(signature).decode()}"

        request.session["_stealth_key"] = key_name
        request.session["_trap_field"] = trap_name
        request.session["form_start_time"] = time.time()

        return {
            "dynamic_key": key_name,
            "trap_name": trap_name,
            "token": token,
        }
        
from django.shortcuts import redirect
from django.urls import reverse
from django.shortcuts import redirect
from django.urls import resolve

class CompteGeleMiddleware:
    """
    🔒 Redirige tout utilisateur ayant un compte gelé vers la page 'compte_gele'
    sauf pour les routes autorisées.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Vérifie uniquement les utilisateurs connectés
        if request.user.is_authenticated:
            profil = getattr(request.user, "profil", None)

            if profil and profil.est_gelé:
                try:
                    current_url_name = resolve(request.path_info).url_name
                except Exception:
                    current_url_name = None

                # URLs autorisées (ne pas rediriger)
                exempt_views = ['compte_gele', 'recuperer_compte', 'deconnexion', 'admin:logout']

                if current_url_name not in exempt_views:
                    return redirect('compte_gele')

        # Si tout va bien → on passe à la vue
        response = self.get_response(request)
        return response