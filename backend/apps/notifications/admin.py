from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Read-only: notifications are created by the system, not by hand."""

    list_display = ("created_at", "recipient", "event_type", "title", "is_read", "email_sent_at")
    list_filter = ("event_type", "is_read")
    search_fields = ("title", "recipient__username", "case__case_number")
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
