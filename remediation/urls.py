from django.urls import path
from . import views

app_name = 'remediation'

urlpatterns = [
    path('', views.remediation_dashboard, name='dashboard'),
    path('lancer/<int:action_id>/<int:equipement_id>/', views.lancer_remediation, name='lancer'),
    path('api/ajouter-regle/', views.ajouter_regle, name='ajouter_regle'),
]
