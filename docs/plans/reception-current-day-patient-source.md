# Reception current-day patient source

- Status: **accepted logical contract aligned; production reader remains blocked**
- Last updated: **2026-10-07**
- Owning project: **KaosEghis**
- Affected projects: **KaosEghis, KaosReception, orchestration**

## Context and decision

The 2026-10-07 product decision changes Reception's `금일 환자 목록` from any
order-derived interpretation to an encounter-status projection. Include only
today's encounters whose exact state is `진료완료` or `수납완료`. Exclude
`진료대기`, `보류`, cancellation, and every unknown state. Reception selects one
entry for a revisit notice. Patient name exists only for immediate display/print;
it must not be persisted, logged, retained as history, or used as identity.

The original Orders-oriented plan carried parent/order facts and five included
states. This Reception plan is independent: it has no order join, child rows,
category, order state, chart number, demographics, transport, or persistence.

## Source evidence and exact mapping

Existing reviewed evidence supports this narrow mapping:

| Eghis source | Provider meaning | Rule |
| --- | --- | --- |
| `public.h1opdin.clinic_ymd` | clinic-local day | Must equal the current `Asia/Seoul` date. |
| `public.h1opdin.recept_no` | `selection_id` | Current encounter identity only. |
| `public.h1opdin.proc_gb = '10'` | 진료대기 | Excluded. |
| `public.h1opdin.proc_gb = '25'` | 보류 | Excluded. |
| `public.h1opdin.proc_gb = '30'` | 진료완료 | Included as `CONSULTATION_COMPLETED`. |
| `public.h1opdin.proc_gb = '40'` | 수납완료 | Included as `PAYMENT_COMPLETED`. |
| every other/null/blank status | unknown/unapproved | Excluded; never coerced to completed. |
| `h1opdin.ptnt_no = hz_mst_ptnt.ptnt_no` | patient-master join | Internal only; never leaves the provider. |
| `hz_mst_ptnt.ptnt_nm` | `display_name` | Display/print-time only; no identity, storage, log, or history use. |

The code meanings are backed by supervised UI/source comparisons and the
operator-confirmed code-30/code-40 terminology in `docs/kaosorders.md`. Existing
`core/weekly_age_reporting.py` already uses the exact `clinic_ymd` plus 30/40
scope, and the patient-context reader establishes the patient-master name field.
This evidence is enough for the pure mapping boundary, not for enabling a new
production query.

## Implemented boundary

`KaosEghis/core/reception_current_day_patients.py` defines an immutable,
redacted provider protocol and a synthetic-only projection. It requires:

- source ID `kaoseghis-reception-day-v1` and projection ID
  `reception-current-day-patients-v1`;
- an aware observation time and a positive freshness limit no greater than the
  accepted 300-second maximum;
- current `Asia/Seoul` clinic-day equality for both scope and observation;
- a complete, whole-day, untruncated, consistent read with the connection closed;
- exact source aliases and a maximum of 10,000 detached rows;
- exact-duplicate collapse, conflicting-duplicate rejection, and deterministic
  `selection_id` ordering;
- only codes 30 and 40 in output; every other state is excluded;
- fixed/redacted errors and no database, network, file, runtime, log, or UI I/O.

The pure boundary requires an explicit `freshness_limit`; callers may choose a
stricter value but values over 300 seconds are rejected. A stale/future/wrong-day/
incomplete read produces no list. Reception must treat that as unavailable and
must not retain an older name/list.

## Dependencies, impact, and safety constraints

The accepted central contract is
`/srv/projects/KaosClinic/orchestration/contracts/reception-current-day-patients-v1.md`.
It freezes the provider/projection IDs, source mapping revision, 300-second
freshness ceiling, complete-read and unavailable behavior, ephemeral selection
and print lifecycle, and the prohibition on name persistence/logging/history.

A separate Eghis source-reader review must approve one parameterized, bounded,
read-only day query through the existing serialized reader and credential path.
It must prove unique encounter membership, patient-name join cardinality, complete
zero-row authority, row bounds, snapshot consistency, cleanup, and no output of
chart number or other patient data. No SQL reader, publisher, endpoint, UI,
trigger, persistence, or deployment is authorized by this change.

## Evidence and validation

- Existing source evidence: `docs/kaosorders.md`, especially the supervised
  status comparisons and operator-confirmed 30/40 meanings.
- Existing field use: `KaosEghis/core/weekly_age_reporting.py` and
  `KaosEghis/core/kaospacs_patient_context.py`.
- New synthetic tests cover literal mappings, clinic-time boundary, freshness,
  completeness, unknown-state exclusion, deduplication, deterministic ordering,
  redaction, closed fields, and absence of I/O imports.

## Open questions and next action

1. Eghis may propose the bounded production query and synthetic DB tests;
   no live read is implied or approved.
2. Transport/runtime work remains blocked on the production gates in the
   accepted central contract and separate authorization.

## Revision history

- **2026-10-07:** Recorded the status-based product decision and implemented the
  pure synthetic provider/projection boundary. Identified the central contract
  and production-reader gates; no live source or Reception runtime was touched.
- **2026-10-07:** Aligned the provider source ID and fixed 300-second freshness
  ceiling with the accepted central contract and Reception consumer.
