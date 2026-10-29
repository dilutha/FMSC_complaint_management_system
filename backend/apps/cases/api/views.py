"""HTTP layer: parse/validate requests, enforce visibility, delegate to services."""
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.cases.models import (
    ACTIVE_STATUSES,
    Attachment,
    Authority,
    Case,
    CaseStatus,
    CaseType,
    Category,
    LinkType,
    Priority,
    UpdateKind,
)
from apps.cases.services import access, assignment, deadlines, duplicates, submission, updates, workflow
from apps.cases.services.attachments import ALLOWED_TYPES, save_attachments
from apps.cases.services.exceptions import NotPermitted
from apps.cases.services.timeline import build_timeline

from . import serializers as s

ORDERING = {
    "created_at": "created_at", "-created_at": "-created_at",
    "deadline_at": "deadline_at", "-deadline_at": "-deadline_at",
    "priority": "priority", "-priority": "-priority",
    "updated_at": "updated_at", "-updated_at": "-updated_at",
}


class CaseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_serializer_class(self):
        return s.CaseListSerializer if self.action == "list" else s.CaseDetailSerializer

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "case_submit"
            return [ScopedRateThrottle()]
        if self.action == "attachments" and self.request.method == "POST":
            self.throttle_scope = "attachment_upload"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        qs = access.visible_cases(self.request.user)
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status__in=[v for v in p["status"].split(",") if v in CaseStatus.values])
        if p.get("case_type") in CaseType.values:
            qs = qs.filter(case_type=p["case_type"])
        if p.get("priority") in Priority.values:
            qs = qs.filter(priority=p["priority"])
        if p.get("category", "").isdigit():
            qs = qs.filter(category_id=p["category"])
        if p.get("assigned_authority", "").isdigit():
            qs = qs.filter(assigned_authority_id=p["assigned_authority"])
        # Member B filters for the admin, case-administrator and department dashboards.
        # They narrow the already visibility-filtered queryset, so they never widen access.
        if p.get("submitter_role"):
            qs = qs.filter(submitted_by__role__in=p["submitter_role"].split(","))
        if p.get("unassigned") == "true":
            qs = qs.filter(assigned_authority__isnull=True)
        if p.get("queue") == "review":
            qs = qs.filter(status__in=[CaseStatus.SUBMITTED, CaseStatus.UNDER_REVIEW, CaseStatus.REOPENED])
        if p.get("mine") == "true":
            qs = qs.filter(submitted_by=self.request.user)
        if p.get("active") == "true":
            qs = qs.filter(status__in=ACTIVE_STATUSES)
        if p.get("overdue") == "true":
            qs = qs.filter(status__in=ACTIVE_STATUSES, deadline_at__lt=timezone.now())
        if p.get("search"):
            term = p["search"].strip()[:100]
            qs = qs.filter(Q(title__icontains=term) | Q(case_number__icontains=term) | Q(location__icontains=term))
        return qs.order_by(ORDERING.get(p.get("ordering"), "-created_at"), "-id")

    def _case(self):
        return self.get_object()  # visibility-filtered: other users' cases 404

    def _detail(self, case, code=status.HTTP_200_OK):
        case = Case.objects.select_related("category", "assigned_authority", "submitted_by").get(pk=case.pk)
        return Response(s.CaseDetailSerializer(case, context=self.get_serializer_context()).data, status=code)

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str, description="Comma-separated status values"),
            OpenApiParameter("case_type", str, enum=CaseType.values),
            OpenApiParameter("priority", str, enum=Priority.values),
            OpenApiParameter("category", int),
            OpenApiParameter("assigned_authority", int),
            OpenApiParameter("submitter_role", str, description="Comma-separated: student, lecturer, non_academic_staff"),
            OpenApiParameter("unassigned", bool),
            OpenApiParameter("queue", str, enum=["review"], description="Cases awaiting case-administrator review"),
            OpenApiParameter("mine", bool),
            OpenApiParameter("active", bool),
            OpenApiParameter("overdue", bool),
            OpenApiParameter("search", str),
            OpenApiParameter("ordering", str, enum=list(ORDERING)),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=s.CaseCreateSerializer, responses={201: s.CaseDetailSerializer})
    def create(self, request):
        ser = s.CaseCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        case = submission.submit_case(
            actor=request.user,
            title=data["title"],
            description=data["description"],
            case_type=data["case_type"],
            category=data["category"],
            location=data["location"],
            requested_priority=data["requested_priority"],
            declaration_accepted=data["declaration_accepted"],
            attachments=data.get("attachments", []),
        )
        return self._detail(case, status.HTTP_201_CREATED)

    @extend_schema(request=s.ClassificationSerializer, responses=s.CaseDetailSerializer,
                   summary="Administrator: confirm or adjust category and priority")
    def partial_update(self, request, pk=None):
        case = self._case()
        ser = s.ClassificationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case = submission.review_classification(
            case,
            actor=request.user,
            category=ser.validated_data.get("category"),
            priority=ser.validated_data.get("priority"),
            note=ser.validated_data.get("note", ""),
        )
        return self._detail(case)

    @extend_schema(request=s.TransitionSerializer, responses=s.CaseDetailSerializer)
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        case = self._case()
        ser = s.TransitionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case = workflow.transition(
            case,
            ser.validated_data["to_status"],
            actor=request.user,
            reason=ser.validated_data.get("reason", ""),
            resolution_note=ser.validated_data.get("resolution_note", ""),
        )
        return self._detail(case)

    @extend_schema(request=s.AssignSerializer, responses=s.CaseDetailSerializer)
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        case = self._case()
        ser = s.AssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case = assignment.assign_case(
            case,
            actor=request.user,
            authority=ser.validated_data["authority"],
            message=ser.validated_data.get("message", ""),
            internal_note=ser.validated_data.get("internal_note", ""),
        )
        return self._detail(case)

    @extend_schema(responses=s.RecommendationSerializer)
    @action(detail=True, methods=["get"], url_path="assignment-recommendation")
    def assignment_recommendation(self, request, pk=None):
        case = self._case()
        if not access.is_case_admin(request.user):
            raise NotPermitted("Only administrators can view assignment recommendations.")
        rec = assignment.recommend_authority(case)
        return Response(s.RecommendationSerializer(
            {"authority": rec.authority, "reason": rec.reason, "rule_id": rec.rule_id}
        ).data)

    @extend_schema(methods=["GET"], responses=s.CaseUpdateSerializer(many=True))
    @extend_schema(methods=["POST"], request=s.UpdateCreateSerializer,
                   responses={201: inline_serializer("UpdateResult", {
                       "update": s.CaseUpdateSerializer(allow_null=True), "case": s.CaseDetailSerializer()})})
    @action(detail=True, methods=["get", "post"])
    def updates(self, request, pk=None):
        case = self._case()
        ctx = self.get_serializer_context()
        if request.method == "GET":
            qs = case.updates.select_related("author", "case").prefetch_related("attachments")
            if not access.is_staff_for(request.user, case):
                qs = qs.filter(is_internal=False)
            page = self.paginate_queryset(qs)
            return self.get_paginated_response(s.CaseUpdateSerializer(page, many=True, context=ctx).data)

        ser = s.UpdateCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        update, case = updates.add_update(
            case,
            actor=request.user,
            body=d["body"],
            kind=d["kind"],
            is_internal=d["is_internal"],
            new_status=d.get("new_status"),
            resolution_note=d["resolution_note"],
            reason=d["reason"],
            attachments=d.get("attachments", []),
        )
        case = Case.objects.select_related("category", "assigned_authority", "submitted_by").get(pk=case.pk)
        return Response(
            {
                "update": s.CaseUpdateSerializer(update, context=ctx).data if update else None,
                "case": s.CaseDetailSerializer(case, context=ctx).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=s.VerifyResolutionSerializer, responses=s.CaseDetailSerializer)
    @action(detail=True, methods=["post"], url_path="verify-resolution")
    def verify_resolution(self, request, pk=None):
        case = self._case()
        ser = s.VerifyResolutionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case = updates.verify_resolution(
            case, actor=request.user, confirmed=ser.validated_data["confirmed"], feedback=ser.validated_data["feedback"]
        )
        return self._detail(case)

    @extend_schema(request=s.ReopenSerializer, responses=s.CaseDetailSerializer)
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        case = self._case()
        ser = s.ReopenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case = updates.reopen_case(case, actor=request.user, reason=ser.validated_data["reason"])
        return self._detail(case)

    @extend_schema(request=s.DeadlineSerializer, responses=s.CaseDetailSerializer)
    @action(detail=True, methods=["post"])
    def deadline(self, request, pk=None):
        case = self._case()
        ser = s.DeadlineSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case = deadlines.change_deadline(
            case, actor=request.user, new_deadline=ser.validated_data["deadline_at"], reason=ser.validated_data["reason"]
        )
        return self._detail(case)

    @extend_schema(responses=s.TimelineEntrySerializer(many=True))
    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        return Response(build_timeline(self._case(), request.user))

    @extend_schema(methods=["GET"], responses=s.AttachmentSerializer(many=True))
    @extend_schema(methods=["POST"], request={"multipart/form-data": s.AttachmentUploadSerializer},
                   responses={201: s.AttachmentSerializer(many=True)})
    @action(detail=True, methods=["get", "post"])
    def attachments(self, request, pk=None):
        case = self._case()
        ctx = self.get_serializer_context()
        if request.method == "GET":
            return Response(s.AttachmentSerializer(case.attachments.all(), many=True, context=ctx).data)
        kinds = access.actor_kinds(request.user, case)
        if not kinds & {access.ADMIN, access.AUTHORITY, access.SUBMITTER}:
            raise NotPermitted("You cannot add attachments to this case.")
        if case.status in (CaseStatus.CLOSED, CaseStatus.REJECTED):
            raise NotPermitted("Attachments cannot be added to a closed case.")
        ser = s.AttachmentUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        is_staff = bool(kinds & {access.ADMIN, access.AUTHORITY})
        saved = save_attachments(
            case, ser.validated_data["files"], actor=request.user, kind="completion" if is_staff else "evidence"
        )
        return Response(s.AttachmentSerializer(saved, many=True, context=ctx).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={(200, "application/octet-stream"): bytes})
    @action(detail=True, methods=["get"], url_path=r"attachments/(?P<attachment_id>\d+)/download",
            url_name="attachment-download")
    def attachment_download(self, request, pk=None, attachment_id=None):
        case = self._case()
        att = get_object_or_404(Attachment, pk=attachment_id, case=case)
        response = FileResponse(att.file.open("rb"), content_type=att.content_type, as_attachment=not att.is_image,
                                filename=att.original_name)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @extend_schema(responses=s.DuplicateMatchSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="potential-duplicates")
    def potential_duplicates(self, request, pk=None):
        case = self._case()
        if not access.is_case_admin(request.user):
            raise NotPermitted("Only administrators can view potential duplicates.")
        linked_ids = {other.pk for _, other in duplicates.linked_cases(case)}
        matches = [m for m in duplicates.find_potential_duplicates(case) if m.case.pk not in linked_ids]
        data = [{"case": m.case, "score": m.score, "reasons": m.reasons} for m in matches]
        return Response(s.DuplicateMatchSerializer(data, many=True, context=self.get_serializer_context()).data)

    @extend_schema(methods=["GET"], responses=s.LinkedCaseSerializer(many=True))
    @extend_schema(methods=["POST"], request=s.LinkCreateSerializer, responses={201: s.LinkedCaseSerializer})
    @action(detail=True, methods=["get", "post"])
    def links(self, request, pk=None):
        case = self._case()
        ctx = self.get_serializer_context()
        if request.method == "GET":
            visible = set(access.visible_cases(request.user).values_list("pk", flat=True))
            data = [
                {"link_id": link.pk, "link_type": link.link_type, "note": link.note, "case": other}
                for link, other in duplicates.linked_cases(case)
                if other.pk in visible
            ]
            return Response(s.LinkedCaseSerializer(data, many=True, context=ctx).data)
        ser = s.LinkCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        other = get_object_or_404(access.visible_cases(request.user), pk=ser.validated_data["other_case_id"])
        link = duplicates.link_cases(
            case, other, actor=request.user, link_type=ser.validated_data["link_type"], note=ser.validated_data["note"]
        )
        return Response(
            s.LinkedCaseSerializer({"link_id": link.pk, "link_type": link.link_type, "note": link.note, "case": other},
                                   context=ctx).data,
            status=status.HTTP_201_CREATED,
        )


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = s.CategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(is_active=True)


class AuthorityViewSet(viewsets.ReadOnlyModelViewSet):
    """Active authorities, for administrators' assignment choices."""

    serializer_class = s.AuthoritySerializer
    pagination_class = None

    def get_queryset(self):
        if not access.is_case_admin(self.request.user):
            raise NotPermitted("Only administrators can list authorities.")
        return Authority.objects.filter(is_active=True)


def _choices(enum):
    return [{"value": v, "label": label} for v, label in enum.choices]


class CaseOptionsView(APIView):
    """Enumerations and limits the Flutter client needs (single source of truth)."""

    @extend_schema(responses=inline_serializer("CaseOptions", {
        "case_types": serializers.ListField(), "priorities": serializers.ListField(),
        "statuses": serializers.ListField(), "update_kinds": serializers.ListField(),
        "link_types": serializers.ListField(), "attachments": serializers.DictField(),
    }))
    def get(self, request):
        from django.conf import settings

        cfg = settings.FMSC_CASES
        return Response({
            "case_types": _choices(CaseType),
            "priorities": _choices(Priority),
            "statuses": _choices(CaseStatus),
            "update_kinds": _choices(UpdateKind),
            "link_types": _choices(LinkType),
            "attachments": {
                "allowed_extensions": sorted(ALLOWED_TYPES),
                "max_image_bytes": cfg["MAX_IMAGE_BYTES"],
                "max_video_bytes": cfg["MAX_VIDEO_BYTES"],
                "max_per_case": cfg["MAX_ATTACHMENTS_PER_CASE"],
            },
            "verification_window_days": cfg["VERIFICATION_WINDOW_DAYS"],
            "reopen_window_days": cfg["REOPEN_WINDOW_DAYS"],
        })
