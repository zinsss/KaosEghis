# Offline Orders Delivery Foundation

Updated: 2026-10-04

## Current Milestone

The operator approved an offline delivery-queue milestone after the design review,
with a commit and push after each completed, tested milestone. This does not approve
production storage, source acquisition, publishing, or changes to KaosOrders runtime.

`core/kaosorders_outbox_shadow.py` is a synthetic-only local SQLite outbox. Nothing
in application runtime imports it. Every caller must supply an explicit file path
and `synthetic_fixture=True`. This assertion is not proof that data is synthetic.
Files contain **plaintext synthetic fixtures only**: do not supply patient data.
Production encryption, Windows ACLs, journal/backup protection and retention are
not implemented. Setting a flag does not make this production-ready.

The pure serializer and the two pinned receiver fixtures are unchanged. The outbox
calls the serializer only in isolated tests. There is no default data path, settings
integration, worker, timer, network client, endpoint, credential or EMR query.
`/api/v1/order-snapshots` remains prohibited for the normalized source payload.

## Implemented Offline

- Explicit exclusive creation enrolls one synthetic clinic/source/projection,
  mapping revision, caller-supplied epoch and receiver generation. Opening an
  existing store never creates missing state, resets an epoch or migrates a schema.
- One producer epoch is shared by all its days. Each day allocates revisions from
  1, independently, only when a complete validated snapshot is successfully sealed.
  Counters are positive signed-64-bit values; exhaustion cannot wrap.
- Each operation opens a local SQLite connection, uses a `BEGIN IMMEDIATE`
  transaction with `synchronous=FULL`, and closes on success or failure. The
  existing EMR coordinator/mutex is not used for this independent synthetic store.
- Revision allocation and the exact canonical sealed UTF-8 request bytes commit
  together. A failed validation, insertion or commit consumes no revision.
- At most one unresolved batch exists per day. A later `seal` refuses to replace
  it. `pending` returns the original immutable bytes without changing observation
  time, batch ID, revision, epoch or digest. No HTTP request is made.
- Refresh requests increment a durable generation counter. The caller captures its
  ticket **before** reading source facts. Sealing/acknowledging that ticket cannot
  swallow a later request; after acknowledgement the remaining requests coalesce
  into one fresh read. The queue never performs that read itself.
- Accepted batch IDs remain reserved across every day in this store. A receipt
  retains only cursor/digest/body-hash/generation metadata after acknowledgement;
  the pending body is set to null in the same transaction as acknowledged progress.
  This is logical removal, not secure erasure of SQLite pages or journal/backup bytes.
- Application/schema markers, counters, receipt consistency and pending-byte hashes
  detect unsupported or inconsistent state. This is corruption detection, not
  authentication or protection against a maliciously rewritten/rolled-back store.
- A temporary 16 MiB per-batch guard applies to this synthetic harness only. It is
  not an approved transport limit. Total scope/storage quotas and receipt expiry
  still require design before production.

## Synthetic Receipts

`SyntheticAcknowledgement` is an internal test object, **not an approved HTTP ack
schema**. It carries outcome, receiver generation, the request cursor and the
receiver's committed cursor. The cursor binds all scope fields, epoch, revision,
batch ID and content digest. No patient/order IDs or payload excerpts belong in it.

| Outcome | Offline behavior |
| --- | --- |
| accepted / duplicate | Both cursors and receiver generation must match the pending batch. Atomically acknowledge and clear its body. |
| repeated local success | Only the most recent acknowledged cursor may return already_acknowledged; an old ack never clears a newer pending batch. |
| stale / conflict / resync_required | Preserve bytes and durably pause that day. No implicit resume/reset operation is provided. |
| wrong/missing cursor, scope, digest or receiver generation | Fixed redacted rejection; preserve pending data. A future supervisor must stop and reconcile, not blindly retry. |

There is no authentication implementation. A local test object cannot prove a real
receiver committed anything. Unknown/forged extra fields are rejected; object
representations are redacted. Exact payload bytes remain sensitive outside fixtures
and are never safe to log merely because their containing model has a redacted repr.

