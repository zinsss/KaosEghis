# Current-Day Membership Count Proposal

Prepared: 2026-10-06, from sender `b1a0ad53dc625ed270b8a5f8cadab475baeebe02`.

Status: **one aggregate observation completed; production authority unresolved**.
This is a bounded candidate-membership check for source gate 1, not a production
reader, normalized snapshot, clinical state mapping or approval to publish. The
initial `ok` authorized preparation only. The later observation below used the
operator's standing bounded read-only authorization, after passive screen reading
and explicit confirmation that the displayed tab counts were for today.

## Question And Limits

For the current KST date, how many candidate reception records have any linked
order, and how many have none, grouped by allowlisted `proc_gb` and `hold_yn`?
The future Orders scope includes non-cancelled visits with no orders and excludes
cancelled visits. This inspection retains all state buckets as counts so the
operator can compare them against EMR list totals before any filter is approved.

Earlier supervised observations associated code 50 with cancelled reception.
This proposal does not turn that observation into a universal cancellation rule,
combine it with guessed qualifier meanings, or label every other code included.
Unknown/null/blank states remain visible as fixed count buckets, never silently
excluded. No production state policy changes.

`WITH_ORDERS` means any linked child record exists, including cancelled child rows,
fees and unknown categories. It does not mean an active, billable, completed or
clinically relevant order. `WITHOUT_ORDERS` means no child in the candidate table
matched the existing reception link. It is not proof that no orders exist anywhere.
The query starts from receptions, not an inner join to orders; multiple children
cannot multiply reception counts. The link's wider uniqueness/reuse domain and
complete source coverage remain unverified.

One successful observation may verify these candidate buckets against a known UI
checkpoint. It cannot prove authoritative full-day membership, clinic partitioning,
child completeness, a complete state/qualifier truth table, or save atomicity.
No gate is resolved merely by matching counts. Prior dummy state transitions need
not be repeated just to collect more examples. No dummy change is part of this run.

## Exact Statement And Inputs

Complete parameterized SQL:
[source_current_day_counts_v1.sql](../tests/fixtures/source_current_day_counts_v1.sql).

SHA-256 of UTF-8 statement text with LF newlines:
`6f510ed7ca47f9c01c1f692b7b92fee52c3dbcceca0e4b693c8cb0bf832069c8`.
The test-only harness pins this hash and refuses changed SQL pending review.

| Source | Every selected or referenced column | Purpose |
| --- | --- | --- |
| `public.h1opdin` | `clinic_ymd` | Bound current-day predicate |
| `public.h1opdin` | `recept_no` | Internal existence link, null/blank and duplicate-key checks; never returned |
| `public.h1opdin` | `proc_gb`, `hold_yn` | Server-side allowlisted code/flag buckets |
| `public.h2opd_doct_ord` | `recept_no` | Internal `EXISTS` link only; no order row/key returned |

Fixed parameters:

- `day`: operator-reviewed current KST date formatted `YYYYMMDD`; no historical date.
- `encounter_limit`: `10001` (10,000 cap plus one sentinel).
- `codes`: exact strings `10`, `20`, `25`, `30`, `40`, `50`.
- `flags`: exact strings `Y`, `N`.

The injected trusted aware clock checks today's KST date before queue submission,
after verified closure, and after aggregate validation. The SQL also checks the
server's current KST date inside the single autocommit statement and gates the
reception selection, so a queued request crossing midnight cannot return a prior
day as successful. A server/client date mismatch or rollover rejects findings.
This is a date guard, not an EMR-save completion marker.

