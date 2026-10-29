"""End-to-end API workflows for every role, using the seeded demo accounts and
real token sign-in (no force_authenticate). Runs on the isolated test
database only; never on Supabase."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.management.commands.seed_demo_users import DEMO_PASSWORD, DEMO_USERS
from apps.accounts.models import User
from apps.cases.models import Category

API = "/api/v1"


@pytest.fixture
def demo(db, settings, django_capture_on_commit_callbacks):
    settings.DEBUG = True
    call_command("seed_demo_users", quiet_table=True, stdout=open("/dev/null", "w"))
    return {username: User.objects.get(username=username) for username, *_ in DEMO_USERS}


def sign_in(username, password=DEMO_PASSWORD):
    client = APIClient()
    res = client.post(f"{API}/auth/token/", {"username": username, "password": password}, format="json")
    assert res.status_code == 200, (username, res.status_code, res.data)
    client.credentials(HTTP_AUTHORIZATION=f"Token {res.data['token']}")
    return client


@pytest.fixture
def events(django_capture_on_commit_callbacks):
    """Run after-commit integration events (notifications, audit, suggestion sync) as in production."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


def submit(client, category, **overrides):
    data = {
        "title": "Projector not working in Hall A",
        "description": "The projector in Hall A does not turn on during lectures.",
        "case_type": "complaint",
        "category_id": category.pk,
        "location": "Hall A",
        "requested_priority": "normal",
        "declaration_accepted": True,
        **overrides,
    }
    return client.post(f"{API}/cases/", data, format="json")


# --- Demo users ----------------------------------------------------------------------------


@pytest.mark.django_db
class TestDemoUsers:
    def test_every_demo_account_signs_in_with_its_role(self, demo):
        for username, role, *_ in DEMO_USERS:
            res = APIClient().post(f"{API}/auth/token/", {"username": username, "password": DEMO_PASSWORD})
            assert res.status_code == 200 and res.data["user"]["role"] == role, username

    def test_passwords_are_hashed_and_roles_safe(self, demo):
        for user in demo.values():
            assert user.password.startswith("pbkdf2_sha256$") and DEMO_PASSWORD not in user.password
            assert user.email.endswith("@example.com") and user.is_active
        assert [u.username for u in demo.values() if u.is_superuser or u.is_staff] == ["demo_system_admin"]
        assert list(demo["demo_authority"].authorities.values_list("code", flat=True)) == ["maintenance"]

    def test_seeding_is_idempotent(self, demo, settings):
        call_command("seed_demo_users", quiet_table=True, stdout=open("/dev/null", "w"))
        assert User.objects.filter(username__startswith="demo_").count() == len(DEMO_USERS)

    def test_refuses_outside_development(self, db, settings, monkeypatch):
        settings.DEBUG = False
        monkeypatch.delenv("FMSC_ALLOW_DEMO_USERS", raising=False)
        with pytest.raises(CommandError, match="local development only"):
            call_command("seed_demo_users", stdout=open("/dev/null", "w"))
        assert not User.objects.filter(username__startswith="demo_").exists()

    def test_demo_credentials_are_not_exposed_by_the_api(self, demo):
        body = sign_in("demo_system_admin").get(f"{API}/manage/users/").content.decode()
        assert DEMO_PASSWORD not in body and "pbkdf2" not in body


# --- Authentication ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuthentication:
    def test_wrong_password_and_unknown_user_get_the_same_answer(self, demo):
        wrong = APIClient().post(f"{API}/auth/token/", {"username": "demo_student", "password": "nope"})
        unknown = APIClient().post(f"{API}/auth/token/", {"username": "nobody", "password": "nope"})
        assert wrong.status_code == unknown.status_code == 400
        assert wrong.data == unknown.data

    def test_empty_and_malformed_requests(self, demo):
        empty = APIClient().post(f"{API}/auth/token/", {"username": "", "password": ""}, format="json")
        assert empty.status_code == 400 and set(empty.data["error"]["details"]) == {"username", "password"}
        malformed = APIClient().post(f"{API}/auth/token/", "{not json", content_type="application/json")
        assert malformed.status_code == 400 and malformed.data["error"]["code"] == "parse_error"

    def test_inactive_account_cannot_sign_in(self, demo):
        User.objects.filter(username="demo_lecturer").update(is_active=False)
        res = APIClient().post(f"{API}/auth/token/", {"username": "demo_lecturer", "password": DEMO_PASSWORD})
        assert res.status_code == 400

    def test_protected_endpoints_need_a_valid_token(self, demo):
        assert APIClient().get(f"{API}/cases/").status_code == 401
        bad = APIClient()
        bad.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
        assert bad.get(f"{API}/cases/").data["error"]["code"] == "authentication_failed"

    def test_logout_invalidates_the_token(self, demo):
        client = sign_in("demo_student")
        assert client.post(f"{API}/auth/logout/").status_code == 204
        assert client.get(f"{API}/auth/me/").status_code == 401


