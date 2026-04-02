from django.contrib import admin
from .models import (
    EquipementReseau,
    CommandeAutomatique,
    Incident,
    JournalReseau,
    StatReseau,
    HistoriqueConnexion,
)


# ================================================================
# 1️⃣ ADMIN – ÉQUIPEMENTS RÉSEAU
# ================================================================

@admin.register(EquipementReseau)
class EquipementReseauAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "type_equipement",
        "adresse_ip",
        "statut",
        "cpu_usage",
        "ram_usage",
        "latence",
        "derniere_verification",
        "actif",
    )
    list_filter = ("type_equipement", "statut", "actif")
    search_fields = ("nom", "adresse_ip", "utilisateur_ssh", "localisation")
    readonly_fields = ("derniere_verification", "cree_le", "modifie_le")
    ordering = ("nom",)

    fieldsets = (
        ("Informations générales", {
            "fields": (
                "nom", "type_equipement", "adresse_ip", "port_ssh",
                "description", "localisation", "actif", "statut"
            ),
        }),
        ("Identifiants SSH", {
            "fields": (
                "utilisateur_ssh", "mot_de_passe_ssh_chiffre", "cle_publique",
            ),
            "description": "Les mots de passe sont chiffrés avec Fernet pour plus de sécurité."
        }),
        ("Métriques réseau", {
            "fields": (
                "cpu_usage", "ram_usage", "disk_usage", "network_bandwidth", "latence", "derniere_verification",
            ),
        }),
        ("Métadonnées", {
            "fields": ("cree_par", "cree_le", "modifie_le"),
        }),
    )


# ================================================================
# 2️⃣ ADMIN – COMMANDES AUTOMATIQUES
# ================================================================

@admin.register(CommandeAutomatique)
class CommandeAutomatiqueAdmin(admin.ModelAdmin):
    list_display = ("nom", "critique", "confirmation_requise", "cree_par", "cree_le")
    search_fields = ("nom", "description", "contenu")
    list_filter = ("critique", "confirmation_requise")
    readonly_fields = ("cree_le",)
    ordering = ("nom",)

    fieldsets = (
        ("Détails de la commande", {
            "fields": ("nom", "description", "contenu"),
        }),
        ("Ciblage", {
            "fields": ("applicable_pour",),
        }),
        ("Paramètres d’exécution", {
            "fields": ("confirmation_requise", "critique"),
        }),
        ("Métadonnées", {
            "fields": ("cree_par", "cree_le"),
        }),
    )


# ================================================================
# 3️⃣ ADMIN – INCIDENTS ET ALERTES
# ================================================================

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "titre", "equipement", "niveau", "statut", "date_debut", "date_resolution"
    )
    list_filter = ("niveau", "statut")
    search_fields = ("titre", "description", "equipement__nom")
    readonly_fields = ("date_debut", "date_resolution")
    ordering = ("-date_debut",)

    fieldsets = (
        ("Informations sur l’incident", {
            "fields": ("equipement", "titre", "description", "niveau", "statut")
        }),
        ("Dates", {
            "fields": ("date_debut", "date_resolution")
        }),
        ("Auteur", {
            "fields": ("cree_par",)
        }),
    )


# ================================================================
# 4️⃣ ADMIN – JOURNAL D’ACTIVITÉS RÉSEAU
# ================================================================

@admin.register(JournalReseau)
class JournalReseauAdmin(admin.ModelAdmin):
    list_display = (
        "equipement", "utilisateur", "action", "resultat", "date_action", "ip_utilisateur"
    )
    list_filter = ("resultat", "action")
    search_fields = ("equipement__nom", "utilisateur__username", "action", "commande_executee")
    readonly_fields = ("date_action",)
    ordering = ("-date_action",)

    fieldsets = (
        ("Informations principales", {
            "fields": ("equipement", "utilisateur", "action", "resultat", "ip_utilisateur")
        }),
        ("Détails techniques", {
            "fields": ("commande_executee", "sortie_ssh"),
            "description": "Contient la commande SSH et la sortie brute si disponible."
        }),
        ("Date", {
            "fields": ("date_action",),
        }),
    )


# ================================================================
# 5️⃣ ADMIN – STATISTIQUES RÉSEAU (métriques CPU/RAM)
# ================================================================

@admin.register(StatReseau)
class StatReseauAdmin(admin.ModelAdmin):
    list_display = ("equipement", "ping_ms", "cpu_usage", "ram_usage", "disponible", "date_releve")
    list_filter = ("disponible",)
    search_fields = ("equipement__nom",)
    ordering = ("-date_releve",)


# ================================================================
# 6️⃣ ADMIN – HISTORIQUE DE CONNEXION SSH
# ================================================================

@admin.register(HistoriqueConnexion)
class HistoriqueConnexionAdmin(admin.ModelAdmin):
    list_display = ("equipement", "utilisateur", "action", "resultat", "ip_source", "date_action")
    list_filter = ("resultat", "action")
    search_fields = ("equipement__nom", "utilisateur__username", "details")
    readonly_fields = ("date_action",)
    ordering = ("-date_action",)

    fieldsets = (
        ("Informations principales", {
            "fields": ("equipement", "utilisateur", "action", "resultat", "ip_source")
        }),
        ("Détails", {
            "fields": ("details", "date_action"),
            "description": "Contient le message d’erreur ou le log complet SSH."
        }),
    )
    
    
# Fin du fichier
