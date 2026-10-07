# KaosOrders Current-Day Source Semantics Matrix

Date: 2026-10-07. Status: **Eghis contract proposal; production source authority
remains blocked.**

This is the Eghis-owned response to the KaosOrders disabled
`CurrentDayRuntimeReadGate` milestone at
`37713151070abe835fc89a16b0c401bd06794931`. KaosOrders reported 582 passed and
2 skipped. Those receiver results were supplied in the handoff and were not rerun
or independently inspected in this repository.

The matrix separates committed Eghis facts and synthetic proofs, recorded product
decisions, and source or clinical meanings that still lack evidence. It introduces
no model, parser, serializer, fixture, SQL, HTTP route, authentication rule or
runtime hook. `EghisSourceDayReader` remains `UNAVAILABLE`, and no payload described
here may be sent to `/api/v1/order-snapshots`.

## Proposed Fact Identity

| Item | Eghis proposal | Status |
| --- | --- | --- |
| Contract ID | `kaosorders.current-day-orders` | Proposed for explicit Orders acceptance |
| Contract version | `1` | Proposed; independent of normalized-source v1/v2 |
| Projection ID | `kaosorders-current-day-orders-v1` | Proposed for explicit Orders acceptance |
| Mapping revision | No value assigned | Blocked on source-evidence-bound production mapping |
| Fact kind | One closed, complete current-day encounter/order fact set | Proposed; not a wire envelope |
| Replacement authority | Only a validated FULL current-day fact may replace same-day in-memory state | Product decision recorded in `docs/kaosorders.md`; source proof unresolved |
| Persistence | No patient/order persistence or historical replay | Recorded product decision |
| Transport | None approved | HTTP/auth/session/retry remain separate work |

This identity is intentionally new. Do not reuse `kaosorders.normalized-source`
version 1 or 2, `kaosorders-all-orders-v2`, `synthetic-v2`, or v2 epoch/revision
semantics. The new fact is not an optional text companion attached to a v2 order.

## Evidence And Semantics Matrix

| Topic | Verified repository fact or recorded decision | What remains unresolved | Consequence now |
| --- | --- | --- | --- |
| Current-day scope | The recorded decision is the current KST clinic day, with no historical replay. Startup and KST rollover require a fresh observation. | Authoritative source objects, clinic-day predicate, save boundary and final day recheck are not proven. | Identity may be proposed; no production FULL read. |
| Encounter membership | The recorded Orders decision includes every verified non-cancelled encounter, including waiting, in-progress, hold, consultation-completed, payment-completed and no-order encounters. | Complete production mapping of every reception code and retained qualifier combination is absent. `hold_opd` is excluded and must not be reacquired or inferred. | Unknown or ambiguous state fails the candidate set; it is never skipped or defaulted. |
| Cancelled parents | The recorded decision excludes a verified cancelled encounter and its children; a later verified restoration may re-add it. | Code/qualifier evidence is not a complete cancellation truth table. | No production filtering until mapping evidence exists. |
| Child coverage | The recorded decision keeps every child of each included encounter, including cancelled, fee, non-billing and unclassified rows. No-order encounters remain with an empty list. | Complete child relation, cross-date child handling, save consistency and absence of alternate storage are not proven. | No category/fee pruning and no authoritative omission/removal yet. |
| Order identity | Existing synthetic models/tests preserve encounter, order date, order number and sequence. Repository evidence observed a matching candidate unique key. | Lossless production numeric-to-text conversion, all-category reuse and cross-date membership remain unresolved. | Keep the four-part logical key proposal; do not claim a lifetime ID. |
| Four source text facts | Synthetic work distinguishes catalog code/name from user code/name. A bounded observation located one expected display code/name in `user_cd`/`user_nm`. | All-category null/blank/length/content provenance and safe-display coverage are not proven. | Preserve four nullable exact facts in the proposal; no fallback or production mapping. |
| Type and department | Existing source models preserve order type and department without category decisions; bounded aggregate evidence observed candidate fields. | Complete domains, null/blank policy and universal meaning are not proven. | Proposed nullable exact facts require Orders acceptance and source evidence. |
| Order state | Synthetic tests distinguish `ACTIVE` and `CANCELLED` and keep state separate from strict flags. | No approved direct source state column or all-category rule exists; `dc_yn` and `act_yn` meanings are incomplete. | Retain the two-value logical vocabulary only as a proposal; never infer it from one flag. |
| Retained flags | Existing validators accept only exact `Y`/`N` for `dc_yn` and `act_yn`; tests cover synthetic combinations without deriving state. | Production domains and meanings across all order categories are not proven. | Invalid or contradictory facts fail the whole candidate set. |
| Numeric facts | Normalized-source v2 has synthetic exact-decimal quantity/days/frequency coverage. | The new fact has no approved columns, meanings, units, null policy or bounds for them. | Omit them entirely from current-day-orders v1; do not add null placeholders. |
| Demographics | Existing normalized-source tests exercise synthetic chart/name/sex/age, and recorded decisions define M/F/null plus completed years at clinic date. | Safe production age derivation and unseen domains remain unresolved. The new complete-order boundary has not approved a demographic inventory. | Do not copy v2 demographics into the new fact by assumption; parent context needs joint acceptance. |
| Complete empty | Tests prove failed/partial/unavailable inputs cannot normalize as complete; diagnostic aggregates are always non-authoritative. | A zero-row production result is not a verified empty current day. | Startup/rollover is unavailable/empty UI state, not `FULL` source truth. |
| Comparison | Synthetic ledgers test same-key replacement, explicit cancellation, absence and reappearance as distinct observations. | Comparison is authoritative only after a complete same-scope read exists. | Absence may remove only after a future valid FULL replacement; it is not cancellation proof. |
| Read boundary | Shared FIFO/mutex, finite timeout, read-only checks and close-before-interpretation are implemented/tested for existing readers and probes. | A reviewed complete-current-day operation and least-privilege identity are absent; effective schema `CREATE` remains a blocker. | Production reader stays disabled. |
| Session/runtime | Orders reports a disabled memory-only `CurrentDayRuntimeReadGate`; existing v1/API/UI remain unchanged. | New parser/serializer, session fencing, authentication, freshness, retry and atomic replacement are not agreed. | No hookup from Eghis; existing v1/v2 coordinator and outbox remain untouched. |
| PACS/Reception | PACS consumes its sibling adapter and owns imaging lifecycle. Reception states here are Eghis source facts; KaosReception is a separate application. | No shared PACS or KaosReception contract is approved by this proposal. | Orders work must not alter PACS delivery or infer KaosReception semantics. |

