"""Database configuration rules (config/database.py), the connection check
command and the Supabase Data API hardening. Synthetic values only."""
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import connection

from config.database import build_databases, describe

SUPA_DIRECT = "db.abcdefghijklmnopqrst.supabase.co"
SUPA_POOLER = "aws-0-ap-south-1.pooler.supabase.com"


def build(env, *, testing=False, allow_sqlite=False):
    return build_databases(env, sqlite_path="/tmp/x.sqlite3", allow_sqlite=allow_sqlite, testing=testing)["default"]


class TestPrecedence:
    def test_separate_db_variables(self):
        db = build({"DB_NAME": "postgres", "DB_USER": "fmsc_app", "DB_PASSWORD": "pw", "DB_HOST": SUPA_DIRECT,
                    "DB_PORT": "5432"})
        assert (db["NAME"], db["USER"], db["PASSWORD"], db["HOST"], db["PORT"]) == (
            "postgres", "fmsc_app", "pw", SUPA_DIRECT, "5432")
        assert db["ENGINE"] == "django.db.backends.postgresql"

    def test_database_url_with_encoded_password_and_query_options(self):
        db = build({"DATABASE_URL": f"postgresql://fmsc_app:p%40ss%2Fw0rd@{SUPA_DIRECT}:5432/postgres"
                                    "?sslmode=verify-full&sslrootcert=/certs/prod-ca.crt"})
        assert db["PASSWORD"] == "p@ss/w0rd"
        assert db["OPTIONS"]["sslmode"] == "verify-full"
        assert db["OPTIONS"]["sslrootcert"] == "/certs/prod-ca.crt"

    def test_database_url_and_separate_variables_together_is_an_error(self):
        with pytest.raises(ImproperlyConfigured, match="either DATABASE_URL or DB_HOST"):
            build({"DATABASE_URL": "postgresql://u:p@localhost/db", "DB_HOST": "other"})

    def test_legacy_postgres_variables_still_work(self):
        db = build({"POSTGRES_DB": "fmsc_cases", "POSTGRES_USER": "fmsc", "POSTGRES_HOST": "127.0.0.1",
                    "POSTGRES_PORT": "54329"})
        assert (db["NAME"], db["HOST"], db["PORT"]) == ("fmsc_cases", "127.0.0.1", "54329")

    def test_db_variables_win_over_legacy_names(self):
        assert build({"DB_HOST": "new", "POSTGRES_HOST": "old"})["HOST"] == "new"

    def test_non_postgres_url_rejected(self):
        with pytest.raises(ImproperlyConfigured):
            build({"DATABASE_URL": "mysql://u:p@h/db"})


class TestEngine:
    def test_sqlite_only_for_development_and_tests(self):
        with pytest.raises(ImproperlyConfigured, match="SQLite"):
            build({"DB_ENGINE": "django.db.backends.sqlite3"})
        assert build({"DB_ENGINE": "sqlite"}, allow_sqlite=True)["ENGINE"] == "django.db.backends.sqlite3"

    def test_legacy_sqlite_switch_wins_over_env_file_engine(self):
        env = {"FMSC_DB_ENGINE": "sqlite", "DB_ENGINE": "django.db.backends.postgresql"}
        assert build(env, allow_sqlite=True)["ENGINE"] == "django.db.backends.sqlite3"

    def test_unknown_engine(self):
        with pytest.raises(ImproperlyConfigured, match="Unsupported"):
            build({"DB_ENGINE": "django.db.backends.mysql"})


class TestSupabaseRules:
    def test_supabase_defaults_to_required_ssl_and_refuses_weaker(self):
        assert build({"DB_HOST": SUPA_DIRECT, "DB_USER": "fmsc_app"})["OPTIONS"]["sslmode"] == "require"
        for weak in ("disable", "allow", "prefer"):
            with pytest.raises(ImproperlyConfigured, match="must use DB_SSLMODE"):
                build({"DB_HOST": SUPA_DIRECT, "DB_SSLMODE": weak})

    def test_local_server_defaults_to_prefer(self):
        assert build({"DB_HOST": "localhost"})["OPTIONS"]["sslmode"] == "prefer"

    def test_verify_modes_need_a_root_certificate(self):
        with pytest.raises(ImproperlyConfigured, match="DB_SSLROOTCERT"):
            build({"DB_HOST": SUPA_DIRECT, "DB_SSLMODE": "verify-full"})

    def test_pooler_needs_project_ref_in_user_name(self):
        with pytest.raises(ImproperlyConfigured, match="<role>.<project-ref>"):
            build({"DB_HOST": SUPA_POOLER, "DB_USER": "fmsc_app"})
        assert build({"DB_HOST": SUPA_POOLER, "DB_USER": "fmsc_app.abcdefghijklmnopqrst"})["USER"].endswith("rst")

    def test_connection_pool_is_on_by_default_outside_tests(self):
        db = build({"DB_HOST": SUPA_POOLER, "DB_USER": "fmsc_app.ref", "DB_PORT": "5432"})
        assert db["OPTIONS"]["pool"] == {"min_size": 1, "max_size": 4, "timeout": 15, "max_idle": 120,
                                         "max_lifetime": 900}
        assert db["CONN_MAX_AGE"] == 0  # Django requires this with pooling
        assert db["CONN_HEALTH_CHECKS"] is False  # opt-in: costs a round trip per request
        assert "prepare_threshold" not in db["OPTIONS"]

    def test_pool_can_be_tuned_or_disabled(self):
        tuned = build({"DB_POOL_MAX_SIZE": "8", "DB_POOL_CHECK": "true"})
        assert tuned["OPTIONS"]["pool"]["max_size"] == 8 and tuned["CONN_HEALTH_CHECKS"] is True
        plain = build({"DB_POOL": "false"})
        assert "pool" not in plain["OPTIONS"] and plain["CONN_MAX_AGE"] == 60 and plain["CONN_HEALTH_CHECKS"] is True

    def test_tests_do_not_use_the_pool(self):
        assert "pool" not in build({"DB_HOST": "localhost"}, testing=True)["OPTIONS"]

    def test_transaction_pooler_disables_prepared_statements_and_persistence(self):
        db = build({"DB_HOST": SUPA_POOLER, "DB_USER": "fmsc_app.ref", "DB_PORT": "6543"})
        assert db["OPTIONS"]["prepare_threshold"] is None
        assert db["CONN_MAX_AGE"] == 0 and db["DISABLE_SERVER_SIDE_CURSORS"] is True

    def test_tests_never_run_against_supabase(self):
        with pytest.raises(ImproperlyConfigured, match="Tests must not run"):
            build({"DB_HOST": SUPA_DIRECT}, testing=True)

    def test_connect_timeout_and_validation(self):
        assert build({})["OPTIONS"]["connect_timeout"] == 10
        assert build({"DB_CONNECT_TIMEOUT": "5"})["OPTIONS"]["connect_timeout"] == 5
        with pytest.raises(ImproperlyConfigured):
            build({"DB_CONNECT_TIMEOUT": "soon"})
        with pytest.raises(ImproperlyConfigured):
            build({"DB_SSLMODE": "maybe"})
        with pytest.raises(ImproperlyConfigured):
            build({"DB_POOL_MODE": "bouncy"})

    def test_describe_never_includes_the_password(self):
        summary = describe(build({"DB_HOST": SUPA_DIRECT, "DB_PASSWORD": "top-secret-value"}))
        assert "top-secret-value" not in str(summary)
        assert summary["password_set"] is True and summary["supabase"] is True
        assert summary["django_pool"] == "on (max 4)"


