import logging
import time
from monitoring.ssh_utils import get_ssh_client, exec_command_safe

logger = logging.getLogger("monitoring.remediation")


# ===============================
# 🧠 Base de connaissances
# ===============================
REMEDIATIONS = {
    # ===============================
    # 🔥 CPU / LOAD
    # ===============================
    "CPU élevé": {
        "linux": {
            "soft": ["ps aux --sort=-%cpu | head", "pkill -f 'stress|yes' || true"],
            "hard": ["systemctl restart ssh || true", "systemctl restart cron || true"],
        },
        "windows": {
            "soft": ["Get-Process | Sort-Object CPU -Descending | Select-Object -First 5", "Get-Process | Where-Object { $_.CPU -gt 50 } | Stop-Process -Force -ErrorAction SilentlyContinue"],
            "hard": ["Restart-Service -Name 'LanmanServer' -Force", "Restart-Service -Name 'Schedule'"],
        }
    },

    "Load excessif": {
        "linux": {
            "soft": ["uptime", "ps aux --sort=-%cpu | head"],
            "hard": ["systemctl restart systemd-logind || true"],
        },
        "windows": {
            "soft": ["Get-CimInstance Win32_Processor | Select-Object LoadPercentage"],
            "hard": ["Restart-Service -Name 'W32Time'"],
        }
    },

    # ===============================
    # 💾 RAM / OOM
    # ===============================
    "RAM saturée": {
        "linux": {
            "soft": ["sync", "echo 3 > /proc/sys/vm/drop_caches"],
            "hard": ["systemctl restart systemd-journald || true", "ps -eo pid,ppid,%mem,comm --sort=-%mem | head -n 5"],
        },
        "windows": {
            "soft": ["Clear-Variable -Name * -ErrorAction SilentlyContinue", "[System.GC]::Collect()", "Clear-DnsClientCache"],
            "hard": ["Restart-Service -Name 'SysMain' -Force", "Get-Process | Where-Object { $_.PrivateMemorySize64 -gt 500MB -and $_.ProcessName -notmatch 'System|Idle|svchost|explorer' } | Stop-Process -Force -ErrorAction SilentlyContinue"],
        }
    },

    "OOM killer": {
        "linux": {
            "soft": ["dmesg | tail -n 50"],
            "hard": ["systemctl restart docker || true"],
        },
        "windows": {
            "soft": ["Get-EventLog -LogName System -EntryType Error -Newest 20"],
            "hard": ["Restart-Service -Name 'Docker' -ErrorAction SilentlyContinue"],
        }
    },

    # ===============================
    # 💽 DISQUE
    # ===============================
    "Disque plein": {
        "linux": {
            "soft": ["journalctl --vacuum-time=3d", "rm -rf /tmp/*"],
            "hard": ["apt autoremove -y || true", "apt clean || true"],
        },
        "windows": {
            "soft": ["Clear-RecycleBin -Confirm:$false -ErrorAction SilentlyContinue", "Remove-Item -Path 'C:\\Windows\\Temp\\*' -Recurse -Force -ErrorAction SilentlyContinue"],
            "hard": ["dism /online /cleanup-image /startcomponentcleanup"],
        }
    },

    "Inodes saturés": {
        "linux": {
            "soft": ["find /var/log -type f -delete"],
            "hard": ["rm -rf /var/tmp/*"],
        },
        "windows": {
            "soft": ["Remove-Item -Path \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue"],
            "hard": ["Get-ChildItem -Path 'C:\\Windows\\Logs' -Recurse | Remove-Item -Force -ErrorAction SilentlyContinue"],
        }
    },

    "Filesystem read-only": {
        "linux": {
            "hard": ["mount -o remount,rw / || true"],
        },
        "windows": {
            "hard": ["Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\StorageDevicePolicies' -Name WriteProtect -Value 0 -ErrorAction SilentlyContinue"],
        }
    },

    # ===============================
    # 🌐 RÉSEAU
    # ===============================
    "Interface down": {
        "linux": {
            "soft": ["ip link set eth0 up || true"],
            "hard": ["systemctl restart NetworkManager || true"],
        },
        "windows": {
            "soft": ["Get-NetAdapter | Where-Object { $_.Status -ne 'Up' } | Enable-NetAdapter -Confirm:$false"],
            "hard": ["Restart-Service -Name 'Netman'"],
        }
    },

    "Erreurs CRC": {
        "linux": {
            "soft": ["ethtool -k eth0"],
            "hard": ["ethtool -K eth0 rx off tx off || true", "sleep 1", "ethtool -K eth0 rx on tx on || true"],
        },
        "windows": {
            "soft": ["Get-NetAdapterStatistics"],
            "hard": ["Disable-NetAdapter -Name '*' -Confirm:$false", "Enable-NetAdapter -Name '*' -Confirm:$false"],
        }
    },

    "Pertes de paquets": {
        "linux": {
            "soft": ["tc qdisc show dev eth0"],
            "hard": ["tc qdisc del dev eth0 root || true", "tc qdisc add dev eth0 root fq"],
        },
        "windows": {
            "soft": ["Test-NetConnection -ComputerName 8.8.8.8"],
            "hard": ["Restart-Service -Name 'nlasvc'"], # Network Location Awareness
        }
    },

    # ===============================
    # 🔐 SERVICES
    # ===============================
    "SSH indisponible": {
        "linux": {
            "hard": ["systemctl restart ssh || true"],
        },
        "windows": {
            "hard": ["Restart-Service -Name 'ssh-agent', 'sshd' -ErrorAction SilentlyContinue"],
        }
    },

    "Service HTTP down": {
        "linux": {
            "hard": ["systemctl restart nginx || systemctl restart apache2 || true"],
        },
        "windows": {
            "hard": ["Restart-Service -Name 'W3SVC' -ErrorAction SilentlyContinue"], # IIS
        }
    },

    "Docker bloqué": {
        "linux": {
            "hard": ["systemctl restart docker || true"],
        },
        "windows": {
            "hard": ["Restart-Service -Name 'Docker' -ErrorAction SilentlyContinue"],
        }
    },

    # ===============================
    # 🌡️ MATÉRIEL
    # ===============================
    "Surchauffe": {
        "linux": {
            "soft": ["sensors"],
            "hard": ["systemctl restart thermald || true"],
        },
        "windows": {
            "soft": ["Get-CimInstance -Namespace root/wmi -ClassName MsAcpi_ThermalZoneTemperature"],
            "hard": ["Set-CimInstance -Query 'Select * from Win32_Processor' -Property @{PowerManagementStatus=0} -ErrorAction SilentlyContinue"],
        }
    },

    # ===============================
    # 🆕 NOUVELLES ANOMALIES (LINUX)
    # ===============================
    "MySQL down": {
        "linux": { "hard": ["systemctl restart mysql || systemctl restart mariadb"] }
    },
    "PostgreSQL down": {
        "linux": { "hard": ["systemctl restart postgresql"] }
    },
    "Processus Zombies": {
        "linux": { "soft": ["ps -ef | grep 'defunct'"], "hard": ["kill -9 $(ps -ef | grep 'defunct' | awk '{print $3}') || true"] }
    },
    "Saturation Swap": {
        "linux": { "soft": ["swapoff -a", "swapon -a"] }
    },
    "Échec DNS": {
        "linux": { "hard": ["systemctl restart systemd-resolved || systemctl restart nscd || true"] },
        "windows": { "hard": ["Clear-DnsClientCache", "Restart-Service -Name 'Dnscache'"] }
    },
    "Verrou APT bloqué": {
        "linux": { "hard": ["rm /var/lib/dpkg/lock* || true", "dpkg --configure -a"] }
    },
    "Décalage horaire": {
        "linux": { "hard": ["ntpdate pool.ntp.org || chronyc sources -v || true"] },
        "windows": { "hard": ["w32tm /resync"] }
    },
    "Trop de sessions SSH": {
        "linux": { "soft": ["who"], "hard": ["pkill -u $(who | awk '{print $1}' | sort | uniq -c | awk '$1 > 10 {print $2}') || true"] }
    },
    "Brute force SSH": {
        "linux": { "hard": ["systemctl restart fail2ban || iptables -F || true"] }
    },
    "Entropie faible": {
        "linux": { "hard": ["systemctl restart haveged || apt install -y haveged && systemctl start haveged"] }
    },

    # ===============================
    # 🆕 NOUVELLES ANOMALIES (WINDOWS)
    # ===============================
    "Spooler down": {
        "windows": { "hard": ["Restart-Service -Name 'Spooler' -Force"] }
    },
    "Pare-feu désactivé": {
        "windows": { "hard": ["Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True"] }
    },
    "Antivirus désactivé": {
        "windows": { "hard": ["Set-Service -Name 'WinDefend' -StartupType Automatic", "Start-Service -Name 'WinDefend' -ErrorAction SilentlyContinue", "Set-MpPreference -DisableRealtimeMonitoring 0 -DisableIOAVProtection 0 -ErrorAction SilentlyContinue"] }
    },
    "WinRM down": {
        "windows": { "hard": ["winrm quickconfig -quiet", "Restart-Service -Name 'WinRM'"] }
    },
    "Corbeille volumineuse": {
        "windows": { "soft": [r"Clear-RecycleBin -DriveLetter C -Force -Confirm:$false -ErrorAction SilentlyContinue"] }
    },
    "Redémarrage en attente": {
        "windows": { "soft": ["Write-Host 'Redémarrage requis détecté'"] }
    },
    "Brute force RDP": {
        "windows": { "hard": ["Restart-Service -Name 'TermService' -Force"] }
    },
    "File d'attente disque": {
        "windows": { "soft": ["Get-Counter '\\PhysicalDisk(_Total)\\Current Disk Queue Length'"] }
    },
    "Windows Update down": {
        "windows": { "hard": ["Restart-Service -Name 'wuauserv'"] }
    },
    "Bureau à distance down": {
        "windows": { "hard": ["Set-ItemProperty -Path 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' -Name 'fDenyTSConnections' -Value 0", "Restart-Service -Name 'TermService' -Force"] }
    },
    
    # ===============================
    # 🆕 NOUVELLES ANOMALIES (PHASE 14)
    # ===============================
    "Connexions réseau saturées": {
        "linux": { "soft": ["sysctl -w net.ipv4.tcp_tw_reuse=1"], "hard": ["systemctl restart nginx || true", "systemctl restart apache2 || true"] }
    },
    "Dossier temporaire saturé (Linux)": {
        "linux": { "soft": ["find /tmp -type f -atime +1 -delete"], "hard": ["rm -rf /tmp/* || true"] }
    },
    "Serveur Web Local en erreur": {
        "linux": { "hard": ["systemctl restart nginx || systemctl restart apache2 || true"] }
    },
    "Épuisement File Handlers": {
        "linux": { "soft": ["sysctl -w fs.file-max=100000"] }
    },
    "Anomalie Processus (Load)": {
        "linux": { 
            "soft": ["ps -eo pid,pcpu,pmem,args --sort=-pcpu | head -n 10"],
            "hard": ["ps -eo pid,%cpu,comm --sort=-%cpu | awk '$2 > 80 {print $1}' | xargs kill -9 || true"]
        }
    },
    "Service de Temps arrêté": {
        "windows": { "hard": ["Set-Service -Name 'W32Time' -StartupType Automatic", "Restart-Service -Name 'W32Time' -Force", "w32tm /config /reliable:YES /update", "Start-Sleep -Seconds 2", "w32tm /resync /force"] }
    },
    "Dossier temporaire saturé (Windows)": {
        "windows": { "soft": ["Remove-Item -Path 'C:\\Windows\\Temp\\*' -Recurse -Force -ErrorAction SilentlyContinue"] }
    },
    "Journal des événements arrêté": {
        "windows": { "hard": ["Restart-Service -Name 'EventLog' -Force"] }
    },
    "Fuite de Handles (Windows)": { 
        "windows": { 
            "soft": ["Get-Process | Sort-Object Handles -Descending | Select-Object -First 5"],
            "hard": ["Get-Process | Where-Object { $_.Handles -gt 8000 -and $_.ProcessName -notmatch 'System|Idle|lsass|csrss|wininit|services' } | Stop-Process -Force -ErrorAction SilentlyContinue"]
        }
    },
    "Erreurs RDP fréquentes": {
        "windows": { "hard": ["Restart-Service -Name 'TermService' -Force"] }
    },
    
    # ===============================
    # 🆕 NOUVELLES REMÉDIATIONS (PHASE 15 - 30 Règles)
    # ===============================
    # --- LINUX ---
    "Inodes critiques": {
        "linux": { "soft": ["find /var/tmp -type f -mtime +2 -delete"], "hard": ["find /var/log -type f -name '*.gz' -delete"] }
    },
    "Incident OOM (Dmesg)": {
        "linux": { "hard": ["echo 1 > /proc/sys/vm/drop_caches || true"] }
    },
    "Mémoire partagée saturée": {
        "linux": { "hard": ["find /dev/shm -type f -mmin +60 -delete || true"] }
    },
    "Attaque Bruteforce SSH détectée": {
        "linux": { "hard": ["systemctl restart fail2ban || systemctl restart ssh || true"] }
    },
    "Désynchronisation NTP": {
        "linux": { "hard": ["systemctl restart systemd-timesyncd || ntpdate pool.ntp.org || true", "hwclock --systohc || true"] }
    },
    "Service Cron arrêté": {
        "linux": { "hard": ["systemctl restart cron || systemctl restart crond || true"] }
    },
    "Espace Root critique": {
        "linux": { "soft": ["apt-get clean || true"], "hard": ["journalctl --vacuum-time=1d || true"] }
    },
    "Limite fichiers ouverts": {
        "linux": { "soft": ["sysctl -w fs.file-max=200000 || true"] }
    },
    "Dépôts inaccessibles": {
        "linux": { "soft": ["apt-get update --fix-missing || true"] }
    },
    "Accès Root SSH autorisé": {
        "linux": { "hard": ["sed -i 's/^PermitRootLogin yes/PermitRootLogin no/g' /etc/ssh/sshd_config || true", "systemctl reload ssh || true"] }
    },

    # --- WINDOWS ---
    "Service DHCP down": {
        "windows": { "hard": ["Restart-Service -Name 'Dhcp' -Force -ErrorAction SilentlyContinue"] }
    },
    "Service DNS down": {
        "windows": { "hard": ["Restart-Service -Name 'Dnscache' -Force -ErrorAction SilentlyContinue"] }
    },
    "Antivirus arrêté": {
        "windows": { "hard": ["Start-Service -Name 'WinDefend' -ErrorAction SilentlyContinue", "Set-Service -Name 'WinDefend' -StartupType Automatic"] }
    },
    "Journal d'événements down": {
        "windows": { "hard": ["Restart-Service -Name 'EventLog' -Force -ErrorAction SilentlyContinue"] }
    },
    "Planificateur de tâches down": {
        "windows": { "hard": ["Restart-Service -Name 'Schedule' -Force -ErrorAction SilentlyContinue"] }
    },
    "Fuite Mémoire Paginée": {
        "windows": { "soft": ["Clear-Content -Path 'C:\\Windows\\Temp\\*' -ErrorAction SilentlyContinue"] }
    },
    "Espace disque C: critique": {
        "windows": { "soft": ["Clear-RecycleBin -Force -Confirm:$false -ErrorAction SilentlyContinue"], "hard": ["dism.exe /online /Cleanup-Image /StartComponentCleanup"] }
    },
    "File d'attente CPU élevée": {
        "windows": { "soft": ["Get-Process | Sort-Object CPU -Descending | Select-Object -First 3"] }
    },
    "Connexions TCP Windows saturées": {
        "windows": { "hard": ["Restart-Service -Name 'W3SVC' -ErrorAction SilentlyContinue", "Restart-Service -Name 'Tcpip' -ErrorAction SilentlyContinue"] }
    },
    "Sessions RDP Fantômes": {
        "windows": { "hard": ["quser | Select-String 'Disc' | ForEach-Object { logoff $($_.ToString() -split ' +')[2] }"] }
    },

    # --- RÉSEAU ---
    "CPU Équipement Réseau saturé": {
        "linux": { "soft": ["echo 'Alerte CPU Switch/Routeur'"] } # Pas de SSH sysadmin standard sur Switch
    },
    "Instabilité Interface (Flapping)": {
        "linux": { "soft": ["echo 'Flapping detecte'"] }
    },
    "Changement de topologie (STP)": {
        "linux": { "soft": ["echo 'STP Event detecte'"] }
    },
    "Session BGP inactive": {
        "linux": { "soft": ["echo 'BGP Down'"] }
    },
    "Voisin OSPF inactif": {
        "linux": { "soft": ["echo 'OSPF Down'"] }
    },
    "Incompatibilité Duplex": {
        "linux": { "soft": ["echo 'Duplex Mismatch'"] }
    },
    "Spoofing d'adresse MAC (Flapping)": {
        "linux": { "soft": ["echo 'MAC Flapping'"] }
    },
    "RAM Équipement Réseau saturée": {
        "linux": { "soft": ["echo 'Alerte RAM Switch/Routeur'"] }
    },
    "Attaque Pare-feu (Logs)": {
        "linux": { "soft": ["echo 'Alerte Securite Pare-feu'"] }
    },
}


