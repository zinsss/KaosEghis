# Current-day volatile provider remaining gates

- **Status:** Phase 3A pure lifecycle model implemented; disabled runtime and all
  production gates remain pending
- **Last updated:** 2026-10-08
- **Owning project:** KaosEghis
- **Affected projects:** KaosEghis, KaosOrders, KaosReception, orchestration,
  clinic operations

## Context and accepted baseline

The selected architecture is one Eghis-owned, SQLite-free, volatile current-day
provider. Orchestration commit
`527776400d774abf40f0cf248e5bab60c0c77602` is the normative baseline for this
plan and supersedes the earlier `bd3c66a` planning baseline:

- `architecture/current-day-volatile-provider-v1.md` selects one authoritative
  owner and destination-minimal Orders and Reception projections;
- `contracts/eghis-current-day-provider-session-v1.md` accepts the common
  lifecycle/session rules and authorizes only a later pure, I/O-free lifecycle
  model plus synthetic tests;
- `contracts/kaosorders-current-day-orders-v1.md` retains every Orders
  fact-shape, source-evidence, wire/auth, runtime, scheduler, persistence, and
  deployment prohibition; and
- `contracts/reception-current-day-patients-v1.md` retains Reception's exact
  mapping, fail-closed behavior, and 300-second maximum age.

This document prepares Eghis-owned inputs for the remaining contracts and
evidence reviews. It does not select a production host, open a route, bind a
credential, schedule a source read, approve a production query, or authorize
deployment. Live or real patient/order facts must never enter this plan, logs,
fixtures, or handoff evidence; tests use synthetic values only.

## Current repository evidence and plan delta

The repository already contains three separate building blocks, none of which
is the common runtime provider:

1. `KaosEghis/core/kaosorders_current_day_orders.py` is a pure immutable Orders
   fact model/validator/comparator using synthetic data only.
2. `KaosEghis/core/reception_current_day_patients.py` is a pure Reception
   projection boundary, and `KaosEghis/core/reception_current_day_reader.py` is
   an unwired bounded parameterized reader adapter.
3. `KaosEghis/core/emr_read_queue.py` and `KaosEghis/core/eghis_db.py` provide
   the existing serialized-read and close-before-return boundary. The current
   macro scheduler is a persistent SQLite job system and is not suitable for
   this provider's no-persistence lifecycle.

The original project plans treated Orders and Reception as independent source
paths. The plan delta is to establish one owner lifecycle and one accepted source
observation per scheduled cycle, then derive two independently validated
projections. Existing readers remain unwired until the common source-observation
shape, topology, cadence, and destination contracts are separately accepted.

## Singleton owner and process topology inputs

The invariant is exact: one clinic/source scope has one active owner process,
one active generation, at most one in-flight source observation, and at most one
coalesced successor. A Python module global in multiple workers is forbidden.
Consumer requests never elect an owner and never start a source read.

### Option A — one in-process owner and serving process (preferred input)

- One supervised Eghis process owns the lifecycle, refresh coordinator,
  immutable snapshot reference, and destination handlers.
- Before creating a session/generation it acquires one machine-scoped singleton
  lease for the configured clinic/source scope. On Windows, the candidate is a
  restrictive named mutex owned for process lifetime. The exact name must be a
  non-secret hash of static scope identity, never a patient/source value.
- Failure to acquire the lease leaves the process unavailable and prevents source
  reads and serving. There is no standby takeover without a full new session,
  generation, and fresh complete observation.
- This minimizes internal IPC and split-brain surfaces, but the chosen process
  must be suitable for supervision and must not be multiplied by an HTTP worker
  count, UI restart pattern, or auto-reloader.

### Option B — one dedicated owner plus bounded authenticated local IPC

- One dedicated owner process alone holds the singleton lease, source boundary,
  and active snapshot. A separate serving process may read only destination-
  specific projections through an accepted local IPC contract.
- IPC must have bounded request/response sizes, deadlines, destination audience
  separation, OS ACLs, application authentication, no caching, and generation/
  sequence fencing. The serving process may not copy the internal superset or
  initiate source refreshes.
- Owner or IPC failure makes serving unavailable; no file, shared SQLite, replay,
  or stale recovery path is allowed.

Option B adds failure and credential surfaces and should be selected only if the
approved host/service topology cannot safely run Option A. Multi-owner active/
active, shared mutable memory across workers, consumer-owned polling, and a
shared database/file cache are rejected.

