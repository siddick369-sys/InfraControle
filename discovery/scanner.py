# discovery/scanner.py
# ═══════════════════════════════════════════════════════════════════════════════
# InfraControl — Deep Discovery Scanner v2.0
# Scanner réseau professionnel avec fingerprinting OS, extraction MAC/Vendor,
# détection de services, et import automatique dans Django.
# ═══════════════════════════════════════════════════════════════════════════════

import re
import socket
import struct
import platform
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import IPv4Network, IPv4Address
from datetime import datetime
import os
import django

logger = logging.getLogger("infracontrol.discovery")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 : BASE DE DONNÉES OUI (MAC → Constructeur)
# ─────────────────────────────────────────────────────────────────────────────
# Les 3 premiers octets (OUI) identifient le fabricant.
# Dictionnaire extensible — ajouter vos propres entrées selon votre parc.

OUI_DATABASE = {
    # Cisco
    "00:1A:2F": "Cisco", "00:1B:54": "Cisco", "00:1C:58": "Cisco",
    "00:1E:49": "Cisco", "00:1E:F7": "Cisco", "00:22:55": "Cisco",
    "00:23:04": "Cisco", "00:23:BE": "Cisco", "00:24:C4": "Cisco",
    "00:25:45": "Cisco", "00:26:0B": "Cisco", "00:26:CB": "Cisco",
    "00:27:0D": "Cisco", "00:2A:6A": "Cisco", "00:30:F2": "Cisco",
    "00:40:96": "Cisco", "00:50:0F": "Cisco", "00:60:2F": "Cisco",
    "00:0A:41": "Cisco", "00:0B:BE": "Cisco", "00:0C:30": "Cisco",
    "00:0D:29": "Cisco", "00:0E:38": "Cisco", "00:0F:24": "Cisco",
    "00:17:94": "Cisco", "00:18:73": "Cisco", "00:19:AA": "Cisco",
    "2C:33:11": "Cisco", "2C:54:2D": "Cisco", "D0:72:DC": "Cisco",
    "F4:CF:E2": "Cisco", "F8:72:EA": "Cisco", "FC:5B:39": "Cisco",
    # HP / HPE / Aruba
    "00:1A:4B": "HP", "00:1C:C4": "HP", "00:1E:0B": "HP",
    "00:21:5A": "HP", "00:23:7D": "HP", "00:25:B3": "HP",
    "00:17:A4": "HP", "00:14:38": "HP", "00:0B:CD": "HP",
    "00:0D:9D": "HP", "00:0E:7F": "HP", "00:0F:20": "HP",
    "10:60:4B": "HP", "14:02:EC": "HP", "1C:98:EC": "HP",
    "28:80:23": "HP", "30:8D:99": "HP", "38:63:BB": "HP",
    "3C:D9:2B": "HP", "48:0F:CF": "HP", "5C:B9:01": "HP",
    "68:B5:99": "HP", "80:C1:6E": "HP", "94:57:A5": "HP",
    "9C:8E:99": "HP", "A0:1D:48": "HP", "A0:D3:C1": "HP",
    "B4:B5:2F": "HP", "D4:C9:EF": "HP", "EC:B1:D7": "HP",
    # Dell
    "00:14:22": "Dell", "00:1A:A0": "Dell", "00:1E:C9": "Dell",
    "00:21:70": "Dell", "00:22:19": "Dell", "00:24:E8": "Dell",
    "00:26:B9": "Dell", "00:0B:DB": "Dell", "00:0D:56": "Dell",
    "00:0F:1F": "Dell", "14:18:77": "Dell", "18:03:73": "Dell",
    "18:66:DA": "Dell", "18:A9:9B": "Dell", "24:6E:96": "Dell",
    "28:F1:0E": "Dell", "34:17:EB": "Dell", "44:A8:42": "Dell",
    "4C:76:25": "Dell", "50:9A:4C": "Dell", "54:9F:35": "Dell",
    "5C:F9:DD": "Dell", "74:86:7A": "Dell", "78:2B:CB": "Dell",
    "80:18:44": "Dell", "84:2B:2B": "Dell", "98:90:96": "Dell",
    "B0:83:FE": "Dell", "B8:2A:72": "Dell", "BC:30:5B": "Dell",
    "D4:81:D7": "Dell", "F0:1F:AF": "Dell", "F4:8E:38": "Dell",
    # Juniper
    "00:05:85": "Juniper", "00:10:DB": "Juniper", "00:12:1E": "Juniper",
    "00:14:F6": "Juniper", "00:17:CB": "Juniper", "00:19:E2": "Juniper",
    "00:1F:12": "Juniper", "00:21:59": "Juniper", "00:22:83": "Juniper",
    "00:23:9C": "Juniper", "00:24:DC": "Juniper", "00:26:88": "Juniper",
    "28:8A:1C": "Juniper", "28:C0:DA": "Juniper", "2C:21:31": "Juniper",
    "2C:6B:F5": "Juniper", "3C:61:04": "Juniper", "3C:8A:B0": "Juniper",
    "40:A6:77": "Juniper", "40:B4:F0": "Juniper", "44:F4:77": "Juniper",
    "4C:96:14": "Juniper", "50:C5:8D": "Juniper", "54:1E:56": "Juniper",
    "54:E0:32": "Juniper", "64:64:9B": "Juniper", "64:87:88": "Juniper",
    "78:19:F7": "Juniper", "78:FE:3D": "Juniper", "80:71:1F": "Juniper",
    "84:18:88": "Juniper", "84:B5:9C": "Juniper", "88:A2:5E": "Juniper",
    "88:E0:F3": "Juniper", "9C:CC:83": "Juniper", "A8:D0:E5": "Juniper",
    "AC:4B:C8": "Juniper", "B0:A8:6E": "Juniper", "B0:C6:9A": "Juniper",
    "CC:E1:7F": "Juniper", "D4:04:FF": "Juniper", "DC:38:E1": "Juniper",
    "EC:3E:F7": "Juniper", "F0:1C:2D": "Juniper", "F4:A7:39": "Juniper",
    "F4:CC:55": "Juniper",
    # Fortinet
    "00:09:0F": "Fortinet", "08:5B:0E": "Fortinet", "70:4C:A5": "Fortinet",
    "90:6C:AC": "Fortinet", "E8:1C:BA": "Fortinet",
    # MikroTik
    "00:0C:42": "MikroTik", "48:8F:5A": "MikroTik", "4C:5E:0C": "MikroTik",
    "6C:3B:6B": "MikroTik", "74:4D:28": "MikroTik", "B8:69:F4": "MikroTik",
    "C4:AD:34": "MikroTik", "CC:2D:E0": "MikroTik", "D4:01:C3": "MikroTik",
    "E4:8D:8C": "MikroTik",
    # Ubiquiti
    "00:15:6D": "Ubiquiti", "00:27:22": "Ubiquiti", "04:18:D6": "Ubiquiti",
    "18:E8:29": "Ubiquiti", "24:5A:4C": "Ubiquiti", "44:D9:E7": "Ubiquiti",
    "68:72:51": "Ubiquiti", "78:8A:20": "Ubiquiti", "80:2A:A8": "Ubiquiti",
    "B4:FB:E4": "Ubiquiti", "DC:9F:DB": "Ubiquiti", "F0:9F:C2": "Ubiquiti",
    "FC:EC:DA": "Ubiquiti",
    # VMware
    "00:0C:29": "VMware", "00:50:56": "VMware", "00:05:69": "VMware",
    # Microsoft (Hyper-V)
    "00:15:5D": "Microsoft Hyper-V",
    # Intel (serveurs, cartes réseau)
    "00:1B:21": "Intel", "00:1E:67": "Intel", "00:22:FA": "Intel",
    "3C:97:0E": "Intel", "68:05:CA": "Intel", "8C:EC:4B": "Intel",
    "A4:BF:01": "Intel", "F8:F2:1E": "Intel",
    # Supermicro (serveurs)
    "00:25:90": "Supermicro", "00:0E:0C": "Supermicro", "AC:1F:6B": "Supermicro",
    # Lenovo
    "00:06:1B": "Lenovo", "70:5A:0F": "Lenovo", "98:FA:9B": "Lenovo",
    # Apple
    "00:03:93": "Apple", "00:1C:B3": "Apple", "28:CF:DA": "Apple",
    "3C:15:C2": "Apple", "70:56:81": "Apple", "A4:83:E7": "Apple",
    # Samsung
    "00:21:19": "Samsung", "00:26:37": "Samsung", "5C:0A:5B": "Samsung",
    "8C:F5:A3": "Samsung", "BC:72:B1": "Samsung",
    # Huawei
    "00:E0:FC": "Huawei", "20:F3:A3": "Huawei", "48:46:FB": "Huawei",
    "70:72:3C": "Huawei", "AC:CF:85": "Huawei",
    # TP-Link
    "00:1D:0F": "TP-Link", "14:CC:20": "TP-Link", "50:C7:BF": "TP-Link",
    "60:32:B1": "TP-Link", "B0:4E:26": "TP-Link", "F4:F2:6D": "TP-Link",
    # Netgear
    "00:14:6C": "Netgear", "00:1E:2A": "Netgear", "20:0C:C8": "Netgear",
    "28:C6:8E": "Netgear", "6C:B0:CE": "Netgear", "C4:04:15": "Netgear",
    # D-Link
    "00:17:9A": "D-Link", "00:1C:F0": "D-Link", "1C:7E:E5": "D-Link",
    "28:10:7B": "D-Link", "78:54:2E": "D-Link", "C4:A8:1D": "D-Link",
    # Arista
    "00:1C:73": "Arista", "28:99:3A": "Arista", "44:4C:A8": "Arista",
    # Palo Alto Networks
    "00:1B:17": "Palo Alto", "08:30:6B": "Palo Alto", "00:86:9C": "Palo Alto",
    # SonicWall
    "00:06:B1": "SonicWall", "00:0C:F1": "SonicWall",
    # pfSense / Netgate
    "00:08:A2": "Netgate",
}


