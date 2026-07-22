# KaosEghis-inj

Last updated: 2026-07-22

## Status

`KaosEghis-inj` is a planned KaosEghis plugin and Raspberry Pi display workflow.
This document defines the intended architecture before implementation. It does not
describe a currently active clinical workflow.

## Purpose

KaosEghis-inj will provide a simple injection-room worklist for staff who should not
need to operate the Windows EMR directly.

The system will:

- read injection orders from eGHIS in read-only mode
- maintain the authoritative injection-room worklist in KaosEghis
- detect new, changed, cancelled, deleted, restored, and reordered source orders
- display the current worklist on a Raspberry Pi kiosk
- let staff mark a worklist row Done and undo that action with confirmation
- keep the Raspberry Pi free of durable patient data
- operate automatically during configured office hours

Done is an operational KaosEghis-inj worklist state. It does not write an
administration record to eGHIS and must not be described as eGHIS documentation.

## Operator Model

The Raspberry Pi should behave like an appliance, not another workstation.

For staff, normal operation should be limited to:

- reading the current list
- vertical scrolling
- selecting `Done`
- selecting `Undo`
- using one large retry control if automatic recovery has not succeeded

Staff should not see a desktop, terminal, settings screen, browser chrome, title bar,
close button, context menu, or mouse-accessible exit path.

Administrative controls remain in KaosEghis. The Pi may expose only narrow,
authenticated appliance controls such as health, reload, wake, sleep, display-app
restart, and reboot.

## Architecture

```text
eGHIS PostgreSQL (read-only)
            |
            v
KaosEghis-inj on EMR workstation
  - polling and reconciliation
  - authoritative local worklist
  - Done / Undo state
  - daily worklist lifecycle
  - worklist API
  - Pi health and control
            |
            | non-PHI reload signal
            v
Raspberry Pi kiosk
  - Raspberry Pi OS Lite 64-bit
  - full-screen kiosk browser
  - transient in-memory worklist
  - scrolling and Done / Undo controls
  - display schedule and self-recovery
            |
            | authenticated pull
            +-----------------------> KaosEghis-inj worklist API
```

## Ownership Boundary

### KaosEghis-inj owns

- read-only eGHIS database access
- injection-order classification
- stable source-order identity
- local worklist persistence
- worklist state transitions
- Done and Undo persistence
- daily rollover and privacy retention
- API authentication and authorization
- Pi health monitoring and narrow control requests
- sanitized operational audit

### Raspberry Pi owns

- kiosk presentation
- vertical scrolling
- transient in-memory display state
- office-hours display schedule
- display wake, sleep, and privacy blanking
- automatic reconnect and display-process recovery
- sending an opaque item ID for explicit Done or Undo actions

### Raspberry Pi does not own

- eGHIS database access
- order filtering or reconciliation
- authoritative worklist state
- durable patient or order storage
- clinical administration documentation
- arbitrary remote commands

## Confirmed eGHIS Findings

The inspected eGHIS PostgreSQL data supports this working classification:

- `public.h2opd_doct_ord` is the order source
- `ord_type = '07'` strongly identifies injection-style orders
- `proc_dept_cd = 'INJ'` is the routing signal currently expected for the injection
  room workflow
- `dc_yn = 'Y'` represents an explicit source cancellation
- `inject_path` is not reliable enough to be the primary routing filter

Examples observed under the working rule include:

- `타마돌주사(트라마돌염산염)`
- `티램주(염산티로프라미드)`
- `페니라민주사(클로르페니라민말레산염)`
- `동광염산린코마이신주`
- `디페인주사(디클로페낙나트륨)`

The production query must be validated again against the live schema before
deployment. No write permission is required or permitted.

## Read-Only Source Data

### Order table

`public.h2opd_doct_ord` fields expected to be useful:

- `recept_no`
- `ord_no`
- `ord_seq_no`
- `ord_cd`
- `medfee_nm`
- `ord_type`
- `proc_dept_cd`
- `dc_yn`

### Patient linkage

Read-only joins observed so far:

- `public.h1opdin`
  - `recept_no`
  - `ptnt_no`
  - `sex`
  - `ageday`
- `public.hz_mst_ptnt`
  - `ptnt_no`
  - `ptnt_nm`
  - `birth_ymd`
  - `sex`

The display should use only the minimum demographics required by staff. The final
field set must be reviewed before implementation rather than copying whole source
rows.

