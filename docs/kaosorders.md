# KaosOrders cross-system implementation plan

Last updated: 2026-09-30

## Purpose and settled boundaries

KaosOrders is the staff-facing, read-only order board that replaces the earlier
KaosInj concept. The clinic has one doctor and one Windows EMR workstation.

The deployment recommendation is explicit:

```text
eGHIS PostgreSQL
  -> KaosEghis on the Windows EMR workstation (read-only source access)
  -> authenticated LAN updates
  -> KaosOrders backend on KaosClinic
  -> authenticated board reads
  -> older Acer laptop running LMDE and Chrome/Chromium kiosk mode
```

The Acer laptop is a viewer only. It does not host the KaosOrders backend or a
patient/order database. KaosOrders never queries eGHIS, KaosPACS, Orthanc,
DICOM, or MWL directly. It never edits EMR orders and never infers examination
completion from EMR encounter completion.

## Current versus planned

### Verified KaosEghis foundation

The Windows checkout was verified clean at `44e3d8f`, then the shared-reader
hardening was committed and pushed as `3100421`.

Implemented and covered by mocked/isolated tests:

- verified chart clear/load triggers;
- two-second clear/load debounce;
- one clear +30-second follow-up with replacement/preservation rules;
- startup/reconnection reconciliation and a five-minute successful-read safety
  check;
- manual `Poll Now`;
- one in-process FIFO worker shared by PACS, flu reporting, health checks,
  patient context, and diagnostics;
- a Windows machine-wide mutex across updated Kaos processes;
- immediate cursor/connection cleanup before local processing or delivery; and
- fail-closed behavior that blocks subsequent reads when physical connection
  closure is uncertain.

The focused and broader regression runs passed 111 and 474 tests respectively
using mocked source connections and isolated test locks. Production data and
the running EMR were not accessed.

Still gated:

- production least-privilege/session verification;
- a reviewed, parameterized operation-only query API;
- bounded recovery from a non-returning/stuck driver;
- the all-orders plus reception-status reader;
- stable encounter/order identities from the real schema; and
- any KaosOrders publisher or production-table query.

See [KaosEghis-emr](kaoseghis-emr.md), especially its Windows verification and
acceptance-gate sections.

### Implemented KaosOrders v1 foundation

The separate KaosOrders repository contains:

- FastAPI `GET /health`;
- bearer-authenticated per-encounter `POST /api/v1/order-snapshots`;
- separately authenticated `GET /api/v1/board`;
- SQLite storage for a minimum current-patient projection;
- idempotent encounter/order upserts, stale timestamp rejection, explicit order
  withdrawal, and non-destructive `UNKNOWN` handling;
- a responsive CSS grid with no fixed column count;
- board rendering for `보류` encounters with `XRAY`, `BMD`, or `ECG`;
- no service worker, IndexedDB, localStorage, export, or edit path;
- an isolated Docker network and exact-host-address port binding; and
- API, privacy, UI-smoke, and deployment tests.

V1 limitations:

- `완료` currently hides a patient instead of showing `처방완료`;
- there is no read-only order-detail endpoint or modal;
- the API is an encounter-at-a-time upsert, not a revisioned daily
  reconciliation protocol;
- omitted orders are deliberately non-destructive;
- there is no stale-state banner or restart revision-gap protocol;
- retention is rolling inactivity, not a clinic-day lifecycle; and
- some runtime wording still references the earlier Raspberry Pi viewer.

### Planned work

- verify production read-only permissions and introduce registered parameterized
  operations without changing PACS results;
- discover real daily order/reception identities and completeness semantics;
- compare complete validated source snapshots and deliver only changes;
- add revisions, retries, restart resynchronization, and stale-state display;
- add completed `처방완료` tiles with minimum read-only details;
- keep diagnostic `보류` tiles non-clickable and category-only;
- migrate to a single-clinic-day retention model; and
- configure the Acer LMDE kiosk using its measured display characteristics.

