"""Progress updates, resolution verification and reopening."""
from django.db import transaction

from apps.cases import signals
from apps.cases.models import TERMINAL_STATUSES, AttachmentKind, Case, CaseStatus, CaseUpdate, UpdateKind

from . import access
from .access import ADMIN, AUTHORITY, MONITOR, SUBMITTER
from .attachments import save_attachments
from .events import emit
from .exceptions import InvalidTransition, NotPermitted, ValidationFailed
from .workflow import transition

STAFF_KINDS = {UpdateKind.COMMENT, UpdateKind.PROGRESS}
SUBMITTER_KINDS = {UpdateKind.COMMENT, UpdateKind.INFORMATION_RESPONSE}


def add_update(case: Case, *, actor, body, kind=UpdateKind.COMMENT, is_internal=False, new_status=None,
               resolution_note="", reason="", attachments=()):
    """Add a comment/progress note, optionally moving the case to a new status
    in the same request (the 'Save progress' / 'Mark as solved' actions)."""
    with transaction.atomic():
        # Re-read and lock: permissions and status checks must use current state.
        case = Case.objects.select_for_update(of=("self",)).select_related("assigned_authority").get(pk=case.pk)
        return _add_update_locked(case, actor=actor, body=body, kind=kind, is_internal=is_internal,
                                  new_status=new_status, resolution_note=resolution_note, reason=reason,
                                  attachments=attachments)


def _add_update_locked(case, *, actor, body, kind, is_internal, new_status, resolution_note, reason, attachments):
    kinds = access.actor_kinds(actor, case)
    body = (body or "").strip()
    is_staff = bool(kinds & {ADMIN, AUTHORITY})
    is_monitor = MONITOR in kinds and not kinds & {ADMIN, AUTHORITY, SUBMITTER}

    if not kinds & {ADMIN, AUTHORITY, SUBMITTER, MONITOR}:
        raise NotPermitted("You cannot add updates to this case.")
    if is_monitor:
        # Admins monitor: they may post messages, but never change status or add files.
        if new_status:
            raise NotPermitted("Admins can add messages but cannot change a case's status.")
        if attachments:
            raise NotPermitted("Admins cannot attach files to a case.")
        if not body:
            raise ValidationFailed("Please enter a message.", details={"body": ["This field is required."]})
        kind = UpdateKind.ADMIN_MESSAGE
    elif is_staff:
        if kind not in STAFF_KINDS:
            raise ValidationFailed("Unsupported update type.", details={"kind": ["Invalid for staff."]})
    else:
        if kind not in SUBMITTER_KINDS:
            raise ValidationFailed("Unsupported update type.", details={"kind": ["Invalid for submitters."]})
        if is_internal:
            raise NotPermitted("Only staff can add internal notes.")
        if new_status:
            raise NotPermitted("Use the verification or reopen actions to change this case's status.")
    if case.status in TERMINAL_STATUSES and ADMIN not in kinds:
        raise InvalidTransition("This case is closed. Reopen it to add updates.")
    if not body and not new_status:
        raise ValidationFailed("Please enter an update.", details={"body": ["This field is required."]})
    if attachments and not is_staff and case.status in TERMINAL_STATUSES:
        raise InvalidTransition("Attachments cannot be added to a closed case.")

    with transaction.atomic():
        update = None
        if body:
            update = CaseUpdate.objects.create(case=case, author=actor, kind=kind, body=body, is_internal=is_internal)
            if attachments:
                save_attachments(
                    case,
                    list(attachments),
                    actor=actor,
                    kind=AttachmentKind.COMPLETION if is_staff else AttachmentKind.EVIDENCE,
                    update=update,
                )
            emit(signals.case_update_added, case, actor, update_id=update.pk, kind=kind, is_internal=is_internal)
        if new_status:
            case = transition(case, new_status, actor=actor, reason=reason or body, resolution_note=resolution_note)
    return update, case


def verify_resolution(case: Case, *, actor, confirmed: bool, feedback=""):
    """Submitter confirms the fix (→ closed) or reports the problem persists (→ reopened)."""
    feedback = (feedback or "").strip()
    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)
        if SUBMITTER not in access.actor_kinds(actor, case):
            raise NotPermitted("Only the person who submitted this case can verify its resolution.")
        if case.status != CaseStatus.SOLVED:
            raise InvalidTransition("This case is not awaiting verification.")
        if not confirmed and not feedback:
            raise ValidationFailed(
                "Please describe why the problem has not been resolved.",
                details={"feedback": ["This field is required."]},
            )
        resolution = case.resolutions.filter(outcome="pending").first()
        CaseUpdate.objects.create(
            case=case,
            author=actor,
            kind=UpdateKind.VERIFICATION,
            body=("Confirmed the issue is resolved." if confirmed else "Reported that the problem persists.")
            + (f" {feedback}" if feedback else ""),
        )
        if confirmed:
            case = transition(case, CaseStatus.CLOSED, actor=actor, reason=feedback or "Resolution confirmed by submitter.")
        else:
            case = transition(case, CaseStatus.REOPENED, actor=actor, reason=feedback)
        emit(
            signals.case_resolution_verified,
            case,
            actor,
            resolution_id=resolution.pk if resolution else None,
            confirmed=confirmed,
            feedback=feedback,
        )
    return case


def reopen_case(case: Case, *, actor, reason):
    return transition(case, CaseStatus.REOPENED, actor=actor, reason=reason)
