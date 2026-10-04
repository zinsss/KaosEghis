# EMR Source Contract Review

Reviewed: 2026-10-05

Status: **synthetic parity with the pinned disabled receiver contract implemented**.
This is not an approved HTTP endpoint, production query or deployment change.
The [source model](kaoseghis-emr.md#offline-source-model-2026-10-03) remains offline.
The subsequent [synthetic delivery milestone](kaoseghis-emr-delivery.md) adds an
isolated local outbox and crash tests, not production storage or transport. The
serializer and pinned fixtures are unchanged.

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

## Reception Baseline: 2026-10-05

The operator confirmed one disposable waiting visit dated 2026-10-05 KST.
A tested reception-only aggregate operation observed one `10/N/N` reception
at 00:43:33 KST, with verified read-only mode and both cursor/physical connection
closed before interpretation (0.152 s lifetime). It read no patient/order
identifiers, demographics or orders. See the [supervised comparison](kaosorders.md#supervised-reception-comparison-2026-10-05)
for scope, limits and the 280-focused/944-related mocked test results.

The in-consultation observation is pending. This baseline alone does not resolve
code 10 or compound qualifiers. No validators, normalized mappings, runtime reader,
transport or PACS behavior changed. All other source-evidence gates remain open.

## Review Findings

| Finding | Evidence | Required resolution |
| --- | --- | --- |
| Shared snapshot is not a drop-in PACS payload | `OrderFacts` has source identity/code/type/department, but no accession, imaging schedule, modality, station or exam description. `kaospacs_client._validate_kaospacs_entry` requires these imaging fields. | Retain the working PACS projection. Review a separate imaging extension/adapter, never invent an accession from the source tuple or reuse `observed_at` as the schedule. |
| Local PACS checkout and sender API expectations differ | Windows posts to `/orders/upsert` and `/orders/cancel`. The inspected Gateway defines health, imaging-worklist GET and admin completion, not those order routes. | Inspect the actual deployed receiver revision/capabilities before planning migration. This discrepancy does not prove the running clinic API is broken. |
| State qualifier meanings remain unverified | Fixed hold_yn/hold_opd and dc_yn/act_yn Y/N facts are now retained in the offline model and draft serializer. Compound semantics are still unverified. | Verify combinations before live normalization; presence and synthetic parity do not authorize mapping every row solely by proc_gb/dc_yn. |
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
