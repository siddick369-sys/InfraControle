import logging
import subprocess
import paramiko
import time
import platform
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from monitoring.smart_monitor import analyser_toutes_anomalies
from monitoring.models import ChangePlanifie, EquipementReseau, Incident, TacheMonitoring

logger = logging.getLogger("monitoring.tasks")
@shared_task(name="monitoring.tasks.tache_analyse_anomalies")
def tache_analyse_anomalies():
    """
    🧠 Tâche planifiée Celery : 
    Analyse automatiquement tous les équipements réseau pour détecter les anomalies.
    """
    logger.info(f"[TÂCHE] Démarrage de l’analyse des anomalies ({timezone.now()})")

    try:
        resultats = analyser_toutes_anomalies()

        nb_total = len(resultats)
        nb_anomalies = sum(1 for _, anomalies in resultats if anomalies)

        logger.info(f"[TÂCHE TERMINÉE] {nb_total} équipements analysés, {nb_anomalies} anomalies détectées.")

        return {
            "timestamp": timezone.now().isoformat(),
            "equipements_analyzes": nb_total,
            "anomalies_detectees": nb_anomalies,
        }

    except Exception as e:
        logger.error(f"[TÂCHE ERREUR] {e}", exc_info=True)
        raise e  # retire self.retry, inutile ici    

@shared_task(name="monitoring.tasks.verifier_statut_equipements")
def verifier_statut_equipements():
    debut = time.time()
    tache = TacheMonitoring.objects.create(
        nom="Vérification des équipements",
        statut="en cours",
        date_execution=timezone.now()
    )

    total = 0
    ok = 0
    resultats = []

    is_windows = platform.system().lower() == "windows"

    from monitoring.utils.maintenance import est_en_maintenance

    for eq in EquipementReseau.objects.all():
        if est_en_maintenance(eq):
            logger.info(f"[TASKS] {eq.nom} en maintenance -> Saut du check statut.")
            ok += 1 # On considère OK pour ne pas fausser le ratio si besoin
            continue

        total += 1
        try:
            # ✅ Ping cross-platform
            ping_cmd = (
                ["ping", "-n", "1", eq.adresse_ip]  # Windows
                if is_windows
                else ["ping", "-c", "1", "-W", "2", eq.adresse_ip]  # Linux
            )

            ping = subprocess.run(
                ping_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )

            if ping.returncode != 0:
                eq.statut = "hors ligne"
                eq.derniere_verification = timezone.now()
                eq.save(update_fields=["statut", "derniere_verification"])
                resultats.append({"nom": eq.nom, "statut": "hors ligne"})
                continue

            # ✅ Test SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=eq.adresse_ip,
                port=eq.port_ssh or 22,
                username=eq.utilisateur_ssh,
                password=eq.mot_de_passe_ssh,
                timeout=8,
                look_for_keys=False,
                allow_agent=False
            )
            ssh.close()

            # Envoi d'email si l'équipement revient en ligne
            if eq.statut in ["hors ligne", "erreur", "inconnu"]:
                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(
                    subject=f"✅ Retour en Ligne : {eq.nom} ({eq.adresse_ip})",
                    message=f"L'équipement {eq.nom} ({eq.adresse_ip}) est de nouveau accessible via Ping et SSH après avoir été '{eq.statut}'.\nHeure: {timezone.now().strftime('%d/%m/%Y %H:%M')}",
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@infracontrol.local'),
                    recipient_list=getattr(settings, 'ADMIN_EMAILS', ['admin@infracontrol.local']),
                    fail_silently=True
                )
                logger.info(f"[ALERT] Email envoyé pour le retour en ligne de {eq.nom}")

            eq.statut = "en ligne"
            eq.derniere_verification = timezone.now()
            eq.save(update_fields=["statut", "derniere_verification"])
            resultats.append({"nom": eq.nom, "statut": "en ligne"})
            ok += 1

        except Exception as e:
            if eq.statut == "en ligne":
                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(
                    subject=f"🚨 Perte de Connexion : {eq.nom}",
                    message=f"L'équipement {eq.nom} ({eq.adresse_ip}) ne répond plus.\nErreur: {str(e)}",
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@infracontrol.local'),
                    recipient_list=getattr(settings, 'ADMIN_EMAILS', ['admin@infracontrol.local']),
                    fail_silently=True
                )
            eq.statut = "erreur"
            eq.derniere_verification = timezone.now()
            eq.save(update_fields=["statut", "derniere_verification"])
            resultats.append({"nom": eq.nom, "statut": "erreur", "details": str(e)})
            logger.warning(f"[ERREUR SSH] {eq.nom}: {e}")

    duree = round(time.time() - debut, 2)
    tache.resultat = {"total": total, "connectes": ok, "resultats": resultats}
    tache.duree = duree
    tache.statut = "succès"
    tache.message = f"{ok}/{total} équipements connectés"
    tache.save()

    logger.info(f"Vérification terminée ({ok}/{total}) en {duree}s")
    return resultats
