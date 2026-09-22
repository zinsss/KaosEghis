# KaosEghis Flu

Last updated: 2026-09-22

Project name: `KaosEghis-flu`

Current visible panel title: `Weekly - Influenza Report`

## Purpose

KaosEghis-flu is the Eghis-side weekly reporting/statistics workflow for influenza-oriented operational summaries.

Current visible scope is intentionally small:

- select an ISO week
- inspect the derived date range
- run the weekly age-group practice-count query
- display aggregate results in a table

## Current Visible UI

Panel:

- [KaosEghis/ui/plugins/flu_panel.py](/E:/Kaos/KaosEghis/KaosEghis/ui/plugins/flu_panel.py)

Current visible layout:

- title: `Weekly - Influenza Report`
- `Week No. [ ] : <date range> [Search]`
- age-group, visit-count and distinct-patient-count table

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
- loads SQLite settings and runs PostgreSQL work outside the Qt GUI thread
- retries a brief SQLite lock once and bounds PostgreSQL connection setup to five seconds
- limits the flu SQL statement to three seconds on its own connection; no automatic query retry
- names that PostgreSQL session `KaosEghis-Flu` for attribution
- closes the cursor and connection on success, error and query timeout
- stops if a read-only session cannot be established, rather than silently falling back
- initializes/migrates local SQLite only during application startup, not on every report load

Source tables currently used:

- `public.h1opdin`
- `public.hz_mst_ptnt`

## EMR Slowdown Investigation (2026-09-22)

The repeatable operator report remains unresolved; closing a connection does not prove
that a query could not have competed with EMR for database CPU, memory or I/O.

Read-only live metadata and `EXPLAIN (FORMAT JSON)` checks (without `ANALYZE`) found:

- The local eGHIS PostgreSQL server reports version 9.2.4.
- The configured flu query is the built-in query, not an override.
- Current and two previous weekly plans use `h1opdin_id01` for the visit date and
  `hz_mst_ptnt_pkey` for the patient join. No full-table scan appears in these plans.
- The flu path does not call UIA, change foreground focus, or trigger grid caching.
- Connection cleanup already existed; SQL execution itself was previously unbounded.
- The database activity snapshot did not expose other sessions' state to this login,
  so it cannot establish whether EMR was blocked. Planner estimates are not measured
  execution times and do not rule out resource contention.

The new timeout is session-local `statement_timeout`, supported by PostgreSQL 9.2.
No `lock_timeout`, JIT or parallel-worker settings are applied to this older server.
No schema, index, EMR data or server-wide configuration changes were made. The count
query and age-group semantics are unchanged.

Each Search writes a bounded timing record beside the local settings database:
`data/flu-report.jsonl` (64 KiB plus one rotated backup). Fields include UTC timestamp,
requested week, outcome, total elapsed seconds and cumulative DB milestones through
`connection_closed`. The file contains no SQL, connection string, raw exception text,
patient data, or result counts. Logging failure does not change the query result.

On the next slowdown, compare the log timestamp and `connection_closed` milestone with
when EMR slowed and recovered. A fast, closed report followed by prolonged EMR slowness
needs a simultaneous database/EMR-service investigation, not another blind query rewrite.
The three-second cap reduces exposure; it is not evidence that the reported cause is fixed.

The operator confirmed slowness persists after `Report loaded`, not only during Search.
A live, no-patient-data probe verified read-only mode and the three-second setting on
9.2.4. A separate 100 ms timeout test using `pg_sleep` raised SQLSTATE `57014`, recorded
connection closure, and left zero probe sessions in `pg_stat_activity`. This validates
cleanup/timeout behavior only; it does not reproduce or resolve the EMR slowdown.

Reference: [PostgreSQL 9.2 statement timeout](https://www.postgresql.org/docs/9.2/runtime-config-client.html).

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
