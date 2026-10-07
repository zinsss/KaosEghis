# Current-Day Complete Order Design

Date: 2026-10-07. **Design and documentation only.** No model code, parser,
serializer, canonical fixture, wire schema, source query or runtime connection is
implemented by this decision.

The later Orders-owned accepted contract at
`182db514b5404b69d4d10c2b30fbc2bb2ce3725d` supersedes this proposal wherever
the parent boundary was still open: its included waiting state is `WAITING`,
`patient_name` is bounded to 128 code points, and parent/child qualifiers are
closed nested objects. See
[the current implementation matrix](kaoseghis-orders-source-semantics-matrix.md).

Subsequent operator request: mirror the selected patient's EMR order-grid name,
daily quantity, frequency/count and days. The [offline query draft](kaoseghis-current-day-orders-query.md)
prepares candidate source columns for that request without changing this model or
its numeric-field deferral into a production mapping approval.

## Pinned Review

- Sender: clean `main` at `1cc3a984957539b2ca5919f98f5f8fad458c37ae`,
  origin `https://github.com/zinsss/KaosEghis.git`.
- Receiver workstation: clean `main` at
  `3813b52587ce5b2f7c0a81c17d7d9a60dd1ef3c3`, origin
  `git@github.com:zinsss/KaosOrders.git`.
- Receiver review: a separate temporary clone, checked out detached at that exact
  commit. No receiver worktree, service or production state was modified.
- Reviewed sender text component/tests, display-source evidence, contract review,
  evidence gates and Orders decisions. Reviewed receiver `order_text_shadow.py`,
  both order-text test files, order-text model, current-day memory design, v2 plan,
  implementation plan and privacy policy.

Receiver reports **315 focused compatibility tests and 709 full isolated tests
passed**. Those are receiver milestone results, not tests rerun by this review.
Its code/tests confirm acceptance of the four-field policy below. The receiver
uses its own immutable key class; the sender uses existing `OrderKey`. This is a
Python implementation difference, not a fact-policy difference or a wire format.

## Decisions And Identity

Accept the receiver's candidate namespace as the sender's **design identity**:

| Item | Decision |
| --- | --- |
| Fact contract | `kaosorders.current-day-orders` |
| Fact contract version | `1` |
| Projection ID | `kaosorders-current-day-orders-v1` |
| Production mapping revision | Unassigned and unapproved; requires a new source-evidence-bound value |
| Scope | Current KST non-cancelled encounters and all of their children |
| Completeness | Verified FULL replacement only; failure is not a snapshot |

These names identify a future fact boundary, not an implemented wire contract,
accepted endpoint or enrollment. Receiver ratification of this complete design is
still required. Do not invent a mapping default, use a placeholder as an approved
mapping, or reuse `synthetic-v2`. No synthetic mapping revision is allocated here.

The new order must be **one complete independent fact**, not an optional text
companion joined to `SourceOrderV2` and not a conversion that fills v2 `order_code`.
The logical field inventory below is design prose, not JSON, field encoding or a
new constructor. It preserves catalog and user facts side by side.

## Complete Order Inventory

Each field in the initial inventory must be explicitly present. Missing is not
null. Unexpected fields reject; they are not silently removed. Rows may not be
dropped, truncated or defaulted to make the whole set validate.

