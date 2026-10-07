# Current-Day Full-Field Read Experiment

Prepared 2026-10-07 from sender `37cc889409395a5f4feeecbfc4c03631a8c45a57`.
Operator request: perform the next one-shot current-day reception/order read,
not enable polling. No screen actions or patient/order output.

## Reviewed Operation

Exact statement: `tests/fixtures/source_current_day_orders_read_probe_v1.sql`.
UTF-8/LF SHA-256:
`82e942bfbdf68e751c0bbe86528b8130f5dab50f727506a7d97aab55f619702e`.
Test-only harness: `tests/source_current_day_read.py`; no runtime importer or CLI.

This is a separate diagnostic copy of the offline candidate statement. The
original draft SQL and all existing normalized-source fixtures/hashes are unchanged.
The copy adds server-side 128-character diagnostic bounds on reception code and
numeric text representations before returning source data. Those bounds limit this
experiment's content size; they are not an approved clinical numeric domain/scale.
The query never substitutes defaults, rounds, multiplies or assigns units.

Exhaustive source column allowlist:

- `public.h1opdin`: `clinic_ymd`, `recept_no`, `proc_gb`, `hold_yn`.
- `public.h2opd_doct_ord`: `recept_no`, `ord_ymd`, `ord_no`, `ord_seq_no`,
  `ord_cd`, `medfee_nm`, `user_cd`, `user_nm`, `qty`, `divide`, `days`,
  `ord_type`, `proc_dept_cd`, `dc_yn`, `act_yn`.

Only bound parameters: today's KST `day`, `encounter_cap=1000`, `order_cap=10000`.
One CTE SELECT uses one READ COMMITTED statement snapshot. Parents drive the LEFT
JOIN so no-order receptions remain present. All linked children remain included;
no billing, fee, category, cancellation or reception-state filter is applied. The
candidate reception count is NOT necessarily unique patients or active visits.
No patient master, chart number, name, resident ID, DOB, phone, address, diagnosis,
notes, insurance, excluded qualifier, credentials or source definitions are selected.

Identifiers and order fields are fetched transiently for linkage/content checks,
then discarded. They are not printed, serialized, logged, stored or delivered by
the helper. An allowlisted order-text column is not an all-category content-safety
approval. No text classifier or patient-data export is added.

## Bounds And Closure

- Explicit operator approval and current KST day before queue admission, again
  inside the FIFO before connection creation, after closure and after validation.
  SQL independently guards the server's current KST day at statement start.
- Shared `run_serialized_read` FIFO and machine-wide Windows mutex unchanged.
- Connect timeout 3 s; verified session `readonly=True`, autocommit, READ COMMITTED;
  statement timeout 2 s, checked through session settings before the source SELECT.
- Caps plus one on both source scopes; structural SQL failures return metadata
  only, never an apparently successful truncated data set.
- At most 11,001 fetched result rows: 11,000 valid-row ceiling plus a rejection
  sentinel. This is not the old 257-row aggregate helper. Driver rowcount, fetched
  count and SQL expected result count must agree.
- Server field-length guards cover all variable-length selected fields. Client
  rejects unreviewed text, non-finite/float numbers, over-bound exact decimals and
  unexpected column/row types after verified physical closure.
- Cursor and physical connection both closed and verified before count/link/key
  checks, normalization-like inspection or aggregate reporting. Uncertain physical
  closure poisons the shared reader and retains mutex ownership as before.
- No retries, EXPLAIN ANALYZE, writes, write-permission test, second source query,
  historical read, UIA inspection, app restart or deployment.

After close, the validator checks repeated metadata/parent agreement, all counts,
all no-order rows, native four-part key uniqueness and child/parent links. It does
not normalize identities/states or generate a source snapshot. Unknown reception
codes stay opaque; retained Y/N flags receive no new meaning. NULL order names and
numbers are counted, not replaced. The transient detached-row container has a
redacted repr and is cleared after validation or rejection.

## Output Allowlist

Fixed status, `authoritative_snapshot=false`, closure booleans and:

- Candidate reception, order, no-order reception, with-order reception and returned
  row counts; NULL counts for requested name/number columns only.
