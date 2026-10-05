# Source Structure Probe: Approved Evidence

Prepared: 2026-10-05

Status: **approved one-shot catalog read completed; source authority unresolved**.
Operation ID: `source-structure-v1`. Executed once, with no retries or polling.
Prepared against sender `9d15c83ab0f8bc95440e922bc60a6b3bb1bb66cf` on clean
`main`; GitHub `main` matched. Receiver reference remains
`890a4dd4ce992f2598c85557513cd2c70b098a2b`, with no receiver changes.

The exact procedure and limits below were presented before execution. The operator
then clarified approval as "as long as read only". This run used that approval for
the single presented operation, not additional source discovery. The result is
recorded under [Approved Observation](#approved-observation).

## Single Evidence Question

For gate 1 (full-day membership/history boundaries), do the two known reception
and order objects have declared direct inheritance links, foreign keys or dependent
views that require further coverage review?

This may identify structural gaps; it cannot close gate 1 by itself. Zero links do
not prove absence of independent archive tables, application-managed relationships,
dynamic SQL, external storage or undocumented history. It does not determine state
semantics, save atomicity, least privilege or verified-empty-day authority. No
other source gate is being tested by this operation.

Previously sampled key identities are not queried again. No broad schema-name
search or recursive dependency walk is included.

## Exact Operation

The complete parameterized statement is
[`tests/fixtures/source_structure_v1.sql`](../tests/fixtures/source_structure_v1.sql).
That file, not a shortened example or generated variant, is the reviewed statement
for this operation. UTF-8/LF SHA-256:

`b4541a09068dc41c76f3d32a871d8f2fae4efdeae219c4135c8ad267a5adf1c2`

Exact bound parameters:

```json
{"schema":"public","reception_table":"h1opdin","order_table":"h2opd_doct_ord"}
```

The statement reads `pg_catalog` only. These parameters identify objects for
catalog lookup; neither clinical table is scanned. It selects no clinical source
columns, no row identifiers and no hold_opd value, shape or length.

The proposal harness is `tests/source_structure_proposal.py`. It has no database
driver, credentials, settings, CLI, default connection or runtime importer. A
separately approved one-shot caller must pass the existing
`core.eghis_db.run_verified_evidence_query` bound to the configured connection.
The harness never opens a connection itself; callback injection is not permission
to bypass that shared reader. No persistent live caller or runtime wiring is added.
An explicit `approved=True` is a caller assertion after operator approval, not
permission in itself. The harness verifies the pinned query digest before calling
the reader. A changed query requires a new review.

One approved operation consists of:

1. Acquire the shared FIFO slot and machine-wide `Global\KaosEghis-EMR-read` mutex.
2. Open one physical connection with a 3-second connection timeout and the existing
   evidence application name. No connection pool or second connection.
3. Set session `readonly=True`, `autocommit=True`, isolation `READ COMMITTED`.
4. Execute the existing session-local `SET statement_timeout = 2000`, then
   `SELECT current_setting('transaction_read_only'), current_setting('statement_timeout'), current_setting('transaction_isolation')`.
   Require exactly `on`, `2s`, `read committed` before catalog access.
5. Execute the exact catalog statement once with the three bound parameters.
   It is a single database statement, not multiple observations combined together.
6. Fetch the bounded aggregate report, close the cursor and physical connection,
   and verify their closed flags through the existing shared reader.
7. Only after closure, validate and emit the sanitized report. Do not print/store
   the SQL, parameters, provider exceptions, raw catalog rows or connection string.
   An uncertain physical close stops further reads; do not reset that safety latch.

No attempt is made to test read-only mode by writing. No grant, credential change,
server configuration, runtime setting, EMR UI action or application restart occurs.
The probe shares the normal reader slot and may briefly delay another queued read.

## Every Catalog Column

These are all fields used for selection, join, filtering or counting. OIDs remain
inside the database solely for metadata joins/deduplication; none are returned.

| Catalog | Columns |
| --- | --- |
| `pg_class` | `oid`, `relname`, `relnamespace`, `relkind` |
| `pg_namespace` | `oid`, `nspname` |
| `pg_inherits` | `inhrelid`, `inhparent` |
| `pg_constraint` | `oid`, `contype`, `conrelid`, `confrelid` |
| `pg_depend` | `refobjid`, `refclassid`, `classid`, `objid` |
| `pg_rewrite` | `oid`, `ev_class` |

The query compares catalog relation names to bound constants. It does not output
names of newly discovered tables, views, constraints or rules. It does not read
comments, expressions, view definitions, attribute values or clinical records.

The catalog design follows PostgreSQL's definitions of
[inheritance links](https://www.postgresql.org/docs/9.2/catalog-pg-inherits.html),
[foreign-key metadata](https://www.postgresql.org/docs/9.2/catalog-pg-constraint.html),
[dependencies](https://www.postgresql.org/docs/9.2/catalog-pg-depend.html) and
[rewrite relations](https://www.postgresql.org/docs/9.2/catalog-pg-rewrite.html).
Only catalog columns available in the referenced 9.2 definitions are used. This
does not certify the live server version or that the proposed statement executes
successfully there; mocked tests cannot prove that. Permission/schema errors stop
the operation with fixed reasons, without fallback queries.

## Output Allowlist and Caps

Only the following sanitized output may leave the one-shot caller:

- Fixed status code and `authoritative_snapshot=false`.
- Closure booleans (`connection_opened`, `readonly_verified`, `cursor_closed`,
  `connection_closed`) and elapsed connection-work seconds.
- Fixed object labels `receptions` and `orders`.
- Relation-kind tokens `r`, `p`, `v`, `m`, `f` only. An unrecognized kind rejects
  the result; no raw kind/name is printed.
- Integer total `relationship_count`, and per-object integer counts:
  `parent_links`, `child_links`, `outgoing_foreign_keys`, `incoming_foreign_keys`,
  `dependent_views`, `dependent_materialized_views`.

Counts describe catalog edges, not patients or clinical orders. View dependencies
are deduplicated per target/view before counting, so several referenced columns do
not inflate the view count. A relationship to both targets contributes to each
target; foreign-key counts count constraints, not distinct neighboring tables.

Caps:

- Exactly two matched relations required; SQL limit 3 is an overflow sentinel.
- At most 64 deduplicated scoped edges across both objects; SQL limit 65 rejects
  overflow, never silently truncates it into a successful report.
- Exactly 16 report rows expected: 2 summaries, 2 relation-kind rows and 12 metric
  rows. SQL limit 17 detects extra rows. The shared reader's fetch limit stays 257;
  the stricter proposal validator rejects anything above 16 or missing required rows.
- Statement timeout 2 seconds; connect timeout 3 seconds; existing mutex wait at
  most 60 seconds. These are component limits, not a promised total wall-clock bound.
  Deduplication may inspect additional catalog entries before the edge cap; the
  statement timeout bounds that work, not a claimed 64-row scan limit.

Missing/duplicate objects, unexpected columns/labels/types, inconsistent totals,
partial results, timeouts, permission errors, unverified mode/cleanup and overflow
produce no findings. A successful zero-edge report remains non-authoritative and
cannot be normalized as a source snapshot or unblock the production day reader.

## Verification and Decision

The proposal tests use the existing mocked driver and shared reader, with an
isolated test mutex and blocked external networking. They cover success/zero edges,
cap sentinels, missing/duplicate/malformed rows, exact parameter binding, all cleanup
failures, no implicit approval, fixed provider errors, closure before interpretation,
no v2 snapshot conversion and the unchanged UNAVAILABLE reader.

Verification on 2026-10-05:

- Focused proposal/evidence/source/v2 serializer/FIFO tests: **966 passed in
  4.22 s**, including all 71 new proposal cases.
- Broader source-shadow, shared-reader, PACS, flu/weekly-report, patient-context,
  outbox, runtime-contention and vaccine-post-print selection: **1,460 passed,
  1 failed in 48.95 s**. The failure was the vaccine post-print reminder test
  `test_label_print_starts_reminder_once_for_manually_opened_system[False-True]`.
  It did not recur in the subsequent full suite; its cause is not resolved here.
- Full isolated suite: **3,091 passed, 26 failed in 151.00 s**. The 26 failures
  match the previously documented baseline vaccine font/ink/shortcut-width
  failures. No test assertion or unrelated application code was changed.
- External network/real DB/native input/printing were blocked by the existing
  isolated runner; the shared reader used mocked connections and test mutexes.
- `git diff --check` passed. Application modules and v1/v2 fixture contents are
  unchanged. The new SQL fixture's line endings are pinned to LF for its digest.

Those results describe preparation before live approval. No application code,
endpoint, transport, publisher, board or PACS change is part of this operation.
All source gates remain unresolved.

Approval scope presented: **one closed-hours execution of source-structure-v1 exactly
as specified above**, followed only by its sanitized metadata counts and cleanup
results.
Approval does not cover a second attempt, any clinical-row read, further metadata
discovery, a new query, privilege changes or production enablement.

## Approved Observation

Recorded on **2026-10-05 at 23:09 KST**, starting from clean sender HEAD/GitHub
`main` at `bda2933aae172af4bcd9df3c4137daf49cdfa9bd`.

- The exact query digest above was rechecked and unchanged.
- All **71 proposal tests passed in 0.95 s** with mocked connections before the
  live call. No code, query, parameter or cap was changed between review and run.
- The one-shot caller read only the configured connection setting from local
  SQLite using `mode=ro`, closed that local connection, and did not print or persist
  the setting. It then called the approved proposal through
  `run_verified_evidence_query`, using the real shared FIFO and machine-wide mutex.
- Exactly one fixed catalog operation was attempted, with the previously reviewed
  session-local read-only/timeout setup and verification. No clinical table, UI,
  patient record, view contents or view definition was read.
- Result: `structure_observed`; `authoritative_snapshot=false`.
- Read-only mode, cursor closure and physical source-connection closure were all
  verified. Source connection work took **0.101 seconds**. Interpretation and
  sanitized output occurred only after those closure checks succeeded.

| Sanitized metadata | Receptions | Orders |
| --- | ---: | ---: |
| Ordinary relation (`r`) | yes | yes |
| Direct parent inheritance links | 0 | 0 |
| Direct child inheritance links | 0 | 0 |
| Outgoing foreign-key constraints | 0 | 0 |
| Incoming foreign-key constraints | 0 | 0 |
| Dependent views | 4 | 3 |
| Dependent materialized views | 0 | 0 |

The total is **7 scoped target-to-view links**, not necessarily 7 distinct views:
the two sets may overlap. No OIDs, view names, definitions, patient/order identifiers,
raw catalog rows or excluded qualifier values were output or persisted.

### Interpretation and Limits

The structural subquestion is now observed: these targets have dependent views
that merit coverage review, while the selected direct inheritance/foreign-key
counts were zero. Zero declared constraints do not negate application-managed
relationships, and zero inheritance links do not rule out independent archives.

No evidence here establishes the views' purpose, filters, membership, history
coverage, privileges, save atomicity, demographics or normalized state semantics.
No complete source gate is resolved. `EghisSourceDayReader` remains UNAVAILABLE,
all publishing remains disabled, and no PACS, receiver or application was changed
or restarted. The query was not retried or widened after this result.

The next candidate investigation is a separately scoped, mocked review of the
dependent views' allowlisted structural metadata. Do not read view definitions,
clinical rows or arbitrary object names as an automatic follow-up. A zero-count
result must never be reinterpreted as an authoritative empty clinic day.

This evidence update changes documentation only. A follow-up isolated run passed
all **100 proposal and evidence-to-v2 boundary tests in 1.08 s**. The full isolated
suite was not repeated for the documentation update; the preparation results above,
including the 26 existing vaccine-layout failures, remain the latest full-suite
result. Application modules, query bytes, tests and fixtures remain unchanged.
