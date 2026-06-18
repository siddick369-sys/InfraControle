import logging
import os
import requests
from django.conf import settings
from django.db.models import Count, Avg
from monitoring.models import EquipementReseau, Incident

logger = logging.getLogger('reports.ai')

from decouple import config

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = config("GROQ_API_KEY", default=None)
GROQ_MODEL = config("GROQ_MODEL", default="llama-3.3-70b-versatile")

def collecter_donnees_brutes(date_debut, date_fin):
    """
    Collecte toutes les statistiques réseau pour la période donnée.
    """
    equipements = EquipementReseau.objects.all()
    total_equipements = equipements.count()
    
    # Statuts
    en_ligne = equipements.filter(statut="en ligne").count()
    hors_ligne = equipements.filter(statut="hors ligne").count()
    
    # Types
    types_stats = equipements.values('type_equipement').annotate(total=Count('id'))
    
    # Perfs moyennes
    perfs = EquipementReseau.objects.aggregate(
        moyenne_cpu=Avg('cpu_usage'),
        moyenne_ram=Avg('ram_usage')
    )
    
    # Incidents de la période (limités à 20 pour éviter le 413 Payload Too Large)
    incidents = Incident.objects.filter(
        date_debut__gte=date_debut, 
        date_debut__lte=date_fin
    ).order_by('-niveau', '-date_debut')[:20]
    
    incidents_details = []
    for inc in incidents:
        duree = "Non résolu"
        if inc.date_resolution:
            delta = inc.date_resolution - inc.date_debut
            duree = f"{delta.total_seconds() // 60} minutes"
            
        incidents_details.append({
            "equipement": inc.equipement.nom,
            "type_panne": inc.titre,
            "criticite": inc.niveau,
            "duree": duree,
            "statut": "Résolu" if inc.statut == "résolu" else "En cours",
            "action": inc.description or "Aucune",
            "date": inc.date_debut.strftime("%Y-%m-%d %H:%M")
        })

    donnees = {
        "periode": f"Du {date_debut} au {date_fin}",
        "synthese": {
            "total_equipements": total_equipements,
            "actifs_up": en_ligne,
            "inactifs_down": hors_ligne,
            "pourcentage_up": round((en_ligne/total_equipements*100), 2) if total_equipements > 0 else 0
        },
        "repartition_types": list(types_stats),
        "performances_moyennes": {
            "cpu": round(perfs['moyenne_cpu'] or 0, 2),
            "ram": round(perfs['moyenne_ram'] or 0, 2)
        },
        "incidents": incidents_details
    }
    return donnees

def generer_rapport_groq(date_debut, date_fin):
    """
    Formate le prompt et appelle le modèle Groq pour générer le rapport.
    """
    donnees_brutes = collecter_donnees_brutes(date_debut, date_fin)
    
    # Tronquer la chaîne pour éviter l'erreur 413 Payload Too Large
    donnees_str = str(donnees_brutes)
    if len(donnees_str) > 6000:
        donnees_str = donnees_str[:6000] + "... [TRONQUÉ]"
    
    prompt = f"""
Agis en tant que Responsable d'Infrastructure Réseau et Rédacteur Administratif expert. Ta tâche est de rédiger un rapport administratif complet, formel et structuré concernant l'état actuel de notre parc informatique et la situation générale du réseau, en te basant sur les données de monitoring que je vais te fournir.
Le rapport final doit être parfaitement formaté pour une lecture par la direction, clair, objectif, mais suffisamment précis techniquement. Format: Markdown.

Voici la structure obligatoire que le document doit respecter :
1. En-tête Administratif
Date et heure de génération du rapport.
Objet : Rapport de supervision et état de santé de l'infrastructure réseau.
Période couverte par le rapport.
2. Synthèse Exécutive (Vue d'ensemble)
Un résumé de haut niveau (2 à 3 paragraphes maximum) décrivant la situation générale actuelle du réseau.
Mention des faits marquants (stabilité globale, incidents majeurs résolus ou en cours).
3. État Actuel des Équipements (Inventaire et Statut)
Un résumé quantitatif : Nombre total d'équipements supervisés, pourcentage d'équipements fonctionnels (UP), hors ligne (DOWN).
Une répartition claire par catégorie (Routeurs, Switchs, Serveurs, Pare-feux, Points d'accès).
4. Historique des Incidents et Alertes (Le cas échéant)
Liste détaillée des pannes ou anomalies critiques détectées durant la période.
Pour chaque incident, précise : l'équipement concerné, la nature de la panne, la durée de l'interruption de service, et l'action corrective apportée.
5. Analyse des Performances et Métriques Clés
Bilan de l'utilisation de la bande passante et identification d'éventuels goulots d'étranglement ou latences anormales.
Synthèse de la charge des ressources critiques (utilisation CPU/Mémoire des équipements principaux).
6. Conclusion, Recommandations et Plan d'Action
Des recommandations concrètes pour optimiser l'architecture réseau ou prévenir les pannes futures.
Les opérations de maintenance préventive à planifier (ex: mises à jour de firmwares, remplacement de matériel vieillissant).

Ton ton doit être neutre, strictement professionnel et rassurant.

*** DONNÉES BRUTES DU SYSTÈME ***
{donnees_str}
"""

    logger.info(f"Appel Groq API pour le rapport du {date_debut} au {date_fin}...")
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY non configurée pour les rapports.")
        return "# Erreur de Configuration\nLa clé GROQ_API_KEY est manquante dans les paramètres."

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            },
            timeout=120
        )
        response.raise_for_status()
        res_json = response.json()
        contenu_rapport = res_json["choices"][0]["message"]["content"]
        logger.info("Rapport Groq généré avec succès.")
        return contenu_rapport
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport par Groq: {e}")
        return f"# Erreur de Génération\nL'intelligence artificielle n'a pas pu générer le rapport. Détail technique : {str(e)}"
