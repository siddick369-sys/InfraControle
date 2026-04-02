from django.shortcuts import render

# Create your views here.

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

from aiengine.tasks import analyser_incident_task


from .models import *
from .forms import *
import paramiko
from .decorators import *
# =============================
# 1️⃣ AJOUT D’ÉQUIPEMENT RÉSEAU
# =============================

COMMANDES_SUGGEREES = {
    "CPU élevé": [
        "top -o %CPU",
        "ps aux --sort=-%cpu | head",
        "uptime",
    ],
    "RAM saturée": [
        "free -m",
        "ps aux --sort=-%mem | head",
        "sync && echo 3 | sudo tee /proc/sys/vm/drop_caches",
    ],
    "Disque plein": [
        "df -h",
        "du -sh /var/log/* | sort -h",
        "journalctl --vacuum-time=3d",
    ],
}

   
def get_suggestions_terminal(equipement):
    incidents = Incident.objects.filter(
        equipement=equipement,
        statut="ouvert"
    )

    suggestions = {}
    for i in incidents:
        if i.titre in COMMANDES_SUGGEREES:
            suggestions[i.titre] = COMMANDES_SUGGEREES[i.titre]

    return suggestions

@login_required
@critical_access_required
def ajouter_equipement_view(request):
    """Formulaire d’ajout d’un nouvel équipement réseau"""
    if request.method == "POST":
        form = EquipementReseauForm(request.POST)
        if form.is_valid():
            equipement = form.save(commit=False)
            equipement.cree_par = request.user
            equipement.save()
            messages.success(request, f"✅ Équipement '{equipement.nom}' ajouté avec succès !")
            return redirect('liste_equipements')
        else:
            messages.error(request, "❌ Erreur dans le formulaire. Vérifiez les champs.")
    else:
        form = EquipementReseauForm()
    return render(request, 'monitoring/ajouter_equipement.html', {'form': form})


@login_required
def modifier_equipement_view(request, equipement_id):
    """Vue pour modifier un équipement existant (via modal ou page)"""
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)
    
    # 🔒 1️⃣ Permission Check
    if not request.user.is_superuser and equipement.cree_par != request.user:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"status": "error", "errors": "🚫 Vous n’avez pas la permission de modifier cet équipement."}, status=403)
        messages.error(request, "🚫 Vous n’avez pas la permission de modifier cet équipement.")
        return redirect("detail_equipement", equipement_id=equipement.id)

    # 🔑 2️⃣ Critical Access Check
    critical_access = request.session.get("critical_access", False)
    critical_time = request.session.get("critical_access_time")
    if not critical_access or not critical_time:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                "status": "error", 
                "errors": "🔐 Confirmation de mot de passe requise.",
                "redirect_url": f"{reverse('motdepasse')}?next={reverse('liste_equipements')}"
            }, status=403)
        messages.warning(request, "🔐 Confirmation requise pour modifier cet équipement.")
        return redirect(f"{reverse('motdepasse')}?next={request.path}")
    
    if request.method == "POST":
        form = EquipementReseauForm(request.POST, instance=equipement)
        if form.is_valid():
            form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"status": "ok", "message": "✅ Équipement mis à jour !"})
            messages.success(request, f"✅ Équipement '{equipement.nom}' modifié avec succès !")
            return redirect('liste_equipements')
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"status": "error", "errors": form.errors}, status=400)
            messages.error(request, "❌ Erreur dans le formulaire.")
    else:
        form = EquipementReseauForm(instance=equipement)
    
    return render(request, 'monitoring/ajouter_equipement.html', {'form': form, 'equipement': equipement})


# =============================
# 2️⃣ LISTE DES ÉQUIPEMENTS
# =============================

@login_required
def liste_equipements_view(request):
    equipements = EquipementReseau.objects.all().order_by('nom')
    return render(request, 'monitoring/liste_equipements.html', {'equipements': equipements})


# =============================
# 3️⃣ EXÉCUTION D’UNE COMMANDE SSH
# =============================
import paramiko
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from monitoring.models import EquipementReseau, CommandeAutomatique, JournalReseau
COMMANDES_INTERDITES = [
    "rm -rf",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",  # fork bomb
]
def est_commande_dangereuse(cmd):
    return any(d in cmd.lower() for d in COMMANDES_INTERDITES)
from .core import executer_commande_core, est_commande_dangereuse

@login_required
def executer_commande_view(request, equipement_id, commande_id):
    """Exécute une commande distante SSH sur un équipement réseau."""

    equipement = get_object_or_404(EquipementReseau, id=equipement_id)
    commande = get_object_or_404(CommandeAutomatique, id=commande_id)
    ip_user = request.META.get("REMOTE_ADDR", "unknown")

    # 🔒 1️⃣ Sécurité : propriétaire ou superuser (vérification AVANT mot de passe critique)
    if not request.user.is_superuser and equipement.cree_par != request.user:
        messages.error(
            request,
            "🚫 Vous n’avez pas la permission d’exécuter des commandes sur cet équipement."
        )
        return redirect("detail_equipement", equipement_id=equipement.id)

    # 🔑 2️⃣ Accès critique requis pour l'exécution
    # (Appel manuel du check car on a besoin de vérifier les permissions AVANT)
    critical_access = request.session.get("critical_access", False)
    critical_time = request.session.get("critical_access_time")
    
    if not critical_access or not critical_time:
        messages.warning(request, "🔐 Confirmation du mot de passe requise pour exécuter une commande.")
        return redirect(f"{reverse('motdepasse')}?next={request.path}")

    last_time = timezone.datetime.fromisoformat(critical_time)
    if timezone.now() - last_time > timedelta(minutes=10):
        messages.info(request, "⏰ Session critique expirée.")
        request.session["critical_access"] = False
        return redirect(f"{reverse('motdepasse')}?next={request.path}")

    try:
        # Appel de la fonction CORE centralisée (qui gère l'ANSI et le PTY adaptatif)
        resultat = executer_commande_core(
            equipement=equipement,
            commande=commande,
            utilisateur=request.user,
            ip_utilisateur=ip_user
        )

        # ===============================
        # 🟢 FEEDBACK UI
        # ===============================
        if resultat["succes"]:
            messages.success(
                request,
                f"✅ Commande '{commande.nom}' exécutée avec succès."
            )
        else:
            messages.warning(
                request,
                f"⚠️ Commande '{commande.nom}' exécutée avec erreurs."
            )

        return render(
            request,
            "monitoring/resultat_commande.html",
            {
                "equipement": equipement,
                "commande": commande,
                "sortie": resultat["sortie"],
                "succes": resultat["succes"],
            },
        )

    except Exception as e:
        messages.error(request, f"❌ Erreur SSH : {e}")
        return redirect("detail_equipement", equipement_id=equipement.id)
    