# --- Complaint workflow across roles -------------------------------------------------------------


@pytest.mark.django_db
class TestComplaintWorkflow:
    def test_full_lifecycle_submit_assign_resolve_verify(self, demo, events):
        category = Category.objects.get(code="classroom")
        student, admin = sign_in("demo_student"), sign_in("demo_case_admin")
        officer, it_officer = sign_in("demo_authority"), sign_in("demo_it_officer")

        # Validation first: nothing is saved.
        bad = submit(student, category, title="", declaration_accepted=False)
        assert bad.status_code == 400 and "title" in bad.data["error"]["details"]

        with events():
            res = submit(student, category)
        assert res.status_code == 201 and res.data["status"] == "submitted"
        case_id, number = res.data["id"], res.data["case_number"]
        assert [c["case_number"] for c in student.get(f"{API}/cases/?mine=true").data["results"]] == [number]

        # Other users cannot see it; the student cannot manage it.
        assert sign_in("demo_lecturer").get(f"{API}/cases/{case_id}/").status_code == 404
        assert student.post(f"{API}/cases/{case_id}/transition/", {"to_status": "under_review"}).status_code == 403

        # Administrator reviews and assigns to the Maintenance Division.
        with events():
            assert admin.post(f"{API}/cases/{case_id}/transition/", {"to_status": "under_review"}).status_code == 200
            maintenance = demo["demo_authority"].authorities.get()
            res = admin.post(f"{API}/cases/{case_id}/assign/", {"authority_id": maintenance.pk})
        assert res.status_code == 200 and res.data["status"] == "assigned"

        # Unit boundary: the IT officer cannot see a Maintenance case.
        assert it_officer.get(f"{API}/cases/{case_id}/").status_code == 404
        assert case_id in [c["id"] for c in officer.get(f"{API}/cases/").data["results"]]

        # The responsible officer records progress and solves it; not admin-only actions.
        with events():
            res = officer.post(f"{API}/cases/{case_id}/updates/",
                               {"body": "Technician booked for Tuesday.", "kind": "progress", "new_status": "in_progress"})
            assert res.status_code in (200, 201), res.data
            res = officer.post(f"{API}/cases/{case_id}/transition/",
                               {"to_status": "solved", "resolution_note": "Replaced the projector lamp."})
        assert res.status_code == 200 and res.data["status"] == "solved"
        assert officer.post(f"{API}/cases/{case_id}/assign/", {"authority_id": maintenance.pk}).status_code == 403

        # Student sees the resolution and notification, then confirms.
        detail = student.get(f"{API}/cases/{case_id}/").data
        assert detail["latest_resolution"]["note"] == "Replaced the projector lamp."
        assert detail["allowed_actions"]["can_verify_resolution"] is True
        titles = [n["title"] for n in student.get(f"{API}/notifications/").data["results"]]
        assert any("solved" in t for t in titles)
        with events():
            res = student.post(f"{API}/cases/{case_id}/verify-resolution/", {"confirmed": True, "feedback": ""})
        assert res.status_code == 200 and res.data["status"] == "closed"

        # Timeline is visible to the submitter; internal notes are not.
        assert student.get(f"{API}/cases/{case_id}/timeline/").status_code == 200

    def test_student_can_reopen_a_closed_case_with_a_reason(self, demo, events):
        category = Category.objects.get(code="classroom")
        student, admin = sign_in("demo_student"), sign_in("demo_case_admin")
        case_id = submit(student, category).data["id"]
        maintenance = demo["demo_authority"].authorities.get()
        with events():
            admin.post(f"{API}/cases/{case_id}/assign/", {"authority_id": maintenance.pk})
            admin.post(f"{API}/cases/{case_id}/transition/", {"to_status": "solved", "resolution_note": "Fixed the cable."})
            student.post(f"{API}/cases/{case_id}/verify-resolution/", {"confirmed": True})
        assert student.post(f"{API}/cases/{case_id}/reopen/", {"reason": ""}).status_code == 400
        res = student.post(f"{API}/cases/{case_id}/reopen/", {"reason": "It stopped working again."})
        assert res.status_code == 200 and res.data["status"] == "reopened"


# --- Suggestions ---------------------------------------------------------------------------------


