# Suggestion evaluation workflow

A suggestion is a case whose `case_type` is `suggestion`. Member A's module handles submission, attachments, comments and verification for suggestions in the same way as for complaints.

The `apps.suggestions` module adds a `SuggestionEvaluation` record. It holds:
- the decision and the reason for it;
- the responsible unit;
- the target date;
- progress, including progress updates;
- an immutable decision history.

## Statuses and how they map to the case lifecycle

**The case status remains the single source of truth for the workflow.** Every suggestion action that changes the case uses Member A's services (`assign_case` and `transition`), so the lifecycle rules, case history and integration signals apply unchanged.

| Suggestion status | Case status | Reached by | Who |
|---|---|---|---|
| Submitted | `submitted` | Submission | Submitter |
| Under Evaluation | `under_review` (or `waiting_for_information`) | **Start evaluation** | Administrator |
| Accepted for Implementation | `assigned` to the responsible unit | **Accept**. A responsible unit is required; a decision note and target date are optional. | Administrator |
| Planned | `assigned` or `in_progress` | **Set target date**. The date is required and cannot be in the past. | Administrator or member of the responsible unit |
| *(progress update)* | The first update moves the case to `in_progress` | **Add progress update**: a note, plus an optional 0–99 % figure | Administrator or unit member |
| Implemented | `solved`, then `closed` once the submitter confirms | **Mark as implemented**: a summary of at least 10 characters | Administrator or unit member |
| Declined | `rejected` | **Decline**: a **reason of at least 10 characters is required** and shown to the submitter | Administrator |
| Under Evaluation (again) | `under_review` | **Reconsider** a declined suggestion. A reason is required. | Administrator |

Other rules:
- **Decline** is only possible before acceptance. After that, Member A's lifecycle does not allow `assigned → rejected`.
- If the submitter **disputes** an implementation, the case is reopened through the normal verification flow and the suggestion returns to *Accepted*.

## Changes made through the case API

An administrator can still use the case endpoints on a suggestion, for example to reject or assign it directly. `sync_from_case()` mirrors those changes into the evaluation as follows:
- `rejected` → Declined (using the rejection reason)
- `assigned` → Accepted
- `solved` → Implemented (using the resolution note)
- `reopened` → Accepted

Stale events, meaning those delivered after the case has already moved on, are ignored.

## Notifications sent to the submitter

| Event | Sent by | Notification |
|---|---|---|
| Evaluation started | Case `status_changed` | "Your suggestion … is being evaluated" |
| Accepted | Case `status_changed` → `assigned` | "Suggestion … accepted for implementation", naming the unit |
| Declined | Case `status_changed` → `rejected` | "Suggestion … was declined", with the reason |
| Planned or rescheduled | Suggestion module | Target date |
| Progress update | Suggestion module | Percentage, if one was given |
| Implemented | Case `solved` | "Suggestion … has been implemented" and a request to confirm |

The responsible unit's members receive the normal assignment notification. Each event produces exactly one notification per person.

## API

All paths are under `/api/v1/`. The `{id}` is the case id.

| Method | Path | Body |
|---|---|---|
| GET | `suggestions/?status=&responsible_unit=&mine=&search=` | – |
| GET | `suggestions/{id}/` | – |
| POST | `suggestions/{id}/decision/` | `{decision: start_evaluation\|accept\|decline\|reconsider, reason?, responsible_unit_id?, target_date?}` |
| POST | `suggestions/{id}/plan/` | `{target_date, plan_note?}` |
| POST | `suggestions/{id}/progress/` | `{note, percent_complete?}` (0–99) |
| POST | `suggestions/{id}/implementation/` | `{summary}` |
| GET | `suggestions/options/` | – |

The detail response includes `allowed_actions`. These are hints for the user interface; the server checks permission on every action.

Submitters see role labels instead of staff names, following the same rule as the case module.
