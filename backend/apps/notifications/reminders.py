"""Deadline reminders: notify the responsible unit before a case's deadline.
Run on a schedule via `manage.py send_deadline_reminders`; safe to repeat."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.cases.models import Case, CaseType

from .models import NotificationEvent, TargetType
from .services import authority_members, case_admins, notify


def send_deadline_reminders(now=None) -> int:
    now = now or timezone.now()
    horizon = now + timedelta(hours=settings.FMSC_NOTIFICATIONS["REMINDER_HOURS_BEFORE_DEADLINE"])
    sent = 0
    due_soon = Case.objects.active().filter(deadline_at__gt=now, deadline_at__lte=horizon).select_related(
        "assigned_authority"
    )
    for case in due_soon:
        recipients = authority_members(case.assigned_authority) or case_admins()
        hours_left = max(1, int((case.deadline_at - now).total_seconds() // 3600))
        sent += len(notify(
            recipients,
            event_type=NotificationEvent.DEADLINE_REMINDER,
            title=f"{case.case_number} is due in about {hours_left} hour{'s' if hours_left != 1 else ''}",
            body=f"{case.title} · currently {case.get_status_display().lower()}.",
            case=case,
            target_type=TargetType.SUGGESTION if case.case_type == CaseType.SUGGESTION else TargetType.CASE,
            target_id=case.pk,
            # One reminder per deadline: a changed deadline earns a new reminder.
            dedup_key=f"deadline_reminder:{case.pk}:{case.deadline_at.isoformat()}",
        ))
    return sent
