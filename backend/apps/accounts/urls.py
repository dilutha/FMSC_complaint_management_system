"""Authentication endpoints, mounted at /api/v1/auth/ (shared contract)."""
from django.urls import path

from .views import ChangePasswordView, MeView, TokenLoginView, TokenLogoutView

urlpatterns = [
    path("token/", TokenLoginView.as_view(), name="auth-token"),
    path("logout/", TokenLogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
]
