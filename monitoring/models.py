from django.db import models

# Create your models here.


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings
import base64, random, string


# ================================
# 🧠 1️⃣ UTILITAIRE DE CHIFFREMENT SSH
# ================================

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
import logging

logger = logging.getLogger("monitoring.crypto")


class CryptoManager:
    """
    Gère le chiffrement/déchiffrement avec gestion d'erreurs
    """

    @staticmethod
    def _get_fernet():
        """Récupère l'instance Fernet"""
        if not hasattr(settings, 'FERNET_KEY') or not settings.FERNET_KEY:
            raise ValueError("FERNET_KEY non configurée dans settings")
        return Fernet(settings.FERNET_KEY)

    @staticmethod
    def encrypt(text):
        """
        Chiffre un texte
        """
        if not text:
            return None
        
        try:
            fernet = CryptoManager._get_fernet()
            return fernet.encrypt(text.encode()).decode()
        except Exception as e:
            logger.error(f"[CRYPTO] Erreur chiffrement: {e}")
            return None

    @staticmethod
    def decrypt(token):
        """
        Déchiffre un token avec gestion d'erreurs
        """
        if not token:
            return None
        
        try:
            fernet = CryptoManager._get_fernet()
            return fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            logger.error(f"[CRYPTO] Token invalide - clé changée ou données corrompues")
            return None
        except Exception as e:
            logger.error(f"[CRYPTO] Erreur déchiffrement: {e}")
            return None

    @staticmethod
    def decrypt_or_default(token, default=None):
        """
        Déchiffre avec valeur par défaut si échec
        """
        result = CryptoManager.decrypt(token)
        return result if result is not None else default

    @staticmethod
    def regenerate_key():
        """
        Génère une nouvelle clé Fernet (à utiliser avec précaution)
        """
        new_key = Fernet.generate_key().decode()
        logger.warning(f"[CRYPTO] Nouvelle clé générée: {new_key[:20]}...")
        return new_key
# ================================
# 🌐 2️⃣ ÉQUIPEMENTS RÉSEAU
# ================================

class EquipementReseau(models.Model):
    TYPE_CHOICES = [
        ('routeur', 'Routeur'),
        ('switch', 'Switch'),
        ('serveur', 'Serveur Linux'),
        ('serveur_win', 'Serveur Windows'),
        ('pc_win', 'PC Windows'),
        ('parefeu', 'Pare-feu'),
        ('wifi', 'Point d\'accès Wi-Fi'),
        ('autre', 'Autre'),
    ]

    nom = models.CharField(max_length=100)
    type_equipement = models.CharField(max_length=20, choices=TYPE_CHOICES)
    adresse_ip = models.GenericIPAddressField()
    echec_consecutif = models.PositiveIntegerField(default=0)
    port_ssh = models.PositiveIntegerField(default=22)
    utilisateur_ssh = models.CharField(max_length=100, blank=True, null=True)
    mot_de_passe_ssh_chiffre = models.TextField(help_text="Mot de passe SSH chiffré avec Fernet",null=True,blank=True)
    cle_publique = models.TextField(blank=True, null=True, help_text="Clé publique SSH si utilisée")
    description = models.TextField(blank=True, null=True)
    localisation = models.CharField(max_length=255, blank=True, null=True)
    alertes_email_active = models.BooleanField(
        default=True,
        help_text="Autoriser l'envoi d'alertes email pour cet équipement"
    )

    actif = models.BooleanField(default=True, help_text="Permet de désactiver la supervision de cet équipement")
    derniere_verification = models.DateTimeField(blank=True, null=True)
    statut = models.CharField(
        max_length=20,
        choices=[
            ('en ligne', '🟢 En ligne'),
            ('hors ligne', '🔴 Hors ligne'),
            ('inconnu', '⚪ Inconnu')
        ],
        default='inconnu'
    )

    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)
    cpu_usage = models.FloatField(null=True, blank=True)
    utilisateur = models.CharField(max_length=50, help_text="Nom d'utilisateur SSH, ex: ubuntu",default="sasu")
    mot_de_passe = models.CharField(max_length=100, help_text="Mot de passe SSH",default="sasu")
    ram_usage = models.FloatField(null=True, blank=True)
    disk_usage = models.FloatField(null=True, blank=True)
    network_bandwidth = models.FloatField(null=True, blank=True)
    latence = models.FloatField(null=True, blank=True)
    snmp_community = models.CharField(
        max_length=100, 
        default='public', 
        blank=True, 
        null=True,
        help_text="Communauté SNMP (ex: public, private)"
    )
    derniere_alerte_sante = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date du dernier envoi d'email de santé (pour limitation 2/h)"
    )

    # 📍 Topologie
    pos_x = models.FloatField(null=True, blank=True)
    pos_y = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.nom} ({self.adresse_ip})"

    # Récupère le mot de passe SSH déchiffré
    
    logger = logging.getLogger("monitoring.models")
    @property
    def mot_de_passe_ssh(self):
        """
        Retourne le mot de passe déchiffré ou None si impossible
        """
        try:
            return CryptoManager.decrypt(self.mot_de_passe_ssh_chiffre)
        except Exception as e:
            logger.error(f"[EQUIPEMENT] {self.adresse_ip}: Erreur déchiffrement mot de passe: {e}")
            return None
    
    def set_mot_de_passe_ssh(self, password):
        """
        Chiffre et stocke le mot de passe
        """
        self.mot_de_passe_ssh_chiffre = CryptoManager.encrypt(password)
    
    def has_valid_ssh_password(self):
        """
        Vérifie si le mot de passe est valide (déchiffrable)
        """
        return self.mot_de_passe_ssh is not None
    class Meta:
        verbose_name = "Équipement réseau"
        verbose_name_plural = "Équipements réseau"
        ordering = ['nom']


