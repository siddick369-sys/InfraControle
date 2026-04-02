from django.contrib import admin
from .models import SessionFormation, MessageInvestigation

@admin.register(SessionFormation)
class SessionFormationAdmin(admin.ModelAdmin):
    list_display = ('user', 'incident_source', 'titre_scenario', 'statut', 'score', 'date_debut')
    list_filter = ('statut', 'date_debut')

@admin.register(MessageInvestigation)
class MessageInvestigationAdmin(admin.ModelAdmin):
    list_display = ('session', 'role', 'date_creation')
    list_filter = ('role', 'date_creation')
