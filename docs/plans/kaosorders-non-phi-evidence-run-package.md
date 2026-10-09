# KaosOrders Non-PHI Source Evidence Run Package

- **Status:** the consumed attempt remains blocked with no evidence artifact;
  a new resolver-bound approval-manifest candidate is prepared for independent
  review, but its package-review, window, authorization, and final manifest
  fields remain `BLOCKED`; no execution authority exists
- **Last updated:** 2026-10-10
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
Independent review subsequently passed the exact composition at
`e9e65e8dd8452e07a20908c63aa3703c767e9c3f`; that PASS settles code review only
and does not populate or waive the remaining prerequisite records.

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

### 2026-10-10 final-manifest attempt: fail-closed pre-authentication stop

Independent integration review passed exact Eghis commit
`8d131d5cdfab7fb4df1ea3c4b45c7f136d479f59` and manifest SHA-256
`0927dbcbbe54aa215a74f706a5751df4e99ecad213f9731e44dcde7efa753a0e`.
The reviewed single-use authorization was consumed for its one preflight at
2026-10-10 08:01 KST, inside the approved 08:00:00–08:30:00 KST window.

Repository and package checks passed: exact HEAD, current component bytes,
frozen statement inventory, manifest bindings, non-secret identity/path
attestation, window, and driver availability all matched. The approved local
settings boundary existed, but its opaque single-connection configuration was
absent. Therefore the concrete resource-owning path could not establish that a
dedicated approved identity was available. The closed no-fallback rule stopped
the attempt before authentication. No alternate file, environment, host,
credential store, or source path was searched.

No credential value, connection string, host detail, authentication, physical
connection, cursor, transaction, P00, later statement, live value, or patient
data was accessed. Cursor/physical-connection/lease cleanup is `not_applicable`
because no such resource was acquired. No partial or complete evidence artifact
was created or published, and every evidence criterion remains unproven. The
single-use authorization cannot be retried, extended, or reused even though the
window had not yet expired at the stop.

### Approved non-secret settings-resolution correction

After the stopped attempt, the owner separately approved only the operational
correction needed to resolve the opaque connection value from the existing
application settings store. The locator was recovered through sanitized session
history and matched the repository's existing public configuration contract.
Its literal, the store location, and the value are intentionally absent from
this document, source additions, tests, commit messages, and handoff.

`KaosEghis/core/kaosorders_non_phi_evidence_settings.py` is a new disabled,
unwired boundary. A future separately authorized caller must inject one exact
absolute settings-store path and one opaque locator. The resolver:

- accepts no defaults, discovery, fallback, environment scan, or alternate
  store;
- opens exactly that existing regular file using SQLite `mode=ro`, enables and
  verifies connection-local query-only mode, and uses one parameterized exact
  lookup;
- requires exactly one non-blank string row, rejects missing, duplicate,
  malformed, relative-path, symlink, reused, or cleanup-uncertain cases with the
  fixed `settings_resolution_failed` reason;
- uses whitespace trimming only to decide whether the string is non-blank and
  passes the original opaque string unchanged, including leading/trailing
  whitespace and Unicode code points, into the reviewed connection path;
- closes and verifies the cursor and settings connection before passing the
  opaque value directly into the already reviewed
  `Psycopg2SingleConnectionPath`; and
- never returns the opaque value through its public factory, logs, exceptions,
  representations, artifacts, or observations.

The factory only constructs the existing disabled composition. It performs no
source authentication or connection, and no application/runtime module imports
it. The previous immutable manifest does not bind this new component and cannot
be reused. No real setting value was read during implementation or tests; all
fixtures are unmistakably synthetic.

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
permitted. The owner supplied the complete substantive record below on
2026-10-10, and independent review accepted it at commit `722bef9`; it is not
execution authority.

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

#### Completed privacy-safe identity/path attestation

At 2026-10-10 07:05 KST, the owner explicitly acted as the
`database-security-authority`, approved the exact literal identity/path classes,
bound the frozen P00 digest, and supplied the inclusive validity dates. The
immutable attestation artifact is the following exact RFC 8785 JCS line; it
contains no name, contact, messaging, account, host, database, credential,
connection, or secret-store identifier:

```json
{"authority_role":"database-security-authority","contract_id":"kaoseghis.orders-evidence-read-path-attestation.v1","decision":"approved","expires_on":"2026-10-12","identity_class":"dedicated-least-privilege-read-only","p00_statement_sha256":"6b32e06db86fd62b7df3c6edb860b6f0e1482ec2f3e98b3304811688d0dcd3d6","path_class":"existing-serialized-read-single-connection","valid_from":"2026-10-10"}
```

The SHA-256 of those exact UTF-8 bytes, without a trailing line feed, is
`4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401`.
The closed envelope therefore has these exact values:

```json
{
  "contract_id": "kaoseghis.orders-evidence-read-path-attestation.v1",
  "decision": "approved",
  "attestation_sha256": "4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401",
  "identity_class": "dedicated-least-privilege-read-only",
  "path_class": "existing-serialized-read-single-connection",
  "p00_statement_sha256": "6b32e06db86fd62b7df3c6edb860b6f0e1482ec2f3e98b3304811688d0dcd3d6",
  "authority_role": "database-security-authority",
  "valid_from": "2026-10-10",
  "expires_on": "2026-10-12"
}
```

This supplies every owner-controlled substantive field in the closed
identity/path attestation and its privacy-safe immutable digest. Independent
review accepted exact commit `722bef966f5496c4b21df8db35053705a4fdc861`
and digest
`4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401`.
The attestation does not
pre-prove effective database privileges: after all prerequisites and the final
manifest pass review, P00 must still prove all 15 booleans in the same bounded
connection before any substantive evidence statement. The accepted digest is an
eligible future manifest input, but `identity_path_attestation_sha256` remains
`BLOCKED` until all remaining prerequisites are complete and the final manifest
is populated and independently reviewed.

#### Privacy-safe owner account-purpose attestation

