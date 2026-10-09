# KaosOrders Non-PHI Source Evidence Run Package

- **Status:** disabled composition/adapter review candidate; execution remains
  blocked before authentication pending independent composition PASS,
  non-secret identity/path and window records, immutable approval binding, and
  fresh single-attempt authorization
- **Last updated:** 2026-10-09
- **Owner:** KaosEghis
- **Affected projects:** KaosEghis, KaosOrders, orchestration, integration review
- **Central baseline:** orchestration `4603c61b85488da9da21c6720f080f3df673ea9e`
- **Orders readiness:** `239b9b948bbb6e8c54288d2196287fb70a38aba0`
- **Package ID:** `eghis-kaosorders-non-phi-evidence-run-v1`
- **Package revision:** `review-candidate-3`

## Context and plan delta

Orchestration authorized the bounded non-PHI evidence protocol at immutable commit
`e341737`. This package is the Eghis-owned, documentation-only first run package
required before any source operation. It does not authorize or perform execution.

Canonical protocol `4603c61b85488da9da21c6720f080f3df673ea9e`
records independent acceptance of executor/backend commit `1eaf325` but stops
the execution gate. The owner separately authorized only the bounded disabled
composition prerequisite described below. That approval does not authenticate,
connect, execute a statement, activate runtime, or authorize an evidence attempt.

Independent review of `fa3e9cef41c495190e08b96f9c91f7f2401407b0`
confirmed the prior ownership and cleanup fixes but found that direct synchronous
`cursor.execute()` and `fetchmany()` could outlive the common deadline. At
2026-10-09 22:19 KST the owner authorized exactly one exception remediation for
those two calls and their synthetic slow/hanging probes. The exception is
implementation/testing-only and does not authorize authentication, source
connection, statement execution against a database, or an evidence attempt.

Independent review of `3bee2c454a4c122e49b6c1afd3eb21f07f20fd26`
then found a narrower helper race: `Event.wait()` could report success for a
completion occurring just after its timeout, while the helper did not re-read
the monotonic clock. At 2026-10-09 22:30 KST the owner authorized one additional
correction limited to completion-time proof and deterministic boundary tests.
This does not widen any source, schema, runtime, or evidence-attempt authority.

The original evidence plan contemplated one broad evidence package. Exact
demographic fields, authoritative joins, production types, and index identities
are still unproven, so this revision deliberately closes only a metadata-first
run. It may establish only the 15 scoped privilege booleans and allowlisted
catalog facts. It cannot establish full least privilege, ratify a mapping, or
dynamically expand into row, domain, aggregate, plan, or demographic queries. A
later inventory requires a new immutable digest, documentation revision, Orders
review, and independent PASS.

## Settled leap-day rule

Completed age is evaluated at the `Asia/Seoul` clinic-day boundary. A person born
on 29 February has a 28 February anniversary in a non-leap year and a 29 February
anniversary in a leap year. Age increments at 00:00 `Asia/Seoul` on that
anniversary. This settles product policy only; it does not approve a birth-date
source field, source expression, or source access.

Synthetic rule vectors for a 2000-02-29 origin are closed as follows:

| KST instant | Expected completed years |
| --- | ---: |
| 2024-02-28 23:59:59 | 23 |
| 2024-02-29 00:00:00 | 24 |
| 2025-02-27 23:59:59 | 24 |
| 2025-02-28 00:00:00 | 25 |

These invented dates are contract vectors, not patient examples.

## Closed statement inventory

The exact statement bytes are frozen in
[Eghis → KaosOrders Non-PHI Evidence Statements v1](evidence/eghis-kaosorders-non-phi-statements-v1.md).
No implicit driver probe, session discovery, retry, count, `EXPLAIN`, wildcard,
row sample, or follow-up statement is allowed.

| ID | Purpose | Maximum rows | Criteria result |
| --- | --- | ---: | --- |
| `EKO-C00` | Start one read-only repeatable-read transaction. | 0 | Control must complete before evidence; any notice, result row, or failure stops the run. |
| `EKO-C01` | Set the local statement timeout to 1.5 seconds. | 0 | Exact control must succeed before evidence. |
| `EKO-C02` | Set the local lock timeout to 100 milliseconds. | 0 | Exact control must succeed before evidence. |
| `EKO-C03` | Set the local idle-in-transaction timeout to 5 seconds. | 0 | Exact control must succeed before evidence. |
| `EKO-P00` | Prove transaction read-only mode and exactly the 14 additional allowlisted privilege facts named by the statement. | 1 | The 15 scoped facts are `proven` only if one row has every closed boolean true. This does not establish full least privilege; any false, null, missing, extra, or non-boolean value stops before `EKO-V01`. |
| `EKO-V01` | Record only PostgreSQL `server_version_num` as the source database version class. | 1 | Exactly one six-ASCII-digit string in the frozen inclusive range `120000..179999` is accepted. Any other type, width, alphabet, or value stops before `EKO-M10` with `version_mismatch`. |
| `EKO-M10` | Return type/nullability/generated/identity metadata for exactly 19 named candidate columns. | 19 | Each named field is `proven` only for its observed metadata fact; absence or any schema mismatch is `unproven` and stops the run. No clinical meaning is inferred. |
| `EKO-K20` | Return matching-index metadata for exactly three predefined candidate key shapes, excluding partial and expression indexes. | 3 | Observed match facts may be `proven`; authoritative key choice and expected runtime plan remain `unproven` until a later reviewed inventory. |
| `EKO-C99` | Roll back the read-only transaction on every success, failure, timeout, or cancellation path. | 0 | Cleanup cannot be `closed` until rollback, cursor closure, physical connection closure, and lease release are all confirmed. |

