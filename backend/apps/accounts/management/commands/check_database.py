"""Diagnose the database connection without printing secrets.

    python manage.py check_database

Reports the configured target (never the password), whether the connection
uses SSL, the server version and role, unapplied migrations and, on Supabase,
tables that the public Data API could reach. Exits with an error and a
specific hint when the connection fails.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connection
from django.db.migrations.executor import MigrationExecutor

from config.database import describe

HINTS = (
    ("password authentication failed", "Check DB_USER/DB_PASSWORD (or the password in DATABASE_URL). "
     "Special characters in DATABASE_URL must be URL-encoded."),
    ("tenant or user not found", "For the Supabase pooler, DB_USER must be <role>.<project-ref>, "
     "and DB_HOST must be the pooler host shown in Connect → Session pooler."),
    ("could not translate host name", "The host name is wrong or not resolvable. Copy DB_HOST from the "
     "Supabase dashboard (Connect button)."),
    ("network is unreachable", "The direct connection (db.<ref>.supabase.co) is IPv6-only. On an IPv4 "
     "network use the Session pooler host instead (see backend/database/README.md)."),
    ("timeout expired", "The server did not answer within DB_CONNECT_TIMEOUT seconds. Check the host, "
     "port, firewall/VPN and that the Supabase project is not paused."),
    ("ssl", "SSL negotiation failed. Supabase needs DB_SSLMODE=require (or verify-full with "
     "DB_SSLROOTCERT pointing at the downloaded CA certificate)."),
    ("does not exist", "The database or role does not exist. On Supabase the database is normally 'postgres'."),
)


class Command(BaseCommand):
    help = "Check the database connection, SSL, migrations and Supabase exposure (prints no secrets)."

    def handle(self, *args, **options):
        info = describe(connection.settings_dict)
        self.stdout.write("Configured database:")
        for key, value in info.items():
            self.stdout.write(f"  {key:13} {value}")

        try:
            connection.ensure_connection()
        except OperationalError as exc:
            message = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
            hint = next((h for needle, h in HINTS if needle in message.lower()), None)
            raise CommandError(f"Connection failed: {message}" + (f"\nHint: {hint}" if hint else "")) from None

        if connection.vendor == "postgresql":
            self._postgres_details(info)
        else:
            self.stdout.write(self.style.WARNING("Connected to SQLite (local tests only, not PostgreSQL)."))

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            self.stdout.write(self.style.WARNING(f"Unapplied migrations: {len(pending)}. Run: python manage.py migrate"))
        else:
            self.stdout.write(self.style.SUCCESS("All migrations are applied."))
        self.stdout.write(self.style.SUCCESS("Database connection OK."))

    def _postgres_details(self, info):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('server_version'), current_user, current_database()")
            version, user, database = cursor.fetchone()
            # Encryption of OUR connection comes from libpq (PQsslInUse). pg_stat_ssl
            # describes the server's incoming connection, which behind a pooler
            # (Supavisor) is the pooler's own link, not the client's.
            ssl_on = connection.connection.pgconn.ssl_in_use
            cursor.execute("SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            row = cursor.fetchone()
            ssl_version = row[1] if row and row[0] else None
            # Supabase projects have the Data API roles anon/authenticated.
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')")
            has_data_api_roles = cursor.fetchone()[0]
        self.stdout.write(f"  server        PostgreSQL {version}")
        self.stdout.write(f"  connected as  {user} on database {database}")
        if ssl_on:
            detail = ssl_version or ("client to pooler" if ".pooler." in (info["host"] or "") else "client")
            self.stdout.write(self.style.SUCCESS(f"  ssl           in use ({detail})"))
        elif info["supabase"]:
            raise CommandError("The connection to Supabase is not encrypted. Set DB_SSLMODE=require.")
        else:
            self.stdout.write(self.style.WARNING("  ssl           not in use (acceptable only for a local server)"))
        if info["supabase"] or has_data_api_roles:
            self._supabase_exposure()

    def _supabase_exposure(self):
        """Tables in `public` are served by Supabase's Data API to the public anon key
        unless RLS is enabled and anon/authenticated have no privileges."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.relname,
                       c.relrowsecurity,
                       has_table_privilege('anon', c.oid, 'SELECT')
                         OR has_table_privilege('authenticated', c.oid, 'SELECT')
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                ORDER BY c.relname
            """)
            rows = cursor.fetchall()
        exposed = [name for name, rls, api_select in rows if not rls or api_select]
        if exposed:
            self.stdout.write(self.style.ERROR(
                f"  data api      {len(exposed)} public table(s) are reachable or lack RLS, e.g. {exposed[:5]}. "
                "Run backend/database/20_harden_data_api.sql after migrating."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"  data api      {len(rows)} public tables: RLS on, no anon access"))