def lookup_vendor(mac_address: str) -> str:
    """
    Cherche le constructeur à partir de l'adresse MAC (3 premiers octets OUI).
    Normalise les formats courants (tirets, deux-points, points Cisco).
    """
    if not mac_address:
        return "Inconnu"

    # Normaliser : retirer séparateurs, passer en majuscules
    cleaned = mac_address.upper().replace("-", "").replace(":", "").replace(".", "")

    if len(cleaned) < 6:
        return "Inconnu"

    # Reformater en XX:XX:XX pour lookup
    oui = f"{cleaned[0:2]}:{cleaned[2:4]}:{cleaned[4:6]}"

    return OUI_DATABASE.get(oui, "Inconnu")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 : EXTRACTION MAC DEPUIS LA TABLE ARP
# ─────────────────────────────────────────────────────────────────────────────

def extraire_mac_arp(ip: str) -> str:
    """
    Récupère l'adresse MAC d'une IP depuis la table ARP du système.

    Stratégie multi-OS :
      Linux  : ip neigh show <ip>  →  puis fallback arp -n <ip>
      Windows: arp -a <ip>
      macOS  : arp -n <ip>

    Retourne la MAC normalisée (AA:BB:CC:DD:EE:FF) ou chaîne vide.
    """
    system = platform.system().lower()
    mac = ""

    # ── Forcer une entrée ARP en envoyant un ping silencieux ──
    # Nécessaire si la table ARP ne contient pas encore cette IP.
    try:
        if system == "windows":
            subprocess.run(
                ["ping", "-n", "1", "-w", "500", ip],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3
            )
        else:
            subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3
            )
    except Exception:
        pass

    # ── Extraction selon l'OS ──
    try:
        if system == "linux":
            # Méthode 1 : ip neigh (moderne)
            result = subprocess.run(
                ["ip", "neigh", "show", ip],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                # Format : "192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
                match = re.search(r"lladdr\s+([0-9a-fA-F:]{17})", result.stdout)
                if match:
                    mac = match.group(1)

            # Méthode 2 : arp -n (fallback)
            if not mac:
                result = subprocess.run(
                    ["arp", "-n", ip],
                    capture_output=True, text=True, timeout=5
                )
                match = re.search(r"([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}", result.stdout)
                if match:
                    mac = match.group(0)

            # Méthode 3 : lire /proc/net/arp directement (ultra-fiable)
            if not mac:
                try:
                    with open("/proc/net/arp", "r") as f:
                        for line in f:
                            if ip in line:
                                parts = line.split()
                                if len(parts) >= 4 and parts[0] == ip:
                                    candidate = parts[3]
                                    if candidate != "00:00:00:00:00:00":
                                        mac = candidate
                                    break
                except FileNotFoundError:
                    pass

        elif system == "windows":
            result = subprocess.run(
                ["arp", "-a", ip],
                capture_output=True, text=True, timeout=5
            )
            # Format Windows : "192.168.1.1     aa-bb-cc-dd-ee-ff     dynamique"
            match = re.search(r"([0-9a-fA-F]{2}[\-:]){5}[0-9a-fA-F]{2}", result.stdout)
            if match:
                mac = match.group(0)

        elif system == "darwin":  # macOS
            result = subprocess.run(
                ["arp", "-n", ip],
                capture_output=True, text=True, timeout=5
            )
            match = re.search(r"([0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2}", result.stdout)
            if match:
                mac = match.group(0)

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Erreur extraction MAC pour {ip}: {e}")

    # ── Normaliser ──
    if mac:
        # Remplacer tirets par deux-points, majuscules
        mac = mac.replace("-", ":").upper()

        # Compléter les octets courts (macOS : "0:0:0:..." → "00:00:00:...")
        parts = mac.split(":")
        mac = ":".join(p.zfill(2) for p in parts)

        # Ignorer les MAC vides ou broadcast
        if mac in ("00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"):
            return ""


def get_arp_ips() -> set:
    """
    Récupère toutes les IPs actuellement présentes dans la table ARP du système.
    Permet de découvrir des hôtes qui ont communiqué récemment mais sont silencieux (firewall).
    """
    ips = set()
    system = platform.system().lower()
    try:
        if system == "windows":
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
            # Format: "  192.168.1.1           aa-bb-cc-dd-ee-ff     dynamique"
            found = re.findall(r"(\d+\.\d+\.\d+\.\d+)", result.stdout)
            ips.update(found)
        else:
            # Linux / macOS
            result = subprocess.run(["arp", "-n"], capture_output=True, text=True, timeout=5)
            found = re.findall(r"(\d+\.\d+\.\d+\.\d+)", result.stdout)
            ips.update(found)
    except Exception:
        pass
    
    # Filtrer broadcast et localhost
    return {ip for ip in ips if not ip.endswith(".255") and not ip.startswith("127.")}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 : SCAN DE PORTS ET DÉTECTION DE SERVICES
# ─────────────────────────────────────────────────────────────────────────────

# Ports à scanner avec le service associé
PORTS_SERVICES = {
    22:    "SSH",
    23:    "Telnet",
    53:    "DNS",
    80:    "HTTP",
    135:   "MSRPC",
    139:   "NetBIOS",
    161:   "SNMP",
    443:   "HTTPS",
    445:   "SMB",
    993:   "IMAPS",
    1433:  "MSSQL",
    1521:  "Oracle",
    3306:  "MySQL",
    3389:  "RDP",
    5432:  "PostgreSQL",
    5900:  "VNC",
    5985:  "WinRM",
    8080:  "HTTP-Proxy",
    8443:  "HTTPS-Alt",
    8291:  "MikroTik-Winbox",
    8728:  "MikroTik-API",
    10000: "Webmin",
}


def scanner_ports(ip: str, ports: dict = None, timeout: float = 0.8) -> list:
    """
    Scan TCP Connect sur une liste de ports.

    Retourne une liste de dicts : [{"port": 22, "service": "SSH", "open": True}, ...]
    Seuls les ports ouverts sont retournés pour la concision.
    """
    if ports is None:
        ports = PORTS_SERVICES

    ouverts = []

    for port, service in ports.items():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                if result == 0:
                    # Tenter un banner grab rapide
                    banner = ""
                    try:
                        sock.settimeout(1.0)
                        # Envoyer un mini-probe pour certains services
                        if port in (80, 8080, 8443, 443):
                            sock.sendall(b"HEAD / HTTP/1.0\r\n\r\n")
                        elif port == 22:
                            pass  # SSH envoie le banner automatiquement

                        data = sock.recv(256)
                        if data:
                            banner = data.decode("utf-8", errors="replace").strip()
                    except Exception:
                        pass

                    ouverts.append({
                        "port": port,
                        "service": service,
                        "banner": banner[:200] if banner else "",
                    })
        except Exception:
            continue

    return ouverts


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 : FINGERPRINTING OS ET TYPE D'ÉQUIPEMENT
# ─────────────────────────────────────────────────────────────────────────────

def extraire_ttl(ip: str) -> int:
    """
    Envoie un ping et extrait le TTL de la réponse.

    Mapping standard :
      TTL 64  → Linux / Unix / macOS / équipements réseau (certains)
      TTL 128 → Windows
      TTL 255 → Routeurs / Switchs (Cisco IOS, JunOS, etc.)

    Retourne le TTL ou -1 si impossible.
    """
    system = platform.system().lower()

    try:
        if system == "windows":
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1500", ip],
                capture_output=True, text=True, timeout=5
            )
            # Cherche "TTL=xxx" (format Windows FR/EN)
            match = re.search(r"TTL[=:](\d+)", result.stdout, re.IGNORECASE)
        else:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", ip],
                capture_output=True, text=True, timeout=5
            )
            # Cherche "ttl=xxx" (format Unix)
            match = re.search(r"ttl=(\d+)", result.stdout, re.IGNORECASE)

        if match:
            return int(match.group(1))

    except Exception:
        pass

    return -1


