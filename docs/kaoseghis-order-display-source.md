# Prescription Display Source Review

## Question And Scope

Continue from sender `61c835d579ab0959bf44ba3e04d2aee78cb9c07b`. The operator's
cropped screenshot shows the supplied user code and code-name, while the
separately approved singleton check found empty `ord_cd` and NULL `medfee_nm`.
Do not equate missing values in these two columns with a missing prescription,
infer a billing exclusion, fabricate a code/name, or weaken v1/v2 validators.

The operator asked to proceed with locating the display source. Start with
metadata only. Any subsequent value check must be separately reviewed, bounded
and mocked first; the existing prior-day approval concerns only the identified
2026-10-06 singleton visit, not historical day-wide reading or raw-row export.
No identifying input or screenshot is stored in this document or fixtures.

## Operation 1: Candidate Columns

Exact query: [`source_order_display_columns_v1.sql`](../tests/fixtures/source_order_display_columns_v1.sql).
SHA-256 `ab37138970de6c60406f5a4d34acd7400dc572fe0fe8b144eaca1c263a4a1f59`.

This statement reads only `pg_catalog.pg_class`, `pg_namespace`, `pg_attribute`
and `pg_type`; **no clinical table is read**. It selects the exact ordinary table
`public.h2opd_doct_ord`, then candidate column metadata matching
`(ord|user|medfee|code|name|_cd$|_nm$)`. Excluded names include the forbidden
qualifier and direct patient-name fields. Names are screened as lowercase SQL
identifiers, type names are allowlisted or represented by `OTHER_TYPE`, and
unreviewed identifiers cause a fixed rejection. No defaults, comments, view or
function bodies, row samples, identifiers or data values are returned.

Referenced metadata columns: class `oid`, `relnamespace`, `relname`, `relkind`;
namespace `oid`, `nspname`; attribute `attrelid`, `attnum`, `attname`, `atttypid`,
`attnotnull`, `attisdropped`; type `oid`, `typname`. SELECT capability is evaluated
with `has_column_privilege`, without enumerating roles or credentials.

Output allowlist: exact relation count, bounded candidate-column count, candidate
column identifier, reviewed type/`OTHER_TYPE`, nullability and SELECT booleans.
At most 128 columns plus one sentinel and two fixed summary rows are returned;
overflow, missing/duplicate summaries or an ambiguous/missing relation reject.
Column names alone are not clinical meaning or permission to read their values.

The existing shared FIFO and `Global\KaosEghis-EMR-read` Windows mutex are used.
Connection timeout 3 seconds, statement timeout 2 seconds, verified read-only
autocommit session and one reviewed source statement. Cursor and physical
connection closure must be verified before metadata interpretation/output. The
local DSN setting is read-only and closed before the EMR connection opens.
No provider errors, credentials or SQL values are logged. No automatic retry,
permission change, safety-latch reset or timeout widening.

Tests precede any live operation. The helper reuses the existing test-only
storage-inspection safety/report boundary; it has no runtime importer or CLI.

## Results

Operation 1 ran once after **176 mocked tests passed in 1.48 s** (41 new display
metadata cases plus 135 existing storage cases). It found 20 candidate columns;
all were selectable. Relevant observed metadata:

| Column | Type | Nullable | SELECT |
| --- | --- | --- | --- |
| `user_cd` | `varchar` | yes | yes |
| `user_nm` | `varchar` | yes | yes |
| `ord_cd` | `varchar` | yes | yes |
| `medfee_cd` | `varchar` | yes | yes |
| `medfee_nm` | `varchar` | yes | yes |

Read-only verification, cursor closure and physical connection closure all passed
in **0.0553 seconds**. The local DSN handles closed before the EMR connection.
No clinical row or value was read. The existence of `user_cd`/`user_nm` is not by
itself proof that they provide the displayed values.

## Operation 2: Exact Display-Pair Match

The operator's request to proceed concerns the same previously identified,
explicitly approved 2026-10-06 singleton visit. Retain that point scope, with the
existing 2026-10-07 inspection-window guard. Do not broaden to another visit/day,
historical day-wide data or new patient fields.

Exact query: [`source_order_display_match_v1.sql`](../tests/fixtures/source_order_display_match_v1.sql).
SHA-256 `2ad618c051b8035e80ed4fd014d691bb4ee4243732af4c330ff01f27da864f31`.

Columns referenced: `h1opdin.clinic_ymd`, `ptnt_no` (bound predicate only),
`recept_no` (internal linkage); `h2opd_doct_ord.recept_no`, `ord_ymd`, `ord_no`,
`ord_seq_no` (internal keys/day checks), `user_cd` and `user_nm`. The latter two
are compared inside SQL with the operator-supplied code/name already visible in
the screenshot. **No source string or identifier is returned**, not even the
matching values. No notes, diagnosis, demographics, financial fields or excluded
qualifier are selected or interpreted.

