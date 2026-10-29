"""In-app notifications (Member B). Created by apps.notifications.services.notify()
from case-module signals, suggestion decisions and scheduled reminders."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationEvent(models.TextChoices):
    CASE_SUBMITTED = "case_submitted", "Submission confirmation"
    NEW_CASE = "new_case", "New case for review"
    CASE_ASSIGNED = "case_assigned", "Case assigned"
    STATUS_UPDATE = "status_update", "Status update"
    INFORMATION_REQUESTED = "information_requested", "More information requested"
    CASE_UPDATE = "case_update", "New update on a case"
    DEADLINE_REMINDER = "deadline_reminder", "Deadline reminder"
    ESCALATION = "escalation", "Escalation"
    CASE_SOLVED = "case_solved", "Case solved"
    RESOLUTION_VERIFIED = "resolution_verified", "Resolution verified"
    CASE_REOPENED = "case_reopened", "Case reopened"
    CASE_REJECTED = "case_rejected", "Case rejected"
    SUGGESTION_DECISION = "suggestion_decision", "Suggestion decision"
    SUGGESTION_UPDATE = "suggestion_update", "Suggestion implementation update"


class TargetType(models.TextChoices):
    """What the client should open when the notification is tapped."""

    CASE = "case", "Case"
    SUGGESTION = "suggestion", "Suggestion"


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    event_type = models.CharField(max_length=30, choices=NotificationEvent.choices)
    title = models.CharField(max_length=150)
    body = models.CharField(max_length=500, blank=True)
    case = models.ForeignKey(
        "cases.Case", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications"
    )
    target_type = models.CharField(max_length=20, choices=TargetType.choices, blank=True)
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    dedup_key = models.CharField(max_length=200, help_text="Identifies the source event; unique per recipient.")
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["recipient", "dedup_key"], name="unique_notification_per_event"),
        ]
        indexes = [models.Index(fields=["recipient", "is_read", "-created_at"], name="notification_inbox_idx")]

    def __str__(self):
        return f"{self.recipient_id}: {self.title}"
