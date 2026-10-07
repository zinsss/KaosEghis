# Controlled Order Grid Numeric Comparison

Date: 2026-10-07, Asia/Seoul. Evidence preparation only, not a runtime reader.

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

## Status And Limits

The operator approved elevated passive inspection. A separate explicit approval
was requested for the exact one-statement live numeric comparison after the
focused mocked tests passed. No live database comparison has been performed yet.

Focused coverage includes synthetic relational execution of the actual SELECT
(PostgreSQL-specific syntax/type introspection adapted to in-memory SQLite),
strict Decimal input, ambiguous/missing rows, key/date guards, UI changes, midnight,
unknown types, read-only/cleanup failures, queue poisoning and redacted reporting.
SQLite adaptation is not PostgreSQL type or execution-plan certification.

Verification: 97 focused tests passed. The broader isolated source/shadow,
serializer/outbox/shared-reader, PACS, flu and patient-context group passed
2,737 tests in 50.29 s (one existing pywinauto COM threading warning). Source DB
connections are mocked, test mutexes are isolated and external network is blocked.
The unrelated full UI suite and its previously known failures were not modified
or rerun for this test-only change.

The production day reader remains UNAVAILABLE. All existing evidence gates remain
unresolved. No full-day field export, source normalization, v1/v2 contract change,
fixture/hash change, runtime setting/trigger, outbox, transport, board or PACS
change, deployment or restart is authorized by this check. Failed or unverified
reads are never authoritative empty snapshots. The normalized-source payload
remains prohibited at `/api/v1/order-snapshots`.