**Inputs still required:** operations must identify the approved non-production
and eventual production host/service manager; Orders and Reception must identify
whether they are same-host or cross-host consumers; orchestration must then accept
Option A or B and the exact singleton lease/supervision contract.

## Destination transport, authentication, and network inputs

No route or credential format is accepted here. The following alternatives are
inputs to separate destination contracts.

### Transport option 1 — bounded authenticated HTTP

- Separate versioned Orders and Reception routes, handlers, schemas, payload
  bounds, rate limits, and audience checks. The existing
  `/api/v1/order-snapshots` route is never reused.
- Loopback is not authentication. Same-host HTTP still requires destination-
  specific credentials and fail-closed audience validation.
- Cross-host HTTP requires TLS with server identity validation and, preferably,
  mutual TLS or a short-lived audience-bound token over TLS. Plain HTTP and
  bearer credentials over an unencrypted network are forbidden.
- Bind only to the accepted interface. Host firewall rules allow only the exact
  consumer hosts and destination port. No public wildcard exposure, discovery,
  proxy caching, or browser-facing access is allowed.

### Transport option 2 — bounded authenticated local IPC

- Available only when owner and consumer are on the same approved host.
- A Windows named pipe is the leading candidate; use a restrictive service ACL
  and separate logical or physical audience boundaries for Orders and Reception.
- OS identity/ACL checks are necessary but do not replace application-level
  destination authorization, version validation, size/deadline bounds, and
  fixed non-echoing errors.
- Remote pipe access, anonymous access, shared temp files, memory-mapped patient
  payloads, and durable queues are forbidden.

### Credential lifecycle inputs

- Orders and Reception receive distinct identities and audiences; no credential
  grants both projections by default.
- Provision credentials out of source control and application databases through
  an approved machine/service secret store. Configuration contains references,
  not secret values.
- Rotation must support a short, bounded overlap between old and new credential
  versions, record only non-secret version metadata, and complete without serving
  an unauthenticated fallback.
- Revocation must be independently possible per destination and take effect
  without source refresh or process restart if the selected mechanism supports
  it; otherwise the contract must define a bounded restart procedure.
- Missing, expired, revoked, wrong-audience, ambiguous, or unreadable credentials
  fail closed with no clinical response fields and no source read.

**Consumer decisions required:** Orders and Reception must each accept its route
or IPC name, request/response wire contract, media type, maximum bytes/rows,
polling behavior, credential type, audience, rollover behavior, fixed errors,
and cache controls. Operations must approve the bind/interface, service account,
secret store, certificate authority if applicable, firewall allowlist, and
rotation/revocation runbook.

## Refresh coordinator contract inputs

The central lifecycle invariants are already fixed: scheduled owner refresh,
single-flight execution, at most one coalesced successor, a monotonic local
ticket, close-before-normalize, final lifecycle fence, and atomic full
replacement. The proposed initial operating values below are **contract inputs,
not accepted runtime defaults**:

| Item | Proposed input | Required acceptance/evidence |
| --- | --- | --- |
| startup | One immediate cycle after singleton and source prerequisites are valid | Synthetic restart tests; no serving before success. |
| base cadence | 60 seconds from completion of the prior cycle | Orders accepts freshness; Reception confirms this stays within its 300-second ceiling; clinical-hours capacity evidence passes. |
| jitter | Stable process-local 0–5 seconds, never persisted | Operations confirms it cannot violate freshness; deterministic synthetic clock tests. |
| source deadline | 10 seconds for the whole queued observation, with stricter connection/statement bounds defined by the approved source reader | Orders source evidence and serialized-queue contention evidence must show the limit is safe. |
| retry | No retry inside a cycle; a failed cycle publishes nothing | Avoids hidden duplicate source load and keeps one observation per cycle. |
| failure backoff | Proposed next-cycle delays 60, 120, then at most 300 seconds while unavailable | Reception must confirm immediate fail-closed clearing; Orders must accept its stale policy; operations must accept recovery delay. |
| coalescing | While active, retain only one successor requirement | Synthetic concurrency tests prove no parallel connection or lost current-day rollover. |
| rollover | KST day change invalidates before read, rotates generation, and requests one immediate cycle | Injected-clock midnight/late-result tests. |
| shutdown | Stop admission/serving, cancel or bound the in-flight operation, prove cursor/connection closure, then drop references and lease | Source-runner cancellation/cleanup proof and supervised stop deadline. |

