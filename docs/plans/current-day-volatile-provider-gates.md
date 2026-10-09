# Current-day volatile provider remaining gates

- **Status:** Phase 3A pure lifecycle reviewed; Phase 3B synthetic Orders serializer
  and disabled in-process handler implemented; independent handoff review pending;
  source, runtime activation, and all production gates remain pending
- **Last updated:** 2026-10-09
- **Owning project:** KaosEghis
- **Affected projects:** KaosEghis, KaosOrders, KaosReception, orchestration,
  clinic operations

## Context and accepted baseline

The selected architecture is one Eghis-owned, SQLite-free, volatile current-day
provider. Orchestration commit
`5dd9e23` is the normative baseline for this plan. It retains the lifecycle/runtime
decisions accepted at `5277764`, the destination-token hardening accepted at
`9288070`, and supersedes the earlier `bd3c66a` planning baseline:

- `architecture/current-day-volatile-provider-v1.md` selects one authoritative
  owner and destination-minimal Orders and Reception projections;
- `contracts/eghis-current-day-provider-session-v1.md` accepts the common
  lifecycle/session rules and authorizes only a later pure, I/O-free lifecycle
  model plus synthetic tests;
- `contracts/eghis-current-day-provider-runtime-v1.md`,
  `contracts/kaosorders-current-day-orders-wire-v1.md`, and
  `contracts/reception-current-day-patients-wire-v1.md` accept the Option A H4
  owner/runtime baseline and separate destination wire/auth boundaries;
- `contracts/kaosorders-current-day-orders-v1.md` keeps the logical fact shape
  and production source-evidence gates separate while authorizing only disabled,
  injected synthetic wire components under the later accepted contracts; and
- `contracts/reception-current-day-patients-v1.md` retains Reception's exact
  mapping, fail-closed behavior, and 300-second maximum age.

This document prepares Eghis-owned inputs for the remaining contracts and
evidence reviews. It does not select a production host, open a route, bind a
credential, schedule a source read, approve a production query, or authorize
deployment. Live or real patient/order facts must never enter this plan, logs,
fixtures, or handoff evidence; tests use synthetic values only.

## Current repository evidence and plan delta

The repository contains four separate building blocks, none of which is a mounted
or active common runtime provider:

1. `KaosEghis/core/kaosorders_current_day_orders.py` is a pure immutable Orders
   fact model/validator/comparator using synthetic data only.
2. `KaosEghis/core/reception_current_day_patients.py` is a pure Reception
   projection boundary, and `KaosEghis/core/reception_current_day_reader.py` is
   an unwired bounded parameterized reader adapter.
3. `KaosEghis/core/emr_read_queue.py` and `KaosEghis/core/eghis_db.py` provide
   the existing serialized-read and close-before-return boundary. The current
   macro scheduler is a persistent SQLite job system and is not suitable for
   this provider's no-persistence lifecycle.
4. `KaosEghis/core/kaosorders_current_day_wire.py` is the Phase 3B pure,
   synthetic-only Orders serializer and exact in-process handler. It imports only
   the reviewed pure lifecycle/fact boundaries and standard-library helpers; no
   runtime module imports it.

The original project plans treated Orders and Reception as independent source
paths. The plan delta is to establish one owner lifecycle and one accepted source
observation per scheduled cycle, then derive two independently validated
projections. Existing readers remain unwired until production source mapping,
capacity/cleanup evidence, and concrete deployment inputs are separately accepted.

## Accepted singleton owner and process topology

The invariant is exact: one clinic/source scope has one active owner process,
one active generation, at most one in-flight source observation, and at most one
coalesced successor. A Python module global in multiple workers is forbidden.
Consumer requests never elect an owner and never start a source read.

### Option A — one in-process owner and serving process (accepted H4 baseline)

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

### Later topology changes

Orchestration `9288070` accepts Option A for the H4 implementation baseline. A
dedicated owner plus local IPC, multiple workers, or any other topology is not an
implementation alternative in this phase and would require a new reviewed central
contract. Multi-owner active/active, shared mutable memory across workers,
consumer-owned polling, and a shared database/file cache remain rejected.

