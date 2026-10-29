"""Read-only audit log in Django admin. Nobody, including superusers, can add,
change or delete events here."""
from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "entity_type", "entity_id", "entity_label", "actor_label", "actor_role")
    list_filter = ("action", "entity_type", "source")
    search_fields = ("entity_label", "entity_id", "actor_label", "action")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.can_view_audit_log)

    def has_module_permission(self, request):
        return self.has_view_permission(request)
