# KaosEghis-emr

Last updated: 2026-10-10

The latest [complete-order source-gate review](kaoseghis-current-day-source-gate-review.md)
pins receiver `d6316753151f2cbcda36f1e9ea7a7b049ca22b43`, whose separate
synthetic volatile session is complete. This sender stage reviews existing
evidence and mocked safety boundaries only; no closed-hours live operation was
approved or performed in this session. All production gates remain open and
`EghisSourceDayReader` remains UNAVAILABLE. The proposed minimal encounter facts
need a separate versioned review, not an implicit v2 join. No production mapping,
PACS behavior, source query, session wiring or delivery changes follow.

The latest [independent current-day complete-order proof](kaoseghis-current-day-orders-parity.md)
implements only a pure synthetic model and memory collection against receiver
`0f3b8c13e77b03994d66da7e8d5a7414e035a3ea`. It retains independent text facts,
strict qualifiers and exact nullable daily-quantity/frequency/day Decimals under
`kaosorders.current-day-orders` version 1 / `kaosorders-current-day-orders-v1`.
Production mapping remains unassigned. The existing text component, v1/v2 code,
fixtures, readers and runtime remain untouched. No wire/session/persistence or
live read was added. All source-evidence gates and the production reader block
remain in force; synthetic parity is not source authority.

