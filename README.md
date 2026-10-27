# FMSC Complaint & Suggestion Management App

This app is for the Faculty of Management Studies and Commerce, University of Sri Jayewardenepura.

This repository currently contains **Member A's core case-management module**:
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

The backend needs Python 3.12 and PostgreSQL (16 or newer).

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate        # Windows (use bin/activate on Linux/macOS)
pip install -r requirements.txt
cp .env.example .env                                   # then set real values; never commit .env
```

Create the database. In `psql` as a superuser, run:

```sql
CREATE ROLE fmsc LOGIN PASSWORD '...';
CREATE DATABASE fmsc_cases OWNER fmsc;
```

Then apply migrations and start the server:

```bash
python manage.py migrate
python manage.py seed_reference_data      # categories and authorities from the proposal
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

- **Swagger UI:** http://localhost:8000/api/docs/
- **Admin (reference data, routing rules, deadline policies, read-only case history):** http://localhost:8000/admin/

### Scheduled processing (production)

Run the deadline processor every 15 minutes. It is idempotent.

```
*/15 * * * * cd /srv/fmsc/backend && .venv/bin/python manage.py process_case_deadlines
```

On Windows, create a Task Scheduler task that runs `.venv\Scripts\python.exe manage.py process_case_deadlines`.

### Tests

```bash
cd backend
pytest                                      # against PostgreSQL (POSTGRES_* env vars)
FMSC_DB_ENGINE=sqlite pytest                # local-only fallback when no PostgreSQL credentials are available
```

## Mobile

```bash
cd mobile
flutter pub get
flutter test
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1/   # Android emulator → local backend
```

## Documentation

- [docs/API.md](docs/API.md): endpoints, errors, pagination and attachments
- [docs/CASE_LIFECYCLE.md](docs/CASE_LIFECYCLE.md): statuses, transitions and the closure and deadline policy
- [docs/SHARED_CONTRACTS.md](docs/SHARED_CONTRACTS.md): interfaces agreed (or to be agreed) with Member B
- [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md): official USJ colours and sources, contrast checks and the UX principles used