# ===============================
# 🚑 REMÉDIATION PRINCIPALE
# ===============================
def appliquer_remediation(equipement, incident, niveau_max="hard"):
    """
    Applique une remédiation progressive et adaptée à l'OS.
    Retourne True si AU MOINS une action a été tentée avec succès.
    """
    from monitoring.ssh_utils import get_os_type

    plan_global = REMEDIATIONS.get(incident.titre)
    if not plan_global:
        # Check dynamic rules
        from remediation.models import AnomalieRegle
        regle_dyn = AnomalieRegle.objects.filter(nom=incident.titre).first()
        if regle_dyn:
            logger.info(f"[REMEDIATION] Déclenchement de la règle dynamique: {regle_dyn.nom}")
            try:
                ssh = get_ssh_client(equipement)
                cmds = regle_dyn.get_remediation_commands()
                action_executee = False
                for cmd in cmds:
                    logger.warning(f"[REMEDIATION:DYNAMIQUE] {equipement.nom} → {cmd}")
                    # Basic OS fallback logic if rule is 'all'
                    is_win = regle_dyn.os_cible == "windows" or equipement.type_equipement in ["pc_win", "serveur_win"]
                    if is_win:
                        full_cmd = f"powershell -Command \"{cmd}\""
                    else:
                        full_cmd = f"sudo sh -c \"{cmd}\""
                    exec_command_safe(ssh, full_cmd)
                    action_executee = True
                    time.sleep(1)
                ssh.close()
                return action_executee
            except Exception as e:
                logger.error(f"[REMEDIATION ÉCHEC DYNAMIQUE] {equipement.nom} ({incident.titre}) : {e}", exc_info=True)
                return False
        else:
            logger.info(f"[REMEDIATION] Aucun plan pour {incident.titre}")
            return False

    try:
        ssh = get_ssh_client(equipement)
        os_type = get_os_type(ssh) # Detect once
        
        # On récupère le plan spécifique à l'OS ou on sort
        plan = plan_global.get(os_type)
        if not plan:
            logger.warning(f"[REMEDIATION] Plan {incident.titre} non défini pour {os_type}")
            ssh.close()
            return False

        action_executee = False
        tentative_reussie = False

        for niveau in ["soft", "hard"]:
            if niveau not in plan:
                continue

            if niveau == "hard" and niveau_max != "hard":
                break

            for cmd in plan[niveau]:
                logger.warning(f"[REMEDIATION:{niveau.upper()}] {equipement.nom} ({os_type}) → {cmd}")
                
                if os_type == "windows":
                    # Commande PowerShell directe
                    full_cmd = f"powershell -Command \"{cmd}\""
                else:
                    # Commande Linux avec sudo
                    full_cmd = f"sudo sh -c \"{cmd}\""
                    
                out, err = exec_command_safe(ssh, full_cmd)

                # Si pas d'erreur majeure dans 'err', on considère que c'est une action tentée
                # (Certains outils écrivent des warnings dans stderr, donc on est prudent)
                action_executee = True
                time.sleep(1)

        ssh.close()
        return action_executee

    except Exception as e:
        logger.error(
            f"[REMEDIATION ÉCHEC] {equipement.nom} ({incident.titre}) : {e}",
            exc_info=True
        )
        return False