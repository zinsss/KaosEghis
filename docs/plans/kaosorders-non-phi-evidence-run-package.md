# KaosOrders Non-PHI Source Evidence Run Package

- **Status:** review candidate; execution blocked pending independent PASS
- **Last updated:** 2026-10-09
- **Owner:** KaosEghis
- **Affected projects:** KaosEghis, KaosOrders, orchestration, integration review
- **Central baseline:** orchestration `e341737`
- **Package ID:** `eghis-kaosorders-non-phi-evidence-run-v1`
- **Package revision:** `review-candidate-1`

## Context and plan delta

Orchestration authorized the bounded non-PHI evidence protocol at immutable commit
`e341737`. This package is the Eghis-owned, documentation-only first run package
required before any source operation. It does not authorize or perform execution.

The original evidence plan contemplated one broad evidence package. Exact
demographic fields, authoritative joins, production types, and index identities
are still unproven, so this revision deliberately closes only a metadata-first
run. It may establish least-privilege and allowlisted catalog facts. It cannot
ratify a mapping, and it cannot dynamically expand into row, domain, aggregate,
plan, or demographic queries. A later inventory requires a new immutable digest,
documentation revision, Orders review, and independent PASS.

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
[Eghis → KaosOrders Non-PHI Evidence Statements v1](evidence/eghis-kaosorders-non-phi-evidence-statements-v1.md).
No implicit driver probe, session discovery, retry, count, `EXPLAIN`, wildcard,
row sample, or follow-up statement is allowed.

| ID | Purpose | Maximum rows | Criteria result |
| --- | --- | ---: | --- |
| `EKO-C00` | Start one read-only repeatable-read transaction. | 0 | Control must complete before evidence; any notice, result row, or failure stops the run. |
| `EKO-C01` | Set the local statement timeout to 1.5 seconds. | 0 | Exact control must succeed before evidence. |
| `EKO-C02` | Set the local lock timeout to 100 milliseconds. | 0 | Exact control must succeed before evidence. |
| `EKO-C03` | Set the local idle-in-transaction timeout to 5 seconds. | 0 | Exact control must succeed before evidence. |
| `EKO-P00` | Prove transaction read-only mode, SELECT on exactly three allowlisted relations, and absence of specified write/DDL/temp/non-system-function capabilities across non-system objects. | 1 | `proven` only if one row has every closed boolean true; otherwise stop and mark least privilege `unproven`. |
| `EKO-V01` | Record only PostgreSQL `server_version_num` as the source database version class. | 1 | Version provenance is `proven` only for one ASCII-digit string of at most 16 bytes; mismatch against the reviewed execution target stops the run. |
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

The capture produces one UTF-8 canonical JSON object with exactly these top-level
fields: `contract_id`, `package_id`, `package_revision`, `central_commit`,
`evidence_date`, `environment_class`, `source_version_class`, `statements`,
`criteria`, and `run_status`. Unexpected or missing fields reject the whole file.
The envelope contains no source ID, mapping revision, host, database, role, user,
credential, connection string, SQL, raw exception, raw timestamp, path, PID, or
patient-derived value.

Each `statements` item has exactly `statement_id`, `statement_sha256`, `status`,
`row_count`, `elapsed_bucket`, and `cleanup_status`. `status` is one of
`proven`, `unproven`, `not_applicable`; `row_count` is allowed only because the
closed metadata cardinalities are public package facts (five control rows of 0,
plus 1, 1, 19, and 3), not a
clinical count. `elapsed_bucket` is one of `lt_100ms`, `100_to_499ms`,
`500_to_1499ms`, `timeout`, and `cleanup_status` is `closed` or `uncertain`.

`EKO-P00` output is exactly the 15 booleans named in its SELECT. `EKO-V01`
outputs only `source_version_class`, which must be an ASCII-digit string of 1..16
bytes. `EKO-M10` output
is exactly `relation_id`, `column_id`, `column_present`, `data_type`, `nullable`,
`generated`, `identity`; the first two values must match the 19-entry allowlist,
and `data_type` is capped at 128 ASCII characters. `EKO-K20` output is exactly
`relation_id`, `index_method`, `is_unique`, `is_primary`, `is_valid`, `is_ready`,
`key_id`, `matching_index_count`, `any_unique`, `any_primary`, `all_valid`,
`all_ready`, `single_index_method`; relation/key IDs must match the three-entry
allowlist and `matching_index_count` is capped at 64.

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
- transaction admission only after an external serialized-read lease is obtained;
- 10-second total admission-to-physical-close deadline;
- 1.5-second statement timeout and 100-millisecond lock timeout per statement;
- no retry, no savepoint retry, no second connection, and no coalesced follow-up;
- maximum 24 result rows and 64 KiB canonical output for the full run;
- maximum 128 bytes for any scalar text and maximum matching-index count 64;
- cursor closure immediately after each fetch, transaction rollback after the last
  read, physical connection closure before validation/persistence, and detached
  row clearing after canonical output; and
- source version/environment mismatch, queue delay leaving less than 5 seconds,
  or inability to guarantee cleanup before the global deadline stops before the
  first statement.

## Criteria mapping

| Mapping criterion | This run can establish | This run cannot establish |
| --- | --- | --- |
| least privilege | Closed booleans for the exact relations and prohibited capabilities in `EKO-P00`. | Broader deployment identity, network, TLS, secret-store, or unlisted callable paths. Any false/unknown result blocks all later statements. |
| candidate fields/types | Presence, PostgreSQL type, nullability, generated and identity flags for 19 already named candidates. | Authoritative meaning, content domain, privacy approval, demographic source, or mapping assignment. |
| keys/indexes | Simple key/index shapes for three relations. | Expected production plan, capacity, complete relation coverage, save fence, or authoritative key selection. |
| parent/child semantics | Nothing; status remains `unproven`. | Raw state × hold truth table, child cancellation truth table, cancellation/restoration, no-order and category coverage. |
| completeness | Nothing; status remains `unproven`. | Complete-day, verified-empty, duplicate/orphan/off-day, exact-one join, alternate relation, and save consistency. |
| demographics | Leap-day product rule only, from owner decision rather than source evidence. | Chart/name/sex/age source fields, exact-one join, privacy-approved birth input/expression, and production domain proof. |
| performance | Bounded metadata statement duration buckets only. | Clinical-hours query plan, queue impact, row/byte capacity, aggregate query latency, or common-observation deadline proof. |

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
   codes without host, role, path, PID, or raw time disclosure.

No harness or product code is implemented in this documentation phase.

## Evidence provenance, expiry, and revalidation

A later evidence file must bind to this exact Eghis commit, central `e341737`, the
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
