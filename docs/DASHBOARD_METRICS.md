# Dashboard metric definitions

The dashboard API, the Flutter dashboard and the printable report at `/manage/report/` all calculate figures in one place: `backend/apps/dashboard/metrics.py`. Each figure below is tested against a hand-checked dataset in `apps/dashboard/tests/test_dashboard.py`.

## Which cases are counted

The **date range selects cases by the date they were submitted**. Each count then describes those cases **as they are now**. For example, *Open = 4* means that 4 of the cases submitted in the range are still open today.

The **Trends** series works differently. There, the range selects *events* by the date they happened (submissions, solutions and closures). So a case submitted in March and solved in April appears in March's *Submitted* figure and April's *Solved* figure.

Filters are combined with AND. The available filters are:

| Filter | Matches |
|---|---|
| `category` | Case category id |
| `priority` | `urgent` or `normal` (the confirmed priority) |
| `case_type` | `complaint` or `suggestion` |
| `status` | One or more case statuses, comma-separated |
| `authority` | The currently assigned responsible unit |
| `location` | Location text containing the given value (case-insensitive) |

## Counts

| Figure | Definition |
|---|---|
| Total | Every case in the range. |
| Complaints / suggestions | Total split by case type. |
| Open | Status is not `closed` and not `rejected`. Solved cases still waiting for verification count as open. |
| Not attempted | Status is `submitted`. No administrator has acted yet. |
| Attempted | Total minus not attempted. |
| Not started | Status is `assigned`: accepted and assigned, but work has not begun. |
| Awaiting verification | Status is `solved`. |
| Urgent / normal | Split by confirmed `priority`. The submitter's original request is kept separately in `requested_priority`. |
| Overdue | The case is still active (`ACTIVE_STATUSES`) and its `deadline_at` is in the past. This is the same rule as the case module's `is_overdue`. Cases with no deadline policy are never overdue. |

## Rates

Every rate returns `{value, numerator, denominator}`. `value` is a percentage with one decimal place, or `null` when the denominator is 0.

| Rate | Numerator | Denominator |
|---|---|---|
| Overdue | Overdue cases | Active cases |
| Resolution | Cases now `solved` or `closed` | Total minus rejected |
| Reopening | Cases with `reopen_count > 0` | Cases that were ever solved (`solved_at` is set) |
| Repeat issue | Cases an administrator linked to an **earlier** case as `duplicate` or `related` | Total |
| Suggestion acceptance | Suggestions accepted, planned or implemented | Suggestions with a decision (accepted, planned, implemented or declined) |
| Suggestion implementation | Suggestions implemented | Suggestions accepted, planned or implemented |

Unconfirmed `possible_duplicate` links are excluded from the repeat-issue rate. Links are stored with the older case first, so the later case is always the repeat.

## Times

Both times are reported as a median, an average and the number of cases they are based on.

| Figure | Starts | Ends | Cases included |
|---|---|---|---|
| First response (hours) | `created_at` | The first status change *out of* `submitted`. This is an administrator reviewing, assigning or rejecting the case. | Cases that have left `submitted` |
| Resolution (days) | `created_at` | `solved_at`, when the case was **marked Solved**. | Cases now `solved` or `closed` |

**Resolution time ends at Solved, not at verified closure.** The time a submitter takes to confirm the fix is not part of the responsible unit's work. If a case was reopened, `solved_at` holds the latest solution, so the figure includes the rework.

The median is the headline figure, because a few very old cases would distort an average.

## Responsible unit workload

The workload view shows, for each unit, the cases in range currently assigned to it:
- counts: active, not started, in progress, waiting for information, reopened, awaiting verification, resolved and overdue;
- the average age of its open cases;
- its median resolution time.

Every active unit is listed, including units with no cases.

> Workload counts show how many cases each unit currently holds. Volume depends on the kind of issues a unit handles. On its own, it is not a measure of the unit's performance.

The API response and both user interfaces show this note.

## Ageing report

The ageing report covers not-started cases (`scope=not_started`, the default) or all open cases (`scope=open`). It gives:
- each case's age in whole days since submission;
- counts in the buckets 0–2, 3–7, 8–14, 15–30 and more than 30 days;
- the 50 oldest cases.

This is the proposal's "age report showing the number of days for not-started cases".

## Privacy

Dashboard and report responses contain case numbers, titles, statuses, categories, locations and unit names. They never include descriptions, comments, attachments or submitter identities.

The endpoints are limited to administrators and faculty management. Every CSV export is recorded in the audit log.
