# EMR Source Contract Review

Reviewed: 2026-10-03

Status: **offline source review recorded; receiver agreement is pending**. This is
not an approved HTTP schema, new endpoint, production query or deployment change.
The [source model](kaoseghis-emr.md#offline-source-model-2026-10-03) remains offline.

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

## Review Findings

| Finding | Evidence | Required resolution |
| --- | --- | --- |
| Shared snapshot is not a drop-in PACS payload | `OrderFacts` has source identity/code/type/department, but no accession, imaging schedule, modality, station or exam description. `kaospacs_client._validate_kaospacs_entry` requires these imaging fields. | Retain the working PACS projection. Review a separate imaging extension/adapter, never invent an accession from the source tuple or reuse `observed_at` as the schedule. |
| Local PACS checkout and sender API expectations differ | Windows posts to `/orders/upsert` and `/orders/cancel`. The inspected Gateway defines health, imaging-worklist GET and admin completion, not those order routes. | Inspect the actual deployed receiver revision/capabilities before planning migration. This discrepancy does not prove the running clinic API is broken. |
| State qualifiers are not represented by the current shared model | `source_state_code` is a single code. Source evidence also includes reception `hold_yn`/`hold_opd` and order `act_yn`; compound semantics are unverified. | Before live normalization, define the minimal fixed qualifier fields and verified combinations, or prove those qualifiers irrelevant to the selected meaning. Do not silently discard them and map every row solely by `proc_gb`/`dc_yn`. |
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

Next, agree the new normalized-source wire contract and synthetic receiver cases
against this actual repository. Keep v1 available without semantic changes. No
new route name, schema version, mapping, query, publisher or live migration is
approved by this inspection. The reader gate below remains incomplete, including
the deployed PACS contract and source qualifier/coverage questions.

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

No executable transport/schema is added in this review stage. The KaosClinic
receiver revision is now recorded; resolve the gaps against its actual code before
producing shared synthetic wire fixtures and ingestion contract tests. No live API
request, source query or receiver test execution was performed in this inspection.