from django.http import JsonResponse
import subprocess
import paramiko
import subprocess
import paramiko
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from monitoring.models import EquipementReseau, JournalReseau


@login_required
def tester_connexion_view(request, equipement_id):
    """Teste la connectivité réseau (ping + SSH) d’un équipement."""
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)

    # 🔒 1️⃣ Permission Check
    if not request.user.is_superuser and equipement.cree_par != request.user:
        messages.error(request, "🚫 Permission refusée pour cet équipement.")
        return redirect("detail_equipement", equipement_id=equipement.id)

    # 🔑 2️⃣ Critical Access Check
    critical_access = request.session.get("critical_access", False)
    critical_time = request.session.get("critical_access_time")
    if not critical_access or not critical_time:
        messages.warning(request, "🔐 Confirmation requise pour tester la connexion.")
        return redirect(f"{reverse('motdepasse')}?next={request.path}")
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    success = False
    erreur = None
    sortie_ping = ""
    sortie_ssh = ""

    # 🧩 1️⃣ PING
    try:
        # Ajuste la commande ping selon le système
        ping_cmd = ["ping", "-c", "2", "-W", "2", equipement.adresse_ip]
        if subprocess.run(["uname"], stdout=subprocess.PIPE).returncode != 0:
            # Si Windows, adapte les paramètres
            ping_cmd = ["ping", "-n", "2", equipement.adresse_ip]

        ping = subprocess.run(
            ping_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )

        sortie_ping = ping.stdout.strip() or ping.stderr.strip()

        if ping.returncode != 0:
            equipement.statut = "hors ligne"
            equipement.derniere_verification = timezone.now()
            equipement.save()

            JournalReseau.objects.create(
                equipement=equipement,
                utilisateur=request.user,
                action="Test manuel de connexion (ping)",
                resultat="échec",
                sortie_ssh=sortie_ping,
            )

            messages.error(request, f"❌ Ping échoué pour {equipement.nom}")
            return redirect("detail_equipement", equipement_id=equipement.id)

    except Exception as e:
        erreur = f"Erreur lors du ping : {e}"
        equipement.statut = "erreur"
        equipement.save()
        JournalReseau.objects.create(
            equipement=equipement,
            utilisateur=request.user,
            action="Test manuel de connexion (ping)",
            resultat="échec",
            sortie_ssh=str(e),
        )
        messages.error(request, erreur)
        return redirect("detail_equipement", equipement_id=equipement.id)

    # 🧩 2️⃣ SSH
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=equipement.adresse_ip,
            port=equipement.port_ssh,
            username=equipement.utilisateur_ssh,
            password=equipement.mot_de_passe_ssh,
            timeout=5
        )
        stdin, stdout, stderr = ssh.exec_command("hostname")
        sortie_ssh = stdout.read().decode().strip() or stderr.read().decode().strip()
        ssh.close()

        equipement.statut = "en ligne"
        equipement.derniere_verification = timezone.now()
        equipement.save()

        JournalReseau.objects.create(
            equipement=equipement,
            utilisateur=request.user,
            action="Test manuel de connexion (SSH)",
            resultat="succès",
            sortie_ssh=f"Ping OK\nSSH: {sortie_ssh}",
        )

        messages.success(request, f"✅ Ping + SSH réussis avec {equipement.nom} ({sortie_ssh})")
        success = True

    except Exception as e:
        erreur = f"Erreur SSH : {e}"
        equipement.statut = "hors ligne"
        equipement.derniere_verification = timezone.now()
        equipement.save()

        JournalReseau.objects.create(
            equipement=equipement,
            utilisateur=request.user,
            action="Test manuel de connexion (SSH)",
            resultat="échec",
            sortie_ssh=str(e),
        )
        messages.error(request, f"❌ SSH échoué pour {equipement.nom} : {e}")
    return redirect("detail_equipement", equipement_id=equipement.id)

import json, paramiko, subprocess
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import EquipementReseau, JournalReseau

@login_required
def dashboard_monitoring_view(request):
    equipements = EquipementReseau.objects.all().order_by('nom')
    stats = {
        "total": equipements.count(),
        "connectes": equipements.filter(statut="connecté").count(),
        "deconnectes": equipements.filter(statut="déconnecté").count(),
        "erreurs": equipements.filter(statut="erreur").count(),
    }
    return render(request, "monitoring/dashboard.html", {"equipements": equipements, "stats": stats})
import paramiko, re, subprocess
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import EquipementReseau
@login_required
@csrf_exempt
def get_realtime_stats(request):
    """Retourne les métriques système de chaque équipement en temps réel (CPU, RAM, Disk, Latence)."""
    data = []

    for e in EquipementReseau.objects.filter(actif=True):
        cpu = ram = disk = latence = net = None
        try:
            # --- 1️⃣ Test ping pour latence ---
            ping_cmd = ["ping", "-c", "1", "-W", "2", e.adresse_ip]
            ping = subprocess.run(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            match = re.search(r"time=(\d+\.\d+)\s*ms", ping.stdout)
            if match:
                latence = float(match.group(1))

            # --- 2️⃣ Connexion SSH ---
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=e.adresse_ip,
                port=e.port_ssh,
                username=e.utilisateur_ssh,
                password=e.mot_de_passe_ssh,
                timeout=5
            )

            # --- 3️⃣ Commandes de métriques ---
            cmds = {
                "cpu": "top -bn1 | grep 'Cpu(s)' | awk '{print 100 - $8}'",
                "ram": "free | grep Mem | awk '{print ($3/$2)*100}'",
                "disk": "df -h / | awk 'NR==2{print $5}' | tr -d '%'",
                "net": "cat /proc/net/dev | grep eth0 | awk '{print $2/1024/1024}'"
            }

            for key, cmd in cmds.items():
                stdin, stdout, stderr = ssh.exec_command(cmd)
                val = stdout.read().decode().strip()
                if val:
                    if key in ["cpu", "ram", "disk"]:
                        locals()[key] = round(float(val), 2)
                    elif key == "net":
                        net = round(float(val), 2)

            ssh.close()
            e.cpu_usage = cpu
            e.ram_usage = ram
            e.disk_usage = disk
            e.network_bandwidth = net
            e.latence = latence
            e.statut = "en ligne"
            e.derniere_verification = timezone.now()
            e.save(update_fields=["cpu_usage", "ram_usage", "disk_usage", "network_bandwidth", "latence", "statut", "derniere_verification"])

        except Exception as ex:
            e.statut = "hors ligne"
            e.save(update_fields=["statut"])
            print(f"[ERREUR] {e.nom}: {ex}")

        data.append({
            "id": e.id,
            "nom": e.nom,
            "statut": e.statut,
            "cpu": e.cpu_usage or 0,
            "ram": e.ram_usage or 0,
            "disk": e.disk_usage or 0,
            "net": e.network_bandwidth or 0,
            "latence": e.latence or 0,
        })

    return JsonResponse({"equipements": data, "timestamp": timezone.now().isoformat()})