The immutable SHA-256 values below were generated from the exact statement
boundaries in the companion document. Independent review must reproduce all nine
before execution can be considered:

| ID | SHA-256 |
| --- | --- |
| `EKO-C00` | `8e8fe700469cae8bd58eb7c36c0e9f7af5eb7c31abd2fd4aa1ac2bbc294a1605` |
| `EKO-C01` | `5b4365b0e536dcaf636f0d4a87d9ce36f786fe570c4320172a9a6a352b34fd2e` |
| `EKO-C02` | `45ab9545d6195a0772ec432ff05d89e6d6f6e5e8efcbac9e5f486a9697960a1f` |
| `EKO-C03` | `98abef6980f6444c65a59fe0c434990d73d43af8c8cbf7bb603b831d06b1c306` |
| `EKO-P00` | `6b32e06db86fd62b7df3c6edb860b6f0e1482ec2f3e98b3304811688d0dcd3d6` |
| `EKO-V01` | `3155dd719026df1163a083a69503aef73ffa7279cd0d0b5dde4c4178b0b99b57` |
| `EKO-M10` | `16f87d77183f5f2173d63513e6e527bbc9b6be865d86fd89e89a8970e1abf543` |
| `EKO-K20` | `2e8e2160000f566de2b8c4ccda1f9e90b3992d9b66842e07616c6d5ab9a11462` |
| `EKO-C99` | `0b45ae2ca7baf6547c3d61d85a8f616b64a5efca3637b4bf88008e64d8be29aa` |

## Closed output envelope and schemas

The pure candidate emits at most one canonical ASCII JSON object. The root is a
closed object with exactly these fields and values/types (canonical key ordering
is lexical):

| Field | Exact value or type |
| --- | --- |
| `contract_id` | literal `kaoseghis.non-phi-source-evidence` |
| `contract_version` | integer `1`; booleans rejected |
| `package_id` | literal `eghis-kaosorders-non-phi-evidence-run-v1` |
| `package_revision` | literal `review-candidate-3` |
| `central_commit` | full literal `e3417375984acc2a58392315e26035e14c253219` |
| `run_status` | exactly `complete` or `blocked` |
| `fixed_reason` | exactly `none`, `preflight_failed`, `inventory_mismatch`, `unexpected_shape`, `privacy_boundary`, `row_limit`, `byte_limit`, `timeout`, `cancel_failed`, `cleanup_uncertain`, `version_mismatch`, or `capture_failed`; `none` is valid only with `complete` |
| `evidence_date` | ISO `YYYY-MM-DD` date supplied by the reviewed run boundary |
| `environment_class` | literal `production-read-only` |
| `provenance` | closed object defined below |
| `results` | closed object defined below |
| `criteria` | exactly 91 closed criterion objects in the inventory order below |

Unexpected/missing fields, coercion, NaN/infinity, non-ASCII metadata, or an
artifact over 65,536 bytes reject the artifact. It contains no source ID,
mapping revision, host/database/user identity, credential, connection string,
SQL, exception text, timestamp, PID, patient-derived value, or driver echo.

`results` has exactly `p00`, `v01`, `m10`, and `k20`:

- `p00` is either null or one object with exactly the 15 statement booleans. It
  is non-null only for `complete` and every value is literal JSON true.
- `v01` is always an object with exactly `source_version_class`. Its value is a
  six-ASCII-digit string in `120000..179999`, or null when no accepted version
  was observed. A clean blocked envelope may retain an already validated version.
- `m10` is null or exactly 19 objects in the frozen `(relation_id,column_id)`
  order. Each has exactly `relation_id`, `column_id`, `column_present`,
  `data_type`, `nullable`, `generated`, `identity`. Every required candidate must
  have `column_present=true`; false with the four metadata fields null is a valid
  catalog shape but an `inventory_mismatch` that blocks before K20, publishes no
  complete artifact, and leaves `metadata.closed_candidate_columns` unproven.
  When true, `data_type` is 1..128 printable ASCII bytes and the other three
  fields are booleans.
- `k20` is null or exactly three objects in the frozen `(relation_id,key_id)`
  order. Each has **exactly eight fields**: `relation_id`, `key_id`,
  `matching_index_count`, `any_unique`, `any_primary`, `all_valid`, `all_ready`,
  `single_index_method`. The count is a non-boolean integer `0..64`; zero requires
  all four flags false and the method null. A positive count permits a null method
  or 1..128 printable ASCII bytes. This exactly matches the eight-column SELECT.

For `complete`, all four results are populated. For `blocked`, `p00`, `m10`, and
`k20` are null; `v01.source_version_class` follows the rule above. Timeout,
cancellation failure, cleanup uncertainty, or publication failure creates no
artifact at all. Clean fixed validation failures may atomically publish only the
closed blocked envelope.

Each `criteria` item is a closed object with exactly `criterion_id`, `status`,
`source_statement_id`, and `fixed_reason`. `status` is exactly `proven`,
`unproven`, or `not_applicable`. `source_statement_id` is null or one of
`EKO-P00`, `EKO-V01`, `EKO-M10`, `EKO-K20`; metadata-only logical limits never
receive a source statement. `fixed_reason` is null only for a proven complete-run
fact; otherwise it is a fixed reason, `metadata_only`,
`owner_decision_not_source_evidence`, or `synthetic_harness_only`.

