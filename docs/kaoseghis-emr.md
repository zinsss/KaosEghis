# KaosEghis-emr

Last updated: 2026-09-22

Status: design requirements agreed with the operator; the shared manager and
F6/F7 listener are not implemented yet. This document changes no runtime settings,
database privileges, polling behavior, or EMR data.

## Purpose and Ownership

KaosEghis-emr will be the shared eGHIS read adapter for KaosEghis-pacs,
KaosOrders, on-demand flu reporting, and patient-context database lookups.

- Observe F6/F7 and the verified BtnF6/BtnF7 controls without suppressing, replaying,
  or generating those inputs. Signals indicate intent, not successful order saves.
- Capture verified chart identity before the EMR action opens another window.
- Use the fixed per-chart 20-second reconciliation delay in
  [KaosOrders signal capture](kaosorders.md); a different chart has its own timer.
- Reconcile actual source states before delivering minimal data to the PACS and
  KaosOrders adapters. These adapters retain their own domain and delivery logic.
- Run flu reporting only on explicit request. Prefer small source reads and local
  calculations, subject to exact count/age semantics and validation.
- Serialize source reads through a bounded background queue. UIA observation and
  downstream network delivery must not run while holding an EMR DB connection.

The initial host can be the KaosEghis process; a separate installed service is not
required. Any independently running KaosEghis-pacs agent must also be migrated or
retired at cutover. An in-process queue alone cannot coordinate an external agent.

## Non-Negotiable Source Safety

**KaosEghis-emr must never modify the eGHIS database.**

1. Use reviewed, parameterized read operations, not an arbitrary SQL execution API.
   Do not allow callers to disable the safety policy through query text or settings.
2. Establish and verify read-only session/transaction mode before every source read.
   If that cannot be established, fail closed: no report or order query is executed.
3. Require a dedicated least-privilege database identity with SELECT on approved
   source objects and only the necessary connection/schema permissions. It must not
   be a superuser, owner, or inherit a role that can write. Effective PUBLIC/group
   permissions, temporary-object creation, and function execution also need review.
4. Privilege provisioning is an explicit administrator/vendor task, outside this
   component. Never create roles, grant/revoke permissions, or alter the production
   server automatically. Current credentials have not been certified for this role.
5. No INSERT, UPDATE, DELETE, DDL, source migrations, indexes, maintenance commands,
   writable routines, sequence updates, row-locking reads, or server configuration
   changes. Trusted session-local read-only/timeout setup is the narrow exception
   for connection configuration; it does not change EMR records or schema.
6. A SELECT prefix or keyword blacklist is not sufficient proof of read-only safety.
   Restrict operations at the API layer and enforce permissions at the database.
7. This component observes UI actions only. Existing macros that type, click, or
   chart in EMR remain separate and do not gain a database-write capability.

Local KaosEghis persistence and authenticated downstream API delivery remain
separate operations. "Read-only" here means no application-driven EMR data/schema
mutation, not zero database CPU/I/O or zero internal server disk activity.

