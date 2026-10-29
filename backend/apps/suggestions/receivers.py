from apps.cases import signals
from apps.cases.models import CaseType

from . import services


def on_case_submitted(sender, case, actor, payload, **kwargs):
    if case.case_type == CaseType.SUGGESTION:
        services.get_evaluation(case)


def on_case_status_changed(sender, case, actor, payload, **kwargs):
    if case.case_type == CaseType.SUGGESTION:
        services.sync_from_case(case, actor=actor, from_status=payload.get("from_status"),
                                to_status=payload.get("to_status"), reason=payload.get("reason") or "")


def connect():
    signals.case_submitted.connect(on_case_submitted, dispatch_uid="suggestions_case_submitted")
    signals.case_status_changed.connect(on_case_status_changed, dispatch_uid="suggestions_case_status_changed")
