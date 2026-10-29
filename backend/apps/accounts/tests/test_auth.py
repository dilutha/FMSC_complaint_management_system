from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.audit.models import AuditEvent
from apps.platform_testing import PASSWORD, make_user

LOGIN = "/api/v1/auth/token/"
ME = "/api/v1/auth/me/"


def token_client(key):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {key}")
    return client


@pytest.mark.django_db
class TestLogin:
    def test_login_by_username_returns_token_and_capabilities(self, api, admin_user):
        res = api().post(LOGIN, {"username": admin_user.username, "password": PASSWORD})
        assert res.status_code == 200
        assert res.data["user"]["role"] == "case_admin"
        assert "view_dashboard" in res.data["user"]["capabilities"]
        assert "manage_users" not in res.data["user"]["capabilities"]
        assert token_client(res.data["token"]).get(ME).data["id"] == admin_user.pk

    def test_login_by_email_is_case_insensitive(self, api, student):
        res = api().post(LOGIN, {"username": student.email.upper(), "password": PASSWORD})
        assert res.status_code == 200 and res.data["user"]["id"] == student.pk

    def test_wrong_password_is_rejected_and_audited_without_the_password(self, api, student):
        res = api().post(LOGIN, {"username": student.username, "password": "not-the-password"})
        assert res.status_code == 400 and res.data["error"]["code"] == "validation_error"
        event = AuditEvent.objects.get(action="auth.login_failed")
        assert event.entity_id == str(student.pk)
        assert "not-the-password" not in str(event.metadata) + str(event.new_value)

    def test_unknown_user_gets_the_same_message(self, api, student):
        known = api().post(LOGIN, {"username": student.username, "password": "x"}).data["error"]
        unknown = api().post(LOGIN, {"username": "nobody-here", "password": "x"}).data["error"]
        assert known == unknown

    def test_inactive_user_cannot_sign_in(self, api, student):
        student.is_active = False
        student.save()
        assert api().post(LOGIN, {"username": student.username, "password": PASSWORD}).status_code == 400

    def test_passwords_are_hashed(self, student):
        assert student.password != PASSWORD and student.password.startswith(("pbkdf2_", "argon2", "bcrypt"))


@pytest.mark.django_db
class TestTokenLifecycle:
    def test_expired_token_is_rejected_and_deleted(self, settings, student):
        settings.FMSC_AUTH = {"TOKEN_TTL_HOURS": 12}
        token = Token.objects.create(user=student)
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=13))
        res = token_client(token.key).get(ME)
        assert res.status_code == 401 and res.data["error"]["code"] == "authentication_failed"
        assert not Token.objects.filter(pk=token.pk).exists()

    def test_login_reuses_a_valid_token_and_rotates_an_expired_one(self, api, student):
        first = api().post(LOGIN, {"username": student.username, "password": PASSWORD}).data["token"]
        again = api().post(LOGIN, {"username": student.username, "password": PASSWORD}).data["token"]
        assert first == again
        Token.objects.filter(key=first).update(created=timezone.now() - timedelta(days=2))
        rotated = api().post(LOGIN, {"username": student.username, "password": PASSWORD}).data["token"]
        assert rotated != first

    def test_logout_revokes_the_token(self, api, student):
        key = api().post(LOGIN, {"username": student.username, "password": PASSWORD}).data["token"]
        client = token_client(key)
        assert client.post("/api/v1/auth/logout/").status_code == 204
        assert client.get(ME).status_code == 401


@pytest.mark.django_db
class TestProfile:
    def test_user_can_update_contact_details_but_not_role_or_name(self, api, student):
        res = api(student).patch(ME, {"contact_number": "0710000000", "role": "system_admin",
                                      "first_name": "Changed"}, format="json")
        assert res.status_code == 200
        student.refresh_from_db()
        assert student.contact_number == "0710000000"
        assert student.role == Role.STUDENT and student.first_name == "Test"

    def test_change_password_requires_current_password(self, api, student):
        res = api(student).post("/api/v1/auth/change-password/",
                                {"current_password": "wrong", "new_password": "An0ther-Synthetic-pass"})
        assert res.status_code == 400 and "current_password" in res.data["error"]["details"]

    def test_change_password_rejects_weak_password(self, api, student):
        res = api(student).post("/api/v1/auth/change-password/",
                                {"current_password": PASSWORD, "new_password": "12345678"})
        assert res.status_code == 400

    def test_change_password_signs_out_other_devices(self, api, student):
        old = api().post(LOGIN, {"username": student.username, "password": PASSWORD}).data["token"]
        res = token_client(old).post("/api/v1/auth/change-password/",
                                     {"current_password": PASSWORD, "new_password": "An0ther-Synthetic-pass"})
        assert res.status_code == 200 and res.data["token"] != old
        assert token_client(old).get(ME).status_code == 401
        assert token_client(res.data["token"]).get(ME).status_code == 200
        assert AuditEvent.objects.filter(action="auth.password_changed", actor=student).exists()


@pytest.mark.django_db
class TestCapabilities:
    @pytest.mark.parametrize("role,expected", [
        (Role.STUDENT, ["submit_cases"]),
        (Role.LECTURER, ["submit_cases"]),
        (Role.NON_ACADEMIC_STAFF, ["submit_cases"]),
        (Role.AUTHORITY, ["handle_assigned_cases"]),
        (Role.MANAGEMENT, ["view_dashboard"]),
        (Role.CASE_ADMIN, ["evaluate_suggestions", "review_cases", "view_dashboard"]),
        (Role.SYSTEM_ADMIN, ["manage_authorities", "manage_users", "post_admin_messages", "view_audit_log",
                             "view_dashboard"]),
    ])
    def test_role_capabilities(self, role, expected):
        assert make_user(role).capabilities() == expected

    def test_inactive_user_has_no_capabilities(self):
        user = make_user(Role.SYSTEM_ADMIN, is_active=False)
        assert user.capabilities() == []
