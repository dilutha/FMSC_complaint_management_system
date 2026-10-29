"""Seed the categories and authorities named in the approved project proposal.

Deadline policies and routing rules are NOT seeded: their values must be
approved by the faculty and entered by an administrator (Django admin).
Safe to run repeatedly.
"""
from django.core.management.base import BaseCommand

from apps.cases.models import Authority, Category

#: The four resolving departments (canonical codes never change; names are for display).
AUTHORITIES = [
    ("IT Department", "it-unit"),
    ("Maintenance Department", "maintenance"),
    ("Examination Unit", "examination-unit"),
    ("Dean's Office", "deans-office"),
]
#: Earlier default names, renamed once to the current ones. Names edited by an
#: administrator are never overwritten.
LEGACY_NAMES = {"it-unit": "IT Unit", "maintenance": "Maintenance Division"}
CATEGORIES = [
    ("Classroom", "classroom", "maintenance"),
    ("IT", "it", "it-unit"),
    ("Maintenance", "maintenance", "maintenance"),
    ("Examination", "examination", "examination-unit"),
    ("Other", "other", None),
]


class Command(BaseCommand):
    help = "Create proposal-defined categories and authorities if missing."

    def handle(self, *args, **options):
        for name, code in AUTHORITIES:
            authority, created = Authority.objects.get_or_create(code=code, defaults={"name": name})
            if not created and authority.name == LEGACY_NAMES.get(code):
                authority.name = name
                authority.save(update_fields=["name", "updated_at"])
        for order, (name, code, authority_code) in enumerate(CATEGORIES):
            Category.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "sort_order": order,
                    "default_authority": Authority.objects.filter(code=authority_code).first(),
                },
            )
        self.stdout.write(self.style.SUCCESS("Reference data ready."))
