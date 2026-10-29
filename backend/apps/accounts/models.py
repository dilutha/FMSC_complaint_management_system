"""SHARED CONTRACT — owned by Member B (authentication and role permissions).

AUTH_USER_MODEL is fixed to this model. The `role` values and the helper
properties used by the case module (`display_name`, `is_case_admin`,
`is_management_viewer`, `is_authority_officer`, `can_submit_cases`) must keep
their meaning; see docs/SHARED_CONTRACTS.md. The `can_*` capability properties
below are the single place where platform permissions are defined; DRF
permission classes in apps.accounts.permissions delegate to them.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    STUDENT = "student", "Student"
    LECTURER = "lecturer", "Lecturer"
    CASE_ADMIN = "case_admin", "Administrator"
    AUTHORITY = "authority", "Relevant Authority"
    MANAGEMENT = "management", "Faculty Management"
    SYSTEM_ADMIN = "system_admin", "System Administrator"


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT, db_index=True)
    department = models.CharField(max_length=120, blank=True)
    contact_number = models.CharField(max_length=30, blank=True)

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    # --- Case-module contract (Member A depends on these) -------------------

    @property
    def is_case_admin(self) -> bool:
        return self.is_superuser or self.role in {Role.CASE_ADMIN, Role.SYSTEM_ADMIN}

    @property
    def is_management_viewer(self) -> bool:
        return self.role == Role.MANAGEMENT

    @property
    def is_authority_officer(self) -> bool:
        return self.role == Role.AUTHORITY

    @property
    def can_submit_cases(self) -> bool:
        return self.is_active

    # --- Platform capabilities (Member B) ------------------------------------

    @property
    def is_system_admin(self) -> bool:
        return self.is_superuser or self.role == Role.SYSTEM_ADMIN

    @property
    def can_view_dashboard(self) -> bool:
        """Management dashboard, reports and authority workload."""
        return self.is_active and (self.is_case_admin or self.is_management_viewer)

    @property
    def can_evaluate_suggestions(self) -> bool:
        """Record suggestion decisions (accept, decline, reconsider)."""
        return self.is_active and self.is_case_admin

    @property
    def can_view_audit_log(self) -> bool:
        return self.is_active and self.is_system_admin

    @property
    def can_manage_users(self) -> bool:
        return self.is_active and self.is_system_admin

    @property
    def can_manage_authorities(self) -> bool:
        return self.is_active and self.is_case_admin

    def capabilities(self) -> list:
        """Capability names sent to the client for navigation hints only.
        Every endpoint re-checks permissions on the server."""
        names = {
            "view_dashboard": self.can_view_dashboard,
            "evaluate_suggestions": self.can_evaluate_suggestions,
            "view_audit_log": self.can_view_audit_log,
            "manage_users": self.can_manage_users,
            "manage_authorities": self.can_manage_authorities,
            "handle_assigned_cases": self.is_active and (self.is_authority_officer or self.is_case_admin),
        }
        return sorted(name for name, allowed in names.items() if allowed)
