# Controlled Metadata Follow-Up

Prepared: 2026-10-05. Starting sender/GitHub main:
`666afa887aab6f6cfae71b33b767a365ce624da0`, clean.

The operator authorized continuing the necessary **read-only** investigation.
This supersedes repeated permission prompts for the two bounded metadata checks
below, not the privacy restrictions or production-reader block. No patient table
contents, excluded qualifier, view definitions, credentials or role names may be
retrieved/output. No EMR action or write test is authorized.

## Exact Operations

Both exact statements are checked in under tests only. The one-shot caller must
use `run_verified_evidence_query` through the existing shared FIFO and
`Global\KaosEghis-EMR-read` mutex. No application importer, CLI or stored credential
is added. Each operation is executed separately, once, without automatic retry.

### View Dependencies: Gate 1

Exact statement: [source_view_dependencies_v1.sql](../tests/fixtures/source_view_dependencies_v1.sql).
SHA-256: `606b07c562cdd5d7349424cae728fccabd5cfe402e721f411374835b04626582`.

Parameters: schema `public`, reception table `h1opdin`, order table
`h2opd_doct_ord`. Catalog inputs (including joins/predicates):

| Catalog | Selected/referenced columns |
| --- | --- |
| pg_class | oid, relname, relnamespace, relkind |
| pg_namespace | oid, nspname |
| pg_depend | refobjid, refclassid, classid, objid |
| pg_rewrite | oid, ev_class |

Find directly dependent views and their one-hop relation/routine dependency
links. Do not recursively enumerate the schema, select view rows, or decompile
expressions. OIDs/names are used inside the statement only. Final output is
exactly the 17 fixed metric/count pairs in `VIEW_FIELDS` in
[the review harness](../tests/source_metadata_followup.py).

Caps: 2 source relations (3 sentinel), 64 scoped-view edges (65 sentinel),
128 relation edges and 128 routine edges (129 sentinels), 17 report rows
(18 sentinel). Distinct edges are capped after deduplication; statement timeout
bounds work before deduplication. Counts are not a claim that views are complete
or equivalent to the base tables. Unknown other relations are counted, not named.
Routine dependency metadata is not a complete call graph and no routine is run.

### Effective Privileges: Gate 8

Exact statement: [source_privileges_v1.sql](../tests/fixtures/source_privileges_v1.sql).
SHA-256: `7b4ad2bcaedfb489dc8a7401f748ddccda25eca995d494f70183aba205772795`.

Same schema/reception/order parameters, plus fixed **privilege-description data**:
`table_nonselect=INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER`,
`column_nonselect=INSERT,UPDATE,REFERENCES`, `schema_nonselect=CREATE`.
These are bound text arguments to built-in privilege inquiry functions, not SQL
commands. They never exercise any privilege, invoke source functions or change a
role. The shared SQL validator is unchanged.

| Catalog | Selected/referenced columns |
| --- | --- |
| pg_class | oid, relname, relnamespace, relkind, relowner |
| pg_namespace | oid, nspname |
| pg_roles | oid, rolname, rolsuper, rolcreaterole, rolcreatedb, rolinherit |
| pg_proc | oid, pronamespace, prosecdef |

Built-ins: `current_user`, `pg_has_role`, `has_table_privilege`,
`has_any_column_privilege`, `has_schema_privilege`, `has_function_privilege`.
Only aggregate flags/counts from `PRIVILEGE_FIELDS` leave the server. No role name,
password, ACL text, function name/body, connection string or database name is output.
The SELECT capability and non-SELECT capabilities are assessed independently of
the connection's enforced read-only mode. A read-only session does not establish
least privilege of its login role.

Caps: 2 source relations (3 sentinel), 1 own role/schema (2 sentinels),
64 reachable roles (65 sentinel), 128 schema-local SECURITY DEFINER routines
(129 sentinel), 18 report rows (19 sentinel). No broad function execution or
ownership/grant modification. This detects selected privilege blockers; a clean
result would not certify cluster-wide least privilege or function safety. RLS is
not inspected with later-version catalog fields on this PostgreSQL 9.2 source.

