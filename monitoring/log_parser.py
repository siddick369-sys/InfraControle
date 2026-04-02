import re
from .ssh_utils import get_ssh_client, exec_command_safe

def collecter_logs_ssh(equipement):
    """
    Lit les derniers logs syslog et détecte patterns d'anomalies.
    """
    anomalies = []
    try:
        ssh = get_ssh_client(equipement)
        out, err = exec_command_safe(ssh, "tail -n 200 /var/log/syslog")
        ssh.close()

        if re.search(r"link down|link is down", out, re.I):
            anomalies.append("Interface flapping détectée")
        if re.search(r"spanning tree", out, re.I):
            anomalies.append("Changement topologie STP")
        if re.search(r"OSPF.*Neighbor Down", out, re.I):
            anomalies.append("OSPF Neighbor Down")
        if re.search(r"BGP.*Closed|BGP.*Idle", out, re.I):
            anomalies.append("BGP Neighbor Down")
    except Exception:
        pass

    return anomalies