The closed `provenance` object contains exactly:

- repository-relative `artifact_path` literal
  `evidence/eghis-kaosorders-non-phi-evidence-v1.json`;
- lowercase 64-hex `safe_content_sha256`, computed over canonical
  `{"criteria":<criteria>,"results":<results>}` from the same in-memory objects;
- `reviewer_role=independent-integration-review` and
  `authority_role=clinical-product-owner` (roles, never personal identities);
- `applicable_source_database_version`, equal to the accepted V01 value or null;
- `accepted_version_range=120000-179999`;
- `expires_on`, exactly 30 calendar days after `evidence_date`; and
- ordered `revalidation_triggers`: source/database version change; schema,
  relation, column, key, or index change; privilege or identity change; statement
  or digest change; package or protocol change; environment-class change;
  contradictory or unverifiable evidence; review expiry.

## Aggregation and suppression policy

This metadata-first package performs **no clinical aggregation** and persists no
source counts. All completeness, state, flag, cancellation, no-order, orphan,
duplicate, join-cardinality, verified-empty, demographic, category, and latency
criteria remain `unproven`.

Any later aggregate inventory must use server-side suppression. Exact clinical
counts are forbidden. Zero may be recorded only as `PROVEN_ZERO`; counts 1..9 and
any unsafe cohort become the undifferentiated value `UNPROVEN`, without the count,
code, or reason; counts of at least 10 may be recorded only as `AT_LEAST_10` when
the reviewer confirms that the category itself is non-sensitive. Unknown raw
codes, free text, names, demographics, keys, dates, and values may never leave the
database boundary. These rules are acceptance constraints, not authorization for
a later statement.

## Bounds, transaction, and timeout rules

- one physical connection, one read-only `REPEATABLE READ` transaction, and no
  connection pool;
- one monotonic 10-second fence starts immediately before FIFO/serialized-lease
  admission and includes queue wait, lease acquisition, connection, every control
  and metadata read, cancellation, rollback, cursor closure, physical connection
  closure, and lease release;
- 1.5-second statement timeout and 100-millisecond lock timeout per statement;
- no retry, no savepoint retry, no second connection, and no coalesced follow-up;
- maximum 24 result rows and 64 KiB canonical output for the full run;
- maximum 128 bytes for any scalar text and maximum matching-index count 64;
- cursor closure immediately after each fetch, transaction rollback after the last
  read, physical connection closure and lease release before artifact construction
  or publication, and detached row clearing after canonical output; and
- package/environment mismatch, queue delay leaving less than 5 seconds, or
  inability to guarantee cleanup before the global deadline stops before the
  first statement; V01 version mismatch stops before M10.

## Fixed criterion inventory and crosswalk

The envelope contains these exact 91 IDs, once each and in the order shown. Only
the first 20 can become `proven` in a complete metadata run. The 56 logical and
capacity IDs remain `unproven/metadata_only`; the owner policy is
`not_applicable/owner_decision_not_source_evidence`; failure-rule IDs are
`not_applicable/synthetic_harness_only` unless the corresponding clean fixed
failure produced the blocked envelope.

**P00 scoped booleans (15, `EKO-P00`):**
`preflight.transaction_read_only`, `preflight.all_relations_present`,
`preflight.all_select`, `preflight.no_insert`, `preflight.no_update`,
`preflight.no_delete`, `preflight.no_truncate`, `preflight.no_references`,
`preflight.no_trigger`, `preflight.no_database_create`,
`preflight.no_database_temp`, `preflight.no_public_schema_create`,
`preflight.no_non_system_function_execute`,
`preflight.no_non_system_relation_write`,
`preflight.no_non_system_schema_create`.

**Scoped metadata (5):** `metadata.source_version_class` (`EKO-V01`),
`metadata.closed_candidate_columns` (`EKO-M10`), and
`metadata.index.parent_encounter_key`, `metadata.index.child_four_part_key`,
`metadata.index.patient_join_key` (`EKO-K20`).

**All seven parent fields:** `parent_field.encounter_id`,
`parent_field.chart_number`, `parent_field.patient_name`, `parent_field.sex`,
`parent_field.age`, `parent_field.state`, `parent_field.hold_yn`.

**All thirteen child fields:** `child_field.encounter_id`,
`child_field.order_date`, `child_field.order_number`,
`child_field.order_sequence`, `child_field.catalog_code`,
`child_field.catalog_name`, `child_field.user_code`, `child_field.user_name`,
`child_field.order_type`, `child_field.department_code`, `child_field.state`,
`child_field.dc_yn`, `child_field.act_yn`.

**Parent states and lifecycle:** `parent_state.waiting`,
`parent_state.in_progress`, `parent_state.on_hold`,
`parent_state.consultation_completed`, `parent_state.payment_completed`,
`parent_lifecycle.cancellation`, `parent_lifecycle.restoration`.

**Child state and qualifiers:** `child_semantics.active`,
`child_semantics.cancelled`, `child_semantics.dc_yn`,
`child_semantics.act_yn`.

**Relations and all categories:** `relation.parent`, `relation.child`,
`relation.patient_exact_one`, `category.fee`, `category.non_billing`,
`category.medication`, `category.procedure`, `category.unclassified`.

