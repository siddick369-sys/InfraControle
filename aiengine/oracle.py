import logging
from django.utils import timezone
from django.db.models import Q
from monitoring.models import Incident, EquipementReseau, StatReseau
from .client import appeler_ia

logger = logging.getLogger("ai")

class OracleEngine:
    """
    Moteur de l'Oracle IA - Analyse l'état du réseau et fournit des recommandations.
    """

    @staticmethod
    def get_network_context():
        """
        Récupère un résumé technique de l'état actuel du réseau.
        """
        now = timezone.now()
        incidents_ouverts = Incident.objects.filter(statut='ouvert').count()
        equipements_hors_ligne = EquipementReseau.objects.filter(statut='hors ligne').count()
        
        # Récupérer les 5 derniers incidents critiques
        derniers_incidents = Incident.objects.filter(statut='ouvert').order_by('-date_debut')[:5]
        incidents_txt = "\n".join([f"- {i.niveau.upper()}: {i.titre} sur {i.equipement.nom}" for i in derniers_incidents])

        import requests
        prom_context = ""
        try:
            # Query Prometheus (if available) for available memory as a "Wow Effect" Live Metric
            resp = requests.get("http://prometheus:9090/api/v1/query", params={"query": "node_memory_MemAvailable_bytes / 1024 / 1024 / 1024"}, timeout=2)
            if resp.status_code == 200:
                data = resp.json().get('data', {}).get('result', [])
                if data:
                    prom_context = f"\n- RAM Disponible sur les nœuds vus par Prometheus : {round(float(data[0]['value'][1]), 2)} GB"
        except Exception:
            pass

        # Récupérer la latence moyenne des équipements actifs
        stats_recentes = StatReseau.objects.filter(date_releve__gte=now - timezone.timedelta(minutes=15))
        avg_latency = 0
        if stats_recentes.exists():
            latencies = [s.ping_ms for s in stats_recentes if s.ping_ms is not None]
            if latencies:
                avg_latency = sum(latencies) / len(latencies)

        context = f"""
ÉTAT ACTUEL DU RÉSEAU :
- Incidents ouverts : {incidents_ouverts}
- Équipements hors ligne : {equipements_hors_ligne}
- Latence moyenne (15 min) : {avg_latency:.2f} ms{prom_context}

DERNIERS INCIDENTS :
{incidents_txt if incidents_txt else "Aucun incident critique récent."}
"""
        return context

    @staticmethod
    def chat(user_message, history=None):
        """
        Traite un message utilisateur et retourne une réponse de l'Oracle.
        """
        network_context = OracleEngine.get_network_context()
        
        prompt = f"""
Tu es "l'Oracle", un chatbot intelligent intégré à InfraControl, une plateforme de supervision réseau avancée.
Ton rôle est d'aider les techniciens à comprendre l'état du réseau, diagnostiquer des pannes et fournir des recommandations.

CONTEXTE SYSTÈME :
{network_context}

INSTRUCTIONS SPÉCIALES (GROQ IA WOW EFFECTS) :
1. Sois technique mais concis. Si l'on demande un scan de sécurité réseau (ex: port scan, CVE), génère obligatoirement une commande dans un bloc bash (ex: ```bash\nnmap -sV cible\n```).
2. Si l'on te demande de créer un script d'automatisation ou un Playbook Ansible, génère-le obligatoirement dans un bloc ```yaml\n...\n``` pour que l'IHM le transforme en fichier.
3. Si l'on te demande de dessiner une topologie réseau ou de faire un diagramme, tape-le en texte sous forme d'art ASCII enveloppé dans un bloc ```ascii\n...\n```.
4. ROUTAGE DOM : Si l'utilisateur te demande d'ouvrir une page ou d'aller sur un module, termine ta réponse par un bloc ```navigate\nLE_LIEN\n```. Utilise EXCLUSIVEMENT ces liens stricts:
- Tableau de bord: `/monitoring/dashboard/`
- Topologie Réseau: `/monitoring/network/map/`
- Incidents: `/monitoring/incidents/`
- Equipements: `/monitoring/equipements/`
- Audit WiFi: `/wifi/`
- Découverte/Scan: `/discovery/`
- Rapports: `/reports/`
- Remédiation: `/remediation/`
5. PROFILAGE PSYCHOLOGIQUE : Si la situation traitée dans le message de l'utilisateur ou le contexte est critique/urgente, insère le tag "[SEVERITY: CRITICAL]" dans ta réponse. Sinon, insère "[SEVERITY: NORMAL]". Ce tag sera utilisé par le Frontend pour changer sa couleur et l'allure de sa voix synthétique.
6. Si l'utilisateur te transmet un fichier texte/log en tête de son message, analyse-le en profondeur.

7. Si on te demande d'exporter ou de faire un rapport PDF de la conversation, ajoute "[ACTION: EXPORT_PDF]" dans ta réponse.
8. Si l'utilisateur demande "dessine un graphique", "montre-moi un graphe" ou parle de comparaison chiffrée, génère UNIQUEMENT les valeurs brutes séparées par des virgules dans un bloc ```svg-chart\nvaleur1,valeur2,valeur3\n``` (ex: 30,50,90). Le frontend rendra un graphique animé.

MESSAGE DE L'UTILISATEUR :
{user_message}

RÉPONSE DE L'ORACLE :
"""
        return appeler_ia(prompt)
