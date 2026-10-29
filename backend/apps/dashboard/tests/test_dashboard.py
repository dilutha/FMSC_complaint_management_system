"""Dashboard calculations against a hand-checked synthetic dataset.

    case  type        category     priority  status        created   1st response  solved after  notes
    c1    complaint   Maintenance  normal    submitted     10 d ago  –             –
    c2    complaint   Maintenance  urgent    under_review   9 d ago  2 h           –             location "Hall A"
    c3    complaint   Maintenance  normal    assigned      20 d ago  4 h           –             overdue (Maintenance)
    c4    suggestion  IT           normal    solved         6 d ago  6 h           4 d           IT Unit
    c5    complaint   Maintenance  normal    closed         8 d ago  8 h           2 d           reopened once
    c6    complaint   Maintenance  normal    rejected       3 d ago  10 h          –             duplicate of c1
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.cases.models import Authority, Case, CaseLink, CaseStatusHistory
from apps.cases.services import assignment, updates, workflow

SUMMARY = "/api/v1/dashboard/summary/"


@pytest.fixture
def dataset(student, admin_user, officer, it_officer, maintenance, it_unit, category, it_category, make_case,
            run_events):
    now = timezone.now()
    with run_events():
        c1 = make_case(student, title="Broken chair")
        c2 = make_case(student, title="Projector flickers", requested_priority="urgent", location="Hall A")
        c3 = make_case(student, title="Leaking tap")
        c4 = make_case(student, title="More charging points", case_type="suggestion", category=it_category)
        c5 = make_case(student, title="Door lock jammed")
        c6 = make_case(student, title="Broken chair again")
    with run_events():
        workflow.transition(c2, "under_review", actor=admin_user)
        assignment.assign_case(c3, actor=admin_user, authority=maintenance)
        assignment.assign_case(c4, actor=admin_user, authority=it_unit)
    with run_events():
        workflow.transition(c4, "solved", actor=it_officer, resolution_note="Twelve sockets installed.")
    with run_events():
        assignment.assign_case(c5, actor=admin_user, authority=maintenance)
    with run_events():
        workflow.transition(c5, "solved", actor=officer, resolution_note="Lock replaced by locksmith.")
    with run_events():
        updates.verify_resolution(c5, actor=student, confirmed=True)
    with run_events():
        workflow.transition(c5, "reopened", actor=admin_user, reason="Lock jammed again.")
    with run_events():
        workflow.transition(c5, "solved", actor=officer, resolution_note="Lock mechanism replaced.")
    with run_events():
        workflow.transition(c5, "closed", actor=admin_user)
    with run_events():
        workflow.transition(c6, "rejected", actor=admin_user, reason="Duplicate of an earlier case.")
    CaseLink.objects.create(from_case=c1, to_case=c6, link_type="duplicate", created_by=admin_user)

    def stamp(case, days_ago, response_hours=None, solved_after_days=None, **extra):
        created = now - timedelta(days=days_ago)
        fields = {"created_at": created, **extra}
        if solved_after_days is not None:
            fields["solved_at"] = created + timedelta(days=solved_after_days)
        Case.objects.filter(pk=case.pk).update(**fields)
        if response_hours is not None:
            CaseStatusHistory.objects.filter(case=case, from_status="submitted").update(
                created_at=created + timedelta(hours=response_hours))

    stamp(c1, 10)
    stamp(c2, 9, 2)
    stamp(c3, 20, 4, deadline_at=now - timedelta(hours=1))
    stamp(c4, 6, 6, 4)
    stamp(c5, 8, 8, 2)
    stamp(c6, 3, 10)
    return {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5, "c6": c6}


@pytest.mark.django_db
class TestSummary:
    def test_totals_and_rates(self, api, management, dataset):
        data = api(management).get(SUMMARY).data
        assert data["totals"] == {
            "total": 6, "complaints": 5, "suggestions": 1, "open": 4, "attempted": 5, "not_attempted": 1,
            "not_started": 1, "awaiting_verification": 1, "closed": 1, "rejected": 1, "urgent": 1, "normal": 5,
            "overdue": 1,
        }
        assert data["rates"]["overdue"] == {"value": 33.3, "numerator": 1, "denominator": 3}
        assert data["rates"]["resolution"] == {"value": 40.0, "numerator": 2, "denominator": 5}
        assert data["rates"]["reopening"] == {"value": 50.0, "numerator": 1, "denominator": 2}
        assert data["rates"]["repeat_issue"] == {"value": 16.7, "numerator": 1, "denominator": 6}

    def test_timings(self, api, management, dataset):
        timings = api(management).get(SUMMARY).data["timings"]
        assert timings["first_response_hours"] == {"median": 6.0, "average": 6.0, "sample_size": 5}
        assert timings["resolution_days"] == {"median": 3.0, "average": 3.0, "sample_size": 2}

    def test_breakdowns(self, api, management, dataset):
        data = api(management).get(SUMMARY).data
        by_status = {row["value"]: row["count"] for row in data["by_status"]}
        assert by_status == {"submitted": 1, "under_review": 1, "waiting_for_information": 0, "assigned": 1,
                             "in_progress": 0, "solved": 1, "closed": 1, "rejected": 1, "reopened": 0}
        assert [(r["label"], r["count"]) for r in data["by_category"]] == [("Maintenance", 5), ("IT", 1)]
        assert {r["value"]: r["count"] for r in data["by_priority"]} == {"urgent": 1, "normal": 5}
        assert data["by_location"][0]["count"] == 5

    def test_suggestion_metrics(self, api, management, dataset):
        suggestions = api(management).get(SUMMARY).data["suggestions"]
        counts = {r["value"]: r["count"] for r in suggestions["by_status"]}
        assert counts["implemented"] == 1 and sum(counts.values()) == 1
        assert suggestions["implementation_rate"] == {"value": 100.0, "numerator": 1, "denominator": 1}

    @pytest.mark.parametrize("params,total", [
        ({"priority": "urgent"}, 1),
        ({"case_type": "suggestion"}, 1),
        ({"status": "submitted,closed"}, 2),
        ({"location": "hall a"}, 1),
    ])
    def test_filters(self, api, management, dataset, params, total):
        assert api(management).get(SUMMARY, params).data["totals"]["total"] == total

    def test_category_and_authority_filters(self, api, management, dataset, it_category, maintenance):
        client = api(management)
        assert client.get(SUMMARY, {"category": it_category.pk}).data["totals"]["total"] == 1
        assert client.get(SUMMARY, {"authority": maintenance.pk}).data["totals"]["total"] == 2  # c3, c5

    def test_date_range_selects_by_submission_date(self, api, management, dataset):
        today = timezone.localdate()
        res = api(management).get(SUMMARY, {"date_from": (today - timedelta(days=9)).isoformat(),
                                            "date_to": today.isoformat()})
        assert res.data["totals"]["total"] == 4  # c2, c4, c5, c6

    @pytest.mark.parametrize("params", [
        {"date_from": "2026-10-10", "date_to": "2026-10-01"},
        {"date_from": "not-a-date"},
        {"status": "bogus"},
        {"priority": "extreme"},
    ])
    def test_invalid_filters_are_rejected(self, api, management, params):
        res = api(management).get(SUMMARY, params)
        assert res.status_code == 400 and res.data["error"]["code"] == "validation_error"

    def test_empty_data(self, api, management):
        data = api(management).get(SUMMARY).data
        assert data["totals"]["total"] == 0
        assert data["rates"]["overdue"] == {"value": None, "numerator": 0, "denominator": 0}
        assert data["timings"]["resolution_days"] == {"median": None, "average": None, "sample_size": 0}
        assert all(row["count"] == 0 for row in data["by_status"])


@pytest.mark.django_db
class TestWorkloadAgeingTrends:
    def test_workload_per_unit(self, api, admin_user, dataset, maintenance, it_unit):
        Authority.objects.create(name="Dean's Office", code="deans-office")
        data = api(admin_user).get("/api/v1/dashboard/workload/").data
        rows = {r["authority"]["name"]: r for r in data["results"]}
        assert rows["Maintenance Division"]["active"] == 1
        assert rows["Maintenance Division"]["not_started"] == 1
        assert rows["Maintenance Division"]["overdue"] == 1
        assert rows["Maintenance Division"]["resolved"] == 1
        assert rows["Maintenance Division"]["average_open_age_days"] == 20.0
        assert rows["IT Unit"]["awaiting_verification"] == 1 and rows["IT Unit"]["active"] == 0
        assert rows["Dean's Office"]["active"] == 0  # units with no cases still appear
        assert "not, on its own, a measure" in data["note"]

    def test_ageing_of_not_started_cases(self, api, management, dataset):
        data = api(management).get("/api/v1/dashboard/ageing/").data
        assert data["count"] == 1 and data["oldest"][0]["case_number"] == dataset["c3"].case_number
        assert data["oldest"][0]["age_days"] == 20 and data["oldest"][0]["is_overdue"] is True
        assert {b["label"]: b["count"] for b in data["buckets"]}["15–30 days"] == 1
        assert api(management).get("/api/v1/dashboard/ageing/", {"scope": "open"}).data["count"] == 4

    def test_trends_by_day(self, api, management, dataset):
        today = timezone.localdate()
        data = api(management).get("/api/v1/dashboard/trends/", {
            "date_from": (today - timedelta(days=30)).isoformat(), "date_to": today.isoformat(),
            "interval": "day"}).data
        assert data["interval"] == "day"
        assert sum(p["submitted"] for p in data["series"]) == 6
        assert sum(p["closed"] for p in data["series"]) == 1
        days = [p["period"] for p in data["series"]]
        assert days == sorted(days) and len(days) == len(set(days))


@pytest.mark.django_db
class TestReports:
    def test_paginated_report(self, api, management, dataset):
        res = api(management).get("/api/v1/reports/cases/", {"page_size": 2})
        assert res.data["count"] == 6 and len(res.data["results"]) == 2
        row = res.data["results"][0]
        assert {"case_number", "status", "authority", "age_days", "is_overdue", "first_response_at"} <= set(row)
        assert "description" not in row

    def test_csv_export_is_audited_and_safe(self, api, management, student, make_case):
        make_case(student, title="=HYPERLINK(\"http://evil.test\")")
        res = api(management).get("/api/v1/reports/cases/", {"export": "csv"})
        assert res.status_code == 200 and res["Content-Type"].startswith("text/csv")
        body = res.content.decode()
        assert body.splitlines()[0].startswith("Case number,Title")
        assert "'=HYPERLINK" in body
        assert AuditEvent.objects.filter(action="report.exported", actor=management).exists()


@pytest.mark.django_db
class TestServerRenderedReport:
    def test_management_sees_the_report(self, client, management, dataset):
        client.force_login(management)
        res = client.get("/manage/report/")
        assert res.status_code == 200
        assert "Total cases" in res.content.decode() and "not, on its own, a measure" in res.content.decode()

    def test_students_are_refused_and_anonymous_redirected(self, client, student):
        assert client.get("/manage/report/").status_code == 302
        client.force_login(student)
        assert client.get("/manage/report/").status_code == 403