On 2026-10-10 the authorized owner attested that the repository-configured
database account is a dedicated read-only least-privilege account and that the
configured database is the intended target. The following record intentionally
contains no person, contact, account, host, database, credential, connection, or
secret-store identifier. It is serialized as the exact RFC 8785 JCS line shown:

```json
{"asserted_account_purpose":"dedicated-read-only-least-privilege","asserted_on":"2026-10-10","authority_scope":"authorized-owner-statement-only","contract_id":"kaoseghis.orders-evidence-owner-account-purpose-attestation.v1","decision":"attested","target_scope":"repository-configured-intended-database"}
```

The SHA-256 of those exact UTF-8 bytes, without a trailing line feed, is
`4a64d3d82c1d66da7b2d71a2d017881bd457a3b1528788ab36bbb59c11f935b0`.
This immutable digest proves only the recorded owner assertion. It is not the
closed `attestation_sha256` below and is not inserted into the canonical
approval manifest: the statement does not establish that the owner is acting as
the required `database-security-authority`, does not attest the exact
`existing-serialized-read-single-connection` path, does not bind the P00 digest,
and supplies no validity interval. Effective privileges also remain runtime
facts that P00 must prove in-connection before any substantive evidence
statement; the owner assertion cannot pre-prove any of P00's 15 booleans.

#### Privacy-safe owner authority/approval assertion

On 2026-10-10 the owner additionally stated that the speaker is the relevant
authority and approves. The statement is recorded without a personal, contact,
messaging, account, host, database, credential, connection, or secret-store
identifier. Its bounded semantic scope is prerequisite-attestation processing
only, represented by this exact RFC 8785 JCS line:

```json
{"asserted_on":"2026-10-10","authority_claim":"relevant-authority","contract_id":"kaoseghis.orders-evidence-owner-authority-approval-assertion.v1","decision":"approved","scope":"prerequisite-attestation-processing-only"}
```

The SHA-256 of those exact UTF-8 bytes, without a trailing line feed, is
`740a56a5fc8301e8a357676cffdf59c1779be4ff426f43f0a3344cd0b41cc81a`.
This record establishes only that the unidentified speaker claims relevant
authority and approves the stated prerequisite-processing scope. It does not
state the literal `database-security-authority` role, identify or attest the
exact serialized path, bind P00, provide validity dates, name canonical
operator/cancellation-owner references, approve an active window, or provide
the post-prerequisite fresh single-attempt authorization required by the central
protocol. It therefore is not inserted as `attestation_sha256`,
`window_approval_sha256`, or `fresh_single_attempt_authorization_sha256`, and it
does not authorize credential lookup, authentication, connection, or execution.

#### Identity/path fail-closed proof checklist

Current readiness is **INDEPENDENT PASS**: the owner-supplied record populates
`attestation_sha256`, `valid_from`, and `expires_on`, and independent review
accepted exact commit `722bef966f5496c4b21df8db35053705a4fdc861` and its
digest. The manifest still remains `BLOCKED`. Before any future
authentication, reviewed preflight must prove every item below; false, missing,
expired, contradictory, unverifiable, or extra sensitive content stops before
credential lookup or connection:

1. The object has exactly the `IdentityPathAttestation` fields above, uses the
   literal contract/decision/classes/authority role, and passes strict types
   without coercion.
2. `attestation_sha256` resolves to one independently reviewed, immutable,
   privacy-safe non-secret attestation. The digest and reviewed artifact must
   agree byte-for-byte; an absent artifact or digest mismatch is unproven.
3. The authority attests a dedicated least-privilege read-only identity and the
   existing serialized single-connection path. Shared/general-purpose identity,
   pooling, fallback, discovery, retention, or a second connection is rejected.
4. The attestation binds the exact P00 digest
   `6b32e06db86fd62b7df3c6edb860b6f0e1482ec2f3e98b3304811688d0dcd3d6`
   and states that P00's 15 booleans must all be literal true. The attestation
   does not pre-prove those booleans; the bounded observation must still prove
   them in-connection or stop.
5. Its inclusive validity dates cover the exact KST evidence date, and no
   revocation, identity/path change, privilege change, or contradictory evidence
   has occurred since review. Any such event requires a new artifact and review.
6. The artifact contains no credential, username, role dump, host/port/database,
   connection property, secret locator, live payload, patient value, or raw log.
7. The future caller binds the attested path only through the reviewed
   `Psycopg2SingleConnectionPath` and `EghisFifoMutexLeaseBackend`; it cannot
   replace either with a callback, duck-typed allocator, pool, or fallback.

Passing this checklist is a prerequisite proof only. It does not authorize an
attempt, assign a source identity/mapping revision, or permit credential details
to enter this repository or handoff.

The executor approval must provide exactly: approval contract/version ID,
`approved` decision, review SHA-256, exact 40-hex executor commit matching the
running build, reviewer role `independent-integration-review`, and package revision
`review-candidate-3`. For this frozen candidate, the running-build commit is
`e9e65e8dd8452e07a20908c63aa3703c767e9c3f`; a different commit is rejected even
when the executor file itself is byte-identical.

The window record must provide exactly: window contract/version ID, `approved`
decision, approval SHA-256, KST start/end no longer than 30 minutes and containing
the attempt time, plus non-sensitive stable references naming the operator and
cancellation owner. The prior 08:00:00–08:30:00 record was consumed and is not
reusable. The owner's 08:47:38 KST exact statement supplies a new complete
09:00:00–09:30:00 KST candidate below; it is documentation-only and remains
unusable until independent review PASS.

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

Current human-only window readiness is closed as follows:

| Required value | Current state | Acceptance rule |
| --- | --- | --- |
| `approval_sha256` | `fa11d56b6bb1aa72ea0d224ad83e64bef1e7195814e65deb7d9b4031d22d654c` (**REVIEW PENDING**) | Exact lowercase 64-hex digest of the new JCS artifact below. |
| `starts_at` | `2026-10-10T09:00:00+09:00` | Exact owner-approved future KST timestamp at statement receipt. |
| `ends_at` | `2026-10-10T09:30:00+09:00` | Same KST date, strictly after start, duration exactly 30 minutes. |
| `operator_reference` | `kaosclinic-eghis` | Explicitly bound; passes `[A-Za-z0-9][A-Za-z0-9._-]*` and is 1..64 characters. |
| `cancellation_owner_reference` | `kaosclinic-owner` | Explicitly bound, distinct, and passes the same closed syntax. |
| attempt time and evidence date | **BLOCKED** | Inside the approved interval and identical KST calendar date. |

