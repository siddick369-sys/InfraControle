from django.contrib import admin
from .models import ActionRemediation, HistoriqueRemediation

@admin.register(ActionRemediation)
class ActionRemediationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'automatique')

@admin.register(HistoriqueRemediation)
class HistoriqueRemediationAdmin(admin.ModelAdmin):
    list_display = ('equipement', 'action', 'statut', 'date_action')
    list_filter = ('statut', 'date_action')