def deviner_os(ttl: int, ports_ouverts: list, banner_ssh: str = "",
               vendor: str = "") -> dict:
    """
    Combine TTL + ports ouverts + banners + vendor pour deviner l'OS.

    Retourne :
      {"os": "Windows Server 2019", "os_family": "windows", "confidence": 85}
    """
    scores = {
        "windows": 0,
        "linux": 0,
        "network_device": 0,
        "firewall": 0,
    }
    os_detail = "Inconnu"
    confidence = 0

    ports_set = {p["port"] for p in ports_ouverts}
    banners = {p["port"]: p.get("banner", "") for p in ports_ouverts}

    # ── TTL Analysis ──
    if ttl > 0:
        if 120 <= ttl <= 128:
            scores["windows"] += 45
        elif 60 <= ttl <= 64:
            # ⚠️ Problème : WSL2 et Docker Desktop ont un TTL de 64
            # Si on voit des ports Windows, on baisse la certitude Linux
            if ports_set & {135, 139, 445, 3389}:
                scores["windows"] += 40
                scores["linux"] += 10
            else:
                scores["linux"] += 35
                scores["network_device"] += 10
        elif ttl >= 250:
            scores["network_device"] += 45
            scores["firewall"] += 20

    # ── Ports Windows ──
    windows_ports = {135, 139, 445, 3389, 5985, 1433}
    windows_hits = len(ports_set & windows_ports)
    if windows_hits >= 3:
        scores["windows"] += 50
    elif windows_hits >= 1:
        scores["windows"] += 25

    # ── Ports Linux ──
    if 22 in ports_set:
        # Si port 22 ouvert ET ports Windows ouverts -> Probablement Windows + WSL/Dev
        if ports_set & {135, 445, 3389}:
            scores["windows"] += 15
            scores["linux"] += 10
        else:
            scores["linux"] += 25
            scores["network_device"] += 15

    linux_db_ports = {3306, 5432, 10000}
    if ports_set & linux_db_ports:
        scores["linux"] += 15

    # ── Ports Équipement Réseau ──
    network_ports = {23, 161, 8291, 8728}
    net_hits = len(ports_set & network_ports)
    if net_hits >= 2:
        scores["network_device"] += 35
    elif net_hits >= 1:
        scores["network_device"] += 15

    # ── Vendor Analysis ──
    vendor_lower = vendor.lower() if vendor else ""
    network_vendors = ["cisco", "juniper", "mikrotik", "arista", "ubiquiti",
                       "tp-link", "netgear", "d-link", "huawei", "technicolor", "sagemcom"]
    firewall_vendors = ["fortinet", "palo alto", "sonicwall", "netgate"]
    server_vendors = ["dell", "hp", "hpe", "supermicro", "lenovo", "intel"]

    if any(v in vendor_lower for v in network_vendors):
        scores["network_device"] += 40
    if any(v in vendor_lower for v in firewall_vendors):
        scores["firewall"] += 50
    if any(v in vendor_lower for v in server_vendors):
        scores["windows"] += 5
        scores["linux"] += 5

    # ── Banner SSH Analysis ──
    ssh_banner = banners.get(22, "")
    if ssh_banner:
        ssh_lower = ssh_banner.lower()
        if "ubuntu" in ssh_lower:
            scores["linux"] += 30
            os_detail = "Ubuntu Linux"
        elif "debian" in ssh_lower:
            scores["linux"] += 30
            os_detail = "Debian Linux"
        elif "openssh" in ssh_lower:
            scores["linux"] += 15
        elif "cisco" in ssh_lower:
            scores["network_device"] += 45
            os_detail = "Cisco IOS"

    # ── HTTP Banner Analysis ──
    for http_port in [80, 443, 8080, 8443]:
        http_banner = banners.get(http_port, "").lower()
        if http_banner:
            if "microsoft" in http_banner or "iis" in http_banner:
                scores["windows"] += 30
                os_detail = "Windows (IIS)"
            elif "fortios" in http_banner or "fortigate" in http_banner:
                scores["firewall"] += 40
                os_detail = "Fortinet FortiOS"
            elif "tp-link" in http_banner or "d-link" in http_banner:
                scores["network_device"] += 40
                os_detail = "Access Point Web Panel"

    # ── Winbox = MikroTik certain ──
    if 8291 in ports_set:
        scores["network_device"] += 50
        os_detail = "MikroTik RouterOS"

    # ── Déterminer le gagnant ──
    winner = max(scores, key=scores.get)
    max_score = scores[winner]
    total_score = sum(scores.values())

    if total_score > 0:
        confidence = min(95, int((max_score / total_score) * 100))
    else:
        confidence = 10

    if os_detail == "Inconnu":
        os_map = {
            "windows": "Windows PC/Server",
            "linux": "Linux System",
            "network_device": "Network Equipment",
            "firewall": "Firewall",
        }
        os_detail = os_map.get(winner, "Inconnu")

    return {
        "os": os_detail,
        "os_family": winner,
        "confidence": confidence,
        "scores": scores,
    }