No production EMR query, schema, index, role, permission, or server setting is
changed by this planning work.

## Superseded proposals

- Raspberry Pi 4 viewer -> existing Acer laptop running LMDE.
- Assumed 1920x1080 layout -> measure the Acer's actual resolution and scaling.
- Five fixed tiles per row -> responsive columns chosen by readable minimum
  tile width.
- Per-chart F7 polling or treating F6/F7 as save proof -> verified chart-number
  clear/load changes request whole-day reconciliation; keys/buttons remain
  diagnostic only.
- Focus/caret manipulation or injected F1 -> no focus movement or injected key
  is permitted for polling.
- Unsettled backend location -> KaosClinic backend with Acer kiosk-only is the
  recommended deployment.
- KaosEghis-inj/KaosInj task-board direction -> separate KaosOrders service.

## Deployment options

### Backend on KaosClinic, Acer as kiosk only — recommended

This preserves the existing KaosOrders Compose/server foundation, lets the
screen reboot without losing server state, and keeps temporary patient data off
the kiosk. Bind the service only to KaosClinic's clinic-LAN address and firewall
it to the EMR workstation and Acer. Do not add Caddy, Cloudflare, public DNS,
router forwarding, PACS networks, or public/Tailscale ingress.

### Backend and kiosk on the Acer — fallback only

This couples screen, service, database, power, browser maintenance, and recovery
on one old staff device. Reconsider only if KaosClinic cannot reliably host the
small service.

## Board tile and state rules

The board is a responsive grid of comfortably sized multi-line tiles. The
actual Acer resolution and viewing distance determine the minimum tile width;
five columns is not a requirement.

| Verified source state | Relevant orders | Board behavior | Click behavior |
| --- | --- | --- | --- |
| `접수` or `진료` | any | hidden | none |
| `보류` | none | hidden | none |
| `보류` | `XRAY`, `BMD`, or `ECG` | restrained diagnostic tile | none |
| `완료` | none | hidden | none |
| `완료` | at least one board-relevant order | tile with `처방완료` | read-only relevant-order details |
| `취소` or verified removal | any | withdraw/hide | none |
| unavailable/unknown/failed/partial | any | keep last validated state; mark stale after threshold | no destructive change |

Every visible tile shows chart number, sex/age display, patient name, source
state, and allowlisted category badges.

For `보류`, coexisting ordinary orders are neither shown nor available through
details. Diagnostic tiles do not open a detail view. X-ray/BMD may retain the
imaging accent; ECG stays visually separate and does not imply PACS/DICOM
integration.

For `완료`, `처방완료` means EMR encounter completion, not imaging completion.
Clicking opens a read-only detail surface; clicking its backdrop or explicit
back/close control returns to the grid. It has no edit, cancel, completion, or
EMR-write controls.

Only allowlisted board-relevant order details should be transported or shown.
Whether completed details include categories beyond `XRAY`/`BMD`/`ECG` remains
a business decision; do not expose every ordinary order by default.

State recalculation must cover edits, deletion of one or every order, encounter
removal/cancellation, and `완료 -> 보류`. A verified transition back to `보류`
becomes a non-clickable diagnostic tile only if an eligible category remains.

## Source reconciliation rules

1. UI signals and F6/F7 observations request a read only.
2. Only a complete validated source read may produce destructive differences.
3. A failed, timed-out, cancelled, partial, or schema-invalid read does not
   replace the last validated snapshot and cannot mean “empty day.”
4. Normal reads compare against the last validated snapshot and publish only
   changed upserts/withdrawals.
5. Omission in a delta message has no meaning.
6. Omission in an authoritative daily replacement means removal only after a
   complete validated source read.
7. Delivery retries reuse the same delivery identifier and payload.
8. Duplicate accepted revisions are acknowledged idempotently; lower revisions
   are rejected.
9. A revision gap, reset, restart, or explicit recovery requests a full
   authoritative resynchronization for the affected source day.
