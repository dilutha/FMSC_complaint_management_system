"""Django settings for the FMSC Complaint & Suggestion Management backend.

All secrets and environment-specific values come from environment variables
(optionally loaded from backend/.env). Nothing secret is committed.
"""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, existing env vars win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


def env_int(name, default):
    return int(env(name, default))


def env_float(name, default):
    return float(env(name, default))


DEBUG = env_bool("DJANGO_DEBUG", False)
TESTING = env_bool("FMSC_TESTING", False) or "pytest" in sys.modules or "test" in sys.argv[1:2]

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or TESTING:
        SECRET_KEY = "insecure-development-only-key"  # never used in production
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is false.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,10.0.2.2")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    # Shared / Member B owned (placeholder until Member B's module lands)
    "apps.accounts",
    # Member A: core case management
    "apps.cases",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database ---------------------------------------------------------------
# PostgreSQL is the project database. FMSC_DB_ENGINE=sqlite is an explicit,
# local-only escape hatch for running the unit tests where no PostgreSQL
# credentials are available; it must never be used for deployment.
if env("FMSC_DB_ENGINE", "postgresql") == "sqlite":
    if not (DEBUG or TESTING):
        raise ImproperlyConfigured("SQLite is only permitted for local tests.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "local-test.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "fmsc_cases"),
            "USER": env("POSTGRES_USER", "fmsc"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Asia/Colombo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Attachments live in a private directory that is never mapped to a public URL.
# They are streamed only through the authorised download endpoint.
PRIVATE_MEDIA_ROOT = Path(env("FMSC_PRIVATE_MEDIA_ROOT", "") or BASE_DIR / "private_media")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "private": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(PRIVATE_MEDIA_ROOT), "base_url": None},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security ---------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG and not TESTING:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 3600)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --- Django REST Framework --------------------------------------------------
REST_FRAMEWORK = {
    # Shared contract with Member B: token auth for Flutter, session auth (with
    # CSRF) for browser/admin use. Member B may swap in JWT here centrally.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.cases.api.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.cases.api.errors.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "case_submit": env("FMSC_THROTTLE_CASE_SUBMIT", "10/hour"),
        "attachment_upload": env("FMSC_THROTTLE_ATTACHMENT_UPLOAD", "40/hour"),
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FMSC Complaint & Suggestion Management API",
    "DESCRIPTION": (
        "Case-management API for the Faculty of Management Studies and Commerce, "
        "University of Sri Jayewardenepura."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Case-management policy (configurable without code changes) ------------
FMSC_CASES = {
    "MAX_IMAGE_BYTES": env_int("FMSC_MAX_IMAGE_MB", 5) * 1024 * 1024,
    "MAX_VIDEO_BYTES": env_int("FMSC_MAX_VIDEO_MB", 50) * 1024 * 1024,
    "MAX_ATTACHMENTS_PER_CASE": env_int("FMSC_MAX_ATTACHMENTS_PER_CASE", 10),
    # Days a solved case waits for the submitter's verification before auto-closure.
    "VERIFICATION_WINDOW_DAYS": env_int("FMSC_VERIFICATION_WINDOW_DAYS", 7),
    # Days after closure during which the submitter may still reopen.
    "REOPEN_WINDOW_DAYS": env_int("FMSC_REOPEN_WINDOW_DAYS", 14),
    # Hours after the deadline at which a level-2 escalation is raised.
    "ESCALATION_LEVEL2_AFTER_HOURS": env_int("FMSC_ESCALATION_LEVEL2_AFTER_HOURS", 48),
    "DUPLICATE_WINDOW_DAYS": env_int("FMSC_DUPLICATE_WINDOW_DAYS", 30),
    "DUPLICATE_THRESHOLD": env_float("FMSC_DUPLICATE_THRESHOLD", 0.45),
    "CASE_NUMBER_PREFIX": env("FMSC_CASE_NUMBER_PREFIX", "FMSC"),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"apps": {"handlers": ["console"], "level": env("FMSC_LOG_LEVEL", "INFO")}},
}
