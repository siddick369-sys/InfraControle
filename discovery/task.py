# discovery/tasks.py
from celery import shared_task, current_app
from django.utils import timezone
import logging
import socket
import subprocess
import re
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import EquipementDecouvert
from .alerts import envoyer_alerte_thread

logger = logging.getLogger("discovery")


# ============================================================================
# UTILITAIRES RÉSEAU
# ============================================================================

def get_local_network():
    """Détecte le réseau local"""
    #try:
    #     import netifaces as ni
    #     gateways = ni.gateways()
    #     default_iface = gateways['default'][ni.AF_INET][1]
    #     addrs = ni.ifaddresses(default_iface)
    #     ip_info = addrs[ni.AF_INET][0]
    #     ip = ip_info['addr']
    #     netmask = ip_info['netmask']
    #     mask_bits = sum(bin(int(x)).count('1') for x in netmask.split('.'))
         #return f"{ip}/{mask_bits}"
    #except Exception as e:
#        logger.error(f"Erreur détection réseau: {e}")
 #   return None


def scan_arp(network_cidr):
    """Scan ARP avec arp-scan"""
    try:
        result = subprocess.run(
            ['arp-scan', '-l', '-I', 'eth0', network_cidr],
            capture_output=True, text=True, timeout=30
        )
        devices = []
        for line in result.stdout.split('\n'):
            match = re.match(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f:]{17})', line, re.I)
            if match:
                devices.append({
                    'ip': match.group(1),
                    'mac': match.group(2).upper(),
                    'vendor': 'Inconnu'
                })
        return devices
    except Exception as e:
        logger.warning(f"arp-scan échoué: {e}, fallback sur ping")
        return None


def ping_sweep(network_cidr, max_workers=50):
    """Fallback ping sweep"""
    base = '.'.join(network_cidr.split('.')[:3])
    ips = [f"{base}.{i}" for i in range(1, 255)]
    
    def ping_host(ip):
        try:
            system = platform.system().lower()
            count = "-n" if system == "windows" else "-c"
            wait = "-w" if system == "windows" else "-W"
            result = subprocess.run(
                ["ping", count, "1", wait, "500", ip],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
            return ip if result.returncode == 0 else None
        except:
            return None
    
    active = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(ping_host, ip) for ip in ips]
        for future in as_completed(futures):
            result = future.result()
            if result:
                active.append({'ip': result, 'mac': 'N/A', 'vendor': 'N/A'})
    return active


# ============================================================================
# RÉSOLUTION HOSTNAME
# ============================================================================

def resolve_hostname(ip, mac=None):
    """Résolution multi-méthodes"""
    # 1. SNMP (priorité pour équipements réseau)
    snmp = snmp_get_sysname(ip)
    if snmp:
        return snmp
    
    # 2. mDNS/Avahi
    mdns = mdns_lookup(ip)
    if mdns:
        return mdns
    
    # 3. DNS Inverse
    dns = dns_reverse(ip)
    if dns:
        return dns
    
    # 4. NetBIOS
    netbios = netbios_lookup(ip)
    if netbios:
        return netbios
    
    # 5. Inférence MAC
    if mac:
        return infer_from_mac(mac)
    
    return ""


