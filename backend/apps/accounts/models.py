"""SHARED CONTRACT — owned by Member B (authentication infrastructure).

This is the minimal user model the case module depends on. It exists so that
AUTH_USER_MODEL is fixed before the first migration (Django cannot swap it
later without a database reset). Member B may extend this model freely as long
as the `role` field values and the helper properties below keep their meaning.
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
