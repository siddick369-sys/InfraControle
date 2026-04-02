from monitoring.wifi.ai.features import extraire_features_wifi
from monitoring.wifi.ai.rules import RULES
from monitoring.models import WifiRecommendation


def generer_recommandations_wifi(ap):
    features = extraire_features_wifi(ap)
    recommandations = []

    for rule in RULES:
        if rule["condition"](features):
            reco = WifiRecommendation.objects.create(
                ap=ap,
                type_recommandation=rule["type"],
                gravite=rule["gravite"],
                message=rule["message"],
                justification=rule["justification"],
            )
            recommandations.append(reco)

    return recommandations
