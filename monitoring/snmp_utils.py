import logging
import re
from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
from pysnmp.smi.rfc1902 import ObjectIdentity as ObjId

logger = logging.getLogger("monitoring.snmp")

def snmp_get_safe(ip, oid, community, timeout=5):
    """Wrapper sécurisé pour pysnmp"""
    try:
        iterator = getCmd(
            SnmpEngine(), CommunityData(community, mpModel=1),
            UdpTransportTarget((ip, 161), timeout=timeout, retries=1),
            ContextData(), ObjectType(ObjId(oid)), lookupMib=False
        )
        errorIndication, errorStatus, _, varBinds = next(iterator)
        
        if errorIndication or errorStatus: return None
        
        val = varBinds[0][1]
        # Conversion intelligente
        try: return float(val)
        except: pass
        try: return int(val)
        except: pass
        return str(val)
    except:
        return None

def collecter_materiel_snmp(ip, community="public"):
    """
    Remplit les champs hardware et réseau SNMP
    """
    # OIDs standards et propriétaires
    oids = {
        # Environnement
        "temperature_c": [
            "1.3.6.1.4.1.9.9.13.1.3.1.3.1", # Cisco
            "1.3.6.1.2.1.99.1.1.1.4.1"      # Standard
        ],
        "fan_status": ["1.3.6.1.4.1.9.9.13.1.4.1.3.1"], # Cisco Fan
        "power_supply_status": ["1.3.6.1.4.1.9.9.13.1.5.1.3.1"], # Cisco PS
        
        # CPU & RAM (Cisco & Host Resources)
        "cpu_usage": [
            "1.3.6.1.4.1.9.9.109.1.1.1.1.5.1", # Cisco 5min CPU
            "1.3.6.1.4.1.9.2.1.58.0",          # Cisco 5min CPU old
        ],
        "ram_used": ["1.3.6.1.4.1.9.9.48.1.1.1.5.1"], # Cisco Used Memory (Bytes)
        "ram_free": ["1.3.6.1.4.1.9.9.48.1.1.1.6.1"], # Cisco Free Memory (Bytes)
        
        # Réseau (Interface 1 souvent l'uplink, à adapter si besoin)
        "errors_in": ["1.3.6.1.2.1.2.2.1.14.1"],  # ifInErrors.1
        "errors_out": ["1.3.6.1.2.1.2.2.1.20.1"], # ifOutErrors.1
        "drops_in": ["1.3.6.1.2.1.2.2.1.13.1"],   # ifInDiscards.1
        "drops_out": ["1.3.6.1.2.1.2.2.1.19.1"],  # ifOutDiscards.1
    }
    
    data = {}
    
    # Récupération
    for metric, oid_list in oids.items():
        val = None
        for oid in oid_list:
            val = snmp_get_safe(ip, oid, community)
            if val is not None: break
        data[metric] = val

    # Normalisation booléens
    for k in ['fan_status', 'power_supply_status']:
        if data.get(k) is not None:
            # 1 = Normal/Ok dans la plupart des MIBs Cisco
            data[k] = str(data[k]) in ['1', '1.0', 'ok', 'normal']
            
    # Calcul RAM Usage %
    if data.get("ram_used") is not None and data.get("ram_free") is not None:
        used = float(data["ram_used"])
        free = float(data["ram_free"])
        total = used + free
        if total > 0:
            data["ram_usage"] = round((used / total) * 100, 1)
            
    return data