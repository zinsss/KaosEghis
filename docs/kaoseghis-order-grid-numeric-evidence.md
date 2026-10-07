# Controlled Order Grid Numeric Comparison

Date: 2026-10-07, Asia/Seoul. One approved evidence comparison, not a runtime reader.

## Purpose And UI Check

The operator requests the prescription grid's displayed order name, daily amount,
frequency and days. The operator identifies `tree\ucc98\ubc29` and describes
`\uc77c\ud22c` as daily amount. Candidate source columns remain `user_nm`, `qty`,
`divide`, `days`; there is no multiplication, unit conversion or approved mapping
from that description alone.

Two passive elevated UIA checks found one visible prescription Tree with the
static headers code, code name, daily amount, frequency and days. The provider
exposes Group / TreeItem / DataItem rows and string-valued cell access. Checks
took 6.65 s and 5.30 s including discovery/provider traversal, not database time.
Non-elevated discovery had failed while both EMR processes were elevated.
No clicks, typing, focus changes, database connections or patient-value output
occurred in these structural checks. Their bounded traversal was not a complete
grid export and establishes no source mapping.

## Exact Proposed Live Operation

SQL: `tests/fixtures/source_order_grid_numeric_match_v1.sql`.
SHA-256 of UTF-8/LF text:
`7fcceeffe55f539aa7e952a2112bd61d183acf64508fb881b2484d3d917e5db3`.

Test-only caller: `tests/source_order_grid_numeric.py`. It has no runtime importer,
connection configuration, UI actions or publishing. No automatic invocation.

Exhaustive source columns referenced:

- `public.h1opdin`: `clinic_ymd`, `ptnt_no`, `recept_no`.
- `public.h2opd_doct_ord`: `recept_no`, `ord_ymd`, `ord_no`, `ord_seq_no`,
  `user_cd`, `user_nm`, `qty`, `divide`, `days`.

Seven bound parameters only: current KST `day`, ephemeral UI `chart_no`, exact UI
`code` and `name`, and exact Decimal `daily`, `frequency`, `days`. Text is not
trimmed, normalized, supplemented from another column or matched approximately.
No catalog field, patient master, excluded qualifier or clinical note is read.
Identifiers and displayed values remain transient and are never diagnostic output.

The one statement finds the current-day reception and the exact code/name child.
It uses cap-plus-one (`LIMIT 2`) for each singleton scope. Zero or multiple matches,
invalid four-part keys and off-day children reject the comparison. Other orders
are not retrieved. It does not filter cancellation/type/fee flags or classify rows.
It compares three numbers server-side; numeric source values are not returned.
Equal UI examples are rejected because they cannot distinguish swapped columns.

Allowlisted result only: capped counts (0..2), three numeric-match booleans and
source type names (`numeric`, `smallint`, `integer`, `bigint`). Floating-point or
unknown types are rejected, not silently approved through coercion. NULL numbers
do not match a displayed number. No scale, unit or all-category convention is
deduced from equality. Exact UI source context is rechecked after physical close;
a changed chart, row, code/name or number discards the result.

Use the existing `run_verified_evidence_query` boundary: shared FIFO, machine-wide
Windows mutex, connect timeout 3 s, statement timeout 2 s, verified read-only
READ COMMITTED session, single SELECT, bounded aggregate fetch. Cursor and physical
connection closure must both be verified before post-read UI inspection or result
interpretation. No write is attempted to test permissions. No retry on failure.
Do not use a process-killing UI watchdog while a source connection may exist.

Client KST day is checked before capture, before query, after close and after
validation; SQL also checks the current server KST day. Midnight invalidates the
operation. This is one-row candidate correspondence only, not save consistency,
selected-visit authority or full-day completeness proof.

## Approved Live Result

The operator separately approved the exact one-statement comparison with "go"
after the focused mocked tests passed. It was performed once on the current KST
clinic day, 2026-10-07. The parameterized SQL and its hash were unchanged.

Two initial UI capture attempts stopped before opening a source connection because
the TreeItem row had no UIA runtime ID. The chart and grid runtime IDs were present.
The successful capture used the verified chart/grid identities plus a bounded
row position/rectangle and exact code/name/three-number comparison before and
after the read. This is a transient UI position, NOT a source-order identity.
The DB still had to establish exactly one current-day reception and exactly one
code/name child with valid four-part keys. The comparator validator was unchanged.
Eight additional synthetic checks covered the temporary row-position guard.

Sanitized result: `one_row_numeric_match`, `authoritative_snapshot=false`.

| Screen fact | Compared source | Result for this sample |
| --- | --- | --- |
| Code | `user_cd` | Exact match in the singleton lookup |
| Code name / prescription name | `user_nm` | Exact match in the singleton lookup |
| Daily amount | `qty` | Equal; PostgreSQL type `numeric` |
| Frequency/count | `divide` | Equal; PostgreSQL type `numeric` |
| Days | `days` | Equal; PostgreSQL type `numeric` |

All three screen numbers were different, so the equalities distinguish their
column positions. None of their actual values or prescription text is recorded.
The approved result contains only booleans, allowlisted source types, closure
proof and timings. No identifiers, raw rows, query parameters or provider errors
were output or persisted by the inspection helper or in these reports.

- Source statement calls: **1**, through the shared FIFO and global Windows mutex.
- Read-only session verified before the SELECT: **true**.
- Cursor closed and verified: **true**.
- Physical connection closed and verified before interpretation: **true**.
- Connection lifecycle: **0.0622 s (62.2 ms)**, including connect/session setup,
  SELECT/fetch and cleanup. This is NOT isolated SQL execution time or server CPU.
- Passive UI captures: **5,409.1 ms before**, **4,124.6 ms after**. These include
  discovery/provider access and are separate from database connection time.
- UI actions sent: **0**. No click, typing, focus change or database write.

The transient UI helper has an existing-report guard against accidental rerun;
no source-reading helper was added to application runtime. No second DB query,
execution-plan call or historical-day access was performed for this operation.

## Limits And Verification

This is a controlled single-row correspondence observation. It does not establish
all-category name/number coverage, source precision/scale/null/domain limits,
clinical units, actual administration, save consistency, durable UI row identity,
key lifecycle or whole-day authority. A matching row must not be generalized into
an approved clinical dose calculation. All production evidence gates stay open.

Focused coverage includes synthetic relational execution of the actual SELECT
(PostgreSQL-specific syntax/type introspection adapted to in-memory SQLite),
strict Decimal input, ambiguous/missing rows, key/date guards, UI changes, midnight,
unknown types, read-only/cleanup failures, queue poisoning and redacted reporting.
SQLite adaptation is not PostgreSQL type or execution-plan certification.

Verification before the live query: 97 focused tests passed again in 1.14 s.
After recording the live findings, the broader isolated source/shadow,
serializer/outbox/shared-reader, PACS, flu and patient-context group passed
2,737 tests in 47.81 s (one existing pywinauto COM threading warning). Source DB
connections are mocked, test mutexes are isolated and external network is blocked.
The unrelated full UI suite and its previously known failures were not modified
or rerun for this test-only change.

The production day reader remains UNAVAILABLE. All existing evidence gates remain
unresolved. No full-day field export, source normalization, v1/v2 contract change,
fixture/hash change, runtime setting/trigger, outbox, transport, board or PACS
change, deployment or restart is authorized by this check. Failed or unverified
reads are never authoritative empty snapshots. The normalized-source payload
remains prohibited at `/api/v1/order-snapshots`.