**Deployment inputs still required:** operations must identify the approved
non-production and eventual production host/service manager, the exact singleton
lease implementation and supervision settings, and whether each consumer crosses
a host boundary. These concrete values do not reopen the accepted Option A design.

## Accepted destination transport and authentication boundary

Orchestration `9288070` accepts separate Orders and Reception wire contracts and
a bounded HTTPS-style HTTP destination boundary. It also accepts distinct
destination bearer identities/audiences, fail-closed authentication, TLS server
verification, no plaintext fallback, no TLS 1.3 early data, and the rule that
loopback is not authentication. Synthetic in-process handler tests may avoid a
socket and real credential, but that does not weaken the production boundary.

### Bounded authenticated HTTP

- Separate versioned Orders and Reception routes, handlers, schemas, payload
  bounds, rate limits, and audience checks. The existing
  `/api/v1/order-snapshots` route is never reused.
- Loopback is not authentication. Same-host HTTP still requires destination-
  specific credentials and fail-closed audience validation.
- Cross-host HTTP requires TLS with server identity validation and the accepted
  destination-specific bearer identity. Plain HTTP and bearer credentials over
  an unencrypted network are forbidden.
- Bind only to the accepted interface. Host firewall rules allow only the exact
  consumer hosts and destination port. No public wildcard exposure, discovery,
  proxy caching, or browser-facing access is allowed.

### Credential lifecycle

- Orders and Reception each receive a separate opaque bearer token with a distinct
  identity and audience. Each token is independently generated by a CSPRNG with at
  least 256 bits of entropy. Sharing or deriving one destination token from the
  other is forbidden; no credential grants both projections.
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

The destination routes, media types, closed envelopes, lifecycle cursors, bounds,
headers, freshness/readiness, polling, audiences, and auth-failure semantics are
settled by the separate accepted central wire contracts. Concrete production
bearer provisioning/store references, certificate authority and server identity,
bind/interface/port, service accounts, firewall allowlist, and rotation/revocation
runbook remain deployment inputs and must not be guessed in code or documentation.

## Accepted refresh coordinator contract

The central lifecycle invariants are already fixed: scheduled owner refresh,
single-flight execution, at most one coalesced successor, a monotonic local
ticket, close-before-normalize, final lifecycle fence, and atomic full
replacement. Orchestration `9288070` accepts these H4 values:

| Item | Accepted H4 value | Remaining implementation/evidence |
| --- | --- | --- |
| startup | One immediate cycle after singleton and source prerequisites are valid | Synthetic restart tests; no serving before success. |
| base cadence | 60 seconds from completion of the prior cycle | Clinical-hours capacity evidence passes. |
| jitter | Stable process-local 0–5 seconds, never persisted | Deterministic synthetic clock tests. |
| source deadline | 10 seconds for the whole queued observation, with stricter connection/statement bounds defined by the approved source reader | Orders source evidence and serialized-queue contention evidence must show the limit is safe. |
| retry | No retry inside a cycle; a failed cycle publishes nothing | Avoids hidden duplicate source load and keeps one observation per cycle. |
| failure backoff | Base next-cycle delays are 60, 120, and 300 seconds, plus stable process-local jitter of 0–5 seconds; the third and every later failure therefore schedules 300–305 seconds after completion | Synthetic base-delay cap/reset and jittered-total tests; destination freshness still independently gates serving. |
| coalescing | While active, retain only one successor requirement | Synthetic concurrency tests prove no parallel connection or lost current-day rollover. |
| rollover | KST day change invalidates before read, rotates generation, and requests one immediate cycle | Injected-clock midnight/late-result tests. |
| shutdown | Stop admission/serving, cancel or bound the in-flight operation, prove cursor/connection closure, then drop references and lease | Source-runner cancellation/cleanup proof and supervised stop deadline. |