import paramiko
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import JournalActivite
from .models import EquipementReseau
import paramiko
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.models import JournalActivite
from .models import EquipementReseau

@login_required
def tester_ssh_view(request, equipement_id):
    """
    Teste la connexion SSH à un équipement et enregistre le résultat dans le journal.
    """
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)
    
    # 🔒 1️⃣ Permission Check First
    if not request.user.is_superuser and equipement.cree_par != request.user:
        messages.error(request, "🚫 Permission refusée pour cet équipement.")
        return redirect("detail_equipement", equipement_id=equipement.id)

    # 🔑 2️⃣ Critical Access Check Second
    critical_access = request.session.get("critical_access", False)
    critical_time = request.session.get("critical_access_time")
    
    if not critical_access or not critical_time:
        messages.warning(request, "🔐 Confirmation requise pour tester la connexion.")
        return redirect(f"{reverse('motdepasse')}?next={request.path}")

    last_time = timezone.datetime.fromisoformat(critical_time)
    if timezone.now() - last_time > timedelta(minutes=10):
        request.session["critical_access"] = False
        return redirect(f"{reverse('motdepasse')}?next={request.path}")

    ip = request.META.get("REMOTE_ADDR", "unknown")
    erreur = None

    try:
        # --- Initialisation du client SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # ✅ Utilisation du mot de passe déchiffré !
        ssh.connect(
            hostname=equipement.adresse_ip,
            username=equipement.utilisateur_ssh,
            password=equipement.mot_de_passe_ssh,  # mot de passe déchiffré
            port=equipement.port_ssh or 22,
            timeout=8,
            look_for_keys=False,
            allow_agent=False
        )

        # --- Exécution d'une commande simple pour confirmer
        stdin, stdout, stderr = ssh.exec_command("hostname")
        resultat = stdout.read().decode().strip()
        ssh.close()

        # --- Mise à jour du statut
        equipement.statut = "en ligne"
        equipement.derniere_verification = timezone.now()
        equipement.save()

        JournalActivite.objects.create(
            utilisateur=request.user,
            action=f"Test SSH réussi ({equipement.nom})",
            resultat="succès",
            ip=ip,
            details=f"Réponse : {resultat}"
        )

        messages.success(request, f"✅ Connexion SSH réussie à {equipement.nom} ({resultat})")

    except paramiko.AuthenticationException:
        erreur = "Échec d'authentification : identifiants incorrects."
        equipement.statut = "hors ligne"
        equipement.save()
        messages.error(request, f"❌ {erreur}")

    except paramiko.SSHException as e:
        erreur = f"Erreur SSH : {e}"
        equipement.statut = "hors ligne"
        equipement.save()
        messages.error(request, f"⚠️ {erreur}")

    except Exception as e:
        import traceback 
        
        traceback.print_exc()
        erreur = f"Erreur inattendue : {e}"
        equipement.statut = "hors ligne"
        equipement.save()
        messages.error(request, f"⚠️ {erreur}")

    finally:
        # --- Journalisation systématique (succès ou échec)
        JournalActivite.objects.create(
            utilisateur=request.user,
            action=f"Test SSH sur {equipement.nom}",
            resultat="succès" if not erreur else "échec",
            ip=ip,
            details="Connexion réussie" if not erreur else erreur
        )

    return redirect("detail_equipement", equipement_id=equipement.id)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from core.models import JournalActivite
from .models import EquipementReseau, CommandeAutomatique
import paramiko
import socket
import paramiko, re, subprocess, socket
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from .models import EquipementReseau, CommandeAutomatique

