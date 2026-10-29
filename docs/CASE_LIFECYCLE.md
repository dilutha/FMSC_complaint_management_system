# Case lifecycle (proposed shared status values)

Every rule here is enforced in the backend by `apps/cases/services/workflow.py`. The Flutter app only displays what the API returns in `allowed_actions`.

## Status values

| Value | Label | Meaning |
|---|---|---|
| `submitted` | Submitted | Created by a student or lecturer. |
| `under_review` | Under Review | An administrator is checking the case. |
| `waiting_for_information` | Waiting for Information | More detail is needed from the submitter or another party. |
| `assigned` | Assigned | A responsible authority has the case but has not started work. |
| `in_progress` | In Progress | The authority is working on it. |
| `solved` | Solved – Awaiting Verification | A resolution note has been recorded and the submitter is asked to confirm. |
| `closed` | Closed | Confirmed by the submitter, closed by an administrator, or closed automatically. |
| `rejected` | Rejected | Invalid, out of scope or inappropriate. A recorded reason is required. |
| `reopened` | Reopened | The resolution was disputed, or the problem returned. |

**Departures from the brief and the proposal (need Member B's agreement):**
- **No separate "Verification" status.** The brief has Solved → Verification → Closed, but nothing happens between those two steps. So the verification window is `solved` plus the `verification_due_at` field, and the label says "Awaiting Verification".
- **No "Not Started" status.** The proposal lists it, but it is really a dashboard measure, not a stored status. Member B can derive it as `status = assigned` (accepted but no work started), using `age_days`.

## Allowed transitions

Capacities: **A** = case administrator, **Au** = member of the *currently assigned* authority, **S** = the submitter, **Sys** = the scheduled job.

| From → To | Who | Requires |
|---|---|---|
| submitted → under_review | A | |
| submitted / under_review / waiting → rejected | A | reason |
| under_review → waiting_for_information | A | reason (shown to the submitter) |
| waiting → under_review | A | |
| waiting → in_progress | A, Au | an assigned authority |
| *(assignable)* → assigned | A, via the `assign` action only | an active authority |
| assigned / in_progress / reopened → waiting_for_information | A, Au | reason |
| assigned / reopened → in_progress | A, Au | |
| assigned / in_progress / reopened → solved | A, Au | resolution note of at least 10 characters |
| solved → closed | S (confirm), A, Sys (window expired) | |
| solved → reopened | S (problem persists), A | reason / feedback |
| closed → reopened | S within `REOPEN_WINDOW_DAYS`, A at any time | reason |
| rejected → under_review | A | reason (reconsideration) |
| reopened → under_review | A | |

You can assign a case from: submitted, under_review, waiting_for_information, assigned, in_progress or reopened. Reassigning ends the current assignment record and moves the case back to `assigned`.

## Side effects

- **Every change** writes a `CaseStatusHistory` row with the actor (null means system) and the reason. History is never deleted.
- **Solved:** sets `solved_at` and `verification_due_at`, creates a `CaseResolution` with outcome `pending`, adds a public resolution update, and emits `case_solved` (Member B notifies the submitter).
- **Closed:** sets `closed_at`. Closes the pending resolution as `confirmed` (submitter), `closed_by_admin` or `auto_closed`.
- **Reopened:** clears `closed_at`, increments `reopen_count`, and marks the pending resolution `disputed` (submitter) or `superseded` (admin), keeping the original note. It also recalculates the deadline from policy and records a `DeadlineChange`.
- **Rejected:** sets `closed_at`. The case is not overdue and can't be escalated.

## Closure policy (configurable)

| Setting | Default | Effect |
|---|---|---|
| `FMSC_VERIFICATION_WINDOW_DAYS` | 7 | A solved case with no submitter response is closed automatically after this many days. |
| `FMSC_REOPEN_WINDOW_DAYS` | 14 | How long after closure the submitter can still reopen. After that, they submit a new case. |

These defaults are placeholders and **need the faculty's approval**.

## Deadlines and escalation

- **Deadline policies** (Django admin → Deadline policies) set the resolution hours by priority, optionally narrowed by case type and/or category. The most specific active policy wins. If no policy matches, the case has no deadline; the system never invents one.
- **Recalculation:** the deadline is recalculated when an administrator changes priority or category (measured from submission), and when a case is reopened (measured from the reopening). Administrators can also set it manually with a required reason. All of these changes are recorded in `DeadlineChange`.
- **Overdue** means an active status with `deadline_at` in the past. The API supports it as a filter (`?overdue=true`) and returns it as a field (`is_overdue`).
- **Escalation:** `manage.py process_case_deadlines` (run on a schedule) raises level 1 at the deadline and level 2 after `FMSC_ESCALATION_LEVEL2_AFTER_HOURS`. The constraint UNIQUE(case, level, deadline_at) makes repeated runs idempotent. A new deadline can be escalated again. Each new event emits `case_escalated`.

## Mandatory messages and role separation (added by Member B)

- **Every status change made by staff needs a message.** This covers case administrators and the assigned department. The message must be at least 5 characters. It is saved in the same database transaction as the change, in `CaseStatusHistory.reason`, and the complainant sees it in the timeline. The rule lives in `workflow.transition()` (`MIN_STAFF_MESSAGE`). Marking a case solved uses its resolution note, of at least 10 characters, as the message. The submitter's own actions (confirming or reopening a case) and the scheduled job keep their existing rules.
- **Assignment needs a message.** `assign_case(..., message=...)` and `POST /cases/{id}/assign/ {authority_id, message}` both require it. The message is recorded as "Assigned to <department>: <message>". The optional `internal_note` stays visible to staff only.
- **History records who acted, and in what capacity.** `CaseStatusHistory` and `CaseUpdate` now store `actor_role`/`author_role` and `actor_authority`/`author_authority`. The complainant's timeline shows that role or department (for example "IT Department" or "Case Administrator") instead of staff names.
- **Capacities:**
  - Only case administrators (capacity A) review, assign and change status.
  - Admins (`system_admin`, the new capacity `MONITOR`) can read every case and post `admin_message` updates. They cannot change status, assign cases or attach files.
- **Who can submit:** only students, lecturers and non-academic staff.
- **What departments can see:** department users (`authority`) see only cases currently assigned to their department, including when looking up a case by its id.
