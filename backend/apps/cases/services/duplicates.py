"""Rule-based potential-duplicate detection (no machine learning).

Candidates are cases from the configured recent window (excluding rejected
ones) that share the category or location. Each candidate is scored:

    0.30  same category
    0.25  location similarity (token overlap / containment)
    0.45  text similarity (keyword Jaccard of title+description, blended
          with a character-level title ratio)

Matches at or above FMSC_CASES["DUPLICATE_THRESHOLD"] are shown to staff.
Nothing is rejected, merged or hidden automatically.
"""
import re
from dataclasses import dataclass, field
from datetime import timedelta
from difflib import SequenceMatcher

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.cases.models import Case, CaseLink, CaseStatus, LinkType

from . import access
from .exceptions import NotPermitted, ValidationFailed

STOPWORDS = frozenset(
    """a an and are as at be been but by for from has have in is it its near not of on or the this that to
    was were with there their very please also our we i my me us any some no yes can cannot could would
    should will been being into out over under again more most other such only own same so than too""".split()
)
TOKEN_RE = re.compile(r"[a-z0-9]+")


def keywords(text: str) -> set:
    tokens = TOKEN_RE.findall((text or "").lower())
    return {_stem(t) for t in tokens if len(t) > 2 and t not in STOPWORDS}


def _stem(token: str) -> str:
    # Light suffix stripping so "leaking"/"leaks"/"leak" match.
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def location_similarity(a: str, b: str) -> float:
    na, nb = " ".join(TOKEN_RE.findall(a.lower())), " ".join(TOKEN_RE.findall(b.lower()))
    if not na or not nb:
        return 0.0
    if na == nb or na in nb or nb in na:
        return 1.0
    return jaccard(set(na.split()), set(nb.split()))


@dataclass
class DuplicateMatch:
    case: Case
    score: float
    reasons: list = field(default_factory=list)


def score_pair(case: Case, other: Case) -> DuplicateMatch:
    reasons = []
    score = 0.0
    if case.category_id == other.category_id:
        score += 0.30
        reasons.append("Same category")
    loc = location_similarity(case.location, other.location)
    if loc:
        score += 0.25 * loc
        if loc >= 0.5:
            reasons.append("Similar location")
    kw_a = keywords(f"{case.title} {case.description}")
    kw_b = keywords(f"{other.title} {other.description}")
    text = 0.6 * jaccard(kw_a, kw_b) + 0.4 * SequenceMatcher(None, case.title.lower(), other.title.lower()).ratio()
    score += 0.45 * text
    shared = sorted(kw_a & kw_b)
    if shared:
        reasons.append("Shared keywords: " + ", ".join(shared[:6]))
    return DuplicateMatch(other, round(score, 3), reasons)


def find_potential_duplicates(case: Case, *, limit=5):
    cfg = settings.FMSC_CASES
    window_start = case.created_at - timedelta(days=cfg["DUPLICATE_WINDOW_DAYS"])
    window_end = case.created_at + timedelta(days=cfg["DUPLICATE_WINDOW_DAYS"])
    location_terms = [t for t in TOKEN_RE.findall(case.location.lower()) if len(t) > 2][:5]
    location_q = Q()
    for term in location_terms:
        location_q |= Q(location__icontains=term)

    candidates = (
        Case.objects.exclude(pk=case.pk)
        .exclude(status=CaseStatus.REJECTED)
        .filter(created_at__gte=window_start, created_at__lte=window_end)
        .filter(Q(category_id=case.category_id) | location_q)
        .select_related("category", "assigned_authority")[:200]
    )
    threshold = cfg["DUPLICATE_THRESHOLD"]
    matches = [m for m in (score_pair(case, other) for other in candidates) if m.score >= threshold]
    matches.sort(key=lambda m: (-m.score, -m.case.created_at.timestamp()))
    return matches[:limit]


def linked_cases(case: Case):
    links = CaseLink.objects.filter(Q(from_case=case) | Q(to_case=case)).select_related("from_case", "to_case")
    return [(link, link.to_case if link.from_case_id == case.pk else link.from_case) for link in links]


def link_cases(case: Case, other: Case, *, actor, link_type=LinkType.RELATED, note=""):
    if not access.is_case_admin(actor):
        raise NotPermitted("Only administrators can link cases.")
    if case.pk == other.pk:
        raise ValidationFailed("A case cannot be linked to itself.")
    a, b = sorted([case, other], key=lambda c: c.pk)
    try:
        with transaction.atomic():
            return CaseLink.objects.create(from_case=a, to_case=b, link_type=link_type, note=note.strip(), created_by=actor)
    except IntegrityError:
        raise ValidationFailed("These cases are already linked.", code="already_linked")
