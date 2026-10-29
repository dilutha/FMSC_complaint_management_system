"""DRF permission classes for platform features. Each delegates to a capability
property on the user model so the rules are defined in one place."""
from rest_framework.permissions import BasePermission


class _Capability(BasePermission):
    capability = ""
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, self.capability, False))


class CanViewDashboard(_Capability):
    capability = "can_view_dashboard"
    message = "The dashboard is available to administrators and faculty management only."


class CanViewAuditLog(_Capability):
    capability = "can_view_audit_log"
    message = "The audit log is available to system administrators only."


class CanManageUsers(_Capability):
    capability = "can_manage_users"
    message = "Only system administrators can manage user accounts."


class CanManageAuthorities(_Capability):
    capability = "can_manage_authorities"
    message = "Only administrators can manage authorities."
