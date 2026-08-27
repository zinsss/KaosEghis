# KaosEghis-scheduler

Last updated: 2026-08-27

## Status

**Scheduler foundation implemented. Backup workflow not implemented.**

KaosEghis now has an in-process Scheduler tab that binds a saved macro to a local
time and selected weekdays. The scheduler does not contain a separate backup engine.
The future backup process will be implemented as an ordinary, reviewed macro and then
selected by a schedule.

Current implementation:

- top-level `Scheduler` tab
- local schedule and run-history persistence
- saved macro selector
- local time and weekday schedule
- disabled-by-default jobs
- 10-second countdown before automatic or manual execution
- Cancel active control
- dry run and Run now controls
- skip and operator-prompt missed-run policies
- sanitized local result history
- one process-wide real-macro execution lock
- no execution of old missed jobs during application startup

Not implemented yet:

- the backup-copy macro/action itself
- eGHIS close and backup-dialog macro
- claim-day preparation macro
- one-shot dates, monthly calendars, holidays, or claim-day recurrence
- Windows service or Windows Task Scheduler integration
- execution while KaosEghis is closed
- arbitrary shell commands, scripts, SQL, or executable launch fields

## Runtime Model

The scheduler runs inside the visible KaosEghis desktop process.

- KaosEghis must remain open.
- The logged-in desktop must remain available for interactive macros.
- Startup initializes SQLite, recalculates every enabled job's next future time, and
  starts a lightweight due-time timer.
- Startup never replays a time missed while the application was closed.
- The timer checks for due jobs every five seconds.
- A due automatic job starts only when it is no more than 60 seconds late.
- A job older than that is recorded as `missed` and advanced to its next occurrence.
- A `prompt` job never auto-runs. It notifies the operator and must be started with
  `Run now`.

This behavior prevents a sleeping, suspended, or newly opened workstation from
unexpectedly sending delayed automation input.

## Schedule Model

Each `scheduler_jobs` row stores:

- name
- linked macro item ID
- enabled state
- `HH:MM` local time
- selected weekdays, Monday through Sunday
- missed-run policy: `skip` or `prompt`
- next run timestamp
- last run timestamp and status
- created and updated timestamps

Jobs are disabled by default. Enabling a job is the operator's explicit authorization
for that macro to run at its selected time while KaosEghis is open.

The initial recurrence model intentionally supports only one local time on selected
weekdays. It does not attempt timezone conversion, cron syntax, interval schedules,
or calendar recurrence.

## Run Model

Each `scheduler_runs` row stores:

- schedule and macro references
- trigger: `scheduled` or `manual`
- intended time
- actual start and finish time
- status
- executed step count
- short sanitized summary

Expected statuses include:

- `countdown`
- `running`
- `succeeded`
- `blocked`
- `failed`
- `cancelled`
- `missed`

Only `succeeded` means the linked macro returned success. Histories deliberately use
safe summaries such as `Macro completed` or `Macro safety check blocked execution`.
They do not persist raw exceptions, clipboard text, patient information, credentials,
or backup contents.

## Execution Flow

For an enabled scheduled job:

1. Detect the due timestamp.
2. Apply missed-run policy and lateness tolerance.
3. Create a local countdown run record.
4. Show a top-right notification for the 10-second countdown.
5. Allow the operator to cancel.
6. Re-read the schedule and linked macro after countdown.
7. Block if either the schedule or macro is disabled or missing.
8. Ask `MacroRunner.execute_macro(..., dry_run=False)` to run the macro.
9. Let MacroRunner enforce its normal connector, profile, target, and modal safety.
10. Stop on the macro's first failed action.
11. Store a sanitized result and calculate the next future occurrence.

`Run now` uses the same countdown and MacroRunner path but does not move the saved
automatic next-run timestamp.

## Concurrency

Only one real macro may execute in the KaosEghis process at a time. Manual Launcher,
Builder, and Scheduler runs share one nonblocking execution lock.

- a second real run is blocked rather than queued
- dry run does not hold the real-execution lock
- cancellation continues through the existing runner cancellation flag
- no UI element handles are persisted in Scheduler tables

This protects against two workflows sending input to the desktop simultaneously.

## EMR Safety Boundary

The Scheduler does not bypass normal macro safety.

An EMR macro still requires:

- an enabled macro
- a manually established valid cached application connection when required
- matching process and window identity
- a valid EMR target profile
- resolvable targets
- no blocking unknown modal state
- supported macro actions only

If readiness or target resolution fails, the Scheduler records a blocked run. It does
not reconnect silently, activate a different application, or continue with remaining
steps.

Background macros that do not interact with eGHIS may later use a non-EMR application
preset or a narrowly approved file action. That action must still be explicit and
validated; the Scheduler itself does not execute arbitrary filesystem commands.

## Operator UI

The Scheduler page contains:

- scheduler readiness/active status
- jobs table: Enabled, Name, Macro, Time, Days, Next run, Last result
- New schedule
- Edit
- Delete
- Enable / Disable
- Dry run
- Run now
- Cancel active
- Refresh
- run-history table
- compact dry-run/result log

