from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.http import JsonResponse
import json, random
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
        
        print(f"[DEBUG] WiFi Dashboard: {aps.count()} APs found. Current User: {self.request.user}")
        return context

def wifi_api_stats(request):
    """Endpoint AJAX pour le rafraîchissement sans rechargement"""
    aps = AccessPoint.objects.all()
    total_aps = aps.count()
    aps_up = aps.filter(statut='up').count()
    aps_down = aps.filter(statut='down').count()
    total_clients = WifiClient.objects.filter(access_point_actuel__isnull=False).count()
    
    total_bw = 0
    c_2g = 0
    c_5g = 0
    aps_data = []
    
    for ap in aps:
        last_metric = ap.metrics.first()
        if last_metric:
            total_bw += (last_metric.traffic_tx_bytes + last_metric.traffic_rx_bytes)
            c_2g += last_metric.clients_2ghz
            c_5g += last_metric.clients_5ghz
        
        aps_data.append({
            'id': ap.id,
            'nom': ap.nom,
            'ip': ap.adresse_ip,
            'statut': ap.statut,
            'cpu': ap.cpu_usage,
            'clients': ap.clients_connectes.count()
        })
    
    alerts = WifiAlert.objects.filter(est_resolu=False).order_by('-timestamp')[:5]
    alerts_data = [{
        'type': a.type_alerte,
        'desc': a.description,
        'sev': a.severite,
        'ap': a.access_point.nom if a.access_point else 'N/A',
        'time': a.timestamp.strftime("%H:%M")
    } for a in alerts]

    # Clients connectés (nouveau)
    clients = WifiClient.objects.filter(access_point_actuel__isnull=False, est_bloque=False).order_by('-score_confiance')[:50]
    clients_data = [{
        'id': c.id,
        'mac': c.mac_adresse,
        'ip': c.adresse_ip,
        'device': c.device_type,
        'rssi': c.rssi or -50,
        'score': c.score_confiance,
        'bloque': c.est_bloque,
        'ap_name': c.access_point_actuel.nom if c.access_point_actuel else 'N/A',
    } for c in clients]
    
    return JsonResponse({
        'total_aps': total_aps,
        'aps_up': aps_up,
        'aps_down': aps_down,
        'total_clients': total_clients,
        'total_bw': round(total_bw / (1024 * 1024), 2),
        'c_2g': c_2g,
        'c_5g': c_5g,
        'aps': aps_data,
        'alerts': alerts_data,
        'clients': clients_data,
    })

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

def ap_metrics_api(request, ap_id):
    """
    Retourne les dernières données temps réel pour un AP spécifique (AJAX).
    """
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    ap = get_object_or_404(AccessPoint, id=ap_id)
    
    last_metric = ap.metrics.first()
    if not last_metric:
        return JsonResponse({"error": "No metrics available"}, status=404)
        
    return JsonResponse({
        "timestamp": last_metric.timestamp.strftime('%H:%M:%S'),
        "clients_2ghz": last_metric.clients_2ghz,
        "clients_5ghz": last_metric.clients_5ghz,
        "cpu_usage": ap.cpu_usage,
        "ram_usage": ap.ram_usage,
        "statut": ap.statut,
        "total_clients": ap.clients_connectes.count(),
        "clients_list": [
            {
                "mac": c.mac_adresse,
                "ip": c.adresse_ip,
                "device": c.device_type,
                "rssi": c.rssi,
                "score": c.score_confiance,
                "bloque": c.est_bloque,
                "last_seen": "Il y a un instant"
            } for c in ap.clients_connectes.filter(est_bloque=False)
        ]
    })


@login_required
@require_POST
def trigger_attack_ajax(request):
    """Injecte immédiatement un client Kali Linux pour démonstration au jury."""
    ap = AccessPoint.objects.filter(statut='up').first()
    if not ap:
        return JsonResponse({'error': 'Aucun AP actif'}, status=400)

    hacker_mac = f"DE:AD:BE:EF:{random.randint(10,99)}:{random.randint(10,99)}"
    client, _ = WifiClient.objects.update_or_create(
        mac_adresse=hacker_mac,
        defaults={
            'adresse_ip': '192.168.1.99',
            'device_type': 'Kali Linux / Attaquant',
            'access_point_actuel': ap,
            'rssi': -88,
            'snr': 5,
            'score_confiance': 5,
            'est_bloque': False,
        }
    )
    WifiAlert.objects.create(
        access_point=ap,
        type_alerte='INTRUSION_BRUTE_FORCE',
        description=f'⚠️ Attaque brute-force WPA3 détectée depuis {hacker_mac} (192.168.1.99) sur {ap.nom}',
        severite='high'
    )
    return JsonResponse({'ok': True, 'mac': hacker_mac, 'ap': ap.nom})


@login_required
@require_POST
def block_client_ajax(request):
    """Bloque un client suspect (simulation)."""
    data = json.loads(request.body)
    client_id = data.get('client_id')
    try:
        client = WifiClient.objects.get(id=client_id)
        client.est_bloque = True
        client.access_point_actuel = None
        client.save()
        # Résoudre l'alerte associée si applicable
        WifiAlert.objects.filter(
            description__icontains=client.mac_adresse, est_resolu=False
        ).update(est_resolu=True)
        return JsonResponse({'ok': True, 'mac': client.mac_adresse})
    except WifiClient.DoesNotExist:
        return JsonResponse({'error': 'Client introuvable'}, status=404)