@shared_task
def verifier_incidents_ouverts():
    from monitoring.models import Incident
    from monitoring.verifier_resolution import verifier_resolution_incident

    incidents = Incident.objects.filter(statut="ouvert")
    for incident in incidents:
        verifier_resolution_incident(incident)


@shared_task(name="monitoring.tasks.purge_incidents_resolus")
def purge_incidents_resolus():
    limite = timezone.now() - timezone.timedelta(days=1)

    qs = Incident.objects.filter(
        statut="résolu",
        date_resolution__isnull=False,
        date_resolution__lt=limite,
    )

    logger.error(f"[PURGE] Incidents trouvés : {qs.count()}")

    for inc in qs:
        logger.error(f"[PURGE] Suppression incident #{inc.id}")
        inc.delete()

    return qs.count()

from celery import shared_task
from django.utils import timezone
import logging
from celery import shared_task, group
from django.utils import timezone
import logging
from celery import shared_task
from django.utils import timezone
import logging

# Assurez-vous que l'import pointe vers le fichier corrigé ci-dessus
from monitoring.stat_collector import collecter_stat_complete
from monitoring.models import EquipementReseau

logger = logging.getLogger("monitoring.tasks")
from celery import shared_task
import logging
from monitoring.models import EquipementReseau
from monitoring.stat_collector import collecter_stat_complete

logger = logging.getLogger("monitoring.tasks")

@shared_task(
    name="monitoring.tasks.collecter_toutes_les_stats",
    time_limit=600,  # Limite de temps globale (10 minutes)
    soft_time_limit=540
)
def collecter_toutes_les_stats():
    """
    Tâche unique qui parcourt tous les équipements et lance la collecte.
    """
    equipements = EquipementReseau.objects.all()
    total = equipements.count()
    success = 0
    erreurs = 0

    logger.info(f"[TASK] Lancement de la collecte globale pour {total} equipements.")

    for eq in equipements:
        try:
            # On appelle l'orchestrateur pour chaque machine
            # La gestion des erreurs est deja faite a l'interieur de collecter_stat_complete
            stat = collecter_stat_complete(eq)
            
            if stat and stat.disponible:
                success += 1
            else:
                erreurs += 1
                
        except Exception as e:
            erreurs += 1
            logger.error(f"[TASK] Erreur critique sur {eq.adresse_ip}: {e}")
            # On continue la boucle meme si un equipement fait crasher le script
            continue

    msg_final = f"Collecte terminee : {success} succes, {erreurs} echecs sur {total} au total."
    logger.info(f"[TASK] {msg_final}")
    
    return msg_final
logger = logging.getLogger("wifi.tasks")


@shared_task(
    name="monitoring.tasks.collecter_wifi_equipements",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 30},
)
def collecter_wifi_equipements():
    """
    Tâche centrale Wi-Fi :
    - collecte données
    - enregistrement DB
    - détection incidents
    - auto-maintenance
    """

    from monitoring.models import EquipementReseau, WifiAccessPoint
    from monitoring.wifi.collector import collect_wifi
    from monitoring.wifi.persist import enregistrer_wifi
    from monitoring.wifi.detection import detecter_incidents_wifi
    from monitoring.wifi.auto_maintenance import auto_maintenance_wifi

    aps = (
        EquipementReseau.objects
        .filter(type_equipement="wifi", actif=True)
        .select_related("wifi_ap")
    )

    for equipement in aps:
        try:
            logger.info(f"[WIFI] Analyse AP {equipement.nom}")

            # ⚠️ Vérifier qu'il s'agit bien d'un AP Wi-Fi
            if not hasattr(equipement, "wifi_ap"):
                logger.warning(f"[WIFI] {equipement.nom} sans WifiAccessPoint")
                continue

            # 1️⃣ Collecte
            data = collect_wifi(equipement)

            if not data:
                logger.warning(f"[WIFI] Aucune donnée pour {equipement.nom}")
                continue

            # 2️⃣ Enregistrement DB
            enregistrer_wifi(equipement, data)

            # 3️⃣ Détection incidents
            anomalies = detecter_incidents_wifi(equipement)
            from monitoring.wifi.ai.recommender import generer_recommandations_wifi

