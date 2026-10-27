"""Serializers: validate input shape and control exposed fields.

Business rules (who may do what, which transitions are legal) are enforced in
apps.cases.services, not here.
"""
from django.urls import reverse
from rest_framework import serializers

from apps.cases.models import (
    Attachment,
    Authority,
    Case,
    CaseResolution,
    CaseStatus,
    CaseType,
    CaseUpdate,
    Category,
    LinkType,
    Priority,
    UpdateKind,
)
from apps.cases.services import access
from apps.cases.services.workflow import allowed_transitions

#: Fields that can never be set through a submission request.
PROTECTED_SUBMISSION_FIELDS = frozenset(
    {
        "case_number", "status", "assigned_authority", "assigned_authority_id", "submitted_by", "priority",
        "deadline_at", "solved_at", "closed_at", "verification_due_at", "reopen_count", "created_at", "updated_at",
    }
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "code", "description"]


class AuthorityBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Authority
        fields = ["id", "name", "code", "unit"]


class AuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Authority
        fields = ["id", "name", "code", "unit", "officer_name", "designation", "email", "phone"]


class UserBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField()
    role = serializers.CharField()


class AttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "original_name", "content_type", "size", "kind", "created_at", "download_url"]

    def get_download_url(self, obj) -> str:
        path = reverse("case-attachment-download", kwargs={"pk": obj.case_id, "attachment_id": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class ResolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseResolution
        fields = ["id", "note", "resolved_at", "outcome", "submitter_feedback", "outcome_at"]


class CaseListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    assigned_authority = AuthorityBriefSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    age_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = Case
        fields = [
            "id", "case_number", "title", "case_type", "category", "priority", "status", "status_label",
            "location", "assigned_authority", "created_at", "updated_at", "deadline_at", "is_overdue", "age_days",
        ]


class CaseDetailSerializer(CaseListSerializer):
    submitted_by = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)
    latest_resolution = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()
    viewer_capacities = serializers.SerializerMethodField()

    class Meta(CaseListSerializer.Meta):
        fields = CaseListSerializer.Meta.fields + [
            "description", "requested_priority", "submitted_by", "solved_at", "closed_at", "verification_due_at",
            "reopen_count", "attachments", "latest_resolution", "allowed_actions", "viewer_capacities",
        ]

    def _viewer(self):
        return self.context["request"].user

    def get_submitted_by(self, obj) -> dict:
        viewer = self._viewer()
        if access.is_staff_for(viewer, obj) or obj.submitted_by_id == viewer.pk:
            u = obj.submitted_by
            return {"id": u.pk, "display_name": u.display_name, "role": u.role}
        return None

    def get_latest_resolution(self, obj) -> dict:
        res = obj.resolutions.order_by("-resolved_at", "-id").first()
        return ResolutionSerializer(res).data if res else None

    def get_allowed_actions(self, obj) -> dict:
        viewer = self._viewer()
        kinds = access.actor_kinds(viewer, obj)
        targets = [str(s) for s in allowed_transitions(obj, viewer)]
        return {
            "transitions": targets,
            "can_assign": "assigned" in targets,
            "can_verify_resolution": access.SUBMITTER in kinds and obj.status == CaseStatus.SOLVED,
            "can_reopen": "reopened" in targets,
            "can_comment": bool(kinds & {access.ADMIN, access.AUTHORITY, access.SUBMITTER})
            and (obj.status not in (CaseStatus.CLOSED, CaseStatus.REJECTED) or access.ADMIN in kinds),
            "can_add_internal_note": bool(kinds & {access.ADMIN, access.AUTHORITY}),
            "can_change_deadline": access.ADMIN in kinds,
            "can_reclassify": access.ADMIN in kinds,
            "can_view_duplicates": access.ADMIN in kinds,
        }

    def get_viewer_capacities(self, obj) -> list:
        return sorted(access.actor_kinds(self._viewer(), obj))


class CaseCreateSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=5, max_length=150)
    description = serializers.CharField(min_length=10, max_length=5000)
    case_type = serializers.ChoiceField(choices=CaseType.choices)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True), source="category")
    location = serializers.CharField(min_length=2, max_length=200)
    requested_priority = serializers.ChoiceField(choices=Priority.choices, default=Priority.NORMAL)
    declaration_accepted = serializers.BooleanField()
    attachments = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False, max_length=255), required=False, allow_empty=True
    )

    def validate(self, attrs):
        sent = set(self.initial_data.keys()) if hasattr(self.initial_data, "keys") else set()
        protected = sorted(sent & PROTECTED_SUBMISSION_FIELDS)
        if protected:
            raise serializers.ValidationError({f: ["This field cannot be set when submitting a case."] for f in protected})
        return attrs