Official reference: PostgreSQL 9.2 [privilege inquiry functions](https://www.postgresql.org/docs/9.2/functions-info.html),
[dependency catalog](https://www.postgresql.org/docs/9.2/catalog-pg-depend.html),
and [rewrite catalog](https://www.postgresql.org/docs/9.2/catalog-pg-rewrite.html).
These justify inquiry semantics only, not this clinic's source meaning.

## Shared Safety And Failure Rules

- Finite connect timeout 3 s, statement timeout 2 s, verified read-only mode,
  autocommit READ COMMITTED. The one evidence statement is one statement snapshot.
- Shared reader retrieves at most 257 rows; tighter operation-specific lengths,
  strict field allowlists, integer bounds and count equalities are checked after
  verified cursor/physical-connection closure.
- Every partial, unknown, oversized, inconsistent, denied, timed-out or
  cleanup-unverified result is rejected with a fixed redacted reason. No retries,
  timeout extension or permission bypass. Uncertain physical close stops reads.
- Even a successful report always has `authoritative_snapshot=false`; no report
  is a source snapshot or can enter v2 normalization. No verified-empty claim.
- `EghisSourceDayReader` stays UNAVAILABLE; no production query, publication,
  endpoint, token, retry worker, PACS change or receiver change.

## Results

Both operations ran once at **2026-10-05 23:42 KST**, after 256 isolated mocked
tests passed in 1.45 s. No retries, clinical-row reads, view definitions, role
names, raw query results or production-write attempts were performed/persisted.
The stored connection setting was read in memory from the local settings database
opened with SQLite `mode=ro`; that local cursor/connection closed before the shared
EMR reader was called. No setting or credential was logged.

| Closure evidence | Views | Privileges |
| --- | --- | --- |
| Status | metadata_observed | metadata_observed |
| Read-only verified | true | true |
| Cursor closed | true | true |
| Physical connection closed | true | true |
| Connection work, seconds | 0.0717 | 0.0750 |
| Authoritative snapshot | false | false |

### View Findings

| Fixed aggregate | Count |
| --- | --- |
| Matched / ordinary source relations | 2 / 2 |
| Reception / order view links | 4 / 3 |
| Scoped view links / unique views / shared views | 7 / 4 / 3 |
| Ordinary / materialized views | 4 / 0 |
| Direct relation dependency links | 30 |
| Reception / order relation links | 4 / 3 |
| Other ordinary relation links | 23 |
| Other view / materialized / other-kind relation links | 0 / 0 / 0 |
| Recorded direct routine dependency links | 5 |

This resolves the earlier overlap subquestion: the three order-dependent views
are also reception-dependent, giving four distinct views. The 23 additional
ordinary-relation links are **not necessarily 23 unique tables**. No linked
object was named, queried or interpreted. The five recorded routine dependency
links are not a complete call graph. View filters, archive role, join meaning,
date scope and completeness remain unknown. Do not promote these views to a new
source, invoke a function, or infer equivalence to the two candidate base tables.

### Privilege Findings

| Fixed aggregate | Count |
| --- | --- |
| Matched / ordinary source relations | 2 / 2 |
| Own roles / inherit-enabled roles | 1 / 1 |
| Superuser / role-admin / database-admin roles | 0 / 0 / 0 |
| Reachable roles / privileged reachable roles | 1 / 0 |
| SELECT-capable source relations | 2 |
| Non-SELECT table-capable / column-capable relations | 0 / 0 |
| Source relation owner-role capabilities | 0 |
| Matched / usable / CREATE-capable source schemas | 1 / 1 / 1 |
| Schema-local SECURITY DEFINER / executable definer routines | 0 / 0 |

The source role has no detected non-SELECT capability on the **two scoped tables**,
but it does have CREATE capability in `public`. Thus gate 8 now has a concrete
least-privilege blocker, not merely absent permission evidence. The inquiry does
not attribute the grant to PUBLIC, direct grants or inherited roles. Do not change
shared schema grants or the EMR's login automatically. A database administrator
must review an appropriately restricted reader identity and effective grants;
no vendor response is required to recognize this blocker.

The connection itself was verified read-only throughout. A role capability was
observed, never exercised. This does not imply our check modified the EMR or that
PACS must be stopped. No PACS setting/code/process was touched. Other schemas,
databases, callable routines, external privileges and later-version policies were
not exhaustively audited. Zero selected privilege counts are not a complete
security certification.

## Read-Only Stopping Boundary

The two bounded structural/privilege operations are complete. **None of the eight
full source gates is resolved.** Repeating these counts or reading arbitrary
clinical rows cannot establish the remaining guarantees. In particular:

1. A consistent SELECT is not proof that the EMR saves reception and all orders
   in one transaction. Repeated equal reads, idle UI/caret state and a delay do not
   certify completeness. Authoritative FULL/empty snapshots remain blocked.
2. Operator-controlled disposable-visit changes are needed for untested date
   moves, retained-flag/state ambiguities and all-category edit/cancel/restore/key
   reuse paths. The agent must not perform those writes under read-only approval.
   Record aggregate-only before/after checkpoints and explicitly report the limits
   of finite observations. Do not repeat established transitions without a gap.
3. Completed-years age needs an approved derived source or a separately reviewed
   local derivation. Existing no-DOB/no-resident-number retrieval rules remain in
   force; broad read-only approval does not authorize those sensitive inputs.
4. Removing effective schema CREATE capability is an admin/write decision, not a
   read-only evidence operation. No grant is changed here, including PUBLIC.

Vendor information is unavailable, so do not make it the only next action. The
practical operator/admin checklist is in the [gate review](kaoseghis-source-evidence-gates.md#next-practical-decision).
If completeness/save-boundary authority cannot be established, a separately agreed
non-authoritative observation contract is the alternative. It must not claim FULL,
infer deletion from absence, or silently weaken v2. No alternative is implemented.

## Verification

Pre-live focused run: **256 passed in 1.45 s**. Final verification, including
additional success-to-v2 rejection checks:

- New probe module: 158 synthetic/mocked cases, all passed in the runs below.
- Focused source/model/v2/evidence/FIFO group: **1,124 passed in 4.64 s**.
- Broader source-shadow/outbox/shared-reader/PACS/flu/weekly-age/patient-context/
  runtime-contention/post-print group: **1,619 passed in 48.92 s**.
- Full isolated suite: **3,249 passed, 26 failed in 148.24 s**. The failures are
  the same previously documented baseline vaccine label/font/ink and shortcut
  width cases (24 label tests, 2 shortcut tests). No assertion was weakened or
  unrelated application/UI code changed. The earlier intermittent post-print
  failure did not occur in either current broader or full run.
- `git diff --check` passed. No application file, existing test assertion, v1/v2
  serializer, normalized fixture byte/hash, source block or PACS path changed.

The guarded runner blocks real database/network/desktop/printing activity and uses
temporary test data and isolated test mutexes. Only the two one-shot operations
above used the live shared reader and production mutex.
