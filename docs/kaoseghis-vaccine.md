# KaosEghis-vaccine

Last updated: 2026-09-22

## Status

KaosEghis-vaccine now has its first working foundation. The `Vaccine` tab is no longer
a placeholder.

Current implemented pieces:

- SQLite tables:
  - `vaccine_types`
  - `vaccine_records`
  - `vaccine_audit_events`
- editable local vaccine type catalog
- local vaccine preparation record save/load/delete
- explicit general/private, general/private influenza, national Influenza, and national
  COVID type classification
- separate `COVID-19 (Pfizer)` and `COVID-19 (Moderna)` products, sharing one national
  COVID schedule and daily-count bucket
- explicit prepared/printed/completed/cancelled/error record lifecycle
- operator-confirmed completion and cancellation corrections
- sanitized lifecycle audit without patient values
- vaccine dropdown ordering with up/down arrow controls
- EMR-target-based patient context fetch into the Vaccine page
- one fetched patient context can create separate simultaneous-vaccination records
- visible same-day `Influenza` and `COVID-19` counts
- a separate `예외` count under each daily-cap counter, derived from completed
  national records with `counts_toward_cap = false` on today's completion date;
  excludes private shots, unfinished records and cancellations, with no change
  to cap accounting or printed labels
- structured single-current-year Influenza and COVID schedule settings
- date-picker-based program windows and inclusive birth-date ranges
- configuration-driven national influenza program preview
- exact inclusive birth-date and schedule-boundary checks
- daily-cap, child-dose-review, and elderly-exception-review results
- native Windows thermal-label printing through the configured printer
- successful first print checkpoints the record as `printed`, then `completed`
- completed-record reprints that never alter daily counts
- post-print consent, guarded resident-number lookup in the selected system, and
  retry/skip/form clearing without additional printing or count changes

Still not implemented in this stage:

- final vaccination registration automation (patient lookup is implemented)
- EMR writeback/charting
- automatic eligibility confirmation inside the national systems

## EMR Patient Targets

Database initialization adds these configurable UIA targets to every EMR profile:

| Target key | Purpose | Seeded selector |
| --- | --- | --- |
| `vaccine.patient_chart_no` | Patient chart number | `txt환자번호` |
| `vaccine.patient_resident_id` | Resident number | `txt주민번호` |
| `vaccine.patient_name` | Patient name | `txt환자명` |
| `vaccine.patient_sex_age` | Sex and age | `lblSexAge` (patient-information fallback: `txtSexAge`) |
| `vaccine.patient_birth_date` | Date of birth | `dateEdit1` |
| `vaccine.patient_phone` | Preferred mobile telephone | `txt휴대폰` |
| `vaccine.patient_telephone` | Telephone fallback | `txt전화` |
| `vaccine.patient_address` | Address | `txt주소` |

The patient-information DOB control remains the preferred source. If that control is
empty or unavailable, Vaccine derives DOB from the captured resident number and keeps
the result only as `YYYY-MM-DD` in the current patient context.

The `lblSexAge`/`txtSexAge` UIA value also remains preferred. Some eGHIS builds do not
expose that label reliably, even while the other Patient Information fields are
readable. When it is missing, Vaccine derives `M`/`F` from the captured resident-number
classification digit and calculates full age from the derived birth date as of the
current day. No resident number is logged during this fallback.

The target definitions are available under `Macros -> EMR`. Initialization fills an
untouched placeholder with these verified Automation IDs but never overwrites a target
that already has an operator-configured selector. Numeric values that match a displayed
patient number are removed and replaced by `txt환자번호` because patient data is not a
stable selector.

`Fetch from EMR` is an explicit operator action. It requires the manually cached eGHIS
connection, focuses the connected process through the connector gate, and clicks the
current Patient Information opener at screen coordinate `(210, 115)`. It then waits for
`txt환자번호` and reads all configured fields from that same eGHIS process/window. The
reader refreshes the trusted eGHIS helper-process family while the patient-information
window opens. Before broad discovery, it tries the foreground popup only when it is
visible, belongs to that trusted process family, and is not the main EMR window. The
chart control must resolve uniquely beneath the named Patient Information scope;
focus is rechecked after lookup. An empty chart in that verified popup remains pending
instead of falling through to another window's patient. There is up to a 600 ms opening
grace period for these narrow paths, with no delay when the popup is already ready.
The exact fallback `Edit` lookup enumerates visible native windows owned by
that trusted family, then queries only their UIA subtrees with a process condition. It
does not query the entire desktop UIA tree. Existing process-window fallback discovery
still includes hidden UIA host windows when the native-window fast path finds no match.
The exact chart control that establishes readiness is retained for value reading instead
of being rediscovered in a second WinForms tree scan. Value extraction follows the same
UIA ValuePattern and WinForms legacy-value paths used by the in-app capture tool.
Its readable value is captured immediately, and the nearest `환자 기초 정보` ancestor is
used as the scope for the remaining fields instead of rescanning the full eGHIS window.
This coordinate is a temporary opener fallback; the patient fields themselves use stable
UIA Automation IDs. The fetch never runs on startup or in the background.
An external timing helper must have sufficient access to the EMR process: a standard-user
helper inspecting an elevated EMR may see only the outer window. Zero matches in that
case are not evidence of a fast or missing control. Read-only performance checks must
not click, focus, type, run macros, access the source DB, or log patient values.
After the configured fields are read, KaosEghis sends one `{ESC}` to close the Patient
Information view. Escape is never sent when that view could not be resolved.

Each successful `Fetch from EMR` starts a new unsaved vaccine record, even when
fetching the same patient again. It detaches any previously loaded/saved record and
prepared Flu + COVID pair, resets both program checks, and clears the vaccine selection
and charting previews. The operator must select a vaccine for each successful fetch,
even for the same patient. Existing records are unchanged; a new database record is created only
by Save, Print, or explicit pair preparation. A failed fetch preserves the current
form and record references.

The non-editable vaccine dropdown has no default selection on startup, after a new EMR
fetch or Clear form/New vaccine record, or when the selected type disappears during
refresh. Add/Edit/Delete refresh the dropdown immediately. An ordinary refresh preserves
an explicit existing selection by ID only while its name, code, program, chart note and
enabled state remain unchanged; a material edit requires reselection. Explicitly loading
a saved record restores its type by ID (a missing ID never falls back to a matching name).
The closed dropdown ignores mouse-wheel changes, and focusing or highlighting a popup
row alone is not accepted as a selection. Without a selected
vaccine, Save/Print and pair preparation are disabled and their handlers also reject
the action. Flu + COVID preparation still requires an explicitly selected COVID product.

The dropdown has a solid amber background with dark text and a `Select vaccine`
placeholder, including while hovered or focused. It displays the selection without a
duplicate label below; its tooltip provides the full name for longer entries. Fetch
from EMR uses cyan text; Print label uses green text when enabled. Both buttons keep
transparent backgrounds, including on hover and press; disabled controls are muted.
Up/down arrow controls reorder the selected type while preserving its ID
and selection.
Printing a loaded record is blocked if its vaccine ID/name differs from the visible
selection, so changing the dropdown cannot silently print the previously saved vaccine.

When the current chart number has records for today, `Edit today's record` appears
beside Save/Print. Its menu lists each record's ID, vaccine, and status, including
separate flu and COVID records. Selecting one explicitly loads it for editing;
`Save record` then updates that record instead of inserting another. The record ID
is shown above the previews. `New vaccine record` returns to a separate preparation.
Matching uses the exact chart number, never a name-only match. The date is the
completion date when available, otherwise the creation date in local time. Other
dates remain accessible through the DB page. Editing does not change completion
status or increment daily counts.

For simultaneous influenza and COVID vaccinations, fetch once and prepare the pair
before printing. `New vaccine record` can also reuse the displayed patient context
while preparing/saving separate records before printing; it clears the record
reference and vaccine selection. Once post-print system entry succeeds or is skipped,
the form is cleared and another fetch is needed for a separate preparation.

