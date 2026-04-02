from django.shortcuts import render

# Create your views here.

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from .tasks import generer_rapport_executif


@login_required
def generer_rapport_executif_view(request):
    mode = request.GET.get("mode", "auto")

    # Lancement async
    generer_rapport_executif.delay(mode_pdf=mode)

    messages.success(
        request,
        "📄 Génération du rapport exécutif lancée. "
        "Le PDF sera disponible sous peu."
    )

    # return redirect("liste_rapports_executifs")
    return redirect("liste_equipements")