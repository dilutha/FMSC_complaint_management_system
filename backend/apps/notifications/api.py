"""Notification centre API. Users only ever see their own notifications;
anyone else's id answers 404 (shared contract: invisible objects are 404)."""
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .services import mark_all_read, mark_read


class NotificationSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="get_event_type_display", read_only=True)
    case_number = serializers.CharField(source="case.case_number", read_only=True, default=None)
    target = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "event_type", "event_label", "title", "body", "is_read", "read_at", "created_at",
                  "case_number", "target"]
        read_only_fields = fields

    def get_target(self, obj) -> dict | None:
        """Navigation reference: {"type": "case" | "suggestion", "id": <case id>}."""
        if not obj.target_type or obj.target_id is None:
            return None
        return {"type": obj.target_type, "id": obj.target_id}


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation has no user
            return Notification.objects.none()
        qs = Notification.objects.filter(recipient=self.request.user).select_related("case")
        if self.action == "list" and self.request.query_params.get("unread") == "true":
            qs = qs.filter(is_read=False)
        return qs

    @extend_schema(parameters=[OpenApiParameter("unread", bool, description="Only unread notifications")])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        return Response(self.get_serializer(mark_read(self.get_object())).data)

    @extend_schema(request=None, responses=inline_serializer("MarkAllRead", {"updated": serializers.IntegerField()}))
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        return Response({"updated": mark_all_read(request.user)})

    @extend_schema(responses=inline_serializer("UnreadCount", {"unread": serializers.IntegerField()}))
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread": Notification.objects.filter(recipient=request.user, is_read=False).count()})
