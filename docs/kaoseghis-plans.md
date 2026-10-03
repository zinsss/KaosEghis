# KaosEghis Plans

Last updated: 2026-10-03

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

### Workspace Formatter

- reusable Korean compact-date formatter implemented in the core layer
- `Workspace > Formatter` provides explicit Format, Copy, and Clear controls
- input is sorted and deduplicated before grouping by year and month
- malformed or impossible dates produce controlled validation instead of partial output
- no persistence, network request, EMR action, or automatic clipboard write

### KaosEghis-SOCL

- first editable composition milestone implemented as a top-level tab
- reviewed Subjective and Physical Exam vocabulary is seeded once into local SQLite
- physician can add, rename, delete, reorder, and rewrite rendered phrases
- only explicitly checked findings are rendered
- output remains editable and clipboard-only
- encounter selections and generated text are not persisted
- no diagnosis, Assessment/Plan, order, or EMR automation behavior
- detailed design: `docs/kaoseghis-socl.md`

### KaosEghis-emr

- shared FIFO reader and Windows machine-wide mutex implemented for existing PACS,
  flu, health and patient-context reads; a separate broker executable is not required
- target: one KaosEghis-emr connector with separate KaosPACS and KaosOrders adapters;
  source validation/privacy/delivery plus verified EMR interpretation, normalization
  and source-change detection stay here; imaging/board decisions belong to receivers
- perform normalization/comparison only after physical connection closure; preserve
  approved source facts and normalized meanings, including distinct 30/40 states
- offline source model/comparison implemented in `core/emr_source.py` and
  `core/emr_source_shadow.py`, with synthetic lifecycle and mocked-cleanup tests;
  the day reader remains unavailable and has no runtime or delivery hooks
- current PACS refresh uses chart clear/load +2-second debounce, clear +30-second
  follow-up preserved across loads, five-minute successful-read safety check and
  startup/reconnect/manual reconciliation; F6/F7/button observations are diagnostic only
- coordinate a bounded background queue with at most one live source DB connection;
  on-demand flu waits without connecting until the active connection has closed
- mandatory: never modify the EMR database; fail closed without verified read-only
  access and reviewed operations
- mandatory: close every source connection immediately after its read, including
  error/timeout/cancellation cleanup; no idle pool or connection held for publishing
- uncertain physical closure latches the reader unhealthy and blocks further
  connections; production privilege verification, registered parameterized
  operations and bounded stuck-driver recovery remain gated
- preserve fallback reconciliation until signal capture is validated and account
  for independently running legacy pollers during migration
- requirements and acceptance gates: [KaosEghis-emr](kaoseghis-emr.md)
- offline [receiver contract review](kaoseghis-emr-contract-review.md) recorded;
  KaosOrders on `zin@kaosclinic:/srv/projects/KaosOrders` was inspected read-only
  at `b5f7ccd`; its v1 lacks normalized source/day intake. Contract agreement,
  deployed PACS compatibility and source qualifiers remain pending, so the live
  day-reader gate has not passed

### KaosOrders

- separate KaosClinic service; Raspberry Pi OS/Chromium touchscreen viewer has no
  durable patient/order storage
- receiver consumes centrally interpreted EMR facts and owns category rules, fee
  exclusions, visibility, badges and details; it applies updates idempotently, rejects
  stale data and maintains its own state without duplicating EMR table decoding
- source edit/disappearance/key-reuse detection stays in KaosEghis-emr; KaosPACS is
  a sibling consumer, not a downstream dependency of KaosOrders
- Windows source normalizer/ledger/v2 example are disabled offline prototypes;
  no real day reader, production mappings or publishing is enabled
- destination-neutral source processing is now separate from the legacy board
  prototype; existing JSON remains an unapproved reference, not the shared contract
- next: agree the normalized-source contract with the server repository, test source
  interpretation/comparison and receiver rules with synthetic data/mocked DBs, then
  obtain approval for bounded live shadow verification
- preserve existing PACS runtime until its own contract migration is verified
- detailed evidence and gates: [KaosOrders](kaosorders.md)

### KaosEghis-pacs

- read-only Eghis image-study order polling
- local worklist persistence
- cancellation tracking
- local KaosPACS API bridge
- current business-state ownership stays in KaosEghis-pacs until a reviewed migration;
  target EMR interpretation/source-change detection belongs to KaosEghis-emr, while
  imaging eligibility, modality/station rules and worklist behavior belong to KaosPACS
- imaging-state ownership stays in KaosPACS; existing API and cancellation behavior
  are unchanged by the target architecture

### KaosEghis-flu

- weekly influenza report surface
- weekly practice-count/statistics backend
- no export-grade workflow yet

### KaosEghis-vaccine

- next planned plugin implementation priority
- lifecycle and count foundation completed: only explicitly completed, counted national
  records contribute to daily totals; cancellation reverses that contribution and all
  corrections use sanitized audit entries
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

### Earlier Board Directions (Historical)

The local KaosEghis-inj/KaosInj board and its Done/Undo UI are superseded. The
September 30 plan then proposed an Acer/LMDE viewer, completed-patient tiles and
non-clickable diagnostic hold tiles. Those device/board choices are also
superseded by the October decisions in [KaosOrders](kaosorders.md): KaosClinic
service, Pi touchscreen viewer, confirmed hold encounters and receiver-owned
classification/details. Neither older plan authorizes new runtime or UI work.

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
- claim-day statistical preparation has a
  [read-only manual preview](kaoseghis-claim-preparation.md), without aggregation execution
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
- keep the vaccine workflow stable while verifying the shared EMR connector and
  receiver-owned KaosOrders processing; do not implement the superseded local inj board
- keep the KaosOrders source adapter behind production permission, registered
  operation, real-schema identity, and complete-read gates
- define KaosEghis-pw as hidden infrastructure before adding credential-backed
  internal service autofill
- keep PACS deployment checklist and production-readiness docs current
- keep PACS dry-run behavior explicit and safe
- refine flu reporting UX and export/report format
- agree the KaosOrders normalized-source contract and extend offline lifecycle tests before
  any new live day-wide reader; verify completeness and privacy before publishing
- carry the supervised source identity/state/removal evidence into complete-read
  criteria and a reviewed minimum detail allowlist; do not infer unverified cases
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
- follow the staged KaosOrders gates in `docs/kaosorders.md`; the older
  `docs/kaoseghis-inj.md` local-worklist/API plan is historical, not the next milestone
- consider scanner settings UI only after the fixed NAPS2 profile workflow is proven in daily use
- test the Scheduler foundation with disabled and harmless macros before enabling a
  production backup schedule

### Deferred

- KaosPACS push
- MWL/DICOM write paths
- arbitrary shell commands or an unattended scheduler service outside the visible app
- broad macro recorder
- separate EMR broker process unless independent consumers or bounded stuck-driver
  recovery prove it necessary

## Known Mismatches to Reconcile Later

- README current UI list is stale relative to actual tabs
- `KaosClip` still exists as a tab even though long-term direction is plugin integration
- some historical macro/config UI work exists outside the newest simplified visible flow
- `docs/kaoseghis-inj.md` remains historical background; KaosOrders is the
  current staff-board direction

## Documentation Rule

When work is:

- added
- completed
- removed
- renamed
- moved between tabs or plugin groups

the relevant docs in `docs/` should be updated in the same change.