**Completeness and reconciliation:** `completeness.clinic_day`,
`completeness.all_parents`, `completeness.no_order_parents`,
`completeness.all_children`, `reconciliation.parent_counts`,
`reconciliation.child_counts`, `reconciliation.duplicates`,
`reconciliation.orphans`, `reconciliation.off_day`,
`reconciliation.verified_empty`, `reconciliation.save_completion_fence`,
`reconciliation.single_snapshot`.

**Simultaneous caps:** `cap.parents_and_sentinel`,
`cap.children_and_sentinel`, `cap.source_and_result_bytes`,
`cap.atomic_peak_memory`, `cap.global_deadline`.

**Owner policy:** `policy.age.leap_day_rule_a`.

**All failure rules:** `failure.preflight`, `failure.inventory_mismatch`,
`failure.unexpected_shape`, `failure.privacy_boundary`, `failure.row_limit`,
`failure.byte_limit`, `failure.timeout`, `failure.cancel`, `failure.rollback`,
`failure.cleanup`, `failure.version_mismatch`, `failure.capture_failed`,
`failure.contradiction`, `failure.no_retry_no_broadening`.

This explicit crosswalk does not imply evidence. The 19 M10 catalog candidates
do not prove the 7+13 logical fields, relation authority, category coverage, or
clinical semantics. P00 proves only its 15 booleans, not full least privilege.
K20 proves only the three allowlisted matching-index summaries, not expected
plans, authoritative keys, capacity, or complete relation coverage.

Expected application-query plan and index identities are `not_applicable` to this
metadata-only run because no patient-row, domain, aggregate, join, or application
query is permitted. `EKO-K20` can record only whether one of three predefined key
shapes has a simple matching index. Any later row or aggregate inventory must
freeze its own expected node/index identities and sanitized `EXPLAIN` statement
before a new review; this package cannot supply or inherit them dynamically.

No result from this run can name `source_id` or `mapping_revision`, enable
`EghisSourceDayReader`, or authorize a patient-row/aggregate statement.

## Non-echo capture requirements

The future capture harness must validate column names, order, types, cardinality,
text alphabet/length, enums, and total bytes before creating output. It must build
the canonical envelope from a fresh allowlisted object rather than serializing a
driver row or exception. Driver messages, SQLSTATE text, SQL, parameters, source
paths, connection properties, server messages, notices, stdout, and stderr are
discarded; only fixed reason codes may survive.

The fixed failure reasons are: `preflight_failed`, `inventory_mismatch`,
`unexpected_shape`, `privacy_boundary`, `row_limit`, `byte_limit`, `timeout`,
`cancel_failed`, `cleanup_uncertain`, `version_mismatch`, and `capture_failed`.
Failures emit no partial statement result. A temporary output must use create-new,
same-directory atomic publication and be removed after any failure; final output
must not exist until physical close and complete validation are proven.

## Stop, cancellation, and cleanup rules

Stop before `EKO-C00` if the exact commit/package/digests, approved maintenance
window, dedicated read-only path, reviewer, or cancellation owner is absent. Stop
after `EKO-P00` unless all 15 booleans are true, proceeding only to mandatory
`EKO-C99` cleanup. Stop after any later statement on
unexpected rows, types, values, plan/load behavior, lock wait, timeout, version,
privacy risk, or output growth. Never broaden privileges, inventory, predicates,
timeouts, suppression, or relation scope and never retry in the same run.

On cancellation, request driver cancellation once, close the cursor, roll back the
transaction, close the physical connection, and confirm the serialized-read lease
is released within the 10-second global deadline. If any step is uncertain, emit
only `cleanup_uncertain`, retain no result file, and require operator confirmation
before another separately approved attempt.

## Synthetic verification plan

Before execution approval, a pure injected harness must use invented catalog rows
and fake driver objects to prove:

1. exact happy-path shapes for all nine statements and deterministic canonical
   output;
2. digest mismatch, missing/extra/reordered columns, wrong types, booleans,
   duplicate/missing metadata IDs, 65th index row, 17th key column, 129-byte text,
   64-KiB overflow, and non-ASCII metadata rejection;
3. a 1..9 synthetic cohort can only become undifferentiated `UNPROVEN`, never an
   exact count or source code;
4. invented canaries placed in credentials, parameters, rows, exceptions, notices,
   SQLSTATE messages, stdout, and stderr never appear in output or logs;
5. timeout/cancellation/rollback/cursor-close/connection-close/lease-release paths,
   including uncertain cleanup and no partial file;
6. statement order is exactly `EKO-C00`, `EKO-C01`, `EKO-C02`, `EKO-C03`,
   `EKO-P00`, `EKO-V01`, `EKO-M10`, `EKO-K20`, `EKO-C99`, with no retry or
   dynamic query;
7. the four synthetic leap-day vectors above and adjacent ordinary birthdays; and
8. immutable evidence provenance, expiry/revalidation triggers, and fixed reason
   codes without host identity, PID, or raw time disclosure.

The repository now includes a pure injected candidate harness at
`KaosEghis/core/kaosorders_non_phi_evidence_capture.py` and synthetic tests at
`tests/test_kaosorders_non_phi_evidence_capture.py`. It imports no source driver,
filesystem, network, credential, runtime, logger, or deployment module. Its sink
and source port are test-injected only; no production adapter or activation exists.

