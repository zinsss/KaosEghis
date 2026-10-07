# KaosOrders Source-Side Shadow Foundation

Last updated: 2026-10-07

## Status and Current Decisions

**Latest grid-detail request:** the operator wants the EMR-selected patient's
prescription name, daily quantity, frequency/count and days as shown in its orders
grid. An [offline current-day query draft](kaoseghis-current-day-orders-query.md)
now includes `qty`/`divide`/`days` as independent candidate source facts. A separate
[approved one-row check](kaoseghis-order-grid-numeric-evidence.md) confirmed exact
grid name/number correspondence and PostgreSQL `numeric` types on 2026-10-07.
All-category coverage, numeric null/domain/scale policy and production approval
remain unresolved. A [separate bounded full-field diagnostic](kaoseghis-current-day-read-evidence.md)
subsequently read 269 current-day candidate receptions and 1,025 linked orders,
including 7 no-order receptions, with verified closure in 74.467 ms. Only sanitized
counts/timings were reported. This is a one-shot observation, not runtime enablement
or complete source authority; the original draft SQL remains unchanged.
This does not add fields to a receiver model or silently assign dose semantics.

**Preferred polling direction, not enabled:** the
[full-snapshot recommendation](kaoseghis-current-day-read-evidence.md#full-snapshot-polling-recommendation)
uses a fresh bounded whole-current-day read for each refresh, with serialized
connections, coalesced requests and post-close validation. The one-shot total was
146.837 ms; server load and repeated clinical-hours impact remain unmeasured.
Full-fact comparison can detect observed edits/removals and state changes without
inventing edit timestamps, but cannot capture every transient change. Suppressing
unchanged delivery is only appropriate when the receiver already holds matching
valid state in the active current-day session/generation. Restart, rollover or a
fresh-snapshot request requires a fresh full snapshot. Keep state memory-only,
preserve valid same-day state on source failure, and leave session/transport and
all production source-evidence gates unresolved. No receiver or runtime change is
authorized by this recommendation.

**Current implementation handoff:** the [2026-10-07 complete-order design](kaoseghis-current-day-orders-design.md)
records receiver `3813b52` acceptance of the four synthetic text facts and the
sender decision for a separate `kaosorders.current-day-orders` version 1 /
`kaosorders-current-day-orders-v1` identity. The production mapping revision is
unassigned. Receiver review must precede a new complete synthetic model; v2 and
the existing coordinator cannot accept it. This milestone is documentation-only.

**Latest operator decision:** [current-day, memory-only board](#current-day-memory-only-decision-2026-10-06).
The EMR database is the sole durable source of patient/order truth. KaosOrders
must not persist patient/order state; at the KST day change, clear the transient
board and start the new day. This supersedes the production persistence/history
requirements below, not the historical synthetic test results. No running system
or stored data was changed by this documentation update.

The latest [controlled source-evidence review](kaoseghis-source-evidence-gates.md)
pins receiver `890a4dd4ce992f2598c85557513cd2c70b098a2b` and records completed
v2 receiver-only synthetic parity/persistence/recovery separately from unresolved
source authority. A subsequent approved catalog-only operation found 4 reception
view links and 3 order view links, with physical closure verified in 0.101 s;
see [sanitized evidence](kaoseghis-source-structure-probe.md#approved-observation).
No clinical rows, definitions or identifiers were returned.
The [follow-up metadata review](kaoseghis-source-metadata-followup.md#results)
confirmed four unique views (three shared) and an effective public-schema CREATE
privilege, with verified closure in 0.0717 s and 0.0750 s. No clinical rows or
definitions were read and no privilege was exercised or changed. All eight source
gates remain blocked, including normalization without hold_opd and now a concrete
least-privilege finding. Vendor information is not expected; see the
[operator/admin next decisions](kaoseghis-source-evidence-gates.md#next-practical-decision).
More equal snapshots or successful reads cannot establish save authority. Transport remains
gated. The sender still has no v2 outbox or acknowledgement consumer, and its v1
synthetic outbox is not v2 proof.
That review's handoff supersedes historical next-step lists below.

### Source-Faithful Order Display: 2026-10-06

The operator clarified that KaosOrders should show the actual EMR orders as they
are, rather than substitute a special code-to-business-label translation. Preserve
the source order code and the EMR's order name. Do not rename a national-flu order
to a different fixed label, synthesize a vaccination order from an empty child
list, or replace one code with another. UI grouping/badges, if retained, organize
the source facts; they must not rewrite the order's identity or name. This does
not approve new category/fee/visibility rules or discard previously reviewed rules.

The operator reaffirmed the already-agreed interaction: the patient grid is a
summary; selecting a patient opens that encounter's **complete order list**.
Show the actual source orders with their original codes/names in that detail view,
including non-billing and unclassified orders. Summary categorization or reviewed
fee exclusions must not silently remove rows from the complete detail list. Retain
the supplied state of cancelled child rows rather than present them as active.
This does not bring cancelled encounters back into the agreed encounter scope.
The new national-flu item should simply appear as itself in this list; no special
vaccine-code-to-label mapping or new overview pill is requested by this decision.

The operator initially planned a new national-flu item with no billing or payment
on a disposable visit, then reported adding/sending it on one actual vaccinated
patient's visit on 2026-10-06. See the narrow read-only
[named-order observation](kaoseghis-named-order-observation.md). Do not treat this
as a disposable record or change it for testing. The intended check is whether
the actual entered order is represented faithfully, not mapped to an invented
label. No-charge status must not be used to hide it.

The operator explicitly clarified that KaosOrders views today's actual orders;
it is not an insurance, claims or payment workbench. Do not make billing
eligibility/insurance/payment configuration a prerequisite for displaying an
order, and do not filter the complete detail list on those grounds. This does
not silently remove previously agreed reception-state facts or change the
cancelled-encounter exclusion. EMR configuration remains operator-controlled.

The existing offline `OrderFacts`/v2 wire facts contain order code, type and
department but no order-name field. Source-faithful name display is therefore
required by the agreed complete-order detail view, not an already implemented
capability. This is a source/contract implementation gap, not a newly proposed UI
feature or a reason to replace the agreed detail view with category labels. Review
the exact source field and a separate bounded catalog-name/contract design before
implementation. This is not authorization for arbitrary clinical text, notes,
diagnoses or raw-row export. Keep existing v1/v2 models, strict validators,
fixtures/hashes and runtime unchanged until that separate change is approved.

The later operator-scoped [catalog check](kaoseghis-named-order-observation.md#approved-single-catalog-follow-up)
found one linked child with an empty catalog code and NULL standard-name field.
An operator-supplied screenshot shows the expected code/name in the prescription
grid, but the two queried columns did not establish the display source.
This exposed a source/contract gap,
not permission to substitute the operator's expected label, discard the child
as a fee, or weaken v2's nonempty-code requirement. No category, financial,
transport or board behavior changed.

The subsequent [reviewed display-source check](kaoseghis-order-display-source.md)
confirmed an exact `user_cd` code match and `user_nm` name match for the same
approved singleton. Only aggregate equality counts were returned, after verified
physical closure in 0.0507 s. This answers the immediate field-location question,
not universal source semantics or the existing v2 representation gap. Keep the
original catalog facts distinct; do not silently replace `order_code`, infer a
label or alter v1/v2 fixtures/hashes. The next receiver discussion is a separate
bounded original user/display-code and name representation with explicit
null/blank rules. Cross-category coverage, safe bounds and source authority remain
unresolved. No new runtime query, transport, board or PACS change is enabled.

The [2026-10-07 synthetic order-text proposal](kaoseghis-order-text-proposal.md)
now preserves separate catalog code/name and user code/name facts with the full
order key, without altering v1/v2. It is an offline component only, not a session
schema or approved source mapping. Receiver `fd5e4b8` was reviewed read-only; its
existing v2/session facts cannot yet carry these fields. The linked next handoff
requests receiver field-policy agreement and a separate synthetic proof, with no
wire, transport or board implementation. That field-policy/proof handoff is now
complete at receiver `3813b52`; the full-model design linked above supersedes it.
All live source gates remain open.

### Current-Day Memory-Only Decision: 2026-10-06

The operator clarified that past clinic days are over, the EMR DB is the source
of truth, and KaosOrders must not save patient/order data. The dummy still exists,
but artificial date-moving is not part of the normal clinic workflow.

```text
EMR database (sole durable patient/order source)
  -> KaosEghis-emr (serialized read-only access, detached validated current-day data)
  -> KaosOrders (current-day in-memory projection)
  -> browser board (transient display only)
```

- Source polling covers the current KST clinic date only. No historical backfill,
  previous-day rescan or later correction of completed days is required. Remove
  cross-date move/backdate/history experiments from the acceptance checklist.
- KaosOrders does not durably store patient/order projections, payloads, a replay
  history or patient/order-bearing logs. Browser cache/storage/service workers,
  crash dumps and swap must not become an unintended persistence path. Deployment
  verification for those controls belongs to a later receiver milestone.
- At KST midnight, discard the old day's in-memory board state and start the new
  day. This is an explicit display lifecycle rule, not an authoritative empty EMR
  snapshot. Do not delete or modify any EMR record.
- On receiver restart, start without patient/order state and request a fresh
  validated snapshot for today. No local patient/order database is restored.
  Until that succeeds, represent unavailable/loading state, not verified emptiness.
- Same-day additions, edits, cancellation/removal, completion, payment and return
  to hold must still come from source observations. The receiver must not invent
  a durable clinical status independent of the EMR.
- Today's non-cancelled encounters remain in the proposed Orders scope even when
  they have no orders. The later 2026-10-06 operator clarification excludes
  cancelled encounters and their child rows from that future Orders projection.
  Keep all scoped children of included encounters, including cancelled child orders,
  fees and unclassified rows, with the four-part order key intact.
- The operator further confirmed on 2026-10-06 that today's national-influenza
  vaccination visits have no EMR orders. This is an expected no-order workflow:
  retain each otherwise-scoped encounter with an empty order list. Do not invent
  a vaccine order or infer vaccination type from the absence of orders. This does
  not attribute all 122 observed no-child receptions to vaccination, and does not
  generalize to private influenza, COVID or other visits. No-order counts alone
  are not evidence of missing storage or grounds for broader database grants.
- A previously included encounter becoming cancelled is omitted from the next
  verified complete current-day Orders projection, removing its prior board state.
  A restored non-cancelled encounter can reappear in a later complete snapshot.
  Absence means out of the agreed scope, not proof of a particular clinical event.
  The source must still recognize verified cancellation to apply this scope; unknown
  or ambiguous states must not be silently excluded.
- A failed/partial/timed-out read must not clear a populated current-day board or
  imply order deletion. Validated complete replacement remains distinct from
  availability failure. Old-day or old-session responses must not repopulate a
  reset board; authentication, session fencing, ordering and rollover races need
  an explicit memory-only delivery design.
- A durable patient/order outbox/replay ledger is not required for this workflow.
  Pending old-day work must not be relabeled as today. Do not mutate existing v1
  synthetic stores, fixtures or hashes; their durable-cursor/receipt semantics are
  historical offline proofs, not an approved volatile-session protocol.

This is a new sender-side product decision requiring a KaosOrders design handoff.
Do not claim receiver implementation/parity already matches it, reinterpret v2
epoch/revision fields silently, remove validators, or retrofit runtime endpoints.
The separate synthetic SQLite receiver/outbox tests remain intact but no longer
define the desired production persistence architecture. Configuration/authentication
design is separate from the prohibition on patient/order persistence.

The cancelled-encounter clarification is a **future Orders-only scope decision**,
not a filter added to the shared destination-neutral source or KaosPACS. Existing
v1/v2 models, six-state synthetic fixtures/hashes and the receiver's pure session
proof remain unchanged. The future current-day session contract must explicitly
declare its narrower encounter scope before any reader or publisher is enabled.
No order-level cancellation rule was removed. All source-evidence gates remain open.

No query, EMR UI operation, data deletion, grant change, PACS change, deployment,
restart or publication was performed for this decision. The production day reader
stays UNAVAILABLE. `/api/v1/order-snapshots` remains prohibited for normalized data.
Next validate missing **normal same-day** source workflows and design the
receiver's volatile reset/resynchronization behavior with synthetic data only.

Documentation-only verification: the existing 29 evidence-to-v2 boundary tests
passed in 0.84 s, and `git diff --check` passed. These preserve the blocked reader;
they are not proof of an implemented memory-only receiver. The full suite was not
repeated because no code/test/fixture changed; its preceding results remain above.

This supersedes the older laptop/LMDE, completed-patient board, PACS-only hold tiles,
and per-chart F7/20-second designs. KaosOrders runs on **KaosClinic**. The viewer is
a continuously running **Raspberry Pi 4 with Raspberry Pi OS, Chromium kiosk, and
a 21-inch touchscreen**. The Pi must persist no patient/order data. Browser storage,
cache, swap, crash recovery, and maintenance controls belong to that deployment,
not this repository.

The planned board is a responsive patient grid using Korean category pills. Only a
confirmed `보류` encounter with at least one active relevant order is visible. Touching its tile
shows every allowlisted normalized order; touching anywhere again closes the detail.
The board never infers clinical completion. No board/kiosk UI was changed here.

The Windows foundation is **disabled and not connected to runtime triggers**. It has
a blocked reader interface, typed in-memory normalization, synthetic fixtures,
complete-snapshot comparison, and an offline proposed v2 serializer. There is no
source SQL, production mapping catalog, HTTP client, production outbox, persisted
production snapshot, or publish path. Enabling settings cannot bypass missing approvals.
The separate [synthetic delivery outbox](kaoseghis-emr-delivery.md) now tests local
transaction/restart/retry behavior only; its plaintext fixture store must not hold PHI.

A destination-neutral [offline source model](kaoseghis-emr.md#offline-source-model-2026-10-03)
now lives in `core/emr_source.py` and `core/emr_source_shadow.py`. This is the new
source-interpretation/comparison foundation, not the old board-filtered serializer.
Its real day reader is also blocked; no Orders adapter or server integration is enabled.
The 2026-10-03 offline regression run passed 120 new source-model cases and 528
targeted tests overall, including the retained board prototype and shared DB reader.

On 2026-10-03 the operator corrected the server to `zin@kaosclinic`. Read-only SSH
inspection found `/srv/projects/KaosOrders`, clean on `main`, revision
`b5f7ccd8257f29235c90b11499b8ed352fc06d0d`. Its implemented v1 API accepts
per-encounter category snapshots and stores XRAY/BMD/ECG only. It does not accept
the new shared source model, distinct completion/payment states, structured edits
or authoritative day reconciliation. Its September 30 deployment/board plans are
older than the current decisions above. Remote code/docs and services were not
changed; the running deployed image/API was not tested.
The old normalized v2 proposal remains a superseded offline reference, not the
agreed source contract. See the [source contract review](kaoseghis-emr-contract-review.md)
for actual receiver gaps, field boundaries and acceptance cases. This does not
approve a live day reader or sending the shared snapshot to the v1 endpoint.

### Pinned Normalized Contract Parity: 2026-10-04

KaosOrders reference `7c9275fb74680f46e4d459c821c7d501758c6b1c` now contains a
disabled normalized-source contract and in-memory receiver tests. It still has no
production intake route. Its contract version 1 is unrelated to the existing
per-encounter `/api/v1/order-snapshots`; that route is prohibited for this payload.

The Windows offline serializer `core/kaosorders_normalized_source.py` matches both
reference fixtures exactly, including full and verified-empty days, nulls, row
ordering, canonical decimal strings and SHA-256. Source qualifiers are mandatory
fixed raw Y/N facts (hold_yn/hold_opd, dc_yn/act_yn), never inferred clinical meaning.
The later [qualifier decision proposal](kaoseghis-emr-contract-review.md#qualifier-decision-proposal-2026-10-05)
does not change this implemented v1 requirement. Receiver `6837845` subsequently
accepted consistent exclusion of raw `hold_opd` in a separate v2 projection; the
sender-only synthetic implementation is described below. Source-policy and
production delivery gates remain unresolved.
It retains all source encounters/orders and distinct consultation/payment completion,
with no category, pill, visibility, fee, detail or PACS fields. Explicit null sex
can be preserved, while blank sex fails with a fixed redacted reason.

Metadata is supplied by synthetic tests only: clinic_id, batch_id, source_epoch
and revision, with an explicit synthetic gate. The serializer neither creates nor
persists production ordering. Durable cursor allocation, exact retry storage,
restart/ack recovery and authenticated source scope still need design. No approved
endpoint/token, production query, publisher, persistence, settings or trigger was
added; the reader remains blocked and existing runtime is unchanged.

The separate v2 sender modules now use `kaosorders.normalized-source` version 2,
`kaosorders-all-orders-v2`, and `synthetic-v2`. Encounter qualifiers contain exactly
required Y/N `hold_yn`; `hold_opd` is always forbidden. Order flags remain strict
Y/N. No v1 conversion, outbox migration, production mapping or live reader is
provided. Full/empty v2 synthetic fixtures match independently constructed sender
output byte-for-byte; **receiver v2 parity is still the next step**, before any
receiver storage work. See [v2 compatibility and handoff](kaoseghis-emr-contract-review.md#synthetic-v2-sender-2026-10-05)
and [fixture provenance](../tests/fixtures/normalized_source_v2_provenance.md).
The earlier board-oriented v2 proposal remains superseded and unrelated to this
normalized-source version. No endpoint or token has been approved.

See [v1 field-by-field compatibility and source blockers](kaoseghis-emr-contract-review.md#synthetic-parity-2026-10-04)
and [fixture provenance](../tests/fixtures/normalized_source_v1_provenance.md).
Return these exact outputs to the KaosOrders session for receiver-side synthetic
parity/edge-case review and durable ordering design. Keep production intake, the
existing v1 API and the board untouched until the remaining gates are resolved.
Verification passed: 317 focused serializer/source-model tests, all 2,424 isolated
Windows tests, and direct synthetic checks against the pinned receiver's parser
and in-memory reconciler. Runtime acquisition, publishing and storage remain off.

### Offline Delivery Milestone: 2026-10-04

After reviewing the uncommitted receiver documents at `zin@kaosclinic` on base
`7c9275fb74680f46e4d459c821c7d501758c6b1c`, the operator approved the next
sender-side milestone. The serializer parity work was not repeated or changed.
`core/kaosorders_outbox_shadow.py` implements explicit synthetic store enrollment,
per-day revisions under one supplied producer epoch, one immutable pending batch
per day, durable coalesced refresh requests and exact internal receipt checks.
Its tests exercise process exits before/after seal and acknowledgement commits.

No production epoch allocator, encryption, authenticated acknowledgement/recovery
protocol, HTTP client, retry worker, source query, settings or runtime importer is
provided. Internal `SyntheticAcknowledgement` objects are not a new wire contract.
Missing state is not recreated; paused/receiver-ahead/lost-state recovery requires
later explicit design. The [delivery document](kaoseghis-emr-delivery.md) is the
current implementation boundary and receiver handoff; earlier no-outbox statements
describe the prior parity stage, not production enablement.
Verification: all **2,496 isolated tests passed**, including **72 new outbox cases**.
The pure serializer and both pinned contract fixtures are unchanged.

The [initial receipt review](kaoseghis-emr-contract-review.md#synthetic-receipt-review-2026-10-04)
found historical duplicates hiding receiver progress at `40c6a49`. The
[acknowledgement recheck](kaoseghis-emr-contract-review.md#synthetic-acknowledgement-recheck-2026-10-04)
against `02acc8a93c0c373d4e53d181058b46ce1fb405c7` confirms the correction:
current active retry is duplicate, same-epoch history is stale, and retired epochs
require resync across days. Stale/resync durably preserve pending bytes and pause
without adopting receiver progress or allocating another revision. Verification:
413 focused sender tests, 24 receiver store tests, and five direct synthetic
compatibility scenarios passed. Only sender tests/docs changed; no store,
validator, runtime or delivery enablement changed. Production recovery decisions
and all source-evidence gates remain open.

### Source and Application Ownership: 2026-10-03

[KaosEghis-emr](kaoseghis-emr.md#connector-ownership-decision-2026-10-03) is the
shared read-only source adapter, with separate KaosPACS and KaosOrders deliveries.
**KaosEghis-emr owns reusable EMR interpretation and source-change detection;
KaosOrders on KaosClinic owns board-specific processing and persistent state.**
This supersedes the earlier same-day connector-only restriction. Processing on
Windows is allowed; source interpretation and application decisions are separate.

- Windows owns the shared queue/mutex, reviewed SQL, key and field validation,
  snapshot coverage/consistency evidence, privacy allowlists and transport. Close
  the physical EMR connection before local processing or delivery; a slow receiver
  must not hold up another source job by retaining its DB connection.
- KaosEghis-emr interprets verified EMR reception/order codes, normalizes approved
  fields and detects source edits, state transitions, disappearance/restoration and
  reused keys by comparing validated source snapshots after connection closure.
  Preserve approved source facts with normalized meanings, including distinct
  진료완료 (`30`) and 수납완료 (`40`); receivers need not duplicate EMR table logic.
- KaosOrders owns order categorization, reviewed fee exclusions, visibility, badges
  and grid/details. It validates and applies source observations idempotently,
  rejects stale updates and maintains its own application state. A source transition
  to 보류 is a fact from Windows; whether it creates a tile is a KaosOrders decision.
  Under the later source-faithful display decision, these presentation decisions
  must not substitute order codes or rename the EMR's actual order. Name transport
  still needs a separately reviewed field/contract design.
- KaosPACS receives directly from the sibling PACS adapter, not through KaosOrders.
  KaosOrders filtering or availability must not determine PACS order delivery.
- Read the approved day's encounter/order facts across relevant states, including
  waiting, hold, completed-unpaid, paid and cancelled. Do not send only current
  hold patients: unchanged child orders can become visible or hidden solely from
  reception changes, and edits may leave a paid encounter's status unchanged.
- Use the reviewed source encounter key and full order tuple including `ord_ymd`.
  A current-row key is not an immutable lifetime order instance. Compare approved
  structured contents as well as status; key reuse must not retain old details.
- No reliable source edit/cancel timestamp is verified. `observed_at` records our
  read time. Changes reverted between observations remain undetectable without
  separately verified history; do not invent event timestamps.
- Failed, partial or inconsistent reads are not authoritative empty days. Windows
  reports a non-authoritative outcome; KaosOrders retains its last valid state.
- Shared source processing and receiver-owned board rules do not permit raw-row
  exports, arbitrary SQL, free-text notes or additional patient identifiers. Preserve the
  Orders privacy boundary: no resident ID, DOB, phone, address, diagnosis or notes.
  Any necessary transient DOB-to-age projection stays local and discards DOB.

The legacy `kaosorders_source.py` normalizer, `kaosorders_shadow.py` ledger and
synthetic v2 JSON remain **disabled reference/test artifacts**, not an approved
implementation of this split. Common validation helpers now come from `emr_source`;
the new shared model/comparison has no category, fee or visibility rules. Its source
lifecycle tests are separate from the retained legacy board tests. Receiver
classification, update-application and board tests still belong in KaosOrders.
No runtime code, query or endpoint is migrated by this offline stage.

Next gates, in order:

1. Resolve the reviewed KaosOrders v1 gaps and agree a versioned normalized-source
   schema, approved raw/normalized meanings, field allowlist, key scope, structured
   edit fields and authoritative snapshot semantics. The old v2 example is not approval
   of a new API; baseline/delta delivery and recovery rules also need review.
2. Test Windows source interpretation/change detection and receiver application rules
   with synthetic lifecycle scenarios. Test acquisition/serialization through the
   shared coordinator using mocked DBs only, including close-before-processing.
   The internal source model/comparison and mocked cleanup tests are implemented;
   synthetic wire parity with the pinned draft is now implemented. Production
   receiver rules, durable ordering and actual day acquisition remain future work.
3. After separate approval, verify a bounded day-wide query and compare shadow
   results without publishing or replacing PACS. Complete-day consistency, payment,
   reception removal/reuse and other-category behavior still need evidence.
4. Review authenticated delivery, acknowledgements, stale/retry ordering, restart
   and retention before enabling publishing. Board UI work follows the verified
   foundation and receiver contract, not the current disabled serializer.

## Source Evidence and Blockers

The initial foundation evidence below comes from existing code/documentation, not
a verified production schema. No production query was used to build that foundation.
The separately approved, limited laboratory and reception-status metadata reviews
are recorded afterward; they do not establish full source-reader or reconciliation
semantics.

| Required field | Non-sensitive provenance | What remains unproven |
| --- | --- | --- |
| Encounter ID | The approved 2026-10-02 catalog inspection found a valid unique index on `public.h1opdin.recept_no`, a NOT NULL column. | Stability, reuse after removal, patient linkage over transitions, encounters without orders, cancellation/removal behavior. |
| Order ID | The approved 2026-10-02 catalog inspection found a valid unique index on `(recept_no, ord_ymd, ord_no, ord_seq_no)`, all NOT NULL. A supervised follow-up observed a deleted full key reappear with different order code/type/department. | The tuple identifies a current source row, not an immutable lifetime order instance. Restoration/replacement and key-reuse handling must be reviewed before enabling reconciliation. The older three-part PACS join omits `ord_ymd` and is not sufficient evidence for a KaosOrders key. Existing PACS behavior is unchanged. |
| Chart number | Flu joins `h1opdin.ptnt_no` with `hz_mst_ptnt.ptnt_no`; patient-context SQL reads `hz_mst_ptnt.ptnt_no`. | Reception linkage for a whole-day projection. Chart number cannot substitute for encounter ID. |
| Name, sex, age | Context reader uses `hz_mst_ptnt.ptnt_nm`, `sex`, `birth_ymd`; flu calculates age at `h1opdin.clinic_ymd`. Older injection notes mention `ageday`. | Operator approved exact M/F/null and completed-years-at-clinic-date conventions on 2026-10-05; safe age derivation and unseen source values remain unverified. The shadow boundary accepts Korean sex plus integer age, never DOB. |
| Clinic day | Flu reader uses `h1opdin.clinic_ymd`. | Authoritative day membership for every relevant encounter and order. |
| Reception state | Flu filters `h1opdin.proc_gb IN ('30', '40')`; supervised 2026-10-01 UI comparisons observed `10` on one 진료대기 encounter, `25` on one 보류 encounter, `40` on five 완료 encounters, and `50` on one 취소 encounter, all with `hold_yn=N`, `hold_opd=N`. Code-30 counts progressed from one to two to three as expected by the operator. Agreed labels: `30` 진료완료 (수납 전), `40` 수납완료. | Not a complete state dictionary or enabled mapping. Other codes, compound-state rules and transitions remain unverified; dictionary access is denied to the configured reader. The 30/40 terminology is operator-confirmed, not dictionary-derived. |
| Order state | PACS treats `h2opd_doct_ord.dc_yn = 'Y'` as cancellation in its imaging join. | All-category state, withdrawal, replacement, deletion and restoration semantics. Do not generalize automatically. |
| Category/detail | PACS uses `proc_dept_cd`, `ord_cd`; old notes list `ord_type`, `medfee_nm`. | Reviewed category and static display-spec catalogs. No name matching or raw descriptions. |
| Timestamps | PACS timestamps come from MWL. | Verified reception/order/update timestamps are unavailable. MWL is not a permitted KaosOrders source. Omit unverified times. |
| Complete read | Existing queries are domain-filtered PACS/flu readers. | No authoritative daily all-encounter/all-relevant-order snapshot is proven. Successful fetch or zero rows alone is not completeness. |

Relevant files: `core/pacs_polling.py`, `core/weekly_age_reporting.py`,
`core/kaospacs_patient_context.py`, and historical `docs/kaoseghis-inj.md`.
The injection plan is historical evidence, not approved current behavior.

### Controlled Aggregate Source Evidence: 2026-10-04

Starting Windows revision: `e12685dde19080d97179c00476362feba9d34c8f`, clean on
`main...origin/main`. Receiver reference `a837d385ff367e4f72310226d8bc8439fc0c50fe`
was inspected in a temporary detached checkout. Its acknowledgement/offline-recovery
stage is complete; this review did not repeat or implement recovery/transport.

The operator approved a bounded closed-hours, read-only review and confirmed
Friday **2026-10-02** as populated and Saturday **2026-10-03** as having no visits,
both KST. No weekday was assumed empty. Existing key/index observations and the
single-visit edit/removal/reuse and `25 -> 30 -> 25 -> 50 -> 10 -> 25` transition
evidence were inventoried, not repeated with patient-level reads.

Before source access, mocked tests covered each new operation and its failure/
privacy/closure paths. The fixed parameterized schema and day statements in
`tools/inspect_source_evidence.py` were reviewed. Identifiers are used only inside
server-side joins/key counts, never selected into client output. No patient name,
resident number, DOB, phone, address, diagnosis, notes, order labels or raw patient/
order rows were queried for output. DOB was not queried at all. The existing
connection setting was consumed privately through read-only local settings access;
no credential was displayed, exported, changed or passed on the command line.

#### Scope and Consistency

- Candidate membership: every `h1opdin` reception with exact bound `clinic_ymd`,
  without status, payment, hold, category or order-existence filters.
- Child population: every `h2opd_doct_ord` row linked by reception key, without
  cancellation/category filters and without restricting its order date.
- Independent crosscheck within the same statement: orders dated that clinic day,
  including a count not linked to that day's reception population.
- Four-part duplicate/null/blank-key counts stay on the server. No-order receptions
  remain in membership. Sex values are counted per reception, not per unique patient.
- All these aggregates share one reviewed SELECT/CTE command snapshot. The schema
  read and each day read are separate observations, not one multi-query snapshot.
- Cap-plus-one bounds are 10,001 receptions and 100,001 orders for detection;
  257 aggregate rows detect report overflow. No bound was reached. Overflow or
  invalid/partial output never becomes an empty success.

Catalog preflight confirmed the three reviewed objects are base tables with SELECT
access. `clinic_ymd` and `ord_ymd` are bpchar; reception/order-parent keys are varchar;
order number/sequence are numeric. The known full-key columns are NOT NULL.
Reception date/patient link/status/flags and sex are nullable in the catalog.
The candidate `hz_mst_ptnt.ageday` column was absent; this is not a search for every
possible age source or proof that no other age representation exists.

#### Sanitized Counts

| Observation | 2026-10-02 populated | 2026-10-03 confirmed closed |
| --- | ---: | ---: |
| Receptions | 173 | 0 |
| Linked child orders | 1,081 | 0 |
| Receptions with no orders | 17 | 0 |
| Orders dated the selected day | 1,081 | 0 |
| Same-date orders outside the day's reception population | 0 | 0 |
| Linked orders with a different/null order date | 0 | 0 |
| Invalid/duplicate encounter keys | 0 | 0 |
| Invalid/duplicate four-part child keys | 0 | 0 |
| Missing patient links / duplicate sex-join excess | 0 | 0 |

Populated-day reception combinations: `40/N/N` = **168**, `50/N/N` = **5**
(`proc_gb/hold_yn/hold_opd`). No code 10, 20, 25 or 30 appeared in this observation;
this does not resolve code 10 or establish all compound-state meanings.

Order combinations (`ord_type / department / dc_yn / act_yn`):

| Type | Department | dc_yn | act_yn | Count |
| --- | --- | --- | --- | ---: |
| 01 | DRUG | N | N | 482 |
| 03 | LAB | N | N | 1 |
| 03 | LAB | N | Y | 82 |
| 05 | BLANK | N | Y | 148 |
| 06 | BLANK | N | Y | 176 |
| 07 | INJ | N | N | 98 |
| UNREVIEWED | BLANK | N | Y | 53 |
| UNREVIEWED | INJ | N | N | 1 |
| UNREVIEWED | UNREVIEWED | N | N | 33 |
| UNREVIEWED | UNREVIEWED | N | Y | 7 |

BLANK represents an empty text value; NULL is a separate bucket. UNREVIEWED is a
server-side privacy mask for values outside the explicit diagnostic allowlist,
not a source code/category or inferred clinical meaning. All 1,081 orders had
`dc_yn=N`; `act_yn=N` totaled 615 and `act_yn=Y` totaled 466. No all-category
cancellation rule can be verified from this sample. No action flag was interpreted
as administration, collection, imaging completion or payment.

Sex counts were **M=62, F=111**; no actual null/blank/other value appeared on this
day. Nullable schema alone does not establish null/blank conventions. Approval of
exact M/F/null mapping and completed-years-at-clinic-date age was requested from
the operator during the review and subsequently granted on 2026-10-05 as recorded
below; this did not enable mappings or prove unobserved source behavior.
No age or DOB values were read or retained.

#### Demographic Policy Approval: 2026-10-05

The operator approved both proposed conventions:

- Exact source `M` means male and normalizes to contract `M`; exact `F` means
  female and normalizes to contract `F`. A true database NULL remains null.
  Blank, whitespace, unknown or other unverified source values remain blocked;
  they must not be coerced to null or `O`. Contract support for `O` does not
  establish a source mapping for it.
- Age means completed years (만 나이) on the encounter's clinic date, not on
  the observation date or today's date. The convention is approved; a safe,
  validated derivation is still unverified. No DOB query/export/persistence is
  authorized by this approval, and the absent candidate `ageday` column does
  not justify substituting another source or guessing age.

This is a documentation-only policy decision, not source evidence or permission
for new live operations. No validator, source model, mapping implementation or
runtime setting changed. Code-10 waiting versus in-progress and the other source
gates remain unresolved. `EghisSourceDayReader` stays UNAVAILABLE and publishing
remains disabled.

#### Closure and Verification

Exactly three live inspection operations ran, without retries or fallback queries.
Each used the shared one-worker FIFO and `Global\KaosEghis-EMR-read` mutex, a
3-second connection timeout, and a 2-second statement timeout. Session settings
were verified as read-only/read-committed before each source statement. Both the
cursor's closed flag and physical connection's closed flag were checked before
aggregate processing. Connection-lifetime timings (excluding queue wait):

| Operation | Seconds | Cursor closed | Physical connection closed |
| --- | ---: | --- | --- |
| Catalog preflight | 0.2077 | yes | yes |
| Populated-day aggregates | 0.5806 | yes | yes |
| Confirmed-empty-day aggregates | 0.0523 | yes | yes |

Focused mocked evidence/shared-reader/source-model tests: **239 passed in 2.32 s**.
Tests cover finite verified sessions, copied parameters, FIFO/closure, every setup/
query/fetch/cleanup failure, safety latching, cap-plus-one overflow, missing groups,
inconsistent crosschecks, expectation mismatch, redaction and the UNAVAILABLE block.
The original shared `run_readonly_query` path and all existing consumers are unchanged.
Only the explicit diagnostic entry point and inspection tool can perform these reads.

Final verification after midnight KST: **903 related isolated tests passed in
41.09 s**, covering evidence/source/shadow/serializer/outbox, shared reader, PACS,
flu, patient context and contention. The broadest offscreen Qt run completed with
**2,561 passed and 26 failed in 145.56 s**. All 26 label/font/layout failures were
reproduced in a temporary untouched checkout at starting commit `e12685d`
(245 passed, 26 failed for those two test files). They are pre-existing under this
runner, not new evidence-path failures; no unrelated UI fixes were made. The full
runner also encountered a test-only WebEngine profile cleanup lock after pytest
finished. No production file/application was cleaned up or restarted. There are
**67 new mocked inspection cases**; database/network/native input remained blocked
in tests, and test mutexes/application data were isolated from the live operation.

#### Remaining Gates

This verifies populated and operator-confirmed empty **candidate table scopes**,
not a complete production source policy. Clinical authority of reception-day
membership still needs sign-off, including nullable dates, historical/archive
coverage and cross-day encounters/orders not present in these two observations.
No undated reception was assigned a day by inference. The single-statement snapshot
does not prove that an EMR workflow commits all related changes atomically.

Still unresolved: code-10 waiting versus in-progress distinction; unseen/null/blank
reception/qualifier combinations; all-category cancellation/deletion/restoration;
masked type/department catalog coverage; unseen demographic source values and a
verified age derivation without querying DOB in this milestone. The conventions
approved above do not supply missing source evidence. Clinical units and event
timestamps were not inferred. Existing single-visit findings retain their limited scope.

`authoritative_snapshot` is always false for inspection results, including an
observed empty scope. `EghisSourceDayReader` remains UNAVAILABLE. No source ledger,
normalization policy, runtime trigger, settings, outbox, HTTP, board, PACS, application
restart or deployment was enabled or changed. `/api/v1/order-snapshots` remains
prohibited for normalized-source payloads. Raw diagnostic files are not committed.

### Supervised Reception Comparison: 2026-10-05

The operator registered a disposable visit and confirmed its clinic date as
2026-10-05 KST and that it was the only visit currently in the waiting list.
Before the live read, `inspect_source_evidence` gained an explicit `reception`
operation. It selects only `proc_gb`, `hold_yn`, and `hold_opd` from the exact
bound clinic date, masks unknown values on the server, and returns grouped counts
and a population total. It does not query patient identifiers, demographics,
orders, text, or additional tables. One reviewed SELECT/CTE command supplies both
total and groups; there is no repeated timer or automatic polling.

The operation uses the existing verified evidence boundary, FIFO and machine-wide
mutex unchanged, including 3-second connect and 2-second statement timeouts.
The 10,001-reception and 257-result sentinels, strict result allowlists, group-sum
crosscheck, and expected-population check fail closed. Failure, overflow, partial
results and unverified closure cannot yield findings or an authoritative snapshot.

Mocked verification before source access: **280 focused tests passed in 2.59 s**
and **944 related isolated tests passed in 45.75 s**. There are 41 additional
cases covering reception-only scope, parameterization, result rejection, approval,
session verification and cleanup failures. Native input, printer, live database
and non-test network access were blocked during tests; mutexes were isolated.

| Operator-confirmed stage | KST observation | Reception count | proc_gb / hold_yn / hold_opd | Connection lifetime |
| --- | --- | ---: | --- | ---: |
| Registered and waiting | 2026-10-05 00:43:33 | 1 | 10 / N / N: 1 | 0.152 s |
| Open for consultation, operator reported ready | 2026-10-05 00:46:30 | 1 | 20 / N / UNREVIEWED: 1 | 0.0523 s |
| On hold after operator F6, isolation reconfirmed | 2026-10-05 11:27:12 | 1 | 25 / N / N: 1 | 0.0545 s |

Exactly three live reception-only operations ran, one per operator-confirmed stage,
without retries, plus the separately documented single shape operation below.
The subsequent reads reused the unchanged, previously tested query and
connection boundary. Read-only mode, cursor closure and physical connection
closure were verified before processing.
No clicks, typing, focus changes, writes or patient/order exports were performed.
The operator was asked to open the dummy for consultation without adding orders
or pressing F6/F7, then reported ready before the second observation.

This observation is a day aggregate, not an identified-patient lookup. Attribution
depends on the operator-confirmed isolated visit and an unchanged population; any
additional reception or unrelated change makes the comparison inconclusive.
All three observations contained exactly one reception. The supervised sequence
supports `10` for waiting, `20` for open consultation and `25` for hold in this test; it does not
verify every transition or authorize a complete production state mapping.

**New qualifier blocker:** the in-consultation `hold_opd` value was masked as
`UNREVIEWED`, meaning it is outside the exact Y/N allowlist and is neither SQL
NULL nor empty text. The raw value was not returned or inspected. No meaning,
format or substitute value can be inferred from the mask. In particular, do not
coerce it to Y/N, interpret it as administration/payment, discard the reception,
or send the diagnostic marker as a raw qualifier. The current strict-Y/N source
model and normalized contract cannot represent this source value unchanged.
It needs a separately reviewed privacy-safe qualifier investigation and, if
necessary, a coordinated contract decision before enabling the production reader.
Do not broaden validators merely to obtain parity.

Five additional synthetic regression cases verify masked reception observation
and rejection of `UNREVIEWED` for each of the four normalized qualifier fields.
After these additions, **482 focused tests passed in 3.94 s** and **949 related
isolated tests passed in 41.98 s**. No source-row fixture was exported.

No source mapping, runtime reader, serializer, publishing, PACS or board behavior
changed. The production reader remains UNAVAILABLE and `/api/v1/order-snapshots`
remains prohibited.

#### Qualifier Shape Follow-Up: 2026-10-05

The operator approved a bounded follow-up while the dummy remained open. The new
explicit `reception_shape` diagnostic uses one fixed parameterized SELECT for the
confirmed clinic date. It reads the same three reception fields and returns only
allowlisted reception code/hold flag, a fixed shape label for `hold_opd`, and counts.
The raw `hold_opd` text, exact length, numeric value, identifiers, demographics and
order fields are never returned. There is no arbitrary field/pattern/SQL input.

Shape labels distinguish SQL NULL, empty text, exact Y/N, lowercase y/n, padded
Y/N in either case, ASCII whitespace, digits, letters, mixed letters/digits, other,
and over-64-character text. The last guard precedes the regular-expression checks.
These are diagnostic shapes, not source codes or clinical interpretations. The
shape section is distinct from the raw-flag aggregate section, and both validators
reject the other section's rows. No trim/case/boolean conversion is applied to
source facts or the normalized contract.

The same shared FIFO, machine-wide mutex, verified read-only session, 3-second
connect timeout, 2-second statement timeout and verified physical closure apply.
Population/output sentinels and count/allowlist checks remain in force. Validation
occurs after closure. Errors return fixed redacted reasons without partial findings;
an empty diagnostic result never becomes an authoritative source snapshot.

Before source access, **529 focused tests passed in 3.03 s** and **996 related
isolated tests passed in 42.04 s**. The 47 additional synthetic cases cover every
shape label, fixed query/output review, approval/scope, session/cleanup failures,
overflow, partial results, section isolation and rejection of raw field values.
Mocks block live DB, native input/printer and non-test network access, with isolated
mutexes. Tests do not include a raw live-source value or patient fixture.

Exactly one live shape operation ran, without retries, at **2026-10-05 00:56:30 KST**:

| Receptions | proc_gb | hold_yn | hold_opd shape | Count |
| ---: | --- | --- | --- | ---: |
| 1 | 20 | N | ASCII_DIGITS | 1 |

Read-only mode and cursor/physical connection closure were verified before
interpretation; connection lifetime was **0.0519 s**. No clicks, focus changes,
typing, writes or application restarts occurred. Live access stopped after this
one observation; it did not probe individual numeric candidates or export digits.

This rules out exact/lowercase/padded Y/N and whitespace for the observed value.
It does not establish whether that number is a flag, identifier, counter or another
code, nor its meaning. In particular, do not treat numeric/nonzero text as true,
export it as an identifier, replace it with a shape label, or widen the contract
blindly. The strict-Y/N raw qualifier incompatibility remains a production blocker.
The hold-return comparison below found N again, but does not establish the numeric
domain or authorize its export. A source-definition review and coordinated contract decision
remain necessary. The production reader, mappings, validators, publishing and
PACS are unchanged and disabled where previously blocked.

#### Hold Return: 2026-10-05

After being asked to press F6 and leave the dummy on hold, the operator reported
ready. Because the previous observation was just after midnight, no live read was
performed until the operator reconfirmed that the same isolated dummy remained
and normal clinic work had not resumed (operator reported a holiday).

One existing `reception` operation then ran for the confirmed 2026-10-05 clinic
date at **11:27:12 KST**, returning exactly one **25/N/N** reception. Verified
read-only mode, cursor closure and physical connection closure all succeeded;
connection lifetime was **0.0545 s**. No retry, additional shape query, UI action,
write, patient identifier or raw numeric qualifier retrieval occurred.

The sampled states now show `10/N/N -> 20/N/(numeric text) -> 25/N/N` for this
operator-confirmed isolated workflow. Thus N was observed again on hold. The
overnight gap was not continuously monitored, and these samples cannot determine
the exact update time or prove the numeric value's role. They do not justify
casting numeric text to Y or assuming that it is a lock owner, clinician ID,
boolean or other known code. The strict-Y/N contract blocker remains.

This follow-up changes only documentation. **529 focused mocked tests passed in
6.54 s**; the broader 996-test result above belongs to the preceding code change
and was not rerun for this documentation-only observation. Source/model/validator
code, production reader block, publishing and PACS are unchanged. The next useful
step is a source-definition review and coordinated representation decision, not
an automatic export of the unknown numeric field.

### Approved Laboratory Metadata Review: 2026-10-01

The operator explicitly approved a limited read-only order-metadata inspection.
Distinct catalog codes/names/type/department were inspected for 2026-09-01 through
2026-09-30, using the existing serialized reader and Windows mutex. Reception keys
were used only inside the date filter; no patient fields or source order-instance
IDs were returned. Connections/cursors closed before reviewing the detached metadata.
The month-wide read finished and closed in approximately 0.24 seconds, with a
2-second statement timeout and a 301-combination result cap (not reached).

Observed laboratory metadata used `ord_type = '03'` and `proc_dept_cd = 'LAB'`,
but this includes urine tests and cannot itself authorize a BLOOD mapping. This is
a recent-use sample, not the full order catalog or proof of specimen/collection method.
There were 32 distinct nonempty catalog codes; empty code/name entries were also
present and must not become mapped orders.

The following is a manually summarized review catalog, not raw order rows or
enabled production mappings. Categories follow the operator-approved rule below;
display labels remain review summaries, not approved production specifications.

| Agreed group | Catalog codes | Proposed review label |
| --- | --- | --- |
| BLOOD under agreed LAB rule | `D0002010`, `D0002030`, `D0002040`, `D0002050`, `D0002070`, `D0013` | CBC components and differential |
| BLOOD under agreed LAB rule | `D1830`, `D1840`, `D1850`, `D1860`, `D1880`, `D1890` | Bilirubin, total protein, ALT, AST, albumin, gamma-GTP |
| BLOOD under agreed LAB rule | `D2263`, `D2611`, `D2613` | Triglycerides, total cholesterol, HDL |
| BLOOD under agreed LAB rule | `D2280`, `D2300`, `D2310` | Creatinine, BUN, uric acid |
| BLOOD under agreed LAB rule | `D2800020`, `D2800030`, `D2800060` | Sodium, chloride, potassium |
| BLOOD under agreed LAB rule | `D3230050`, `D3250010` | Free T4, TSH |
| BLOOD under agreed LAB rule | `D3800010`, `D3800020` | Lipase, amylase |
| BLOOD under agreed LAB rule | `D4300030` | PSA |
| BLOOD under agreed LAB rule | `D6020006` | TB antigen-stimulated interferon-gamma study |
| URINE override; not BLOOD | `D2202`, `D2252` | Urine microscopy and urinalysis |
| BLOOD confirmed by operator | `D3063` | HbA1c: laboratory blood test; include in 채혈 |
| Excluded, confirmed by operator | `D3021`, `D3022` | Finger-stick glucose; do not trigger 채혈 or another laboratory category |

On 2026-10-01 the operator confirmed that `D3063` is a laboratory HbA1c test and
belongs in BLOOD/채혈, while `D3021` and `D3022` are finger-stick glucose tests and
are excluded. These exact-code decisions take precedence over the shared `03`/`LAB`
metadata. They do not classify other unreviewed point-of-care codes. A patient with
only either excluded code must not gain a 채혈 badge; a coexisting approved BLOOD
order can still make the patient eligible under the normal reception-state rules.

The operator subsequently approved the broader rule on the same day:

1. Require exact `ord_type = '03'` and `proc_dept_cd = 'LAB'`, with a nonempty code.
2. Exclude exact codes `D3021` and `D3022` before category assignment.
3. Route exact codes `D2202` and `D2252` to URINE/소변검사.
4. Classify the remaining matching laboratory orders as BLOOD/채혈.

This gives 28 BLOOD codes, two URINE codes, and two exclusions in the reviewed
sample, without maintaining an individual inclusion rule for each blood test.
Keep exclusions/category overrides editable and flag newly encountered codes for
review: a new non-blood laboratory test could otherwise receive the wrong badge.
This is a clinic-approved workflow heuristic, not verified specimen metadata.
Do not infer classification from code prefixes or broad substring matching. The
disabled exact-code fixture policy has not yet been replaced by a production LAB
rule implementation. This inspection did not validate encounter identity, source
state, specimen fields, or complete-day reconciliation semantics.
No code mapping, feature flag, source query implementation, or publishing was enabled.

### Approved Reception-Status Metadata Review: 2026-10-01

The operator approved a separate limited read-only inspection to verify reception
states. Queries used the existing serialized reader/machine-wide mutex, 3-second
connection and 2-second statement timeouts. No patient values or encounter/order
instance IDs were returned, and no database permissions or records were changed.
Successful metadata reads closed their source connections in approximately
0.16-0.22 seconds.

Verified schema facts from PostgreSQL catalog metadata for `public.h1opdin`:

- `proc_gb` is `character varying(10)` with no explanatory column comment.
- `hold_yn` is documented as `수납, 진료 등 진행중인 상태 : 'Y'`.
- `hold_opd` is documented as `진료중인 상태 : 'Y'`.
- Consequently, neither field name alone establishes membership in the 보류 list.
  No numeric status-to-label mapping was inferred from existing flu filters.

Candidate code dictionaries exist: `public.hz_mst_div` (index/label definitions),
`hz_mst_div_detail` (field-key definitions), and `hz_mst_div_key1`, `key2`, `key3`,
`longkey1` (codediv/key/value definitions). A narrow header lookup was rejected
with SQLSTATE `42501` (insufficient privilege). A separate metadata privilege check
confirmed that the configured account has table-level SELECT on `h1opdin`, but not
on any of these dictionary tables. No alternate credentials, grants, or privileged
workarounds were used. The rejected query followed the shared helper's cleanup path.

**Status mapping remains blocked.** Obtain an authorized, non-patient export of
the dictionary definition for `h1opdin.proc_gb`, including its labels and any
required compound-state logic, or ask the database administrator for a narrowly
scoped read-only dictionary view. Broad dictionary access is unnecessary and could
expose unrelated configuration. If no authoritative dictionary exists, plan an
operator-supervised comparison against already known EMR list states, without
changing real patient records. Counts alone are not proof of a status mapping.
Stable keys, cancellations/removals and whole-day completeness remain separate gates.

The operator subsequently approved a one-time elevated UI inspection. The passive
helper `KaosEghis/tools/inspect_reception_status.py` sends no input and opens no
database connection. Its report contains only allowlisted status/header labels,
selection flags, grid structure, and fixed diagnostic reasons, never patient values.
It exits after a bounded inspection; six focused privacy/label/ancestor tests pass.

On this workstation, direct native-handle UIA traversal remained empty even after
elevation. Starting at the operator-captured point `(1834, 169)` and walking to its
same-process `외래리스트` ancestor exposed the `진료대기`, `보류`, `완료`, `취소` tabs.
The observed selected tab was `진료대기`. Grid headers included `상태`, `접수시간`,
`환자번호`, `환자명`, `성별`, `나이`; patient rows/values were not exported or inspected.
No database/UI status pairing has yet been verified. The operator was asked to
select `보류` manually for a subsequent supervised comparison. A future paired
reader must verify the displayed clinic day and unambiguous encounter linkage,
recheck the UI selection, and keep patient values out of reports and persistence.

A subsequent attempt after the operator opened 보류 could not see the pane:
Windows reported the EMR as shell-cloaked (`DWMWA_CLOAKED = 2`). The helper now
checks visibility before point lookup, can wait up to 60 seconds without changing
desktops, and tries bounded points within the pane's current native rectangle.
The supervised wait expired while the EMR was still hidden from the active desktop.
No patient values or database queries were involved. A temporary desktop switch
and return was proposed for operator approval; it is not implemented or automatic.

### Supervised Completed-List Comparison: 2026-10-01

The retry confirmed 보류 was selected; the operator confirmed that list was empty.
No encounter was created or changed for the test. The operator then selected 완료
and explicitly confirmed the displayed clinic day as **2026-10-01**. The UI exposed
30 row objects (not an authoritative day total).

The separate, explicitly launched `KaosEghis/tools/compare_reception_status.py`
sampled five visible chart-number cells in memory, without reading name, DOB,
resident ID or other patient-value cells. It used the shared read coordinator to
aggregate `h1opdin.proc_gb`, `hold_yn`, and `hold_opd` for those chart numbers and the
operator-confirmed day. Matching exactly one same-day encounter per sampled chart
was required. No identifiers were returned by the database query or included in
the saved report. The same EMR process/pane, selected list, and sampled chart cells
were rechecked after the connection closed.

Observed result, **not a production mapping**:

| UI list | Sampled encounters | proc_gb | hold_yn | hold_opd |
| --- | --- | --- | --- | --- |
| 완료 | 5 | `40` | `N` | `N` |

The source connection closed in approximately **0.162 seconds**. No clicks,
keystrokes, desktop switches, source writes, or feature-flag changes were sent.
The report contains only the confirmed day, UI label, status codes, aggregate counts,
closure/timing information, and disabled-mapping status.

This is evidence that `40` occurs in 완료, not proof that it is the only 완료 code
or that every `40` encounter belongs there under every flag combination. The day
was confirmed by the operator, not independently extracted from a UI date control.
At this stage, stable production encounter/order identity, other states (especially
보류), state transitions, and complete-day reconciliation remained unverified. UI chart/day
matching is confined to this diagnostic and is not a production encounter key.

The comparison helper has a UI-only watchdog, disabled while the shared reader may
own a source connection. Its database operation remains a bounded SELECT under
the existing read-only account and mutex. Only a parsed date and up to five strict
ASCII-digit chart literals can enter its one-off query; it does not replace the
planned parameterized production reader. No inspection is scheduled or automatic.
Focused inspection/comparison/coordinator tests: **43 passed**. The complete
isolated repository suite, including the new helpers, passed **1,923 tests**.

### Supervised Cancelled-List Comparison: 2026-10-01

The operator then selected 취소 and reported one cancelled entry. The same helper
used the previously operator-confirmed clinic day, **2026-10-01**, and sampled the
one visible chart-number cell in memory. Exactly one same-day source encounter
matched. The selected list, EMR process/pane, and sampled chart cell were unchanged
when rechecked after the source connection closed.

Observed result, **not a production mapping**:

| UI list | Sampled encounters | proc_gb | hold_yn | hold_opd |
| --- | --- | --- | --- | --- |
| 취소 | 1 | `50` | `N` | `N` |

The source connection closed in **0.1062 seconds**. No UI actions, source writes,
or production mapping changes were made. Only aggregate status metadata, the
confirmed day, and closure/timing information were saved; no patient identifiers
were exported. This establishes an observed 취소 case with `50`, not an exhaustive
mapping or proof of all cancellation/restore transitions. At this stage, 보류 and
진료대기 remained unpaired with source states, and `30` remained unverified. The day was operator
confirmed, not independently read from a UI date control.

### Supervised Hold-List Comparison: 2026-10-01

After a patient naturally appeared in 보류, the operator selected that list and
approved another comparison for the same confirmed clinic day, **2026-10-01**.
One earlier attempt stopped on an unexpected selected tab before querying the
source; another was cancelled while Windows approval was pending. Neither attempt
produced accepted source evidence.

The successful retry sampled one visible chart-number cell in memory and matched
exactly one same-day source encounter. The same process/pane, selected list, and
sampled chart cell were rechecked unchanged after the source connection closed.

Observed result, **not a production mapping**:

| UI list | Sampled encounters | proc_gb | hold_yn | hold_opd |
| --- | --- | --- | --- | --- |
| 보류 | 1 | `25` | `N` | `N` |

The shared reader closed the source connection in **0.0892 seconds**. No UI actions,
source writes, or production mapping changes were made. Only aggregate status
metadata, the confirmed day, and closure/timing information were saved; no patient
identifiers were exported. This is evidence of 보류 with `proc_gb=25` despite both
hold flags being `N`, not proof of every 보류 flag combination or transition.
The clinic day was operator-confirmed, not independently read from a UI date control.

At this stage, 진료대기 and code `30` remained unverified. Stable production keys, order-state
semantics, state transitions, and complete-day reconciliation remain separate
gates. The production reader and publishing remain disabled.

### Supervised Waiting-List Comparison: 2026-10-01

The operator reported one waiting patient and approved comparison of 진료대기 for
the same confirmed clinic day, **2026-10-01**. The helper sampled one visible
chart-number cell in memory and matched exactly one same-day source encounter.
The process/pane, selected list, and sampled chart cell were unchanged on the
post-read UI check, after the source connection had closed.

Observed result, **not a production mapping**:

| UI list | Sampled encounters | proc_gb | hold_yn | hold_opd |
| --- | --- | --- | --- | --- |
| 진료대기 | 1 | `10` | `N` | `N` |

The shared reader closed the source connection in **0.078 seconds**. No UI actions,
source writes, or production mapping changes were made. Only aggregate status
metadata, the confirmed day, and closure/timing information were saved; no patient
identifiers were exported. The clinic day was operator-confirmed, not independently
read from a UI date control.

This confirms an observed waiting-list case with `10`, not an exhaustive rule for
all rows in that list or a verified distinction between registered and in-progress
states. At this stage, code `30` remained unexplained. The four observed list/code pairs do not
prove state-transition behavior, durable encounter/order keys, order-state
semantics, or complete-day reconciliation. Production reading and publishing remain
disabled pending those separate checks.

### Code 30 Presence Check: 2026-10-01

The operator asked whether any encounters currently have `proc_gb=30` and noted
that the Reservation tab is hidden because the clinic does not use reservations.
A one-off, same-day SELECT on the already reviewed `public.h1opdin` table returned
only grouped flags and counts, filtered to `clinic_ymd=20261001` and `proc_gb=30`.
No patient identifiers or other patient values were selected or exported.

| proc_gb | Encounter count | hold_yn | hold_opd |
| --- | --- | --- | --- |
| `30` | 1 | `N` | `N` |

The operation used the shared FIFO reader and Windows mutex, with 3-second connect
and 2-second statement timeouts. Its source connection closed in **0.0939 seconds**.
There were no source writes, UI actions, or production mapping changes.

This is a point-in-time count of encounter rows, not a distinct-patient count or a
UI/state-label comparison. No historical dates were queried. The existence of the
unused Reservation tab did not establish that `30` means reservation. The subsequent
operator confirmation below identifies the observed workflow state separately.

### Operator-Confirmed Code 30 Meaning: 2026-10-01

At the operator's explicit request, a separate bounded lookup returned only the
name of the single current code-30 encounter for manual identification. That name
is not retained in this document or diagnostic files. The shared reader closed
its source connection in **0.1021 seconds**. A subsequent count-only read, also
explicitly requested, found **two** code-30 encounter rows for the same clinic day;
its connection closed in **0.1007 seconds**. A further requested count found **three**,
matching the operator's expectation, and closed in **0.1038 seconds**. The operator
confirmed the result. No records or UI states were changed.

The operator confirmed code `30` as **orders complete but not paid yet**, then
explicitly chose distinct encounter-status labels:

| proc_gb | Agreed label | Meaning |
| --- | --- | --- |
| `30` | 진료완료 | Clinical/order-entry workflow complete; payment pending. |
| `40` | 수납완료 | Payment complete. |

These labels are operator-confirmed terminology, not independently read dictionary
labels. Preserve the historical UI observation of the tab named 완료 above; it is
not being renamed in the EMR. Code `30` is not a reservation state.

Reception workflow completion and payment state are separate from individual order
execution, cancellation, or withdrawal. Code `30` must not by itself mark child
orders completed/cancelled, and unpaid must not be treated as 보류. The existing
board rule remains confirmed 보류 plus an ACTIVE relevant order. No normalization
mapping, source reader, publishing flag, or PACS behavior was enabled or changed.
State transitions and compound flag combinations still require separate verification.

**Blocked:** the reviewed, parameterized whole-day source operation. Do not invent
joins, status codes, IDs, or completeness filters. `EghisKaosOrdersDayReader.read_day`
currently returns `unavailable` without connecting. The `DayReader` interface requires
detached results after cursor and physical connection closure.

### Approved Single-Visit Identifier Baseline: 2026-10-02

The operator supplied their own visit in the hold list and approved a limited
read-only identifier inspection. A catalog-only query inspected the two existing
source tables, followed by one parameterized statement limited to the exact
operator-supplied name and clinic day. Ambiguous patient/visit matches stop the
inspection; no other patient histories or new production tables were queried.
Both reads used `run_readonly_query`, its FIFO and machine-wide mutex, a 3-second
connect timeout, and a 2-second statement timeout. The local connection setting
was read with SQLite `mode=ro`; credentials were not output.

Catalog evidence:

- `h1opdin_pkey` is a valid unique index on `(recept_no)`; the column is NOT NULL.
- `h2opd_doct_ord_key` is a valid unique index on
  `(recept_no, ord_ymd, ord_no, ord_seq_no)`; all four columns are NOT NULL.
- The date is part of source order uniqueness. The previously proposed three-part
  identity is not approved for KaosOrders even if unique in a small sample.
- Index uniqueness does not establish identity stability during edits, or prevent
  reuse of an identifier after its row is removed. Those remain separate tests.

The sample matched exactly one patient and one encounter on the confirmed day.
The encounter state was `proc_gb=25`, `hold_yn=N`, `hold_opd=N`, consistent with the
operator's hold-list observation. Two source order rows were present: one with
`ord_type=05`, empty department, `dc_yn=N`, `act_yn=Y`; one with `ord_type=01`,
department `DRUG`, `dc_yn=N`, `act_yn=N`. Both order dates matched the clinic day;
full keys were nonempty and unique in this sample. These are two source rows, not
two approved board tasks. No meaning for `act_yn`, type `05`, or board eligibility
was inferred from this sample.

Catalog and sample connections were confirmed closed after approximately 0.1512
and 0.1626 seconds respectively. No UI input, writes, clinical changes, delivery,
or runtime reader enablement occurred. No names, chart numbers, raw visit/order
IDs, order descriptions, resident IDs, or source-row snapshots were written to a
local report or this document. Temporary keyed comparison fingerprints were kept
in the diagnostic session, without raw identifiers, for a supervised follow-up;
they are not production IDs or a durable source snapshot. At baseline, edits,
cancellations, deletions, restoration and state-transition behavior were unverified.

### Supervised Test-Order Edit: 2026-10-02

The operator confirmed that the visit is disposable, edited the existing test
order manually, saved back to hold, and requested the follow-up read. The same
bounded, parameterized single-statement inspection and shared reader were used;
the connection was confirmed closed in approximately 0.1809 seconds.

Comparison against the baseline's temporary keyed fingerprints found:

- Patient linkage and encounter identity were unchanged.
- Both full four-part order keys were retained, with no added or missing keys.
- The encounter remained `proc_gb=25`, `hold_yn=N`, `hold_opd=N`.
- One order's inspected fields were unchanged; the other changed `qty`, `days`,
  and `divide`. The remaining inspected fields, including code, cancellation
  flag and action flag, were unchanged. The operator subsequently confirmed that
  all three fields were deliberately edited, so the observed field changes match
  the intended test edit.

This supports identity retention for this particular saved medication edit only.
It does not establish edit behavior for all six board categories, date changes,
replacement, cancellation, deletion, restoration or reception-state transitions.
No raw identifiers or numeric medication values were added to diagnostic output
or this document. No EMR input, writes, production reader or publishing was enabled.

### Supervised Test-Order Removal: 2026-10-02

The operator removed only the medication order from the disposable test visit,
saved back to hold, and requested another read. The same bounded statement
returned one source order row, down from two. The patient linkage and encounter
identity remained unchanged, as did `proc_gb=25`, `hold_yn=N`, `hold_opd=N`.

One full order key was absent; the other key and all its inspected fields were
unchanged. The only remaining row had `ord_type=05`, empty department, `dc_yn=N`,
and `act_yn=Y`. No retained `DRUG` row or `dc_yn=Y` replacement appeared in this
visit's `h2opd_doct_ord` result. The query did not filter orders by cancellation or
action flags, and its 101-row cap was not reached, so this disappearance was not
caused by either filter or truncation. This establishes disappearance from the
inspected source table for this removal, not absence from any history/archive
table or a universal deletion rule for other order categories.

The source connection was confirmed closed in approximately 0.1596 seconds.
No EMR input or writes were sent by the diagnostic. No raw identifiers, patient
details or medication values were persisted in a local report or this document.

The planned reader must detect missing orders using complete authoritative
snapshots, not cancellation flags alone. The unchanged encounter must not be
cancelled merely because an order disappears. This single-visit observation does
not establish whole-day completeness or authorize live reconciliation. At this
point restoration and key reuse were unverified; the requested next step was
re-adding the same disposable test order and comparing its key with the removed one.

### Follow-Up Showing Order-Key Reuse: 2026-10-02

After the operator reported readiness, the same read-only inspection found three
source rows: the unchanged type `05` row and two `INJ` rows, with types `07` and
`06`. All three had `dc_yn=N`; both `INJ` rows had `act_yn=N`. The patient linkage,
encounter key and hold-state fields remained unchanged. The row cap was not
reached, and current full keys were nonempty and unique.

Of the two keys added since the removal snapshot, one exactly matched the deleted
full four-part key and one had not appeared in the original snapshot. The reused
key now had different `ord_cd`, `ord_type`, `proc_dept_cd`, `qty`, `days` and
`divide` fingerprints from the removed medication row. The operator subsequently
confirmed that an injection was deliberately added for testing instead of the
original medication. This confirms a replacement/key-reuse case, not a
same-medication restoration test. The two `INJ` rows do not establish two clinical
injections; drug/administration-row relationships and display rules remain
unverified. No order names or medication values were output.

The source connection was confirmed closed in approximately 0.1756 seconds.
No UI input, writes, production enablement or delivery occurred. The observation
refutes treating this tuple as an immutable historical order-instance ID. A future
complete-snapshot reader must handle disappearance followed by reappearance with
changed content, including category changes, without retaining obsolete details
or treating a withdrawal as permanent. It must not infer a new lifetime instance
from code, row position or a fingerprint. Exact reconstruction of an unobserved
delete/re-add between snapshots remains unproven. The disabled reader and existing
PACS behavior are unchanged.

### Supervised Hold-to-Completed Transition: 2026-10-02

The operator was asked to complete the disposable visit without changing its
injection orders or processing payment, then reported completion. The diagnostic
kept the exact patient/day scope, uniqueness guards, row cap and shared reader,
changing only the expected state from `25` to `30`. No broad day query was used.

The read found `proc_gb=30`, `hold_yn=N`, `hold_opd=N`, with unchanged patient linkage
and encounter identity. The source connection was confirmed closed in approximately
0.1377 seconds. The full order keys were nonempty and unique, the row cap was not
reached, and all sampled order dates still matched the clinic day.

Order rows increased from three to four: two previous keys remained with all
inspected fields unchanged, one key disappeared, and two new keys appeared. The
new snapshot contained one type `05` row (empty department, `act_yn=Y`), one type
`07`/`INJ` row (`act_yn=N`), and two type `06` rows (empty department, `act_yn=Y`).
All four had `dc_yn=N`. The previous type `06`/`INJ` row was absent from the result.
The operator subsequently confirmed that only completion was performed, with no
manual order edits and no payment. Source-row replacement therefore occurred
during this completion-only test, and `30` was observed as unpaid completion.
The internal mechanism remains unverified. Do not infer billing/clinical meaning
for these types or that a vanished row means a clinical cancellation.

This observes the requested `25` to `30` transition for the same encounter, but
does not establish unchanged order identity through completion. The planned board
must gate visibility on reception state independently of order existence. The return
to hold and subsequent cancellation are recorded below; payment remains untested.
No raw identifiers or patient/medication values were written to the test notes,
and no EMR input, writes, live reader enablement or publishing was performed.

### Return to Hold and Added Fee Labels: 2026-10-02

The operator asked whether the rows added at completion were injection fees. A
narrow follow-up requested only order codes and their standard `medfee_nm` labels
within the same guarded single-visit inspection, without notes or free-text fields.
The completion-state guard first found that the visit was already back at `25`
and stopped without reading order details (connection closed in 0.1030 seconds).
The expected-hold query then completed and closed its connection in 0.1025 seconds.

The encounter moved from `30` back to `25`, with `hold_yn=N`, `hold_opd=N`, unchanged
patient linkage and the same encounter key. All four order keys remained, with no
changes in their inspected fields, additions or removals. The two completion-added
keys still matched their completed-snapshot code/type/department fingerprints, so
their current labels could be safely associated with those earlier additions:

| Code | Standard source fee label |
| --- | --- |
| `KK010` | 피하또는근육내주사 |
| `AL801` | 외래환자 의약품관리료-1일분(의원,치과의원,보건의료원 의·치과) |

Both were type `06`, with empty department, `dc_yn=N`, `act_yn=Y`; order and
medical-fee codes matched. These label observations identify an injection
administration fee and an outpatient medication-management fee, not two additional
clinical injections. Keep these billing rows distinct from the actual injection
order when reviewing future category/display rules. No production mapping was
enabled, and no general rule for all type `06` or empty-department rows is inferred.

Only these two standard fee-code labels and aggregate comparison results were
reported. No patient identity, raw visit/order keys, numeric medication values or
free-text notes were written to local diagnostic reports or this document. The
day-wide reader, board, PACS behavior and delivery remain unchanged and disabled
where previously disabled.

### Supervised Reception Cancellation: 2026-10-02

The operator was asked to cancel only the disposable reception/visit, without
deleting the patient or manually removing its orders, and reported readiness.
The same parameterized single-visit query changed its expected-state guard from
`25` to `50`. Patient/day scope, match-uniqueness checks, row cap, timeouts and the
shared serialized reader were unchanged.

The read observed `proc_gb=50`, `hold_yn=N`, `hold_opd=N`, with unchanged patient
linkage and encounter identity. All four full order keys remained, with no added
or missing keys and no changes in their inspected fields. All four rows still had
`dc_yn=N`: one type `05` row, one type `07`/`INJ` row, and two type `06` rows with
empty departments. Cancellation did not remove the reception or its order rows
from the inspected tables in this sample. It did not set an order cancellation
flag on the inspected rows either. The query was untruncated.

The source connection was confirmed closed in approximately 0.1148 seconds. No
UI input, writes, patient-data report, delivery or production enablement occurred.

This confirms that encounter cancellation must override otherwise uncancelled
child rows for the board. A future reader must not leave a cancelled visit visible
merely because orders exist with `dc_yn=N`, and must not equate reception
cancellation with completion of those orders. This supports the existing planned
encounter-withdrawal cascade, not a live mapping or whole-day completeness claim.
At this point cancellation recovery was unverified. The operator then confirmed
that the cancellation list offers reception restoration; that same-visit test is
recorded below. Reception removal/key reuse and payment transitions remain unverified.

### Cancelled Reception Restored to Waiting: 2026-10-02

The operator used reception restoration on the same disposable cancelled visit,
without creating a new reception, and reported that it returned to `접수대기`, not
hold. The diagnostic did not assume a destination code: it removed only the
expected-state condition while retaining the exact patient/day scope, unique
patient/visit requirement, row cap, timeouts and shared serialized reader. It
observed the state of this one restored encounter, not a whole-day state mapping.

The reception changed from `proc_gb=50` to `10`, with `hold_yn=N`, `hold_opd=N`.
Patient linkage and encounter identity were unchanged. All four full order keys
remained, and all inspected fields matched the cancelled snapshot. No keys were
added or removed, the read was untruncated, and every sampled order date still
matched the clinic day. The source connection was confirmed closed in approximately
0.1243 seconds. No UI input, writes, patient-data report, delivery or runtime
enablement occurred.

This verifies restoration to waiting for this encounter, not automatic return to
hold. The operator's `접수대기` wording is recorded as reported; the earlier UI
tab observation named `진료대기` is not retroactively renamed. Both observations
associated waiting with code `10` in their respective samples.

For the planned hold-only board, restored waiting must remain hidden despite the
surviving orders. Cancellation must not create an irreversible tombstone for the
encounter or its unchanged order keys: a later verified return to hold with a
relevant order must be eligible again. The final waiting-to-hold check is recorded
below. Whole-day completeness, payment, other-category behavior and reception key
reuse after actual removal remain unverified. No production mapping was enabled.

### Final Waiting-to-Hold Round Trip: 2026-10-02

The operator moved the restored test visit to hold without editing its orders and
requested the final comparison. The original expected-hold single-visit query
observed `proc_gb=25`, `hold_yn=N`, `hold_opd=N`, after the previous `10` state.
Patient linkage and encounter identity were unchanged. All four full order keys
and all inspected fields matched both the waiting snapshot and the pre-cancellation
hold snapshot; there were no added or removed keys. Keys remained nonempty and
unique, the read was untruncated, and order dates still matched the clinic day.

The source connection was confirmed closed in approximately 0.1122 seconds. No
EMR input, source writes, raw-row report, delivery or runtime enablement occurred.
This completes this disposable encounter's observed state round trip:
`25 -> 30 -> 25 -> 50 -> 10 -> 25`. Completion changed some source order rows;
all subsequent transitions preserved the resulting four keys and inspected fields.

The observed cases should become synthetic regression scenarios before building
the day reader: same-key field edits, physical row disappearance, key reuse with
changed category/content, completion-added fee rows, cancellation with uncancelled
child rows, restored waiting remaining hidden, and return to hold without changed
order data. Do not copy real identifiers or source rows into fixtures. A restored
relevant order must be eligible without requiring its content to change, while
the reviewed fee rows must not be mistaken for extra injections.

This is one encounter and a limited set of order types, not approval of all six
categories, a general lifecycle model, a complete-day query or live publishing.
Payment, reception removal/key reuse, other-category cancellation behavior,
unobserved between-poll changes and whole-day completeness remain separate gates.
The production KaosOrders reader remains unavailable; PACS is unchanged.

### Offline Lifecycle Regression Tests: 2026-10-02

After the operator reported cleanup of the disposable visit, this stage used only
synthetic projection fixtures and mocked database connections. No live inspection
command was run, and no captured identifiers, medication values or source rows
were copied into tests. The real source reader remains unavailable and publishing
is still blocked. No board, production mapping, source SQL or API contract changed.

Added 34 parameterized test cases across `tests/test_kaosorders_shadow.py` and
`tests/test_emr_read_queue.py`, covering:

- Same-key approved detail edits, exact payload replacement, and idempotent retries.
- Complete-snapshot disappearance followed by same-key return, with the same or
  a different category; category replacement without an observed empty snapshot.
- An ignored medication key becoming an injection, and a relevant key becoming
  an ignored fee without leaving stale board content.
- Synthetic consultation/administration/medication-management fee rows not adding
  injections; unknown fee categories still rejecting the entire uncertain day.
- The observed hold/closed/hold/cancelled/waiting/hold sequence with active child
  orders unchanged, including cancellation/restart and restored waiting hidden.
- Failed, partial, timed-out or unverified fee-only reads preserving the last
  valid injection; a failed read also preserving a pending edit and its retry.
- FIFO handoff after a simulated flu-read error/timeout to queued orders, health
  and PACS work, with cursor/connection cleanup before the next connection opens.

Five new cases initially failed: explicitly ignored fee rows bypassed duplicate,
empty-ID and orphan checks. The disabled normalizer now validates parent linkage
and per-encounter order-key uniqueness before excluding reviewed unrelated rows.
Ambiguous snapshots preserve the prior baseline. Reuse across separate snapshots
or across distinct encounters remains allowed; it is not confused with duplicate
keys inside one encounter in one snapshot. No shared connection code changed.

Approved display edits are represented by synthetic, reviewed `detail_code`
entries. Raw `qty`, `days` and `divide` remain rejected projection fields; mapping
these source values to an approved dose/display specification is still future
reader work. Synthetic fee exclusions are not production code/type mappings.
These tests cover the sender's normalized state and proposed payload, not a live
server, UI or a proof of complete-day SQL/identity semantics.

The initial focused shadow/coordinator/import run passed **273 tests**. Tests used
a temporary local app-data directory, mocked driver/input/network boundaries and
test-only Windows mutex names, never the running clinic app's source connection.
The broader targeted regression run passed **407 tests in 73.63 seconds**, including
PACS polling/refresh/delivery, weekly flu reporting, flu diagnostics and patient
context API tests. This was not a full repository test run. Garbage collection was
kept on the test main thread for Qt test stability; that runner-only precaution
did not change application code. The final diff whitespace check passed.

## Shared Reader and Triggers

The [EMR coordinator](kaoseghis-emr.md) retains its existing scheduling and connection
ownership. A future real operation must
enter `run_readonly_query` and its one-worker FIFO/global Windows mutex, never a new
connection or a nested queue. Fixed reviewed SQL and bound day parameters are required.
Optional `params=` binding was added and verified with mocked databases on 2026-10-01.
It supports copied positional/named values without changing existing callers. This
completes the binding capability, not approval or implementation of a whole-day
operation. The focused regression run passed **162 tests**; the full isolated suite
passed **1,950 tests**. No live EMR access or app restart was part of that verification.
The one-off status-comparison diagnostic still uses its previously
validated literals; its existing query behavior was not migrated in this stage.
There is no configurable KaosOrders SQL or connection-string override in this patch.

PACS retains chart clear/load +2-second debounce, clear +30-second follow-up preserved
across loads, five-minute successful-read safety check, startup/reconnect reconciliation,
manual Poll Now, and fail-closed cleanup. F6/F7/BtnF6/BtnF7 remain diagnostic intent
signals, not proof of commit/completion. Chart discovery is defined in the EMR document.

Future integration must reuse these coalesced day requests, not install another timer.
Multiple reads for one day require reviewed consistency, not an assumption that separate
autocommit queries form a consistent snapshot. No Orthanc, KaosPACS, DICOM or MWL read
is introduced. Existing PACS continues its own unchanged integration.

## Offline Prototype: Normalization and Privacy

This section documents the legacy disabled board prototype, not the new shared
`emr_source` model or the approved final
boundary. Under the refined 2026-10-03 decision, verified EMR code interpretation,
source-field normalization, identity validation and privacy belong on Windows.
Category/display mapping and fee exclusions belong in KaosOrders. Any replacement
normalized-source schema needs explicit review; the current combined model is not
automatically suitable for both adapters.

`core/kaosorders_source.py` defines detached reads, mapping policies, encounters,
orders and daily snapshots. Required IDs are non-empty source keys, never derived
from chart number, time, text, category, list order or row position. Duplicate encounter
IDs or duplicate order IDs within an encounter invalidate the day. Multiple encounters
per chart and multiple same-category orders remain distinct.

The exact-code policy has no default production rules. Tests use synthetic `TEST_*`
codes, not a production dictionary. An explicitly reviewed unrelated category is omitted;
unknown categories invalidate the day rather than silently disappearing from comparison.

| Category | Pill | Allowlisted static display-spec fields |
| --- | --- | --- |
| XRAY | 엑스레이 | exam, body_part, view |
| BLOOD | 채혈 | study |
| URINE | 소변검사 | study |
| ECG | 심전도 | exam |
| BMD | 골밀도 | exam, site |
| INJECTION | 주사 | medication, dose, route |

Details come only from exact reviewed catalog entries. Unmapped detail codes produce
an empty specification, allowing category-only display. No raw-text fallback exists.
Injection dose/route combinations require explicit approval; source free text cannot
pass through the current boundary.

Extra fields are rejected, including resident ID, DOB, phone, address, diagnosis, notes,
insurance, SQL, bearer tokens and credentials. DOB calculation is not implemented;
if needed later, calculate transiently after source closure and discard DOB before
constructing these models. Timestamps must be timezone-aware and verified or absent.
Data-bearing representations are redacted; exceptions contain fixed reason codes.
Only count/status summaries are loggable. No rows, payloads, identifiers, or patient
fields are logged or written by the new modules.

## Offline Prototype: Complete-Snapshot Comparison

The ledger below is an offline reference implementation combining source comparison
and board rules. The target keeps reusable source-snapshot comparison in KaosEghis-emr
and board decisions/persistent application state in KaosOrders. Receivers still validate
completeness, duplicates and stale updates. Source-baseline progress and per-destination
acknowledgement must be separate; missed deliveries need full-snapshot recovery.
The prototype's generic CLOSED state does not preserve the required 30/40 distinction.
The following behavior records existing offline code, not an approved new contract.
The new `emr_source_shadow.SourceLedger` implements the source-only comparison
separately; unlike this legacy ledger, it never cascades board withdrawals or waits
for a receiver acknowledgement before advancing its source baseline.

`core/kaosorders_shadow.py` normalizes the entire read before changing state.
A complete read must also assert verified keys/states, whole-day coverage, no truncation,
and source consistency. These assertions describe an approved reader's obligations,
not independent proof or production enablement. Fixtures do not validate real schema.

- 접수 (`REGISTERED`), 진료 (`IN_PROGRESS`), 보류 (`ON_HOLD`) are live; only ON_HOLD with an ACTIVE relevant order is visible.
- 완료 (`CLOSED`) hides the encounter without changing order states. CLOSED to ON_HOLD can show it again.
- 취소 (`CANCELLED`) withdraws the encounter and previously published child orders. The receiver must cascade this withdrawal, never mark completion.
- `WITHDRAWN` explicitly withdraws one order. No order/completed state exists in this contract.
- Missing orders can be withdrawn only from a complete authoritative day. Removing all orders hides the tile without cancelling an existing encounter.
- Missing encounters can be withdrawn only with the same complete-day evidence.
- Failed, partial, timed-out, unavailable, unknown-state, invalid-key, stale or conflicting observations preserve the last validated snapshot.
- The same encounter key changing chart identity is rejected, not silently reassigned.

One pending proposal is allowed. An identical retry returns the same proposal/batch ID;
another read waits for acknowledgement. Acknowledgement advances the memory baseline;
none is sent to a server. A future subscriber must coalesce busy requests instead of
dropping them. Two clinic-day baselines are retained by default. Rollover cannot withdraw
the previous day, and eviction is not a source action. Restart or an evicted day requires
full authoritative reconciliation. There is no persisted outbox or snapshot.

## Superseded v2 Proposal and Receiver Work

See [synthetic v2 example](kaosorders-v2-proposal.json). This combined sender-side
proposal predates the refined source/application ownership decision and is retained
for existing offline tests. It is not the existing v1 contract, not a patient export,
and not approved for production. Reusable source normalization remains appropriate
on Windows, but the proposal's board-category filtering, generic CLOSED state and
non-cancelled/relevant-order filter must not define the shared source boundary.
The serializer needs
an explicit synthetic-fixture argument and has no HTTP transport. Route proposal only:
`POST /api/v2/source/day-snapshots` on KaosClinic, never the v1 route.

The proposal includes clinic day, timezone-aware observation time, random batch ID,
complete-day declaration, reception-state inventory without demographics, and minimal
normalized demographics/orders only for non-cancelled encounters with relevant orders.
The inventory distinguishes no-order encounters from source removal after restart.
It still contains source identifiers: do not log it or forward it to the Pi.
Explicit withdrawals remain separate from closure.

Required KaosOrders-side work under the refined ownership split, following the
[receiver review](kaoseghis-emr-contract-review.md#kaosorders-receiver-review):

1. Agree a versioned strict normalized-source schema/endpoint: approved source facts
   and normalized meanings, completeness evidence, timestamp checks and size limits.
   Preserve v1 unchanged; neither the route nor version of the replacement is settled.
2. Authenticate the source to one authorized clinic scope; do not infer authorization
   from patient identifiers. Keep bearer tokens in a secret store, never URLs or logs.
3. Atomically reconcile one complete clinic day only after full validation. Omission
   must never delete/withdraw data from a failed or partial request.
4. Consume centrally interpreted reception/order facts without duplicating EMR table
   decoding. Apply board categories on the server, including approved LAB/finger-stick/
   urine rules and reviewed fee exclusions. Apply source edits/replacement using
   verified keys without collapsing encounters or retaining old details on key reuse.
   Keep unknown/unreviewed data from silently withdrawing prior state. Distinguish
   disappearance, explicit cancellation, clinical completion and payment; retain the
   normalized 30/40 distinction even when both states hide a tile.
5. Idempotently acknowledge batch ID plus a server-side content check. Reject reused IDs
   with different contents and stale/conflicting observations. Define authenticated restart
   epochs/revisions if clock ordering is insufficient; no durable revision scheme exists here.
6. Derive visible tiles only from ON_HOLD plus ACTIVE orders. Show Korean pills and all
   allowlisted details; never infer performed/completed state.
7. Serve a minimal viewer projection, not source IDs/reconciliation payloads, with
   authenticated access and no-store headers. Handle stale/offline state without emptying
   the board on failure. Enforce no PHI in logs/browser persistence.
8. Define retention, full restart reconciliation, rejected-batch handling, acknowledgements,
   retry/backoff bounds and cache clearing. Validate with synthetic integration tests first.

## Flags, Secrets and Deployment Gates

Implemented defaults:

```text
kaosorders_shadow_enabled=false
kaosorders_publish_enabled=false
```

Neither is enabled in the working database. No UI/startup hook exists. The offline
`read_shadow_day(settings, clinic_day, observed_at)` returns nothing when disabled.
With shadow `true`, it returns `unavailable`: the real reader remains blocked. Publishing
`true` is rejected when invoking shadow. No setting currently enables HTTP or source SQL.

Before a later supervised shadow deployment:

- Obtain explicit approval for limited production/schema verification. Prove keys, state
  codes, categories, timestamps, clinic-day membership and consistent complete-read semantics.
- Implement/review the parameterized day operation through the shared reader. Verify
  SELECT-only least-privilege credentials, finite limits and all cleanup paths.
- Review versioned mapping catalogs, row/byte bounds, completeness evidence, queue and
  cancellation recovery, plus the inventory of other Kaos-managed readers.
- Add a gated subscriber reusing existing triggers; verify startup, reconnect, busy
  coalescing, follow-up, safety, manual fallback and midnight without changing PACS.
- Use existing `eghis_db_connection_string` through its existing configuration/credential
  path only. Do not open a second connection or log/read out credentials. Shadow needs
  no KaosOrders endpoint or bearer token because publishing stays `false`.
- Review count/status output only, never persist real source rows or shadow payloads.
- Publishing is a separate stage: approved normalized-source contract, authenticated
  KaosClinic HTTPS endpoint, non-PHI source scope, secret-store token reference and
  bounded idempotent delivery.
  These endpoint/scope/secret settings do not yet exist in this implementation.

## September Plan Reconciliation: 2026-10-03

Remote commit `baa78dc` recorded the September 30 cross-system plan. It is merged
into the Windows work without reverting October source evidence or decisions.
Its implemented v1 description is now checked against the actual receiver revision
in the [contract review](kaoseghis-emr-contract-review.md). Its Acer/LMDE,
completed-tile and sender-classification designs are historical, not current
requirements. Neither older v2 route proposal is an approved endpoint.

The following safety and operational requirements remain applicable:

- Keep the source operation registered/reviewed and parameterized. Production
  privilege verification and bounded stuck-driver recovery remain separate gates;
  bound parameters alone do not turn the query helper into an operation-only API.
- Polling never injects F1, manipulates focus/caret or treats F6/F7 as save proof.
  Preserve the existing day-scoped trigger, follow-up, manual and safety behavior.
- Keep the service clinic-LAN-only and isolated from PACS/public proxy networks.
  Deployment, firewall, TLS and viewer-token provisioning require separate review;
  do not place a long-lived token in a URL, world-readable file or process argument.
- Define clinic-day logical expiry, physical purge/grace and stale thresholds.
  The earlier `04:00 Asia/Seoul` suggestion remains unapproved. Failed reads do
  not authorize current-day deletion. Keep the disposable projection out of
  general-purpose/cloud backups and persist no patient data on the viewer.
- Test independent source/receiver restart, full resynchronization, retries,
  missed delivery, midnight and viewer reconnect. Durable outbox/revisions are
  design candidates, not implemented capabilities of the in-memory ledger.
- Keep the kiosk unprivileged, transient and recoverable: review RAM-backed
  profile, cache/swap/crash controls, power settings, maintenance exit and
  token reprovisioning on the actual Pi hardware before routine use.
- Roll back by disabling the Orders publisher and uncertain viewer independently.
  Preserve EMR/PACS and manual polling; receiver rollback must never write EMR,
  delete PACS data or change production database settings.

## Verification

Synthetic fixtures and mocked connections cover queueing, close-before-processing,
six categories, identity, state changes, authoritative deletion, incomplete/unknown data,
retry identity, restart, day isolation, forbidden fields, redaction and disabled defaults.
Existing refresh tests cover coalescing, startup/reconnect, follow-up, retry and rollover.

The suite rejects unmocked PostgreSQL connections and non-test network access. Only
test-owned ephemeral loopback HTTP listeners are allowed. Native WebEngine navigation
is stubbed; test mutexes/databases are isolated. Foundation implementation/testing
used no production queries. The separately approved metadata-only inspection above
made no database changes. No v1/v2 publishing was enabled.

Verification on 2026-10-01 (isolated temporary data, mocked source/network/input):

- Focused shadow/coordinator/refresh tests: **144 passed**.
- Complete repository suite, including the supervised inspection helpers: **1,923 passed**.
- Existing coordinator, PACS readers/triggers, flu reader, and patient-context
  production modules are unchanged. The suite performed no live EMR validation.