The first successful explicit fetch discovers and caches the Patient Information scope
and its available native field controls. Nothing opens or preloads this window at app
startup. The cache retains only handles and identity metadata, never patient values or
UIA wrappers, and is not written to SQLite. Each fetch still opens the view normally.

On a repeat fetch, fresh UIA wrappers are acquired directly from the cached handles.
An identity-valid cache is retained briefly while the popup is hidden or its chart field
is empty during reopening. No patient values are read from a hidden cached scope. If
it never becomes ready, the fetch fails and discards the cache; broad fallback discovery
also rejects hidden chart controls and hidden scopes. A new verified foreground popup
can supersede the pending old popup immediately. Missing optional fields are still
searched again, preserving support for controls that appear later.
The connected window, process creation times, scope/control runtime IDs, Automation IDs,
control types, visibility, and native child ownership must still match. Valid cached
fields avoid another descendant search and always read current values. A missing or
replaced control, changed settings, recreated popup, or restarted EMR invalidates the
cache and uses normal discovery to rebuild it. No COM objects are shared across threads.

Missing fields are searched again rather than treating their absence as permanent.
Controls without verifiable native handles retain the existing lookup path; a scope
without a native handle cannot use the field cache. For a cacheable fetch, the chart
number is reread after the other values: if it changes or clears, no patient context is
accepted and the cache is discarded. This verifies consistency during the read, not
completion of all EMR background loading.

Regression tests demonstrate two descendant searches on first fetch and none on a
fully cached repeat fetch, including a switch to a different patient's fresh values.
Live elapsed-time improvement remains to be measured on the operator's EMR. Fetch is
still synchronous; moving it off the GUI thread is a separate change.

The opened window is a resolved pywinauto UIA wrapper, so target lookup indexes its
descendants by exact Automation ID. All configured patient fields are read from one
shared descendant index rather than rescanning the window for every field. Failure to
find the chart-number target is reported as a target-configuration problem instead of
being mislabeled as a generic window-readiness failure.

Some eGHIS views retain hidden controls with the same Automation ID as the currently
opened Patient Information field. Exact-ID lookup therefore accepts a match only when
there is one candidate overall or exactly one visible candidate. Multiple visible
matches remain blocked rather than risking capture from the wrong patient surface.

The Patient Information form may be hosted by an eGHIS helper such as
`eGhis.Forms.exe` rather than the connected `eGhis.exe` PID. Fetch therefore searches
the cached process and only descendants whose executable name begins with `eGhis`.
Unrelated child applications are excluded, and the operation remains read-only after
the explicit operator click that opens Patient Information.

The preferred telephone value is `txt휴대폰`; `txt전화` is used only when the mobile
field is blank. Date of birth is shown transiently on the Vaccine page and is not added
to the local Vaccine record schema by this change. No fetched values are written to logs.

Resident-number formatting has an explicit output boundary. The captured hyphenated
value, such as `700101-1234567`, is preserved for operator display and thermal-label
output. Only the value handed to a verified external vaccination-system resident-number
field is normalized to `7001011234567`. Capture, preview, and saved form values are not
silently rewritten. The post-print system-input adapter applies this normalization
immediately before input and requires 13 ASCII digits.

This specification preserves the proven workflow and rule structure from the former
`eGhis_Assistant` Labeler module. The vaccine catalog and seasonal rule values must be
editable so the clinic can update products, birthdays, schedules, and limits without a
code change.

## Current Vaccine Page Surface

The current `Vaccine` page now exposes:

- patient-context fetch from configured EMR targets
- managed vaccine type dropdown and chart-note preview
- saved local preparation records
- today's `Influenza` count with configured cap
- today's `COVID-19` count with configured cap
- one editable Influenza schedule and one editable COVID schedule
- explicit program-year labels, date windows, birth-date ranges, activation, and caps

The counts are derived only from local records whose lifecycle is `completed`, whose
explicit `counts_toward_cap` snapshot is true, and whose `completed_on` date is today.
Prepared, printed, cancelled, errored, general/private, and merely previewed records do
not increment a national count. Repeating completion for the same record is idempotent,
and cancelling a completed record removes it from the count while retaining a sanitized
audit event. `Mark completed` remains an explicit correction action. The normal label
path records the lifecycle only after the Windows print spooler accepts the label.

## Vaccine Record Lifecycle

Every new local record starts as `prepared`. The supported lifecycle states are:

- `prepared`: local preparation only; never counted
- `printed`: print-success checkpoint; never counted by itself
- `completed`: explicit completion; counted only when its snapshotted program type is
  national Influenza or national COVID and the workflow marks it counted
- `cancelled`: explicit correction; excluded from daily counts
- `error`: failed workflow state; excluded from daily counts

The vaccine type's program classification is copied into the record when it is prepared,
so later catalog edits cannot silently rewrite completed history. General/private
vaccinations can never be forced into a national counter. Lifecycle changes and deletion
are explicit operator actions and create audit entries containing only record ID, event,
status transition, and a fixed non-patient summary.

## Current Influenza Program Preview

The Main page provides `Check influenza program`. It reads the resident ID only long
enough to derive a transient birth date, then evaluates:

- the explicitly enabled influenza season
- the configured inclusive birth-date groups
- the configured start/end window for the matched group
- the current local counted total and configured daily cap
- child one-dose/two-dose ambiguity
- elderly exception review when that option is explicitly enabled

Possible results are eligible, blocked, cap reached, operator review required,
private/unmatched, patient context required, and configuration error. The displayed
result contains no resident ID or patient name.

`program_enabled` defaults to `false`. The seeded 2026-2027 opening dates now reflect
the September 2026 KDCA amendment. Known old saved dates are amended once and affected
schedules disabled for review; custom dates and other seasons are preserved. The
operator must review every date and configured birth range before changing it to
`true`. See the [revised schedule and migration details](national-vaccination-schedules-and-rules.md).
For national Influenza label printing, the same evaluation is mandatory. A blocked
result stops printing. A child-dose or rural-exception review result requires explicit
operator confirmation, and the result's count treatment is snapshotted at completion.
This check performs no vaccination-system input or eGHIS write.

### Medically Underserved Rural-Area Influenza Rule

The clinic uses the configured rural-area exception for the three elderly opening
groups. It changes both eligibility and cap handling:

- when the 75+ window opens, 75+ vaccinations consume the shared 100-dose cap;
  70-74 and 65-69 require confirmation of a patient-specific exception and do not
  consume that cap when confirmed
- when the 70-74 window opens, 75+ and 70-74 consume the shared cap; 65-69 remains the
  patient-confirmed, non-counted exception path
- when the 65-69 window opens, all three elderly groups consume the shared cap

There is one shared national Influenza cap of 100 per day. Counted elderly and counted
pediatric vaccinations contribute to that same total; there are not separate elderly
and child caps. Rural-exception elderly vaccinations remain outside the shared total
only until that patient's normal age-group window opens.

Before the first elderly opening date, none of the elderly groups is open. The
exception behavior is enabled explicitly in Vaccine Settings and is never inferred
from the clinic or workstation location. The operator must verify a recognized
patient-specific exception, such as qualifying registered residence or another
official exception reason. These rules must be reviewed against the official program
notice each year.

Detailed source, schedule, count, and annual configuration guidance is maintained in
[`national-vaccination-schedules-and-rules.md`](national-vaccination-schedules-and-rules.md).

### Pediatric Influenza Opening Rule

The configured two-dose pediatric window opens before the one-dose window. During that
early interval, KaosEghis must stop before label printing and alert the operator to
check the vaccination system manually for whether the child is a first-time influenza
recipient who requires two doses. A confirmed vaccination consumes the shared daily
Influenza cap together with counted elderly vaccinations. Once the one-dose window
opens, an age-eligible child can proceed without that specific first-window alert,
subject to the configured end date and cap.