# ================================
# ⚙️ 3️⃣ COMMANDES RÉSEAU (actions rapides)
# ================================
class CommandeAutomatique(models.Model):
    """
    Représente une commande ou un ensemble de commandes réseau exécutables à distance via SSH.
    Peut être simple ('reboot') ou complexe (script multi-lignes).
    """
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # ✅ supporte plusieurs lignes (séparées par des \n)
    contenu = models.TextField(help_text="Commandes SSH à exécuter (séparées par des sauts de ligne)")
    
    # ✅ facultatif : certaines commandes ne concernent que certains types d’équipements
    applicable_pour = models.ManyToManyField(
        'EquipementReseau',
        blank=True,
        related_name='commandes_applicables'
    )
    
    OS_CHOICES = [
        ('all', 'Tous (Universel)'),
        ('linux', 'Linux Uniquement'),
        ('windows', 'Windows Uniquement')
    ]
    os_cible = models.CharField(
        max_length=10, 
        choices=OS_CHOICES, 
        default='linux',
        help_text="Système d'exploitation cible pour cette commande."
    )
    
    confirmation_requise = models.BooleanField(default=True)
    critique = models.BooleanField(default=False)
    
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom} ({'critique' if self.critique else 'standard'})"

    def commandes_split(self):
        """Retourne la liste des lignes de commandes"""
        return [cmd.strip() for cmd in self.contenu.splitlines() if cmd.strip()]
    
    

