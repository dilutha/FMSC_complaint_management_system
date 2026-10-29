from django.core.management.base import BaseCommand

from apps.notifications.reminders import send_deadline_reminders


class Command(BaseCommand):
    help = "Remind responsible units about cases whose deadline is approaching. Idempotent."

    def handle(self, *args, **options):
        sent = send_deadline_reminders()
        self.stdout.write(self.style.SUCCESS(f"Deadline reminders sent: {sent}"))