## Stable Order Identity

Do not match orders by patient name or order description. Use a stable source key
derived from:

```text
recept_no + ord_no + ord_seq_no
```

KaosEghis should also assign an opaque local worklist item ID. The Pi uses the opaque
ID for Done and Undo requests and does not need source database keys.

## Worklist States

Initial states:

- `active`: waiting in the injection-room worklist
- `done`: staff marked the operational row complete
- `cancelled`: eGHIS explicitly cancelled or confirmed removal of the source order

Optional internal reason values may distinguish:

- `source_cancelled`
- `source_removed`
- `operator_done`
- `operator_undo`
- `source_restored`

### State transitions

```text
new eGHIS order                  -> active
source field change              -> active, updated revision
dc_yn = Y                        -> cancelled
confirmed hard deletion          -> cancelled (source_removed)
cancelled source order restored  -> active
staff confirms Done              -> done
staff confirms Undo              -> active, only if source remains valid
```

Done and Cancelled are not interchangeable. Done is an operator worklist action;
Cancelled reflects eGHIS business order state.

## Polling and Reconciliation

Polling does not need to compare every patient in eGHIS. Each cycle should use two
narrow read-only paths.

### 1. Discover current injection orders

Query the selected/current service date for:

- `ord_type = '07'`
- `proc_dept_cd = 'INJ'`
- both normal and cancelled `dc_yn` values

Do not filter cancelled rows out before reconciliation. Otherwise a cancellation
would be indistinguishable from a query omission.

### 2. Revalidate locally active source keys

For source keys currently stored as Active:

- check whether the exact key still exists
- read `dc_yn`
- compare normalized display fields
- do not apply the active-order, INJ, department, or cancellation filters to the
  existence check

This catches a patient declining an injection after the order was already displayed.
The next successful poll sees `dc_yn = 'Y'`, marks the local item Cancelled, increments
the worklist generation, and signals the Pi to reload.

### Hard deletion safety

Absence from the filtered discovery query must never be treated as deletion.

Only mark an active row `cancelled/source_removed` when:

- its exact stable key is absent from a separate unfiltered existence query
- eGHIS connectivity and query execution succeeded
- preferably, absence is confirmed in two consecutive polls

If the database is unavailable, the query is rejected, or results are incomplete,
cancel nothing.

### Changes

Normalize only approved display fields and compare them with the stored row. When
they differ:

- update the same worklist item
- increment its revision
- set `changed_at`
- keep Active unless source state says otherwise
- signal the Pi to reload
- let the Pi temporarily highlight the changed row

### Done rows

Done rows do not need high-frequency source comparison and are excluded from the live
active reconciliation set. A lower-frequency audit reconciliation may be added later
if operational experience shows that post-completion source cancellation matters.

## Generation-Based Synchronization

KaosEghis should update local rows in one transaction. If the visible worklist
changes, increment a monotonically increasing worklist generation.

The Pi should fetch and atomically replace its complete in-memory list rather than
applying individual patient/order events.

Example response shape:

```json
{
  "generation": 42,
  "work_date": "2026-07-22",
  "server_time": "2026-07-22T09:15:12+09:00",
  "source_status": "available",
  "items": []
}
```

The reload notification contains no patient information. If a notification is lost,
the Pi performs a periodic full refresh and compares the generation number.

## Daily Lifecycle

The worklist is date-scoped. Yesterday's list must never be reused as today's current
list.

### Before opening

1. Pi clears its in-memory display.
2. KaosEghis selects a new current work date.
3. KaosEghis performs a read-only initial poll for that date.
4. Pi fetches the complete current list.
5. Display turns on at the configured opening time.

If KaosEghis or eGHIS is unavailable, show a clear unavailable/recovery screen. Do
not present the previous day's list as current.

### During office hours

- poll eGHIS at a measured, configurable interval
- reconcile new, changed, cancelled, and removed active rows
- notify the Pi only when generation changes
- keep periodic Pi refresh as a missed-signal fallback
- preserve staff scroll position across ordinary refreshes
- show a `new items` affordance rather than forcibly jumping while staff are reading

### Closing

- turn off or blank the display automatically
- clear patient/order data from Pi memory
- keep the Pi powered
- close the current display session
- apply KaosEghis-side identifying-data retention according to the approved policy

Completed and cancelled rows are visible only within the current day's operator
worklist. The next day's view begins clean.