## Restart and Recovery

Tests terminate a separate synthetic Python process immediately before and after
seal/ack transaction commits, then reopen the store. Pre-commit exit must preserve
the previous state; post-commit exit must expose the complete new state. These are
process-crash tests, not proof against physical disk/power failure on every device.
Tests also cover SQL failure between related writes, concurrent store instances,
cross-day isolation, byte corruption, missing state and mismatched acknowledgements.

Normal reopen retains epoch, cursor, pending bytes and coalesced refresh requests.
Missing/corrupt state fails closed. Intentional epoch reset, sender/receiver backup
rollback, lost-state repair, receiver-ahead recovery and new receiver enrollment are
**not implemented**. They require an authenticated, durable recovery handshake that
fences the old producer and checks receiver cursor/generation before retrying.

## Remaining Design

The sender-side working decisions from the 2026-10-04 review remain proposals for
joint receiver agreement, not authorization to deploy:

- Require one authorized producer and receiver-recorded epoch grants. New epochs
  start each resumed day at revision 1; ordinary restart/day rollover does not.
- Keep a sealed unresolved batch immutable; coalesce refresh requests behind it.
- Define a versioned, authenticated, content-bound acknowledgement/recovery schema.
  Only committed accepted/duplicate receipts release normal pending work.
- A semantic mapping or coverage change uses an approved new projection and an
  explicit cutover. Never relabel a pending batch or bypass mapping checks by
  incrementing the epoch. This store refuses in-place mapping changes.
- Proposed retry budget: 2-second initial backoff, 60-second cap, jitter, 15-second
  total attempt deadline; warn after 5 minutes and pause after 15 minutes or 20
  attempts. No retry scheduler, timers or request attempts exist in this milestone.
- Retain the stricter decimal magnitude/exponent/input bounds on the sender only.
  Do not convert implementation limits to clinical units or shared contract bounds
  without source evidence. Neither serializer nor receiver validation was changed.
- Approve production encryption/ACLs/backups, storage quotas, receipt retention,
  replay fences after PHI purge, allowed days, TLS and transport byte limits.

Source evidence is still missing for whole-day membership and consistent/empty
reads, code 10 and qualifier combinations, all-category cancellation, sex/age
conventions and clinical units. Existing supervised observations are documented in
[KaosOrders](kaosorders.md#source-evidence-and-blockers); no new live reads occurred.

## Next Handoff

KaosOrders' synthetic receiver at exact commit
`02acc8a93c0c373d4e53d181058b46ce1fb405c7` resolves the historical-duplicate
issue reported against `40c6a49`. The
[acknowledgement recheck](kaoseghis-emr-contract-review.md#synthetic-acknowledgement-recheck-2026-10-04)
confirms current active retries give duplicate, same-epoch history gives stale,
and retired-epoch retries give resync_required even when another day advanced
the producer. Committed is the requested day's actual current cursor. Negative
receipts durably pause and preserve pending bytes without adopting that cursor or
allocating its next revision. No sender validator or runtime change was needed.

Next, agree epoch grants/fencing, receiver enrollment, lost-state/receiver-ahead
recovery, acknowledgement encoding/status mapping, retry/pause policy and mapping
cutover. Do not repeat serializer work or enable transport. Keep both runtimes,
the existing v1 API and board untouched. Source-evidence gates remain unresolved;
do not use patient data or implement a production day reader in this handoff.

## Verification

The final isolated Windows suite passed **2,496 tests in 491.32 seconds**, including
**72 new outbox cases** and all **317 source-model/serializer parity cases**. Existing
source-shadow, shared-reader, PACS, flu, patient-context, vaccine, macro and UI groups
also passed; no tests were excluded. The serializer and both pinned fixture files
have no changes from commit `31086389310e0641c0ed4a8f3e3d97eec804a23c`.

Tests used real temporary SQLite fixture files, mocked EMR connections, isolated
test mutexes/application data, blocked external network/WebEngine access and blocked
unmocked native desktop/printer operations. No production data, EMR interaction,
API call, app restart, source settings change or deployment occurred.