Consumer polling must not affect this cadence. A consumer may poll more frequently
only if its accepted rate limit permits; every poll remains a side-effect-free read
of the current immutable projection.

Provider health is a bounded non-clinical state, not a patient payload. Proposed
states are `STARTING`, `READY`, `DEGRADED`, `UNAVAILABLE`, `STOPPING`; exact wire
encoding is deferred. `READY` requires a current-day accepted observation and an
independently servable destination projection. Any wrong day, failed lifecycle
fence, stale-by-destination result, auth/configuration failure, or uncertain source
cleanup is not ready. Health must not expose raw source errors, SQL, identifiers,
names, facts, credentials, or content digests.

## One common source observation: mapping and evidence gates

The owner needs one bounded source observation capable of independently producing
the two accepted logical projections. The current Reception query and the Orders
diagnostic/model are not yet that common observation. Before implementation,
orchestration must accept one of these source shapes:

1. **Preferred input:** one parameterized read-only statement/snapshot returning
   a bounded internal superset of current-day encounter, permitted patient-name,
   and order facts, plus closed metadata/count proofs. It is detached, closed,
   validated, and discarded after projection construction.
2. **Alternative needing an explicit central clarification:** multiple bounded
   statements within one read-only transaction/snapshot treated as one observation.
   This is acceptable only if snapshot consistency, cleanup, total deadlines,
   counts, and all-or-nothing failure are proven and the central contract defines
   it as one observation. Independent queries at different snapshots are not one
   common observation.

The common reader must use the existing serialized-read/physical-close boundary.
It must never share its internal superset, connection, cursor, SQL error, or raw
row container with either consumer.

### Reception evidence ledger

Already accepted at the logical/unwired level:

- current `Asia/Seoul` day from `h1opdin.clinic_ymd`;
- exact included `proc_gb` values `30` and `40`, with unknown/null/blank excluded;
- encounter identity from `recept_no`;
- exact-one patient-master join and display-only name;
- 10,000-entry synthetic ceiling, duplicate rules, closed META proof, fixed
  errors, and 300-second freshness maximum.

Still required before production use:

- approved non-PHI PostgreSQL plan/types/index and SELECT-privilege evidence;
- complete-day authority, exact-one join cardinality, verified-empty proof, and
  source-domain evidence on the intended reader identity;
- clinical-hours capacity/latency/queue impact and cleanup/timeout evidence;
- confirmation that the common superset preserves Reception's narrower privacy
  and row/byte bounds and cannot expose chart number or order fields to Reception.

### Orders evidence ledger

The immutable parent/child fact shape is accepted, but production mapping remains
unassigned. Required evidence includes:

- authoritative current-day parent membership including no-order encounters and
  verified cancelled-parent exclusion;
- exact parent state mapping for the five included logical states and strict
  `hold_yn`, including unknown/conflicting combinations;
- complete child relation, four-part key uniqueness/reuse, exact retained text
  fields, `dc_yn`/`act_yn`, explicit child cancellation, disappearance, and
  restoration across all categories;
- one complete snapshot/transaction authority, verified-empty semantics, and
  no partial/truncated replacement;
- approved mapping revision, source/projection identity, maximum source/result
  rows and bytes, latency, query plan, privileges, and clinical-hours load;
- an Orders-owned decision for freshness/stale serving and destination payload
  bounds before a provider serializer or handler exists.

No numeric display-field proposal, legacy normalized source, diagnostic outbox,
or current `/api/v1/order-snapshots` behavior becomes part of this provider unless
a later accepted Orders contract explicitly adds it.

### Evidence procedure and acceptance

1. Freeze candidate SQL, parameters, selected columns, metadata proofs, row/byte/
   time ceilings, and fixed output allowlist in synthetic fixtures first.
2. Prove parameterization, SQL-injection separation, complete-day and zero-row
   META semantics, duplicate/conflict rules, join cardinality, overflow, timeout,
   cancellation, cursor/connection close, and no clinical echo using synthetic
   SQLite/mocked PostgreSQL only.
3. Obtain separately governed, non-PHI DBA/vendor or approved non-production
   evidence for types, indexes/plans, privileges, source domains, and cardinality.
4. If a production shadow is ever proposed, it requires a new explicit approval
   and a redacted aggregate-only protocol. This phase does not authorize it.
5. Ratify mapping revisions and verified-empty authority centrally before any
   runtime coordinator imports the readers.

