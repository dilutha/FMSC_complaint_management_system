from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cases import signals
from apps.cases.models import Case, CaseResolution, CaseStatus, ResolutionOutcome
from apps.cases.services import assignment, updates, workflow
from apps.cases.services.exceptions import InvalidTransition, NotPermitted, ValidationFailed

BASE = "/api/v1/cases/"
NOTE = "Replaced the leaking pipe section and dried the ceiling."


@pytest.fixture
def assigned_case(student, admin_user, maintenance, make_case):
    case = make_case(student)
    workflow.transition(case, CaseStatus.UNDER_REVIEW, actor=admin_user, reason="Status update recorded by test.")
    return assignment.assign_case(case, actor=admin_user, authority=maintenance, message="Assigned by test.")


@pytest.fixture
def solved_case(assigned_case, officer):
    workflow.transition(assigned_case, CaseStatus.IN_PROGRESS, actor=officer, reason="Status update recorded by test.")
    return workflow.transition(assigned_case, CaseStatus.SOLVED, actor=officer, resolution_note=NOTE)


@pytest.mark.django_db
class TestLifecycle:
    def test_full_happy_path_via_api(self, api, student, admin_user, officer, maintenance, make_case):
        case = make_case(student)
        admin = api(admin_user)
        assert admin.post(f"{BASE}{case.pk}/transition/", {"to_status": "under_review", "reason": "Status update recorded by test."}).data["status"] == "under_review"
        res = admin.post(f"{BASE}{case.pk}/assign/", {"authority_id": maintenance.pk, "internal_note": "Urgent", "message": "Assigned by test."})
        assert res.status_code == 200 and res.data["status"] == "assigned"
        assert res.data["assigned_authority"]["id"] == maintenance.pk

        auth = api(officer)
        res = auth.post(f"{BASE}{case.pk}/updates/", {"body": "Plumber on site", "kind": "progress", "new_status": "in_progress"})
        assert res.status_code == 201 and res.data["case"]["status"] == "in_progress"
        res = auth.post(f"{BASE}{case.pk}/updates/", {"body": "Work complete", "kind": "progress",
                                                      "new_status": "solved", "resolution_note": NOTE})
        assert res.status_code == 201, res.data
        assert res.data["case"]["status"] == "solved"
        assert res.data["case"]["solved_at"] and res.data["case"]["verification_due_at"]
        assert res.data["case"]["latest_resolution"]["note"] == NOTE

        res = api(student).post(f"{BASE}{case.pk}/verify-resolution/", {"confirmed": True})
        assert res.status_code == 200 and res.data["status"] == "closed"
        assert res.data["closed_at"]

        history = list(Case.objects.get(pk=case.pk).status_history.values_list("to_status", flat=True))
        assert history == ["submitted", "under_review", "assigned", "in_progress", "solved", "closed"]
        timeline = api(student).get(f"{BASE}{case.pk}/timeline/").data
        assert [e["to_status"] for e in timeline if e["type"] == "status_change"] == history

    @pytest.mark.parametrize(
        "start,target",
        [("submitted", "solved"), ("submitted", "closed"), ("submitted", "in_progress"),
         ("under_review", "closed"), ("submitted", "reopened")],
    )
    def test_invalid_transitions_rejected(self, student, admin_user, make_case, start, target):
        case = make_case(student)
        if start == "under_review":
            workflow.transition(case, start, actor=admin_user, reason="Status update recorded by test.")
        with pytest.raises(InvalidTransition):
            workflow.transition(case, target, actor=admin_user, reason="x" * 20, resolution_note="x" * 20)

    def test_invalid_transition_api_returns_409(self, api, student, admin_user, make_case):
        case = make_case(student)
        res = api(admin_user).post(f"{BASE}{case.pk}/transition/", {"to_status": "closed", "reason": "Status update recorded by test."})
        assert res.status_code == 409
        assert res.data["error"]["code"] == "invalid_transition"

    def test_assigned_cannot_be_set_via_transition(self, student, admin_user, make_case):
        case = make_case(student)
        with pytest.raises(InvalidTransition):
            workflow.transition(case, CaseStatus.ASSIGNED, actor=admin_user, reason="Status update recorded by test.")

    def test_rejection_requires_reason(self, api, student, admin_user, make_case):
        case = make_case(student)
        res = api(admin_user).post(f"{BASE}{case.pk}/transition/", {"to_status": "rejected"})
        assert res.status_code == 400 and "reason" in res.data["error"]["details"]
        res = api(admin_user).post(f"{BASE}{case.pk}/transition/", {"to_status": "rejected", "reason": "Duplicate of FMSC-2026-00001"})
        assert res.status_code == 200
        case.refresh_from_db()
        assert case.status == "rejected" and case.closed_at
        assert case.status_history.last().reason == "Duplicate of FMSC-2026-00001"

    def test_rejected_case_can_be_reconsidered_by_admin(self, student, admin_user, make_case):
        case = make_case(student)
        workflow.transition(case, CaseStatus.REJECTED, actor=admin_user, reason="Out of scope")
        case = workflow.transition(case, CaseStatus.UNDER_REVIEW, actor=admin_user, reason="Reconsidered")
        assert case.status == "under_review" and case.closed_at is None

    def test_solved_requires_resolution_note(self, assigned_case, officer):
        with pytest.raises(ValidationFailed) as exc:
            workflow.transition(assigned_case, CaseStatus.SOLVED, actor=officer, resolution_note="done")
        assert "resolution_note" in exc.value.details

    def test_cannot_start_work_without_assignment(self, student, admin_user, make_case):
        case = make_case(student)
        workflow.transition(case, CaseStatus.UNDER_REVIEW, actor=admin_user, reason="Status update recorded by test.")
        workflow.transition(case, CaseStatus.WAITING_FOR_INFORMATION, actor=admin_user, reason="Which room exactly?")
        with pytest.raises(InvalidTransition):
            workflow.transition(case, CaseStatus.IN_PROGRESS, actor=admin_user, reason="Status update recorded by test.")

    def test_waiting_for_information_requires_and_shows_request(self, api, student, admin_user, make_case):
        case = make_case(student)
        workflow.transition(case, CaseStatus.UNDER_REVIEW, actor=admin_user, reason="Status update recorded by test.")
        with pytest.raises(ValidationFailed):
            workflow.transition(case, CaseStatus.WAITING_FOR_INFORMATION, actor=admin_user)
        workflow.transition(case, CaseStatus.WAITING_FOR_INFORMATION, actor=admin_user, reason="Please add a photo.")
        res = api(student).post(f"{BASE}{case.pk}/updates/", {"body": "Photo attached.", "kind": "information_response"})
        assert res.status_code == 201
        timeline = api(student).get(f"{BASE}{case.pk}/timeline/").data
        assert any(e["body"] == "Please add a photo." for e in timeline)

    def test_authority_of_other_unit_cannot_transition(self, assigned_case, it_officer):
        with pytest.raises(NotPermitted):
            workflow.transition(assigned_case, CaseStatus.IN_PROGRESS, actor=it_officer, reason="Status update recorded by test.")

    def test_status_change_signal(self, assigned_case, officer, django_capture_on_commit_callbacks):
        seen = []
        handler = lambda sender, case, actor, payload, **kw: seen.append(payload)  # noqa: E731
        signals.case_status_changed.connect(handler)
        try:
            with django_capture_on_commit_callbacks(execute=True):
                workflow.transition(assigned_case, CaseStatus.IN_PROGRESS, actor=officer, reason="Status update recorded by test.")
        finally:
            signals.case_status_changed.disconnect(handler)
        assert seen == [{"from_status": "assigned", "to_status": "in_progress", "reason": "Status update recorded by test."}]

    def test_failing_receiver_does_not_break_transition(self, assigned_case, officer, django_capture_on_commit_callbacks):
        def broken(**kwargs):
            raise RuntimeError("notification service down")

        signals.case_status_changed.connect(broken)
        try:
            with django_capture_on_commit_callbacks(execute=True):
                case = workflow.transition(assigned_case, CaseStatus.IN_PROGRESS, actor=officer, reason="Status update recorded by test.")
        finally:
            signals.case_status_changed.disconnect(broken)
        assert case.status == "in_progress"


