from django.core.management.base import BaseCommand
from django.utils import timezone
from monitoring.smart_monitor import analyser_toutes_anomalies
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Analyse tous les équipements réseau et détecte les anomalies (manuel ou CRON)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("🔍 Lancement de l'analyse des anomalies réseau..."))
        self.stdout.write("Horodatage : " + timezone.now().strftime("%d/%m/%Y %H:%M:%S"))

        try:
            resultats = analyser_toutes_anomalies()
            nb_total = len(resultats)
            nb_anomalies = sum(1 for _, anomalies in resultats if anomalies)

            self.stdout.write(self.style.SUCCESS(
                f"✔️ Analyse terminée — {nb_total} équipements analysés, {nb_anomalies} anomalies détectées."
            ))
            logger.info(f"[MANUEL] {nb_total} équipements analysés — {nb_anomalies} anomalies détectées.")

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Erreur pendant l’analyse : {e}"))
            logger.error(f"[MANUEL] Erreur lors de l’analyse : {e}", exc_info=True)