class ClassificationSerializer(serializers.Serializer):
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source="category", required=False)
    priority = serializers.ChoiceField(choices=Priority.choices, required=False)
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class TransitionSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=CaseStatus.choices)
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    resolution_note = serializers.CharField(max_length=5000, required=False, allow_blank=True)


class AssignSerializer(serializers.Serializer):
    authority_id = serializers.PrimaryKeyRelatedField(queryset=Authority.objects.all(), source="authority")
    internal_note = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class RecommendationSerializer(serializers.Serializer):
    authority = AuthorityBriefSerializer(allow_null=True)
    reason = serializers.CharField()
    rule_id = serializers.IntegerField(allow_null=True)


class CaseUpdateSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = CaseUpdate
        fields = ["id", "kind", "body", "is_internal", "created_at", "author", "attachments"]

    def get_author(self, obj) -> dict:
        viewer = self.context["request"].user
        if access.is_staff_for(viewer, obj.case) or obj.author_id == viewer.pk:
            return {"id": obj.author_id, "display_name": obj.author.display_name}
        return {"id": None, "display_name": "Faculty staff"}


class UpdateCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")
    kind = serializers.ChoiceField(
        choices=[
            (UpdateKind.COMMENT, UpdateKind.COMMENT.label),
            (UpdateKind.PROGRESS, UpdateKind.PROGRESS.label),
            (UpdateKind.INFORMATION_RESPONSE, UpdateKind.INFORMATION_RESPONSE.label),
        ],
        default=UpdateKind.COMMENT,
    )
    is_internal = serializers.BooleanField(default=False)
    new_status = serializers.ChoiceField(choices=CaseStatus.choices, required=False, allow_null=True)
    resolution_note = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    attachments = serializers.ListField(child=serializers.FileField(allow_empty_file=False), required=False)


class VerifyResolutionSerializer(serializers.Serializer):
    confirmed = serializers.BooleanField()
    feedback = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class ReopenSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5, max_length=2000)


class DeadlineSerializer(serializers.Serializer):
    deadline_at = serializers.DateTimeField(allow_null=True)
    reason = serializers.CharField(min_length=3, max_length=500)


class AttachmentUploadSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(allow_empty_file=False), allow_empty=False)


class LinkCreateSerializer(serializers.Serializer):
    other_case_id = serializers.IntegerField()
    link_type = serializers.ChoiceField(choices=LinkType.choices, default=LinkType.RELATED)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class LinkedCaseSerializer(serializers.Serializer):
    link_id = serializers.IntegerField()
    link_type = serializers.CharField()
    note = serializers.CharField()
    case = CaseListSerializer()


class DuplicateMatchSerializer(serializers.Serializer):
    case = CaseListSerializer()
    score = serializers.FloatField()
    reasons = serializers.ListField(child=serializers.CharField())


class TimelineEntrySerializer(serializers.Serializer):
    type = serializers.CharField()
    at = serializers.DateTimeField()
    title = serializers.CharField()
    body = serializers.CharField(allow_blank=True)
    actor = serializers.DictField()
    is_internal = serializers.BooleanField()
    from_status = serializers.CharField(required=False, allow_null=True)
    to_status = serializers.CharField(required=False)
    kind = serializers.CharField(required=False)
    attachment_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
