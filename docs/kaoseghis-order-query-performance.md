# Current-Day Aggregate Query Performance

Date: 2026-10-07. Approved **one-shot aggregate inspection**, not a full-order
reader, production mapping or publishing approval. Starting sender commit:
`733775be2c7ae61a5883a7fcab786866a03f3db2`.

## Scope And Approval

The operator requested today's whole-order polling time and system load. After
being told the production reader remains blocked and that aggregate-query cost
is not full-field transfer cost, the operator explicitly chose measurement of the
existing aggregate query first. No source gate or runtime block was lifted.

The approved operation was one execution of the existing pinned
[coverage SELECT](../tests/fixtures/source_order_coverage_v1.sql), followed only
on valid bounded counts by one execution of the same SELECT prefixed with
`EXPLAIN (ANALYZE TRUE, BUFFERS TRUE, FORMAT JSON)`. The SELECT hash remains
`d608ae8ca3e477b1719f67f7ad2ff8a539bafae64aa8d27b795009300611c53c`.
EXPLAIN ANALYZE executes the SELECT again; it is not a non-executing estimate.
No retries, continuous poll, write test, table ANALYZE, configuration change or
additional source query was performed.

Referenced columns remain `h1opdin.clinic_ymd`, `h1opdin.recept_no`, and
`h2opd_doct_ord.recept_no/ord_ymd/ord_no/ord_seq_no`. Keys stay inside the DB.
No patient master, demographics, notes, order text, qualifiers or excluded field
was read. All candidate receptions, including cancelled/no-order candidates,
remain in the diagnostic; this is not the future non-cancelled Orders projection.

Limits: 10,000 receptions and 100,000 rows per order arm, each plus a sentinel;
17 fixed aggregate metrics; current KST day guards; 3-second connection timeout;
2-second statement timeout. Both calls use the existing FIFO and machine-wide
Windows mutex with verified read-only autocommit READ COMMITTED. Each cursor and
physical connection closes before interpretation/output and before the next call.
Local connection settings were obtained using SQLite `mode=ro`, closed before
source access, and never printed. No credential or raw execution plan was saved.

## Sanitized Findings

Ordinary query observation: **2026-10-07 18:02:52 KST**, current day `2026-10-07`.

| Aggregate | Result |
| --- | ---: |
| Candidate encounters | 269 |
| Encounters with linked orders | 262 |
| Encounters without linked orders | 7 |
| Linked order rows | 1,025 |
| Orders dated today | 1,025 |
| Invalid or duplicate encounter/key metrics | 0 |
| Off-day linked orders / unmatched today-dated orders | 0 / 0 |
| Three-part order keys spanning different dates | 0 |
| Cap overflow / aggregate consistency anomalies | None observed |

All ordinary-query metrics passed the existing bounded aggregate validator.
This remains `authoritative_snapshot=false`, not authoritative membership,
clinical state, save consistency, category coverage or verified-empty authority.

| Timing / resource indicator | Result |
| --- | ---: |
| Ordinary query client wall time, including queue/session/close/validation | 67.014 ms |
| Ordinary physical connection lifecycle | 65.9 ms |
| Profile client wall time | 65.191 ms |
| Profile physical connection lifecycle | 64.6 ms |
| Profile server total runtime | 10.791 ms |
| Profile root-node execution time | 10.406 ms |
| Root shared-buffer hits | 1,744 |
| Root shared-buffer reads / dirtied / written | 0 / 0 / 0 |
| Root local-buffer and temporary-block metrics | All zero |
| Index scan nodes / sequential scan nodes | 3 / 0 |
| Read-only verification, cursor close, physical close, both calls | All confirmed |

The plan summary uses root buffer totals, not sums of parent and child nodes,
which would double count. Only fixed numeric metrics and allowlisted scan-node
types leave the sanitizer. Predicates, identifiers, relation/index names and raw
plan text are not printed or persisted. Server timing is from the second,
instrumented execution, not an exact isolated SQL duration for the first call.

This query was inexpensive in this observation. The profile follows an ordinary
read and is therefore a warm-cache measurement; the first read's preexisting
cache state was not measured. Buffer hits are accesses, not distinct pages or a
RAM-footprint measurement. Zero buffer reads does not mean the entire DB server
had no disk activity. EXPLAIN instrumentation adds overhead. These distinctions
follow PostgreSQL's [EXPLAIN documentation](https://www.postgresql.org/docs/9.2/sql-explain.html).

Server CPU percentage, peak memory, cold-cache latency, lock-wait distribution,
concurrent EMR latency and whole-field extraction/transfer were **not measured**.
The client process CPU timer rounded to zero for both short calls; that is not
evidence of zero CPU cost and is not a server metric. A single two-execution
checkpoint supplies neither latency percentiles nor a safe fixed polling period.

## Fresh Snapshot Decision

If separately reviewed complete-field reads remain inexpensive, a fresh FULL
current-day observation per poll fits the memory-only design. Compare each valid
complete set against the last accepted in-memory set to catch additions, changed
facts, cancellations, disappearance and reappearance without timestamp guessing.
Keep reads serialized, close physically before processing, and replace atomically
only after whole-set validation and a current-day/session/generation recheck.
Failed, partial, timed-out or unverified reads preserve valid same-day state.

This recommendation does not approve a query or change a polling trigger. The
aggregate statement counts/groups keys, not all proposed order fields. Full source
coverage, content safety and save-boundary consistency remain separate gates. No
production reader, model/serializer, transport, settings, board or PACS change is
made. Never send normalized data to `/api/v1/order-snapshots`.

## Mocked Verification

Before live execution, profile sanitization, coverage, evidence-reader and FIFO
regressions passed **365 tests in 3.30 s**, with mocked DBs, isolated mutexes and
blocked external network. An initial new-test failure exposed a missing test-local
FIFO reset fixture; importing the existing isolated coordinator fixed test
isolation without changing production code or weakening assertions.

The test-only profile helper has no CLI, credentials or runtime importer. Failure,
timeout, invalid plan, unverified cleanup, changed SELECT hash and rollover produce
fixed errors without plan/provider text or an empty authoritative snapshot.

After measurement, the broader source/shadow/serializer/outbox/shared-reader,
PACS, flu-report and patient-context regression group passed **2,422 tests in
46.59 s** under the same isolation. Runtime source files and existing SQL/contract
fixtures are unchanged; `git diff --check` passed. The unrelated full UI suite was
not rerun for this test-helper/documentation change, and its previously known
failures were not addressed. No additional live query was needed for verification.
