from .client import appeler_ia
from .prompts import PROMPT_RAPPORT_EXECUTIF


def generer_analyse_executive(contexte):
    """
    Appelle l’IA pour générer le texte du rapport exécutif
    """
    prompt = PROMPT_RAPPORT_EXECUTIF.format(
        donnees=contexte
    )

    return appeler_ia(
        prompt=prompt
    )