import subprocess
import platform
import socket
import ipaddress

def ping_ip(ip):
    system = platform.system().lower()

    cmd = ["ping", "-n", "1", "-w", "300"] if system == "windows" else ["ping", "-c", "1", "-W", "1"]
    cmd.append(str(ip))

    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def scanner_reseau_local(cidr):
    """
    Scan le réseau local via ping
    """
    reseau = ipaddress.ip_network(cidr, strict=False)
    resultats = []

    for ip in reseau.hosts():
        if ping_ip(ip):
            try:
                hostname = socket.gethostbyaddr(str(ip))[0]
            except Exception:
                hostname = ""

            resultats.append({
                "ip": str(ip),
                "hostname": hostname,
                "type": "inconnu",
            })

    return resultats