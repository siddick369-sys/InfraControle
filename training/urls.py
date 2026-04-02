from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [
    path('', views.training_dashboard, name='dashboard'),
    path('lancer/<int:incident_id>/', views.lancer_sandbox, name='lancer_sandbox'),
    path('generer-ia/', views.generer_scenario_ia_view, name='generer_scenario_ia'),
    path('sandbox/<int:session_id>/', views.sandbox_view, name='sandbox_view'),
    path('sandbox/<int:session_id>/chat/', views.sandbox_chat_api, name='sandbox_chat'),
    path('sandbox/<int:session_id>/validate/', views.sandbox_validate_api, name='sandbox_validate'),
]
