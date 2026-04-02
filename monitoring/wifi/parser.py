import re

def parse_station_dump(raw):
    clients = []

    if not raw:
        return clients

    blocks = raw.split("Station ")

    for block in blocks[1:]:
        mac = block.split()[0]

        rssi = re.search(r"signal:\s*(-?\d+)", block)
        tx = re.search(r"tx bitrate:\s*([\d.]+)", block)
        rx = re.search(r"rx bitrate:\s*([\d.]+)", block)

        clients.append({
            "mac": mac,
            "rssi": int(rssi.group(1)) if rssi else None,
            "tx_rate_mbps": float(tx.group(1)) if tx else None,
            "rx_rate_mbps": float(rx.group(1)) if rx else None,
        })

    return clients