@login_required
def equipement_detail_view(request, equipement_id):
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)
    stat = equipement.stats.order_by("-date_releve").first()

    metrics = []
    if stat:
        metrics = [
        {"label": "CPU", "value": stat.cpu_usage or 0, "unit": "%", "color": "danger"},
        {"label": "RAM", "value": stat.ram_usage or 0, "unit": "%", "color": "warning"},
        {"label": "Disque", "value": stat.disk_usage or 0, "unit": "%", "color": "info"},
        {"label": "Réseau IN", "value": stat.bandwidth_in_mbps or 0, "unit": "Mbps", "color": "success"},
        {"label": "Réseau OUT", "value": stat.bandwidth_out_mbps or 0, "unit": "Mbps", "color": "primary"},
        {"label": "Température", "value": stat.temperature_c or 0, "unit": "°C", "color": "danger"},
    ]


    # 💻 Déduction de l'OS cible basée sur le type
    type_eq = str(equipement.type_equipement).lower()
    
    # Si le type contient 'win' ou 'pc', c'est Windows. Sinon, Linux par défaut.
    os_filtre = 'windows' if ('win' in type_eq or 'pc' in type_eq) else 'linux'
    
    # --- Recherche et Pagination des Commandes ---
    search_query = request.GET.get('q_cmd', '').strip()
    
    commandes_base = CommandeAutomatique.objects.filter(
        Q(os_cible='all') | Q(os_cible=os_filtre)
    ).order_by("nom")

    if search_query:
        commandes_base = commandes_base.filter(
            Q(nom__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(contenu__icontains=search_query)
        )

    paginator = Paginator(commandes_base, 10) # 10 par page
    page_number = request.GET.get('page')
    try:
        commandes = paginator.page(page_number)
    except PageNotAnInteger:
        commandes = paginator.page(1)
    except EmptyPage:
        commandes = paginator.page(paginator.num_pages)

    contexte = {
        "equipement": equipement,
        "stat": stat,
        "metrics": metrics,
        "commandes": commandes,
    }

    return render(request, "monitoring/equipement_detail.html", contexte)

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from django.db import connection
from .models import TentativeAccesCritique
from datetime import timedelta
import re


@login_required
def motdepasse_view(request):
    """Vue de confirmation du mot de passe pour les pages critiques."""
    user = request.user
    tentative, _ = TentativeAccesCritique.objects.get_or_create(user=user)

    # Vérifie si le compte est bloqué
    if tentative.est_bloque():
        restant = (tentative.bloque_jusqua - timezone.now()).seconds // 3600
        messages.error(request, f"⛔ Compte bloqué pour {restant}h en raison de multiples échecs.")
        return render(request, "security/motdepasse.html", {"bloque": True})

    if request.method == "POST":
        password = request.POST.get("password", "").strip()

        # Anti-injection SQL basique
        if re.search(r"(--)|(['\";])|(\b(OR|AND|SELECT|UPDATE|DELETE|INSERT)\b)", password, re.IGNORECASE):
            messages.error(request, "❌ Tentative suspecte détectée !")
            tentative.incrementer()
            return redirect("motdepasse")

        # Vérification du mot de passe Django
        if user.check_password(password):
            tentative.reinitialiser()
            request.session["critical_access"] = True
            request.session["critical_access_time"] = timezone.now().isoformat()
            messages.success(request, "🔓 Accès critique autorisé !")
            return redirect(request.GET.get("next", "dashboard_monitoring"))

        else:
            tentative.incrementer()
            if tentative.nombre_tentatives >= 6:
                tentative.bloquer_24h()
                # Envoi d’un mail d’alerte
                send_mail(
                    "🚨 Tentatives de connexion critique échouées",
                    f"Bonjour {user.username},\n\nVotre compte a été temporairement bloqué (24h) après 6 tentatives de mot de passe erronées sur une page critique.",
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
                messages.error(request, "⚠️ Trop de tentatives. Votre compte est bloqué 24h.")
            else:
                messages.error(request, f"❌ Mot de passe incorrect ({tentative.nombre_tentatives}/6).")

    return render(request, "security/motdepasse.html", {"bloque": tentative.est_bloque()})



from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from monitoring.models import Incident
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from monitoring.models import Incident
from django.db.models import Q

@login_required
def liste_incidents_view(request):
    """Affiche la page principale du centre d'alertes."""
    return render(request, "monitoring/incidents_liste.html")

from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from monitoring.models import Incident

@login_required
def incidents_json_view(request):
    """
    Retourne la liste JSON des incidents visibles pour l’utilisateur connecté.
    - Par défaut : incidents OUVERTS uniquement
    - Un utilisateur normal ne voit que ses équipements
    - Un superutilisateur voit tout
    """

    # ✅ Par défaut : incidents ouverts uniquement
    incidents = Incident.objects.all() \
        .select_related("equipement") \
        .order_by("-date_debut")

    # 🔒 Sécurité multi-utilisateur
    if not request.user.is_superuser:
        incidents = incidents.filter(equipement__cree_par=request.user)

    # 🎛️ Filtres optionnels
    niveau = request.GET.get("niveau")
    statut = request.GET.get("statut")
    recherche = request.GET.get("q")

    if niveau:
        incidents = incidents.filter(niveau=niveau)

    # ⚠️ Si l'utilisateur demande explicitement les résolus
    if statut:
        incidents = Incident.objects.filter(statut=statut)
        if not request.user.is_superuser:
            incidents = incidents.filter(equipement__cree_par=request.user)

    if recherche:
        incidents = incidents.filter(
            Q(equipement__nom__icontains=recherche) |
            Q(titre__icontains=recherche) |
            Q(description__icontains=recherche)
        )

    data = [
        {
            "id": i.id,
            "equipement": i.equipement.nom if i.equipement else "N/A",
            "titre": i.titre,
            "niveau": i.niveau,
            "statut": i.statut,
            "date_debut": i.date_debut.strftime("%d/%m/%Y %H:%M"),
        }
        for i in incidents
    ]

    return JsonResponse({
        "incidents": data,
        "count": len(data),
        "timestamp": timezone.now().isoformat()
    })
@login_required
def marquer_incident_resolu_view(request, incident_id):
    """
    Marque un incident comme résolu.
    """
    incident = get_object_or_404(Incident, id=incident_id)
    if incident.statut == "résolu":
        messages.info(request, "✅ Cet incident est déjà marqué comme résolu.")
    else:
        incident.statut = "résolu"
        incident.date_resolution = timezone.now()
        incident.save()
        messages.success(request, f"✅ Incident '{incident.titre}' marqué comme résolu.")
    return redirect("liste_incidents")


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from monitoring.models import Incident

@login_required
def incidents_non_resolus_count_view(request):
    """
    Retourne le nombre d'incidents ouverts (non résolus)
    au format JSON pour la cloche de notification.
    """
    count = Incident.objects.filter(statut="ouvert").count()
    return JsonResponse({"count": count})

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from monitoring.models import TacheMonitoring

@login_required
def historique_taches_view(request):
    """
    Affiche l’historique des tâches Celery exécutées.
    """
    taches = TacheMonitoring.objects.all()[:50]  # les 50 plus récentes
    return render(request, "monitoring/historique_taches.html", {"taches": taches})



from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from monitoring.models import EquipementReseau, Incident, CommandeAutomatique
from monitoring.smart_monitor import collecter_performance_ssh, collecter_materiel_snmp
import socket
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from monitoring.models import EquipementReseau, CommandeAutomatique, StatReseau
from monitoring.health import calculer_health_score


# (Note: Duplicate equipement_detail_view and its decorator removed)
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from monitoring.models import Incident

@login_required
def compteur_incidents_json(request):
    """
    Retourne le nombre d'incidents OUVERTS visibles pour l'utilisateur.
    - Un utilisateur normal ne voit que ses équipements
    - Un superutilisateur voit tout
    """

    incidents = Incident.objects.filter(statut="ouvert")

    # 🔒 Restriction par propriétaire
    if not request.user.is_superuser:
        incidents = incidents.filter(equipement__cree_par=request.user)

    return JsonResponse({
        "count": incidents.count()
    })
    
    
@login_required
def health_global_json(request):
    qs = StatReseau.objects.filter(
        health_score__lt=50,
        equipement__cree_par=request.user
    ).select_related("equipement")

    if not qs.exists():
        return JsonResponse({"alert": False})

    stat = qs.first()
    return JsonResponse({
        "alert": True,
        "message": f"""
        ⚠️ Équipement critique :
        <b>{stat.equipement.nom}</b><br>
        Score santé : <b>{stat.health_score}</b>
        """
    })
    
import subprocess
import paramiko
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from monitoring.models import EquipementReseau
@login_required
def equipement_statut_json(request, equipement_id):
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)

    return JsonResponse({
        "statut": equipement.statut,
        "latence": equipement.latence,
        "last_check": (
            equipement.derniere_verification.isoformat()
            if equipement.derniere_verification else None
        )
    })
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from datetime import timedelta
from monitoring.models import EquipementReseau, Maintenance
from django.contrib.auth.decorators import login_required

@login_required
def mettre_en_maintenance(request, equipement_id):
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)

    if request.method == "POST":
        Maintenance.objects.create(
            equipement=equipement,
            debut=timezone.now(),
            fin=timezone.now() + timedelta(hours=72),
            active=True,
            cree_par=request.user,
            raison="Maintenance manuelle"
        )

        equipement.statut = "maintenance"
        equipement.save(update_fields=["statut"])

        messages.warning(
            request,
            f"🛠 {equipement.nom} est maintenant en maintenance"
        )

    return redirect("detail_equipement", equipement_id=equipement.id)


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from monitoring.models import EquipementReseau, StatReseau, Incident

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from monitoring.models import EquipementReseau, Maintenance, StatReseau

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from monitoring.models import EquipementReseau, Incident, Maintenance


