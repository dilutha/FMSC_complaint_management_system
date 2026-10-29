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
    # Group 1: complainers
    STUDENT = "student", "Student"
    LECTURER = "lecturer", "Lecturer"
    NON_ACADEMIC_STAFF = "non_academic_staff", "Non-academic Staff"
    # Group 2: admins (faculty-wide monitoring and messages; no status or assignment changes)
    SYSTEM_ADMIN = "system_admin", "Admin"
    # Group 3: case administrators (review, assignment and the official case workflow)
    CASE_ADMIN = "case_admin", "Case Administrator"
    # Group 4: resolving departments (members of exactly one cases.Authority)
    AUTHORITY = "authority", "Resolving Department"
    # Read-only reporting viewer from the original proposal (kept for compatibility)
    MANAGEMENT = "management", "Faculty Management"


#: Roles that may submit complaints and suggestions.
COMPLAINER_ROLES = frozenset({Role.STUDENT, Role.LECTURER, Role.NON_ACADEMIC_STAFF})


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
        """Case administrators run the official workflow: review, assign, change status.
        Admins (system_admin) monitor only, so they are deliberately not included."""
        return self.is_superuser or self.role == Role.CASE_ADMIN

    @property
    def is_management_viewer(self) -> bool:
        """Faculty-wide read access to every case (admins and faculty management)."""
        return self.role in {Role.MANAGEMENT, Role.SYSTEM_ADMIN}

    @property
    def is_authority_officer(self) -> bool:
        return self.role == Role.AUTHORITY

    @property
    def can_submit_cases(self) -> bool:
        """Only complainers (students, lecturers, non-academic staff) submit cases."""
        return self.is_active and self.role in COMPLAINER_ROLES

    # --- Platform capabilities (Member B) ------------------------------------

    @property
    def is_complainer(self) -> bool:
        return self.role in COMPLAINER_ROLES

    @property
    def is_system_admin(self) -> bool:
        return self.is_superuser or self.role == Role.SYSTEM_ADMIN

    @property
    def can_post_admin_messages(self) -> bool:
        """Admins may add messages to any case without workflow powers."""
        return self.is_active and self.role == Role.SYSTEM_ADMIN

    @property
    def can_view_dashboard(self) -> bool:
        """Faculty-wide dashboard, reports and department workload."""
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
        """Department records are system configuration, managed by admins."""
        return self.is_active and self.is_system_admin

    @property
    def workspace(self) -> str:
        """Which dashboard the app opens after sign-in (from the trusted role, never the client)."""
        if self.is_case_admin:
            return "case_admin"
        if self.role == Role.SYSTEM_ADMIN:
            return "admin"
        if self.role == Role.MANAGEMENT:
            return "management"
        if self.role == Role.AUTHORITY:
            return "department"
        return "complainer"

    def capabilities(self) -> list:
        """Capability names sent to the client for navigation hints only.
        Every endpoint re-checks permissions on the server."""
        names = {
            "view_dashboard": self.can_view_dashboard,
            "evaluate_suggestions": self.can_evaluate_suggestions,
            "view_audit_log": self.can_view_audit_log,
            "manage_users": self.can_manage_users,
            "manage_authorities": self.can_manage_authorities,
            "handle_assigned_cases": self.is_active and self.is_authority_officer,
            "submit_cases": self.can_submit_cases,
            "review_cases": self.is_active and self.is_case_admin,
            "post_admin_messages": self.can_post_admin_messages,
        }
        return sorted(name for name, allowed in names.items() if allowed)