Capacity acceptance must cover the source ceiling plus one sentinel, complete
detached-result byte bounds, peak immutable old+candidate+projection memory during
atomic swap, serialized queue wait, connection/setup/execute/fetch/cleanup/validate
timings, and repeated clinical-hours impact. One prior bounded observation is useful
evidence but is not a production capacity guarantee.

## Operations, privacy, and rollback inputs

### Monitoring

Allow only lifecycle state, destination readiness booleans, bounded row counts,
queue/read/close/validation durations, sequence/generation change counters, fixed
reason categories, and process-resource aggregates. Never log payloads, source rows,
SQL, raw exceptions, credentials, request headers, identifiers, names, demographics,
clinical text, digests, or URLs containing facts. Metrics labels must be closed and
low-cardinality.

### Shutdown and memory pressure

- Stop scheduling and request admission before source cancellation/closure.
- Keep the singleton lease until serving is stopped and in-flight cleanup is
  confirmed; then discard source and projection references.
- Reject a candidate before swap when its measured row/byte/memory bounds exceed
  the accepted ceiling. Never truncate, partially publish, or invoke persistence.
- Define a fail-fast supervised restart threshold for sustained memory pressure;
  restart begins unavailable and requires a new session/generation and fresh read.
- Garbage collection/object release is not secure erasure and must not be described
  as such.

### Dumps, swap, hibernation, and caches

Deployment review must disable or tightly govern user/system crash dumps for the
provider, restrict debugger rights, decide whether encrypted swap/pagefile and
hibernation satisfy clinic policy, and prohibit response/proxy/browser/service-worker
caches. Every future HTTP response is `Cache-Control: no-store`; exact wire headers
remain destination-contract work.

### Rollback

The rollback unit is runtime activation, not data migration: stop destination
admission, stop refresh, close the source boundary, drop volatile references,
release the singleton lease, disable the provider service/feature gate, and return
consumers to their accepted unavailable/manual-safe behavior. There is no patient
database, replay, schema migration, or cache to restore. Rollback must not reactivate
the legacy Orders snapshot route for these projections.

## Phase 3A pure lifecycle implementation

`KaosEghis/core/current_day_provider_lifecycle.py` implements the first code slice
authorized by orchestration `5277764`. It is deliberately I/O-free and has no
source reader, SQL, transaction, serializer/parser, HTTP/auth, socket, OS mutex,
thread/timer, settings, persistence, UI, runtime mount, or deployment import.

The settled implementation decisions are:

- all provider, cursor, ticket, destination, observation, lease-claim, and snapshot
  records are frozen/redacted values;
- `OpaqueIdentity` supports equality/hash only and defines no magnitude or order;
- every transition returns a new `ProviderState`; publishing creates one complete
  `ProviderSnapshot` and changes the caller's state reference once, so existing
  readers retain the complete old immutable reference while later readers receive
  the complete new one;
- startup is empty/`STARTING`; KST rollover clears first and retires the old pair;
  lease loss and shutdown clear serving and in-flight references fail closed;
- one injected refresh ticket captures session, generation, day, lease token, and
  exact 10-second deadline; one active cycle admits only one coalesced successor;
- ordinary completion schedules 60 seconds plus the injected stable 0–5-second
  jitter; failures use 60/120/300 seconds plus jitter, cap at 300, never retry
  inside the cycle, and success resets the failure count;
- final publication checks lease, session, generation, clinic day, active ticket,
  and deadline; late/restart/rollover/lease-loss results cannot publish;
- each accepted observation advances one common sequence while Orders and Reception
  may independently be available, verified empty, or unavailable; a failed source
  cycle retains the prior internal immutable reference but has no replacement
  authority; and
- health/reason values are a closed nonclinical vocabulary with fixed exceptions
  and redacted representations.

The lease is only an injected immutable claim. This slice does not acquire a named
mutex, elect a process, schedule work, or provide a runtime singleton. Destination
states contain only synthetic item counts and integer content markers; no patient-
or order-shaped fixture is required.

### Phase 3A validation evidence

- The normal focused pytest command reached repository `tests/conftest.py` but all
  21 then-defined cases failed in setup because the unrelated PySide6 PACS fixture
  could not load host `libxkbcommon.so.0`; no lifecycle assertion ran in that pass.
- Following the approved pure-model verification procedure, the final focused
  suite passed **23 tests** with `--noconftest`, plugin autoload disabled, and
  bytecode disabled.
- Adjacent pure Orders facts, Reception projection, and bounded Reception reader
  regressions passed **293 tests** under the same isolated mode.