Encounter and child scans each have a two-row singleton sentinel. The only result
is six bounded integer aggregates: encounter count, child count, invalid-key
count, off-day count, exact expected-code match count and exact expected-name
match count. Only one encounter and one valid same-day child are accepted. Both
match counts must equal one before reporting the pair matched; partial matches
do not confirm a mapping. Missing/ambiguous rows, malformed counts, window change,
failed/partial/timed-out reads and uncertain cleanup reject without any snapshot.

Use the same FIFO/global mutex, read-only proof, 3 s connection/2 s statement
limits, one statement snapshot and verified physical closure before processing.
The two operations are independent observations, not one shared snapshot. No
permission changes, retries or runtime wiring. Mocked tests precede the live
check. Any success is evidence only for this particular displayed pair, not a
universal mapping for every order category or permission to reinterpret v2.

### Approved Observation

Operation 2 ran once on 2026-10-07 after **283 mocked tests passed in 1.69 s**
(86 display-source cases, 135 storage cases and 62 singleton cases). Its single
aggregate row confirmed exactly one encounter and one same-day child, zero
invalid keys and zero off-day children. The exact expected `user_cd` match count
was **1** and the exact expected `user_nm` match count was **1**.

This verifies that the operator-supplied screen code and screen name occur in
`h2opd_doct_ord.user_cd` and `h2opd_doct_ord.user_nm`, respectively, for this
approved case. Only comparison counts were returned; no source code/name strings,
patient/order identifiers or raw clinical rows were retrieved or recorded.
The result is `display_pair_matched`, with `authoritative_snapshot=false`.

Read-only verification, cursor closure and physical connection closure all passed
in **0.0507 seconds**. The local configuration handles closed before the EMR
connection opened. There was no retry, write, UI action, privilege change or
broader date scan. These two operations were the only live operations in this
display-source follow-up.

## Compatibility And Next Handoff

| Fact | Evidence and boundary |
| --- | --- |
| Screen code | Exact `user_cd` comparison matched for this one approved child. |
| Screen name | Exact `user_nm` comparison matched for the same child. |
| Existing catalog facts | The earlier empty `ord_cd` and NULL `medfee_nm` are distinct observations, not values to overwrite with expected text. |
| Identity | The four-part encounter/date/order-number/sequence key remains unchanged; neither display code nor name replaces identity. |
| Existing v2 | Requires a nonempty `order_code` and has no name fact. Do not silently reinterpret it as `user_cd`, change fixtures/hashes or relax validators. |
| Coverage | A matching singleton does not establish all-category coverage, null/blank handling, length bounds, save completion or universal display precedence. |

The immediate source-location question is answered for this case. There is no
need to broaden permissions or inspect an alternate table to locate this pair.
That does not establish that alternate storage is irrelevant for other orders.
All broader source-authority gates remain unresolved.

Next KaosOrders handoff: review a separate source-neutral representation for
original user/display code and name alongside distinct catalog facts. Agree
field names, bounds, explicit null/blank semantics and privacy constraints before
any implementation; broader source coverage still needs evidence. Preserve the
complete actual order detail irrespective of billing eligibility, fee/category
classification or a hard-coded national-flu translation. No-order encounters
remain a separate valid case, not a substitute for this present child.

Runtime, source contracts/fixtures, PACS, publishing, settings, triggers and board
remain unchanged; the day reader stays UNAVAILABLE. No receiver code, endpoint,
token or transport is added. `/api/v1/order-snapshots` remains prohibited for
normalized-source data.

## Verification

The related source/shadow/serializer/outbox/shared-reader, PACS, flu and
patient-context regression group passed **2,200 tests in 46.54 s**. Tests use
mocked databases, isolated test mutexes, temporary application data and blocked
external network/native input/printer access. No production write was attempted.

Full isolated suite: **4,076 passed, 26 failed in 188.32 s**. All failures match
the preceding documented baseline: 20 label-area assertions at 203 dpi, three
title-font assertions, one manufacturer-pill ink assertion and two
vaccine-shortcut width assertions. The full suite is not green. No unrelated UI
fix or weakened assertion was included. All 86 new display-source cases passed.

Git comparison against the starting commit confirmed no application-code or
existing JSON-fixture changes. Existing v1/v2 serializers, validators, fixture
bytes/hashes, synthetic stores and runtime behavior are unchanged. Only test-only
inspection helpers/statements, mocked tests and sanitized documentation are added
or updated. No identifying diagnostic artifact is committed.

Subsequent milestone: the [synthetic order-text proposal](kaoseghis-order-text-proposal.md)
uses this bounded finding to test four distinct nullable code/name facts offline.
It performs no further live reads and leaves this evidence, v1/v2 and runtime
behavior unchanged. Receiver agreement is required before a new complete fact or
session contract can carry these fields.