@login_required
def equipement_reparer(request, equipement_id):
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)

    # 1️⃣ Résoudre TOUS les incidents ouverts
    Incident.objects.filter(
        equipement=equipement,
        statut="ouvert"
    ).update(
        statut="résolu",
        date_resolution=timezone.now(),
        notifie=False
    )

    # 2️⃣ Sortir de maintenance (auto ou manuelle)
    Maintenance.objects.filter(
        equipement=equipement,
        active=True
    ).update(
        active=False,
        fin=timezone.now()
    )

    # 3️⃣ Réinitialiser état équipement
    equipement.statut = "en ligne"
    equipement.echec_consecutif = 0
    equipement.derniere_verification = timezone.now()
    equipement.save(update_fields=[
        "statut",
        "echec_consecutif",
        "derniere_verification"
    ])

    # 4️⃣ Réinitialiser le score santé
    stat = equipement.stats.first()
    if stat:
        stat.health_score = 100
        stat.alerte_envoyee = False
        stat.date_releve = timezone.now()
        stat.save(update_fields=[
            "health_score",
            "alerte_envoyee",
            "date_releve"
        ])

    messages.success(
        request,
        f"🛠️ {equipement.nom} réparé et remis en service"
    )

    return redirect("detail_equipement", equipement_id=equipement.id)
@login_required
def terminal_equipement(request, e_id):
    equipement = get_object_or_404(EquipementReseau, id=e_id)
    return render(request, "monitoring/terminal.html", {
        "equipement": equipement,
        "suggestions": get_suggestions_terminal(equipement),
    })
    
 



@login_required
def toggle_alertes_email(request, equipement_id):
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)

    # 🔒 1️⃣ Permission Check
    if not request.user.is_superuser and equipement.cree_par != request.user:
        messages.error(request, "🚫 Permission refusée.")
        return redirect("detail_equipement", equipement_id=equipement.id)

    # 🔑 2️⃣ Critical Access Check
    critical_access = request.session.get("critical_access", False)
    critical_time = request.session.get("critical_access_time")
    if not critical_access or not critical_time:
        messages.warning(request, "🔐 Confirmation requise pour changer les réglages d'alerte.")
        return redirect(f"{reverse('motdepasse')}?next={request.path}")

    equipement.alertes_email_active = not equipement.alertes_email_active
    equipement.save(update_fields=["alertes_email_active"])

    if equipement.alertes_email_active:
        messages.success(request, f"🔔 Alertes email ACTIVÉES pour {equipement.nom}")
    else:
        messages.warning(request, f"🔕 Alertes email DÉSACTIVÉES pour {equipement.nom}")

    return redirect("detail_equipement", equipement_id=equipement.id)

# monitoring/views.py
from django.shortcuts import render

def noc_view(request):
    return render(request, "monitoring/noc.html")
# monitoring/views.py
from django.http import JsonResponse
from django.utils import timezone
from monitoring.models import EquipementReseau, StatReseau
def noc_status_api(request):
    data = []

    for e in EquipementReseau.objects.all():
        stat = e.stats.first()

        data.append({
            "id": e.id,
            "nom": e.nom,
            "type": getattr(e, "type_equipement", "Inconnu"),
            "statut": e.statut,
            "health": stat.health_score if stat else None,
            "cpu": stat.cpu_usage if stat else None,
            "ram": stat.ram_usage if stat else None,
            "disk": stat.disk_usage if stat else None,
            "last_check": (
                stat.date_releve.isoformat()
                if stat else None
            )
        })

    return JsonResponse({
        "timestamp": timezone.now().isoformat(),
        "equipements": data
    })
    
    
from django.shortcuts import render
from django.contrib.auth.decorators import login_required



from django.http import JsonResponse
from monitoring.models import EquipementReseau, LienReseau

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import EquipementReseau, LienReseau

@login_required
def network_map_api(request):
    nodes = []
    links = []

    # On prépare les nœuds
    for e in EquipementReseau.objects.all():
        # Mapping des couleurs selon statut
        color_map = {
            'en ligne': '#10b981',  # Vert
            'hors ligne': '#ef4444', # Rouge
            'inconnu': '#94a3b8',   # Gris
        }
        
        # Cas particulier latence (Warning si > 100ms par ex)
        color = color_map.get(e.statut, '#94a3b8')
        if e.statut == 'en ligne' and e.latence and e.latence > 100:
            color = '#f59e0b' # Orange

        # Tooltip riche
        tooltip = (
            f"<div class='p-2' style='min-width:150px; background: rgba(15, 23, 42, 0.9); color: white; border-radius: 8px; border: 1px solid {color}'>"
            f"<b class='d-block mb-1' style='font-size: 1.1rem;'>{e.nom}</b>"
            f"<small class='text-muted d-block mb-2'>{e.get_type_equipement_display()}</small>"
            f"<div class='d-flex flex-column gap-1' style='font-size: 0.85rem;'>"
            f"<span>📍 IP: <span class='text-info'>{e.adresse_ip}</span></span>"
            f"<span>⚡ Latence: <span style='color:{color}'>{e.latence or '?'} ms</span></span>"
            f"<span>💾 RAM: {e.ram_usage or '?'}%</span>"
            f"<span>🔥 CPU: {e.cpu_usage or '?'}%</span>"
            f"</div>"
            f"</div>"
        )
        
        nodes.append({
            "id": e.id,
            "label": e.nom,
            "group": e.type_equipement,
            "status": e.statut,
            "title": tooltip,
            "x": e.pos_x,
            "y": e.pos_y,
            "color": {
                "border": color,
                "highlight": {"border": color},
                "hover": {"border": color}
            },
            # Données additionnelles pour la sidebar
            "metrics": {
                "cpu": e.cpu_usage,
                "ram": e.ram_usage,
                "disk": e.disk_usage,
                "latence": e.latence,
                "ip": e.adresse_ip,
                "type": e.get_type_equipement_display(),
                "loc": e.localisation
            }
        })

    # On prépare les liens
    for l in LienReseau.objects.filter(actif=True):
        label_interface = f"{l.interface_source} ↔ {l.interface_destination}"
        
        links.append({
            "from": l.source.id,
            "to": l.destination.id,
            "type": l.type_lien,
            "label": label_interface,
        })

    return JsonResponse({
        "nodes": nodes,
        "links": links
    })