Local verification on 2026-10-09 after the second bounded correction: the exact
focused file passed 37 tests under
the repository-approved `--noconftest` pure-model path; 355 adjacent lifecycle,
Orders, wire, Reception model, and Reception reader tests passed under the same
isolation. The normal focused invocation reached 37 setup errors solely because
the host cannot load PySide6 without `libxkbcommon.so.0`; all 37 cases failed at
fixture setup before the pure tests ran. No system package was
installed and this environmental blocker was not bypassed for the normal suite.

## Evidence provenance, expiry, and revalidation

A later evidence file must bind to the eventual independently reviewed Eghis
commit, central `e341737`, the
nine statement digests, evidence date, `production-read-only` environment class,
source/database version class, reviewer and authority roles, and the explicit
expiry trigger. It expires immediately on source/database version change, schema,
column, relation, key/index or privilege change, statement/digest change, identity
or environment change, contradictory evidence, protocol amendment, or review
expiry. Expired or unverifiable evidence becomes `unproven` and cannot be reused.

## Safety constraints and remaining gates

No source, credential, patient-level value, live checkout, service, runtime, or
deployment was accessed. No SQL was executed. The existing candidate application
query is not part of this package. Patient demographics, DOB/resident identifiers,
source rows, clinical aggregates, raw logs, and exact clinical counts remain
prohibited.

Orders and independent integration review accepted the exact package and the owner
authorized one bounded run, but execution remains fail-closed whenever the approved
read-only identity/path, exact executor, or window cannot be proven. Even a
successful metadata run would leave all row/domain/semantics/completeness/
performance criteria unproven and therefore cannot ratify a mapping. A later
expanded inventory must repeat the entire review sequence; this package cannot
dynamically authorize it.

## Authorized execution attempt: fail-closed pre-connection stop

On 2026-10-09 the owner authorized exact package `review-candidate-3` at Eghis
`dd394fe70ea2f8db4bf8dcbdffbbd749f8096952` under orchestration
`042bd0409fdd12421d93946594eda25ab189726d` and cleanup clarification
`8b6ae2ab822afbb7ee9c575e1587369eb850d1c8`. Repository synchronization and
immutable commit checks passed, but the registered H4 development clone supplied
no separately approved least-privilege read-only identity/path or production
adapter capable of proving the P00 boundary. The only package implementation is
the pure injected harness; `EghisSourceDayReader` remains unavailable.

The attempt therefore stopped before authentication, connection, cursor creation,
transaction start, or any statement. No credential store or value, connection
string, source host, live checkout, service, or patient data was inspected. No
cursor or physical connection existed, so closure is `not_applicable` rather than
claimed. No evidence artifact or partial file was created, and all P00/V01/M10/K20
and downstream mapping criteria remain unproven.

The next attempt requires a separately reviewable non-secret identity/path
attestation and an approved executor that reuses the existing serialized-read
boundary while enforcing the exact statement bytes, order, one 10-second fence,
in-connection shape/control validation, immediate cursor/physical-connection
closure, and post-close-only artifact construction. This record does not
authorize creating that adapter, inspecting credentials, or retrying.

At 2026-10-09 19:57 KST the owner authorized exactly one new retry, explicitly
without waiving any prerequisite. Repository sync preflight was repeated and the
exact Eghis, orchestration, and Orders commits were verified. The retry again
stopped before authentication because none of the following was available as a
reviewable non-secret record: an approved least-privilege identity/path
attestation; an independently approved bounded production executor; or a bounded
window naming its operator and cancellation owner. The approval timestamp alone
was not treated as proof of those prerequisites.

No authentication, connection, cursor, transaction, statement, cancellation, or
cleanup operation occurred. Cursor and physical-connection closure are therefore
`not_applicable`, not inferred. No evidence/partial artifact was created. This
consumes the authorized retry; another attempt requires new explicit approval
after all three prerequisite records exist and pass review.

## Prepared prerequisite contracts and executor candidate

Owner approval at 20:01 KST authorizes preparation and review, not source access.
The disabled candidate is
`KaosEghis/core/kaosorders_non_phi_evidence_executor.py`; its synthetic contract
tests are `tests/test_kaosorders_non_phi_evidence_executor.py`. It has no driver,
settings, credential lookup, connection string, source discovery, CLI, scheduler,
runtime import, or route. It accepts a resource-owning connection context, the
reviewed concrete serialized-read lease, and an atomic no-overwrite sink only
after three closed prerequisite objects validate.

The concrete disabled lease backend is
`KaosEghis/core/kaosorders_non_phi_evidence_lease.py`. Its factory is not imported
or called by application runtime code. Construction alone does not submit work,
acquire a mutex, connect, or read a source. On an explicitly approved future
attempt, it reuses the same bounded-capacity single-worker FIFO and
`_exclusive_reader` named mutex as `run_serialized_read`. The backend exposes
ownership only after the worker enters the exclusive scope, and reports release
only after that worker exits the scope. Queue admission, named-mutex wait, held
time, and release confirmation all consume the executor's one absolute deadline.
An unconfirmed queued worker, deadline-expired held lease, worker failure, or
release uncertainty marks the shared EMR reader unhealthy and blocks later reads.
No connection or credential behavior is included.

Normal lease release additionally requires executor-observed proof that the
owned physical connection was either never acquired or was confirmed closed. A
false or raised physical close is passed into the concrete lease as an unverified
cleanup result. The backend marks the shared reader unhealthy and wakes its
worker through the poison path; the worker raises inside the exclusive-reader
scope so Windows retains the named-mutex handle. It must not report normal lease
release. This blocks both later local FIFO reads and cross-process readers pending
operator recovery, and no evidence artifact may be published.

