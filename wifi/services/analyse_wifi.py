"""
wifi/services/analyse_wifi.py — Logique métier Wi-Fi
"""
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('monitoring')


def analyser_saturation_canal(radio):
    """
    Analyse la saturation d'un canal Wi-Fi.
    Retourne un dict avec les résultats.
    """
    from monitoring.models import WifiStat, WifiIncident
    
    stats_recentes = WifiStat.objects.filter(
        radio=radio,
        date_releve__gte=timezone.now() - timedelta(hours=1)
    ).order_by('-date_releve')[:12]
    
    if not stats_recentes:
        return {'sature': False, 'message': 'Pas de données'}
    
    canaux_satures = sum(1 for s in stats_recentes if s.canal_sature)
    taux_saturation = canaux_satures / len(stats_recentes) * 100
    
    if taux_saturation > 60:
        # Créer un incident Wi-Fi
        WifiIncident.objects.create(
            ap=radio.ap,
            radio=radio,
            type_incident='canal_sature',
            description=f"Canal {radio.canal} ({radio.bande} GHz) saturé à {taux_saturation:.0f}% sur la dernière heure."
        )
        return {
            'sature': True,
            'taux': taux_saturation,
            'canal': radio.canal,
            'bande': radio.bande,
            'message': f'Canal saturé à {taux_saturation:.0f}%'
        }
    
    return {'sature': False, 'taux': taux_saturation}


def detecter_clients_intrus(ap):
    """
    Détecte les clients suspects sur un AP.
    """
    from monitoring.models import WifiClient, WifiIncident
    
    clients = WifiClient.objects.filter(radio__ap=ap)
    suspects = []
    
    for client in clients:
        # Signal très fort + pas de SSID connu = suspect
        if client.rssi > -30 and not client.ssid:
            client.intrus = True
            client.save()
            suspects.append(client)
    
    if suspects:
        WifiIncident.objects.create(
            ap=ap,
            type_incident='auth_fail',
            description=f"{len(suspects)} client(s) suspect(s) détecté(s): {', '.join(c.mac for c in suspects)}"
        )
    
    return suspects


def recommander_canal_optimal(radio):
    """
    Recommande un canal optimal basé sur l'analyse des statistiques.
    """
    from monitoring.models import WifiStat, WifiRadio, WifiRecommendation
    
    bande = radio.bande
    
    # Canaux disponibles par bande
    canaux = {
        '2.4': [1, 6, 11],
        '5': [36, 40, 44, 48, 149, 153, 157, 161],
        '6': [1, 5, 9, 13, 17, 21, 25, 29],
    }
    
    canaux_disponibles = canaux.get(bande, [])
    if not canaux_disponibles:
        return None
    
    # Trouver les canaux les moins utilisés
    utilisation_par_canal = {}
    for canal in canaux_disponibles:
        radios_sur_canal = WifiRadio.objects.filter(
            bande=bande, canal=canal, radio_active=True
        ).exclude(pk=radio.pk)
        utilisation_par_canal[canal] = radios_sur_canal.count()
    
    canal_optimal = min(utilisation_par_canal, key=utilisation_par_canal.get)
    
    if canal_optimal != radio.canal:
        WifiRecommendation.objects.create(
            ap=radio.ap,
            radio=radio,
            type_recommandation='canal',
            message=f"Changer canal {radio.canal} → {canal_optimal} sur bande {bande} GHz",
            gravite=3,
            justification=f"Canal {radio.canal} utilisé par {utilisation_par_canal.get(radio.canal, 0)} radios voisines. Canal {canal_optimal} utilisé par {utilisation_par_canal[canal_optimal]} radios."
        )
    
    return canal_optimal


def collecter_stats_wifi(ap):
    """
    Collecte les statistiques Wi-Fi d'un AP.
    """
    from monitoring.models import WifiStat, WifiClient
    
    stats_creees = []
    for radio in ap.radios.filter(radio_active=True):
        clients = WifiClient.objects.filter(radio=radio)
        nb_clients = clients.count()
        
        debit_total = sum(
            (c.tx_rate_mbps or 0) + (c.rx_rate_mbps or 0) 
            for c in clients
        )
        
        stat = WifiStat.objects.create(
            ap=ap,
            radio=radio,
            nb_clients=nb_clients,
            debit_total_mbps=debit_total,
            canal_sature=radio.taux_utilisation and radio.taux_utilisation > 80,
        )
        stats_creees.append(stat)
    
    return stats_creees
