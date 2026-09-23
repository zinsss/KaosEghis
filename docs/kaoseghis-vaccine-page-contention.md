# Vaccine page and PACS database contention

## Report (2026-09-22)

KaosEghis intermittently stalled at Building workspace and was subsequently
unusably slow when the operator tried to open Vaccine / Fetch from EMR.
No live patient fetch, keyboard input, or application restart was performed
during this investigation.

## Reproduced defects

- PACS polling updated existing local SQLite worklist rows, then queried the
  external EMR MWL while its local write transaction remained open. A delayed
  EMR query therefore prevented unrelated KaosEghis database writes.
- Opening Vaccine called both activate_page() and refresh_view(), duplicating
  the refresh. Each refresh ran database schema migrations, and selecting the
  vaccine type ran them again. These writes occurred on the Qt GUI thread.
- PACS missing-order reconciliation could overwrite a completion or edit made
  while the remote query was pending, because it used an old local snapshot.

The lock conflict and stale-status overwrite were reproduced using temporary
databases and fake remote-query callbacks. They are confirmed code defects,
but no stack trace from the operator's original stall was available. They do
not establish that flu reporting directly causes EMR slowness.

## Changes

- Commit and close the local PACS update connection before remote revalidation.
- Read cancellation candidates using a separate, closed local connection.
- Recheck each candidate under a short local write transaction after the
  external query; skip rows changed in the meantime.
- Initialize Vaccine's database during construction, not during page refresh,
  vaccine selection, or read-only setup for Fetch from EMR.
- Run page activation or fallback refresh, never both for the Vaccine tab.

EMR SQL, polling intervals, vaccination records/count rules, patient field
selectors, and keyboard/mouse automation are unchanged. EMR access remains
read-only. Fetch's UIA work is still synchronous; this patch addresses the
separate local-database stalls rather than claiming to fix every UIA delay.

## Verification

`tests/test_runtime_database_contention.py` covers local write availability
during PACS revalidation, concurrent completion/cancellation preservation,
Vaccine refresh while another writer is active, migration-free fetch setup,
and single-pass page activation. Tests use fake patients/orders only.

Focused regression plus PACS polling/worklist/sync, navigation, Vaccine fetch,
post-print, settings, and session-retry suites: 204 passed. One existing
pywinauto COM threading-mode warning was emitted.

The running desktop process must be restarted to load the changed Python code.
Actual responsiveness in the operator's workflow remains to be confirmed.
