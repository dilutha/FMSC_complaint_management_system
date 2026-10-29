-- =============================================================================
-- FMSC backend: read-only verification queries (changes nothing)
-- =============================================================================
-- Run in the Supabase SQL Editor after migrating. Expected results are noted.

-- 1. The Django role is least-privileged.
--    Expect: fmsc_app | t (can login) | f | f | f | f
SELECT rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls
FROM pg_roles
WHERE rolname = 'fmsc_app';

-- 2. Django's tables exist (catalog only, so this works as `postgres` even though
--    it cannot read fmsc_app's data). Migration status: `python manage.py check_database`.
--    Expect one row per Django app prefix: accounts, audit, auth, authtoken, cases,
--    django, notifications, suggestions.
SELECT split_part(c.relname, '_', 1) AS app_prefix, count(*) AS tables
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
GROUP BY 1
ORDER BY 1;

-- 3. Every table in `public`: owner, RLS, and whether the Data API roles can read it.
--    Expect: owner = fmsc_app, rls_enabled = t, anon_select = f, authenticated_select = f
SELECT c.relname                                            AS table_name,
       pg_get_userbyid(c.relowner)                          AS owner,
       c.relrowsecurity                                     AS rls_enabled,
       has_table_privilege('anon', c.oid, 'SELECT')          AS anon_select,
       has_table_privilege('authenticated', c.oid, 'SELECT') AS authenticated_select
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
ORDER BY c.relname;

-- 4. The audit log is protected by its trigger (created by Django migration
--    audit.0002_protect_audit_rows). Expect one row: audit_event_protect
SELECT tgname
FROM pg_trigger
WHERE tgrelid = 'public.audit_auditevent'::regclass AND NOT tgisinternal;
