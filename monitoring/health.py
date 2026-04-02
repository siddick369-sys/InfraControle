import logging

logger = logging.getLogger("monitoring.health")

CRITICAL_THRESHOLDS = {
    "cpu": 90,
    "ram": 90,
    "disk": 95,
    "temp": 75,
    "packet_loss": 5,
}

WARNING_THRESHOLDS = {
    "cpu": 80,
    "ram": 80,
    "disk": 85,
    "temp": 65,
    "packet_loss": 2,
}


def penalite(valeur, warning, critical, p_warning, p_critical):
    """
    Calcule une pénalité progressive
    """
    if valeur is None:
        return 0

    try:
        valeur = float(valeur)
    except Exception:
        return 0

    if valeur >= critical:
        return p_critical
    elif valeur >= warning:
        return p_warning
    return 0


def calculer_health_score(stat):
    """
    🧠 Score de santé réseau intelligent (0 à 100)
    - Tolérant aux valeurs None
    - Pénalités progressives
    - Loggable
    """
    if not stat:
        return 0

    if not stat.disponible:
        return 0

    score = 100
    details = []

    score -= penalite(stat.cpu_usage, 80, 95, 15, 30)
    score -= penalite(stat.ram_usage, 80, 95, 15, 30)
    score -= penalite(stat.disk_usage, 85, 98, 15, 30)
    score -= penalite(stat.temperature_c, 65, 80, 10, 25)
    score -= penalite(stat.packet_loss, 2, 8, 10, 25)

    # Bonus négatif si erreurs réseau
    if stat.errors_in and stat.errors_in > 0:
        score -= min(stat.errors_in * 2, 15)

    if stat.errors_out and stat.errors_out > 0:
        score -= min(stat.errors_out * 2, 15)

    score = max(int(score), 0)

    logger.info(
        f"[HEALTH] {stat.equipement.nom} → score={score}"
    )

    return score