## Vaccine Schedule Settings

`Vaccine -> Settings` contains two structured pages: `Influenza schedule` and
`COVID schedule`. Each page represents the single schedule currently maintained by
the clinic. At the next program year, the operator edits that same form in place after
checking the official dates and birth-date boundaries.

There is no saved season library, year selector, duplicate-season action, or automatic
roll-forward. The program-year label is editable reference text. Influenza exposes the
staggered elderly dates, child one-dose/two-dose windows, inclusive age-group birth
ranges, exception-review option, and daily cap. COVID exposes its program window,
inclusive national-program birth range, and daily cap.

An incomplete schedule can be retained while disabled. Enabling a schedule requires
all of its dates and birth ranges to be complete and ordered correctly. The structured
forms continue to store the values in the established settings JSON so the eligibility
engine remains compatible.

## Confirmed Requirements

- The daily vaccination cap remains an operational rule.
- The default cap is `100` for a counted program bucket.
- The cap value must be editable, but it must be actively enforced while that program
  is enabled.
- Vaccine products and their display/chart/label names must be editable.
- The operator may select more than one vaccine for the same patient, including a
  dedicated national influenza + national COVID combination workflow.
- National influenza eligibility remains dependent on the patient's age group,
  birthday boundary, and the date schedule for that group.
- Exception influenza age groups remain a distinct supported path.
- The birthday boundaries, age-group schedules, exception behavior, and counter
  behavior must follow the legacy Labeler rule structure.
- Seasonal values must be reviewed explicitly before a season is enabled.
- General/private influenza never consumes the national influenza cap. When its patient
  matches a configured national influenza target group, label printing requires an
  explicit operator confirmation that the non-national product is intentional.
- Other paid/private vaccines bypass national-program eligibility checking.

## Intended Operator Workflow

1. The operator explicitly loads the current patient from the connected eGHIS window.
2. KaosEghis reads the minimum transient patient context needed for the workflow.
3. The operator selects a vaccine from the editable vaccine catalog.
4. National influenza or national COVID vaccination invokes the configured program
   rules. General/private influenza performs a target-group safety check but never
   consumes a national count; other vaccines bypass national-program checking.
5. KaosEghis shows the eligibility result, applicable age group, schedule state,
   counter state, and reason for any block or exception.
6. The operator reviews or edits the prepared label and chart text.
7. An explicit action prints the thermal label and checkpoints the local record.
8. After successful printing and checkpointing, a Yes/No prompt offers patient
   lookup in the corresponding vaccine system. No is the default.
9. Yes focuses that system, enters the printed record's resident number without
   its hyphen, and sends one `Enter`. No skips system entry.
10. Successful input or an explicit skip clears patient fields, record/pair
    references, vaccine selection, previews of patient information, and program-check
    results. Saved records remain. The operator reviews the
    external lookup result and performs vaccination registration manually.

KaosEghis must never submit the final vaccination record without an explicit operator
action.

### Vaccine Shortcuts (lookup-first revision 2026-10-06)

The Main page has four explicit actions: `National Influenza`, `National COVID`,
`National Flu+COVID`, and `General Influenza`.

- Each opens a confirmation before fetching, creating a record, or printing.
  The confirmation authorizes the label(s), system lookup(s), and existing EMR
  chart-text handoff together. Cancel performs none of those actions.
- COVID products must be chosen every time, with no preselected Pfizer/Moderna.
  Choices come from the currently enabled vaccine catalog by program type, not
  hardcoded IDs or name matching. Multiple flu entries also require a choice.
- On Yes, fetch a fresh EMR patient and detach the previous record/selection.
  A failed fetch or missing name, chart number, or complete resident number stops
  before printing. Changed/disabled vaccine configuration also stops the shortcut.
- An existing non-cancelled record for this chart/date and requested program
  stops the shortcut and directs the operator to `Edit today's record`.
  National/private flu are both checked for a flu shortcut; either COVID product
  matches the COVID check. The shortcut never silently reprints or counts twice.
- Existing age, schedule, cap, general/private target warnings, and explicit
  exception confirmations remain in force. The pair fetches once, creates two
  separate records, and checks/prints each independently.
- Each selected vaccine now runs in this order: resident-number lookup in its
  corresponding system, existing program check/operator exception confirmation,
  then label printing/completion. Normal eligible cases print without another
  confirmation; existing child-dose and general/private warnings still apply.
- Exception confirmation occurs only after lookup input succeeds. The operator
  checks the address and exception eligibility in the external national system
  before choosing Yes; No is the default and stops further printing. Input success
  means that the resident number and Enter were sent, not that a patient result
  loaded or an address/exception was automatically verified.
- For Flu+COVID, perform lookup/review/printing for Flu first, then COVID, so each
  review takes place before changing to the next system. No second resident-number
  insertion occurs after printing. Clipboard/EMR charting follows only after all
  selected labels complete. Normal manual printing retains its existing workflow.
- Entry failure retains the form and prepared record without printing/counting
  that vaccine. `Retry entry` retries that system, then resumes checking/printing
  only after success; `Cancel shortcut` stops without clearing the patient form.
  Login/launch stays available for recovery. A successful earlier pair label is
  not reprinted or counted again when the second system is retried.
- Declined/blocked checks, changed records, stopped lookup, and print failures
  stop further labels/charting and retain the form and saved records. A partial
  pair keeps its completed first record and uncompleted second record; status
  reports the completed-label count. Charting text for already completed labels
  remains available for manual recovery. No automatic retry, clinical registration,
  or address-based eligibility decision is introduced.
- Conflicting actions and repeated shortcut activation are blocked during the
  workflow. No new automatic login, reset, clinical registration, or EMR database
  query is introduced. Keep the same patient selected in EMR throughout.

The previously idle session reminder starts on the existing valid print attempt
as a fallback for manually opened systems. Subsequent shortcut prints do not
restart an already-running reminder.

Validation uses synthetic patients, temporary local databases, and mocked EMR,
printer, clipboard, and system input. Live end-to-end verification is still needed.
The initial shortcut implementation's Windows regression run passed 2,026 tests,
including 49 shortcut cases;
native Qt previews were checked at 1280x900 and 1920x1080 without opening the live
app or sending printer/EMR input.

Lookup-first revision validation (2026-10-06): 88 focused workflow tests passed.
The full isolated run passed 3,290 tests with 26 existing label-rendering/layout
failures; all 26 were reproduced with the unchanged `10afd0c` VaccineTab source.
After the final review-dialog reentry guards, the non-renderer vaccine regression
group passed 549 tests (the two baseline shortcut-layout cases were deselected).
No real EMR interaction, resident-number entry, clipboard update, or printing was
performed by these tests, and the running application was not restarted.

### External System Handoff

The post-print handoff uses the printed vaccine's configured external system,
then the manually connected EMR:

1. Verify and focus the expected system window.
2. Double-click its configured resident-number input coordinate, then send `Delete`
   to clear the selected text. Do not send `Ctrl+A`: it can move the caret to the
   second resident-number field.
3. Type all 13 resident-number digits with the hyphen removed. Recheck the target
   before clearing and before each digit; stop if focus or desktop changes.
4. Send one `Enter` to request that system's patient lookup.
5. After confirmed input dispatch, copy the corresponding charting text to the clipboard.
6. Once all requested lookups have been dispatched, focus EMR and send `F1`,
   `Enter`, then `Ctrl+V`. There is no final Enter or automatic chart submission.
7. Clear the form. All vaccine-system search-result review, eligibility confirmation,
   entry, and final registration remain manual operator actions.

Routing uses the record's program type: national influenza goes to the influenza
browser system; national COVID (both Pfizer and Moderna) goes to COVID; general
and private influenza go to General. Unknown mappings stop without typing.

