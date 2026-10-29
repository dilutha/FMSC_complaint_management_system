"""Role-scoped dashboard overview (GET /api/v1/dashboard/overview/).

Every figure is computed from the cases the caller may see, starting from the
case module's own visibility rule (access.visible_cases) and only narrowing it:

* complainer  - cases the user submitted
* department  - cases currently assigned to the user's department
* case_admin / admin / management - every case in the faculty

So counts can never reveal more than the matching case lists.
"""
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import Role
from apps.cases.models import ACTIVE_STATUSES, Authority, CaseStatus, CaseStatusHistory, CaseType
from apps.cases.services import access

S = CaseStatus
REVIEW_STATUSES = (S.SUBMITTED, S.UNDER_REVIEW, S.REOPENED)
PROCESSING_STATUSES = (S.UNDER_REVIEW, S.WAITING_FOR_INFORMATION, S.ASSIGNED, S.IN_PROGRESS, S.REOPENED)
RESOLVED_STATUSES = (S.SOLVED, S.CLOSED)
GLOBAL_WORKSPACES = ("case_admin", "admin", "management")


def scoped_cases(user):
    workspace = user.workspace
    qs = access.visible_cases(user)
    if workspace == "complainer":
        return workspace, qs.filter(submitted_by=user)
    if workspace == "department":
        return workspace, qs.filter(assigned_authority__members=user, assigned_authority__is_active=True)
    return workspace, qs


def _row(case, now, staff):
    row = {
        "id": case.pk,
        "case_number": case.case_number,
        "title": case.title,
        "case_type": case.case_type,
        "status": case.status,
        "status_label": case.get_status_display(),
        "priority": case.priority,
        "category": case.category.name,
        "assigned_authority": case.assigned_authority.name if case.assigned_authority else None,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "is_overdue": bool(case.deadline_at and case.status in ACTIVE_STATUSES and case.deadline_at < now),
    }
    if staff:
        row["submitter_role_label"] = case.submitted_by.get_role_display()
    return row


def overview(user, now=None) -> dict:
    now = now or timezone.now()
    workspace, qs = scoped_cases(user)
    qs = qs.order_by()  # aggregates do not need ordering
    active = Q(status__in=ACTIVE_STATUSES)
    counts = qs.aggregate(
        total=Count("id", distinct=True),
        complaints=Count("id", filter=Q(case_type=CaseType.COMPLAINT), distinct=True),
        suggestions=Count("id", filter=Q(case_type=CaseType.SUGGESTION), distinct=True),
        open=Count("id", filter=~Q(status__in=(S.CLOSED, S.REJECTED)), distinct=True),
        new=Count("id", filter=Q(status=S.SUBMITTED), distinct=True),
        awaiting_review=Count("id", filter=Q(status__in=REVIEW_STATUSES), distinct=True),
        processing=Count("id", filter=Q(status__in=PROCESSING_STATUSES), distinct=True),
        waiting_for_information=Count("id", filter=Q(status=S.WAITING_FOR_INFORMATION), distinct=True),
        assigned=Count("id", filter=Q(status=S.ASSIGNED), distinct=True),
        in_progress=Count("id", filter=Q(status=S.IN_PROGRESS), distinct=True),
        reopened=Count("id", filter=Q(status=S.REOPENED), distinct=True),
        resolved=Count("id", filter=Q(status__in=RESOLVED_STATUSES), distinct=True),
        rejected=Count("id", filter=Q(status=S.REJECTED), distinct=True),
        overdue=Count("id", filter=active & Q(deadline_at__lt=now), distinct=True),
        unassigned=Count("id", filter=active & Q(assigned_authority__isnull=True), distinct=True),
        needs_reassignment=Count("id", filter=active & (
            Q(status=S.REOPENED) | Q(assigned_authority__isnull=False, assigned_authority__is_active=False)
        ), distinct=True),
        pending_suggestions=Count("id", filter=Q(case_type=CaseType.SUGGESTION, status__in=REVIEW_STATUSES + (
            S.WAITING_FOR_INFORMATION,)), distinct=True),
        awaiting_action=Count("id", filter=Q(status__in=(S.ASSIGNED, S.REOPENED)), distinct=True),
    )

    staff = workspace != "complainer"
    base = qs.select_related("category", "assigned_authority", "submitted_by")
    if workspace == "case_admin":
        # Review queue: urgent first, then oldest first.
        # "urgent" sorts after "normal" alphabetically, so descending puts urgent first.
        recent_qs = base.filter(status__in=REVIEW_STATUSES).order_by("-priority", "created_at", "id")
    else:
        recent_qs = base.order_by("-updated_at", "-id")
    result = {
        "workspace": workspace,
        "role": user.role,
        "role_label": user.get_role_display(),
        "generated_at": now.isoformat(),
        "counts": counts,
        "recent": [_row(c, now, staff) for c in recent_qs[:8]],
    }

    if workspace == "department":
        result["department"] = [
            {"id": a.pk, "name": a.name} for a in user.authorities.filter(is_active=True).order_by("name")
        ]

    if workspace in GLOBAL_WORKSPACES:
        by_status = dict(qs.values_list("status").annotate(n=Count("id")).order_by())
        result["by_status"] = [{"value": v, "label": label, "count": by_status.get(v, 0)} for v, label in S.choices]
        per_department = {
            row["assigned_authority_id"]: row
            for row in qs.filter(assigned_authority__isnull=False).values("assigned_authority_id").annotate(
                total=Count("id"),
                active=Count("id", filter=active),
                overdue=Count("id", filter=active & Q(deadline_at__lt=now)),
                resolved=Count("id", filter=Q(status__in=RESOLVED_STATUSES)),
            ).order_by()
        }
        result["by_department"] = [
            {"id": a.pk, "name": a.name, "is_active": a.is_active,
             **{k: per_department.get(a.pk, {}).get(k, 0) for k in ("total", "active", "overdue", "resolved")}}
            for a in Authority.objects.filter(Q(is_active=True) | Q(pk__in=per_department.keys())).order_by("name")
        ]
        activity = (
            CaseStatusHistory.objects.filter(case__in=qs.values("pk"))
            .select_related("case", "changed_by", "actor_authority").order_by("-created_at", "-id")[:10]
        )
        result["recent_activity"] = [
            {
                "case_id": h.case_id,
                "case_number": h.case.case_number,
                "title": h.case.title,
                "to_status": h.to_status,
                "to_status_label": S(h.to_status).label,
                "actor": (h.actor_authority.name if h.actor_authority else
                          (Role(h.actor_role).label if h.actor_role in Role.values else
                           (h.changed_by.display_name if h.changed_by else "System"))),
                "message": h.reason,
                "at": h.created_at.isoformat(),
            }
            for h in activity
        ]
    return result
