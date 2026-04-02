from django.contrib import admin
from monitoring.models import AnalyseIA

@admin.register(AnalyseIA)
class AnalyseIAAdmin(admin.ModelAdmin):
    """
    Analyse IA des incidents
    Lecture seule – source de vérité IA
    """
    list_display = (
        "incident_id",
        "categorie",
        "confiance_pct",
        "cree_le",
    )
    list_filter = (
        "categorie",
        "cree_le",
    )
    search_fields = (
        "incident__titre",
        "incident__equipement__nom",
        "cause_racine",
        "solution_humaine",
    )
    ordering = ("-cree_le",)
    readonly_fields = (
        "incident",
        "cause_racine",
        "categorie",
        "solution_humaine",
        "remediation_auto",
        "explication_simple",
        "confiance",
        "cree_le",
    )
    fieldsets = (
        (
            "🚨 Incident",
            {
                "fields": ("incident",),
            },
        ),
        (
            "🧠 Cause racine",
            {
                "fields": ("cause_racine", "categorie", "confiance"),
            },
        ),
        (
            "🛠️ Remédiation",
            {
                "fields": (
                    "solution_humaine",
                    "remediation_auto",
                ),
            },
        ),
        (
            "🎓 Explication simplifiée",
            {
                "fields": ("explication_simple",),
                "classes": ("collapse",),
            },
        ),
        (
            "ℹ️ Métadonnées",
            {
                "fields": ("cree_le",),
            },
        ),
    )

    def incident_id(self, obj):
        return f"#{obj.incident.id}"
    incident_id.short_description = "Incident"

    def confiance_pct(self, obj):
        return f"{int(obj.confiance * 100)} %"
    confiance_pct.short_description = "Confiance IA"
