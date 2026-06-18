from django.urls import path
from . import views

app_name = 'wifi'

urlpatterns = [
    path('dashboard/', views.WifiDashboardView.as_view(), name='dashboard'),
    path('ap/<int:pk>/', views.APDetailView.as_view(), name='ap_detail'),
    path('api/stats/', views.wifi_api_stats, name='api_stats'),
    path('api/ap/<int:ap_id>/metrics/', views.ap_metrics_api, name='ap_metrics_api'),
    path('api/trigger-attack/', views.trigger_attack_ajax, name='trigger_attack'),
    path('api/block-client/', views.block_client_ajax, name='block_client'),
]
