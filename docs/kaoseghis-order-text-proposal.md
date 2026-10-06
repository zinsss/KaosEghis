# Synthetic Order Text Proposal

Date: 2026-10-07. Sender starting point:
`bd46d44eeb2661d4d72971d2205242cdbc3df1d0`.

Status: **separate offline field-model proof only**. No EMR operation, wire
contract, serializer, source-state mapping, production reader, board change or
delivery is introduced. The operator asked to proceed after the bounded
[display-source evidence](kaoseghis-order-display-source.md).

## Receiver Compatibility Review

Read-only SSH review of `/srv/projects/KaosOrders` found a clean `main` at
`fd5e4b8b68e6efb06025b2696fd9b50553199ded`, with origin
`git@github.com:zinsss/KaosOrders.git`. Reviewed `current-day-memory-design.md`,
the v2 plan, implementation-plan excerpts, privacy policy, v2 fact models and
the pure current-day coordinator. No receiver files, services or data changed.

The receiver's v2 facts and synthetic coordinator still use a nonempty
`order_code` and have no original order-name fact. The proposed volatile session
wire remains unimplemented. Neither the receiver nor sender can carry the newly
verified blank-catalog/user-code case by merely adding a name to an existing v2
payload. Replacing `order_code` with `user_cd` would silently change its meaning.

This milestone therefore proves the new fields separately, without declaring a
v3 contract or changing the current-day coordinator, v1/v2 facts or fixtures.
Receiver agreement on names, bounds and a new fact/projection identity is still
required. Source evidence and real-data privacy approval are not supplied by a
successful synthetic test.

## Proposed Facts

`core/emr_order_text_shadow.py` contains `SyntheticOrderText` and one strict
synthetic construction function. The object contains exactly a four-part order
key and four text facts; all text fields must be explicitly present:

| Proposed field | Candidate source column | Synthetic type and bound |
| --- | --- | --- |
| `catalog_code` | `h2opd_doct_ord.ord_cd` | exact string, at most 128 Unicode code points, or null |
| `catalog_name` | `h2opd_doct_ord.medfee_nm` | exact string, at most 256 Unicode code points, or null |
| `user_code` | `h2opd_doct_ord.user_cd` | exact string, at most 128 Unicode code points, or null |
| `user_name` | `h2opd_doct_ord.user_nm` | exact string, at most 256 Unicode code points, or null |

These are proposed semantic aliases, not approved production column mappings.
In particular, `catalog_code` identifies the earlier `ord_cd` candidate, not
`medfee_cd` and not a promise that every value is an insurance/standard code.
The user pair matches the supplied screen pair in one approved singleton only.
Universal display precedence, provenance and content restrictions remain open.

The key reuses `OrderKey(encounter_id, order_date, order_number, order_sequence)`.
All four parts remain identity; neither code nor name becomes a key. No quantities,
units, category, billing decision or state is inferred from the text. This small
companion model is not a full order or snapshot and does not certify completeness.

## Preservation And Rejection

- Null, empty string, whitespace-only text, and padded text remain distinct.
  No trimming, case folding, Unicode normalization, substitution, translation,
  fallback or blank-to-null conversion occurs. Missing fields are rejected rather
  than defaulted. This representation decision is not a clinical interpretation.
- Unicode is preserved exactly, including Korean. Bounds are provisional
  synthetic limits, not observed maximum source lengths. Over-limit values are
  rejected without truncation; a future snapshot must fail as a whole rather
  than silently lose a row or a name. No source length/value query was performed.
- Control, format, surrogate, line-separator and paragraph-separator characters
  are rejected. This includes newlines, tabs, NUL, DEL, C1 controls and bidi format
  controls. No automatic cleanup or coercion makes them acceptable.
- Unexpected fields and non-string/non-null values are rejected. The top-level
  and nested-key objects are closed shapes. The four-part key is revalidated and
  detached from the caller. Direct construction and replacement also validate.
- All-null text facts still belong to an identified order. They do not mean a
  missing order, no-order encounter or verified-empty day. The component has no
  snapshot, state-normalization, filtering or reconciliation authority.
- A name-only/code-only edit changes the fact object without changing its key.
  Reused keys with changed text remain different content, not a deduplicated
  identical item. No clinical edit time is inferred.
- Construction requires literal `synthetic_fixture=True`; this is a test boundary,
  not authentication or a mechanism proving source provenance. Objects have
  redacted representations and errors have fixed reasons. The module performs
  no logging, I/O, persistence, database access, HTTP or runtime registration.

