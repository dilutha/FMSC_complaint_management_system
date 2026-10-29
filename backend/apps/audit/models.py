"""Shared, append-only audit log (Member B). Every module records administrative
and workflow events here through apps.audit.services.record(); there is no
other audit table.

The case module keeps its own *domain* history (status history, assignments,
deadline changes) as part of the case record. This log answers a different
question: who changed what, across every module.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditImmutableError(Exception):
    """Raised when code tries to modify or delete a recorded audit event."""


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AuditImmutableError("Audit events cannot be modified.")

    def delete(self):
        raise AuditImmutableError("Audit events cannot be deleted.")


class AuditSource(models.TextChoices):
    API = "api", "API request"
    CASE_EVENT = "case_event", "Case workflow event"
    SYSTEM = "system", "Scheduled job"


class AuditEvent(models.Model):
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Empty for system actions.",
    )
    # Snapshots, so the record stays meaningful if the account later changes.
    actor_label = models.CharField(max_length=150, blank=True)
    actor_role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=60, db_index=True, help_text="Dotted name, e.g. case.status_changed.")
    entity_type = models.CharField(max_length=40)
    entity_id = models.CharField(max_length=40)
    entity_label = models.CharField(max_length=200, blank=True)
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=20, choices=AuditSource.choices, default=AuditSource.API)
    dedup_key = models.CharField(
        max_length=200, null=True, blank=True, unique=True,
        help_text="Set for events derived from signals so re-processing cannot create duplicates.",
    )

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "-created_at"], name="audit_entity_idx"),
            models.Index(fields=["actor", "-created_at"], name="audit_actor_idx"),
            models.Index(fields=["action", "-created_at"], name="audit_action_idx"),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.entity_type}#{self.entity_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AuditImmutableError("Audit events cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditImmutableError("Audit events cannot be deleted.")