def snmp_get_sysname(ip, community='public'):
    """SNMP sysName pour équipements réseau"""
    try:
        result = subprocess.run(
            ['snmpget', '-v2c', '-c', community, '-t', '2', '-r', '0',
             ip, '1.3.6.1.2.1.1.5.0'],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            match = re.search(r'STRING:\s*"?([^"\n]+)"?', result.stdout)
            if match:
                return match.group(1).strip()
    except:
        pass
    return None


def mdns_lookup(ip):
    """mDNS pour VMs Linux et mobiles"""
    try:
        result = subprocess.run(
            ['avahi-resolve-address', ip],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            match = re.search(r'\s+(\S+)\.local', result.stdout)
            if match:
                return match.group(1)
    except:
        pass
    
    try:
        parts = ip.split('.')
        rev = '.'.join(reversed(parts))
        result = subprocess.run(
            ['dig', '+short', '+time=1', '@224.0.0.251', '-p', '5353',
             f'{rev}.in-addr.arpa.', 'PTR'],
            capture_output=True, text=True, timeout=2
        )
        if result.stdout.strip():
            return result.stdout.strip().split('.')[0]
    except:
        pass
    return None


def dns_reverse(ip):
    """DNS inverse"""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        if 'in-addr.arpa' not in hostname:
            return hostname
    except:
        pass
    return None


def netbios_lookup(ip):
    """NetBIOS pour Windows"""
    try:
        result = subprocess.run(
            ['nmblookup', '-A', ip],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.split('\n'):
            if '<00>' in line and 'GROUP' not in line:
                name = line.split()[0].strip()
                if name and name != 'No':
                    return name.lower()
    except:
        pass
    return None


def infer_from_mac(mac):
    """Inférence depuis MAC (OUI)"""
    oui = mac.upper().replace(':', '')[:6]
    vendors = {
        'B827EB': 'Raspberry Pi',
        'DCA632': 'Raspberry Pi',
        '080027': 'VirtualBox VM',
        '000C29': 'VMware VM',
        '005056': 'VMware VM',
        '001B11': 'Cisco',
        '0004F2': 'Polycom',
        '000CE7': 'Cisco',
        '00155D': 'Microsoft Hyper-V',
        '00163E': 'Xen VM',
        '001A11': 'Google',
        '001C7F': 'Dell',
        '00215A': 'Cisco',
        '00249B': 'Linksys',
        '002590': 'Supermicro',
        '0026B9': 'Dell',
        '0050B6': 'Cisco',
        '00E04C': 'Realtek',
        '107B44': 'Dell',
        '14FEB5': 'Cisco',
        '28CFE9': 'Apple',
        '3C0754': 'Apple',
        '44AD19': 'Apple',
        '64006A': 'Dell',
        '705A0F': 'Hewlett Packard',
        '74E543': 'Intel',
        '847BEB': 'Apple',
        'A45E60': 'Apple',
        'B4E62A': 'Apple',
        'B8AC6F': 'Apple',
        'C05627': 'Apple',
        'D022BE': 'Apple',
        'D067E5': 'Apple',
        'DC2B61': 'Apple',
        'E0F847': 'Apple',
        'F01898': 'Apple',
    }
    return vendors.get(oui, None)


# ============================================================================
# DÉTECTION TYPE ET OS
# ============================================================================

def detect_type_and_os(ip, hostname, mac):
    """Détection complète type + OS"""
    h = (hostname or "").lower()
    mac_u = (mac or "").upper()
    
    # Détection type
    type_score = {'serveur': 0, 'routeur': 0, 'switch': 0, 'wifi': 0, 'autre': 0}
    
    if any(k in h for k in ['router', 'gw', 'gateway']):
        type_score['routeur'] += 3
    if any(k in h for k in ['switch', 'sw']):
        type_score['switch'] += 3
    if any(k in h for k in ['ap', 'wifi']):
        type_score['wifi'] += 3
    if any(k in h for k in ['srv', 'server', 'nas']):
        type_score['serveur'] += 2
    
    for port in [22, 80, 443, 3389, 161, 445, 5900, 8080]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            if sock.connect_ex((ip, port)) == 0:
                if port in [22, 3389]:
                    type_score['serveur'] += 1
                if port == 3389:
                    type_score['serveur'] += 2 # Windows RDP
                if port in [80, 443]:
                    type_score['routeur'] += 1
                if port == 161:
                    type_score['switch'] += 2
                if port == 445:
                    type_score['serveur'] += 2 # SMB/Windows
            sock.close()
        except:
            pass
    
    dtype = max(type_score, key=type_score.get)
    if type_score[dtype] == 0:
        dtype = 'autre'
    
    # Détection OS
    os_type = 'inconnu'
    if any(x in h for x in ['ubuntu', 'debian', 'centos', 'linux']):
        os_type = 'Linux'
    elif any(x in h for x in ['windows', 'pc-', 'desktop', 'laptop']):
        os_type = 'Windows'
    elif any(x in mac_u for x in ['B827EB', 'DCA632']):
        os_type = 'Raspberry Pi'
    elif any(x in mac_u for x in ['080027', '000C29', '005056', '00155D']):
        os_type = 'Virtual VM'
    
    # Check port 445 for Windows
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        if sock.connect_ex((ip, 445)) == 0:
            os_type = 'Windows'
        sock.close()
    except:
        pass

    return dtype, os_type


def fingerprint_device(dev):
    """Analyse complète d'un appareil"""
    ip = dev['ip']
    mac = dev.get('mac', 'N/A')
    
    logger.info(f"Analyse de {ip}...")
    
    hostname = resolve_hostname(ip, mac)
    if hostname:
        logger.info(f"  Hostname: {hostname}")
    
    dtype, os_type = detect_type_and_os(ip, hostname, mac)
    
    return {
        'ip': ip,
        'mac': mac,
        'hostname': hostname or "inconnu",
        'type': dtype,
        'os': os_type,
        'vendor': dev.get('vendor', 'N/A')
    }


# ============================================================================
# SCANNER PRINCIPAL
# ============================================================================

def scanner_reseau_complet(network=None):
    """Scan réseau complet avec toutes les méthodes"""
    if not network:
        network = get_local_network()
        if not network:
            raise Exception("Réseau non détecté")
    
    logger.info(f"🚀 Scan de {network}")
    
    devices = scan_arp(network)
    if not devices:
        logger.info("Fallback ping sweep...")
        devices = ping_sweep(network)
    
    logger.info(f"{len(devices)} appareils trouvés")
    
    results = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fingerprint_device, d) for d in devices]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    results.sort(key=lambda x: int(x['ip'].rsplit('.', 1)[1]))
    return results


# ============================================================================
# TÂCHES CELERY
# ============================================================================

@shared_task(
    name="discovery.tasks.enregistrer_ip",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 10},
)
def enregistrer_ip(data):
    """
    Enregistre UN équipement découvert (appelé individuellement)
    ⚠️ L'envoi d'alerte est désactivé ici car géré en batch dans scanner_reseau_auto
    """
    ip = data.get("ip")
    if not ip:
        return "ip_manquante"

    # ✅ CORRECTION : mac_addresse (avec deux 'd') comme dans votre modèle
    equipement, created = EquipementDecouvert.objects.update_or_create(
        adresse_ip=ip,
        defaults={
            "hostname": data.get("hostname", ""),
            "type_detecte": data.get("type", "inconnu"),
            "mac_addresse": data.get("mac", ""),  # ← mac_addresse (deux d)
            "systeme_exploitation": data.get("os", "inconnu"),  # ← inconnu (valeur par défaut)
            "vu_le": timezone.now(),
        }
    )

    # 📝 On ne fait PAS l'alerte ici pour permettre le mode récapitulatif
    # L'alerte est gérée dans scanner_reseau_auto après collecte de tous les équipements
    
    return {
        "status": "ok",
        "ip": ip,
        "created": created,
        "hostname": equipement.hostname,
    }


