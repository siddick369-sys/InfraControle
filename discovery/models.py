from django.db import models

# Create your models here.


from django.db import models

class EquipementDecouvert(models.Model):
    adresse_ip = models.GenericIPAddressField(unique=True)
    hostname = models.CharField(max_length=255, blank=True)
    type_detecte = models.CharField(max_length=50, default="inconnu")
    vu_le = models.DateTimeField(auto_now=True)
    ajoute = models.BooleanField(default=False)
    email_envoye = models.BooleanField(default=False)
    mac_addresse = models.CharField(max_length=17,blank=True)
    systeme_exploitation = models.CharField(max_length=50, default="inconnu")

    def __str__(self):
        return self.adresse_ip
