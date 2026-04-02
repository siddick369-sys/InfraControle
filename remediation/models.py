from django.db import models
from monitoring.models import EquipementReseau, Incident

class ActionRemediation(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField()
    script = models.TextField(help_text="Commande ou script à exécuter via SSH ou Docker API")
    automatique = models.BooleanField(default=False)

    def __str__(self):
        return self.nom

class HistoriqueRemediation(models.Model):
    equipement = models.ForeignKey(EquipementReseau, on_delete=models.CASCADE)
    incident = models.ForeignKey(Incident, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.ForeignKey(ActionRemediation, on_delete=models.CASCADE)
    statut = models.CharField(max_length=50, choices=[('succes', 'Succès'), ('echec', 'Échec')])
    sortie_log = models.TextField(blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

class AnomalieRegle(models.Model):
    """
    Règle dynamique liant une anomalie à une commande de détection
    et à une ou plusieurs commandes de remédiation.
    """
    OS_CHOICES = [
        ('all', 'Tous (Universel)'),
        ('linux', 'Linux'),
        ('windows', 'Windows')
    ]
    nom = models.CharField(max_length=150, unique=True, help_text="Ex: Processus Zombies")
    cmd_detection = models.TextField(help_text="Commande de détection, ex: ps -ef | grep defunct")
    cmd_remediation = models.TextField(help_text="Commandes de remédiation (séparées par des sauts de ligne si plusieurs)")
    os_cible = models.CharField(max_length=20, choices=OS_CHOICES, default='linux')
    cree_le = models.DateTimeField(auto_now_add=True)

    def get_remediation_commands(self):
        return [cmd.strip() for cmd in self.cmd_remediation.splitlines() if cmd.strip()]

    def __str__(self):
        return self.nom

