from django.urls import path
from . import views

urlpatterns = [
    path(
        "rapports/generer/",
        views.generer_rapport_executif_view,
        name="generer_rapport_executif"
    ),
]