PostgreSQL documents the limits of read-only transaction mode and separately
controlled privileges: [read-only transactions](https://www.postgresql.org/docs/9.2/sql-set-transaction.html),
[object privileges](https://www.postgresql.org/docs/9.2/ddl-priv.html).

## Exclusive Connection Ownership

**At most one Kaos-managed EMR database connection may exist at a time.**
Serializing SQL execution while leaving multiple connections open is not sufficient.

- Every source operation uses the same queue: PACS, KaosOrders, flu reports, patient
  lookups, health checks, diagnostics, retries, and fallback reconciliation.
- Reserve the single connection slot before attempting to connect and retain it
  through cursor/connection cleanup. No other connection attempt starts until that
  cleanup completes successfully.
- An on-demand flu request arriving during another read stays queued with no DB
  connection. Show a queued status without blocking the GUI; do not preempt the
  active operation, open a second connection, or bypass the queue on timeout.
- A cancelled or expired queued request never connects. Cancelling an active request
  does not release the slot until its connection has actually been closed.
- If closure is uncertain or fails, mark the manager unhealthy and block new source
  connections pending recovery. Do not open a second diagnostic connection to probe
  the first while ownership remains unresolved.
- Multiple KaosEghis instances and legacy agents must share the same owner or refuse
  duplicate DB access. Separate per-module/per-process locks are not enough.

This limit applies to Kaos-owned connections. It must not close, block, or reconfigure
the eGHIS application's own connections or connections owned by unrelated software.

## Connection Lifetime

**Close the cursor and physical connection immediately after each bounded source
read finishes, before local computation, UI updates, persistence, or publishing.**

```text
wait in queue / settle timer (no connection)
  -> connect
  -> establish read-only mode and finite timeout
  -> execute reviewed read and fetch its bounded result
  -> close cursor and connection
  -> calculate locally / deliver to consumer
```

- No idle connection pool, cached connection, shared global connection, or open
  transaction between jobs. Cache validated results or metadata, never connections.
- Use nested cleanup so a cursor-close error cannot skip connection cleanup.
- Clean up on success, query/fetch/setup error, timeout, active cancellation, and
  controlled application shutdown. A cancelled queued job must never connect.
- Each job needs finite queue, connect, and query deadlines. Cancellation must not
  merely hide a running request or allow late delivery after the job was discarded.
- A multi-read report closes after each read. Do not hold the connection while
  calculating ages, waiting for the next batch, retrying, or posting downstream.
- Never hold a local SQLite write transaction across a source database operation.
- Cleanup failure is a failure, not successful completion. A stuck driver requires
  an unhealthy state and bounded recovery design; a thread/finally block alone is
  not proof that a non-returning driver has closed its server session. Determine
  whether worker-process isolation is needed before promising hard recovery bounds.
- Record only operation type, queue/read/close timings, and outcome. No credentials,
  SQL, chart numbers, birth dates, names, or raw rows in routine diagnostics.

## Failure and Reconciliation Rules

- A failed, timed-out, incomplete, or unverified read is not an empty order list and
  must never trigger downstream cancellation/deletion.
- Do not infer source completion or cancellation from F6/F7 alone.
- Keep manual/startup reconciliation for missed signals and other-workstation edits.
  Validate key/button capture before replacing the current PACS timer.
- Keep one active source read at a time, coalesce duplicate pending work, and bound
  retries. Flu calculations run after connection closure and do not occupy the DB
  worker. Prevent starvation as well as unbounded queue growth.
- This adapter cannot coordinate eGHIS's own queries; read-only and serialization
  do not establish that the observed flu-related slowdown has been fixed.

## Acceptance Gates

Before enabling the new source path:

- Verify role/session restrictions without attempting writes against production.
  Rejection tests use an isolated test database, including multi-statement and
  side-effecting-operation attempts.
- Prove connections/cursors close on all normal and exceptional paths; verify that
  downstream callbacks start only after closure and idle jobs leave no DB sessions.
- Test cancellation before connect, during execution, and before result delivery;
  shutdown and cleanup errors must not produce late successful results.
- Test concurrency, queue deadlines, duplicate signals, independent patients, and
  slow-query behavior while the GUI remains responsive.
- Assert a maximum live connection count of one, including connection setup, delayed
  cleanup, cancellation, health checks, and multiple callers. Specifically test that
  flu requested during PACS work cannot connect until the PACS connection closes.
- Verify cleanup failure stops queue dispatch and duplicate application/agent
  instances cannot independently acquire another source connection.
- Validate chart identity and both buttons in observation-only mode, including
  unrelated F7 uses such as claim aggregation, modals, EMR restarts, and DPI changes.
- Compare flu totals and age-at-visit boundaries with the established report.
- Define and verify the KaosOrders publish contract before sending patient data.
- Inventory all active EMR DB clients at cutover so no legacy poller bypasses the
  manager. Keep an explicit fallback while signal capture is being verified.

## Existing Foundation

`core/eghis_db.py` already requests read-only sessions and uses nested cursor and
connection cleanup. Flu queries have connection/statement limits. This is useful
groundwork, but not certification of the complete policy above: the shared queue,
reviewed-operation API, privilege verification, and signal capture remain work to do.
