# KaosEghis Plans

Last updated: 2026-08-08

## Current Working State

The project has moved beyond scaffold-only status and now contains real guarded foundations in several areas:

- local SQLite persistence
- Eghis connector state
- UI target registry
- EMR target profiles
- macro-to-profile binding
- dry-run and partial real macro infrastructure
- read-only PostgreSQL access
- PACS local worklist
- flu weekly reporting

## Active Product Tracks

### Core KaosEghis

- keep daily-use macro access simple
- preserve strict automation safety boundaries
- improve top-level navigation and coherence
- add launcher collections without losing direct-run speed for simple macros

### KaosEghis-SOCL

- first editable composition milestone implemented as a top-level tab
- reviewed Subjective and Physical Exam vocabulary is seeded once into local SQLite
- physician can add, rename, delete, reorder, and rewrite rendered phrases
- only explicitly checked findings are rendered
- output remains editable and clipboard-only
- encounter selections and generated text are not persisted
- no diagnosis, Assessment/Plan, order, or EMR automation behavior
- detailed design: `docs/kaoseghis-socl.md`

### KaosEghis-pacs

- read-only Eghis image-study order polling
- local worklist persistence
- cancellation tracking
- local KaosPACS API bridge
- business-state ownership stays in KaosEghis-pacs
- imaging-state ownership stays in KaosPACS

### KaosEghis-flu

- weekly influenza report surface
- weekly practice-count/statistics backend
- no export-grade workflow yet

### KaosEghis-vaccine

- next planned plugin implementation priority
- reuse the proven label formats and printing workflow from the former Labeler module
- preserve the legacy influenza eligibility structure: editable inclusive birthday
  groups, editable age-group schedules, one-dose/two-dose child schedules, and the
  exception-influenza path
- keep the daily counted-program cap, with `100` as the default and an editable value
- make the vaccine catalog, chart/label wording, seasonal boundaries, schedule dates,
  exception rules, and cap configuration editable without a code change
- keep exception influenza separately counted from standard capped influenza, matching
  the legacy behavior
- add a first-class influenza + COVID workflow that loads the patient once, evaluates
  both programs independently, prints separate labels together, and prepares both
  national-program patient searches in sequence
- model the government portal login as explicit session preparation: `Open Vaccine
  Systems` asks for the certificate password in a fresh masked prompt, uses it only after
  positive login-window verification, and then independently verifies/caches the general
  native app, influenza browser page, and COVID native app
- do not store or log the certificate password; stale program sessions require explicit
  operator reconnection
- add an opt-in session keeper for the general and COVID native applications' two-hour
  idle logout; use independent verified-window timers, exclude the influenza browser,
  and never perform a blind foreground-window click
- require explicit operator review before enabling each seasonal rule set
- implementation must remain separate from the existing Flu-Report statistics workflow
- detailed specification: `docs/kaoseghis-vaccine.md`
- national schedule and rule reference:
  `docs/national-vaccination-schedules-and-rules.md`

### KaosEghis-pw

- hidden infrastructure module, not a visible tab
- startup master-password prompt
- if unlocked:
  - internal KaosEghis service surfaces may use stored credentials
- if locked:
  - the rest of the app still opens
  - credential-backed actions stay blocked
- hidden popup on a complex global hotkey
- the same hotkey:
  - prompts for master password when locked
  - opens service/action popup when unlocked
- supports manual external credential typing only
- should type credentials rather than paste them by default
- must not become a general-purpose password manager
- detailed plan: `docs/kaoseghis-pw.md`

### KaosEghis-inj

- planned immediately after KaosEghis-vaccine
- patient-centered staff task-board track covering injection, verified laboratory, and
  optional read-only imaging/PACS updates
- read-only eGHIS DB polling for `ord_type='07'` and `proc_dept_cd='INJ'`
- laboratory source classification and completion semantics must be verified against the
  live eGHIS schema before implementation; do not guess from injection fields
- imaging status must reuse the existing KaosEghis-pacs/KaosPACS boundary and must not
  duplicate PACS polling or permit staff-created imaging completion
- stable order-key reconciliation for new, changed, cancelled, deleted, and restored
  source orders
- date-scoped KaosEghis-owned task board with independent category/source/operational
  states
- Raspberry Pi kiosk receives a non-PHI reload signal and pulls a complete generation
  snapshot into memory
- target a 21-inch touch-screen appliance with kinetic patient-list scrolling, large
  64-pixel-or-greater Done/Undo controls, no hover/right-click dependency, and no mouse
  or keyboard required for routine use
- staff may scroll and confirm Done/Undo; state is persisted only in KaosEghis
- Done rows remain visible, move below Active rows, and are struck through
- Raspberry Pi OS Lite kiosk with no mouse exit, automatic recovery, and scheduled
  display wake/sleep
- no Raspberry Pi durable PHI storage

### KaosEghis-scan

