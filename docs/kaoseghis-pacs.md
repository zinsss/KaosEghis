# KaosEghis PACS

Last updated: 2026-09-30

Project name: `KaosEghis-pacs`  
Panel title: `PACS Worklist`

## Purpose

KaosEghis-pacs is the Eghis-side PACS bridge inside the KaosEghis desktop app.

Current scope:

- read-only Eghis DB polling
- local SQLite PACS worklist persistence
- local PACS audit
- explicit KaosPACS API sync
- explicit KaosPACS reconciliation
- read-only KaosPACS patient-context fallback API
- operator-facing PACS settings and local worklist tools
- embedded KaosPACS Web admin page

This project does not implement direct DICOM behavior in KaosEghis itself.

## Patient Context API

Purpose:

- KaosPACS Web may launch from EMR with only `m_patid=<chart_no>`
- if launch URL and existing DICOM do not provide demographics, KaosPACS can call KaosEghis-pacs for minimal patient identity context
- this endpoint is read-only and patient-context only
- this endpoint does not expose orders, reports, diagnosis, phone, address, resident ID, insurance, or EMR notes

Endpoint:

- `GET /patients/context/<chart_no>`

Default service URL:

- `http://127.0.0.1:8765/patients/context/<chart_no>` for same-machine local use
- for split deployment, bind KaosEghis-pacs on its LAN address and call:
  - `http://192.168.0.100:8765/patients/context/<chart_no>`

Transitional compatibility:

- the deployed KaosPACS Web currently calls
  `GET /api/kaospacs/patient-context?chart_no=<chart_no>`
- that legacy route remains available temporarily and returns its original lowercase
  field shape
- new callers must use `/patients/context/<chart_no>`

Success response:

```json
{
  "PatientID": "2735",
  "PatientName": "홍길동",
  "PatientBirthDate": "19700101",
  "PatientSex": "M",
  "source": "egHis"
}
```

Error responses:

- `400` -> `{ "error": "invalid_patient_id" }`
- `401` -> `{ "error": "unauthorized" }` when token auth is configured
- `404` -> `{ "error": "not_found" }`
- `409` -> `{ "error": "ambiguous" }`
- `503` -> `{ "error": "source_unavailable" }`

Authentication:

- preferred environment variable: `KAOSEGHIS_PACS_API_TOKEN`
- literal prompt spelling `KAOSEGHiS_PACS_API_TOKEN` and legacy
  `KAOSPACS_INTEGRATION_TOKEN` remain accepted for compatibility
- otherwise the service uses PACS setting `kaospacs_integration_token`
- callers send `Authorization: Bearer <token>`
- loopback-only binding may run without a token for local development
- any non-loopback/LAN bind refuses to start unless a token is configured

Runtime:

- the KaosEghis desktop application starts the patient-context API after local
  settings/database initialization and stops it when the application exits
- an API bind/configuration failure does not prevent the desktop UI from opening
- service module: `python -m KaosEghis.service.kaospacs_api`
- the service module remains available for isolated diagnostics or service-hosted use
- optional CLI override:
  - `python -m KaosEghis.service.kaospacs_api --host 192.168.0.100 --port 8765`
- the service reads KaosEghis settings locally and queries eGHIS read-only
- when CLI host/port are omitted, the service reads:
  - `kaospacs_patient_context_bind_host`
  - `kaospacs_patient_context_port`
- the request path itself does not initialize or migrate the local SQLite database

Field rules:

- `PatientID`: exact chart number string
- `PatientName`: UTF-8 Korean-safe string
- `PatientBirthDate`: `YYYYMMDD` or empty string
- `PatientSex`: `M`, `F`, `O`, or empty string when unknown
- `source`: `egHis`

Privacy:

- allowed returned fields only:
  - `PatientID`
  - `PatientName`
  - `PatientBirthDate`
  - `PatientSex`
  - `source`
- forbidden output:
  - resident registration number
  - phone
  - address
  - diagnosis
  - EMR notes
  - insurance details
  - order details
- logs should avoid patient values and full payloads
- request logging is suppressed so chart numbers and returned demographics are not
  written to the service log
- this API is separate from MWL and order synchronization; it supplies demographics
  context only when KaosPACS Web cannot obtain those fields from an existing DICOM study

## Architecture

```text
Eghis DB (read-only)
        |
        v
KaosEghis-pacs
        |
        |-- Local SQLite worklist
        |
        |-- Local audit
        |
        `-- KaosPACS API
                |
                v
             KaosPACS
                |
                v
        Orthanc / MWL / DICOM
