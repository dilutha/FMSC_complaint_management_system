class CaseServiceError(Exception):
    """Base for business-rule violations. Mapped to HTTP 400/403/409 by the API."""

    code = "case_rule_violation"
    status_code = 400

    def __init__(self, message, *, code=None, details=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}


class InvalidTransition(CaseServiceError):
    code = "invalid_transition"
    status_code = 409


class NotPermitted(CaseServiceError):
    code = "permission_denied"
    status_code = 403


class ValidationFailed(CaseServiceError):
    code = "validation_error"
    status_code = 400
