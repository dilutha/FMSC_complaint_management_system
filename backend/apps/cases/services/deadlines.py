"""Deadline calculation, manual changes, overdue detection and escalation."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.cases import signals
from apps.cases.models import (
    TERMINAL_STATUSES,
    Case,
    CaseStatus,
    DeadlineChange,
    DeadlinePolicy,
    EscalationEvent,
)

from . import access
from .events import emit
from .exceptions import NotPermitted, ValidationFailed

logger = logging.getLogger("apps.cases.deadlines")


def matching_policy(*, priority, case_type, category):
    """Most specific active policy: category+type > category > type > priority only."""
    candidates = DeadlinePolicy.objects.filter(is_active=True, priority=priority).filter(
        Q(case_type="") | Q(case_type=case_type)
    ).filter(Q(category__isnull=True) | Q(category=category))

    def specificity(p):
        return (p.category_id is not None) * 2 + (p.case_type != "")

    ranked = sorted(candidates, key=lambda p: (-specificity(p), p.resolution_hours, p.pk))
    return ranked[0] if ranked else None


def calculate_deadline(*, priority, case_type, category, start):
    """Returns the deadline datetime, or None when no policy is configured.
    No deadline is invented when the faculty has not configured one."""
    policy = matching_policy(priority=priority, case_type=case_type, category=category)
    return start + timedelta(hours=policy.resolution_hours) if policy else None


def record_deadline(case: Case, new_deadline, *, actor, reason):
    """Persist a deadline change with history. Caller holds the case lock."""
    old = case.deadline_at
    if old == new_deadline:
        return
    case.deadline_at = new_deadline
    case.save(update_fields=["deadline_at", "updated_at"])
    DeadlineChange.objects.create(case=case, old_deadline=old, new_deadline=new_deadline, changed_by=actor, reason=reason)
    emit(
        signals.case_deadline_changed,
        case,
        actor,
        old_deadline=old.isoformat() if old else None,
        new_deadline=new_deadline.isoformat() if new_deadline else None,
        reason=reason,
    )


def change_deadline(case: Case, *, actor, new_deadline, reason):
    if not access.is_case_admin(actor):
        raise NotPermitted("Only administrators can change deadlines.")
    if not reason or not reason.strip():
        raise ValidationFailed("A reason is required to change a deadline.", details={"reason": ["This field is required."]})
    if new_deadline is not None and new_deadline <= timezone.now():
        raise ValidationFailed("The new deadline must be in the future.", details={"deadline_at": ["Must be in the future."]})
    with transaction.atomic():
        locked = Case.objects.select_for_update().get(pk=case.pk)
        if locked.status in TERMINAL_STATUSES:
            raise ValidationFailed("Deadlines cannot be changed on closed or rejected cases.")
        record_deadline(locked, new_deadline, actor=actor, reason=reason.strip())
    return locked


def escalation_levels_due(case: Case, now):
    """Levels the case is eligible for at `now`. Level 1 at the deadline,
    level 2 after the configured grace period."""
    if not case.deadline_at or case.deadline_at >= now:
        return []
    levels = [1]
    grace = timedelta(hours=settings.FMSC_CASES["ESCALATION_LEVEL2_AFTER_HOURS"])
    if now >= case.deadline_at + grace:
        levels.append(2)
    return levels


def process_deadlines(now=None):
    """Scheduled job (run via `manage.py process_case_deadlines`).

    * Raises escalation events for overdue active cases (idempotent).
    * Auto-closes solved cases whose verification window has expired.
    """
    from .workflow import transition  # local import: workflow imports this module

    now = now or timezone.now()
    stats = {"escalations_created": 0, "auto_closed": 0}

    for case in Case.objects.overdue(now).select_related("assigned_authority"):
        for level in escalation_levels_due(case, now):
            try:
                with transaction.atomic():
                    event = EscalationEvent.objects.create(
                        case=case,
                        level=level,
                        deadline_at=case.deadline_at,
                        status_at_escalation=case.status,
                        authority=case.assigned_authority,
                        created_at=now,
                    )
                    emit(
                        signals.case_escalated,
                        case,
                        None,
                        escalation_id=event.pk,
                        level=level,
                        deadline_at=case.deadline_at.isoformat(),
                        authority_id=case.assigned_authority_id,
                        status=case.status,
                    )
                stats["escalations_created"] += 1
            except IntegrityError:
                pass  # already escalated at this level for this deadline

    expired = Case.objects.filter(status=CaseStatus.SOLVED, verification_due_at__lt=now)
    for case in expired:
        try:
            transition(case, CaseStatus.CLOSED, actor=None, reason="Closed automatically: verification window expired.")
            stats["auto_closed"] += 1
        except Exception:  # pragma: no cover - logged and skipped so one bad row can't stop the job
            logger.exception("Auto-close failed for case %s", case.pk)
    return stats
