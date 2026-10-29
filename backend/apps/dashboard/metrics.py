"""Management dashboard and report calculations.

Every metric is defined once here and documented in docs/DASHBOARD_METRICS.md.
Counts are computed with database aggregation; medians are computed in Python
from per-case durations fetched in a single query.

Cohort rule: the date range selects cases by *submission date*. Every count
describes that cohort as it stands now (for example, "open" means a case
submitted in the range that is not yet closed or rejected). The trends series
is the exception: there, the range selects *events* (submissions, solutions and
closures) by the date they happened.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean, median

from django.db.models import Count, Exists, Min, OuterRef, Q, Subquery
from django.db.models.functions import Lower, Trim, Trunc
from django.utils import timezone

from apps.cases.models import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    Authority,
    Case,
    CaseLink,
    CaseResolution,
    CaseStatus,
    CaseStatusHistory,
    CaseType,
    LinkType,
    Priority,
)
from apps.suggestions.models import SuggestionEvaluation, SuggestionStatus

S = CaseStatus
RESOLVED_STATUSES = (S.SOLVED, S.CLOSED)
REPEAT_LINK_TYPES = (LinkType.DUPLICATE, LinkType.RELATED)
AGE_BUCKETS = ((0, 2, "0–2 days"), (3, 7, "3–7 days"), (8, 14, "8–14 days"), (15, 30, "15–30 days"),
               (31, None, "More than 30 days"))
WORKLOAD_NOTE = (
    "Workload counts show how many cases each unit currently holds. Volume depends on the kind of issues "
    "a unit handles and is not, on its own, a measure of the unit's performance."
)


@dataclass
class DashboardFilters:
    date_from: date | None = None
    date_to: date | None = None
    category: int | None = None
    priority: str | None = None
    case_type: str | None = None
    statuses: list = field(default_factory=list)
    authority: int | None = None
    location: str = ""

    def as_dict(self):
        return {
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "category": self.category,
            "priority": self.priority,
            "case_type": self.case_type,
            "status": self.statuses,
            "authority": self.authority,
            "location": self.location,
        }


def apply_filters(qs, f: DashboardFilters, *, dates=True):
    if dates and f.date_from:
        qs = qs.filter(created_at__date__gte=f.date_from)
    if dates and f.date_to:
        qs = qs.filter(created_at__date__lte=f.date_to)
    if f.category:
        qs = qs.filter(category_id=f.category)
    if f.priority:
        qs = qs.filter(priority=f.priority)
    if f.case_type:
        qs = qs.filter(case_type=f.case_type)
    if f.statuses:
        qs = qs.filter(status__in=f.statuses)
    if f.authority:
        qs = qs.filter(assigned_authority_id=f.authority)
    if f.location:
        qs = qs.filter(location__icontains=f.location)
    return qs


def cohort(f: DashboardFilters):
    return apply_filters(Case.objects.all(), f)


def _rate(numerator, denominator):
    return {
        "value": round(numerator * 100 / denominator, 1) if denominator else None,
        "numerator": numerator,
        "denominator": denominator,
    }


def _duration_stats(durations, unit_seconds):
    values = [d.total_seconds() / unit_seconds for d in durations if d is not None and d.total_seconds() >= 0]
    return {
        "median": round(median(values), 1) if values else None,
        "average": round(mean(values), 1) if values else None,
        "sample_size": len(values),
    }


def first_response_subquery():
    """When an administrator first moved the case out of `submitted`."""
    return Subquery(
        CaseStatusHistory.objects.filter(case=OuterRef("pk"), from_status=S.SUBMITTED)
        .order_by("created_at", "id")
        .values("created_at")[:1]
    )


def summary(f: DashboardFilters, now=None) -> dict:
    now = now or timezone.now()
    qs = cohort(f)
    active = Q(status__in=ACTIVE_STATUSES)
    totals = qs.aggregate(
        total=Count("id"),
        complaints=Count("id", filter=Q(case_type=CaseType.COMPLAINT)),
        suggestions=Count("id", filter=Q(case_type=CaseType.SUGGESTION)),
        open=Count("id", filter=~Q(status__in=TERMINAL_STATUSES)),
        active=Count("id", filter=active),
        not_attempted=Count("id", filter=Q(status=S.SUBMITTED)),
        not_started=Count("id", filter=Q(status=S.ASSIGNED)),
        awaiting_verification=Count("id", filter=Q(status=S.SOLVED)),
        closed=Count("id", filter=Q(status=S.CLOSED)),
        rejected=Count("id", filter=Q(status=S.REJECTED)),
        urgent=Count("id", filter=Q(priority=Priority.URGENT)),
        normal=Count("id", filter=Q(priority=Priority.NORMAL)),
        overdue=Count("id", filter=active & Q(deadline_at__lt=now)),
        ever_solved=Count("id", filter=Q(solved_at__isnull=False)),
        reopened=Count("id", filter=Q(reopen_count__gt=0)),
        resolved=Count("id", filter=Q(status__in=RESOLVED_STATUSES)),
        repeat=Count("id", filter=Q(Exists(
            CaseLink.objects.filter(to_case=OuterRef("pk"), link_type__in=REPEAT_LINK_TYPES)
        ))),
        # Per-choice counts in the same query (each query costs a network round trip).
        **{f"status__{v}": Count("id", filter=Q(status=v)) for v in CaseStatus.values},
        **{f"case_type__{v}": Count("id", filter=Q(case_type=v)) for v in CaseType.values},
    )
    totals["attempted"] = totals["total"] - totals["not_attempted"]
    repeat = totals["repeat"]

    # One query for both durations (first response and resolution).
    response_durations, resolution_durations = [], []
    for row in qs.annotate(first_action_at=first_response_subquery()).values(
        "created_at", "first_action_at", "solved_at", "status"
    ):
        if row["first_action_at"] is not None:
            response_durations.append(row["first_action_at"] - row["created_at"])
        if row["status"] in RESOLVED_STATUSES and row["solved_at"] is not None:
            resolution_durations.append(row["solved_at"] - row["created_at"])

    return {
        "filters": f.as_dict(),
        "generated_at": now.isoformat(),
        "totals": {k: totals[k] for k in (
            "total", "complaints", "suggestions", "open", "attempted", "not_attempted", "not_started",
            "awaiting_verification", "closed", "rejected", "urgent", "normal", "overdue",
        )},
        "rates": {
            "overdue": _rate(totals["overdue"], totals["active"]),
            "resolution": _rate(totals["resolved"], totals["total"] - totals["rejected"]),
            "reopening": _rate(totals["reopened"], totals["ever_solved"]),
            "repeat_issue": _rate(repeat, totals["total"]),
        },
        "timings": {
            "first_response_hours": _duration_stats(response_durations, 3600),
            "resolution_days": _duration_stats(resolution_durations, 86400),
        },
        "by_status": _from_totals(totals, "status", CaseStatus),
        "by_priority": [{"value": Priority.URGENT, "label": Priority.URGENT.label, "count": totals["urgent"]},
                        {"value": Priority.NORMAL, "label": Priority.NORMAL.label, "count": totals["normal"]}],
        "by_case_type": _from_totals(totals, "case_type", CaseType),
        "by_category": [
            {"id": row["category_id"], "label": row["category__name"], "count": row["count"]}
            for row in qs.values("category_id", "category__name").annotate(count=Count("id")).order_by("-count", "category__name")
        ],
        "by_location": [
            {"label": row["label"], "count": row["count"]}
            for row in qs.annotate(key=Lower(Trim("location"))).values("key")
            .annotate(count=Count("id"), label=Min("location")).order_by("-count", "key")[:10]
        ],
        "suggestions": suggestion_summary(qs),
    }


def _from_totals(totals, field_name, choices):
    return [{"value": v, "label": label, "count": totals[f"{field_name}__{v}"]} for v, label in choices.choices]


def suggestion_summary(case_qs) -> dict:
    counts = dict(
        SuggestionEvaluation.objects.filter(case__in=case_qs.filter(case_type=CaseType.SUGGESTION))
        .values_list("status").annotate(count=Count("id")).order_by()
    )
    accepted_ever = sum(counts.get(s, 0) for s in (SuggestionStatus.ACCEPTED, SuggestionStatus.PLANNED,
                                                    SuggestionStatus.IMPLEMENTED))
    decided = accepted_ever + counts.get(SuggestionStatus.DECLINED, 0)
    return {
        "by_status": [{"value": v, "label": label, "count": counts.get(v, 0)} for v, label in SuggestionStatus.choices],
        "acceptance_rate": _rate(accepted_ever, decided),
        "implementation_rate": _rate(counts.get(SuggestionStatus.IMPLEMENTED, 0), accepted_ever),
    }


def workload(f: DashboardFilters, now=None) -> dict:
    """Current workload per responsible unit, for cases in the cohort."""
    now = now or timezone.now()
    qs = cohort(f).filter(assigned_authority__isnull=False)
    active = Q(status__in=ACTIVE_STATUSES)
    rows = {
        row["assigned_authority_id"]: row
        for row in qs.values("assigned_authority_id").annotate(
            active=Count("id", filter=active),
            not_started=Count("id", filter=Q(status=S.ASSIGNED)),
            in_progress=Count("id", filter=Q(status=S.IN_PROGRESS)),
            waiting_for_information=Count("id", filter=Q(status=S.WAITING_FOR_INFORMATION)),
            reopened=Count("id", filter=Q(status=S.REOPENED)),
            awaiting_verification=Count("id", filter=Q(status=S.SOLVED)),
            resolved=Count("id", filter=Q(status__in=RESOLVED_STATUSES)),
            overdue=Count("id", filter=active & Q(deadline_at__lt=now)),
        ).order_by()
    }
    ages, resolution = {}, {}
    for authority_id, created_at in qs.filter(active).values_list("assigned_authority_id", "created_at"):
        ages.setdefault(authority_id, []).append(now - created_at)
    for authority_id, created_at, solved_at in qs.filter(status__in=RESOLVED_STATUSES, solved_at__isnull=False) \
            .values_list("assigned_authority_id", "created_at", "solved_at"):
        resolution.setdefault(authority_id, []).append(solved_at - created_at)

    authorities = Authority.objects.filter(Q(is_active=True) | Q(pk__in=rows.keys()))
    if f.authority:
        authorities = authorities.filter(pk=f.authority)
    empty = {k: 0 for k in ("active", "not_started", "in_progress", "waiting_for_information", "reopened",
                            "awaiting_verification", "resolved", "overdue")}
    result = []
    for authority in authorities.order_by("name"):
        counts = {k: rows.get(authority.pk, empty)[k] for k in empty}
        result.append({
            "authority": {"id": authority.pk, "name": authority.name, "is_active": authority.is_active},
            **counts,
            "average_open_age_days": _duration_stats(ages.get(authority.pk, []), 86400)["average"],
            "median_resolution_days": _duration_stats(resolution.get(authority.pk, []), 86400)["median"],
        })
    result.sort(key=lambda r: (-r["active"], r["authority"]["name"]))
    return {"filters": f.as_dict(), "generated_at": now.isoformat(), "note": WORKLOAD_NOTE, "results": result}


def ageing(f: DashboardFilters, *, scope="not_started", limit=50, now=None) -> dict:
    """Age in days of not-started (status `assigned`) or all open cases."""
    now = now or timezone.now()
    qs = cohort(f)
    qs = qs.filter(status=S.ASSIGNED) if scope == "not_started" else qs.exclude(status__in=TERMINAL_STATUSES)
    qs = qs.select_related("category", "assigned_authority").order_by("created_at", "id")
    ages = [(now - created).days for created in qs.values_list("created_at", flat=True)]
    buckets = [
        {"label": label, "min_days": lo, "max_days": hi,
         "count": sum(1 for a in ages if a >= lo and (hi is None or a <= hi))}
        for lo, hi, label in AGE_BUCKETS
    ]
    oldest = [
        {
            "id": case.pk,
            "case_number": case.case_number,
            "title": case.title,
            "case_type": case.case_type,
            "status": case.status,
            "status_label": case.get_status_display(),
            "priority": case.priority,
            "category": case.category.name,
            "authority": case.assigned_authority.name if case.assigned_authority else None,
            "created_at": case.created_at.isoformat(),
            "age_days": (now - case.created_at).days,
            "is_overdue": bool(case.deadline_at and case.status in ACTIVE_STATUSES and case.deadline_at < now),
        }
        for case in qs[:limit]
    ]
    return {
        "filters": f.as_dict(), "generated_at": now.isoformat(), "scope": scope, "count": len(ages),
        "average_age_days": round(mean(ages), 1) if ages else None, "buckets": buckets, "oldest": oldest,
    }


INTERVALS = ("day", "week", "month")


def default_interval(f: DashboardFilters) -> str:
    if f.date_from and f.date_to and (f.date_to - f.date_from).days <= 31:
        return "day"
    if f.date_from and (f.date_to or timezone.localdate()) - f.date_from <= timedelta(days=180):
        return "week"
    return "month"


def trends(f: DashboardFilters, interval=None, now=None) -> dict:
    """Submissions, solutions and closures per period. The date range filters
    each series by the date of that event."""
    now = now or timezone.now()
    interval = interval if interval in INTERVALS else default_interval(f)
    base = apply_filters(Case.objects.all(), f, dates=False)

    def _series(qs, field_name):
        if f.date_from:
            qs = qs.filter(**{f"{field_name}__date__gte": f.date_from})
        if f.date_to:
            qs = qs.filter(**{f"{field_name}__date__lte": f.date_to})
        rows = qs.annotate(period=Trunc(field_name, interval)).values("period").annotate(count=Count("id")).order_by()
        return {timezone.localtime(r["period"]).date() if hasattr(r["period"], "tzinfo") else r["period"]: r["count"]
                for r in rows}

    submitted = _series(base, "created_at")
    solved = _series(CaseResolution.objects.filter(case__in=base), "resolved_at")
    closed = _series(base.filter(status=S.CLOSED), "closed_at")
    periods = sorted(set(submitted) | set(solved) | set(closed))
    if periods:
        periods = _fill_periods(periods[0], periods[-1], interval)
    return {
        "filters": f.as_dict(),
        "generated_at": now.isoformat(),
        "interval": interval,
        "series": [
            {"period": p.isoformat(), "submitted": submitted.get(p, 0), "solved": solved.get(p, 0),
             "closed": closed.get(p, 0)}
            for p in periods
        ],
    }


def _fill_periods(start: date, end: date, interval: str) -> list:
    result, current = [], start
    while current <= end:
        result.append(current)
        if interval == "day":
            current += timedelta(days=1)
        elif interval == "week":
            current += timedelta(weeks=1)
        else:
            current = date(current.year + current.month // 12, current.month % 12 + 1, 1)
    return result


def report_queryset(f: DashboardFilters):
    return (
        cohort(f)
        .select_related("category", "assigned_authority")
        .annotate(first_response_at=first_response_subquery())
        .order_by("-created_at", "-id")
    )


REPORT_COLUMNS = [
    ("case_number", "Case number"), ("title", "Title"), ("case_type", "Type"), ("category", "Category"),
    ("priority", "Priority"), ("status", "Status"), ("location", "Location"), ("authority", "Responsible unit"),
    ("created_at", "Submitted"), ("first_response_at", "First response"), ("deadline_at", "Deadline"),
    ("solved_at", "Solved"), ("closed_at", "Closed"), ("age_days", "Age (days)"), ("is_overdue", "Overdue"),
    ("reopen_count", "Times reopened"),
]


def report_row(case, now=None) -> dict:
    now = now or timezone.now()

    def _iso(value):
        return timezone.localtime(value).isoformat(timespec="minutes") if value else None

    return {
        "id": case.pk,
        "case_number": case.case_number,
        "title": case.title,
        "case_type": case.case_type,
        "category": case.category.name,
        "priority": case.priority,
        "status": case.status,
        "status_label": case.get_status_display(),
        "location": case.location,
        "authority": case.assigned_authority.name if case.assigned_authority else None,
        "created_at": _iso(case.created_at),
        "first_response_at": _iso(case.first_response_at),
        "deadline_at": _iso(case.deadline_at),
        "solved_at": _iso(case.solved_at),
        "closed_at": _iso(case.closed_at),
        "age_days": (now - case.created_at).days,
        "is_overdue": bool(case.deadline_at and case.status in ACTIVE_STATUSES and case.deadline_at < now),
        "reopen_count": case.reopen_count,
    }

