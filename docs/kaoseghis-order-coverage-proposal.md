# Current-Day Order Coverage Proposal

Prepared: 2026-10-06 from sender `053c2a764a18e4a3aa0eee387da34d9515e09262`.

Status: **one approved aggregate checkpoint completed; full source authority
unresolved**. This is a bounded aggregate diagnostic for gate 2, not a full-day
reader or normalized snapshot. All eight complete source gates remain unresolved.
The production reader stays UNAVAILABLE, and nothing here authorizes publishing
or patient-data export. Initial preparation was mocked only; the later observation
is recorded below.

## Why This Check

The [previous membership observation](kaoseghis-current-day-counts-proposal.md#observed-checkpoint-2026-10-06)
included 118 code-40/N receptions with no matching child in the inspected order
table. That is not evidence of no clinical orders elsewhere. Before implementing
an all-orders reader, compare the proposed parent-linked child set against the
same table's order-date set, without returning identifiers or dropping no-order
encounters.

The built-in queries were reviewed at the starting commit:

| Query | Membership and link | What it cannot establish |
| --- | --- | --- |
| PACS, `core/pacs_polling.py` | `mwl` joins `h2opd_doct_ord` using three key components from `eghis_key`; XRAY only, scheduled status 100 or cancelled child flag; day is selected from coalesced MWL timestamps | No reception-side membership or no-order encounters; join does not use `ord_ymd`; not all-order or four-part identity authority |
| Flu report, `core/weekly_age_reporting.py` | `h1opdin` joins the patient master; clinic-date range, states 30/40 and birthdate-derived age buckets; counts distinct patients | Does not read order rows at all; cannot establish child coverage or explain missing child rows |
| Proposed diagnostic | All current-day candidate receptions, their linked children without an order-date filter, and orders dated today | Counts and anomalies only; no alternate-table discovery, clinical interpretation, complete source authority or save-completion proof |

Both existing features allow configured SQL overrides. This review did not read
runtime settings, so it describes built-ins, not verified deployed overrides.
Neither existing query is a ready replacement for an all-orders source. No PACS
or flu-report code or configuration is changed. The flu report's demographic join
is not copied into this probe.

## Exact Statement And Inputs

Complete parameterized statement:
[source_order_coverage_v1.sql](../tests/fixtures/source_order_coverage_v1.sql).

SHA-256 of UTF-8 SQL with LF newlines:
`d608ae8ca3e477b1719f67f7ad2ff8a539bafae64aa8d27b795009300611c53c`.
The test-only harness rejects a changed hash pending review. There is no CLI,
connection setting, driver creation, output sink or application importer.

| Source | Every selected/referenced source column | Use |
| --- | --- | --- |
| `public.h1opdin` | `clinic_ymd` | Bound current-day predicate |
| `public.h1opdin` | `recept_no` | Internal existence link, null/blank and duplicate checks |
| `public.h2opd_doct_ord` | `recept_no`, `ord_ymd`, `ord_no`, `ord_seq_no` | Internal full-key grouping, date-set comparison and validity checks |

No source key or order date leaves the database. No qualifier, reception state,
order code/type/department, patient-master column, demographic, clinical note,
insurance or excluded `hold_opd` value is retrieved. Cancellation is not inferred.

Inputs are only `day` (reviewed current KST date as `YYYYMMDD`),
`encounter_limit=10001`, and `order_limit=100001`. One server current-KST-day guard
gates both day-selected sets. The injected aware clock checks before queueing,
after verified cleanup, and after validation. A rollover or client/server date
mismatch discards the report. No arbitrary date or historical reception scope.

The linked arm includes children of today's receptions even if their order date
differs. Only the aggregate off-day count is returned. This is not a historical
reception scan or authorization for backfill. The other arm selects only orders
dated today. `EXISTS` avoids multiplying orders when reception keys are duplicated.
The diagnostic retains all candidate receptions, including cancelled/no-order
ones; it does not implement the future Orders-only cancellation filter.

## Exact Output Allowlist

The statement returns two columns, `metric` and `n`, with exactly these 17 rows:

| Fixed metric | Meaning |
| --- | --- |
| `current_day_matches` | Server date agrees with the bound current day, 0/1 |
| `encounters` | Candidate reception rows |
| `encounters_with_orders` | Candidate reception rows with any linked child |
| `encounters_without_orders` | Candidate reception rows without a linked child |
| `invalid_encounter_keys` | Reception rows with null/blank keys |
| `duplicate_encounter_keys` | Duplicate reception-key groups |
| `linked_orders` | All child rows linked to the current-day reception set |
| `dated_orders` | Order rows dated today |
| `linked_orders_on_day` | Linked children whose order date is today |
| `linked_orders_off_day` | Linked children whose date differs, including null |
| `dated_orders_with_day_encounter` | Today-dated orders with a current-day reception |
| `dated_orders_without_day_encounter` | Today-dated orders without a matching current-day reception |
| `linked_invalid_keys` | Linked rows with any null/blank full-key component |
| `dated_invalid_keys` | Today-dated rows with any null/blank full-key component |
| `linked_duplicate_keys` | Duplicate four-part-key groups in linked rows |
| `dated_duplicate_keys` | Duplicate four-part-key groups in today-dated rows |
| `linked_three_part_multi_date_keys` | Linked three-part-key groups occurring on multiple distinct order dates |

Duplicate metrics count groups, not excess rows. Key validity here means only
null/blank checks, not full source-domain/calendar validation. A three-part group
spanning dates is not necessarily a duplicate four-part key. An unmatched
today-dated row is not necessarily globally orphaned, cancelled or erroneous.
An off-day child is not assigned clinical meaning or silently excluded.

After physical closure, the harness checks exact metric membership, strict
integer counts, caps, partition sums, intersecting-set equality and subcount
bounds. Positive anomaly metrics return only their fixed names in
`review_required`, with status `coverage_anomalies_observed`. A clean diagnostic
is `order_counts_observed`. Neither status grants source authority.

The report also allows `authoritative_snapshot=false`, fixed redacted status
codes, four session/closure booleans and finite bounded connection-work seconds.
No raw rows, SQL, provider messages, credentials, keys or arbitrary strings are
reported, logged or persisted by the harness. Aggregate zero remains an observation,
not an authoritative empty snapshot. Every rejected report omits findings.

## Bounds, Consistency And Cleanup

- Use only the trusted shared `run_verified_evidence_query`, its FIFO worker and
  machine-wide `Global\KaosEghis-EMR-read` mutex. No new connection path or pool.
- Connection timeout 3 seconds; statement timeout 2 seconds. Verify read-only
  autocommit READ COMMITTED and the finite timeout before executing the statement.
  Never test restrictions by attempting a write.
- One source statement, no retries, polling, timeout increase or permission bypass.
- Reception cap 10,000 plus sentinel; each order arm cap 100,000 plus sentinel.
  Encounter/order sentinels reject the entire report, never partial coverage.
- Exactly 17 output rows are required, with SQL limit 18 as an output sentinel.
  The shared reader's larger fetch bound does not relax this validator.
- Caps bound materialized candidate rows, not necessarily all underlying scan work.
  Index efficiency and live execution time are unverified; the statement timeout
  bounds server execution. A timeout means stop, not broaden the query.
- Cursor and physical connection closure must be verified before interpretation
  or output. Uncertain physical cleanup stops the shared reader and future reads.
- Failed, malformed, partial, overflowed, inconsistent, wrong-day or
  cleanup-unverified reads cannot become empty/complete source snapshots.

One reviewed statement avoids combining independent autocommit snapshots.
Internal set agreement still cannot show that an EMR save spans one transaction,
that alternate order storage is absent, or that source membership is authoritative.
The previously reviewed unique index and dummy key-reuse observations are not
repeated or upgraded into immutable lifetime identity claims.

## Live Checkpoint Procedure

Initial preparation performed no live DB, screen, input or service operation.
A live checkpoint must review this exact statement and confirm the then-current
KST day under the bounded read-only authorization. Run it once using the shared
verified reader; retain only sanitized aggregate findings, closure results and
limitations. Do not run it against a previous observed day after midnight.

This can answer whether the two candidate sets agree at that checkpoint and
whether key/link anomalies need investigation. It cannot resolve the whole gate
by itself, explain the 118 prior missing matches through alternate storage, or
authorize a FULL reader. If the check is clean, the next decision is source
membership/save consistency, not automatic publishing. Receiver transport remains
design-only; never use `/api/v1/order-snapshots` for normalized-source payloads.

## Approved Observation: 2026-10-06

The operator said `go` to the explicit next step of running this reviewed read-only
check once for the current clinic day. The sender was clean at
`bf71a4879d49686df3407a23064e8ac699fa291c`. Host and UTC clock checks confirmed
that the current KST date was still `2026-10-06`, the date already confirmed by the
operator for the earlier membership comparison. All **118 mocked preflight tests
passed again in 1.22 s** before source access.

At **20:52:15 KST**, the unchanged hash-pinned statement ran exactly once through
the shared FIFO and machine-wide Windows mutex. The local connection setting was
read in memory using SQLite `mode=ro`; its cursor and physical connection were
closed and their closed state checked before source access. No credential or
other local setting was output. The source report was `order_counts_observed`,
with `review_required=[]` and `authoritative_snapshot=false`.

| Aggregate | Observed count |
| --- | ---: |
| Server current-day match | 1 |
| Candidate receptions | 267 |
| Receptions with any linked child | 145 |
| Receptions without a matching child | 122 |
| Null/blank reception keys | 0 |
| Duplicate reception-key groups | 0 |
| All linked order rows | 938 |
| Orders dated today | 938 |
| Linked orders dated today | 938 |
| Linked orders dated outside today or null | 0 |
| Today-dated orders with a current-day reception | 938 |
| Today-dated orders without a current-day reception | 0 |
| Linked rows with null/blank key components | 0 |
| Today-dated rows with null/blank key components | 0 |
| Duplicate four-part-key groups in linked rows | 0 |
| Duplicate four-part-key groups in today-dated rows | 0 |
| Linked three-part groups spanning multiple order dates | 0 |

| Session/cleanup evidence | Result |
| --- | --- |
| Local settings connection closed before source | true |
| Source connection opened | true |
| Read-only mode, finite timeout and isolation verified | true |
| Source cursor closed | true |
| Physical source connection closed before interpretation/output | true |
| Connection work | 0.0731 s |

The linked and today-dated sets have matching cardinalities and no unmatched-date,
null/blank-key or duplicate-key anomalies in this one statement. No source or
output cap was reached. The reception/child-presence totals also match the earlier
membership observation, but those separate operations are not one atomic snapshot.
This query did not reread reception states, qualifiers, categories or UI counts.

The 122 count still means only no matching child in `h2opd_doct_ord`. It does not
establish no orders elsewhere, explain the earlier 118 code-40/N missing matches,
or justify dropping no-order encounters. No active/cancelled meaning was inferred
for any child. The observed four-part keys are unique at this checkpoint, not
proved immutable across deletion/reuse or complete across other storage.

This completes the bounded key/link comparison, not the whole child-coverage
gate. Alternate storage, save consistency, authoritative membership/empty days,
retained-state combinations, category lifecycles, demographics/age policy and
least-privilege permissions remain unresolved. No second source statement, retry, source
row export, UI action, dummy modification, production reader, delivery, PACS
change, service restart or deployment was performed.

## Verification

- New probe: **118 mocked tests passed in 1.41 s**.
- Focused source/shadow/serialization/outbox/shared-reader, PACS, flu-report and
  patient-context regressions: **1,701 passed in 43.71 s**.
- The synthetic aggregate oracle is not a SQL engine. Initial preparation used
  static hash-pinned SQL review only; the single later PostgreSQL observation
  and its limited connection timing are recorded above, not a performance guarantee.
- Full isolated suite: **3,577 passed, 26 failed in 178.09 s**. The failures match
  the preceding [baseline record](kaoseghis-current-day-counts-proposal.md#verification):
  20 label-area/font-size cases at 203 dpi, three title-font cases, one pill-ink
  case and two shortcut-row width cases. No assertions were weakened and no
  unrelated vaccine change was made. The full suite is not green.
- Tests used mocked DB connections, isolated test mutexes, blocked external
  networking, offscreen Qt, disabled pytest plugin autoload and temporary local
  data. Those test runs obtained no live connection timing or source findings;
  the separate approved observation above did.
- `git diff --check` passed. Application code and all four existing v1/v2 JSON
  fixture bytes remain unchanged from the starting commit.
- Application source, v1/v2 fixtures/hashes, runtime settings, triggers, publishing,
  receiver, PACS and flu report remain unchanged. No production reader is enabled.
- The observation follow-up changes only this document and two evidence-summary
  links. Its preflight reran 118 tests; the focused/full results above are the
  immediately preceding preparation runs, not additional post-observation runs.
