"""Turns the case module's integration signals (apps.cases.signals) into
notifications. Rules:

* One notification per recipient per event (dedup key from apps.audit.event_refs).
* The person who acted is never notified of their own action, except for the
  submission confirmation.
* Suggestions are cases with case_type="suggestion"; they get suggestion
  wording and open the suggestion screen.
* Bodies never contain internal notes, assignment notes or comment text.
"""
from apps.audit.event_refs import case_event_ref
from apps.cases import signals
from apps.cases.models import CaseStatus, CaseType, Priority

from .models import NotificationEvent as E
from .models import TargetType
from .services import authority_members, case_admins, management_viewers, notify

S = CaseStatus
_PRE_ACCEPTANCE = {S.SUBMITTED, S.UNDER_REVIEW, S.WAITING_FOR_INFORMATION}


def _is_suggestion(case) -> bool:
    return case.case_type == CaseType.SUGGESTION


def _noun(case) -> str:
    return "suggestion" if _is_suggestion(case) else "case"


def _send(event, case, payload, recipients, *, event_type, title, body="", exclude=None, audience=""):
    target_type = TargetType.SUGGESTION if _is_suggestion(case) else TargetType.CASE
    key = case_event_ref(event, case, payload) + (f":{audience}" if audience else "")
    return notify(recipients, event_type=event_type, title=title, body=body, case=case, target_type=target_type,
                  target_id=case.pk, dedup_key=key, exclude=exclude)


def on_case_submitted(sender, case, actor, payload, **kwargs):
    noun, num = _noun(case), case.case_number
    _send("case_submitted", case, payload, [case.submitted_by], event_type=E.CASE_SUBMITTED, audience="submitter",
          title=f"We received your {noun} {num}",
          body=f"“{case.title}” has been submitted. You will be notified as it progresses.")
    _send("case_submitted", case, payload, case_admins(), event_type=E.NEW_CASE, exclude=actor, audience="staff",
          title=f"New {noun} {num} to review",
          body=f"{case.category.name} · {Priority(case.priority).label} priority: {case.title}")


def on_case_assigned(sender, case, actor, payload, **kwargs):
    num, unit = case.case_number, payload.get("authority_name") or ""
    if _is_suggestion(case):
        title = f"Suggestion {num} assigned to {unit} for implementation"
    else:
        title = f"Case {num} assigned to {unit}"
    _send("case_assigned", case, payload, authority_members(case.assigned_authority), event_type=E.CASE_ASSIGNED,
          exclude=actor, title=title, body=f"{case.title} · {Priority(case.priority).label} priority")


def _status_message(case, from_status, to_status, reason, actor):
    """(event_type, title, body) for the submitter, or None when another event covers it."""
    num = case.case_number
    if to_status == S.WAITING_FOR_INFORMATION:
        return E.INFORMATION_REQUESTED, f"More information needed for {num}", reason
    if _is_suggestion(case):
        if to_status == S.UNDER_REVIEW:
            return E.STATUS_UPDATE, f"Your suggestion {num} is being evaluated", ""
        if to_status == S.ASSIGNED and from_status in _PRE_ACCEPTANCE:
            unit = case.assigned_authority.name if case.assigned_authority else "the responsible unit"
            return E.SUGGESTION_DECISION, f"Suggestion {num} accepted for implementation", f"{unit} will implement it."
        if to_status == S.REJECTED:
            return E.SUGGESTION_DECISION, f"Suggestion {num} was declined", reason
        if to_status == S.CLOSED:
            return E.STATUS_UPDATE, f"Suggestion {num} closed", ""
        return None  # in_progress: progress updates come from the suggestion module
    if to_status == S.UNDER_REVIEW:
        return E.STATUS_UPDATE, f"Your case {num} is under review", ""
    if to_status == S.ASSIGNED:
        unit = case.assigned_authority.name if case.assigned_authority else "A responsible unit"
        return E.STATUS_UPDATE, f"Your case {num} has been assigned", f"{unit} is responsible for this case."
    if to_status == S.IN_PROGRESS:
        return E.STATUS_UPDATE, f"Work has started on {num}", ""
    if to_status == S.CLOSED:
        body = "Closed automatically after the verification period ended." if actor is None else ""
        return E.STATUS_UPDATE, f"Case {num} closed", body
    if to_status == S.REJECTED:
        return E.CASE_REJECTED, f"Case {num} was rejected", reason
    return None  # solved and reopened have dedicated events


