# discovery/alerts.py
import threading
import logging
import json
import requests
from datetime import datetime
from typing import List, Optional

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger("discovery.alerts")


# ============================================================================
# CONFIGURATION
# ============================================================================

class AlertConfig:
    """Configuration centralisée des alertes"""
    
    # Seuils
    SEUIL_INDIVIDUEL = 5      # Max emails individuels avant récapitulatif
    SEUIL_BATCH_FORCE = 10    # Force le mode batch au-delà
    
    # Timeout requêtes HTTP (Slack/Teams)
    TIMEOUT_WEBHOOK = 10
    
    # Couleurs pour Teams/Slack
    COLORS = {
        'danger': '#dc3545',   # Rouge - nouveau device
        'warning': '#ffc107',  # Jaune - attention
        'info': '#17a2b8',     # Bleu - info
        'success': '#28a745',  # Vert - OK
    }


# ============================================================================
# UTILITAIRES
# ============================================================================

def format_device_info(eq) -> dict:
    """Formate les infos d'un équipement pour les notifications"""
    return {
        'ip': eq.adresse_ip,
        'hostname': eq.hostname or 'Inconnu',
        'type': eq.type_detecte,
        'mac': getattr(eq, 'mac_adresse', 'N/A'),
        'os': getattr(eq, 'systeme_exploitation', 'Inconnu'),
        'vu_le': eq.vu_le.strftime('%d/%m/%Y %H:%M:%S') if eq.vu_le else 'N/A'
    }


# ============================================================================
# EMAIL
# ============================================================================

