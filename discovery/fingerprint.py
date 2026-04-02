# discovery/fingerprinting.py
import socket
import subprocess
import re
import platform


def ping_ttl(ip):
    """
    Récupère le TTL d'une réponse ping (cross-platform)
    """
    system = platform.system().lower()
    count_flag = "-n" if system == "windows" else "-c"
    
    try:
        proc = subprocess.run(
            ["ping", count_flag, "1", ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3
        )
        # TTL case-insensitive pour Linux/Windows
        match = re.search(r"TTL[=:](\d+)", proc.stdout, re.IGNORECASE)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def port_ouvert(ip, port, timeout=1):
    """
    Vérifie si un port TCP est ouvert
    """
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def detecter_type_equipement(ip, hostname=""):
    """
    Détection intelligente sans authentification
    """
    score = {
        "serveur": 0,
        "routeur": 0,
        "switch": 0,
        "wifi": 0,
        "autre": 0,
    }

    # ========================
    # 🔹 TTL
    # ========================
    ttl = ping_ttl(ip)
    if ttl:
        if ttl <= 70:
            score["serveur"] += 2
        elif ttl <= 130:
            score["serveur"] += 1
        elif ttl >= 200:
            score["routeur"] += 2
            score["switch"] += 1

    # ========================
    # 🔹 Ports
    # ========================
    if port_ouvert(ip, 22):
        score["serveur"] += 2
    if port_ouvert(ip, 3389):
        score["serveur"] += 3
    if port_ouvert(ip, 80) or port_ouvert(ip, 443):
        score["routeur"] += 1
        score["wifi"] += 1
    if port_ouvert(ip, 161):
        score["switch"] += 2
        score["routeur"] += 2

    # ========================
    # 🔹 Hostname
    # ========================
    h = hostname.lower()
    if any(k in h for k in ["router", "gw", "gateway"]):
        score["routeur"] += 3
    if any(k in h for k in ["switch", "sw"]):
        score["switch"] += 3
    if any(k in h for k in ["ap", "wifi", "wlan"]):
        score["wifi"] += 3
    if any(k in h for k in ["srv", "server", "prod", "nas"]):
        score["serveur"] += 2

    # ========================
    # 🎯 Décision finale
    # ========================
    meilleur = max(score, key=score.get)
    return meilleur if score[meilleur] > 0 else "autre"