def on_case_status_changed(sender, case, actor, payload, **kwargs):
    message = _status_message(case, payload.get("from_status"), payload.get("to_status"),
                              payload.get("reason") or "", actor)
    if message:
        event_type, title, body = message
        _send("case_status_changed", case, payload, [case.submitted_by], event_type=event_type, title=title,
              body=body, exclude=actor)


def on_case_solved(sender, case, actor, payload, **kwargs):
    num = case.case_number
    if _is_suggestion(case):
        event_type, title = E.SUGGESTION_UPDATE, f"Suggestion {num} has been implemented"
    else:
        event_type, title = E.CASE_SOLVED, f"Case {num} solved – please confirm"
    body = "Please check the resolution and confirm it, or tell us if the problem persists."
    if case.verification_due_at:
        body += f" Respond by {case.verification_due_at:%d %b %Y}."
    _send("case_solved", case, payload, [case.submitted_by], event_type=event_type, title=title, body=body,
          exclude=actor)


def on_case_resolution_verified(sender, case, actor, payload, **kwargs):
    if not payload.get("confirmed"):
        return  # the matching case_reopened event notifies staff
    _send("case_resolution_verified", case, payload, authority_members(case.assigned_authority),
          event_type=E.RESOLUTION_VERIFIED, exclude=actor,
          title=f"Submitter confirmed {case.case_number} is resolved")


def on_case_reopened(sender, case, actor, payload, **kwargs):
    num, reason = case.case_number, payload.get("reason") or ""
    staff = authority_members(case.assigned_authority) + case_admins()
    _send("case_reopened", case, payload, staff, event_type=E.CASE_REOPENED, exclude=actor, audience="staff",
          title=f"{_noun(case).capitalize()} {num} was reopened", body=reason)
    if actor is not None and actor.pk != case.submitted_by_id:
        _send("case_reopened", case, payload, [case.submitted_by], event_type=E.CASE_REOPENED,
              audience="submitter", title=f"Your {_noun(case)} {num} was reopened", body=reason)


def on_case_escalated(sender, case, actor, payload, **kwargs):
    level = payload.get("level") or 1
    recipients = authority_members(case.assigned_authority) + case_admins()
    if level >= 2:
        recipients += management_viewers()
    deadline = case.deadline_at.strftime("%d %b %Y, %H:%M") if case.deadline_at else "the deadline"
    _send("case_escalated", case, payload, recipients, event_type=E.ESCALATION,
          title=f"{case.case_number} is overdue (escalation level {level})",
          body=f"The deadline ({deadline}) has passed and the case is still {case.get_status_display().lower()}.")


def on_case_update_added(sender, case, actor, payload, **kwargs):
    if payload.get("is_internal") or actor is None:
        return
    num = case.case_number
    if actor.pk == case.submitted_by_id:
        staff = authority_members(case.assigned_authority) or case_admins()
        is_info = payload.get("kind") == "information_response"
        _send("case_update_added", case, payload, staff, event_type=E.CASE_UPDATE, exclude=actor,
              title=f"{'Information provided' if is_info else 'New comment'} on {num}",
              body="The submitter added an update. Open the case to read it.")
    else:
        _send("case_update_added", case, payload, [case.submitted_by], event_type=E.CASE_UPDATE, exclude=actor,
              title=f"New update on your {_noun(case)} {num}", body="Open it to read the update.")


def connect():
    signals.case_submitted.connect(on_case_submitted, dispatch_uid="notify_case_submitted")
    signals.case_assigned.connect(on_case_assigned, dispatch_uid="notify_case_assigned")
    signals.case_status_changed.connect(on_case_status_changed, dispatch_uid="notify_case_status_changed")
    signals.case_solved.connect(on_case_solved, dispatch_uid="notify_case_solved")
    signals.case_resolution_verified.connect(on_case_resolution_verified, dispatch_uid="notify_case_verified")
    signals.case_reopened.connect(on_case_reopened, dispatch_uid="notify_case_reopened")
    signals.case_escalated.connect(on_case_escalated, dispatch_uid="notify_case_escalated")
    signals.case_update_added.connect(on_case_update_added, dispatch_uid="notify_case_update")
