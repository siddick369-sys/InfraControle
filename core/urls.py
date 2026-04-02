# path("api/", include("core.api.urls")),

from django.urls import path, include
from core import views
from core.api import urls as api_urls

urlpatterns = [
    # ==============================
    # 🔐 AUTHENTIFICATION & COMPTE
    # ==============================
    path("inscription/", views.inscription_view, name="inscription"),
    path("connexion/", views.connexion_view, name="connexion"),
    path("deconnexion/", views.deconnexion_view, name="deconnexion"),

    # ==============================
    # 🧾 VÉRIFICATION DE COMPTE (OTP)
    # ==============================
    path("verification/", views.verification_view, name="verification_compte"),
    path("renvoi-code/", views.renvoi_code, name="renvoi_code"),

    # ==============================
    # 🔑 2FA (Double Authentification)
    # ==============================
    path("2fa/activer/", views.activer_2fa_view, name="activer_2fa"),
    path("2fa/qrcode/", views.qr_code_2fa, name="qr_code_2fa"),
    path("2fa/confirm/", views.confirm_reset_2fa, name="confirm_reset_2fa"),
    path("2fa/desactiver/", views.desactiver_2fa, name="desactiver_2fa"),
    path("2fa/verifier/", views.verification_2fa, name="verification_2fa"),
    path("2fa/reset/", views.reset_2fa_request, name="reset_2fa_request"),

    # ==============================
    # 🔁 MOT DE PASSE (RESET)
    # ==============================
    path("mot-de-passe/oubli/", views.demande_reset_view, name="reset_password_request"),
    path("mot-de-passe/oubli/reset", views.verification_reset, name="verification_reset"),
    path('mot-de-passe/reinitialiser/<str:token>/', views.reset_password_confirm_view, name='reset_password_confirm'),
    # ==============================
    # 👤 PROFIL UTILISATEUR
    # ==============================
    path("profil/", views.profile_view, name="profile"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("profil/modifier/", views.edit_profile, name="edit_profile"),
    path('compte/gele/', views.page_compte_gele_view, name='compte_gele'),
    path('compte/reactiver/', views.recuperer_compte_view, name='recuperer_compte'),
    path('compte/supprimer/', views.supprimer_compte_view, name='supprimer_compte'),


    # ==============================
    # 📊 TABLEAU DE LOGS / ANALYTICS
    # # ==============================
    path("logs/dashboard/", views.logs_dashboard_view, name="logs_dashboard"),

    # ==============================
    # ⚙️ API REST (Chart.js & Monitoring)
    # ==============================
    path("api/", include(api_urls)),
    path("set_form_start_time/", views.set_form_start_time, name="set_form_start_time"),

    # ==============================
    # 🧱 ENDPOINTS TECHNIQUES / TEST
    # # ==============================
    # path("test/alerte/", views.test_alerte, name="test_alerte"),
    path("test/ping/", views.test_ping, name="test_ping"),
]