10. The server keeps the last validated projection during source/delivery
    failure and displays stale state after a configured age.

Pending reasons and source dates remain coalesced while one read runs. Events
retain their dates across midnight. The source connection closes before local
comparison, persistence, or network delivery.

## Proposed transport contract

The implemented v1 contract remains during migration. This is a proposed v2
semantic shape, not a final schema; real key derivations require source evidence.

```http
POST /api/v2/reconciliations
Authorization: Bearer <KAOSORDERS_INGEST_TOKEN>
Content-Type: application/json
Idempotency-Key: <stable-delivery-uuid>
```

```json
{
  "schema_version": 2,
  "delivery_id": "stable-uuid-reused-for-retries",
  "source_day": "2026-09-30",
  "revision": 42,
  "mode": "delta",
  "observed_at": "2026-09-30T14:32:08+09:00",
  "operations": [
    {
      "operation": "upsert",
      "encounter_source_id": "TBD_FROM_VERIFIED_SCHEMA",
      "chart_number": "1234",
      "patient_name": "김아무개",
      "sex_age_display": "F/53",
      "reception_status": "완료",
      "orders": [
        {
          "order_source_id": "TBD_FROM_VERIFIED_SCHEMA",
          "board_category": "XRAY",
          "display_label": "엑스레이",
          "source_status": "ACTIVE"
        }
      ]
    }
  ]
}
```

Contract rules:

- `delivery_id` provides retry idempotency; `revision` is monotonic per
  `source_day` in a durable minimal KaosEghis outbox.
- `mode=delta` contains explicit `upsert`, `withdraw_order`, or
  `withdraw_encounter`; omissions are non-destructive.
- `mode=replace` is accepted only after a complete validated daily read and is
  authoritative for that source day.
- source IDs are required semantic slots but remain `TBD` until schema
  verification. Do not derive them from chart number, time, text, or row order.
- send only tile/detail fields, source identifiers/state, and timestamps/
  revision. Never send resident number, DOB, phone, address, diagnosis, notes,
  insurance, raw rows, raw payloads, or unrelated orders.
- acknowledgements contain delivery/revision and aggregate counts only.

Before v2 is finalized, decide whether completed details use a dedicated
authenticated endpoint or an embedded minimum projection. A dedicated endpoint
reduces each board refresh but needs identical no-store/authentication rules.

## Single-clinic-day lifecycle

KaosOrders is a disposable projection, not a ledger.

- tag rows with `source_day`;
- serve only the active clinic day;
- stop serving the previous day at the configured Asia/Seoul boundary;
- physically purge prior-day rows after a validated current-day replacement or
  a short bounded grace period;
- retain the last validated current-day state through transient failure; and
- exclude the SQLite database from cloud/general-purpose backups.

`04:00 Asia/Seoul` is a candidate boundary, not an approved or implemented
value. The current rolling retention remains v1 behavior until migrated.

## LMDE kiosk plan

Record the Acer's native resolution, scaling, viewing distance, and comfortable
Korean type size before choosing tile dimensions. Continue using CSS `auto-fit`.

Planned kiosk behavior:

- dedicated unprivileged kiosk account;
- automatic login only if clinic physical-security policy permits;
- startup after network availability and relaunch after browser failure;
- Chrome/Chromium kiosk mode with a RAM-backed temporary profile;
- sync, password saving, translation, downloads, extensions, crash/session
  restore, service workers, and disk cache disabled;
- automatic reconnect while retaining the last in-memory board with clear
  disconnected/stale status;
- suspend, hibernate, and lid-close sleep disabled on clinic AC power;
- documented keyboard/mouse maintenance exit;
- manual after-hours LMDE/browser updates and tested reboot; and
- a recovery sheet for browser, LAN, token, and KaosClinic outages.

