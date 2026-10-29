import pytest
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.cases.models import Authority
from apps.platform_testing import make_user

USERS = "/api/v1/manage/users/"
AUTHORITIES = "/api/v1/manage/authorities/"

PROTECTED = [
    ("/api/v1/dashboard/summary/", {"management", "admin_user", "system_admin"}),
    ("/api/v1/dashboard/trends/", {"management", "admin_user", "system_admin"}),
    ("/api/v1/dashboard/workload/", {"management", "admin_user", "system_admin"}),
    ("/api/v1/dashboard/ageing/", {"management", "admin_user", "system_admin"}),
    ("/api/v1/reports/cases/", {"management", "admin_user", "system_admin"}),
    ("/api/v1/audit-events/", {"system_admin"}),
    (USERS, {"system_admin"}),
    (AUTHORITIES, {"admin_user", "system_admin"}),
]
ROLES = ["student", "officer", "management", "admin_user", "system_admin"]


@pytest.mark.django_db
@pytest.mark.parametrize("url,allowed", PROTECTED)
@pytest.mark.parametrize("who", ROLES)
def test_role_permission_matrix(request, api, url, allowed, who):
    user = request.getfixturevalue(who)
    res = api(user).get(url)
    assert res.status_code == (200 if who in allowed else 403), (who, url, res.status_code)


@pytest.mark.django_db
@pytest.mark.parametrize("url", [p for p, _ in PROTECTED] + ["/api/v1/notifications/", "/api/v1/suggestions/"])
def test_anonymous_requests_are_rejected(api, url):
    assert api().get(url).status_code == 401


@pytest.mark.django_db
class TestUserManagement:
    def test_create_user_hashes_password_and_audits(self, api, system_admin, maintenance):
        res = api(system_admin).post(USERS, {
            "username": "new.officer", "email": "new.officer@example.test", "first_name": "New",
            "last_name": "Officer", "role": "authority", "password": "Synthetic-pass-456",
            "authority_ids": [maintenance.pk],
        }, format="json")
        assert res.status_code == 201, res.data
        assert "password" not in res.data
        user = User.objects.get(username="new.officer")
        assert user.check_password("Synthetic-pass-456") and user.password != "Synthetic-pass-456"
        assert list(user.authorities.all()) == [maintenance]
        event = AuditEvent.objects.get(action="user.created")
        assert event.actor == system_admin and "Synthetic-pass-456" not in str(event.new_value)

    def test_new_user_requires_a_strong_password(self, api, system_admin):
        res = api(system_admin).post(USERS, {"username": "weak", "role": "student", "password": "password"})
        assert res.status_code == 400 and "password" in res.data["error"]["details"]

    def test_duplicate_email_rejected(self, api, system_admin, student):
        res = api(system_admin).post(USERS, {"username": "dup", "email": student.email.upper(), "role": "student",
                                             "password": "Synthetic-pass-456"})
        assert res.status_code == 400 and "email" in res.data["error"]["details"]

    def test_role_change_is_audited_with_previous_and_new_value(self, api, system_admin, student):
        res = api(system_admin).patch(f"{USERS}{student.pk}/", {"role": "lecturer"}, format="json")
        assert res.status_code == 200
        event = AuditEvent.objects.get(action="user.role_changed")
        assert event.previous_value == {"role": "student"} and event.new_value == {"role": "lecturer"}

    def test_admin_cannot_change_own_role_or_deactivate_self(self, api, system_admin):
        assert api(system_admin).patch(f"{USERS}{system_admin.pk}/", {"role": "student"}).status_code == 400
        assert api(system_admin).patch(f"{USERS}{system_admin.pk}/", {"is_active": False}).status_code == 400

    def test_deactivation_ends_sessions(self, api, system_admin, student):
        Token.objects.create(user=student)
        res = api(system_admin).patch(f"{USERS}{student.pk}/", {"is_active": False}, format="json")
        assert res.status_code == 200
        assert not Token.objects.filter(user=student).exists()
        assert AuditEvent.objects.filter(action="user.deactivated", entity_id=str(student.pk)).exists()

    def test_students_cannot_be_given_authority_membership(self, api, system_admin, student, maintenance):
        res = api(system_admin).patch(f"{USERS}{student.pk}/", {"authority_ids": [maintenance.pk]}, format="json")
        assert res.status_code == 400

    def test_leaving_the_authority_role_removes_case_access(self, api, system_admin, officer, maintenance):
        res = api(system_admin).patch(f"{USERS}{officer.pk}/", {"role": "lecturer"}, format="json")
        assert res.status_code == 200
        assert not maintenance.members.filter(pk=officer.pk).exists()
        assert AuditEvent.objects.filter(action="user.authorities_changed").exists()

    def test_users_cannot_be_deleted(self, api, system_admin, student):
        assert api(system_admin).delete(f"{USERS}{student.pk}/").status_code == 405

    def test_search_and_filter(self, api, system_admin):
        make_user(Role.MANAGEMENT, username="dean.office")
        res = api(system_admin).get(USERS, {"search": "dean", "role": "management"})
        assert [u["username"] for u in res.data["results"]] == ["dean.office"]


@pytest.mark.django_db
class TestAuthorityManagement:
    def test_create_update_and_deactivate_are_audited(self, api, admin_user):
        res = api(admin_user).post(AUTHORITIES, {"name": "Library", "code": "library", "unit": "Library services"})
        assert res.status_code == 201
        pk = res.data["id"]
        assert api(admin_user).patch(f"{AUTHORITIES}{pk}/", {"is_active": False}).status_code == 200
        assert not Authority.objects.get(pk=pk).is_active
        actions = list(AuditEvent.objects.filter(entity_type="authority").values_list("action", flat=True))
        assert set(actions) == {"authority.created", "authority.deactivated"}

    def test_lists_inactive_authorities_too(self, api, admin_user, maintenance):
        Authority.objects.create(name="Old Unit", code="old", is_active=False)
        names = {a["name"] for a in api(admin_user).get(AUTHORITIES).data}
        assert {"Maintenance Division", "Old Unit"} <= names

    def test_authorities_cannot_be_deleted(self, api, admin_user, maintenance):
        assert api(admin_user).delete(f"{AUTHORITIES}{maintenance.pk}/").status_code == 405
