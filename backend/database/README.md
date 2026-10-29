# Database: Supabase PostgreSQL

The architecture is **Flutter app → Django REST API → Supabase PostgreSQL**.

- Django connects to the database through its ORM, using the `psycopg` 3 driver.
- The Flutter app never connects to Supabase directly. It holds no database password, anon key or service-role key.
- Supabase Auth, Storage and the client libraries are **not used**. Django handles authentication (expiring tokens), authorisation, validation and file storage. Adding Supabase Auth would create a second, competing user system.

## Where the schema comes from

**Django migrations are the only source of the application schema.** Every table, constraint, index and the audit-log trigger is created by `python manage.py migrate`. There are 31 tables in `public`: the tables for `accounts`, `cases`, `audit`, `notifications` and `suggestions`, plus Django's own (auth, sessions, admin, tokens, migrations).

The SQL files in this folder **do not create application tables**. They only cover what Django can't manage:

| Order | File | Run as | When | What it does |
|---|---|---|---|---|
| 1 | `10_create_app_role.sql` | `postgres` in the Supabase SQL Editor | Once per Supabase project, before the first migration | Creates the least-privilege `fmsc_app` role and grants it CONNECT, plus USAGE and CREATE on the `public` schema |
| 2 | *(Django)* `python manage.py migrate` | `fmsc_app`, through Django | After every model change | Creates and updates all tables, then **automatically applies file 3** |
| 3 | `20_harden_data_api.sql` | the table owner (`fmsc_app`) | Applied automatically after each migration; can also be run manually | Revokes `anon` and `authenticated` privileges and enables row level security on every table |
| 4 | `90_verify.sql` | `postgres` or `fmsc_app` | Any time | Read-only checks with the expected results noted |

Because none of the files create tables, running them in any order can't produce a conflicting schema.

Nothing here drops or resets anything.

Entities such as "departments" and "complaint comments" from the original brief already exist in the models:
- departments: `Authority.unit` and `User.department`;
- comments: `CaseUpdate`;
- resolutions: `CaseResolution`;
- suggestion evaluation and progress: `apps.suggestions`.

No extra tables were invented.

## Why the Data API hardening matters

Supabase automatically publishes the `public` schema as a REST and GraphQL API that anyone with the project's **anon key** can call. That key is not secret: it is meant to be embedded in client apps.

Tables that Django creates in `public` would therefore be readable by anyone with the anon key unless two things are true:
- `anon` and `authenticated` have no privileges on them;
- row level security (RLS) is enabled.

`20_harden_data_api.sql` makes both true. Django is unaffected, because a table's **owner** is not subject to its RLS.

After every `migrate`, `apps/accounts/supabase.py` applies the same SQL to any database that has Supabase's roles, so a new table can't be left exposed by forgetting a manual step. `python manage.py check_database` reports any table that is still exposed.

If the Data API is not used at all, you can also turn it off in Dashboard → Project Settings → Data API.

## Which Supabase connection to use

Supabase offers three connection types (Dashboard → **Connect**).

| Option | Host | Port | User name | Use it for |
|---|---|---|---|---|
| **Session pooler** | `aws-<n>-<region>.pooler.supabase.com` | 5432 | `fmsc_app.<project-ref>` | **Local development** (works on IPv4 home and university networks), and long-running servers on IPv4 |
| Direct connection | `db.<project-ref>.supabase.co` | 5432 | `fmsc_app` | Long-running servers with IPv6, or with the paid IPv4 add-on |
| Transaction pooler | `aws-<n>-<region>.pooler.supabase.com` | 6543 | `fmsc_app.<project-ref>` | Serverless or very many short-lived processes only |

**For local Django development, use the Session pooler.**
- The direct connection is IPv6-only by default, and many networks in Sri Lanka are IPv4-only.
- The session pooler behaves like a normal PostgreSQL connection, so Django features such as server-side cursors and persistent connections keep working.

**Transaction mode** (port 6543) doesn't support prepared statements, cursors held between transactions, or session state. When `DB_PORT=6543` (or `DB_POOL_MODE=transaction`), `config/database.py` turns off psycopg's prepared statements (`prepare_threshold=None`), server-side cursors and persistent connections.

**SSL:**
- Supabase hosts default to `sslmode=require`, and weaker modes are refused.
- For certificate verification, download the CA certificate from Dashboard → Database settings and set `DB_SSLMODE=verify-full` and `DB_SSLROOTCERT=/path/to/prod-ca-2021.crt`.