@pytest.mark.django_db
class TestSuggestionWorkflow:
    def test_submit_decide_implement(self, demo, events):
        category = Category.objects.get(code="other")
        student, admin = sign_in("demo_student"), sign_in("demo_case_admin")
        officer, management = sign_in("demo_authority"), sign_in("demo_management")
        with events():
            res = submit(student, category, case_type="suggestion", title="More charging points in the library",
                         description="Add power outlets near the study tables.", location="Library")
        sid = res.data["id"]
        assert student.get(f"{API}/suggestions/{sid}/").data["status"] == "submitted"

        # Only administrators decide; management can view.
        assert student.post(f"{API}/suggestions/{sid}/decision/", {"decision": "decline", "reason": "x" * 20}).status_code == 403
        assert management.post(f"{API}/suggestions/{sid}/decision/", {"decision": "start_evaluation"}).status_code == 403
        assert management.get(f"{API}/suggestions/{sid}/").status_code == 200
        assert admin.post(f"{API}/suggestions/{sid}/decision/", {"decision": "decline", "reason": ""}).status_code == 400

        maintenance = demo["demo_authority"].authorities.get()
        with events():
            res = admin.post(f"{API}/suggestions/{sid}/decision/",
                             {"decision": "accept", "responsible_unit_id": maintenance.pk, "reason": "Approved."},
                             format="json")
        assert res.status_code == 200 and res.data["status"] == "accepted"
        with events():
            assert officer.post(f"{API}/suggestions/{sid}/progress/", {"note": "Ordered sockets.",
                                                                        "percent_complete": 50}).status_code == 200
            res = officer.post(f"{API}/suggestions/{sid}/implementation/", {"summary": "Twelve sockets installed."})
        assert res.status_code == 200 and res.data["status"] == "implemented"
        assert any("implemented" in n["title"] for n in student.get(f"{API}/notifications/").data["results"])


# --- Management, administration and notifications ---------------------------------------------------


@pytest.mark.django_db
class TestRoleAccess:
    @pytest.mark.parametrize("username,expected", [
        ("demo_student", {"dashboard": 403, "users": 403, "audit": 403, "authorities": 403}),
        ("demo_lecturer", {"dashboard": 403, "users": 403, "audit": 403, "authorities": 403}),
        ("demo_authority", {"dashboard": 403, "users": 403, "audit": 403, "authorities": 403}),
        ("demo_management", {"dashboard": 200, "users": 403, "audit": 403, "authorities": 403}),
        ("demo_case_admin", {"dashboard": 200, "users": 403, "audit": 403, "authorities": 200}),
        ("demo_system_admin", {"dashboard": 200, "users": 200, "audit": 200, "authorities": 200}),
    ])
    def test_matrix(self, demo, username, expected):
        client = sign_in(username)
        urls = {"dashboard": "dashboard/summary/", "users": "manage/users/", "audit": "audit-events/",
                "authorities": "manage/authorities/"}
        got = {k: client.get(f"{API}/{u}").status_code for k, u in urls.items()}
        assert got == expected

    def test_dashboard_counts_match(self, demo, events):
        category = Category.objects.get(code="classroom")
        student = sign_in("demo_student")
        for _ in range(3):
            submit(student, category)
        submit(student, category, requested_priority="urgent")
        totals = sign_in("demo_management").get(f"{API}/dashboard/summary/").data["totals"]
        assert (totals["total"], totals["urgent"], totals["not_attempted"]) == (4, 1, 4)

    def test_notifications_are_private(self, demo, events):
        with events():
            submit(sign_in("demo_student"), Category.objects.get(code="classroom"))
        mine = sign_in("demo_student").get(f"{API}/notifications/").data["results"]
        assert mine
        other = sign_in("demo_lecturer")
        assert other.get(f"{API}/notifications/{mine[0]['id']}/").status_code == 404
        assert other.post(f"{API}/notifications/{mine[0]['id']}/read/").status_code == 404


# --- Query-count regression guards (performance) -------------------------------------------------


@pytest.mark.django_db
class TestQueryBudgets:
    def test_login_uses_at_most_four_queries(self, demo):
        APIClient().post(f"{API}/auth/token/", {"username": "demo_student", "password": DEMO_PASSWORD})  # token exists
        with CaptureQueriesContext(connection) as queries:
            res = APIClient().post(f"{API}/auth/token/", {"username": "demo_student", "password": DEMO_PASSWORD})
        assert res.status_code == 200 and len(queries) <= 4, [q["sql"][:80] for q in queries]

    @pytest.mark.parametrize("path", ["cases/?mine=true", "suggestions/", "notifications/"])
    def test_list_query_count_does_not_grow_with_rows(self, demo, path, events):
        """Guards against N+1 queries: 2 rows and 8 rows must cost the same."""
        category = Category.objects.get(code="other")
        student = sign_in("demo_student")

        def count():
            with CaptureQueriesContext(connection) as q:
                assert student.get(f"{API}/{path}").status_code == 200
            return len(q)

        for _ in range(2):
            with events():
                submit(student, category, case_type="suggestion")
        few = count()
        for _ in range(6):
            with events():
                submit(student, category, case_type="suggestion")
        assert count() == few
