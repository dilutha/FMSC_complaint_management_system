"""Case-management domain models (Member A).

Business rules live in apps.cases.services; models only describe data,
relationships, constraints and cheap derived properties.
"""
import uuid

from django.conf import settings
from django.core.files.storage import storages
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class CaseType(models.TextChoices):
    COMPLAINT = "complaint", "Complaint"
    SUGGESTION = "suggestion", "Suggestion"


class Priority(models.TextChoices):
    URGENT = "urgent", "Urgent"
    NORMAL = "normal", "Normal"


class CaseStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under Review"
    WAITING_FOR_INFORMATION = "waiting_for_information", "Waiting for Information"
    ASSIGNED = "assigned", "Assigned"
    IN_PROGRESS = "in_progress", "In Progress"
    SOLVED = "solved", "Solved – Awaiting Verification"
    CLOSED = "closed", "Closed"
    REJECTED = "rejected", "Rejected"
    REOPENED = "reopened", "Reopened"


#: Statuses in which work is still expected; deadlines and escalation apply.
ACTIVE_STATUSES = frozenset(
    {
        CaseStatus.SUBMITTED,
        CaseStatus.UNDER_REVIEW,
        CaseStatus.WAITING_FOR_INFORMATION,
        CaseStatus.ASSIGNED,
        CaseStatus.IN_PROGRESS,
        CaseStatus.REOPENED,
    }
)
TERMINAL_STATUSES = frozenset({CaseStatus.CLOSED, CaseStatus.REJECTED})


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# --- Reference data -----------------------------------------------------------


class Authority(TimeStampedModel):
    """A responsible unit (Maintenance Division, IT Unit, Dean's Office ...)."""

    name = models.CharField(max_length=150, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    unit = models.CharField(max_length=150, blank=True, help_text="Faculty division or department.")
    officer_name = models.CharField(max_length=150, blank=True)
    designation = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="authorities",
        help_text="Users who may act on cases assigned to this authority.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "authorities"

    def __str__(self):
        return self.name


class Category(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    description = models.CharField(max_length=255, blank=True)
    default_authority = models.ForeignKey(
        Authority, null=True, blank=True, on_delete=models.SET_NULL, related_name="default_for_categories"
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class AssignmentRule(TimeStampedModel):
    """Approved routing rule used to *recommend* an authority. Never auto-assigns."""

    name = models.CharField(max_length=150)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE, related_name="rules")
    location_keyword = models.CharField(
        max_length=100, blank=True, help_text="Case-insensitive text that must appear in the case location."
    )
    authority = models.ForeignKey(Authority, on_delete=models.CASCADE, related_name="rules")
    order = models.PositiveSmallIntegerField(default=100, help_text="Lower values are evaluated first.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(category__isnull=False) | ~Q(location_keyword=""),
                name="assignment_rule_has_condition",
            )
        ]

    def __str__(self):
        return self.name


class DeadlinePolicy(TimeStampedModel):
    """Configurable resolution target. The most specific active match wins:
    category + type + priority > type + priority > priority only."""

    name = models.CharField(max_length=150)
    priority = models.CharField(max_length=10, choices=Priority.choices)
    case_type = models.CharField(max_length=12, choices=CaseType.choices, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE, related_name="deadline_policies")
    resolution_hours = models.PositiveIntegerField(help_text="Hours from submission (or reopening) to the deadline.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name_plural = "deadline policies"
        constraints = [
            models.CheckConstraint(condition=Q(resolution_hours__gt=0), name="deadline_policy_positive_hours"),
        ]

    def __str__(self):
        return self.name


class CaseNumberSequence(models.Model):
    """Per-year counter. Rows are locked with SELECT ... FOR UPDATE when issuing numbers."""

    year = models.PositiveSmallIntegerField(primary_key=True)
    last_value = models.PositiveIntegerField(default=0)


# --- Cases --------------------------------------------------------------------


class CaseQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=ACTIVE_STATUSES)

    def overdue(self, now=None):
        now = now or timezone.now()
        return self.active().filter(deadline_at__isnull=False, deadline_at__lt=now)


class Case(TimeStampedModel):
    case_number = models.CharField(max_length=30, unique=True, editable=False)
    title = models.CharField(max_length=150)
    description = models.TextField(max_length=5000)
    case_type = models.CharField(max_length=12, choices=CaseType.choices, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="cases")
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL, db_index=True)
    requested_priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL, help_text="Priority requested by the submitter."
    )
    location = models.CharField(max_length=200)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_cases")
    assigned_authority = models.ForeignKey(
        Authority, null=True, blank=True, on_delete=models.PROTECT, related_name="cases"
    )
    status = models.CharField(max_length=30, choices=CaseStatus.choices, default=CaseStatus.SUBMITTED, db_index=True)

    deadline_at = models.DateTimeField(null=True, blank=True, db_index=True)
    solved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    verification_due_at = models.DateTimeField(null=True, blank=True)
    reopen_count = models.PositiveSmallIntegerField(default=0)
    declaration_accepted = models.BooleanField(default=False)

    objects = CaseQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "deadline_at"], name="case_status_deadline_idx"),
            models.Index(fields=["assigned_authority", "status"], name="case_authority_status_idx"),
            models.Index(fields=["submitted_by", "-created_at"], name="case_submitter_created_idx"),
            models.Index(fields=["category", "-created_at"], name="case_category_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(closed_at__isnull=True) | Q(status__in=[CaseStatus.CLOSED, CaseStatus.REJECTED]),
                name="case_closed_at_only_when_terminal",
            ),
        ]

    def __str__(self):
        return f"{self.case_number} — {self.title}"

    @property
    def is_overdue(self) -> bool:
        return bool(self.deadline_at and self.status in ACTIVE_STATUSES and self.deadline_at < timezone.now())

    @property
    def age_days(self) -> int:
        return (timezone.now() - self.created_at).days if self.created_at else 0


