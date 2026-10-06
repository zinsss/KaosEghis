# Exact Named-Order Observation

## Scope And Approval

On 2026-10-06 KST the operator reported adding and sending the new national-flu
order on one actual vaccinated patient's visit, then supplied its exact catalog
name: `국가접종 독감`. This is not the previously proposed disposable visit.
No clinical record modification, UI interaction, printing, claim submission or
test transition is authorized or needed. The existing instruction to perform
bounded read-only evidence checks and this exact-name clarification scope this
one observation. Do not look up or request a patient name or chart number.

The sole question is whether this exact, operator-supplied standard order name is
present in the already-reviewed current-day order candidate, and which catalog
code/type/department and raw retained flags it has. This can verify a narrow
storage/name-source observation, not an authoritative whole-day reader, billing
exclusion or completed-save boundary.

## Reviewed Operation

The exact parameterized statement is
[`source_named_order_v1.sql`](../tests/fixtures/source_named_order_v1.sql).
SHA-256 over the UTF-8 statement with LF newlines:
`c1ec4286191ce2b766df5a922619e008583558ab6f10bf6fc050739af78f01e6`.

Selected/referenced source columns, exhaustively:

| Table | Columns | Purpose |
| --- | --- | --- |
| `public.h1opdin` | `clinic_ymd`, `recept_no` | Current KST day; internal linkage and aggregate key checks only |
| `public.h2opd_doct_ord` | `recept_no`, `ord_ymd`, `ord_no`, `ord_seq_no` | Same-day match and internal four-part key checks only |
| `public.h2opd_doct_ord` | `medfee_nm` | Exact parameter equality only; no arbitrary source text returned |
| `public.h2opd_doct_ord` | `ord_cd`, `ord_type`, `proc_dept_cd`, `dc_yn`, `act_yn` | Grouped catalog metadata and raw-flag observation |

The name is supplied as a bound parameter, not interpolated. No LIKE/search of
other names, patient joins, free text, quantities, prices or billing flags.
`hold_opd` is not selected, tested, returned or interpreted. Reception/order keys
remain inside the SQL statement and never leave the database.

Privacy-safe result allowlist:

- Fixed summary labels and integer counts: current-day match, scoped encounters,
  matched orders/encounters, invalid/duplicate encounter and four-part order keys.
- Grouped **catalog** code, allowlisted order type/department, raw `dc_yn`/`act_yn`
  and count. These are not patient, encounter or individual order identifiers.
- Catalog code must match `^[A-Za-z0-9_.@#*-]{1,32}$` at the server and client;
  otherwise the report fails with `catalog_code_unreviewed`, without the value.
- Type allowlist `01` through `09`; departments `LAB`, `DRUG`, `INJ`, `XRAY`,
  `BMD`, `ECG`, `PT`; retained flags `Y`/`N`. Other values become fixed
  `NULL`/`BLANK`/`UNREVIEWED` markers at the server. Markers have no clinical meaning
  and do not make a valid normalized qualifier.
- Fixed status codes, session/cleanup booleans and elapsed connection seconds.

Caps: 10,000 day encounters plus one sentinel, 1,000 exact-name matched orders
plus one sentinel, 32 grouped combinations plus one sentinel. The final result
has eight summary rows and at most 32 buckets; the statement returns at most 41
rows to detect overflow. Overflow, malformed/partial aggregates, key anomalies,
unknown catalog-code format, timeout or uncertain cleanup cannot return findings.
A successful zero match means only `named_order_not_found`, never an empty clinic
day. Every report remains `authoritative_snapshot=false`.

Use only `run_verified_evidence_query` through the shared FIFO and
`Global\KaosEghis-EMR-read` Windows mutex. Connection timeout is 3 seconds;
statement timeout 2 seconds. Verify `transaction_read_only=on`, timeout `2s`, and
`read committed` before the single source statement. Its CTEs share that one
statement snapshot; no multiple-autocommit snapshot assumption is made.

Verify both cursor closure and physical connection closure before interpreting
or outputting aggregates. A failed physical close blocks further reads through
the existing safety latch. No reset of that latch, automatic retry, widened
timeout or permission changes. Verify the current KST day before/after the read
and after interpretation, with a server-side day guard for queue delay. The local
SQLite DSN setting is read using `mode=ro`, its handles closed before the EMR
read, and the setting/provider errors never printed.

## Mocked Preflight

`tests/source_named_order.py` is test-only, with no CLI or runtime importer.
`tests/test_source_named_order.py` covers scope/approval, query pinning, parameter
binding, strict privacy-safe output, overflow, malformed results, key anomalies,
all retained flag combinations, fixed unknown masks, not-found versus failure,
midnight races, session verification, every cleanup failure, FIFO serialization,
redacted errors and absence of runtime/transport dependencies.

These are mocked DB and static query-review tests, not a PostgreSQL SQL simulator.
No live query is justified by a mock's fabricated result alone.

## Exact-Code Follow-up

The first exact-name operation returned no match. The operator then answered the
code question with `국가접종독감` (without a space). The separately reviewed
follow-up statement is
[`source_named_order_code_v1.sql`](../tests/fixtures/source_named_order_code_v1.sql),
SHA-256 `87c78f2d7c8be948546503bc690be71ca0c98f6ebb6761619b5f51e3000aa25f`.

