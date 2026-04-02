from prometheus_client import Gauge, Counter

# =====================
# 🔢 Métriques système
# =====================
CPU_USAGE = Gauge(
    "equipement_cpu_usage",
    "CPU usage percentage",
    ["equipement"]
)

RAM_USAGE = Gauge(
    "equipement_ram_usage",
    "RAM usage percentage",
    ["equipement"]
)

DISK_USAGE = Gauge(
    "equipement_disk_usage",
    "Disk usage percentage",
    ["equipement"]
)

HEALTH_SCORE = Gauge(
    "equipement_health_score",
    "Health score (0-100)",
    ["equipement"]
)

# =====================
# 🚨 Incidents
# =====================
INCIDENTS_TOTAL = Counter(
    "equipement_incidents_total",
    "Total incidents detected",
    ["equipement", "type"]
)


from monitoring.prometheus_metrics import (
    CPU_USAGE,
    RAM_USAGE,
    DISK_USAGE,
    HEALTH_SCORE,
    INCIDENTS_TOTAL,
)

def publier_metrics_prometheus(equipement, stat):
    nom = equipement.nom

    if stat.cpu_usage is not None:
        CPU_USAGE.labels(equipement=nom).set(stat.cpu_usage)

    if stat.ram_usage is not None:
        RAM_USAGE.labels(equipement=nom).set(stat.ram_usage)

    if stat.disk_usage is not None:
        DISK_USAGE.labels(equipement=nom).set(stat.disk_usage)

    if stat.health_score is not None:
        HEALTH_SCORE.labels(equipement=nom).set(stat.health_score)