from django.contrib import admin
from monitoring.models import RapportExecutif

@admin.register(RapportExecutif)
class RapportExecutifAdmin(admin.ModelAdmin):
    """
    Administration des rapports exécutifs IA
    """
    list_display = (
        "periode",
        "nb_incidents",
        "nb_equipements_impactes",
        "pdf_disponible",
        "cree_le",
    )
    list_filter = (
        "date_debut",
        "date_fin",
        "cree_le",
    )
    search_fields = (
        "resume_global",
        "analyse_ia",
    )
    ordering = ("-date_debut",)
    readonly_fields = (
        "date_debut",
        "date_fin",
        "resume_global",
        "analyse_ia",
        "nb_incidents",
        "nb_equipements_impactes",
        "fichier_pdf",
        "cree_le",
    )
    fieldsets = (
        (
            "📅 Période",
            {
                "fields": ("date_debut", "date_fin"),
            },
        ),
        (
            "📊 Synthèse",
            {
                "fields": (
                    "nb_incidents",
                    "nb_equipements_impactes",
                ),
            },
        ),
        (
            "🧠 Analyse IA",
            {
                "fields": (
                    "resume_global",
                    "analyse_ia",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "📄 Fichier PDF",
            {
                "fields": ("fichier_pdf",),
            },
        ),
        (
            "ℹ️ Métadonnées",
            {
                "fields": ("cree_le",),
            },
        ),
    )

    def periode(self, obj):
        return f"{obj.date_debut} → {obj.date_fin}"
    periode.short_description = "Période"

    def pdf_disponible(self, obj):
        if obj.fichier_pdf:
            return "📄 Oui"
        return "❌ Non"
    pdf_disponible.short_description = "PDF"
