from django.db import models
from django.contrib.auth.models import User
from monitoring.models import Incident

class SessionFormation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions_formation")
    incident_source = models.ForeignKey(Incident, on_delete=models.SET_NULL, null=True, blank=True, help_text="L'incident historique utilisé comme scénario")
    titre_scenario = models.CharField(max_length=200, blank=True)
    description_scenario = models.TextField(blank=True, help_text="Briefing généré par l'IA au début de la session")
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, default='en_cours', choices=[
        ('en_cours', 'En Cours'),
        ('termine_succes', 'Terminé (Succès)'),
        ('termine_echec', 'Terminé (Échec)'),
    ])
    score = models.IntegerField(default=0)
    tentatives_cli = models.IntegerField(default=0)

    def __str__(self):
        return f"Session {self.user.username} - {self.titre_scenario or 'Sandbox'}"

class MessageInvestigation(models.Model):
    session = models.ForeignKey(SessionFormation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=[('user', 'Stagiaire'), ('assistant', 'IA Système')])
    contenu = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_creation']
        
    def __str__(self):
        return f"{self.get_role_display()} ({self.date_creation.strftime('%H:%M:%S')})"