`Print prepared pair` waits for both actual print results and local checkpoints
before asking once about both systems. A prior completed status is not proof that
the current reprint succeeded. On partial printing failure, no handoff starts and
the form remains for operator review. Existing successful print checkpoints remain.

Printing success here means the printer service accepted the output, not physical
verification that a label emerged. Print/checkpoint failure never clears the form.
Reprints retain existing record IDs and do not add to daily counts.

System-entry failure keeps the form and shows `Retry entry` and `Skip and clear`.
Retry does not print, save, or update counts. In a two-system handoff, successful
systems are removed from the pending queue, so retry only visits unfinished systems.
If input was interrupted or submission is uncertain, inspect the system before
retrying. There are no automatic input retries. `Stop` cancels further input after
the current external call returns; already-sent input cannot be undone.

Charting text is snapshotted before the handoff prompt from each printed record's
vaccine-type note, using the same fallback as the Charting text preview. Only
successfully dispatched lookups contribute notes. Flu + COVID notes are joined
with a newline; a retry adds only the newly successful system's note. A wholly
failed, cancelled, or declined handoff does not change the clipboard. No patient
identifiers are automatically appended. Clipboard copying runs in the GUI completion
handler, before form clearing. If it fails, input is not retried: the status warns
and the note remains in the Charting text preview for manual copying; no EMR keys
are sent. This does not certify that the national system accepted the lookup or
registered a vaccination.

EMR charting runs on a separate background continuation after clipboard copying.
For Flu + COVID, partial success copies the available note but does not start EMR
charting yet. After the remaining lookup succeeds, both notes are pasted together
once. Skipping the remaining lookup does not paste a partial note automatically.
The connected EMR process/root window is validated with existing focus helpers,
without grid-cache preloading. Each key checks desktop availability, held inputs,
and the exact foreground EMR window/focus. Short guarded waits separate the keys.
Clipboard contents must still match the captured note immediately before paste.
An unexpected popup, focus change, Stop request, or clipboard failure stops the
sequence without refocusing, replaying the lookup, or retrying an uncertain paste.
The text remains on the clipboard, and charting failure also retains it in the
preview after form clearing. Check the chart before pasting manually to avoid a
duplicate. The operator must keep the same patient selected in EMR throughout:
these focus checks do not independently verify patient identity or pasted contents.

The handoff runs on a COM-initialized worker, using transient snapshots of the
printed records rather than live form text. Patient editing, Fetch, Print, and
record-changing buttons are disabled while a handoff is pending or EMR charting
is active. Login/launch can
be used after a failed handoff, before Retry. Automatic session resets are disabled;
manual resets are blocked during shortcuts, printing, the handoff prompt, and
pending/active handoffs.

Before input, the worker verifies an unlocked Windows desktop, no held input keys,
Virtual Desktop 1, and an unambiguous target. Each typing stage rechecks focus and
the desktop, with a 15-second cooperative deadline per system. Provider calls
cannot be forcibly interrupted, but they do not run on the Qt GUI thread. No
resident number is sent via the clipboard, logs, status messages, or Qt signals.

It must never open an unrelated system, select a vaccine program implicitly, submit a
vaccination record, or continue after an unexpected window/target failure.

The captured targets are used only after explicit post-print consent:

- General vaccine system: top-level window name `예방접종통합관리시스템`, class
  `CyWindowClass`, with resident-number input coordinate `(448, 2074)` because the
  input does not expose a distinct UIA control. Its configured non-clinical
  session-reset coordinate is `(1154, 1968)`.
- Influenza browser system: double-click the configured resident-number input coordinate
  (default capture `(2924, 1415)`), send Delete without Ctrl+A, then type all
  13 digits without the hyphen using ordinary digit-key events
  (`vk_packet=False`, not Unicode packets or clipboard paste), then send one Enter.
  The `Resident input X/Y` settings are the primary entry target, not a fallback.
  `edtPtntRrn1` remains available for system-launch readiness checks but is not
  required for this coordinate handoff.
  Resolution requires one matching browser window and a visible document/frame at
  the configured OIS origin/application directory containing the saved point.
  A configured window/tab title also filters the browser. Before clicking, the
  point's nearest UIA Document must be one of those trusted documents; no exact
  Edit control, Automation ID, or UIA keyboard-focus flag is required.
  Browser foreground, document identity/URL/bounds, point ownership, desktop, and
  unchanged native keyboard focus are rechecked during entry. A failed check
  stops without Enter and retains the form. No field-value readback is required,
  so success confirms key dispatch only, not that the website accepted all digits
  or found the intended patient. Review the resulting lookup manually.
  Keep the input coordinates calibrated: these guards do not prove that the point
  is still the resident field after an in-page layout change. A blocking native
  popup, wrong document, invalid coordinate, or multiple matching browser windows
  stops the handoff; no popup is dismissed automatically.
- COVID system: top-level window name `코로나19통합관리시스템`, class
  `CyWindowClass`. Its configured non-clinical session-reset coordinate is
  `(2456, 1982)` and its resident-number input coordinate is `(1466, 2107)`.

For the two native systems, the configured point must still be inside and owned
by the exact foreground title/class window, and native keyboard focus must remain
unchanged after the click. These applications do not expose the field separately,
so field contents cannot be independently verified. Keep their saved layout/input
coordinates calibrated; an internal layout change can move a field even if the
point is still inside the correct window. Missing, moved-outside, covered, or
ambiguous targets stop; the handoff does not automatically open/login to systems.

Resident numbers remain available only to the selected workflow's transient input path;
they must not appear in automation logs or status messages.

`Vaccine -> Settings -> System targets` stores these editable window titles, classes,
stable UIA automation IDs, and input coordinates. It intentionally does not store
numeric Windows/UIA Handle values because the operating system recreates them every
application launch.

### KDCA OIS Launch URLs

The System targets page also stores the clinic's editable static OIS deep links. These
are system-entry pages, not `menuid` portal-navigation URLs and not session-bearing
links:

| System | Default launch URL |
| --- | --- |
| General vaccine | `https://ois.kdca.go.kr/iris/index_run.jsp` |
| COVID | `https://ois.kdca.go.kr/covr/index_run.jsp` |
| Influenza | `https://ois.kdca.go.kr/iroi/indexWSP.jsp` |

The Open buttons follow the signed-in portal's real menu controls; they do not type
these URLs into the address bar. The saved URLs remain exact selectors for launch
links on a system-selection page and for destination-origin verification. They contain
no credentials, session IDs, patient values, or vaccination data. Before it opens a selected service, KaosEghis opens the KDCA portal
and checks the current browser page using the configured accessible controls:

- visible `로그아웃` link/button only, or the KDCA session anchor `/isc/logout.do`
  (including its absolute `https://is.kdca.go.kr/isc/logout.do` form) exposed by Chrome
  accessibility: signed in; the system menu is used without accessing the vault;
- visible `공동인증서 로그인` link/button only, or the KDCA certificate anchor
  `javascript:fnPkiCall('pLo')` exposed by Chrome accessibility: sign-in required; the
  guarded certificate flow runs;
- both, neither, duplicate actionable links/buttons, or inaccessible controls:
  wait through loading/redirects, then stop safely if still unresolved at the deadline.

Chrome can expose a text heading/child and the actual login link with the same name.
Only the clickable link/button counts toward sign-in detection; a matching `Text`
element is not another login action and cannot establish an authenticated session.
Each check reads login and logout controls from one UIA tree snapshot.

The editable `Portal menu path` and `Launch control text (optional)` fields are under
`Vaccine > Settings > System targets` for each system:

- General: `시스템을 선택해주세요 > 예방접종관리` (captured portal link
  `menuid=197625`), then, after the selection page loads, the image with
  accessible/alt text `예방접종통합관리시스템` (HTML ID `ocs_button1`, image
  `/irad/regs/common/images/main/case5_off.gif`).