| Logical field | Proposed representation and NULL/blank policy | Decision status |
| --- | --- | --- |
| `key.encounter_id` | Nonempty, unpadded exact string, at most 128 Unicode code points; null/blank forbidden | Existing synthetic key policy retained |
| `key.order_date` | Exact date, not datetime; null/blank forbidden; encoding and source parsing not defined here | Existing synthetic key policy retained |
| `key.order_number` | Nonempty, unpadded exact string, at most 128 code points; no numeric coercion or zero default | Existing synthetic key policy retained |
| `key.order_sequence` | Nonempty, unpadded exact string, at most 128 code points; no numeric coercion or zero default | Existing synthetic key policy retained |
| `catalog_code` | Exact string up to 128 code points or null; empty, whitespace and padding preserved | Joint synthetic agreement at receiver `3813b52` |
| `catalog_name` | Exact string up to 256 code points or null; empty, whitespace and padding preserved | Joint synthetic agreement |
| `user_code` | Exact string up to 128 code points or null; empty, whitespace and padding preserved | Joint synthetic agreement |
| `user_name` | Exact string up to 256 code points or null; empty, whitespace and padding preserved | Joint synthetic agreement |
| `order_type` | Exact string up to 128 code points or null; empty, whitespace and padding preserved without classification | New sender design proposal; receiver review needed |
| `department_code` | Exact string up to 128 code points or null; empty, whitespace and padding preserved without classification | New sender design proposal; receiver review needed |
| `state` | Exactly `ACTIVE` or `CANCELLED`; no null, blank, UNKNOWN default or administration/completion state | Proposed normalized vocabulary retained from prior synthetic facts; production interpretation blocked |
| `qualifiers.dc_yn` | Exactly `Y` or `N`; required, non-null, nonblank, no case/space coercion | Strict retained-flag representation retained; no new meaning assigned |
| `qualifiers.act_yn` | Exactly `Y` or `N`; same strict rules | Strict retained-flag representation retained; not an action-completion flag by assumption |

The qualifier object contains exactly those two fields. Every text/key string
rejects Unicode categories `Cc`, `Cf`, `Cs`, `Zl` and `Zp`; Korean and other
permitted Unicode remain exact. The four catalog/user fields retain the accepted
synthetic policy without trim, case folding, normalization, translation, default,
fallback or blank-to-null conversion. Proposed type/department fields use the same
preservation policy, not the older v2 required-nonblank type policy. Unknown but
structurally valid type/department codes stay facts; lack of a category is not a
reason to remove a row. Source provenance/content approval remains mandatory.

Do not add a redundant `order_code`, computed `display_name`, guessed
`source_state_code`, category, visibility, fee decision, clinical unit or event
timestamp. No authoritative independent order-state-code column was established
for this new model. Retained flags and a separately reviewed normalization policy
must justify `state`; the model does not imply `dc_yn=Y -> CANCELLED`, or any rule
for `act_yn`. Unverified or contradictory production state/flag combinations fail
the candidate FULL read, not merely that row. Synthetic enum/flag combinations
are structural tests and do not approve a production truth table.

### Numeric Facts Deferred

| Field | Initial decision | Conditions for a later addition |
| --- | --- | --- |
| `quantity` | Not in the initial model; not even a null placeholder | Separately approve source column, meaning, null policy, sign/range/scale and content/provenance |
| `days` | Not in the initial model; not inferred from duration or another field | Same separate approval; no guessed days/unit interpretation |
| `frequency` | Not in the initial model; not inferred from quantity/days | Same separate approval; no guessed schedule interpretation |

No numeric source mapping is approved here. After separate review, exact finite
decimal facts may be considered; binary floats, numeric blank strings, coercion,
rounding and invented units must not be accepted. A true source NULL could be an
explicit null only under that field's approved policy, never a substitute for
failed extraction. Exact bounds and any canonical decimal wire encoding remain
undecided. Adding these fields requires an explicit contract/projection review,
not reuse of v2 numeric assumptions or silently widening the initial closed shape.

## Field Evidence Ledger

Representation agreement is distinct from column observation, complete coverage
and permission to publish. No production mapping in this table is approved.
Candidate order columns refer to `public.h2opd_doct_ord` unless stated otherwise.