```

Architecture rules:

- Eghis DB access is read-only.
- KaosEghis-pacs communicates only through the KaosPACS local API.
- KaosEghis-pacs never writes directly into Orthanc.
- KaosEghis-pacs never writes directly to DICOM.
- KaosEghis-pacs never writes directly to MWL.

## Runtime Boundaries

Status ownership:

- business state `active` / `cancelled` is owned by KaosEghis-pacs
- imaging state `completed` / `expired` is owned by KaosPACS
- local `error` remains an operator/runtime error state, not a business or imaging truth source

### Poll

- source: Eghis DB
- direction: Eghis DB -> local SQLite
- write target: local `pacs_worklist_items`
- read-only against Eghis DB
- operator-selected date only
- if a local active row for the selected date disappears from `public.mwl`, it is preserved locally and marked `cancelled`

### Shared-source coordination

All PACS source and health reads use the shared FIFO worker and Windows
machine-wide mutex documented in
[KaosEghis-emr](kaoseghis-emr.md#shared-read-queue-stage-one). Cursor and
connection cleanup finishes inside that exclusive operation before SQLite work
or KaosPACS delivery. Uncertain physical connection closure blocks subsequent
reads instead of releasing the slot.

Verified chart clear/load changes request whole-day reconciliation after the
two-second debounce. Clear +30-second follow-up, startup/reconnect work,
five-minute successful-read safety, date preservation across midnight, and
manual `Poll Now` remain in effect. F6/F7 and button observations are diagnostic
only; they do not prove a successful save.

The future KaosOrders all-orders/reception reader must enter the same shared
boundary. It is a separate registered operation and must not broaden or replace
the working PACS query in place. Preserve PACS changed-only delivery and current
business/imaging ownership while introducing it.

### Sync

- source: local SQLite
- direction: local SQLite -> KaosPACS Gateway API
- no direct Orthanc/MWL/DICOM write
- production path: `KaosEghis -> Gateway :8060 -> MWL internal API :8055`
- KaosEghis must not target MWL internal API `:8055` directly in production
- preferred create/update endpoint: `POST /orders/upsert`
- preferred cancel/delete endpoint: `POST /orders/cancel`
- compatibility fallback for older KaosPACS servers:
  - only on HTTP `404 Not Found`
  - create/update -> `PUT /worklist`
  - cancel/delete -> `POST /worklist/cancel`
- requests are sent as `application/json; charset=utf-8`
- requests send `Authorization: Bearer <kaospacs_gateway_api_token>` when a token is configured
- payload JSON is encoded as UTF-8 without forcing ASCII escapes
- active rows only
- cancelled previously-sent rows call the KaosPACS cancel endpoint

### Changed-Only Delivery

Automatic refreshes and Poll Now send only new/changed active payloads and pending
cancellations. A local `kaospacs_mwl_fingerprint` records the normalized payload,
operation and destination after successful delivery. Repeated source upserts or
local timestamp changes alone do not cause HTTP delivery. The fingerprint is a
SHA-256 digest; credentials and raw payload copies are not stored in it or logged.

- Payload edits, changing the destination URL, or reactivating a cancelled order
  require delivery again. Token rotation does not invalidate acknowledgements.
- Errors remain retryable. Failed delivery clears the acknowledgement because a
  timeout may occur after the server accepted a change. Dry run never acknowledges
  a payload or changes sync state. Malformed JSON and explicit rejection responses
  are failures, not acknowledgements. HTTP 404 compatibility fallbacks are unchanged.
- Before sending each item, recheck that its payload and business state still match
  the captured candidate. An edit during HTTP retains the old payload's fingerprint,
  so the new payload remains eligible for the next refresh.
- Old sent/cancelled rows without a fingerprint are delivered once to establish a
  verified baseline; migration does not assume the current payload was sent before.
  No records are deleted or silently marked delivered by migration.
- `Sync to KaosPACS` remains the explicit full-resend fallback, including unchanged
  eligible rows, with confirmation. Poll Now uses changed-only delivery. After a
  remote restore/reset at the same URL, use full resend to rebuild its worklist.
- `unchanged` is a subset of `skipped`; `invalid` is a subset of `errors`. Invalid
  rows remain visible locally but generate no HTTP calls. Unchanged validation
  errors are not rewritten on every refresh. Correcting the missing fields makes
  a record eligible again.

Read-only local inspection on 2026-09-29 found three error rows missing both
`ScheduledAt` and `Description`. No EMR query, repair, deletion or live delivery
was performed during this investigation. These validation failures are not
evidence of database or network timeouts.

### Refresh Timings

Launcher refresh messages include `checks`, `source`, `local`, `delivery` and
`total`, all in seconds:

- `checks`: PACS health and source SELECT 1 checks.
- `source`: order and existence reads, including serialization/connection waits,
  fetch/close and mapping overhead. This is not pure server SQL execution time.
- `local`: the remaining poll stage, including SQLite updates/reconciliation.
- `delivery`: local candidate validation and acknowledgement work plus HTTP sends.
- `total`: the whole dispatched refresh, including settings and GUI/result handling;
  it does not include the initial two-second delay or time before dispatch.

If the poll stage aborts unexpectedly without a result, its time is shown as
`read/local` rather than incorrectly assigning all time to source SQL. Delivery
exceptions preserve successful source-read evidence for the safety timer. Timing
logs contain no queries, payloads, chart numbers or credentials.

### Reconcile

- source: KaosPACS Gateway imaging worklist when Gateway URL is configured
- direction: KaosPACS Gateway imaging worklist -> local SQLite status update
- preferred source: `GET /imaging/worklist`
- if Gateway URL is configured and Gateway is unavailable, reconcile reports `KaosPACS Gateway unavailable`
- fallback source: KaosPACS API `GET /worklist` only when Gateway URL is explicitly blank
- completed returned by KaosPACS becomes local `completed`
- expired returned by KaosPACS becomes local `expired`
- KaosEghis-pacs never calculates expiry locally
- local `cancelled` is never overwritten by KaosPACS unless KaosEghis explicitly restores it in future business logic
- never creates new local rows from KaosPACS
- never deletes local rows
- never infers local business cancellation from KaosPACS imaging state

KaosEghis embeds KaosPACS Web `/imaging/worklist` on the KaosPACS Web service for admin imaging lifecycle and correction UI. KaosEghis does not render or own imaging completion correction locally.

Local state transition model:

```text
eGHIS create/update -> Active
eGHIS delete/cancel -> Cancelled
KaosPACS Completed -> Completed
KaosPACS Expired -> Expired
```

Only KaosEghis-pacs may produce `cancelled`.

Only KaosPACS may produce `completed` and `expired`.

KaosEghis does not mark imaging complete.

## Local Storage Model

Local worklist table:

- `pacs_worklist_items`

Allowed local worklist fields:

- `patient_name`
- `patient_birth_date`
- `patient_sex`
- `chart_no`
- `study`
- `modality`
- `requested_at`
- `accession_or_order_id`
- `status`
- `source`
- `kaospacs_mwl_status`
- `kaospacs_mwl_last_synced_at`
- `kaospacs_mwl_error`
- `created_at`
- `updated_at`

Local audit table:

- `pacs_audit_events`

Allowed local audit fields:

- `event_type`
- `worklist_item_id`
- `accession_or_order_id`
- `status_before`
- `status_after`
- `summary`
- `error_message`
- `created_at`

## Privacy Rules

KaosEghis-pacs does not permanently store:

- resident registration number
- phone
- address
- diagnosis
- EMR notes
- insurance information
- raw SQL result rows
- raw KaosPACS payloads

KaosEghis-pacs stores only the minimum local worklist data needed to bridge Eghis image-study orders into KaosPACS and MWL. That local worklist now includes patient name, DOB, and sex because MWL consumers need them. It does not store resident ID, phone number, address, diagnosis, EMR notes, insurance details, or raw Eghis DB rows.

Audit logs intentionally exclude sensitive patient information.

Audit rules:

- do not store patient name in audit
- do not store raw exception text in audit
- do not store raw SQL result rows in audit
- do not store raw KaosPACS payloads in audit
- use aggregate summaries for poll, sync, and reconcile
- allow sanitized non-PHI poll summaries such as:
  - `active order removed from eGHIS MWL -> marked cancelled`
- use sanitized error categories only:
  - `connection failed`
  - `timeout`
  - `invalid payload`
  - `unavailable`
  - `unknown error`

## Current UI

Visible panel module:

- [KaosEghis/ui/plugins/pacs_panel.py](/E:/Kaos/KaosEghis/KaosEghis/ui/plugins/pacs_panel.py)

Visible PACS actions:

- `Previous day`
- `Next day`
- `Today`
- `Reload Admin Page`
- `Open in External Browser`
- `Refresh`
- `Check KaosPACS`
- `Poll now`
- `Sync to KaosPACS`
- `Reconcile from KaosPACS`
- `Manual insert`
- `Edit selected`
- `Delete / Cancel selected`
- `Refresh audit`
- `Clear audit`
- `Copy audit summary`

Current table columns:

Local source worklist columns:

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

Current worklist filters:

- `Active`
- `Completed`
- `Cancelled`
- `Expired`
- `Error`
- `All`

Admin correction UI:

- KaosPACS Admin page is embedded in the PACS tab
- if Qt WebEngine is unavailable, KaosEghis shows the configured admin URL and an external-browser fallback
- KaosPACS Web owns correction actions such as manual Mark Complete or Mark Cancelled

Selected-date behavior:

- PACS worklist view is scoped to the selected date
- `Poll now` queries the selected date only
- `Refresh` refreshes the local SQLite rows for the selected date only
- selected date persists for the current UI session until the operator changes it

Audit table columns:

- `Time`
- `Type`
- `Accession / Order ID`
- `Status Before`
- `Status After`
- `Summary`
- `Error`

## PACS Settings

Editable PACS settings in the Settings tab:

- `eghis_db_connection_string`
- `eghis_db_image_study_query`
- `kaospacs_api_base_url`
- `kaospacs_gateway_url`
- `kaospacs_web_admin_url`
- `kaospacs_gateway_api_token`
- `kaospacs_patient_context_bind_host`
- `kaospacs_patient_context_port`
- `kaospacs_integration_token`
- `kaospacs_api_timeout_seconds`
- `pacs_auto_poll_enabled`
- `pacs_refresh_mode` (`chart_clear` by default; `timer` for rollback)
- `pacs_poll_interval_seconds`
- `pacs_dry_run`

Rules:

- connection string is hidden by default
- gateway API token is hidden by default
- patient-context integration token is hidden by default
- production `kaospacs_api_base_url` should point to Gateway `:8060`, not MWL internal API `:8055`
- `kaospacs_web_admin_url` points to KaosPACS Web at `:8070/imaging/worklist`, not the Gateway API
- when KaosEghis-pacs and KaosPACS run on different machines, `kaospacs_patient_context_bind_host` should be the KaosEghis-pacs LAN IP such as `192.168.0.100`, not `127.0.0.1`
- poll interval minimum is `15` seconds
- auto poll is off by default
- dry run is off by default
- testing KaosPACS connection uses `GET /health` only
- When enabled, `Chart clear/load` mode waits two seconds after a verified clear
  or sampled numeric load/change, then refreshes that day's PACS orders. A clear
  also requests a follow-up at clear +30 seconds. Loads preserve that deadline
  and do not schedule their own follow-up. A later clear updates the deadline.
  Startup and detected EMR reconnect also refresh with one +30-second follow-up.
  The persisted mode key remains `chart_clear`; no settings migration is needed.
  The selected historical date affects Poll Now, not chart-triggered jobs.
- With automatic event refresh enabled, five minutes without a successful read
  for today requests a safety refresh, independent of chart signals and EMR focus.
  Failures of that check back off by 60, 120, 240, then 300 seconds, capped there.
  Successful reads reset the deadline; events, failed reads and historical reads
  do not. The five-second deadline timer itself performs no database access.
- Poll Now remains available with automatic refresh disabled. It also runs on the
  background worker. Requests received during a refresh coalesce by date rather than
  being discarded. Fast reads and delayed follow-ups are queued separately so a
  load does not consume a future follow-up. Already-due work for the same day is
  combined. Failed reads do not advance the last-successful-read timestamp.
- The legacy timer is retained as an explicit rollback option. Existing automatic
  enable/disable and dry-run settings are preserved. Restart the desktop after updating.
- All existing eGHIS database readers now use the shared serialized read queue.
  Connections are read-only, bounded, and closed before local work or HTTP delivery.
  See [KaosEghis-emr](kaoseghis-emr.md) for concurrency boundaries and live checks.
- This stage does not change the imaging query into an all-orders/status snapshot,
  nor guarantee immediate delivery after a missed signal or delayed save. The safety
  check covers silent changes while the app and services are available; Poll Now
  remains the immediate manual fallback. F6/F7 signals are still diagnostic only.
- Explicit source cancellations whose previous delivery failed remain eligible
  for the next sync, including the bounded follow-up, until PACS acknowledges them.
  Source read success and delivery success remain separate; no clear implies cancellation.

## Legacy Patient-Context API

The older `core/kaospacs_patient_context_api.py` implementation is retained for
compatibility, with its own tests. It is not started by the desktop application.
The current desktop starts only `service/kaospacs_api.py`, using
`kaospacs_patient_context_bind_host`, `kaospacs_patient_context_port`, and
`kaospacs_integration_token`. This keeps the current loopback default and avoids
starting two listeners on port 8765. The settings below apply only to callers
that explicitly start the legacy implementation.

The legacy API provides a read-only endpoint backed by the local PACS worklist
for patient demographic fallback:

```text
GET /api/kaospacs/patient-context?chart_no=<chart_no>
Authorization: Bearer <kaospacs_gateway_api_token>
```

Default listener settings:

```text
kaospacs_patient_context_api_enabled=true
kaospacs_patient_context_api_host=0.0.0.0
kaospacs_patient_context_api_port=8765
kaospacs_patient_context_api_allow_loopback_without_token=true
```

The endpoint returns only:

- `chart_no`
- `patient_name`
- `patient_birth_date`
- `patient_sex`
- `source`
- `confidence`

It does not return orders, reports, diagnoses, notes, resident IDs, phone
numbers, addresses, insurance data, or raw eGHIS records.

For the clinic deployment, allow the PACS host `192.168.0.200` to reach the EMR
host `192.168.0.100:8765`. KaosPACS Web uses this endpoint only when
`/emr.php?m_patid=<chart_no>` lacks name/DOB/sex and Orthanc has no local DICOM
metadata for that patient yet.

KaosPACS Web also has a browser-local fallback for EMR desktops. The browser can
call `http://127.0.0.1:8765/api/kaospacs/patient-context` from the EMR machine
itself. Loopback calls may be allowed without a bearer token so the shared token
is not exposed in browser HTML. Non-loopback callers still require the bearer
token when configured.