# après la collecte et la détection
            generer_recommandations_wifi(equipement.wifi_ap)

            # 4️⃣ Auto-maintenance intelligente
            if anomalies:
                logger.warning(
                    f"[WIFI] {equipement.nom} anomalies détectées : {anomalies}"
                )
                auto_maintenance_wifi(equipement)
                
        

        except Exception as e:
            logger.error(
                f"[WIFI ERROR] {equipement.nom}: {e}",
                exc_info=True
            )

    logger.info("[WIFI] Analyse Wi-Fi terminée")
    
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from monitoring.models import ChangePlanifie
from monitoring.core import executer_commande_core
import logging

logger = logging.getLogger(__name__)


@shared_task(name="monitoring.tasks.executer_changements_planifies")
def executer_changements_planifies():
    """
    Exécute les changements planifiés (one-shot ou périodiques)
    ⚠️ Ne dépend PAS des vues Django
    """

    now = timezone.now()

    changements = ChangePlanifie.objects.filter(
        actif=True,
        statut="valide"
    )

    for change in changements:
        try:
            # ==========================
            # ⏱️ CALCUL DU MOMENT D’EXÉCUTION
            # ==========================
            reference = change.derniere_execution or change.date_execution

            if reference and reference > now:
                continue  # ⏳ Pas encore le moment

            logger.info(
                f"[CHANGE] Exécution planifiée : {change.commande.nom} "
                f"sur {change.equipement.nom}"
            )

            # ==========================
            # 🔐 EXÉCUTION MÉTIER
            # ==========================
            executer_commande_core(
                equipement=change.equipement,
                commande=change.commande,
                utilisateur=change.cree_par,   # peut être None → géré
                ip_utilisateur="scheduler"
            )

            # ==========================
            # 🕒 MISE À JOUR DES DATES
            # ==========================
            change.derniere_execution = now

            if change.frequence == "daily":
                change.date_execution = now + timedelta(days=1)

            elif change.frequence == "weekly":
                change.date_execution = now + timedelta(weeks=1)

            elif change.frequence == "once":
                change.statut = "execute"
                change.actif = False

            change.save()

        except Exception as e:
            logger.error(
                f"[CHANGE ERROR] {change.commande.nom} "
                f"sur {change.equipement.nom} : {e}",
                exc_info=True
            )

