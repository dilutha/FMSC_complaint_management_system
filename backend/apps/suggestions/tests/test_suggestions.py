from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.cases.models import Case
from apps.cases.services import updates, workflow
from apps.notifications.models import Notification
from apps.suggestions.models import SuggestionEvaluation, SuggestionStatusChange

URL = "/api/v1/suggestions/"


def url(case, action=""):
    return f"{URL}{case.pk}/{action + '/' if action else ''}"


def decide(client, case, decision, **data):
    return client.post(url(case, "decision"), {"decision": decision, **data}, format="json")


def evaluation(case):
    return SuggestionEvaluation.objects.get(case=case)


def case_status(case):
    return Case.objects.get(pk=case.pk).status


@pytest.fixture
def suggestion(student, officer, make_case, run_events):
    with run_events():
        return make_case(student, case_type="suggestion", title="Add more charging points in the library",
                         description="Students need more power outlets near the study tables.", location="Library")


@pytest.fixture
def accepted(api, admin_user, maintenance, suggestion, run_events):
    with run_events():
        res = decide(api(admin_user), suggestion, "accept", responsible_unit_id=maintenance.pk,
                     reason="Supported by the student union.")
    assert res.status_code == 200, res.data
    return suggestion


@pytest.mark.django_db
class TestDecisions:
    def test_submission_creates_an_evaluation(self, suggestion):
        assert evaluation(suggestion).status == "submitted"

    def test_start_evaluation_moves_case_to_review(self, api, admin_user, suggestion, run_events):
        with run_events():
            res = decide(api(admin_user), suggestion, "start_evaluation")
        assert res.status_code == 200 and res.data["status"] == "under_evaluation"
        assert case_status(suggestion) == "under_review"

    def test_accept_requires_a_responsible_unit(self, api, admin_user, suggestion):
        res = decide(api(admin_user), suggestion, "accept")
        assert res.status_code == 400 and "responsible_unit_id" in res.data["error"]["details"]

    def test_accept_assigns_the_case_and_notifies(self, accepted, officer, student, maintenance):
        ev = evaluation(accepted)
        assert ev.status == "accepted" and ev.responsible_unit == maintenance and ev.decided_at
        assert case_status(accepted) == "assigned"
        assert Case.objects.get(pk=accepted.pk).assigned_authority == maintenance
        decision = Notification.objects.get(recipient=student, event_type="suggestion_decision")
        assert "accepted" in decision.title and decision.target_type == "suggestion"
        assert Notification.objects.filter(recipient=officer, event_type="case_assigned").exists()
        assert AuditEvent.objects.filter(action="suggestion.accepted", entity_id=str(accepted.pk)).exists()

    @pytest.mark.parametrize("reason", ["", "   ", "No."])
    def test_decline_requires_a_meaningful_reason(self, api, admin_user, suggestion, reason):
        res = decide(api(admin_user), suggestion, "decline", reason=reason)
        assert res.status_code == 400 and "reason" in res.data["error"]["details"]
        assert evaluation(suggestion).status == "submitted" and case_status(suggestion) == "submitted"

    def test_decline_rejects_the_case_and_tells_the_submitter_why(self, api, admin_user, student, suggestion,
                                                                  run_events):
        reason = "The library is being renovated next year; this will be included in that plan."
        with run_events():
            res = decide(api(admin_user), suggestion, "decline", reason=reason)
        assert res.status_code == 200 and res.data["status"] == "declined" and res.data["decision_reason"] == reason
        assert case_status(suggestion) == "rejected"
        note = Notification.objects.get(recipient=student, event_type="suggestion_decision")
        assert "declined" in note.title and note.body == reason
        assert Notification.objects.filter(recipient=student, event_type="case_rejected").count() == 0

    def test_reconsider_reopens_evaluation(self, api, admin_user, suggestion, run_events):
        client = api(admin_user)
        with run_events():
            decide(client, suggestion, "decline", reason="Out of scope for this academic year.")
            res = decide(client, suggestion, "reconsider", reason="Funding became available this term.")
        assert res.status_code == 200 and res.data["status"] == "under_evaluation"
        assert case_status(suggestion) == "under_review"

    def test_cannot_decline_after_acceptance(self, api, admin_user, accepted):
        res = decide(api(admin_user), accepted, "decline", reason="Changed our minds about this one.")
        assert res.status_code == 409

    def test_decision_history_is_preserved(self, api, admin_user, suggestion, run_events):
        client = api(admin_user)
        with run_events():
            decide(client, suggestion, "start_evaluation")
            decide(client, suggestion, "decline", reason="Out of scope for this academic year.")
            decide(client, suggestion, "reconsider", reason="Funding became available this term.")
        history = client.get(url(suggestion)).data["history"]
        assert [h["to_status"] for h in history] == ["under_evaluation", "declined", "under_evaluation"]
        assert history[1]["reason"] == "Out of scope for this academic year."
        row = SuggestionStatusChange.objects.first()
        with pytest.raises(ValueError):
            row.save()
        with pytest.raises(ValueError):
            row.delete()


