from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.cases import signals
from apps.cases.models import Case, CaseStatus, DeadlineChange, DeadlinePolicy, EscalationEvent, ResolutionOutcome
from apps.cases.services import assignment, deadlines, workflow
from apps.cases.services.exceptions import NotPermitted, ValidationFailed

BASE = "/api/v1/cases/"


@pytest.fixture
def policies(category):
    return {
        "normal": DeadlinePolicy.objects.create(name="Normal", priority="normal", resolution_hours=120),
        "urgent": DeadlinePolicy.objects.create(name="Urgent", priority="urgent", resolution_hours=48),
        "urgent_complaint_maint": DeadlinePolicy.objects.create(
            name="Urgent maintenance complaint", priority="urgent", case_type="complaint", category=category,
            resolution_hours=24,
        ),
    }


@pytest.mark.django_db
class TestDeadlineCalculation:
    def test_no_policy_means_no_deadline(self, student, make_case):
        case = make_case(student)
        assert case.deadline_at is None and not case.is_overdue

    def test_priority_policy(self, student, make_case, policies):
        case = make_case(student)
        assert abs((case.deadline_at - case.created_at) - timedelta(hours=120)) < timedelta(seconds=5)

    def test_most_specific_policy_wins(self, student, make_case, policies):
        case = make_case(student, requested_priority="urgent")
        assert abs((case.deadline_at - case.created_at) - timedelta(hours=24)) < timedelta(seconds=5)
        sugg = make_case(student, requested_priority="urgent", case_type="suggestion")
        assert abs((sugg.deadline_at - sugg.created_at) - timedelta(hours=48)) < timedelta(seconds=5)

    def test_inactive_policy_ignored(self, student, make_case, policies):
        DeadlinePolicy.objects.update(is_active=False)
        assert make_case(student).deadline_at is None

    def test_reclassification_recalculates_with_history(self, student, admin_user, make_case, policies):
        from apps.cases.services.submission import review_classification

        case = make_case(student)
        case = review_classification(case, actor=admin_user, priority="urgent")
        assert abs((case.deadline_at - case.created_at) - timedelta(hours=24)) < timedelta(seconds=5)
        assert DeadlineChange.objects.filter(case=case).count() == 1


@pytest.mark.django_db
class TestDeadlineChanges:
    def test_admin_changes_deadline_with_reason(self, api, admin_user, student, make_case):
        case = make_case(student)
        new = timezone.now() + timedelta(days=10)
        res = api(admin_user).post(f"{BASE}{case.pk}/deadline/", {"deadline_at": new.isoformat(), "reason": "Parts on order"},
                                   format="json")
        assert res.status_code == 200
        change = DeadlineChange.objects.get(case=case)
        assert change.reason == "Parts on order" and change.old_deadline is None and change.changed_by == admin_user

    def test_non_admin_cannot_change(self, student, officer, make_case):
        case = make_case(student)
        for user in (student, officer):
            with pytest.raises(NotPermitted):
                deadlines.change_deadline(case, actor=user, new_deadline=timezone.now() + timedelta(days=1), reason="x")

    def test_past_deadline_rejected(self, admin_user, student, make_case):
        with pytest.raises(ValidationFailed):
            deadlines.change_deadline(make_case(student), actor=admin_user,
                                      new_deadline=timezone.now() - timedelta(hours=1), reason="oops")


@pytest.mark.django_db
class TestOverdueAndEscalation:
    def _overdue(self, case, hours):
        Case.objects.filter(pk=case.pk).update(deadline_at=timezone.now() - timedelta(hours=hours))
        case.refresh_from_db()
        return case

    def test_overdue_detection(self, api, admin_user, student, make_case):
        late = self._overdue(make_case(student), 1)
        make_case(student, title="Not late case")
        assert late.is_overdue
        assert list(Case.objects.overdue()) == [late]
        res = api(admin_user).get(f"{BASE}?overdue=true")
        assert [c["id"] for c in res.data["results"]] == [late.pk]
        assert res.data["results"][0]["is_overdue"] is True

    def test_closed_cases_are_not_overdue(self, student, admin_user, make_case):
        case = self._overdue(make_case(student), 1)
        workflow.transition(case, CaseStatus.REJECTED, actor=admin_user, reason="Invalid")
        assert not Case.objects.overdue().exists()

    def test_escalation_is_idempotent(self, student, admin_user, maintenance, make_case, django_capture_on_commit_callbacks):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        self._overdue(case, 2)
        seen = []
        handler = lambda sender, case, actor, payload, **kw: seen.append(payload["level"])  # noqa: E731
        signals.case_escalated.connect(handler)
        try:
            with django_capture_on_commit_callbacks(execute=True):
                first = deadlines.process_deadlines()
                second = deadlines.process_deadlines()
        finally:
            signals.case_escalated.disconnect(handler)
        assert first["escalations_created"] == 1 and second["escalations_created"] == 0
        assert seen == [1]
        event = EscalationEvent.objects.get()
        assert event.level == 1 and event.authority == maintenance and event.status_at_escalation == "assigned"

    def test_level_two_after_grace_period(self, student, make_case, settings):
        case = self._overdue(make_case(student), settings.FMSC_CASES["ESCALATION_LEVEL2_AFTER_HOURS"] + 1)
        stats = deadlines.process_deadlines()
        assert stats["escalations_created"] == 2
        assert sorted(EscalationEvent.objects.filter(case=case).values_list("level", flat=True)) == [1, 2]

    def test_new_deadline_allows_new_escalation(self, student, make_case):
        case = self._overdue(make_case(student), 1)
        deadlines.process_deadlines()
        self._overdue(case, 0.5)
        deadlines.process_deadlines()
        assert EscalationEvent.objects.filter(case=case).count() == 2

    def test_management_command(self, student, make_case, capsys):
        self._overdue(make_case(student), 1)
        call_command("process_case_deadlines")
        assert "Escalations created: 1" in capsys.readouterr().out


@pytest.mark.django_db
class TestAutoClose:
    def test_solved_case_auto_closes_after_window(self, student, admin_user, officer, maintenance, make_case):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        workflow.transition(case, CaseStatus.SOLVED, actor=officer, resolution_note="Fixed the leak completely.")
        assert deadlines.process_deadlines()["auto_closed"] == 0
        Case.objects.filter(pk=case.pk).update(verification_due_at=timezone.now() - timedelta(minutes=1))
        assert deadlines.process_deadlines()["auto_closed"] == 1
        case.refresh_from_db()
        assert case.status == "closed"
        assert case.resolutions.get().outcome == ResolutionOutcome.AUTO_CLOSED
        assert case.status_history.last().changed_by is None

    def test_reopen_recalculates_deadline(self, student, admin_user, officer, maintenance, make_case, category):
        DeadlinePolicy.objects.create(name="Normal", priority="normal", resolution_hours=72)
        case = make_case(student)
        original = case.deadline_at
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        workflow.transition(case, CaseStatus.SOLVED, actor=officer, resolution_note="Fixed the leak completely.")
        case = workflow.transition(case, CaseStatus.REOPENED, actor=student, reason="Leak is back")
        assert case.deadline_at >= original
        assert DeadlineChange.objects.filter(case=case, reason__icontains="reopening").exists()