# ================================
# 🚨 4️⃣ INCIDENTS / ALERTES
# ================================
class Incident(models.Model):
    """Historique des anomalies détectées (pannes, lenteurs, surcharges, etc.)."""
    equipement = models.ForeignKey(EquipementReseau, on_delete=models.CASCADE, related_name='incidents')
    titre = models.CharField(max_length=255)
    notifie = models.BooleanField(default=False)
    derniere_detection = models.DateTimeField(default=timezone.now)
    
    description = models.TextField(blank=True, null=True)
    niveau = models.CharField(
        max_length=20,
        choices=[('info', 'Info'), ('avertissement', 'Avertissement'), ('critique', 'Critique')],
        default='info'
    )
    statut = models.CharField(
        max_length=20,
        choices=[('ouvert', 'Ouvert'), ('résolu', 'Résolu')],
        default='ouvert'
    )
    
    CATEGORIE_CHOICES = [
        ('sante', 'Santé'),
        ('securite', 'Sécurité'),
        ('decouverte', 'Découverte'),
        ('autre', 'Autre'),
    ]
    categorie = models.CharField(
        max_length=20,
        choices=CATEGORIE_CHOICES,
        default='autre'
    )

    analyse_ia_en_cours = models.BooleanField(default=False)
    date_debut = models.DateTimeField(default=timezone.now)
    date_resolution = models.DateTimeField(blank=True, null=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"[{self.niveau}] {self.titre} - {self.equipement.nom}"

    def marquer_resolu(self):
        self.statut = 'résolu'
        self.date_resolution = timezone.now()
        self.save()


# --- 🔔 Signal pour les notifications en direct ---
from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

@receiver(post_save, sender=Incident)
def notifier_creation_incident(sender, instance, created, **kwargs):
    """Émet un événement WebSocket quand un incident est créé."""
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "incidents",  # groupe WebSocket global
            {
                "type": "nouvel_incident",
                "id": instance.id,
                "titre": instance.titre,
                "niveau": instance.niveau,
                "equipement": instance.equipement.nom,
                "date": instance.date_debut.strftime("%d/%m/%Y %H:%M"),
            },
        )

# ================================
# 🧾 5️⃣ JOURNAL D’ACTIVITÉS RÉSEAU
# ================================

class JournalReseau(models.Model):
    """
    Trace toutes les opérations exécutées (manuelles ou automatiques)
    """
    equipement = models.ForeignKey(EquipementReseau, on_delete=models.SET_NULL, null=True, blank=True)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    commande_executee = models.TextField(blank=True, null=True)
    resultat = models.CharField(max_length=100, blank=True, null=True)
    sortie_ssh = models.TextField(blank=True, null=True)
    date_action = models.DateTimeField(auto_now_add=True)
    ip_utilisateur = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ['-date_action']

    def __str__(self):
        return f"{self.action} sur {self.equipement} ({self.date_action.strftime('%d/%m %H:%M')})"


# ================================
# 📊 6️⃣ HISTORIQUE DES MESURES (PING, LATENCE, ETC.)
# ================================
from django.db import models
from django.utils import timezone

class StatReseau(models.Model):
    equipement = models.ForeignKey(
        EquipementReseau,
        on_delete=models.CASCADE,
        related_name="stats"
    )

    # 🕒 Horodatage
    date_releve = models.DateTimeField(default=timezone.now)

    # 🌐 Disponibilité & latence
    disponible = models.BooleanField(default=True)
    ping_ms = models.FloatField(null=True, blank=True)
    jitter_ms = models.FloatField(null=True, blank=True)
    packet_loss = models.FloatField(null=True, blank=True, help_text="% de paquets perdus")

    # 🧠 CPU
    cpu_usage = models.FloatField(null=True, blank=True)
    cpu_load_1m = models.FloatField(null=True, blank=True)
    cpu_load_5m = models.FloatField(null=True, blank=True)
    anomalies = models.TextField(
        null=True, 
        blank=True, 
        help_text="Liste des anomalies détectées par l'analyse des logs"
    )

    # 💾 Mémoire
    ram_usage = models.FloatField(null=True, blank=True)
    ram_total_mb = models.IntegerField(null=True, blank=True)
    ram_used_mb = models.IntegerField(null=True, blank=True)

    # 💽 Disque
    disk_usage = models.FloatField(null=True, blank=True)
    disk_read_mb = models.FloatField(null=True, blank=True)
    disk_write_mb = models.FloatField(null=True, blank=True)
    inode_usage = models.FloatField(null=True, blank=True)

    # 🌐 Réseau
    bandwidth_in_mbps = models.FloatField(null=True, blank=True)
    bandwidth_out_mbps = models.FloatField(null=True, blank=True)
    errors_in = models.IntegerField(null=True, blank=True)
    errors_out = models.IntegerField(null=True, blank=True)
    drops_in = models.IntegerField(null=True, blank=True)
    drops_out = models.IntegerField(null=True, blank=True)

    # 🌡️ Matériel (SNMP / capteurs)
    temperature_c = models.FloatField(null=True, blank=True)
    fan_status = models.BooleanField(null=True, blank=True)
    power_supply_status = models.BooleanField(null=True, blank=True)

    # 📈 Qualité globale (score synthétique)
    health_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="Score global 0–100 calculé",
        default=100
    )
    alerte_envoyee = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date_releve"]
        indexes = [
            models.Index(fields=["equipement", "date_releve"]),
        ]

    def __str__(self):
        return f"{self.equipement.nom} @ {self.date_releve.strftime('%d/%m %H:%M:%S')}"

