# Current-Day Complete-Order Source Gate Review

Reviewed: 2026-10-10. **Documentation and existing mocked-test review only.**

## Exact Scope and Authorization

Sender started clean on `main` at
`d5f75e0f8c4eeb1cc17fbe6b52bd1f578da6903a`, with origin
`https://github.com/zinsss/KaosEghis.git`. The receiver-reviewed sender
`b40e48ed7dbed3c0a5d00ed0a653c45f2ff0c8cb` is its predecessor. The newer
commit fixes isolated Windows Qt test setup/cleanup, not production source facts.

Receiver `d6316753151f2cbcda36f1e9ea7a7b049ca22b43` was reviewed in a clean
temporary detached checkout of `https://github.com/zinsss/KaosOrders.git`.
Its complete-order model and separate volatile session are already implemented
synthetically. Its documentation reports 339 shared model cases, 54 focused
session tests and 860 full-suite passes with 2 skips. Those are receiver-reported
results, not tests rerun by this review. No parity implementation is repeated.

There is **no explicit closed-hours live-read approval for this session**. No EMR
connection, UI capture, patient/order export, live probe, credential lookup,
service restart or deployment was performed. Earlier read-only approvals are not
carried forward as approval for a new operation. Historical observations below
remain dated evidence, not new findings about today's clinic or permissions.

No code, SQL, fixture, hash, validator, mapping, runtime setting or trigger changes
are part of this milestone. `EghisSourceDayReader` still returns `UNAVAILABLE`.
Production mapping revision remains **unassigned and unapproved**.

## Status Meaning and Gate Crosswalk

`VERIFIED` requires direct, approved evidence for the entire stated gate.
`PARTIAL` means useful bounded observations exist but do not authorize production.
`UNRESOLVED` means the required operational decision/evidence is absent.
`BLOCKED` identifies a concrete obstacle. No entire production gate is VERIFIED.

