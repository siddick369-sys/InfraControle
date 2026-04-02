# monitoring/smart_monitor.py
import threading
import concurrent.futures
import logging
import time
from django.utils import timezone
from datetime import timedelta
from monitoring.models import Maintenance, WifiAccessPoint

from django.core.mail import send_mail
from django.conf import settings
from monitoring.utils.maintenance import est_en_maintenance
from monitoring.models import EquipementReseau, Incident, CommandeAutomatique
from monitoring.ssh_utils import collecter_performance_ssh, get_ssh_client, exec_cmd
from monitoring.snmp_utils import collecter_materiel_snmp
from monitoring.log_parser import collecter_logs_ssh
try:
    from monitoring.network import collecter_ping_jitter
except ImportError:
    def collecter_ping_jitter(ip, count=4, timeout=2): return None, None, 100.0

logger = logging.getLogger("monitoring")

from monitoring.remediation_engine import appliquer_remediation
from monitoring.verifier_resolution import verifier_resolution_incident

# ==============================
# Helper for robust float conversion
# ==============================
def safe_float(value, default=0.0):
    """Convertit une chaîne en float de manière robuste (gère virgules, espaces et erreurs)."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    
    try:
        # Nettoyage de base : suppression des espaces, remplacement des virgules par des points
        s = str(value).strip().replace(',', '.')
        
        # Si c'est purement numérique après nettoyage, on convertit directement
        try:
            return float(s)
        except ValueError:
            pass
            
        # Sinon, on cherche un nombre isolé (ex: "Size: 1.25 GB")
        # On évite de capturer des nombres collés à des lettres comme "1GB" si possible
        import re
        match = re.search(r"(?:^|\s)([-+]?\d*\.?\d+)(?:\s|$|[a-zA-Z])", s)
        if match:
            return float(match.group(1))
        return default
    except (ValueError, TypeError):
        return default

# ==============================
# 1️⃣ Envoi d’email asynchrone
# ==============================
def _thread_envoyer_mail(sujet, message, destinataire):
    try:
        send_mail(sujet, message, settings.DEFAULT_FROM_EMAIL, [destinataire], fail_silently=True)
        logger.info(f"[ALERTE] Email envoyé à {destinataire} : {sujet}")
    except Exception as e:
        logger.error(f"[ERREUR EMAIL THREAD] {e}", exc_info=True)


def envoyer_notification(incident, utilisateur=None):
    """Lance un thread pour envoyer l'alerte email sans bloquer le monitoring."""
    destinataire = None
    if utilisateur and utilisateur.email:
        destinataire = utilisateur.email
    elif incident.equipement.cree_par and incident.equipement.cree_par.email:
        destinataire = incident.equipement.cree_par.email

    if not destinataire:
        logger.warning(f"[ALERTE] Aucun destinataire trouvé pour {incident.titre}")
        return

    sujet = f"[ALERTE {incident.niveau.upper()}] {incident.equipement.nom}"
    message = f"""
🚨 {incident.titre}

Équipement : {incident.equipement.nom}
Adresse IP : {incident.equipement.adresse_ip}

Description :
{incident.description}

Horodatage : {incident.date_debut.strftime("%d/%m/%Y %H:%M")}
"""

    t = threading.Thread(target=_thread_envoyer_mail, args=(sujet, message, destinataire))
    t.daemon = True
    t.start()


def envoyer_notification_echec_remediation(incident):
    """Envoie un email spécial si la remédiation automatique a échoué."""
    destinataire = None
    if incident.equipement.cree_par and incident.equipement.cree_par.email:
        destinataire = incident.equipement.cree_par.email
    
    if not destinataire:
        return

    # Anti-spam : un seul mail d'échec par incident par heure
    from django.core.cache import cache
    cache_key = f"fail_rem_{incident.id}"
    if cache.get(cache_key):
        return
    cache.set(cache_key, True, 3600)

    sujet = f"❌ [ÉCHEC REMÉDIATION] {incident.equipement.nom} : {incident.titre}"
    message = f"""
La tentative de remédiation automatique pour l'incident suivant a ÉCHOUÉ :

Incident : {incident.titre}
Équipement : {incident.equipement.nom} ({incident.equipement.adresse_ip})
Description : {incident.description}

Veuillez intervenir manuellement sur l'équipement.
    """
    t = threading.Thread(target=_thread_envoyer_mail, args=(sujet, message, destinataire))
    t.daemon = True
    t.start()


# =========================================
# 2️⃣ Création et traitement d’incidents
# =========================================
# def enregistrer_incident(equipement, titre, desc, niveau="critique"):
#     """Crée ou récupère un incident pour éviter les doublons."""
#     incident, created = Incident.objects.get_or_create(
#         equipement=equipement,
#         titre=titre,
#         defaults={
#             "description": desc,
#             "niveau": niveau,
#             "statut": "ouvert",
#             "cree_par": equipement.cree_par,
#             "date_debut": timezone.now(),
#         },
#     )
#     if created:
#         logger.warning(f"[INCIDENT] {equipement.nom} → {titre}")
#     return incident, created