Independent review of the new exact record and its commit is pending. Missing,
stale, expired, mismatched, or unreviewed values still stop before credential
lookup or connection. The prior accepted commit `7b9baca642b6d3d77ec9e182c0892202136a64ba`
and its digest remain historical and non-reusable.

#### Owner-approved 09:00:00–09:30:00 KST window — review pending

At 2026-10-10 08:47:38 KST, the owner explicitly approved both seconds-bearing
endpoints and both privacy-safe stable role references. The start was future at
statement receipt. The immutable approval artifact is this exact RFC 8785 JCS
line:

```json
{"cancellation_owner_reference":"kaosclinic-owner","contract_id":"kaoseghis.orders-evidence-window.v1","decision":"approved","ends_at":"2026-10-10T09:30:00+09:00","operator_reference":"kaosclinic-eghis","starts_at":"2026-10-10T09:00:00+09:00"}
```

The SHA-256 of those exact UTF-8 bytes, without a trailing line feed, is
`fa11d56b6bb1aa72ea0d224ad83e64bef1e7195814e65deb7d9b4031d22d654c`.
The closed envelope therefore has these exact values:

```json
{
  "contract_id": "kaoseghis.orders-evidence-window.v1",
  "decision": "approved",
  "approval_sha256": "fa11d56b6bb1aa72ea0d224ad83e64bef1e7195814e65deb7d9b4031d22d654c",
  "starts_at": "2026-10-10T09:00:00+09:00",
  "ends_at": "2026-10-10T09:30:00+09:00",
  "operator_reference": "kaosclinic-eghis",
  "cancellation_owner_reference": "kaosclinic-owner"
}
```

The references satisfy the closed literal syntax, both endpoints share the same
KST date, and the duration is positive and exactly 1,800 seconds. This record is
not a fresh single-attempt authorization, does not populate the resolver-bound
manifest, and does not authorize setting read, authentication, connection, or
execution. It expires fail-closed at 09:30:00 KST and cannot be reused. A fresh
single-attempt authorization may be requested only after this exact artifact and
commit receive independent PASS and while a viable reviewed window remains.

#### Completed owner-approved 08:00:00–08:30:00 KST window

At 2026-10-10 07:48:51 KST, the owner explicitly approved both seconds-bearing
endpoints and both privacy-safe role references. The start was future at the
07:49:26 KST validation time. The immutable approval artifact is this exact RFC
8785 JCS line:

```json
{"cancellation_owner_reference":"kaosclinic-owner","contract_id":"kaoseghis.orders-evidence-window.v1","decision":"approved","ends_at":"2026-10-10T08:30:00+09:00","operator_reference":"kaosclinic-eghis","starts_at":"2026-10-10T08:00:00+09:00"}
```

The SHA-256 of those exact UTF-8 bytes, without a trailing line feed, is
`c848e431379c76eb5d1f75d98c22da10899ab0a06f35466f7c78abc01caa252d`.
The closed envelope therefore has these exact values:

```json
{
  "contract_id": "kaoseghis.orders-evidence-window.v1",
  "decision": "approved",
  "approval_sha256": "c848e431379c76eb5d1f75d98c22da10899ab0a06f35466f7c78abc01caa252d",
  "starts_at": "2026-10-10T08:00:00+09:00",
  "ends_at": "2026-10-10T08:30:00+09:00",
  "operator_reference": "kaosclinic-eghis",
  "cancellation_owner_reference": "kaosclinic-owner"
}
```

The references satisfy the closed literal syntax, both endpoints share the same
KST date, and the duration is positive and exactly 30 minutes. Independent
review accepted the record at exact commit
`7b9baca642b6d3d77ec9e182c0892202136a64ba`. The accepted digest is eligible
for manifest population and is populated below. The window record itself is not
a fresh single-attempt authorization and does not activate authentication or
execution. If final manifest review does not complete before 08:30:00 KST, this
record and the manifest bound to it expire and cannot be reused.

#### Earlier incomplete `08:00` plus 30 minutes candidate

At owner-message context 2026-10-10 07:41:20 KST and Lead validation time
07:42:08 KST, the owner supplied the literal `8시부터 30분간`. The Lead may
track this only as a candidate `08:00`–`08:30` minute interval. The start minute
was future at validation and the interpreted duration is 30 minutes, but the
owner did not supply seconds, an explicit approval statement, or the operator
and cancellation-owner bindings in this message. Therefore no ISO endpoint is
canonicalized, no prior reference is implicitly carried forward, and no active
window artifact or digest is created.

The next owner statement must use concrete future same-day `HH:MM:SS` endpoints,
explicit approval, and both role references in the exact form shown below. Until
then, `window_approval_sha256` remains `BLOCKED`.

#### Earlier incomplete `07:40` plus 30 minutes candidate

The owner's earlier shorthand is the literal `7시40부터 30분간`. The Lead may
track this only as a candidate `07:40`–`08:10` interval. The owner did not supply
seconds, an explicit approval statement, or the operator and cancellation-owner
bindings in this message. Therefore no endpoint is canonicalized, no prior
reference is implicitly carried forward, and no active window artifact or digest
is created.

The next owner statement must use concrete future same-day `HH:MM:SS` endpoints,
explicit approval, and both role references in the exact form already shown
below. Until then, `window_approval_sha256` remains `BLOCKED`.

#### Latest noncompliant `07:36`–`08:06` shorthand

The owner supplied the literal shorthand `7시36부터 8시6분`. The Lead observed
2026-10-10 07:36:31 KST before validation. The request omits seconds; interpreting
the minute endpoints as `:00` would make the start already past. Although the
minute-to-minute difference is exactly 30 minutes, the request is fail-closed
and does not become an active window, canonical artifact, digest, or execution
authority. This document records only the literal requested minute endpoints and
does not infer seconds.

