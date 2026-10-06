# EMR Source Contract Review

Reviewed: 2026-10-05

Status: **v1 synthetic parity and v2 receiver-only synthetic proofs complete;
production source authority remains unresolved**.
This is not an approved HTTP endpoint, production query or deployment change.

**2026-10-06 scope correction:** [current-day memory-only KaosOrders](kaosorders.md#current-day-memory-only-decision-2026-10-06)
supersedes the prior production durable-projection/outbox/history target. EMR DB
is the only durable patient/order source; KaosOrders resets transient state at
KST day change and reloads today after restart. No historical/date-moving test is
required. The v1/v2 bytes, validators and synthetic stores below remain unchanged;
their durable cursor assumptions must not be silently reinterpreted as a volatile
session protocol. Receiver design acknowledgement is needed before implementation.
Current-day membership/consistency and remaining source gates are still unresolved.
The later same-day clarification excludes cancelled encounters only from the future
Orders projection and retains every non-cancelled encounter, including no-order
visits. All child orders of included encounters remain in scope, including cancelled
orders. Exclusion/restoration must be recognized from verified source states and
applied only through complete successful snapshots. This narrows the proposed
session scope, not the unchanged shared v1/v2 models, fixtures or PACS behavior.
The test-only [current-day aggregate operation](kaoseghis-current-day-counts-proposal.md#observed-checkpoint-2026-10-06)
was subsequently run once after passive UI reading and operator confirmation of
today's date. Its 263 code-40/N and four code-50/N candidates match the visible
completed/cancelled tab totals. The 263 include 118 candidates with no matching
child in the inspected table, not proof of no orders elsewhere. Physical closure
was verified in 0.0733 s. No excluded qualifier, patient identifier or demographic
was returned. This sampled match does not approve a production state mapping or
prove child/save completeness; the reader and all delivery remain blocked.
The following [order-coverage checkpoint](kaoseghis-order-coverage-proposal.md#approved-observation-2026-10-06)
was explicitly approved and run once at 20:52:15 KST after 118 mocked tests passed.
Its 938 linked children and 938 today-dated orders agree, with zero key/link
anomalies; 267 receptions split into 145 with children and 122 without. Physical
closure was verified in 0.0731 s. This does not prove absence of alternate order
storage, resolve save consistency or change the contract/source reader block.
The [later catalog-only storage review](kaoseghis-order-storage-review.md)
found 60 structurally plausible candidates but SELECT capability on only the
existing doctor-order object. None of the other 59 has table- or column-level
SELECT. This is a concrete limit on investigating alternate storage, not proof
that those objects are relevant or empty. No complete source or normalized
snapshot can be claimed from these metadata observations; production remains blocked.
The operator subsequently confirmed that today's national-flu vaccination visits
have no EMR orders. No-order encounters are therefore an expected workflow, not
evidence by themselves of incomplete order storage. Retain them with an empty
order list, without inventing a vaccination order or classifying empty visits as
flu. The 122 total was not attributed entirely to vaccination. Broader access is
not required solely because of that count; other source gates remain separate.
The operator then chose a new no-billing/no-payment EMR item for a disposable
test and clarified [source-faithful display](kaosorders.md#source-faithful-order-display-2026-10-06):
preserve the actual EMR order code/name, not a special national-flu label mapping.
The current offline order facts lack a name field, so a reviewed source-name
field and explicit contract/catalog extension remain design work. No schema,
validator, fixture/hash or runtime is changed by this decision, and arbitrary
clinical text remains excluded. Zero-charge status alone is not a fee exclusion.
The operator reaffirmed the existing UI requirement: clicking a patient grid item
opens all scoped source orders with their original names/codes. Summary categories
or fee exclusions do not prune this complete detail list. A new national-flu item
appears as itself, not as a separate translated label. The missing name field is
an implementation gap against that agreed requirement, not a new UI proposal.
The [source model](kaoseghis-emr.md#offline-source-model-2026-10-03) remains offline.
The subsequent [synthetic delivery milestone](kaoseghis-emr-delivery.md) adds an
isolated local outbox and crash tests, not production storage or transport. The
v1 serializer and pinned fixtures are unchanged.

The [2026-10-05 qualifier decision proposal](#qualifier-decision-proposal-2026-10-05)
was accepted in receiver `6837845`; the separate
[synthetic v2 sender milestone](#synthetic-v2-sender-2026-10-05) implements that
offline projection only. This is not an in-place v1 amendment or live source approval.

The current [controlled source-gate review](kaoseghis-source-evidence-gates.md)
pins receiver `890a4dd4ce992f2598c85557513cd2c70b098a2b`. Its v2 parser,
reconciliation, separate synthetic persistence and receiver recovery tests are now
present. No joint v2 sender recovery or transport exists. All eight source gates
remain unresolved; the initial review added documentation and mocked boundary tests.
The subsequent approved catalog operation is recorded below. Historical sections
retain their original scope;
the linked gate matrix and handoff supersede their earlier next-step wording.
Vendor information is not expected. The separate
[source-structure-v1 evidence](kaoseghis-source-structure-probe.md#approved-observation)
records one approved catalog-only investigation for gate 1 at 23:09 KST on
2026-10-05. It found 4 reception-dependent view links and 3 order-dependent view
links, no selected inheritance/FK links, and verified physical closure in 0.101 s.
The view sets may overlap. No clinical rows/definitions were read, no runtime
importer was added, and no source gate or production snapshot delivery was approved.

The [subsequent metadata follow-up](kaoseghis-source-metadata-followup.md#results)
resolved the overlap: four distinct dependent views, three shared, with 23 other
ordinary-relation links and five recorded routine links. It also found effective
CREATE capability in `public`, despite no detected non-SELECT privileges on the
two scoped source tables. This is a concrete least-privilege blocker; no privilege
was exercised or changed. Both read-only connections closed before interpretation
(0.0717 s and 0.0750 s). No complete source gate is resolved. See the
[operator/admin next decisions](kaoseghis-source-evidence-gates.md#next-practical-decision).

## Evidence Scope

- Reviewed the Windows working-copy source model, source ledger, current PACS
  query/client, and documented supervised source observations. No new EMR reads.
- Read the local `E:\Kaos\KaosPACS` checkout at
  `16d3a94fe3a99a88bc54a3905e25931f6b5863f5`, branch
  `codex/kaospacs-admin-mark-complete`. This is not proof of the deployed version.
- The operator corrected the host to `zin@kaosclinic`. Strict, noninteractive SSH
  found `/srv/projects/KaosOrders`, clean on `main...origin/main`, at
  `b5f7ccd8257f29235c90b11499b8ed352fc06d0d` (initial service foundation).
  Reviewed its schema, ingest handler, SQLite application logic, API/privacy tests
  and architecture/contract/implementation-plan docs. This is repository evidence,
  not verification of the running container/image or a live API test. The earlier
  `zin@kaosgdd` lookup was the wrong host; KaosReception is a separate application.
- No pulls, remote edits, service restarts, API calls, patient exports or publishing.
- Parity stage: Windows `main` was clean at
  `c6b9bc9490d9d84d1e19faabfd0c03c5d25e1cde`; actual remote `main` matched.
  Read `zinsss/KaosOrders` at exact commit
  `7c9275fb74680f46e4d459c821c7d501758c6b1c` in a temporary detached checkout.
  Reviewed `docs/normalized-source-contract-v1.md`, `app/source_contract.py`,
  `app/source_shadow.py`, both golden fixtures, and source contract/reconciliation
  tests. No KaosEghis pull/reset, runtime configuration, commit or push was made.

## Synthetic Parity: 2026-10-04

`core/kaosorders_normalized_source.py` is a pure offline serializer. It accepts a
validated detached `SourceSnapshot`, required `SyntheticDeliveryMetadata`
(`clinic_id`, `batch_id`, `source_epoch`, `revision`) and explicit
`synthetic_fixture=True`. These are caller assertions, not production authorization
or proof of synthetic content. No metadata is generated, persisted or allocated.

The source model now requires immutable, fixed qualifier objects: reception
`hold_yn`/`hold_opd`, order `dc_yn`/`act_yn`. Only exact `Y` or `N` values are
accepted, without trimming, defaulting or inferring state/administration. They
participate in source fact equality and edit detection. Missing/extra fields or
unknown flags reject the entire read. No production mapping has been added.

The serializer rechecks types, exact fields, bounds, parent links, duplicates,
metadata and wire text before producing an allowlisted JSON object. It retains
every encounter and order: no-order, completed, paid, cancelled, fees and
unclassified rows included. A cancelled parent never rewrites child state.
It emits only FULL/complete snapshots, never deltas or disappearance-as-cancellation.
It has no IO/logging/database/HTTP/trigger dependency or runtime importer.

### Field Compatibility

| Source / input | Contract field | Synthetic compatibility / remaining gate |
| --- | --- | --- |
| Constants | `contract_id`, `contract_version`, `snapshot_kind`, `complete` | Exact `kaosorders.normalized-source`, `1`, `FULL`, `true`. Only validated complete source snapshots are inputs. |
| Explicit metadata | `scope.clinic_id` | Direct strict nonempty text, at most 128 characters; no deployment setting added. Authentication binding unresolved. |
| Source scope | `scope.source_id`, `projection_id`, `clinic_day`, `mapping_revision` | Direct values and ISO date; no scope inferred from patient data. Day coverage and mapping rollout remain blocked. |
| `observed_at` | `observed_at` | Offset-preserving ISO timestamp; source observation only, no clinical/edit/payment event time. Clock policy unresolved. |
| Encounter identity | `encounter_id`, `chart_number`, `patient_name` | Direct, `chart_no` renamed only; 128-character limits, no whitespace trimming. No chart-derived visit key. |
| Explicit normalized demographics | `sex`, `age` | `M`/`F`/`O` or explicit null, integer 0-130 or null. Source can retain explicit `None`; blank sex fails with `unverified_sex`, never silently becomes null. Operator approved exact source M/F/null and completed-years-at-clinic-date conventions on 2026-10-05; other source values and safe age derivation remain unverified. No production mapping enabled. |
| Reception code/state | `source_state_code`, `state` | All six states, including distinct consultation/payment completion. Only supplied verified policy meanings; no default production code-10 or compound mapping. |
| `ReceptionQualifiers` | `qualifiers.hold_yn`, `hold_opd` | Required exact raw Y/N facts, immutable and unclassified. Compound clinical meanings remain blocked. |
| `OrderKey` | `key.encounter_id`, `order_date`, `order_number`, `order_sequence` | All four components retained; date is identity, not event time or accession. Same-key replacement remains possible. |
| Catalog facts | `order_code`, `order_type`, `department_code` | Exact source facts, including empty department, fees and unknown catalog entries; no category/detail/fee decision. Padded text is rejected rather than altered. |
| Order code/state | `source_state_code`, `state` | Direct ACTIVE/CANCELLED meaning from supplied policy; no parent-state or qualifier inference. All-category mapping still needs evidence. |
| `OrderQualifiers` | `qualifiers.dc_yn`, `act_yn` | Required exact raw Y/N facts; `act_yn` does not mean administered/performed here. |
| `Decimal` or `None` | `quantity`, `days`, `frequency` | Exact fixed decimal strings or explicit null, no exponent/trailing zeros/negative zero/units. Floats rejected. Existing source bounds (absolute value <= 1e9, exponent -12..12, input length <= 32) remain stricter than the receiver draft; not broadened. |
| Explicit metadata | `batch_id`, `source_epoch`, `revision` | Required canonical UUID text and strict positive integers <= 2^63-1. No defaults or production ordering state; durable allocation/retry/restart remains unresolved. |
| Canonical complete object | `content_sha256` | Lowercase SHA-256 over UTF-8 JSON without only this top-level member: Unicode preserved, keys sorted, separators comma/colon, NaN/infinity forbidden. |
| Source row ordering | `encounters`, `orders` | Encounters sorted by ID, orders lexicographically by complete four-part key. No filtering, truncation or category grouping. |

Both [golden fixtures](../tests/fixtures/normalized_source_v1_provenance.md) were
copied unchanged with exact reference commit and Git-blob provenance. Independent
synthetic source inputs reproduce the complete parsed objects, including nulls,
ordering, numeric strings and these content digests:

- Full: `4173c829519b0884a9cca0a7ee216ee8d6bfa05147427de1a16f638bf2c93030`
- Empty: `d286948d18b2e7b66f86f1a1b6c7931f58cd1753e8572e1338df85f1f37fecef`

The exact reference parser and in-memory reconciler also accepted both outputs in
an isolated temporary environment using its pinned Pydantic 2.13.4. Digest parity,
retry, same-key edit, day isolation and tamper rejection passed without API/DB calls.
This did not install dependencies into the application environment or modify the
receiver repository. The serializer's returned dictionary contains identifiers;
redacted input-model representations do not make the JSON safe to log.

### Verification Results

- Focused serializer/source-model group: **317 passed** in 17.19 seconds.
- Entire isolated Windows test suite: **2,424 passed** in 487.78 seconds. This
  includes existing source-shadow, FIFO/mutex, PACS, flu, patient-context, UIA,
  vaccine, scheduler and other regression groups; no tests were excluded.
- Exact pinned receiver parser/reconciler check: full/empty parity, both digests,
  exact retry, same-key edit, day isolation and tamper rejection all passed.
- Tests used temporary application data, mocked DB connections, test-only mutexes,
  blocked non-test network/WebEngine access, and blocked native desktop/printer
  operations. Main-thread-only garbage collection avoids the known Qt test hazard.
  No EMR access, input, source export, API call, live print or service restart occurred.

The full suite verifies offline compatibility and unchanged existing behavior under
mocks, not production mappings, read permissions or live end-to-end delivery.

### Production Blockers and Handoff

No approved endpoint or token exists. `/api/v1/order-snapshots` remains prohibited
for this payload. No new production query, publisher, persistent outbox, settings,
trigger, board change or deployment is added. The source reader stays UNAVAILABLE.

Source gates remain: complete-day membership/consistency/empty proof, all-category
state mapping, code 10, qualifier combinations, sex/age conventions, numeric units
and event-time semantics. Raw qualifier retention does not resolve these meanings.
Delivery gates remain: durable source epoch/revision allocation, exact retry storage,
authenticated restart/ack recovery, mapping migration, byte limits, accepted days,
TLS/endpoint/credential provisioning, persistent atomic reconciliation and retention.
The serializer does not enforce cross-call cursor ordering; it owns no such state.

Next KaosOrders handoff: review these exact serializer outputs against `7c9275f`,
retain the same synthetic fixtures, and add/confirm receiver cases for every raw
qualifier combination, same-key edits/reuse, disappearance, explicit null versus
blank rejection and the sender's stricter numeric bounds. Resolve durable ordering
and source-evidence gaps on paper before either side adds production transport or
acquisition. Keep the existing v1 API and board unchanged.

## Delivery Review and Offline Milestone

Read-only SSH review of the three current uncommitted receiver documents on base
`7c9275f` completed without changing the receiver repository. Sender-side design
decisions and the operator-approved offline queue milestone are recorded in
[delivery foundation](kaoseghis-emr-delivery.md). A supplied synthetic epoch spans
its producer's clinic days; revisions are allocated independently per day in a
transaction with immutable sealed bytes. Exact retries do not reserialize or reread.
Refresh requests coalesce behind one unresolved batch, with a pre-read generation
ticket preserving requests that arrive during a read or pending delivery.

Internal receipts check scope, mapping, receiver generation, epoch/revision,
batch ID and digest before atomically releasing pending data. They do not define
an approved HTTP acknowledgement or authenticate a server. The synthetic store
has no runtime importer, default path, production encryption/ACL provisioning,
recovery handshake, transport or retry worker. Missing/corrupt state fails closed.

The previous parity-stage verification remains valid; the new queue uses those
unchanged fixtures. Complete-day source evidence and all production delivery gates
remain unresolved. Next receiver work is isolated persistence/receipt/recovery
testing, not a new route, board integration or use of `/api/v1/order-snapshots`.

## Synthetic Receipt Review: 2026-10-04

Historical findings at `40c6a49`; the retry blocker below is resolved for the
synthetic cases in the [02acc8a recheck](#synthetic-acknowledgement-recheck-2026-10-04).
The production recovery and source-evidence decisions remain open.

Sender baseline: `d298ac4c19068f6cf32964e36f75ce83850705bf`.
Receiver reference: `zinsss/KaosOrders` exact commit
`40c6a496385a4c6fd48c6532554748db23d4e3cb`, inspected in a new temporary detached
checkout. Reviewed `app/source_store.py`, `tests/test_source_store.py`, and the
contract, implementation-plan and architecture documents. Neither store, validator,
serializer, fixture nor runtime behavior was changed for this compatibility review.

### Internal Field Parity

| Receiver type | Sender type | Exact field order and value shape |
| --- | --- | --- |
| SyntheticReceipt | SyntheticAcknowledgement | outcome, receiver_generation, request, committed; committed can be None. |
| ReceiptCursor | BatchCursor | scope, source_epoch, revision, batch_id, content_sha256. |
| ReceiptScope | DeliveryScope | clinic_id, source_id, projection_id, clinic_day, mapping_revision. |

The scope day is a Python date; IDs/digests are strings and ordering values are
strict positive integers. Receiver generation and batch IDs use canonical UUID
strings. This is field/value compatibility, **not Python type interchangeability**:
the sender requires its exact dataclass types and rejects an actual foreign receipt
object. A future approved boundary must explicitly validate/reconstruct sender
types; no cross-repository runtime import, converter or network schema was added.

### Actual Receiver Semantics

An isolated probe executed only the reference's synthetic contract, authorization
model and store, with networking blocked and temporary plaintext fixture databases.
No FastAPI/runtime database/config modules were imported. It confirmed:

| Rule | Observed result at 40c6a49 |
| --- | --- |
| Producer epoch | Shared by clinic/source/projection across days. |
| Day revisions | Independent; a new day or transition to the current/newer epoch requires revision 1. |
| Established day | A newer complete revision may skip intermediate revisions. |
| Exact retry after ordinary restart | duplicate, without replacing the projection again. |
| Older revision/epoch, previously unseen batch | stale, with that day's current cursor or None when the day is absent. |
| Equal ordering position with changed batch/content | conflict. |
| Reused batch ID / in-place mapping change | conflict; mapping is fixed across days of a producer. |
| Unsupported restart ordering | resync_required, with current cursor or None. |
| Observation-clock regression | A newer revision with an earlier observed_at is accepted; observation time is not ordering authority. |

**Compatibility blocker: historical duplicates hide newer receiver state.**
In [source_store.py at the pinned duplicate branch](https://github.com/zinsss/KaosOrders/blob/40c6a496385a4c6fd48c6532554748db23d4e3cb/app/source_store.py#L477),
a recognized historical batch returns `duplicate(request=old, committed=old)`
before current ordering checks. The probe accepted revision 1, then revision 3,
then retried revision 1: the projection remained at 3, but the receipt reported 1
as committed. The same historical retry still returns duplicate after a newer
producer epoch is accepted. Therefore the stale rule above has an exact-retry
precedence exception; it is not an unconditional fence for old generations.

The sender rejects a success receipt that *reports* a different current cursor.
It cannot detect a newer cursor omitted from the receipt, so a rolled-back sender
with that old batch pending would accept the historical duplicate as ordinary
success. This is an unresolved recovery/receipt-meaning gap, not permission to
relax validation. No production path is active.

Recommended receiver-side resolution for joint approval: distinguish proof of a
batch's historical acceptance from the current day cursor. Return the actual
current cursor in `committed`, or agree a separate explicitly named current-cursor
field in a future contract. Also check the active producer epoch/grant before
ordinary duplicate success: another day can advance the producer epoch while this
day's cursor remains old. Merely returning this day's current cursor cannot expose
that global fence. Keep ordinary same-lineage restart retries idempotent.

### Added Sender Coverage

Added only missing acknowledgement tests: exact field layout; negative receipts
with current/newer/different-mapping cursors; durable pause with coalesced requests
retained; unsupported-restart resync with an older receiver cursor; success receipts
with mismatched committed epoch/batch/digest/mapping/day/revision; and rejection of
same-shaped foreign Python receipt/cursor/scope objects. Existing tests already
covered ordinary accepted/duplicate, negative receipts with no cursor, wrong request
binding, receiver generation mismatch and old acknowledgements during newer work.
No receiver code is imported by these repository tests.

Verification: **21 added receipt cases**; the final focused outbox/source-model/
serializer group passed **410 tests in 26.20 seconds**. The related source-shadow,
shared-reader, PACS, flu, patient-context and database-contention regression group
passed **833 tests in 92.29 seconds**. An isolated direct probe against the exact
receiver commit confirmed the table above and reproduced the historical-duplicate
gap. Reference imports were limited to synthetic modules; no runtime/API imports.
Tests used fixture-only temporary SQLite stores, mocked EMR connections, isolated
mutexes/application data, blocked network/WebEngine and blocked native operations.
The full application suite was not rerun for this tests-and-documentation-only
milestone. All application files remain unchanged from the sender baseline.

### Decisions Still Required

| Area | Decision/recommendation still requiring joint agreement |
| --- | --- |
| Epoch grants/fencing | Authenticated durable grant per clinic/source/projection; retire old authority across every day and define duplicate behavior after retirement. No timestamp/UUID-derived epochs. |
| Receiver generation | Explicit authenticated enrollment and binding; unknown/replaced generation stops delivery, never trust-on-first-response. |
| Lost sender/receiver state | Pause; reconcile durable receipts/cursors and grant a new lineage only through approved recovery. Never silently recreate state or replay into a blank replacement receiver. |
| Receiver ahead | Historical acceptance is insufficient. Fix receipt/current-cursor semantics, expose producer fencing, and reconcile before another allocation; do not jump to receiver revision + 1 automatically. |
| Ack encoding / HTTP | Internal Python objects are not a wire schema. Agree strict versioned encoding, null/type rules, authentication and status mapping; HTTP 2xx alone must never release pending work. No endpoint is selected. |
| Retry / pause | Only transient transport failures may retry the exact sealed bytes. Keep stale/conflict/resync durably paused; malformed/scope/generation/current-cursor mismatch requires supervision. Agree resume authority and budgets before adding a worker. |
| Mapping cutover | Preserve pending bytes and fixed mapping. Use a reviewed new projection with explicit cutover/retirement; epoch increments must not bypass mapping compatibility. |

The sender's proposed 2-second initial backoff, 60-second cap, 15-second attempt
deadline, 5-minute warning and 15-minute/20-attempt pause remain unimplemented and
not a negotiated transport policy. Stricter decimal bounds remain sender-only.
Complete-day membership/consistency/verified-empty evidence, code 10, qualifier
combinations, all-category cancellation and sex/age conventions remain unresolved.
Both stores remain plaintext-synthetic-only. No transport, token, encryption,
production persistence, EMR access, PACS change, deployment or service restart.
`/api/v1/order-snapshots` remains prohibited for normalized source payloads.

## Synthetic Acknowledgement Recheck: 2026-10-04

Sender reference: `7055e1bd52d8f9dd0d63f7f680dbc17d0d7e014b`.
Receiver reference: `02acc8a93c0c373d4e53d181058b46ce1fb405c7`, inspected in a
new temporary detached checkout. Reviewed `app/source_store.py`, its store tests,
and `docs/normalized-source-contract-v1.md`, including the diff from `40c6a49`.
Internal receipt/cursor/scope field parity is unchanged. Neither sender validators
nor either store implementation was changed in this recheck.

### Corrected Retry Outcomes

| Exact retry after receiver reopen | Outcome | Committed cursor |
| --- | --- | --- |
| Still current under the active producer epoch | duplicate | request |
| A newer revision of that day exists in the same epoch | stale | Actual newer day cursor |
| That day advanced to a newer producer epoch | resync_required | Actual current day cursor in the newer epoch |
| Another day advanced the producer; requested day did not advance | resync_required | Actual requested-day cursor, even when equal to request |
| Another day advanced the producer; requested day has a newer old-epoch revision | resync_required | Actual requested-day cursor, not the other day's cursor |

The [accepted-retry check](https://github.com/zinsss/KaosOrders/blob/02acc8a93c0c373d4e53d181058b46ce1fb405c7/app/source_store.py#L542)
tests the shared producer epoch before current-cursor equality. This closes the
previous historical-duplicate gap for these synthetic cases. No projection was
changed by any of the five retry scenarios. Previously unseen retired-epoch
requests also return resync_required; when that day has no cursor, committed is
None, as covered by the receiver's store tests. Missing lineage for an already
accepted retry remains a corruption error, not permission to recreate state.

### Sender Preservation and Verification

An isolated in-process probe used the actual pinned receiver and unchanged sender
with only temporary plaintext synthetic SQLite stores. It reconstructed receipt
fields explicitly into the sender's exact dataclass types in test-local code;
this is not a network schema or runtime adapter. All **five scenarios passed**.

For stale/resync, reopening the sender retained the exact pending bytes, batch,
epoch, revision, digest and coalesced refresh request. The pause reason persisted;
acknowledged revision/generation stayed at zero and allocated revision stayed at
one. A later success receipt could not bypass the pause. Requesting another
refresh did not clear it, and sealing another batch failed with scope_paused.
No receiver cursor was adopted and no receiver-next revision was allocated.
An ordinary current duplicate alone acknowledged its pending batch normally.

Added three sender resync receipt cases and strengthened the existing negative
receipt cases with explicit byte/counter preservation and blocked-seal assertions.
Older stale combinations remain as defensive negative-receipt coverage, not claims
that the revised receiver emits stale for retired epochs. Repository tests import
no receiver code.

Verification: **413 focused sender outbox/source-model/serializer tests passed in
5.18 seconds**; **24 pinned receiver store tests passed in 1.77 seconds**; the five
direct compatibility scenarios above passed separately. Receiver tests skipped
its runtime conftest imports, not any store test. Network was blocked, sender EMR
connections mocked, test mutexes/application data isolated, and native desktop/
printer operations blocked. No receiver API/config/runtime database was imported.
The broader application suite was not rerun for this tests/docs-only recheck.

The synthetic historical-retry issue is resolved, not the production recovery
protocol. Still required: authenticated epoch grants/fencing, receiver-generation
enrollment, lost-state and receiver-ahead reconciliation, acknowledgement encoding/
HTTP status mapping, retry/backoff and supervised pause/resume, and mapping cutover.
Source-evidence gates remain unresolved: complete-day membership/consistency,
verified-empty days, code 10, qualifier combinations, all-category cancellation,
and sex/age conventions. No production storage, encryption, transport, runtime
wiring, EMR access, PACS changes, deployment or restart was added.
`/api/v1/order-snapshots` remains prohibited for normalized-source payloads.

## Controlled Source Evidence: 2026-10-04

The next approved milestone started from sender
`e12685dde19080d97179c00476362feba9d34c8f`, with receiver reference
`a837d385ff367e4f72310226d8bc8439fc0c50fe` inspected in a temporary detached
checkout. The receiver now records completed synthetic acknowledgement/recovery
proof; those stages were not repeated or turned into runtime transport.

See the [sanitized source evidence](kaosorders.md#controlled-aggregate-source-evidence-2026-10-04)
for the exact operation boundaries, counts, allowlisted combinations and closure
timings. The operator confirmed 2026-10-02 as populated and 2026-10-03 as closed
in KST. Three bounded read-only operations ran: catalog metadata, one populated-day
statement, and one confirmed-empty-day statement. All closed before interpretation;
no patient/order identifiers, raw rows, demographic values other than aggregate sex
tokens, DOB, clinical text or credentials were output/persisted.

| Gate | New evidence | Decision |
| --- | --- | --- |
| Day membership including no-order visits | 173 receptions, 17 without orders, no status/category filters | Candidate table scope covered; clinical/day/archive authority not fully approved. |
| Child coverage and four-part identity | 1,081 linked orders; no invalid/duplicate full keys; no same-date orders outside the day or cross-date children in sample | One-day coverage evidence, not proof of every cross-day/history lifecycle. |
| Consistency | All reception/order/sex aggregates in one plain SELECT/CTE statement | Single database command snapshot; no claim that separate reads or EMR workflow saves are atomic. |
| Overflow/failure | Cap-plus-one bounds plus output sentinel; mocked failed/partial/timeout/inconsistent/overflow paths yield no authoritative empty | No silent truncation; runtime reader remains blocked. |
| Verified empty | Operator-confirmed closed date had zero receptions, linked orders and same-date orders | Verified empty candidate scope, not a normalized complete snapshot. |
| Reception/qualifiers | 168 at 40/N/N; five at 50/N/N | No new evidence for code 10 or other compound meanings. |
| Order qualifiers | All dc_yn=N; act_yn=N/Y both present across allowlisted type/department buckets | No all-category cancellation/administration mapping inferred. |
| Sex | M=62/F=111 per reception; nullable source field, no null/blank sample | Operator approved exact M/F as male/female preserving M/F, and true NULL as null on 2026-10-05. Blank/whitespace and other unverified values remain blocked, not mapped to null/O. No implementation enabled. |
| Age | Reviewed candidate ageday column absent from patient table; no DOB/age values queried | Operator approved completed years on the encounter clinic date on 2026-10-05. Safe derivation remains unresolved; no DOB access authorized. |

The [2026-10-05 demographic policy approval](kaosorders.md#demographic-policy-approval-2026-10-05)
resolves the two operator convention decisions, not missing source evidence.
Earlier historical references to pending conventions are superseded only in that
respect. This documentation-only update performs no live operations and changes
no validator, mapping, source reader or runtime behavior.

**Whole-day production reader remains blocked.** The aggregate acquisition shape
has evidence for these dates, but it cannot supply the missing source-policy facts.
Do not remove `EghisSourceDayReader`'s UNAVAILABLE return, declare empty authority
from a failed read, enable triggers/settings, or wire a serializer/outbox/endpoint.
PACS, board, transport, deployment and running applications remain untouched.
Normalized-source payloads must never go to `/api/v1/order-snapshots`.

Verification: 239 focused and 903 related isolated tests passed. The full
offscreen Qt run returned 2,561 passes and 26 failures; the same 26 vaccine
label/layout failures reproduce at the untouched `e12685d` baseline. No unrelated
UI changes were included. New inspection code has 67 mocked cases; the source
reader, source model/ledger, serializer, outbox and PACS implementations are unchanged.

## Reception Comparison: 2026-10-05

The operator confirmed one disposable waiting visit dated 2026-10-05 KST.
A tested reception-only aggregate operation observed one `10/N/N` reception
at 00:43:33 KST, with verified read-only mode and both cursor/physical connection
closed before interpretation (0.152 s lifetime). It read no patient/order
identifiers, demographics or orders. See the [supervised comparison](kaosorders.md#supervised-reception-comparison-2026-10-05)
for scope, limits and the 280-focused/944-related mocked test results.

After the operator opened the dummy for consultation and reported ready, one
further read at 00:46:30 KST found `20/N/UNREVIEWED`, still exactly one reception.
Verified read-only mode and cursor/physical closure succeeded again (0.0523 s).
The same previously tested query was used, with no retry or expanded field access.

The observed `10 -> 20` transition supports waiting versus open consultation for
this isolated test, not all lifecycle/compound-state mappings. A concrete contract
blocker remains: `hold_opd` falls outside the exact Y/N allowlist (not null/empty),
so its source value is not representable by the current strict raw qualifier.
`UNREVIEWED` is a server-side privacy mask, not the source value. Do not guess Y/N,
discard this encounter, export the unknown value, or weaken either validator.
A bounded privacy-safe qualifier investigation and any resulting contract change
need separate review. No validators, normalized mappings, runtime reader,
transport or PACS behavior changed. All other source-evidence gates remain open.

Post-observation synthetic regression checks: 482 focused and 949 related isolated
tests passed. Five added cases preserve the diagnostic mask boundary and verify
that normalized qualifier validators reject `UNREVIEWED`; no validator was changed.

### Qualifier Shape Follow-Up

The [approved 2026-10-05 shape inspection](kaosorders.md#qualifier-shape-follow-up-2026-10-05)
returned one `20/N` reception whose `hold_opd` consists of ASCII digits. Only the
fixed `ASCII_DIGITS` shape label and count crossed the source boundary; the digits,
numeric value and exact length were not returned. The single live operation at
00:56:30 KST verified read-only mode and closed the cursor/physical connection
before processing (0.0519 s), after 529 focused and 996 related mocked tests passed.

This excludes a mere case/whitespace variant of Y/N for that observation, but not
an identifier or an unverified numeric code. No clinical/boolean meaning was inferred.
Do not send the shape label in place of raw facts, cast numeric text to Y/N or
broaden the sender/receiver validators. Source-domain and privacy review must
precede any coordinated contract revision. No production model/contract was changed,
no endpoint called and no runtime reader enabled. All other evidence gates remain.

### Hold Return

After the operator reported the dummy on hold and reconfirmed that it remained
the only reception, one existing bounded read at 2026-10-05 11:27:12 KST returned
`25/N/N` (count 1). Read-only session, cursor closure and physical closure were
verified before interpretation (0.0545 s). No additional field, raw value or
identifier was queried for output; see [hold return](kaosorders.md#hold-return-2026-10-05).

The `10 -> 20 -> 25` sequence and return of `hold_opd` to N support the sampled
waiting/open-consultation/hold distinction for this isolated workflow. They do
not explain the earlier numeric value or remove its strict-Y/N incompatibility.
The overnight gap was not continuously observed; no precise transition time or
causal field definition was inferred. Source-definition/privacy review and a
coordinated contract decision remain required. No validator or runtime changed;
529 focused mocked tests passed for this documentation-only follow-up.

## Qualifier Decision Proposal: 2026-10-05

**Status: recommendation for joint review, not an agreed or implemented contract.**
Review started from sender `3801dad3378dad831569c635acfa035887bbb0b9` (clean main).
The existing clean detached receiver checkout was verified at
`a837d385ff367e4f72310226d8bc8439fc0c50fe`. This is a pinned reference, not a claim
about the latest receiver or deployed service. No pull, SSH, live EMR read, metadata
query, API call, app restart or receiver edit was performed in this review.

### Definition and Usage Findings

| Evidence | Finding | Consequence |
| --- | --- | --- |
| Previously recorded catalog comment | `hold_opd` was described as a consultation-in-progress Y flag; the later isolated visit used numeric text while open. | The comment does not define the observed domain. Do not turn it into proof that numeric means Y. |
| Previously recorded dictionary access | The configured reader was denied SELECT on the candidate code dictionaries. | Do not repeat denied queries, change credentials or request broad grants merely for this review. A narrowly scoped non-patient field definition from the vendor/administrator remains a possible evidence source. |
| Sender `core/emr_source.py` | `ReceptionQualifiers` and `_source_flag` require exact Y/N. `normalize_source_day` obtains state from the explicit policy for `state_code`, not from either qualifier. | The current failure is intentional validation, not a broken query or parser. This code design is not proof that every production compound state can ignore qualifiers. |
| Sender `core/emr_source_shadow.py` | Whole encounter equality includes both qualifiers. | Removing a field changes the compared projection and requires a new baseline, not silent reuse of the old ledger. |
| Sender `core/kaosorders_normalized_source.py` | Qualifiers are revalidated and included in the canonical digest. | Changing the field changes payload bytes and digests; never rewrite a sealed pending batch. |
| Receiver `app/source_contract.py` | `ReceptionQualifiers` requires `hold_opd: SourceFlag`; extra fields are forbidden and contract version is exactly 1. | Numeric text, null, omission and diagnostic replacement are incompatible with current v1. |
| Receiver `app/source_shadow.py` and `tests/test_source_reconciliation.py` | Qualifier-only changes count as encounter edits through full-model equality. | Raw qualifier retention is tested behavior, not an optional ignored key. |
| Receiver `app/source_store.py` | Synthetic storage has a required `hold_opd` column and reconstructs the strict qualifier model after restart. | Parser-only changes would not be sufficient; a future version needs a reviewed storage/reconstruction change too. |
| Receiver application search at the pinned revision | Uses were confined to the normalized contract and synthetic store; no status derivation, categorization or board rule consuming this field was found. | There is no demonstrated consumer need to export the unknown number. Receiver ownership must still confirm that omission is acceptable. |

The numeric value's role is **still unknown**. Existing metadata and code did not
identify it as a clinician, lock owner, boolean, counter or other defined code.
No numeric value or length was retrieved to try to establish such a meaning.

### Recommended Contract Boundary

Prefer an explicitly versioned, minimized projection over relaxing raw-value
validation. Subject to receiver and source-policy approval, propose:

1. Preserve `kaosorders.normalized-source` contract version 1, its strict validators,
   fixtures, hashes and stored test behavior unchanged. The currently blocked
   production reader must not bypass v1 by omitting a required field.
2. Specify a new normalized-source contract version (proposed version 2, subject
   to receiver agreement) in which encounter `qualifiers` contains only required
   exact-Y/N `hold_yn`. `hold_opd` is forbidden for **every** encounter, including
   those whose source value happens to be N or Y. No optional/null substitute,
   raw string, numeric ID, hash, shape marker or guessed boolean is sent.
3. Preserve `source_state_code`, independently verified normalized `state`, all
   encounters (including in-progress and no-order visits), all child rows and the
   four-part order key. Order `dc_yn`/`act_yn` remain strict raw Y/N. No category,
   fee, visibility, display, PACS or clinical-unit behavior is added.
4. Revise the **approved source projection and matching offline source model**
   explicitly. Do not feed numeric qualifiers into v1 and catch the error by
   dropping the encounter or stripping a field. Under a future approved v2 query,
   raw `hold_opd` would not be selected for transport/persistence. Unknown or extra
   projected input fields still fail closed; no arbitrary metadata dictionary.
5. Confirm that excluding this field does not hide evidence needed to normalize
   a reception state. If it is essential to a compound-state rule, this proposal
   is insufficient: retain the reader block until a verified, privacy-safe typed
   semantic can be agreed. The single `10 -> 20 -> 25` test alone does not authorize
   all production mappings or claim complete-day consistency.

This is an intentional revision of the earlier requirement to retain all four raw
qualifiers, **not** permission to silently discard a required fact in the current
contract. The new version number refers to the normalized-source contract, not the
older superseded board-oriented v2 prototype or an HTTP URL. No endpoint is chosen.
`/api/v1/order-snapshots` remains prohibited for any normalized-source payload.

Rejected shortcuts: widening to arbitrary strings; numeric/nonzero-to-Y conversion;
putting `UNREVIEWED`/`ASCII_DIGITS` in a raw-fact field; per-row omission; filtering
out in-progress visits; inferring a lock/doctor identity; or shipping a partial
snapshot as complete. Keeping v1 blocked while obtaining an authoritative field
definition is the safe alternative if the receiver requires raw retention.

### Cutover and Acceptance

- A shape/semantic change needs coordinated contract version, explicit projection
  scope and mapping revision. A mapping-revision string alone cannot alter the
  existing v1 schema. Agree any new projection ID and authorized lineage through
  the existing enrollment/fencing design; no automatic epoch/revision allocation.
- Do not rewrite pending v1 bytes, reuse their batch IDs/digests for v2, merge
  baselines, adopt a receiver cursor or reset stores. Existing stale/resync pause
  rules stand. Any migration/new-store test uses synthetic temporary stores only.
- Compare changes only within the agreed projection. A `proc_gb`/normalized-state
  change must still be detected; changes solely to the deliberately excluded
  field are not promised delivery events. Document that changed comparison scope.
- Keep v1 golden fixtures and rejection tests intact. Add separate v2 full/empty
  fixtures, canonical hashes and sender/receiver parity only after joint approval.
  Test all six states, no-order encounters, cancellation with active children,
  edits/reused keys, qualifier-only edits for retained fields, and all completeness
  failures. Reject `hold_opd` even when supplied as Y/N, null, number, string or mask.
- Test version separation, unsupported-version rejection, sealed retries, stale/
  resync pause preservation, mapping cutover and restart reconstruction. The
  receiver's required storage column cannot be left silently defaulted to N.
- Other source gates remain: authoritative day membership/consistency, full state
  and cancellation coverage, remaining flag combinations, safe age derivation,
  demographic source conventions and least-privilege verification. This design
  decision alone does not approve a live day reader, transport or deployment.

### Receiver Handoff

Ask the KaosOrders session to review this proposal against its current checkout,
first reporting branch/status/HEAD and preserving existing work. Compare with the
pinned `a837d385ff367e4f72310226d8bc8439fc0c50fe` reference used here. Return decisions
only on: whether raw `hold_opd` is required for any business rule; whether to accept
its consistent exclusion in a new normalized-source version; the exact version/
projection identity; synthetic store cutover; and the parity acceptance matrix.
If retention is required, identify the concrete consumer purpose and evidence
needed to define a safe domain rather than requesting arbitrary raw values.

Do not implement the proposal, change validators, edit v1 fixtures, enable SQL,
call an API or touch the board/PACS in that review. Sender implementation should
start only after the receiver returns an explicit agreed specification. No
receiver agreement or implementation is claimed by this sender document.

### Verification

Added 16 synthetic sender rejection cases covering numeric strings and the
`ASCII_DIGITS` diagnostic marker across all four current qualifier fields.
**545 focused tests passed in 3.05 s**; **1,012 related isolated tests passed in
41.69 s**. Runtime source, normalizer, serializer, ledger and outbox code are unchanged.
Mocked databases, isolated mutexes and blocked native/non-test network access were
used. The broad full UI suite was not repeated for this docs/test-only change.

A direct pure-parser check in the unchanged receiver checkout accepted both
original v1 fixtures and rejected **30/30** re-sealed synthetic invalid cases with
the fixed reason `invalid_payload`: six invalid values for each of four qualifiers,
each missing qualifier, one extra diagnostic field, and unsupported version 2.
Socket/SQLite access was explicitly blocked; only the pure contract module and
synthetic fixture JSON were used, with bytecode writing disabled. Existing v1
fixtures/digests were not changed; no proposed v2 payload was declared valid.

## Synthetic V2 Sender: 2026-10-05

Receiver acceptance was read from exact KaosOrders commit
`6837845fc4c691075bab41c6e07ef69e8562580b`,
`docs/normalized-source-contract-v2-plan.md`. Sender work began from clean main at
`51d7601327ab4db58155960b8e0be75ea029e43f`. The earlier proposal above is historical;
receiver agreement now exists for the minimized projection, not for production use.

### Implemented Boundary

- `core/emr_source_v2.py`: separate frozen/slotted read, encounter, qualifier and
  snapshot types, complete-read assertions, closed input fields, strict retained
  flags, graph/bounds validation and canonical sorting. V1 snapshots/encounter
  qualifiers are not accepted as v2. Unchanged order identity/fact primitives are
  shared; v1 validation, normalization and serialization are not bypassed or edited.
- `core/kaosorders_normalized_source_v2.py`: pure serializer with an explicit
  `synthetic_fixture=True` gate and separately typed, explicitly supplied clinic,
  batch, epoch and revision metadata. No UUID, revision, epoch or time is generated.
  Directly constructed snapshots are revalidated before serialization.
- Only the exact agreed synthetic projection/mapping pair is accepted. This is
  not a production mapper, parser endpoint, authorization mechanism or evidence
  that caller assertions certify a live complete-day read.
- No `hold_opd` field exists on the v2 encounter qualifier type. Supplying it in
  source aliases fails rather than stripping it, whatever its value. The slotted
  qualifier cannot carry an extra attribute. Retained flags remain exact Y/N.
- V2 fact equality preserves retained-qualifier, state and order edits. Tests
  distinguish explicit cancellation, disappearance and reuse of the complete key.
  No new ledger, source subscription, ordering allocator, outbox or storage is added.
  A new observation timestamp/digest is not itself a business-fact edit.

### Field Compatibility

| Field | V2 sender behavior | Receiver status / remaining decision |
| --- | --- | --- |
| Contract identity | `kaosorders.normalized-source`, integer version `2` | Agreed plan; independent receiver parser verification next. |
| Projection / mapping | Exactly `kaosorders-all-orders-v2` / `synthetic-v2` | Production mapping, enrollment and fencing not approved. |
| Clinic / source / day | Explicit scope, strict text and calendar date | Source day membership/consistency remains gated. |
| Batch / epoch / revision | Explicit UUID and integers 1 through 2^63-1 | No durable allocation or adoption of a receiver cursor. |
| Full / complete | Always `FULL` / `true`, only after validated fixture input | Failed, partial, unavailable, timed-out, unverified and overflowed input cannot normalize as empty. |
| Encounter identity / demographics | Same facts as v1; explicit null retained, blank sex rejected | M/F source policy approved; unseen values and safe age derivation unresolved. Synthetic O is not source approval. |
| Reception code / state | Explicit synthetic policy, all six states including separate consultation/payment completion | No production mapping enabled; dependence on excluded qualifier remains an evidence gate. |
| Encounter qualifiers | Exactly required `hold_yn`, strict Y/N | `hold_opd` forbidden for every encounter, including Y/N source cases. |
| Order identity | Encounter ID + order date + order number + order sequence | Same four-part identity; no manufactured stable-ID substitute. |
| Order facts / qualifiers | Every child retained, including fees/unclassified; `dc_yn` and `act_yn` required Y/N | No category, fee, visibility, display or clinical interpretation. |
| Quantity / days / frequency | Null or exact canonical decimal string, no units, no float coercion | Sender limit: magnitude <= 10^9, exponent -12..12, input/output text <= 32; contract adoption still undecided. |
| Observation time | Aware source observation time only | Not ordering authority or a clinical event timestamp. |
| Digest | UTF-8, Unicode preserved, sorted keys, compact separators, no NaN/infinity, SHA-256 without digest field | Receiver must independently verify exact hashes. |

### Fixture Candidates

See [v2 provenance](../tests/fixtures/normalized_source_v2_provenance.md) for exact
file-byte hashes, construction and references. Canonical files use UTF-8 plus one
LF, pinned by fixture-scoped Git attributes. Existing v1 fixture Git blobs and
content hashes remain unchanged.

| Fixture | Contents | Content SHA-256 |
| --- | --- | --- |
| Full | Six encounters, five orders; all six reception states; no-order, cancelled-parent/active-child, cancelled-child, fee and unclassified cases | `a6b7e348c734c7af4c1f7467e0f66ec84dfaa4904fe53d53a1a389ddc9b17c2d` |
| Empty | Separate synthetic complete day, zero encounters/orders | `f03a8a244b8c3d324d6011d0c15f49c49ce2567872665ba1e4e1efb8413daf16` |

Sender tests independently construct input aliases and match parsed objects,
canonical file bytes and independently calculated digests. This is **sender
fixture parity**, not a claim of completed receiver v2 parser/storage parity.

### Verification Results

- 225 new v2 cases; full and empty fixtures both match exact parsed objects,
  canonical bytes and independent digests. V1 committed fixture blobs are pinned
  and unchanged. The existing source-import boundary test permits only the two
  new offline modules; a separate v2 test forbids runtime importers and IO dependencies.
- Focused v2/v1 source/serializer, evidence and shared-reader group: **770 passed
  in 3.51 s**.
- Related source-shadow, receipt/outbox, shared-reader, PACS, flu/weekly-age,
  patient-context and database-contention group: **1,237 passed in 41.31 s**.
- Full isolated suite: **2,894 passed, 27 failed in 142.83 s**. Twenty-six failures
  are existing vaccine label font/ink and shortcut-width assertions. They were
  reproduced in a clean detached `e12685dde19080d97179c00476362feba9d34c8f`
  baseline: **273 passed, 26 failed in 17.43 s** for the three vaccine test files.
  Their test files and corresponding vaccine/printing code are unchanged since
  that baseline.
- The extra full-suite failure was
  `test_pair_notes_do_not_leak_into_next_patient_after_skip`; the complete post-print
  file passed on isolated retry (**28 passed in 6.52 s**) and in the baseline run.
  This is an unresolved intermittent suite failure, not a claimed fix or a green
  full suite. No unrelated vaccine behavior or assertions were changed.

Tests used mocked database connections, isolated test mutexes, a temporary data
directory, offscreen Qt and blocked external network/native input/printer access.
The mock cleanup check verifies zero live connections and cursor/connection close
events before serialization. No production connection or live cleanup assertion
was attempted. No raw diagnostic output was added to the repository.

### Unresolved Gates and Handoff

No live operation was performed in this milestone. The `EghisSourceDayReader`
UNAVAILABLE block, shared reader, physical-connection boundary, PACS, flu reports,
settings, triggers, v1 serializers/outbox/receipts and runtime imports are unchanged.
No production SQL, patient export, endpoint, token, delivery, deployment or restart.
`/api/v1/order-snapshots` remains prohibited for every normalized-source payload.

For the original milestone, source gates included full-day membership/history.
The later current-day decision narrows that to today's membership; complete child
coverage and clinical-save consistency, verified-empty authority, full state and
qualifier-combination evidence (including whether state interpretation needs the
excluded field), all-category cancellation/deletion/restoration, unseen sex values,
safe completed-years age derivation and least-privilege verification remain
unresolved. Isolated 10/20/25 observations and fixture success do not clear these gates.

For that original persistent design, delivery gates included durable epoch/revision
grants and fencing, receiver-generation enrollment, lost-state/receiver-ahead
recovery, content-bound acknowledgement encoding
and HTTP status mapping, retry/backoff/pause policy, mapping cutover, storage security
and retention. No v1 sealed bytes, batch IDs, cursors or receipts are rewritten.
Stale/conflict/resync must continue to pause and preserve pending bytes in the
existing synthetic v1 proof. The current-day memory-only decision now requires a
separate volatile-session/restart design instead of a production durable store.

**Next KaosOrders handoff:** inspect the exact resulting sender commit and copy the
two v2 fixtures with provenance. Implement only a separate pure v2 receiver parser
and in-memory reconciliation tests, with independent canonical digest/negative
parity tests against the agreed identity. Reject excluded `hold_opd` and
invalid/missing retained flags, preserve v1 behavior, and report exact fixture
equality. Reconciliation must retain every source fact, replace same-key and
retained-qualifier edits, distinguish disappearance from explicit cancellation,
preserve other days/scopes, and leave accepted state unchanged after rejected input.
Use synthetic fixtures and blocked network access only. Do this before v2
persistence, transport or board work; do not weaken validators, migrate v1 stores,
use live data or enable intake.

### Exact Checklist Recheck: 2026-10-05

The repeated implementation request named the older `51d7601` reference, but the
working tree was already clean and pushed at
`609961e3f28c5528d1ae93389ddf3247d6a9c48a`. Existing work was preserved, not repeated
or reset. All four requested receiver documents were read at exact commit
`6837845fc4c691075bab41c6e07ef69e8562580b`: the v2 plan and handoff, v1 contract,
architecture and implementation plan. No receiver files or services were changed.

One narrow direct-helper gap was corrected: the standalone v2 digest function now
rejects an excluded field at any nested dictionary/list/tuple location before JSON
encoding or SHA-256. It neither strips the field nor hashes a replacement. Ninety
synthetic location/value cases prove rejection before either encoder or hasher is
called, with fixed `invalid_payload` errors and no diagnostic output/logs. Cycle and
non-text-key failures are also fixed and redacted. This privacy guard is not a wire
parser or full schema validator; the serializer still validates the complete source
snapshot first. Valid fixture bytes and both content hashes remain unchanged.

Three new Git-blob assertions pin the v1 model, serializer and synthetic outbox to
their exact `51d7601` reference bytes, complementing the existing v1 fixture blob
and digest tests. No v1 validator, serializer, fixture, hash or outbox was changed.
The receiver handoff now explicitly includes **in-memory reconciliation only**, with
no v2 persistence or runtime integration. All previously listed source-evidence and
delivery gates remain unresolved, including any reception-state dependency on the
excluded qualifier. The live reader remains UNAVAILABLE.

Recheck verification: **866 focused tests passed in 3.79 s**, including all 321 v2
cases. The full isolated rerun finished with **2,991 passed and 26 failed in
140.91 s**. The failures are exactly the previously reproduced vaccine font/ink
and shortcut-width cases; the intermittent post-print failure did not recur.
This is not a green full suite, and no vaccine assertions or code were changed.
Mocked databases, test mutexes, temporary app data, blocked external network/native
input/printer access and offscreen Qt were retained. A Git comparison against
`51d7601` also confirmed no changes to the v1 model, ledger, serializer, outbox or
either v1 fixture. No live EMR operations, publishing or service restarts occurred.

## Review Findings

| Finding | Evidence | Required resolution |
| --- | --- | --- |
| Shared snapshot is not a drop-in PACS payload | `OrderFacts` has source identity/code/type/department, but no accession, imaging schedule, modality, station or exam description. `kaospacs_client._validate_kaospacs_entry` requires these imaging fields. | Retain the working PACS projection. Review a separate imaging extension/adapter, never invent an accession from the source tuple or reuse `observed_at` as the schedule. |
| Local PACS checkout and sender API expectations differ | Windows posts to `/orders/upsert` and `/orders/cancel`. The inspected Gateway defines health, imaging-worklist GET and admin completion, not those order routes. | Inspect the actual deployed receiver revision/capabilities before planning migration. This discrepancy does not prove the running clinic API is broken. |
| State qualifier domain and meanings remain unverified | The offline model/contract requires raw Y/N qualifiers. The 2026-10-05 open-consultation observation returned hold_opd outside exact Y/N; a bounded follow-up established ASCII-digit text without returning the digits or assigning meaning. | Review this source-domain and privacy incompatibility before live normalization. Do not coerce/drop the qualifier, omit the encounter, serialize the mask/shape, or weaken validators to obtain parity. |
| Observation IDs do not solve transport ordering | The ledger has memory-only UUIDs, timestamps and scope-local baselines. They are not durable, monotonic receiver revisions. | Agree duplicate/content checks, stale rejection, authenticated restart ordering and recovery with each receiver. Do not treat a newer UUID or a restart flag as overwrite authority. |
| Orders v1 is not a normalized-source receiver | The KaosClinic checkout accepts a per-encounter category snapshot, stores only XRAY/BMD/ECG, and has no source-day replacement or distinct consultation/payment completion. | Agree a separately versioned intake with receiver-owned classification. Preserve v1 semantics; do not translate the shared model lossily to the existing route. |

The local MWL `PUT /worklist` handler writes the supplied worklist payload as a
replacement. It is not evidence that a one-item PUT performs an upsert. Do not
point the Windows client at the internal MWL API as a workaround for missing
Gateway routes, and do not send a shared day snapshot to an existing endpoint.
The current PACS client, fallback behavior and server code are unchanged here.

## KaosOrders Receiver Review

Source root: `zin@kaosclinic:/srv/projects/KaosOrders`, revision recorded above.
`app/schemas.py`, `app/main.py` and `app/database.py` implement v1;
`docs/implementation-plan.md` describes future behavior, not available endpoints.

### Implemented Contract

- `POST /api/v1/order-snapshots` accepts `schema_version=1`, aware `observed_at`,
  one encounter and at most 100 order entries. Unknown fields are rejected.
- Encounter fields are `encounter_id`, `chart_number`, `patient_name`,
  `sex_age_display`, and `reception_status`. States are received, in-care, hold,
  cancelled, one combined completion value, and UNKNOWN.
- Each order has optional `order_id`, caller-assigned `category` and `status`.
  Only XRAY/BMD/ECG are stored. OTHER/UNKNOWN categories are ignored. There are
  no source code/type/department, four-part key, quantity/days/frequency or fixed
  state-qualifier fields. Category fallback identity is permitted in v1 only.
- An ingestion token is checked before body validation. The board has a separate
  token; responses are no-store and validation errors do not echo rejected input.
  Keep these privacy/authentication boundaries in any new version.
- Each encounter update is transactional. Older observation timestamps are
  ignored; omissions and empty order arrays are non-destructive. Reception
  cancellation withdraws stored child orders; completion hides the encounter
  without completing source orders. Restoring active children needs their explicit
  resubmission, not just changing the reception status.
- The board groups non-withdrawn XRAY/BMD/ECG under hold encounters. It has no
  source-day identity, structured edit details, full-day replacement, durable
  revision/restart protocol or source-staleness field. Retention is rolling
  inactivity, not an agreed clinic-day boundary. An order status of COMPLETED
  remains visible when on hold; v1 does not infer imaging completion.

### Migration Gaps

| Area | Current behavior | Required before source delivery |
| --- | --- | --- |
| Ownership | Caller supplies final category; receiver drops unrelated categories. | A new version accepts only approved source facts and owns classification/fee rules. Do not export arbitrary rows or clinical text. |
| Identity and edits | Opaque optional order ID, or category fallback; only category/status content is stored. | Agree full four-part key encoding and same-key content replacement, including reuse with different code and structured edits. No category fallback. |
| Reception state | One completion value cannot distinguish consultation-completed from payment-completed. | Preserve distinct normalized meanings and the approved qualifiers; board visibility stays a separate receiver decision. |
| Disappearance | Omitted orders remain stored; ignored OTHER rows do not remove an old diagnostic row with the same key. | Complete scoped reconciliation must remove stale source facts, including category changes, without calling all disappearance a source cancellation. Never give v1 omissions destructive semantics. |
| Retry/order | Equal-time identical content is a no-op, but equal-time different content can overwrite it; there is no batch/content conflict check. | Content-bound idempotency, stale rejection, authenticated restart ordering, atomic source-day application and full recovery. A timestamp or UUID alone is insufficient. |
| Bounds/privacy | Receiver chart/name limits are 64/100 characters versus 128 in the internal model; v1 is capped at 100 orders per encounter. | Agree wire limits and complete-day bounds; reject overflow rather than truncating or chunking into falsely authoritative snapshots. Preserve strict PHI allowlists. |
| Scope/lifecycle | No source/projection/day scope or mapping version; rolling inactivity purge. | Agree scope-bound authentication, mapping changes, day lifecycle and stale display before authoritative replacement. |

The receiver's September 30 docs still describe an Acer/LMDE viewer, completed
tiles and non-clickable diagnostic hold tiles. Those are older plans than the
current decisions in [KaosOrders](kaosorders.md#status-and-current-decisions): Pi 4
touchscreen, confirmed hold encounters and receiver-owned broader categories and
details. They are neither current implementation proof nor permission to change
the board. Remote documentation and code remain untouched in this read-only review.

### Test Evidence and Next Gate

Inspected, not executed here: `tests/test_api.py` covers exact retries, token
separation, stale/unknown updates, explicit withdrawal, cancellation, completion,
duplicate-key rejection and retention. `tests/test_privacy.py` checks prohibited
fields, generic validation responses and no sensitive logging. These v1 tests do
not establish whole-day replacement, conflicting same-time content, quantity
edits, key reuse across categories, source restart or new snapshot scope behavior.

The October 4 parity stage above now covers the pinned disabled draft, not this
older v1 API. Keep v1 available without semantic changes. No production route,
mapping, query, publisher or live migration is approved. The reader gate below
remains incomplete, including deployed PACS and source qualifier/coverage questions.

## Field Boundary

These are reviewed requirements/candidates, not approval of a live query or mapping.
The new internal model covers only the common/Orders-oriented columns below; it
is not a complete universal imaging model.

| Data | Shared/Orders boundary | PACS-specific boundary |
| --- | --- | --- |
| Source scope | Source ID, projection/coverage ID, clinic day, mapping revision. Authentication must bind the permitted scope. | Preserve an independently reviewed imaging scope; board filtering must not affect it. |
| Encounter identity | Source encounter ID, chart number, minimal name/sex/age. Chart number is not the visit key. | Preserve current patient identity linkage. No requirement to adopt the board's age format. |
| Order identity | Four-part tuple: encounter, order date, order number, sequence. Current-row identity, not immutable lifetime identity. | Preserve source-to-accession linkage. The existing three-part MWL join omits order date and is not proof of a unique four-part linkage. |
| Reception state | Approved raw code/qualifiers plus distinct normalized waiting, in-progress, hold, consultation-completed, payment-completed and cancelled meanings. Unknown/ambiguous combinations block dependent authority. | Apply imaging eligibility independently; payment or hidden board state is not imaging completion/cancellation. |
| Order state | Approved raw cancellation/qualifier facts plus normalized meaning. Keep cancelled encounters and unchanged active child orders in the complete source scope. | Preserve explicit source cancellation separately from imaging completion/expiry and disappearance evidence. |
| Catalog metadata | Exact code/type/department, including fee and currently unclassified rows within the approved source scope. No raw notes/descriptions. KaosOrders owns category and fee rules. | Reviewed imaging metadata and exam-description allowlist only; no board-category assumptions. |
| Quantity/days/frequency | Proposed exact-decimal edit fields. Source observations verified that `qty`/`days`/`divide` can change, not that they are a clinical dose/route specification. No float conversion or inferred units. | Do not add these fields to imaging delivery unless that receiver requires and approves them. |
| Time | Timezone-aware `observed_at` only until source event-time semantics are verified. Never claim actual edit/cancel time. | Retain verified imaging schedule separately; read time cannot substitute for it. |
| Birth date | No DOB in the Orders payload; a reviewed local age calculation may use/discard it transiently. | Existing PACS identity contract permits DOB. Keep this destination-specific; do not add it to the common Orders export. |
| Other personal/clinical data | No resident ID, phone, address, diagnosis, notes, credentials or arbitrary rows. | Same prohibitions; existing approved PACS demographic fields are the narrow exception to the Orders DOB restriction. |

Raw qualifiers must use an explicit, versioned allowlist, not an arbitrary metadata
dictionary. Field presence does not approve its interpretation. Age convention,
sex mapping, null/blank code semantics and structured-value units still require
source-to-contract review before live data is accepted.

## Snapshot Semantics

- Prefer a complete validated snapshot for the first integration. Source deltas
  may support diagnostics/efficiency, but a receiver missing a delivery must be
  able to recover from the full snapshot. Delta-only transport is not approved.
- Completeness applies to the authenticated source/projection/day, not just the
  rows currently visible on the board. Include no-order encounters and all agreed
  reception states, including completed, paid and cancelled.
- A successful query or `complete=true` is insufficient. Prove day membership,
  join coverage, no truncation, consistent reception/order observation and cleanup.
  An empty day needs the same evidence as a populated day.
- A failed, partial, timed-out or unknown-state read is not an authoritative empty
  snapshot. Keep the last valid receiver state and report unavailable/stale status.
- Missing means absent from a verified complete scope. Keep it distinct from an
  explicit cancellation, reception closure, payment and local baseline eviction.
- Same-key content changes replace the prior source facts. A source key may be
  reused; it must not inherit old board details or be assumed to identify the same
  completed imaging study forever. Never delete DICOM as a side effect of this read.
- A receiver validates the entire batch before atomically accepting it. Reject
  duplicate/orphan keys, forbidden fields and conflicting duplicate batch IDs.
  Compare content as well as batch identity. Transport failure is not source failure.
- Source baseline progress is independent of each destination's acknowledgement.
  Retries, retention and restart ordering need a reviewed delivery design. No durable
  queue, authenticated epoch or revision sequence exists in the current prototype.
- Do not use the old board-filtered v2 JSON as the shared contract: it collapses
  completion/payment, filters orders by board categories, and excludes some encounters.

## Reader Gate

Before implementing/enabling a real day operation:

1. Resolve the inspected KaosOrders v1 gaps and verify the deployed PACS contract.
   Agree minimum fields, privacy profiles, scope semantics and backward-compatible
   migration. Receiver repository inspection is complete; agreement is not.
2. Resolve source membership, qualifier semantics, demographics and structured-value
   provenance. Preserve the already reviewed four-part key; do not expand dictionary
   permissions or assume unverified codes from naming conventions.
3. Review a bounded parameterized query design using the existing FIFO/machine-wide
   mutex. Reception/order consistency must come from one reviewed statement or a
   separately reviewed read-only snapshot transaction, not independent autocommit
   reads assumed to share one snapshot. No transaction-mode change is made here.
4. Test caps, overflow detection, nulls, all state transitions, consistent empty days,
   errors, timeouts and connection closure with mocked DBs first. A cap must yield a
   non-authoritative outcome, never silently truncate. Close before normalization.
5. Obtain separate approval for bounded live shadow verification. No production
   source access, publisher activation or PACS cutover follows from this review.

## Receiver Acceptance Cases

The common source tests exist; these cross-system cases still need receiver tests:

- Same-key quantity/catalog edit while payment state remains unchanged.
- Cancelled reception with uncancelled child rows; restoration to waiting then hold.
- Complete disappearance, same-key return and changed content after key reuse.
- Fees/unknown catalog rows retained as source facts without silently removing old
  tasks; application classification is reviewed independently.
- Incomplete/empty-looking failures leave the board/worklist unchanged.
- Identical retries, reused batch ID with different content, out-of-order delivery,
  source restart, receiver restart and missed delivery/full-snapshot recovery.
- Historical-day refresh never clears another day; changed projection/mapping does
  not silently reinterpret an existing receiver scope.
- PACS accession/schedule and existing imaging completion survive source refresh;
  Orders never receives PACS-only DOB or imaging payload fields.
- One receiver being offline does not block source cleanup or the other receiver.

The synthetic serializer/fixtures above implement draft parity only, not runtime
transport. No live API request or source query was performed. The initial receiver
inspection did not execute tests; later parity validation used only the pinned
reference parser/reconciler with synthetic objects, without API/storage integration.
