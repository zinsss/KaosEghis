# Controlled Order Storage Review

Started 2026-10-06 at sender `c6386573c8ff36521470b0abfe181b40d77f8593`, clean main.
The operator authorized continuing necessary read-only checks until the next
engineering step is ready. This waives repeated permission prompts for bounded
reviewed checks, not privacy limits, mocked preflight, source gates or the runtime
block. No production implementation, EMR writes, grant changes or publishing.

The preceding [order coverage checkpoint](kaoseghis-order-coverage-proposal.md#approved-observation-2026-10-06)
found 122 receptions without children in the inspected table. The next question
is alternate storage, not another repetition of those counts.

## Operation 1: Catalog Candidates

Exact statement: [source_order_storage_catalog_v1.sql](../tests/fixtures/source_order_storage_catalog_v1.sql).
UTF-8/LF SHA-256:
`51228a1824143b04761280d2ea6eb813b6c1c230ce38c19166af937389da0933`.

Single gate-2 subquestion: which ordinary public relations have the known
reception column plus an order-number or order-code column? This does not prove
that candidate relations contain clinical orders or that no other source exists.

All catalog columns used:

| Catalog | Columns |
| --- | --- |
| pg_class | oid, relname, relkind, relnamespace |
| pg_namespace | oid, nspname |
| pg_attribute | attrelid, attname, atttypid, attnum, attisdropped |
| pg_type | oid, typname |

No clinical table contents, comments, definitions, routine bodies, demographics
or excluded qualifiers are read. OIDs remain inside metadata joins. Selected
attribute names are only `recept_no`, `ord_ymd`, `ord_no`, `ord_seq_no`, `ord_cd`.

Parameters: schema `public`, known order object `h2opd_doct_ord`, candidate limit
65, those five column names, and fixed type tokens `varchar`, `bpchar`, `text`,
`int2`, `int4`, `int8`, `numeric`, `date`, `timestamp`. Object-name pattern is
`^h[1-9][a-z_]{1,60}$`. Newly observed names outside this narrow EMR-style pattern
are masked on the server, counted, and cause fixed rejection without findings.
Unreviewed types are similarly masked/rejected; missing optional fields are the
fixed token `MISSING`. Relation kind must be `r`.

Allowed metadata output: candidate count and a sorted map of validated schema
object names to the five allowlisted type/missing tokens and SELECT-capability
booleans. These are table/column metadata, not patient/order identifier values.
Three internal fixed summaries must agree: `candidate_relations`,
`unreviewed_names`, `known_order_relations`. Unknown fields, duplicate names,
missing known source, malformed/partial results and overflow reject all findings.

Caps: 64 candidate objects plus one sentinel; 3 summary rows plus up to 64 profiles
(67 allowed result rows, 69 SQL sentinel limit). Underlying catalog search work is
bounded by the 2-second statement timeout, not by a claimed 64-entry scan.

## Shared Procedure

Each operation uses the existing verified evidence reader, FIFO and machine-wide
Windows mutex. Connection timeout 3 s; statement timeout 2 s; verified read-only
autocommit READ COMMITTED before one source statement. No retries, higher timeout,
permission bypass, direct connection or application-defined function execution.

Read the local connection setting with SQLite `mode=ro` only, close its cursor and
physical connection before source access, and never print the setting. Close and
verify source cursor and physical connection before validation or output. Uncertain
physical cleanup stops reads. Reports allow only fixed reasons, validated metadata
or aggregates, four closure/session booleans and bounded timing. No provider text,
raw rows, patient identifiers, payloads or credentials are logged or persisted.

Always `authoritative_snapshot=false`. No report can normalize as a source snapshot
or clear a valid board. `EghisSourceDayReader` remains UNAVAILABLE. The test harness
has no driver/default connection, CLI, settings or runtime importer.

Clinical-row follow-ups, if justified by metadata, require separate exact reviewed
parameterized SQL, caps, output allowlists and mocked tests before execution.
No broad scan is automatically generated from returned object names.

## Findings And Verification

Operation 1 ran once at **21:02:13 KST**, after **65 mocked tests passed in 1.12 s**.
It returned fixed `metadata_unreviewed`, with no findings retained. It did not
expose which unknown name/type failed the strict allowlist. Read-only mode, cursor
and physical connection closure were verified; connection work was **0.1007 s**.
The local settings cursor/connection had closed before source access. No retry or
clinical-table read was performed. All source gates remain unresolved.

## Operation 2: Explicitly Partial Catalog Inventory

Exact statement: [source_order_storage_inventory_v1.sql](../tests/fixtures/source_order_storage_inventory_v1.sql).
SHA-256: `6d78f3c379c8941bfd86d190c38608977d3df5199bc18505f937509883f14088`.
Same catalog columns, parameters, name/type allowlists and shared safety procedure
as operation 1. The first query and its rejecting validator remain unchanged.

This separate operation partitions candidate metadata into reviewed profiles,
omitted-name count, and omitted-type count among reviewed names. Unknown names and
types never leave the server. It returns reviewed profiles only plus three new
fixed integer summaries: `total_candidates`, `omitted_names`, `omitted_types`.
They must sum exactly to the returned reviewed-profile count. The known source
must still have a valid reviewed profile. Cap remains 64 candidate objects plus
one sentinel; up to 70 report rows (6 summaries + 64 profiles), SQL sentinel 72.

The validator reuses the unchanged strict profile validation and adds the
partition checks. `inventory_complete=false` whenever either omitted count is
positive. This is explicitly partial metadata discovery, not a complete source
inventory or clinical snapshot. A failure still returns no findings. A successful
profile permits preparing a later statement, not silently querying table contents.
No type/name allowlist is broadened in response to operation 1's rejection.

Operation 2 ran once at **21:05:12 KST**, after **92 mocked tests passed in 1.18 s**.
It observed **60** candidate ordinary tables: **44** reviewed profiles, **16** names
masked/omitted, **0** omitted types among reviewed names. Therefore
`inventory_complete=false`, `authoritative_snapshot=false`. Only the existing
`h2opd_doct_ord` had table-level SELECT among the 44 returned profiles. Its
reception/code columns are varchar, order date bpchar, and number/sequence numeric.
No meaning is inferred from other table names. No alternate table was queried.

Reviewed metadata included `h2opd_doct_ord_back`, `h2opd_procedure`,
`h2opd_jubjong`, `h3lab_result`, `h3xray_result` and other structural candidates,
all without table-level SELECT. Their existence does not prove independent
orders, current-day use, archival purpose or a missing source link. Table-level
privilege alone cannot rule out a limited column-level grant.

Read-only, cursor and physical-connection closure were verified in **0.0639 s**;
the local settings connection closed beforehand. No patient/order values, omitted
names, definitions, clinical contents or excluded qualifiers were returned. Only
the limited metadata and these aggregates are recorded, not a catalog dump.

## Operation 3: Candidate Column Access

Exact statement: [source_order_storage_access_v1.sql](../tests/fixtures/source_order_storage_access_v1.sql).
SHA-256: `2cf32cd7d263f149398a8c8211886bf6e5a2c280ea8dbfffc7fabdd4b884a8d3`.

Gate-2 access subquestion: does the current identity have any effective SELECT
capability on another structurally plausible source, including candidates omitted
from the metadata-name output? This inquiry tests capabilities without exercising
them, trying a denied clinical SELECT, or bypassing a permission.

Catalog columns: `pg_class(oid,relname,relkind,relnamespace)`,
`pg_namespace(oid,nspname)`, `pg_attribute(attrelid,attname,attnum,attisdropped)`.
Same five attribute-name filters, public ordinary-table scope and 64+1 candidate
cap. Parameters: schema, known order object, candidate limit and column-name list.
No source columns are read. Built-in privilege inquiries only:
`has_table_privilege`, `has_any_column_privilege`, `has_column_privilege`, with
`SELECT` as privilege-description data. Missing-column inquiries are guarded.

Allowed output is exactly 11 fixed metric/integer pairs: `candidate_relations`,
`known_relations`, `known_table_select`, `known_any_column_select`,
`other_relations`, `other_table_select`, `other_any_column_select`,
`other_reception_select`, `other_four_part_keys`, `other_four_part_select`,
`other_code_select`. No object/role name, ACL, key or patient data is output.
SQL limit 12 detects extra rows; validator requires exact fields, strict counts,
caps and subset equalities. Shared timeouts/read-only/closure procedure unchanged.

This cannot remove the already-observed schema-CREATE blocker or certify
cluster-wide least privilege. Positive access is not approval to read a table;
zero access is not proof that a table is empty or irrelevant.

Operation 3 ran once at **21:08:30 KST**, after **135 mocked tests passed in 1.29 s**.
It observed:

| Aggregate capability | Count |
| --- | ---: |
| All scoped candidate ordinary relations | 60 |
| Known doctor-order relation | 1 |
| Known relation with table SELECT | 1 |
| Known relation with any-column SELECT | 1 |
| Other candidate relations | 59 |
| Other relations with table SELECT | 0 |
| Other relations with any-column SELECT | 0 |
| Other relations with reception-column SELECT | 0 |
| Other relations containing all four named key columns | 41 |
| Other relations with SELECT on all four key columns | 0 |
| Other relations with order-code SELECT | 0 |

This includes the 16 candidates whose names were omitted in operation 2, without
revealing those names. Column-level access is not a hidden alternate route for
this scoped inventory. No denied SELECT was attempted, no grant was exercised
beyond catalog inquiries, and no restricted source function/view was used as a
workaround. Read-only mode, cursor and physical connection closure were verified;
connection work **0.1020 s**, local settings connection already closed.

## Decision And Stopping Point

The initial decision below is amended by the operator's subsequent
[national-flu workflow clarification](#operator-workflow-clarification). The access
observations remain valid, but expanded permissions are not a prerequisite merely
because some receptions have no order rows.

The alternate-storage investigation has reached a concrete access boundary.
The current identity can read only the already-inspected doctor-order object
among these candidates. Other ordinary objects with similar columns exist, but
neither their current-day contents nor their clinical role has been established.
The 59 objects are structural candidates, not 59 proven independent order sources;
do not request blanket access or infer semantics from names.

The catalog review did not determine the workflow of the 122 receptions with no
doctor-order rows. No metadata count proves that they need another order source.
The operator later provided relevant no-order workflow evidence below. More reads
of the same accessible table cannot substitute for clinical workflow context.

**Not ready to enable an authoritative FULL source reader.** The bounded
subquestions (candidate existence and effective candidate SELECT capability) are
observed; none of the eight full source gates is closed. In particular:

- If a concrete expected order is missing from the accessible source, review its
  source and seek narrow read-only access only if justified. Do not grant all
  candidates or treat expected empty child lists as evidence that new grants are
  needed. The separately observed effective CREATE capability in public remains
  a distinct least-privilege issue; no shared EMR grant is changed automatically.
- Save consistency/completion cannot be proved by these metadata reads, repeated
  equal counts, UI readiness, or arbitrary delays. Source completion evidence or a
  separately accepted non-authoritative observation contract is still required.
- Existing supervised state/key observations are preserved. Unseen retained-flag
  combinations and relevant all-category lifecycle paths need normal operator
  checkpoints, not guessed meanings or agent-authored clinical changes.
- The approved sex/age convention still lacks a reviewed safe age derivation;
  no DOB, resident number, demographic value or excluded qualifier was retrieved.

No further live query is attempted in this milestone. This is an access/evidence
block, not authorization to enable an incomplete reader, claim verified-empty
authority, use app credentials from another process, bypass permissions, change
PACS or relax v2. No clinical row was queried in any of these three operations.

## Operator Workflow Clarification

After the catalog review, the operator stated that today's national-influenza
vaccination patients have no EMR orders. Record this as operator-confirmed
workflow evidence for 2026-10-06, not as a new database observation or a universal
rule for every vaccination type/date.

This corrects the earlier emphasis on alternate storage: an encounter without
children can be entirely valid. The count alone never established missing orders,
and broader database permissions are not the next required step solely because
122 child lists were empty. The aggregate includes four earlier code-50/N
candidates; neither 122 nor the other 118 is automatically a national-flu count.
No patient identifiers, vaccination-record join or new live query is needed to
record this clarification.

For the agreed future Orders scope:

- Keep otherwise-included non-cancelled receptions even when they have no orders.
- Use an empty child-order list; do not fabricate vaccination or other orders.
- Do not classify a visit as national flu merely because its child list is empty.
- Preserve verified cancelled-encounter exclusion as a separate rule.
- Keep source failure/partial-read handling distinct from a valid empty child
  list. The clarification does not turn a failed whole-day read into an empty day.

The next useful validation is source scope/consistency and remaining normal
order-category lifecycle evidence, not speculative alternate-table access driven
by this count. Existing supervised transitions need not be repeated without a
specific gap. Save completion, retained qualifiers, safe age derivation and
least-privilege review remain separate unresolved matters. The production reader,
contracts, fixtures and runtime behavior are unchanged.

### Planned Dummy Checkpoint

The operator offered a disposable national-flu-like dummy case for tomorrow,
2026-10-07 KST. The useful first checkpoint is a dummy reception with **no EMR
orders**, following the stated workflow, not a newly invented vaccination order
or order code. Wait for the operator to leave it ready and confirm its current-day
state; nothing is scheduled or executed automatically.

The later read-only comparison should verify reception presence independently of
child presence and retain a valid empty order list. If a concrete coverage gap
remains, a separately confirmed ordinary test-order add/remove comparison can
follow under operator control. Do not repeat already-established lifecycle tests
without a question to answer, change a real record, print, submit a claim or
perform an EMR write. Review the exact bounded aggregate operation and mocked
failure/closure tests before any new live check. No patient details need to be
posted, logged or added to this documentation.

## KaosOrders Handoff

Review this completed sender milestone as a source-blocker update only. Preserve
the current-day memory-only session design and existing synthetic coordinator;
do not implement transport, wire fixtures, endpoint, token or board integration.
No source snapshot was produced. Do not send anything to
`/api/v1/order-snapshots`. Carry the operator-confirmed national-flu no-order
workflow into scope review: retain those encounters with empty order lists, not
fabricated orders or inferred vaccine labels. Expanded source access is conditional
on an actual missing-order case, not the no-order count. Remaining scope and
save-boundary evidence is still required; an observation-only alternative needs
an explicit separate contract decision. Do not
silently change FULL/complete=true or interpret missing rows as authoritative
deletions. Keep existing v1/v2 validators, hashes and synthetic stores intact.

## Final Verification

The three mocked preflight results and three live connection-closure records are
listed above. Focused source/shadow/serializer/outbox/shared-reader, PACS,
flu-report and patient-context regressions: **1,836 passed in 44.07 s**, including
all 135 new storage-review cases.

Full isolated suite: **3,712 passed, 26 failed in 179.98 s**. These are the same
previously recorded 24 vaccine label font/ink failures and two vaccine-shortcut
width failures; see the [preceding baseline](kaoseghis-order-coverage-proposal.md#verification).
No assertion was relaxed and no unrelated vaccine fix was made. The full suite
is not green. Tests used blocked external networking, mocked databases, isolated
test mutexes, offscreen Qt, disabled plugin autoload and temporary test data.

`git diff --check` passed. Application code and all four existing v1/v2 canonical
fixture bytes/hashes remain unchanged from the starting commit.
Only tests, SQL fixtures under tests, and sanitized documentation are changed.
The production reader, runtime triggers/settings, publishing and PACS stay untouched.

The later national-flu clarification and planned dummy checkpoint are
documentation-only updates. Focused source/v2/order-evidence regressions passed
**694 tests in 2.60 s**. No live database/UI operation was performed for that
clarification. The full-suite result above is the preceding milestone's result,
not a new full run; no application code, tests or fixture bytes changed afterward.
