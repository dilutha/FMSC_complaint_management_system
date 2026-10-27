import pytest

from apps.cases.models import AssignmentRule, Authority, CaseAssignment, CaseStatus
from apps.cases.services import assignment, workflow
from apps.cases.services.exceptions import InvalidTransition, ValidationFailed

BASE = "/api/v1/cases/"


@pytest.mark.django_db
class TestRecommendation:
    def test_falls_back_to_category_default(self, student, make_case, maintenance):
        rec = assignment.recommend_authority(make_case(student))
        assert rec.authority == maintenance and rec.rule_id is None

    def test_most_specific_rule_wins(self, student, make_case, category, maintenance, it_unit):
        deans = Authority.objects.create(name="Dean's Office", code="deans")
        AssignmentRule.objects.create(name="Building B", location_keyword="building b", authority=it_unit, order=1)
        specific = AssignmentRule.objects.create(
            name="Maintenance in Building B", category=category, location_keyword="Building B", authority=deans, order=50
        )
        rec = assignment.recommend_authority(make_case(student))
        assert rec.authority == deans and rec.rule_id == specific.pk

    def test_inactive_rule_or_authority_ignored(self, student, make_case, category, maintenance, it_unit):
        AssignmentRule.objects.create(name="Off", category=category, authority=it_unit, is_active=False)
        it_unit.is_active = False
        it_unit.save()
        AssignmentRule.objects.create(name="Inactive authority", category=category, authority=it_unit)
        assert assignment.recommend_authority(make_case(student)).authority == maintenance

    def test_no_match(self, student, make_case, category):
        category.default_authority = None
        category.save()
        rec = assignment.recommend_authority(make_case(student))
        assert rec.authority is None

    def test_api(self, api, admin_user, student, make_case, maintenance):
        case = make_case(student)
        res = api(admin_user).get(f"{BASE}{case.pk}/assignment-recommendation/")
        assert res.status_code == 200 and res.data["authority"]["id"] == maintenance.pk


@pytest.mark.django_db
class TestAssignment:
    def test_assign_records_history_and_override(self, student, admin_user, make_case, it_unit):
        case = make_case(student)
        case = assignment.assign_case(case, actor=admin_user, authority=it_unit, internal_note="IT handles HVAC panels")
        a = CaseAssignment.objects.get(case=case)
        assert case.status == "assigned" and case.assigned_authority == it_unit
        assert a.is_current and a.is_override and a.recommended_authority.code == "maintenance"
        assert a.internal_note == "IT handles HVAC panels"

    def test_reassignment_preserves_history(self, student, admin_user, officer, make_case, maintenance, it_unit):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        workflow.transition(case, CaseStatus.IN_PROGRESS, actor=officer)
        case = assignment.assign_case(case, actor=admin_user, authority=it_unit)
        rows = list(CaseAssignment.objects.filter(case=case).order_by("created_at", "id"))
        assert [r.authority for r in rows] == [maintenance, it_unit]
        assert [r.is_current for r in rows] == [False, True]
        assert rows[0].ended_at is not None
        assert case.status == "assigned"  # new authority has not started yet
        assert case.status_history.last().reason == "Reassigned to IT Unit."

    def test_same_authority_twice_rejected(self, student, admin_user, make_case, maintenance):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        with pytest.raises(ValidationFailed):
            assignment.assign_case(case, actor=admin_user, authority=maintenance)

    def test_inactive_authority_rejected(self, student, admin_user, make_case, it_unit):
        it_unit.is_active = False
        it_unit.save()
        with pytest.raises(ValidationFailed):
            assignment.assign_case(make_case(student), actor=admin_user, authority=it_unit)

    def test_cannot_assign_closed_case(self, student, admin_user, make_case, maintenance):
        case = make_case(student)
        workflow.transition(case, CaseStatus.REJECTED, actor=admin_user, reason="Spam")
        with pytest.raises(InvalidTransition):
            assignment.assign_case(case, actor=admin_user, authority=maintenance)

    def test_assign_api_validates_authority(self, api, admin_user, student, make_case):
        case = make_case(student)
        res = api(admin_user).post(f"{BASE}{case.pk}/assign/", {"authority_id": 99999})
        assert res.status_code == 400 and "authority_id" in res.data["error"]["details"]

    def test_reclassify_updates_priority_and_logs_internal_note(self, api, admin_user, student, make_case, it_category):
        case = make_case(student)
        res = api(admin_user).patch(f"{BASE}{case.pk}/", {"priority": "urgent", "category_id": it_category.pk, "note": "Safety"})
        assert res.status_code == 200
        assert res.data["priority"] == "urgent" and res.data["category"]["id"] == it_category.pk
        case.refresh_from_db()
        assert case.requested_priority == "normal"  # original request preserved
        assert case.updates.filter(is_internal=True).exists()
