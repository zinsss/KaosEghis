# KaosEghis Automation

Last updated: 2026-08-20

## Purpose

This document describes the automation boundary of KaosEghis:

- what is read-only
- what is manual test only
- what is dry-run only
- what is actually executable

The project deliberately avoids mixing these categories.

This document also records when automation-adjacent behavior belongs to a hidden
infrastructure module rather than the main visible automation surfaces.

## Layers

### Detection

Modules:

- [KaosEghis/core/emr_detector.py](/E:/Kaos/KaosEghis/KaosEghis/core/emr_detector.py)
- [KaosEghis/core/eghis_connector.py](/E:/Kaos/KaosEghis/KaosEghis/core/eghis_connector.py)

Responsibilities:

- process detection
- window detection
- active-window checks
- connector readiness state

### Read-Only UI Inspection

Modules:

- [KaosEghis/core/uia_inspector.py](/E:/Kaos/KaosEghis/KaosEghis/core/uia_inspector.py)
- [KaosEghis/core/wait_engine.py](/E:/Kaos/KaosEghis/KaosEghis/core/wait_engine.py)
- [KaosEghis/tools/debug_macro_resolution.py](/E:/Kaos/KaosEghis/KaosEghis/tools/debug_macro_resolution.py)

Responsibilities:

- locate UI targets
- inspect enabled/visible/text state
- wait on conditions without changing UI state
- expose a local timing helper for target-resolution troubleshooting
- inspect the control under a clicked screen coordinate and extract the best available
  name/value metadata for operator troubleshooting

Current lookup preference:

1. direct scoped `child_window(...)` lookup when exact criteria are available
2. parent-scoped direct lookup when `parent_target_id` or `parent_automation_id` is configured
3. EMR scope-anchor lookup when an EMR UI target stores a narrowed container such as `grdOpdList`
4. ancestor-path scoped lookup when an EMR UI target stores a parsed Inspector parent chain
5. descendant scan fallback only when direct lookup does not resolve uniquely

Ancestor-path support:

- EMR UI targets can now store a normalized Inspector ancestor chain
- the chain is parsed from pasted Inspector text and saved with the target definition
- EMR UI targets can also store an explicit intermediate scope anchor such as `grdOpdList`
- Explicit EMR connect/reconnect eagerly caches the configured patient-status tab and
  prescription, symptom, diagnosis, and patient-list grid handles. Partial Win32 and
  UIA results are merged so a grid exposed through only one backend is still cached.
  Macro readiness validates and reuses these handles without repeating the descendant
  scan; reconnect is required after the underlying handles become stale.
- Cached grid-row targets resolve directly to the configured row proxy without
  enumerating every UIA cell. Parent-scoped name patterns first inspect immediate
  children, which keeps dynamic patient-status tabs such as `완료 (...)` on the fast
  path while retaining descendant and ancestor fallbacks for other controls.
- noisy top-level wrappers such as Desktop or duplicate outer windows are ignored
- resolution walks from the first stable inner ancestor down to the final target
- when a stable intermediate scope anchor exists, prefer it over a long ancestor chain
- this is intended to improve speed and reduce false matches in deep Windows Forms trees

Screen capture support:

- the EMR page includes a global click-capture helper
- default hotkey: `Ctrl+Shift+F9`
- Windows dispatches the registered hotkey through Qt's native event filter, so
  KaosEghis does not need to be the foreground application
- the next mouse click inspects the control under that coordinate
- captured details include coordinate, backend, handle, automation ID, control type,
  class name, best available value, and ancestor summary
- captured details are copied to the clipboard for quick reuse in target setup or
  debugging
- if global hotkeys are unavailable, the same flow can still be armed from the EMR page

Launcher access:

- global hotkey: `Ctrl+Alt+Shift+F11`
- restores KaosEghis and switches directly to `KaosEghis` -> `Launcher`
- works while another application is foreground through the Windows native hotkey
  dispatcher
- performs navigation only; it never starts a macro automatically

### Manual Explicit Write Tests

Modules:

- [KaosEghis/core/paste_test.py](/E:/Kaos/KaosEghis/KaosEghis/core/paste_test.py)
- [KaosEghis/core/write_test.py](/E:/Kaos/KaosEghis/KaosEghis/core/write_test.py)
- [KaosEghis/core/eghis_key_paste_test.py](/E:/Kaos/KaosEghis/KaosEghis/core/eghis_key_paste_test.py)

Responsibilities:

- explicit operator-triggered target tests
- narrow, test-only write methods
- logging of result/failure

These are not background automation engines.

### Stored Macro Automation

Modules:

- [KaosEghis/core/macro_runner.py](/E:/Kaos/KaosEghis/KaosEghis/core/macro_runner.py)
- [KaosEghis/core/safety_gate.py](/E:/Kaos/KaosEghis/KaosEghis/core/safety_gate.py)

Responsibilities:

- connector-gated run execution
- cancellation
- limited supported actions
- a dedicated `legacy_symptom_paste` path for old eGHIS symptom-entry flows that
  need the proven `focus -> F1 -> Enter -> paste -> Enter` sequence
- future EMR profile-aware resolution boundary
- per-run target caching so repeated steps can reuse the same resolved control
- one readiness check per run unless a step explicitly re-checks focus/window state
- cache invalidation on cancellation, readiness failure, and target-resolution failure
- dry-run/operator summary reporting for resolved target count and cache hit/miss counts

Current transition state:

- macros can now be bound to an EMR target profile
- dry run can report the resolved profile name
- actual click/send/paste target resolution is intentionally not switched over yet

### Hidden Credential Infrastructure

Planned module:

- `KaosEghis-pw`