def mapper_type_equipement(os_family: str, ports_ouverts: list,
                            vendor: str, hostname: str) -> str:
    """
    Mappe le résultat du fingerprinting aux TYPE_CHOICES du modèle EquipementReseau.
    """
    ports_set = {p["port"] for p in ports_ouverts}
    vendor_lower = vendor.lower() if vendor else ""
    hostname_lower = hostname.lower() if hostname else ""

    # ── Pare-feu ──
    if os_family == "firewall":
        return "parefeu"

    # ── WiFi / Access Point (Priorité car souvent mal détectés) ──
    wifi_vendors = ["ubiquiti", "tp-link", "netgear", "d-link", "linksys", "meraki", "aruba", "ruckus", "mist", "extreme"]
    wifi_hints = ["ap-", "wifi", "accesspoint", "unifi", "wlan", "hotspot"]
    if any(v in vendor_lower for v in wifi_vendors) or any(h in hostname_lower for h in wifi_hints):
        if 80 in ports_set or 443 in ports_set or 161 in ports_set or 8080 in ports_set:
            return "wifi"

    # ── Équipement réseau ──
    if os_family == "network_device":
        switch_hints = ["switch", "sw-", "sw_", "catalyst", "nexus", "bridge"]
        for hint in switch_hints:
            if hint in hostname_lower or hint in vendor_lower:
                return "switch"
        return "routeur"

    # ── Windows ──
    if os_family == "windows":
        server_hints = ["srv", "server", "dc-", "ad-", "sql", "win-srv"]
        if any(h in hostname_lower for h in server_hints) or (ports_set & {445, 1433, 5985}):
            return "serveur_win"
        return "pc_win"

    # ── Linux ──
    if os_family == "linux":
        return "serveur"

    return "autre"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 : DÉTECTION RÉSEAU LOCAL