Consumer polling must not affect this cadence. Accepted success polling is 10
seconds for Orders and 60 seconds for Reception; every poll remains a side-effect-
free read of the current immutable projection and destination freshness still
governs whether a retained internal observation can be served.

Provider health is a bounded non-clinical state, not a patient payload. The closed
states are `STARTING`, `READY`, `DEGRADED`, `UNAVAILABLE`, `STOPPING`; destination
wire encoding is settled in its accepted contract. `READY` requires a current-day
accepted observation with both destination projections independently servable;
one unavailable projection is `DEGRADED` and both unavailable is `UNAVAILABLE`.
Any wrong day, failed lifecycle
fence, stale-by-destination result, auth/configuration failure, or uncertain source
cleanup is not ready. Health must not expose raw source errors, SQL, identifiers,
names, facts, credentials, or content digests.

## One common source observation: mapping and evidence gates

The owner needs one bounded source observation capable of independently producing
the two accepted logical projections. The current Reception query and the Orders
diagnostic/model are not yet that common observation. Orchestration `9288070`
accepts either one bounded read-only statement or multiple bounded statements in
one read-only transaction/snapshot as one common observation. The latter must
prove snapshot consistency, all-or-nothing validation, total deadline/count
bounds, and cleanup; independent queries at different snapshots are forbidden.
Production SQL, mapping, privileges, and capacity evidence remain unaccepted.

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
- the already accepted Orders wire limits and freshness behavior remain synthetic
  implementation inputs only until the source mapping and production evidence are
  accepted.

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
caches. The synthetic Orders handler implements the accepted exact no-store headers;
deployment must still prove that HTTP/proxy layers preserve them and add no cache.

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
  lease loss clears references fail closed, while shutdown first stops admission
  and serving but retains the lease and in-flight cleanup responsibility, then
  releases references and lease only after explicit cleanup confirmation;
- one injected refresh ticket captures session, generation, day, lease token, and
  exact 10-second deadline; one active cycle admits only one coalesced successor;
- ordinary completion schedules 60 seconds plus the injected stable 0–5-second
  jitter; failures use base delays of 60/120/300 seconds plus that jitter, so the
  third and every later total is 300–305 seconds, never retry inside the cycle,
  and success resets the failure count;
- final publication checks lease, session, generation, clinic day, active ticket,
  and deadline; late/restart/rollover/lease-loss results cannot publish;
- ticket or sequence exhaustion never wraps: an explicit same-day transition
  retires the old pair, accepts one injected fresh generation identity, clears the
  snapshot and counters, and requires a complete fresh observation;
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
- During the single review remediation, the normal focused command again reached
  the autouse PySide6 fixture and produced **26 setup errors** for the same missing
  host library. The isolated lifecycle suite then passed **26 tests**, and the
  combined lifecycle plus adjacent pure Orders/Reception suites passed **319
  tests** (26 lifecycle and 293 adjacent).
- Tests cover literal constants, equality-only IDs, startup, deadline, stable
  jitter, single-flight/coalescing, success and failure schedules, base-delay
  cap/reset and jittered totals,
  KST rollover, restart/day/ticket/lease fences, A-B-A rejection, verified empty,
  destination failure isolation, sequence retry/conflict/regression, validated
  day/pair disposition scope, immutable old-or-new replacement, two-stage
  shutdown, ticket/sequence exhaustion rotation at the exact counter boundaries,
  closed phase/reason/destination/lease invariants, fixed errors, redacted
  representations, and a standard-library-only AST boundary.

The isolated results are focused verification, not a complete repository baseline.
The full baseline remains blocked by the existing host GUI-library dependency.

## Phase 3B synthetic Orders wire implementation

`KaosEghis/core/kaosorders_current_day_wire.py` implements only the synthetic,
injected, disabled Orders boundary authorized by orchestration `5dd9e23`. It is not
mounted or imported by application runtime code and contains no socket, HTTP server,
source reader, SQL, credential lookup, settings, scheduler, persistence, UI, or
deployment integration.

The implementation fixes these contract artifacts:

