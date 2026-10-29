"""Stable identifiers for case-module events.

Member A's signals can be delivered more than once (retries, re-running a
job). Audit and notification receivers derive a deterministic key per event
from the record the event created, then rely on unique constraints so a
second delivery is a no-op.
"""
from apps.cases.models import CaseAssignment, CaseStatusHistory, DeadlineChange


def case_event_ref(event: str, case, payload: dict) -> str:
    """Return "<event>:<case id>:<discriminator>" for a case signal."""
    if event == "case_submitted":
        part = "0"
    elif event == "case_assigned":
        part = _latest_id(CaseAssignment.objects.filter(case=case, authority_id=payload.get("authority_id")))
    elif event == "case_status_changed":
        part = _latest_id(CaseStatusHistory.objects.filter(case=case, to_status=payload.get("to_status")))
    elif event == "case_solved":
        part = payload.get("resolution_id")
    elif event == "case_resolution_verified":
        part = f"{payload.get('resolution_id')}-{bool(payload.get('confirmed'))}"
    elif event == "case_reopened":
        part = payload.get("reopen_count")
    elif event == "case_escalated":
        part = payload.get("escalation_id")
    elif event == "case_deadline_changed":
        part = _latest_id(DeadlineChange.objects.filter(case=case))
    elif event == "case_update_added":
        part = payload.get("update_id")
    else:
        raise ValueError(f"Unknown case event: {event}")
    return f"{event}:{case.pk}:{part}"


def _latest_id(queryset):
    return queryset.order_by("-id").values_list("id", flat=True).first() or 0