@pytest.mark.django_db
class TestImplementation:
    def test_unit_member_plans_and_reports_progress(self, api, officer, student, accepted, run_events):
        client = api(officer)
        target = (timezone.localdate() + timedelta(days=30)).isoformat()
        with run_events():
            res = client.post(url(accepted, "plan"), {"target_date": target, "plan_note": "Order sockets in May."})
        assert res.status_code == 200 and res.data["status"] == "planned" and res.data["target_date"] == target
        with run_events():
            res = client.post(url(accepted, "progress"), {"note": "Sockets ordered.", "percent_complete": 40})
        assert res.status_code == 200 and res.data["progress_percent"] == 40
        assert res.data["progress_updates"][0]["note"] == "Sockets ordered."
        assert case_status(accepted) == "in_progress"
        titles = list(Notification.objects.filter(recipient=student, event_type="suggestion_update")
                      .values_list("title", flat=True))
        assert any("planned" in t for t in titles) and any("Progress" in t for t in titles)

    def test_target_date_cannot_be_in_the_past(self, api, officer, accepted):
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        res = api(officer).post(url(accepted, "plan"), {"target_date": past})
        assert res.status_code == 400 and "target_date" in res.data["error"]["details"]

    def test_progress_of_100_must_use_mark_implemented(self, api, officer, accepted):
        res = api(officer).post(url(accepted, "progress"), {"note": "All done", "percent_complete": 100})
        assert res.status_code == 400

    def test_other_units_cannot_update_implementation(self, api, it_officer, accepted):
        assert api(it_officer).get(url(accepted)).status_code == 404  # not visible at all
        assert api(it_officer).post(url(accepted, "progress"), {"note": "x"}).status_code == 404

    def test_implemented_then_submitter_confirms(self, api, officer, student, accepted, run_events):
        with run_events():
            res = api(officer).post(url(accepted, "implementation"),
                                    {"summary": "Twelve new sockets installed beside the study tables."})
        assert res.status_code == 200 and res.data["status"] == "implemented"
        assert res.data["progress_percent"] == 100 and res.data["implemented_at"]
        assert case_status(accepted) == "solved"
        assert Notification.objects.filter(recipient=student, title__contains="implemented").exists()
        with run_events():
            updates.verify_resolution(Case.objects.get(pk=accepted.pk), actor=student, confirmed=True)
        assert case_status(accepted) == "closed" and evaluation(accepted).status == "implemented"

    def test_disputed_implementation_returns_to_accepted(self, api, officer, student, accepted, run_events):
        with run_events():
            api(officer).post(url(accepted, "implementation"), {"summary": "Twelve new sockets installed."})
        with run_events():
            updates.verify_resolution(Case.objects.get(pk=accepted.pk), actor=student, confirmed=False,
                                      feedback="Only two sockets work.")
        assert case_status(accepted) == "reopened" and evaluation(accepted).status == "accepted"

    def test_implementation_summary_required(self, api, officer, accepted):
        res = api(officer).post(url(accepted, "implementation"), {"summary": "done"})
        assert res.status_code == 400 and "summary" in res.data["error"]["details"]


@pytest.mark.django_db
class TestSyncAndAccess:
    def test_rejection_through_case_api_is_mirrored(self, admin_user, suggestion, run_events):
        with run_events():
            workflow.transition(suggestion, "rejected", actor=admin_user, reason="Already implemented last term.")
        ev = evaluation(suggestion)
        assert ev.status == "declined" and ev.decision_reason == "Already implemented last term."

    def test_students_cannot_decide(self, api, student, suggestion):
        res = decide(api(student), suggestion, "decline", reason="I changed my mind about it.")
        assert res.status_code == 403
        assert evaluation(suggestion).status == "submitted"

    def test_submitter_sees_role_labels_not_staff_names(self, api, student, admin_user, accepted):
        data = api(student).get(url(accepted)).data
        assert data["decided_by"] == "Administrator"
        assert admin_user.display_name not in str(data["history"])
        assert data["allowed_actions"] == []

    def test_other_students_and_complaints_are_404(self, api, other_student, student, suggestion, make_case):
        assert api(other_student).get(url(suggestion)).status_code == 404
        complaint = make_case(student)
        assert api(student).get(f"{URL}{complaint.pk}/").status_code == 404

    def test_list_filters_and_allowed_actions(self, api, admin_user, suggestion, accepted):
        client = api(admin_user)
        assert client.get(URL, {"status": "accepted"}).data["count"] == 1
        assert client.get(URL, {"status": "declined"}).data["count"] == 0
        assert set(client.get(url(accepted)).data["allowed_actions"]) == {"plan", "record_progress", "mark_implemented"}

    def test_management_can_view_but_not_decide(self, api, management, suggestion):
        assert api(management).get(url(suggestion)).status_code == 200
        assert decide(api(management), suggestion, "start_evaluation").status_code == 403

    def test_legacy_suggestion_gets_an_evaluation_lazily(self, api, admin_user, student, make_case):
        case = make_case(student, case_type="suggestion")  # no on-commit receivers ran
        assert not SuggestionEvaluation.objects.filter(case=case).exists()
        assert api(admin_user).get(url(case)).data["status"] == "submitted"