- Influenza: `시스템을 선택해주세요 > 예방접종관리`, then the image with accessible/alt text
  `현물공급인플루엔자시스템` (captured HTML ID `inf_button1`).
- COVID: `시스템을 선택해주세요 > 코로나19 예방접종관리 > 등록시스템 > 예방접종등록시스템`.
  The COVID root has HTML `menuid=203443`; its empty `href`, and the empty `href`
  on `등록시스템`, are intentional menu controls, not navigation URLs. If the leaf link
  (captured `menuid=203488`) is already visible, it is clicked directly. Otherwise
  only the configured ancestors are expanded, each once.

Chrome includes KDCA's icon-font prefix (observed `U+EA80`) in the final COVID
link's accessible name. Menu matching ignores leading private-use icon characters,
but still matches the remaining label exactly. The selector also accepts the observed
`시스템을 선택해주세요 / 현재 선택된 시스템 : ...` accessible name after a system
has been selected. Other prefixes/suffixes are not accepted, and multiple matches
remain ambiguous. These display decorations do not need to be copied into settings.

Existing saved copies of the previous defaults are upgraded once on database initialization.
Custom paths, custom launch-control names, and routes with a custom launch URL are
preserved. All three paths and the selection-image names remain editable here.

The captured menu IDs are documentation, not URLs navigated to directly. Normal
control activation preserves the website's own navigation, frames, and session handoff.
No tokens/cookies are extracted and no page scripts are injected. If a selector is
missing or ambiguous, the operation stops with the current stage and leaves the page
for manual review. A permission/notice dialog is never accepted automatically.

#### Login/Launch Reliability

The explicit KDCA operation runs in one background COM worker. Progress identifies
portal detection, certificate picker, password field, confirmed sign-in, portal menu,
optional selection control, and destination detection. Other launch buttons and Fetch from EMR are
disabled while it runs; Reset Now is blocked. Session maintenance is manual only.
`Stop` prevents subsequent actions after the current UIA call returns. No second
worker is started while that call is outstanding.

- Browser title alone is insufficient: a visible browser Document must expose the
  configured portal origin through UIA. With multiple portal windows, the verified
  foreground window is preferred; unresolved ambiguity stops the operation.
  Existing document runtime IDs are recorded before opening the portal so a stale
  logout link in an old tab cannot satisfy the new session check.
- UIA browser wrappers are rebound by HWND across navigation. Read-only readiness
  checks retry for up to 30 seconds per phase, including delayed certificate rows
  and confirmation buttons. A cell and its Text child count as one certificate;
  distinct duplicate cells remain ambiguous.
- Native certificate dialogs must be owned by that browser; the known web picker
  remains scoped to it. Password focus is checked before and after selecting existing
  text. The secret is retrieved again immediately before use in case the vault was
  locked during loading, and is submitted only once. No clipboard is used.
- After positive sign-in, the menu is activated inside that same verified portal
  Document. A native modal popup or changed focus stops activation. Exact control
  names/URLs are required; a Text child is not a second clickable link. Images are
  considered only when an explicit launch-control name is configured. Foreign-origin
  iframe controls are excluded. Each matched action is sent once, with no direct-URL
  fallback and no second click after an uncertain provider error.
- Chrome exposes the General/Influenza launch link and its contained image
  (`ocs_button1` / `inf_button1`) as two UIA elements with the same name. A matching
  image whose nearest actionable ancestor is also a matched link/button is counted
  once, and that ancestor is activated. Separate links, separate windows, and controls
  across a Document boundary are not merged; true ambiguity still stops the launch.
- A system-selection page or Influenza popup can be followed in the original browser
  window, or a newly visible/owned window in the same browser process. Unrelated
  pre-existing browser windows and other browser processes are excluded. Influenza
  readiness requires its configured input under the OIS `/iroi/` application, not
  just any page at the OIS host.
- Success now requires the configured General/COVID title **and** class to be
  visible, or the configured influenza resident input to appear on the OIS page.
  Merely accepting a URL is not success. Destination detection waits up to 30 seconds;
  launch permission dialogs and failed launches produce an actionable failure, not
  an automatic duplicate launch. An already-open native system is brought forward,
  not relaunched; multiple matching native windows stop the action.
- Logs include fixed workflow stages, outcome, and elapsed time only, never passwords,
  certificate contents, patient data, page contents, or raw provider exceptions.

Live acceptance checks: restart KaosEghis, try each Open action once signed out and
once signed in, test a delayed certificate picker and a portal notice, and confirm
that failure/Stop re-enables the buttons. Unit tests use fake portals, vault values,
and windows; they do not sign in to KDCA or send real patient data.

`Vaccine -> Main` provides explicit `Open General`, `Open Influenza`, and `Open COVID`
actions. They never read or enter patient data, and never automate a vaccination step.

### Manual Window Placement (2026-10-01)

Window placement is entirely operator-controlled for General, Influenza, and COVID.
There is no automatic placement or planned replacement: no Shift-drag, FancyZones
snapping, `Win+Arrow` sequence, saved-rectangle restoration, monitor relocation,
or positioning timer. The current source already had the former snapping sequence
removed; this decision also removes the remaining future auto-placement proposal.

Open actions only launch/detect the requested system or focus an already-open
native system. The readiness wait verifies launch, not window placement. Regression
tests prohibit mouse/keyboard placement input and Win32 move/resize calls on launch.

Resident-number and session-reset coordinates are unchanged. Manually position each
system so those saved points match its inputs, or update the points in System targets.
Opening a system does not click either point. Existing focus and Virtual Desktop 1
selection for resident-number entry/manual resets remain; they do not relocate
individual windows, resize them, or place them on a monitor.

### Explicit KDCA Certificate Login

`Vaccine -> Main -> Log in to KDCA` is an explicit, one-at-a-time certificate-login
helper for the KDCA portal at `https://is.kdca.go.kr/`. It is not a generic browser
autofill feature and never runs at startup, on a timer, after a vaccination action, or
as a retry loop.

The editable configuration under `Vaccine -> Settings -> System targets` contains only
non-secret selectors: the portal URL, browser-title fragment, `공동인증서 로그인` control
text, optional captured login-button X/Y fallback, certificate-picker/password-window
text, logged-in (`로그아웃`) control text, title fragments, certificate label, optional
password Automation ID, password control
type, confirmation-control text, and the
KaosEghis-pw credential-entry reference. The initial certificate label is `이진성34`; the
initial credential entry reference is `공인인증서 - 이진성`.

On an explicit click, KaosEghis opens the configured portal and first establishes one
unambiguous sign-in state. It requests the KaosEghis-pw vault password only when the
configured login control is visible and the configured logged-in control is not. It then
requires exactly one matching certificate picker, certificate label, password field, and
confirmation control. It types the vault password as Windows Unicode keyboard input
directly into that one verified control without using clipboard. It waits for the
configured logged-in control before reporting success. Missing, stale, or ambiguous
controls stop the sequence before the password is typed.

After certificate confirmation, the portal may briefly retain its login button or
expose no session controls while redirecting. KaosEghis waits for a unique visible
logout control for the bounded sign-in timeout instead of stopping at the old login
page. It does not type the certificate password twice or dismiss portal notices.
If a notice prevents confirmation, close it manually and retry Open General/COVID/
Influenza; an already authenticated session skips password entry. The selected
system link opens only after positive authentication confirmation.

The certificate picker can be a separate desktop window or KDCA's web dialog inside
the identified browser. The web dialog has an unnamed UIA `Window` with class token
`xwup_cert_pop`; its visible `인증서 입력 (전자서명)` heading supplies the configured
title match. Certificate, password, and confirmation searches stay inside that dialog,
not the whole browser. Hidden, disabled, or duplicate pickers are rejected. The observed
password Automation ID is `xwup_certselect_tek_input1`, editable in System targets;
leaving it blank still requires one unambiguous input within the verified dialog.
The confirmation control is verified before any password input.

