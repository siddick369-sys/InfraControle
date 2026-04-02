from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from core.models import JournalActivite

class LogsStatsAPI(APIView):
    """Retourne les statistiques de logs pour Chart.js"""

    def get(self, request):
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        logs = JournalActivite.objects.filter(date_action__gte=last_30_days)

        # Regroupement par jour
        data_by_day = {}
        for log in logs:
            jour = log.date_action.strftime("%Y-%m-%d")
            data_by_day[jour] = data_by_day.get(jour, 0) + 1

        labels = list(data_by_day.keys())
        values = list(data_by_day.values())

        # Comptage des types d’action
        actions = {}
        for log in logs:
            a = log.action
            actions[a] = actions.get(a, 0) + 1

        return Response({
            "labels": labels,
            "values": values,
            "actions": actions,
            "total_logs": logs.count(),
        })