The role references remain valid candidate literals. The owner must choose new
concrete future same-day `HH:MM:SS` endpoints with positive duration no longer
than 30 minutes. The exact required form remains:

> `2026-10-10 KST 실행 창을 <미래의 HH:MM:SS>부터 <같은 날이며 시작 후 30분 이내인 HH:MM:SS>까지 승인한다. operator_reference는 kaosclinic-eghis, cancellation_owner_reference는 kaosclinic-owner로 승인한다.`

Placeholders are not approval values. Until a new exact statement passes
validation and independent review, `window_approval_sha256` remains `BLOCKED`.

#### Earlier superseded noncompliant 07:00–12:00 KST request

The owner superseded the uncommitted 08:00–08:30 proposal with a five-hour
07:00–12:00 KST request. The exact request is fail-closed because it exceeds the
30-minute maximum, and its start had already passed when validated. It is not
split, shortened, reinterpreted, canonicalized as an approved artifact, or given
an approval digest. The earlier 08:00–08:30 artifact and digest were discarded
before commit and cannot be reused without a new explicit owner approval.

The two role references remain valid candidate literals because the owner changed
only the time. To create a compliant record, the owner must send this exact form
with newly selected concrete times:

> `2026-10-10 KST 실행 창을 <미래의 HH:MM:SS>부터 <같은 날이며 시작 후 30분 이내인 HH:MM:SS>까지 승인한다. operator_reference는 kaosclinic-eghis, cancellation_owner_reference는 kaosclinic-owner로 승인한다.`

Placeholders are not approval values. Both concrete endpoints must be future at
validation, use the same 2026-10-10 KST date, have positive duration no longer
than 30 minutes, and leave enough time for independent prerequisite and final
manifest review. Until such a statement is received, `window_approval_sha256`
remains `BLOCKED`.

#### Owner-supplied candidate window and pre-authentication assessment

At 2026-10-09 23:52 KST, the owner confirmation supplied the following
non-secret candidate values for independent review. They are recorded as
proposed inputs only; they do not change the closed template or make its
`approval_sha256` valid:

| Field | Candidate value | Readiness |
| --- | --- | --- |
| `starts_at` | `2026-10-10T00:30:00+09:00` | Supplied; not activated pending the prerequisite PASS and immutable approval digest. |
| `ends_at` | `2026-10-10T01:00:00+09:00` | Supplied; same KST day and exactly 30 minutes, but not reusable after expiry. |
| `operator_reference` | `agent:kaosclinic-eghis:main` | Supplied, but the colon characters do not match the closed `[A-Za-z0-9][A-Za-z0-9._-]*` syntax; a compliant canonical reference requires owner confirmation and cannot be normalized implicitly. |
| `cancellation_owner_reference` | **BLOCKED** | The owner-supplied reference is identity-bearing and remains out of band; no privacy-safe canonical value may be invented. |
| `approval_sha256` | **BLOCKED** | No immutable privacy-safe approval artifact and digest has been reviewed. |
| attempt time/evidence date | **BLOCKED** | No attempt occurred; a future attempt must begin inside the approved interval on 2026-10-10 KST. |

Privacy-safe H4 inspection established only that the repository defines the
`eghis_db_connection_string` setting key, defaults it to empty in tracked source,
and has existing consumers that obtain a configured value through application
settings. The registered H4 clone contained no local `.env`, SQLite, or database
configuration artifact to inspect, and no value was read or printed. The earlier
account-purpose statement alone did not create the closed attestation. The later
07:05 KST authority statement now supplies the exact substantive path,
authority, P00, and validity fields in the completed artifact above.

The identity/path record is **INDEPENDENT PASS**, and the exact 08:00:00–08:30:00
window above is also **INDEPENDENT PASS**. The canonical manifest below remains
unchanged and `BLOCKED`. No username, host, database, role dump, connection
property, credential, or secret-store locator is needed or permitted. A fresh
single-attempt authorization and final populated-manifest review remain required.

At the 2026-10-10 06:57 KST assessment, that endpoint had passed without the
required prerequisite PASS. The candidate window is therefore **EXPIRED** and
cannot be activated, extended, or reused. Its prior non-active values remain
historical evidence only; a new same-day bounded window, closed canonical role
references, immutable window approval digest, and later fresh single-attempt
authorization are required.

None of the historical rejected or incomplete requests authorizes access. Only
the exact seconds-bearing 08:00:00–08:30:00 record above received independent
PASS, and that PASS alone still does not authorize credential lookup,
authentication, connection, or query.

### Exact remaining package/review state

Accepted inputs are: the disabled composition at
`e9e65e8dd8452e07a20908c63aa3703c767e9c3f`; the deterministic closed
run-package procedure at `b57d2ea298e0bd5a5e30e047c3aa74c625cd666f`;
identity/path attestation commit `722bef966f5496c4b21df8db35053705a4fdc861`
and digest
`4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401`;
and window commit `7b9baca642b6d3d77ec9e182c0892202136a64ba` and digest
`c848e431379c76eb5d1f75d98c22da10899ab0a06f35466f7c78abc01caa252d`.
The independently accepted executor/package review record and the fresh owner
authorization are now frozen below. The populated manifest remains
**REVIEW PENDING** and cannot be consumed before its own independent final PASS.
The attempt timestamp/evidence date remains unset until a fully approved attempt
actually starts inside the window.

### Immutable fresh single-attempt authorization

At 2026-10-10 07:55:13 KST, the owner supplied this exact authorization text:

> `KaosEghis non-PHI evidence package eghis-kaosorders-non-phi-evidence-run-v1 / review-candidate-3, run-package commit b57d2ea298e0bd5a5e30e047c3aa74c625cd666f, composition commit e9e65e8dd8452e07a20908c63aa3703c767e9c3f, identity/path digest 4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401, window commit 7b9baca642b6d3d77ec9e182c0892202136a64ba 및 window digest c848e431379c76eb5d1f75d98c22da10899ab0a06f35466f7c78abc01caa252d (2026-10-10T08:00:00+09:00–2026-10-10T08:30:00+09:00)에 바인딩하여, 그 window 안에서 정확히 1회의 bounded non-PHI evidence attempt를 승인한다. retry, scope expansion, runtime activation, push, deploy는 승인하지 않는다.`