| Field | Candidate provenance and existing evidence | Coverage / production decision |
| --- | --- | --- |
| Encounter key | `recept_no`, linked to candidate `h1opdin.recept_no`; unique parent index and sample linkage observed | Authoritative current-day parent scope and complete linkage unresolved; not approved |
| Order date key | `ord_ymd`; part of observed four-column unique key | Date parsing, all-category linkage and current-day membership unresolved; not approved |
| Order number key | `ord_no`; non-null numeric key column observed | Lossless source-numeric-to-text convention and all-category reuse unresolved; not approved |
| Order sequence key | `ord_seq_no`; non-null numeric key column observed | Same convention/coverage limits; not approved |
| `catalog_code` | `ord_cd`; earlier singleton found empty text | One observation, not universal standard/insurance-code semantics; not approved |
| `catalog_name` | `medfee_nm`; earlier singleton found SQL NULL | One observation, not universal display authority or safe-content proof; not approved |
| `user_code` | `user_cd`; exact operator-supplied screen-code comparison matched in one approved singleton | Location supported for that case only; all-category/null/length/content coverage unresolved; not approved |
| `user_name` | `user_nm`; exact screen-name comparison matched in that singleton | Same limitation; no arbitrary text retrieval or fallback authorized; not approved |
| `order_type` | `ord_type`; prior metadata and allowlisted aggregate buckets observed | No complete domain, nullable/padded policy evidence or all-category semantics; not approved |
| `department_code` | `proc_dept_cd`; prior metadata and aggregate buckets observed | No complete domain or universal department/category interpretation; not approved |
| `state` | No approved direct column; candidate interpretation would need reviewed retained facts and source workflow evidence | Complete ACTIVE/CANCELLED mapping across all categories unresolved; not approved |
| `qualifiers.dc_yn` | `dc_yn`; prior strict-flag samples and limited lifecycle observations | No all-category cancellation rule; not approved |
| `qualifiers.act_yn` | `act_yn`; prior strict-flag samples | No administration, collection, examination or completion meaning proven; not approved |
| `quantity` | No source column selected by this decision | Excluded; production and representation addition unapproved |
| `days` | No source column selected by this decision | Excluded; production and representation addition unapproved |
| `frequency` | No source column selected by this decision | Excluded; production and representation addition unapproved |

The joint four-field agreement sets synthetic 128/256 limits, not measured source
maxima. A length/Unicode check cannot establish that names never contain patient
details or free clinical text. Content/provenance review must cover every retained
category, including cancelled, fee and unclassified rows. Never query or log extra
patient data to compensate for missing evidence. Only the existing sanitized
[display-source observation](kaoseghis-order-display-source.md) is referenced;
there are no new source operations or values in this milestone.

The closed inventory excludes resident numbers, DOB, phone, address, diagnosis,
notes, insurance, credentials, raw rows/payloads and PACS/DICOM/MWL/Orthanc facts.
It is not permission to place any of them inside a name field. Future validation
errors and representations must be fixed/redacted; neither values, identifiers
nor content digests belong in logs. Safe rendering is plain text, never HTML.

## Current-Day Set And Consistency

- Scope is the current clinic date in `Asia/Seoul`, for one explicitly bound
  clinic/source/projection/mapping. There is no historical backfill or date-moving
  source test. Day ownership must be rechecked before a result is accepted.
- Include every verified non-cancelled encounter: waiting, in progress, hold,
  consultation-completed and payment-completed. No-order encounters remain with
  an empty child set. Empty children never synthesize a vaccination or other order.
- Exclude verified cancelled encounters and their children only in the future
  Orders projection. Unknown/ambiguous reception state is a failed candidate read,
  not a reason to assume cancellation or skip that encounter. `hold_opd` stays
  excluded in every form; if a state requires it, production remains blocked.
- Keep every child of each included encounter: active and cancelled child orders,
  fees, non-billing items and unclassified rows. Billing, insurance, payment
  eligibility and receiver summary categories do not prune the complete list.
- Encounter membership determines the scope; the child date is part of identity,
  not an independently sufficient filter. Do not silently drop or relabel a child
  with a different date. Its admissibility/linkage needs source evidence; until
  settled, fail a contradictory candidate set rather than claim completeness.
  This does not authorize querying a previous day's encounters.
- Parent cancellation removes that encounter and its children only through a
  later verified complete replacement; verified restoration permits reappearance.
  Shared source facts, historical v1/v2 completeness and PACS remain unchanged.
- Failed, partial, timed-out, unavailable, inconsistent, overflowed or unverified
  reads provide no replacement. Preserve the last valid same-day state. Zero
  candidate rows do not establish a verified-empty day without source authority.

