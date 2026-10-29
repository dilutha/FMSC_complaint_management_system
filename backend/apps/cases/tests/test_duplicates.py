from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cases.models import Case, CaseLink, CaseStatus
from apps.cases.services import duplicates, workflow
from apps.cases.services.exceptions import NotPermitted, ValidationFailed

BASE = "/api/v1/cases/"


@pytest.mark.django_db
class TestDuplicateDetection:
    def test_similar_case_is_flagged(self, student, other_student, make_case):
        original = make_case(student)
        similar = make_case(
            other_student,
            title="Leaking water in corridor",
            description="Ceiling water leak in the corridor on the second floor of Building B.",
            location="Building B 2nd floor corridor",
        )
        matches = duplicates.find_potential_duplicates(similar)
        assert [m.case for m in matches] == [original]
        assert "Same category" in matches[0].reasons
        assert any(r.startswith("Shared keywords") for r in matches[0].reasons)

    def test_unrelated_case_not_flagged(self, student, make_case, it_category):
        make_case(student)
        other = make_case(student, title="Wifi password not working", category=it_category,
                          description="Cannot connect laptops to the student wifi network.", location="Library")
        assert duplicates.find_potential_duplicates(other) == []

    def test_rejected_and_out_of_window_cases_excluded(self, student, admin_user, make_case, settings):
        rejected = make_case(student)
        workflow.transition(rejected, CaseStatus.REJECTED, actor=admin_user, reason="Spam submission")
        old = make_case(student)
        Case.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=settings.FMSC_CASES["DUPLICATE_WINDOW_DAYS"] + 5)
        )
        new = make_case(student)
        assert duplicates.find_potential_duplicates(new) == []

    def test_submission_is_never_auto_rejected(self, student, make_case):
        make_case(student)
        second = make_case(student)
        assert second.status == "submitted"

    def test_keyword_normalisation(self):
        assert duplicates.keywords("Leaking leaks LEAKED the") == {"leak"}


@pytest.mark.django_db
class TestLinking:
    def test_admin_links_without_merging(self, api, admin_user, student, make_case):
        a, b = make_case(student), make_case(student)
        res = api(admin_user).post(f"{BASE}{b.pk}/links/", {"other_case_id": a.pk, "link_type": "duplicate"})
        assert res.status_code == 201
        assert Case.objects.filter(pk__in=[a.pk, b.pk]).count() == 2
        link = CaseLink.objects.get()
        assert (link.from_case_id, link.to_case_id) == (a.pk, b.pk)
        assert [x["case"]["id"] for x in api(admin_user).get(f"{BASE}{a.pk}/links/").data] == [b.pk]
        # linked cases are no longer suggested as potential duplicates
        assert api(admin_user).get(f"{BASE}{b.pk}/potential-duplicates/").data == []

    def test_duplicate_link_rejected(self, admin_user, student, make_case):
        a, b = make_case(student), make_case(student)
        duplicates.link_cases(a, b, actor=admin_user)
        with pytest.raises(ValidationFailed):
            duplicates.link_cases(b, a, actor=admin_user)

    def test_self_link_rejected(self, admin_user, student, make_case):
        a = make_case(student)
        with pytest.raises(ValidationFailed):
            duplicates.link_cases(a, a, actor=admin_user)

    def test_non_admin_cannot_link(self, student, make_case):
        a, b = make_case(student), make_case(student)
        with pytest.raises(NotPermitted):
            duplicates.link_cases(a, b, actor=student)

    def test_submitter_does_not_see_links_to_others_cases(self, api, admin_user, student, other_student, make_case):
        mine, theirs = make_case(student), make_case(other_student)
        duplicates.link_cases(mine, theirs, actor=admin_user)
        assert api(student).get(f"{BASE}{mine.pk}/links/").data == []
