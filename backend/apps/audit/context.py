"""Request context for audit records.

AuditContextMiddleware remembers the current request so code that does not
receive the user explicitly (model signals) can still attribute a change.
The user is read lazily: DRF authenticates inside the view and writes the
authenticated user back onto the underlying Django request.
"""
import re
from contextvars import ContextVar

_current_request = ContextVar("fmsc_audit_request", default=None)

# Attachment downloads are sensitive-record access and are audited.
_ATTACHMENT_DOWNLOAD = re.compile(r"^/api/v1/cases/(?P<case_id>\d+)/attachments/(?P<attachment_id>\d+)/download/$")


def current_actor():
    request = _current_request.get()
    user = getattr(request, "user", None) if request is not None else None
    return user if user is not None and user.is_authenticated else None


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            response = self.get_response(request)
        finally:
            _current_request.reset(token)
        self._audit_sensitive_access(request, response)
        return response

    @staticmethod
    def _audit_sensitive_access(request, response):
        if request.method != "GET" or response.status_code != 200:
            return
        match = _ATTACHMENT_DOWNLOAD.match(request.path)
        if not match:
            return
        from .services import record

        user = getattr(request, "user", None)
        record(
            "case.attachment_downloaded",
            actor=user if user is not None and user.is_authenticated else None,
            entity_type="case",
            entity_id=match["case_id"],
            metadata={"attachment_id": int(match["attachment_id"])},
        )