### Disabled executable composition candidate

`KaosEghis/core/kaosorders_non_phi_evidence_composition.py` is the sole non-test
composition root prepared under the bounded owner approval. It is not imported
by application runtime. Construction performs no queue submission,
authentication, connection, cursor creation, statement execution, publication,
or persistence. On an independently approved future call it binds exactly:

- the nine statement blocks extracted only from the fixed repository document,
  in `STATEMENT_SPECS` order, with every SHA-256 revalidated;
- `execute_reviewed_package_once()` and
  `build_disabled_orders_evidence_lease()`;
- one `ResourceOwningConnectionAdapter` over one
  exact `Psycopg2SingleConnectionPath`; and
- one volatile `AtomicNoOverwriteMemorySink`.

The path no longer accepts a caller allocator, receiver callback, or caller-
asserted acquisition enum. Reviewed code invokes exactly one
`psycopg2.connect` call with the future-approved opaque connection string and
fixed application/connect-timeout options. The string is injected only at
construction, is never discovered, logged, observed, or represented, and is
cleared when the single attempt starts. The exact owner derives `no connection`
only when that concrete driver call raises before returning an object. There is
no second-delivery callback surface and no caller-controlled success/absence
result.

Connection acquisition is daemon-contained by the same absolute deadline as
the executor. A late return is owned by that containment path and receives a
best-effort close, but is never reported as timely closure: ownership remains
uncertain and the FIFO/mutex lease is poisoned pending operator recovery. The
adapter wraps the sole cursor, records fixed non-sensitive acquisition/close
observations, prohibits cursor and connection reuse, and verifies the physical
driver's closed state. Statement execution, bounded fetch, cancellation, cursor
creation/close, and physical close are all deadline-contained. A timed-out
execute/fetch is never treated as a result, marks ownership uncertain, prevents
any later statement/fetch admission, and poisons the lease; only cleanup calls
may be attempted after the deadline. A timeout or exception never claims
closure, even if the daemon operation later finishes. Any uncertain acquisition,
statement/fetch, cancel, cursor cleanup, or physical close is propagated into
the accepted lease poison path; normalization and the volatile sink remain
unreachable until cursor, physical connection, and lease cleanup are all
verified within the fence.

The common bounded-call helper records a target-side monotonic completion time
before signaling completion and re-reads monotonic time after a successful
wait. A result is accepted only when both readings are finite and no later than
the one absolute deadline. Completion exactly at the deadline is accepted;
just-after-deadline or clock-uncertain completion is discarded as incomplete.
Consequently execute/fetch ownership becomes uncertain and cleanup/lease
poisoning applies, while physical close can never become verified from a late
result.

The sink is deliberately memory-only and atomic: it creates one temporary value,
publishes only when no final exists, never overwrites a pre-existing value, and
removes only values created by its own failed run. It is not filesystem or
production persistence. The composition is single-attempt and has no fallback,
pool, retained idle connection, retry, settings, scheduler, route, source
discovery, logging, or runtime activation.

The owner-authorized exception after the second integration-review failure is
limited to two executor defects: remove caller self-attestation of serialized
lease state, and make the one 10-second fence govern validation through all
cleanup and publication paths. It does not reopen the statement inventory,
evidence schema, source-access, runtime, or deployment scope.

The non-secret identity/path attestation must provide exactly: contract/version
ID, `approved` decision, privacy-safe attestation SHA-256, identity class
`dedicated-least-privilege-read-only`, path class
`existing-serialized-read-single-connection`, the frozen P00 statement digest,
authority role `database-security-authority`, and validity dates covering the
evidence date. No username, role dump, host, credential, or connection property is
permitted. This attestation is **not available** and cannot be invented here.

### Non-secret identity/path attestation template

The database security authority must complete and privacy-review this exact
shape outside chat. Angle-bracket values are required non-secret references, not
values supplied by this plan:

```json
{
  "contract_id": "kaoseghis.orders-evidence-read-path-attestation.v1",
  "decision": "approved",
  "attestation_sha256": "<64 lowercase hex privacy-safe attestation digest>",
  "identity_class": "dedicated-least-privilege-read-only",
  "path_class": "existing-serialized-read-single-connection",
  "p00_statement_sha256": "6b32e06db86fd62b7df3c6edb860b6f0e1482ec2f3e98b3304811688d0dcd3d6",
  "authority_role": "database-security-authority",
  "valid_from": "<YYYY-MM-DD>",
  "expires_on": "<YYYY-MM-DD>"
}
```

The attestation must not contain a username, host, port, database name,
connection string, role dump, credential, secret-store locator, token, or live
payload. Approval is invalid unless its date range covers the evidence date and
its digest resolves to a separately reviewed non-secret attestation.

The executor approval must provide exactly: approval contract/version ID,
`approved` decision, review SHA-256, exact 40-hex executor commit matching the
running build, reviewer role `independent-integration-review`, and package revision
`review-candidate-3`. The prepared candidate is not approved until its final
commit and tests receive independent PASS.

The window record must provide exactly: window contract/version ID, `approved`
decision, approval SHA-256, KST start/end no longer than 30 minutes and containing
the attempt time, plus non-sensitive stable references naming the operator and
cancellation owner. Those values are **not available** and cannot be inferred from
the owner's general approval.

