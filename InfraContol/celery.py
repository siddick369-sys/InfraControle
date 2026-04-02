import os
from celery import Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InfraContol.settings')
app = Celery('InfraContol')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()