@pytest.mark.django_db
class TestCheckDatabaseCommand:
    def test_reports_connection_without_secrets(self):
        out = StringIO()
        call_command("check_database", stdout=out)
        text = out.getvalue()
        assert "Database connection OK." in text
        password = connection.settings_dict.get("PASSWORD")
        if password:
            assert password not in text


@pytest.mark.django_db
class TestApiDocsAndCors:
    def test_docs_routes_resolve(self, api, student):
        for url in ("/api/schema/", "/api/docs/", "/api/redoc/"):
            assert api(student).get(url).status_code == 200

    def test_production_settings_lock_docs_and_cors(self):
        """Load settings as production would (DEBUG off) in a fresh interpreter."""
        import json
        import os
        import subprocess
        import sys

        code = (
            "import json, django; from django.conf import settings; "
            "print(json.dumps({'docs': settings.SPECTACULAR_SETTINGS['SERVE_PERMISSIONS'], "
            "'cors_regexes': settings.CORS_ALLOWED_ORIGIN_REGEXES, 'cors': settings.CORS_ALLOWED_ORIGINS, "
            "'ssl_redirect': settings.SECURE_SSL_REDIRECT}))"
        )
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DB_", "POSTGRES_", "DATABASE_", "FMSC_"))}
        env.update(DJANGO_SETTINGS_MODULE="config.settings", DJANGO_DEBUG="false",
                   DJANGO_SECRET_KEY="test-only-production-like-key", CORS_ALLOWED_ORIGINS="https://fmsc.example.lk")
        result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True,
                                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        prod = json.loads(result.stdout.strip().splitlines()[-1])
        assert prod["docs"] == ["rest_framework.permissions.IsAuthenticated"]
        assert prod["cors_regexes"] == [] and prod["cors"] == ["https://fmsc.example.lk"]
        assert prod["ssl_redirect"] is True

    def test_cors_allows_only_configured_origins(self, client, settings):
        settings.CORS_ALLOWED_ORIGINS = ["https://fmsc.example.lk"]
        settings.CORS_ALLOWED_ORIGIN_REGEXES = []
        ok = client.options("/api/v1/auth/token/", HTTP_ORIGIN="https://fmsc.example.lk",
                            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        bad = client.options("/api/v1/auth/token/", HTTP_ORIGIN="https://evil.example",
                             HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
        assert ok["Access-Control-Allow-Origin"] == "https://fmsc.example.lk"
        assert "Access-Control-Allow-Origin" not in bad


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="Supabase hardening is PostgreSQL-only")
def test_supabase_hardening_revokes_data_api_access():
    """Simulates Supabase's anon/authenticated roles inside the test transaction
    (CREATE ROLE is transactional, so nothing outlives the test)."""
    from apps.accounts.supabase import harden

    with connection.cursor() as cursor:
        cursor.execute("SELECT rolcreaterole OR rolsuper FROM pg_roles WHERE rolname = current_user")
        if not cursor.fetchone()[0]:
            pytest.skip("test database user cannot create roles")
        cursor.execute("SELECT count(*) FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
        if cursor.fetchone()[0] == 0:
            cursor.execute("CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN")
        cursor.execute("GRANT SELECT ON cases_case, accounts_user TO anon, authenticated")
        cursor.execute("SELECT has_table_privilege('anon', 'cases_case', 'SELECT')")
        assert cursor.fetchone()[0] is True

        assert harden(connection) is True

        cursor.execute("""
            SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND (NOT c.relrowsecurity OR has_table_privilege('anon', c.oid, 'SELECT')
                   OR has_table_privilege('authenticated', c.oid, 'SELECT'))
        """)
        assert cursor.fetchone()[0] == 0
    # The owner (Django) is unaffected by RLS.
    from apps.accounts.models import User

    User.objects.create_user("rls.check", password="Synthetic-pass-123")
    assert User.objects.filter(username="rls.check").exists()
