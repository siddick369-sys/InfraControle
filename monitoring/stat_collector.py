import logging
from django.utils import timezone
from monitoring.alerts import envoyer_alerte_health
from monitoring.models import StatReseau, EquipementReseau

# ==============================================================================
# 1. L'IMPORTATION CORRECTE
# ==============================================================================
# On importe la fonction depuis le fichier monitoring/network_utils.py
try:
    from monitoring.network import collecter_ping_jitter
except ImportError as e:
    # Fallback pour déboguer si le fichier est mal placé
    logging.getLogger("monitoring.collecte").error(f"Erreur d'import network_utils: {e}")
    # Fonction bouchon pour éviter le crash
    def collecter_ping_jitter(ip, count=4, timeout=2): return None, None, 100.0

from monitoring.ssh_utils import collecter_performance_ssh, collecter_logs_ssh
from monitoring.snmp_utils import collecter_materiel_snmp

logger = logging.getLogger("monitoring.collecte")

def collecter_stat_complete(equipement):
    """
    Orchestrateur principal.
    Utilise le nouveau script network_utils pour le Ping/Jitter.
    """
    ip = equipement.adresse_ip
    logger.info(f"[COLLECTE] Debut pour {equipement.nom} ({ip})")
    
    # =========================================================================
    # 2. APPEL DE VOTRE NOUVELLE FONCTION
    # =========================================================================
    try:
        # On appelle la fonction importée.
        # On peut ajuster count=10 pour plus de précision comme défini par défaut
        ping_ms, jitter_ms, packet_loss = collecter_ping_jitter(ip, count=4, timeout=2)
    except Exception as e:
        logger.warning(f"[COLLECTE] Erreur Ping critique {ip}: {e}")
        ping_ms, jitter_ms, packet_loss = None, None, 100.0

    # Vérification de disponibilité
    # Si packet_loss est None (erreur technique), on considère 100% de perte
    final_loss = packet_loss if packet_loss is not None else 100.0
    is_up = (final_loss < 100.0)

    # =========================================================================
    # 3. SUITE DE LA COLLECTE (SSH / SNMP)
    # =========================================================================
    ssh_data = {}
    snmp_data = {}
    anomalies = []
    
    if is_up:
        # --- SSH ---
        # On tente le SSH si l'utilisateur et le mot de passe sont renseignés sur l'équipement
        if equipement.utilisateur_ssh and (equipement.mot_de_passe_ssh or equipement.mot_de_passe_ssh_chiffre):
            try:
                ssh_data = collecter_performance_ssh(equipement) or {}
                anomalies = collecter_logs_ssh(equipement) or []
            except Exception as e:
                logger.error(f"[COLLECTE] Echec SSH sur {ip}: {e}")

        # --- SNMP ---
        if equipement.snmp_community:
            try:
                snmp_data = collecter_materiel_snmp(ip, equipement.snmp_community) or {}
            except Exception as e:
                logger.error(f"[COLLECTE] Echec SNMP sur {ip}: {e}")

    # =========================================================================
    # 4. SCORE ET SAUVEGARDE
    # =========================================================================
    score = 100
    if not is_up:
        score = 0
    else:
        # Pénalités basées sur vos nouvelles métriques précises
        if final_loss > 0: score -= int(final_loss * 2)
        if ping_ms and ping_ms > 100: score -= 10
        if jitter_ms and jitter_ms > 20: score -= 5  # Jitter > 20ms est mauvais pour la VoIP
        
        # Pénalités Système
        if ssh_data.get('cpu_usage', 0) > 90: score -= 20
        if ssh_data.get('ram_usage', 0) > 90: score -= 20
        
        # Pénalités Logs
        if anomalies: score -= (len(anomalies) * 10)

    score = max(0, min(100, score))

    try:
        stat = StatReseau.objects.create(
            equipement=equipement,
            date_releve=timezone.now(),
            disponible=is_up,
            
            # --- Vos champs remplis par network_utils ---
            ping_ms=ping_ms,
            jitter_ms=jitter_ms,
            packet_loss=final_loss,
            
            # --- Le reste des données ---
            cpu_usage=ssh_data.get('cpu_usage'),
            cpu_load_1m=ssh_data.get('cpu_load_1m'),
            cpu_load_5m=ssh_data.get('cpu_load_5m'),
            ram_usage=ssh_data.get('ram_usage'),
            ram_total_mb=ssh_data.get('ram_total_mb'),
            ram_used_mb=ssh_data.get('ram_used_mb'),
            disk_usage=ssh_data.get('disk_usage'),
            inode_usage=ssh_data.get('inode_usage'),
            disk_read_mb=ssh_data.get('disk_read_mb'),
            disk_write_mb=ssh_data.get('disk_write_mb'),
            bandwidth_in_mbps=ssh_data.get('bandwidth_in_mbps'),
            bandwidth_out_mbps=ssh_data.get('bandwidth_out_mbps'),
            errors_in=ssh_data.get('errors_in'),
            errors_out=ssh_data.get('errors_out'),
            drops_in=ssh_data.get('drops_in'),
            drops_out=ssh_data.get('drops_out'),
            temperature_c=snmp_data.get('temperature_c'),
            fan_status=snmp_data.get('fan_status'),
            power_supply_status=snmp_data.get('power_supply_status'),
            
            # Gestion des anomalies (texte)
            anomalies="\n".join(anomalies) if anomalies else None,
            
            health_score=score,
            alerte_envoyee=bool(anomalies)
        )
        
        # Mise à jour Equipement
        envoyer_alerte_health(stat)
        equipement.statut = 'en ligne' if is_up else 'hors ligne'
        equipement.derniere_verification = timezone.now()
        equipement.save()

        logger.info(f"[COLLECTE] SUCCESS {ip} | Ping:{ping_ms}ms | Jitter:{jitter_ms}ms | Score:{score}")
        return stat

    except Exception as e:
        logger.error(f"[COLLECTE] Erreur DB: {e}")
        return None