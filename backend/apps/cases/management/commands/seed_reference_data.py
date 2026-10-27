"""Seed the categories and authorities named in the approved project proposal.

Deadline policies and routing rules are NOT seeded: their values must be
approved by the faculty and entered by an administrator (Django admin).
Safe to run repeatedly.
"""
from django.core.management.base import BaseCommand

from apps.cases.models import Authority, Category

AUTHORITIES = [
    ("Maintenance Division", "maintenance"),
    ("IT Unit", "it-unit"),
    ("Dean's Office", "deans-office"),
    ("Department Office", "department-office"),
    ("Examination Unit", "examination-unit"),
]
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
            Authority.objects.get_or_create(code=code, defaults={"name": name})
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
