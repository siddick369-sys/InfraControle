from remediation.models import AnomalieRegle

AnomalieRegle.objects.get_or_create(
    nom='Reset DNS Cache (Windows)', 
    defaults={
        'cmd_detection': 'ipconfig /displaydns | findstr "Record"', 
        'cmd_remediation': 'ipconfig /flushdns', 
        'os_cible': 'windows'
    }
)
AnomalieRegle.objects.get_or_create(
    nom='Nettoyage Processus Zombies (Linux)', 
    defaults={
        'cmd_detection': "ps -A -ostat,ppid,pid,cmd | grep -e '^[Zz]'", 
        'cmd_remediation': "kill -9 $(ps -A -ostat,ppid | grep -e '^[Zz]' | awk '{print $2}')", 
        'os_cible': 'linux'
    }
)
print("Remediation rules successfully added via shell.")