# ================================
# 🧰 7️⃣ OUTIL DE TEST / DÉMO (optionnel)
# ================================

def generate_demo_data():
    """
    Crée quelques équipements fictifs pour tests.
    """
    from django.contrib.auth.models import User
    user = User.objects.first()
    equipements = [
        ("Routeur principal", "routeur", "192.168.1.1"),
        ("Serveur web", "serveur", "192.168.1.10"),
        ("Switch étage 2", "switch", "192.168.2.5"),
    ]
    for nom, typ, ip in equipements:
        e = EquipementReseau(
            nom=nom,
            type_equipement=typ,
            adresse_ip=ip,
            utilisateur_ssh="admin",
            localisation="Salle serveur",
            cree_par=user,
        )
        e.set_mot_de_passe_ssh("admin123")
        e.save()
        
        
        
class HistoriqueConnexion(models.Model):
    RESULTAT_CHOICES = [
        ("succès", "Succès"),
        ("échec", "Échec"),
        ("avertissement", "Avertissement"),
    ]

    equipement = models.ForeignKey(EquipementReseau, on_delete=models.CASCADE, related_name="connexions")
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255, help_text="Type d’action (connexion, exécution de commande, etc.)")
    resultat = models.CharField(max_length=20, choices=RESULTAT_CHOICES, default="succès")
    ip_source = models.GenericIPAddressField(blank=True, null=True)
    details = models.TextField(blank=True, null=True, help_text="Sortie brute ou erreur SSH.")
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_action"]
        verbose_name = "Historique de connexion"
        verbose_name_plural = "Historiques des connexions"

    def __str__(self):
        return f"{self.equipement.nom} - {self.action} ({self.resultat})"
    
class LienReseau(models.Model):
    TYPE_LIEN = [
        ("ethernet", "Ethernet"),
        ("fibre", "Fibre"),
        ("vpn", "VPN"),
    ]

    source = models.ForeignKey(
        EquipementReseau,
        related_name="liens_sortants",
        on_delete=models.CASCADE
    )
    destination = models.ForeignKey(
        EquipementReseau,
        related_name="liens_entrants",
        on_delete=models.CASCADE
    )

    interface_source = models.CharField(max_length=50)
    interface_destination = models.CharField(max_length=50)

    type_lien = models.CharField(
        max_length=20,
        choices=TYPE_LIEN,
        default="ethernet"
    )

    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.source.nom} → {self.destination.nom}"
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class TentativeAccesCritique(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="tentatives_critiques")
    nombre_tentatives = models.PositiveIntegerField(default=0)
    derniere_tentative = models.DateTimeField(default=timezone.now)
    bloque_jusqua = models.DateTimeField(null=True, blank=True)

    def incrementer(self):
        self.nombre_tentatives += 1
        self.derniere_tentative = timezone.now()
        self.save()

    def reinitialiser(self):
        self.nombre_tentatives = 0
        self.derniere_tentative = timezone.now()
        self.bloque_jusqua = None
        self.save()

    def est_bloque(self):
        if self.bloque_jusqua and timezone.now() < self.bloque_jusqua:
            return True
        return False

    def bloquer_24h(self):
        self.bloque_jusqua = timezone.now() + timedelta(hours=24)
        self.save()
        
        
        
