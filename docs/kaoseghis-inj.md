# KaosEghis-inj

Last updated: 2026-07-15

## Purpose

`KaosEghis-inj` is the future injection-order workflow for KaosEghis.

Its role is to:

- read injection orders from eGHIS in read-only mode
- detect new, changed, and cancelled injection worklist entries
- own the authoritative injection worklist on the KaosEghis side
- notify a Raspberry Pi device to reload the latest worklist

It is not responsible for:

- writing back into eGHIS
- letting the Raspberry Pi own or edit worklist state
- storing long-term worklist state on the Raspberry Pi

## Ownership Boundary

### KaosEghis-inj owns

- eGHIS DB read-only polling
- injection order filtering
- authoritative local INJ worklist
- add / update / cancel / restore logic
- outbound signal to Raspberry Pi when worklist changes
- future operator UI for INJ worklist review

### Raspberry Pi side owns

- receiving a reload signal from KaosEghis-inj
- pulling the current worklist from KaosEghis-inj
- transient in-memory device-side handling
- device-specific display / printer / hardware behavior

### Raspberry Pi side does not own

- source-of-truth worklist state
- eGHIS DB access
- order classification logic
- durable PHI storage

## Current DB Findings

The eGHIS PostgreSQL data inspected so far supports this working interpretation:

- `ord_type = '07'` strongly matches injection-style orders
- `proc_dept_cd = 'INJ'` is the better routing signal for device workflow

Practical routing rule:

```sql
WHERE ord_type = '07'
  AND proc_dept_cd = 'INJ'
  AND COALESCE(dc_yn, 'N') <> 'Y'
```

The following real examples matched that pattern:

- `타마돌주사(트라마돌염산염)`
- `티램주(염산티로프라미드)`
- `페니라민주사(클로르페니라민말레산염)`
- `동광염산린코마이신주`
- `디페인주사(디클로페낙나트륨)`

`inject_path` is not reliable enough to be the primary filter on its own, because some clear injection rows have `inject_path = '02'` while others are blank.

## Read-Only eGHIS Data Sources

### Order source

Primary order table:

- `public.h2opd_doct_ord`

Useful fields:

- `recept_no`
- `ord_no`
- `ord_seq_no`
- `ord_cd`
- `medfee_nm`
- `ord_type`
- `proc_dept_cd`
- `dc_yn`

### Patient linkage

Read-only joins verified:

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

Recommended read-only join shape:

```sql
SELECT
    o.recept_no,
    o.ord_no,
    o.ord_seq_no,
    h.ptnt_no,
    p.ptnt_nm,
    COALESCE(h.sex, p.sex) AS sex,
    h.ageday,
    p.birth_ymd,
    o.ord_cd,
    o.medfee_nm
FROM public.h2opd_doct_ord o
JOIN public.h1opdin h
  ON h.recept_no = o.recept_no
LEFT JOIN public.hz_mst_ptnt p
  ON p.ptnt_no = h.ptnt_no
WHERE o.ord_type = '07'
  AND o.proc_dept_cd = 'INJ'
  AND COALESCE(o.dc_yn, 'N') <> 'Y'
```

## Privacy Model

### KaosEghis-inj local side

KaosEghis-inj may hold the authoritative worklist locally because it is the EMR-side adapter.

Even so, it should still minimize stored fields to the workflow minimum.

### Raspberry Pi side

The Raspberry Pi should not receive full worklist payloads in the signal itself.

Preferred model:

1. KaosEghis-inj updates its own worklist
2. KaosEghis-inj sends a minimal reload signal over HTTP
3. Raspberry Pi requests the current worklist from KaosEghis-inj
4. Raspberry Pi keeps that worklist in memory only

Do not store durable PHI on the Raspberry Pi unless a later design explicitly approves it.

## Network Model

### Signal path

KaosEghis-inj sends:

- `POST /api/reload-worklist` to the Raspberry Pi

This signal should contain no patient information.

Example:

```json
{
  "reason": "worklist_changed"
}
```

### Worklist fetch path

Raspberry Pi requests:

- `GET /api/inj-worklist` from KaosEghis-inj

KaosEghis-inj remains the source of truth.

## Why This Boundary Is Preferred

- KaosEghis-inj already has the eGHIS-side logic and permissions
- the Pi should not duplicate EMR classification logic
- retry and reconciliation stay centralized
- the reload signal itself is privacy-light
- the Pi remains replaceable and operationally simple

## Future Implementation Shape

Planned components:

- read-only eGHIS INJ poller
- local INJ worklist repository
- change detection and cancellation tracking
- KaosEghis-inj HTTP API for worklist fetch
- Pi notifier client from KaosEghis-inj
- operator UI for INJ worklist review

## Non-Goals

At this stage, KaosEghis-inj should not:

- write into eGHIS
- let the Raspberry Pi modify worklist state
- let the Raspberry Pi read PostgreSQL directly
- send full PHI inside the reload signal
- make the Raspberry Pi a second source of truth
