"""Scheduled deadline processing.

Run every 15 minutes from the server scheduler, e.g. cron:

    */15 * * * * cd /srv/fmsc/backend && .venv/bin/python manage.py process_case_deadlines

or Windows Task Scheduler. The command is idempotent, so overlapping or
repeated runs never create duplicate escalation events.
"""
from django.core.management.base import BaseCommand

from apps.cases.services.deadlines import process_deadlines


class Command(BaseCommand):
    help = "Raise escalations for overdue cases and auto-close expired verifications."

    def handle(self, *args, **options):
        stats = process_deadlines()
        self.stdout.write(
            self.style.SUCCESS(
                f"Escalations created: {stats['escalations_created']}; auto-closed: {stats['auto_closed']}"
            )
        )
