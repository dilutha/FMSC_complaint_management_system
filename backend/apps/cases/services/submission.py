"""Case submission and administrator classification review."""
from django.db import transaction
from django.utils import timezone

from apps.cases import signals
from apps.cases.models import TERMINAL_STATUSES, Case, CaseStatus, CaseUpdate, Category, Priority, UpdateKind

from . import access
from .attachments import save_attachments
from .deadlines import calculate_deadline, record_deadline
from .events import emit
from .exceptions import NotPermitted, ValidationFailed
from .numbering import next_case_number
from .workflow import write_history


def submit_case(*, actor, title, description, case_type, category: Category, location, requested_priority,
                declaration_accepted, attachments=()):
    """Create a case. Protected fields (status, assignment, timestamps) are set
    here only, never from request data."""
    if not actor.can_submit_cases:
        raise NotPermitted("Your account cannot submit cases.")
    if not category.is_active:
        raise ValidationFailed("This category is no longer available.", details={"category_id": ["Inactive category."]})
    if not declaration_accepted:
        raise ValidationFailed(
            "You must confirm that the information is accurate.",
            details={"declaration_accepted": ["Please confirm the declaration."]},
        )

    with transaction.atomic():
        now = timezone.now()
        case = Case.objects.create(
            case_number=next_case_number(),
            title=title.strip(),
            description=description.strip(),
            case_type=case_type,
            category=category,
            priority=requested_priority,
            requested_priority=requested_priority,
            location=location.strip(),
            submitted_by=actor,
            status=CaseStatus.SUBMITTED,
            declaration_accepted=True,
            deadline_at=calculate_deadline(
                priority=requested_priority, case_type=case_type, category=category, start=now
            ),
        )
        write_history(case, "", CaseStatus.SUBMITTED, actor, "Case submitted.")
        save_attachments(case, list(attachments), actor=actor)
        emit(
            signals.case_submitted,
            case,
            actor,
            case_number=case.case_number,
            case_type=case.case_type,
            priority=case.priority,
            category=category.code,
        )
    return case


def review_classification(case: Case, *, actor, category=None, priority=None, note=""):
    """Administrator confirms or adjusts category/priority during review."""
    if not access.is_case_admin(actor):
        raise NotPermitted("Only administrators can change a case's category or priority.")
    if category is not None and not category.is_active:
        raise ValidationFailed("This category is inactive.", details={"category_id": ["Inactive category."]})

    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)
        if case.status in TERMINAL_STATUSES:
            raise ValidationFailed("Closed or rejected cases cannot be reclassified.")
        changes = []
        if category is not None and category.pk != case.category_id:
            changes.append(f"Category: {case.category.name} → {category.name}")
            case.category = category
        if priority is not None and priority != case.priority:
            changes.append(f"Priority: {case.get_priority_display()} → {Priority(priority).label}")
            case.priority = priority
        if not changes:
            return case
        case.save(update_fields=["category", "priority", "updated_at"])
        body = "; ".join(changes) + (f". Note: {note.strip()}" if note and note.strip() else "")
        update = CaseUpdate.objects.create(case=case, author=actor, kind=UpdateKind.COMMENT, body=body, is_internal=True)
        new_deadline = calculate_deadline(
            priority=case.priority, case_type=case.case_type, category=case.category, start=case.created_at
        )
        if new_deadline != case.deadline_at:
            record_deadline(case, new_deadline, actor=actor, reason="Recalculated after reclassification.")
        emit(signals.case_update_added, case, actor, update_id=update.pk, kind=update.kind, is_internal=True)
    return case
