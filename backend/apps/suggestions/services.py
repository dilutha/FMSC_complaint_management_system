"""Suggestion evaluation workflow.

Every action that changes the underlying case goes through Member A's case
services (assign_case, transition), so the case lifecycle rules, history and
integration signals stay authoritative:

    start evaluation  submitted → under_evaluation     case → under_review
    accept            → accepted (responsible unit)    case → assigned (assign_case)
    decline           → declined (reason required)     case → rejected
    reconsider        declined → under_evaluation      case → under_review
    plan              accepted/planned → planned       case unchanged
    record progress   (status unchanged)               case → in_progress on first update
    mark implemented  accepted/planned → implemented   case → solved (submitter verifies)

Changes made directly through the case API are mirrored by sync_from_case().
"""
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record as audit
from apps.cases.models import Case, CaseStatus, CaseType, ResolutionOutcome
from apps.cases.services import access
from apps.cases.services.assignment import assign_case
from apps.cases.services.exceptions import InvalidTransition, NotPermitted, ValidationFailed
from apps.cases.services.workflow import ASSIGNABLE_FROM, transition
from apps.notifications.models import NotificationEvent, TargetType
from apps.notifications.services import notify

from .models import SuggestionEvaluation, SuggestionProgressUpdate, SuggestionStatus, SuggestionStatusChange

St = SuggestionStatus
CS = CaseStatus
MIN_REASON = 10
OPEN_FOR_DECISION = {St.SUBMITTED, St.UNDER_EVALUATION}
IN_IMPLEMENTATION = {St.ACCEPTED, St.PLANNED}
_DECLINABLE_CASE_STATUSES = {CS.SUBMITTED, CS.UNDER_REVIEW, CS.WAITING_FOR_INFORMATION}
_SOLVABLE_CASE_STATUSES = {CS.ASSIGNED, CS.IN_PROGRESS, CS.REOPENED}


# --- Evaluation records --------------------------------------------------------------


def initial_status_for(case: Case) -> str:
    """Suggestion status implied by a case's current status (for records created later)."""
    return {
        CS.SUBMITTED: St.SUBMITTED,
        CS.UNDER_REVIEW: St.UNDER_EVALUATION,
        CS.WAITING_FOR_INFORMATION: St.UNDER_EVALUATION,
        CS.ASSIGNED: St.ACCEPTED,
        CS.IN_PROGRESS: St.ACCEPTED,
        CS.REOPENED: St.ACCEPTED,
        CS.SOLVED: St.IMPLEMENTED,
        CS.CLOSED: St.IMPLEMENTED,
        CS.REJECTED: St.DECLINED,
    }[CS(case.status)]


def get_evaluation(case: Case) -> SuggestionEvaluation:
    if case.case_type != CaseType.SUGGESTION:
        raise ValidationFailed("This case is not a suggestion.")
    evaluation = SuggestionEvaluation.objects.filter(case=case).first()
    if evaluation:
        return evaluation
    status = initial_status_for(case)
    reason = ""
    if status == St.DECLINED:
        last = case.status_history.filter(to_status=CS.REJECTED).order_by("-id").first()
        reason = (last.reason if last else "") or "Rejected before suggestion evaluation was recorded."
    evaluation, _ = SuggestionEvaluation.objects.get_or_create(
        case=case,
        defaults={"status": status, "responsible_unit": case.assigned_authority, "decision_reason": reason},
    )
    return evaluation


def _lock(case: Case) -> SuggestionEvaluation:
    get_evaluation(case)
    return SuggestionEvaluation.objects.select_for_update(of=("self",)).select_related("case", "responsible_unit").get(case=case)