from django.db import models
from django.utils import timezone

class TacheMonitoring(models.Model):
    nom = models.CharField(max_length=255)
    statut = models.CharField(max_length=50, default="en attente")  # ex: en cours, succès, échec
    resultat = models.JSONField(null=True, blank=True)
    message = models.TextField(blank=True)
    date_execution = models.DateTimeField(default=timezone.now)
    duree = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-date_execution"]

    def __str__(self):
        return f"{self.nom} ({self.statut})"

    
class Maintenance(models.Model):
    equipement = models.ForeignKey(
        EquipementReseau,
        on_delete=models.CASCADE,
        related_name="maintenances"
    )
    debut = models.DateTimeField()
    fin = models.DateTimeField()
    active = models.BooleanField(default=True)
    raison = models.TextField(blank=True)
    cree_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True
    )

    def __str__(self):
        return f"Maintenance {self.equipement.nom} ({self.debut} → {self.fin})"
    


class WifiAccessPoint(models.Model):
    equipement = models.OneToOneField(
        EquipementReseau,
        on_delete=models.CASCADE,
        related_name="wifi_ap"
    )

    fabricant = models.CharField(max_length=100, blank=True)
    modele = models.CharField(max_length=100, blank=True)
    version_firmware = models.CharField(max_length=100, blank=True)

    mode_gestion = models.CharField(
        max_length=20,
        choices=[
            ("standalone", "Standalone"),
            ("controller", "Géré par contrôleur"),
            ("cloud", "Cloud"),
        ],
        default="standalone"
    )

    adresse_mac = models.CharField(max_length=17, unique=True)

    nb_clients_max = models.PositiveIntegerField(default=50)

    actif = models.BooleanField(default=True)
    dernier_scan = models.DateTimeField(null=True, blank=True)
    etat = models.CharField(
    max_length=20,
    choices=[
        ("ok", "OK"),
        ("alerte", "Alerte"),
        ("maintenance", "Maintenance"),
        ("offline", "Hors ligne"),
    ],
    default="ok"
)

    def __str__(self):
        return f"AP {self.equipement.nom}"

class WifiRadio(models.Model):
    ap = models.ForeignKey(
        WifiAccessPoint,
        on_delete=models.CASCADE,
        related_name="radios"
    )
    canal_auto = models.BooleanField(
    default=True,
    help_text="Autoriser le changement automatique de canal"
)

    bande = models.CharField(
        max_length=10,
        choices=[
            ("2.4", "2.4 GHz"),
            ("5", "5 GHz"),
            ("6", "6 GHz"),
        ]
    )

    canal = models.PositiveIntegerField()
    largeur_canal_mhz = models.PositiveIntegerField(default=20)

    puissance_tx_dbm = models.IntegerField()
    bruit_dbm = models.IntegerField(null=True, blank=True)

    radio_active = models.BooleanField(default=True)

    taux_utilisation = models.FloatField(
        null=True, blank=True,
        help_text="Utilisation radio (%)"
    )

    def __str__(self):
        return f"{self.ap} — {self.bande} GHz"
class WifiSSID(models.Model):
    nom = models.CharField(max_length=100)
    commandes_interdites = models.JSONField(
    blank=True,
    null=True,
    help_text="Actions interdites sur ce SSID"
)

    securite = models.CharField(
        max_length=30,
        choices=[
            ("open", "Ouvert"),
            ("wpa2", "WPA2-PSK"),
            ("wpa3", "WPA3-SAE"),
            ("enterprise", "WPA2/WPA3-Enterprise"),
        ]
    )

    vlan = models.PositiveIntegerField()
    isolation_clients = models.BooleanField(default=False)

    qos_profile = models.CharField(
        max_length=50,
        blank=True,
        help_text="Profil QoS (VoIP, invité, critique…)"
    )

    actif = models.BooleanField(default=True)

    radios = models.ManyToManyField(
        WifiRadio,
        related_name="ssids",
        blank=True
    )

    def __str__(self):
        return f"SSID {self.nom}"
