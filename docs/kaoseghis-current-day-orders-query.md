# Current-Day Orders Query Draft

Prepared 2026-10-07 from sender `22550e6733e87b497bf311249d06d3a795a4bb6c`.
**This full-row draft remains offline. No live execution or polling enablement.**

## Operator Requirement

The requested details are the values populated in the EMR orders grid when a
patient is selected: prescription name, displayed daily quantity (the operator
confirmed the meaning of the UI label), frequency/count and days. Preserve those
displayed facts rather than substituting categories, billing eligibility or a
computed medication instruction. Do not multiply or divide quantity by frequency,
invent units or turn a missing value into zero/one.

Internal encounter/order identities and retained states are still needed to compare
snapshots, detect removals and group children correctly. They are not extra visible
prescription columns. This milestone changes no board or display policy.

The subsequently supplied screenshot confirms that these are the code-name,
daily-quantity, count and days columns in the lower orders grid. Price, unit price
and billing classification are not requested. No actual prescription text, numeric
row sample, diagnosis or screenshot is copied into this document or test fixtures.
The screenshot identifies the UI columns, not their database-column mapping.

| Requested grid column | Candidate source | Draft output | Evidence / remaining question |
| --- | --- | --- | --- |
| Prescription name | `user_nm` | `user_name` | Earlier name evidence plus one exact current-day grid comparison; all-category correspondence unverified |
| Daily quantity | `qty` | `source_qty` | One approved grid equality; source type `numeric`; all-category domain/null/scale/units unverified |
| Frequency/count | `divide` | `source_divide` | One approved grid equality; source type `numeric`; all-category domain/null/scale unverified |
| Days | `days` | `source_days` | One approved grid equality; source type `numeric`; all-category domain/null/scale unverified |

The separate [approved single-row comparison](kaoseghis-order-grid-numeric-evidence.md)
found exact code/name and three numeric equalities on 2026-10-07. This is evidence
for the displayed correspondence in that sample, not a universal dose definition.
The query still exposes the three candidate columns independently under source
names, not normalized `quantity`/`frequency` or clinical dose semantics. Raw values are
selected without casts, rounding, defaults, arithmetic or unit suffixes. Future
numeric handling must preserve exact values, reject binary-float approximations,
and approve null/domain/scale/bounds from source evidence, not the old v2 contract.

