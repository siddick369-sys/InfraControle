from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count
from .models import AccessPoint, WifiMetric, WifiClient, WifiAlert

class WifiDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "wifi/wifi_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Stats globales
        aps = AccessPoint.objects.all()
        context['total_aps'] = aps.count()
        context['aps_up'] = aps.filter(statut='up').count()
        context['aps_down'] = aps.filter(statut='down').count()
        
        context['total_clients'] = WifiClient.objects.filter(access_point_actuel__isnull=False).count()
        
        # Bande passante globale (basée sur la dernière métrique de chaque AP)
        total_bw = 0
        for ap in aps:
            last_metric = ap.metrics.first()
            if last_metric:
                total_bw += (last_metric.traffic_tx_bytes + last_metric.traffic_rx_bytes)
        
        context['total_bandwidth_mb'] = round(total_bw / (1024 * 1024), 2)
        
        # Alertes récentes
        context['recent_alerts'] = WifiAlert.objects.filter(est_resolu=False).order_by('-timestamp')[:10]
        
        # Liste des APs avec leurs métriques rapides
        context['aps_list'] = aps
        
        return context

class APDetailView(LoginRequiredMixin, DetailView):
    model = AccessPoint
    template_name = "wifi/ap_detail.html"
    context_object_name = "ap"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ap = self.get_object()
        
        # Clients connectés à cet AP
        context['clients'] = ap.clients_connectes.all()
        
        # Historique des métriques (24 dernières pour le graphique)
        context['metric_history'] = ap.metrics.all()[:24][::-1]
        
        # Alertes spécifiques à cet AP
        context['alerts'] = ap.alertes.filter(est_resolu=False)
        
        return context
