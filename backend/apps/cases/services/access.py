"""Object-level access rules. The API layer must use these, never the UI."""
from django.db.models import Q

from apps.cases.models import Case

ADMIN = "admin"
AUTHORITY = "authority"
SUBMITTER = "submitter"
MANAGEMENT = "management"
SYSTEM = "system"


def is_case_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.is_case_admin)


def is_assigned_member(user, case: Case) -> bool:
    if not (user and user.is_authenticated) or case.assigned_authority_id is None:
        return False
    return case.assigned_authority.members.filter(pk=user.pk, is_active=True).exists() and case.assigned_authority.is_active


def actor_kinds(user, case: Case) -> set:
    """Every capacity in which `user` may act on `case`."""
    if user is None:
        return {SYSTEM}
    kinds = set()
    if is_case_admin(user):
        kinds.add(ADMIN)
    if is_assigned_member(user, case):
        kinds.add(AUTHORITY)
    if case.submitted_by_id == user.pk:
        kinds.add(SUBMITTER)
    if getattr(user, "is_management_viewer", False):
        kinds.add(MANAGEMENT)
    return kinds


def is_staff_for(user, case: Case) -> bool:
    """Staff may see internal notes: admins, management, the assigned authority."""
    return bool(actor_kinds(user, case) & {ADMIN, AUTHORITY, MANAGEMENT})


def visible_cases(user):
    """Queryset of cases `user` may read. Anything else must look like a 404."""
    qs = Case.objects.select_related("category", "assigned_authority", "submitted_by")
    if not (user and user.is_authenticated):
        return qs.none()
    if user.is_case_admin or user.is_management_viewer:
        return qs
    return qs.filter(
        Q(submitted_by=user)
        | Q(assigned_authority__members=user, assigned_authority__is_active=True)
    ).distinct()