The editor contains:

- schedule name
- existing saved macro
- time
- weekday toggles
- missed-run policy
- enabled toggle

Deleting a schedule deletes only its scheduler history. It does not delete the macro.
Deleting a macro removes schedules that reference it so an orphan schedule cannot run.

## Backup Macro Direction

The lunch backup is not a special Scheduler job type. The intended composition is:

```text
Scheduler job
  -> saved Backup macro
      -> future approved file-copy action(s)
```

Before the backup macro is implemented, confirm:

- exact source directory and completed artifact pattern
- how a completed, stable backup is distinguished from a file still being written
- approved destination folders
- Dropbox account and retention boundary
- overwrite/version behavior
- temporary filename behavior
- size and optional hash verification
- cleanup behavior, if any, as a separately approved action

The backup macro must never copy live PostgreSQL data directories or partially written
files. Initial implementation should copy to a temporary destination, verify it, then
rename it into place. Source deletion is out of scope for the first backup milestone.

## End-of-Day eGHIS Backup Direction

The end-of-day workflow will be a guarded macro connected to a schedule. The requested
operator sequence is:

1. Focus the manually connected eGHIS process/window.
2. If the verified eGHIS lock screen is present, type its password from an unlocked
   KaosEghis-pw credential entry and submit it.
3. Send `Alt+F4` to the verified eGHIS window.
4. Wait for the exact close-confirmation dialog and activate its Yes button.
5. Wait for the exact backup confirmation and activate its confirmation control.
6. Wait for the eGHIS Backup window and check the verified power-off-after-backup
   checkbox.

The password must not be stored in a macro step, scheduler row, setting, result, or log.
The workflow must block when the KaosEghis-pw vault is locked or the configured
credential entry is unavailable.

### Captured eGHIS Controls

The following controls were captured from the current production eGHIS build on
2026-08-27.

#### Close confirmation

Parent dialog:

- UIA Name: `확인`
- Control type: `Window`
- Ancestor: `이지스 전자차트 2.0` (`Window`)

Yes button:

- UIA Name: `예(Y)`
- Control type: `Button`
- Class observed: `WindowsForms10.Window.b.app.0.2bf8098_r6_ad1`
- Parent target: the `확인` dialog above
- Observed coordinate: `(1240, 1015)`, diagnostic reference only

The observed handle and Automation ID were both `45881156`. That number is a transient
window handle and must not be saved or used as an Automation ID selector. Resolve this
button by its parent dialog, UIA Name, and control type.

#### Power off after backup

Parent dialog:

- UIA Name: `이지스 백업`
- Control type: `Window`

Checkbox:

- UIA Name: `백업 완료 후 PC를 자동 종료 합니다.`
- Automation ID: `chkShutDown`
- Control type: `CheckBox`
- Class observed: `WindowsForms10.BUTTON.app.0.141b42a_r7_ad1`
- Parent target: the `이지스 백업` dialog above
- Observed coordinate: `(854, 1616)`, diagnostic reference only

`chkShutDown` is the preferred stable selector. The implementation should resolve and
toggle this checkbox directly rather than send a blind Space key.

### Captures Still Required

- eGHIS lock-screen password field and its parent dialog/window
- backup confirmation button and its parent dialog/window
- final/default backup action control, if it is separate from the confirmation above
- schedule time and selected weekdays
- KaosEghis-pw service-entry name that supplies the eGHIS password

Every write step remains independently configurable in the macro. Exact dialog targets
must be captured and manually tested first. The macro must not force-kill eGHIS, click
unknown dialogs, type a password without first resolving the lock field, issue blind
confirmation keys, or call an operating-system shutdown fallback.

## Claim-Day Direction

Claim-day statistical preparation remains planning-only. Scheduling does not authorize
claim submission, billing changes, credential entry, or final approval. The manual
workflow and operator review boundary must be documented first.

## Privacy and Logging

Scheduler names, macro names, and summaries are operational metadata. Operators should
not place patient names, chart numbers, national IDs, credentials, or clinical content
in schedule names.

Scheduler persistence must not contain:

- macro input values or clipboard contents
- patient or claim contents
- passwords, tokens, or connection strings
- raw exceptions
- raw backup file contents

## Tests and Operational Checks

Automated coverage includes:

- schedule and history repository CRUD
- macro-only schedule binding
- weekday next-run calculation
- startup recalculation without execution
- due execution after countdown
- countdown cancellation
- missed late-run skip
- prompt policy without automatic execution
- process-wide macro overlap blocking
- Scheduler UI construction without execution

Before production backup scheduling, manually verify:

1. disabled schedules never run
2. countdown cancellation works
3. sleep/resume produces a missed record rather than a late run
4. a blocked EMR connection stops the macro
5. a concurrent launcher macro blocks the scheduler run
6. the backup macro handles representative files and unavailable destinations
7. logs contain no sensitive content

## Next Milestone

The next Scheduler-specific milestone is to define and test the backup macro's approved
file-copy action against temporary folders. The scheduler structure is ready; the real
backup source, destination, stability, and verification rules are still required.