- Structural consistency, unique-key and parent-link booleans on success only.
- Queue wait, connection setup, execute, fetch, cleanup, connection lifecycle,
  post-close validation, total probe wall time and helper-process CPU time.

Execute timing includes client/driver/server round-trip and normal client-cursor
buffering; it is NOT isolated server execution time. Client CPU is NOT database
server CPU/load. No memory/network byte total or buffer/I/O metric is claimed.
This one-shot observation does not establish repeated-poll impact or concurrency
under normal clinical load.

## Verification And Status

Before any live operation, focused SQL/harness tests passed: **225 tests in 1.59 s**.
They use mocked PostgreSQL connections, isolated test mutexes, blocked external
network and synthetic in-memory relational tables. They cover failed reads,
timeouts, mode/cleanup failure, partial/overflow data, midnight, no-order rows,
four-part keys, cancellation flags, exact numeric/null behavior and fixed errors.

The shared-boundary group also passed **433 tests in 3.57 s** before live access.

Final verification after recording the observation and adding an additional
reception-code bound test: **434 focused/shared-boundary tests in 3.51 s** and
**2,832 broader isolated source/shadow/serializer/outbox/shared-reader, PACS, flu
and patient-context tests in 47.90 s**. One existing pywinauto COM threading warning
remains. The unrelated full UI suite and its known failures were not modified or
rerun. `git diff --check` passed. No existing runtime code or source-wire fixtures
changed; the added query/harness/tests are under `tests/` only.

## Approved Observation

On 2026-10-07 KST, the operator's "go" approved the described one-shot read. The
bounded statement ran once after its exact SQL, column/output allowlists, bounds
and mocked failure tests were reviewed. No UAC or EMR screen manipulation was
needed for this database-only operation. No other source statement or plan query
was run during this experiment.

Result: `populated_candidate_observed`, `authoritative_snapshot=false`.

| Aggregate | Observed |
| --- | ---: |
| Candidate reception records (not cancellation-filtered) | 269 |
| Receptions with linked orders | 262 |
| Receptions without linked orders | 7 |
| Linked orders | 1,025 |
| Returned joined rows | 1,032 |
| NULL requested prescription names | 0 |
| NULL qty / divide / days | 0 / 0 / 0 |

All 1,025 order rows passed the exact-Decimal checks on the three numeric fields.
The returned row total agrees with 1,025 orders plus 7 no-order rows. Repeated
parent metadata agreed; native four-part order keys were unique; every returned
child linked to its scoped parent; no-order parents were preserved. No clipping,
duplicate-key or link/count inconsistency was observed in this statement's scope.
This is not proof that unqueried storage cannot contain additional records.

Session read-only verification, cursor closure and physical connection closure
were all **true**. Source rows were processed only after physical close and were
then discarded. No source values, identifiers, raw rows or payloads were printed,
written to evidence reports or committed.

| Timing | Milliseconds |
| --- | ---: |
| Queue/worker/mutex wait | 47.440 |
| Connection and session setup | 47.647 |
| Execute round-trip (includes normal driver buffering) | 22.830 |
| Fetch/decode | 3.737 |
| Cursor and physical connection cleanup | 0.247 |
| Entire connection lifecycle | 74.467 |
| Validation after close | 24.230 |
| Entire probe wall time | 146.837 |
| Helper-process CPU time | 93.750 |

Timings describe one fresh helper process on this populated day. Queue timing
includes worker/native mutex setup, not necessarily contention. Client CPU time
is coarse Windows process accounting, not server CPU or EMR load. The read was
short in this observation; no claim of zero load or general performance under
repeated/concurrent clinical activity is made. No buffer/I/O, server CPU, memory
or transfer-byte measurement was performed. The existing aggregate EXPLAIN result
must not be presented as an execution plan for this different full-field query.

## Full-Snapshot Polling Recommendation

Documentation-only recommendation recorded on 2026-10-07 from the observation
above and the operator's question about a fresh full read on every poll. This is
not approval to enable the diagnostic as a production reader or schedule new reads.

