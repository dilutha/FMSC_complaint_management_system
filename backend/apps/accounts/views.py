"""Authentication, profile, and user/authority management (Member B).

Response shapes for /auth/token/ and /auth/me/ keep the placeholder contract
the case module's Flutter screens were built against; fields were only added.
"""
from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.services import record as audit
from apps.cases.models import Authority

from .authentication import token_expired
from .models import User
from .permissions import CanManageAuthorities, CanManageUsers
from .serializers import (
    AUTHORITY_MEMBER_ROLES,
    AuthorityAdminSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    MeSerializer,
    UserAdminSerializer,
    search_users,
)

TokenResponse = inline_serializer("TokenResponse", {"token": serializers.CharField(), "user": MeSerializer()})


def _me(user):
    return MeSerializer(user).data


def issue_token(user) -> Token:
    """Reuse a still-valid token (other devices stay signed in), else rotate."""
    token = Token.objects.filter(user=user).first()
    if token and not token_expired(token):
        return token
    Token.objects.filter(user=user).delete()
    return Token.objects.create(user=user)


class LoginThrottle(ScopedRateThrottle):
    scope_attr = "throttle_scope"


class TokenLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=TokenResponse)
    def post(self, request):
        ser = LoginSerializer(data=request.data, context={"request": request})
        if not ser.is_valid():
            identifier = str(request.data.get("username", ""))[:150]
            known = User.objects.filter(username=identifier).values_list("pk", flat=True).first()
            audit("auth.login_failed", entity_type="user", entity_id=known or "unknown",
                  metadata={"identifier": identifier})
            ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]
        token = issue_token(user)
        audit("auth.login", actor=user, entity=user, entity_label=user.username)
        return Response({"token": token.key, "user": _me(user)})


class TokenLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        audit("auth.logout", actor=request.user, entity=request.user, entity_label=request.user.username)
        return Response(status=204)


class MeView(APIView):
    """GET the signed-in user; PATCH updates contact details only. Names, email
    and role are managed by a system administrator."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(_me(request.user))

    @extend_schema(request=MeSerializer, responses=MeSerializer)
    def patch(self, request):
        ser = MeSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(_me(request.user))


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [LoginThrottle]
    throttle_scope = "password_change"

    @extend_schema(request=ChangePasswordSerializer, responses=TokenResponse)
    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = request.user
        with transaction.atomic():
            user.set_password(ser.validated_data["new_password"])
            user.save(update_fields=["password"])
            # Sign out every other device: old tokens stop working.
            Token.objects.filter(user=user).delete()
            token = Token.objects.create(user=user)
            audit("auth.password_changed", actor=user, entity=user, entity_label=user.username)
        return Response({"token": token.key, "user": _me(user)})


# --- User management (system administrators) -------------------------------------------

_AUDITED_USER_FIELDS = ("username", "email", "first_name", "last_name", "role", "department", "contact_number",
                        "is_active")


class UserAdminViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                       mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Create, edit, activate and deactivate accounts. Accounts are never
    deleted (cases and history refer to them); deactivate instead."""

    serializer_class = UserAdminSerializer
    permission_classes = [CanManageUsers]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = User.objects.prefetch_related("authorities").order_by("username")
        p = self.request.query_params
        if p.get("search"):
            qs = search_users(qs, p["search"])
        if p.get("role"):
            qs = qs.filter(role=p["role"])
        if p.get("is_active") in ("true", "false"):
            qs = qs.filter(is_active=p["is_active"] == "true")
        return qs

    @extend_schema(parameters=[OpenApiParameter("search", str), OpenApiParameter("role", str),
                               OpenApiParameter("is_active", bool)])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        password = serializer.validated_data.pop("password")
        authorities = serializer.validated_data.pop("authorities", [])
        user = User(**serializer.validated_data)
        user.set_password(password)
        user.save()
        user.authorities.set(authorities)
        serializer.instance = user
        audit("user.created", actor=self.request.user, entity=user, entity_label=user.username,
              new={**_snapshot(user), "authority_ids": [a.pk for a in authorities]})

    @transaction.atomic
    def perform_update(self, serializer):
        user = serializer.instance
        before = _snapshot(user)
        before_authorities = sorted(user.authorities.values_list("pk", flat=True))
        password = serializer.validated_data.pop("password", None)
        user = serializer.save()
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
            Token.objects.filter(user=user).delete()
            audit("user.password_reset", actor=self.request.user, entity=user, entity_label=user.username)
        if user.role not in AUTHORITY_MEMBER_ROLES and user.authorities.exists():
            user.authorities.clear()  # a non-staff role must not keep case access
        if not user.is_active:
            Token.objects.filter(user=user).delete()  # end active sessions immediately

        after = _snapshot(user)
        after_authorities = sorted(user.authorities.values_list("pk", flat=True))
        changed = {k for k in before if before[k] != after[k]}
        actor = self.request.user
        if "role" in changed:
            audit("user.role_changed", actor=actor, entity=user, entity_label=user.username,
                  previous={"role": before["role"]}, new={"role": after["role"]})
        if "is_active" in changed:
            audit("user.activated" if user.is_active else "user.deactivated", actor=actor, entity=user,
                  entity_label=user.username, previous={"is_active": before["is_active"]},
                  new={"is_active": after["is_active"]})
        other = changed - {"role", "is_active"}
        if other:
            audit("user.updated", actor=actor, entity=user, entity_label=user.username,
                  previous={k: before[k] for k in other}, new={k: after[k] for k in other})
        if before_authorities != after_authorities:
            audit("user.authorities_changed", actor=actor, entity=user, entity_label=user.username,
                  previous={"authority_ids": before_authorities}, new={"authority_ids": after_authorities})


def _snapshot(user):
    return {field: getattr(user, field) for field in _AUDITED_USER_FIELDS}


# --- Authority management (administrators) ----------------------------------------------

_AUDITED_AUTHORITY_FIELDS = ("name", "code", "unit", "officer_name", "designation", "email", "phone", "is_active")


class AuthorityAdminViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                            mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Add, edit, activate and deactivate responsible authorities. Authorities
    with case history cannot be deleted, so deactivation replaces deletion."""

    serializer_class = AuthorityAdminSerializer
    permission_classes = [CanManageAuthorities]
    http_method_names = ["get", "post", "patch", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        return Authority.objects.order_by("name")

    def perform_create(self, serializer):
        authority = serializer.save()
        audit("authority.created", actor=self.request.user, entity=authority,
              new={f: getattr(authority, f) for f in _AUDITED_AUTHORITY_FIELDS})

    def perform_update(self, serializer):
        before = {f: getattr(serializer.instance, f) for f in _AUDITED_AUTHORITY_FIELDS}
        authority = serializer.save()
        after = {f: getattr(authority, f) for f in _AUDITED_AUTHORITY_FIELDS}
        changed = [f for f in _AUDITED_AUTHORITY_FIELDS if before[f] != after[f]]
        if changed:
            action = "authority.updated"
            if changed == ["is_active"]:
                action = "authority.activated" if authority.is_active else "authority.deactivated"
            audit(action, actor=self.request.user, entity=authority, previous={f: before[f] for f in changed},
                  new={f: after[f] for f in changed})
