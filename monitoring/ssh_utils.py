import paramiko
import logging
import time
import socket
from django.utils import timezone

logger = logging.getLogger("monitoring.ssh")

def get_ssh_client(equipement):
    """Crée une connexion SSH robuste (Compatible Windows/Linux)"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ip = str(equipement.adresse_ip).strip()
    user = str(equipement.utilisateur_ssh or equipement.utilisateur or 'root').strip()
    port = int(equipement.port_ssh or 22)
    timeout = 10
    
    try:
        password = equipement.mot_de_passe_ssh
        if not password:
            raise ValueError("Mot_de_passe_vide")
    except Exception as e:
        if str(e) == "Mot_de_passe_vide":
            logger.warning(f"[SSH] Hote ignore ({ip}) : Aucun mot de passe configure.")
        else:
            logger.error(f"[SSH] Erreur dechiffrement pour {ip}: {e}")
        raise PermissionError("Mot de passe invalide ou non renseigne")
    try:
        logging.getLogger("paramiko").setLevel(logging.WARNING)
        client.connect(
            hostname=ip, port=port, username=user, password=str(password),
            timeout=timeout, auth_timeout=timeout, banner_timeout=timeout,
            look_for_keys=False, allow_agent=False
        )
        return client
    except Exception as e:
        logger.error(f"[SSH] Echec connexion {ip}: {e}")
        raise

import re

def exec_cmd(client, cmd):
    """Exécute et nettoie le résultat des codes ANSI"""
    try:
        _, stdout, _ = client.exec_command(cmd, timeout=10)
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        # Nettoyage ANSI
        ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
        out = ansi_escape.sub('', out)
        # Supprime caractères de contrôle
        out = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', out)
        return out.strip()
    except:
        return ""

def get_os_type(client):
    """Detects if the remote OS is Windows or Linux"""
    out = exec_cmd(client, "uname")
    if "Linux" in out or "Darwin" in out:
        return "linux"
    
    out_win = exec_cmd(client, "cmd.exe /c ver")
    if "Windows" in out_win:
        return "windows"
        
    return "unknown"

def collecter_performance_windows_ssh(client, equipement, metrics):
    """Collecte les métriques de performance sur Windows via PowerShell"""
    try:
        out_cpu = exec_cmd(client, 'powershell -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"')
        if out_cpu and out_cpu.isdigit():
            metrics['cpu_usage'] = float(out_cpu)
            metrics['cpu_load_1m'] = float(out_cpu) / 100.0

        out_ram = exec_cmd(client, 'powershell -Command "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory | ConvertTo-Json"')
        import json
        if out_ram and "{" in out_ram:
            try:
                ram_data = json.loads(out_ram)
                total_kb = float(ram_data.get("TotalVisibleMemorySize", 0))
                free_kb = float(ram_data.get("FreePhysicalMemory", 0))
                if total_kb > 0:
                    used_kb = total_kb - free_kb
                    metrics['ram_total_mb'] = total_kb / 1024
                    metrics['ram_used_mb'] = used_kb / 1024
                    metrics['ram_usage'] = round((used_kb / total_kb) * 100, 1)
            except Exception as e:
                logger.error(f"[SSH Windows] Erreur lecture RAM: {e}")

        cmd_disk = "powershell -Command \"Get-CimInstance Win32_LogicalDisk -Filter 'DeviceID=''C:''' | Select-Object Size, FreeSpace | ConvertTo-Json\""
        out_disk = exec_cmd(client, cmd_disk)
        if out_disk and "{" in out_disk:
            try:
                disk_data = json.loads(out_disk)
                total_b = float(disk_data.get("Size", 0))
                free_b = float(disk_data.get("FreeSpace", 0))
                if total_b > 0:
                    used_b = total_b - free_b
                    metrics['disk_usage'] = round((used_b / total_b) * 100, 1)
            except Exception as e:
                logger.error(f"[SSH Windows] Erreur lecture Disque: {e}")

        # ✅ NOUVEAU : Lecture/Écriture Disque (I/O)
        out_disk_io = exec_cmd(client, 'powershell -Command "$read = (Get-Counter \'\\PhysicalDisk(_Total)\\Disk Read Bytes/sec\' -ErrorAction SilentlyContinue).CounterSamples.CookedValue; $write = (Get-Counter \'\\PhysicalDisk(_Total)\\Disk Write Bytes/sec\' -ErrorAction SilentlyContinue).CounterSamples.CookedValue; @{read=$read; write=$write} | ConvertTo-Json"')
        if out_disk_io and "{" in out_disk_io:
            try:
                io_data = json.loads(out_disk_io)
                metrics['disk_read_mb'] = round(float(io_data.get("read", 0)) / (1024 * 1024), 2)
                metrics['disk_write_mb'] = round(float(io_data.get("write", 0)) / (1024 * 1024), 2)
            except:
                pass

        # ✅ NOUVEAU : Réseau (Bande passante, Drops, Erreurs)
        out_net = exec_cmd(client, 'powershell -Command "$stats = Get-NetAdapterStatistics | Where-Object {$_.ReceivedBytes -gt 0} | Select-Object ReceivedBytes, SentBytes, ReceivedDiscardedPackets, OutboundDiscardedPackets, ReceivedPacketErrors, OutboundPacketErrors | Measure-Object -Property ReceivedBytes, SentBytes, ReceivedDiscardedPackets, OutboundDiscardedPackets, ReceivedPacketErrors, OutboundPacketErrors -Sum; $res = @{}; foreach($prop in $stats) { $res[$prop.Property] = $prop.Sum }; $res | ConvertTo-Json"')
        if out_net and "{" in out_net:
            try:
                net_data = json.loads(out_net)
                rx_bytes = float(net_data.get("ReceivedBytes", 0))
                tx_bytes = float(net_data.get("SentBytes", 0))
                # Simple approximation (ce sont des compteurs globaux cumulés, pour des stats "live" mbps il faudrait 2 mesures)
                metrics['bandwidth_in_mbps'] = round((rx_bytes * 8) / 1000000, 2)
                metrics['bandwidth_out_mbps'] = round((tx_bytes * 8) / 1000000, 2)
                
                metrics['drops_in'] = int(net_data.get("ReceivedDiscardedPackets", 0))
                metrics['drops_out'] = int(net_data.get("OutboundDiscardedPackets", 0))
                metrics['errors_in'] = int(net_data.get("ReceivedPacketErrors", 0))
                metrics['errors_out'] = int(net_data.get("OutboundPacketErrors", 0))
            except Exception as e:
                logger.error(f"[SSH Windows] Erreur lecture Réseau: {e}")

        out_uptime = exec_cmd(client, 'powershell -Command "(New-TimeSpan -Start (Get-CimInstance Win32_OperatingSystem).LastBootUpTime -End (Get-Date)).TotalSeconds"')
        if out_uptime:
            try:
                metrics['uptime_seconds'] = int(float(out_uptime.replace(',', '.')))
            except:
                pass

        equipement.statut = 'en ligne'
        equipement.derniere_verification = timezone.now()
        equipement.cpu_usage = metrics['cpu_usage']
        equipement.ram_usage = metrics['ram_usage']
        equipement.save()
        
        logger.info(f"[SSH Windows] Succes {equipement.adresse_ip}")
        return metrics

    except Exception as e:
        logger.error(f"[SSH Windows] Echec {equipement.adresse_ip}: {e}")
        return metrics

def collecter_performance_linux_ssh(client, equipement, metrics):
    """Collecte TOUTES les métriques Linux pour StatReseau"""
    try:
        out = exec_cmd(client, "cat /proc/loadavg")
        if out:
            parts = out.split()
            metrics['cpu_load_1m'] = float(parts[0])
            metrics['cpu_load_5m'] = float(parts[1])
            
        out = exec_cmd(client, "grep 'cpu ' /proc/stat")
        if out:
            metrics['cpu_usage'] = metrics.get('cpu_load_1m', 0) * 10
            
        out = exec_cmd(client, "free -m")
        if out:
            for line in out.splitlines():
                if "Mem:" in line:
                    p = line.split()
                    total, used = int(p[1]), int(p[2])
                    metrics['ram_total_mb'] = total
                    metrics['ram_used_mb'] = used
                    metrics['ram_usage'] = round((used/total)*100, 1)

        out = exec_cmd(client, "df -P / | tail -1")
        if out:
            p = out.split()
            for x in p:
                if "%" in x: metrics['disk_usage'] = float(x.replace("%",""))
        
        out = exec_cmd(client, "df -Pi / | tail -1")
        if out:
            p = out.split()
            for x in p:
                if "%" in x: metrics['inode_usage'] = float(x.replace("%",""))

        cmd_disk = "cat /proc/diskstats | grep -E 'sd|vd|nvme' | head -1"
        cmd_net = "cat /proc/net/dev | grep -v Lo | sort -k2 -nr | head -1"
        
        t1 = time.time()
        d1_io = exec_cmd(client, cmd_disk).split()
        d1_net = exec_cmd(client, cmd_net).replace(":", " ").split()
        
        time.sleep(2)
        
        t2 = time.time()
        d2_io = exec_cmd(client, cmd_disk).split()
        d2_net = exec_cmd(client, cmd_net).replace(":", " ").split()
        
        delta_t = t2 - t1
        
        if d1_io and d2_io and len(d1_io)>10 and len(d2_io)>10:
            r1, w1 = int(d1_io[5]), int(d1_io[9])
            r2, w2 = int(d2_io[5]), int(d2_io[9])
            metrics['disk_read_mb'] = round(((r2-r1)*512/1048576)/delta_t, 2)
            metrics['disk_write_mb'] = round(((w2-w1)*512/1048576)/delta_t, 2)

        if d1_net and d2_net and len(d1_net)>10:
            rx1, tx1 = int(d1_net[1]), int(d1_net[9])
            rx2, tx2 = int(d2_net[1]), int(d2_net[9])
            
            metrics['bandwidth_in_mbps'] = round(((rx2-rx1)*8/1000000)/delta_t, 2)
            metrics['bandwidth_out_mbps'] = round(((tx2-tx1)*8/1000000)/delta_t, 2)
            
            metrics['errors_in'] = int(d2_net[3])
            metrics['drops_in'] = int(d2_net[4])
            metrics['errors_out'] = int(d2_net[11])
            metrics['drops_out'] = int(d2_net[12])

        out = exec_cmd(client, "cat /proc/uptime")
        if out: metrics['uptime_seconds'] = int(float(out.split()[0]))

        equipement.statut = 'en ligne'
        equipement.derniere_verification = timezone.now()
        equipement.cpu_usage = metrics['cpu_usage']
        equipement.ram_usage = metrics['ram_usage']
        equipement.save()
        
        logger.info(f"[SSH Linux] Succes {equipement.adresse_ip}")
        return metrics

    except Exception as e:
        logger.error(f"[SSH Linux] Echec global {equipement.adresse_ip}: {e}")
        return metrics

def collecter_performance_ssh(equipement):
    """Fonction principale de collecte de performance cross-platform"""
    metrics = {
        "cpu_usage": None, "cpu_load_1m": None, "cpu_load_5m": None,
        "ram_usage": None, "ram_total_mb": None, "ram_used_mb": None,
        "disk_usage": None, "inode_usage": None,
        "disk_read_mb": 0.0, "disk_write_mb": 0.0,
        "bandwidth_in_mbps": 0.0, "bandwidth_out_mbps": 0.0,
        "drops_in": 0, "drops_out": 0,
        "errors_in": 0, "errors_out": 0,
        "uptime_seconds": 0
    }
    
    client = None
    try:
        client = get_ssh_client(equipement)
        os_type = get_os_type(client)
        
        if os_type == "windows":
            return collecter_performance_windows_ssh(client, equipement, metrics)
        elif os_type == "linux":
            return collecter_performance_linux_ssh(client, equipement, metrics)
        else:
            logger.warning(f"[SSH] OS inconnu pour {equipement.adresse_ip}. Fallback sur Linux.")
            return collecter_performance_linux_ssh(client, equipement, metrics)

    except Exception as e:
        logger.error(f"[SSH] Echec connexion/collecte {equipement.adresse_ip}: {e}")
        return metrics
    finally:
        if client: client.close()

def ssh_connect(equipement):
    return get_ssh_client(equipement)


import time
import logging
import paramiko

logger = logging.getLogger("monitoring.ssh")

def exec_command_safe(client, command, sudo_password=None, timeout=20):
    """
    Exécute une commande SSH de manière robuste.
    Gère : Commandes simples, Sudo avec mot de passe, Timeouts.
    """
    if not client:
        return None, "Erreur : Client SSH non connecte"

    try:
        # On demande un PTY pour permettre l'interactivité (indispensable pour sudo)
        transport = client.get_transport()
        chan = transport.open_session()
        chan.get_pty()
        chan.settimeout(timeout)
        
        # Lancement de la commande
        chan.exec_command(command)

        # Gestion du mot de passe SUDO si nécessaire
        if sudo_password and "sudo" in command:
            # On attend un peu que le prompt 'Password:' apparaisse
            time.sleep(0.5)
            if chan.send_ready():
                chan.send(f"{sudo_password}\n")

        # Lecture des données par blocs (évite de saturer la RAM sur de gros outputs)
        stdout_data = []
        stderr_data = []
        
        start_time = time.time()
        while not chan.exit_status_ready():
            # Vérification du timeout global
            if (time.time() - start_time) > timeout:
                logger.warning(f"[SSH] Timeout atteint pour : {command[:30]}...")
                return None, "Timeout de commande"

            # Récupération des données disponibles
            if chan.recv_ready():
                stdout_data.append(chan.recv(4096).decode('utf-8', errors='ignore'))
            
            if chan.recv_stderr_ready():
                stderr_data.append(chan.recv_stderr(4096).decode('utf-8', errors='ignore'))
            
            time.sleep(0.1)

        # Récupération du reste après fermeture
        while chan.recv_ready():
            stdout_data.append(chan.recv(4096).decode('utf-8', errors='ignore'))

        output = "".join(stdout_data).strip()
        error = "".join(stderr_data).strip()
        exit_status = chan.recv_exit_status()

        # Nettoyage spécifique pour SUDO (retirer le prompt de mot de passe du résultat)
        if sudo_password:
            output = output.replace(sudo_password, "").strip()
            # On retire souvent la première ligne si c'est "[sudo] password for..."
            lines = output.splitlines()
            if lines and "password" in lines[0].lower():
                output = "\n".join(lines[1:]).strip()

        if exit_status != 0 and not output:
            return None, f"Erreur (Code {exit_status}): {error}"

        return output, None

    except Exception as e:
        logger.error(f"[SSH] Exception lors de l'execution : {e}")
        return None, str(e)
    
    
import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger("monitoring.alerts")

def envoyer_mail_thread(subject, text_content, html_content, recipient_list):
    """Fonction executee dans un thread separe"""
    msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, recipient_list)
    msg.attach_alternative(html_content, "text/html")
    try:
        msg.send()
    except Exception as e:
        logger.error(f"[ALERTE] Echec envoi email : {e}")

def notifier_anomalies(equipement, anomalies):
    """
    Gère la logique d'alerte avec anti-spam (1 mail max par heure par type d'erreur)
    """
    for anomalie in anomalies:
        # Clé unique pour l'anti-spam : Equipement + Type d'anomalie
        cache_key = f"alert_sent_{equipement.id}_{anomalie.replace(' ', '_')}"
        
        # Si la clé existe en cache, on ne fait rien (on a déjà prévenu récemment)
        if cache.get(cache_key):
            continue

        # Sinon, on marque comme envoyé pour les 60 prochaines minutes
        cache.set(cache_key, True, timeout=3600)

        # Préparation de l'email
        subject = f"⚠️ ALERTE : {anomalie} sur {equipement.nom}"
        context = {
            'equipement': equipement,
            'anomalie': anomalie,
            'date': equipement.derniere_verification,
        }
        
        # Rendu du template HTML
        html_content = render_to_string('monitoring/emails/alerte_anomalie.html', context)
        text_content = f"Alerte sur {equipement.nom} ({equipement.adresse_ip}) : {anomalie}"

        # LANCEMENT DU THREAD (Asynchrone)
        t = threading.Thread(
            target=envoyer_mail_thread,
            args=(subject, text_content, html_content, [settings.ADMIN_EMAIL])
        )
        t.start()
        
        logger.info(f"[ALERTE] Email envoye (Thread) pour {anomalie} sur {equipement.adresse_ip}")
        
        
        
import re
import logging
from .ssh_utils import get_ssh_client, exec_command_safe
# On va créer ce fichier

logger = logging.getLogger("monitoring.logs")

def collecter_logs_linux_ssh(ssh, equipement):
    anomalies_detectees = []
    # On lit un peu plus de lignes pour avoir du contexte
    cmd = "sudo tail -n 500 /var/log/syslog /var/log/auth.log 2>/dev/null"
    password = equipement.mot_de_passe_ssh
    
    out, err = exec_command_safe(ssh, cmd, sudo_password=password)

    if not out: return []

    # --- DICTIONNAIRE DE DÉTECTION AVANCÉE ---
    patterns = {
        # RÉSEAU
        r"link (down|is down)": "Coupure physique d'interface (Link Down)",
        r"spanning-tree|topology change": "STP : Changement de topologie (Boucle potentielle)",
        r"OSPF.*Neighbor Down": "Routage : Voisin OSPF perdu",
        r"BGP.*(Closed|Idle|Down)": "Routage : Session BGP interrompue",
        
        # INTRUSION & SÉCURITÉ (auth.log / syslog)
        r"Failed password for": "Sécurité : Tentative d'intrusion (Echec mot de passe)",
        r"Invalid user|user not found": "Sécurité : Tentative d'accès (Utilisateur inconnu)",
        r"Accepted password.*root": "Sécurité : Connexion ROOT réussie (Attention !)",
        
        # SYSTÈME & RESSOURCES
        r"Out of memory|OOM-killer": "Critique : Processus tué par manque de RAM (OOM)",
        r"Disk quota exceeded|No space left": "Critique : Disque saturé (Plus d'espace)",
        r"EXT4-fs error|I/O error": "Matériel : Erreur d'écriture sur le disque",
        r"segfault at": "Logiciel : Crash de processus (Segmentation fault)"
    }

    for pattern, label in patterns.items():
        if re.search(pattern, out, re.IGNORECASE | re.MULTILINE):
            anomalies_detectees.append(label)

    if anomalies_detectees:
        notifier_anomalies(equipement, list(set(anomalies_detectees)))

    return anomalies_detectees

def collecter_logs_windows_ssh(ssh, equipement):
    anomalies_detectees = []
    # PowerShell list event logs
    cmd = 'powershell -Command "Get-EventLog -LogName System,Application -EntryType Error -Newest 100 2>$null | Format-Table -HideTableHeaders Message | Out-String"'
    out, err = exec_command_safe(ssh, cmd)

    if not out: return []

    patterns = {
        r"Disk|disque.*plein|No space left": "Critique : Disque saturé (Plus d'espace)",
        r"Out of memory|mémoire insuffisante|Resource-Exhaustion": "Critique : Manque de RAM",
        r"crash|unexpectedly quit|faulting application": "Logiciel : Crash de processus",
        r"disk error|I/O error|erreur matérielle": "Matériel : Erreur d'écriture sur le disque"
    }

    for pattern, label in patterns.items():
        if re.search(pattern, out, re.IGNORECASE | re.MULTILINE):
            anomalies_detectees.append(label)

    if anomalies_detectees:
        notifier_anomalies(equipement, list(set(anomalies_detectees)))

    return anomalies_detectees

def collecter_logs_ssh(equipement):
    ssh = None
    try:
        ssh = get_ssh_client(equipement)
        os_type = get_os_type(ssh)

        if os_type == "windows":
            return collecter_logs_windows_ssh(ssh, equipement)
        else:
            return collecter_logs_linux_ssh(ssh, equipement)
            
    except Exception as e:
        logger.error(f"[LOGS] Erreur collecte sur {equipement.adresse_ip}: {e}")
        return []
    finally:
        if ssh: ssh.close()
