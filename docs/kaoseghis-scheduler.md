# KaosEghis-scheduler

Last updated: 2026-07-23

## Status

**Planned plugin. Not implemented.**

This document records the intended scheduler scope before any unattended automation
is added. No current KaosEghis component should be interpreted as providing these
scheduled production workflows.

Any implementation that changes the shared connector, macro runner, safety gate, or
application startup behavior is a KaosEghis core change and requires explicit user
approval before work begins.

## Purpose

`KaosEghis-scheduler` will coordinate a small number of predictable clinic workstation
jobs at configured times while preserving clear safety boundaries.

The first planned workflows are:

1. copy completed backup data to one or more destination folders around lunch time
2. perform a guarded end-of-day eGHIS close/backup/shutdown-dialog sequence
3. prepare statistical claim data on configured claim days, initially as planning and
   dry-run work only

The scheduler is not intended to become a general-purpose unattended macro platform.
Every job type must have an explicit schema, safety policy, and operator-facing result.

## Guiding Principles

- scheduled jobs are opt-in and disabled by default
- every job and every optional action step has its own enabled toggle
- file operations and interactive UI automation are separate execution classes
- no scheduled action silently bypasses connector or target validation
- unknown windows, dialogs, or states block the run
- a failed step stops dependent steps
- no job runs automatically merely because KaosEghis starts late
- dry run and manual test must exist before scheduled execution is enabled
- routine logs contain operational results, not patient or claim contents
- secrets are referenced through secure credential storage, not stored in scheduler
  rows

## Planned Plugin Boundary

### Scheduler plugin owns

- job definitions and schedules
- per-step enabled settings
- due-job calculation
- missed-run policy
- run locking and overlap prevention
- dry-run planning
- sanitized run history
- operator countdown, cancellation, and status presentation
- dispatch to an approved job-specific service

### Existing KaosEghis services continue to own

- EMR process/window identity verification
- connector readiness and stale-state handling
- UI target resolution
- macro execution safety
- app settings and credential references

### Scheduler plugin does not own

- arbitrary script execution
- arbitrary shell commands
- unrestricted file copying
- forced eGHIS termination
- direct database modification
- claim submission
- bypass of unknown modal dialogs
- automatic credential entry without an approved secure flow

## Job Categories

### Background file job

Does not require eGHIS UI interaction and may run while the workstation is otherwise
idle or in use.

Initial example:

- lunch backup-copy job

### Interactive desktop job

Requires the correct logged-in Windows desktop, visible eGHIS UI, connector identity,
and known UI targets.

Initial example:

- end-of-day eGHIS close and backup-dialog sequence

Interactive jobs must never run in a non-interactive service session.

### Preparation-only job

Collects or prepares information but does not submit or finalize an external process.

Initial example:

- claim-day statistical preparation

## Workflow 1: Lunch Backup Copy

### Goal

At a configured lunch-time schedule, copy one or more completed backup artifacts from
an approved source folder to one or more approved destination folders. One destination
may be a folder synchronized by Dropbox.

### Important boundary

Copy completed backup artifacts only. Do not copy live eGHIS database files, open
PostgreSQL data directories, or files that are still being written.

### Planned configuration

- job enabled
- local time and selected weekdays
- source folder
- allowed filename pattern or approved file set
- selection rule:
  - newest completed artifact
  - artifacts created since the previous successful run
  - explicitly selected filenames
- one or more destination folders
- per-destination enabled toggle
- overwrite policy
- verification policy
- source age/stability requirement
- timeout
- retry count
- missed-run policy

### Planned execution

1. Confirm the source folder exists and is inside the configured boundary.
2. Enumerate only files matching the approved rule.
3. Reject symlinks, unexpected file types, and active partial files.
4. Confirm each source file's size and modification time remain stable for a configured
   interval.
5. Copy to a temporary destination filename such as `.partial`.
6. Verify copied size and, when enabled, a cryptographic hash.
7. Rename the temporary file to its final destination name.
8. Record each destination result independently.
9. Leave the source unchanged unless a later retention feature is separately approved.

### Failure behavior

