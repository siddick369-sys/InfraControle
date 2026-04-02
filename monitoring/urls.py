from django.urls import path

from monitoring.views_metrics import *
from . import views

urlpatterns = [
    path('equipements/', views.liste_equipements_view, name='liste_equipements'),
    path('equipements/<int:equipement_id>/modifier/', views.modifier_equipement_view, name='modifier_equipement'),
    path('equipements/terminale/<int:e_id>', views.terminal_equipement, name='terminal_equipement'),
    path('equipements/ajouter/', views.ajouter_equipement_view, name='ajouter_equipement'),
    path('equipements/<int:equipement_id>/tester/', views.tester_connexion_view, name='tester_connexion'),
    path('equipements/<int:equipement_id>/commande/<int:commande_id>/', views.executer_commande_view, name='executer_commande'),
    
    # Nouvelles URLs CRUD Planification directe
    path('equipements/<int:equipement_id>/planifier/', views.planifier_commande_equipement_view, name='planifier_commande_equipement'),
    path('equipements/<int:equipement_id>/planifications/', views.liste_planifications_equipement_view, name='liste_planifications_equipement'),
    path('planifications/<int:plan_id>/supprimer/', views.supprimer_planification_view, name='supprimer_planification'),
    
    path('planifier/<int:commande_id>', views.planifier_commande_view, name='planifier'),
    path("commandes/<int:commande_id>/", views.commande_detail, name="commande_detail"),
    path('dashboard/', views.dashboard_monitoring_view, name='dashboard_monitoring'),
    path("commandes/", views.liste_commandes, name="liste_commandes"),
 
    path('creer-commande/', views. creer_commande_view, name='creer-commande'),
    path('api/realtime/', views.get_realtime_stats, name='get_realtime_stats'),
    # monitoring/urls.py
    path(
        "api/equipements/<int:equipement_id>/metrics/",
        equipement_metrics_api,
        name="equipement_metrics_api",
    ),
    path(
        "changes/validation/",
        views.liste_changements_a_valider,
        name="liste_changements_a_valider"
    ),
    path(
        "changes/<int:change_id>/valider/",
        views.valider_changement,
        name="valider_changement"
    ),
    path(
        "changes/<int:change_id>/refuser/",
        views.refuser_changement,
        name="refuser_changement"
    ),


    path("equipement/<int:equipement_id>/tester-ssh/", views.tester_ssh_view, name="tester_ssh"),
    path("equipement/<int:equipement_id>/", views.equipement_detail_view, name="detail_equipement"),
    path("incidents/", views.liste_incidents_view, name="liste_incidents"),
    path("motdepasse/", views.motdepasse_view, name="motdepasse"),
    path("incidents/data/", views.incidents_json_view, name="incidents_json"),
    path("incidents/count/", views.incidents_non_resolus_count_view, name="incidents_non_resolus_count"),
    path("historique-taches/", views.historique_taches_view, name="historique_taches"),
    path("health/global/", views.health_global_json, name="health"),
    path(
    "equipement/<int:equipement_id>/toggle-alertes/",
    views.toggle_alertes_email,
    name="toggle_alertes_email"
),
    # monitoring/urls.py
    path("api/noc/status/", views.noc_status_api, name="noc_status_api"),
    path("noc/", views.noc_view, name="noc_view"),
    path("dashboard/", views.wifi_dashboard_view, name="wifi_dashboard"),
    path("api/dashboard/", views.wifi_dashboard_api, name="wifi_dashboard_api"),


    path("network/map/", views.network_map_view, name="network_map"),
    path("api/network/map/", views.network_map_api, name="network_map_api"),
    path("api/network/save-pos/", views.save_node_position, name="save_node_position"),
    path("api/heatmap/", views.wifi_heatmap_api, name="wifi_heatmap_api"),
    path("heatmap/", views.wifi_heatmap_view, name="wifi_heatmap"),
    path('api/ai/analyze/<int:equipement_id>/', views.ai_analyze_view, name='ai_analyze'),
    path(
    "commandes/<int:commande_id>/modifier/",
    views.modifier_commande,
    name="modifier_commande"
),
    
    # (Optionnel) URL pour lancer l'optimisation WiFi globale
    path('api/ai/wifi-audit/', views.ai_wifi_audit_view, name='ai_wifi_audit'),


    path(
        "equipement/<int:equipement_id>/statut/",
        views.equipement_statut_json,
        name="equipement_statut_json"
    ),
    path(
    "equipement/<int:equipement_id>/reparer/",
    views.equipement_reparer,
    name="equipement_reparer"
),
    path(
    "equipement/<int:equipement_id>/maintenance/",
    views.mettre_en_maintenance,
    name="mettre_en_maintenance"
),


    path("incident/<int:incident_id>/resolu/", views.marquer_incident_resolu_view, name="marquer_incident_resolu"),
    path("maintenance/reset/", views.basculer_maintenance_generale_view, name="basculer_maintenance_generale"),
    path("incidents/<int:incident_id>/analyse-ia/", views.analyser_incident_ia_view, name="analyseIa"),
    path(
        "incidents/<int:incident_id>/analyse-ia/resultat/",
        views.resultat_analyse_ia,
        name="resultat_analyse_ia"
    ),


]