# ─────────────────────────────────────────────────────────────────────────────

def detecter_reseaux_locaux() -> list:
    """
    Détecte tous les réseaux locaux de la machine.

    Retourne une liste de CIDRs : ["192.168.1.0/24", "10.0.0.0/24"]
    Compatible Linux / Windows / macOS.
    """
    reseaux = []
    system = platform.system().lower()

    try:
        if system == "linux":
            result = subprocess.run(
                ["ip", "-4", "addr", "show"],
                capture_output=True, text=True, timeout=5
            )
            # Parser "inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0"
            for match in re.finditer(
                r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)\s+.*scope\s+global", result.stdout
            ):
                ip_addr = match.group(1)
                prefix = int(match.group(2))
                network = IPv4Network(f"{ip_addr}/{prefix}", strict=False)
                reseaux.append(str(network))

        elif system == "windows":
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True, text=True, timeout=5
            )
            # Trouver les paires IP / Masque
            ips = re.findall(r"IPv4[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", result.stdout)
            masks = re.findall(r"Masque[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", result.stdout)

            # Fallback anglais
            if not ips:
                ips = re.findall(r"IPv4 Address[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", result.stdout)
                masks = re.findall(r"Subnet Mask[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", result.stdout)

            for ip_addr, mask in zip(ips, masks):
                if ip_addr.startswith("127."):
                    continue
                network = IPv4Network(f"{ip_addr}/{mask}", strict=False)
                reseaux.append(str(network))

        elif system == "darwin":
            result = subprocess.run(
                ["ifconfig"],
                capture_output=True, text=True, timeout=5
            )
            for match in re.finditer(
                r"inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+(0x[0-9a-f]+)", result.stdout
            ):
                ip_addr = match.group(1)
                if ip_addr.startswith("127."):
                    continue
                hex_mask = match.group(2)
                prefix = bin(int(hex_mask, 16)).count("1")
                network = IPv4Network(f"{ip_addr}/{prefix}", strict=False)
                reseaux.append(str(network))

    except Exception as e:
        logger.error(f"Erreur détection réseau: {e}")

    # Fallback : si rien trouvé, essayer socket
    if not reseaux:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            reseaux.append(f"{local_ip}/24")
        except Exception:
            pass

    # Filtrer les réseaux de loopback et APIPA
    reseaux = [
        r for r in reseaux
        if not r.startswith("127.") and not r.startswith("169.254.")
    ]

    return reseaux


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6 : SCANNER PRINCIPAL — DEEP DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────

