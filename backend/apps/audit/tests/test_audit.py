from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditEvent, AuditImmutableError
from apps.audit.services import record, sanitise
from apps.cases import signals
from apps.cases.models import Case
from apps.cases.services import assignment, deadlines, submission, workflow
from apps.platform_testing import PASSWORD

AUDIT = "/api/v1/audit-events/"


def actions_for(case):
    return list(AuditEvent.objects.filter(entity_type="case", entity_id=str(case.pk))
                .order_by("id").values_list("action", flat=True))


@pytest.mark.django_db
class TestCaseWorkflowAudit:
    def test_submission_assignment_and_status_changes_are_recorded(self, student, admin_user, maintenance, make_case,
                                                                   run_events):
        with run_events():
            case = make_case(student)
        with run_events():
            workflow.transition(case, "under_review", actor=admin_user)
        with run_events():
            assignment.assign_case(case, actor=admin_user, authority=maintenance, internal_note="Internal routing note")
        assert actions_for(case) == ["case.submitted", "case.status_changed", "case.assigned", "case.status_changed"]

        assigned = AuditEvent.objects.get(action="case.assigned")
        assert assigned.actor == admin_user and assigned.actor_role == "case_admin"
        assert assigned.new_value["authority_id"] == maintenance.pk
        assert "Internal routing note" not in str(assigned.metadata) + str(assigned.new_value)
        change = AuditEvent.objects.filter(action="case.status_changed").order_by("id").first()
        assert change.previous_value == {"status": "submitted"} and change.new_value == {"status": "under_review"}

    def test_rejection_reason_is_kept(self, student, admin_user, make_case, run_events):
        case = make_case(student)
        with run_events():
            workflow.transition(case, "rejected", actor=admin_user, reason="Outside the faculty's remit.")
        event = AuditEvent.objects.get(action="case.status_changed", new_value__status="rejected")
        assert event.reason == "Outside the faculty's remit."

    def test_priority_and_category_changes_are_attributed_to_the_request_user(self, api, student, admin_user,
                                                                             make_case, it_category):
        case = make_case(student)
        res = api(admin_user).patch(f"/api/v1/cases/{case.pk}/", {"priority": "urgent", "category_id": it_category.pk},
                                    format="json")
        assert res.status_code == 200, res.data
        priority = AuditEvent.objects.get(action="case.priority_changed")
        assert priority.actor == admin_user
        assert priority.previous_value == {"priority": "normal"} and priority.new_value == {"priority": "urgent"}
        assert AuditEvent.objects.get(action="case.category_changed").new_value == {"category_id": it_category.pk}

    def test_deadline_change_and_escalation_are_recorded(self, student, admin_user, make_case, run_events):
        case = make_case(student)
        with run_events():
            deadlines.change_deadline(case, actor=admin_user, new_deadline=timezone.now() + timedelta(days=2),
                                      reason="Contractor visit scheduled.")
        Case.objects.filter(pk=case.pk).update(deadline_at=timezone.now() - timedelta(hours=1))
        with run_events():
            deadlines.process_deadlines()
        assert AuditEvent.objects.get(action="case.deadline_changed").reason == "Contractor visit scheduled."
        escalation = AuditEvent.objects.get(action="case.escalated")
        assert escalation.actor is None and escalation.source == "system" and escalation.actor_label == "System"

    def test_comment_text_is_never_copied(self, api, student, make_case, run_events):
        case = make_case(student)
        with run_events():
            api(student).post(f"/api/v1/cases/{case.pk}/updates/", {"body": "My private phone is 0771234567"})
        event = AuditEvent.objects.get(action="case.update_added")
        assert "0771234567" not in str(event.metadata) + str(event.new_value) + event.reason

    def test_redelivered_signal_does_not_duplicate(self, student, admin_user, make_case, run_events):
        case = make_case(student)
        with run_events():
            workflow.transition(case, "under_review", actor=admin_user)
        payload = {"from_status": "submitted", "to_status": "under_review", "reason": ""}
        signals.case_status_changed.send(sender=Case, case=case, actor=admin_user, payload=payload)
        assert AuditEvent.objects.filter(action="case.status_changed").count() == 1

    def test_attachment_download_is_audited(self, api, student, category):
        from apps.platform_testing import png_upload

        case = submission.submit_case(actor=student, title="Broken window", description="Glass cracked in room 4.",
                                      case_type="complaint", category=category, location="Room 4",
                                      requested_priority="normal", declaration_accepted=True,
                                      attachments=[png_upload()])
        attachment = case.attachments.get()
        res = api(student).get(f"/api/v1/cases/{case.pk}/attachments/{attachment.pk}/download/")
        assert res.status_code == 200
        event = AuditEvent.objects.get(action="case.attachment_downloaded")
        assert event.actor == student and event.metadata == {"attachment_id": attachment.pk}