Password input uses the full Windows `INPUT` union layout (40 bytes on Win64,
28 bytes on Win32); a keyboard-only union has the wrong size and is rejected by
Windows. Input is considered successful only if all requested key events are sent.

Some Chrome installations do not expose portal controls through Windows UI Automation.
For only the `공동인증서 로그인` portal button, the operator may save an Inspector-captured
screen X/Y fallback. KaosEghis uses it only after it has identified exactly one visible
KDCA browser window and verified that the screen point belongs to that same unminimized
window. A zero coordinate disables this fallback; no generic foreground click occurs.

The certificate password remains encrypted in KaosEghis-pw and is never copied to
SQLite settings, macros, clipboard history, notifications, or logs. If the certificate
provider blocks synthetic keyboard input or changes its password dialog, KaosEghis stops
for manual entry; it does not guess a replacement control.

### Manual Session Reset and Reminder

Automatic resets and automatic retries have been removed for all vaccine systems.
The old `vaccine_session_keeper_enabled` value is ignored even when stored as `true`;
saving System targets writes it as `false`. There is no automatic-reset toggle.

Reset Now in Main and System targets is the only trigger for external input. General
and COVID retain their saved session-reset coordinates, guarded by these checks:

- exactly one visible native window has the configured exact title and class;
- Windows is unlocked and the system window is enabled and not minimized;
- no keyboard/mouse button is held;
- **virtual Desktop 1** (the first desktop in Windows Task View, not monitor 1)
  has been selected and verified;
- the saved reset point is inside that window; and
- the window at that point belongs to the verified system rather than an overlapping
  application.

After a manual press and a unique matching system window is found, Reset Now switches
to virtual Desktop 1 and brings the exact General/COVID window forward before testing
the reset point. A window that remains covered, moved away from the saved point, or
cannot be focused is not clicked. It uses the Windows-only
[pyvda desktop API](https://github.com/mirober/pyvda), not repeated Ctrl+Win+Arrow
shortcuts. The dependency is declared in both project dependency files. No desktop
is created, renamed, or deleted, and individual windows are not moved to another
desktop or monitor by a session reset. The operator remains on Desktop 1 afterward.

After switching, window identity, input activity, Desktop 1, and point ownership
are checked again. If the operator resumes input or leaves Desktop 1, that attempt
sends no click. Missing desktop support, ambiguous targets, or failed checks block
that attempt. Nothing schedules a retry; the operator decides when to press again.

Reset Now immediately displays progress on Main and System targets. Local settings
are read without migrations or writes, with a short database timeout, and the connection
is closed before any window checks. All window inspection and reset input runs in one
background worker, so a slow browser/UIA provider does not freeze the interface.
Failures (including settings-read failures) are shown instead of silently returning.
The existing Stop button cancels a pending reset. A 60-second limit also cancels it;
both prevent subsequent input when a stalled provider call finally returns. Another
reset cannot start until that worker exits. The final summary retains results already
sent before cancellation, and a cancelled/failed attempt does not restart the reminder.
These limits only stop a user-requested operation; they never schedule a reset.

For Flu, Reset Now looks for one visible browser page matching the configured HTTPS
launch origin and system path. It requires a top-level page, not an embedded Flu frame
inside the portal. Pressing Reset Now is the operator's approval to send F5; there is
no extra KaosEghis confirmation/warning popup. Unfinished Flu input may be lost.
Focus, page identity, URL, input state,
and Desktop 1 are rechecked before sending F5 once. It does not dismiss browser reload
warnings, resubmit forms, log in, enter credentials, or retry. F5 being sent is not
proof that the server renewed the session or that the login remained valid.

The shared passive reminder is idle when the Vaccine workspace is constructed;
app startup, page visits, settings reloads, and portal login alone do not start it.
It starts after a successful General/Flu/COVID launch result confirms the destination
system (including a verified already-open system). Failed or cancelled launches do
not start it. If a system was opened manually, the first valid label-print attempt
starts the reminder immediately before calling the printer service, even if that
service subsequently reports a print failure. Missing selection, declined program
checks, and cancelled pair-print confirmation do not start it.

Single-label and paired-label printing share this fallback. Further launches,
prints, or reprints never restart an already-running reminder. There remains one
shared reminder, not separate counters per system. A successful manual reset can
also start an idle reminder or restart an active one under the rules below.

Until started, the progress bar shows `Reminder not started`, Reset Now keeps its
normal text color and remains manually available, and no reminder popup is scheduled.
Once started, the reminder remains active while other pages are displayed. Its state
is process-local: restarting KaosEghis leaves it idle again until a qualifying action.
It does not infer when a manually opened system actually signed in, and never
inspects a browser or sends input by itself:

- Before 60 minutes: Reset Now uses its normal text color.
- From 60 to 90 minutes: both Reset Now buttons gradually change toward red.
- At 90 minutes and later: the text stays red.
- At 115 minutes: one nonmodal, topmost popup offers Reset Now and Close, even when
  the Vaccine page is hidden. It is shown without activating/stealing typing focus.
- Close (also the default/Escape action) dismisses only the popup; age and red text
  remain. There is no repeated popup until a completed manual reset starts a new cycle.
- Reset Now performs the same guarded manual action. It is disabled during conflicting
  vaccine operations; Close remains available.

The reminder age resets only when at least one action was sent and every other target
was either acted on or not open. A partial failure or declined Flu refresh retains the
old reminder age. Successful completion also closes any outstanding reminder popup.
The settings progress bar shows elapsed reminder age, not an automatic-action countdown
or verified session expiry. The appearance/popup check runs every 30 seconds only
after the reminder has started.

The 2026-10-01 reminder-start change passed **226 focused tests** and the full
**1,977-test** isolated suite. Launches, print output, and reset input were mocked;
no live vaccine-system actions or real label printing were used for verification.

The activity check reads only timing and whether keys/buttons are held; it does
not capture typed content. It uses Windows
[GetLastInputInfo](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlastinputinfo)
and the current-down bit from
[GetAsyncKeyState](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getasynckeystate).
Point ownership is checked again immediately before sending the click. This reduces
input races but cannot guarantee that the operator will not resume moving the mouse
at that instant. **Reset sent** means the click was sent, not that the external
application's new session expiry was read or confirmed.

Results are shown in Main and System targets, without logging patient or credential
values. Flu's actual timeout and whether refresh renews it remain unverified.

## Combined Influenza + COVID Workflow

National influenza and COVID vaccination seasons commonly overlap. KaosEghis-vaccine
must therefore support preparing both vaccinations in one guarded patient workflow.

Current implementation: `Prepare Flu + COVID` reuses the loaded patient context to
create two separate local preparation records. The operator selects the COVID product
(Pfizer or Moderna) in the Vaccine dropdown before preparing the pair. `Print prepared
pair` first requires one explicit operator confirmation, then runs each label's own
eligibility gate and print checkpoint. It stops and reports the affected vaccine if either label cannot
be printed; it never treats a partial pair as fully completed.

- Provide a quick `Influenza + COVID` selection in addition to individual vaccine
  selection.
- Load the current patient context once and reuse it transiently for both preparations.
- Evaluate influenza and COVID eligibility independently. One passing result must not
  hide or override a block, warning, or exception for the other vaccine.
- Show separate eligibility, schedule, product, and counter results for influenza and
  COVID before printing or external-system preparation.
- Prepare a separate label for each selected vaccine by default so vaccine/product and
  counter information remain unambiguous.
- Present both label previews together and allow the operator to print both in one
  explicit print action or print either label individually.
- Increment each applicable counter exactly once only after its configured successful
  workflow checkpoint.
- Enter the patient's national ID into the influenza and COVID vaccination programs in
  sequence through one explicit `Prepare both programs` action.
- Verify the expected destination window before each insertion. Failure in one program
  must stop that insertion, report which program failed, and must not silently continue
  with an unknown window.
- Return to eGHIS after preparation and produce one editable charting summary that
  clearly lists both vaccines.
- Final registration/submission in eGHIS and both national programs remains manual.

The combined workflow coordinates two independent vaccine preparations; it does not
merge their eligibility rules, counters, labels, or submission state.

Both COVID products use the `national_covid` program type, so their completed records
contribute to the same national COVID daily count. Existing legacy generic `COVID-19`
catalog entries and historical records remain unchanged.

## Editable Vaccine Catalog

The catalog must support local add, edit, disable, reorder, and delete operations.
Suggested editable fields:

- display name
- label text
- chart text/name
- program type:
  - general/private
  - national influenza
  - national COVID
- enabled
- counted program bucket, if any
- requires national-program preparation
- label template

The initial catalog should be seeded from the legacy Labeler list, but the seed is not
an immutable clinical list. The clinic remains able to update products without editing
Python source.

## Legacy Influenza Rule Model

The following rule structure remains required.

### Age Groups

- general/paid influenza
- elderly 75 years and older
- elderly 70-74 years
- elderly 65-69 years
- eligible child
- exception influenza

Each age group uses editable inclusive birth-date boundaries rather than an age value
calculated with an undocumented convention. The configured boundaries determine the
group exactly as the legacy Labeler did.

### Schedule Windows

Editable seasonal schedule values must include:

- start date for 75+ elderly vaccination
- start date for 70-74 elderly vaccination
- start date for 65-69 elderly vaccination
- elderly program end date
- start and end dates for children requiring two doses
- start and end dates for children requiring one dose
- inclusive birth-date ranges for every elderly and child group

The application must display the active schedule and matching birth range used for a
decision. A season cannot be enabled until all required values are valid.

### Eligibility Flow

- A patient outside national influenza birth ranges follows the general/paid path.
- An eligible elderly group may use the counted national path only after its configured
  start date and before the configured end date.
- A child follows the configured one-dose or two-dose schedule. Where dose history
  cannot be determined automatically, the operator must answer an explicit question.
- An elderly patient whose group is not yet in the standard schedule may follow the
  exception path only after explicit operator confirmation of the configured exception
  condition.
- If the configured program period has not started or has ended, the national path is
  blocked with a clear reason.
- Boundary comparisons must be covered by tests at the exact first/last eligible
  birthday and first/last schedule date.

### Daily Counters and Cap

- The default counted-program cap is `100` per day.
- The configured cap is editable per program bucket.
- Standard elderly and child national influenza vaccinations contribute to the legacy
  counted influenza total.
- Exception influenza remains separately counted and does not consume the standard
  influenza cap, matching the legacy behavior.
- Paid influenza does not consume the national influenza cap.
- National COVID uses its configured daily counted bucket and cap.
- A count is committed only by the explicit completion checkpoint. The printing stage
  calls that checkpoint only after confirmed print success.
- A failed, cancelled, or merely previewed workflow must not increase a counter.
- Counter correction requires an explicit operator action and a local non-PHI audit
  entry.

## Labels and Printing

KaosEghis now reuses the visual hierarchy of the former Labeler module:

- thermal label size: `80 mm x 40 mm`
- preview before printing
- configurable printer name
- configurable label fields and vaccine wording
- explicit Print action only

The printer setting `vaccine_label_printer_name` defaults to the legacy Windows printer
name `4BARCODE 4B-2054L` and is editable under `Vaccine -> Settings`. The print service
does not hardcode a printer. It uses `QPrinter` in Windows native-spooler mode with an
`80 mm x 40 mm` page and zero margins. It does not log label fields or raw print errors.
The complete label is first rasterized at the printer's reported device-pixel dimensions
and DPI, then submitted as one opaque black-and-white image. This avoids sending the
date, counters, fine dividers and patient fields as separate native text/vector commands
that the thermal driver may omit. The raster exists only in memory; no patient-image
file is saved. A successful submission still requires physical output verification.

Label fields use device-pixel fonts fitted to their individual print rectangles. The
vaccine title stays on one line, with space above/below the divider lines; long custom
names shrink instead of wrapping into clipped lines.
All vaccine titles use the compact pill-title font size as their standard, including
plain-text general/private products. Long names may shrink further to fit; short plain
titles are not enlarged beyond that standard.

National influenza titles follow the configured birth-date group: `노인독감` for
elderly groups, `소아독감` for child groups, and `노인독감.예외` for an approved
non-counted elderly exception. The standard Pfizer/Moderna entries print as
`코로나.화이자` / `코로나.모더나`. These are print titles only: saved vaccine product
names, eligibility gates and shared daily counters are unchanged. General/private
products retain their configured names. Reprints use the record's completion date and
saved counted/non-counted decision; if the current configuration cannot identify its
influenza group, the original saved vaccine name is retained rather than guessing.

On paper, national influenza uses `노인 (독감)`, `소아 (독감)`, or `노인 (독감) 예외`:
parentheses here represent a black pill containing white `독감` text, not printed
punctuation. `노인`, `소아`, and `예외` stay outside the pill as black text.
The COVID manufacturer is visually separated from `코로나`: `화이자` is
inside a white outlined pill and `모더나` is white text inside a black pill. The
manufacturer name remains explicit, so recognition does not depend on shading alone.
Pills fit the measured text plus small padding, with a reduced height. Prefix, pill,
and optional exception suffix form one compact centered group rather than filling
separate columns. Both horizontal divider lines remain. The title band has extra
vertical space above and below the centered title without enlarging the text or pill.
Pill styles are explicitly selected from the national program result, not inferred by
the renderer from product names. All other products, including general/private
influenza, print their saved list name as plain text, even if that name resembles a
national label title.

All printed text is bold. Patient name and chart number are left aligned at the top,
`xx/100` is centered on the label, and the daily total is right aligned. These are
separate fields, so changing the total does not move the cap counter.
National influenza shows `오늘 총 독감: xxx` at the right. This is
today's total completed national influenza records (elderly, children and non-counted
national exceptions), not the `x/100` cap counter. Private influenza is excluded and
private labels do not show this total. The pending first print includes its own record
in the displayed total; a completed-record reprint does not add another. Cancelled,
deleted, prepared-only and printed-only records do not contribute. Only records with
the `national_influenza` program classification are counted; vaccine names do not change
that classification. This read-only total does not change the existing completion or
cap-accounting rules.