The observed 74.467 ms connection lifecycle and 146.837 ms total probe time make
a fresh, bounded **whole-current-day read per refresh** a promising design at
this clinic's observed volume. Prefer this direction over limiting the read to
the departing chart or relying on unverified edit timestamps. Do not describe
server load as negligible: server CPU/I/O and repeated clinical-hours impact were
not measured. One closed-hours result is not a latency or capacity guarantee.

The requested detail fields have separate, limited evidence: the
[approved one-row grid comparison](kaoseghis-order-grid-numeric-evidence.md)
matched the screen code/name to `user_cd`/`user_nm`, and the displayed daily-amount,
frequency and days columns to `qty`/`divide`/`days`. All three numeric columns have
PostgreSQL `numeric` type. Preserve the independent exact values; do not multiply,
divide, infer units or generalize this sample to every order category. The full-day
diagnostic confirms exact-decimal readability in this sample, not universal display
semantics or approved null/domain/scale policy.

Proposed safeguards for a later, separately reviewed implementation:

- Keep one serialized source connection through the shared FIFO and machine-wide
  mutex. Close and verify cursor and physical connection before validation,
  comparison, normalization or any delivery. A queued request must not open a
  concurrent connection.
- Debounce chart clear/load/change events by 2 s. Coalesce bursts and redundant
  pending refresh requests rather than replay every event. Consider one necessary
  +30 s follow-up for delayed commits; a newer chart transition supersedes the old
  pending follow-up. Keep a 5-minute successful-read safety check and manual
  refresh fallback in the proposed policy. This changes no existing timer or PACS
  trigger, and neither delay proves EMR save completion.
- Build and validate the complete current-day candidate in memory before replacing
  accepted state. Failed, partial, timed-out, overflowed, inconsistent or unverified
  reads retain valid same-day state; zero candidate rows are not a verified empty
  day. Recheck the KST day before acceptance; midnight clears the prior-day state.
- Compare complete, validated facts to catch observed additions, same-key edits,
  disappearance, restoration, key reuse and reception-state changes. Compare all
  retained facts, not only the row count or chart number. This is state comparison,
  not an audit trail: transient changes between snapshots can be missed.
- A fresh full **read** need not cause redundant delivery or rendering when facts
  are unchanged and the receiver is known to hold matching valid current-day state
  in the active session/generation. Receiver restart, a changed session/generation,
  KST rollover or a fresh-snapshot request requires a fresh full snapshot regardless
  of the sender's previous comparison. Session, wire and acknowledgement decisions
  remain separate; do not reuse v2 epoch/revision ordering.
- Retain only current-day patient/order state in memory. Do not introduce a durable
  patient/order outbox, historical polling or receiver projection storage.

The measured diagnostic includes all candidate reception states, with no
cancellation filter. The future Orders projection still includes verified
non-cancelled encounters even without orders, and every scoped child including
cancelled, fee and unclassified rows. Excluding a verified cancelled encounter is
a separate scope decision, not evidence that this diagnostic already implements
the approved projection or that raw state codes are fully mapped.

Next performance evidence should be a separately approved, bounded clinical-hours
pilot after reviewing the source operation and remaining gates. Observe repeated
read/close latency, queue delay and EMR responsiveness with a stop condition for
timeouts or new slowdown. Any claim about server load requires separately reviewed
server measurements. No such pilot, additional live query, production scheduling,
serializer or delivery was performed for this documentation update.

Documentation-update verification: **531 focused tests passed in 3.80 s**, covering
the current-day probe/candidate, grid numeric comparison, shared read queue and
source-evidence inspection. Databases were mocked, mutexes isolated and external
network access blocked. `git diff --check` passed. The earlier broader result
above remains historical; the full suite was not rerun for this docs-only change.

## Remaining Boundaries

Single-statement consistency is not proof that an EMR save spanning multiple
transactions has finished. This does not prove alternative storage absent or
authoritative current-day membership. Zero candidate rows are explicitly
`zero_candidate_not_verified_empty`; failure/partial/timeout never clears any
same-day projection. No complete production evidence gate is resolved here.

`EghisSourceDayReader` remains UNAVAILABLE. No application/runtime/configuration,
trigger, adapter, v1/v2 model/fixture/hash, serializer, outbox, transport, board or
PACS change. Nothing is sent to `/api/v1/order-snapshots` or any receiver.