- exact `GET /api/v1/current-day/orders`, media types, closed success/error bodies,
  application-controlled no-store headers, 16 MiB body bound, and fixed status/code
  table;
- deterministic RFC 8785-compatible JSON for the contract's closed ASCII-key,
  integer/boolean/null/string-only schema, with literal populated and verified-empty
  canonical fixture bytes and SHA-256 digests;
- exact parent/child/qualifier/key projection from the reviewed immutable fact
  model, preserving nullable/blank child text and deterministic collection order;
- an invented synthetic Orders-only bearer identity and injected identity set with
  fixed/redacted failures for missing, malformed, expired, revoked, wrong-audience,
  wrong-projection, and wrong-source credentials;
- one immutable `SyntheticOrdersProjection` that binds the exact lifecycle snapshot
  reference and injected synthetic clinic/source/mapping scope to one complete fact
  set, clinic day, destination availability, and synthetic projected item count;
- startup, rollover, projection-reference, future-time, 300-second freshness,
  rate-limit, response-bound, verified-empty, and failure-envelope behavior; and
- an in-process request/response handoff only. Request handling does not schedule or
  trigger source work, bind a route, open a network connection, or read a secret.

The synthetic mapping label and bearer bytes are test artifacts. They are never a
production mapping revision or credential and cannot be promoted. The production
mapping remains unassigned, `EghisSourceDayReader` remains unavailable, and the
existing `/api/v1/order-snapshots` path is explicitly rejected rather than reused.

### Phase 3B validation evidence

- The normal focused command collected the 23 then-defined wire tests, but all 23
  stopped in autouse setup because importing the unrelated PySide6 PACS fixture
  failed on missing host `libxkbcommon.so.0`; no wire assertion ran in that pass.
- The final wire suite contains **24 tests** and passes with `--noconftest`, plugin
  autoload disabled, and bytecode disabled.
- The combined Phase 3B wire suite plus pure Orders facts, lifecycle, Reception
  projection, and bounded Reception reader regressions passes **343 tests** under
  the same isolated mode.
- Tests include literal contract assertions independent of implementation enums,
  literal fixture bytes/digests, independent SHA-256 checks, all closed error codes,
  request negotiation, auth/audience/revocation, exact headers, bounds, freshness,
  rollover, immutable snapshot identity, verified empty, redaction, and an AST
  boundary proving the module remains free of I/O/runtime imports and calls.

These isolated results are focused pure verification, not a full baseline. The
existing host GUI-library blocker remains unresolved and no system package was
installed or changed.

## Safe implementation sequence

1. Independent review of the provider contract inputs: completed through central
   baseline `9288070`.
2. Implement the pure, I/O-free lifecycle state model and synthetic matrix:
   completed and reviewed in Phase 3A.
3. Accept Option A, the common runtime/transport rules, and separate destination
   wire/auth contracts: completed through central baseline `9288070`.
4. Freeze and synthetically verify the common source-observation contract; obtain
   approved non-PHI source evidence and central mapping revisions.
5. Implement a disabled coordinator and source adapter behind injected boundaries;
   test single-flight, deadlines, cleanup, rollover, atomicity, and memory bounds.
6. Implement disabled destination projections/handlers and consumer parsers with
   synthetic contract/integration tests and auth-denial/cache tests. The Eghis
   Orders serializer/handler candidate is complete in Phase 3B; Orders parser/client
   work remains unauthorized until independent review accepts this handoff.
7. Prepare a deployment proposal covering service topology, singleton enforcement,
   secret/certificate operations, firewall, monitoring, dumps/swap, rollback, and
   Reception spool. Deployment still requires separate explicit approval.

No phase may infer acceptance of a later phase. In particular, successful synthetic
tests do not approve a source mapping, and an accepted mapping does not authorize a
route or deployment.

## Explicit unresolved decisions and owners

