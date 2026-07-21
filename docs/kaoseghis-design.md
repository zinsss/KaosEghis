# KaosEghis Design

Last updated: 2026-07-21

## Purpose

KaosEghis is a local Windows companion application for Eghis EMR. The project is intentionally split into safe, incremental surfaces:

- daily-use automation access
- configuration and diagnostics
- plugin workflows
- local data persistence
- guarded EMR-side integration

The application is not a background agent. It is an operator-driven desktop tool built around explicit user actions, read-only diagnostics, and tightly scoped write paths.

## Current Application Shell

Entry point:

- `python main.py`
- [KaosEghis/app.py](/E:/Kaos/KaosEghis/KaosEghis/app.py)

Main window:

- [KaosEghis/ui/main_window.py](/E:/Kaos/KaosEghis/KaosEghis/ui/main_window.py)
- fixed-size `QMainWindow`
- global Nord stylesheet, including themed vertical and horizontal scrollbars
- shared buttons keep stable font metrics across normal and selected states; selection
  uses accent color without a late bold-weight change that can clip Korean or Latin text
- the optional KaosEghis-PACS patient-context listener follows the desktop app
  lifecycle; it starts from saved settings and closes with the application
- top-level tabs:
  - `Macros`
  - `KaosGdd`
  - `Vaccine`
  - `PACS`
  - `Flu-Report`
  - `Scan`
  - `Settings`

## Current Top-Level Information Architecture

### `Macros`

Primary daily-use tab.

- contains compact in-tab navigation:
  - `Launcher`
  - `Builder`
  - `MacroTexts`
  - `EMR`
- `EMR` now hosts the EMR target profile foundation rather than a simple summary view
- `Launcher` is the daily-use macro launcher surface; double-click or its run button
  executes immediately with an in-page `Running '<macro name>'...` status instead of
  a confirmation dialog
- the Launcher does not repeat saved macro names above its three columns
- the Launcher EMR toggle uses a dedicated green accent when connected and an
  orange warning accent when manual reconnection is required
- the Launcher columns are `Favorite`, `Macro`, and `Comments`
- cross-column drag/drop placement is saved after Qt finalizes the move, so a macro
  moved into `Favorite` remains there after refresh or restart
- existing `Eghis` entries migrate to `Macro`, `ETC` entries migrate to `Favorite`,
  and the former `Medical Documents` category migrates to `Comments` without
  deleting entries
- `Comments` also shows saved MacroTexts; double-clicking one copies its fixed text
  or one randomized option to the Windows clipboard without running an EMR action
- `Builder` is the macro add/edit surface
- `MacroTexts` creates and edits fixed or randomized reusable text; the same item can
  be selected by a macro `preset_text` step or copied directly from `Comments`
- randomized MacroText options use `---` on its own line as the separator, allowing
  each randomly selected comment to preserve multiple lines

### `Settings`

Dedicated top-level settings tab.

### `KaosGdd`

Embedded KaosGDD browser surface.

- uses Qt WebEngine when available
- uses a named persistent WebEngine profile so login cookies and browser storage
  survive normal application restarts
- stores the profile under `<KaosEghis data directory>/web/kaosgdd/`, separately
  from SQLite, and does not write browser session data to application logs
- falls back to a plain label when WebEngine is unavailable

### `Vaccine`

Placeholder plugin tab.

- no active workflow yet

### `PACS`

Dedicated KaosEghis-pacs top-level surface.

- local worklist
- polling
- sync
- reconciliation
- audit

### `Flu-Report`

Dedicated KaosEghis-flu report surface.

- panel title: `Weekly - Influenza Report`

### `Scan`

Dedicated KaosEghis-scan surface.

- one-click non-GUI scan through the saved NAPS2 profile `Canon DR-C125 Native`
- timestamped PDF output under the active KaosEghis data directory's `temp` folder
- in-app PDF list and preview
- native file drag-out for manual browser upload
- `View folder` fallback
- configurable periodic cleanup and explicit `Clean now`

## Architectural Boundaries

### Core

[KaosEghis/core](/E:/Kaos/KaosEghis/KaosEghis/core)

Responsibilities:

- connector and process/window detection
- UI target inspection
- wait engine
- macro runner
- PACS polling
- weekly reporting
- clipboard and write-test helpers

### Database

[KaosEghis/db](/E:/Kaos/KaosEghis/KaosEghis/db)

Responsibilities:

- local SQLite initialization
- schema migration
- repository CRUD
- local worklist/macro/settings persistence
- EMR target profile persistence
- EMR UI target library persistence

### UI

[KaosEghis/ui](/E:/Kaos/KaosEghis/KaosEghis/ui)

Responsibilities:

- top-level navigation
- plugin panels
- daily-use views
- settings forms

## Design Constraints

### Safety

The system deliberately separates:

- read-only EMR inspection
- manual, explicit test actions
- dry-run macro definition
- real automation execution

Real automation remains guarded. Dangerous background behavior, hidden polling loops, and implicit EMR write actions are not the default design.

### Privacy

The design permits only minimum necessary local persistence for PACS/flu workflows.

Examples of data explicitly not intended for long-term local storage:

- resident ID
- DOB
- sex
- phone
- address
- diagnosis
- EMR notes
- insurance details
- raw Eghis DB rows
- raw KaosPACS payloads

For KaosEghis-pacs specifically:

- Eghis DB access is read-only
- local worklist is minimum necessary only
- local PACS audit excludes patient names and raw exception text
- KaosEghis-pacs talks to Orthanc/MWL/DICOM only through KaosPACS, never directly

### Incremental Delivery

The design strategy is milestone-based:

- foundation first
- read-only detection and reporting next
- local persistence next
- explicit test tools next
- guarded real automation only after connector/safety correctness

## Completed Design Decisions

- Python package name is `KaosEghis`
- main desktop UI is PySide6
- SQLite is local and initialized on app startup
- EMR target profiles are now a first-class local model for future macro resolution
- EMR UI targets can now preserve parsed Inspector ancestor chains for deeper scoped lookup
- macros can now bind to a specific EMR target profile or fall back to the default profile
- PACS and flu are product/plugin workflows, not separate executables inside this repo
- KaosClip remains a future plugin direction, not a standalone app
- future `KaosEghis-inj` should keep authoritative injection worklist ownership on the KaosEghis side and treat Raspberry Pi as a reload-only consumer
- `KaosEghis-scan` uses a non-GUI NAPS2 process with the Canon DR-C125 Native profile, keeps PDFs in a dedicated temporary folder, and supports manual browser upload through in-app preview, native file drag-out, and a View folder fallback

## Removed or Superseded Directions

- standalone KaosClip app direction: superseded
- dashboard-first layout: superseded
- overloaded `Eghis Assist` top-level workflow: superseded by use-first vs configuration/plugin separation
- older `KaosEghis` top-level tab naming: superseded by direct product tab naming

## Near-Term Design Maintenance Rule

This document should be updated whenever:

- a top-level tab changes
- a plugin is added, removed, renamed, or regrouped
- a workflow moves between tabs
- KaosClip integration direction changes again
- the KaosEghis-inj or KaosEghis-scan ownership/privacy boundary changes
