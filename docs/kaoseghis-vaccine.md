# KaosEghis-vaccine

Last updated: 2026-09-01

## Status

KaosEghis-vaccine now has its first working foundation. The `Vaccine` tab is no longer
a placeholder.

Current implemented pieces:

- SQLite tables:
  - `vaccine_types`
  - `vaccine_records`
- editable local vaccine type catalog
- local vaccine preparation record save/load/delete
- drag/drop ordering for vaccine types
- EMR-target-based patient context fetch into the Vaccine page
- visible same-day `Influenza` and `COVID-19` counts
- structured single-current-year Influenza and COVID schedule settings
- date-picker-based program windows and inclusive birth-date ranges
- configuration-driven national influenza program preview
- exact inclusive birth-date and schedule-boundary checks
- daily-cap, child-dose-review, and elderly-exception-review results

Still not implemented in this stage:

- thermal label printing
- vaccination program automation
- EMR writeback/charting
- vaccination completion lifecycle

## EMR Patient Targets

Database initialization adds these configurable UIA targets to every EMR profile:

| Target key | Purpose | Seeded selector |
| --- | --- | --- |
| `vaccine.patient_chart_no` | Patient chart number | `txt환자번호` |
| `vaccine.patient_resident_id` | Resident number | `txt주민번호` |
| `vaccine.patient_name` | Patient name | `txt환자명` |
| `vaccine.patient_sex_age` | Sex and age | `lblSexAge` |
| `vaccine.patient_birth_date` | Date of birth | `dateEdit1` |
| `vaccine.patient_phone` | Preferred mobile telephone | `txt휴대폰` |
| `vaccine.patient_telephone` | Telephone fallback | `txt전화` |
| `vaccine.patient_address` | Address | `txt주소` |

The target definitions are available under `Macros -> EMR`. Initialization fills an
untouched placeholder with these verified Automation IDs but never overwrites a target
that already has an operator-configured selector. Numeric values that match a displayed
patient number are removed and replaced by `txt환자번호` because patient data is not a
stable selector.

`Fetch from EMR` is an explicit operator action. It requires the manually cached eGHIS
connection, focuses the connected process through the connector gate, and clicks the
current Patient Information opener at screen coordinate `(210, 115)`. It then waits for
`txt환자번호` and reads all configured fields from that same eGHIS process/window. This
coordinate is a temporary opener fallback; the patient fields themselves use stable UIA
Automation IDs. The fetch never runs on startup or in the background.
After the configured fields are read, KaosEghis sends one `{ESC}` to close the Patient
Information view. Escape is never sent when that view could not be resolved.

The preferred telephone value is `txt휴대폰`; `txt전화` is used only when the mobile
field is blank. Date of birth is shown transiently on the Vaccine page and is not added
to the local Vaccine record schema by this change. No fetched values are written to logs.

Resident-number formatting has an explicit output boundary. The captured hyphenated
value, such as `700101-1234567`, is preserved for operator display and thermal-label
output. Only the value handed to a verified external vaccination-system resident-number
field is normalized to `7001011234567`. Capture, preview, and saved form values are not
silently rewritten. The external vaccination-system typing workflow is not implemented
yet; its future adapter must apply this normalization immediately before input.

This specification preserves the proven workflow and rule structure from the former
`eGhis_Assistant` Labeler module. The vaccine catalog and seasonal rule values must be
editable so the clinic can update products, birthdays, schedules, and limits without a
code change.

## Current Vaccine Page Surface

The current `Vaccine` page now exposes:

- patient-context fetch from configured EMR targets
- editable vaccine type list and chart-note preview
- saved local preparation records
- today's `Influenza` count with configured cap
- today's `COVID-19` count with configured cap
- one editable Influenza schedule and one editable COVID schedule
- explicit program-year labels, date windows, birth-date ranges, activation, and caps

The counts are derived from local `vaccine_records.created_at` rows for the current
day. The influenza preview uses the current total conservatively when checking the
configured cap, but previewing never increments the count. The later print/completion
lifecycle must make the durable counter checkpoint explicit before operational use.

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

`program_enabled` defaults to `false`. Existing or seeded dates are configuration
placeholders, not a claim about the current national program. The operator must enter
and review the official season dates and birth ranges before changing it to `true`.
This preview performs no printing, counter increment, vaccination-system input, or
eGHIS write.

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
- Paid influenza and other private vaccines do not use the national influenza
  eligibility gate.

## Intended Operator Workflow

1. The operator explicitly loads the current patient from the connected eGHIS window.
2. KaosEghis reads the minimum transient patient context needed for the workflow.
3. The operator selects a vaccine from the editable vaccine catalog.
4. National influenza or national COVID vaccination invokes the configured program
   rules. Other vaccines bypass national-program eligibility checking.
5. KaosEghis shows the eligibility result, applicable age group, schedule state,
   counter state, and reason for any block or exception.
6. The operator reviews or edits the prepared label and chart text.
7. An explicit action prints the thermal label.
8. An explicit action focuses the selected vaccination program and enters the
   patient's national ID into its known input field.
9. KaosEghis returns focus to eGHIS and prepares the configured vaccination chart text.
10. The operator confirms or edits the entry in both eGHIS and the vaccination program.

KaosEghis must never submit the final vaccination record without an explicit operator
action.

