from django.urls import path
from . import views

urlpatterns = [
    path("", views.liste_decouvertes, name="liste_decouvertes"),
]