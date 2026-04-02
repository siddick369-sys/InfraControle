from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from monitoring.models import EquipementReseau
from .models import EquipementDecouvert
from .tasks import scanner_reseau_auto


@login_required
def liste_decouvertes(request):
    """
    Affiche les équipements découverts.
    - Le scan réseau est déclenché via Celery (non bloquant)
    - L’ajout manuel reste inchangé
    """

    # ==========================
    # 🔍 LANCEMENT DU SCAN (ASYNC)
    # ==========================
    if request.method == "POST" and "scan" in request.POST:
        custom_subnet = request.POST.get("custom_subnet")
        subnets = [custom_subnet] if custom_subnet else None
        
        scanner_reseau_auto.delay(subnets=subnets)
        
        msg = "🔍 Scan du réseau lancé"
        if custom_subnet:
            msg += f" sur {custom_subnet}"
        msg += " en arrière-plan."
        
        messages.info(request, msg)
        return redirect("liste_decouvertes")

    # ==========================
    # ➕ AJOUT D’UN ÉQUIPEMENT
    # ==========================
    if request.method == "POST" and "ajouter" in request.POST:
        ip = request.POST.get("ip")
        hostname = request.POST.get("hostname")
        type_detecte = request.POST.get("type")

        if EquipementReseau.objects.filter(adresse_ip=ip).exists():
            messages.warning(request, f"{ip} est déjà supervisé.")
            return redirect("liste_decouvertes")

        EquipementReseau.objects.create(
            nom=hostname or ip,
            adresse_ip=ip,
            type_equipement=type_detecte or "autre",
            statut="inconnu",
            cree_par=request.user,
        )

        EquipementDecouvert.objects.filter(
            adresse_ip=ip
        ).update(ajoute=True)

        messages.success(
            request,
            f"Équipement {hostname or ip} ajouté avec succès."
        )
        return redirect("liste_decouvertes")

    # ==========================
    # 📋 RECHERCHE & PAGINATION
    # ==========================
    query = request.GET.get("q", "")
    decouvertes_list = EquipementDecouvert.objects.all().order_by("-vu_le")

    if query:
        decouvertes_list = decouvertes_list.filter(
            Q(hostname__icontains=query) |
            Q(type_detecte__icontains=query) |
            Q(adresse_ip__icontains=query) |
            Q(adresse_mac__icontains=query)
        )

    paginator = Paginator(decouvertes_list, 5) # 5 découvertes par page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "discovery/liste_decouvertes.html",
        {
            "page_obj": page_obj,
            "query": query,
        }
    )