# aiengine/context.py
from django.utils import timezone
from datetime import timedelta

from monitoring.models import (
    Incident,
    StatReseau,
    WifiStat,
)

def construire_contexte_incident(incident):
    equipement = incident.equipement

    # ==========================
    # 🧾 INCIDENT
    # ==========================
    contexte = {
        "incident": {
            "id": incident.id,
            "titre": incident.titre,
            "description": incident.description,
            "statut": incident.statut,
            "date_detection": incident.date_debut.isoformat(),
            "nb_occurrences": Incident.objects.filter(
                equipement=equipement,
                titre=incident.titre
            ).count(),
        }
    }

    # ==========================
    # 🖥️ ÉQUIPEMENT
    # ==========================
    contexte["equipement"] = {
        "nom": equipement.nom,
        "type": equipement.type_equipement,
        "ip": equipement.adresse_ip,
        "statut": equipement.statut,
        "echec_consecutif": equipement.echec_consecutif,
        "derniere_verification": (
            equipement.derniere_verification.isoformat()
            if equipement.derniere_verification else None
        ),
    }

    # ==========================
    # 📊 MÉTRIQUES RÉSEAU
    # ==========================
    stats = (
        StatReseau.objects
        .filter(equipement=equipement)
        .order_by("-date_releve")
        .first()
    )

    if stats:
        contexte["metriques"] = {
            "cpu": stats.cpu_usage,
            "ram": stats.ram_usage,
            "disk": stats.disk_usage,
            "latence": stats.ping_ms,
            "packet_loss": stats.packet_loss,
            "temperature": stats.temperature_c,
        }

    # ==========================
    # 📶 WIFI
    # ==========================
    if hasattr(equipement, "wifi_ap"):
        wifi_stats = (
            WifiStat.objects
            .filter(ap=equipement.wifi_ap)
            .order_by("-date_releve")
            .first()
        )

        if wifi_stats:
            contexte["wifi"] = {
                "nb_clients": wifi_stats.nb_clients,
                "canal_sature": wifi_stats.canal_sature,
                "debit_total": wifi_stats.debit_total_mbps,
                "taux_erreur": wifi_stats.taux_erreur,
            }

    # ==========================
    # 🕰️ HISTORIQUE RÉCENT
    # ==========================
    incidents_recents = Incident.objects.filter(
        equipement=equipement,
        date_debut__gte=timezone.now() - timedelta(hours=24)
    ).exclude(id=incident.id)

    contexte["incidents_recents"] = [
        {
            "titre": i.titre,
            "statut": i.statut,
            "date": i.date_debut.isoformat(),
        }
        for i in incidents_recents
    ]

    return contexte