@csrf_exempt
@login_required
def save_node_position(request):
    """Sauvegarde les coordonnées X/Y d'un nœud après drag-and-drop"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            node_id = data.get("id")
            x = data.get("x")
            y = data.get("y")
            
            equipement = EquipementReseau.objects.get(id=node_id)
            equipement.pos_x = x
            equipement.pos_y = y
            equipement.save(update_fields=['pos_x', 'pos_y'])
            
            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

from django.views.decorators.clickjacking import xframe_options_sameorigin

@login_required
@xframe_options_sameorigin
def network_map_view(request):
    is_embedded = request.GET.get('embed') == '1' or request.GET.get('simulation_mode') == '1'
    context = {
        'base_template': 'minimal_base.html' if is_embedded else 'base.html',
        'is_embedded': is_embedded
    }
    return render(request, "monitoring/network_map.html", context)

from django.http import JsonResponse
from django.utils import timezone
from .models import (
    WifiAccessPoint, WifiRadio, WifiClient, WifiIncident, WifiStat
)

@login_required
def wifi_dashboard_api(request):
    now = timezone.now()

    aps = WifiAccessPoint.objects.filter(actif=True)
    radios = WifiRadio.objects.filter(radio_active=True)
    clients = WifiClient.objects.all()
    incidents = WifiIncident.objects.filter(resolu=False)

    radios_saturees = radios.filter(taux_utilisation__gte=90).count()
    ap_maintenance = WifiAccessPoint.objects.filter(
        equipement__maintenances__active=True
    ).distinct().count()

    clients_par_bande = {
        "2.4": radios.filter(bande="2.4").aggregate(c=models.Count("id"))["c"],
        "5": radios.filter(bande="5").aggregate(c=models.Count("id"))["c"],
        "6": radios.filter(bande="6").aggregate(c=models.Count("id"))["c"],
    }

    debit_total = WifiStat.objects.filter(
        date_releve__gte=now - timezone.timedelta(minutes=5)
    ).aggregate(
        total=models.Sum("debit_total_mbps")
    )["total"] or 0

    data = {
        "ap_total": aps.count(),
        "radios_total": radios.count(),
        "radios_saturees": radios_saturees,
        "clients_total": clients.count(),
        "incidents": incidents.count(),
        "ap_maintenance": ap_maintenance,
        "clients_par_bande": clients_par_bande,
        "debit_total": round(debit_total, 2),
    }

    return JsonResponse(data)



from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def wifi_heatmap_view(request):
    return render(request, "wifi/heatmap.html")

@login_required
def wifi_dashboard_view(request):
    return render(request, "wifi/dashboard.html")

from django.http import JsonResponse
from .models import WifiRadio, WifiStat

@login_required
def wifi_heatmap_api(request):
    radios = WifiRadio.objects.select_related("ap", "ap__equipement")

    heatmap = []

    for r in radios:
        stat = WifiStat.objects.filter(radio=r).first()

        taux = r.taux_utilisation or 0
        bruit = r.bruit_dbm or -90
        active = r.radio_active

        if not active:
            couleur = "gray"
        elif taux >= 90 or (stat and stat.canal_sature) or bruit > -80:
            couleur = "red"
        elif taux >= 70:
            couleur = "yellow"
        else:
            couleur = "green"

        heatmap.append({
            "ap": r.ap.equipement.nom,
            "radio_id": r.id,
            "bande": r.bande,
            "canal": r.canal,
            "clients": stat.nb_clients if stat else 0,
            "utilisation": taux,
            "bruit": bruit,
            "couleur": couleur,
        })

    return JsonResponse({"radios": heatmap})


import json
from django.conf import settings
from django.utils import timezone
from .models import EquipementReseau, StatReseau, WifiStat, WifiRecommendation, WifiAccessPoint
import json
import logging
from django.conf import settings
from django.utils import timezone
from .models import EquipementReseau, StatReseau, WifiStat, WifiRecommendation, WifiAccessPoint

# Import de la NOUVELLE librairie
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class InfrastructureAI:
    def __init__(self, mode="gemini"):
        self.mode = mode
        
        if self.mode == "gemini":
            # Nouvelle initialisation avec le Client unifié
            # Assurez-vous d'avoir votre clé API
            self.client = genai.Client(api_key="VOTRE_API_KEY_ICI")

    def _query_gemini(self, prompt):
        """ Envoie le prompt à Gemini 1.5 Flash avec la nouvelle syntaxe """
        try:
            response = self.client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json'  # Force le JSON
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Erreur Gemini Client: {e}")
            # On retourne une erreur formatée en JSON pour ne pas casser le parsing
            return json.dumps({"error": str(e), "analyse": "Erreur de connexion IA", "action": "Vérifier logs"})

    def predict_health(self, equipement_id):
        """ Prédit la santé d'un équipement (CPU, RAM, Ping) """
        try:
            equipement = EquipementReseau.objects.get(id=equipement_id)
            stats = StatReseau.objects.filter(equipement=equipement).order_by('-date_releve')[:20]

            if not stats:
                return {"analyse": "Pas assez de données.", "risque": "Inconnu", "action": "Attendre plus de mesures"}
            # Construction du contexte
            data_context = "\n".join([
                f"- {s.date_releve.strftime('%H:%M')}: CPU={s.cpu_usage}%, RAM={s.ram_usage}%, Ping={s.ping_ms}ms"
                for s in stats
            ])
            prompt = f"""
            Tu es un expert SRE. Analyse ces logs pour '{equipement.nom}':
            {data_context}
            Réponds en JSON strict : {{ "risque": "Faible/Moyen/Critique", "analyse": "Texte court", "action": "Action recommandée" }}
            """
            # Appel IA
            if self.mode == "gemini":
                result = self._query_gemini(prompt)
                # Parsing sécurisé
                return json.loads(result)
            return {"analyse": "Mode local non implémenté", "risque": "N/A"}
        except Exception as e:
            logger.error(f"Erreur predict_health: {e}")
            return {"analyse": "Erreur interne", "risque": "Erreur", "action": str(e)}
    def generate_wifi_recommendations(self):
        """ Analyse le WiFi et crée des recommandations en BDD """
        # 1. Récupération des données (30 dernières minutes)
        stats_recentes = WifiStat.objects.select_related('ap', 'radio').filter(
            date_releve__gte=timezone.now() - timezone.timedelta(minutes=30)
        )
        if not stats_recentes.exists():
            return {"status": "skipped", "message": "Pas assez de données récentes."}
        # 2. Construction du contexte riche pour l'IA
        data_list = []
        for s in stats_recentes:
            data_list.append({
                "ap": s.ap.equipement.nom,
                "radio": f"{s.radio.bande} GHz",
                "canal": s.radio.canal,
                "clients": s.nb_clients,
                "retry_rate": s.taux_retry,
                "saturation": s.canal_sature
            })
        prompt = f"""
        Expert WiFi, analyse ces données JSON :
        {json.dumps(data_list)}
        Identifie les problèmes (canal saturé, interférences, surcharge).
        Réponds UNIQUEMENT par un tableau JSON :
        [
            {{
                "ap_nom": "Nom Exact de l'AP",
                "type_reco": "canal" | "puissance" | "equilibrage",
                "gravite": 1 à 5,
                "message": "Titre",
                "justification": "Détails"
            }}
        ]
        """
        # 3. Appel IA
        raw_response = self._query_gemini(prompt)
        # 4. Traitement et Sauvegarde
        try:
            recommandations = json.loads(raw_response)
            count = 0
            
            for reco in recommandations:
                try:
                    # Recherche de l'AP par nom
                    ap_obj = WifiAccessPoint.objects.get(equipement__nom=reco.get("ap_nom"))
                    
                    # Anti-spam : on ne crée pas si une reco identique existe depuis < 1h
                    exists = WifiRecommendation.objects.filter(
                        ap=ap_obj,
                        type_recommandation=reco["type_reco"],
                        cree_le__gte=timezone.now() - timezone.timedelta(hours=1)
                    ).exists()

                    if not exists:
                        WifiRecommendation.objects.create(
                            ap=ap_obj,
                            type_recommandation=reco["type_reco"],
                            gravite=reco["gravite"],
                            message=reco["message"],
                            justification=reco["justification"]
                        )
                        count += 1
                        
                except WifiAccessPoint.DoesNotExist:
                    continue # L'IA a inventé un nom, on ignore
                except Exception as e:
                    logger.warning(f"Erreur création reco: {e}")

            return {"status": "success", "nb_recos": count}

        except json.JSONDecodeError:
            return {"status": "error", "message": "Réponse IA invalide"}
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import EquipementReseau
# Importez votre classe corrigée 
@login_required
def ai_analyze_view(request, equipement_id):
    if request.method != "GET":
        return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)

    # Sécurité : Vérifie que l'équipement existe
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)

    try:
        ai = InfrastructureAI(mode="gemini")
        
        # Appel synchrone (Attention : peut bloquer la page 2-3 secondes)
        # Pour une version PRO, il faut utiliser Celery ici.
        resultat = ai.predict_health(equipement.id)

        # Parsing sécurisé du résultat
        import json
        data = {}
        if isinstance(resultat, str):
            try:
                # Nettoyage Markdown (Gemini aime mettre ```json au début)
                clean_res = resultat.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_res)
            except json.JSONDecodeError:
                # Fallback si l'IA bavarde
                data = {
                    "risque": "Indéterminé", 
                    "analyse": resultat, 
                    "action": "Vérifier manuellement"
                }
        else:
            data = resultat
        return JsonResponse({'status': 'success', 'data': data})
    except Exception as e:
        # Loggez l'erreur réelle dans la console serveur pour le debug
        print(f"ERREUR IA: {e}")
        return JsonResponse({'status': 'error', 'message': "Erreur interne du module IA"}, status=500)