def hote_est_actif(ip: str, timeout: int = 1) -> bool:
    """
    Vérifie rapidement si un hôte est actif. Optimisé pour la vitesse.
    """
    system = platform.system().lower()

    # ── Méthode 1 : Ping ICMP (Délai court) ──
    try:
        count_flag = "-n" if system == "windows" else "-c"
        # Diminution du timeout global pour le ping
        timeout_flag = "-w" if system == "windows" else "-W"
        timeout_val = "500" if system == "windows" else "1"

        proc = subprocess.run(
            ["ping", count_flag, "1", timeout_flag, timeout_val, ip],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
        )
        if proc.returncode == 0:
            return True
    except Exception:
        pass

    # ── Méthode 2 : TCP Connect ultra-rapide sur ports "phares" ──
    # On ne check que 3-4 ports critiques pour voir si la machine "vit"
    essential_ports = [22, 80, 443, 445, 135, 161]
    for port in essential_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Timeout réduit à 0.2s pour le "vivant check"
                sock.settimeout(0.2)
                if sock.connect_ex((ip, port)) == 0:
                    return True
        except Exception:
            continue

    return False


def scanner_ip(ip: str, scan_ports: bool = True) -> dict | None:
    """
    Deep scan d'une IP unique.
    """
    # ── ÉTAPE 1 : Vérifier si l'hôte est actif ──
    if not hote_est_actif(ip):
        return None

    # ── ÉTAPE 2 : Hostname ──
    hostname = get_hostname(ip)

    # ── ÉTAPE 3 : Adresse MAC + Constructeur ──
    mac = extraire_mac_arp(ip)
    vendor = lookup_vendor(mac) if mac else "Inconnu"

    # ── ÉTAPE 4 : TTL ──
    ttl = extraire_ttl(ip)

    # ── ÉTAPE 5 : Scan de ports ──
    ports_ouverts = []
    if scan_ports:
        ports_ouverts = scanner_ports(ip)

    # ── ÉTAPE 6 : Fingerprinting OS ──
    os_info = deviner_os(
        ttl=ttl,
        ports_ouverts=ports_ouverts,
        vendor=vendor,
    )

    # ── ÉTAPE 7 : Mapper au TYPE_CHOICES Django ──
    type_equipement = mapper_type_equipement(
        os_family=os_info["os_family"],
        ports_ouverts=ports_ouverts,
        vendor=vendor,
        hostname=hostname,
    )

    # ── ÉTAPE 8 : Construire le nom ──
    if hostname:
        nom = hostname.split(".")[0]  # Prendre le short name
    elif vendor and vendor != "Inconnu":
        nom = f"{vendor}_{ip.rsplit('.', 1)[1]}"
    else:
        nom = f"device_{ip.rsplit('.', 1)[1]}"

    # ── ÉTAPE 9 : Construire la description ──
    services_str = ", ".join(
        f"{p['service']}:{p['port']}" for p in ports_ouverts
    )
    description = (
        f"Découvert le {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n"
        f"OS: {os_info['os']} (confiance: {os_info['confidence']}%)\n"
        f"MAC: {mac or 'Non disponible'} | Fabricant: {vendor}\n"
        f"TTL: {ttl if ttl > 0 else 'N/A'}\n"
        f"Services: {services_str or 'Aucun détecté'}"
    )

    # ── Port SSH détecté ? ──
    port_ssh = 22
    for p in ports_ouverts:
        if p["service"] == "SSH":
            port_ssh = p["port"]
            break

    return {
        # Champs principaux (mappés au modèle Django)
        "nom": nom,
        "type_equipement": type_equipement,
        "adresse_ip": ip,
        "port_ssh": port_ssh,
        "description": description,
        "statut": "actif",

        # Champs enrichis (pour l'affichage et l'analyse)
        "hostname": hostname,
        "mac_address": mac,
        "vendor": vendor,
        "ttl": ttl,
        "os": os_info["os"],
        "os_family": os_info["os_family"],
        "os_confidence": os_info["confidence"],
        "ports_ouverts": ports_ouverts,
        "services": [p["service"] for p in ports_ouverts],
        "discovered_at": datetime.now().isoformat(),
    }


def get_hostname(ip: str) -> str:
    """
    Récupére le hostname par DNS inverse.
    """
    hostname = ""
    try:
        # Tenter gethostbyaddr
        hostname = socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        # Tenter getnameinfo
        try:
            hostname = socket.getnameinfo((ip, 0), 0)[0]
            if hostname == ip:
                hostname = ""
        except Exception:
            pass
    
    return hostname