Proposed future set validation rejects duplicate encounter/full-order keys,
orphan children, identity ambiguity, malformed facts and overflow as one failure.
Retain the existing synthetic ceilings of 10,000 encounters and 100,000 orders as
provisional maximums, without claiming production capacity. Never silently cap,
page independently or publish partial results as FULL. Canonical ordering for a
future comparison is encounter ID, then the complete four-part order key; wire
ordering/bytes/hashes are not defined here.

One SQL statement snapshot would not by itself prove an EMR save complete across
multiple commits. Repeated equal reads, elapsed delays, chart events and UI
readiness do not replace save-boundary evidence. Any future approved source read
must retain FIFO serialization, the machine-wide mutex, verified read-only mode,
finite timeouts and verified cursor/physical connection closure **before**
interpretation, normalization, comparison, output or delivery. No such read or
source normalization is enabled here.

## Comparison Meaning

Compare only complete, validated sets in the same day, source, projection and
mapping scope. Equality covers every retained fact, not just order code. The
four-part key identifies a current source row, not an immutable lifetime order.

| Observation between valid full sets | Permitted interpretation |
| --- | --- |
| Same key, identical facts | Same observed content |
| Same key, any text/type/department/state/qualifier change | Replace the full fact; observed content changed, not proof of edit versus key reuse |
| Present key with explicit normalized CANCELLED state | Retained cancelled child fact under an included parent; not physical deletion |
| Previously present key absent | Remove from current projection; absence from scope, not proof of cancellation, deletion, payment or administration |
| Previously absent key returns | Add current facts; possible restoration/reuse, not proof of the original clinical instance |
| Cancelled parent omitted, later included again | Scope removal/reappearance after verified full reads; no durable restoration history |
| Invalid read or mismatched day/scope | No same-day replacement and no disappearance inference |

Missed observations can hide a delete/recreate cycle, even when text is identical.
The design promises faithful current content, not edit auditing or definitive
reuse detection. No inferred clinical event timestamp, lifetime ID or durable
tombstone/history is introduced. `observed_at` belongs to the source observation,
not order edit, cancellation, administration, collection, examination or payment.
It neither orders session delivery nor makes unchanged content an edit.

## Volatile Session Relationship

The fact contract defines what a complete current-day observation means. A future
separate delivery/session protocol decides who may send it, which volatile
generation/session is current and which delivery supersedes another. This design
does not specify an envelope, authentication, acknowledgements, digest encoding,
HTTP status, retry/backoff or transport. None is implemented.

Keep the receiver's existing v2-based `CurrentDaySessionCoordinator` unchanged as
a historical synthetic lifecycle proof. It must not accept the new order or have
its allowed projection changed in place. Later integration needs an explicitly
reviewed new fact/context boundary and fresh synthetic parity tests.

Receiver restart and KST midnight discard prior patient/order and delivery state,
rotate volatile generation and require a fresh full current-day observation.
Startup/rollover is empty and unavailable, not a verified-empty source assertion.
A sender restart likewise needs a new session and fresh read, not cursor adoption.
Old-day/session/generation work cannot repopulate the board; date/generation must
be rechecked immediately before atomic replacement. Midnight discards old-day
state even when today's source is unavailable; same-day source failure preserves
the last valid same-day facts subject to a still-separate freshness policy.

There is no durable patient/order outbox, receiver projection, replay history or
epoch/revision allocation. V2 `source_epoch` and `revision` keep their old meanings
and are not carried over as session sequencing. The future session-local sequence
and exact in-memory retry rules require separate agreement. Configuration/auth
material is distinct from forbidden patient/order persistence.

Receiver-owned categorization and eventual plain-text rendering must not rewrite
original code/name facts or suppress complete detail rows. No UI, category policy
or name-fallback decision is made here. Logs, caches, browser stores, crash dumps,
swap and hibernation remain separate accidental-persistence deployment gates.

## Remaining Policy And Evidence

There is **no policy difference** in the joint four-field synthetic agreement.
The sender accepts the receiver's proposed new contract/projection names for this
design. Receiver approval is still needed for the complete inventory, nullable
type/department preservation, omission of numeric fields from the initial model,
set/comparison rules and new identity as a combined design. This is not claimed
full-model parity. Production mapping revision and source mappings remain absent.

