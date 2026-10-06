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

Three source statements were executed in the initial name/code phase, each with its own verified
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
must not filter it out of the complete detail list. None of these operations
reads those fields. Existing separately agreed reception-state facts and
cancelled-encounter scope are not silently changed by this clarification.

### Operator-Specified Current-Day Check

The operator subsequently supplied a chart number to identify the visit. Neither
that identifier nor the accompanying name is recorded here, in fixtures or test
data. The name is not used. The identifier is an ephemeral bound predicate only;
it is never returned by the database or copied into a result/error report.

The reviewed statement is
[`source_targeted_order_v1.sql`](../tests/fixtures/source_targeted_order_v1.sql),
SHA-256 `21021162c560696540142a8f0407e2c850a1dc8c9012999746baed71c10d828d`.
It addresses only whether the specified chart has a **current-day** reception and
linked doctor orders, including whether an order-date filter could hide a linked
child. It does not search historical receptions or identify a different patient.

Exhaustive source columns: `h1opdin.clinic_ymd`, `ptnt_no` (predicate only),
`recept_no` (internal linkage/key checks); `h2opd_doct_ord.recept_no`, `ord_ymd`,
`ord_no`, `ord_seq_no` (internal linkage/date/key checks), `ord_cd`, `medfee_nm`
(only equality against the two previously operator-supplied spellings).
No patient-name table, demographics, financial fields, excluded qualifier,
clinical notes or raw identifiers/labels are retrieved.

Output allowlist: 12 fixed metric names and bounded nonnegative integer counts
for server-day match, matched day receptions, linked children, same-day versus
off-day child-date counts, exact compact/spaced-name and code matches, invalid
and duplicate keys. Child dates/keys themselves never leave the database. A
current-day encounter's linked children are counted in one statement, not loaded
as a historical projection. All reports remain non-authoritative, including a
zero reception or zero child count.

Caps: ten matching current-day receptions plus one sentinel, 1,000 linked orders
plus one sentinel, 12 metric rows plus one sentinel. The existing verified shared
FIFO reader/global Windows mutex, connection timeout 3 s, statement timeout 2 s,
read-only verification and physical closure before interpretation are retained.
Current-day checks run before/after the read and interpretation, plus inside SQL.
No clock override or retry past KST midnight. Mocked preflight: **216 passed in
1.53 s**, comprising 150 existing name checks and 66 new targeted cases.

One targeted operation was performed before KST midnight on 2026-10-06. It found
one matched current-day reception and one linked order, also dated that day.
There were zero off-day orders and zero invalid/duplicate key counts. Exact
compact-name, spaced-name and supplied-code match counts were all zero.

Read-only/session verification and cursor/physical connection closure all passed;
elapsed connection time was **0.0554 seconds**. Local DSN SQLite handles closed
before the EMR connection opened. No patient identifiers, source order IDs, names,
catalog codes or raw rows were returned. The operator-supplied identifier was
used only as an in-memory bound predicate and was not committed or logged.

This confirms the specified chart has a reception and a child order in the
inspected day candidate; the day filter does not explain that child's absence
from the earlier name matches. It does **not** identify the child as the newly
reported flu item. The actual catalog-name string was not read, so the agent
cannot state what it says or claim a different known display label. No source
gate, name mapping, billing rule or save-completion guarantee is established.

The operator then asked for the actual prescription label. By that point KST
midnight had passed. The current-day guard was retained and no historical lookup
was performed. A separately scoped request to inspect only that prior-day
visit's single standard catalog name/code was subsequently explicitly approved.
There is no approval for broad historical reading, raw record export or any
change to the runtime's current-day-only behavior.

### Approved Single-Catalog Follow-up

This new operation is separate from the unchanged current-day probes. The
operator explicitly approved only the previously specified 2026-10-06 visit's
single standard order label/code after KST midnight. The test-only helper permits
only that visit date, on inspection date 2026-10-07; it is not a reusable
historical reader or runtime exception. The identifier remains an in-memory bound
predicate, is not echoed and is not recorded in source control.