def enregistrer_incident(equipement, titre, desc, niveau="critique"):
    incident = Incident.objects.filter(
        equipement=equipement,
        titre=titre,
        statut="ouvert"
    ).first()

    if incident:
        # Mise à jour simple (heartbeat)
        incident.derniere_detection = timezone.now()
        incident.save(update_fields=["derniere_detection"])
        return incident, False

    # 🔥 Nouvel incident uniquement
    incident = Incident.objects.create(
        equipement=equipement,
        titre=titre,
        description=desc,
        niveau=niveau,
        cree_par=equipement.cree_par,
        statut="ouvert",
    )

    logger.warning(f"[INCIDENT NOUVEAU] {equipement.nom} → {titre}")
    return incident, True

from django.utils import timezone
from monitoring.ssh_utils import collecter_performance_ssh
from monitoring.snmp_utils import collecter_materiel_snmp
import logging

logger = logging.getLogger(__name__)
from monitoring.models import Maintenance, Incident

def cloturer_maintenance_si_ok(equipement):
    """
    Termine la maintenance si aucun incident ouvert ne subsiste
    """
    reste_des_incidents = Incident.objects.filter(
        equipement=equipement,
        statut="ouvert"
    ).exists()

    if not reste_des_incidents:
        Maintenance.objects.filter(
            equipement=equipement,
            active=True
        ).update(
            active=False,
            fin=timezone.now()
        )

        equipement.statut = "en ligne"
        equipement.save(update_fields=["statut"])
        
import logging
from django.utils import timezone
from monitoring.ssh_utils import collecter_performance_ssh
from monitoring.snmp_utils import collecter_materiel_snmp
from monitoring.models import Incident, Maintenance
from monitoring.wifi.collector import collect_wifi
from monitoring.wifi.persist import enregistrer_wifi
from monitoring.wifi.detection import detecter_incidents_wifi
logger = logging.getLogger("monitoring.resolution")


def verifier_resolution_incident(incident):
    """
    Vérifie si un incident est résolu selon son type.
    Si résolu :
    - statut = résolu
    - date_resolution mise à jour
    - sortie automatique de maintenance si plus aucun incident ouvert
    """

    equipement = incident.equipement
    titre = incident.titre.lower()

    perf = collecter_performance_ssh(equipement) or {}
    mat = collecter_materiel_snmp(equipement.adresse_ip) or {}

    # Valeurs sécurisées
    cpu = safe_float(perf.get("cpu_usage") or mat.get("cpu_usage"))
    ram = safe_float(perf.get("ram_usage") or mat.get("ram_usage"))
    disk = safe_float(perf.get("disk_usage"))

    packet_loss = safe_float(perf.get("packet_loss"))
    latence = safe_float(perf.get("latence"))

    temp = safe_float(mat.get("temperature_c"))
    crc_in = int(mat.get("crc_in") or mat.get("errors_in") or 0)
    crc_out = int(mat.get("crc_out") or mat.get("errors_out") or 0)

    resolu = False

    # =============================
    # 🔥 RESSOURCES
    # =============================
    if "cpu" in titre:
        resolu = cpu < 80

    elif "ram" in titre:
        resolu = ram < 80

    elif "disque" in titre:
        resolu = disk < 85

    # =============================
    # 🌐 RÉSEAU
    # =============================
    elif "packet" in titre or "perte" in titre:
        resolu = packet_loss < 1

    elif "latence" in titre:
        resolu = latence > 0 and latence < 100

    elif "hors ligne" in titre:
        resolu = bool(perf)

    # =============================
    # 📡 SNMP / MATÉRIEL
    # =============================
    elif "crc" in titre:
        resolu = crc_in == 0 and crc_out == 0

    elif "surchauffe" in titre:
        resolu = temp < 65

    # =============================
    # 🛡️ SÉCURITÉ & AGENTS (WINDOWS)
    # =============================
    elif "antivirus" in titre:
        # On vérifie si RealTimeProtectionEnabled est à 1
        res = exec_cmd(get_ssh_client(equipement), "powershell -Command \"Get-MpComputerStatus | Select-Object -ExpandProperty RealTimeProtectionEnabled\"")
        resolu = "1" in res or "True" in res

    elif "handles" in titre:
        # On vérifie le total des handles
        res = exec_cmd(get_ssh_client(equipement), "powershell -Command \"(Get-Process | Measure-Object -Property Handles -Sum).Sum\"")
        if res and res.isdigit():
            resolu = int(res) < 80000 # Seuil de résolution un peu plus bas que le déclenchement (100k)

    elif "service" in titre or "down" in titre:
        # Vérification générique de service
        failed_win = exec_cmd(get_ssh_client(equipement), "powershell -Command \"Get-Service | Where-Object { $_.Status -ne 'Running' -and $_.StartType -eq 'Automatic' } | Select-Object -ExpandProperty Name\"")
        # Si le titre contient un nom de service connu
        mapping = {"spooler": "Spooler", "w3svc": "W3SVC", "windefend": "WinDefend", "wuauserv": "wuauserv"}
        service_trouve = False
        for k, v in mapping.items():
            if k in titre:
                service_trouve = True
                resolu = v not in failed_win.split()
                break
        if not service_trouve:
            resolu = True # Par défaut si on ne peut pas vérifier finement

    # =============================
    # 📜 LOGS
    # =============================
    elif "log" in titre:
        # Si le log ne réapparaît plus → considéré résolu
        resolu = True

    # =============================
    # ✅ RÉSOLUTION
    # =============================
    if resolu:
        incident.statut = "résolu"
        incident.date_resolution = timezone.now()
        incident.notifie = False
        incident.save(update_fields=["statut", "date_resolution", "notifie"])
        stat = equipement.stats.first()
        if stat:
            stat.alerte_envoyee = False
            stat.save(update_fields=["alerte_envoyee"])

        logger.info(
            f"[RESOLUTION] {incident.titre} résolu sur {equipement.nom}"
        )

        # 🔓 Sortie de maintenance si plus aucun incident ouvert
        reste_incidents = Incident.objects.filter(
            equipement=equipement,
            statut="ouvert"
        ).exists()

        if not reste_incidents:
            Maintenance.objects.filter(
                equipement=equipement,
                active=True
            ).update(
                active=False,
                fin=timezone.now()
            )

            equipement.statut = "en ligne"
            equipement.save(update_fields=["statut"])

            logger.info(
                f"[MAINTENANCE FIN] {equipement.nom} remis en service"
            )

        return True

    return False