The SQL uses the PostgreSQL 9.2 documented transaction timestamp/time-zone
conversion and existential subquery semantics. In verified autocommit mode the
source statement has its own transaction timestamp. These references support SQL
semantics only, not the clinic's source authority:
[date/time functions](https://www.postgresql.org/docs/9.2/functions-datetime.html),
[EXISTS](https://www.postgresql.org/docs/9.2/functions-subquery.html).

There is no patient-master join, excluded `hold_opd` access, age/DOB derivation,
demographic field, clinical note, insurance, source definition or credential output.
No order date/type/department or cancellation flag is used as a selection filter.

## Aggregate Output Allowlist

SQL returns only five columns: `section`, `code`, `hold`, `presence`, `n`.

- Summary metric names: `current_day_matches`, `encounters`,
  `invalid_encounter_keys`, `duplicate_encounter_keys`.
- Bucket code: one of the six exact codes above, `NULL`, `BLANK`, `UNREVIEWED`.
- Bucket retained flag: `Y`, `N`, `NULL`, `BLANK`, `UNREVIEWED`.
- Order presence: `WITH_ORDERS` or `WITHOUT_ORDERS`.
- Strict bounded integer counts; no source identifiers or unallowlisted strings.

After physical closure, the harness validates required summaries, unique bucket
keys, count totals and source caps. Invalid/duplicate reception keys reject the
entire report. It returns total/with-order/without-order counts and sorted buckets.
Unknown values are masked on the server; their underlying text is never returned.

Other report fields are fixed redacted status codes, `authoritative_snapshot=false`,
four closure/session booleans and bounded connection-work seconds. No identifiers,
payloads, SQL/provider error text or credentials enter reports or logs. The harness
does not print, log, persist or deliver reports. Even a valid zero count is only an
observation, never authority for an empty FULL snapshot or board removal.

## Bounds And Cleanup

- Use the existing `run_verified_evidence_query`, FIFO worker and machine-wide
  `Global\KaosEghis-EMR-read` mutex. No direct driver, new connection or mutex path.
- Connect timeout: 3 seconds. Statement timeout: 2 seconds. Verify read-only mode,
  `2s` timeout and READ COMMITTED before the source statement. Never try a write.
- One source statement, no retry, polling loop, timeout increase or permission bypass.
- Reception cap 10,000 plus sentinel. At most 90 code/flag/presence buckets plus
  four summaries: report cap 94, SQL sentinel limit 95. The shared reader fetches
  at most 257; the tighter 94 bound is checked before accepting a report.
- Child existence is bounded to one boolean per scoped reception, not a child-row
  export/count. Underlying search work may still scan many rows; indexes/performance
  are not assumed. The 2-second statement timeout bounds that work. A timeout stops
  this operation; it is not grounds to broaden the query.
- Cursor and physical connection must both close and be verified before aggregate
  interpretation/output. Uncertain physical closure poisons the shared reader and
  blocks further reads; no connection pooling or automatic recovery.
- Missing, malformed, partial, inconsistent, overflowed, denied, timed-out,
  cleanup-unverified and wrong-day reports have no findings and are never empty
  snapshots. One statement gives one database snapshot, not proof of an atomic EMR
  save across potentially separate commits.

## Checkpoint Procedure

Use **this one reviewed statement**, once, on the operator-confirmed current KST
date under bounded read-only authorization. Obtain the current-day EMR tab counts
by passive screen reading or operator report. Hidden tabs and each tab's date/filter
remain comparison limitations until verified. No names, screenshots with patient
details, or patient/order identifiers are needed. Do not infer an empty day from a
holiday or the old dummy; no date-moving source experiment is authorized.

If no comparable current-day UI checkpoint is available, defer the live operation.
Any normal dummy cancellation/restoration comparison is a later separately reviewed
checkpoint performed by the operator, not an automatic action in this proposal.
Only sanitized aggregates, closure evidence and limitations may later be recorded.

## Observed Checkpoint: 2026-10-06

The operator requested screen reading rather than manually transcribing counts.
A narrow reception-tab screenshot showed completed **263** and cancelled **4**.
Waiting was selected; waiting and hold had no displayed numeric counts. The date
was not readable through the passive controls, so the operator explicitly confirmed
these were today's counts. No zero was inferred from a missing tab count. Hidden
tabs were not exposed or switched. No patient rows were read or captured.

At **19:17:36 KST**, the pinned statement ran once for `2026-10-06`, after its
106 mocked tests passed again in **1.23 s**. The local connection setting was read
in memory from SQLite opened with `mode=ro`; that local cursor and connection
closed before the shared EMR reader was called. No credential was output.

| Observed aggregate bucket | Linked child rows present | No linked child rows | Total |
| --- | --- | --- | --- |
| `proc_gb=40`, `hold_yn=N` | 145 | 118 | 263 |
| `proc_gb=50`, `hold_yn=N` | 0 | 4 | 4 |
| Total candidate receptions | 145 | 122 | 267 |

Only these code/retained-flag combinations occurred in this statement. The accepted
report passed the current-day, source-cap, unique/valid reception-key and aggregate
sum checks. It is `counts_observed` with `authoritative_snapshot=false`.

| Read/cleanup evidence | Result |
| --- | --- |
| Local settings connection closed before source access | true |
| EMR connection opened | true |
| Read-only session/finite timeout verified | true |
| Cursor closed | true |
| Physical connection closed before interpretation/output | true |
| Connection work | 0.0733 s |

The source buckets match the two visible tab totals, consistent with the earlier
supervised 40/50 associations for this observed retained-flag combination. Applying
the requested scope to this sample would retain 263 candidate encounters and omit
the four cancelled candidates; requiring child presence would incorrectly omit
118 of the 263 candidates as well. This is evidence that the reception side must
drive membership, not an approved production cancellation filter.

Crucially, the 118 count means **no matching child in the inspected order table**,
not proof of no clinical orders elsewhere. Alternate order storage, the complete
child relation, global identity/reuse and EMR save consistency were not investigated
by this statement. UI and DB observations are not one atomic snapshot. The absence
of other source buckets does not prove hidden UI tab counts or all state mappings.
No full gate is closed, no empty-day authority established, and no runtime reader
enabled. No second query, retry, date-moving test or dummy transition was performed.

## Verification

- New mocked probe tests: **106 passed in 1.26 s**. Shared driver is mocked, external network
  and native input are blocked, and tests use an isolated FIFO and test-only mutex.
- Focused source/proposal/v1/v2/serialization/FIFO regression group:
  **1,230 passed in 5.57 s**.
- Full isolated suite, including PACS, flu-report and patient-context groups:
  **3,459 passed, 26 failed in 180.30 s**. Failures are the previously documented
  24 vaccine label font/ink cases and two shortcut-row width cases, not new source
  failures. See the earlier [baseline verification record](kaoseghis-source-metadata-followup.md#verification).
  Those unrelated failures are not fixed; the full suite is not green.
- `git diff --check` passed. Application code and all four existing v1/v2 canonical
  JSON fixtures remain unchanged from the starting commit.
- Initial preparation had no live operations. The later single observation and
  verified closure are recorded above; only sanitized aggregate evidence is saved.
  No EMR input, record write, application restart, publishing or deployment occurred.
- `EghisSourceDayReader` remains UNAVAILABLE. No application imports the proposal.
  Existing v1/v2 fixtures/hashes, PACS, receiver, settings, triggers, transport,
  endpoints and runtime behavior are unchanged. All source-evidence gates remain
  unresolved. Never send normalized facts to `/api/v1/order-snapshots`.
