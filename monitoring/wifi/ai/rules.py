RULES = [
    {
        "condition": lambda f: f["canal_sature"],
        "type": "canal",
        "gravite": 4,
        "message": "Canal Wi-Fi saturé",
        "justification": "Taux d’occupation radio élevé"
    },
    {
        "condition": lambda f: f["clients_faible_rssi"] >= 3,
        "type": "puissance",
        "gravite": 3,
        "message": "Plusieurs clients avec signal faible",
        "justification": "RSSI < -75 dBm sur plusieurs clients"
    },
    {
        "condition": lambda f: f["nb_clients"] > 30,
        "type": "equilibrage",
        "gravite": 4,
        "message": "Point d’accès surchargé",
        "justification": "Nombre de clients supérieur au seuil recommandé"
    },
    {
        "condition": lambda f: f["radios_bruitees"] > 0,
        "type": "performance",
        "gravite": 3,
        "message": "Interférences radio détectées",
        "justification": "Bruit radio supérieur à -85 dBm"
    },
]