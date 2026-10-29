# FMSC Complaint & Suggestion Management App

This app is for the Faculty of Management Studies and Commerce, University of Sri Jayewardenepura.

This repository contains two integrated modules.

**Member B's platform module:**
- authentication with expiring tokens and role-based permissions
- user and authority management
- notifications (in-app, with optional email copies)
- the append-only audit log
- the management dashboard and reports
- suggestion evaluation and implementation tracking
- the matching Flutter screens and the shared design system

See [docs/SUGGESTIONS.md](docs/SUGGESTIONS.md) and [docs/DASHBOARD_METRICS.md](docs/DASHBOARD_METRICS.md).

**Member A's core case-management module:**
- complaint submission
- case tracking and the progress timeline
- review and assignment
- the status lifecycle
- deadlines and escalation triggers
- duplicate detection
- resolution verification and reopening
- the related Flutter screens

```
backend/   Django 5.2 LTS + Django REST Framework (MTV), PostgreSQL
mobile/    Flutter app (case screens, USJ design system)
docs/      API, lifecycle, shared contracts with Member B, design system
```

## Backend

The backend runs on **Python 3.12**. Django 5.2 supports Python 3.10–3.13; Python 3.14 is not yet supported by this stack. The database is **Supabase-hosted PostgreSQL**, accessed by Django only. All commands below run from `backend/`, where `manage.py` lives.

### 1. Get the code

```bash
git clone <repository-url>
cd FMSC_complaint_management_system/backend
```

### 2. Create and activate the virtual environment

macOS or Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### 3. Install dependencies

```bash
pip install -r requirements-dev.txt    # runtime + pytest (use requirements.txt on servers)
pip check
```

`requirements.lock` records the exact versions last tested.

### 4. Configure the environment

```bash
cp .env.example .env    # Windows: Copy-Item .env.example .env
```

Edit `.env`:
- Set `DJANGO_SECRET_KEY`. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(50))"`.
- Set the Supabase values `DB_HOST`, `DB_USER` and `DB_PASSWORD`.

To obtain the Supabase values and create the `fmsc_app` role (one-time, per project), see **[backend/database/README.md](backend/database/README.md)**. `.env` is git-ignored; never commit it or put database credentials in the Flutter app.

### 5. Check the connection, then migrate

```bash
python manage.py check                # Django configuration
python manage.py check_database       # connection, SSL, role, pending migrations, Supabase exposure (no secrets printed)
python manage.py showmigrations
python manage.py migrate              # also locks Supabase's public Data API out of the tables
python manage.py seed_reference_data  # categories and authorities from the proposal
python manage.py seed_demo_users      # demo accounts for every role (development only)
python manage.py seed_demo_data       # optional: representative demo cases in every state
python manage.py createsuperuser      # optional: your own administrator account
```

### Demo accounts (development only)

`python manage.py seed_demo_users` creates or updates one account per role. It can be re-run safely and never creates duplicates. It refuses to run unless `DJANGO_DEBUG=true`, or unless `FMSC_ALLOW_DEMO_USERS=true` is set deliberately.

All demo accounts use the password **`Password@123`**. It is stored hashed (PBKDF2), like any other password.

> **This is a development-only password.** Never use it for real accounts, and never run `seed_demo_users` against production.

| Username | Role | Lands on | Can do |
|---|---|---|---|
| `demo_student` | Student | Student dashboard | Submit and track own complaints and suggestions |
| `demo_lecturer` | Lecturer | Lecturer dashboard | Same as a student |
| `demo_non_academic` | Non-academic staff | Non-academic staff dashboard | Same as a student |
| `demo_system_admin` | Admin | Admin dashboard | Read every case and post admin messages; user accounts, departments and audit log. Cannot change statuses or assign cases. |
| `demo_case_admin` | Case Administrator | Review queue | Review, assign to a department (with a message), change status (with a message), decide on suggestions |
| `demo_it` | IT Department | IT Department dashboard | Cases assigned to the IT Department only |
| `demo_maintenance` | Maintenance Department | Maintenance dashboard | Cases assigned to Maintenance only |
| `demo_exams` | Examination Unit | Examination Unit dashboard | Cases assigned to the Examination Unit only |
| `demo_deans_office` | Dean's Office | Dean's Office dashboard | Cases assigned to the Dean's Office only |
| `demo_management` | Faculty Management | Faculty overview | Read-only reports |

`python manage.py seed_demo_data` adds 9 representative cases (it can be re-run safely). They cover every state: new, under review, assigned to each of the four departments, in progress, resolved and closed, plus two suggestions. They go through the real workflow, so their history and notifications are genuine. Like the demo users, it runs only when `DJANGO_DEBUG=true`.


### 6. Run the server

```bash
python manage.py runserver            # http://127.0.0.1:8000
python manage.py runserver 0.0.0.0:8000   # if a phone or emulator must reach it (Android emulator uses http://10.0.2.2:8000/api/v1/)
```