class WifiClient(models.Model):
    mac = models.CharField(max_length=17)
    ip = models.GenericIPAddressField(null=True, blank=True)

    fabricant = models.CharField(max_length=100, blank=True)
    type_device = models.CharField(
        max_length=50,
        choices=[
            ("pc", "PC"),
            ("mobile", "Mobile"),
            ("iot", "IoT"),
            ("autre", "Autre"),
        ],
        default="autre"
    )
    intrus = models.BooleanField(
    default=False,
    help_text="Client détecté comme suspect"
)

    ssid = models.ForeignKey(
        WifiSSID,
        on_delete=models.SET_NULL,
        null=True
    )

    radio = models.ForeignKey(
        WifiRadio,
        on_delete=models.SET_NULL,
        null=True
    )

    rssi = models.IntegerField(help_text="Signal (dBm)")
    snr = models.IntegerField(null=True, blank=True)

    tx_rate_mbps = models.FloatField(null=True, blank=True)
    rx_rate_mbps = models.FloatField(null=True, blank=True)

    roaming = models.BooleanField(default=False)

    connecte_depuis = models.DateTimeField()
    dernier_paquet = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.mac} @ {self.ssid}"
class WifiStat(models.Model):
    ap = models.ForeignKey(WifiAccessPoint, on_delete=models.CASCADE)
    radio = models.ForeignKey(WifiRadio, on_delete=models.CASCADE)

    date_releve = models.DateTimeField(default=timezone.now)

    nb_clients = models.PositiveIntegerField()
    debit_total_mbps = models.FloatField()

    taux_erreur = models.FloatField(null=True, blank=True)
    taux_retry = models.FloatField(null=True, blank=True)

    canal_sature = models.BooleanField(default=False)

    def __str__(self):
        return f"Stats {self.ap} {self.radio.bande}"    
class WifiIncident(models.Model):
    ap = models.ForeignKey(WifiAccessPoint, on_delete=models.CASCADE)
    radio = models.ForeignKey(WifiRadio, null=True, blank=True, on_delete=models.SET_NULL)
    ssid = models.ForeignKey(WifiSSID, null=True, blank=True, on_delete=models.SET_NULL)

    type_incident = models.CharField(
        max_length=50,
        choices=[
            ("canal_sature", "Canal saturé"),
            ("interference", "Interférence"),
            ("debit_faible", "Débit faible"),
            ("auth_fail", "Échec authentification"),
            ("radio_down", "Radio inactive"),
        ]
    )
    action_appliquee = models.CharField(
    max_length=200,
    blank=True
)

    description = models.TextField()
    date_detection = models.DateTimeField(auto_now_add=True)
    resolu = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.type_incident} — {self.ap}"
    
    
    
class WifiRecommendation(models.Model):
    ap = models.ForeignKey(WifiAccessPoint, on_delete=models.CASCADE)
    radio = models.ForeignKey(WifiRadio, null=True, blank=True, on_delete=models.SET_NULL)
    ssid = models.ForeignKey(WifiSSID, null=True, blank=True, on_delete=models.SET_NULL)

    type_recommandation = models.CharField(
        max_length=50,
        choices=[
            ("canal", "Changement de canal"),
            ("puissance", "Ajustement puissance"),
            ("equilibrage", "Équilibrage clients"),
            ("securite", "Sécurité"),
            ("performance", "Performance"),
        ]
    )

    message = models.TextField()
    gravite = models.IntegerField(
        default=3,
        help_text="1=info, 3=important, 5=critique"
    )

    justification = models.TextField()
    cree_le = models.DateTimeField(auto_now_add=True)
    appliquee = models.BooleanField(default=False)

    def __str__(self):
        return f"Reco {self.type_recommandation} – {self.ap}"
    
    
