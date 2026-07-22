# KaosEghis Plans

Last updated: 2026-07-22

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

### KaosEghis-inj

- planned injection-room worklist track with a detailed architecture specification
- read-only eGHIS DB polling for `ord_type='07'` and `proc_dept_cd='INJ'`
- stable order-key reconciliation for new, changed, cancelled, deleted, and restored
  source orders
- date-scoped KaosEghis-owned worklist with `active`, `done`, and `cancelled` states
- Raspberry Pi kiosk receives a non-PHI reload signal and pulls a complete generation
  snapshot into memory
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

### KaosClip

- redesign into KaosEghis plugin/capability
- no standalone app direction

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

## In-Progress or Partially Integrated Areas

- real macro execution scope remains intentionally narrow
- plugin information architecture continues to evolve
- README is not yet aligned with the latest UI/tabs
- KaosClip is still placeholder-only

## Near-Term Priorities

### High Priority

- keep PR documentation and repo docs current
- keep PACS deployment checklist and production-readiness docs current
- keep PACS dry-run behavior explicit and safe
- refine flu reporting UX and export/report format
- validate the KaosEghis-inj live source query, cancellation behavior, and minimum
  display fields before implementing its local worklist milestone
- validate KaosEghis-scan behavior with representative multi-page feeder documents

### Medium Priority

- unify macro configuration surfaces with current tab architecture
- define final home for KaosClip
- improve plugin naming consistency
- implement KaosEghis-inj only in the staged order documented in
  `docs/kaoseghis-inj.md`: source verification, local worklist, API, kiosk, then
  appliance hardening
- consider scanner settings UI only after the fixed NAPS2 profile workflow is proven in daily use

### Deferred

- KaosPACS push
- MWL/DICOM write paths
- scheduler
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