The closed record has only the authorization timestamp, the exact unmodified
text, a contract identifier, and the decision. Its exact RFC 8785 JCS UTF-8
bytes, without a trailing line feed, are:

```json
{"authorization_text":"KaosEghis non-PHI evidence package eghis-kaosorders-non-phi-evidence-run-v1 / review-candidate-3, run-package commit b57d2ea298e0bd5a5e30e047c3aa74c625cd666f, composition commit e9e65e8dd8452e07a20908c63aa3703c767e9c3f, identity/path digest 4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401, window commit 7b9baca642b6d3d77ec9e182c0892202136a64ba 및 window digest c848e431379c76eb5d1f75d98c22da10899ab0a06f35466f7c78abc01caa252d (2026-10-10T08:00:00+09:00–2026-10-10T08:30:00+09:00)에 바인딩하여, 그 window 안에서 정확히 1회의 bounded non-PHI evidence attempt를 승인한다. retry, scope expansion, runtime activation, push, deploy는 승인하지 않는다.","authorized_at":"2026-10-10T07:55:13+09:00","contract_id":"kaoseghis.orders-evidence-single-attempt-authorization.v1","decision":"approved"}
```

The SHA-256 of those exact bytes is
`afd57b2836f0d76bbaf2ee939d5ae215829410418ad23f15e4892ccd688cfcd3`.
This authorization is single-use, expires with the bound window, forbids retry
and scope expansion, and cannot be consumed until the final manifest receives
independent PASS.

### Immutable independent package-review record

Independent review supplied this exact digest-free RFC 8785 JCS record for the
accepted executor/package binding:

```json
{"contract_id":"kaoseghis.orders-evidence-executor-approval.v1","decision":"approved","executor_commit":"e9e65e8dd8452e07a20908c63aa3703c767e9c3f","package_revision":"review-candidate-3","reviewer_role":"independent-integration-review"}
```

The SHA-256 of those exact UTF-8 bytes, without a trailing line feed, is
`3ec16a2a63c380238aed884ff5d4a2b16129d0aabf9c6eab00fd888940068136`.

### Populated immutable approval manifest — final review pending

The following single line is the exact final RFC 8785 JCS serialization. Its
root digest was calculated by the non-self-referential rule below. It is a
review candidate, not executable authority: final independent manifest PASS and
an in-window recheck are still mandatory.

```json
{"approval_manifest_sha256":"0927dbcbbe54aa215a74f706a5751df4e99ecad213f9731e44dcde7efa753a0e","components":[{"commit":"1eaf325ab313fbde5a39b41f59ac21483271e861","component_id":"executor","path":"KaosEghis/core/kaosorders_non_phi_evidence_executor.py","sha256":"cc8694535fdac41ffa3b60acb20f5ce4fd7135cbca144c05522fba9e79838faa","symbols":["execute_reviewed_package_once","SerializedReadLease"]},{"commit":"1eaf325ab313fbde5a39b41f59ac21483271e861","component_id":"fifo-mutex-backend","path":"KaosEghis/core/kaosorders_non_phi_evidence_lease.py","sha256":"67f6c42b805a99a326201965a2a25a55efac65309863147dd777099921068949","symbols":["EghisFifoMutexLeaseBackend","build_disabled_orders_evidence_lease"]},{"commit":"e9e65e8dd8452e07a20908c63aa3703c767e9c3f","component_id":"composition-adapter-sink","path":"KaosEghis/core/kaosorders_non_phi_evidence_composition.py","sha256":"536117212fe40a8ce4f19085a2a84845bcb99bab4c93aaf55cee626ccb641846","symbols":["Psycopg2SingleConnectionPath","ResourceOwningConnectionAdapter","AtomicNoOverwriteMemorySink","build_disabled_orders_evidence_composition"]},{"commit":"dd394fe70ea2f8db4bf8dcbdffbbd749f8096952","component_id":"capture-contract","path":"KaosEghis/core/kaosorders_non_phi_evidence_capture.py","sha256":"95e7b292bbc1f2858a9621bfbc7e0fa19028fb2c01fd0107333c912cf1d47f96","symbols":["STATEMENT_SPECS","PACKAGE_REVISION"]}],"contract_id":"kaoseghis.orders-evidence-immutable-approval-manifest.v1","decision":"approved","independent_review_sha256":"3ec16a2a63c380238aed884ff5d4a2b16129d0aabf9c6eab00fd888940068136","package_id":"eghis-kaosorders-non-phi-evidence-run-v1","package_revision":"review-candidate-3","prerequisites":{"fresh_single_attempt_authorization_sha256":"afd57b2836f0d76bbaf2ee939d5ae215829410418ad23f15e4892ccd688cfcd3","identity_path_attestation_sha256":"4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401","window_approval_sha256":"c848e431379c76eb5d1f75d98c22da10899ab0a06f35466f7c78abc01caa252d"},"statement_inventory":{"commit":"1fc38adb189988eba5b177c30e2a9f8cc4633e68","ids_in_order":["EKO-C00","EKO-C01","EKO-C02","EKO-C03","EKO-P00","EKO-V01","EKO-M10","EKO-K20","EKO-C99"],"path":"docs/plans/evidence/eghis-kaosorders-non-phi-statements-v1.md","sha256":"0f123faff860e6eb18b4c8f6309b65731b459774950b1cedaa143f8d7caf7575"}}
```

Removing only `approval_manifest_sha256`, canonicalizing the remaining object,
and hashing its exact UTF-8 bytes yields
`0927dbcbbe54aa215a74f706a5751df4e99ecad213f9731e44dcde7efa753a0e`,
which exactly equals the supplied root value.

The statement-inventory digest binds the exact nine BEGIN/END blocks and the
per-statement SHA-256 table earlier in this document; both reproduced during
population. Component order, paths, symbols, commits, and content digests are
exact. Any later code, statement, package, review, attestation, or window change
invalidates the manifest and requires regeneration plus review.

