from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def verifie_compte_non_gele(view_func):
    """
    🧊 Décorateur : empêche un utilisateur avec un compte gelé d’accéder à la vue.
    Redirige vers la page 'compte_gele' avec un message d’alerte.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            profil = getattr(request.user, "profil", None)
            if profil and getattr(profil, "est_gelé", False):
                messages.warning(request, "🚨 Votre compte est gelé. Veuillez le réactiver.")
                return redirect("compte_gele")
        return view_func(request, *args, **kwargs)

    return wrapper