@login_required
def ai_wifi_audit_view(request):
    """ Lance l'audit global et génère les recommandations """
    try:
        ai = InfrastructureAI(mode="gemini")
        rapport = ai.generate_wifi_recommendations()
        return JsonResponse({'status': 'success', 'rapport': rapport})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
from django.shortcuts import get_object_or_404
from monitoring.models import CommandeAutomatique, ChangePlanifie
@login_required
def commande_detail(request, commande_id):
    """
    Détail d’une commande réseau
    """
    commande = get_object_or_404(CommandeAutomatique, id=commande_id)
    planification = ChangePlanifie.objects.filter(
        commande=commande,
        actif=True
    ).first()
    return render(
        request,
        "monitoring/commande_detail.html",
        {
            "commande": commande,
            "planification": planification,
        }
    )
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from monitoring.models import CommandeAutomatique, ChangePlanifie
@login_required
def liste_commandes(request):
    """
    Liste toutes les commandes réseau disponibles
    """
    commandes = CommandeAutomatique.objects.all().order_by("-cree_le")
    # Récupère les commandes planifiées
    commandes_planifiees = {
        c.commande_id: c
        for c in ChangePlanifie.objects.filter(actif=True)
    }
    return render(
        request,
        "monitoring/liste_commandes.html",
        {
            "commandes": commandes,
            "commandes_planifiees": commandes_planifiees,
        }
    )
@login_required
@critical_access_required
def planifier_commande_view(request, commande_id):
    commande = get_object_or_404(CommandeAutomatique, id=commande_id)
    if request.method == "POST":
        form = ChangePlanifieForm(request.POST)
        if form.is_valid():
            planif = form.save(commit=False)
            planif.commande = commande
            planif.cree_par = request.user
            planif.save()
            messages.success(
                request,
                "⏱️ Commande planifiée avec succès"
            )
            return redirect("commande_detail", commande_id=commande.id)
    else:
        form = ChangePlanifieForm()
    return render(
        request,
        "monitoring/commande_planifier.html",
        {
            "commande": commande,
            "form": form,
        }
    )    
@login_required
@critical_access_required
def creer_commande_view(request):
    if request.method == "POST":
        form = CommandeAutomatiqueForm(request.POST)
        if form.is_valid():
            commande = form.save(commit=False)
            commande.cree_par = request.user
            commande.save()
            form.save_m2m()
            messages.success(
                request,
                "✅ Commande réseau créée avec succès"
            )
            return redirect("liste_commandes")
    else:
        form = CommandeAutomatiqueForm()

    return render(
        request,
        "monitoring/commande_form.html",
        {"form": form}
    )


from monitoring.forms import PlanificationDirecteForm

@login_required
@critical_access_required
def planifier_commande_equipement_view(request, equipement_id):
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)
    
    if request.method == "POST":
        form = PlanificationDirecteForm(request.POST)
        if form.is_valid():
            commande_texte = form.cleaned_data['commande_texte']
            
            # Créer une CommandeAutomatique spécifique pour ce changement
            nom_cmd_dynamique = f"CMD_PLANIF_EQ{equipement.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
            commande_auto = CommandeAutomatique.objects.create(
                nom=nom_cmd_dynamique,
                description=f"Commande planifiée manuellement pour {equipement.nom}",
                contenu=commande_texte,
                cree_par=request.user,
                confirmation_requise=False,
                critique=False 
            )
            # Lier l'équipement concerné
            commande_auto.applicable_pour.add(equipement)

            planif = form.save(commit=False)
            planif.commande = commande_auto
            planif.equipement = equipement
            planif.cree_par = request.user
            planif.valide_par = request.user
            planif.date_validation = timezone.now()
            planif.statut = "valide" # Validé auto car validé par le filtre form
            planif.save()
            
            messages.success(
                request,
                f"⏱️ Commande planifiée avec succès sur {equipement.nom}"
            )
            return redirect("liste_planifications_equipement", equipement_id=equipement.id)
    else:
        form = PlanificationDirecteForm(initial={"frequence": "once", "date_execution": timezone.now()})
        
    return render(
        request,
        "monitoring/planifier_commande_equipement.html",
        {
            "equipement": equipement,
            "form": form,
        }
    )

