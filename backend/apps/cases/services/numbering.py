"""Case reference numbers: <PREFIX>-<YEAR>-<5-digit sequence>, e.g. FMSC-2026-00042.

Concurrency-safe: the per-year counter row is locked (SELECT ... FOR UPDATE)
inside the caller's transaction, and Case.case_number is UNIQUE in the
database as the final guarantee.
"""
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.cases.models import CaseNumberSequence


def next_case_number(year=None) -> str:
    year = year or timezone.localdate().year
    prefix = settings.FMSC_CASES["CASE_NUMBER_PREFIX"]
    with transaction.atomic():
        try:
            with transaction.atomic():
                seq, _ = CaseNumberSequence.objects.select_for_update().get_or_create(year=year)
        except IntegrityError:
            # Another transaction created this year's row first; lock it instead.
            seq = CaseNumberSequence.objects.select_for_update().get(year=year)
        seq.last_value += 1
        seq.save(update_fields=["last_value"])
        return f"{prefix}-{year}-{seq.last_value:05d}"