Responsibilities:

- startup master-password prompt
- hidden locked/unlocked vault state
- hidden popup on a complex global hotkey
- internal service credential support
- manual external credential typing

Boundary:

- not a visible top-level automation tab
- not a general-purpose password manager
- not a browser extension replacement
- no clipboard-based password handling by default

### EMR Target Foundation

Modules:

- [KaosEghis/ui/tabs/emr_targets_page.py](/E:/Kaos/KaosEghis/KaosEghis/ui/tabs/emr_targets_page.py)
- [KaosEghis/db/repositories.py](/E:/Kaos/KaosEghis/KaosEghis/db/repositories.py)

Responsibilities:

- store named EMR target profiles
- store per-profile UI target definitions
- store optional per-target ancestor paths parsed from Inspector parent chains
- expose the active/default EMR profile for future macro runs
- keep credentials and secrets out of the profile model

## Current Automation Safety Posture

### Allowed

- read-only Eghis process/window detection
- read-only PostgreSQL reporting/polling
- dry-run macro validation
- explicit manual test actions initiated by the user

### Restricted

- real EMR automation is still deliberately limited
- not all stored macro actions are executable
- no broad unattended runner

## Scheduler Boundary

`KaosEghis-scheduler` now binds saved macros to a local time and selected weekdays.
It runs only inside the visible KaosEghis process, keeps jobs disabled by default,
uses a countdown, and records sanitized history. Startup calculates future times and
does not replay missed work.

Scheduled real execution uses the same `MacroRunner` path as manual execution. It
therefore cannot bypass connector, target-resolution, supported-action, or
single-execution safety. The guarded `eGHIS End-of-Day Backup and Power Off` macro is
implemented but is created only by an explicit Scheduler control, disabled by default,
hidden from Launcher, and never assigned a schedule automatically. Backup-file copying
is still not implemented, and claim-day work remains planning-only.

The end-of-day macro uses four editable EMR target keys:
`shutdown.lock_password`, `shutdown.close_yes`, `shutdown.backup_yes`, and
`shutdown.power_off_after_backup`. The first action may inspect the known eGHIS lock
dialog without treating that expected dialog as an unknown-modal failure. It types only
the password retrieved from the unlocked KaosEghis-pw entry `eGhis EMR`; the saved
username is ignored. Later actions independently activate the close Yes button, wait,
activate the database-backup Yes button, wait again, and select the exact backup
power-off checkbox. Missing or ambiguous targets stop execution. No
credential value is stored in SQLite, macro steps, Scheduler history, or UI logs.
- hidden background macro service
- generic recorder
- unconstrained mouse automation
- visible credential-management tab clutter for KaosEghis-pw

## Connector Requirement

Real macro execution must pass the Eghis connector gate.

That means:

- Eghis must be discovered
- process and window identity must match
- connector validity must hold
- blocked states must stop execution

## Patient Note Alert Monitor

KaosEghis polls only the configured current-patient chart-number UIA target while an
EMR connection is cached. The chart-number target must use a stable UIA selector rather
than the displayed numeric patient number, which changes between eGHIS sessions. When that
value changes, the monitor waits briefly for the patient view to settle, resolves the
configured memo target, and reads that memo once for the new patient. The default memo
path is the directly readable `TreatmentPtntMemo` target. Scope, Name, and an
Inspect.exe ancestor path remain optional fallbacks if a future eGHIS update changes
the control tree.
Automation IDs and exact UIA Name properties for both targets are editable under
Settings > General. The memo target also accepts a pasted Inspect.exe `Ancestors:`
block. That ancestor chain is tried first when configured; a single memo scope
Automation ID remains available as a fallback for future control-tree changes.
The chart UIA Name is optional and must be a stable Inspect.exe property. A patient's
current chart number must never be entered as the Name criterion because that value
changes when the selected patient changes.

The Vaccine patient-information fetch uses the separate eGHIS Patient Information view.
Its verified chart selector is `txt환자번호`; the changing chart number is read from the
control value. Other verified selectors are `txt환자명`, `txt주민번호`, `txt주소`,
`lblSexAge`, `dateEdit1`, `txt휴대폰`, and `txt전화`. The explicit fetch opens that view
only after the operator presses the Vaccine fetch button, then reads the fields from the
connected eGHIS process. It does not treat any displayed patient value as a UIA selector.

When the marker is present, a large red always-on-top warning asks the operator to
review the patient memo in EMR. The popup does not display the memo contents, does not
retain them, and hides automatically when the marker is absent or EMR disconnects.
The chart number remains transient in memory and is used only as a change token. It is
not logged, displayed, or persisted. The UIA check runs on a dedicated background
monitor thread and reuses resolved elements for that EMR connection. It does not focus
EMR, write text, run macros, or perform full-window descendant scans on every check.
If the connected EMR chart or memo target cannot be read, the top notification area
shows a generic monitor-unavailable warning. No chart number or memo content is
included in that warning.

## Read-Only Database Automation

The same safety stance applies to PostgreSQL access:

- read-only only
- write-like SQL rejected
- unavailable driver handled safely
- results normalized before local persistence

## Completed

- process/window detection
- connector state model
- read-only UI inspection
- conditional wait engine
- manual target write tests
- real runner skeleton
- read-only Eghis PostgreSQL adapter foundation
- EMR target profile persistence for future macro targeting

## Removed or Avoided

- silent runtime fake data generation in production polling paths
- broad unsafe UI writing through unreviewed automation flows

## Maintenance Triggers

Update this document whenever:

- a manual write path is added or removed
- a macro action becomes really executable
- connector gate rules change
- new unattended automation is introduced