class CaseStatusHistory(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=30, choices=CaseStatus.choices, blank=True)
    to_status = models.CharField(max_length=30, choices=CaseStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, help_text="Empty for system actions."
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name_plural = "case status history"


class CaseAssignment(models.Model):
    """Assignment history. Exactly one row per case is current."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="assignments")
    authority = models.ForeignKey(Authority, on_delete=models.PROTECT, related_name="assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    recommended_authority = models.ForeignKey(
        Authority, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    is_override = models.BooleanField(default=False, help_text="Admin chose a different authority from the recommendation.")
    internal_note = models.TextField(blank=True)
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["case"], condition=Q(is_current=True), name="one_current_assignment_per_case"
            )
        ]


class UpdateKind(models.TextChoices):
    COMMENT = "comment", "Comment"
    PROGRESS = "progress", "Progress update"
    INFORMATION_REQUEST = "information_request", "Information requested"
    INFORMATION_RESPONSE = "information_response", "Information provided"
    RESOLUTION = "resolution", "Resolution note"
    VERIFICATION = "verification", "Resolution verification"


class CaseUpdate(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="updates")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=30, choices=UpdateKind.choices, default=UpdateKind.COMMENT)
    body = models.TextField(max_length=5000)
    is_internal = models.BooleanField(default=False, help_text="Visible to staff only, never to the submitter.")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]


class ResolutionOutcome(models.TextChoices):
    PENDING = "pending", "Awaiting verification"
    CONFIRMED = "confirmed", "Confirmed by submitter"
    DISPUTED = "disputed", "Submitter reported problem persists"
    AUTO_CLOSED = "auto_closed", "Closed after verification window"
    CLOSED_BY_ADMIN = "closed_by_admin", "Closed by administrator"
    SUPERSEDED = "superseded", "Reopened by staff"


class CaseResolution(models.Model):
    """One row each time a case is marked solved; never overwritten on reopen."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="resolutions")
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    note = models.TextField(max_length=5000)
    resolved_at = models.DateTimeField(default=timezone.now)
    outcome = models.CharField(max_length=20, choices=ResolutionOutcome.choices, default=ResolutionOutcome.PENDING)
    submitter_feedback = models.TextField(blank=True)
    outcome_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["resolved_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["case"], condition=Q(outcome="pending"), name="one_pending_resolution_per_case"
            )
        ]


class DeadlineChange(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="deadline_changes")
    old_deadline = models.DateTimeField(null=True, blank=True)
    new_deadline = models.DateTimeField(null=True, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]


class EscalationEvent(models.Model):
    """Raised by the scheduled deadline processor. The unique constraint makes
    escalation idempotent: one event per (case, level, deadline)."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="escalations")
    level = models.PositiveSmallIntegerField()
    deadline_at = models.DateTimeField(help_text="The deadline that was missed.")
    status_at_escalation = models.CharField(max_length=30, choices=CaseStatus.choices)
    authority = models.ForeignKey(Authority, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["case", "level", "deadline_at"], name="unique_escalation_per_deadline"),
            models.CheckConstraint(condition=Q(level__gte=1), name="escalation_level_positive"),
        ]


class LinkType(models.TextChoices):
    POSSIBLE_DUPLICATE = "possible_duplicate", "Possible duplicate"
    DUPLICATE = "duplicate", "Duplicate"
    RELATED = "related", "Related"


class CaseLink(models.Model):
    """Links related submissions without merging or deleting either case.
    Stored once per unordered pair (from_case.id < to_case.id)."""

    from_case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="links_from")
    to_case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="links_to")
    link_type = models.CharField(max_length=20, choices=LinkType.choices, default=LinkType.RELATED)
    note = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_case", "to_case"], name="unique_case_link_pair"),
            models.CheckConstraint(condition=Q(from_case__lt=F("to_case")), name="case_link_ordered_pair"),
        ]


def private_storage():
    """Storage for attachments. Configured in settings.STORAGES['private'];
    it has no public base URL, so files are reachable only via the API."""
    return storages["private"]


def _attachment_path(instance, filename):
    # Random, non-guessable storage names; the original name is kept in the DB only.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"cases/{instance.case_id}/{uuid.uuid4().hex}.{ext}"


class AttachmentKind(models.TextChoices):
    EVIDENCE = "evidence", "Evidence"
    COMPLETION = "completion", "Completion evidence"


class Attachment(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="attachments")
    update = models.ForeignKey(CaseUpdate, null=True, blank=True, on_delete=models.SET_NULL, related_name="attachments")
    file = models.FileField(upload_to=_attachment_path, storage=private_storage, max_length=255)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=12, choices=AttachmentKind.choices, default=AttachmentKind.EVIDENCE)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]

    @property
    def is_image(self):
        return self.content_type.startswith("image/")
