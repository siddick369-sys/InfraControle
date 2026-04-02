from django.urls import path
from .views import LogsStatsAPI

urlpatterns = [
    path("logs/stats/", LogsStatsAPI.as_view(), name="logs_stats_api"),
]