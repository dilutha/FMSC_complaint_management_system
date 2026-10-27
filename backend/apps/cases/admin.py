"""Server-rendered administration (Django admin templates) for reference data
and read-only case inspection. Status, assignment and deadline changes are
deliberately read-only here so every change goes through the validated services
and the API."""
from django.contrib import admin

from .models import (
    AssignmentRule,
    Attachment,
    Authority,
    Case,
    CaseAssignment,
    CaseLink,
    CaseResolution,
    CaseStatusHistory,
    CaseUpdate,
    Category,
    DeadlineChange,
    DeadlinePolicy,
    EscalationEvent,
)


@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "unit", "officer_name", "email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "officer_name", "email")
    prepopulated_fields = {"code": ("name",)}
    filter_horizontal = ("members",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "default_authority", "is_active", "sort_order")
    list_filter = ("is_active",)
    list_editable = ("sort_order", "is_active")
    prepopulated_fields = {"code": ("name",)}


@admin.register(AssignmentRule)
class AssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "location_keyword", "authority", "order", "is_active")
    list_filter = ("is_active", "category", "authority")


@admin.register(DeadlinePolicy)
class DeadlinePolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "priority", "case_type", "category", "resolution_hours", "is_active")
    list_filter = ("priority", "case_type", "is_active")


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class StatusHistoryInline(ReadOnlyInline):
    model = CaseStatusHistory
    fields = ("created_at", "from_status", "to_status", "changed_by", "reason")


class AssignmentInline(ReadOnlyInline):
    model = CaseAssignment
    fk_name = "case"
    fields = ("created_at", "authority", "assigned_by", "recommended_authority", "is_override", "is_current", "internal_note")


class UpdateInline(ReadOnlyInline):
    model = CaseUpdate
    fields = ("created_at", "kind", "author", "is_internal", "body")


class ResolutionInline(ReadOnlyInline):
    model = CaseResolution
    fields = ("resolved_at", "resolved_by", "outcome", "note", "submitter_feedback")


class AttachmentInline(ReadOnlyInline):
    model = Attachment
    fields = ("created_at", "original_name", "content_type", "size", "kind", "uploaded_by")


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("case_number", "title", "case_type", "priority", "status", "assigned_authority", "deadline_at", "created_at")
    list_filter = ("status", "case_type", "priority", "category", "assigned_authority")
    search_fields = ("case_number", "title", "location")
    date_hierarchy = "created_at"
    inlines = [StatusHistoryInline, AssignmentInline, UpdateInline, ResolutionInline, AttachmentInline]
    readonly_fields = [f.name for f in Case._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EscalationEvent)
class EscalationEventAdmin(admin.ModelAdmin):
    list_display = ("case", "level", "deadline_at", "status_at_escalation", "authority", "created_at")
    list_filter = ("level",)
    readonly_fields = [f.name for f in EscalationEvent._meta.fields]


admin.site.register(DeadlineChange)
admin.site.register(CaseLink)