@pytest.mark.django_db
class TestVerificationAndReopen:
    def test_solved_emits_notification_event(self, assigned_case, officer, django_capture_on_commit_callbacks):
        seen = []
        handler = lambda sender, case, actor, payload, **kw: seen.append(case.pk)  # noqa: E731
        signals.case_solved.connect(handler)
        try:
            with django_capture_on_commit_callbacks(execute=True):
                workflow.transition(assigned_case, CaseStatus.SOLVED, actor=officer, resolution_note=NOTE)
        finally:
            signals.case_solved.disconnect(handler)
        assert seen == [assigned_case.pk]

    def test_submitter_confirms(self, solved_case, student):
        case = updates.verify_resolution(solved_case, actor=student, confirmed=True)
        assert case.status == "closed"
        assert case.resolutions.get().outcome == ResolutionOutcome.CONFIRMED

    def test_problem_persists_reopens_and_preserves_resolution(self, api, solved_case, student, officer):
        res = api(student).post(f"{BASE}{solved_case.pk}/verify-resolution/", {"confirmed": False})
        assert res.status_code == 400 and "feedback" in res.data["error"]["details"]
        res = api(student).post(
            f"{BASE}{solved_case.pk}/verify-resolution/", {"confirmed": False, "feedback": "Still leaking after rain."}
        )
        assert res.status_code == 200 and res.data["status"] == "reopened"
        assert res.data["reopen_count"] == 1
        first = CaseResolution.objects.get(case=solved_case)
        assert first.outcome == ResolutionOutcome.DISPUTED and first.note == NOTE
        assert first.submitter_feedback == "Still leaking after rain."

        # The authority resolves again; both resolutions are kept.
        workflow.transition(solved_case, CaseStatus.IN_PROGRESS, actor=officer, reason="Status update recorded by test.")
        workflow.transition(solved_case, CaseStatus.SOLVED, actor=officer, resolution_note="Roof membrane resealed fully.")
        assert solved_case.resolutions.count() == 2
        assert list(solved_case.resolutions.values_list("outcome", flat=True)) == ["disputed", "pending"]

    def test_only_submitter_can_verify(self, solved_case, other_student, officer, admin_user):
        for user in (officer, admin_user, other_student):
            with pytest.raises(NotPermitted):
                updates.verify_resolution(solved_case, actor=user, confirmed=True)

    def test_verify_requires_solved_status(self, assigned_case, student):
        with pytest.raises(InvalidTransition):
            updates.verify_resolution(assigned_case, actor=student, confirmed=True)

    def test_reopen_requires_reason(self, api, solved_case, student):
        res = api(student).post(f"{BASE}{solved_case.pk}/reopen/", {"reason": ""})
        assert res.status_code == 400
        assert "reason" in res.data["error"]["details"]

    def test_reopen_closed_case_within_window(self, api, solved_case, student):
        updates.verify_resolution(solved_case, actor=student, confirmed=True)
        res = api(student).post(f"{BASE}{solved_case.pk}/reopen/", {"reason": "The leak returned this week."})
        assert res.status_code == 200, res.data
        assert res.data["status"] == "reopened" and res.data["closed_at"] is None

    def test_reopen_closed_case_after_window_blocked(self, api, solved_case, student, settings):
        updates.verify_resolution(solved_case, actor=student, confirmed=True)
        Case.objects.filter(pk=solved_case.pk).update(
            closed_at=timezone.now() - timedelta(days=settings.FMSC_CASES["REOPEN_WINDOW_DAYS"] + 1)
        )
        res = api(student).post(f"{BASE}{solved_case.pk}/reopen/", {"reason": "The leak returned this week."})
        assert res.status_code == 409

    def test_admin_can_reopen_after_window(self, solved_case, student, admin_user):
        updates.verify_resolution(solved_case, actor=student, confirmed=True)
        Case.objects.filter(pk=solved_case.pk).update(closed_at=timezone.now() - timedelta(days=365))
        case = updates.reopen_case(solved_case, actor=admin_user, reason="Audit found recurrence")
        assert case.status == "reopened"

    def test_submitter_cannot_reopen_rejected(self, student, admin_user, make_case):
        case = make_case(student)
        workflow.transition(case, CaseStatus.REJECTED, actor=admin_user, reason="Out of scope")
        with pytest.raises(InvalidTransition):
            updates.reopen_case(case, actor=student, reason="Please reconsider")

    def test_history_preserved_across_reopen(self, solved_case, student):
        updates.verify_resolution(solved_case, actor=student, confirmed=False, feedback="Still broken")
        statuses = list(solved_case.status_history.values_list("to_status", flat=True))
        assert statuses[-3:] == ["in_progress", "solved", "reopened"]

    def test_closed_case_blocks_submitter_updates(self, solved_case, student):
        updates.verify_resolution(solved_case, actor=student, confirmed=True)
        with pytest.raises(InvalidTransition):
            updates.add_update(solved_case, actor=student, body="One more thing")

    def test_submitter_cannot_change_status_via_updates(self, api, solved_case, student):
        res = api(student).post(f"{BASE}{solved_case.pk}/updates/", {"body": "done", "new_status": "closed"})
        assert res.status_code == 403