#### Non-self-referential manifest digest

`approval_manifest_sha256` is an envelope checksum, not a member of its own
preimage. Generation and verification use this exact algorithm:

1. Parse the complete manifest as one JSON object. Reject duplicate keys,
   trailing content, invalid Unicode (including lone surrogates), NaN, infinity,
   or any value outside the RFC 8785/I-JSON domain.
2. Require exactly one root `approval_manifest_sha256` field. For generation it
   may contain the literal `BLOCKED`; for an approved final manifest it must be
   exactly 64 lowercase hexadecimal characters.
3. Make a logical copy and remove **only** that one root field. No nested field,
   other digest, `BLOCKED` value, array item, or component may be omitted or
   normalized away.
4. Serialize the remaining object with RFC 8785 JCS: recursively sort object
   property names by the RFC's UTF-16 code-unit ordering; emit no insignificant
   whitespace or byte-order mark; serialize strings and escapes exactly as JCS;
   and use ECMAScript shortest-round-trip number serialization. The current
   manifest intentionally uses no JSON numbers, but a later number must still
   obey this rule.
5. Encode that canonical character sequence as exact UTF-8 bytes, compute
   SHA-256, and encode the 32-byte result as lowercase hexadecimal.
6. Insert that 64-hex value as the root `approval_manifest_sha256`. The final
   stored/transmitted manifest itself must also be emitted as RFC 8785 JCS.
7. To verify, parse with the same rejection rules, retain the supplied digest,
   remove only the root digest field, reproduce steps 4–5, and compare the two
   lowercase-hex values exactly. A mismatch, missing/duplicate field, alternate
   canonicalization, or unverifiable implementation is fail-closed.

This rule has no circular preimage: changing any other manifest value changes
the digest, while changing only `approval_manifest_sha256` does not change the
preimage and is caught by comparison. The populated `decision` is `approved`
because the three prerequisite digests, fresh single-attempt authorization
digest, independent review digest, and reproducible manifest digest are all
real non-secret immutable references. That field is not usable execution
authority before independent final manifest PASS. Final review must also prove
`main.py` and all application/runtime modules have no import, route, scheduler,
settings, or startup binding to this composition. The manifest is not a
credential carrier and may never contain a connection string, host, identity
value, secret locator, clinical payload, or raw operational log.

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
regressions passed. The normal focused invocation reached 32 setup errors for the
same host-library blocker. No host package was installed, and isolated
verification is not reported as a full baseline.

### Resolver-bound approval-manifest candidate — blocked review input

The owner authorized preparation and independent review only for a new manifest
candidate bound to Eghis commit
`4565605845617de1ed3099c7abb887fbc45daabe`. The candidate adds the exact
disabled application-settings resolver component while retaining every
previously reviewed executor, FIFO/mutex, composition/adapter/sink, capture, and
nine-statement binding. Orders readiness remains complete at
`239b9b948bbb6e8c54288d2196287fb70a38aba0`; it requires no contract or schema
change.

The prior manifest, window, and authorization were consumed or expired and are
not reusable. The accepted identity/path attestation digest remains an eligible
privacy-safe prerequisite reference within its recorded validity interval, but
it does not authorize setting resolution, authentication, connection, or source
access. No identity/path value, operator, cancellation owner, window, or new
authorization is inferred here.

The following single line is the exact RFC 8785 JCS candidate. `BLOCKED` is
deliberate in the root checksum, decision, independent-review, window, and
fresh-authorization fields. This is a review input only, not a populated final
manifest and not execution authority:

```json
{"approval_manifest_sha256":"BLOCKED","components":[{"commit":"1eaf325ab313fbde5a39b41f59ac21483271e861","component_id":"executor","path":"KaosEghis/core/kaosorders_non_phi_evidence_executor.py","sha256":"cc8694535fdac41ffa3b60acb20f5ce4fd7135cbca144c05522fba9e79838faa","symbols":["execute_reviewed_package_once","SerializedReadLease"]},{"commit":"1eaf325ab313fbde5a39b41f59ac21483271e861","component_id":"fifo-mutex-backend","path":"KaosEghis/core/kaosorders_non_phi_evidence_lease.py","sha256":"67f6c42b805a99a326201965a2a25a55efac65309863147dd777099921068949","symbols":["EghisFifoMutexLeaseBackend","build_disabled_orders_evidence_lease"]},{"commit":"e9e65e8dd8452e07a20908c63aa3703c767e9c3f","component_id":"composition-adapter-sink","path":"KaosEghis/core/kaosorders_non_phi_evidence_composition.py","sha256":"536117212fe40a8ce4f19085a2a84845bcb99bab4c93aaf55cee626ccb641846","symbols":["Psycopg2SingleConnectionPath","ResourceOwningConnectionAdapter","AtomicNoOverwriteMemorySink","build_disabled_orders_evidence_composition"]},{"commit":"dd394fe70ea2f8db4bf8dcbdffbbd749f8096952","component_id":"capture-contract","path":"KaosEghis/core/kaosorders_non_phi_evidence_capture.py","sha256":"95e7b292bbc1f2858a9621bfbc7e0fa19028fb2c01fd0107333c912cf1d47f96","symbols":["STATEMENT_SPECS","PACKAGE_REVISION"]},{"commit":"4565605845617de1ed3099c7abb887fbc45daabe","component_id":"application-settings-resolver","path":"KaosEghis/core/kaosorders_non_phi_evidence_settings.py","sha256":"71977c3cb3fc475b679a3fa35152322f066fc7af6ef0ea393493d40202cd986d","symbols":["ApplicationSettingsOpaqueResolver","build_disabled_orders_evidence_composition_from_settings"]}],"contract_id":"kaoseghis.orders-evidence-immutable-approval-manifest.v1","decision":"BLOCKED","independent_review_sha256":"BLOCKED","package_id":"eghis-kaosorders-non-phi-evidence-run-v1","package_revision":"review-candidate-3","prerequisites":{"fresh_single_attempt_authorization_sha256":"BLOCKED","identity_path_attestation_sha256":"4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401","window_approval_sha256":"BLOCKED"},"statement_inventory":{"commit":"1fc38adb189988eba5b177c30e2a9f8cc4633e68","ids_in_order":["EKO-C00","EKO-C01","EKO-C02","EKO-C03","EKO-P00","EKO-V01","EKO-M10","EKO-K20","EKO-C99"],"path":"docs/plans/evidence/eghis-kaosorders-non-phi-statements-v1.md","sha256":"0f123faff860e6eb18b4c8f6309b65731b459774950b1cedaa143f8d7caf7575"}}
```

