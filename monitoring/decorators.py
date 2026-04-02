from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from functools import wraps
from datetime import timedelta


def critical_access_required(view_func):
    """Décorateur pour protéger les pages critiques."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        critical_access = request.session.get("critical_access", False)
        critical_time = request.session.get("critical_access_time")

        # Vérifie si un accès critique est actif et récent (< 10 minutes)
        if not critical_access or not critical_time:
            messages.warning(request, "🔐 Vous devez confirmer votre mot de passe pour accéder à cette page.")
            return redirect(f"{reverse('motdepasse')}?next={request.path}")

        last_time = timezone.datetime.fromisoformat(critical_time)
        if timezone.now() - last_time > timedelta(minutes=10):
            messages.info(request, "⏰ Votre session critique a expiré.")
            request.session["critical_access"] = False
            return redirect(f"{reverse('motdepasse')}?next={request.path}")

        return view_func(request, *args, **kwargs)

    return wrapper