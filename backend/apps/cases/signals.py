"""Integration contract between the case module (Member A) and Member B's
notification, audit and dashboard services.

The case module never imports Member B's code. It emits these signals *after*
the surrounding database transaction commits (see services.events.emit), so
receivers never observe rolled-back state and a failing receiver cannot undo a
case change.

Every signal is sent with ``sender=Case`` and these keyword arguments:

    case       – the Case instance (re-read after commit)
    actor      – the User who acted, or None for scheduled/system actions
    payload    – a dict of JSON-serialisable event details (documented below)

Member B connects receivers, e.g. in their AppConfig.ready():

    from apps.cases import signals
    signals.case_solved.connect(notify_submitter_case_solved)
"""
from django.dispatch import Signal

# payload: {"case_number", "case_type", "priority", "category"}
case_submitted = Signal()

# payload: {"authority_id", "authority_name", "previous_authority_id",
#           "is_reassignment", "is_override", "recommended_authority_id"}
case_assigned = Signal()

# payload: {"from_status", "to_status", "reason"}
case_status_changed = Signal()

# payload: {"resolution_id", "verification_due_at"}  -> notify the submitter
case_solved = Signal()

# payload: {"resolution_id", "confirmed": bool, "feedback"}
case_resolution_verified = Signal()

# payload: {"reason", "reopen_count", "previous_status"}
case_reopened = Signal()

# payload: {"escalation_id", "level", "deadline_at", "authority_id", "status"}
case_escalated = Signal()

# payload: {"old_deadline", "new_deadline", "reason"}
case_deadline_changed = Signal()

# payload: {"update_id", "kind", "is_internal"}
case_update_added = Signal()

ALL_SIGNALS = {
    "case_submitted": case_submitted,
    "case_assigned": case_assigned,
    "case_status_changed": case_status_changed,
    "case_solved": case_solved,
    "case_resolution_verified": case_resolution_verified,
    "case_reopened": case_reopened,
    "case_escalated": case_escalated,
    "case_deadline_changed": case_deadline_changed,
    "case_update_added": case_update_added,
}
