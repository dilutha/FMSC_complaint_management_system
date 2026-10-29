"""End-to-end API workflows for the four user groups, using the seeded demo
accounts and real token sign-in (no force_authenticate). Isolated test
database only; never Supabase.

Groups: complainers (student, lecturer, non-academic staff), admin (monitor and
message), case administrator (review, assign, status), resolving departments
(IT, Maintenance, Examination Unit, Dean's Office; own cases only).
"""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.management.commands.seed_demo_users import DEMO_PASSWORD, DEMO_USERS
from apps.accounts.models import Role, User
from apps.cases.models import Authority, Case, CaseStatusHistory, Category

API = "/api/v1"
COMPLAINERS = ["demo_student", "demo_lecturer", "demo_non_academic"]
DEPARTMENTS = {"demo_it": "it-unit", "demo_maintenance": "maintenance", "demo_exams": "examination-unit",
               "demo_deans_office": "deans-office"}
QUIET = open("/dev/null", "w")


@pytest.fixture
def demo(db, settings):
    settings.DEBUG = True
    call_command("seed_demo_users", quiet_table=True, stdout=QUIET)
    return {username: User.objects.get(username=username) for username, *_ in DEMO_USERS}


@pytest.fixture
def events(django_capture_on_commit_callbacks):
    """Run after-commit integration events (notifications, audit, suggestion sync) as in production."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


def sign_in(username, password=DEMO_PASSWORD):
    client = APIClient()
    res = client.post(f"{API}/auth/token/", {"username": username, "password": password}, format="json")
    assert res.status_code == 200, (username, res.status_code, res.data)
    client.credentials(HTTP_AUTHORIZATION=f"Token {res.data['token']}")
    client.me = res.data["user"]
    return client


def submit(client, category_code="classroom", **overrides):
    data = {
        "title": "Projector not working in Hall A",
        "description": "The projector in Hall A does not turn on during lectures.",
        "case_type": "complaint",
        "category_id": Category.objects.get(code=category_code).pk,
        "location": "Hall A",
        "requested_priority": "normal",
        "declaration_accepted": True,
        **overrides,
    }
    return client.post(f"{API}/cases/", data, format="json")


def dept(code):
    return Authority.objects.get(code=code)


def assign(admin, case_id, code, message="This department handles this kind of issue."):
    return admin.post(f"{API}/cases/{case_id}/assign/", {"authority_id": dept(code).pk, "message": message},
                      format="json")


# --- Demo users and landing -------------------------------------------------------------------


@pytest.mark.django_db
class TestDemoUsers:
    @pytest.mark.parametrize("username,role,workspace", [
        ("demo_student", Role.STUDENT, "complainer"),
        ("demo_lecturer", Role.LECTURER, "complainer"),
        ("demo_non_academic", Role.NON_ACADEMIC_STAFF, "complainer"),
        ("demo_system_admin", Role.SYSTEM_ADMIN, "admin"),
        ("demo_case_admin", Role.CASE_ADMIN, "case_admin"),
        ("demo_it", Role.AUTHORITY, "department"),
        ("demo_maintenance", Role.AUTHORITY, "department"),
        ("demo_exams", Role.AUTHORITY, "department"),
        ("demo_deans_office", Role.AUTHORITY, "department"),
        ("demo_management", Role.MANAGEMENT, "management"),
    ])
    def test_every_role_signs_in_and_lands_on_its_workspace(self, demo, username, role, workspace):
        me = sign_in(username).me
        assert (me["role"], me["workspace"]) == (role, workspace)

    def test_accounts_are_safe(self, demo):
        for user in demo.values():
            assert user.password.startswith("pbkdf2_sha256$") and DEMO_PASSWORD not in user.password
            assert user.email.endswith("@example.com") and user.is_active
            assert not user.is_superuser and not user.is_staff
        for username, code in DEPARTMENTS.items():
            assert list(demo[username].authorities.values_list("code", flat=True)) == [code]
        assert {a.name for a in Authority.objects.filter(code__in=DEPARTMENTS.values())} == {
            "IT Department", "Maintenance Department", "Examination Unit", "Dean's Office"}

    def test_seeding_is_idempotent_and_renames_legacy_accounts(self, db, settings):
        settings.DEBUG = True
        User.objects.create_user("demo_it_officer", password="x", role=Role.AUTHORITY)
        for _ in range(2):
            call_command("seed_demo_users", quiet_table=True, stdout=QUIET)
        assert User.objects.filter(username__startswith="demo_").count() == len(DEMO_USERS)
        assert not User.objects.filter(username="demo_it_officer").exists()

    def test_refuses_outside_development(self, db, settings, monkeypatch):
        settings.DEBUG = False
        monkeypatch.delenv("FMSC_ALLOW_DEMO_USERS", raising=False)
        with pytest.raises(CommandError, match="local development only"):
            call_command("seed_demo_users", stdout=QUIET)

    def test_demo_data_covers_every_state_and_is_idempotent(self, db, settings, events):
        settings.DEBUG = True
        with events():
            call_command("seed_demo_data", stdout=QUIET)
        first = Case.objects.count()
        with events():
            call_command("seed_demo_data", stdout=QUIET)
        assert Case.objects.count() == first == 9
        statuses = set(Case.objects.values_list("status", flat=True))
        assert {"submitted", "under_review", "assigned", "in_progress", "solved", "closed"} <= statuses
        assert set(Case.objects.exclude(assigned_authority=None).values_list("assigned_authority__code", flat=True)) \
            == set(DEPARTMENTS.values())


# --- Authentication ----------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuthentication:
    def test_wrong_password_and_unknown_user_get_the_same_answer(self, demo):
        wrong = APIClient().post(f"{API}/auth/token/", {"username": "demo_student", "password": "nope"})
        unknown = APIClient().post(f"{API}/auth/token/", {"username": "nobody", "password": "nope"})
        assert wrong.status_code == unknown.status_code == 400 and wrong.data == unknown.data

    def test_empty_and_malformed_requests(self, demo):
        empty = APIClient().post(f"{API}/auth/token/", {"username": "", "password": ""}, format="json")
        assert empty.status_code == 400 and set(empty.data["error"]["details"]) == {"username", "password"}
        malformed = APIClient().post(f"{API}/auth/token/", "{not json", content_type="application/json")
        assert malformed.status_code == 400 and malformed.data["error"]["code"] == "parse_error"

    def test_inactive_account_cannot_sign_in(self, demo):
        User.objects.filter(username="demo_lecturer").update(is_active=False)
        assert APIClient().post(f"{API}/auth/token/", {"username": "demo_lecturer",
                                                       "password": DEMO_PASSWORD}).status_code == 400

    def test_protected_endpoints_need_a_valid_token(self, demo):
        assert APIClient().get(f"{API}/cases/").status_code == 401
        assert APIClient().get(f"{API}/dashboard/overview/").status_code == 401
        bad = APIClient()
        bad.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
        assert bad.get(f"{API}/cases/").data["error"]["code"] == "authentication_failed"

    def test_logout_invalidates_the_token(self, demo):
        client = sign_in("demo_student")
        assert client.post(f"{API}/auth/logout/").status_code == 204
        assert client.get(f"{API}/auth/me/").status_code == 401

    def test_the_client_cannot_choose_its_role(self, demo):
        res = APIClient().post(f"{API}/auth/token/", {"username": "demo_student", "password": DEMO_PASSWORD,
                                                      "role": "case_admin"})
        assert res.data["user"]["role"] == "student"
        client = sign_in("demo_student")
        client.patch(f"{API}/auth/me/", {"role": "case_admin"}, format="json")
        assert User.objects.get(username="demo_student").role == "student"


# --- Group 1: complainers -----------------------------------------------------------------------


@pytest.mark.django_db
class TestComplainers:
    @pytest.mark.parametrize("username", COMPLAINERS)
    def test_submit_complaint_and_suggestion(self, demo, username, events):
        client = sign_in(username)
        with events():
            complaint = submit(client)
            suggestion = submit(client, "other", case_type="suggestion", title="Extend library hours",
                                description="Keep the library open later in exam weeks.")
        assert complaint.status_code == suggestion.status_code == 201
        assert complaint.data["status"] == "submitted" and complaint.data["case_number"].startswith("FMSC-")
        owner = Case.objects.get(pk=complaint.data["id"]).submitted_by
        assert owner.username == username
        notes = client.get(f"{API}/notifications/").data["results"]
        assert any(complaint.data["case_number"] in n["title"] for n in notes)  # confirmation

    def test_validation_errors_and_ownership_cannot_be_spoofed(self, demo):
        client = sign_in("demo_student")
        bad = submit(client, title="")
        assert bad.status_code == 400 and "title" in bad.data["error"]["details"]
        undeclared = submit(client, declaration_accepted=False)
        assert undeclared.status_code == 400 and "declaration_accepted" in undeclared.data["error"]["details"]
        spoof = submit(client, submitted_by=demo["demo_lecturer"].pk)
        assert spoof.status_code == 400 and "submitted_by" in spoof.data["error"]["details"]
        assert not Case.objects.exists()

    def test_complainers_see_only_their_own_cases(self, demo):
        mine = submit(sign_in("demo_student")).data["id"]
        theirs = submit(sign_in("demo_lecturer"), title="Lecturer's own complaint").data["id"]
        student = sign_in("demo_student")
        assert [c["id"] for c in student.get(f"{API}/cases/").data["results"]] == [mine]
        for path in (f"cases/{theirs}/", f"cases/{theirs}/timeline/", f"cases/{theirs}/updates/"):
            assert student.get(f"{API}/{path}").status_code == 404
        assert student.get(f"{API}/suggestions/").data["count"] == 0

    def test_complainers_cannot_manage_cases(self, demo):
        student = sign_in("demo_student")
        case_id = submit(student).data["id"]
        assert student.post(f"{API}/cases/{case_id}/transition/",
                            {"to_status": "under_review", "reason": "Trying to review"}).status_code == 403
        assert assign(student, case_id, "it-unit").status_code == 403
        for path in ("dashboard/summary/", "reports/cases/", "audit-events/", "manage/users/"):
            assert student.get(f"{API}/{path}").status_code == 403, path

    def test_complainer_dashboard_counts_only_own_records(self, demo, events):
        student = sign_in("demo_student")
        for _ in range(2):
            submit(student)
        submit(student, "other", case_type="suggestion", title="Library hours suggestion")
        submit(sign_in("demo_lecturer"), title="Someone else's case")
        data = student.get(f"{API}/dashboard/overview/").data
        assert data["workspace"] == "complainer"
        assert (data["counts"]["total"], data["counts"]["open"], data["counts"]["pending_suggestions"]) == (3, 3, 1)
        assert all(r["title"] != "Someone else's case" for r in data["recent"])
        assert "by_department" not in data and "recent_activity" not in data


# --- Group 2: admin --------------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdmin:
    def test_sees_every_case_and_can_post_messages(self, demo, events):
        submit(sign_in("demo_student"))
        case_id = submit(sign_in("demo_non_academic"), title="Second complaint").data["id"]
        admin = sign_in("demo_system_admin")
        assert admin.get(f"{API}/cases/").data["count"] == 2
        detail = admin.get(f"{API}/cases/{case_id}/").data
        assert detail["allowed_actions"]["can_post_admin_message"] is True
        assert detail["allowed_actions"]["transitions"] == [] and detail["allowed_actions"]["can_assign"] is False
        with events():
            res = admin.post(f"{API}/cases/{case_id}/updates/", {"body": "The faculty is monitoring this case."})
        assert res.status_code == 201 and res.data["update"]["kind"] == "admin_message"
        timeline = sign_in("demo_non_academic").get(f"{API}/cases/{case_id}/timeline/").data
        entry = next(e for e in timeline if e.get("kind") == "admin_message")
        assert entry["body"] == "The faculty is monitoring this case." and entry["actor"]["name"] == "Admin"

    def test_cannot_change_status_assign_or_decide(self, demo):
        case_id = submit(sign_in("demo_student")).data["id"]
        admin = sign_in("demo_system_admin")
        assert admin.post(f"{API}/cases/{case_id}/transition/",
                          {"to_status": "under_review", "reason": "Admin trying"}).status_code == 403
        assert assign(admin, case_id, "it-unit").status_code == 403
        assert admin.post(f"{API}/cases/{case_id}/updates/",
                          {"body": "Changing status", "new_status": "under_review"}).status_code == 403
        sid = submit(sign_in("demo_student"), "other", case_type="suggestion").data["id"]
        assert admin.post(f"{API}/suggestions/{sid}/decision/", {"decision": "start_evaluation"}).status_code == 403
        assert Case.objects.get(pk=case_id).status == "submitted"

    def test_admin_dashboard_is_faculty_wide(self, demo):
        for name in COMPLAINERS:
            submit(sign_in(name))
        data = sign_in("demo_system_admin").get(f"{API}/dashboard/overview/").data
        assert data["workspace"] == "admin" and data["counts"]["total"] == 3 and data["counts"]["new"] == 3
        assert {d["name"] for d in data["by_department"]} >= {"IT Department", "Examination Unit"}
        assert sum(s["count"] for s in data["by_status"]) == 3


# --- Group 3: case administrator ---------------------------------------------------------------------


@pytest.mark.django_db
class TestCaseAdministrator:
    def test_review_assign_and_keep_monitoring(self, demo, events):
        case_id = submit(sign_in("demo_student")).data["id"]
        ca = sign_in("demo_case_admin")
        queue = ca.get(f"{API}/dashboard/overview/").data
        assert queue["workspace"] == "case_admin" and [r["id"] for r in queue["recent"]] == [case_id]

        no_msg = ca.post(f"{API}/cases/{case_id}/transition/", {"to_status": "under_review"})
        assert no_msg.status_code == 400 and "reason" in no_msg.data["error"]["details"]
        assert ca.post(f"{API}/cases/{case_id}/transition/",
                       {"to_status": "under_review", "reason": "Reviewing the evidence."}).status_code == 200

        missing = ca.post(f"{API}/cases/{case_id}/assign/", {"authority_id": dept("it-unit").pk})
        assert missing.status_code == 400 and "message" in missing.data["error"]["details"]
        Authority.objects.create(name="Closed Unit", code="closed-unit", is_active=False)
        assert assign(ca, case_id, "closed-unit").status_code == 400
        with events():
            res = assign(ca, case_id, "it-unit", "Network faults are handled by the IT Department.")
        assert res.status_code == 200 and res.data["status"] == "assigned"
        assert res.data["assigned_authority"]["name"] == "IT Department"

        # Still visible to the case administrator after assignment (status filter and history).
        assert case_id in [c["id"] for c in ca.get(f"{API}/cases/?status=assigned").data["results"]]
        row = CaseStatusHistory.objects.filter(case_id=case_id, to_status="assigned").get()
        assert row.changed_by.username == "demo_case_admin" and row.actor_role == "case_admin"
        assert "Network faults" in row.reason

        with events():
            again = assign(ca, case_id, "maintenance", "Cable damage found; Maintenance handles cabling.")
        assert again.status_code == 200 and again.data["assigned_authority"]["name"] == "Maintenance Department"

    def test_cannot_use_admin_configuration(self, demo):
        ca = sign_in("demo_case_admin")
        for path in ("manage/users/", "audit-events/", "manage/authorities/"):
            assert ca.get(f"{API}/{path}").status_code == 403, path


# --- Group 4: resolving departments -----------------------------------------------------------------


@pytest.mark.django_db
class TestDepartments:
    @pytest.mark.parametrize("owner,code", list(DEPARTMENTS.items()))
    def test_department_sees_and_handles_only_its_own_cases(self, demo, owner, code, events):
        case_id = submit(sign_in("demo_student")).data["id"]
        unassigned_id = submit(sign_in("demo_lecturer"), title="Not assigned yet").data["id"]
        ca = sign_in("demo_case_admin")
        with events():
            assign(ca, case_id, code)

        mine = sign_in(owner)
        assert [c["id"] for c in mine.get(f"{API}/cases/").data["results"]] == [case_id]
        assert mine.get(f"{API}/cases/{unassigned_id}/").status_code == 404

        # Every other department is locked out, even by direct ID.
        for other in DEPARTMENTS:
            if other == owner:
                continue
            client = sign_in(other)
            assert client.get(f"{API}/cases/").data["count"] == 0
            for path in (f"cases/{case_id}/", f"cases/{case_id}/timeline/", f"cases/{case_id}/updates/"):
                assert client.get(f"{API}/{path}").status_code == 404
            assert client.post(f"{API}/cases/{case_id}/transition/",
                               {"to_status": "in_progress", "reason": "Not mine"}).status_code == 404
            assert client.get(f"{API}/cases/?assigned_authority={dept(code).pk}").data["count"] == 0

        # Status changes need an explanatory message, saved atomically with the change.
        no_msg = mine.post(f"{API}/cases/{case_id}/transition/", {"to_status": "in_progress"})
        assert no_msg.status_code == 400 and Case.objects.get(pk=case_id).status == "assigned"
        with events():
            ok = mine.post(f"{API}/cases/{case_id}/transition/",
                           {"to_status": "in_progress", "reason": "Received and under investigation."})
        assert ok.status_code == 200
        row = CaseStatusHistory.objects.filter(case_id=case_id, to_status="in_progress").get()
        assert (row.actor_role, row.actor_authority.code, row.reason) == (
            "authority", code, "Received and under investigation.")

        # Departments cannot assign or manage.
        assert assign(mine, case_id, "it-unit").status_code == 403
        assert mine.get(f"{API}/dashboard/summary/").status_code == 403
        overview = mine.get(f"{API}/dashboard/overview/").data
        assert overview["workspace"] == "department" and overview["counts"]["total"] == 1
        assert [d["name"] for d in overview["department"]] == [dept(code).name]


@pytest.mark.django_db
def test_department_cannot_see_its_own_legacy_unassigned_submission(demo):
    """Regression (found by the live test on Supabase): a case a department user
    submitted before departments stopped submitting must not appear in their lists."""
    from apps.cases.services import submission

    legacy = submission.submit_case(
        actor=demo["demo_student"], title="Legacy submission", description="Submitted before the role change.",
        case_type="complaint", category=Category.objects.get(code="classroom"), location="Hall A",
        requested_priority="normal", declaration_accepted=True,
    )
    Case.objects.filter(pk=legacy.pk).update(submitted_by=demo["demo_maintenance"])
    client = sign_in("demo_maintenance")
    assert client.get(f"{API}/cases/").data["count"] == 0
    assert client.get(f"{API}/cases/{legacy.pk}/").status_code == 404
    assert client.get(f"{API}/dashboard/overview/").data["counts"]["total"] == 0


# --- Complete workflow --------------------------------------------------------------------------------


@pytest.mark.django_db
class TestCompleteWorkflow:
    def test_submit_review_assign_process_resolve_track(self, demo, events):
        staff = sign_in("demo_non_academic")
        with events():
            case_id = submit(staff, "examination", title="Results missing on the portal",
                             description="My examination results are not visible on the portal.").data["id"]
        ca, exams = sign_in("demo_case_admin"), sign_in("demo_exams")
        assert exams.get(f"{API}/cases/{case_id}/").status_code == 404  # not before assignment
        with events():
            ca.post(f"{API}/cases/{case_id}/transition/", {"to_status": "under_review", "reason": "Checking details."})
            assign(ca, case_id, "examination-unit", "Examination records are kept by the Examination Unit.")
            exams.post(f"{API}/cases/{case_id}/transition/",
                       {"to_status": "in_progress", "reason": "Verifying the examination records."})
            done = exams.post(f"{API}/cases/{case_id}/transition/",
                              {"to_status": "solved", "resolution_note": "The missing results were published."})
        assert done.status_code == 200 and done.data["status"] == "solved"

        detail = staff.get(f"{API}/cases/{case_id}/").data
        assert detail["latest_resolution"]["note"] == "The missing results were published."
        timeline = staff.get(f"{API}/cases/{case_id}/timeline/").data
        changes = [(e["to_status"], e["actor"]["name"], e["body"]) for e in timeline if e["type"] == "status_change"]
        assert ("in_progress", "Examination Unit", "Verifying the examination records.") in changes
        assert any(s == "assigned" and who == "Case Administrator" for s, who, _ in changes)
        assert all(e["actor"]["name"] not in {"Demo Examination Officer", "Demo Case Administrator"} for e in timeline)
        titles = [n["title"] for n in staff.get(f"{API}/notifications/").data["results"]]
        assert any("solved" in t for t in titles)
        with events():
            closed = staff.post(f"{API}/cases/{case_id}/verify-resolution/", {"confirmed": True})
        assert closed.data["status"] == "closed"

    def test_suggestion_workflow(self, demo, events):
        lecturer = sign_in("demo_lecturer")
        with events():
            sid = submit(lecturer, "other", case_type="suggestion", title="More charging points",
                         description="Add power outlets near the study tables.", location="Library").data["id"]
        ca, maint = sign_in("demo_case_admin"), sign_in("demo_maintenance")
        assert lecturer.post(f"{API}/suggestions/{sid}/decision/", {"decision": "decline",
                                                                     "reason": "x" * 20}).status_code == 403
        with events():
            res = ca.post(f"{API}/suggestions/{sid}/decision/",
                          {"decision": "accept", "responsible_unit_id": dept("maintenance").pk, "reason": "Approved."},
                          format="json")
        assert res.status_code == 200 and res.data["status"] == "accepted"
        with events():
            maint.post(f"{API}/suggestions/{sid}/progress/", {"note": "Ordered sockets.", "percent_complete": 50})
            res = maint.post(f"{API}/suggestions/{sid}/implementation/", {"summary": "Twelve sockets installed."})
        assert res.data["status"] == "implemented"
        assert sign_in("demo_it").get(f"{API}/suggestions/{sid}/").status_code == 404


# --- Access matrix and dashboards ----------------------------------------------------------------------


@pytest.mark.django_db
class TestRoleAccess:
    @pytest.mark.parametrize("username,expected", [
        ("demo_student", {"overview": 200, "dashboard": 403, "users": 403, "audit": 403, "authorities": 403}),
        ("demo_non_academic", {"overview": 200, "dashboard": 403, "users": 403, "audit": 403, "authorities": 403}),
        ("demo_it", {"overview": 200, "dashboard": 403, "users": 403, "audit": 403, "authorities": 403}),
        ("demo_case_admin", {"overview": 200, "dashboard": 200, "users": 403, "audit": 403, "authorities": 403}),
        ("demo_system_admin", {"overview": 200, "dashboard": 200, "users": 200, "audit": 200, "authorities": 200}),
        ("demo_management", {"overview": 200, "dashboard": 200, "users": 403, "audit": 403, "authorities": 403}),
    ])
    def test_matrix(self, demo, username, expected):
        client = sign_in(username)
        urls = {"overview": "dashboard/overview/", "dashboard": "dashboard/summary/", "users": "manage/users/",
                "audit": "audit-events/", "authorities": "manage/authorities/"}
        assert {k: client.get(f"{API}/{u}").status_code for k, u in urls.items()} == expected

    def test_overview_counts_match_the_case_lists(self, db, settings, events):
        settings.DEBUG = True
        with events():
            call_command("seed_demo_data", stdout=QUIET)
        for username, _role, *_ in DEMO_USERS:
            client = sign_in(username)
            listed = client.get(f"{API}/cases/?page_size=100").data["count"]
            assert client.get(f"{API}/dashboard/overview/").data["counts"]["total"] == listed, username

    def test_notifications_are_private(self, demo, events):
        with events():
            submit(sign_in("demo_student"))
        mine = sign_in("demo_student").get(f"{API}/notifications/").data["results"]
        other = sign_in("demo_lecturer")
        assert other.get(f"{API}/notifications/{mine[0]['id']}/").status_code == 404


# --- Query-count regression guards ------------------------------------------------------------------


@pytest.mark.django_db
class TestQueryBudgets:
    def test_login_uses_at_most_four_queries(self, demo):
        APIClient().post(f"{API}/auth/token/", {"username": "demo_student", "password": DEMO_PASSWORD})
        with CaptureQueriesContext(connection) as queries:
            res = APIClient().post(f"{API}/auth/token/", {"username": "demo_student", "password": DEMO_PASSWORD})
        assert res.status_code == 200 and len(queries) <= 4, [q["sql"][:80] for q in queries]

    @pytest.mark.parametrize("path", ["cases/?mine=true", "suggestions/", "notifications/", "dashboard/overview/"])
    def test_query_count_does_not_grow_with_rows(self, demo, path, events):
        student = sign_in("demo_student")

        def count():
            with CaptureQueriesContext(connection) as q:
                assert student.get(f"{API}/{path}").status_code == 200
            return len(q)

        for _ in range(2):
            with events():
                submit(student, "other", case_type="suggestion")
        few = count()
        for _ in range(6):
            with events():
                submit(student, "other", case_type="suggestion")
        assert count() == few
