# discovery/utils.py
import ipaddress
import socket


def detecter_ip_locale():
    """
    Détecte l'IP locale réellement utilisée par la machine
    (méthode fiable cross-platform)
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Pas de connexion réelle, juste pour connaître l'IP source
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def detecter_reseau_local():
    """
    Détecte automatiquement le sous-réseau local du serveur Django.
    Ex:
      IP détectée : 192.168.1.34
      Réseau retourné : 192.168.1.0/24
    """
    ip_locale = detecter_ip_locale()

    if not ip_locale:
        return None

    # Sécurité : exclure loopback
    if ip_locale.startswith("127."):
        return None

    # Hypothèse raisonnable par défaut (réseau entreprise classique)
    try:
        reseau = ipaddress.ip_network(f"{ip_locale}/24", strict=False)
        return str(reseau)
    except ValueError:
        return None