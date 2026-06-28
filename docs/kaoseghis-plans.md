# KaosEghis Plans

Last updated: 2026-06-28

## Current Working State

The project has moved beyond scaffold-only status and now contains real guarded foundations in several areas:

- local SQLite persistence
- Eghis connector state
- UI target registry
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

### KaosEghis-flu

- weekly influenza report surface
- weekly practice-count/statistics backend
- no export-grade workflow yet

### KaosClip

- redesign into KaosEghis plugin/capability
- no standalone app direction

## Completed Milestone Areas

- structure and naming cleanup
- settings persistence
- Eghis process/window detection
- clipboard MVP
- UI target registry
- macro model and dry run
- read-only UIA target inspection
- conditional wait engine
- Eghis connector safety gate
- PACS local worklist model
- read-only PACS PostgreSQL adapter
- KaosPACS local API bridge
- weekly age/practice-count reporting

## In-Progress or Partially Integrated Areas

- real macro execution scope remains intentionally narrow
- plugin information architecture continues to evolve
- README is not yet aligned with the latest UI/tabs
- KaosClip is still placeholder-only

## Near-Term Priorities

### High Priority

- keep PR documentation and repo docs current
- stabilize PACS read path and cancellation semantics
- stabilize KaosPACS sync-state behavior
- improve PACS operator visibility for sync state and manual sync safety
- refine flu reporting UX and export/report format
- reconcile visible UI with older tab remnants and placeholder surfaces

### Medium Priority

- unify macro configuration surfaces with current tab architecture
- define final home for KaosClip
- improve plugin naming consistency

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
