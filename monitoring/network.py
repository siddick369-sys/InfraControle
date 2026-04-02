import subprocess
import re
import statistics
import platform
import logging
import socket
from typing import Tuple, Optional

logger = logging.getLogger("monitoring.network")

def collecter_ping_jitter(
    ip: str, 
    count: int = 10,  # Augmenté pour meilleure statistique jitter
    timeout: int = 2,
    interval: float = 0.2  # Délai entre pings pour éviter rate-limiting
) -> Tuple[Optional[float], Optional[float], float]:
    """
    Retourne (ping_ms, jitter_ms, packet_loss%)
    Compatible Windows/Linux/macOS avec gestion IPv4/IPv6.
    """
    if not ip:
        return None, None, 100.0

    # Validation IP (IPv4 ou IPv6)
    try:
        socket.getaddrinfo(ip, None)
    except socket.gaierror:
        logger.error(f"[PING] Adresse invalide: {ip}")
        return None, None, 100.0

    system = platform.system().lower()
    
    # Détection IPv6
    try:
        socket.inet_pton(socket.AF_INET6, ip)
        is_ipv6 = True
    except (socket.error, OSError):
        is_ipv6 = False

    # Construction commande
    if system == "windows":
        # Windows: -i interval en secondes (minimum 1s par défaut, -w timeout ms)
        cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000)]
        if is_ipv6:
            cmd.append("-6")
        cmd.append(str(ip))
        encoding = "cp850"
        errors = "replace"  # Mieux que 'ignore' pour debug
    elif system == "darwin":  # macOS
        cmd = ["ping", "-c", str(count), "-W", str(timeout), "-i", str(interval)]
        if is_ipv6:
            cmd = ["ping6"] + cmd[1:]
        cmd.append(str(ip))
        encoding = "utf-8"
        errors = "replace"
    else:  # Linux et autres Unix
        cmd = ["ping", "-c", str(count), "-W", str(timeout), "-i", str(interval)]
        if is_ipv6 and subprocess.run(["which", "ping6"], capture_output=True).returncode == 0:
            cmd[0] = "ping6"
        cmd.append(str(ip))
        encoding = "utf-8"
        errors = "replace"

    try:
        # Exécution sans fenêtre console (Windows)
        startupinfo = None
        if system == "windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=encoding,
            errors=errors,
            timeout=timeout * count + 5,  # Timeout global généreux
            startupinfo=startupinfo
        )
        
        output = process.stdout + process.stderr  # Certains pings écrivent sur stderr
        
        # --- PARSING PERTE (plus robuste) ---
        loss = 100.0
        
        # Patterns internationaux pour perte
        loss_patterns = [
            r"(\d+)%\s*(?:packet\s*)?loss",           # Anglais standard
            r"(\d+)%\s*(?:perte|perdus|perdidas)",    # Français/Espagnol
            r"(\d+)%\s*(?:de\s+)?perte",              # Français variant
            r"perte\s*(\d+)%",                        # Windows Français "(perte 0%)"
            r"received,\s*(\d+)%\s*loss",             # Format "X received, Y% loss"
            r"Success\s*rate\s*is\s*(\d+)\s*percent", # Cisco style
            r"(\d+)\s*received,\s*\d+\s*transmitted", # Linux alternatif (calcul inverse)
        ]
        
        for pattern in loss_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                if "Success rate" in pattern:
                    loss = 100.0 - float(match.group(1))  # Inverser pour Cisco
                elif "received" in pattern and "transmitted" in pattern:
                    # Calcul manuel si besoin
                    continue
                else:
                    loss = float(match.group(1))
                break

        # --- PARSING TEMPS (multi-format) ---
        times = []
        
        # Patterns pour temps de réponse
        time_patterns = [
            r"time[=<]?([\d\.]+)\s*ms",           # Standard: time=12.3ms
            r"temps[=<]?([\d\.]+)\s*ms",          # Français: temps=12ms
            r"dur[ée]e[=<]?([\d\.]+)\s*ms",      # Français alternatif
            r"tiempo[=<]?([\d\.]+)\s*ms",        # Espagnol
            r"rtt[=\s]+([\d\.]+)/",              # Format rtt min/avg/max
            r"round-trip[^=]*=\s*[\d\.]+/([\d\.]+)/",  # round-trip min/avg/max
            r"(\d+\.\d+)\s*ms\s*\(",             # Format avec parenthèses
            r"time[=<]?1\s*ms",                  # <1ms ou =1ms (Windows)
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    m = m[0] if m else None
                if m:
                    try:
                        val = float(m)
                        if 0 < val < 10000:  # Filtre valeurs aberrantes
                            times.append(val)
                    except ValueError:
                        continue
                else:
                    # Cas <1ms sans capture de groupe
                    times.append(0.5)

        # --- CALCUL STATISTIQUES ---
        ping_ms = None
        jitter_ms = None

        if times:
            # Filtrer outliers (optionnel mais recommandé pour réseau)
            if len(times) >= 4:
                # Méthode IQR pour outliers
                sorted_times = sorted(times)
                q1 = sorted_times[len(sorted_times)//4]
                q3 = sorted_times[3*len(sorted_times)//4]
                iqr = q3 - q1
                filtered = [t for t in times if q1 - 1.5*iqr <= t <= q3 + 1.5*iqr]
                if len(filtered) >= 2:
                    times = filtered
            
            ping_ms = round(statistics.median(times), 2)  # Médiane plus robuste que moyenne
            if len(times) >= 2:
                # Jitter = écart-type ou MAD (Median Absolute Deviation)
                try:
                    jitter_ms = round(statistics.stdev(times), 2)
                except statistics.StatisticsError:
                    jitter_ms = 0.0
        else:
            # Aucun temps parsé mais commande OK = probablement <1ms
            if process.returncode == 0 and loss < 100:
                ping_ms = 0.5
                jitter_ms = 0.0

        logger.debug(f"[PING] {ip}: ping={ping_ms}ms, jitter={jitter_ms}ms, loss={loss}%")
        return ping_ms, jitter_ms, loss

    except subprocess.TimeoutExpired:
        logger.warning(f"[PING] Timeout sur {ip}")
        return None, None, 100.0
    except Exception as e:
        logger.error(f"[PING] Erreur critique {ip}: {e}", exc_info=True)
        return None, None, 100.0