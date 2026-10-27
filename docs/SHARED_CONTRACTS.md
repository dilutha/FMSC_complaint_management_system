# Shared contracts with Member B — **proposals awaiting agreement**

This machine had no existing FMSC repository and none of Member B's code. Member A therefore built the case module against the smallest interfaces it needs. Each one is marked below as **placeholder** (Member B replaces it) or **contract** (both sides depend on it and must agree before changing it).

## 1. User model and roles — contract

`apps/accounts/models.py` sets `AUTH_USER_MODEL = accounts.User`. This had to exist before the first migration, because Django cannot swap the user model later without resetting the database.

- **Role values the case module relies on:** `student`, `lecturer`, `case_admin`, `authority`, `management`, `system_admin`
- **Properties it uses:** `display_name`, `is_case_admin`, `is_management_viewer`, `is_authority_officer`, `can_submit_cases`
- **Authority membership:** stored as `cases.Authority.members` (M2M to User), not on the user model.

Member B may take ownership of the `accounts` app and add fields, as long as the values and properties above keep their meaning.

## 2. Authentication — placeholder

- **Backend:** DRF `TokenAuthentication` plus `SessionAuthentication` (CSRF enforced), configured centrally in `REST_FRAMEWORK`. The placeholder endpoints `/api/v1/auth/token|me|logout/` can be replaced, for example with JWT or university SSO.
- **Flutter:** implement `lib/integration/auth_session.dart` → `AuthSession`. Set `scheme` to `'Bearer'` for JWT. The API client calls `onUnauthorised()` on any 401. Delete `placeholder_sign_in_screen.dart` when the real login lands.

## 3. Notifications, audit, dashboards — contract (Django signals)

Defined in `apps/cases/signals.py`. They are sent **after commit**, with `sender=Case, case, actor, payload`. A receiver that fails is logged and doesn't roll back the case change.

| Signal | Expected consumer |
|---|---|
| `case_submitted` | Admin "new case" notification; audit log |
| `case_assigned` | Authority assignment notification; audit log |
| `case_status_changed` | Status-update notification; audit log; dashboard cache |
| `case_solved` | **Solved message to the submitter** (proposal requirement) |
| `case_resolution_verified` | Audit log; satisfaction reporting |
| `case_reopened` | Notify the assigned authority and admins |
| `case_escalated` | Escalation notice to admins and management |
| `case_deadline_changed` | Audit log |
| `case_update_added` | Notify the other party; audit log |

The case module keeps its own **domain history**: status history, assignment history, resolutions, deadline changes and escalations. These are part of the case record and feed the timeline. The generic audit log (who changed what, across every module) stays with Member B.

## 4. API conventions — contract

These are described in `docs/API.md`: the `/api/v1/` prefix, the error envelope, page-number pagination, and HTTP 404 for objects you can't see.

## 5. Status values — contract

These are listed in `docs/CASE_LIFECYCLE.md`. Dashboard measures map to them like this:

| Dashboard measure (proposal) | Query |
|---|---|
| Not attempted | `status = submitted` |
| Attempted | every other status |
| Open | not `closed` and not `rejected` |
| Not started | `status = assigned` |
| Age in days | `age_days`, or `now - created_at` |
| Urgent | `priority = urgent` (confirmed by an admin; the original request is in `requested_priority`) |

## 6. Flutter navigation — contract

`lib/features/cases/case_routes.dart` provides `CaseRoutes.myCases()`, `CaseRoutes.openSubmit(context)` and `CaseRoutes.openCase(context, id)`. A notification tap for a case calls `openCase`.

Wrap the app in `CaseScope(repository: ApiCaseRepository(apiClient), pickAttachments: pickAttachmentsFromDevice, …)`.

## 7. Open questions for Member B and the faculty

1. Confirm the status values and the two departures noted in CASE_LIFECYCLE.md.
2. Approve the verification window (7 days) and the reopen window (14 days).
3. Approve the deadline-policy values. None are seeded; administrators enter them in Django admin.
4. Choose the auth scheme: DRF token or JWT.
5. Decide who owns `Authority` and `Category` CRUD UIs beyond Django admin.
6. The official maroon has inconsistent published HEX and RGB values; see DESIGN_SYSTEM.md.
