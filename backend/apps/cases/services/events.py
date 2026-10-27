import logging

from django.db import transaction

logger = logging.getLogger("apps.cases.events")


def emit(signal, case, actor=None, **payload):
    """Send an integration signal once the current transaction commits.

    Receiver failures are logged rather than raised: a notification outage must
    not make a committed case change look like it failed to the user.
    """
    from apps.cases.models import Case

    case_id = case.pk

    def _send():
        fresh = Case.objects.get(pk=case_id)
        for receiver, result in signal.send_robust(sender=Case, case=fresh, actor=actor, payload=payload):
            if isinstance(result, Exception):
                logger.error("Case event receiver %r failed for case %s: %r", receiver, case_id, result)

    transaction.on_commit(_send)