Exact statement: [`source_single_catalog_v1.sql`](../tests/fixtures/source_single_catalog_v1.sql).
SHA-256 `df5e23c2596a16000c3ca754a8c024b59b6e15db94410ad2d09b0aab20c050e8`.
Columns referenced: `h1opdin.clinic_ymd`, `ptnt_no`, `recept_no` and
`h2opd_doct_ord.recept_no`, `ord_ymd`, `ord_no`, `ord_seq_no`, `ord_cd`,
`medfee_nm`. There is no patient-name/demographic/financial/notes query.

Both encounter and child scans are capped at two as a singleton sentinel. The
statement returns one aggregate row: encounter/order count, invalid-key/off-day/
withheld-text counts, and **only if exactly one encounter and one valid same-day
child exist**, the approved standard catalog code/name. Otherwise the server
withholds both text fields and the client rejects without selecting a row.
Code/name caps are 64/256 characters. Control characters and resident/phone-like
numeric patterns are withheld at the server and checked again after closure;
other Unicode control/format characters fail the client check. Nulls and whitespace
are not silently replaced or reinterpreted. No source key or patient field leaves
the database. Actual catalog values are for the requested response only, not this
evidence document, fixtures, logs or persisted diagnostics.

The same shared FIFO/global mutex and verified read-only session are used, with
3 s connection and 2 s statement limits, no retries and physical closure before
interpretation. Server/caller guards reject inspection-window changes. No existing
validator, runtime reader block, current-day probe or v1/v2 fixture is weakened.
Mocked preflight: **278 passed in 1.73 s**, including 62 singleton cases covering
approval, exact date/window, scope ambiguity, privacy shape rejection, nulls,
cleanup and fixed errors.

The explicitly approved singleton operation ran once on 2026-10-07. It passed
the exactly-one encounter/child scope check. The permitted catalog code field
was an empty string and the permitted standard-name field was SQL NULL. No
nonempty label or code was returned or recorded. The result is not proof that
the EMR has no displayed prescription or that the reported item was not saved;
only these two fields in this candidate were inspected.

Verified read-only mode, cursor closure and physical connection closure all
passed in **0.0602 seconds**, after local DSN handles had closed. There was no
retry, broad historical scan, UI action or write. This was the second live
operation in the targeted follow-up (one current-day aggregate before midnight,
one separately approved singleton catalog check after midnight).

This exposes a concrete source/contract representation issue: existing v2 requires
nonempty `order_code`, and has no order-name fact field. Do not fabricate a code
from the operator's expected label, silently drop the child as a fee, replace NULL
with a guessed name or weaken v1/v2. Determine the actual standard display-name
source with separately reviewed metadata/field evidence first. No free clinical
text retrieval is approved by this finding. The source reader remains blocked.

### Operator Screenshot Clarification

The operator then supplied a cropped EMR prescription-grid screenshot. It visibly
shows the previously supplied compact code and spaced code-name as one row under
the prescription area. The screenshot is not copied into the repository. No
patient identifier or new patient information is transcribed.

The UI observation establishes the operator's displayed spellings, while the
approved DB observation found empty/NULL in the two queried fields. These are
not interchangeable evidence: identify the actual storage/linkage used by the
display before mapping it. Do not infer that the UI order is missing, silently
omit it from the complete detail list, or fill the blank source facts with the
operator's expected text. The visible financial checkbox is not an Orders
inclusion criterion and is not investigated. Next evidence should identify the
standard user-code/display-name field or catalog linkage via reviewed metadata,
without an unrestricted clinical-text or raw-row dump.

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

Targeted follow-up verification: the 216-case preflight (66 new cases) preceded
the current-day aggregate. Its intermediate full isolated run had **3,927 passed,
27 failed in 185.90 s**: the known 26 vaccine label/shortcut failures plus
`test_new_vaccine_record_retains_patient_context_for_simultaneous_vaccinations`,
which raised a Qt object-type/`triggered` AttributeError. That case passed alone
in **1.31 s**; no UI code was changed and the intermittent failure is not treated
as fixed. The singleton preflight subsequently passed **278 cases** (62 more).

Final combined full isolated suite: **3,990 passed, 26 failed in 185.70 s**.
The failures match the previously documented label/shortcut baseline. The full
suite is not green; the intermediate Qt failure did not recur in the final run.
Application code, v1/v2 JSON fixtures and runtime behavior remain unchanged.
