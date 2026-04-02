from django.contrib import admin
from monitoring.models import (
    WifiAccessPoint, WifiRadio, WifiClient,
    WifiStat, WifiIncident, WifiSSID,
    WifiRecommendation
)


class WifiRadioInline(admin.TabularInline):
    model = WifiRadio
    extra = 0
    fields = ['bande', 'canal', 'largeur_canal_mhz', 'puissance_tx_dbm', 'bruit_dbm', 'radio_active', 'taux_utilisation']


@admin.register(WifiAccessPoint)
class WifiAccessPointAdmin(admin.ModelAdmin):
    list_display = ['equipement', 'fabricant', 'modele', 'mode_gestion', 'nb_clients_max', 'actif', 'etat']
    list_filter = ['mode_gestion', 'actif', 'etat']
    search_fields = ['equipement__nom', 'equipement__adresse_ip', 'fabricant', 'modele']
    inlines = [WifiRadioInline]


@admin.register(WifiRadio)
class WifiRadioAdmin(admin.ModelAdmin):
    list_display = ['ap', 'bande', 'canal', 'puissance_tx_dbm', 'radio_active', 'taux_utilisation']
    list_filter = ['bande', 'radio_active']
    search_fields = ['ap__equipement__nom']


@admin.register(WifiClient)
class WifiClientAdmin(admin.ModelAdmin):
    list_display = ['mac', 'ip', 'ssid', 'radio', 'rssi', 'type_device', 'intrus', 'connecte_depuis']
    list_filter = ['type_device', 'intrus', 'roaming']
    search_fields = ['mac', 'ip']


@admin.register(WifiStat)
class WifiStatAdmin(admin.ModelAdmin):
    list_display = ['ap', 'radio', 'nb_clients', 'debit_total_mbps', 'canal_sature', 'date_releve']
    list_filter = ['canal_sature']
    date_hierarchy = 'date_releve'


@admin.register(WifiIncident)
class WifiIncidentAdmin(admin.ModelAdmin):
    list_display = ['ap', 'type_incident', 'description', 'resolu', 'date_detection']
    list_filter = ['type_incident', 'resolu']
    search_fields = ['description']


@admin.register(WifiSSID)
class WifiSSIDAdmin(admin.ModelAdmin):
    list_display = ['nom', 'securite', 'vlan', 'actif', 'isolation_clients']
    list_filter = ['securite', 'actif']
    search_fields = ['nom']


@admin.register(WifiRecommendation)
class WifiRecommendationAdmin(admin.ModelAdmin):
    list_display = ['ap', 'type_recommandation', 'gravite', 'appliquee', 'cree_le']
    list_filter = ['type_recommandation', 'appliquee']