- top-level `Scan` tab implemented
- non-GUI Canon DR-C125 scanning through NAPS2 profile `Canon DR-C125 Native`
- one timestamped PDF per scan job
- dedicated `<KaosEghis data>/temp` folder
- fully manual upload; no PACS upload API call from KaosEghis-scan
- in-app PDF preview and native file drag to a browser upload control
- View folder fallback when browser drag/drop is unavailable
- no direct Orthanc/MWL/DICOM write
- configurable interval that empties direct files from the temporary folder
- explicit `Clean now` control
- no patient identifiers in spool filenames or routine logs

### KaosEghis-scheduler

- scheduler foundation implemented as a top-level in-process tab
- saved macros can be bound to one local time and selected weekdays
- jobs are disabled by default and run only while KaosEghis is open
- startup advances schedules to a future occurrence and never executes an old missed job
- automatic runs use a 10-second countdown, cancellation, sanitized history, and the
  existing MacroRunner safety gate
- the backup-copy macro itself is still under preparation and is not implemented
- initial background workflow: copy completed backup artifacts to one or more approved
  destinations, including an optionally Dropbox-synchronized folder
- guarded interactive eGHIS close/backup/power-off macro implemented as an explicit,
  disabled, hidden saved definition with separate close and backup Yes targets; target
  selectors remain editable under Macros > EMR
- Scheduler never creates its time/weekdays or enables/runs it automatically
- claim-day statistical preparation remains early planning and dry-run/manual-review
  only
- scheduled jobs are disabled by default and use explicit missed-run policies
- interactive jobs require a visible logged-in desktop, connector identity, known UI
  targets, countdown, cancellation, and strict stop-on-failure behavior
- arbitrary commands, forced process termination, and claim submission are non-goals
- detailed plan: `docs/kaoseghis-scheduler.md`

### KaosClip

- redesign into KaosEghis plugin/capability
- no standalone app direction

## Explicit Ownership Decisions

### Supplies

- `KaosEghis-supplies` has been removed from the product plan
- supplies remains served and presented from the KaosGDD side
- KaosEghis will not add a Supplies tab, supplies API client, local supplies storage,
  or supplies settings
- KaosSupplies service ownership and persistence remain outside KaosEghis

## Completed Milestone Areas

- structure and naming cleanup
- settings persistence
- Eghis process/window detection
- clipboard MVP
- UI target registry
- EMR target profile foundation
- macro binding to EMR target profiles and EMR UI target keys
- macro model and dry run
- read-only UIA target inspection
- conditional wait engine
- Eghis connector safety gate
- PACS local worklist model
- read-only PACS PostgreSQL adapter
- KaosPACS local API bridge
- weekly age/practice-count reporting
- PACS production-readiness hardening
- KaosEghis-scan first milestone: scan, preview, drag-out, folder access, and cleanup
- KaosEghis-SOCL first milestone: editable vocabulary, explicit composition, editable
  previews, and clipboard copy

## In-Progress or Partially Integrated Areas

- real macro execution scope remains intentionally narrow
- plugin information architecture continues to evolve
- SOCL vocabulary requires physician review and pruning against real clinic usage
- README is not yet aligned with the latest UI/tabs
- KaosClip is still placeholder-only

## Near-Term Priorities

### High Priority

- keep PR documentation and repo docs current
- implement in this order: KaosEghis-vaccine, then KaosEghis-inj
- define KaosEghis-pw as hidden infrastructure before adding credential-backed
  internal service autofill
- keep PACS deployment checklist and production-readiness docs current
- keep PACS dry-run behavior explicit and safe
- refine flu reporting UX and export/report format
- validate the KaosEghis-inj live injection and laboratory source queries, category
  state semantics, cancellation behavior, PACS projection boundary, and minimum display
  fields before implementing its local worklist milestone
- validate KaosEghis-scan behavior with representative multi-page feeder documents
- verify the scheduler's real backup artifact paths before implementing the backup
  macro, and capture the eGHIS close/backup dialog before that later macro is built

### Medium Priority

- unify macro configuration surfaces with current tab architecture
- refine launcher collection behavior in the staged order documented in
  `docs/kaoseghis-launcher-plan.md`
- keep infrastructure modules hidden unless they truly need first-class operator UI
- define final home for KaosClip
- improve plugin naming consistency
- implement KaosEghis-inj only in the staged order documented in
  `docs/kaoseghis-inj.md`: source verification, local worklist, API, kiosk, then
  appliance hardening
- consider scanner settings UI only after the fixed NAPS2 profile workflow is proven in daily use
- test the Scheduler foundation with disabled and harmless macros before enabling a
  production backup schedule

### Deferred

- KaosPACS push
- MWL/DICOM write paths
- arbitrary shell commands or an unattended scheduler service outside the visible app
- broad macro recorder

## Known Mismatches to Reconcile Later

- README current UI list is stale relative to actual tabs
- `KaosClip` still exists as a tab even though long-term direction is plugin integration
- some historical macro/config UI work exists outside the newest simplified visible flow

## Documentation Rule

When work is:

- added
- completed
- removed
- renamed
- moved between tabs or plugin groups

the relevant docs in `docs/` should be updated in the same change.
