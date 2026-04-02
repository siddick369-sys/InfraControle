from django.db import models
from django.contrib.auth.models import User

class Notification(models.Model):
    TYPE_CHOICES = [
        ('incident', 'Incident Critique'),
        ('discovery', 'Équipement Découvert'),
        ('report', 'Rapport Disponible'),
        ('system', 'Alerte Système'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    type_notif = models.CharField(max_length=20, choices=TYPE_CHOICES)
    titre = models.CharField(max_length=255)
    message = models.TextField()
    lu = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type_notif} - {self.titre}"