def _send_email_individuel(equipement) -> bool:
    """Email pour un seul équipement"""
    
    if not getattr(settings, 'ADMIN_EMAIL', None):
        logger.error("[ALERT] ADMIN_EMAIL non configuré")
        return False

    info = format_device_info(equipement)
    
    sujet = f"🚨 Nouvel équipement - {info['ip']}"
    
    message_text = f"""
╔══════════════════════════════════════════════════════════╗
║          ALERTE INFRACONTROL - SCAN RÉSEAU               ║
╚══════════════════════════════════════════════════════════╝

🌐 Adresse IP    : {info['ip']}
📝 Hostname      : {info['hostname']}
🏷️  Type          : {info['type']}
🔌 Adresse MAC   : {info['mac']}
💻 OS Détecté    : {info['os']}
📅 Détecté le    : {info['vu_le']}

⚠️  Cet équipement n'est pas supervisé.

Actions : Vérifier → Ajouter au monitoring si légitime
"""
    
    message_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; }}
        .content {{ background: #f8f9fa; padding: 20px; }}
        .detail {{ margin: 10px 0; padding: 10px; background: white; border-left: 4px solid #dc3545; }}
        .label {{ font-weight: bold; color: #495057; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚨 Nouvel équipement détecté</h2>
        </div>
        <div class="content">
            <div class="detail">
                <p><span class="label">IP:</span> {info['ip']}</p>
                <p><span class="label">Hostname:</span> {info['hostname']}</p>
                <p><span class="label">Type:</span> {info['type']}</p>
                <p><span class="label">MAC:</span> {info['mac']}</p>
                <p><span class="label">OS:</span> {info['os']}</p>
                <p><span class="label">Détecté:</span> {info['vu_le']}</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    try:
        send_mail(
            subject=sujet,
            message=message_text,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alert@infracontrol.local'),
            recipient_list=[settings.ADMIN_EMAIL],
            html_message=message_html,
            fail_silently=False,
        )
        logger.info(f"[EMAIL] ✅ Envoyé pour {info['ip']}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] ❌ Échec pour {info['ip']}: {e}")
        return False


def _send_email_recapitulatif(equipements: List) -> bool:
    """Email récapitulatif pour plusieurs équipements"""
    
    if not getattr(settings, 'ADMIN_EMAIL', None):
        return False
    
    count = len(equipements)
    sujet = f"🚨 {count} nouveaux équipements détectés - Récapitulatif"
    
    # Tableau texte
    lignes = []
    for i, eq in enumerate(equipements[:50], 1):  # Max 50 dans l'email
        info = format_device_info(eq)
        lignes.append(f"{i:2}. {info['ip']:<15} | {info['hostname']:<20} | {info['type']}")
    
    if count > 50:
        lignes.append(f"\n... et {count - 50} autres équipements")
    
    tableau = "\n".join(lignes)
    
    message_text = f"""
╔══════════════════════════════════════════════════════════╗
║       RÉCAPITULATIF INFRACONTROL - SCAN RÉSEAU           ║
╚══════════════════════════════════════════════════════════╝

📊 Nombre d'équipements détectés : {count}

LISTE DES ÉQUIPEMENTS :
{'─' * 60}
{tableau}
{'─' * 60}

⚠️  Ces équipements ne sont pas supervisés.

Action recommandée : Vérifier l'interface Infracontrol pour
traitement groupé ou individuel.

{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""
    
    # Version HTML avec tableau
    rows_html = ""
    for eq in equipements[:50]:
        info = format_device_info(eq)
        rows_html += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{info['ip']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{info['hostname']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{info['type']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{info['mac']}</td>
        </tr>
        """
    
    message_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; }}
        .stats {{ background: #f8f9fa; padding: 20px; margin: 20px 0; text-align: center; font-size: 24px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #495057; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        .alert {{ background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚨 Alerte Multiple - Récapitulatif</h2>
        </div>
        <div class="stats">
            <strong>{count}</strong> nouveaux équipements détectés
        </div>
        <table>
            <thead>
                <tr>
                    <th>IP</th>
                    <th>Hostname</th>
                    <th>Type</th>
                    <th>MAC</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        {'<p style="text-align: center; color: #666;">... et ' + str(count - 50) + ' autres équipements</p>' if count > 50 else ''}
        <div class="alert">
            <strong>⚠️ Action requise :</strong> Vérifiez ces équipements dans l'interface Infracontrol.
        </div>
    </div>
</body>
</html>
"""
    
    try:
        send_mail(
            subject=sujet,
            message=message_text,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alert@infracontrol.local'),
            recipient_list=[settings.ADMIN_EMAIL],
            html_message=message_html,
            fail_silently=False,
        )
        logger.info(f"[EMAIL] ✅ Récapitulatif envoyé: {count} équipements")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] ❌ Échec récapitulatif: {e}")
        return False


# ============================================================================
# SLACK
# ============================================================================

def _send_slack_individuel(equipement) -> bool:
    """Notification Slack pour un équipement"""
    
    webhook = getattr(settings, 'SLACK_WEBHOOK_URL', None)
    if not webhook:
        return False
    
    info = format_device_info(equipement)
    
    payload = {
        "text": "🚨 Nouvel équipement détecté",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 Alerte Infracontrol - Nouveau Device"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*IP:*\n`{info['ip']}`"},
                    {"type": "mrkdwn", "text": f"*Hostname:*\n{info['hostname']}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{info['type']}"},
                    {"type": "mrkdwn", "text": f"*OS:*\n{info['os']}"},
                    {"type": "mrkdwn", "text": f"*MAC:*\n`{info['mac']}`"},
                    {"type": "mrkdwn", "text": f"*Détecté:*\n{info['vu_le']}"}
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "⚠️ Cet équipement n'est pas supervisé"}
                ]
            }
        ]
    }
    
    try:
        response = requests.post(
            webhook,
            json=payload,
            timeout=AlertConfig.TIMEOUT_WEBHOOK
        )
        response.raise_for_status()
        logger.info(f"[SLACK] ✅ Envoyé pour {info['ip']}")
        return True
    except Exception as e:
        logger.error(f"[SLACK] ❌ Échec pour {info['ip']}: {e}")
        return False


def _send_slack_recapitulatif(equipements: List) -> bool:
    """Notification Slack récapitulative"""
    
    webhook = getattr(settings, 'SLACK_WEBHOOK_URL', None)
    if not webhook:
        return False
    
    count = len(equipements)
    
    # Liste compacte (max 20 pour Slack)
    liste = []
    for eq in equipements[:20]:
        info = format_device_info(eq)
        liste.append(f"• `{info['ip']}` | {info['hostname']} | {info['type']}")
    
    texte_liste = "\n".join(liste)
    if count > 20:
        texte_liste += f"\n... et {count - 20} autres"
    
    payload = {
        "text": f"🚨 {count} nouveaux équipements détectés",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Alerte Multiple - {count} Devices"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Récapitulatif des découvertes :*\n\n{texte_liste}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"⚠️ {count} équipements non supervisés - Voir Infracontrol"}
                ]
            }
        ]
    }
    
    try:
        response = requests.post(webhook, json=payload, timeout=AlertConfig.TIMEOUT_WEBHOOK)
        response.raise_for_status()
        logger.info(f"[SLACK] ✅ Récapitulatif envoyé: {count} équipements")
        return True
    except Exception as e:
        logger.error(f"[SLACK] ❌ Échec récapitulatif: {e}")
        return False


# ============================================================================
# MICROSOFT TEAMS
# ============================================================================

def _send_teams_individuel(equipement) -> bool:
    """Notification Teams pour un équipement"""
    
    webhook = getattr(settings, 'TEAMS_WEBHOOK_URL', None)
    if not webhook:
        return False
    
    info = format_device_info(equipement)
    
    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": AlertConfig.COLORS['danger'],
        "summary": f"Nouvel équipement: {info['ip']}",
        "sections": [{
            "activityTitle": "🚨 Infracontrol - Nouvel Équipement Détecté",
            "facts": [
                {"name": "Adresse IP", "value": info['ip']},
                {"name": "Hostname", "value": info['hostname']},
                {"name": "Type", "value": info['type']},
                {"name": "Adresse MAC", "value": info['mac']},
                {"name": "OS Détecté", "value": info['os']},
                {"name": "Détecté le", "value": info['vu_le']}
            ],
            "markdown": True
        }]
    }
    
    try:
        response = requests.post(webhook, json=payload, timeout=AlertConfig.TIMEOUT_WEBHOOK)
        response.raise_for_status()
        logger.info(f"[TEAMS] ✅ Envoyé pour {info['ip']}")
        return True
    except Exception as e:
        logger.error(f"[TEAMS] ❌ Échec pour {info['ip']}: {e}")
        return False


def _send_teams_recapitulatif(equipements: List) -> bool:
    """Notification Teams récapitulative"""
    
    webhook = getattr(settings, 'TEAMS_WEBHOOK_URL', None)
    if not webhook:
        return False
    
    count = len(equipements)
    
    # Tableau de faits (max 15 pour Teams)
    facts = [{"name": "Nombre total", "value": str(count)}]
    
    for i, eq in enumerate(equipements[:15], 1):
        info = format_device_info(eq)
        facts.append({
            "name": f"{i}. {info['ip']}",
            "value": f"{info['hostname']} ({info['type']})"
        })
    
    if count > 15:
        facts.append({"name": "...", "value": f"Et {count - 15} autres équipements"})
    
    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": AlertConfig.COLORS['warning'],
        "summary": f"{count} nouveaux équipements détectés",
        "sections": [{
            "activityTitle": f"🚨 Infracontrol - Alerte Multiple ({count} devices)",
            "facts": facts,
            "markdown": True
        }]
    }
    
    try:
        response = requests.post(webhook, json=payload, timeout=AlertConfig.TIMEOUT_WEBHOOK)
        response.raise_for_status()
        logger.info(f"[TEAMS] ✅ Récapitulatif envoyé: {count} équipements")
        return True
    except Exception as e:
        logger.error(f"[TEAMS] ❌ Échec récapitulatif: {e}")
        return False


# ============================================================================
# FONCTION PRINCIPALE AVEC GESTION DU SEUIL
# ============================================================================

def envoyer_alertes(equipements: List, force_recap: bool = False) -> dict:
    """
    Crée des incidents pour les équipements découverts au lieu d'envoyer des mails.
    La centralisation est gérée par la tâche de résumé.
    """
    if not equipements:
        return {'total': 0, 'mode': 'aucun', 'succes': {}}
    
    from monitoring.models import Incident, EquipementReseau
    
    count = 0
    for eq in equipements:
        # On essaie de trouver un équipement de référence pour l'incident
        # Si c'est un EquipementDecouvert, on crée un incident lié à un équipement de "système" ou générique si possible
        # Ici on va créer un incident par IP découverte
        
        # On cherche si l'IP est déjà dans EquipementReseau pour lier l'incident
        ref_eq = EquipementReseau.objects.filter(adresse_ip=eq.adresse_ip).first()
        if not ref_eq:
            # Si pas supervisé, on cherche un équipement "serveur de monitoring" ou le premier trouvé pour porter l'alerte
            ref_eq = EquipementReseau.objects.first()

        if ref_eq:
            Incident.objects.get_or_create(
                equipement=ref_eq,
                titre=f"Nouvel équipement détecté : {eq.adresse_ip}",
                statut="ouvert",
                defaults={
                    "description": f"Équipement découvert lors du scan réseau.\nIP: {eq.adresse_ip}\nMAC: {getattr(eq, 'mac_adresse', 'N/A')}\nType: {getattr(eq, 'type_detecte', 'Inconnu')}",
                    "niveau": "avertissement",
                    "categorie": "decouverte",
                }
            )
            count += 1
    
    logger.info(f"[DISCOVERY ALERTE] {count} incidents de découverte créés.")
    
    return {
        'total': count,
        'mode': 'incident',
        'succes': {'email': False, 'slack': False, 'teams': False}
    }

def envoyer_alerte_decouverte(equipement) -> bool:
    """
    Fonction legacy pour un seul équipement
    """
    res = envoyer_alertes([equipement], force_recap=False)
    return res['total'] > 0


# ============================================================================
# COMPATIBILITÉ ANCIEN CODE (threads)
# ============================================================================

def envoyer_alerte_thread(equipements: List, force_recap: bool = False):
    """
    Lance l'envoi dans un thread (non bloquant)
    """
    if not equipements:
        return False
    
    thread = threading.Thread(
        target=envoyer_alertes,
        args=(equipements, force_recap),
        daemon=True,
        name=f"Alert-{len(equipements)}devices"
    )
    thread.start()
    return True