class ConfigurationEquipement(models.Model):
    equipement = models.ForeignKey(
        EquipementReseau,
        on_delete=models.CASCADE,
        related_name="configurations"
    )

    nom = models.CharField(max_length=150)
    type_config = models.CharField(
        max_length=50,
        choices=[
            ("dhcp", "DHCP"),
            ("dns", "DNS"),
            ("wifi", "Wi-Fi"),
            ("firewall", "Firewall"),
            ("vlan", "VLAN"),
            ("autre", "Autre"),
        ]
    )

    contenu = models.TextField(
        help_text="Contenu du fichier de configuration"
    )

    chemin_destination = models.CharField(
        max_length=255,
        help_text="Ex: /etc/dhcp/dhcpd.conf"
    )

    redemarrage_service = models.CharField(
        max_length=100,
        blank=True,
        help_text="Service à redémarrer après application"
    )

    version = models.PositiveIntegerField(default=1)

    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nom} v{self.version}"
    
    
class ExecutionCommande(models.Model):
    equipement = models.ForeignKey(EquipementReseau, on_delete=models.CASCADE)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    commande = models.TextField()
    succes = models.BooleanField(default=False)
    sortie = models.TextField(blank=True)
    erreur = models.TextField(blank=True)

    date_execution = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.equipement.nom} @ {self.date_execution}"
    
    
class ChangePlanifie(models.Model):
    STATUT_CHOICES = [
        ("en_attente", "⏳ En attente de validation"),
        ("valide", "✅ Validé"),
        ("rejete", "❌ Rejeté"),
        ("execute", "⚙️ Exécuté"),
        ("annule", "🚫 Annulé"),
    ]

    commande = models.ForeignKey(
        CommandeAutomatique,
        on_delete=models.CASCADE,
        related_name="planifications"
    )

    equipement = models.ForeignKey(
        EquipementReseau,
        on_delete=models.CASCADE,
        related_name="changements_planifies"
    )

    frequence = models.CharField(
        max_length=20,
        choices=[
            ("once", "Une fois"),
            ("daily", "Quotidien"),
            ("weekly", "Hebdomadaire"),
        ],
        default="once"
    )

    date_execution = models.DateTimeField()

    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default="en_attente"
    )

    # 👤 Validation humaine
    valide_par = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="changements_valides"
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    commentaire_validation = models.TextField(blank=True)

    actif = models.BooleanField(default=True)

    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    cree_le = models.DateTimeField(auto_now_add=timezone.now())

    derniere_execution = models.DateTimeField(null=True, blank=True)

    def est_valide(self):
        return self.statut == "valide"
    
    # monitoring/models.py
class AnalyseIA(models.Model):
    incident = models.OneToOneField(
        "Incident",
        on_delete=models.CASCADE,
        related_name="analyse_ia"
    )

    cause_racine = models.TextField()
    categorie = models.CharField(max_length=100,blank=True,null=True)
    solution_humaine = models.TextField()
    remediation_auto = models.TextField(blank=True)
    explication_simple = models.TextField(blank=True)
    confiance = models.FloatField()

    cree_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analyse IA incident #{self.incident.id}"
class PlanRemediationIA(models.Model):
    analyse = models.OneToOneField(
        AnalyseIA,
        on_delete=models.CASCADE
    )

    actions = models.JSONField()
    rollback = models.JSONField()
    risque = models.CharField(max_length=50)

    validation_humaine = models.BooleanField(default=True)
    
class RapportExecutif(models.Model):
    """
    Rapport hebdomadaire généré par IA
    """

    date_debut = models.DateField()
    date_fin = models.DateField()

    resume_global = models.TextField()
    analyse_ia = models.TextField()

    nb_incidents = models.PositiveIntegerField(default=0)
    nb_equipements_impactes = models.PositiveIntegerField(default=0)

    fichier_pdf = models.FileField(
        upload_to="rapports/",
        null=True,
        blank=True
    )

    cree_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rapport {self.date_debut} → {self.date_fin}"