# KaosEghis PACS

Last updated: 2026-06-28

Project name: `KaosEghis-pacs`

Current visible panel title: `PACS Worklist`

## Purpose

KaosEghis-pacs is the Eghis-side bridge for imaging worklist preparation.

Current scope:

- read-only Eghis PostgreSQL polling
- local SQLite worklist persistence
- local KaosPACS API bridge
- operator-facing worklist panel

Explicitly not in current scope:

- MWL write
- DICOM networking logic
- background scheduler

## Current UI

Visible panel:

- [KaosEghis/ui/plugins/pacs_panel.py](/E:/Kaos/KaosEghis/KaosEghis/ui/plugins/pacs_panel.py)

Current behaviors:

- refresh local rows
- explicit KaosPACS health check
- poll now
- sync to KaosPACS
- manual insert
- cancel selected local row
- filter by status
- show per-row KaosPACS sync state columns

Current PACS table columns:

- `Status`
- `Patient`
- `Chart No`
- `Study`
- `Modality`
- `Requested At`
- `Accession / Order ID`
- `KaosPACS Status`
- `Last Synced`
- `Sync Error`

Current button separation:

- `Refresh` -> local SQLite reload only
- `Check KaosPACS` -> `GET /health` only
- `Poll now` -> Eghis DB to local SQLite only
- `Sync to KaosPACS` -> local SQLite to KaosPACS only

Filter states:

- `active`
- `done`
- `cancelled`
- `error`
- `all`

## Local Storage Model

Local table:

- `pacs_worklist_items`

Allowed local fields:

- `patient_name`
- `chart_no`
- `study`
- `modality`
- `requested_at`
- `accession_or_order_id`
- `status`
- `source`
- `error_message`

Additional local bridge state:

- `kaospacs_mwl_status`
- `kaospacs_mwl_last_synced_at`
- `kaospacs_mwl_error`

This is the intended local persistence boundary.

## Privacy Rules

Do not store:

- patient DOB
- sex
- resident ID
- phone
- address
- diagnosis
- EMR notes
- insurance details
- raw Eghis DB rows

The PACS adapter must normalize to the local worklist model and discard everything else.

## KaosPACS API Bridge

Bridge module:

- [KaosEghis/core/kaospacs_client.py](/E:/Kaos/KaosEghis/KaosEghis/core/kaospacs_client.py)

Configured settings:

- `kaospacs_api_base_url`
- `kaospacs_api_timeout_seconds`

Current API boundary:

- `GET /health`
- `GET /worklist`
- `PUT /worklist`
- `POST /worklist/complete`
- `POST /worklist/cancel`

Current sync rule:

- only local `active` worklist rows are sent in `PUT /worklist`
- cancelled rows are never sent as active entries
- previously-sent cancelled rows trigger `POST /worklist/cancel`
- cancelled rows that were never sent remain local-only and are skipped
- sync shows operator summary counts before/after action

Current sync UX rule:

- if there are active local rows, operator confirmation is required before sync
- sync summary includes:
  - active rows
  - cancelled pending rows
  - sent
  - cancelled
  - errors
  - skipped

Current local MWL sync states:

- `not_sent`
- `sent`
- `cancelled`
- `error`

Payload privacy rule:

- do not send DOB
- do not send sex
- do not send resident ID
- do not send phone
- do not send address
- do not send diagnosis
- do not send EMR notes
- do not send insurance details

## Current Read-Only Query Path

Main module:

- [KaosEghis/core/pacs_polling.py](/E:/Kaos/KaosEghis/KaosEghis/core/pacs_polling.py)

Shared DB helper:

- [KaosEghis/core/eghis_db.py](/E:/Kaos/KaosEghis/KaosEghis/core/eghis_db.py)

Default query shape currently targets:

- `public.mwl m`
- `public.h2opd_doct_ord o`

Join strategy:

- `o.recept_no = split_part(m.eghis_key, '_', 1)`
- `CAST(o.ord_no AS text) = split_part(m.eghis_key, '_', 2)`
- `CAST(o.ord_seq_no AS text) = split_part(m.eghis_key, '_', 3)`

Key PACS logic:

- `o.proc_dept_cd = 'XRAY'`
- active visibility via `m.scheduled_proc_status = '100'`
- cancelled visibility via `COALESCE(o.dc_yn, 'N') = 'Y'`

Returned canonical fields:

- `status`
- `patient_name`
- `chart_no`
- `study`
- `modality`
- `requested_at`
- `accession_or_order_id`
- `source`

## Cancellation Semantics

Cancelled remote rows are not permanently ignored.

Current rule:

- if a remote row comes back cancelled and the local row already exists, update local status to `cancelled`
- if a remote row comes back cancelled and no local row exists yet, skip insertion

This preserves local tracking for previously seen orders while avoiding creation of never-seen cancelled rows.

## Modality Mapping

Current mapping rule:

- `BMD` if `m.scheduled_modality = 'BMD'` or `o.ord_cd = 'HC342'`
- `CR` if `m.scheduled_modality = 'DR'`
- otherwise use `m.scheduled_modality`

## Completed

- local PACS worklist table
- repository CRUD
- PACS panel
- read-only PostgreSQL adapter
- cancellation-aware update behavior
- local KaosPACS API bridge
- local MWL sync-state tracking

## Not Done

- MWL write/export
- DICOM service integration
- scheduler-driven polling

## Maintenance Triggers

Update this document whenever:

- the PACS query changes
- local worklist fields change
- cancellation behavior changes
- KaosPACS integration begins
