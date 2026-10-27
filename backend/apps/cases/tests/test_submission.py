import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.cases import signals
from apps.cases.models import Case, CaseStatus, Category
from apps.cases.services.exceptions import ValidationFailed
from apps.cases.services.numbering import next_case_number

from .conftest import JPEG_BYTES, MP4_BYTES, png

URL = "/api/v1/cases/"


def payload(category, **overrides):
    data = {
        "title": "Projector not working in Hall A",
        "description": "The projector in Hall A does not turn on during lectures.",
        "case_type": "complaint",
        "category_id": category.pk,
        "location": "Hall A",
        "requested_priority": "urgent",
        "declaration_accepted": True,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestSubmission:
    def test_valid_submission_creates_case_with_reference_number(self, api, student, category):
        res = api(student).post(URL, payload(category), format="json")
        assert res.status_code == 201, res.data
        body = res.data
        assert re.fullmatch(r"FMSC-\d{4}-\d{5}", body["case_number"])
        assert body["status"] == "submitted"
        assert body["priority"] == "urgent"
        assert body["assigned_authority"] is None
        case = Case.objects.get(pk=body["id"])
        assert case.submitted_by == student
        assert case.status_history.count() == 1

    def test_lecturer_can_submit_suggestion(self, api, lecturer, category):
        res = api(lecturer).post(URL, payload(category, case_type="suggestion", requested_priority="normal"), format="json")
        assert res.status_code == 201
        assert res.data["case_type"] == "suggestion"

    @pytest.mark.parametrize(
        "field,value",
        [("title", "abc"), ("description", "short"), ("case_type", "praise"), ("requested_priority", "critical"),
         ("location", "")],
    )
    def test_invalid_fields_rejected(self, api, student, category, field, value):
        res = api(student).post(URL, payload(category, **{field: value}), format="json")
        assert res.status_code == 400
        assert res.data["error"]["code"] == "validation_error"
        assert field in res.data["error"]["details"]

    def test_missing_required_fields(self, api, student):
        res = api(student).post(URL, {}, format="json")
        assert res.status_code == 400
        assert {"title", "description", "case_type", "category_id", "location"} <= set(res.data["error"]["details"])

    def test_declaration_required(self, api, student, category):
        res = api(student).post(URL, payload(category, declaration_accepted=False), format="json")
        assert res.status_code == 400
        assert "declaration_accepted" in res.data["error"]["details"]

    def test_inactive_category_rejected(self, api, student, category):
        category.is_active = False
        category.save()
        res = api(student).post(URL, payload(category), format="json")
        assert res.status_code == 400
        assert "category_id" in res.data["error"]["details"]

    @pytest.mark.parametrize(
        "field,value",
        [("status", "closed"), ("assigned_authority_id", 1), ("closed_at", "2026-01-01T00:00:00Z"),
         ("case_number", "FMSC-2026-99999"), ("priority", "urgent")],
    )
    def test_protected_fields_cannot_be_set(self, api, student, category, field, value):
        res = api(student).post(URL, payload(category, **{field: value}), format="json")
        assert res.status_code == 400
        assert field in res.data["error"]["details"]
        assert Case.objects.count() == 0

    def test_unauthenticated_rejected(self, api, category):
        res = api().post(URL, payload(category), format="json")
        assert res.status_code == 401
        assert res.data["error"]["code"] == "not_authenticated"

    def test_submission_emits_event_after_commit(self, student, make_case, django_capture_on_commit_callbacks):
        received = []
        handler = lambda sender, case, actor, payload, **kw: received.append((case.case_number, actor, payload))  # noqa: E731
        signals.case_submitted.connect(handler)
        try:
            with django_capture_on_commit_callbacks(execute=True):
                case = make_case(student)
        finally:
            signals.case_submitted.disconnect(handler)
        assert received == [(case.case_number, student, received[0][2])]
        assert received[0][2]["case_number"] == case.case_number


@pytest.mark.django_db
class TestCaseNumbers:
    def test_numbers_are_sequential_and_unique(self, student, make_case):
        numbers = [make_case(student).case_number for _ in range(5)]
        assert len(set(numbers)) == 5
        seqs = [int(n.rsplit("-", 1)[1]) for n in numbers]
        assert seqs == sorted(seqs) and seqs[-1] - seqs[0] == 4

    def test_sequence_is_per_year(self):
        assert next_case_number(2030).endswith("2030-00001")
        assert next_case_number(2030).endswith("2030-00002")
        assert next_case_number(2031).endswith("2031-00001")

    def test_database_enforces_uniqueness(self, student, make_case):
        from django.db import IntegrityError, transaction

        case = make_case(student)
        clone = Case(
            case_number=case.case_number, title="x" * 6, description="y" * 12, case_type="complaint",
            category=case.category, location="Hall", submitted_by=student,
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            clone.save()


@pytest.mark.django_db
class TestAttachments:
    def test_submission_with_image_and_video(self, api, student, category):
        data = payload(category)
        data["attachments"] = [
            png(),
            SimpleUploadedFile("clip.mp4", MP4_BYTES, content_type="video/mp4"),
        ]
        res = api(student).post(URL, data, format="multipart")
        assert res.status_code == 201, res.data
        assert [a["content_type"] for a in res.data["attachments"]] == ["image/png", "video/mp4"]
        assert all("/download/" in a["download_url"] for a in res.data["attachments"])

    def test_disallowed_extension_rejected(self, api, student, category):
        data = payload(category)
        data["attachments"] = [SimpleUploadedFile("run.exe", b"MZ" + b"\x00" * 40)]
        res = api(student).post(URL, data, format="multipart")
        assert res.status_code == 400
        assert res.data["error"]["code"] == "unsupported_file_type"
        assert Case.objects.count() == 0  # whole submission rolled back

    def test_content_must_match_extension(self, api, student, category):
        data = payload(category)
        data["attachments"] = [SimpleUploadedFile("fake.png", JPEG_BYTES, content_type="image/png")]
        res = api(student).post(URL, data, format="multipart")
        assert res.status_code == 400
        assert res.data["error"]["code"] == "file_content_mismatch"

    def test_size_limit(self, api, student, category, settings):
        settings.FMSC_CASES = {**settings.FMSC_CASES, "MAX_IMAGE_BYTES": 50}
        data = payload(category)
        data["attachments"] = [png()]
        res = api(student).post(URL, data, format="multipart")
        assert res.status_code == 400
        assert res.data["error"]["code"] == "file_too_large"

    def test_attachment_count_limit(self, api, student, category, settings):
        settings.FMSC_CASES = {**settings.FMSC_CASES, "MAX_ATTACHMENTS_PER_CASE": 2}
        data = payload(category)
        data["attachments"] = [png("a.png"), png("b.png"), png("c.png")]
        res = api(student).post(URL, data, format="multipart")
        assert res.status_code == 400
        assert res.data["error"]["code"] == "too_many_attachments"

    def test_download_requires_access(self, api, student, other_student, category):
        data = payload(category)
        data["attachments"] = [png()]
        res = api(student).post(URL, data, format="multipart")
        url = res.data["attachments"][0]["download_url"]
        ok = api(student).get(url)
        assert ok.status_code == 200
        assert ok["Cache-Control"] == "private, no-store"
        assert b"".join(ok.streaming_content).startswith(b"\x89PNG")
        assert api(other_student).get(url).status_code == 404
        assert api().get(url).status_code == 401

    def test_validation_error_does_not_create_case(self, student, make_case):
        bad = SimpleUploadedFile("x.gif", b"GIF89a" + b"\x00" * 20)
        with pytest.raises(ValidationFailed):
            make_case(student, attachments=[bad])
        assert not Case.objects.exists()


@pytest.mark.django_db
def test_category_and_options_endpoints(api, student, category):
    Category.objects.create(name="Hidden", code="hidden", is_active=False)
    res = api(student).get("/api/v1/categories/")
    assert [c["code"] for c in res.data] == ["maintenance"]
    opts = api(student).get("/api/v1/case-options/").data
    assert {s["value"] for s in opts["statuses"]} == set(CaseStatus.values)
    assert "png" in opts["attachments"]["allowed_extensions"]