The v1 URL-fragment/sessionStorage token supports manual provisioning.
Unattended provisioning needs a separate protected design; do not place a
long-lived token in a world-readable file, shell history, or process argument.

## Staged implementation

### Completed foundation

- Windows checkout/source verification;
- shared FIFO and machine mutex;
- chart clear/load scheduling and PACS reconciliation behavior;
- connection cleanup hardening and fail-closed latch; and
- mocked/isolated regression coverage.

### Stage 1 — remaining source-safety gates

- replace configurable/arbitrary SQL entry with registered parameterized
  operations while preserving current PACS/flu results;
- define operator recovery for a stuck driver/retained mutex; and
- verify production credentials/session restrictions using aggregate-only,
  non-writing diagnostics.

### Stage 2 — source discovery and reader

- prove encounter/order identities, states, and complete-read criteria;
- implement complete daily all-orders/reception reads against sanitized fixtures;
- test edits, every-order deletion, cancellation/removal, and
  `완료 -> 보류`; and
- keep results local; do not publish yet.

### Stage 3 — comparison and delivery shadow mode

- retain a temporary validated snapshot and durable minimal outbox;
- calculate deltas and authoritative replacements;
- validate payloads/revisions against a non-production KaosOrders target; and
- leave current PACS delivery unchanged.

### Stage 4 — KaosOrders v2 and board UX

- add revisioned reconciliation alongside v1;
- add clinic-day storage and stale state;
- implement the tile matrix, `처방완료`, and read-only details; and
- keep changes behind feature flags with v1 rollback.

### Stage 5 — kiosk and supervised cutover

- install/harden LMDE on the Acer;
- calibrate the actual display and configure startup/power/recovery;
- restrict LAN access to the EMR workstation and Acer; and
- run live acceptance before routine use.

## Isolated tests

- source coordinator gates listed in `docs/kaoseghis-emr.md`;
- schema fixtures for every verified reception/order transition;
- delta/replace, retry idempotency, lower revisions, revision gaps, restart
  resync, and day rollover;
- no mass removal on empty partial/failed/timed-out reads;
- privacy schema/log tests and forbidden-field rejection;
- tile matrix, mixed-order filtering, non-clickable diagnostic tiles, completed
  detail open/backdrop-close, and responsive measured-resolution tests; and
- kiosk reconnect/crash/reboot tests using a temporary profile.

## Live acceptance checks

- one Kaos-managed source connection during overlapping PACS/flu/KaosOrders
  requests and visibly read-only source sessions;
- current PACS poll/sync/reconcile behavior remains correct;
- clear/load, +30 seconds, safety, manual poll, reconnect, and midnight behavior
  match the verified plan;
- source edits/deletions/cancellation and `완료 -> 보류` converge correctly;
- failed reads retain prior board state with stale indication;
- retries produce no duplicate rows;
- the Acer boots into the grid, reconnects, stays awake, and has a maintenance
  exit; and
- browser storage and logs contain no persisted patient/order data, raw rows,
  payloads, chart/name identifiers, or tokens.

## Rollback

1. Disable the KaosOrders publisher feature flag on Windows.
2. Hide/stop the kiosk if its state is uncertain; EMR and PACS remain available.
3. Retain current PACS behavior and manual `Poll Now`.
4. Disable new KaosOrders operations independently from the verified shared
   reader and PACS trigger path.
5. Restore the prior KaosOrders image/config and purge its disposable projection
   only through a supported maintenance path.

Rollback must not write to eGHIS, delete PACS worklist data, or modify production
database settings.

## Unresolved decisions

- production privilege/session verification procedure and evidence;
- registered operation set and stuck-driver recovery mechanism;
- real encounter/order keys and complete-read criteria;
- completed-order detail allowlist and endpoint shape;
- clinic-day boundary, purge grace, and stale thresholds;
- unattended kiosk viewer-token provisioning;
- Acer resolution/scaling and calibrated tile minimum width; and
- whether future evidence ever justifies a separate EMR broker process.
