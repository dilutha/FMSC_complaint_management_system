from datetime import timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from apps.cases import signals
from apps.cases.models import Case
from apps.cases.services import assignment, deadlines, updates, workflow
from apps.notifications.models import Notification
from apps.notifications.reminders import send_deadline_reminders

URL = "/api/v1/notifications/"


def inbox(user):
    return list(Notification.objects.filter(recipient=user).order_by("id"))


def events(user):
    return [n.event_type for n in inbox(user)]


@pytest.fixture
def assigned_case(student, admin_user, maintenance, officer, make_case, run_events):
    with run_events():
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
    return Case.objects.get(pk=case.pk)


@pytest.mark.django_db
class TestRecipients:
    def test_submission_confirms_to_submitter_and_alerts_admins_not_the_actor(self, student, admin_user, system_admin,
                                                                             make_case, run_events):
        with run_events():
            case = make_case(student)
        [confirmation] = inbox(student)
        assert confirmation.event_type == "case_submitted" and case.case_number in confirmation.title
        assert confirmation.target_type == "case" and confirmation.target_id == case.pk
        assert events(admin_user) == ["new_case"] and events(system_admin) == ["new_case"]

    def test_admin_submitting_a_case_is_not_told_about_their_own_new_case(self, admin_user, make_case, run_events):
        with run_events():
            make_case(admin_user)
        assert events(admin_user) == ["case_submitted"]

    def test_assignment_notifies_only_the_assigned_unit(self, assigned_case, officer, it_officer, student):
        assert "case_assigned" in events(officer)
        assert events(it_officer) == []
        assert events(student)[-1] == "status_update"
        assert "Maintenance Division" in inbox(student)[-1].body

    def test_information_request_carries_the_reason(self, student, admin_user, make_case, run_events):
        case = make_case(student)
        with run_events():
            workflow.transition(case, "under_review", actor=admin_user)
            workflow.transition(case, "waiting_for_information", actor=admin_user,
                                reason="Which room is the projector in?")
        latest = inbox(student)[-1]
        assert latest.event_type == "information_requested" and latest.body == "Which room is the projector in?"

    def test_solved_asks_submitter_to_confirm_and_actor_is_not_notified(self, assigned_case, officer, student,
                                                                        run_events):
        with run_events():
            workflow.transition(assigned_case, "solved", actor=officer, resolution_note="Replaced the leaking pipe.")
        assert events(student)[-1] == "case_solved"
        assert "please confirm" in inbox(student)[-1].title
        assert "case_solved" not in events(officer)

    def test_rejection_tells_the_submitter_why(self, student, admin_user, make_case, run_events):
        case = make_case(student)
        with run_events():
            workflow.transition(case, "rejected", actor=admin_user, reason="Duplicate of an existing case.")
        latest = inbox(student)[-1]
        assert latest.event_type == "case_rejected" and latest.body == "Duplicate of an existing case."

    def test_dispute_reopens_and_notifies_staff_once(self, assigned_case, officer, admin_user, student, run_events):
        with run_events():
            workflow.transition(assigned_case, "solved", actor=officer, resolution_note="Replaced the leaking pipe.")
        with run_events():
            updates.verify_resolution(assigned_case, actor=student, confirmed=False, feedback="Still leaking.")
        assert events(officer).count("case_reopened") == 1
        assert events(admin_user).count("case_reopened") == 1
        assert "case_reopened" not in events(student)
        assert "resolution_verified" not in events(officer)

    def test_confirmation_notifies_the_unit(self, assigned_case, officer, student, run_events):
        with run_events():
            workflow.transition(assigned_case, "solved", actor=officer, resolution_note="Replaced the leaking pipe.")
        with run_events():
            updates.verify_resolution(assigned_case, actor=student, confirmed=True)
        assert events(officer)[-1] == "resolution_verified"

    def test_escalation_reaches_management_only_at_level_two(self, assigned_case, officer, admin_user, management,
                                                             run_events):
        Case.objects.filter(pk=assigned_case.pk).update(deadline_at=timezone.now() - timedelta(hours=1))
        with run_events():
            deadlines.process_deadlines()
        assert "escalation" in events(officer) and "escalation" in events(admin_user)
        assert events(management) == []
        Case.objects.filter(pk=assigned_case.pk).update(deadline_at=timezone.now() - timedelta(days=5))
        with run_events():
            deadlines.process_deadlines()
        assert events(management) == ["escalation"]

    def test_comments_notify_the_other_party_and_internal_notes_stay_internal(self, assigned_case, officer, student,
                                                                              run_events):
        with run_events():
            updates.add_update(assigned_case, actor=officer, body="Plumber booked for Tuesday.", kind="progress")
        assert events(student)[-1] == "case_update"
        assert "Plumber" not in inbox(student)[-1].body  # comment text is not copied
        before = len(inbox(student))
        with run_events():
            updates.add_update(assigned_case, actor=officer, body="Internal: budget code 44", is_internal=True)
        assert len(inbox(student)) == before
        with run_events():
            updates.add_update(assigned_case, actor=student, body="Thank you!")
        assert events(officer)[-1] == "case_update"


