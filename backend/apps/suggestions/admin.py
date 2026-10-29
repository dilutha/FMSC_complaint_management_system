"""Read-only inspection. Decisions are made through the API so the case
workflow, history, audit and notifications always stay consistent."""
from django.contrib import admin

from .models import SuggestionEvaluation, SuggestionProgressUpdate, SuggestionStatusChange


class _ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class HistoryInline(_ReadOnlyInline):
    model = SuggestionStatusChange
    fields = ("created_at", "from_status", "to_status", "actor", "responsible_unit", "target_date", "reason")


class ProgressInline(_ReadOnlyInline):
    model = SuggestionProgressUpdate
    fields = ("created_at", "author", "percent_complete", "note")


@admin.register(SuggestionEvaluation)
class SuggestionEvaluationAdmin(admin.ModelAdmin):
    list_display = ("case", "status", "responsible_unit", "target_date", "progress_percent", "decided_at")
    list_filter = ("status", "responsible_unit")
    search_fields = ("case__case_number", "case__title")
    readonly_fields = [f.name for f in SuggestionEvaluation._meta.fields]
    inlines = [HistoryInline, ProgressInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