All [existing eight source gates](kaoseghis-source-evidence-gates.md#eight-gates)
remain unresolved: current-day membership, child/save consistency, verified-empty
authority, full state/qualifier mapping, state independence from the excluded
field, all-category lifecycle, safe demographics and least privilege. The
additional order-text coverage/content-safety gate also remains unresolved.
The four-field synthetic approval closes none of these gates.

## Exact Next Receiver Handoff

Review the completed sender documentation commit against receiver
`3813b52587ce5b2f7c0a81c17d7d9a60dd1ef3c3`. Preserve both repositories' work;
no pull/reset, deployment or service restart.

1. Ratify or explicitly counterpropose the full inventory/NULL policies and the
   `kaosorders.current-day-orders` version 1 /
   `kaosorders-current-day-orders-v1` design identity. Leave mapping revision
   unassigned. Record differences before implementation, never weaken v2.
2. After accepting that design, the next bounded implementation is a **separate
   pure synthetic complete order model** plus in-memory collection validation and
   comparison tests using explicit synthetic parent/day context. Combine key,
   all four text facts, proposed type/department, state and strict flags in one
   model, not a text object attached to v2. Do not add numeric fields yet.
3. Test exact field policies, same-key content edits, four-part identity/reuse,
   cancellation versus absence/reappearance, all retained children, duplicate/
   orphan/overflow rejection and preservation after invalid inputs. Synthetic
   non-cancelled parent context must retain no-order parents and permit parent
   cancellation/removal/restoration; it is not a source-state mapping or actual
   encounter/demographic reader. Include fixed errors, redacted representations,
   immutable/detached inputs and no I/O/runtime dependency checks.
4. Keep existing text companions, v1/v2 validators/fixtures/hashes/stores and the
   current session coordinator unchanged. Do not add a wire parser, serializer,
   canonical fixture, production SQL/read, HTTP/endpoint/token, transport/retry
   worker, persistence, runtime setting/trigger, board/PACS change or deployment.
   Never send these facts to `/api/v1/order-snapshots`.
5. Run focused and full isolated receiver tests with synthetic data and blocked
   external network. Commit/push only the completed scoped receiver milestone.
   Return its exact commit, accepted/counterproposed policies, test results and
   a sender handoff for a separate complete-model synthetic parity milestone.
   Keep every source gate and session-wire/transport decision unresolved.

This handoff describes the **next** separately authorized implementation. The
present sender milestone remains documentation-only; it implements none of it.

## Verification

No code, test, SQL or fixture is modified by this design. Existing focused
order-text/source regressions and the isolated sender suite are rerun below;
receiver 315/709 results above are reported provenance, not new executions.

The existing order-text/source/shadow/serializer/outbox/shared-reader, PACS, flu
and patient-context group passed **2,383 tests in 49.95 s**. It used mocked DBs,
isolated test mutexes, temporary application data, offscreen Qt and blocked
external networking/native input. No new test or assertion change was needed.

The full isolated suite completed with **4,258 passed / 27 failed in 167.73 s**.
Twenty-six are the already documented UI failures: 24 label font/layout/ink
assertions and two shortcut-row width assertions. One additional failure was
`test_successful_fetch_starts_new_record_without_changing_previous` in
`test_vaccine_fetch_record.py`: a Qt `QStandardItem` lacked `triggered` during
widget construction. Repeating that entire file in a fresh isolated process
passed **22 tests in 5.04 s**. The additional full-suite failure did not reproduce
alone; this is not a claim that the full suite is green or that its cause was fixed.

The changed paths are documentation only. Source, tests, v1/v2 validators,
serializers, fixtures and hashes are unchanged from sender `1cc3a98`; no assertion
was relaxed and no UI fix was attempted. Focused regressions found no new failure;
the full run has the additional non-reproducing Qt failure noted above. Markdown
file-link checks and `git diff --check` passed. There were no EMR/source operations,
receiver API calls, production data exports, runtime changes or service restarts.