@shared_task(
    name="discovery.tasks.scanner_reseau_auto",
    time_limit=120,
    soft_time_limit=90,
)
def scanner_reseau_auto(network=None):
    """
    🔍 Scan réseau complet avec alertes groupées (Email + Slack + Teams)
    """
    try:
        decouvertes = scanner_reseau_complet(network)
        
        # Phase 1 : Enregistrement en base et collecte des nouveaux
        equipements_a_alerter = []
        
        for d in decouvertes:
            payload = {
                "ip": str(d["ip"]),
                "hostname": str(d.get("hostname", "")),
                "type": str(d.get("type", "inconnu")),
                "mac": str(d.get("mac", "")),
                "os": str(d.get("os", "inconnu")),
            }

            # Enregistrement asynchrone (sans alerte individuelle)
            result = current_app.send_task(
                "discovery.tasks.enregistrer_ip",
                args=[payload]
            )
            
            # Vérification synchrone pour savoir si c'est un nouveau
            # (alternative : faire un get après, mais moins propre)
            # Solution : on vérifie ici avant l'envoi
            try:
                eq, created = EquipementDecouvert.objects.get_or_create(
                    adresse_ip=d['ip'],
                    defaults={
                        'hostname': d.get('hostname', ''),
                        'type_detecte': d.get('type', 'inconnu'),
                        'mac_addresse': d.get('mac', ''),  # ← deux d
                        'systeme_exploitation': d.get('os', 'inconnu'),
                        'vu_le': timezone.now(),
                    }
                )
                
                if created or not eq.email_envoye:
                    equipements_a_alerter.append(eq)
                    
            except Exception as e:
                logger.error(f"Erreur DB pour {d['ip']}: {e}")

        total = len(decouvertes)
        nouveaux = len(equipements_a_alerter)
        
        logger.info(f"[DISCOVERY] {total} détectés, {nouveaux} à alerter")

        # Phase 2 : Envoi des alertes groupées (SEUIL D'ALERTE)
        if equipements_a_alerter:
            # 🎯 Envoi avec gestion du seuil (récapitulatif si > 5)
            envoyer_alerte_thread(equipements_a_alerter)
            
            # Marquer comme notifiés
            for eq in equipements_a_alerter:
                eq.email_envoye = True
                eq.save(update_fields=['email_envoye'])

        return {
            "reseau_scane": True,
            "equipements_detectes": total,
            "nouveaux_alerte": nouveaux,
            "network": network or get_local_network(),
        }
        
    except Exception as e:
        logger.error(f"[DISCOVERY] Erreur scan: {e}")
        return {
            "reseau_scane": False,
            "erreur": str(e),
        }
        
        