## Raspberry Pi Appliance

### Recommended operating system

- current stable Raspberry Pi OS Lite, 64-bit
- minimal Wayland kiosk compositor
- Chromium in kiosk mode, or an equivalently locked display client
- `systemd` services for startup, health, and recovery
- read-only/overlay root filesystem where practical
- temporary logs and browser data

### Staff-facing display

- full-screen read-only list presentation
- vertical scrolling only
- large rows and wide scrollbar/touch targets
- no horizontal scrolling
- sticky connection and last-refresh status
- Active rows first
- Done and Cancelled rows remain visible below Active rows
- Done rows are grey and struck through
- Cancelled rows use a distinct cancelled treatment
- no automatic carousel scrolling
- optional `Top`, `New items`, and `Retry` controls only

### Done flow

1. Staff selects `Done` on an Active row.
2. Confirm: `이 항목을 완료 처리하시겠습니까?`
3. Pi sends the opaque item ID and requested action to KaosEghis.
4. KaosEghis persists Done with a timestamp and increments generation.
5. Pi reloads.
6. Row remains visible, moves below Active rows, and is struck through.
7. Its control becomes `Undo`.

### Undo flow

1. Staff selects `Undo`.
2. Confirm: `완료를 취소하고 대기 목록으로 되돌리시겠습니까?`
3. KaosEghis verifies the source order is still present and not cancelled.
4. If valid, state returns to Active and generation increments.
5. If invalid, the row remains non-active and shows the source cancellation/removal
   status.

### No mouse exit

The kiosk must provide no mouse-accessible Exit or Close control. Disable:

- title bar and window controls
- context menus
- browser chrome
- desktop access
- ordinary mouse exit gestures

Maintenance remains possible through authenticated remote administration or a
protected administrator-only keyboard sequence.

## Display Power and Office Hours

The Pi remains powered continuously. Staff should not need to unplug it.

- display wakes automatically before opening
- display sleeps or blanks automatically after closing
- a changed worklist can wake the display during configured office hours
- privacy idle timeout may blank the list while leaving the Pi online
- after reboot, current time and health determine the correct display state
- if network time is unavailable at boot, the appliance must fail safely rather than
  displaying stale information

Prefer monitor DPMS/HDMI blanking. Use HDMI-CEC only when the connected display
supports it reliably. Do not routinely cut monitor or Pi power with a relay.

## Self-Healing and Failure UX

Staff should not troubleshoot the Pi.

Automatic recovery order:

1. retry the failed worklist request
2. reconnect to KaosEghis
3. restart the kiosk/browser process
4. reboot the Pi only after repeated failures
5. notify the administrator if health remains bad

Staff-facing status should be short and unambiguous:

- `정상 연결`
- `연결 복구 중`
- `목록을 불러올 수 없습니다. 관리자에게 문의하세요.`

Never show stale rows as though they are current. Show last successful refresh time
and an unmistakable unavailable state.

## API Boundary

Final route names may change, but responsibility should remain as follows.

### Pi pulls worklist from KaosEghis

```text
GET /api/inj/worklist?date=YYYY-MM-DD
```

Response includes generation, health/status metadata, and the approved current-day
display fields.

### KaosEghis signals Pi

```text
POST /api/reload-worklist
```

Example non-PHI body:

```json
{
  "reason": "worklist_changed",
  "generation": 42
}
```

### Pi requests worklist transitions

```text
POST /api/inj/worklist/<opaque_item_id>/done
POST /api/inj/worklist/<opaque_item_id>/undo
```

These actions modify KaosEghis local operational state only. They do not write to
eGHIS.

### Appliance controls

Potential authenticated controls:

```text
GET  /health
POST /display/wake
POST /display/sleep
POST /worklist/reload
POST /service/restart
POST /system/reboot
```

Do not expose arbitrary shell execution or remote desktop as part of the operator
protocol.

## Security

- use separate strong bearer tokens for Pi-to-KaosEghis and administrator-to-Pi
  access
- bind services only to the required private interface
- restrict source IPs/firewall rules where practical
- never put tokens in URLs
- never display tokens in the kiosk
- do not log request bodies containing patient/order data
- return `Cache-Control: no-store` for worklist responses
- disable browser disk cache for the worklist client or place its profile on volatile
  storage
- rate-limit transition and appliance-control endpoints
- record only sanitized event type, opaque item ID, state transition, result, and
  timestamp in routine audit

