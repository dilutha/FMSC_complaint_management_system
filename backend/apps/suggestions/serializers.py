from rest_framework import serializers

from apps.cases.models import Authority
from apps.cases.services import access

from .models import SuggestionStatus
from .services import allowed_actions, get_evaluation


class _UnitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


def _actor_label(user, viewer, case) -> str:
    """Staff see names; submitters see role labels (same rule as the case module)."""
    if user is None:
        return "System"
    if access.is_staff_for(viewer, case) or user.pk == getattr(viewer, "pk", None):
        return user.display_name
    return user.get_role_display()


class SuggestionListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    case_number = serializers.CharField()
    title = serializers.CharField()
    category = serializers.CharField(source="category.name")
    location = serializers.CharField()
    created_at = serializers.DateTimeField()
    case_status = serializers.CharField(source="status")
    case_status_label = serializers.CharField(source="get_status_display")
    status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    responsible_unit = serializers.SerializerMethodField()
    target_date = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()

    def _evaluation(self, case):
        cache = self.context.setdefault("_evaluations", {})
        if case.pk not in cache:
            cache[case.pk] = getattr(case, "suggestion_evaluation", None) or get_evaluation(case)
        return cache[case.pk]

    def get_status(self, case) -> str:
        return self._evaluation(case).status

    def get_status_label(self, case) -> str:
        return SuggestionStatus(self._evaluation(case).status).label

    def get_responsible_unit(self, case) -> dict | None:
        unit = self._evaluation(case).responsible_unit
        return {"id": unit.pk, "name": unit.name} if unit else None

    def get_target_date(self, case) -> str | None:
        target = self._evaluation(case).target_date
        return target.isoformat() if target else None

    def get_progress_percent(self, case) -> int:
        return self._evaluation(case).progress_percent


class SuggestionDetailSerializer(SuggestionListSerializer):
    description = serializers.CharField()
    submitted_by = serializers.SerializerMethodField()
    decision_reason = serializers.SerializerMethodField()
    decided_at = serializers.SerializerMethodField()
    decided_by = serializers.SerializerMethodField()
    plan_note = serializers.SerializerMethodField()
    implementation_summary = serializers.SerializerMethodField()
    implemented_at = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    progress_updates = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()

    @property
    def _viewer(self):
        return self.context["request"].user

    def get_submitted_by(self, case) -> str:
        return _actor_label(case.submitted_by, self._viewer, case)

    def get_decision_reason(self, case) -> str:
        return self._evaluation(case).decision_reason

    def get_decided_at(self, case) -> str | None:
        value = self._evaluation(case).decided_at
        return value.isoformat() if value else None

    def get_decided_by(self, case) -> str | None:
        user = self._evaluation(case).decided_by
        return _actor_label(user, self._viewer, case) if user else None

    def get_plan_note(self, case) -> str:
        return self._evaluation(case).plan_note

    def get_implementation_summary(self, case) -> str:
        return self._evaluation(case).implementation_summary

    def get_implemented_at(self, case) -> str | None:
        value = self._evaluation(case).implemented_at
        return value.isoformat() if value else None

    def get_history(self, case) -> list:
        rows = self._evaluation(case).history.select_related("actor", "responsible_unit")
        return [
            {
                "id": row.pk,
                "from_status": row.from_status,
                "to_status": row.to_status,
                "to_status_label": SuggestionStatus(row.to_status).label,
                "actor": _actor_label(row.actor, self._viewer, case),
                "reason": row.reason,
                "responsible_unit": row.responsible_unit.name if row.responsible_unit else None,
                "target_date": row.target_date.isoformat() if row.target_date else None,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    def get_progress_updates(self, case) -> list:
        rows = self._evaluation(case).progress_updates.select_related("author")
        return [
            {
                "id": row.pk,
                "note": row.note,
                "percent_complete": row.percent_complete,
                "author": _actor_label(row.author, self._viewer, case),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    def get_allowed_actions(self, case) -> list:
        return allowed_actions(self._evaluation(case), self._viewer)


class DecisionSerializer(serializers.Serializer):
    DECISIONS = ["start_evaluation", "accept", "decline", "reconsider"]

    decision = serializers.ChoiceField(choices=DECISIONS)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    responsible_unit_id = serializers.PrimaryKeyRelatedField(
        queryset=Authority.objects.filter(is_active=True), required=False, allow_null=True,
        source="responsible_unit",
    )
    target_date = serializers.DateField(required=False, allow_null=True)


class PlanSerializer(serializers.Serializer):
    target_date = serializers.DateField()
    plan_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ProgressSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=2000)
    percent_complete = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=100)


class ImplementationSerializer(serializers.Serializer):
    summary = serializers.CharField(max_length=5000)