def scanner_reseau(
    subnets: list = None,
    max_workers: int = 150,  # Augmenté pour la vitesse
    scan_ports: bool = True,
    callback=None,
) -> list:
    """
    Deep Discovery — Scan complet d'un ou plusieurs sous-réseaux.

    Args:
        subnets:     Liste de CIDRs (ex: ["192.168.1.0/24"]). Auto-détecté si None.
        max_workers: Nombre de threads parallèles (défaut 50).
        scan_ports:  Scanner les ports de chaque hôte actif (True/False).
        callback:    Fonction optionnelle appelée avec (progression%, ip, resultat)
                     pour le suivi en temps réel (Django Channels, Celery, etc.)

    Retourne une liste de dictionnaires enrichis.
    """
    # ── Détection des réseaux ──
    if not subnets:
        subnets = detecter_reseaux_locaux()
        if not subnets:
            logger.error("Impossible de détecter le réseau local")
            return []

    # ── Construire la liste d'IPs ──
    all_ips = set()
    for subnet in subnets:
        # ✅ Robustesse : si l'utilisateur saisit "192.168.1.0" sans le /24
        if "/" not in subnet:
            if subnet.endswith(".0"):
                subnet += "/24"
                logger.info(f"Auto-correction : '{subnet}' (ajout du /24)")
            else:
                # Si c'est juste une IP seule, on la garde telle quelle (sera un /32)
                pass

        try:
            network = IPv4Network(subnet, strict=False)
            # Pour un /32, hosts() est vide. On ajoute l'IP manuellement dans ce cas.
            hosts = list(network.hosts())
            if not hosts:
                all_ips.add(str(network.network_address))
            else:
                all_ips.update({str(ip) for ip in hosts})
        except ValueError as e:
            logger.error(f"Sous-réseau invalide '{subnet}': {e}")

    # ── AJOUT : IPs de la table ARP (Découverte assistée) ──
    arp_ips = get_arp_ips()
    detected_count = 0
    for ip in arp_ips:
        # Vérifier si l'IP ARP appartient à l'un des sous-réseaux ciblés
        for subnet in subnets:
            if IPv4Address(ip) in IPv4Network(subnet, strict=False):
                if ip not in all_ips:
                    all_ips.add(ip)
                    detected_count += 1
                break
    
    if detected_count > 0:
        logger.info(f"Découverte assistée par ARP : {detected_count} hôte(s) potentiel(s) ajouté(s)")

    if not all_ips:
        logger.error("Aucune IP à scanner")
        return []

    all_ips_list = sorted(list(all_ips), key=lambda x: int(IPv4Address(x)))
    total = len(all_ips_list)
    logger.info(f"Deep Discovery — Scan de {total} IPs sur {subnets}")

    decouvertes = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(scanner_ip, ip, scan_ports): ip
            for ip in all_ips_list
        }

        for future in as_completed(futures):
            completed += 1
            ip = futures[future]

            try:
                result = future.result()
            except Exception as e:
                logger.warning(f"Erreur lors du scan de {ip}: {e}")
                result = None

            progress = int((completed / total) * 100)

            if result:
                decouvertes.append(result)
                logger.info(
                    f"[{progress:3d}%] Trouvé: {result['adresse_ip']} "
                    f"→ {result['type_equipement']} | {result['vendor']} "
                    f"| {result['os']}"
                )
            elif completed % 50 == 0:
                logger.debug(f"[{progress:3d}%] Progression: {completed}/{total}")

            # Callback pour le suivi temps réel
            if callback:
                try:
                    callback(progress, ip, result)
                except Exception:
                    pass

    # Trier par IP
    decouvertes.sort(
        key=lambda x: int(IPv4Address(x["adresse_ip"]))
    )

    logger.info(f"Deep Discovery terminé : {len(decouvertes)} équipement(s) sur {total} IPs")
    return decouvertes


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7 : IMPORT DJANGO — Sauvegarde dans EquipementReseau
# ─────────────────────────────────────────────────────────────────────────────

def importer_decouvertes(resultats: list, update_existing: bool = False,
                          default_snmp_community: str = "public",
                          localisation: str = None) -> dict:
    """
    Importe les résultats du scan dans la table EquipementReseau.

    Logique :
      - Vérifie les doublons par adresse_ip (unique en pratique)
      - Si l'IP existe déjà :
          * update_existing=False → on skip (défaut sécurisé)
          * update_existing=True  → on met à jour les champs enrichis
      - Mappe les champs du scan vers les champs du modèle Django
      - Remplit des valeurs par défaut sécurisées

    Args:
        resultats:              Liste de dicts retournée par scanner_reseau()
        update_existing:        Mettre à jour les équipements existants
        default_snmp_community: Communauté SNMP par défaut
        localisation:           Localisation à appliquer à tous les équipements

    Retourne un rapport :
        {"created": 5, "updated": 2, "skipped": 3, "errors": [], "details": [...]}
    """
    # Import lazy pour ne pas casser si appelé hors Django
    try:
        from monitoring.models import EquipementReseau
    except ImportError:
        try:
            from equipements.models import EquipementReseau
        except ImportError:
            raise ImportError(
                "Impossible d'importer le modèle EquipementReseau. "
                "Vérifiez que l'app Django est correctement configurée. "
                "Adaptez le chemin d'import ci-dessus à votre projet."
            )

    rapport = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "details": [],
    }

    # Types valides dans le modèle Django
    types_valides = {choice[0] for choice in EquipementReseau.TYPE_CHOICES}

    for device in resultats:
        ip = device["adresse_ip"]
        type_eq = device["type_equipement"]

        # ── Sécurité : vérifier que le type est valide ──
        if type_eq not in types_valides:
            type_eq = "autre"

        try:
            # ── Chercher un doublon ──
            existing = EquipementReseau.objects.filter(adresse_ip=ip).first()

            if existing and not update_existing:
                rapport["skipped"] += 1
                rapport["details"].append({
                    "ip": ip,
                    "action": "skipped",
                    "reason": "Équipement déjà en base",
                })
                continue

            # ── Préparer les données ──
            data = {
                "nom": device["nom"][:100],  # Respecter max_length
                "type_equipement": type_eq,
                "adresse_ip": ip,
                "port_ssh": device.get("port_ssh", 22),
                "description": device.get("description", "")[:5000],
                "statut": "actif",
                "snmp_community": default_snmp_community,
            }

            if localisation:
                data["localisation"] = localisation[:255]

            # SSH : on ne met PAS de credentials par défaut (sécurité)
            # L'admin les configurera manuellement après la découverte.

            if existing and update_existing:
                # ── Mise à jour ──
                for key, value in data.items():
                    setattr(existing, key, value)
                existing.save()
                rapport["updated"] += 1
                rapport["details"].append({
                    "ip": ip,
                    "action": "updated",
                    "nom": data["nom"],
                    "type": type_eq,
                })
            else:
                # ── Création ──
                EquipementReseau.objects.create(**data)
                rapport["created"] += 1
                rapport["details"].append({
                    "ip": ip,
                    "action": "created",
                    "nom": data["nom"],
                    "type": type_eq,
                    "vendor": device.get("vendor", ""),
                    "os": device.get("os", ""),
                })

        except Exception as e:
            rapport["errors"].append({
                "ip": ip,
                "error": str(e),
            })
            logger.error(f"Erreur import {ip}: {e}")

    logger.info(
        f"Import terminé — Créés: {rapport['created']}, "
        f"Mis à jour: {rapport['updated']}, "
        f"Ignorés: {rapport['skipped']}, "
        f"Erreurs: {len(rapport['errors'])}"
    )
    return rapport


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8 : INTÉGRATIONS — Celery Task + Vue Django
# ─────────────────────────────────────────────────────────────────────────────