- missing source: block and report
- no eligible completed file: skip with a clear result
- destination unavailable: mark that destination failed; do not report overall success
- existing destination conflict: follow explicit overwrite/version policy only
- verification mismatch: remove the incomplete destination artifact and fail
- partial success across multiple destinations: report every destination separately

### Dropbox/privacy considerations

A Dropbox-synchronized folder is still an external synchronization boundary. Before
production use, confirm clinic-approved access, account ownership, encryption,
retention, and recovery procedures. The scheduler should never assume that the mere
presence of a Dropbox folder makes a backup compliant or complete.

Do not log backup contents. Paths may be shown to an authorized operator but should
not be copied into broad application logs unnecessarily.

## Workflow 2: Scheduled eGHIS Close and Backup

### Goal

At a configured end-of-day time, optionally perform the known eGHIS close and backup
dialog sequence and optionally select eGHIS's `shutdown after backup` checkbox.

### Planned independently toggleable actions

- request graceful eGHIS close
- confirm the known backup prompt with `Yes`
- enable the known `shutdown after backup` checkbox

Mandatory safety observations such as identity checks, dialog validation, and result
monitoring are not optional action steps.

### Dependency rules

- `shutdown after backup` requires backup confirmation to be enabled
- automatic backup confirmation normally requires graceful close to be enabled
- invalid combinations cannot be saved as an enabled schedule
- disabling an earlier step disables or blocks dependent later steps

An advanced future mode may wait for a prompt opened manually by an operator, but it
must be a separate explicit job mode rather than an accidental dependency bypass.

### Preconditions

- KaosEghis is running
- the correct Windows user is logged in
- the desktop session is unlocked and interactive
- an enabled EMR target profile is selected
- eGHIS process identity, executable identity, PID, window handle, and owning PID are
  valid
- no unknown blocking modal or popup is present
- the required dialog and checkbox UI targets have been configured and manually tested
- scheduler dry run succeeds
- no other interactive scheduler or macro run holds the execution lock

### Planned execution

1. Mark the job Pending and acquire the interactive automation lock.
2. Revalidate the configured schedule and enabled steps.
3. Show a visible countdown with a Cancel action.
4. Confirm the eGHIS connector and target profile.
5. If enabled, request graceful eGHIS close.
6. Wait for the exact known backup dialog within the configured timeout.
7. Validate dialog ownership, title/class, and expected controls.
8. If enabled, set `shutdown after backup` to the requested checked state using an
   approved target action.
9. If enabled, activate the known `Yes` backup control.
10. Observe the known backup-start/result state when a reliable read-only indicator is
    available.
11. Release the lock and record a sanitized result.

The exact order of checkbox and confirmation interaction must be verified against the
live eGHIS dialog before implementation. This document does not assume control IDs or
screen coordinates.

### Prohibited behavior

- no forced process kill
- no blind Enter or coordinate click against an unverified foreground window
- no automatic click through unknown dialogs
- no Windows shutdown command as a fallback for a missed eGHIS checkbox
- no silent reconnection to a different process/window identity
- no continuation after a failed prerequisite or failed step

### Operator experience

Before the action starts, show:

- job name
- planned time
- enabled steps
- countdown
- `Cancel this run`

If blocked, keep the workstation running and show a short reason such as:

- eGHIS is not connected
- desktop is locked
- backup dialog was not found
- dialog did not match the configured target
- unknown modal detected
- backup result could not be confirmed

## Workflow 3: Claim-Day Statistical Preparation

### Status

**Early planning only.**

The source data, preparation rules, claim calendar, expected outputs, review process,
and privacy boundary are not yet sufficiently defined for implementation.

### Initial safe direction

- configure claim-day reminders
- allow a preparation dry run
- gather only approved statistical inputs
- produce an operator-reviewable preparation result
- require manual review and approval
- never submit or finalize a claim automatically

### Explicitly deferred

- unattended claim submission
- automated approval/confirmation
- credential entry into claim portals
- financial or billing state changes
- retries that could duplicate submission

Claim preparation should become its own job specification after the actual manual
workflow is documented step by step.

## Scheduling Semantics

### Time zone

Schedules use the workstation's configured local time zone. The UI must display the
effective time zone and next-run timestamp.