## Combined Influenza + COVID Workflow

National influenza and COVID vaccination seasons commonly overlap. KaosEghis-vaccine
must therefore support preparing both vaccinations in one guarded patient workflow.

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
- A count is committed only after successful explicit printing/confirmation at the
  workflow checkpoint chosen during implementation.
- A failed, cancelled, or merely previewed workflow must not increase a counter.
- Counter correction requires an explicit operator action and a local non-PHI audit
  entry.

## Labels and Printing

The first implementation should reuse the visual format of the former Labeler module:

- thermal label size: `80 mm x 40 mm`
- preview before printing
- configurable printer name
- configurable label fields and vaccine wording
- explicit Print action only

The legacy printer name `4BARCODE 4B-2054L` may be offered as a migration default, but
must not remain hardcoded in the printing service.

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

1. `Open Vaccine Systems` displays a masked certificate-password prompt with no saved or
   prefilled value. Cancelling the prompt performs no login or launch action.
2. KaosEghis opens the configured government portal URL.
3. KaosEghis verifies the expected certificate login window and inserts the transient
   password only into that positively identified password field.
4. KaosEghis follows the configured portal links that launch the required desktop
   applications and influenza browser page.
5. KaosEghis verifies each destination independently and caches only non-secret runtime
   identity such as process ID, window handle/title, or configured browser target.
6. Patient workflows use the cached destinations while they remain valid.
7. A closed, restarted, mismatched, or stale destination is marked `Reconnect required`
   and only that destination must be prepared again.

No patient workflow may attempt a program insertion until the required destination is
ready. The combined influenza + COVID workflow requires both the influenza browser page
and COVID desktop application to be ready before `Prepare both programs` begins.

### Two-Hour Session Keeper

The general and COVID vaccination applications automatically log out after approximately
two hours without use. The influenza browser system is excluded from this native-app
session keeper.

Provide an explicit `Keep vaccination sessions active` toggle after the operator has
completed authenticated session preparation and KaosEghis has verified the relevant
applications.

- Off by default until a successful manual session preparation.
- Maintain independent timers for the general and COVID applications.
- Default to a configurable refresh interval shorter than the two-hour timeout, with
  `90 minutes` as the initial safe default.
- Refresh only a positively identified application/window and only through its known
  non-clinical session-extension action.
- Never use a generic click against whichever window happens to be foreground.
- Never enter the certificate password or attempt certificate login.
- Never open, edit, or submit a patient record as part of session maintenance.
- Do not run the native-app keeper for the influenza HTML browser page.
- If the expected window, session-extension control, or screen state cannot be verified,
  skip the action, mark that application `Reconnect required`, and notify the operator.
- Stop the timer when the operator disconnects, the process exits, the window identity
  changes, the desktop is unavailable, or KaosEghis closes.
- Show last successful extension and next planned extension for each application.
- Keep logs sanitized to application name, result, and time; no patient or credential
  values are permitted.

This is session maintenance only. It must remain isolated from vaccination registration,
patient lookup, label printing, counters, and charting.

### Authentication Boundary

- KaosEghis must not store the Korean digital-certificate password in SQLite, settings,
  logs, notifications, or workflow history.
- `Open Vaccine Systems` prompts for the password every time with a masked input field.
- The prompt has no `Remember password` option and must never be prefilled.
- The password exists only in transient process memory for the current launch sequence.
- Clear the prompt immediately and release password references as soon as login succeeds,
  fails, or is cancelled. Python cannot guarantee physical memory zeroization, so the
  value must never be retained beyond the shortest practical scope.
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

Patient context is transient. KaosEghis-vaccine must not persist or log:

- resident registration number or national ID
- patient name
- date of birth
- sex
- phone number
- address
- diagnosis
- EMR notes
- insurance information

Permitted durable data is configuration and aggregate operational state:

- vaccine catalog
- seasonal eligibility rules
- label templates
- printer configuration
- aggregate daily counters
- sanitized counter corrections and workflow errors

Notifications and routine logs must never contain patient values.

## Planned Local Model

The implementation should keep configuration separate from aggregate counters:

- vaccine products/catalog
- program and counter buckets
- seasonal age groups and inclusive birthday boundaries
- seasonal schedule windows
- editable daily cap values
- label templates
- aggregate daily counter totals
- sanitized operational audit

Patient-level vaccination history is not part of the local KaosEghis-vaccine model.

## Safety and Validation

Before operational use, tests must cover:

- editable vaccine catalog CRUD and ordering
- disabled vaccine products cannot be selected for a new workflow
- combined influenza + COVID selection loads patient context once
- combined workflow evaluates eligibility and counters independently
- combined workflow produces two distinct label previews and supports one explicit
  print-both action
- startup performs no certificate login and stores no certificate password
- `Open Vaccine Systems` uses a fresh masked password prompt and never persists or copies
  the supplied value
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
2. Transient current-patient reader from the connected eGHIS profile. Done as a first EMR-target-based fetch.
3. Pure eligibility/counter decision engine with boundary tests. Done as a guarded
   preview; child-dose confirmation and the print/completion counter checkpoint remain.
4. Thermal label preview and printing service.
5. Guarded external vaccination-program preparation.
6. eGHIS chart-text preparation.
7. Final end-to-end dummy-patient validation.
