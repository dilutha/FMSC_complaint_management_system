"""Keep Supabase's public Data API away from Django's tables.

After every `migrate`, when the database has Supabase's Data API roles
(`anon`, `authenticated`), this applies the statements in
backend/database/20_harden_data_api.sql: revoke their privileges, stop default
grants and enable row level security on every table the connected role owns.
Running it automatically means a newly migrated table can never be left
exposed because someone forgot a manual step. Disable with
FMSC_SUPABASE_HARDEN=false (not recommended).
"""
import logging
from pathlib import Path

from django.conf import settings
from django.db import connections

logger = logging.getLogger("apps.accounts.supabase")

SQL_FILE = Path(settings.BASE_DIR) / "database" / "20_harden_data_api.sql"


def has_data_api_roles(connection) -> bool:
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
        return cursor.fetchone()[0] == 2


def harden(connection) -> bool:
    """Apply the hardening SQL. Returns True when it ran."""
    if not has_data_api_roles(connection):
        return False
    with connection.cursor() as cursor:
        cursor.execute(SQL_FILE.read_text(encoding="utf-8"))
    logger.info("Supabase Data API hardening applied to %s.", connection.alias)
    return True


def harden_after_migrate(sender, using="default", **kwargs):
    # post_migrate fires once per app; every table exists by then, so run once.
    if sender.label != "accounts" or not getattr(settings, "FMSC_SUPABASE_HARDEN", True):
        return
    harden(connections[using])