## Startup Validation

On PACS panel startup, KaosEghis-pacs validates:

- SQLite availability
- PACS settings readability
- poll timer configuration normalization
- current dry-run state

Startup does not:

- poll automatically
- sync automatically
- reconcile automatically
- check KaosPACS automatically

Startup reports configuration readiness only.

## Dry-Run Mode

Setting:

- `pacs_dry_run`

Behavior:

- Poll: normal
- Sync: simulate only
- Reconcile: simulate only

Dry-run rules:

- no KaosPACS modifying API calls are made
- sync state is not changed locally during dry-run sync
- local worklist status is not changed during dry-run reconcile
- operator-visible status text includes `DRY RUN`
- audit summaries include `DRY RUN`

## Deployment Checklist

### Prerequisites

- PostgreSQL connectivity available from the workstation
- KaosPACS reachable from the workstation
- local SQLite initialized
- KaosPACS API endpoint reachable
- poll interval configured
- auto poll disabled by default unless explicitly enabled

### Operator Checklist

- [ ] Poll now works
- [ ] Local worklist updates
- [ ] Manual insert works
- [ ] Manual edit works
- [ ] Sync to KaosPACS works
- [ ] Reconcile works
- [ ] Audit works
- [ ] Auto poll works
- [ ] Settings persist
- [ ] No PHI appears in audit

