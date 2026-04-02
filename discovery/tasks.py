# discovery/tasks.py
from celery import shared_task
from django.utils import timezone
import logging

from .models import EquipementDecouvert
from .alerts import envoyer_alerte_decouverte
from .scanner import scanner_reseau

logger = logging.getLogger("discovery")


@shared_task(
    name="discovery.tasks.enregistrer_ip",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 10},
)
def enregistrer_ip(data):
    ip = data.get("ip")
    if not ip:
        logger.warning(f"[DISCOVERY] IP manquante dans le payload: {data}")
        return "ip_manquante"

    logger.info(f"[DISCOVERY] Tentative d'enregistrement de l'IP: {ip}")
    try:
        equipement, created = EquipementDecouvert.objects.update_or_create(
            adresse_ip=ip,
            defaults={
                "hostname": data.get("hostname") or "",
                "type_detecte": data.get("type") or "inconnu",
                "mac_addresse": data.get("mac") or "",
                "systeme_exploitation": data.get("os") or "inconnu",
                "vu_le": timezone.now(),
            }
        )
        logger.info(f"[DISCOVERY] {'Créé' if created else 'Mis à jour'}: {ip}")
    except Exception as e:
        logger.error(f"[DISCOVERY] Erreur lors de l'enregistrement de {ip}: {e}")
        raise e

    # 📧 EMAIL UNIQUEMENT SI :
    # - nouvel équipement
    # - pas encore ajouté
    # - email jamais envoyé
    if created or not equipement.ajoute:
        if not equipement.email_envoye:
            logger.info(f"[DISCOVERY] Envoi d'alerte pour {ip}")
            ok = envoyer_alerte_decouverte(equipement)
            if ok:
                equipement.email_envoye = True
                equipement.save(update_fields=["email_envoye"])

    return "ok"


@shared_task(
    name="discovery.tasks.scanner_reseau_auto",
    time_limit=1800,  # Augmenté à 30 minutes pour les réseaux /16
    soft_time_limit=1500,
)
def scanner_reseau_auto(subnets=None):
    """
    🔍 Scan du réseau local (Deep Discovery) avec persistance incrémentale.
    """
    total_found = [0]  # Utilisation d'une liste pour mutabilité dans le callback

    def discovery_callback(progress, ip, result):
        if result:
            payload = {
                "ip": result.get("adresse_ip"),
                "hostname": result.get("hostname") or "",
                "type": result.get("type_equipement") or "autre",
                "mac": result.get("mac_address") or "",
                "os": result.get("os") or "Inconnu",
            }
            enregistrer_ip(payload)
            total_found[0] += 1
            logger.info(f"[DISCOVERY] [PROGRESS {progress}%] IP enregistrée: {ip}")

    # Lancement du scan avec le callback
    scanner_reseau(subnets=subnets, callback=discovery_callback)

    logger.info(f"[DISCOVERY] Scan automatique terminé. {total_found[0]} équipements découverts.")

    return {
        "reseau_scane": True,
        "equipements_detectecs": total_found[0],
    }

    
    