National Pfizer/Moderna labels instead show `xx/100  오늘 화이자:xxx` or
`xx/100  오늘 모더나:xxx`. Their cap counter is still shared across both manufacturers;
the adjacent total is specific to that manufacturer and includes national exceptions.
Totals use completed national COVID records' saved product names, recognizing the
standard English names and Korean print-title equivalents. Unknown custom names are
not guessed into a manufacturer. Private, cancelled, prepared-only, printed-only and
other-day records are excluded; reprints do not add to these totals.

Below the lower divider, resident number prints at the left, phone in the middle,
and the date as `yy.MM.dd` at the right. Patient identity stays at the top so it is easier
to notice. All fields fit their own print areas without dropping or truncating values;
unusually long details may use smaller text. General/private products use the same
bold patient-first layout.

An explicit successful print does the following in order:

1. saves a new preparation record when necessary;
2. submits the label to the configured Windows printer;
3. changes `prepared` to `printed` only when submission succeeds;
4. changes the record to `completed`, applying the evaluated count treatment once.

Reprinting an already completed record sends another label but never changes its
completion timestamp or daily count. A missing/unavailable printer or failed submission
leaves a preparation record uncompleted and uncounted. National COVID printing uses the
editable, disabled-by-default 2026-2027 65+ evaluator. Patients outside those configured
age groups remain blocked for manual verification in the national vaccination system;
KaosEghis does not infer high-risk eligibility.

## Vaccination Program Preparation

All three vaccination destinations are reached only after logging in through the
government vaccination-system homepage. The operator must complete the Korean digital
certificate login and launch the required destinations before patient preparation can
begin.

