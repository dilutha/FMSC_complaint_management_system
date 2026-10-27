"""PLACEHOLDER auth endpoints so the Flutter case screens can run end to end.

Member B owns authentication; replace these views (e.g. with JWT or university
SSO) while keeping the response shape documented in docs/SHARED_CONTRACTS.md.
"""
from django.urls import path

from .views import MeView, TokenLoginView, TokenLogoutView

urlpatterns = [
    path("token/", TokenLoginView.as_view(), name="auth-token"),
    path("logout/", TokenLogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
]
