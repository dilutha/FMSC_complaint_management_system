"""Create one demo account per role, for local development and demonstrations.

    python manage.py seed_demo_users

* DEVELOPMENT ONLY. Refuses to run unless DJANGO_DEBUG=true, or
  FMSC_ALLOW_DEMO_USERS=true is set explicitly (e.g. for a staging demo).
* Idempotent: re-running updates the same accounts (role, flags, password,
  unit membership) and never creates duplicates.
* Every account uses the shared demo password below, stored with Django's
  password hasher (never in plain text). Never use it for real accounts.
* Only accounts whose username starts with "demo_" are touched.
"""
import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User
from apps.cases.models import Authority

DEMO_PASSWORD = "Password@123"  # development/demo only; documented in README
DEMO_DOMAIN = "example.com"  # reserved for documentation (RFC 2606)

#: username, role, first name, last name, department text, department code (membership)
DEMO_USERS = [
    # Group 1: complainers
    ("demo_student", Role.STUDENT, "Demo", "Student", "Department of Accounting", None),
    ("demo_lecturer", Role.LECTURER, "Demo", "Lecturer", "Department of Marketing Management", None),
    ("demo_non_academic", Role.NON_ACADEMIC_STAFF, "Demo", "Non-academic Staff", "Faculty Office", None),
    # Group 2: admin (monitoring and messages)
    ("demo_system_admin", Role.SYSTEM_ADMIN, "Demo", "Admin", "Faculty Office", None),
    # Group 3: case administrator
    ("demo_case_admin", Role.CASE_ADMIN, "Demo", "Case Administrator", "Faculty Office", None),
    # Group 4: resolving departments (one department each)
    ("demo_it", Role.AUTHORITY, "Demo", "IT Officer", "IT Department", "it-unit"),
    ("demo_maintenance", Role.AUTHORITY, "Demo", "Maintenance Officer", "Maintenance Department", "maintenance"),
    ("demo_exams", Role.AUTHORITY, "Demo", "Examination Officer", "Examination Unit", "examination-unit"),
    ("demo_deans_office", Role.AUTHORITY, "Demo", "Dean's Office Officer", "Dean's Office", "deans-office"),
    # Read-only reporting viewer from the original proposal
    ("demo_management", Role.MANAGEMENT, "Demo", "Faculty Manager", "Dean's Office", None),
]

#: Earlier demo usernames, renamed in place (never duplicated).
RENAMED = {"demo_it_officer": "demo_it", "demo_authority": "demo_maintenance"}


class Command(BaseCommand):
    help = "Create or update demo users for every role (development only; password Password@123)."

    def add_arguments(self, parser):
        parser.add_argument("--quiet-table", action="store_true", help="Do not print the credentials table.")

    def handle(self, *args, quiet_table=False, **options):
        allowed = settings.DEBUG or os.environ.get("FMSC_ALLOW_DEMO_USERS", "").lower() in ("1", "true", "yes")
        if not allowed:
            raise CommandError(
                "Demo users are for local development only. Set DJANGO_DEBUG=true, or FMSC_ALLOW_DEMO_USERS=true "
                "for an intentional demo environment. Never run this on production."
            )

        call_command("seed_reference_data", stdout=self.stdout)  # authorities and categories (idempotent)
        created, updated = [], []
        with transaction.atomic():
            for old, new in RENAMED.items():
                if not User.objects.filter(username=new).exists():
                    User.objects.filter(username=old).update(username=new)
            for username, role, first, last, department, authority_code in DEMO_USERS:
                user, is_new = User.objects.get_or_create(username=username)
                user.role = role
                user.first_name, user.last_name = first, last
                user.email = f"{username}@{DEMO_DOMAIN}"
                user.department = department
                user.is_active = True
                # No demo account is a Django superuser: a superuser would bypass the
                # separation between admins and case administrators.
                user.is_staff = False
                user.is_superuser = False
                user.set_password(DEMO_PASSWORD)  # hashed with settings.PASSWORD_HASHERS
                user.save()
                memberships = list(Authority.objects.filter(code=authority_code)) if authority_code else []
                user.authorities.set(memberships)
                (created if is_new else updated).append(username)

        self.stdout.write(self.style.SUCCESS(
            f"Demo users ready: {len(created)} created, {len(updated)} updated (no duplicates)."
        ))
        if not quiet_table:
            self.stdout.write(f"All demo accounts use the development-only password: {DEMO_PASSWORD}")
            for username, role, *_rest, authority_code in DEMO_USERS:
                unit = f" (member of {authority_code})" if authority_code else ""
                self.stdout.write(f"  {username:20} {Role(role).label}{unit}")