def _set_status(evaluation, to_status, *, actor, reason="", **fields):
    from_status = evaluation.status
    evaluation.status = to_status
    for name, value in fields.items():
        setattr(evaluation, name, value)
    evaluation.save()
    change = SuggestionStatusChange.objects.create(
        evaluation=evaluation, from_status=from_status, to_status=to_status, actor=actor, reason=reason or "",
        responsible_unit=evaluation.responsible_unit, target_date=evaluation.target_date,
    )
    audit(
        f"suggestion.{to_status}", actor=actor, entity_type="suggestion", entity_id=evaluation.case_id,
        entity_label=evaluation.case.case_number, previous={"status": from_status},
        new={"status": to_status, "responsible_unit_id": evaluation.responsible_unit_id,
             "target_date": evaluation.target_date},
        reason=reason,
    )
    return change


# --- Permissions ------------------------------------------------------------------------


def can_decide(user) -> bool:
    return bool(user and user.is_authenticated and user.can_evaluate_suggestions)


def can_implement(user, case) -> bool:
    return can_decide(user) or access.is_assigned_member(user, case)


def _require_decider(user):
    if not can_decide(user):
        raise NotPermitted("Only administrators can record suggestion decisions.")


def _require_implementer(user, case):
    if not can_implement(user, case):
        raise NotPermitted("Only administrators or the responsible unit can update implementation.")


def _require_reason(reason, message):
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON:
        raise ValidationFailed(message, details={"reason": [f"Enter at least {MIN_REASON} characters."]})
    return reason


def allowed_actions(evaluation: SuggestionEvaluation, user) -> list:
    """Action names `user` may take now (UI hints; every action re-checks)."""
    case, status, actions = evaluation.case, evaluation.status, []
    if can_decide(user):
        if status == St.SUBMITTED and case.status in (CS.SUBMITTED, CS.UNDER_REVIEW):
            actions.append("start_evaluation")
        if status in OPEN_FOR_DECISION and case.status in ASSIGNABLE_FROM:
            actions.append("accept")
        if status in OPEN_FOR_DECISION and case.status in _DECLINABLE_CASE_STATUSES:
            actions.append("decline")
        if status == St.DECLINED and case.status == CS.REJECTED:
            actions.append("reconsider")
    if status in IN_IMPLEMENTATION and can_implement(user, case):
        actions += ["plan", "record_progress"]
        if case.status in _SOLVABLE_CASE_STATUSES:
            actions.append("mark_implemented")
    return actions


# --- Decisions (administrators) ----------------------------------------------------------


def start_evaluation(case: Case, *, actor) -> SuggestionEvaluation:
    _require_decider(actor)
    with transaction.atomic():
        evaluation = _lock(case)
        if evaluation.status != St.SUBMITTED:
            raise InvalidTransition("Evaluation has already started for this suggestion.")
        _set_status(evaluation, St.UNDER_EVALUATION, actor=actor, reason="Evaluation started.")
        if case.status == CS.SUBMITTED:
            transition(case, CS.UNDER_REVIEW, actor=actor, reason="Suggestion evaluation started.")
    return evaluation


def accept(case: Case, *, actor, responsible_unit, reason="", target_date=None) -> SuggestionEvaluation:
    _require_decider(actor)
    if responsible_unit is None:
        raise ValidationFailed("Choose the responsible unit.", details={"responsible_unit_id": ["This field is required."]})
    if target_date and target_date < timezone.localdate():
        raise ValidationFailed("The target date cannot be in the past.", details={"target_date": ["Must not be in the past."]})
    with transaction.atomic():
        evaluation = _lock(case)
        if evaluation.status not in OPEN_FOR_DECISION:
            raise InvalidTransition(f"A suggestion that is '{evaluation.get_status_display()}' cannot be accepted.")
        reason = (reason or "").strip()
        _set_status(
            evaluation, St.ACCEPTED, actor=actor, reason=reason or "Accepted for implementation.",
            responsible_unit=responsible_unit, decision_reason=reason, decided_by=actor, decided_at=timezone.now(),
            target_date=target_date or evaluation.target_date,
        )
        assign_case(case, actor=actor, authority=responsible_unit,
                    message=reason or "Accepted for implementation.", internal_note=reason)
    return evaluation


