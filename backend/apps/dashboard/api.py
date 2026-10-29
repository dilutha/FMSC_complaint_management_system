"""Dashboard and report endpoints. All require the view_dashboard capability
(administrators and faculty management)."""
import csv

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import CanViewDashboard
from apps.audit.services import record as audit
from apps.cases.models import CaseStatus, CaseType, Priority

from . import metrics
from .overview import overview


class DashboardFilterSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    category = serializers.IntegerField(required=False, min_value=1)
    priority = serializers.ChoiceField(choices=Priority.values, required=False)
    case_type = serializers.ChoiceField(choices=CaseType.values, required=False)
    status = serializers.CharField(required=False, help_text="Comma-separated case status values")
    authority = serializers.IntegerField(required=False, min_value=1)
    location = serializers.CharField(required=False, max_length=100, allow_blank=True)

    def validate_status(self, value):
        values = [v.strip() for v in value.split(",") if v.strip()]
        unknown = [v for v in values if v not in CaseStatus.values]
        if unknown:
            raise serializers.ValidationError(f"Unknown status: {', '.join(unknown)}.")
        return values

    def validate(self, attrs):
        if attrs.get("date_from") and attrs.get("date_to") and attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_to": ["The end date must be on or after the start date."]})
        return attrs

    def to_filters(self) -> metrics.DashboardFilters:
        d = self.validated_data
        return metrics.DashboardFilters(
            date_from=d.get("date_from"), date_to=d.get("date_to"), category=d.get("category"),
            priority=d.get("priority"), case_type=d.get("case_type"), statuses=d.get("status", []),
            authority=d.get("authority"), location=(d.get("location") or "").strip(),
        )


def parse_filters(request) -> metrics.DashboardFilters:
    ser = DashboardFilterSerializer(data=request.query_params)
    ser.is_valid(raise_exception=True)
    return ser.to_filters()


FILTER_PARAMETERS = [
    OpenApiParameter("date_from", OpenApiTypes.DATE, description="Submitted on or after (YYYY-MM-DD)"),
    OpenApiParameter("date_to", OpenApiTypes.DATE, description="Submitted on or before (YYYY-MM-DD)"),
    OpenApiParameter("category", int), OpenApiParameter("priority", str, enum=Priority.values),
    OpenApiParameter("case_type", str, enum=CaseType.values),
    OpenApiParameter("status", str, description="Comma-separated case status values"),
    OpenApiParameter("authority", int, description="Responsible unit (authority id)"),
    OpenApiParameter("location", str, description="Text contained in the location"),
]


class DashboardOverviewView(APIView):
    """Role-scoped dashboard for every signed-in user (see overview.py for the scopes)."""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(overview(request.user))


class _DashboardView(APIView):
    permission_classes = [CanViewDashboard]


class DashboardSummaryView(_DashboardView):
    @extend_schema(parameters=FILTER_PARAMETERS, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(metrics.summary(parse_filters(request)))


class DashboardTrendsView(_DashboardView):
    @extend_schema(parameters=FILTER_PARAMETERS + [OpenApiParameter("interval", str, enum=list(metrics.INTERVALS))],
                   responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(metrics.trends(parse_filters(request), interval=request.query_params.get("interval")))


class DashboardWorkloadView(_DashboardView):
    @extend_schema(parameters=FILTER_PARAMETERS, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(metrics.workload(parse_filters(request)))


class DashboardAgeingView(_DashboardView):
    @extend_schema(parameters=FILTER_PARAMETERS + [OpenApiParameter("scope", str, enum=["not_started", "open"])],
                   responses=OpenApiTypes.OBJECT)
    def get(self, request):
        scope = "open" if request.query_params.get("scope") == "open" else "not_started"
        return Response(metrics.ageing(parse_filters(request), scope=scope))


class ReportRowSerializer(serializers.Serializer):
    """Shape of one report row (documentation only; rows are built by metrics.report_row)."""

    id = serializers.IntegerField()
    case_number = serializers.CharField()
    title = serializers.CharField()
    case_type = serializers.CharField()
    category = serializers.CharField()
    priority = serializers.CharField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    location = serializers.CharField()
    authority = serializers.CharField(allow_null=True)
    created_at = serializers.CharField()
    first_response_at = serializers.CharField(allow_null=True)
    deadline_at = serializers.CharField(allow_null=True)
    solved_at = serializers.CharField(allow_null=True)
    closed_at = serializers.CharField(allow_null=True)
    age_days = serializers.IntegerField()
    is_overdue = serializers.BooleanField()
    reopen_count = serializers.IntegerField()


class ExportThrottle(UserRateThrottle):
    scope = "report_export"


class CaseReportView(ListAPIView):
    """Filterable case report. `?export=csv` downloads every matching row."""

    permission_classes = [CanViewDashboard]
    serializer_class = ReportRowSerializer

    def get_throttles(self):
        return [ExportThrottle()] if self.request.query_params.get("export") == "csv" else []

    def get_queryset(self):
        return metrics.report_queryset(parse_filters(self.request))

    @extend_schema(parameters=FILTER_PARAMETERS + [OpenApiParameter("export", str, enum=["csv"])])
    def get(self, request, *args, **kwargs):
        filters = parse_filters(request)
        qs = metrics.report_queryset(filters)
        now = timezone.now()
        if request.query_params.get("export") == "csv":
            return self._csv(qs, filters, now)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response([metrics.report_row(case, now) for case in page])

    def _csv(self, qs, filters, now):
        audit("report.exported", actor=self.request.user, entity_type="report", entity_id="cases",
              metadata={"filters": filters.as_dict(), "rows": qs.count()})
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="fmsc-case-report-{now:%Y%m%d-%H%M}.csv"'
        response["Cache-Control"] = "private, no-store"
        writer = csv.writer(response)
        writer.writerow([label for _, label in metrics.REPORT_COLUMNS])
        for case in qs.iterator(chunk_size=500):
            row = metrics.report_row(case, now)
            writer.writerow([_csv_safe(row[key]) for key, _ in metrics.REPORT_COLUMNS])
        return response


def _csv_safe(value):
    """Neutralise spreadsheet formula injection in user-entered text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return "" if value is None else value
