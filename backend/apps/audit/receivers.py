"""Audit receivers for the case module's integration signals (apps.cases.signals),
plus a model-level hook for priority and category changes, which have no
dedicated signal yet (see docs/SHARED_CONTRACTS.md, "Requests to Member A").

Complaint content (descriptions, comment bodies, resolution notes, submitter
feedback) is deliberately not copied into the audit log.
"""
from django.db.models.signals import post_save, pre_save

from apps.cases import signals
from apps.cases.models import Case

from .context import current_actor
from .event_refs import case_event_ref
from .models import AuditSource
from .services import record


def _record_case_event(event, action, case, actor, payload, *, previous=None, new=None, reason="", metadata=None):
    record(
        action,
        actor=actor,
        entity_type="case",
        entity_id=case.pk,
        entity_label=case.case_number,
        previous=previous,
        new=new,
        reason=reason,
        metadata=metadata,
        source=AuditSource.CASE_EVENT if actor is not None else AuditSource.SYSTEM,
        dedup_key=f"audit:{case_event_ref(event, case, payload)}",
    )


def on_case_submitted(sender, case, actor, payload, **kwargs):
    _record_case_event(
        "case_submitted", "case.submitted", case, actor, payload,
        new={"status": case.status, "case_type": case.case_type, "priority": case.priority,
             "category": payload.get("category")},
    )


def on_case_assigned(sender, case, actor, payload, **kwargs):
    _record_case_event(
        "case_assigned", "case.reassigned" if payload.get("is_reassignment") else "case.assigned", case, actor, payload,
        previous={"authority_id": payload.get("previous_authority_id")},
        new={"authority_id": payload.get("authority_id"), "authority_name": payload.get("authority_name")},
        metadata={"is_override": payload.get("is_override"),
                  "recommended_authority_id": payload.get("recommended_authority_id")},
    )


def on_case_status_changed(sender, case, actor, payload, **kwargs):
    _record_case_event(
        "case_status_changed", "case.status_changed", case, actor, payload,
        previous={"status": payload.get("from_status")},
        new={"status": payload.get("to_status")},
        reason=payload.get("reason") or "",
    )


def on_case_resolution_verified(sender, case, actor, payload, **kwargs):
    _record_case_event(
        "case_resolution_verified", "case.resolution_verified", case, actor, payload,
        new={"confirmed": bool(payload.get("confirmed"))},
        metadata={"resolution_id": payload.get("resolution_id"), "has_feedback": bool(payload.get("feedback"))},
    )


def on_case_escalated(sender, case, actor, payload, **kwargs):
    _record_case_event(
        "case_escalated", "case.escalated", case, actor, payload,
        new={"level": payload.get("level"), "deadline_at": payload.get("deadline_at")},
        metadata={"authority_id": payload.get("authority_id"), "status": payload.get("status")},
    )


def on_case_deadline_changed(sender, case, actor, payload, **kwargs):
    _record_case_event(
        "case_deadline_changed", "case.deadline_changed", case, actor, payload,
        previous={"deadline_at": payload.get("old_deadline")},
        new={"deadline_at": payload.get("new_deadline")},
        reason=payload.get("reason") or "",
    )


def on_case_update_added(sender, case, actor, payload, **kwargs):
    _record_case_event(
        "case_update_added", "case.update_added", case, actor, payload,
        metadata={"update_id": payload.get("update_id"), "kind": payload.get("kind"),
                  "is_internal": bool(payload.get("is_internal"))},
    )


# --- Priority and category changes (model hook) ---------------------------------

_TRACKED_FIELDS = ("priority", "category_id")


def remember_tracked_fields(sender, instance, update_fields=None, **kwargs):
    if instance.pk is None or (update_fields is not None and not {"priority", "category"} & set(update_fields)):
        instance._audit_before = None
        return
    instance._audit_before = Case.objects.filter(pk=instance.pk).values(*_TRACKED_FIELDS).first()


def record_tracked_changes(sender, instance, created, **kwargs):
    before = getattr(instance, "_audit_before", None)
    if created or not before:
        return
    actor = current_actor()
    if before["priority"] != instance.priority:
        record("case.priority_changed", actor=actor, entity_type="case", entity_id=instance.pk,
               entity_label=instance.case_number, previous={"priority": before["priority"]},
               new={"priority": instance.priority})
    if before["category_id"] != instance.category_id:
        record("case.category_changed", actor=actor, entity_type="case", entity_id=instance.pk,
               entity_label=instance.case_number, previous={"category_id": before["category_id"]},
               new={"category_id": instance.category_id})
    instance._audit_before = None


def connect():
    signals.case_submitted.connect(on_case_submitted, dispatch_uid="audit_case_submitted")
    signals.case_assigned.connect(on_case_assigned, dispatch_uid="audit_case_assigned")
    signals.case_status_changed.connect(on_case_status_changed, dispatch_uid="audit_case_status_changed")
    signals.case_resolution_verified.connect(on_case_resolution_verified, dispatch_uid="audit_case_verified")
    signals.case_escalated.connect(on_case_escalated, dispatch_uid="audit_case_escalated")
    signals.case_deadline_changed.connect(on_case_deadline_changed, dispatch_uid="audit_case_deadline")
    signals.case_update_added.connect(on_case_update_added, dispatch_uid="audit_case_update")
    pre_save.connect(remember_tracked_fields, sender=Case, dispatch_uid="audit_case_pre_save")
    post_save.connect(record_tracked_changes, sender=Case, dispatch_uid="audit_case_post_save")
