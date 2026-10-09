# KaosOrders Non-PHI Source Evidence Run Package

- **Status:** review candidate; execution blocked pending independent PASS
- **Last updated:** 2026-10-09
- **Owner:** KaosEghis
- **Affected projects:** KaosEghis, KaosOrders, orchestration, integration review
- **Central baseline:** orchestration `e341737`
- **Package ID:** `eghis-kaosorders-non-phi-evidence-run-v1`
- **Package revision:** `review-candidate-2`

## Context and plan delta

Orchestration authorized the bounded non-PHI evidence protocol at immutable commit
`e341737`. This package is the Eghis-owned, documentation-only first run package
required before any source operation. It does not authorize or perform execution.

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
| `package_revision` | literal `review-candidate-2` |
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
  `data_type`, `nullable`, `generated`, `identity`. If `column_present` is false,
  the last four fields are all null. If true, `data_type` is 1..128 printable
  ASCII bytes and the other three fields are booleans.
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

Local verification on 2026-10-09: the exact focused file passed 36 tests under
the repository-approved `--noconftest` pure-model path; 355 adjacent lifecycle,
Orders, wire, Reception model, and Reception reader tests passed under the same
isolation. The normal focused invocation reached 35 setup errors solely because
the host cannot load PySide6 without `libxkbcommon.so.0`; all 36 cases failed at
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

Actual execution remains blocked until Orders reviews coverage, independent
integration review reproduces the statement digests and passes the exact commit,
and the
owner separately schedules the bounded read-only window. The run will still leave
all row/domain/semantics/completeness/performance criteria unproven and therefore
cannot ratify a mapping. A later expanded inventory must repeat the entire review
sequence; this package cannot dynamically authorize it.

## Next action

1. Independently reproduce the nine frozen statement digests.
2. Orders reviews whether this metadata-first boundary is useful and confirms that
   it does not imply logical/source coverage.
3. Integration review verifies statement bytes, schemas, non-echo rules, bounds,
   and the planned synthetic matrix.
4. Do not execute until all reviews pass and a separate bounded run is scheduled.

## Revision history

- **2026-10-09:** Created the metadata-first closed run package, recorded leap-day
  rule A, fixed statement/output/bounds/non-echo/stop/cleanup requirements, and
  retained every source, credential, mapping, runtime, push, and deployment gate.
- **2026-10-09:** Remediated Orders review findings with the exact eight-column
  K20 shape, closed root/results/criteria/provenance schemas, fixed version range,
  one admission-through-release deadline, explicit 91-ID crosswalk, and a pure
  injected synthetic capture harness. No SQL, source, credential, patient data,
  runtime, package execution, push, or deployment was introduced.
