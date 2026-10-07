# Controlled Source Evidence Gate Review

Reviewed: 2026-10-05

Status: **source authority unresolved; production day reader remains UNAVAILABLE**.

The [current-day source semantics matrix](kaoseghis-orders-source-semantics-matrix.md)
records the Eghis boundary against KaosOrders read-gate commit `3771315` and
logical acceptance commit `182db514`. The independent pure synthetic model assigns
no production mapping revision and closes none of the gates below; existing v1/v2
fixtures and endpoints remain incompatible with the new fact identity.

The [2026-10-07 current-day full-order design](kaoseghis-current-day-orders-design.md)
records receiver agreement on synthetic order-text representation only. All eight
gates below remain unresolved, including normalization without the excluded
qualifier. An additional order-text coverage/content-safety gate remains open:
one screen-pair match does not approve all-category source mapping, NULL/blank
domains, maximum lengths or freedom from patient-entered clinical text. No source
operation, mapping or reader enablement follows from the new design identity.
The initial milestone changed documentation and mocked tests only. No new live EMR
operation was approved, requested or performed. No new query or probe was added.

Operator update: vendor information is not expected to be available. The
[controlled-observation path](#controlled-observation-path-without-vendor-docs)
below replaces vendor documentation as a prerequisite to further investigation.
It does not waive source gates or authorize a live read.

The [metadata-only operation](kaoseghis-source-structure-probe.md#approved-observation)
was subsequently approved and executed once at 23:09 KST on 2026-10-05. It found
4 dependent views for receptions and 3 for orders, with verified physical closure
in 0.101 s. The structural subquestion is observed, but no complete source gate is
resolved. The exact statement/harness remains under `tests/` only; no application
reader or query was added.

The subsequent [metadata follow-up](kaoseghis-source-metadata-followup.md#results)
ran two bounded operations under the operator's standing read-only authorization.
There are four unique dependent views (three shared by both sources), 23 other
ordinary-relation dependency links and five recorded routine dependency links.
The reader lacks selected write capabilities on the two source tables but has
CREATE capability in `public`, a concrete gate-8 least-privilege blocker. Both
physical connections closed, in 0.0717 s and 0.0750 s. No clinical rows or source
definitions were retrieved. All eight complete gates remain unresolved.
The final follow-up verification passed 1,124 focused and 1,619 broader tests;
the full isolated suite had 3,249 passes and the 26 previously documented vaccine
label/layout failures. See the [full verification record](kaoseghis-source-metadata-followup.md#verification).

## Current-Day Scope Correction

The [2026-10-06 operator decision](kaosorders.md#current-day-memory-only-decision-2026-10-06)
narrows the source to the current KST clinic day and makes KaosOrders a transient
in-memory board. The EMR DB is the sole durable patient/order source. At day change,
clear only the transient board and start the new day; never delete EMR records.
Historical backfill/archive coverage, past-day rescan and artificial date-moving
tests are not requirements. Normal same-day changes and complete current-day reads
still need verification. This narrows gates 1-3; it does not establish their proof.
The existing dummy is left unchanged pending a normal operator-confirmed action.
No new live operation or runtime change followed this clarification.

Later on 2026-10-06 the operator excluded cancelled encounters from the future
Orders projection while explicitly retaining no-order encounters. Current-day
membership now means all non-cancelled encounters, whether or not they have orders.
All children of included encounters remain covered, including cancelled child
orders. Verified cancellation removes a formerly included encounter from the next
complete projection; failed/partial reads cannot do so. Restoration must allow it
to reappear. This Orders-only scope does not alter shared source models, PACS,
existing v1/v2 fixtures or the synthetic receiver. Recognizing cancellation and
proving completeness/save consistency remain necessary; no evidence gate is closed.

The subsequent [current-day count proposal](kaoseghis-current-day-counts-proposal.md)
prepares one aggregate-only gate-1 checkpoint under tests: reception code/retained
flag counts split by any-child presence, including no-order visits. It does not
retrieve excluded qualifiers or identifiers, implement a cancellation filter, or
repeat a live dummy transition. Mocked tests cover cleanup, strict bounds and day
rollover. Its [later observation](kaoseghis-current-day-counts-proposal.md#observed-checkpoint-2026-10-06)
ran once at 19:17:36 KST: 267 candidate receptions, split into code-40/N total 263
and code-50/N total 4, matching the two visible operator-confirmed-today UI counts.
Of the 263 code-40 candidates, 118 had no linked child in the inspected table;
this does not prove absence of orders elsewhere. Verified physical closure took
0.0733 s. No full source gate closes and the runtime reader remains blocked.

The next [order-coverage check](kaoseghis-order-coverage-proposal.md#approved-observation-2026-10-06)
was prepared and mocked, then explicitly approved and run once at 20:52:15 KST.
It observed 267 receptions (145 with children, 122 without), 938 linked orders and
938 today-dated orders, with zero unmatched, off-day, null/blank-key or duplicate
four-part-key anomalies. Verified physical closure took 0.0731 s. Built-in PACS is
imaging/MWL-scoped and flu-report does not read orders; neither proves all-order
coverage. No-order receptions stay in the diagnostic. The bounded comparison is
complete, but it neither proves alternate storage absent nor resolves EMR-save
consistency or any complete source gate. The runtime reader remains UNAVAILABLE.

The subsequent [order-storage review](kaoseghis-order-storage-review.md) completed
three bounded catalog operations under continued read-only approval. It found 60
structural candidates, with 44 reviewed profiles and 16 masked names; only the
existing doctor-order object has SELECT. A separate aggregate inquiry confirmed
that none of the other 59 has even column-level SELECT. No candidate contents were
read or permissions bypassed. This limits alternate-table investigation; it does
not establish that another table is required. All connections closed
(0.1007/0.0639/0.1020 s). Full source gates and the reader block remain intact.

The operator then confirmed that today's national-influenza vaccination visits
have no EMR orders. This is positive workflow evidence for legitimate no-order
encounters, not a failure indication. Retain otherwise-in-scope encounters with
empty order lists; never infer a vaccine type or create a synthetic clinical order
from that absence. The total 122 is not individually reconciled or assigned wholly
to vaccination. Do not make broader grants/alternate-table discovery a prerequisite
solely on the basis of this count. Continue relevant source-scope, save-consistency
and normal lifecycle checks; investigate another source only if a concrete expected
order is missing. See the [corrected decision](kaoseghis-order-storage-review.md#operator-workflow-clarification).

## Pinned Scope

- Sender starting HEAD and GitHub `main`:
  `45c233b8e97f0bb0ca511c5ac47a289a0424c791`, clean Windows `main`.
- Receiver reference: `zinsss/KaosOrders` at
  `890a4dd4ce992f2598c85557513cd2c70b098a2b`.
- Receiver inspection used read-only `git show` over SSH against that exact commit
  in `/srv/projects/KaosOrders`. No receiver working files, service, API or database
  were changed or exercised.
- Reviewed sender source/v2 models, shared FIFO/mutex/connection boundary, existing
  controlled aggregate inspector, mocked-reader tests and historical evidence.
- Reviewed receiver v2 plan, architecture, implementation plan, recovery policy,
  v2 store schema/guards and receiver-only recovery tests. Receiver tests were
  inspected, not executed in this sender milestone.

The receiver reference records exact v2 fixture/hash parity, a strict separate
parser, in-memory reconciliation, and a synthetic-only SQLite store without the
excluded encounter qualifier column. Its tests cover receiver restart, lost-ack
retry, receiver-ahead, cross-day epoch fencing and exits around commit. This is
**not joint v2 recovery**: the sender has no v2 outbox or acknowledgement consumer.
The v1 synthetic outbox cannot be reclassified as a v2 implementation.

Receiver documentation contains historical wording that is now stale: the v2 plan's
opening status says persistence is absent, and the implementation plan's unresolved
list still includes fixture parity/separate persistence. Later sections and code
record their synthetic completion. The receiver handoff should reconcile that
wording without marking source or delivery authority complete.

## Evidence Inventory

These are earlier approved observations, not operations repeated in this review.
Detailed provenance and limitations remain in
[contract review](kaoseghis-emr-contract-review.md) and
[source-side history](kaosorders.md).

- 2026-10-02 was the operator-confirmed populated day: 173 candidate receptions,
  1,081 linked orders, 17 no-order receptions. The reviewed key/count cross-checks
  found no invalid/duplicate keys, cross-date children or unmatched same-date
  orders in that sample. They did not establish an authoritative history boundary.
- 2026-10-03 was explicitly confirmed closed by the operator. The reviewed candidate
  scope counted zero receptions and orders. This is an observed empty scope, not
  approval to emit a destructive FULL empty snapshot.
- Those two one-statement reads reported verified read-only mode, cursor closure
  and physical-connection closure before interpretation; elapsed connection work
  was 0.5806 s and 0.0523 s respectively. The schema preflight was 0.2077 s.
- A supervised disposable visit supported waiting/in-progress/hold observations
  for reception codes 10/20/25. Earlier supervised lifecycle checks supported
  distinct consultation-completed/unpaid (30), payment-completed (40), cancellation
  (50), and restoration to waiting. These are sampled UI/state associations, not
  a complete truth table for every retained qualifier combination.
- Earlier order checks observed same-key edits, disappearance on removal, key
  reuse on re-add, and cancellation of a parent with active children retained.
  They did not cover every order category or every cancellation/restoration path.
- The populated sample observed M/F sex values; it did not observe every possible
  null/blank/other value. Operator policy approved exact M/F and SQL NULL, with
  unknown/blank values rejected, and completed-years age at the encounter date.
  That policy does not prove a safe age source/calculation.
- Catalog checks showed SELECT access to candidate base tables. They did not prove
  least privilege. A dictionary permission denial was not bypassed.

No identifiers, raw values, exact excluded-field digits/lengths, clinical rows or
new patient data are included here. Prior excluded-field shape observations are
not copied into v2 data or used as a state rule.

## Eight Gates

All eight gates remain **unresolved**. A tested failure boundary is not source
evidence, and no gate is closed merely because a fixture can represent the result.

| Gate | Evidence already useful | Missing authority / candidate next investigation |
| --- | --- | --- |
| 1. Current-day membership | Candidate reception table/date predicate and no-order receptions observed. Catalog probes found 4 unique dependent views, 3 shared; 23 additional ordinary-relation links and 5 recorded routine links. No selected inheritance/FK links. | Coverage of today's non-cancelled Orders encounters, including no-order visits, with verified exclusion/restoration of cancelled encounters. Metadata alone does not establish that scope; historical backfill/archive coverage and artificial date moves are no longer required. |
| 2. Children and save consistency | Four-part key and linked/same-date counts checked in a sample; one statement uses one database statement snapshot. | Complete children for today's encounter scope and an EMR save transaction/completion boundary. One statement can still observe between two EMR commits. Independent autocommit reads are not one snapshot. |
| 3. Verified-empty authority | Operator-confirmed closed date and zero candidate counts. | Gates 1/2 plus verified current clinic/date, source access and completeness. A failed read is not empty authority. Midnight clearing is an explicit board lifecycle rule, not an empty-source assertion. |
| 4. States/retained qualifiers | Supervised codes 10/20/25/30/40/50 and some exact flag combinations. | Versioned state truth table including hold_yn Y/N, transient states, unknown/null/blank combinations and consultation versus payment completion. No default mapping from a column name or sample. |
| 5. State without excluded field | v2 excludes hold_opd; receiver has no raw-field business requirement. | Compare operator-confirmed states with only approved retained facts; seek ambiguous combinations rather than assume independence. If state remains ambiguous, keep it blocked; a privacy-safe semantic would need separate review. Never retrieve the excluded raw value to guess. |
| 6. All-category lifecycle | Sampled edits, deletion, restoration, parent cancellation and key reuse. | Definitions and a separately approved category/path matrix for dc_yn/act_yn, physical disappearance, restorations and identity reuse. Neither act_yn nor disappearance proves clinical completion/cancellation. |
| 7. Sex/age | Exact M/F/null and completed-years-at-clinic-date policy approved; sampled M/F only. | Controlled source-domain evidence, unknown/null/blank rejection and a reviewed privacy-safe derived-age source/function with synthetic birthday/leap-day tests. Vendor definitions are optional, not expected. No DOB or resident-number retrieval is authorized. |
| 8. Least privilege | Verified read-only sessions; selected table/column non-SELECT capabilities absent on the two sources; no observed superuser/admin/owner-role capabilities. | Effective CREATE capability in public was observed and remains a blocker. Admin review of a restricted reader identity/grants is needed; other schemas/functions and effective paths are not fully audited. Never test with a production write or change shared grants automatically. |

## Vendor/Admin Definition Request

Request documentation, not a patient export. An acceptable response identifies the
EMR/schema version, relevant source objects, definition revision and reviewer role
(vendor or DBA). Do not include account secrets, personal records, database dumps,
patient examples, actual excluded-field values or screenshots containing them.

1. Define which source objects and clinic-day predicate form today's authoritative
   encounter set. Include no-order visits, verified cancelled-encounter exclusion
   and restoration, KST rollover and clinic
   partitioning. Prior-day synchronization and artificial date moves are outside
   the clarified requirement.
2. Define the complete child relation and the uniqueness/reuse domain of encounter,
   order date, order number and sequence. Explain whether a save commits reception
   and all children atomically. If not, document an approved stable-read marker or
   completion protocol without providing actual marker values.
3. Define when today's complete set may authoritatively be empty, including source
   access, permissions and recovery/maintenance states. A calendar closure is only
   an operator expectation, not a source completeness guarantee.
4. Provide the normalized reception-state truth table from permitted source facts,
   including transient and retained-flag combinations. Explicitly answer whether
   hold_opd is required; do not provide its numeric domain, values or lengths.
5. Define cancellation/deletion/restoration/key reuse across order types, including
   fees and unknown/new catalog entries. Distinguish parent state from child state
   and source flags from administration, collection or examination completion.
6. Define sex codes and null/blank semantics. Propose a minimal derived age in
   completed years at encounter date, preferably an approved derived view/function,
   with entirely fictional birthday/leap-day examples. No source DOB values are
   requested, and no derivation or SQL is approved by this checklist.
7. Have the DBA attest effective read-only privileges for the intended dedicated
   reader role: table/view grants, inheritance/PUBLIC grants, ownership, superuser,
   RLS/bypass, role switching, schema creation and SECURITY DEFINER/callable functions.
   Record only approved metadata or fixed results, never credentials or role dumps.

These definitions remain useful if they become available, but they are not a
prerequisite to controlled investigation. Do not replace them with guessed
meanings, repeated broad queries, permission escalation, longer timeouts or
inference from an empty-looking UI. Finite observations alone do not prove today's
source completeness; historical membership is outside the clarified polling scope.

## Controlled Observation Path Without Vendor Docs

The operator reports that vendor information cannot be expected. Do not repeatedly
ask for the same unavailable documentation or silently convert that absence into
approval. Proceed with evidence-only work under the same per-operation approval,
privacy, serialization and physical-closure rules.

1. Prepare a **metadata-only structural probe** first, scoped to the already
   identified reception/order objects. Review key/constraint, relation kind and
   dependency/partition relationships without reading clinical rows or comments
   that could contain arbitrary text. This can identify missing structural evidence
   for gate 1; it cannot prove that an undocumented archive does not exist. Missing
   catalog permissions are reported, never bypassed. Exact catalog columns, SQL,
   caps and sanitized output must be mocked and presented before approval.
2. Build a gap matrix from the existing dummy observations. Do not repeat the
   already observed 10/20/25 and 25/30/50/restoration paths merely to accumulate
   more samples. Focus on missing retained-flag combinations and normal same-day
   category/lifecycle paths, not artificial date moves. Each live comparison gets its own
   approval; the operator performs any dummy-record changes, not the reader.
3. Compare only allowlisted aggregate facts with operator-confirmed UI states and
   counts at a known checkpoint. No patient/order identifiers or row dumps leave
   the database. If aggregate output cannot distinguish two explanations, report
   the ambiguity instead of exporting more detail or declaring the mapping proven.
4. A bounded save-observation experiment may reveal intermediate states, but a
   negative result does not prove atomic saves. Two equal observations, elapsed
   time, caret readiness or chart-clear events are not commit/completeness proof.
   Keep each independent statement's observation separate; never combine them as
   one snapshot or run unapproved background sampling.
5. Review effective privileges separately through allowlisted catalog results and
   operator/admin action where needed. No write test, privilege escalation or
   automatic role/grant change is permitted. Do not retrieve DOB to settle the
   remaining age question; any privacy-safe derived-age proposal needs its own
   review and synthetic boundary cases.
6. Record each result as an observed fact, an unverified hypothesis, or a limitation.
   Only explicit review can approve a tested source scope. If authoritative FULL
   coverage still cannot be established, the present v2 production reader stays
   blocked. A narrower observation-only/non-authoritative contract would require a
   separate sender/receiver design decision; it must not masquerade as FULL/complete
   or infer deletion from missing rows. No such alternative is implemented here.

The single gate-1 metadata probe was prepared under `tests/`, reviewed, approved
and run once; see its [sanitized result](kaoseghis-source-structure-probe.md#approved-observation).
No source gate is resolved and no production behavior is added. The following test result
belongs to the earlier documentation-only planning correction, not the new probe:
The documentation-only follow-up reran all 29 evidence-to-v2 boundary tests:
29 passed in 0.83 s. The full suite was not repeated for this planning correction;
its prior results and unrelated failures remain recorded below.

## Live Operation Approval Boundary

The exact [source-structure-v1 operation](kaoseghis-source-structure-probe.md) was
approved and executed once. The operator's clarification required read-only work;
this run did not extend beyond the reviewed operation. Each further investigation
still needs its exact bounded procedure, mocked failure tests and privacy review
before execution. Vendor documentation is helpful but not required to propose it.

Later the operator explicitly authorized continuing necessary read-only evidence
work until ready. The two [metadata follow-up operations](kaoseghis-source-metadata-followup.md)
were reviewed/tested and run under that authorization, without repeated prompts.
This replaces the per-operation prompt requirement for those bounded read-only
checks; it does not authorize arbitrary SQL, PHI retrieval, writes or production
enablement. The historical checklist below still defines each operation's review
requirements. Further sensitive-data scope or operator/admin writes require a new
specific decision, not an interpretation of this standing read-only authorization.

For each future operation, before approval:

1. Add and run mocked success/failure tests for that exact operation.
2. Present the complete parameterized statement/procedure, every selected source
   column and every join/filter dependency. Exclude raw hold_opd and prohibited PHI.
3. List the exact output allowlist: bounded aggregate counts, approved code/flag
   buckets, metadata, fixed reason codes and connection timing only. No identifiers,
   raw rows, source payloads, SQL/provider errors or credentials in reports/logs.
4. State result/source caps and cap-plus-one rejection. Use the existing FIFO and
   machine-wide Windows mutex. Current evidence defaults are 3 s connect, 2 s
   statement timeout and 257 result-row sentinel; changes require explicit review.
5. Verify read-only mode and finite timeout before source access. Verify cursor and
   physical connection closed before interpreting or emitting detached aggregates.
   An uncertain physical close stops further reads; no connection pooling.
6. Explain the one gate it addresses and what it cannot prove. Obtain explicit
   operator approval for that operation only, including date/expectation if needed.

If consistency cannot be justified with one reviewed statement or a separately
reviewed read-only snapshot transaction, stop. Even a consistent database snapshot
does not establish a complete clinical save without independently reviewed
save-boundary evidence. Failed, partial, inconsistent, overflowed, unverified and timed-out
results must never become authoritative empty snapshots.

## Mocked Boundary Verification

`tests/test_source_evidence_v2_boundary.py` adds 29 synthetic-only cases using the
existing mocked evidence reader, isolated FIFO and test-only mutex:

- successful candidate-empty/populated reports and ten failure/unverified paths
  cannot enter the v2 normalizer or serializer, and never change the blocked reader;
- verified physical cleanup plus any read status does not establish the missing
  whole-day/key/state/consistency assertions for an empty v2 day;
- sampled reception codes with either retained flag value do not install an
  implicit production mapping; and
- fixed rejections emit no diagnostic payload, logs or provider error text.

The existing evidence tests continue to verify finite timeouts, session validation,
post-closure interpretation, FIFO serialization, cap sentinels and uncertain-cleanup
stops. All connections are mocked. The suite blocks external networking, real DB
access, native desktop input and printing; it uses temporary test data and isolated
mutexes, not the production global mutex.

Verification on 2026-10-05:

- Focused source/v2 serializer/evidence/FIFO tests: **895 passed in 5.95 s**,
  including all 29 new boundary cases.
- Broader source-shadow, outbox, shared-reader, PACS, flu/weekly-report,
  patient-context, runtime-contention and vaccine-post-print selection:
  **1,390 passed in 48.30 s**.
- Full isolated `tests` suite: **3,019 passed, 27 failed in 148.45 s**.
  Twenty-six are the previously documented vaccine font/ink/shortcut-width
  failures reproduced at the untouched baseline. The additional intermittent
  `test_pending_handoff_defers_resets_and_blocks_mutation` failure also occurred
  in the earlier v2 milestone; its entire post-print group passed in this broader
  rerun. The full suite is not green, and that intermittent failure is not fixed
  or explained by this evidence review.
- Application code, existing tests and all v1/v2 fixture bytes remain unchanged
  from the starting commit. No unrelated UI fix or assertion relaxation was made.

These used the existing guarded isolated runner, offscreen Qt and disabled pytest
plugin autoload. No live connection timings or fresh source findings were obtained.

## Exact KaosOrders Handoff

Continue with a **design-only current-day memory-board revision**, not production
transport implementation. Pin the completed sender commit returned with this
review and inspect the receiver starting state; the last reviewed receiver was
`890a4dd4ce992f2598c85557513cd2c70b098a2b`.

1. Read the [current-day memory-only decision](kaosorders.md#current-day-memory-only-decision-2026-10-06).
   Update receiver architecture/implementation plans: no durable patient/order
   projection, no history replay, midnight transient reset and fresh current-day
   reload after restart. Do not delete or change any existing store in this step.
   Record historical synthetic store proofs separately from the new product target.
2. Preserve the reader block and v2 exclusion of hold_opd. Do not reinterpret v1
   stores/fixtures or introduce placeholder values. Do not repeat serializer work.
3. Design authenticated current-day scope/session fencing, complete-snapshot
   replacement, stale-response rejection, restart resynchronization, midnight races,
   bounded volatile retry/backoff and unavailable/stale display semantics. Do not
   silently repurpose v2 durable epoch/revision/receipt assumptions; decide contract
   compatibility explicitly. Implementation remains gated by source evidence.
4. A production patient/order outbox and durable receiver cursor/projection are no
   longer requirements. Keep existing synthetic stores/fixtures/hashes unchanged.
   Propose memory-only synthetic tests, including old-day/old-session rejection,
   no persistence, current-day edits/removals, restart and failure-not-empty behavior.
5. Add no endpoint, token, HTTP transport, retry worker, source reader/query,
   production storage, runtime wiring, board/PACS change, deployment or restart.
   Never send normalized-source payloads to `/api/v1/order-snapshots`.

Vendor information is not expected. Record the approved metadata findings without
promoting them to source authority. The bounded dependent-view/privilege follow-up
is now complete. Its four distinct views and effective schema CREATE capability
are observed facts, not source approval. No view rows/definitions or clinical rows
were read. A reviewed complete production day reader still cannot be implemented
from the current evidence.

## Next Practical Decision

Read-only structural automation has reached a boundary that more of the same
queries cannot remove. This is **not ready for production ingestion**. Do not
restart the serializer/parity work or repeatedly ask for unavailable vendor docs.

| Work needed | Who/what changes | Acceptance condition |
| --- | --- | --- |
| Restrict source identity | DBA/admin reviews effective schema CREATE grant and dedicated reader role; no automatic changes | Reviewed least-privilege effective access, beyond the two sampled tables; no production write tests |
| Unseen normal source transitions | Operator performs normal same-day actions on a disposable visit; agent reads approved aggregate checkpoints | Missing retained-flag and category/lifecycle evidence; no artificial date-moving, excluded qualifier or PHI output |
| Save and current-day authority | Reviewed application/database transaction boundary and explicit current-day scope acceptance | Do not treat repeated equal observations or UI readiness as atomic-save proof; failed reads never imply empty/removal |
| Safe age | Approve a privacy-safe derived source or separately review a minimal local derivation | Completed years at encounter date, null/invalid policy, boundary tests; no DOB/resident-number retrieval under the present mandate |

For the dummy matrix, already observed 10/20/25/30/40/50 transitions and INJ
edit/remove/reuse/parent-cancel/restore do not need repetition. Remaining examples
include whether retained hold_yn changes alter a code's state, LAB/imaging/other
category edits/cancellation/restoration, and normal same-day no-order reception
paths. Only test paths actually used by the clinic. Operator confirmation is
needed before each new condition. Do not move the dummy to old dates or demand
historical coverage. A bounded observation is not universal save-consistency proof.

If authoritative completeness is not obtainable, the decision is a separately
versioned **non-authoritative observation** design, not permission to ship
`FULL/complete=true` or infer deletion from absence. KaosOrders must explicitly
accept that different contract before any implementation. Current v2 and its
validators, fixtures/hashes, source block and transport restrictions stay intact.