@shared_task(name="monitoring.tasks.envoi_resume_quotidien")
def envoi_resume_quotidien():
    """
    Tâche centrale d'envoi des alertes :
    - Regroupe tous les incidents non notifiés
    - Applique un rate limit de 2/heure pour la catégorie 'santé'
    """
    from monitoring.models import Incident, EquipementReseau
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings
    from django.utils import timezone
    from datetime import timedelta
    
    logger.info("[ALERTE CENTRALISÉE] Démarrage du traitement des incidents.")
    
    # 1. Récupérer les incidents non notifiés
    incidents = Incident.objects.filter(notifie=False, statut="ouvert").select_related('equipement')
    if not incidents.exists():
        logger.info("[ALERTE CENTRALISÉE] Aucun nouvel incident à notifier.")
        return "Aucun incident"
        
    now = timezone.now()
    seuil_sante = now - timedelta(minutes=30) # 2 fois par heure = toutes les 30 min
    
    # 2. Groupe et filtrage intelligent
    incidents_a_notifier = []
    ids_incidents_traites = []
    
    for inc in incidents:
        # Logique spécifique SANTE : max 2 par heure (un toutes les 30 min)
        if inc.categorie == 'sante':
            eq = inc.equipement
            if eq.derniere_alerte_sante and eq.derniere_alerte_sante > seuil_sante:
                # Trop tôt pour cet équipement (santé)
                logger.debug(f"[ALERTE SKIP SANTE] Cooldown en cours pour {eq.nom}")
                continue
            
            # On accepte l'incident et on met à jour le timestamp de l'équipement
            eq.derniere_alerte_sante = now
            eq.save(update_fields=['derniere_alerte_sante'])

        incidents_a_notifier.append(inc)
        ids_incidents_traites.append(inc.id)

    if not incidents_a_notifier:
        return "Cooldown actif pour tous les incidents"

    # 3. Préparer l'email (groupement par équipement pour le template)
    incidents_par_equipement = {}
    for inc in incidents_a_notifier:
        nom_eq = inc.equipement.nom
        if nom_eq not in incidents_par_equipement:
            incidents_par_equipement[nom_eq] = []
        incidents_par_equipement[nom_eq].append(inc)
        
    sujet = f"🔔 Alertes Centralisées InfraControl - {now.strftime('%d/%m/%Y %H:%M')}"
    
    context = {
        'incidents_par_equipement': incidents_par_equipement,
        'date': now,
        'total_incidents': len(incidents_a_notifier)
    }
    
    html_content = render_to_string('monitoring/emails/resume_quotidien.html', context)
    text_content = f"Résumé de {len(incidents_a_notifier)} alertes détectées."
    
    admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@infracontrol.local')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@infracontrol.local')
    
    msg = EmailMultiAlternatives(sujet, text_content, from_email, [admin_email])
    msg.attach_alternative(html_content, "text/html")
    
    try:
        msg.send()
        # 4. Marquer comme notifiés
        Incident.objects.filter(id__in=ids_incidents_traites).update(notifie=True)
        logger.info(f"[ALERTE CENTRALISÉE] Email envoyé avec {len(incidents_a_notifier)} incidents.")
        return f"Envoyé : {len(incidents_a_notifier)} incidents"
    except Exception as e:
        logger.error(f"[ALERTE CENTRALISÉE] Échec de l'envoi email : {e}", exc_info=True)
        return str(e)