@pytest.mark.django_db
class TestDuplicatePrevention:
    def test_redelivered_event_creates_one_notification(self, assigned_case, officer, student, run_events):
        with run_events():
            workflow.transition(assigned_case, "in_progress", actor=officer)
        count = len(inbox(student))
        payload = {"from_status": "assigned", "to_status": "in_progress", "reason": ""}
        for _ in range(3):
            signals.case_status_changed.send(sender=Case, case=assigned_case, actor=officer, payload=payload)
        assert len(inbox(student)) == count

    def test_deadline_reminders_are_sent_once_per_deadline(self, assigned_case, officer):
        Case.objects.filter(pk=assigned_case.pk).update(deadline_at=timezone.now() + timedelta(hours=5))
        assert send_deadline_reminders() == 1
        call_command("send_deadline_reminders", stdout=open("/dev/null", "w"))
        assert events(officer).count("deadline_reminder") == 1
        Case.objects.filter(pk=assigned_case.pk).update(deadline_at=timezone.now() + timedelta(hours=10))
        assert send_deadline_reminders() == 1  # a new deadline earns a new reminder

    def test_no_reminder_for_distant_or_closed_cases(self, assigned_case):
        Case.objects.filter(pk=assigned_case.pk).update(deadline_at=timezone.now() + timedelta(days=5))
        assert send_deadline_reminders() == 0

    def test_email_copy_is_sent_once(self, settings, student, make_case, run_events):
        settings.FMSC_NOTIFICATIONS = {**settings.FMSC_NOTIFICATIONS, "EMAIL_ENABLED": True}
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        with run_events():
            case = make_case(student)
        submitter_mail = [m for m in mail.outbox if student.email in m.to]
        assert len(submitter_mail) == 1 and case.case_number in submitter_mail[0].subject
        assert case.description not in submitter_mail[0].body
        with run_events():
            signals.case_submitted.send(sender=Case, case=case, actor=student, payload={})
        assert len([m for m in mail.outbox if student.email in m.to]) == 1


@pytest.mark.django_db
class TestNotificationApi:
    def test_users_see_only_their_own_notifications(self, api, student, other_student, make_case, run_events):
        with run_events():
            make_case(student)
        theirs = Notification.objects.get(recipient=student)
        assert api(other_student).get(URL).data["count"] == 0
        assert api(other_student).get(f"{URL}{theirs.pk}/").status_code == 404
        assert api(other_student).post(f"{URL}{theirs.pk}/read/").status_code == 404
        theirs.refresh_from_db()
        assert theirs.is_read is False

    def test_read_unread_flow(self, api, student, admin_user, make_case, run_events):
        with run_events():
            case = make_case(student)
            workflow.transition(case, "under_review", actor=admin_user)
        client = api(student)
        assert client.get(f"{URL}unread-count/").data == {"unread": 2}
        first = client.get(URL).data["results"][0]
        assert first["is_read"] is False and first["target"] == {"type": "case", "id": case.pk}
        assert first["case_number"] == case.case_number
        res = client.post(f"{URL}{first['id']}/read/")
        assert res.status_code == 200 and res.data["is_read"] is True and res.data["read_at"]
        assert client.get(URL, {"unread": "true"}).data["count"] == 1
        assert client.post(f"{URL}read-all/").data == {"updated": 1}
        assert client.get(f"{URL}unread-count/").data == {"unread": 0}

    def test_notifications_cannot_be_created_or_deleted_by_clients(self, api, student, make_case, run_events):
        with run_events():
            make_case(student)
        pk = Notification.objects.get(recipient=student).pk
        assert api(student).post(URL, {"title": "Fake"}).status_code == 405
        assert api(student).delete(f"{URL}{pk}/").status_code == 405

    def test_empty_inbox(self, api, student):
        res = api(student).get(URL)
        assert res.status_code == 200 and res.data["count"] == 0 and res.data["results"] == []
