"""Case lifecycle state machine.

    submitted → under_review → assigned → in_progress → solved → closed
                     ↘ waiting_for_information ↗          ↘ reopened ↗
    submitted / under_review / waiting_for_information → rejected

`assigned` is reached only through services.assignment.assign_case, which
records assignment history. Every other status change goes through
`transition()`, which validates the move, the actor's capacity and required
reasons, then writes the status history and side effects atomically.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.cases import signals
from apps.cases.models import (
    Case,
    CaseResolution,
    CaseStatus,
    CaseStatusHistory,
    CaseUpdate,
    ResolutionOutcome,
    UpdateKind,
)

from . import access
from .access import ADMIN, AUTHORITY, SUBMITTER, SYSTEM
from .deadlines import calculate_deadline, record_deadline
from .events import emit
from .exceptions import InvalidTransition, NotPermitted, ValidationFailed

S = CaseStatus

#: from_status -> {to_status: actor capacities allowed to make the move}
TRANSITIONS = {
    S.SUBMITTED: {S.UNDER_REVIEW: {ADMIN}, S.REJECTED: {ADMIN}},
    S.UNDER_REVIEW: {S.WAITING_FOR_INFORMATION: {ADMIN}, S.REJECTED: {ADMIN}},
    S.WAITING_FOR_INFORMATION: {
        S.UNDER_REVIEW: {ADMIN},
        S.IN_PROGRESS: {ADMIN, AUTHORITY},
        S.REJECTED: {ADMIN},
    },
    S.ASSIGNED: {
        S.IN_PROGRESS: {ADMIN, AUTHORITY},
        S.WAITING_FOR_INFORMATION: {ADMIN, AUTHORITY},
        S.SOLVED: {ADMIN, AUTHORITY},
    },
    S.IN_PROGRESS: {
        S.WAITING_FOR_INFORMATION: {ADMIN, AUTHORITY},
        S.SOLVED: {ADMIN, AUTHORITY},
    },
    S.SOLVED: {S.CLOSED: {ADMIN, SUBMITTER, SYSTEM}, S.REOPENED: {ADMIN, SUBMITTER}},
    S.CLOSED: {S.REOPENED: {ADMIN, SUBMITTER}},
    S.REJECTED: {S.UNDER_REVIEW: {ADMIN}},
    S.REOPENED: {
        S.UNDER_REVIEW: {ADMIN},
        S.IN_PROGRESS: {ADMIN, AUTHORITY},
        S.WAITING_FOR_INFORMATION: {ADMIN, AUTHORITY},
        S.SOLVED: {ADMIN, AUTHORITY},
    },
}

#: Statuses from which an administrator may (re)assign a case.
ASSIGNABLE_FROM = frozenset(
    {S.SUBMITTED, S.UNDER_REVIEW, S.WAITING_FOR_INFORMATION, S.ASSIGNED, S.IN_PROGRESS, S.REOPENED}
)

REASON_REQUIRED = {
    S.REJECTED: "A rejection reason is required.",
    S.REOPENED: "A reason is required to reopen a case.",
    S.WAITING_FOR_INFORMATION: "Describe the information that is needed.",
}
MIN_RESOLUTION_NOTE = 10


def allowed_transitions(case: Case, user) -> list:
    """Status values `user` may move `case` to right now (for UI hints only)."""
    kinds = access.actor_kinds(user, case)
    result = []
    for to_status, capacities in TRANSITIONS.get(case.status, {}).items():
        if kinds & capacities and _authority_precondition_ok(case, to_status, kinds):
            if to_status == S.REOPENED and kinds.isdisjoint({ADMIN}) and not _submitter_can_reopen(case):
                continue
            result.append(to_status)
    if ADMIN in kinds and case.status in ASSIGNABLE_FROM:
        result.append(S.ASSIGNED)
    return result


def _authority_precondition_ok(case, to_status, kinds):
    # Moving into active work needs an assigned authority.
    if to_status in (S.IN_PROGRESS, S.SOLVED) and case.assigned_authority_id is None:
        return False
    return True


def _submitter_can_reopen(case: Case) -> bool:
    if case.status == S.SOLVED:
        return True
    if case.status == S.CLOSED and case.closed_at:
        window = timedelta(days=settings.FMSC_CASES["REOPEN_WINDOW_DAYS"])
        return timezone.now() <= case.closed_at + window
    return False


def write_history(case, from_status, to_status, actor, reason=""):
    return CaseStatusHistory.objects.create(
        case=case, from_status=from_status or "", to_status=to_status, changed_by=actor, reason=reason or ""
    )


def transition(case: Case, to_status, *, actor, reason="", resolution_note=""):
    """Move `case` to `to_status`. `actor=None` means the scheduled system job."""
    to_status = S(to_status)
    reason = (reason or "").strip()
    resolution_note = (resolution_note or "").strip()

    with transaction.atomic():
        case = Case.objects.select_for_update(of=("self",)).select_related("assigned_authority").get(pk=case.pk)
        from_status = S(case.status)
        allowed = TRANSITIONS.get(from_status, {})

        if to_status == S.ASSIGNED:
            raise InvalidTransition("Use the assignment action to assign a case.")
        if to_status not in allowed:
            raise InvalidTransition(
                f"A case cannot move from '{from_status.label}' to '{to_status.label}'.",
                details={"from_status": from_status, "to_status": to_status},
            )

        kinds = access.actor_kinds(actor, case)
        capacities = allowed[to_status] & kinds
        if not capacities:
            raise NotPermitted("You are not permitted to make this status change.")
        if not _authority_precondition_ok(case, to_status, kinds):
            raise InvalidTransition("The case must be assigned to an authority first.")

        if to_status in REASON_REQUIRED and not reason:
            raise ValidationFailed(REASON_REQUIRED[to_status], details={"reason": ["This field is required."]})
        if to_status == S.SOLVED and len(resolution_note) < MIN_RESOLUTION_NOTE:
            raise ValidationFailed(
                f"A resolution note of at least {MIN_RESOLUTION_NOTE} characters is required.",
                details={"resolution_note": ["A resolution note is required to mark a case as solved."]},
            )
        if to_status == S.REOPENED and capacities == {SUBMITTER} and not _submitter_can_reopen(case):
            raise InvalidTransition("The reopening period for this case has ended. Please submit a new case.")

        now = timezone.now()
        fields = {"status", "updated_at"}
        case.status = to_status
        extra = {}

        if to_status == S.SOLVED:
            case.solved_at = now
            case.verification_due_at = now + timedelta(days=settings.FMSC_CASES["VERIFICATION_WINDOW_DAYS"])
            fields |= {"solved_at", "verification_due_at"}
            resolution = CaseResolution.objects.create(case=case, resolved_by=actor, note=resolution_note, resolved_at=now)
            CaseUpdate.objects.create(case=case, author=actor, kind=UpdateKind.RESOLUTION, body=resolution_note)
            extra["resolution"] = resolution

        elif to_status in (S.CLOSED, S.REJECTED):
            case.closed_at = now
            case.verification_due_at = None
            fields |= {"closed_at", "verification_due_at"}
            if to_status == S.CLOSED:
                if actor is None:
                    outcome = ResolutionOutcome.AUTO_CLOSED
                elif SUBMITTER in capacities:
                    outcome = ResolutionOutcome.CONFIRMED
                else:
                    outcome = ResolutionOutcome.CLOSED_BY_ADMIN
                _settle_pending_resolution(case, outcome, feedback=reason, now=now)

        elif to_status == S.REOPENED:
            case.closed_at = None
            case.verification_due_at = None
            case.reopen_count += 1
            fields |= {"closed_at", "verification_due_at", "reopen_count"}
            outcome = ResolutionOutcome.DISPUTED if SUBMITTER in capacities and ADMIN not in capacities else ResolutionOutcome.SUPERSEDED
            _settle_pending_resolution(case, outcome, feedback=reason, now=now)

        elif from_status == S.REJECTED:
            case.closed_at = None
            fields.add("closed_at")

        elif to_status == S.WAITING_FOR_INFORMATION:
            CaseUpdate.objects.create(case=case, author=actor, kind=UpdateKind.INFORMATION_REQUEST, body=reason)

        case.save(update_fields=sorted(fields))
        write_history(case, from_status, to_status, actor, reason or resolution_note)

        if to_status == S.REOPENED:
            new_deadline = calculate_deadline(
                priority=case.priority, case_type=case.case_type, category=case.category, start=now
            )
            record_deadline(case, new_deadline, actor=actor, reason="Deadline recalculated after reopening.")

        emit(signals.case_status_changed, case, actor, from_status=from_status, to_status=to_status, reason=reason)
        if to_status == S.SOLVED:
            emit(
                signals.case_solved,
                case,
                actor,
                resolution_id=extra["resolution"].pk,
                verification_due_at=case.verification_due_at.isoformat(),
            )
        if to_status == S.REOPENED:
            emit(signals.case_reopened, case, actor, reason=reason, reopen_count=case.reopen_count, previous_status=from_status)
    return case


def _settle_pending_resolution(case, outcome, *, feedback, now):
    CaseResolution.objects.filter(case=case, outcome=ResolutionOutcome.PENDING).update(
        outcome=outcome, submitter_feedback=feedback or "", outcome_at=now
    )