| Decision | Required owner/input |
| --- | --- |
| approved host/process/service-manager inventory for accepted Option A | Operations + orchestration |
| concrete bearer provisioning store, rotation overlap, and revocation runbook | Security/operations plus each consumer |
| TLS CA/server identity, bind address, port, firewall allowlist | Security/operations; mandatory before cross-host activation |
| Orders source mapping and revision | Eghis evidence + Orders acceptance + orchestration |
| Reception production evidence and common-reader privacy proof | Eghis evidence + Reception acceptance + orchestration |
| service supervision, health wiring, memory ceiling, dump/swap/hibernation controls, rollback | Operations + security + orchestration |
| runtime activation and deployment | Explicit user approval after all reviews |

## Evidence completed in this phase

- Synthetic-only pure serializer/handler implementation, tests, and contract
  inspection only.
- The new Orders bearer is an explicitly synthetic injected test identity with a
  redacted representation. It is not generated, loaded, stored, logged, mounted,
  or accepted by runtime configuration. The lifecycle `lease_token` remains an
  unrelated injected singleton-fence identity.
- No source/service/network connection, credential discovery, runtime import,
  route binding, scheduler activation, real patient/order fixture, or deployment.
- The plan preserves all accepted lifecycle/session and destination logical
  contracts and names every remaining contract/evidence owner.

## Next action

Independent integration review should compare the Phase 3B serializer/handler,
literal fixture bytes/digests, request/error/auth matrices, and isolated test
evidence with orchestration `5dd9e23`. Until that review passes, Orders receiver
implementation is **not yet authorized**. A PASS authorizes Orders only for its
accepted injected, disabled parser/client and volatile lifecycle/freshness tests;
it does not authorize FastAPI/runtime wiring, real credentials, network access,
board cutover, persistence, activation, or deployment.

The next Eghis runtime/source work remains separately sequenced. Production SQL,
source access, mapping assignment, socket/route mounting, credential lookup,
settings integration, persistence, activation, and deployment remain outside this
slice.

## Revision history

- **2026-10-08:** Created the provider-owned remaining-gates plan, reconciled it
  with orchestration `bd3c66a`, recorded topology/transport/auth/refresh inputs,
  separated Orders and Reception source-evidence ledgers, and preserved all
  runtime, live-source, credential, push, and deployment gates.
- **2026-10-08:** Implemented the Phase 3A pure immutable lifecycle/scheduling/
  atomic-publication model and synthetic test matrix; recorded the normal pytest
  GUI-library setup blocker and isolated focused/adjacent verification. Retained all
  source, transport, credential, socket, runtime, persistence, and deployment gates.
- **2026-10-08:** Remediated the independent review blockers with two-stage
  cleanup-confirmed shutdown, explicit non-wrapping same-day generation rotation,
  closed state invariants, and day/pair-scoped snapshot disposition. Reclassified
  Option A, separate destination wire/auth, HTTPS bearer/TLS rules, and the accepted
  cadence/deadline/backoff as settled H4 decisions under orchestration `5277764`.
- **2026-10-08:** Corrected both failure-backoff descriptions to distinguish the
  accepted 60/120/300-second base delays from the added stable 0–5-second jitter;
  the third and later completion-to-next-cycle totals are 300–305 seconds.
- **2026-10-08:** Aligned with orchestration `9288070`: Orders and Reception must
  use separate, independently generated opaque bearer tokens with at least 256
  bits of CSPRNG entropy. Token sharing or cross-destination derivation is
  forbidden. No credential, secret-store, handler, socket, or runtime artifact was
  created because destination authentication remains unimplemented in this repo.
- **2026-10-09:** Aligned the plan with orchestration `5dd9e23` and implemented the
  synthetic-only Orders serializer, canonical populated/empty fixture bytes and
  digests, invented Orders bearer boundary, and exact disabled in-process handler.
  Recorded the 24 focused and 343 combined isolated passes and the unchanged
  PySide6/`libxkbcommon.so.0` normal-test blocker. No source, socket, route mount,
  real credential, runtime activation, persistence, push, or deployment occurred;
  Orders receiver work remains gated on independent PASS of this handoff.