## Privacy

### KaosEghis local storage

KaosEghis may store the minimum current-day operational fields needed for the
injection-room list. Candidate fields require final review but may include:

- opaque local item ID
- stable source order key
- work date and order time
- patient number and display name
- minimum age/sex context if operationally required
- order code and display name
- state and state reason
- revision and timestamps

Do not copy raw eGHIS rows. Do not store unrelated diagnosis, notes, address, phone,
insurance, billing, or resident registration data.

### Raspberry Pi

- no durable worklist database
- no durable browser cache containing worklist responses
- no screenshots
- no patient/order values in logs
- no patient data in reload signals
- clear in-memory list at closing, logout, connection failure, and daily rollover

## Draft Local Data Model

An implementation may use a table shaped approximately as follows:

```text
inj_worklist_items
  id
  opaque_id
  source_order_key
  recept_no
  ord_no
  ord_seq_no
  work_date
  status                  active / done / cancelled
  status_reason
  patient_no
  patient_name
  patient_sex
  patient_age
  order_code
  order_name
  ordered_at
  source_fingerprint
  revision
  consecutive_missing_count
  first_seen_at
  last_seen_at
  changed_at
  done_at
  cancelled_at
  created_at
  updated_at
```

The final migration must use only approved fields. Database rows remain on the
KaosEghis workstation, not the Pi.

## Testing Plan

### Polling

- new current-day INJ order creates one Active row
- duplicate poll is idempotent
- changed source fields update the same row and revision
- `dc_yn = 'Y'` marks an Active row Cancelled
- absence from filtered discovery does not cancel a row
- confirmed absence from unfiltered existence check cancels after the configured
  confirmation count
- DB failure cancels nothing
- restored source order reactivates the existing row
- Done rows are excluded from high-frequency active reconciliation

### API and synchronization

- generation increments only for visible state changes
- reload signal contains no patient information
- Pi full refresh replaces the in-memory snapshot atomically
- missed reload signal is recovered by periodic pull
- invalid or replayed Done/Undo requests fail safely
- Undo verifies source validity
- worklist responses use `no-store`

### Kiosk

- starts directly in full-screen worklist
- no mouse-accessible exit exists
- list remains vertically scrollable
- refresh preserves scroll position
- Done row remains visible and struck through
- Undo requires confirmation
- current-day rollover clears prior display
- unavailable backend never presents stale rows as current
- browser/worklist data is not durably stored
- display wakes and sleeps on schedule
- kiosk process restarts automatically after failure

### Privacy and logging

- no PHI in reload or health requests
- no PHI in Pi logs
- no raw eGHIS rows in KaosEghis logs
- no tokens in UI, URLs, or logs
- daily cleanup follows the approved retention rule

## Implementation Milestones

### Milestone 0: Source verification

- confirm the live order query and date field
- confirm cancellation and hard-deletion behavior
- measure narrow poll performance
- confirm the minimum required patient/order display fields

### Milestone 1: Local read-only worklist

- SQLite migration and repository
- manual Poll now diagnostic surface
- new/change/cancel/restore reconciliation
- generation tracking and sanitized audit
- no Pi integration yet

### Milestone 2: Worklist API

- authenticated current-day worklist endpoint
- Done/Undo endpoints
- health and generation metadata
- no-store responses and privacy tests

### Milestone 3: Raspberry Pi kiosk

- Raspberry Pi OS Lite image/setup
- full-screen scrollable list
- Done/Undo confirmation and struck-through Done rows
- no mouse exit
- no durable PHI
- periodic refresh and reload signal support

### Milestone 4: Office-hours appliance control

- automatic display wake/sleep
- daily reset and startup recovery
- Pi health status in KaosEghis
- narrow reload/restart/reboot controls
- administrator notification for persistent failure

### Milestone 5: Deployment hardening

- firewall and token rotation guidance
- read-only/overlay filesystem
- power-loss testing
- unplug/reboot recovery testing
- live workflow observation and operator adjustments

## Non-Goals

KaosEghis-inj will not initially:

- write into eGHIS
- document medication administration in eGHIS
- let the Pi query PostgreSQL directly
- store durable PHI on the Pi
- send patient data in reload notifications
- expose arbitrary remote shell execution
- provide remote desktop to staff
- become a medication ordering or clinical decision system
- infer clinical completion from display interaction alone
