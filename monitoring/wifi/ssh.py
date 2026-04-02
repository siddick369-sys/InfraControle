from monitoring.ssh_utils import get_ssh_client, exec_command_safe
import logging
import re

logger = logging.getLogger("wifi.ssh")


# =========================
# 🔍 Détection interfaces
# =========================
def detect_wifi_interfaces(ssh):
    out, _ = exec_command_safe(
        ssh,
        "iw dev | awk '$1==\"Interface\" {print $2}'"
    )
    return out.splitlines() if out else []


# =========================
# 📡 Collecte radios Wi-Fi
# =========================
def collect_radios_ssh(equipement):
    radios = []

    try:
        ssh = get_ssh_client(equipement)
        interfaces = detect_wifi_interfaces(ssh)

        for iface in interfaces:
            info, _ = exec_command_safe(ssh, f"iw dev {iface} info")
            survey, _ = exec_command_safe(ssh, f"iw dev {iface} survey dump")

            # 🔎 Bande
            band = None
            if "2412 MHz" in info:
                band = "2.4"
            elif "5180 MHz" in info:
                band = "5"
            elif "5955 MHz" in info:
                band = "6"

            # 🔎 Canal
            chan_match = re.search(r"channel\s+(\d+)", info)
            canal = int(chan_match.group(1)) if chan_match else None

            # 🔎 Puissance TX
            tx_match = re.search(r"txpower\s+([\d.]+)", info)
            tx_power = int(float(tx_match.group(1))) if tx_match else None

            # 🔎 Bruit radio
            noise_match = re.search(r"noise:\s*(-?\d+)", survey)
            bruit = int(noise_match.group(1)) if noise_match else None

            # 🔎 Utilisation (approx)
            util = None
            busy = re.search(r"channel busy time:\s+(\d+)", survey)
            total = re.search(r"channel total time:\s+(\d+)", survey)
            if busy and total and int(total.group(1)) > 0:
                util = round(
                    (int(busy.group(1)) / int(total.group(1))) * 100,
                    2
                )

            radios.append({
                "interface": iface,
                "bande": band,
                "canal": canal,
                "tx_power": tx_power,
                "bruit": bruit,
                "utilisation": util,
            })

        ssh.close()

    except Exception as e:
        logger.warning(f"[WIFI SSH] radios échouées {equipement.nom}: {e}")

    return radios


# =========================
# 👥 Collecte clients Wi-Fi
# =========================
def collect_clients_ssh(equipement):
    result = []

    try:
        ssh = get_ssh_client(equipement)
        interfaces = detect_wifi_interfaces(ssh)

        for iface in interfaces:
            raw, _ = exec_command_safe(
                ssh,
                f"iw dev {iface} station dump"
            )

            result.append({
                "interface": iface,
                "raw": raw,
            })

        ssh.close()

    except Exception as e:
        logger.warning(f"[WIFI SSH] clients échoués {equipement.nom}: {e}")

    return result


