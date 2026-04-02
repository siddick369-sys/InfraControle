from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('titre', 'user', 'type_notif', 'lu', 'cree_le')
    list_filter = ('type_notif', 'lu', 'cree_le')
    search_fields = ('titre', 'message')
