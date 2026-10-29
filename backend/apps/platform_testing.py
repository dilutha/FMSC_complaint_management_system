"""Shared pytest fixtures for Member B's apps (accounts, audit, notifications,
suggestions, dashboard). Synthetic data only. Loaded through
`pytest_plugins` in backend/conftest.py; the case module's own fixtures in
apps/cases/tests/conftest.py are left untouched."""
import itertools

import pytest
from django.core.files.storage import FileSystemStorage
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.cases.models import Attachment, Authority, Category, DeadlinePolicy
from apps.cases.services import submission

PASSWORD = "Synthetic-pass-123"
_seq = itertools.count(1)


@pytest.fixture(autouse=True)
def platform_isolation(monkeypatch, tmp_path, settings):
    field = Attachment._meta.get_field("file")
    monkeypatch.setattr(field, "storage", FileSystemStorage(location=str(tmp_path / "private"), base_url=None))
    from rest_framework.throttling import SimpleRateThrottle

    monkeypatch.setattr(SimpleRateThrottle, "allow_request", lambda self, request, view: True)
    settings.FMSC_NOTIFICATIONS = {**settings.FMSC_NOTIFICATIONS, "EMAIL_ENABLED": False}


def make_user(role=Role.STUDENT, **kwargs):
    n = next(_seq)
    return User.objects.create_user(
        username=kwargs.pop("username", f"pb-user{n}"), password=PASSWORD, role=role,
        email=kwargs.pop("email", f"pb-user{n}@example.test"), **kwargs
    )


@pytest.fixture
def student(db):
    return make_user(Role.STUDENT, first_name="Test", last_name="Student")


@pytest.fixture
def other_student(db):
    return make_user(Role.STUDENT)


@pytest.fixture
def admin_user(db):
    return make_user(Role.CASE_ADMIN, first_name="Case", last_name="Admin")


@pytest.fixture
def system_admin(db):
    return make_user(Role.SYSTEM_ADMIN, first_name="Sys", last_name="Admin")


@pytest.fixture
def management(db):
    return make_user(Role.MANAGEMENT, first_name="Faculty", last_name="Manager")


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
def deadline_policy(db):
    return DeadlinePolicy.objects.create(name="Normal 72h", priority="normal", resolution_hours=72)


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


@pytest.fixture
def run_events(django_capture_on_commit_callbacks):
    """Run the after-commit integration signals (as in production) for the block."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


def png_upload(name="photo.png"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, content_type="image/png")
