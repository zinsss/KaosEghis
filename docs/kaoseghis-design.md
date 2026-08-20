# KaosEghis Design

Last updated: 2026-08-20

## Purpose

KaosEghis is a local Windows companion application for Eghis EMR. The project is intentionally split into safe, incremental surfaces:

- daily-use automation access
- configuration and diagnostics
- plugin workflows
- hidden infrastructure modules
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
- shared Qt layout metrics provide an 8 px gap between adjacent controls throughout
  the application; intentional tab bars remain visually grouped
- shared buttons keep stable font metrics across normal and selected states; selection
  uses accent color without a late bold-weight change that can clip Korean or Latin text
- the right side of the top tab bar contains a persistent app notification area with
  a colored state dot and short operator-facing text
- app notifications contain action status only and must not expose captured values,
  clipboard contents, patient information, or national IDs
- the optional KaosEghis-PACS patient-context listener follows the desktop app
  lifecycle; it starts from saved settings and closes with the application
- top-level tabs currently in code:
  - `KaosEghis`
  - `Memos`
- `Workspace`
- `PACS`
- `Macros`
- `Settings`

Hidden infrastructure should not add top-level tabs unless it truly needs a daily-use
operator surface. The current credential plan for `KaosEghis-pw` is intentionally
hidden and hotkey-driven rather than visible in the shell.

## Current Top-Level Information Architecture

### `Macros`

Primary daily-use tab.

- contains compact in-tab navigation:
  - `Launcher`
  - `Builder`
  - `MacroTexts`
  - `EMR`
- `EMR` now hosts the EMR target profile foundation rather than a simple summary view
- `EMR` also includes a click-capture helper for probing a live control by hotkey or
  manual arm, then copying the resolved UI metadata/value summary to the clipboard
- `Launcher` is the daily-use macro launcher surface; double-click or its run button
  executes immediately with an in-page `Running '<macro name>'...` status instead of
  a confirmation dialog
- the right side of Launcher contains a compact SOCL composer with `S` and `O` tabs;
  it shares the same local vocabulary as the full SOCL editor
- each Launcher SOCL group uses a dense two-column checkbox layout; optional detail
  fields expand for checked findings, while free-text/other fields remain visible
- Launcher no longer embeds or loads KaosGDD Calendar, Tasks, or Supplies
- the Launcher now supports both direct executable macros and launcher
  collections
- `Ctrl+Alt+Shift+F11` restores KaosEghis and opens the Launcher from any foreground
  application; the shortcut navigates only and never executes a launcher item
- direct macros run immediately
- launcher collections open a chooser dialog on double-click and expose member
  macros from a right-click context menu
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
- macros and MacroTexts can remain available in their editors without appearing in
  Launcher by clearing **Exposed in Launcher**
- exposed MacroTexts can be organized into Comments collections from the MacroTexts
  page, with edit, reorder, remove, and unpack controls
- randomized MacroText options use `---` on its own line as the separator, allowing
  each randomly selected comment to preserve multiple lines
- launcher collection implementation and future expansion plan:
  `docs/kaoseghis-launcher-plan.md`

### `SOCL`

Physician-controlled Subjective and Objective note composer.

- starts with no selected findings
- contains the reviewed primary-care symptom and physical-exam vocabulary
- supports local add/edit/delete/reorder for collections, labels, and rendered phrases
- generates deterministic editable S and O previews from checked findings only
- copies S, O, or combined S/O to the clipboard
- provides the same vocabulary through a compact `S`/`O` tabbed composer on Launcher
- persists vocabulary only; encounter selections and generated notes stay in memory
- performs no diagnosis inference, EMR automation, or eGHIS database write
- detailed design: `docs/kaoseghis-socl.md`

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
- planned editable vaccine catalog and thermal-label workflow
- includes a guarded national-influenza program preview driven by explicitly enabled
  schedule and birth-range settings; it performs no print or EMR write
- preserves the legacy national-influenza age-group, birthday-boundary, schedule,
  exception, and daily-cap model
- default counted-program cap remains `100`, with seasonal values editable by the
  operator
- patient identifiers remain transient and are never written to the local vaccine
  configuration/counter store or routine logs
- detailed specification: `docs/kaoseghis-vaccine.md`

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

### `Scheduler`

Top-level saved-macro scheduling surface.

- binds an existing macro to a local time and selected weekdays
- jobs are disabled by default
- runs only while the visible KaosEghis application is open
- startup calculates future occurrences but never replays a missed job
- uses a 10-second countdown, operator cancellation, and sanitized local history
- shares the MacroRunner safety gate and process-wide execution lock
- the backup workflow remains a future macro; Scheduler itself is not a backup engine

## Architectural Boundaries

### Core

[KaosEghis/core](/E:/Kaos/KaosEghis/KaosEghis/core)

Responsibilities:

- connector and process/window detection
- UI target inspection
- wait engine
- macro runner
- scheduler runtime and due-time calculation
- SOCL explicit-selection renderer
- PACS polling
- weekly reporting
- clipboard and write-test helpers
- shell-level integration points for hidden infrastructure modules

### Hidden Infrastructure Modules

Hidden modules are not daily-use tabs. They provide runtime services to the shell and
other product modules.

Current planned hidden infrastructure module:

- `KaosEghis-pw`
  - startup master-password prompt
  - locked/unlocked credential state
  - hidden credential popup on global hotkey
  - internal-service credential support
  - manual external credential typing support
  - detailed plan: `docs/kaoseghis-pw.md`

### Database

[KaosEghis/db](/E:/Kaos/KaosEghis/KaosEghis/db)

Responsibilities:

- local SQLite initialization
- schema migration
- repository CRUD
- local worklist/macro/settings persistence
- EMR target profile persistence
- EMR UI target library persistence
- scheduler job and sanitized run-history persistence
- SOCL editable vocabulary persistence; no encounter-note persistence

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
- `KaosEghis-pw` should remain a hidden infrastructure module, not a visible top-level tab
- KaosClip remains a future plugin direction, not a standalone app
- future `KaosEghis-inj` should keep authoritative injection/laboratory staff-task state
  on the KaosEghis side, project PACS imaging state read-only through the existing PACS
  boundary, and treat Raspberry Pi as a reload-only, 21-inch touch-first consumer with
  no mouse/keyboard requirement for routine staff use
- `KaosEghis-scan` uses a non-GUI NAPS2 process with the Canon DR-C125 Native profile, keeps PDFs in a dedicated temporary folder, and supports manual browser upload through in-app preview, native file drag-out, and a View folder fallback
- the EMR patient-note alert is a read-only, in-memory safety surface: it checks only
  once per detected chart-number change for the `***` marker, displays no memo
  contents, persists neither chart number nor memo data, and performs no EMR input or
  focus action; its generic memo textbox is disambiguated by an optional persisted
  Inspect.exe ancestor path, which contains UI structure only and no patient data

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