@shared_task(name="monitoring.tasks.envoyer_recapitulatif_journalier_massif")
def envoyer_recapitulatif_journalier_massif():
    """
    Envoie un rapport récapitulatif complet de tous les équipements réseau une fois par jour.
    Agrége les pannes, santés moyennes, etc.
    """
    from monitoring.models import EquipementReseau, Incident
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.utils import timezone
    from django.conf import settings
    from django.db.models import Avg

    equipements = EquipementReseau.objects.all()
    incidents_24h = Incident.objects.filter(date_debut__gte=timezone.now() - timezone.timedelta(days=1))
    
    total = equipements.count()
    en_ligne = equipements.filter(statut="en ligne").count()
    moyenne_cpu = equipements.aggregate(Avg('cpu_usage'))['cpu_usage__avg'] or 0
    moyenne_ram = equipements.aggregate(Avg('ram_usage'))['ram_usage__avg'] or 0
    sante_globale = max(0, 100 - ((moyenne_cpu + moyenne_ram) / 2)) # Pseudo-score de santé
    
    total_incidents = incidents_24h.count()
    incidents_critiques = incidents_24h.filter(niveau='critique').count()

    context = {
        'date': timezone.now().strftime('%d/%m/%Y'),
        'total': total,
        'en_ligne': en_ligne,
        'hors_ligne': total - en_ligne,
        'moyenne_sante': round(sante_globale, 1),
        'total_incidents_24h': total_incidents,
        'incidents_critiques': incidents_critiques,
        'equipements': equipements
    }

    try:
        # Création des lignes de détails pour chaque équipement
        details_html = ""
        for eq in equipements:
            cpu_color = "red" if (eq.cpu_usage or 0) > 85 else ("orange" if (eq.cpu_usage or 0) > 60 else "green")
            ram_color = "red" if (eq.ram_usage or 0) > 85 else ("orange" if (eq.ram_usage or 0) > 60 else "green")
            statut_badge = "<span style='color:green'>En ligne</span>" if eq.statut == "en ligne" else "<span style='color:red'>Hors ligne/Erreur</span>"
            
            details_html += f"""
            <tr>
                <td style="padding:8px; border:1px solid #ddd;">{eq.nom}</td>
                <td style="padding:8px; border:1px solid #ddd;">{eq.adresse_ip} ({eq.type_equipement})</td>
                <td style="padding:8px; border:1px solid #ddd;">{statut_badge}</td>
                <td style="padding:8px; border:1px solid #ddd; color:{cpu_color}"><b>{eq.cpu_usage or 0}%</b></td>
                <td style="padding:8px; border:1px solid #ddd; color:{ram_color}"><b>{eq.ram_usage or 0}%</b></td>
            </tr>
            """

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; background-color:#f9f9fa; padding:20px;">
            <div style="max-width:800px; margin:0 auto; background:#ffffff; border-radius:10px; overflow:hidden; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div style="background-color:#0f172a; color:#0ea5e9; padding:20px; text-align:center;">
                    <h2 style="margin:0;">InfraControl - Résumé Exécutif Détaillé</h2>
                    <p style="margin:5px 0 0; color:#cbd5e1;">Rapport Généré le {context['date']} à {timezone.now().strftime('%H:%M')} (Heure du Conteneur DB)</p>
                </div>
                
                <div style="padding:20px;">
                    <h3 style="border-bottom: 2px solid #e2e8f0; padding-bottom:10px;">📉 Indicateurs Globaux</h3>
                    <ul style="list-style:none; padding:0; display:flex; gap:20px; flex-wrap:wrap;">
                        <li style="background:#f1f5f9; padding:15px; border-radius:8px; flex:1;">Total: <b>{context['total']}</b></li>
                        <li style="background:#dcfce7; padding:15px; border-radius:8px; flex:1;">Actifs: <b style="color:green">{context['en_ligne']}</b></li>
                        <li style="background:#fee2e2; padding:15px; border-radius:8px; flex:1;">Hors Ligne: <b style="color:red">{context['hors_ligne']}</b></li>
                        <li style="background:#e0f2fe; padding:15px; border-radius:8px; flex:1;">Santé: <b>{context['moyenne_sante']}%</b></li>
                    </ul>

                    <h3 style="border-bottom: 2px solid #e2e8f0; padding-bottom:10px; margin-top:30px;">🚨 Incidents Récents (24H)</h3>
                    <p>Total des pannes : <b>{context['total_incidents_24h']}</b> (dont <b style="color:red">{context['incidents_critiques']} critiques</b>).</p>
                    
                    <h3 style="border-bottom: 2px solid #e2e8f0; padding-bottom:10px; margin-top:30px;">💻 Statistiques en Temps Réel par Équipement</h3>
                    <table style="width:100%; border-collapse: collapse; text-align:left; margin-top:15px;">
                        <thead style="background:#0ea5e9; color:#ffffff;">
                            <tr>
                                <th style="padding:10px; border:1px solid #ddd;">Nom</th>
                                <th style="padding:10px; border:1px solid #ddd;">IP / Type</th>
                                <th style="padding:10px; border:1px solid #ddd;">Statut</th>
                                <th style="padding:10px; border:1px solid #ddd;">CPU</th>
                                <th style="padding:10px; border:1px solid #ddd;">RAM</th>
                            </tr>
                        </thead>
                        <tbody>
                            {details_html}
                        </tbody>
                    </table>
                    
                    <p style="margin-top:30px; font-size:12px; color:#64748b; text-align:center;">
                        Ce rapport est généré automatiquement par le conteneur InfraControl.<br>
                        Veuillez vous connecter à l'<a href="http://localhost:8010">Interface d'Administration</a> pour intervenir.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        msg = EmailMultiAlternatives(
            f"📊 InfraControl - Résumé Exécutif Journalier ({context['date']})",
            "Veuillez lire la version HTML de ce message.",
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@infracontrol.local'),
            getattr(settings, 'ADMIN_EMAILS', ['admin@infracontrol.local'])
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        logger.info("[RECAP JOURNALIER] Email massif de résumé quotidien envoyé avec succès.")
        return "Succès de l'envoi"
    except Exception as e:
        logger.error(f"[RECAP JOURNALIER ERROR] {e}")
        return f"Erreur: {str(e)}"