### Initial schedule types

- daily at a time
- selected weekdays at a time
- selected calendar dates
- manual run using the saved job definition

Monthly/claim-day rules remain deferred until requirements are known.

### Missed-run policy

Each job has an explicit policy:

- `skip`: default for interactive jobs
- `prompt`: notify the operator and require a manual start
- `run_once`: eligible only for approved background file jobs

An interactive eGHIS job must not suddenly run because KaosEghis was opened after the
scheduled time.

### Overlap policy

- one interactive automation at a time
- no duplicate run of the same job
- due ticks while a job is running are recorded as skipped overlap
- file-copy concurrency is disabled initially
- cancellation requests stop before the next safe step boundary

### Clock and resume behavior

- recompute next run after clock changes, sleep, resume, and application restart
- store the intended scheduled timestamp with each run
- avoid duplicate execution after backward clock adjustments
- use a short due-time tolerance rather than relying on exact millisecond equality

## Runtime Strategy Decision

Implementation strategy remains **planned and undecided**.

### Option A: In-process scheduler

Advantages:

- simplest UI integration
- direct access to connector and operator notifications
- appropriate for interactive desktop jobs

Limitations:

- jobs do not run when KaosEghis is closed
- sleep/restart handling requires careful recovery semantics

### Option B: Windows Task Scheduler launcher

Advantages:

- reliable triggers when the main application is not already running
- appropriate for approved background file-copy jobs

Limitations:

- UI automation must run only in the logged-in interactive session
- launching the full app at a missed time must not automatically execute an
  interactive job
- credentials and task registration require additional deployment controls

### Recommended direction

Use a split strategy only after design approval:

- interactive eGHIS jobs run inside the visible KaosEghis desktop process
- background backup-copy jobs may later use a narrowly scoped Task Scheduler helper
- both paths share the same SQLite job/run records and locking rules

No service should expose a general command runner.

## Planned UI

Final placement is not decided. The plugin may become a dedicated `Scheduler` tab or
a plugin page.

### Job list

Suggested columns:

- Enabled
- Job name
- Type
- Schedule
- Next run
- Last result

Suggested actions:

- New job
- Edit
- Enable/Disable
- Dry run
- Run now
- View history

### Job editor

Common fields:

- name
- enabled
- job type
- days/dates
- local time
- missed-run policy
- timeout
- retry policy

Job-specific sections expose only their approved parameters. Do not provide arbitrary
command, script, SQL, or executable fields.

### Status

The plugin should show:

- scheduler enabled/disabled
- next due job
- active run
- last successful run
- last blocked/failed reason

## Draft Data Model

This is a planning aid, not an approved migration.

```text
scheduler_jobs
  id
  name
  job_type
  is_enabled
  schedule_type
  schedule_time
  schedule_days
  schedule_dates
  missed_run_policy
  timeout_seconds
  retries
  job_config_json
  created_at
  updated_at

scheduler_job_steps
  id
  job_id
  step_order
  step_type
  is_enabled
  step_config_json
  created_at
  updated_at

scheduler_runs
  id
  job_id
  scheduled_for
  started_at
  finished_at
  status
  completed_steps
  blocked_reason
  summary
```

Configuration JSON must be schema-validated per job type. Do not store passwords,
API tokens, patient data, claim contents, or raw exceptions in scheduler tables.

## Run States

- `pending`
- `countdown`
- `running`
- `succeeded`
- `blocked`
- `failed`
- `cancelled`
- `skipped`
- `missed`

Only `succeeded` means every enabled required step and verification completed.

## Logging and Notifications

Record:

- job ID and type
- scheduled/start/finish timestamps
- enabled steps attempted
- completed step count
- safe status and category
- destination result category for backup copy

Safe error categories:

- source unavailable
- destination unavailable
- verification failed
- eGHIS not connected
- desktop unavailable
- target not found
- unknown dialog
- timeout
- cancelled by operator
- configuration invalid
- unknown error

Do not store raw exceptions, database contents, backup contents, patient data, claim
data, passwords, or tokens in routine scheduler logs.

## Safety Gates

Before enabling a schedule:

