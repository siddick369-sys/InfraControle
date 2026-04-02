from pysnmp.hlapi import *

def snmp_get(ip, oid, community="public"):
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        errorIndication, errorStatus, _, varBinds = next(iterator)
        if errorIndication or errorStatus:
            return None
        return int(varBinds[0][1])
    except Exception:
        return None


def collect_radio_snmp(ap):
    return {
        "bande": "2.4",
        "canal": snmp_get(ap.equipement.adresse_ip, "1.3.6.1.2.1.25.3.2.1.4"),
        "bruit_dbm": snmp_get(ap.equipement.adresse_ip, "1.3.6.1.4.1.9.9.273"),
    }