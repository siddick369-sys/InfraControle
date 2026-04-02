from django.contrib import admin

# Register your models here.


from django.contrib import admin
# from .models import ReseauScan, DecouverteReseau

# discovery/admin.py
from django.contrib import admin
from .models import EquipementDecouvert


@admin.register(EquipementDecouvert)
class EquipementDecouvertAdmin(admin.ModelAdmin):
    list_display = (
        "adresse_ip",
        "hostname",
        "type_detecte",
        "ajoute",
        "vu_le",
    )

    list_filter = (
        "type_detecte",
        "ajoute",
        "vu_le",
    )

    search_fields = (
        "adresse_ip",
        "hostname",
    )

    ordering = ("-vu_le",)

    readonly_fields = ("vu_le",)

    actions = ["marquer_comme_ajoute", "reinitialiser"]

    @admin.action(description="✅ Marquer comme ajouté au monitoring")
    def marquer_comme_ajoute(self, request, queryset):
        queryset.update(ajoute=True)

    @admin.action(description="🔄 Réinitialiser (non ajouté)")
    def reinitialiser(self, request, queryset):
        queryset.update(ajoute=False)
# @admin.register(ReseauScan)
# class ReseauScanAdmin(admin.ModelAdmin):
#     list_display = ("nom", "cidr", "actif", "dernier_scan")
#     list_filter = ("actif",)


# @admin.register(DecouverteReseau)
# class DecouverteReseauAdmin(admin.ModelAdmin):
#     list_display = (
#         "adresse_ip",
#         "hostname",
#         "adresse_mac",
#         "fabricant",
#         "deja_connu",
#         "valide",
#         "dernier_scan",
#     )
#     list_filter = ("valide", "deja_connu")