@pytest.mark.django_db
class TestImmutability:
    def test_model_instances_cannot_be_changed_or_deleted(self, admin_user):
        event = record("test.event", actor=admin_user, entity_type="case", entity_id=1)
        event.reason = "tampered"
        with pytest.raises(AuditImmutableError):
            event.save()
        with pytest.raises(AuditImmutableError):
            event.delete()

    def test_bulk_update_and_delete_are_blocked(self, admin_user):
        record("test.event", actor=admin_user, entity_type="case", entity_id=1)
        with pytest.raises(AuditImmutableError):
            AuditEvent.objects.all().update(reason="tampered")
        with pytest.raises(AuditImmutableError):
            AuditEvent.objects.all().delete()

    @pytest.mark.skipif(connection.vendor != "postgresql", reason="database trigger is PostgreSQL-only")
    def test_database_rejects_raw_updates_and_deletes(self, admin_user):
        from django.db import DatabaseError, transaction

        event = record("test.event", actor=admin_user, entity_type="case", entity_id=1)
        for sql in ("UPDATE audit_auditevent SET reason = 'x' WHERE id = %s",
                    "DELETE FROM audit_auditevent WHERE id = %s"):
            with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql, [event.pk])

    @pytest.mark.skipif(connection.vendor != "postgresql", reason="database trigger is PostgreSQL-only")
    def test_deleting_a_user_keeps_the_record(self, system_admin):
        from apps.platform_testing import make_user

        temp = make_user()
        event = record("test.event", actor=temp, entity_type="user", entity_id=temp.pk)
        temp.delete()
        event = AuditEvent.objects.get(pk=event.pk)
        assert event.actor is None and event.actor_label == temp.display_name

    def test_secrets_are_redacted(self, admin_user):
        event = record("test.event", actor=admin_user, entity_type="user", entity_id=1,
                       new={"password": PASSWORD, "nested": {"auth_token": "abc"}, "name": "ok"})
        assert event.new_value == {"password": "[redacted]", "nested": {"auth_token": "[redacted]"}, "name": "ok"}
        assert sanitise("x" * 2000).endswith("…")


@pytest.mark.django_db
class TestAuditApi:
    def test_system_admin_can_list_and_filter(self, api, system_admin, student, admin_user, make_case, run_events):
        with run_events():
            case = make_case(student)
            workflow.transition(case, "under_review", actor=admin_user)
        res = api(system_admin).get(AUDIT, {"entity_type": "case", "entity_id": case.pk, "action": "case.submitted"})
        assert res.status_code == 200 and res.data["count"] == 1
        assert api(system_admin).get(AUDIT, {"actor": admin_user.pk}).data["count"] >= 1

    def test_history_cannot_be_written_through_the_api(self, api, system_admin, admin_user):
        event = record("test.event", actor=admin_user, entity_type="case", entity_id=1)
        client = api(system_admin)
        assert client.post(AUDIT, {"action": "fake"}).status_code == 405
        assert client.put(f"{AUDIT}{event.pk}/", {"reason": "x"}).status_code == 405
        assert client.patch(f"{AUDIT}{event.pk}/", {"reason": "x"}).status_code == 405
        assert client.delete(f"{AUDIT}{event.pk}/").status_code == 405
        assert AuditEvent.objects.get(pk=event.pk).reason == ""

    def test_case_admins_cannot_read_the_audit_log(self, api, admin_user):
        assert api(admin_user).get(AUDIT).status_code == 403