For review reproducibility only, removing the root
`approval_manifest_sha256` field and hashing the exact RFC 8785 JCS UTF-8
preimage yields
`1cdff065ee2ec33993a8f5563423a3d5b8da86c9a59e186f4656f8ef0a8938a6`.
This fingerprint is not inserted into the candidate and must not be mistaken
for a final approval-manifest digest. Independent review must reproduce every
component and statement digest, confirm the fifth component is disabled and
unwired, and issue a separate immutable package-review record before that
candidate field can be populated.

After that review, the minimum non-secret owner inputs are, in order:

1. A new future same-`Asia/Seoul`-day window no longer than 30 minutes, with
   explicit seconds and exact non-personal role references. Copyable form:
   `YYYY-MM-DD KST 실행 창을 HH:MM:SS부터 HH:MM:SS까지 승인한다. operator_reference는 <reference>, cancellation_owner_reference는 <reference>로 승인한다.`
2. Only after the window record independently passes, one fresh single-attempt
   authorization bound to this resolver implementation, the independently
   reviewed candidate-package commit/digest, the accepted identity/path digest,
   and the new window commit/digest. Copyable form:
   `KaosEghis non-PHI evidence package eghis-kaosorders-non-phi-evidence-run-v1 / review-candidate-3, implementation commit 4565605845617de1ed3099c7abb887fbc45daabe, resolver digest 71977c3cb3fc475b679a3fa35152322f066fc7af6ef0ea393493d40202cd986d, package-review digest <reviewed digest>, identity/path digest 4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401, window commit <reviewed commit> 및 window digest <reviewed digest> (<start ISO 8601>–<end ISO 8601>)에 바인딩하여, 그 window 안에서 정확히 1회의 bounded non-PHI evidence attempt를 승인한다. retry, scope expansion, runtime activation, push, deploy는 승인하지 않는다.`

Placeholders are instructions, not values or approval. After those records pass,
Eghis must regenerate a fully populated canonical manifest with no `BLOCKED`
field and obtain a separate final independent manifest PASS. Until then, setting
read, authentication, connection, statements, publication, and all runtime or
deployment actions remain stopped.

## Next action

1. Independently review the exact resolver-bound candidate above and the new
   09:00:00–09:30:00 window artifact, including their immutable bindings and
   reproduced digests.
2. Keep setting read, authentication, connection, P00, later statements, and
   publication stopped. Every prior window/authorization/manifest is non-reusable.
3. Only after both prerequisite reviews PASS, obtain a fresh single-attempt
   authorization bound to their exact commits/digests, then regenerate the
   populated manifest and obtain its separate final independent review.

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
- **2026-10-09:** After independent PASS of `e9e65e8`, prepared the remaining
  pre-execution package without source access. Added the exact identity/path
  fail-closed checklist, explicit `BLOCKED` KST window/operator/cancellation
  owner readiness, and a closed immutable approval-manifest candidate binding
  executor, FIFO/mutex backend, composition/adapter/sink, capture contract, and
  frozen statement inventory by commit and privacy-safe SHA-256. Human-only
  values, independent manifest review, and fresh attempt authorization remain
  blocked; no runtime wiring, authentication, connection, or execution occurred.
- **2026-10-09:** Corrected the approval-manifest checksum after independent
  review of `fe3a95d`. The SHA-256 preimage now omits only the root
  `approval_manifest_sha256` field and otherwise uses exact RFC 8785 JCS UTF-8
  bytes; verification repeats that transform and compares lowercase hex. This
  removes self-reference without changing any component binding or `BLOCKED`
  prerequisite.
- **2026-10-09:** Assessed the owner's proposed 2026-10-10 00:30–01:00 KST
  window and supplied operator/cancellation-owner references without accessing
  credentials or a source. Privacy-safe repository inspection confirmed only a
  configured-setting key and code path, not a database-security-authority proof
  of a dedicated least-privilege read-only identity. The identity/path
  attestation, window approval digest, immutable manifest, and attempt remain
  blocked; the candidate window expires rather than being reused if prerequisite
  review does not complete in time.
- **2026-10-09:** Removed a raw messaging-account identifier from the readiness
  record after independent review. Only the approved non-sensitive canonical
  reference may enter the closed field; out-of-band provenance is excluded.
  Manifest bytes, `BLOCKED` values, window semantics, and the pre-authentication
  stop are unchanged.
- **2026-10-10:** Recorded the owner's privacy-safe assertion that the intended
  repository-configured account is dedicated, read-only, and least-privilege as
  an exact JCS record with an immutable SHA-256. The record contains no person,
  contact, account, host, database, or secret identifier. It proves account
  purpose only; database-security authority, exact serialized path, P00 binding,
  validity dates, effective privileges, window approval, and the final manifest
  remain blocked. No credential lookup, authentication, or connection occurred.
- **2026-10-10:** Canonicalized the owner's claim of relevant authority and
  approval as a privacy-safe JCS record scoped only to prerequisite-attestation
  processing. It contains no identity/contact/source detail and cannot satisfy
  the literal database-security role, path/P00/validity, window, canonical role,
  or fresh single-attempt fields. Recorded that the prior 00:30–01:00 KST
  candidate window expired without activation. Authentication and execution
  remain stopped.
- **2026-10-10:** Processed the owner's 07:05 KST statement as the complete
  substantive identity/path attestation: literal database-security authority,
  dedicated least-privilege read-only identity class, existing serialized
  single-connection path, frozen P00 digest, and 2026-10-10 through 2026-10-12
  validity. Added its exact privacy-safe JCS artifact and SHA-256. At that commit
  the record awaited review; the later PASS is recorded below. It does not
  pre-prove P00, populate the still-blocked manifest, or authorize
  authentication/execution.
