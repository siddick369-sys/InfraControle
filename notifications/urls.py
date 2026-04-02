from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.liste_notifications, name='liste'),
]
