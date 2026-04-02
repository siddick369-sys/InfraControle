import socket
import ipaddress

def detecter_sous_reseau():
    """
    Détecte automatiquement le sous-réseau du serveur Django
    Ex: 192.168.1.0/24
    """
    hostname = socket.gethostname()
    ip_locale = socket.gethostbyname(hostname)

    try:
        reseau = ipaddress.ip_network(ip_locale + "/24", strict=False)
        return str(reseau)
    except Exception:
        return None