### Bounded KST execution-window template

The future operator and cancellation owner must be named only by stable,
non-sensitive references. This template records no approval by itself:

```json
{
  "contract_id": "kaoseghis.orders-evidence-window.v1",
  "decision": "approved",
  "approval_sha256": "<64 lowercase hex privacy-safe approval digest>",
  "starts_at": "<YYYY-MM-DDTHH:MM:SS+09:00>",
  "ends_at": "<YYYY-MM-DDTHH:MM:SS+09:00>",
  "operator_reference": "<approved non-sensitive operator reference>",
  "cancellation_owner_reference": "<approved non-sensitive cancellation-owner reference>"
}
```

Both endpoints and the evidence date must be the same `Asia/Seoul` date, the
window must be positive and no longer than 30 minutes, and the actual attempt
time must fall inside it. No person name, contact detail, credential, host, or
patient information is permitted. Owner intent does not populate or activate
this record; it must be completed, independently reviewed, and reconfirmed before
one attempt can be authorized.

The candidate starts one monotonic 10-second fence before prerequisite and
statement validation. It requires `evidence_date`, KST `now`, and both
approved-window endpoints to share one exact KST date before connection,
validates all nine statement bytes/digests, opens at most one injected connection,
validates P00/V01/M10/K20 while connected, and marks C99 attempted before its sole
execution. A resource-owning acquisition context must prove either no connection
was allocated or its owned connection was closed, including allocate-then-raise.

The reviewed executor accepts only its exact concrete `SerializedReadLease`
wrapper, not an arbitrary duck-typed state object. The wrapper directly invokes
one backend `acquire_until(deadline)`, independently queries
`held_by_caller()` before any connection, and directly invokes
`release_owned(deadline)` in reviewed `finally` code. It queries ownership again
after release. A positive acquire without observed ownership, no acquisition,
an externally unreleased lease, a forged state object, multiple use, or uncertain
release all block with no publication. The concrete FIFO/mutex backend prepared
above must receive independent review and be bound by a later executor approval;
there is no runtime binding or activation in this candidate.

Validation, lease acquisition, connection acquisition, every statement,
cancellation, C99 rollback, cursor close, physical-connection close, lease
release, canonical artifact construction, atomic sink operations, and failure
cleanup all share the same fence. Confirmed late cleanup returns `timeout`;
uncertain cleanup returns `cleanup_uncertain`; either overrides an earlier
ordinary rejection and prevents publication.

Only after all guards pass may canonical artifact construction and atomic
no-overwrite publication occur. The sink must remove and verify absence of any
run-created visible final after failure; a pre-existing final is never overwritten
or deleted. Allowed fixed validation reasons are preserved without raw error text.
No runtime binding or activation is included.

Local verification after the disabled composition preparation and bounded
acquisition/deadline remediation: 32 composition/adapter/sink cases include
slow and hanging acquisition, execute, fetch, cancellation, cursor-close, and
physical-close probes under a 50-millisecond synthetic fence. The final focused
and adjacent isolated suites passed 128 and 355 tests respectively. The non-GUI
existing EMR read-queue
regression subset passed 45 with 3 platform skips; its four GUI consumer cases
remain unexecutable because this host cannot load PySide6 without
`libxkbcommon.so.0`. A further 355 lifecycle, Orders wire/fact, and Reception pure
regressions passed. The normal focused invocation reached 114 setup errors for the
same host-library blocker. No host package was installed, and isolated
verification is not reported as a full baseline.

## Next action

1. Independently review the exact immutable composition commit, including its
   frozen statement binding, one-shot path, resource ownership, deadline,
   cleanup/poison behavior, no-overwrite sink, and disabled runtime boundary.
2. Provide a reviewable non-secret attestation that identifies the approved
   least-privilege read-only path and confirms how P00 can be executed without
   exposing credentials or connection details.
3. Bind the resulting composition commit, executor, backend, and exact approved
   connection path in the immutable executor approval record.
4. Supply the bounded KST window plus non-sensitive operator and cancellation-owner
   references.
5. After all prerequisites pass, request a fresh single-attempt approval. Do not
   connect or execute before then.

## Revision history

- **2026-10-09:** Created the metadata-first closed run package, recorded leap-day
  rule A, fixed statement/output/bounds/non-echo/stop/cleanup requirements, and
  retained every source, credential, mapping, runtime, push, and deployment gate.
- **2026-10-09:** Remediated Orders review findings with the exact eight-column
  K20 shape, closed root/results/criteria/provenance schemas, fixed version range,
  one admission-through-release deadline, explicit 91-ID crosswalk, and a pure
  injected synthetic capture harness. No SQL, source, credential, patient data,
  runtime, package execution, push, or deployment was introduced.
- **2026-10-09:** Applied the user-authorized second bounded correction after
  Orders final review: any one of the 19 required M10 candidates with
  `column_present=false` now blocks as `inventory_mismatch`, cannot reach K20 or
  a complete artifact, and leaves `metadata.closed_candidate_columns` unproven.
  Package identity advanced to `review-candidate-3`; all nine statement bytes and
  SHA-256 values, output schema, mappings, identities, and runtime boundaries are
  unchanged.
- **2026-10-09:** Recorded the owner-authorized execution gate under orchestration
  `042bd04`/`8b6ae2a` and the fail-closed pre-connection stop. The registered H4
  clone could not prove an approved read-only identity/path and contains no
  approved production executor, so no authentication, connection, cursor, SQL,
  artifact, credential inspection, patient access, retry, runtime activation,
  push, or deployment occurred. All evidence criteria remain unproven.
