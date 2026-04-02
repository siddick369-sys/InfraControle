from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.rapports_liste, name='liste'),
    path('<int:pk>/', views.rapport_detail, name='detail'),
    path('generer/', views.generer_rapport, name='generer'),
    path('<int:pk>/pdf/', views.telecharger_pdf, name='telecharger_pdf'),
]
