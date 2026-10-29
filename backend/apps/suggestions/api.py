"""Suggestion evaluation API. A suggestion's id is its case id, so clients can
open the same record in the case screens. Visibility is the case module's
visibility: anything else answers 404."""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.cases.models import CaseType
from apps.cases.services import access

from . import serializers as s
from . import services
from .models import SuggestionStatus


class SuggestionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    lookup_value_regex = r"\d+"

    def get_serializer_class(self):
        return s.SuggestionListSerializer if self.action == "list" else s.SuggestionDetailSerializer

    def get_queryset(self):
        qs = (
            access.visible_cases(self.request.user)
            .filter(case_type=CaseType.SUGGESTION)
            .select_related("suggestion_evaluation__responsible_unit", "suggestion_evaluation__decided_by")
        )
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("status"):
            wanted = [v for v in p["status"].split(",") if v in SuggestionStatus.values]
            qs = qs.filter(suggestion_evaluation__status__in=wanted)
        if p.get("responsible_unit", "").isdigit():
            qs = qs.filter(suggestion_evaluation__responsible_unit_id=p["responsible_unit"])
        if p.get("mine") == "true":
            qs = qs.filter(submitted_by=self.request.user)
        if p.get("search"):
            term = p["search"].strip()[:100]
            qs = qs.filter(Q(title__icontains=term) | Q(case_number__icontains=term))
        return qs.order_by("-created_at", "-id")

    def _respond(self, case):
        case = self.get_queryset().get(pk=case.pk)
        return Response(s.SuggestionDetailSerializer(case, context=self.get_serializer_context()).data)

    @extend_schema(parameters=[
        OpenApiParameter("status", str, description="Comma-separated suggestion status values"),
        OpenApiParameter("responsible_unit", int), OpenApiParameter("mine", bool), OpenApiParameter("search", str),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=s.DecisionSerializer, responses=s.SuggestionDetailSerializer)
    @action(detail=True, methods=["post"])
    def decision(self, request, pk=None):
        case = self.get_object()
        ser = s.DecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        decision = data["decision"]
        if decision == "start_evaluation":
            services.start_evaluation(case, actor=request.user)
        elif decision == "accept":
            services.accept(case, actor=request.user, responsible_unit=data.get("responsible_unit"),
                            reason=data.get("reason", ""), target_date=data.get("target_date"))
        elif decision == "decline":
            services.decline(case, actor=request.user, reason=data.get("reason", ""))
        else:
            services.reconsider(case, actor=request.user, reason=data.get("reason", ""))
        return self._respond(case)

    @extend_schema(request=s.PlanSerializer, responses=s.SuggestionDetailSerializer)
    @action(detail=True, methods=["post"])
    def plan(self, request, pk=None):
        case = self.get_object()
        ser = s.PlanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.plan(case, actor=request.user, **ser.validated_data)
        return self._respond(case)

    @extend_schema(request=s.ProgressSerializer, responses=s.SuggestionDetailSerializer)
    @action(detail=True, methods=["post"])
    def progress(self, request, pk=None):
        case = self.get_object()
        ser = s.ProgressSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.record_progress(case, actor=request.user, **ser.validated_data)
        return self._respond(case)

    @extend_schema(request=s.ImplementationSerializer, responses=s.SuggestionDetailSerializer)
    @action(detail=True, methods=["post"])
    def implementation(self, request, pk=None):
        case = self.get_object()
        ser = s.ImplementationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.mark_implemented(case, actor=request.user, summary=ser.validated_data["summary"])
        return self._respond(case)

    @extend_schema(responses=inline_serializer("SuggestionOptions", {"statuses": serializers.ListField()}))
    @action(detail=False, methods=["get"])
    def options(self, request):
        return Response({
            "statuses": [{"value": v, "label": label} for v, label in SuggestionStatus.choices],
            "min_reason_length": services.MIN_REASON,
        })