The eight rows below use the current complete-order request's numbering. In the
[historical matrix](kaoseghis-source-evidence-gates.md#eight-gates), gates 4 and 5
are combined here as gate 4; old gate 6 plus text coverage becomes gate 5; numeric
facts are now their own gate 6; demographics and privilege remain gates 7 and 8.
Historical numbers/results are not silently reinterpreted.

| Gate | Status | Approved historical evidence / sanitized finding | Missing evidence and activation effect | Next controlled procedure |
| --- | --- | --- | --- | --- |
| 1. Current-day membership | PARTIAL | Parent-driven `h1opdin.clinic_ymd` candidate, KST date guard and no-order preservation. The approved 2026-10-07 read observed 269 candidate parents, including 7 without children. Earlier operator counts agreed with a bounded reception aggregate. | Authoritative clinic partition/date predicate and full non-cancelled parent set are not established. The existing diagnostic retains all source states; it is not the proposed cancellation-filtered Orders scope. Unknown state cannot be silently omitted. | Review already obtained structure metadata and operator-confirmed current-day counts. Any new aggregate needs exact SQL/column/output review and closed-hours approval. Verify no-order inclusion and cancellation/restoration exclusion without historical/date-moving tests. |
| 2. Parent/child consistency | PARTIAL | The 2026-10-07 statement returned 1,025 linked orders in 1,032 parent-driven result rows. Counts, four-part uniqueness, links and repeated statement metadata passed. Prior same-day linked-order crosschecks had no observed anomalies. Cursor/physical close preceded interpretation. | Single-statement consistency does not prove the statement cannot land between separate EMR save commits. Alternate relevant storage and all-child scope remain unproven. A read-only snapshot transaction cannot by itself certify a multi-transaction clinical save. | Seek an evidenced save-completion/transaction boundary and exhaustive current-day child provenance. A controlled experiment can disprove atomicity but matching reads cannot prove it. Stop if no defensible boundary is available; do not relax FULL/complete. |
| 3. Verified-empty authority | PARTIAL | An operator-confirmed closed day previously returned zero candidate parents/orders with verified cleanup. Mocks distinguish candidate zero from failed/partial reads. | That dated observation is not a complete-source certificate or an observation of today's empty clinic. Depends on gates 1/2, access and current-day verification. No new empty day was observed. | On a separately approved, operator-confirmed empty current KST day, run only the reviewed complete aggregate with source/date/access/completeness checks. If the day is populated or approval absent, leave open; do not move dates or fabricate an empty snapshot. |
| 4. Reception state and retained qualifiers | PARTIAL | Supervised waiting/in-progress/hold and completion/payment/cancellation/restoration observations cover candidate codes 10/20/25/30/40/50. Consultation completion and payment completion were distinguished. | Full `proc_gb`/`hold_yn` truth table, transients, unknown/null/blank cases and reliable state interpretation without `hold_opd` remain unproven. The six enums do not constitute a production mapping. | Review only missing retained-flag/state combinations against operator-confirmed normal workflows. Return allowlisted code/flag counts and fixed unknown buckets, not identities. If retained facts are ambiguous, remain blocked; never retrieve the excluded field to resolve ambiguity. |
| 5. All-category lifecycle and text | PARTIAL | Sample edits, disappearance, key reuse, parent cancellation/restoration and active children under cancelled parents were observed. One custom order's user code/name matched the UI while its catalog fields were empty/NULL. | Coverage of every supported category/path, exact text provenance/content safety and child-state interpretation are incomplete. A source name can contain sensitive content despite passing length/Unicode checks. | Maintain a category/path coverage matrix using operator-entered disposable examples and aggregate equality/shape results only. Cover additions, same-key edits/reuse, cancellation, disappearance and restoration without collecting raw text. No fallback/trim/translation/normalization or code-based identity. |
| 6. Numeric facts | PARTIAL | One approved grid comparison matched `qty`/`divide`/`days` to the three requested columns; metadata says `numeric`. In the 1,025-order sample all three were finite exact Decimals and none were NULL. | All-category correspondence, NULL/domain/sign/precision/scale and clinical units are not established. No observed extrema or 18-integer/12-scale production approval exists. | Prepare a separately reviewed bounded aggregate grouped only by approved category codes: null counts, negative/zero/positive counts, precision/scale ranges and exact correspondence booleans. Mock before approval. Do not return numeric rows, round, coerce floats, multiply fields or infer units. |
| 7. Privacy-minimal encounter facts | UNRESOLVED | Prior policy accepted exact M/F/SQL NULL and completed-years age on encounter date; sampled M/F is limited evidence. Current complete-order parent contains only identity/state. | No complete versioned demographic boundary or safe age source is approved. Prior v1/v2 models do not establish current-day provenance, NULL/unknown display or field bounds. Final board composition is blocked. | Review the separate proposed boundary below, then source metadata/aggregate domain evidence and a safe derived-age method. No DOB/resident-number retrieval or patient-field values are authorized by this review. |
| 8. Least privilege and operational safety | BLOCKED | Shared FIFO/machine-wide mutex, verified read-only mode and physical closure are implemented and mock-tested. Earlier source-table write capabilities were absent, but effective CREATE in `public` was observed. | A dedicated least-privilege identity is not certified. Other effective privilege/function paths and repeated clinical-hours load remain open. A fast one-shot read cannot certify operating safety. | Administrator reviews effective grants/role inheritance/PUBLIC, ownership, RLS/bypass and callable functions, without write tests or automatic grant changes. Recheck only approved metadata after explicit authorization. Plan a separately approved operating-load study; no clinical-hours reads are authorized now. |

The source DB remains the durable truth. This does not make an incomplete query
authoritative. No-order parents are legitimate, including the operator's reported
vaccination workflow; do not infer a flu order from their emptiness or require
broader source access solely because no-order rows exist.

## Candidate Field Evidence

This ledger identifies already documented candidates, not approved production
SELECT columns. The [query draft](kaoseghis-current-day-orders-query.md) is unchanged.

| Target fact | Candidate evidence | Outstanding mapping decision |
| --- | --- | --- |
| Encounter identity/day | `h1opdin.recept_no`, `clinic_ymd` | Authoritative scope, clinic partition, immutable representation and lifetime/reuse limits |
| Four-part child identity | `h2opd_doct_ord.recept_no`, `ord_ymd`, `ord_no`, `ord_seq_no` | Complete relation coverage, date policy and exact native numeric-key-to-text convention; never key by name/code |
| Catalog code/name | `ord_cd`, `medfee_nm` | Independent nullable exact facts; one custom case had empty/NULL values; all-category provenance/content safety open |
| User code/name | `user_cd`, `user_nm` | One exact UI match supports location only; NULL/blank/padding/length/category coverage open |
| Order type/department | `ord_type`, `proc_dept_cd` | Independent nullable exact facts; full domain/provenance and unknown-code handling open |
| Reception state/retained source flag | `proc_gb`, `hold_yn` | Full state truth table without excluded qualifier; no column-name inference |
| Order state/retained flags | `dc_yn`, `act_yn` | Strict Y/N are facts, not proof of administration, collection, imaging, payment or completion; state mapping needs separate evidence |
| Daily quantity/frequency/day count | `qty`, `divide`, `days` | Independent nullable exact Decimals; preserve sign/digits/exponent, scale and signed zero; all-category mapping and bounds open |

Future collection scope is today's verified non-cancelled parents, including
no-order parents, plus **every child** of included parents: active, cancelled,
fee and unclassified rows. A verified cancelled parent and its children are omitted;
restoration can reinclude them. Unknown state invalidates the read rather than
becoming cancellation or active state. A same-key fact difference replaces the
whole fact; disappearance/reappearance does not prove a cancellation/restoration
event. An off-day child is not silently removed or assigned a different date.

`hold_opd` remains excluded: do not retrieve, output, hash, mask, measure or infer
its content, length or shape. Its absence from a model is not evidence that the
state mapper is independent of it. `hold_yn` remains a retained source-evidence
fact, but this review does not add it to the existing minimal synthetic parent.

## Encounter Boundary Decision

**Recommend a separately versioned privacy-minimal encounter fact contract**, not
an implicit join with normalized-source v2 and not an in-place widening of the
existing complete-order parent. A non-binding discussion identity is
`kaosorders.current-day-encounters` version 1; its projection/mapping and wire
inventory remain unassigned. Receiver review is required before any implementation.

| Proposed field | Purpose and proposed policy | Source/evidence status |
| --- | --- | --- |
| `encounter_id` | Exact visit linkage, same representation as complete-order parent; required, not chart number | Candidate reception key already observed; authoritative scope and representation still gated |
| `state` | The same verified normalized state as the order parent; discrepancies reject composition | Six synthetic states agreed; production truth table still gated |
| `chart_number` | Operator-visible patient reference; preserve text/leading zeros, never use as visit identity | No source column/join is approved by this review; reject missing/blank pending explicit policy, do not fabricate |
| `patient_name` | Minimum operator-visible name, exact text with separately reviewed privacy/length bounds | No production mapping or universal content/bounds approval; no fallback or default name |
| `sex` | Exact M/F or true SQL NULL under the previously approved convention | Blank/unknown/other codes do not become NULL or O; source-domain and receiver NULL-display policy remain open |
| `age_years` | Independently derived completed years at encounter clinic date; integer or explicitly approved missing value | Safe derivation/source and missing/invalid/range policy unverified; never substitute zero or infer from sex/chart/other data |

No additional visible insurance/billing data is needed. Observation metadata,
clinic day, source identity and future mapping provenance belong to the shared
scope, not repeated patient details; observation time is not an edit/cancel time.
Exact NULL/blank/content bounds need an explicit synthetic design decision before
a new model; old v2 acceptance of other sex/age values is not authority.

The proposed encounter and order facts must be produced from the **same approved
whole-day observation** and atomically validated/applied together under the same
current day, source, session and generation. Require equal retained parent sets
and states, unique encounter facts and no orphans; no independent delivery/cache
join that can mix observations. The eventual envelope or composition identity is
a future version decision, not a wire shape created here. A failure on either side
preserves the entire last valid same-day projection. Restart/midnight still discard
it. Patient/order state remains RAM-only.

Preferred age path: review an already available, permitted source-side derived-age
view/function that returns only completed years, never DOB. None is known/approved
here; do not create a database function or grant access as part of this work. Test
birthday boundaries, leap-day policy, invalid/future dates, missing values and
KST date handling using invented data before proposing access. The calendar and
range policies must be explicit, not guessed. If no safe source exists, retain the
age blocker and ask whether to defer age or separately authorize a minimal
derivation design. This review does **not** authorize fetching DOB even transiently.

Names/chart references are needed only in a future approved board fact boundary,
never in evidence reports, fixtures, exceptions or logs. There is no current
demographic query or mapping implementation.

## Required Approval Sequence

No new live operation is proposed for immediate execution. Work can continue with
offline review/mock design without permission to connect. Vendor definitions are
not expected; do not make repeated vendor requests a prerequisite or replace
missing authority with guesswork.

1. Administrator reviews the known privilege blocker independently. No automatic
   role/grant change, write attempt or EMR restart. A later metadata-only recheck
   needs its own approval; no credentials/role dumps in its report.
2. Select **one** missing gate subquestion, preferably membership/save authority.
   Inventory previous observations so the already demonstrated state transitions
   are not simply repeated. If evidence cannot establish FULL authority, stop
   that path and record the blocker, not more unbounded reads.
3. Before any live read, provide the exact parameterized statement/procedure,
   every referenced source column, fixed output allowlist, source/result caps,
   timeout and cleanup checks, one targeted gate and remaining limitations.
   Use aggregates only; never select patient/order identities or raw text/numerics
   into the returned result. Date parameters are bound privately, not logged.
4. Add/run mocked tests for that exact operation before requesting approval.
   Require explicit operator confirmation of closed/holiday hours and current KST
   date for that operation. Do not bundle approval for multiple probes. Existing
   historical full-row diagnostic permission is not permission to rerun it under
   this aggregate-only request.
5. Preserve one shared FIFO and `Global\KaosEghis-EMR-read` ownership through
   physical close. Proposed evidence defaults remain connect 3 s / statement 2 s,
   verified read-only mode, fixed reviewed caps plus overflow sentinel and no
   automatic retry. Any differing cap/session transaction needs separate review.
6. Fully fetch the bounded result, verify cursor and physical connection closure,
   then validate/compare/normalize. Failed or uncertain cleanup yields no findings;
   uncertain physical close latches the reader unhealthy. No second diagnostic
   connection while ownership is uncertain. Output fixed failure reasons only.
7. Record only approved counts/enums/null booleans/consistency, non-identifying
   lengths or numeric domain ranges and timings. Never output excluded-field
   shape, identifiers, provider errors, SQL parameters or raw rows. Record live
   connection closure separately from mocked cleanup results.

The later numeric aggregate should use exact database numeric operations for
range/scale summaries only, not convert individual values to floats or infer
units. Unknown type/department/flag values must use fixed unknown buckets or
reject; do not echo arbitrary source text. New probes remain explicitly invoked,
disabled by default and disconnected from runtime.

## Mapping Revision Release Checklist

Do not assign even a provisional production mapping revision until all are met:

1. Approved authoritative current-KST-day, clinic-specific non-cancelled parent
   membership, no-order inclusion and restoration behavior (gate 1).
2. Exhaustive linked child sources, four-part identity/representation, overflow
   rejection and evidenced consistent save/read boundary (gate 2).
3. Direct approved current-day empty observation with access/date/completeness
   authority, distinct from every failure path (gate 3).
4. Reviewed six-state and retained-qualifier truth tables, including unknown cases
   and reliable interpretation without the excluded qualifier (gate 4).
5. All supported category/lifecycle coverage and safe exact provenance for the
   four text facts, type/department and child state; no fallback (gate 5).
6. All-category numeric correspondence, NULL/sign/precision/scale domains and
   separately approved bounds, with exact tuple preservation (gate 6).
7. Agreed versioned minimal encounter boundary, approved field joins/content,
   sex/NULL policy and safe completed-years derivation or explicit age deferral
   that changes the proposed requirement by agreement (gate 7).
8. Certified least-privilege reader identity, effective permission review, bounded
   closure/failure behavior and separately approved repeated-load limits (gate 8).

Bind the eventual mapping review to schema/source versions, exact reviewed query
revision, field provenance, caps and supported category/state domains. A source
schema/domain change invalidates the approval until reviewed. These are future
release criteria, not implemented metadata or an allocated revision.

## Verification Record

Only existing synthetic/mocked tests are run for this documentation milestone.
`tests/conftest.py` blocks external network/real database access and native UI
input, isolates the Windows mutex and application data, and supplies offscreen Qt
fonts. No test may acquire the production mutex or use clinic credentials.

Existing coverage reviewed includes:

- current-day counts/candidate/full-field mocks: approval/date checks, sentinel
  overflow, partial/malformed results, strict flags and candidate-zero rejection;
- aggregate evidence/v2 boundary mocks: no report can confer source authority or
  unblock `EghisSourceDayReader`, even when candidate counts are zero;
- metadata mocks: permission denial, timeout, fixed redacted errors and no retry;
- source/ledger mocks: unknown mappings, failed reads preserve baseline, no inferred
  cancellation and interpretation after physical close; and
- shared-reader mocks: FIFO across consumers, machine-wide semantics with isolated
  test mutexes, cursor failure cleanup and physical-close uncertainty safety latch.

| Run in this milestone | Result |
| --- | --- |
| Eleven focused evidence/source/shared-reader test modules | 1,148 passed in 40.38 s |
| PACS modules, flu-report diagnostics, vaccine patient context and runtime database contention | 193 passed in 41.06 s |
| Relative document link targets and `git diff --check` | Passed |
| Live EMR operations / actual connection-closure observations | None; not approved or performed in this session |

Focused command: `python -m pytest -q` with
`tests/test_source_current_day_counts.py`,
`tests/test_source_current_day_orders_candidate.py`,
`tests/test_source_current_day_read.py`, `tests/test_source_order_coverage.py`,
`tests/test_source_order_grid_numeric.py`, `tests/test_source_order_display.py`,
`tests/test_source_metadata_followup.py`, `tests/test_source_evidence_inspection.py`,
`tests/test_source_evidence_v2_boundary.py`, `tests/test_emr_source.py` and
`tests/test_emr_read_queue.py`.

Broader command: `python -m pytest -q` with all `tests/test_*pacs*.py` files,
`tests/test_flu_report_diagnostics.py`, `tests/test_vaccine_patient_context.py`
and `tests/test_runtime_database_contention.py` (wildcard expanded in PowerShell).
Both runs used `QT_QPA_PLATFORM=offscreen`, `__COMPAT_LAYER=RunAsInvoker` and a
separate temporary `KAOSEGHIS_DATA_DIR`.

No new failure harness or parity suite is needed: these cases already exist. No
source-evidence gate is closed by a passing mock. The full 5,002-test suite was
not repeated for this documentation-only change; its prior all-pass result at
the unchanged-code starting commit is recorded in
[Windows offscreen UI tests](windows-offscreen-ui-tests.md#verification-2026-10-10).
The earlier 26 UI failures were fixed by that preceding test-environment commit,
not hidden, ignored or repaired in this evidence review.

The scoped diff contains five Markdown documents only. Added content was reviewed
for patient/order identifiers, names, source values, DOB/resident number, clinical
text, credentials, SQL parameters and excluded-field content/shape: none was added.
Only historical aggregate observations, allowlisted state/flag codes, source column
names, timing and repository references are recorded. Existing code/tests/fixtures
and running behavior are unchanged. Final commit and remote HEAD are reported in
the completion message rather than a self-referential commit field here.

## Exact Next KaosOrders Handoff

Continue **design/documentation only**, using receiver
`d6316753151f2cbcda36f1e9ea7a7b049ca22b43` and the sender commit containing this
review. Do not repeat the completed model/parity/session implementations.

1. Review this gate matrix: gates 1-6 PARTIAL, gate 7 UNRESOLVED, gate 8 BLOCKED.
   No current-session live operation occurred. Production mapping is unassigned;
   the source reader remains UNAVAILABLE.
2. Accept or counterpropose the separate minimal encounter-fact boundary, explicit
   NULL/unknown/age policy and atomic same-observation composition with orders.
   Do not join v2 or change existing models/fixtures/hashes. No wire inventory is
   frozen by this sender proposal.
3. Prepare a **conditional** session wire/auth decision checklist only: authenticated
   clinic/source/day/generation binding, fresh receiver session after restart,
   current-day fencing, request bounds, exact Decimal/text representation, content-
   bound acknowledgements, volatile retries and failure/staleness behavior.
   Existing synthetic session equality has no approved wire digest. Do not infer
   an encoding from Python object equality or reuse durable epoch/revision rules.
4. Preserve the receiver plan's gate order: source authority and the new encounter
   boundary must pass before approving a concrete wire contract or implementing
   transport. Decide options now only as unresolved proposals, not endpoint/token
   specifications, parser/serializer code or canonical fixtures.
5. Include controls for logs, caches, browser stores, crash dumps, swap and
   hibernation. Memory-only application state is not proof of zero OS/browser
   persistence. No rollout configuration is changed in this stage.

No source queries, runtime hooks, HTTP/token, publisher/retry worker, persistence,
board/PACS changes, deployment or restart. KaosOrders never connects to EMR;
KaosPACS remains an independent sibling consumer. Neither normalized-source nor
complete-order data may be sent to `/api/v1/order-snapshots`.
