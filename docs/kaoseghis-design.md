# KaosEghis Design

Last updated: 2026-06-29

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
- resizable `QMainWindow`
- global Catppuccin Mocha stylesheet
- top-level tabs:
  - `KaosEghis`
  - `KaosGdd`
  - `KaosClip`
  - `Plugins`
  - `Settings`

## Current Top-Level Information Architecture

### `KaosEghis`

Primary daily-use tab.

- shows Eghis connector status
- lists stored macro items for daily use
- supports refresh and dry run
- does not expose macro editing here

### `KaosGdd`

Embedded KaosGDD browser surface.

- uses Qt WebEngine when available
- falls back to a plain label when WebEngine is unavailable

### `KaosClip`

Temporary placeholder tab.

- currently still exists as a simple placeholder
- no production clipboard organizer workflow yet
- roadmap direction changed:
  - KaosClip will be redesigned as part of the KaosEghis plugin surface
  - it is no longer treated as a future standalone app

### `Plugins`

Operational plugin/workflow surface.

Current visible projects inside this tab:

- `PACS Worklist`
- `KaosEghis-flu`

Current `KaosEghis-flu` visible surface:

- `Weekly - Influenza Report`

### `Settings`

Application configuration surface.

- Eghis process/window settings
- KaosGDD URL
- credential reference name
- Eghis PostgreSQL connection string
- optional image-study query override

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
- PACS and flu are plugin workflows, not separate executables inside this repo
- KaosClip is being repositioned toward plugin integration rather than standalone scope

## Removed or Superseded Directions

- standalone KaosClip app direction: superseded
- dashboard-first layout: superseded
- overloaded `Eghis Assist` top-level workflow: superseded by use-first vs configuration/plugin separation

## Near-Term Design Maintenance Rule

This document should be updated whenever:

- a top-level tab changes
- a plugin is added, removed, renamed, or regrouped
- a workflow moves between tabs
- KaosClip integration direction changes again
