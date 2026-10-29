"""Token authentication with expiry.

Keeps the agreed `Authorization: Token <key>` header (shared contract with the
Flutter client) but rejects tokens older than FMSC_AUTH["TOKEN_TTL_HOURS"].
Expired tokens are deleted, so the client must sign in again.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


def token_expired(token) -> bool:
    ttl_hours = settings.FMSC_AUTH["TOKEN_TTL_HOURS"]
    return bool(ttl_hours) and token.created < timezone.now() - timedelta(hours=ttl_hours)


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if token_expired(token):
            token.delete()
            raise AuthenticationFailed("Your session has expired. Please sign in again.")
        return user, token