def decline(case: Case, *, actor, reason) -> SuggestionEvaluation:
    _require_decider(actor)
    reason = _require_reason(reason, "A reason is required to decline a suggestion.")
    with transaction.atomic():
        evaluation = _lock(case)
        if evaluation.status not in OPEN_FOR_DECISION:
            raise InvalidTransition(f"A suggestion that is '{evaluation.get_status_display()}' cannot be declined.")
        _set_status(evaluation, St.DECLINED, actor=actor, reason=reason, decision_reason=reason, decided_by=actor,
                    decided_at=timezone.now())
        transition(case, CS.REJECTED, actor=actor, reason=reason)
    return evaluation


def reconsider(case: Case, *, actor, reason) -> SuggestionEvaluation:
    _require_decider(actor)
    reason = _require_reason(reason, "A reason is required to reconsider a declined suggestion.")
    with transaction.atomic():
        evaluation = _lock(case)
        if evaluation.status != St.DECLINED:
            raise InvalidTransition("Only declined suggestions can be reconsidered.")
        _set_status(evaluation, St.UNDER_EVALUATION, actor=actor, reason=reason)
        transition(case, CS.UNDER_REVIEW, actor=actor, reason=reason)
    return evaluation


# --- Implementation (administrators or the responsible unit) -------------------------------


def plan(case: Case, *, actor, target_date, plan_note="") -> SuggestionEvaluation:
    _require_implementer(actor, case)
    if target_date is None:
        raise ValidationFailed("Enter a target date.", details={"target_date": ["This field is required."]})
    if target_date < timezone.localdate():
        raise ValidationFailed("The target date cannot be in the past.", details={"target_date": ["Must not be in the past."]})
    with transaction.atomic():
        evaluation = _lock(case)
        if evaluation.status not in IN_IMPLEMENTATION:
            raise InvalidTransition("Only accepted suggestions can be planned.")
        rescheduled = evaluation.status == St.PLANNED
        plan_note = (plan_note or "").strip()
        change = _set_status(
            evaluation, St.PLANNED, actor=actor,
            reason=plan_note or ("Target date changed." if rescheduled else "Implementation planned."),
            target_date=target_date, plan_note=plan_note or evaluation.plan_note,
        )
        _notify_submitter(
            evaluation, actor, f"suggestion_plan:{change.pk}",
            f"Suggestion {case.case_number} {'rescheduled' if rescheduled else 'planned'}",
            f"Target completion date: {target_date:%d %b %Y}.",
        )
    return evaluation


def record_progress(case: Case, *, actor, note, percent_complete=None) -> SuggestionProgressUpdate:
    _require_implementer(actor, case)
    note = (note or "").strip()
    if not note:
        raise ValidationFailed("Describe the progress made.", details={"note": ["This field is required."]})
    if percent_complete is not None and not 0 <= percent_complete < 100:
        raise ValidationFailed(
            "Progress must be between 0 and 99%. Use “Mark as implemented” when the work is complete.",
            details={"percent_complete": ["Enter a value from 0 to 99."]},
        )
    with transaction.atomic():
        evaluation = _lock(case)
        if evaluation.status not in IN_IMPLEMENTATION:
            raise InvalidTransition("Progress can only be recorded for accepted or planned suggestions.")
        update = SuggestionProgressUpdate.objects.create(
            evaluation=evaluation, author=actor, note=note, percent_complete=percent_complete
        )
        if percent_complete is not None:
            evaluation.progress_percent = percent_complete
            evaluation.save(update_fields=["progress_percent", "updated_at"])
        if Case.objects.get(pk=case.pk).status in (CS.ASSIGNED, CS.REOPENED):
            transition(case, CS.IN_PROGRESS, actor=actor, reason=f"Implementation started: {note}")
        audit("suggestion.progress_recorded", actor=actor, entity_type="suggestion", entity_id=case.pk,
              entity_label=case.case_number, new={"percent_complete": percent_complete},
              metadata={"progress_update_id": update.pk})
        body = f"{percent_complete}% complete." if percent_complete is not None else "A progress update was added."
        _notify_submitter(evaluation, actor, f"suggestion_progress:{update.pk}",
                          f"Progress on suggestion {case.case_number}", body)
    return update


