"""Authority recommendation and administrator-controlled (re)assignment."""
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.cases import signals
from apps.cases.models import AssignmentRule, Authority, Case, CaseAssignment, CaseStatus

from . import access
from .events import emit
from .exceptions import InvalidTransition, NotPermitted, ValidationFailed
from .workflow import ASSIGNABLE_FROM, write_history


@dataclass
class Recommendation:
    authority: Optional[Authority]
    reason: str
    rule_id: Optional[int] = None


def recommend_authority(case: Case) -> Recommendation:
    """Apply approved routing rules. The most specific matching rule wins
    (category + location > category > location); ties go to the lower `order`.
    Falls back to the category's default authority. Never assigns by itself."""
    location = (case.location or "").lower()
    best, best_score = None, -1
    rules = AssignmentRule.objects.filter(is_active=True, authority__is_active=True).select_related("authority")
    for rule in rules:
        if rule.category_id and rule.category_id != case.category_id:
            continue
        keyword = rule.location_keyword.strip().lower()
        if keyword and keyword not in location:
            continue
        score = (2 if rule.category_id else 0) + (1 if keyword else 0)
        if score > best_score:  # rules are pre-ordered, so first wins ties
            best, best_score = rule, score
    if best:
        return Recommendation(best.authority, f"Matched routing rule “{best.name}”.", best.pk)
    default = case.category.default_authority
    if default and default.is_active:
        return Recommendation(default, f"Default authority for category “{case.category.name}”.")
    return Recommendation(None, "No routing rule matches; choose an authority manually.")


def assign_case(case: Case, *, actor, authority: Authority, internal_note: str = "") -> Case:
    if not access.is_case_admin(actor):
        raise NotPermitted("Only administrators can assign cases.")
    if not authority.is_active:
        raise ValidationFailed("This authority is inactive.", details={"authority_id": ["Inactive authority."]})

    with transaction.atomic():
        case = Case.objects.select_for_update(of=("self",)).select_related("category").get(pk=case.pk)
        if case.status not in ASSIGNABLE_FROM:
            raise InvalidTransition(f"A case that is '{CaseStatus(case.status).label}' cannot be assigned.")
        if case.assigned_authority_id == authority.pk and case.status == CaseStatus.ASSIGNED:
            raise ValidationFailed("The case is already assigned to this authority.")

        now = timezone.now()
        previous_authority_id = case.assigned_authority_id
        recommendation = recommend_authority(case)
        CaseAssignment.objects.filter(case=case, is_current=True).update(is_current=False, ended_at=now)
        CaseAssignment.objects.create(
            case=case,
            authority=authority,
            assigned_by=actor,
            recommended_authority=recommendation.authority,
            is_override=bool(recommendation.authority and recommendation.authority.pk != authority.pk),
            internal_note=(internal_note or "").strip(),
            created_at=now,
        )

        from_status = case.status
        case.assigned_authority = authority
        case.status = CaseStatus.ASSIGNED
        case.save(update_fields=["assigned_authority", "status", "updated_at"])
        is_reassignment = previous_authority_id is not None
        write_history(
            case,
            from_status,
            CaseStatus.ASSIGNED,
            actor,
            f"{'Reassigned' if is_reassignment else 'Assigned'} to {authority.name}.",
        )

        emit(
            signals.case_assigned,
            case,
            actor,
            authority_id=authority.pk,
            authority_name=authority.name,
            previous_authority_id=previous_authority_id,
            is_reassignment=is_reassignment,
            is_override=bool(recommendation.authority and recommendation.authority.pk != authority.pk),
            recommended_authority_id=recommendation.authority.pk if recommendation.authority else None,
        )
        if from_status != CaseStatus.ASSIGNED:
            emit(signals.case_status_changed, case, actor, from_status=from_status, to_status=CaseStatus.ASSIGNED, reason="")
    return case
