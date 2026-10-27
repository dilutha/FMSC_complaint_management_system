import pytest

from apps.cases.services import assignment, updates

BASE = "/api/v1/cases/"


@pytest.mark.django_db
class TestVisibility:
    def test_student_lists_only_own_cases(self, api, student, other_student, make_case):
        mine = make_case(student)
        make_case(other_student, title="Another student's case")
        res = api(student).get(BASE)
        assert res.status_code == 200
        assert [c["id"] for c in res.data["results"]] == [mine.pk]
        assert res.data["count"] == 1

    def test_cross_user_detail_is_404(self, api, student, other_student, make_case):
        case = make_case(other_student)
        for suffix in ("", "timeline/", "updates/", "attachments/", "links/"):
            assert api(student).get(f"{BASE}{case.pk}/{suffix}").status_code == 404, suffix

    def test_cross_user_actions_are_404(self, api, student, other_student, make_case):
        case = make_case(other_student)
        client = api(student)
        assert client.post(f"{BASE}{case.pk}/reopen/", {"reason": "Not fixed at all"}).status_code == 404
        assert client.post(f"{BASE}{case.pk}/updates/", {"body": "hello"}).status_code == 404
        assert client.post(f"{BASE}{case.pk}/verify-resolution/", {"confirmed": True}).status_code == 404

    def test_admin_and_management_see_all(self, api, student, other_student, admin_user, management, make_case):
        make_case(student)
        make_case(other_student)
        assert api(admin_user).get(BASE).data["count"] == 2
        assert api(management).get(BASE).data["count"] == 2

    def test_authority_sees_only_assigned_cases(self, api, student, admin_user, officer, it_unit, make_case):
        assigned = make_case(student)
        other = make_case(student, title="Wifi down in library")
        assignment.assign_case(assigned, actor=admin_user, authority=officer.authorities.first())
        assignment.assign_case(other, actor=admin_user, authority=it_unit)
        res = api(officer).get(BASE)
        assert [c["id"] for c in res.data["results"]] == [assigned.pk]
        assert api(officer).get(f"{BASE}{other.pk}/").status_code == 404

    def test_reassignment_revokes_previous_authority_access(self, api, student, admin_user, officer, maintenance, it_unit, make_case):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        assert api(officer).get(f"{BASE}{case.pk}/").status_code == 200
        assignment.assign_case(case, actor=admin_user, authority=it_unit)
        assert api(officer).get(f"{BASE}{case.pk}/").status_code == 404


@pytest.mark.django_db
class TestRolePermissions:
    def test_student_cannot_assign(self, api, student, maintenance, make_case):
        case = make_case(student)
        res = api(student).post(f"{BASE}{case.pk}/assign/", {"authority_id": maintenance.pk})
        assert res.status_code == 403
        assert res.data["error"]["code"] == "permission_denied"

    def test_student_cannot_transition_own_case(self, api, student, make_case):
        case = make_case(student)
        res = api(student).post(f"{BASE}{case.pk}/transition/", {"to_status": "under_review"})
        assert res.status_code == 403

    def test_student_cannot_reclassify(self, api, student, make_case):
        case = make_case(student)
        res = api(student).patch(f"{BASE}{case.pk}/", {"priority": "urgent"})
        assert res.status_code == 403

    def test_management_is_read_only(self, api, student, management, maintenance, make_case):
        case = make_case(student)
        client = api(management)
        assert client.get(f"{BASE}{case.pk}/").status_code == 200
        assert client.post(f"{BASE}{case.pk}/assign/", {"authority_id": maintenance.pk}).status_code == 403
        assert client.post(f"{BASE}{case.pk}/transition/", {"to_status": "under_review"}).status_code == 403
        assert client.post(f"{BASE}{case.pk}/updates/", {"body": "note"}).status_code == 403

    def test_authority_cannot_modify_unrelated_case(self, api, student, admin_user, it_officer, maintenance, make_case):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        res = api(it_officer).post(f"{BASE}{case.pk}/transition/", {"to_status": "in_progress"})
        assert res.status_code == 404

    def test_authority_cannot_assign(self, api, student, admin_user, officer, maintenance, it_unit, make_case):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        res = api(officer).post(f"{BASE}{case.pk}/assign/", {"authority_id": it_unit.pk})
        assert res.status_code == 403

    def test_only_admin_sees_duplicates_and_recommendation(self, api, student, officer, admin_user, maintenance, make_case):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance)
        for user in (student, officer):
            assert api(user).get(f"{BASE}{case.pk}/potential-duplicates/").status_code == 403
            assert api(user).get(f"{BASE}{case.pk}/assignment-recommendation/").status_code == 403
        assert api(student).get("/api/v1/authorities/").status_code == 403
        assert api(admin_user).get(f"{BASE}{case.pk}/potential-duplicates/").status_code == 200


@pytest.mark.django_db
class TestInternalNotes:
    def test_internal_notes_hidden_from_submitter(self, api, student, admin_user, officer, maintenance, make_case):
        case = make_case(student)
        assignment.assign_case(case, actor=admin_user, authority=maintenance, internal_note="Check with contractor")
        updates.add_update(case, actor=officer, body="Internal: budget approval pending", is_internal=True)
        updates.add_update(case, actor=officer, body="Plumber visit scheduled", kind="progress")

        student_view = api(student).get(f"{BASE}{case.pk}/timeline/").data
        bodies = " ".join(e["body"] for e in student_view)
        assert "Plumber visit scheduled" in bodies
        assert "budget approval" not in bodies and "contractor" not in bodies
        assert all(e["type"] != "assignment" for e in student_view)
        assert all(e["actor"]["name"] in {"You", "Faculty administrator", "Responsible authority", "System"}
                   for e in student_view)

        upd = api(student).get(f"{BASE}{case.pk}/updates/").data["results"]
        assert [u["body"] for u in upd] == ["Plumber visit scheduled"]

        staff_view = api(officer).get(f"{BASE}{case.pk}/timeline/").data
        staff_bodies = " ".join(e["body"] for e in staff_view)
        assert "budget approval" in staff_bodies and "contractor" in staff_bodies

    def test_submitter_cannot_post_internal_note(self, api, student, make_case):
        case = make_case(student)
        res = api(student).post(f"{BASE}{case.pk}/updates/", {"body": "secret", "is_internal": True})
        assert res.status_code == 403

    def test_submitter_detail_hides_staff_only_actions(self, api, student, make_case):
        case = make_case(student)
        actions = api(student).get(f"{BASE}{case.pk}/").data["allowed_actions"]
        assert actions["transitions"] == []
        assert not actions["can_assign"] and not actions["can_add_internal_note"]
        assert actions["can_comment"]
