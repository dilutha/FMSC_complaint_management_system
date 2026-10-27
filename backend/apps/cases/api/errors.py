"""Uniform error envelope (shared contract with Member B):

    {"error": {"code": "validation_error", "message": "...", "details": {...}}}

Unexpected exceptions are not converted here; Django returns a generic 500
without leaking internals when DEBUG is off.
"""
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.cases.services.exceptions import CaseServiceError

_DRF_CODES = {
    exceptions.ValidationError: "validation_error",
    exceptions.ParseError: "parse_error",
    exceptions.AuthenticationFailed: "authentication_failed",
    exceptions.NotAuthenticated: "not_authenticated",
    exceptions.PermissionDenied: "permission_denied",
    exceptions.NotFound: "not_found",
    exceptions.MethodNotAllowed: "method_not_allowed",
    exceptions.UnsupportedMediaType: "unsupported_media_type",
    exceptions.Throttled: "rate_limited",
}


def _envelope(code, message, details=None, status_code=400, headers=None):
    return Response(
        {"error": {"code": code, "message": message, "details": details or {}}}, status=status_code, headers=headers
    )


def api_exception_handler(exc, context):
    if isinstance(exc, CaseServiceError):
        return _envelope(exc.code, exc.message, exc.details, exc.status_code)
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        return None

    code = next((c for cls, c in _DRF_CODES.items() if isinstance(exc, cls)), "error")
    if isinstance(exc, exceptions.ValidationError):
        details = response.data if isinstance(response.data, dict) else {"non_field_errors": response.data}
        message = "Please correct the highlighted fields."
        if list(details) == ["non_field_errors"] and details["non_field_errors"]:
            message = str(details["non_field_errors"][0])
    else:
        details = {}
        message = str(getattr(exc, "detail", "")) or "Request failed."
    if response.status_code == status.HTTP_404_NOT_FOUND:
        message = "Not found."
    headers = {k: v for k, v in response.items() if k in ("Retry-After", "WWW-Authenticate", "Allow")}
    return _envelope(code, message, details, response.status_code, headers)
