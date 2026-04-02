from .pdf import generer_pdf_reportlab

def generer_pdf(rapport, mode="auto"):
    """
    Générateur de PDF unifié utilisant ReportLab.
    WeasyPrint a été retiré pour compatibilité Windows locale.
    """
    # Dans tous les modes (auto, exec, secours), on utilise désormais ReportLab
    return generer_pdf_reportlab(rapport)