It uses the same exhaustive source columns, current-day scope, single-statement
snapshot, caps, timeout, shared lock, read-only and cleanup checks. The only
selection is exact bound `ord_cd = '국가접종독감'` on today's scoped orders.
There is no broad search or date change. This is a distinct operator-clarified
operation, not an automatic retry or a widened scan after a failed source read.

The output substitutes the fixed `CONFIRMED_CODE` token for the catalog code,
then reports only the already operator-supplied code. Arbitrary Unicode/code
retrieval is not added to the original name probe's ASCII restriction. Source
`medfee_nm` is compared inside SQL with the two operator-supplied spellings:
`COMPACT_NAME` means exact `국가접종독감`, `SPACED_NAME` means exact
`국가접종 독감`, `NULL_NAME` is SQL NULL, and `OTHER_NAME` withholds everything
else. The result adds only that fixed name-match token. A different or missing
name must not be replaced with a guessed display name in a source snapshot.

Mocked preflight after this follow-up: **143 passed in 1.37 s**. This includes
both pinned statements, distinct-name buckets for the same catalog code, strict
token rejection and cleanup/provider-failure tests for both lookup modes.

## Observation

First operation, 2026-10-06 KST: exact spaced-name lookup returned
`named_order_not_found`: 267 encounters in the day candidate; zero matched orders
and zero matched encounters. Aggregate key anomaly counts were zero. This does
not establish that the operator's order is absent, or that the day has no orders.

Read-only mode, cursor closure and physical connection closure were all verified;
elapsed connection time **0.0541 seconds**. The local DSN SQLite handles were
closed before opening the EMR connection. No patient/visit/order-row identifiers,
arbitrary names or raw rows were returned or persisted. No UI operations occurred.

Exact-code follow-up also returned `named_order_not_found`: 267 scoped encounters,
zero matched orders/encounters, zero key anomalies. All read-only/session and
closure checks passed in **0.0560 seconds**. Neither zero-match observation proves
the operator's order is absent.

The final narrow check used the original exact-name statement/hash unchanged with
the operator's compact spelling `국가접종독감` as the bound `order_name` instead
of the initial spaced spelling. This tests name-versus-code ambiguity without a
LIKE search, historical date or patient identifier. It has identical columns,
aggregate output, caps and cleanup rules. Code lookup and compact-name lookup
cannot be combined into an OR query. **150 mocked tests passed in 1.34 s** before
this separate operation. It also returned `named_order_not_found`: 267 scoped
encounters, zero matches and zero key anomalies; verified physical closure in
**0.0535 seconds**. Its local DSN connection was also closed before the EMR read.

Three source statements were executed in total, each with its own verified
read-only connection, one statement snapshot and no automatic retries. They are
independent observations, not a shared three-statement snapshot. All returned
successfully but none located the supplied item. No source-name value or catalog
code was retrieved. No source gate is resolved by these zero matches.

Stop here rather than widen dates, names or patient scope. The operator was asked
whether the visit receiving the order is dated 2026-10-06. Until scope and the
exact source representation are established, this is neither a failed-transmission
diagnosis nor proof of alternate-table storage or an authoritative missing order.
Any later operation requires its own reviewed scope and mocked preflight. Do not
alter the real visit to manufacture evidence or silently omit the reported order.

## Operator Scope Clarification

KaosOrders is an order-viewing tool for today's visits, not a claims, insurance
eligibility or payment workbench. Billing eligibility, insurance and payment
operations are not evidence prerequisites for displaying the actual order and
must not filter it out of the complete detail list. Neither operation reads those
fields. Existing separately agreed reception-state facts and cancelled-encounter
scope are not silently changed by this clarification.

## Contract Boundary

This observation does not add an order-name field to existing v1/v2 models,
serializers, fixtures or hashes. The current facts cannot yet carry the original
EMR name. A separately agreed bounded standard-name field or catalog design is
still required for the existing patient-click complete-order-detail requirement.
Do not substitute a hard-coded flu label or omit a no-charge/unclassified order.
No-order non-cancelled encounters remain supported independently.

No production reader, settings, triggers, publisher, endpoint, token, board,
PACS, API call or deployment is changed. `EghisSourceDayReader` stays UNAVAILABLE;
`/api/v1/order-snapshots` remains prohibited for normalized-source data.

## Verification

The initial spaced-name mocked preflight passed **114 tests in 4.23 s**; the
intermediate code preflight passed 143 and final exact-name/code preflight passed
150 as recorded above. The initial broader source/shadow/serializer/outbox/shared
reader, PACS, flu and patient-context group passed **1,950 tests in 45.07 s** before
the later 36 cases were added. The final full isolated suite passed **3,862 tests**
with **26 existing failures in 184.39 s**. These match the preceding documented
baseline: 20 label-area assertions at 203 dpi, three title-font assertions, one
manufacturer-pill ink assertion and two vaccine-shortcut width assertions. No
unrelated fix or weakened assertion was made; the full suite is not green.
External networking and real EMR/native input are blocked in tests; test data and
the Windows mutex are isolated. No real DB test writes were attempted.

Changes are limited to test-only helpers/statements, mocked tests and sanitized
documentation. Existing application code and v1/v2 JSON fixture bytes are
unchanged. No patient-data diagnostic artifact is committed.