from monitoring.wifi.collector import collect_wifi
from monitoring.wifi.persist import enregistrer_wifi
from monitoring.wifi.detection import detecter_incidents_wifi
import logging

logger = logging.getLogger("wifi.analyse")

def analyser_wifi_ap(ap):
    """
    Analyse complète Wi-Fi pour un WifiAccessPoint
    - collecte
    - enregistrement
    - détection incidents
    """

    anomalies = []

    # 🔒 Sécurité absolue
    if not isinstance(ap, WifiAccessPoint):
        raise TypeError(
            f"analyser_wifi_ap attend WifiAccessPoint, reçu {type(ap)}"
        )

    try:
        # ==========================
        # 📡 COLLECTE
        # ==========================
        wifi_data = collect_wifi(ap.equipement)

        if not wifi_data:
            logger.warning(f"[WIFI] Pas de données collectées pour {ap}")
            return anomalies

        # ==========================
        # 💾 ENREGISTREMENT
        # ==========================
        enregistrer_wifi(ap, wifi_data)

        # ==========================
        # 🚨 DÉTECTION INCIDENTS
        # ==========================
        anomalies = detecter_incidents_wifi(ap)

    except Exception as exc:
        logger.error(
            f"[WIFI] Erreur analyse AP {ap}: {exc}",
            exc_info=True
        )
        anomalies.append("wifi_erreur")

    return anomalies
