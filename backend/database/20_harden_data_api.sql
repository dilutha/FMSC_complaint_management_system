-- =============================================================================
-- FMSC backend: close the Supabase Data API over Django's tables
-- =============================================================================
-- Run as:  the role that OWNS the tables (normally `fmsc_app`, i.e. the same
--          role Django connects with). Django runs these same statements
--          automatically after every `migrate` (apps/accounts/supabase.py), so
--          this file is for review, manual re-application and auditing.
-- When:    after `python manage.py migrate`. Idempotent; safe to re-run.
--
-- Background: Supabase publishes the `public` schema through its auto-generated
-- REST/GraphQL Data API, using the public `anon` key and the `authenticated`
-- role. The FMSC Flutter app never talks to Supabase directly: every request
-- goes through the Django API, which enforces roles and case visibility.
-- These statements make sure the Data API cannot read or change application
-- data, even if someone obtains the project's anon key:
--   1. revoke every privilege anon/authenticated hold on our objects;
--   2. stop future objects from being granted to them by default;
--   3. enable row level security (with no policies = deny) as defence in depth.
-- Django is unaffected: the owner of a table is not subject to its RLS.
-- =============================================================================

REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES    FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated;

DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND NOT c.relrowsecurity
          AND pg_has_role(current_user, c.relowner, 'USAGE')
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.relname);
    END LOOP;
END
$$;