- configuration validates
- required paths/targets are present
- dry run succeeds
- a manual run of the same definition succeeds where practical
- dependencies between enabled steps validate
- operator acknowledges unattended behavior

Before every interactive run:

- connector identity validates
- target profile matches
- desktop is interactive
- no unknown modal is present
- global interactive automation lock is acquired

Any failure blocks the run. Scheduler convenience must not weaken macro or connector
safety.

## Privacy and Backup Handling

Backup artifacts may contain sensitive clinical and identifying information.

- copy only to approved destinations
- do not inspect or index backup contents
- do not place patient identifiers in scheduler logs
- do not upload through a custom network path when an approved synchronized folder is
  the configured mechanism
- do not delete source backups in the initial milestone
- make retention and encryption separate reviewed settings
- keep destination credentials outside SQLite

Claim preparation may also contain sensitive information. Its field and retention
rules must be documented before implementation.

## Testing Plan

### Scheduler calculation

- disabled jobs never become due
- next-run calculation respects local time and selected weekdays
- sleep/resume does not duplicate a run
- backward clock adjustment does not duplicate a run
- missed interactive job defaults to skipped
- overlap is prevented

### Backup copy

- unstable/in-progress source is rejected
- approved completed file copies successfully
- multiple destinations report independently
- partial file uses temporary destination name
- size/hash verification failure blocks success
- destination conflict obeys configured policy
- source is not deleted
- no sensitive content appears in logs

### eGHIS backup sequence

- disabled step is omitted from dry run and execution
- invalid toggle dependencies are rejected
- disconnected or mismatched eGHIS blocks execution
- locked/non-interactive desktop blocks execution
- unknown dialog blocks execution
- timeout stops dependent steps
- operator countdown cancellation performs no action
- shutdown checkbox is never changed without exact target resolution
- no force-kill or OS shutdown fallback exists

### Claim preparation

- remains dry-run/manual-review only until separately approved
- no submission action exists
- no credentials or claim contents appear in logs

### Startup

- application startup does not execute an interactive missed job
- scheduler initialization performs no EMR UI action
- scheduler initialization performs no file copy
- disabled-by-default behavior is preserved

## Planned Milestones

### Milestone 0: Workflow verification

- identify exact backup artifact source and completion signal
- inspect and manually record the real eGHIS close/backup dialog targets
- document office times, missed-run preferences, and cancellation expectations
- document claim preparation manually before any claim code

### Milestone 1: Scheduler model and dry run

- local schema and repository
- job list/editor
- schedule calculation
- per-step toggles and dependency validation
- dry-run plans only
- no unattended execution

### Milestone 2: Backup-copy job

- approved file selection
- stable-file detection
- atomic multi-destination copy
- verification and sanitized history
- manual run first, scheduled background run after validation

### Milestone 3: Interactive eGHIS backup job

- explicit core-change approval
- exact UI target definitions
- countdown and cancellation
- connector-gated manual run
- scheduled run only after repeated manual validation

### Milestone 4: Operational hardening

- sleep/resume and clock-change handling
- health/status UI
- missed-run and overlap testing
- deployment checklist
- recovery and operator guidance

### Future milestone: Claim-day preparation

- begin only after the manual claim workflow and privacy boundary are documented
- preparation and review first
- submission remains out of scope unless separately approved

## Open Questions

- Which exact files are the completed backup artifacts?
- How is file completion reliably detected?
- Which lunch-time source and destination folders are approved?
- Is Dropbox synchronization approved for the backup's sensitivity and retention?
- Should each destination use overwrite, date-versioned, or skip-existing behavior?
- What are the exact eGHIS close/backup dialog targets and sequence?
- How long should the pre-run countdown be?
- What happens if a patient encounter or other eGHIS work is still active at closing?
- Should the scheduler notify only in-app, or also through a separate admin channel?
- What is the exact manual claim-day preparation workflow?

## Non-Goals

The planned scheduler will not initially:

- execute arbitrary scripts or commands
- run arbitrary macros on a schedule
- force-close eGHIS
- bypass connector readiness
- submit claims
- enter claim credentials
- delete source backups
- manage Dropbox accounts
- provide a general Windows automation service
- perform unattended actions on application startup
