"""Synthetic fixtures only — no real student or staff data."""
import itertools

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.cases.models import Attachment, Authority, Category
from apps.cases.services import submission

_seq = itertools.count(1)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _private_media(monkeypatch, tmp_path):
    """Write attachments to a temporary private directory."""
    field = Attachment._meta.get_field("file")
    monkeypatch.setattr(field, "storage", FileSystemStorage(location=str(tmp_path / "private"), base_url=None))


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "allow_request", lambda self, request, view: True)


def make_user(role=Role.STUDENT, **kwargs):
    n = next(_seq)
    return User.objects.create_user(
        username=kwargs.pop("username", f"user{n}"), password="Synthetic-pass-123", role=role, **kwargs
    )


@pytest.fixture
def student(db):
    return make_user(Role.STUDENT, first_name="Test", last_name="Student")


@pytest.fixture
def other_student(db):
    return make_user(Role.STUDENT)


@pytest.fixture
def lecturer(db):
    return make_user(Role.LECTURER)


@pytest.fixture
def admin_user(db):
    return make_user(Role.CASE_ADMIN, first_name="Case", last_name="Admin")


@pytest.fixture
def management(db):
    return make_user(Role.MANAGEMENT)


@pytest.fixture
def maintenance(db):
    return Authority.objects.create(name="Maintenance Division", code="maintenance")


@pytest.fixture
def it_unit(db):
    return Authority.objects.create(name="IT Unit", code="it-unit")


@pytest.fixture
def officer(db, maintenance):
    user = make_user(Role.AUTHORITY, first_name="Maint", last_name="Officer")
    maintenance.members.add(user)
    return user


@pytest.fixture
def it_officer(db, it_unit):
    user = make_user(Role.AUTHORITY)
    it_unit.members.add(user)
    return user


@pytest.fixture
def category(db, maintenance):
    return Category.objects.create(name="Maintenance", code="maintenance", default_authority=maintenance)


@pytest.fixture
def it_category(db, it_unit):
    return Category.objects.create(name="IT", code="it", default_authority=it_unit)


@pytest.fixture
def make_case(category):
    def _make(actor, **overrides):
        data = dict(
            title="Water leak near corridor",
            description="Water is leaking from the ceiling near the second floor corridor.",
            case_type="complaint",
            category=category,
            location="Building B, second floor corridor",
            requested_priority="normal",
            declaration_accepted=True,
        )
        data.update(overrides)
        return submission.submit_case(actor=actor, **data)

    return _make


@pytest.fixture
def api():
    def _client(user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        return client

    return _client


def png(name="photo.png", data=PNG_BYTES):
    return SimpleUploadedFile(name, data, content_type="image/png")