- The documented full baseline collected 4,615 tests but stopped with 12 GUI-module
  collection errors for the same missing host `libxkbcommon.so.0`; this is an
  environment blocker, not a lifecycle assertion failure.
- Tests cover literal constants, equality-only IDs, startup, deadline, stable
  jitter, single-flight/coalescing, success and failure schedules, backoff cap/reset,
  KST rollover, restart/day/ticket/lease fences, A-B-A rejection, verified empty,
  destination failure isolation, sequence retry/conflict/regression, immutable
  old-or-new replacement, shutdown, fixed errors, redacted representations, and a
  standard-library-only AST boundary.

The isolated results are focused verification, not a complete repository baseline.
The full baseline remains blocked by the existing host GUI-library dependency.

## Safe implementation sequence

1. Independent review of the provider contract inputs: completed through central
   baseline `5277764`.
2. Implement the pure, I/O-free lifecycle state model and synthetic matrix:
   completed in Phase 3A; independent code review pending.
3. Consumers and orchestration settle the unresolved decisions listed below and
   accept separate destination wire/auth contracts.
4. Freeze and synthetically verify the common source-observation contract; obtain
   approved non-PHI source evidence and central mapping revisions.
5. Implement a disabled coordinator and source adapter behind injected boundaries;
   test single-flight, deadlines, cleanup, rollover, atomicity, and memory bounds.
6. Implement disabled destination projections/handlers and consumer parsers with
   synthetic contract/integration tests and auth-denial/cache tests.
7. Prepare a deployment proposal covering service topology, singleton enforcement,
   secret/certificate operations, firewall, monitoring, dumps/swap, rollback, and
   Reception spool. Deployment still requires separate explicit approval.

No phase may infer acceptance of a later phase. In particular, successful synthetic
tests do not approve a source mapping, and an accepted mapping does not authorize a
route or deployment.

## Explicit unresolved decisions and owners

| Decision | Required owner/input |
| --- | --- |
| Option A in-process owner or Option B dedicated owner/local IPC | Eghis + operations + orchestration, after exact host/process inventory |
| same-host IPC versus HTTP and any cross-host boundary | Orders, Reception, operations, orchestration |
| exact routes/IPC names, media types, schemas, byte/row bounds, status/errors | Separate Orders and Reception contracts |
| credential type, audiences, provisioning store, rotation overlap, revocation | Security/operations plus each consumer |
| TLS CA/server identity, bind address, port, firewall allowlist | Security/operations; mandatory before cross-host activation |
| 60-second cadence, 10-second total deadline, proposed backoff, rate limits | Eghis, Orders, Reception, operations after capacity evidence |
| Orders freshness/stale policy and verified-empty authority | Orders + orchestration |
| common one-statement versus one-transaction observation | Eghis + orchestration after synthetic/source evidence |
| Orders source mapping and revision | Eghis evidence + Orders acceptance + orchestration |
| Reception production evidence and common-reader privacy proof | Eghis evidence + Reception acceptance + orchestration |
| service supervision, health wiring, memory ceiling, dump/swap/hibernation controls, rollback | Operations + security + orchestration |
| runtime activation and deployment | Explicit user approval after all reviews |

## Evidence completed in this phase

- Read-only repository and central-contract inspection only.
- No source/service/network connection, credential discovery, runtime import,
  route binding, scheduler activation, patient/order fixture, or deployment.
- The plan preserves all accepted lifecycle/session and destination logical
  contracts and names every remaining contract/evidence owner.

## Next action

Independent integration review should compare the Phase 3A model/tests with
orchestration `5277764` and verify the pure boundary, transition invariants, and
isolated test evidence. Only after that review may Eghis begin the separately
sequenced disabled coordinator/source-boundary slice using injected synthetic
observations. SQL/source access, HTTP serialization/handlers/auth, sockets, runtime
mounting, persistence, activation, and deployment remain outside this slice.

## Revision history

- **2026-10-08:** Created the provider-owned remaining-gates plan, reconciled it
  with orchestration `bd3c66a`, recorded topology/transport/auth/refresh inputs,
  separated Orders and Reception source-evidence ledgers, and preserved all
  runtime, live-source, credential, push, and deployment gates.
- **2026-10-08:** Implemented the Phase 3A pure immutable lifecycle/scheduling/
  atomic-publication model and synthetic test matrix; recorded the normal pytest
  GUI-library setup blocker and isolated focused/adjacent verification. Retained all
  source, transport, credential, socket, runtime, persistence, and deployment gates.
