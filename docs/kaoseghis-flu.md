# KaosEghis Flu

Last updated: 2026-06-28

Project name: `KaosEghis-flu`

Current visible panel title: `Weekly - Influenza Report`

## Purpose

KaosEghis-flu is the Eghis-side weekly reporting/statistics workflow for influenza-oriented operational summaries.

Current visible scope is intentionally small:

- select an ISO week
- inspect the derived date range
- run the weekly age-group practice-count query
- display the result as plain report text

## Current Visible UI

Panel:

- [KaosEghis/ui/plugins/flu_panel.py](/E:/Kaos/KaosEghis/KaosEghis/ui/plugins/flu_panel.py)

Current visible layout:

- title: `Weekly - Influenza Report`
- `Week No. [ ] : <date range> [Search]`
- plain-text report output area

Current rendered report format:

- `Week <n>, <year>-<mm-dd> ~ <mm-dd>`
- `Total Visits(Practice) Count: <x>`
- one line per predefined age group

Age-group order:

- `~0`
- `1-6`
- `7-12`
- `13-18`
- `19-49`
- `50-64`
- `65 over`

The visible UI is intentionally reduced to this single report surface.

## Backend Reporting Logic

Module:

- [KaosEghis/core/weekly_age_reporting.py](/E:/Kaos/KaosEghis/KaosEghis/core/weekly_age_reporting.py)

Current backend behavior:

- derives ISO week date range
- queries Eghis PostgreSQL in read-only mode
- buckets visits into predefined age groups
- returns visit count and distinct patient count per group

Source tables currently used:

- `public.h1opdin`
- `public.hz_mst_ptnt`

## Relation to Practice-Count Reporting

Weekly practice-count reporting is part of `KaosEghis-flu`.

It is no longer meant to read as a separate third plugin/project.

The older dedicated weekly panel module still exists:

- [KaosEghis/ui/plugins/weekly_visits_panel.py](/E:/Kaos/KaosEghis/KaosEghis/ui/plugins/weekly_visits_panel.py)

Current interpretation:

- backend/reporting logic remains valid
- visible primary workflow is the simplified flu report panel
- weekly practice counts belong conceptually to `KaosEghis-flu`

## Privacy Rules

Visible/reporting output should stay aggregate.

Do not turn this surface into patient-detail persistence.

Avoid storing or exposing:

- resident ID
- phone
- address
- diagnosis
- EMR notes
- insurance details
- raw row dumps

The current backend uses birth date inside query-time age calculation, but the flu panel does not persist or present DOB as an output field.

## Completed

- weekly age-group reporting query
- read-only PostgreSQL execution path
- simplified weekly influenza report panel
- plain-text output format

## Removed or Superseded

- multi-surface visible flu UI: superseded by the single weekly report surface
- separate-looking weekly practice-count project identity: superseded

## Not Done

- finalized report export workflow
- official formatted report template output
- richer validation and operator hints

## Maintenance Triggers

Update this document whenever:

- the report layout changes
- age groups change
- source query changes
- weekly practice-count reporting moves again
