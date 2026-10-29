"""Read-only audit log API. There is deliberately no create, update or delete
endpoint: events are written only by server-side code."""
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, serializers, viewsets

from apps.accounts.permissions import CanViewAuditLog

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id", "created_at", "actor", "actor_label", "actor_role", "action", "entity_type", "entity_id",
            "entity_label", "previous_value", "new_value", "reason", "metadata", "source",
        ]
        read_only_fields = fields


class AuditEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditEventSerializer
    permission_classes = [CanViewAuditLog]

    def get_queryset(self):
        qs = AuditEvent.objects.all()
        p = self.request.query_params
        for param, field in (("action", "action"), ("entity_type", "entity_type"), ("entity_id", "entity_id")):
            if p.get(param):
                qs = qs.filter(**{field: p[param][:60]})
        if p.get("actor", "").isdigit():
            qs = qs.filter(actor_id=p["actor"])
        if date_from := parse_date(p.get("date_from", "") or ""):
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to := parse_date(p.get("date_to", "") or ""):
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    @extend_schema(parameters=[
        OpenApiParameter("action", str), OpenApiParameter("entity_type", str), OpenApiParameter("entity_id", str),
        OpenApiParameter("actor", int), OpenApiParameter("date_from", str, description="YYYY-MM-DD"),
        OpenApiParameter("date_to", str, description="YYYY-MM-DD"),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