Sources:
- [Connect to your database](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Hardening the Data API](https://supabase.com/docs/guides/api/hardening-data-api)
- [Postgres roles](https://supabase.com/docs/guides/database/postgres/roles)

## Connection pooling and latency

Opening a connection to a hosted database means a TCP + TLS handshake and a login over the internet. On 29 October 2026, from Sri Lanka over a mobile hotspot to the `eu-north-1` (Stockholm) Session pooler, this measured **3.7 s**, and each query round trip measured **220–300 ms**.

Django's development server handles each request in a new thread, so ordinary persistent connections are never reused there: every request paid the full 3.7 s.

`DB_POOL=true` (the default outside tests) uses Django's psycopg connection pool. One small pool (`DB_POOL_MAX_SIZE`, default 4) is shared by all threads. Measured on the same network, before → after:

| Request | Before | After |
|---|---|---|
| Login | 4.7–5.4 s | 1.2–1.3 s |
| Case list | 2.7 s | 0.6 s |

The remaining time is mostly query round trips. A Supabase project in a nearer region, for example `ap-south-1` (Mumbai) or `ap-southeast-1` (Singapore), would cut each round trip substantially. The region is fixed when a project is created.

## Settings and their precedence

`config/database.py` builds Django's `DATABASES` setting from the environment.

1. **Engine:** `FMSC_DB_ENGINE=sqlite` (tests only) wins. Otherwise `DB_ENGINE` is used, defaulting to PostgreSQL.
2. **Connection:** either `DATABASE_URL`, or `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` and `DB_PORT`. Setting both is an error. The older `POSTGRES_*` names are still accepted as fallbacks.
3. **Options:** `DB_SSLMODE`, `DB_SSLROOTCERT`, `DB_CONNECT_TIMEOUT` (default 10 s), `DB_CONN_MAX_AGE` (default 60 s) and `DB_POOL_MODE`. A value in the `DATABASE_URL` query string wins.

Safety rules:
- A Supabase pooler host requires the user name to be `<role>.<project-ref>`.
- Tests are refused if they would run against a Supabase host. Django's test runner creates and drops an entire database.

## First-time setup for a new Supabase project

1. **Create the role.** In Dashboard → SQL Editor, paste and run `10_create_app_role.sql`.
2. **Set its password.** In the SQL Editor, run the following. Don't save it as a snippet, and use a long random password, for example from `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
   ```sql
   ALTER ROLE fmsc_app WITH LOGIN PASSWORD '<long random password>';
   ```
3. **Get the connection details.** In Dashboard → **Connect** → **Session pooler**, copy the host and your project ref. The user is `fmsc_app.<project-ref>`.
4. **Fill in `backend/.env`.** Copy `.env.example` and set `DB_HOST`, `DB_USER` and `DB_PASSWORD`.
5. **Check the connection.**
   ```bash
   python manage.py check_database
   ```
   You should see `ssl in use`, `connected as fmsc_app` and the count of unapplied migrations.
6. **Migrate, then check again.**
   ```bash
   python manage.py migrate
   python manage.py check_database
   ```
   The second run should say `RLS on, no anon access` and `All migrations are applied`.
7. **Optionally verify in SQL.** Run `90_verify.sql` in the SQL Editor.

**Both team members** connect with the same `fmsc_app` credentials. Share them through a password manager, never through Git, chat or email.

The password must never appear in the Flutter app.

## Viewing data in the Supabase Table Editor

The dashboard runs as `postgres`, which cannot read tables owned by `fmsc_app`. This is deliberate: complaint data is private.

If an administrator needs to browse the tables in the dashboard, they can grant it explicitly. Remove the grant when it is no longer needed.

```sql
GRANT fmsc_app TO postgres;      -- allow
REVOKE fmsc_app FROM postgres;   -- remove again
```

## Production

- Use a separate Supabase project, or at least a separate role and password.
- Set `DJANGO_DEBUG=false`, which turns on secure cookies, HTTPS redirect and HSTS, and requires sign-in for the API docs.
- Use the direct connection or a dedicated pooler from the server.
- Prefer `sslmode=verify-full`.
- Never use `service_role` keys or the `postgres` password in the application.
- Attachments are stored on the Django server's private disk (`FMSC_PRIVATE_MEDIA_ROOT`), not in Supabase Storage, so the server needs persistent storage.

## Troubleshooting

`python manage.py check_database` prints a hint for each of these errors.

| Error | Cause and fix |
|---|---|
| `Tenant or user not found` | Pooler user name without the project ref. Use `fmsc_app.<project-ref>`. |
| `password authentication failed` | Wrong password, or an un-encoded special character in `DATABASE_URL`. Reset it with `ALTER ROLE`. |
| `Network is unreachable` / `could not translate host name` | The direct host is IPv6-only. Use the Session pooler host. |
| `timeout expired` | Wrong host or port, a firewall or VPN, or the free-tier project is paused (resume it in the dashboard). |
| `permission denied for schema public` during `migrate` | `10_create_app_role.sql` was not run, or Django connected as a different role. |
| `permission denied for table …` when Django runs | The tables were created by another role (for example `postgres`). One role must own and use the tables. Contact the team before changing ownership. |
| `Tests must not run against a Supabase database` | Run tests with `FMSC_DB_ENGINE=sqlite pytest`, or against a local PostgreSQL. |
| `prepared statement "_pg3_0" already exists` | You are on the transaction pooler (port 6543) without `DB_POOL_MODE=transaction`. Use port 5432, or set the mode. |