- **2026-10-10:** Before commit, the owner superseded the 08:00–08:30 proposal
  with 07:00–12:00 KST. The five-hour request exceeds the closed 30-minute limit
  and had a past start, so no window artifact or digest was finalized. Preserved
  the two syntax-valid role references, documented the exact compliant approval
  form needed, and kept the manifest and all execution gates blocked.
- **2026-10-10:** Corrected stale downstream status after integration review
  confirmed independent PASS for identity/path attestation commit `722bef9` and
  digest
  `4c2165d10df152d6e68b878e160c47fc1e6087c05d4a46796be5f2cd639cd401`.
  The accepted digest is eligible for later manifest population, but the
  manifest remains unchanged and `BLOCKED`; the rejected window and every
  authentication/execution gate remain stopped.
- **2026-10-10:** Recorded the owner's latest literal `07:36`–`08:06` shorthand
  fail-closed. At the observed 07:36:31 KST validation time, an inferred `:00`
  start was already past, and the owner had not supplied seconds. No seconds,
  active window, artifact, or digest were inferred; the syntax-valid role
  references and all BLOCKED gates were preserved.
- **2026-10-10:** Recorded the superseding literal `7시40부터 30분간` only as
  an incomplete `07:40`–`08:10` candidate. Seconds, explicit approval, and role
  bindings were absent, so no endpoint, artifact, digest, or execution authority
  was canonicalized; all gates remain blocked.
- **2026-10-10:** Recorded the latest literal `8시부터 30분간` only as an
  incomplete future `08:00`–`08:30` minute candidate. It fits the duration bound
  at minute precision, but seconds, explicit approval, and role bindings were
  absent, so no ISO endpoint, artifact, digest, or execution authority was
  canonicalized.
- **2026-10-10:** Processed the owner's exact 07:48:51 KST statement into a
  complete 08:00:00–08:30:00 same-day window artifact and closed envelope.
  Seconds, explicit approval, and both role bindings are present; the JCS
  SHA-256 is `c848e431379c76eb5d1f75d98c22da10899ab0a06f35466f7c78abc01caa252d`.
  The record remains review-pending and does not populate the still-blocked
  manifest or authorize authentication/execution.
- **2026-10-10:** Recorded independent PASS for window commit `7b9baca` and
  digest `c848e431379c76eb5d1f75d98c22da10899ab0a06f35466f7c78abc01caa252d`.
  Added the exact remaining manifest/review state and the minimal owner statement
  required for a fresh one-attempt authorization. The statement is a template
  only; it was not inferred, hashed, consumed, or treated as execution authority.
- **2026-10-10:** Preserved the owner's exact 07:55:13 KST single-attempt
  authorization in a closed RFC 8785 JCS record with SHA-256
  `afd57b2836f0d76bbaf2ee939d5ae215829410418ad23f15e4892ccd688cfcd3`.
  Recorded the independently accepted package-review artifact digest
  `3ec16a2a63c380238aed884ff5d4a2b16129d0aabf9c6eab00fd888940068136`
  and populated the exact manifest with non-self-referential root digest
  `0927dbcbbe54aa215a74f706a5751df4e99ecad213f9731e44dcde7efa753a0e`.
  Final independent manifest review remains required before authentication or
  execution, and the entire authorization expires fail-closed with the bound
  08:00:00–08:30:00 KST window. No credential, source, query, runtime, push, or
  deployment action occurred.
- **2026-10-10:** Recorded independent final PASS for exact commit `8d131d5` and
  manifest digest `0927dbcbbe54aa215a74f706a5751df4e99ecad213f9731e44dcde7efa753a0e`.
  Consumed the single-use authorization for one 08:01 KST preflight. Exact
  repository/package checks passed, but the approved settings boundary contained
  no configured opaque connection, so execution stopped before authentication
  with no resource acquisition or evidence artifact. No fallback discovery,
  retry, live value access, runtime activation, push, or deployment occurred.
- **2026-10-10:** Under separate owner approval, added only a disabled injected
  read-only application-settings resolver and synthetic contract tests. The
  out-of-band locator was checked against the existing config contract but was
  not copied into any new source, test, document, output, or handoff. No real
  setting value, credential, authentication, source connection, SQL, patient
  data, runtime activation, retry, push, or deployment occurred. A new window,
  fresh authorization, regenerated manifest, and final review remain required.
- **2026-10-10:** Applied the single integration-review return: preserved the
  original opaque string unchanged while retaining whitespace-only rejection,
  and added synthetic probes for connect, cursor creation, both PRAGMA steps,
  value query/fetch, cursor close, connection close, and both post-close
  verification failures. Every failure consumes the resolver once, attempts all
  available cleanup, returns only `settings_resolution_failed`, constructs no
  composition, and emits no locator/value. All execution gates remain stopped.
- **2026-10-10:** Prepared the owner-approved resolver-bound approval-manifest
  candidate for independent review only. Added exact commit/path/symbol/SHA-256
  binding for the disabled resolver at `4565605`, retained all accepted
  component and nine-statement bindings, preserved the accepted privacy-safe
  identity/path digest, and left the independent-review, window, fresh
  authorization, decision, and root manifest fields explicitly `BLOCKED`.
  Recorded a reproducible candidate preimage fingerprint and the exact ordered
  non-secret owner templates needed after review. No setting read,
  authentication, source access, evidence execution, publication, runtime
  activation, push, merge, or deployment occurred.
- **2026-10-10:** Recorded the owner's exact 08:47:38 KST approval as a new
  09:00:00–09:30:00 same-day window artifact with stable privacy-safe operator
  and cancellation-owner references. Canonicalized the exact RFC 8785 JCS bytes
  and SHA-256 while keeping independent review pending. The prior window,
  authorization, and manifest remain non-reusable; no fresh authorization was
  created or consumed and no setting, credential, source, runtime, push, merge,
  or deployment action occurred.