def mark_implemented(case: Case, *, actor, summary) -> SuggestionEvaluation:
    _require_implementer(actor, case)
    summary = (summary or "").strip()
    if len(summary) < MIN_REASON:
        raise ValidationFailed(
            "Describe what was implemented.", details={"summary": [f"Enter at least {MIN_REASON} characters."]}
        )
    with transaction.atomic():
        evaluation = _lock(case)
        if evaluation.status not in IN_IMPLEMENTATION:
            raise InvalidTransition("Only accepted or planned suggestions can be marked as implemented.")
        _set_status(evaluation, St.IMPLEMENTED, actor=actor, reason=summary, implementation_summary=summary,
                    implemented_at=timezone.now(), progress_percent=100)
        # The submitter then confirms through the normal case verification flow.
        transition(case, CS.SOLVED, actor=actor, resolution_note=summary)
    return evaluation


def _notify_submitter(evaluation, actor, dedup_key, title, body):
    case = evaluation.case

    def _send():
        notify([case.submitted_by], event_type=NotificationEvent.SUGGESTION_UPDATE, title=title, body=body,
               case=case, target_type=TargetType.SUGGESTION, target_id=case.pk, dedup_key=dedup_key, exclude=actor)

    transaction.on_commit(_send)


# --- Mirroring case changes made outside this module ---------------------------------------


def sync_from_case(case: Case, *, actor, from_status, to_status, reason=""):
    """Keep the evaluation consistent when the case status changes through the
    case API. A no-op when this module made the change itself, and for stale
    events (delivered after the case has already moved on)."""
    if Case.objects.filter(pk=case.pk).values_list("status", flat=True).first() != to_status:
        return get_evaluation(case)
    with transaction.atomic():
        evaluation = _lock(case)
        status = evaluation.status
        if to_status == CS.UNDER_REVIEW and status in (St.SUBMITTED, St.DECLINED):
            _set_status(evaluation, St.UNDER_EVALUATION, actor=actor, reason=reason or "Case moved to review.")
        elif to_status == CS.ASSIGNED and status in (OPEN_FOR_DECISION | {St.DECLINED}):
            _set_status(evaluation, St.ACCEPTED, actor=actor, reason="Assigned through case management.",
                        responsible_unit=case.assigned_authority, decided_by=actor, decided_at=timezone.now())
        elif (to_status == CS.ASSIGNED and status in IN_IMPLEMENTATION
              and evaluation.responsible_unit_id != case.assigned_authority_id):
            _set_status(evaluation, status, actor=actor, reason="Responsible unit changed.",
                        responsible_unit=case.assigned_authority)
        elif to_status == CS.REJECTED and status != St.DECLINED:
            reason = reason or "Rejected through case management."
            _set_status(evaluation, St.DECLINED, actor=actor, reason=reason, decision_reason=reason,
                        decided_by=actor, decided_at=timezone.now())
        elif to_status == CS.SOLVED and status != St.IMPLEMENTED:
            resolution = case.resolutions.filter(outcome=ResolutionOutcome.PENDING).order_by("-id").first()
            summary = resolution.note if resolution else ""
            _set_status(evaluation, St.IMPLEMENTED, actor=actor, reason=summary or "Marked as solved.",
                        implementation_summary=summary, implemented_at=timezone.now(), progress_percent=100)
        elif to_status == CS.REOPENED and status == St.IMPLEMENTED:
            _set_status(evaluation, St.ACCEPTED, actor=actor, reason=reason or "Implementation reopened.",
                        implemented_at=None)
    return evaluation