## Privacy Boundary

The proposed fields are for reviewed order-code/name sources only. They do not
authorize arbitrary clinical text, patient details, notes, diagnosis, insurance,
credentials or raw-row export. A string validator cannot establish that a column
never contains patient-entered information: safe source provenance/content review
remains required before live reading or delivery. Tests use invented data only.

Future rendering must treat the facts as plain text, never HTML, and must not
rewrite the source order's name into a category label. Display fallback when a
user field is missing is not implemented or approved. Preserve the separately
supplied catalog fields rather than combining them with `user_code or ord_cd`.
All scoped orders, including fees and unclassified/non-billing items, belong in
the patient-click complete detail list; summary categories must not prune it.

## Unchanged Boundaries

Existing v1/v2 facts, validators, serializers, canonical fixtures/hashes and
synthetic stores remain unchanged. Do not inject these four fields into those
contracts. The new component is not accepted by the existing serializer or
receiver and has no runtime importer, projection identifier or mapping revision.

The eventual Orders scope remains today's non-cancelled encounters, including
no-order encounters, and every child of included encounters, including cancelled
child orders. This proposal implements no encounter/child filter. PACS remains an
independent sibling consumer with unchanged queries and behavior.

`EghisSourceDayReader` remains UNAVAILABLE. No source query, live EMR interaction,
settings, triggers, publisher, token, HTTP endpoint, persistence, deployment or
restart occurred. No normalized-source payload may go to
`/api/v1/order-snapshots`. All current-day source-authority gates remain unresolved.

## Exact Next Receiver Handoff

Review this sender commit and the field model/tests against receiver
`fd5e4b8b68e6efb06025b2696fd9b50553199ded`:

1. Accept or revise the four separate field names, explicit null/empty/padded-text
   policy and provisional 128/256-code-point bounds. Do not conflate catalog and
   user fields or invent a default national-flu label.
2. Add only a separate pure synthetic receiver field-model proof and parity tests
   after that review. Preserve v1/v2 models, hashes, stores, session coordinator
   and runtime. Do not import sender code into receiver runtime.
3. Propose an explicitly new future current-day fact/projection identity for the
   narrower encounter scope and new order fields; do not silently reuse v2's
   `order_code` semantics, projection or durable epoch/revision fields. A complete
   new order model and its integration with volatile session facts need their own
   review; this companion object is not a complete session payload.
4. Keep wire parsing/encoding, canonical session fixtures, endpoints, tokens,
   transport, board UI, persistence and deployment disabled. Return the decision
   and exact receiver commit, not a production enablement claim.

Remaining source questions are broader field coverage/null/content bounds, source
state/qualifier combinations, complete current-day membership/save consistency,
verified-empty authority, all-category lifecycle, safe demographics and least
privilege. None is resolved by this model. No further patient action is needed to
repeat the already-verified singleton field-location check.

## Verification

Initial field-model proof: **183 synthetic tests passed in 1.21 s**. Coverage
includes all four retained fields, exact text/null distinctions, forbidden fields,
Unicode/control/overflow guards, explicit synthetic-only construction, full key
identity, same-key edits/reuse, redacted representations, no I/O/runtime importer
and the still-blocked reader.

The existing shared-model import guard initially flagged the new companion. Its
exact offline module name was added to that allowlist and the same no-I/O/board
dependency inspection now also checks the companion itself. Its own separate
test rejects any runtime importer. No v1/v2 validator was weakened.

The final related source/shadow/serializer/outbox/shared-reader, PACS, flu and
patient-context regression group passed **2,383 tests in 47.21 s**. Mocked DB
connections, isolated test mutexes, temporary application data, blocked external
network/native input and offscreen Qt were used. No live EMR operation occurred.

Full isolated suite: **4,259 passed, 26 failed in 187.24 s**. The same 26 failures
were recorded at starting commit `bd46d44`: 20 label-area assertions at 203 dpi,
three title-font assertions, one manufacturer-pill ink assertion and two
vaccine-shortcut width assertions. The full suite is not green. No unrelated UI
fix or relaxed vaccine assertion was included.

Git comparison with the starting commit confirms existing source models, v1/v2
serializers, outbox and all canonical JSON fixture bytes remain unchanged.
`git diff --check` passed. Receiver HEAD and clean working tree were rechecked
unchanged. Only the sender's new offline component, synthetic tests, the narrow
import-boundary guard and documentation are changed. No patient data is included.