# =========================================
# 4️⃣ Analyse d’un seul équipement (version robuste)
# =========================================
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def analyser_un_equipement(e):
    import time
    if e is None:
        logger.error("[ERREUR ANALYSE] L'équipement fourni est None")
        return {"equipement": "Inconnu", "anomalies": ["Erreur : équipement inexistant"]}
    
    # ⛔ MAINTENANCE : On ne monitorer plus (sauf commandes planifiées, gérées ailleurs)
    if est_en_maintenance(e):
        logger.info(f"[SKIP MONITORING] {e.nom} est en maintenance.")
        return {"equipement": e.nom, "anomalies": [], "statut": "maintenance"}

    # Sécurité : Si l'utilisateur a envoyé un QuerySet (ex: via filter()) au lieu d'une instance
    from django.db.models.query import QuerySet
    if isinstance(e, QuerySet):
        e = e.first()
        if not e:
            return {"equipement": "Inconnu", "anomalies": ["Erreur : QuerySet vide"]}
        
    anomalies = []
    incidents_declenches = []

    try:
        # ... (collecte ping/jitter/perf/mat/logs) ...
        try:
            ping_ms, jitter_ms, packet_loss = collecter_ping_jitter(e.adresse_ip)
        except Exception:
            ping_ms, jitter_ms, packet_loss = None, None, 100.0

        if packet_loss == 100.0:
            e.statut = "hors ligne"
            e.save(update_fields=["statut"])
            return {"equipement": e.nom, "anomalies": ["Hors ligne", "100% perte de paquets"]}

        perf = collecter_performance_ssh(e) or {}
        mat = collecter_materiel_snmp(e.adresse_ip) or {}
        logs = collecter_logs_ssh(e) or []

        # ... (collecte wifi) ...
        wifi_anomalies = []
        if hasattr(e, "wifi_ap"):
            wifi_anomalies = analyser_wifi_ap(e.wifi_ap)
            anomalies.extend([f"wifi:{a}" for a in wifi_anomalies])
        
        # ... (métriques système) ...
        cpu = safe_float(perf.get("cpu_usage") or mat.get("cpu_usage"))
        load_1 = safe_float(perf.get("cpu_load_1m"))
        ram = safe_float(perf.get("ram_usage") or mat.get("ram_usage"))
        disk = safe_float(perf.get("disk_usage"))
        inode = safe_float(perf.get("inode_usage"))
        drops_in = int(perf.get("drops_in") or mat.get("drops_in") or 0)
        drops_out = int(perf.get("drops_out") or mat.get("drops_out") or 0)

        def declencher(titre, description):
            import time
            incident, created = enregistrer_incident(e, titre, description)
            if not incident:
                return

            incidents_declenches.append(incident)
            anomalies.append(titre)

            # 🛠 Auto-remédiation
            remediation_tentee = appliquer_remediation(e, incident)
            
            if remediation_tentee:
                # On attend 2 sec pour laisser le temps au service de redémarrer
                time.sleep(2)
                if verifier_resolution_incident(incident):
                    incident.statut = "résolu"
                    incident.date_resolution = timezone.now()
                    incident.save(update_fields=["statut", "date_resolution"])
                    logger.info(f"[REMEDIATION SUCCES] {e.nom} : {titre}")
                    return

            # Si on arrive ici, soit la remédiation a échoué, soit elle n'a pas résolu le problème
            if incident.statut != "résolu":
                verifier_resolution_incident(incident)

            # 🚨 AUTO-MAINTENANCE : Si incident critique persist après remédiation
            if incident.statut == "ouvert" and incident.niveau == "critique":
                # On met en maintenance si pas déjà le cas
                if not est_en_maintenance(e):
                    from monitoring.models import Maintenance
                    Maintenance.objects.create(
                        equipement=e,
                        debut=timezone.now(),
                        fin=timezone.now() + timedelta(hours=2), # Valeur par défaut
                        active=True,
                        raison=f"Maintenance automatique : échec remédiation sur '{titre}'",
                        cree_par=None # Système
                    )
                    e.statut = "hors ligne" # On marque hors ligne pendant maintenance
                    e.save(update_fields=["statut"])
                    logger.warning(f"[AUTO-MAINTENANCE] {e.nom} mis en maintenance (Échec {titre})")

            # NOTE: L'envoi immédiat d'email a été désactivé pour laisser place au résumé quotidien.
            # On ne marque pas incident.notifie = True ici.

        # ==========================
        # 🔥 CPU / LOAD
        # ==========================
        if cpu > 90:
            declencher("CPU élevé", f"CPU à {cpu:.1f}%")

        if load_1 > 4:
            declencher("Load excessif", f"Load 1m = {load_1}")

        # ==========================
        # 💾 MÉMOIRE
        # ==========================
        if ram > 85:
            declencher("RAM saturée", f"RAM à {ram:.1f}%")

        if any("oom-killer" in l.lower() for l in logs):
            declencher("OOM killer", "OOM killer détecté dans les logs")

        # ==========================
        # 💽 DISQUE
        # ==========================
        if disk > 90:
            declencher("Disque plein", f"Disque à {disk:.1f}%")

        if inode > 90:
            declencher("Inodes saturés", f"Inodes à {inode:.1f}%")

        if any("read-only file system" in l.lower() for l in logs):
            declencher("Filesystem read-only", "FS monté en lecture seule")

        # ==========================
        # 🔥 OS-SPECIFIC CHECKS
        # ==========================
        from monitoring.ssh_utils import get_ssh_client, get_os_type, exec_cmd
        ssh_client = None
        os_type = "unknown"
        
        try:
            ssh_client = get_ssh_client(e)
            os_type = get_os_type(ssh_client)
        except:
            pass

        if ssh_client and os_type == "linux":
            # 1. Services Linux critiques
            failed_services = exec_cmd(ssh_client, "systemctl list-units --type=service --state=failed --no-legend")
            srv_mapping = {
                "mysql": ("MySQL down", "Service de base de données MySQL arrêté"),
                "postgresql": ("PostgreSQL down", "Service PostgreSQL en échec"),
                "nginx": ("Service HTTP down", "Serveur Nginx arrêté"),
                "apache2": ("Service HTTP down", "Serveur Apache arrêté"),
                "docker": ("Docker bloqué", "Service Docker ne répond plus")
            }
            for srv, (titre, desc) in srv_mapping.items():
                if f" {srv}.service " in failed_services:
                    declencher(titre, desc)

            # 2. Santé Système Linux
            # Zombies
            if exec_cmd(ssh_client, "ps -ef | grep defunct | grep -v grep"):
                declencher("Processus Zombies", "Des processus zombies ont été détectés")
            
            # Swap
            swap_info = exec_cmd(ssh_client, "free | grep Swap")
            if swap_info:
                try:
                    p = swap_info.split()
                    total_swap = float(p[1])
                    used_swap = float(p[2])
                    if total_swap > 0 and (used_swap / total_swap) > 0.8:
                        declencher("Saturation Swap", f"Utilisation du Swap élevée ({int(used_swap/total_swap*100)}%)")
                except: pass

            # DNS
            if "google.com" not in exec_cmd(ssh_client, "ping -c 1 -W 2 google.com"):
                declencher("Échec DNS", "La résolution de noms ne fonctionne pas")

            # APT Lock
            if exec_cmd(ssh_client, "ls /var/lib/dpkg/lock-frontend 2>/dev/null"):
                declencher("Verrou APT bloqué", "Le gestionnaire de paquets APT est verrouillé par un autre processus")

            # Sessions SSH
            ssh_count = len(exec_cmd(ssh_client, "who").splitlines())
            if ssh_count > 10:
                declencher("Trop de sessions SSH", f"{ssh_count} sessions SSH actives détectées")

            # Low Entropy
            entropy = exec_cmd(ssh_client, "cat /proc/sys/kernel/random/entropy_avail")
            if entropy and int(entropy) < 200:
                declencher("Entropie faible", f"Niveau d'entropie critique ({entropy})")
                
            # 3. Nouveautés Linux (Phase 14)
            # Connexions réseau saturées (> 5000)
            conn_count = exec_cmd(ssh_client, "ss -s | grep TCP: | grep -oP '\d+' | head -1")
            if conn_count and conn_count.isdigit() and int(conn_count) > 5000:
                declencher("Connexions réseau saturées", f"{conn_count} connexions TCP actives")
                
            # Fichiers temporaires pleins (/tmp)
            tmp_use = exec_cmd(ssh_client, "df -h /tmp | awk 'NR==2 {print $5}' | sed 's/%//'")
            if tmp_use and tmp_use.isdigit() and int(tmp_use) > 90:
                declencher("Dossier temporaire saturé (Linux)", f"Utilisation de /tmp à {tmp_use}%")
                
            # Webserver local HTTP inaccessible
            http_code = exec_cmd(ssh_client, "curl -s -o /dev/null -w '%{http_code}' http://localhost --max-time 2")
            if http_code and http_code.isdigit() and int(http_code) >= 500:
                declencher("Serveur Web Local en erreur", f"Code HTTP {http_code} sur localhost")
                
            # Épuisement des File Handlers
            file_fd = exec_cmd(ssh_client, "cat /proc/sys/fs/file-nr | awk '{print $1 / $3 * 100}'")
            if file_fd and float(file_fd) > 90.0:
                declencher("Épuisement File Handlers", f"File descriptors utilisés à {float(file_fd):.1f}%")
                
            # Processus en boucle (État D ou R prolongé)
            if int(exec_cmd(ssh_client, "ps r -A | wc -l") or 0) > 20: # Beaucoup de processus runnable
                declencher("Anomalie Processus (Load)", "Nombre anormalement élevé de processus en cours d'exécution")

            # 4. Nouveautés Linux supplémentaires (10)
            # 1. inodes > 95%
            inode_use = exec_cmd(ssh_client, "df -i / | awk 'NR==2 {print $5}' | sed 's/%//'")
            if inode_use and inode_use.isdigit() and int(inode_use) > 95:
                declencher("Inodes critiques", f"Inodes utilisés à {inode_use}%")

            # 2. OOM Killer logs dans dmesg récemment
            if "Out of memory" in exec_cmd(ssh_client, "dmesg | tail -n 50"):
                declencher("Incident OOM (Dmesg)", "OOM Killer détecté dans les logs noyau récents")

            # 3. Mémoire partagée (/dev/shm) saturée
            shm_use = exec_cmd(ssh_client, "df -h /dev/shm | awk 'NR==2 {print $5}' | sed 's/%//'")
            if shm_use and shm_use.isdigit() and int(shm_use) > 80:
                declencher("Mémoire partagée saturée", f"/dev/shm utilisé à {shm_use}%")

            # 4. Connexions SSH en échec (Bruteforce passif)
            ssh_fails = exec_cmd(ssh_client, "grep 'Failed password' /var/log/auth.log | wc -l")
            if ssh_fails and ssh_fails.isdigit() and int(ssh_fails) > 50:
                declencher("Attaque Bruteforce SSH détectée", f"{ssh_fails} échecs de connexion SSH récents")

            # 5. NTP asynchrone (Dérive)
            ntp_sync = exec_cmd(ssh_client, "timedatectl status | grep 'System clock synchronized: yes'")
            if not ntp_sync:
                declencher("Désynchronisation NTP", "L'horloge système n'est plus synchronisée via NTP")

            # 6. Service Cron down
            if "inactive" in exec_cmd(ssh_client, "systemctl is-active cron || systemctl is-active crond"):
                declencher("Service Cron arrêté", "Le planificateur de tâches Linux est inactif")

            # 7. Espace root (/) > 95%
            root_use = exec_cmd(ssh_client, "df -h / | awk 'NR==2 {print $5}' | sed 's/%//'")
            if root_use and root_use.isdigit() and int(root_use) > 95:
                declencher("Espace Root critique", f"Partition / remplie à {root_use}%")

            # 8. Trop de fichiers ouverts par utilisateur (Ulimit)
            ulimit_warn = exec_cmd(ssh_client, "lsof | wc -l")
            if ulimit_warn and ulimit_warn.isdigit() and int(ulimit_warn) > 80000:
                declencher("Limite fichiers ouverts", f"Nombre élevé de fichiers ouverts: {ulimit_warn}")

            # 9. Dépôts inaccessibles (Apt)
            apt_fail = exec_cmd(ssh_client, "ping -c 1 archive.ubuntu.com || ping -c 1 deb.debian.org")
            if not apt_fail:
                declencher("Dépôts inaccessibles", "Impossible de joindre les dépôts officiels")

            # 10. Utilisateur root par SSH (PermitRootLogin)
            root_ssh = exec_cmd(ssh_client, "grep '^PermitRootLogin yes' /etc/ssh/sshd_config")
            if root_ssh:
                declencher("Accès Root SSH autorisé", "La connexion root par SSH est autorisée (Risque de sécurité)")



        elif ssh_client and os_type == "windows":
            # 1. Services Windows critiques
            failed_win_srvs = exec_cmd(ssh_client, "powershell -Command \"Get-Service | Where-Object { $_.Status -ne 'Running' -and $_.StartType -eq 'Automatic' } | Select-Object -ExpandProperty Name\"").split()
            win_mapping = {
                "Spooler": ("Spooler down", "Service d'impression arrêté"),
                "W3SVC": ("Service HTTP down", "Serveur IIS arrêté"),
                "wuauserv": ("Windows Update down", "Service de mise à jour arrêté"),
                "WinRM": ("WinRM down", "Gestion à distance Windows arrêtée"),
                "TermService": ("Bureau à distance down", "Service RDP en échec")
            }
            for srv, (titre, desc) in win_mapping.items():
                if srv in failed_win_srvs:
                    declencher(titre, desc)

            # 1.5. Nouveaux services critiques Windows
            win_mapping_extra = {
                "Dhcp": ("Service DHCP down", "Le client DHCP est arrêté"),
                "Dnscache": ("Service DNS down", "Le client DNS est arrêté"),
                "WinDefend": ("Antivirus arrêté", "Windows Defender est arrêté"),
                "EventLog": ("Journal d'événements down", "Service EventLog arrêté"),
                "Schedule": ("Planificateur de tâches down", "Service Task Scheduler arrêté")
            }
            for srv, (titre, desc) in win_mapping_extra.items():
                if f"{srv} " in failed_win_srvs or srv in failed_win_srvs:
                    declencher(titre, desc)

            # 2. Sécurité Windows
            if "False" in exec_cmd(ssh_client, "powershell -Command \"(Get-NetFirewallProfile -Profile Domain).Enabled\""):
                declencher("Pare-feu désactivé", "Le pare-feu de domaine est désactivé")
            
            if "1" not in exec_cmd(ssh_client, "powershell -Command \"Get-MpComputerStatus | Select-Object -ExpandProperty RealTimeProtectionEnabled\""):
                declencher("Antivirus désactivé", "La protection temps réel Windows Defender est OFF")

            # 3. Maintenance Windows
            # Corbeille > 5GB (Correction avec -Force, raw string et échappement PowerShell pour $)
            bin_size = exec_cmd(ssh_client, "powershell -Command \"(Get-ChildItem -Path 'C:\\`$Recycle.Bin' -Force -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB\"")
            if safe_float(bin_size) > 5:
                declencher("Corbeille volumineuse", f"La corbeille occupe {safe_float(bin_size):.1f} GB")

            # Reboot Required
            if exec_cmd(ssh_client, "powershell -Command \"Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'\"") == "True":
                declencher("Redémarrage en attente", "Une mise à jour nécessite un redémarrage système")

            # Disk Queue
            q_length = exec_cmd(ssh_client, "powershell -Command \"(Get-Counter -Counter '\\PhysicalDisk(_Total)\\Current Disk Queue Length').CounterSamples.CookedValue\"")
            if q_length and float(q_length.replace(',', '.')) > 2:
                declencher("File d'attente disque", f"Queue Length élevée ({float(q_length.replace(',','.')):.1f})")

            # 4. Nouveautés Windows (Phase 14)
            # Temps Windows (W32Time) arrêté
            if "Running" not in exec_cmd(ssh_client, "powershell -Command \"(Get-Service W32Time).Status\""):
                declencher("Service de Temps arrêté", "W32Time n'est pas en cours d'exécution")
                
            # Fichiers temporaires Windows pleins (> 10GB)
            tmp_size = exec_cmd(ssh_client, "powershell -Command \"(Get-ChildItem -Path 'C:\\Windows\\Temp' -Force -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB\"")
            if safe_float(tmp_size) > 10:
                declencher("Dossier temporaire saturé (Windows)", f"C:\\Windows\\Temp occupe {safe_float(tmp_size):.1f} GB")
                
            # EventLog Error
            if "Running" not in exec_cmd(ssh_client, "powershell -Command \"(Get-Service EventLog).Status\""):
                declencher("Journal des événements arrêté", "Le service EventLog est en panne")
                
            # Nombre excessif de Handles (> 100k)
            handlesCount = exec_cmd(ssh_client, "powershell -Command \"(Get-Process | Measure-Object -Property Handles -Sum).Sum\"")
            if handlesCount and handlesCount.isdigit() and int(handlesCount) > 100000:
                declencher("Fuite de Handles (Windows)", f"Nombre total de handles anormalement élevé ({handlesCount})")
                
            # Déconnexions RDP inattendues (si TermService est on, on regarde les erreurs récentes)
            rdp_errs = exec_cmd(ssh_client, "powershell -Command \"(Get-EventLog -LogName System -Source 'TermService' -EntryType Error -Newest 5 -ErrorAction SilentlyContinue).Count\"")
            if rdp_errs and rdp_errs.isdigit() and int(rdp_errs) > 3:
                declencher("Erreurs RDP fréquentes", f"{rdp_errs} erreurs RDP détectées récemment")

            # 5. Nouveautés Windows (5 supplémentaires pour 10 en tout + les 5 services)
            # 6. Mémoire paginée excessive
            paged_pool = exec_cmd(ssh_client, "powershell -Command \"(Get-Counter '\\Memory\\Pool Paged Bytes').CounterSamples.CookedValue / 1MB\"")
            if paged_pool and safe_float(paged_pool) > 1000:
                declencher("Fuite Mémoire Paginée", f"Pool Paged > {safe_float(paged_pool):.0f} MB")

            # 7. Espace disque C: faible (< 10%)
            c_free_pct = exec_cmd(ssh_client, "powershell -Command \"Get-Volume -DriveLetter C | Select-Object -ExpandProperty SizeRemaining / (Get-Volume -DriveLetter C | Select-Object -ExpandProperty Size) * 100\"")
            if c_free_pct and safe_float(c_free_pct) < 10:
                declencher("Espace disque C: critique", f"Espace C: inférieur à {safe_float(c_free_pct):.1f}%")

            # 8. CPU Queue Length élevé
            cpu_queue = exec_cmd(ssh_client, "powershell -Command \"(Get-Counter '\\System\\Processor Queue Length').CounterSamples.CookedValue\"")
            if cpu_queue and safe_float(cpu_queue) > 10:
                declencher("File d'attente CPU élevée", f"Queue CPU = {safe_float(cpu_queue)}")

            # 9. Connexions TCP sortantes excessives
            tcp_out = exec_cmd(ssh_client, "powershell -Command \"(Get-NetTCPConnection -State Established).Count\"")
            if tcp_out and tcp_out.isdigit() and int(tcp_out) > 3000:
                declencher("Connexions TCP Windows saturées", f"{tcp_out} connexions actives")

            # 10. Sessions inactives RDP (Zombies RDP)
            rdp_disc = exec_cmd(ssh_client, "powershell -Command \"(quser | Select-String 'Disc').Count\"")
            if rdp_disc and rdp_disc.isdigit() and int(rdp_disc) > 5:
                declencher("Sessions RDP Fantômes", f"{rdp_disc} sessions déconnectées occupent la RAM")

        # ==========================
        # 🔥 RÈGLES DYNAMIQUES (Custom)
        # ==========================
        from remediation.models import AnomalieRegle
        if ssh_client:
            regles_dyn = AnomalieRegle.objects.filter(os_cible__in=['all', os_type])
            for regle in regles_dyn:
                try:
                    res_dyn = exec_cmd(ssh_client, regle.cmd_detection)
                    if res_dyn and res_dyn.strip():
                        declencher(regle.nom, f"Anomalie détectée par règle dynamique '{regle.nom}':\n{res_dyn.strip()[:200]}")
                except Exception as e:
                    logger.error(f"[REGLE_DYN] Erreur exécution {regle.nom} sur {e.nom}: {e}")



        # ==========================
        # 🌐 RÉSEAU (RESTORED)
        # ==========================
        drops_in = int(perf.get("drops_in") or mat.get("drops_in") or 0)
        drops_out = int(perf.get("drops_out") or mat.get("drops_out") or 0)
        if drops_in > 0 or drops_out > 0:
            declencher("Pertes de paquets", f"Drops RX:{drops_in} TX:{drops_out}")

        if int(mat.get("crc_in") or mat.get("errors_in") or 0) > 0 or int(mat.get("crc_out") or mat.get("errors_out") or 0) > 0:
            declencher("Erreurs CRC", "Erreurs de transmission détectées sur l'interface")

        if packet_loss > 5.0:
            declencher("Perte de paquets (Ping)", f"{packet_loss:.1f}% de paquets perdus")
        
        if ping_ms and ping_ms > 200:
            declencher("Latence excessive", f"{ping_ms:.1f} ms")
        
        if jitter_ms and jitter_ms > 30:
            declencher("Jitter élevé", f"{jitter_ms:.1f} ms")

        # Nouveautés Réseau (10 supplémentaires)
        # 1. Utilisation Processeur Routeur/Switch (via SNMP fallback)
        cpu_snmp = safe_float(mat.get("cpu_usage"))
        if cpu_snmp and cpu_snmp > 95:
            declencher("CPU Équipement Réseau saturé", f"CPU (SNMP) à {cpu_snmp}%")

        # 2. Ports d'interface d'administration bloqués (Ping OK mais ports fermés)
        from monitoring.ssh_utils import exec_cmd
        import socket
        if str(e.statut) != "hors ligne" and e.type_equipement in ["routeur", "switch", "parefeu"]:
            # 3. Flap des interfaces (Interface Up/Down fréquent) -> Détection via logs si dispo
            if logs and sum(1 for line in logs if "link down" in line.lower() or "link up" in line.lower()) > 5:
                declencher("Instabilité Interface (Flapping)", "De nombreux up/down sur une interface réseau")
            
            # 4. Spanning Tree Topology Change (Boucle réseau STP)
            if logs and sum(1 for line in logs if "topology change" in line.lower()) > 2:
                declencher("Changement de topologie (STP)", "Potentielle boucle réseau (Spanning Tree)")
            
            # 5. BGP Session Down
            if logs and any("bgp" in l.lower() and "down" in l.lower() for l in logs):
                declencher("Session BGP inactive", "Un voisin BGP est tombé")
            
            # 6. OSPF Neighbor Down
            if logs and any("ospf" in l.lower() and "down" in l.lower() for l in logs):
                declencher("Voisin OSPF inactif", "Un voisin OSPF a perdu la relation d'adjacence")

            # 7. Duplex Mismatch (Collision)
            if logs and any("duplex mismatch" in l.lower() for l in logs):
                declencher("Incompatibilité Duplex", "Conflit Half-Duplex / Full-Duplex")
            
            # 8. MAC Address Flapping (Host Move)
            if logs and any("mac address flapping" in l.lower() or "host move" in l.lower() for l in logs):
                declencher("Spoofing d'adresse MAC (Flapping)", "Conflit d'adresse MAC ou attaque ARP")
            
            # 9. RAM Routeur (SNMP fallback)
            ram_snmp = safe_float(mat.get("ram_usage"))
            if ram_snmp and ram_snmp > 95:
                declencher("RAM Équipement Réseau saturée", f"RAM (SNMP) à {ram_snmp}%")
            
            # 10. Pare-feu : Drops massifs détectés
            if logs and sum(1 for line in logs if "deny" in line.lower() or "drop" in line.lower() or "block" in line.lower()) > 50:
                declencher("Attaque Pare-feu (Logs)", "Volume anormal de requêtes bloquées (Scan / DDoS)")

        # ==========================
        # 📊 BANDE PASSANTE
        # ==========================
        bw_in = float(perf.get("bandwidth_in_mbps") or 0)
        bw_out = float(perf.get("bandwidth_out_mbps") or 0)
        if bw_in > 800 or bw_out > 800:
            declencher("Bande passante saturée", f"IN: {bw_in:.1f} Mbps, OUT: {bw_out:.1f} Mbps")

        # ==========================
        # 🌡 MATÉRIEL
        # ==========================
        if float(mat.get("temp") or 0) > 70:
            declencher("Surchauffe", f"{mat.get('temp')} °C")

        # ==========================
        # 🔐 LOGS (Uniquement si pas déjà détecté par OS-Check)
        # ==========================
        if not ssh_client: # Fallback logs si SSH direct a échoué
            if any("ssh" in l.lower() and "failed" in l.lower() for l in logs): declencher("SSH indisponible", "Erreurs SSH dans les logs")
            if any("nginx" in l.lower() and "failed" in l.lower() for l in logs): declencher("Service HTTP down", "Nginx en erreur")
            if any("docker" in l.lower() and "error" in l.lower() for l in logs): declencher("Docker bloqué", "Erreur Docker détectée")

        if ssh_client: ssh_client.close()

        # ==========================
        # 🔁 GESTION ÉCHECS
        # ==========================
        e.echec_consecutif = e.echec_consecutif + 1 if anomalies else 0

        # ==========================
        # 🛠 MAINTENANCE AUTO
        # ==========================
        if e.echec_consecutif >= 2:
            Maintenance.objects.create(
                equipement=e,
                debut=timezone.now(),
                fin=timezone.now() + timedelta(hours=4),
                active=True,
                raison="Maintenance automatique (panne persistante)",
                cree_par=None,
            )

            e.statut = "maintenance"
            e.echec_consecutif = 0
            e.save(update_fields=["statut", "echec_consecutif"])
            return {"equipement": e.nom, "anomalies": []}

        # ==========================
        # ✅ FINAL & AUTO-RESOLUTION
        # ==========================
        # On résout automatiquement les incidents qui ne sont plus détectés
        incidents_ouverts = Incident.objects.filter(equipement=e, statut="ouvert")
        for inc in incidents_ouverts:
            if inc.titre not in anomalies:
                inc.statut = "résolu"
                inc.date_resolution = timezone.now()
                inc.save(update_fields=["statut", "date_resolution"])
                logger.info(f"[AUTO-RESOLU] {e.nom} : {inc.titre} n'est plus détecté")

        e.statut = "en ligne" if not anomalies else "alerte"
        e.derniere_verification = timezone.now()
        e.save(update_fields=["statut", "derniere_verification", "echec_consecutif"])

        return {"equipement": e.nom, "anomalies": anomalies}

    except Exception as ex:
        if e:
            e.statut = "hors ligne"
            e.save(update_fields=["statut"])
        logger.error(f"[ERREUR ANALYSE] {getattr(e, 'nom', 'Inconnu')}: {ex}", exc_info=True)
        return {"equipement": getattr(e, "nom", "Inconnu"), "anomalies": ["Erreur critique"]}
# =========================================
# 5️⃣ Analyse globale multi-thread
# =========================================
def analyser_toutes_anomalies():
    equipements = EquipementReseau.objects.all()
    resultats = []

    logger.info(f"[SCAN] Analyse de {equipements.count()} équipements...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(analyser_un_equipement, e) for e in equipements]
        for future in concurrent.futures.as_completed(futures):
            try:
                resultats.append(future.result())
            except Exception as e:
                logger.error(f"[THREAD ERREUR] {e}", exc_info=True)

    logger.info(f"[SCAN] Terminé — {len(resultats)} équipements analysés.")
    return resultats