@login_required
def liste_planifications_equipement_view(request, equipement_id):
    equipement = get_object_or_404(EquipementReseau, id=equipement_id)
    planifications = ChangePlanifie.objects.filter(
        equipement=equipement,
        actif=True
    ).select_related('commande').order_by('date_execution')
    
    return render(
        request,
        "monitoring/liste_planifications_equipement.html",
        {
            "equipement": equipement,
            "planifications": planifications,
        }
    )

@login_required
@critical_access_required
def supprimer_planification_view(request, plan_id):
    planif = get_object_or_404(ChangePlanifie, id=plan_id)
    equipement_id = planif.equipement.id
    
    if request.method == "POST":
        planif.actif = False
        planif.statut = "annule"
        planif.save()
        messages.success(request, f"🗑️ Planification supprimée avec succès")
        
    return redirect("liste_planifications_equipement", equipement_id=equipement_id)

@login_required
@critical_access_required
def basculer_maintenance_generale_view(request):
    """
    Clôture toutes les maintenances actives pour remettre tout le parc en service.
    """
    if request.method == "POST":
        maintenances_actives = Maintenance.objects.filter(active=True)
        count = maintenances_actives.count()
        
        # On ferme toutes les maintenances
        maintenances_actives.update(
            active=False,
            fin=timezone.now()
        )
        
        # Optionnel: On remet en ligne les équipements concernés
        # (Sauf si le check suivant les remettra hors ligne)
        
        messages.success(request, f"🚀 {count} équipements ont été remis en fonctionnement (Maintenance générale désactivée).")
        
    return redirect("liste_equipements")

@login_required
@critical_access_required
def liste_changements_a_valider(request):
    changements = ChangePlanifie.objects.filter(
        statut="en_attente",
        actif=True
    ).select_related("equipement", "commande", "cree_par")

    return render(
        request,
        "monitoring/liste_a_valider.html",
        {"changements": changements}
    )    
    
@login_required
@critical_access_required
def valider_changement(request, change_id):
    change = get_object_or_404(ChangePlanifie, id=change_id)

    change.statut = "valide"
    change.valide_par = request.user
    change.date_validation = timezone.now()
    change.save()

    messages.success(
        request,
        f"✅ Changement validé pour {change.equipement.nom}"
    )
    return redirect("liste_changements_a_valider")


@login_required
@critical_access_required
def refuser_changement(request, change_id):
    change = get_object_or_404(ChangePlanifie, id=change_id)

    change.statut = "refuse"
    change.actif = False
    change.valide_par = request.user
    change.date_validation = timezone.now()
    change.save()

    messages.warning(
        request,
        f"❌ Changement refusé pour {change.equipement.nom}"
    )
    return redirect("liste_changements_a_valider")
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from monitoring.models import CommandeAutomatique, EquipementReseau
@login_required
def modifier_commande(request, commande_id):
    commande = get_object_or_404(CommandeAutomatique, id=commande_id)

    # 🔒 Sécurité simple
    if not request.user.is_superuser and commande.cree_par != request.user:
        messages.error(request, "🚫 Vous ne pouvez pas modifier cette commande.")
        return redirect("liste_commandes")

    if request.method == "POST":
        commande.nom = request.POST.get("nom")
        commande.description = request.POST.get("description")
        commande.contenu = request.POST.get("contenu")
        commande.critique = bool(request.POST.get("critique"))
        commande.confirmation_requise = bool(request.POST.get("confirmation_requise"))

        equipements_ids = request.POST.getlist("equipements")
        commande.applicable_pour.set(equipements_ids)

        commande.save()

        messages.success(request, "✅ Commande modifiée avec succès.")
        return redirect("commande_detail", commande_id=commande.id)

    equipements = EquipementReseau.objects.all()

    return render(
        request,
        "monitoring/modifier_commande.html",
        {
            "commande": commande,
            "equipements": equipements,
        }
    )
    
# monitoring/views_ai.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from monitoring.models import Incident
from aiengine.orchestrator import analyser_incident_ia, sauvegarder_resultat_ia
from aiengine.tasks import analyser_incident_task
from django.views.decorators.csrf import csrf_exempt

from .models import AnalyseIA

@login_required
def resultat_analyse_ia(request, incident_id):
    incident = get_object_or_404(Incident, id=incident_id)

    # ⏳ Analyse en cours ?
    if incident.analyse_ia_en_cours:
        return JsonResponse({
            "etat": "en_cours",
            "message": "Analyse IA en cours"
        })

    # ❌ Analyse absente
    try:
        analyse = AnalyseIA.objects.get(incident=incident)
    except AnalyseIA.DoesNotExist:
        return JsonResponse({
            "etat": "absente",
            "message": "Aucune analyse IA disponible"
        })

    # ✅ Analyse terminée
    return JsonResponse({
        "etat": "terminee",
        "analyse": {
            "cause_racine": analyse.cause_racine,
            "categorie": analyse.categorie,
            "solution_humaine": analyse.solution_humaine,
            "remediation_auto": analyse.remediation_auto,
            "explication_simple": analyse.explication_simple,
            "confiance": analyse.confiance,
        }
    })

@csrf_exempt
@login_required
def analyser_incident_ia_view(request, incident_id):
    """
    Bouton UI : Analyser un incident avec l'IA.
    Tente Groq en synchrone (rapide), sinon délègue à Ollama via Celery.
    """
    incident = get_object_or_404(Incident, id=incident_id)

    # 🔐 Sécurité minimale
    if not request.user.is_superuser and incident.equipement.cree_par != request.user:
        return JsonResponse({
            "status": "error", 
            "message": "🚫 Permission refusée."
        }, status=403)

    try:
        # 1. Tentative Groq Synchrone
        analyse_brute = analyser_incident_ia(incident, provider='groq')
        
        # Tentative de sauvegarde
        obj_analyse = sauvegarder_resultat_ia(incident, analyse_brute)

        if obj_analyse:
            # Succès Groq !
            return JsonResponse({
                "status": "success",
                "message": "Analyse Groq terminée",
                "analyse": analyse_brute
            })
        
        # 2. Fallback Celery (Ollama)
        incident.analyse_ia_en_cours = True
        incident.save(update_fields=["analyse_ia_en_cours"])
        analyser_incident_task.delay(incident.id)
        
        return JsonResponse({
            "status": "fallback",
            "message": "Groq indisponible, basculement sur Ollama (Celery)..."
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