- **2026-10-09:** Recorded the separately authorized 19:57 KST one-retry gate and
  its second fail-closed pre-authentication stop. The read-only identity/path
  attestation, approved executor, and bounded window/operator/cancellation-owner
  record were all absent, so the retry was consumed without authentication,
  connection, SQL, artifact creation, credential inspection, patient access,
  runtime activation, push, or deployment.
- **2026-10-09:** Under the 20:01 KST preparation approval, defined closed
  non-secret contracts for identity/path attestation, executor approval, and the
  bounded window, and added a disabled injected executor candidate with synthetic
  deadline/order/cleanup/post-close-publication tests. Identity/path and human
  window references remain absent; executor independent review remains pending.
  No authentication, source connection, SQL, artifact, runtime activation, push,
  or deployment occurred.
- **2026-10-09:** Remediated the first executor review return with closed
  single-callback/deadline-bound/released-lease proof, resource-owning acquisition,
  atomic no-overwrite/final-absence publication, one-attempt C99, exact KST
  evidence-date binding, and fixed reason preservation. Added synthetic probes for
  every failure path. Identity/path and window records and independent re-review
  remain pending; no source access or runtime activation occurred.
- **2026-10-09:** Applied the owner-authorized exception after the second/final
  executor review failure. Replaced caller-asserted lease booleans with an
  executor-owned single-entry/finally-release guard and extended one monotonic
  10-second fence from validation through cancellation, rollback, all closes,
  lease release, publication, and failure cleanup. Added forged-positive and late
  cleanup adversarial probes. Statements, evidence schemas, runtime boundaries,
  and all source/credential/deployment gates remain unchanged.
- **2026-10-09:** Applied the owner-authorized remediation of the remaining lease
  blocker. Replaced callback-finally lease state with the exact concrete
  `SerializedReadLease` wrapper: executor code now calls acquire/release and
  independently queries backend ownership before connection and after release.
  Added no-lease, false-positive acquire, forged-object, acquire-then-raise, and
  externally unreleased-backend probes. At that revision the production
  FIFO/mutex backend remained absent and required separate review before any
  execution approval.
- **2026-10-09:** Prepared the disabled concrete production-shaped FIFO/mutex
  backend using the existing EMR read worker and named-mutex scope, with one
  deadline, single-attempt admission, independent held/released observations,
  unhealthy fail-closed behavior, and no runtime import or activation. Added
  closed non-secret identity/path and KST window templates. No values were
  invented and the evidence attempt remains stopped pending independent PASS and
  later authorization reconfirmation.
- **2026-10-09:** After the first independent backend review, connected physical
  connection-close proof to lease cleanup. An unverified or raised close now
  poisons the shared reader and retains the cross-process mutex instead of
  allowing normal release. Added concrete executor/backend tests for close false,
  close raise, and verified close. Frozen statements and all execution gates are
  unchanged.
- **2026-10-09:** Under separate owner authorization, prepared the disabled
  non-test composition, one-shot injected serialized path, resource-owning
  connection/cursor adapter, and volatile atomic no-overwrite sink required by
  canonical stopped gate `4603c61`. Added synthetic success, acquisition,
  deadline, cancellation, cursor/physical close, no-overwrite, non-echo,
  single-attempt, and post-close-order tests. No credential, authentication,
  source connection, SQL execution, live data, runtime import, push, deployment,
  or evidence attempt occurred. Attestation, window, immutable approval binding,
  independent PASS, and fresh one-attempt authorization remain pending.
- **2026-10-09:** Applied the single bounded composition review remediation.
  Removed the arbitrary allocator callback and caller-asserted acquisition enum
  in favor of one exact owner-controlled `psycopg2.connect` boundary; added
  deadline containment and fail-closed lease poisoning for acquisition,
  cancellation, cursor cleanup, and physical close. Synthetic slow/hanging
  probes prove bounded return, no statement use on ambiguous acquisition, no
  artifact publication, and no normal mutex release. Frozen statement bytes,
  digests, package schema, disabled/unwired status, and every prerequisite gate
  remain unchanged; no authentication, source access, or evidence attempt
  occurred.
- **2026-10-09:** Applied the owner-authorized 22:19 KST exception remediation
  after final review of `fa3e9ce`. Wrapped synchronous `cursor.execute()` and
  `fetchmany()` in the same absolute-deadline containment used by acquisition
  and cleanup. A slow/hanging operation now returns within the synthetic fence,
  yields no result or artifact, admits no later statement/fetch, and poisons the
  FIFO/mutex lease. Added four slow/hanging execute/fetch regressions. Frozen
  statements/digests, result and mapping scope, one-connection/no-pooling
  boundary, disabled composition, volatile sink, and all evidence-attempt gates
  remain unchanged.
- **2026-10-09:** Applied the owner-authorized 22:30 KST boundary-race
  correction after review of `3bee2c4`. Completion acceptance now requires a
  target-side monotonic completion timestamp and a post-wait monotonic reading,
  both no later than the shared deadline. Deterministic tests accept the exact
  boundary and reject just-after completion for the helper, execute, fetch, and
  physical close; rejected results publish nothing and poison the shared lease.
  No statement, digest, schema, mapping, runtime, or stopped gate changed.