# ── 8.1 : Tâche Celery (à placer dans discovery/tasks.py ou directement ici) ──

def celery_task_scan_reseau():
    """
    Exemple de tâche Celery. Copiez dans votre discovery/tasks.py :

    from celery import shared_task
    from .scanner import scanner_reseau, importer_decouvertes

    @shared_task(bind=True, name="discovery.deep_scan")
    def deep_scan_task(self, subnets=None, update_existing=False,
                       localisation=None):
        def progress_callback(percent, ip, result):
            self.update_state(
                state="PROGRESS",
                meta={
                    "percent": percent,
                    "current_ip": ip,
                    "found": result["adresse_ip"] if result else None,
                }
            )

        # Phase 1 : Scanner
        resultats = scanner_reseau(
            subnets=subnets,
            max_workers=30,   # Moins agressif en tâche de fond
            scan_ports=True,
            callback=progress_callback,
        )

        # Phase 2 : Importer
        rapport = importer_decouvertes(
            resultats,
            update_existing=update_existing,
            localisation=localisation,
        )

        return {
            "devices_found": len(resultats),
            "report": rapport,
        }
    """
    pass  # Placeholder — voir le docstring ci-dessus


# ── 8.2 : Vue Django (à placer dans discovery/views.py) ──

def django_view_example():
    """
    Exemple de vue Django. Copiez dans votre discovery/views.py :

    from django.http import JsonResponse
    from django.contrib.auth.decorators import login_required
    from django.views.decorators.http import require_POST
    from .scanner import scanner_reseau, importer_decouvertes
    import json

    @login_required
    @require_POST
    def lancer_scan(request):
        '''Lance un scan réseau et importe les résultats.'''
        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            body = {}

        subnets = body.get("subnets", None)  # None = auto-détection
        update = body.get("update_existing", False)
        localisation = body.get("localisation", None)

        # Scan synchrone (pour les petits réseaux)
        resultats = scanner_reseau(
            subnets=subnets,
            scan_ports=True,
        )

        # Import en base
        rapport = importer_decouvertes(
            resultats,
            update_existing=update,
            localisation=localisation,
        )

        return JsonResponse({
            "success": True,
            "devices_found": len(resultats),
            "devices": resultats,
            "import_report": rapport,
        })

    # Pour les gros réseaux, utilisez la tâche Celery :
    #
    # @login_required
    # @require_POST
    # def lancer_scan_async(request):
    #     from .tasks import deep_scan_task
    #     body = json.loads(request.body) if request.body else {}
    #     task = deep_scan_task.delay(
    #         subnets=body.get("subnets"),
    #         update_existing=body.get("update_existing", False),
    #     )
    #     return JsonResponse({"task_id": task.id})
    """
    pass  # Placeholder — voir le docstring ci-dessus


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9 : POINT D'ENTRÉE CLI (test rapide)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # ── INITIALISATION DJANGO (pour le mode CLI) ──
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.append(base_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "InfraContol.settings")
    
    try:
        import django
        django.setup()
        from django.conf import settings
        logger.info("Environnement Django initialisé avec succès.")
    except Exception as e:
        print(f"[!] Warning: Impossible d'initialiser Django : {e}")

    # Configuration du logging pour le mode CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Argument optionnel : subnet
    subnets = None
    if len(sys.argv) > 1:
        subnets = sys.argv[1:]
        print(f"[*] Scan ciblé sur : {subnets}")
    else:
        detected = detecter_reseaux_locaux()
        print(f"[*] Réseaux détectés : {detected}")
        subnets = detected

    # Lancer le scan
    resultats = scanner_reseau(subnets=subnets, scan_ports=True)

    # Affichage des résultats
    print("-" * 90)
    print(f"{'IP':<16} {'TYPE':<13} {'VENDOR':<12} {'OS':<25} {'MAC':<18} {'NOM'}")
    print("-" * 90)

    for r in resultats:
        os_short = r['os'][:24] if r['os'] else "?"
        mac_short = r['mac_address'] or "N/A"
        print(
            f"{r['adresse_ip']:<16} "
            f"{r['type_equipement']:<13} "
            f"{r['vendor']:<12} "
            f"{os_short:<25} "
            f"{mac_short:<18} "
            f"{r['nom']}"
        )

        if r['ports_ouverts']:
            ports_str = ", ".join(
                f"{p['port']}/{p['service']}" for p in r['ports_ouverts']
            )
            print(f"{'':>16} +- Ports: {ports_str}")

    print("-" * 90)
    print(f"Total : {len(resultats)} équipement(s) découvert(s)")
    print()

    # Proposer l'import Django si disponible
    try:
        import django
        print("[?] Voulez-vous importer dans Django ? (o/n) ", end="")
        choix = input().strip().lower()
        if choix in ("o", "oui", "y", "yes"):
            rapport = importer_decouvertes(resultats)
            print(f"[OK] Import terminé : {rapport}")
    except ImportError:
        print("[i] Django non disponible — import ignoré.")