- **API base:** http://127.0.0.1:8000/api/v1/
- **Swagger UI:** http://127.0.0.1:8000/api/docs/
- **ReDoc:** http://127.0.0.1:8000/api/redoc/
- **OpenAPI schema:** http://127.0.0.1:8000/api/schema/
- The API docs are public while `DJANGO_DEBUG=true`; production requires sign-in.
- **Printable management report:** http://localhost:8000/manage/report/. Sign in through `/admin/login/` with an administrator or management account.
- **Admin (reference data, routing rules, deadline policies, read-only case history):** http://localhost:8000/admin/

**CORS** is only needed for the Flutter web build. List the exact origins in `CORS_ALLOWED_ORIGINS`. While `DJANGO_DEBUG=true`, any `http://localhost:<port>` is also allowed, which covers `flutter run -d chrome`.

### Running against a local PostgreSQL instead of Supabase

Point `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` and `DB_NAME` at your server. Non-Supabase hosts default to `DB_SSLMODE=prefer`. For example, in `psql` as a superuser:

```sql
CREATE ROLE fmsc LOGIN PASSWORD '...';
CREATE DATABASE fmsc_cases OWNER fmsc;
```

### Scheduled processing (production)

Run the deadline processor every 15 minutes. It is idempotent.

```
*/15 * * * * cd /srv/fmsc/backend && .venv/bin/python manage.py process_case_deadlines
```

Also run the deadline reminders every hour. This job is idempotent too.

```
0 * * * * cd /srv/fmsc/backend && .venv/bin/python manage.py send_deadline_reminders
```

On Windows, create a Task Scheduler task that runs `.venv\Scripts\python.exe manage.py process_case_deadlines`.

### Tests

Tests **never** run against Supabase. Django's test runner creates and drops a whole database, and the settings refuse a Supabase host while testing.

```bash
cd backend
FMSC_DB_ENGINE=sqlite pytest     # quick, no database server needed (PostgreSQL-only tests are skipped)
DB_HOST=127.0.0.1 DB_PORT=5432 DB_USER=fmsc DB_PASSWORD=... DB_NAME=fmsc_cases pytest   # full suite on a local PostgreSQL
```

Variables set on the command line override the values in `.env`.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `DJANGO_SECRET_KEY must be set when DEBUG is false` | Create `.env` from `.env.example`, or set `DJANGO_DEBUG=true` for local work. |
| `ModuleNotFoundError: No module named 'django'` | The virtual environment isn't active: `source .venv/bin/activate`. |
| `ensurepip ... returned non-zero exit status` while creating the venv | Use Python 3.12 (`python3.12 -m venv .venv`), not 3.14. |
| Connection errors | Run `python manage.py check_database`; it explains the common Supabase errors. See also the troubleshooting table in [backend/database/README.md](backend/database/README.md). |
| `Set either DATABASE_URL or DB_HOST, not both` | Keep only one style in `.env`. |
| Sign-in says **"The server … did not respond in time"** or **"Cannot reach the server at …"** | The message names the address the app is calling. If it says `10.0.2.2` in a browser, the app was started before the address fix, or with the Android-emulator address. Stop it and run `flutter run -d chrome` again (a hot reload `r` is not enough; use `R` or restart). Confirm that `python manage.py runserver` is running. |
| Requests are slow | Each request logs a line such as `POST /api/v1/auth/token/ 200 1180ms db=4q/1036ms` (also visible as the `Server-Timing` header in the browser's network tab). Most of the time is network round trips to the Supabase region. Keep `DB_POOL=true`. |

## Mobile

You need Flutter 3.47 or newer (Dart 3.10 or newer); this was tested with Flutter 3.47.1 stable.

```bash
cd mobile
flutter pub get
flutter test
flutter run -d chrome    # web → http://127.0.0.1:8000 (Android emulator defaults to http://10.0.2.2:8000)
flutter run -d chrome --dart-define=API_TIMEOUT_SECONDS=30    # optional: change the 20 s request timeout
flutter test test/live/live_api_test.dart --dart-define=LIVE_API_BASE_URL=http://127.0.0.1:8000/api/v1/   # read-only check against a running backend
flutter run --dart-define=API_BASE_URL=http://<host>:8000/api/v1/   # any other backend address
```

## Documentation

- [backend/database/README.md](backend/database/README.md): Supabase setup, connection options, SQL scripts and troubleshooting
- [docs/API.md](docs/API.md): endpoints, errors, pagination and attachments
- [docs/CASE_LIFECYCLE.md](docs/CASE_LIFECYCLE.md): statuses, transitions and the closure and deadline policy
- [docs/SHARED_CONTRACTS.md](docs/SHARED_CONTRACTS.md): interfaces agreed (or to be agreed) with Member B
- [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md): official USJ colours and sources, contrast checks, platform tokens and components, and the UX principles used
- [docs/DASHBOARD_METRICS.md](docs/DASHBOARD_METRICS.md): the definition of every dashboard figure
- [docs/SUGGESTIONS.md](docs/SUGGESTIONS.md): suggestion statuses and how they map to the case lifecycle