Independent catalog/user code/name facts stay separate; `medfee_nm` is not used
as a fallback for `user_nm` or vice versa. NULL, empty text, whitespace and padding
are preserved. The earlier observation with an empty catalog code and missing
catalog name must not erase a present user prescription. See the
[display-source evidence](kaoseghis-order-display-source.md) and
[recorded numeric-change evidence](kaoseghis-emr-contract-review.md#field-boundary).

## Candidate Statement

Exact SQL: [source_current_day_orders_candidate_v1.sql](../tests/fixtures/source_current_day_orders_candidate_v1.sql).
UTF-8/LF SHA-256:
`72dd31f8379606e4818988d4e1f6971d106c376b47a7cea2ca42932ca3bbe918`.
The filename's `v1` versions this **draft query**, not a wire/source contract.

Only bound parameters: `day` (current KST date as YYYYMMDD), `encounter_cap`
(trusted exact integer, normally 10000), and `order_cap` (normally 100000).
Do not interpolate SQL or accept arbitrary caller-provided caps. The SQL checks
positive ceiling bounds and uses cap-plus-one sentinels; a future caller must also
validate types, current-day scope and authorization before connection creation.

Selected/referenced source columns, exhaustively:

- `public.h1opdin`: `clinic_ymd`, `recept_no`, `proc_gb`, `hold_yn`.
- `public.h2opd_doct_ord`: `recept_no`, `ord_ymd`, `ord_no`, `ord_seq_no`,
  `ord_cd`, `medfee_nm`, `user_cd`, `user_nm`, `qty`, `divide`, `days`,
  `ord_type`, `proc_dept_cd`, `dc_yn`, `act_yn`.

No patient master, patient name, chart number, resident ID, DOB, sex/age, phone,
address, diagnosis, notes, insurance, credentials or excluded qualifier is selected.
No new clinical unit, edit/cancel timestamp or normalized order state is inferred.
Candidate order-text columns still require the existing content/privacy gate;
an allowlisted column name does not prove its contents are safe for every row.

## Relational Behavior

1. Start from today's candidate receptions, using the server KST date at statement
   start as a guard. Do not start from an order inner join or scan historical parents.
2. Collect every child linked by reception key, without fee/category/billing,
   child cancellation, act flag, type or department filters. Use EXISTS so duplicate
   parent rows cannot multiply the bounded child set before rejection.
3. Check caps, null/blank keys, duplicate parents/full four-part order keys,
   off-day children, strict retained Y/N flags and provisional text/key lengths.
4. Return one metadata-only row on those structural failures, never a truncated
   subset. On a structurally accepted candidate, LEFT JOIN parents to children so
   a no-order parent has its own row with `order_present=false`.
5. Repeat statement metadata and expected total result count on each row. Preserve
   native key and numeric types; no key numeric-to-string convention is approved
   here. The SQL orders by source keys; this is not canonical wire ordering.

The four-part key remains encounter, order date, order number and order sequence.
Separate parent/child key columns avoid silently coercing distinct source types
through a UNION. A missing child is distinguishable from an order whose catalog
and user text fields are all NULL. A missing source parent does not produce an
invented encounter. Today-dated children with no current-day parent are outside
this parent-driven candidate; the existing coverage diagnostic remains separate
evidence, not a second query spliced into the same snapshot.

This extraction draft retains all candidate reception codes unchanged, including
code 50, unknown/null codes and no-order receptions. It does **not** approve the
state truth table or apply an unverified cancellation filter. The future Orders
projection must include verified non-cancelled parents and exclude verified
cancelled parents only after approved normalization. Unknown states fail that
normalization; they are not presumed active. Cancelled child rows remain retained.

`candidate_rows` means structural SQL checks passed, **not complete/authoritative**.
An empty query still returns a META row with zero counts; it is not verified-empty
authority. On failure the counts may describe capped prefixes and cannot be used
as totals. An off-day child rejects the whole candidate instead of being silently
dropped or having its date rewritten. No clinical meaning is assigned to it.

## Required Boundary Before Use

There is no live caller for this file. A future separately reviewed reader must:

- Retain the shared FIFO/machine-wide Windows mutex, verified read-only session,
  finite connection/statement timeouts, and one physical connection at a time.
- Use one statement snapshot, fetch the bounded result completely, then verify
  cursor and physical connection closure before interpretation/normalization.
- Check metadata agreement, actual versus expected returned rows, no-orphan/full-key
  uniqueness, repeated parent consistency, source value types, Unicode/privacy,
  numeric exactness and the approved reception/order state mappings.
- Recheck KST day before enqueue and after closure/validation. A statement begun
  before midnight is not allowed to become the new day's snapshot.
- Fail the whole operation on timeout/partial fetch, inconsistent/unknown result,
  overflow or uncertain cleanup. Keep the previous valid same-day state; never
  convert a DB error, rejected metadata row or unverified zero into empty/removal.
- Keep patient/order results transient; never print or persist rows, source values,
  identifiers, raw plans or provider errors. Only approved sanitized diagnostics.

The existing aggregate evidence reader fetches at most **257 rows** and is NOT a
suitable caller for this full-row draft. Do not reuse it and mistake truncation for
completeness. Maximum valid joined DATA rows are `order_cap + encounter_cap`;
transport-byte and numeric content bounds still require a separate approval.
No full-row reader is implemented or its block removed by this milestone.

PostgreSQL's [CTE behavior](https://www.postgresql.org/docs/9.2/queries-with.html),
[statement time functions](https://www.postgresql.org/docs/9.2/functions-datetime.html)
and [READ COMMITTED snapshot semantics](https://www.postgresql.org/docs/9.2/transaction-iso.html)
inform the single-statement design. One database snapshot does not prove an EMR
save spanning several commits is complete. No claim is made about plan cost or
PostgreSQL source-column type behavior before an approved test of this new query.

## Verification And Next Check

The actual candidate relational statement is exercised against synthetic in-memory
SQLite tables, not hand-generated expected rows alone. Tests adapt only DB-API
parameter markers and PostgreSQL clock/string functions. SQLite does not certify
PostgreSQL syntax/version compatibility, NUMERIC/Decimal adaptation, collation,
query plans, driver closure or clinical source authority. Numeric fixtures use
exact text to detect unwanted conversion, not to approve a source numeric type.

Verification: **131 candidate SQL tests passed in 1.57 s**. The broader isolated
source/shadow/serializer/outbox/shared-reader, PACS, flu-report and patient-context
group passed **2,553 tests in 47.83 s**. Tests use only synthetic in-memory tables,
mocked source access, isolated test mutexes and blocked external network. Existing
runtime files, SQL fixtures and v1/v2 JSON fixtures/hashes remain unchanged; this
adds a distinct candidate SQL fixture. `git diff --check` passed. No production DB,
UI, API or service was accessed or changed. The unrelated full UI suite was not
rerun for this offline SQL/test/documentation change.

The separate [one-row numeric comparison](kaoseghis-order-grid-numeric-evidence.md)
documents the exact bounded statement, mocked tests and one approved live result.
It confirmed the screen equalities and source `numeric` types, with all source
connections closed, but did not establish null/scale/domain or all-category rules.
It does not enable this full-row draft or authorize a new full-day field export.

The [earlier complete-model design](kaoseghis-current-day-orders-design.md) deferred
numeric fields. The operator now requests their grid display explicitly; this draft
prepares candidate retrieval only. It does not silently change a normalized model,
v1/v2 validator, receiver contract, fixture/hash, session coordinator or serializer.
All production source-evidence gates remain unresolved, including all-category
numeric/grid correspondence and numeric bounds/null/scale policy.
No runtime/settings/trigger, publishing, transport, persistent store, board/PACS,
deployment or restart is introduced. `/api/v1/order-snapshots` remains prohibited.