## Proposed Closed Logical Inventory

This is the narrow contract proposal for review, not JSON and not an implemented
model:

- one explicit current KST clinic-day/source/projection/mapping scope;
- explicit parent encounter identity sufficient to group orders, with the final
  parent-context field inventory still requiring joint acceptance;
- every included parent, including a parent with zero children;
- for every child: the four-part key; nullable exact `catalog_code`,
  `catalog_name`, `user_code`, `user_name`, `order_type`, and
  `department_code`; exact logical `ACTIVE` or `CANCELLED`; and required exact
  `dc_yn`/`act_yn` flags;
- no quantity, days, frequency, category, fee decision, display fallback,
  clinical unit, event timestamp, PACS state or durable delivery cursor;
- closed shapes: missing is not null, unexpected fields reject, and duplicate,
  orphan, overflow or ambiguous meaning rejects the whole candidate fact;
- failed, partial, timed-out, unavailable, inconsistent or unverified input is not
  a fact and cannot clear prior same-day receiver state.

The detailed 128/256 text bounds and exact Unicode/null policies remain the
proposal in `docs/kaoseghis-current-day-orders-design.md`. They are not production
source evidence. Orders must accept or counterpropose them before either repository
implements the new pure synthetic model.

## Fixture Boundary

Existing fixtures prove older boundaries only:

- `tests/fixtures/kaosorders_synthetic_day.json` is a historical categorized,
  withdrawal-oriented proposal, not a complete source fact.
- `normalized_source_v1_*.json` and `normalized_source_v2_*.json` belong to
  `kaosorders.normalized-source` and use different projection, mapping and delivery
  semantics. V2 also includes demographics and numeric facts outside this proposal.
- Synthetic rows prove validation mechanics and edge-case vocabulary, not current-
  day source authority or production state mapping.

No existing fixture may be relabeled, edited in place or accepted by the new Orders
runtime gate. A future fixture needs the new identity and independently invented
synthetic data after contract acceptance.

## Exact Downstream Decision

No new clinical workflow choice is requested: the current-day/non-cancelled/all-
children/no-history scope is already recorded. The next decision is contractual:

> Orders must accept or counterpropose `kaosorders.current-day-orders` version 1,
> projection `kaosorders-current-day-orders-v1`, the closed inventory above, and
> the rule that mapping revision stays unassigned until source evidence closes.

After acceptance, Eghis may implement only a separate pure synthetic fact model and
collection validator/comparator. Parser, serializer, HTTP/auth/runtime hookup and
production source acquisition remain later, separately reviewed milestones.