The [2026-10-07 bounded full-field read](kaoseghis-current-day-read-evidence.md)
observed 269 candidate reception records, 1,025 linked orders and 7 no-order
receptions, with verified physical closure in 74.467 ms and total probe time
146.837 ms. The resulting
[full-snapshot polling recommendation](kaoseghis-current-day-read-evidence.md#full-snapshot-polling-recommendation)
prefers a fresh whole-current-day read per refresh, serialized and coalesced,
with validation after close and no deletion on failed/unverified reads. This is
design guidance, not production enablement or proof of negligible server load.
Repeated clinical-hours performance and all source-authority gates remain open;
`EghisSourceDayReader` stays UNAVAILABLE and existing PACS behavior is unchanged.

**Orders target clarified:** the [current-day memory-only decision](kaosorders.md#current-day-memory-only-decision-2026-10-06)
makes the EMR DB the sole durable patient/order source. KaosOrders keeps only
today's transient board, clears it at KST midnight and reloads today's source on
restart. No historical backfill or production patient/order outbox/projection is
required. Prior synthetic persistence milestones below remain historical proofs,
not runtime requirements. Same-day source evidence, safe reads and session/rollover
design remain necessary. This documentation decision changes no running PACS/EMR
behavior and deletes no data.

The later 2026-10-06 scope clarification retains no-order encounters but excludes
cancelled encounters from the future Orders projection. This is Orders-specific,
not a change to shared source facts or PACS. Verified complete snapshots remove
formerly included encounters after cancellation and can restore them after reception
restoration; failures never imply removal. Existing v1/v2 contracts and synthetic
fixtures retain their original full scope until a separate session scope is agreed.

The [exact named-order observation](kaoseghis-named-order-observation.md) records
three narrow current-day name/code checks following an operator-entered order on
a real visit. No match was found; all physical connections closed before result
interpretation. A subsequent operator-scoped aggregate found one current-day
reception and one same-day child, but no match to the supplied name/code. Its
actual display-label source was not established by that check. An explicitly
approved singleton follow-up found an empty catalog code and NULL standard name,
with closure verified in 0.0602 s. Do not guess that the order failed to save or
that this child is the reported new item from those fields alone. Existing v2
rejects an empty order code and has no name fact; no validator is weakened.
The operator's subsequent screenshot shows the expected code/name in the EMR
grid, so source-to-display field linkage must be verified rather than treating
the row as absent or filtering it by financial status.
No patient identifiers or raw rows were
returned. KaosOrders displays actual orders, not claims/insurance/payment tasks;
those financial decisions are not prerequisites for its complete detail list.
No production source or runtime behavior changes follow from this evidence.

The subsequent [display-source follow-up](kaoseghis-order-display-source.md)
resolved the immediate field-location question for that same approved singleton:
both `h2opd_doct_ord.user_cd` and `user_nm` exactly matched the operator-supplied
screen code/name. Only equality counts were returned. Physical connection closure
was verified in 0.0507 s after a separate metadata-only read closed in 0.0553 s.
Preserve these facts separately from empty `ord_cd` and NULL `medfee_nm`; do not
silently change existing v2 code semantics or invent a label. A separately agreed
bounded display-code/name representation and broader coverage/null evidence are
still needed. All broader source-authority gates and the UNAVAILABLE block remain.

The separate [synthetic text-fact proposal](kaoseghis-order-text-proposal.md)
implements an offline four-field component for that gap: catalog code/name and
user code/name stay distinct, with strict full-key binding and no fallback.
It has no reader, serializer, runtime importer or production mapping. Receiver
field/bounds agreement and a new current-day fact contract remain separate;
existing v1/v2 and PACS behavior are unchanged.

Status: the first shared-read stage is implemented. Verified chart clears can now
refresh the existing whole-day PACS query; Poll Now remains a manual fallback.
PACS, flu-report, health, and patient-context reads share one FIFO worker per
process and a Windows machine-wide mutex. Each source connection is read-only and
closed before the next read or any downstream delivery. This is not yet a separate
broker executable or an all-orders/reception-status reader for KaosOrders.
F6/F7 observations remain diagnostic only. The patient-memo alert is unchanged.

The [KaosOrders shadow foundation](kaosorders.md) now has detached typed models,
strict synthetic mapping tests and memory-only complete-day comparison. Its actual
day reader remains blocked: limited key/state/lifecycle evidence is recorded, but
whole-day identity, mappings and completeness are not fully verified. Both new flags
default off; there is no runtime trigger subscriber, new source SQL, network publisher
or production outbox. A separately invoked synthetic SQLite outbox now has restart
and exact-retry tests; it is not runtime storage or approved for patient data.
KaosOrders is hosted on KaosClinic with a Raspberry Pi OS touchscreen viewer; the
new source-state and deployment decisions in that document supersede older plans.

The destination-neutral source model and source comparison are now implemented
**offline only** in `core/emr_source.py` and `core/emr_source_shadow.py`. They have
no production mappings, source SQL, runtime subscribers or delivery path. The
existing PACS pipeline and its shared connection boundary remain unchanged.
The current [source-evidence gate review](kaoseghis-source-evidence-gates.md) pins
receiver `890a4dd4ce992f2598c85557513cd2c70b098a2b`. Its v2 receiver-only
synthetic persistence/recovery proofs are complete, but all eight source-authority
gates remain unresolved. Its later approved catalog-only probe found 4 reception
view links and 3 order view links, with physical closure verified in 0.101 s;
see [sanitized evidence](kaoseghis-source-structure-probe.md#approved-observation).
No clinical rows were read, and no source mapping or runtime path was added. Vendor
information is not expected, so controlled metadata/dummy-workflow investigation
will continue under the operator's bounded read-only authorization. No observation substitutes for unproved
whole-day or save-consistency guarantees; see the linked alternative evidence path.
The [follow-up metadata evidence](kaoseghis-source-metadata-followup.md#results)
now confirms four distinct views and effective CREATE capability in `public`.
The latter blocks least-privilege approval despite no detected non-SELECT
capability on the two source tables. No grant/source/PACS setting changed. The
remaining [operator/admin decisions](kaoseghis-source-evidence-gates.md#next-practical-decision)
cannot be completed by more unsupervised read-only queries alone.
An offline Orders serializer now matches the pinned receiver's disabled normalized
contract with synthetic fixtures only; see [synthetic parity](#synthetic-contract-parity-2026-10-04).

The next offline milestone is implemented in `core/kaosorders_outbox_shadow.py`:
per-day transactional revision allocation, immutable sealed pending batches,
coalesced refresh tickets and content-bound internal synthetic receipts. See
[delivery foundation](kaoseghis-emr-delivery.md) for implemented behavior versus
unresolved production recovery, security, source evidence and transport decisions.
The pure serializer remains unchanged and has no runtime importer. Plaintext test
stores are created only by explicit callers with synthetic fixtures.

The separately approved [closed-hours evidence review](kaosorders.md#controlled-aggregate-source-evidence-2026-10-04)
now has a one-shot aggregate inspection tool. It uses the same FIFO/global mutex
and a stricter diagnostic entry point in `eghis_db.py`; existing reader calls,
PACS behavior and runtime settings are unchanged. This is not a production day
reader: `EghisSourceDayReader` still returns UNAVAILABLE.

## Connector Ownership Decision: 2026-10-03

**KaosEghis-emr owns safe source access, reusable EMR interpretation and source-change
detection. KaosPACS and KaosOrders own application-specific decisions and state.**
This refines the earlier same-day connector-only proposal: the boundary is EMR
interpretation versus application behavior, not processing versus no processing.
This is the target design, not a claim that the existing PACS pipeline or disabled
Orders prototype has moved.

```text
eGHIS DB (read-only)
  -> KaosEghis-emr: shared FIFO + Windows machine-wide mutex
  -> bounded read, detached result, cursor/physical connection closed
  -> validated source normalization and source-snapshot comparison
  -> destination-specific adapters
       -> KaosPACS: imaging eligibility, routing, worklist and imaging lifecycle
       -> KaosOrders: categories, fees, visibility, badges and order details

Flu reports, health checks and patient-context reads use the same source boundary.
```

| Responsibility | Owner |
| --- | --- |
| Chart clear/load scheduling, coalescing, safety/manual reads | KaosEghis-emr |
| Reviewed parameterized SQL, one live Kaos-managed connection, read-only mode, finite limits and verified cleanup | KaosEghis-emr |
| Source key scope, field/type validation, consistency and complete/partial/failed read evidence | KaosEghis-emr |
| Verified EMR code interpretation, normalized fields and source-change detection | KaosEghis-emr, after connection closure |
| Destination field allowlists, minimal identity projection, schema serialization, authenticated delivery and bounded retry | KaosEghis-emr adapters, after connection closure |
| Idempotent update application, stale-update rejection and persistent application state | Each receiving system |
| Category mappings, fee exclusions, badges, visibility and order details | KaosOrders |
| Imaging eligibility, modality/station rules, worklist behavior, completion and expiry | KaosPACS |

Separate adapters do not mean separate database owners or a generic SQL proxy.
They may need different reviewed queries and privacy contracts; do not force the
current imaging query and a future all-orders reader into one universal query.
Neither receiver receives EMR credentials or opens its own EMR DB connection.
Network waits/retries never retain the connection slot or machine-wide mutex.
Share already-read data where the reviewed projections permit it. KaosPACS receives
data directly from its adapter, not through KaosOrders or its filtered board data.
Neither receiver's restart or visibility rules should control the other's source feed.

The Orders projection must preserve approved source facts across relevant reception
states, including completed, paid and cancelled encounters; it must not pre-filter
to visible hold patients or decide categories on Windows. Include reviewed order
codes/type/department, state flags and approved structured edit fields as required
by the future contract, not unrestricted source rows or clinical free text. Source
privacy and completeness checks remain mandatory. Interpret verified source codes
centrally and preserve approved source facts alongside their normalized meanings.
In particular, keep `30` / 진료완료 and `40` / 수납완료 distinct; do not collapse both
into a generic closed state at the shared boundary. Unknown or ambiguous meanings
must fail closed for dependent decisions, not become guessed completion/cancellation.

KaosEghis-emr compares validated source snapshots for same-key content edits, state
transitions, physical disappearance and key reuse. For example, it can report a
진료완료-to-보류 transition or an approved quantity change without deciding tile
visibility or imaging eligibility. Absence proves disappearance only within a
verified complete source scope; it is not itself proof of clinical cancellation.
Reused keys must not silently retain old content or imply an immutable order lifetime.

Receivers apply those observations to their own state with duplicate/stale checks
and full-snapshot recovery. Source observation progress is separate from each
destination's delivery acknowledgement; a missed delivery must remain recoverable.
Snapshot/delta format, retry ordering and baseline persistence still need contract
review. No new event stream or persisted source ledger is enabled by this decision.
`observed_at` means when we read the source, not an inferred edit/cancel time.
Failed or partial reads cannot advance an authoritative comparison or imply removals.

Migration is staged: agree minimal normalized-source contracts with both receiving
repos, test EMR interpretation/source comparison here and application behavior there,
verify the Windows reader with mocked DBs, then seek approval for bounded live
shadow validation. Keep the current PACS
query, cancellation authority and API behavior until contract compatibility and
shadow parity are verified. No new production query or publisher is enabled by
this documentation decision. See [Orders migration](kaosorders.md) and
[PACS compatibility](kaoseghis-pacs.md).

## Offline Source Model: 2026-10-03

This stage implements an internal, fixture-testable model, not a receiver-approved
wire schema. `EghisSourceDayReader.read_day` always returns `unavailable`; no flag
can enable a live query. The old Orders normalizer reuses common validation types
from this module but remains a separate disabled board-reference prototype.

| Model | Contents and boundary |
| --- | --- |
| `EmrDayRead` | Detached rows, source/projection/day scope, observation time, read outcome and explicit evidence flags. |
| `SourcePolicy` | Versioned exact reception/order-state mappings. No default production mapping or category rules. |
| `EncounterFacts` | Encounter ID, chart number, name, normalized sex/age, source state code and normalized state. Consultation completed and payment completed are distinct. Required fixed raw reception qualifiers added in the parity stage. |
| `OrderKey` | Encounter ID, order date, order number and sequence as separate fields. Not a lifetime identity or an accession-number replacement. |
| `OrderFacts` | Key, source order code/type/department, source state code and normalized state; optional exact-decimal quantity/days/frequency behind a separate evidence gate. Required fixed raw order qualifiers added in the parity stage. |
| `ReceptionQualifiers` / `OrderQualifiers` | Immutable exact Y/N facts: hold_yn/hold_opd and dc_yn/act_yn. No clinical interpretation, defaults or arbitrary qualifier dictionary. |
| `SourceSnapshot` | Validated complete scope, mapping revision and immutable encounter/order facts, including cancelled encounters, fee rows and no-order encounters. |
| `SourceObservation` | Full snapshot, observation ID, changed/added facts and missing keys. Missing means absent from the complete scope, not clinically cancelled. |

All field aliases are proposed projections, not new production SQL columns. Optional
structured values have no clinical dose/unit conversion; their source meanings still
need review. DOB, resident ID, phone, address, diagnosis, notes, arbitrary extra fields
and unverified source-event timestamps are rejected. Only `observed_at` is recorded.
Routine representations are redacted and summaries contain counts/status only.

Normalization rejects unverified keys/states/coverage/consistency/closure, failed or
partial reads, unknown state codes, duplicate/orphan keys, invalid fields/numbers
and oversized results (more than 10,000 encounters or 100,000 orders). It never
truncates a result into an authoritative day. Numeric guards bound exact-decimal
representations; they are not vaccine, fee or clinical eligibility rules. Evidence
flags are reader assertions, not independent proof of completeness or DB closure.

`SourceLedger.observe` advances a memory-only baseline after whole-input validation,
independent of any destination acknowledgement. Identical latest observations reuse
their ID; later observations can proceed without either receiver. Every result keeps
the full snapshot for eventual recovery, not just deltas. Stale/conflicting reads,
changed chart identity for an existing encounter, or a changed mapping definition/
revision cannot advance that baseline. Source/projection/day scopes are separate.
Two snapshots are retained by default; restart or eviction requires full reconciliation
and never creates a disappearance event. There is no persistent ledger or outbox.

Synthetic tests cover same-key edits while paid, explicit cancellation versus missing
rows, reused keys with different contents, completion/payment/hold/cancel/restore,
unchanged active child orders, fee preservation, privacy, retry, scope isolation,
mapping drift and incomplete reads. Mocked DB tests check cursor/connection cleanup
before source processing and another queued read finishing while processing waits.
Real database access, network publishing and native input are not part of this stage.

Verification: **120 new source-model cases** and **528 total targeted tests passed**
in 65.22 seconds, including the legacy Orders shadow, shared reader, imports, PACS
polling/refresh/delivery, flu reporting/diagnostics, patient-context API and PACS docs.
Tests used temporary application data, mocked DB/network/input and isolated test
mutexes. This was not a full repository run or live-source validation. Relative
documentation links and tracked/new-file whitespace checks also passed.

Remaining gates: review this internal projection with the receiving repositories,
verify all required source fields and complete-day semantics, implement a bounded
read through the shared coordinator, then separately approve live shadow validation.
Do not activate the old board serializer or replace the existing PACS imaging query.

The [2026-10-03 contract review](kaoseghis-emr-contract-review.md) records receiver
field gaps and the next acceptance checklist. The shared model lacks PACS-specific
accession/schedule/routing data; a separate projection is required. Raw state
qualifier meanings and durable delivery ordering also remain unresolved. The corrected
host is `zin@kaosclinic`, repository `/srv/projects/KaosOrders`, inspected at
`b5f7ccd8257f29235c90b11499b8ed352fc06d0d`. Its existing v1 per-encounter/category
API cannot accept the shared day snapshot or preserve its full state/edit facts.
The review records migration and receiver-test gaps; remote code is unchanged,
running deployment compatibility is unverified, and the reader gate is not passed.

## Synthetic Contract Parity: 2026-10-04

Compared against `zinsss/KaosOrders` at exact commit
`7c9275fb74680f46e4d459c821c7d501758c6b1c` in a temporary detached checkout,
without changing the receiver or this repository's branch/history. The Windows
base and remote `main` were both `c6b9bc9490d9d84d1e19faabfd0c03c5d25e1cde`.

`core/kaosorders_normalized_source.py` provides `serialize_normalized_source` with
explicit `SyntheticDeliveryMetadata` (clinic ID, batch UUID, epoch, revision) and
`synthetic_fixture=True`. It has no defaults for delivery identity/cursors, state
allocator, settings, persistence, IO, logging, network or runtime imports. It can
only serialize already detached, validated source facts after physical DB closure.
It does not read or call either receiving system.

- Required raw qualifiers are retained exactly, validated as Y/N and compared as
  facts. State meanings still come solely from the explicitly supplied policy;
  qualifier values do not establish administration/completion or resolve code 10.
- Explicit `None` sex is now representable as contract null. Existing blank sex
  remains a distinct source value and fails serialization with `unverified_sex`.
  No real demographic mapping or age convention is approved by a synthetic null.
- All rows remain, including no-order encounters, all six reception states,
  cancelled parents with active children, cancelled child rows, fees and unclassified
  catalog entries. No category, display detail, visibility, fee or PACS rules exist.
- Four-part order keys remain separate fields. Encounter IDs and full keys determine
  canonical row order. Exact Decimal values become fixed strings with no exponent,
  redundant fractional zeros, negative zero or units; nulls remain explicit.
- The complete object is hashed as canonical UTF-8 JSON with only content_sha256
  excluded, Unicode preserved, sorted object keys, compact separators and no NaN.
  Exact full/empty fixture parity and validation by the pinned receiver parser passed.

The [field compatibility and evidence table](kaoseghis-emr-contract-review.md#field-compatibility)
records limits, digests, blocked source facts and the next receiver handoff.
Fixture [provenance](../tests/fixtures/normalized_source_v1_provenance.md) pins the
reference commit and unchanged synthetic JSON files. Invalid source/metadata values
produce fixed redacted reasons. Output JSON is not safe to log merely because its
input model representations are redacted.

Verification: **317 focused tests** passed, then **2,424 tests in the full isolated
Windows suite** passed. The pinned KaosOrders parser/reconciler accepted the exact
full/empty outputs and passed synthetic digest/retry/edit/day-isolation/tamper checks.
No live source, native input, printer or receiver API was used. See the contract
review for isolation details; these results are not production-read evidence.

This does not approve an endpoint or token. Never send this payload to
`/api/v1/order-snapshots`. Durable source_epoch/revision allocation, retry storage,
restart/ack ordering, authenticated scopes and mapping migration remain unresolved.
The complete-day reader stays UNAVAILABLE; source coverage, code/qualifier meanings,
sex/age, numeric units and true event-time semantics need separate evidence. No
production query, publisher, settings, trigger, PACS change or deployment was made.

## Closed-Hours Aggregate Inspection: 2026-10-04

`tools/inspect_source_evidence.py` exposes only fixed schema, day, reception and
reception-shape operations with
explicit approval and a supplied clinic date/expected population. It has no CLI
SQL input, startup importer, timer, settings writer, persistence or publisher.
The new `eghis_db.run_verified_evidence_query` entry point keeps the PostgreSQL
driver exclusively in the existing shared connection boundary. Existing
`run_readonly_query` and its consumers are unchanged.

The inspection uses a 3-second connect timeout, 2-second statement timeout, and
verified read-only/read-committed session. Session settings are checked before
the source statement. Cursor and physical connection closed flags are required
before aggregate validation; uncertain physical closure uses the existing reader
safety stop and retained mutex. No write is attempted to test restrictions.

The fixed day statement reads reception membership and child/order-date crosschecks
in one PostgreSQL SELECT/CTE snapshot. Separate dates and the catalog preflight are
separate observations, never combined into a claimed transaction snapshot. Under
[PostgreSQL 9.2 read-committed semantics](https://www.postgresql.org/docs/9.2/transaction-iso.html#XACT-READ-COMMITTED),
a plain SELECT sees one command-start snapshot. This does not establish that the
EMR saved an entire clinical workflow atomically or that all source tables are known.

The source populations use cap-plus-one sentinels (10,000 encounters and 100,000
orders); aggregate output has a 256-row limit plus sentinel. Overflow, missing
summary rows, inconsistent group/count crosschecks, query failure, timeout and
unverified cleanup yield no findings. Even a successful observed-empty scope is
always `authoritative_snapshot=false` and cannot construct a runtime snapshot.
Unknown values are masked server-side; no source identifiers or personal fields
are returned. The reviewed SQL lives in the tool, not diagnostic logs/reports.

Three approved live operations completed: catalog preflight, populated 2026-10-02,
and operator-confirmed closed 2026-10-03, all KST. All verified read-only mode and
cursor/physical closure before interpretation. Only sanitized aggregate/schema
findings are recorded in [source evidence](kaosorders.md#controlled-aggregate-source-evidence-2026-10-04).
No source ledger, serializer, outbox, trigger, settings, HTTP, PACS, board, deployment
or running application was touched. Source mapping/age/membership gates remain open.

Verification: 239 focused and 903 broader related mocked tests passed. The full
offscreen suite had 2,561 passes and 26 label/layout failures, all reproduced at
the untouched starting commit; see the evidence document for details. Existing
runtime consumer implementations and the source reader block are unchanged.

### Demographic Policy Approval: 2026-10-05

The operator approved exact source `M`/`F` as male/female, preserving contract
`M`/`F`, and true database NULL as null. Blank/whitespace and other unverified
values stay blocked, never guessed as null or `O`. Age is completed years (만 나이)
on the encounter's clinic date. This approves the conventions only: safe age
derivation and unobserved source behavior still require evidence. It does not
authorize DOB access, a new live read, or any mapping/runtime implementation.
See the [policy decision](kaosorders.md#demographic-policy-approval-2026-10-05).
Code 10 and other source gates remain unresolved; the reader stays UNAVAILABLE
and serialization/publishing remain disconnected from runtime.

### Reception-Only Evidence: 2026-10-05

The explicit `reception` diagnostic narrows the day scope to grouped
`proc_gb/hold_yn/hold_opd` counts, without querying identities, demographics or
orders. It retains the verified read-only FIFO/mutex boundary and closure proof,
cap-plus-one detection, strict allowlists and count consistency checks. Its
results are never authoritative normalized snapshots and it has no runtime caller.

For the operator-confirmed isolated dummy visit on 2026-10-05, one waiting-state
observation found `10/N/N` (count 1), closing the connection in 0.152 s. The
operator then opened the visit for consultation and reported ready: the second
observation found `20/N/UNREVIEWED` (count 1), closing in 0.0523 s. This supports
the waiting/open-consultation distinction in one supervised transition, not a
complete enabled mapping. `hold_opd` is outside the exact Y/N allowlist; its raw
value was not returned. The strict-Y/N contract cannot yet represent that source
value unchanged. Do not guess a flag or serialize the diagnostic mask.
See the [supervised comparison](kaosorders.md#supervised-reception-comparison-2026-10-05).
Before these live reads, 280 focused and 944 related isolated mocked tests passed.
The shared DB/queue implementation, PACS, publishing and production reader block
remain unchanged.

The separately approved [qualifier shape follow-up](kaosorders.md#qualifier-shape-follow-up-2026-10-05)
adds a `reception_shape` diagnostic, not a normalizer. One read at 00:56:30 KST
observed one `20/N` reception with `hold_opd` shaped as ASCII digits. Only a fixed
shape label and count were returned, never its text, numeric value or exact length.
The existing verified read-only boundary closed the cursor and physical connection
before interpretation (0.0519 s). The shape query was reviewed and passed 529
focused and 996 related isolated mocked tests before that read.

Numeric text does not establish a boolean meaning or a safe raw export. The
strict-Y/N contract is still incompatible with this observed source domain;
unknown qualifier semantics and safe representation remain blocked. No production
model, validator, reader, settings, trigger, delivery, PACS or app was changed.

The operator subsequently put the dummy on hold and reconfirmed isolation after
the overnight gap. One unchanged reception query at 11:27:12 KST found `25/N/N`
(count 1), with read-only mode and cursor/physical closure verified in 0.0545 s.
See [hold return](kaosorders.md#hold-return-2026-10-05). The observed sequence is
waiting `10`, open consultation `20`, then hold `25`; the qualifier was N again
on hold. This does not identify the numeric field's role or establish an exact
transition time. No further live reads or runtime changes were made. The
documentation-only follow-up reran 529 focused mocked tests successfully.

### Qualifier Contract Review: 2026-10-05

Existing schema notes conflict with the observed numeric `hold_opd`; local code
does not define that numeric domain. The pinned receiver at `a837d385ff367e4f72310226d8bc8439fc0c50fe`
requires the field in validation, hashing, comparison and synthetic persistence,
but no business-rule consumer was found. This is reference-code evidence, not a
claim about the deployed server or proof that every source state can ignore it.

The [joint-review proposal](kaoseghis-emr-contract-review.md#qualifier-decision-proposal-2026-10-05)
recommends consistently excluding raw `hold_opd` in a separately versioned future
normalized-source projection, leaving v1 untouched. The source model, mapping,
comparison baseline, serializer and receiver store would need coordinated changes
after agreement; dropping the field from current v1 is prohibited. If it is needed
for verified state semantics, the reader stays blocked pending source definition.

No source queries, receiver edits or runtime changes occurred in this review.
Only docs and 16 synthetic rejection cases changed: 545 focused and 1,012 related
isolated tests passed; the pinned pure receiver parser kept both v1 fixtures valid
and rejected all 30 invalid synthetic cases. Receiver agreement was pending at
that point; the following milestone supersedes that planning status.

### Separate Synthetic V2: 2026-10-05

KaosOrders accepted consistent exclusion of `hold_opd` at
`6837845fc4c691075bab41c6e07ef69e8562580b`. The separate offline
`core/emr_source_v2.py` and `core/kaosorders_normalized_source_v2.py` now implement
contract version 2, projection `kaosorders-all-orders-v2` and synthetic mapping
`synthetic-v2`. V1 model, normalization, fixtures, serializers and outbox are unchanged.

V2 requires only `hold_yn` in encounter qualifiers and exact Y/N `dc_yn` / `act_yn`
in orders. Excluded and extra fields fail, not disappear silently. Complete-read
assertions, graph validation, all six states, all child rows, exact decimals and
redacted failures are covered by synthetic tests. Metadata must be supplied
explicitly; nothing allocates durable ordering or migrates v1 pending batches.

The [full/empty fixture candidates](../tests/fixtures/normalized_source_v2_provenance.md)
are ready for independent KaosOrders parser/digest parity, not production intake.
See [compatibility and next handoff](kaoseghis-emr-contract-review.md#synthetic-v2-sender-2026-10-05).
The real reader stays UNAVAILABLE. Source completeness, full state/flag semantics,
safe age derivation and delivery/enrollment gates remain unresolved. No live reads,
PACS changes, settings/triggers, publishing, endpoint, token, deployment or restart.
The existing `/api/v1/order-snapshots` route remains prohibited for this payload.

## Observation-Only Probe

`core/emr_signal_probe.py` starts with runtime services, not workspace construction.
No new UI is added. Launcher status lines distinguish `F6`, `F7`, `F6 button`,
`F7 button`, `F6 activation (UIA)`, and `F7 activation (UIA)`, followed by the
chart number and snapshot age when identity is available.
Chart-field UIA events and sampled chart changes also appear here as distinct sources.

- The existing EMR connection supplies the process, root window, and treatment
  window. Keyboard capture requires focus inside the treatment child, not merely
  the EMR process. Claim-page F7, other apps, modal dialogs, modified keys,
  injected inputs, and held-key repeats are excluded.
- Button capture uses exact `BtnF6`/`BtnF7` UIA IDs under the treatment window,
  then native HWND hit-testing for a matching left-button press and release.
  Dragging off a button is not a click. A first click activating EMR may show
  chart unavailable until a fresh treatment-context snapshot is available.
- An additional passive UIA listener subscribes to `UIA_Invoke_InvokedEventId`
  on each exact, already-discovered `BtnF6`/`BtnF7` element (`TreeScope_Element`).
  It does not invoke the control. Subscribing successfully does not prove that
  the eGHIS provider emits this event for either keyboard or mouse activation.
  Both original input listeners remain enabled for comparison; duplicate lines
  are intentional in this diagnostic phase.
- Button UIA event callbacks verify only cached sender metadata (process, automation
  ID, HWND, control type), then enqueue an observation from the existing chart
  snapshot. They do not read the sender's text, query the DB, scan a tree, or
  request a fresh patient read. An unverified sender is reported once per
  subscription without any raw provider details or patient data.
- An activation can be delivered after a dialog opens or an action finishes.
  Existing subscriptions remain while the connected buttons still exist, even
  when modal focus temporarily prevents chart sampling. The activation is shown
  without a chart when no fresh snapshot is available. UIA snapshot identity is
  provisional too: event delivery is not a guarantee of pre-action timing,
  successful order completion, or a committed DB change.
- Chart discovery uses the latest operator-captured screen point `(205, 115)`. The point
  must belong to a visible Text control in the connected EMR window and process.
  The background worker reads its current UIA Value/Legacy/Name using the same
  helper as the capture inspector, approximately every 250 ms. It never opens
  patient information. A native window caption is not used as chart identity.
  Native hit-testing may return the text's parent: the UIA target must still
  contain the point and have verified EMR ownership, but HWND equality is not
  required. Virtual targets use a bounded ancestor check, not a tree scan.
  Ownership follows a bounded native parent/owner chain to the connected EMR
  root, with a matching process at every step. Same-process membership alone is
  insufficient. This also accepts eGHIS-owned header windows that are not children
  of the main window; the keyboard treatment-focus restrictions are unchanged.
  The verified UIA control is cached by connection scope, runtime ID, and native
  owner. Subsequent reads follow that control's current bounds, not the old pixel.
  A newly discovered control must first expose a numeric chart value before it
  is cached or subscribed. Focus loss and a temporarily empty known chart discard
  the sample but keep that verified control. Non-numeric text invalidates the cache
  and detaches its property listener; it cannot keep reporting from that control
  indefinitely. Failed discovery/read attempts retry at most once per second in
  the worker, with no tree scan or input injection. A new EMR scope can retry immediately.
  Stale/hidden controls, provider failures, changed identity, and connection changes
  trigger reacquisition. Every successful sample reads fresh text and revalidates
  identity and focus; a previous chart number or property event is never substituted.
- UIA discovery runs only in that worker, is scoped, and caches button handles.
  Missing buttons retry at most every five seconds. Input callbacks do no UIA
  searches, DB reads, text reads, synchronous UI updates, or input injection.
  Both listeners use `suppress=False` and always pass input through.
- UIA registration and removal run on the same non-UI MTA sampling worker.
  EMR reconnects/button recreation replace subscriptions; unchanged samples do
  not repeat registration. Failed registrations retry at most every five seconds.
  A UIA listener failure leaves the keyboard/mouse probe running. Cleanup failures
  disable the UIA listener instead of accumulating subscriptions. Removed handlers
  reject late callbacks. This code never calls process-wide `RemoveAllEventHandlers`.
- F6/F7 snapshots older than 750 ms, missing/non-numeric values, and uncertain contexts
  are not presented as chart identity. The status says `Chart unavailable` with
  a non-patient reason: expired snapshot, unreadable/non-numeric UIA text,
  discovery point outside the EMR hierarchy, changed focus/target, or provider/access
  failure. The discovery error does not assume that a window is covered.
  A failed read is not mislabeled as an expired snapshot. Both keyboard and
  button observations preserve the pre-action failure reason. Sampling time is
  measured before the UIA read, so a slow provider cannot make old text look fresh.
  Even a recent snapshot is provisional: a patient switch between sampling and
  the input can race. Live validation is required before downstream use.
- Observations remain only in memory and the bounded existing status text area.
  No chart numbers are written to files, databases, or network destinations.
  Queue overload is reported, rather than silently implying complete coverage.
- F6/F7 input observations do not request DB work. Each physical press/click
  remains visible for diagnosis; only verified clears feed the refresh path below.

After restarting KaosEghis, connect EMR and verify the four inputs during normal
work. Compare every displayed chart number with the patient on screen, including
rapid patient changes and F7 confirmation/print dialogs. Also test claim-page F7,
EMR restart/reconnect, and launcher drag/drop. Do not trigger clinical actions just
to exercise the probe. Changed screen placement/DPI may invalidate the chart point;
this diagnostic is not yet an authoritative patient-identity source.

The first live probe reported all sources but no chart. Its original reader
required the UIA HWND to equal the native hit and then used only WM_GETTEXT.
These assumptions have been removed, with regression tests for UIA-only values,
parent/virtual hits, fresh values on cached controls, and rejected context changes.
The corrected reader still needs live validation in the elevated clinical app.

On 2026-09-23, real chart Name-change events arrived while F7 repeatedly reported
the point as "outside EMR or covered." Read-only native diagnostics found that the
header Text window belonged to eGHIS through an owned host window, not an IsChild
relationship with the main window. On that live hierarchy, the old child-only
check returned false and the bounded parent/owner check returned true. No patient
text was read or input sent for this diagnostic. Regression tests cover the owned
host, foreign/unrelated windows, bounded walks, moved cached controls, focus loss,
fresh values, and replaced runtime identities. Post-restart F7 chart identity still
requires observation during ordinary clinical work.

A later capture at `(205, 115)` confirmed a numeric Text control with matching
Name and Value while the probe had reported persistent non-numeric cached text.
Both the old and new points hit the same native label during the read-only check,
so the exact original misbinding was not reproduced. The confirmed code defect
was indefinite reuse of a non-numeric cached control. Discovery now uses the
latest captured point, nearer the label's left edge, and invalid text forces
bounded reacquisition. No numeric HWND/Automation ID or patient value from the
capture is saved. Tests cover rejected initial blank/text controls, cache replacement,
listener removal/late-event rejection, narrow labels, and retry limits.

### Activation Comparison

During normal clinical use, look for `UIA activation subscribed: F6, F7` first.
Then compare each ordinary F6/F7 press or button click with the corresponding
`F6 activation (UIA)` / `F7 activation (UIA)` line. Test both keys and both buttons,
including F7 confirmation/print dialogs and an EMR restart. Do not send orders
solely to exercise the probe. Record missing, duplicate, or delayed UIA events
and check the chart snapshot against the patient on screen. Only after that
validation should replacing either original listener be considered.

### Chart-Change Comparison

`core/emr_chart_probe.py` subscribes to Name, Value, LegacyName, and LegacyValue
property changes on the exact verified Text control already found by the chart
reader at `(205, 115)`. It does not save or depend on the numeric Automation ID.
The binding is identified by the current EMR scope and UIA runtime ID. Reconnects
or replaced controls remove the old handler and bind to the newly discovered
instance, including virtual UIA controls without their own HWND. Late callbacks
from a replaced binding are ignored.

The chart listener uses the same MTA worker as the button listener for all
registration/removal. Failed subscription retries are bounded to five seconds;
cleanup failure stops this listener without accumulating handlers. Callbacks use
cached process/runtime/type metadata and the event's new-value payload, never a
fresh UIA text read. Invalid values are not displayed, and provider exception text
is not logged. An already-verified chart field remains subscribed when cleared;
an unknown empty Text control is not subscribed before numeric verification.

Launcher status distinguishes:

- `UIA chart change subscribed`: listener registration succeeded, not proof of delivery.
- `Chart field event (UIA Name)` (or Value/LegacyName/LegacyValue): a genuine
  property callback, showing only a numeric chart value, a cleared-field status,
  or a redacted unavailable-value status. Multiple properties may report the same change.
  Rejected payloads distinguish missing values, non-text values, non-numeric text,
  and numeric text exceeding the 20-digit limit. No rejected content is displayed
  or coerced to a chart number. A missing payload is not a confirmed cleared field.
  These messages alone do not say whether the independent sampled/F6/F7 chart
  read succeeded; compare the following sampled and input-signal lines.
- `Chart observed (sampled)`: the existing reader's initial/reconnected baseline.
- `Chart changed (sampled)`: that reader saw a different number; this is not a UIA event.
- `Chart field empty (sampled)`: the reader verified an empty field. Focus loss or
  a read failure is not presented as a cleared patient.

During normal patient changes, compare UIA lines with sampled lines. A value set
before the first subscription may have only a sampled baseline. Same-patient
reloads may not change any chart property. Neither kind of line proves that all
patient fields/orders have finished loading, and property events do not overwrite
F6/F7 snapshots. Verified clears and sampled numeric loads/changes can request a
day-wide PACS refresh; raw numeric events wait for a verified sample. Clear/change events invalidate pending memo
checks; subsequent sampled chart identity schedules a delayed alert check as
described below. Live logs now confirm eGHIS Name-change event delivery, including clear
and numeric transitions, but not complete coverage or patient-load completion.
A real property change on an isolated, hidden Windows test field also verified
the callback path. Button activation-event delivery remains unverified.

### Chart-Triggered PACS Refresh

- A previously verified numeric chart changing to a verified empty field requests
  refresh. UIA properties and sampled clears are deduplicated under the patient
  lock. Missing/unreadable text, focus loss, and initial empty fields are not clears.
- A verified numeric sample requests refresh when first observed or changed,
  including the same patient after a confirmed clear. Repeated samples of the same
  number and temporary unreadable/focus gaps do not create duplicate load requests.
  Patient identity still uses the 750-ms freshness rule, but day-wide refresh does
  not: no departing chart number is passed to the database reader.
- Wait two seconds after the latest clear/load in a burst, then emit a separate Qt
  request. No F1, caret readiness, focus, typing, or mouse input is needed.
  A new patient loading cannot redirect the request to another patient's query.
- Each request retains its event date across midnight. Automatic refresh does
  not use an operator's currently selected historical worklist date. Poll Now does.
- The PACS worker uses the existing imaging query and cancellation reconciliation,
  then existing KaosPACS delivery. It does not infer completion/cancellation from
  a clear and does not yet read all orders or reception statuses.
- Each clear also schedules one follow-up at 30 seconds after that clear, not
  after the first read finishes. A new load neither cancels nor postpones it and
  does not create its own follow-up. A later clear replaces the pending deadline
  with its own +30 seconds. Neither delay proves that EMR has committed.
- Fast reads and follow-ups have separate pending slots per day. If both are due,
  one read covers both; a read begun before the follow-up deadline cannot consume
  it merely by finishing late. Follow-ups do not recursively schedule follow-ups.
- Only one PACS operation runs at a time. Further requests coalesce by day and
  remain pending rather than being dropped during an active refresh.
- Event mode performs startup and detected EMR-reconnection refreshes, each with
  a +30-second follow-up. F6/F7 keys, clicks and activation events remain diagnostic
  only; they do not request database reads.
- A safety check requests today's refresh after five minutes without a successful
  current-day read, even if no more chart events arrive. A five-second local timer
  checks the deadline only, not the database. It does not require EMR focus or a
  chart signal. In-flight/queued work for today coalesces with this check.
- Safety-check failures retry after 60, 120, 240, then 300 seconds (capped there).
  A successful current-day read resets the five-minute deadline and backoff;
  events, historical reads and failures do not count as success. Delivery errors
  returned by KaosPACS do not invalidate a successful source read. Day rollover
  requests the new day without discarding the previous day's pending follow-up.
- Chart requests are independent of the bounded diagnostic queue. Disconnects,
  changed EMR scope, stop, invalid timing, or a 120-second UIA worker stall discard
  pending trigger candidates. Startup/reconnection and safety reads reconcile missed work.
- Existing automatic-refresh enable/disable and PACS dry-run settings are honored.
  The default `pacs_refresh_mode=chart_clear` (shown as `Chart clear/load`) disables
  the legacy regular polling timer. Disabling automatic refresh also stops the
  safety timer and cancels pending automatic work; Poll Now remains available.
  `timer` is an explicit rollback option in PACS Operator Mode or Settings > PACS.
- Launcher status shows each refresh's reason, date, outcome and total elapsed
  time, plus separate health-check, source-read, local-update and delivery timings.
  Source time includes serialization/connection waits, not just SQL execution;
  total begins at dispatch, excluding the trigger's settling delay. PACS shows the
  last successful source read time; source failures do not advance it. Delivery
  failures do not erase source-read success. Memo timing remains unchanged.
- Delivery now skips successfully acknowledged unchanged payloads. New/edited
  payloads and failed deliveries remain eligible; legacy rows establish a baseline
  with one successful send. See [PACS changed-only delivery](kaoseghis-pacs.md#changed-only-delivery)
  for migration, cancellation, invalid-row and manual-resend behavior.

Before relying on this during normal work, verify F6/F7 keys and buttons, the last
patient of the day, fast patient switches, edits/deletions, and offline recovery.
Compare PACS after the follow-up with Poll Now. The safety check improves recovery
but does not guarantee immediate delivery, especially while the app is closed or
source/destination services are unavailable. Do not create clinical orders just
for testing. No production DB or UI input was exercised during implementation.

### Shared Read Queue (Stage One)

`core/eghis_db.py` routes every existing reader through `core/emr_read_queue.py`.
The one-worker FIFO covers PACS, flu-report, SELECT 1 health checks, patient-context
API calls, and the diagnostic tool. A named Windows mutex additionally excludes
connections from other updated Kaos processes on the machine. It does not block
eGHIS's own connections, or coordinate older versions that bypass this helper.

No connection pool is used. Cursor/connection cleanup is inside the exclusive
operation, on success and failure, before local SQLite work or HTTP delivery.
Read-only session setup must succeed. Default connect and statement limits are
five seconds; flu-report retains its existing shorter three-second statement limit.
The in-process queue is bounded to 64 callers; mutex waiting is bounded to 60 seconds.
Neither SQL nor connection strings nor patient data are logged by the queue.

If connection close raises, is unavailable, or the driver still reports an open
connection, the read fails and the coordinator latches unhealthy. Queued and new
reads are rejected without connecting. The worker retains the Windows mutex so
other updated processes cannot open a second source connection; their lock wait
times out. An abandoned mutex is also an uncertain-ownership failure, not permission
to connect. A cursor-close failure still attempts connection closure; if physical
connection close succeeds, the read fails but subsequent work may proceed.
Nested reads from inside the worker are rejected instead of deadlocking. Queue
capacity is released when the submitted job finishes, not when its caller stops
waiting.

There is no automatic cleanup-failure reset. Operator recovery must establish that
old Kaos-managed connections are gone before restarting the affected clients. The
unhealthy latch and retained mutex are process-lifetime safeguards, not a durable
cross-reboot recovery record. Older agents that bypass this helper are not covered.

#### Windows Checkout Verification (2026-09-30)

The real `E:\Kaos\KaosEghis` checkout was clean on `main` at
`44e3d8f75560321aa3cc7a7e6f2b55131577e58d`, matching the remote `main` head before
this coordinator hardening. No pull, merge, reset, stash, or data-file changes were
needed. Both this document and `docs/kaosorders.md` were present.

Source inspection confirmed the shared reader, global Windows mutex, chart clear/load
trigger, two-second debounce, clear +30-second follow-up, and five-minute
successful-current-day-read safety check. All existing source consumers enter via
`run_readonly_query`: PACS orders/existence checks, flu reporting, patient context,
health checks, and the PACS diagnostic tool. Future KaosOrders reads must use this
same boundary; no KaosOrders adapter or new production-table query was introduced.

Mock tests exercise FIFO ordering across consumer categories, a maximum of one
connection through delayed cleanup, setup/query/fetch/cursor errors, uncertain
connection closure, queue capacity, nested calls, actual consumer entry points, and
post-close result processing. Separate-process lock tests use unique test-only mutex
names. The test suite rejects unmocked PostgreSQL connection attempts by default;
tests never acquire the running clinic app's production mutex.
The focused coordinator/refresh/source-read run passed 111 tests; the broader
EMR/PACS/flu/patient-context regression run passed 474 tests using temporary local
data and mocked source connections.

This verification does not certify production DB privileges or eliminate all future
broker work. Configured legacy SQL still uses the existing safety gate; a reviewed,
parameterized operation-only API and least-privilege credential verification remain
acceptance gates. The queue does not yet offer a per-job queue deadline or active
driver cancellation. A stuck driver can keep ownership indefinitely; process-isolated
bounded recovery is not implemented. No live source queries, UI actions, or claim
that the flu-report slowdown is fixed were part of this verification.

This is the foundation, not the full future broker below. Pending refresh jobs are
in memory; durable broker queues, all-orders snapshots and reception status semantics remain future
work. Serialization may reduce contention but does not prove the flu-report/EMR
timeout issue is resolved.

#### Bound Query Parameters (2026-10-01)

`run_readonly_query` now accepts an optional keyword-only `params` argument:
tuples/lists for `%s` placeholders, or mappings for `%(name)s` placeholders.
Values are passed separately to the driver's `cursor.execute(query, params)`;
the helper does not interpolate, quote, or format them into SQL. Parameters are
for values, never table/column names or arbitrary SQL fragments. Queries must
still be fixed, reviewed read operations under the existing safety policy.

The parameter container and its values are copied before queue submission so
later caller edits, including nested list edits, do not change a waiting request.
Other top-level containers (including bare strings and generators) fail before
queueing or connecting. Values must support copying and driver adaptation.
Calls omitting `params` (or using `None`) retain the original one-argument execute
path, including literal percent characters in existing SQL. Empty containers are
passed to the driver as supplied parameters, not treated as missing parameters.

Bound and legacy reads share the same FIFO, machine-wide mutex, read-only session,
finite timeouts, cursor/connection cleanup, and uncertain-close stop policy. The
new argument does not introduce connections, retries, timers, logging, or pooling.
PACS, flu, health, context and diagnostic call sites were not migrated in this
stage. No live source read or app restart was performed to verify this change.

Focused mocked tests passed **162 tests**, covering existing consumers and shadow
logic, separate parameter forwarding, literal SQL-like values, supported value
types, caller mutation during queue wait, invalid containers, driver adaptation
errors, simulated query timeout, all cleanup failure stages, and blocked subsequent
reads after uncertain connection closure. Test-only Windows mutex names and a
default rejection of unmocked PostgreSQL connections keep production isolated.
The full isolated repository suite passed **1,950 tests** in **193.65 seconds**.
This API capability does not implement or approve the future all-orders day query.

### Delayed Patient-Memo Alert

With `Enable *** patient-note alert` enabled, the shared chart observer schedules
one memo check **five seconds after observing a new patient context**. The existing
red, always-on-top popup and configurable memo target are reused. The default memo
Automation ID remains `TreatmentPtntMemo`.

- The alert no longer starts its own 1.5-second chart polling loop. It does not
  resolve the old chart-target settings; it uses the shared sampled identity.
- Duplicate numeric UIA events/samples do not restart the timer or repeat a check.
- A clear or different patient cancels pending work and clears the old alert.
  A clear followed by the same chart number is a new visit and gets a new check.
- The timer never fires early. A five-second delay is an operator-selected settling
  period, not proof that EMR finished loading every field.
- Memo UIA access runs off the GUI thread, once per context. The shared snapshot
  must still be fresh and identify the same EMR process/window/patient both before
  and after reading. UIA change callbacks invalidate it immediately; samples that
  started before that change cannot restore it.
- Checks are serialized. A slow old read cannot overlap a new one or display a
  stale alert. Stop, disconnect, and settings changes invalidate in-flight results.
- An unreadable memo is unavailable, not a confirmed absence of `***`. There is
  no endless retry or memo polling after this attempt. Reloading the patient or
  saving the alert settings can schedule another delayed check.
- No patient memo contents are logged, persisted, or sent through Qt signals.
  The enabled setting is preserved; installing the change does not silently turn
  a disabled alert back on.

### Resource Boundaries

The UIA activation and chart listeners add no chart polling or database calls.
They reuse the existing two button handles and roughly 250-ms chart sampling.
That sampling still has UIA/provider cost: the whole diagnostic is not event-only.
Pending clear diagnostics only check in-memory deadlines and cached connection
identity. The earlier F1 caret/focus probe and local target lookup have been removed.
Subscriptions are element-scoped, never desktop-wide. Event handlers use a bounded
queue and perform no synchronous UI update. No resource benchmark against EMR's
30-second PACS DB polling has been claimed. Event mode replaces that timer with
clear/load reads, bounded follow-ups and a five-minute successful-read safety
deadline. Whole-day reads and existing delivery can still be frequent during busy work.

The input-hook constraints follow Microsoft's
[low-level hook guidance](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc)
and pynput's [suppression documentation](https://pynput.readthedocs.io/en/latest/faq.html).
The listeners follow Microsoft's
[UIA event guidance](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-eventsforclients)
and [UIA threading requirements](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-threading).
Chart events use the
[property-change callback](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationpropertychangedeventhandler-handlepropertychangedevent).

## Future Broker Scope

The following sections describe the full target architecture, beyond the PACS-only
stage above; they are not a claim that all acceptance gates are implemented.

KaosEghis-emr will be the shared eGHIS connector with separate adapters for
KaosPACS and KaosOrders, plus on-demand flu reporting and patient-context reads.

- Observe F6/F7 and the verified BtnF6/BtnF7 controls without suppressing, replaying,
  or generating those inputs. Signals indicate intent, not successful order saves.
- Capture verified chart identity before the EMR action opens another window.
- Validate the initial and follow-up timing during normal clinical work. The
  earlier per-chart 20-second F7 proposal in [KaosOrders signal capture](kaosorders.md)
  is superseded by day-wide chart-clear/load refreshes.
- Validate source facts and completeness, then interpret verified EMR codes,
  normalize fields and compare source snapshots after connection closure. Deliver
  minimal approved observations through destination adapters; imaging and board
  decisions belong to KaosPACS and KaosOrders respectively.
- Run flu reporting only on explicit request. Prefer small source reads and local
  calculations, subject to exact count/age semantics and validation.
- Serialize source reads through a bounded background queue. UIA observation and
  downstream network delivery must not run while holding an EMR DB connection.

The initial host can be the KaosEghis process; a separate installed service is not
required. Any independently running KaosEghis-pacs agent must also be migrated or
retired at cutover. An in-process queue alone cannot coordinate an external agent.

## Non-Negotiable Source Safety

**KaosEghis-emr must never modify the eGHIS database.**

1. Use reviewed, parameterized read operations, not an arbitrary SQL execution API.
   Do not allow callers to disable the safety policy through query text or settings.
2. Establish and verify read-only session/transaction mode before every source read.
   If that cannot be established, fail closed: no report or order query is executed.
3. Require a dedicated least-privilege database identity with SELECT on approved
   source objects and only the necessary connection/schema permissions. It must not
   be a superuser, owner, or inherit a role that can write. Effective PUBLIC/group
   permissions, temporary-object creation, and function execution also need review.
4. Privilege provisioning is an explicit administrator/vendor task, outside this
   component. Never create roles, grant/revoke permissions, or alter the production
   server automatically. Current credentials have not been certified for this role.
5. No INSERT, UPDATE, DELETE, DDL, source migrations, indexes, maintenance commands,
   writable routines, sequence updates, row-locking reads, or server configuration
   changes. Trusted session-local read-only/timeout setup is the narrow exception
   for connection configuration; it does not change EMR records or schema.
6. A SELECT prefix or keyword blacklist is not sufficient proof of read-only safety.
   Restrict operations at the API layer and enforce permissions at the database.
7. This component observes UI actions only. Existing macros that type, click, or
   chart in EMR remain separate and do not gain a database-write capability.

Local KaosEghis persistence and authenticated downstream API delivery remain
separate operations. "Read-only" here means no application-driven EMR data/schema
mutation, not zero database CPU/I/O or zero internal server disk activity.

PostgreSQL documents the limits of read-only transaction mode and separately
controlled privileges: [read-only transactions](https://www.postgresql.org/docs/9.2/sql-set-transaction.html),
[object privileges](https://www.postgresql.org/docs/9.2/ddl-priv.html).

## Exclusive Connection Ownership

**At most one Kaos-managed EMR database connection may exist at a time.**
Serializing SQL execution while leaving multiple connections open is not sufficient.

- Every source operation uses the same queue: PACS, KaosOrders, flu reports, patient
  lookups, health checks, diagnostics, retries, and fallback reconciliation.
- Reserve the single connection slot before attempting to connect and retain it
  through cursor/connection cleanup. No other connection attempt starts until that
  cleanup completes successfully.
- An on-demand flu request arriving during another read stays queued with no DB
  connection. Show a queued status without blocking the GUI; do not preempt the
  active operation, open a second connection, or bypass the queue on timeout.
- A cancelled or expired queued request never connects. Cancelling an active request
  does not release the slot until its connection has actually been closed.
- If closure is uncertain or fails, mark the manager unhealthy and block new source
  connections pending recovery. Do not open a second diagnostic connection to probe
  the first while ownership remains unresolved.
- Multiple KaosEghis instances and legacy agents must share the same owner or refuse
  duplicate DB access. Separate per-module/per-process locks are not enough.

This limit applies to Kaos-owned connections. It must not close, block, or reconfigure
the eGHIS application's own connections or connections owned by unrelated software.

## Connection Lifetime

**Close the cursor and physical connection immediately after each bounded source
read finishes, before local computation, UI updates, persistence, or publishing.**

```text
wait in queue / settle timer (no connection)
  -> connect
  -> establish read-only mode and finite timeout
  -> execute reviewed read and fetch its bounded result
  -> close cursor and connection
  -> calculate locally / deliver to consumer
```

- No idle connection pool, cached connection, shared global connection, or open
  transaction between jobs. Cache validated results or metadata, never connections.
- Use nested cleanup so a cursor-close error cannot skip connection cleanup.
- Clean up on success, query/fetch/setup error, timeout, active cancellation, and
  controlled application shutdown. A cancelled queued job must never connect.
- Each job needs finite queue, connect, and query deadlines. Cancellation must not
  merely hide a running request or allow late delivery after the job was discarded.
- A multi-read report closes after each read. Do not hold the connection while
  calculating ages, waiting for the next batch, retrying, or posting downstream.
- Never hold a local SQLite write transaction across a source database operation.
- Cleanup failure is a failure, not successful completion. A stuck driver requires
  an unhealthy state and bounded recovery design; a thread/finally block alone is
  not proof that a non-returning driver has closed its server session. Determine
  whether worker-process isolation is needed before promising hard recovery bounds.
- Record only operation type, queue/read/close timings, and outcome. No credentials,
  SQL, chart numbers, birth dates, names, or raw rows in routine diagnostics.

## Failure and Reconciliation Rules

- A failed, timed-out, incomplete, or unverified read is not an empty order list and
  must never trigger downstream cancellation/deletion.
- Do not infer source completion or cancellation from F6/F7 alone.
- Keep manual/startup reconciliation for missed signals and other-workstation edits.
  Validate key/button capture before replacing the current PACS timer.
- Keep one active source read at a time, coalesce duplicate pending work, and bound
  retries. Flu calculations run after connection closure and do not occupy the DB
  worker. Prevent starvation as well as unbounded queue growth.
- This adapter cannot coordinate eGHIS's own queries; read-only and serialization
  do not establish that the observed flu-related slowdown has been fixed.

## Acceptance Gates

Before enabling the new source path:

- Verify role/session restrictions without attempting writes against production.
  Rejection tests use an isolated test database, including multi-statement and
  side-effecting-operation attempts.
- Prove connections/cursors close on all normal and exceptional paths; verify that
  downstream callbacks start only after closure and idle jobs leave no DB sessions.
- Test cancellation before connect, during execution, and before result delivery;
  shutdown and cleanup errors must not produce late successful results.
- Test concurrency, queue deadlines, duplicate signals, independent patients, and
  slow-query behavior while the GUI remains responsive.
- Assert a maximum live connection count of one, including connection setup, delayed
  cleanup, cancellation, health checks, and multiple callers. Specifically test that
  flu requested during PACS work cannot connect until the PACS connection closes.
- Verify cleanup failure stops queue dispatch and duplicate application/agent
  instances cannot independently acquire another source connection.
- Validate chart identity and both buttons in observation-only mode, including
  unrelated F7 uses such as claim aggregation, modals, EMR restarts, and DPI changes.
- Compare flu totals and age-at-visit boundaries with the established report.
- Define and verify the KaosOrders publish contract before sending patient data.
- Inventory all active EMR DB clients at cutover so no legacy poller bypasses the
  manager. Keep an explicit fallback while signal capture is being verified.

## Existing Foundation

`core/eghis_db.py` already requests read-only sessions and uses nested cursor and
connection cleanup. Flu queries have connection/statement limits. This is useful
groundwork, but not certification of the complete policy above: the reviewed-operation
API, privilege verification, bounded queue/cancellation recovery, and production
validation remain work to do. The stage-one shared queue is implemented as described
above; it is not a separate broker executable.
