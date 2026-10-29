-- =============================================================================
-- FMSC backend: least-privilege database role for Django (run ONCE per project)
-- =============================================================================
-- Run in: Supabase Dashboard -> SQL Editor, as the default `postgres` user.
-- Before:  the first `python manage.py migrate`.
-- Safe to re-run: every statement is idempotent.
--
-- Why a separate role instead of `postgres`:
--   * It is not a superuser, cannot create roles or databases and does not
--     bypass row level security.
--   * Supabase's default privileges grant tables created by `postgres` to the
--     public Data API roles (anon, authenticated). Tables created by this role
--     are not granted to them automatically.
--   * Django creates and therefore OWNS every table it manages, so it keeps
--     working when row level security is enabled (owners are not subject to RLS
--     unless FORCE ROW LEVEL SECURITY is set, which this project never does).
--
-- This script never stores a password. After running it, set one in the SQL
-- Editor (do not save that statement anywhere):
--
--     ALTER ROLE fmsc_app WITH LOGIN PASSWORD '<long random password>';
--
-- Then connect Django as `fmsc_app` (direct connection) or
-- `fmsc_app.<project-ref>` (Supavisor pooler). See backend/database/README.md.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fmsc_app') THEN
        CREATE ROLE fmsc_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END
$$;

-- Note: Supabase's `postgres` user is not a superuser, so it cannot alter the
-- SUPERUSER/BYPASSRLS attributes afterwards; 90_verify.sql checks them instead.

-- Django needs to connect, and to create its tables, sequences, indexes and the
-- audit-protection trigger function in the `public` schema.
GRANT CONNECT ON DATABASE postgres TO fmsc_app;
GRANT USAGE, CREATE ON SCHEMA public TO fmsc_app;

-- Guard rails for runaway queries. Migrations in this project are small.
ALTER ROLE fmsc_app SET statement_timeout = '60s';
ALTER ROLE fmsc_app SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE fmsc_app SET search_path = public;
