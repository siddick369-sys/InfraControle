from django.urls import path
from . import views

urlpatterns = [
    path(
        "rapports/generer/",
        views.generer_rapport_executif_view,
        name="generer_rapport_executif"
    ),
    path(
        "oracle/chat/",
        views.oracle_chat_ajax,
        name="oracle_chat_ajax"
    ),
    path(
        "execute_cmd/",
        views.oracle_execute_cmd_ajax,
        name="oracle_execute_cmd"
    ),
]