## Current Query Boundary

Primary module:

- [KaosEghis/core/pacs_polling.py](/E:/Kaos/KaosEghis/KaosEghis/core/pacs_polling.py)

Current default query boundary:

- `public.mwl`
- `public.h2opd_doct_ord`
- `m.scheduled_proc_status = '100'`
- `o.proc_dept_cd = 'XRAY'`
- cancellation tracking through `o.dc_yn`

## Diagnostics

Read-only CLI diagnostic:

- `python -m KaosEghis.tools.debug_pacs_poll`

Diagnostic rules:

- reads PACS settings from local KaosEghis SQLite
- runs read-only aggregate queries against Eghis DB
- prints only sanitized counts and filter diagnostics
- does not print patient name, DOB, sex, resident ID, phone, address, diagnosis, EMR notes, or raw rows
- helps confirm whether recent BMD-like rows are excluded by join failure, status filtering, or `proc_dept_cd = 'XRAY'`

## Completed

- Plugins UI
- Local worklist
- Read-only PostgreSQL adapter
- Cancellation tracking
- KaosPACS API bridge
- Manual worklist editor
- Auto polling
- Reconciliation
- PACS settings UI
- Local audit
- Embedded KaosPACS Web admin page

## Not In Scope

- direct DICOM writes
- direct Orthanc writes
- direct MWL writes
- background scheduler outside the running UI process

## Maintenance Rule

Update this document whenever:

- local PACS fields change
- API boundary changes
- privacy rules change
- startup validation changes
- dry-run behavior changes
- deployment guidance changes
- status ownership rules change
