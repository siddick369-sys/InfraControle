from django.urls import path
from . import views

app_name = 'wifi'

urlpatterns = [
    path('dashboard/', views.WifiDashboardView.as_view(), name='dashboard'),
    path('ap/<int:pk>/', views.APDetailView.as_view(), name='ap_detail'),
]
