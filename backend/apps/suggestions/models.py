"""Suggestion evaluation and implementation tracking (Member B).

A suggestion is a cases.Case with case_type="suggestion" (Member A owns
submission). This app adds the evaluation record: the decision, its reason,
the responsible unit, the target date and implementation progress. The case
status stays the single source of truth for the workflow; see
docs/SUGGESTIONS.md for how the two map onto each other.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SuggestionStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    UNDER_EVALUATION = "under_evaluation", "Under Evaluation"
    ACCEPTED = "accepted", "Accepted for Implementation"
    PLANNED = "planned", "Planned"
    IMPLEMENTED = "implemented", "Implemented"
    DECLINED = "declined", "Declined"


class ImmutableRecord(models.Model):
    """History rows are written once and never edited or deleted."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError(f"{type(self).__name__} records cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(f"{type(self).__name__} records cannot be deleted.")


class SuggestionEvaluation(models.Model):
    case = models.OneToOneField(
        "cases.Case", on_delete=models.CASCADE, related_name="suggestion_evaluation",
        limit_choices_to={"case_type": "suggestion"},
    )
    status = models.CharField(
        max_length=20, choices=SuggestionStatus.choices, default=SuggestionStatus.SUBMITTED, db_index=True
    )
    responsible_unit = models.ForeignKey(
        "cases.Authority", null=True, blank=True, on_delete=models.PROTECT, related_name="suggestions"
    )
    decision_reason = models.TextField(blank=True, help_text="Reason for the latest decision.")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    plan_note = models.TextField(blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    implementation_summary = models.TextField(blank=True)
    implemented_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(progress_percent__lte=100), name="suggestion_progress_max_100"),
            models.CheckConstraint(
                condition=~Q(status="declined") | ~Q(decision_reason=""), name="suggestion_declined_has_reason"
            ),
        ]

    def __str__(self):
        return f"{self.case.case_number} ({self.get_status_display()})"


class SuggestionStatusChange(ImmutableRecord):
    """Decision history. One row for every change of suggestion status or plan."""

    evaluation = models.ForeignKey(SuggestionEvaluation, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, choices=SuggestionStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=SuggestionStatus.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    reason = models.TextField(blank=True)
    responsible_unit = models.ForeignKey("cases.Authority", null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="+")
    target_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]


class SuggestionProgressUpdate(ImmutableRecord):
    evaluation = models.ForeignKey(SuggestionEvaluation, on_delete=models.CASCADE, related_name="progress_updates")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    note = models.TextField(max_length=2000)
    percent_complete = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]
