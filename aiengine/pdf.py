from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger('monitoring')

def generer_pdf_reportlab(rapport):
    """
    Génère un rapport PDF professionnel en utilisant ReportLab Platypus.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    
    # Styles personnalisés
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor("#0ea5e9"),
        alignment=1,
        spaceAfter=20
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=10
    )
    
    body_style = styles['BodyText']
    
    elements = []
    
    # Titre
    elements.append(Paragraph("RAPPORT EXÉCUTIF INFRACONTROL", title_style))
    elements.append(Spacer(1, 12))
    
    # Informations générales
    elements.append(Paragraph("Informations Générales", subtitle_style))
    data = [
        ["ID Rapport", str(rapport.id)],
        ["Période", f"{rapport.date_debut} au {rapport.date_fin}"],
        ["Généré le", rapport.cree_le.strftime("%d/%m/%Y %H:%M") if hasattr(rapport, 'cree_le') else "N/A"],
        ["Incidents détectés", str(getattr(rapport, 'nb_incidents', 'N/A'))],
        ["Équipements impactés", str(getattr(rapport, 'nb_equipements_impactes', 'N/A'))],
    ]
    
    t = Table(data, colWidths=[150, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), HexColor("#f1f5f9")),
        ('TEXTCOLOR', (0, 0), (0, -1), HexColor("#475569")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#808080")),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Résumé global
    elements.append(Paragraph("Résumé de la période", subtitle_style))
    elements.append(Paragraph(rapport.resume_global or "Aucun résumé disponible pour cette période.", body_style))
    elements.append(Spacer(1, 20))
    
    # Analyse IA
    elements.append(Paragraph("Analyse Intelligente (Infr-AI)", subtitle_style))
    analyse_text = getattr(rapport, 'analyse_ia', None) or "L'analyse IA n'a pas pu être générée pour ce rapport."
    # Nettoyage minimal pour éviter les erreurs de parsing Platypus
    analyse_text = analyse_text.replace('\n', '<br/>')
    elements.append(Paragraph(analyse_text, body_style))
    
    # Construction du PDF
    doc.build(elements)
    
    pdf = buffer.getvalue()
    buffer.close()
    
    # Sauvegarde
    filename = f"rapport_{rapport.id}_infracontrol.pdf"
    rapport.fichier_pdf.save(filename, ContentFile(pdf))
    rapport.save()
    
    logger.info(f"PDF ReportLab généré pour le rapport ID {rapport.id}")
    return filename