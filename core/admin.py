from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Profil, JournalActivite, CodeVerification

@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'est_autorise', 'cree_le')
    list_filter = ('role', 'est_autorise')
    search_fields = ('user__username', 'user__email')

from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from django.utils import timezone
from datetime import timedelta
from core.models import JournalActivite

@admin.register(JournalActivite)
class JournalActiviteAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "action", "resultat", "date_action", "ip")
    list_filter = ("action", "date_action")
    search_fields = ("utilisateur__username", "action", "resultat")
    readonly_fields = ("date_action",)

    change_list_template = "admin/logs_dashboard.html"

    def changelist_view(self, request, extra_context=None):
        """Surcharge : affiche le dashboard Chart.js."""
        extra_context = extra_context or {}
        return TemplateResponse(request, "admin/logs_dashboard.html", extra_context)
@admin.register(CodeVerification)
class CodeVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'expire_le', 'tentative')
    search_fields = ('user__username',)