KaosEghis recognizes three separate external contexts:

- general national vaccination program: separately launched desktop application
- influenza vaccination program: HTML page in a browser
- COVID vaccination program: separately launched desktop application

The general and COVID desktop applications do not expose usable UI Automation controls.
The influenza system is browser-based and must be handled as a distinct browser target,
not as another native application window.

### Session Preparation

Provide one explicit `Prepare vaccination systems` surface with independent readiness
indicators:

- Government portal: not opened / login required / authenticated
- General vaccination: not started / ready / stale
- Influenza: not opened / ready / stale
- COVID vaccination: not started / ready / stale

The intended start-of-day sequence is:

1. The operator explicitly presses `Log in to KDCA`; the action requires an unlocked
   KaosEghis-pw vault and makes no attempt when the vault is locked.
2. KaosEghis opens the configured government portal URL and verifies the configured
   certificate-picker/password targets before typing the vault password.
3. KaosEghis follows the configured portal links that launch the required desktop
   applications and influenza browser page.
4. KaosEghis verifies each destination independently and caches only non-secret runtime
   identity such as process ID, window handle/title, or configured browser target.
5. Patient workflows use the cached destinations while they remain valid.
6. A closed, restarted, mismatched, or stale destination is marked `Reconnect required`
   and only that destination must be prepared again.

No patient workflow may attempt a program insertion until the required destination is
ready. The combined influenza + COVID workflow requires both the influenza browser page
and COVID desktop application to be ready before `Prepare both programs` begins.

### Manual Session Maintenance

`Vaccine -> Main -> KDCA systems -> Reset Now` is the last button in the system row.
The same action remains in `Vaccine -> Settings -> System targets -> Reset Now`.
Both buttons are disabled during KDCA login/launch, printing, and resident-number handoff.
Each press makes one guarded General/COVID reset attempt and offers a separately
confirmed Flu refresh. There are no automatic resets or retries. Both buttons fade
toward red after 60 minutes; a 115-minute popup remains available from other pages.
See Manual Session Reset and Reminder above for failure and dismissal behavior.

Manual reset input remains isolated from registration, lookup, vaccination counters,
and charting. Label printing can start the passive reminder but never sends reset input.

### Authentication Boundary

- KaosEghis must not store the Korean digital-certificate password in SQLite, settings,
  logs, notifications, or workflow history.
- `Log in to KDCA` reads the password only from an already unlocked KaosEghis-pw entry;
  it never presents, remembers, or persists the value in the Vaccine surface.
- The password exists only in transient process memory for the one explicit login
  sequence. Python cannot guarantee physical memory zeroization, so it must never be
  retained beyond the shortest practical scope.
- Do not place the password on the clipboard.
- Do not record password keystrokes, screenshots, target values, or raw login errors.
- Insert the password only after verifying the expected certificate login window and
  password field. A mismatch aborts the entire launch sequence.
- If the certificate software rejects synthetic input or uses a protected input control,
  stop for manual password entry and continue only after positive login verification.
- A future persistent credential-store integration would require a separate security
  review; it is not part of the planned workflow.
- Gateway/session cookies and application sessions remain owned by the government portal,
  browser, and launched applications.

### Patient Entry

Any coordinate or keyboard fallback for the native applications must be:

- tied to an explicit selected program profile
- manually initiated
- preceded by positive window identity verification
- limited to the known national-ID field and required navigation
- stopped immediately when the expected window or field is not found
- followed by manual operator review and submission

The browser-based influenza workflow should prefer a verified configured browser target
when technically available. It must not assume that native-application coordinates or
UIA selectors apply to the HTML page.

No fixed coordinate from the legacy application is considered valid until recaptured
and tested against the current installation.

## Data and Privacy

EMR patient context remains transient until the operator explicitly chooses `Save
record`. The existing local `vaccine_records` table then stores the minimum fields shown
on its preparation form so the operator can edit, reprint, correct, or delete that local
record. These local records are sensitive clinical workflow data and must remain in the
protected KaosEghis data directory. They must never be written to routine logs,
notifications, lifecycle audit summaries, or external services without a separately
verified workflow.

Routine logs and `vaccine_audit_events` must not contain:

- resident registration number or national ID
- patient name
- date of birth
- sex
- phone number
- address
- diagnosis
- EMR notes
- insurance information

Durable local data consists of:

- vaccine catalog
- seasonal eligibility rules
- label templates
- printer configuration
- explicit local preparation records created by the operator
- daily counts derived from completed, counted national-program records
- sanitized counter corrections and workflow errors

Notifications and routine logs must never contain patient values.

## Planned Local Model

The implementation keeps configuration separate from patient workflow records and
sanitized lifecycle audit:

- vaccine products/catalog
- program and counter buckets
- seasonal age groups and inclusive birthday boundaries
- seasonal schedule windows
- editable daily cap values
- label templates
- completion-derived daily counter totals
- sanitized operational audit

The local records are an operator workflow ledger, not an authoritative replacement for
eGHIS or the national vaccination system. Final clinical submission remains manual.

## Safety and Validation

Before operational use, tests must cover:

- editable vaccine catalog CRUD and ordering
- disabled vaccine products cannot be selected for a new workflow
- combined influenza + COVID selection loads patient context once
- combined workflow evaluates eligibility and counters independently
- combined workflow produces two distinct label previews and supports one explicit
  print-both action
- startup performs no certificate login and stores no certificate password
- `Log in to KDCA` requires an unlocked KaosEghis-pw credential and never persists,
  copies, or logs the supplied value
- password insertion occurs only after positive certificate-window/field verification
- login failure/cancellation discards the transient password and launches no blind clicks
- each external destination has an independent ready/stale state
- combined preparation blocks until both influenza and COVID destinations are ready
- session keeper is opt-in, excludes influenza, and touches only a positively identified
  general/COVID session-extension action
- failed session verification produces `Reconnect required` rather than a blind click
- failure to identify either vaccination-program window blocks that program insertion
  without entering the national ID into an unknown window
- exact birthday boundary inclusion/exclusion for every age group
- exact schedule start/end boundary behavior
- child one-dose/two-dose operator confirmation
- exception influenza confirmation and separate counter behavior
- counted influenza stops at the configured cap of 100 by default
- paid influenza does not consume the national cap
- preview/cancel/failure does not increment a counter
- successful checkpoint increments exactly once
- counter correction is explicit and audited without patient information
- national ID remains transient and absent from SQLite and logs
- label preview uses the configured template and `80 mm x 40 mm` page
- external-program preparation blocks on an unexpected window
- no final vaccination submission occurs automatically

## Implementation Sequence

1. Editable vaccine catalog and local preparation records. Done.
2. Transient current-patient reader from the connected eGHIS profile. Done as an
   EMR-target-based fetch. The reader queries exact Automation IDs through native UIA,
   prefers the visible `txt환자번호` beneath the `환자 기초 정보` ancestor when eGHIS
   exposes duplicate IDs elsewhere, and indexes the remaining fields in one scoped
   query. It does not scan or log raw patient rows.
3. Pure eligibility/counter decision engine with boundary tests. Done as a guarded
   preview; child-dose and exception confirmation remain.
4. Explicit lifecycle, national-program classification, completion-derived count, and
   sanitized correction audit. Done.
5. Thermal label preview and Windows native printing. Done for one explicit label.
The published 2026-2027 65+ COVID schedule is represented by a disabled-by-default,
editable evaluator. Immunocompromised and facility-resident eligibility remains a
manual national-system verification path and is never inferred from eGHIS.

For both seasonal Flu and COVID, rural-area exceptions are an operator-confirmed path:
the local option is enabled by default, but every early-group exception still shows a
confirmation alert and is non-counted. The app never derives that confirmation from an
EMR address.
6. Guarded external vaccination-program preparation.
7. eGHIS chart-text preparation.
8. Final end-to-end dummy-patient validation.
