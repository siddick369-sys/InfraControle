from django.db import models
from django.utils import timezone

class AccessPoint(models.Model):
    STATUS_CHOICES = [
        ('up', 'Opérationnel'),
        ('down', 'Hors ligne'),
        ('maintenance', 'Maintenance'),
    ]

    nom = models.CharField(max_length=100)
    mac_adresse = models.CharField(max_length=17, unique=True, db_index=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    modele = models.CharField(max_length=100, blank=True)
    firmware = models.CharField(max_length=50, blank=True)
    uptime = models.DurationField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default='down')
    
    cpu_usage = models.FloatField(default=0.0)
    ram_usage = models.FloatField(default=0.0)
    
    derniere_vue = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} ({self.adresse_ip})"

    class Meta:
        verbose_name = "Point d'Accès"
        verbose_name_plural = "Points d'Accès"

class WifiMetric(models.Model):
    access_point = models.ForeignKey(AccessPoint, on_delete=models.CASCADE, related_name='metrics')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    clients_2ghz = models.PositiveIntegerField(default=0)
    clients_5ghz = models.PositiveIntegerField(default=0)
    
    channel_utilization = models.FloatField(default=0.0) # en %
    
    traffic_tx_bytes = models.BigIntegerField(default=0)
    traffic_rx_bytes = models.BigIntegerField(default=0)

    class Meta:
        ordering = ['-timestamp']
        # Utilisation de indexes au lieu de index_together (déprécié)
        indexes = [
            models.Index(fields=['access_point', 'timestamp']),
        ]

class WifiClient(models.Model):
    mac_adresse = models.CharField(max_length=17, unique=True, db_index=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    device_type = models.CharField(max_length=100, blank=True) # OS/Type
    
    access_point_actuel = models.ForeignKey(AccessPoint, on_delete=models.SET_NULL, null=True, related_name='clients_connectes')
    
    rssi = models.IntegerField(null=True, blank=True) # dBm
    snr = models.IntegerField(null=True, blank=True) # dB
    score_confiance = models.IntegerField(default=80, help_text="Score de confiance 0-100 (0=dangereux, 100=sûr)")
    est_bloque = models.BooleanField(default=False, help_text="Client bloqué par l'admin")
    
    derniere_connexion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Client {self.mac_adresse}"

class WifiAlert(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Information'),
        ('medium', 'Avertissement'),
        ('high', 'Critique'),
    ]

    access_point = models.ForeignKey(AccessPoint, on_delete=models.CASCADE, null=True, blank=True, related_name='alertes')
    type_alerte = models.CharField(max_length=100) # Rogue AP, CPU High, etc.
    description = models.TextField()
    severite = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    est_resolu = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
