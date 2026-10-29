# Shared contracts between Member A (cases) and Member B (platform)

Member A wrote the original version of this file before Member B's code existed, and marked each interface as a **placeholder** or a **contract**. This version records:
- what Member B implemented against each one;
- the decisions Member B took where Member A asked a question (**Member A to confirm**);
- what Member B asks of Member A.

## 1. User model and roles: contract (unchanged)

`accounts.User` and the role values `student`, `lecturer`, `case_admin`, `authority`, `management` and `system_admin` are unchanged. **No migration changes the shared user table.**

The properties the case module relies on keep their meaning: `display_name`, `is_case_admin`, `is_management_viewer`, `is_authority_officer` and `can_submit_cases`.

Member B added **capability properties** to the same model. They are the single definition of platform permissions:

| Property | True for |
|---|---|
| `can_view_dashboard` | case admin, system admin, management |
| `can_evaluate_suggestions` | case admin, system admin |
| `can_manage_authorities` | case admin, system admin |
| `can_manage_users` | system admin |
| `can_view_audit_log` | system admin |

Authority membership is still `cases.Authority.members`. Because membership is what grants access to case data, the user-management API only allows authority officers and administrators to be members. Changing a user's role to anything else removes their memberships.

## 2. Authentication: implemented

- **Decision (Member A to confirm):** keep DRF tokens rather than switching to JWT. The `Authorization: Token <key>` header and the `{token, user}` login response are unchanged, so Member A's API client works as before.
- Tokens now **expire** (`FMSC_TOKEN_TTL_HOURS`, default 12). The backend uses `apps.accounts.authentication.ExpiringTokenAuthentication`. An expired token returns 401, and Member A's `ApiClient` already calls `session.onUnauthorised()` when that happens.
- Users can sign in with their username or email.
- **Flutter:** `PlatformAuthSession` implements the shared `AuthSession` interface. Tokens are kept in secure storage (Keychain or Keystore). `placeholder_sign_in_screen.dart` has been deleted, as Member A requested. `InMemoryAuthSession` is kept because Member A's tests use it.

## 3. Notifications, audit and dashboards: implemented

All three consume Member A's signals, so **no case-module code was changed**.

| Signal | Notification | Audit action |
|---|---|---|
| `case_submitted` | Confirmation to the submitter; "new case" to administrators | `case.submitted` |
| `case_assigned` | Members of the assigned unit | `case.assigned` / `case.reassigned` |
| `case_status_changed` | Submitter (review, information request with reason, assigned, in progress, closed, rejected with reason) | `case.status_changed` |
| `case_solved` | Submitter: "solved, please confirm" (the proposal requirement) | covered by the status change |
| `case_resolution_verified` | The unit, when the fix is confirmed | `case.resolution_verified` |
| `case_reopened` | The unit and administrators; the submitter too if staff reopened it | covered by the status change |
| `case_escalated` | The unit and administrators; management from level 2 | `case.escalated` |
| `case_deadline_changed` | – | `case.deadline_changed` |
| `case_update_added` | The other party. Internal notes notify nobody. | `case.update_added` (no comment text) |

Delivery rules:
- **Duplicates.** Each event has a deterministic key (`apps/audit/event_refs.py`), and unique constraints make a repeated delivery a no-op.
- **Actor.** The person who acted is never notified of their own action.
- **Suggestions.** Suggestion cases use suggestion wording and open the suggestion screen.

**Audit schema:** actor (plus a snapshot of their label and role), action, entity type, id and label, previous value, new value, reason, metadata, source and timestamp. Rows cannot be changed or deleted. This is enforced by the model, the queryset and a PostgreSQL trigger. The case module's own domain history (status history, assignments and so on) stays where it is; the audit log records who changed what across all modules.

## 4. API conventions: unchanged

Member B's endpoints follow Member A's conventions in `docs/API.md` exactly. They reuse the same error handler, the same pagination class and the same 404-for-invisible rule.

## 5. Status values and suggestions

**Decision (Member A to confirm):** suggestions have no status values of their own in the case model. Their evaluation state (Submitted, Under Evaluation, Accepted, Planned, Implemented, Declined) lives in `SuggestionEvaluation`. Each decision moves the case through Member A's services. The mapping is in [SUGGESTIONS.md](SUGGESTIONS.md).

Dashboard measures use the mapping Member A proposed (Not attempted = `submitted`, Not started = `assigned`, Open = not closed or rejected). Full definitions are in [DASHBOARD_METRICS.md](DASHBOARD_METRICS.md).

**Decision (Member A to confirm):** resolution time ends at `solved_at`.

## 6. Flutter navigation: implemented

- `main.dart` now mounts `PlatformScope` and `CaseScope` around a role-based `AppShell`. The **Cases** tab is `CaseRoutes.myCases()`.
- Every case link (notifications, ageing report, case report, "Open full case" on a suggestion) calls **`CaseRoutes.openCase`**. There is no second case-detail screen.
- `PlatformRoutes.openSuggestion(context, id)` and `PlatformRoutes.openTarget(context, type, id)` are the platform's entry points.

## 7. Answers to Member A's open questions

1. **Status values.** Accepted as proposed, including both departures: no "Verification" status and no stored "Not Started" status.
2. **Verification and reopen windows.** Not changed. They still need the faculty's approval.
3. **Deadline policies.** Not changed. Reminders use whatever policies administrators configure.
4. **Auth scheme.** DRF tokens with expiry (section 2).
5. **Authority and category CRUD.** Member B provides authority management (API and Flutter: create, edit, activate, deactivate; no delete). Category management stays in Django admin.
6. **Maroon value.** Not resolved; it still needs the branding office. The platform screens do not depend on it beyond the shared app-bar token.

## 8. Requests to Member A

1. **A `case_reclassified` signal.** Priority and category changes currently have no signal, so the audit log records them through a `pre_save`/`post_save` hook on `Case`, attributed through request context. A signal from `review_classification` with `{changes, note}` would be cleaner. Member B will switch to it once it exists.
2. **An assigned-cases list for authority officers in Flutter.** The case screens list only `mine=true`. Authority officers can open assigned cases from notifications and reports, but they have no list of them. This is case tracking, so it belongs to Member A.
3. **The OpenAPI warning on `AuthorityViewSet`.** `could not derive type of path parameter "id"`. A `queryset` attribute or `swagger_fake_view` guard would fix it.
4. **`mobile/analysis_options.yaml`.** `flutter pub get` (Flutter 3.47) added an `analyzer.exclude` block to this file. It was left uncommitted for Member A to accept or discard.
