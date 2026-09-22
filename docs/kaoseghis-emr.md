# KaosEghis-emr

Last updated: 2026-09-23

Status: the shared DB manager is still a design. An observation-only F6/F7/chart probe
now writes to the existing Launcher status area. It does not change database
privileges, polling behavior, or EMR data.

## Observation-Only Probe

`core/emr_signal_probe.py` starts with runtime services, not workspace construction.
No new UI is added. Launcher status lines distinguish `F6`, `F7`, `F6 button`,
`F7 button`, `F6 activation (UIA)`, and `F7 activation (UIA)`, followed by the
chart number and snapshot age when identity is available.
Chart-field UIA events and sampled chart changes also appear here as distinct sources.

- The existing EMR connection supplies the process, root window, and treatment
  window. Keyboard capture requires focus inside the treatment child, not merely
  the EMR process. Claim-page F7, other apps, modal dialogs, modified keys,
  injected inputs, and held-key repeats are excluded.
- Button capture uses exact `BtnF6`/`BtnF7` UIA IDs under the treatment window,
  then native HWND hit-testing for a matching left-button press and release.
  Dragging off a button is not a click. A first click activating EMR may show
  chart unavailable until a fresh treatment-context snapshot is available.
- An additional passive UIA listener subscribes to `UIA_Invoke_InvokedEventId`
  on each exact, already-discovered `BtnF6`/`BtnF7` element (`TreeScope_Element`).
  It does not invoke the control. Subscribing successfully does not prove that
  the eGHIS provider emits this event for either keyboard or mouse activation.
  Both original input listeners remain enabled for comparison; duplicate lines
  are intentional in this diagnostic phase.
- Button UIA event callbacks verify only cached sender metadata (process, automation
  ID, HWND, control type), then enqueue an observation from the existing chart
  snapshot. They do not read the sender's text, query the DB, scan a tree, or
  request a fresh patient read. An unverified sender is reported once per
  subscription without any raw provider details or patient data.
- An activation can be delivered after a dialog opens or an action finishes.
  Existing subscriptions remain while the connected buttons still exist, even
  when modal focus temporarily prevents chart sampling. The activation is shown
  without a chart when no fresh snapshot is available. UIA snapshot identity is
  provisional too: event delivery is not a guarantee of pre-action timing,
  successful order completion, or a committed DB change.
- Chart capture uses the operator-supplied screen point `(222, 115)`. The point
  must belong to a visible Text control in the connected EMR window and process.
  The background worker reads its current UIA Value/Legacy/Name using the same
  helper as the capture inspector, approximately every 250 ms. It never opens
  patient information. A native window caption is not used as chart identity.
  Native hit-testing may return the text's parent: the UIA target must still
  contain the point and have verified EMR ownership, but HWND equality is not
  required. Virtual targets use a bounded ancestor check, not a tree scan.
  The control can be reused when the native hit is its own HWND; values are never
  cached. Parent/virtual hits are resolved again each sample. Invalid controls,
  unreadable values, changed placement, and connection changes trigger reacquisition.
- UIA discovery runs only in that worker, is scoped, and caches button handles.
  Missing buttons retry at most every five seconds. Input callbacks do no UIA
  searches, DB reads, text reads, synchronous UI updates, or input injection.
  Both listeners use `suppress=False` and always pass input through.
- UIA registration and removal run on the same non-UI MTA sampling worker.
  EMR reconnects/button recreation replace subscriptions; unchanged samples do
  not repeat registration. Failed registrations retry at most every five seconds.
  A UIA listener failure leaves the keyboard/mouse probe running. Cleanup failures
  disable the UIA listener instead of accumulating subscriptions. Removed handlers
  reject late callbacks. This code never calls process-wide `RemoveAllEventHandlers`.
- F6/F7 snapshots older than 750 ms, missing/non-numeric values, and uncertain contexts
  are not presented as chart identity. The status says `Chart unavailable` with
  a non-patient reason: expired snapshot, unreadable/non-numeric UIA text,
  wrong/covered point, changed focus/target, or provider/access failure.
  A failed read is not mislabeled as an expired snapshot. Both keyboard and
  button observations preserve the pre-action failure reason. Sampling time is
  measured before the UIA read, so a slow provider cannot make old text look fresh.
  Even a recent snapshot is provisional: a patient switch between sampling and
  the input can race. Live validation is required before downstream use.
- Observations remain only in memory and the bounded existing status text area.
  No chart numbers are written to files, databases, or network destinations.
  Queue overload is reported, rather than silently implying complete coverage.
- No 20-second reconciliation timer or DB queue is enabled in this probe. Each
  separate physical press/click remains visible for diagnosis. PACS polling and
  flu reports are untouched.

After restarting KaosEghis, connect EMR and verify the four inputs during normal
work. Compare every displayed chart number with the patient on screen, including
rapid patient changes and F7 confirmation/print dialogs. Also test claim-page F7,
EMR restart/reconnect, and launcher drag/drop. Do not trigger clinical actions just
to exercise the probe. Changed screen placement/DPI may invalidate the chart point;
this diagnostic is not yet an authoritative patient-identity source.

The first live probe reported all sources but no chart. Its original reader
required the UIA HWND to equal the native hit and then used only WM_GETTEXT.
These assumptions have been removed, with regression tests for UIA-only values,
parent/virtual hits, fresh values on cached controls, and rejected context changes.
The corrected reader still needs live validation in the elevated clinical app.

### Activation Comparison

During normal clinical use, look for `UIA activation subscribed: F6, F7` first.
Then compare each ordinary F6/F7 press or button click with the corresponding
`F6 activation (UIA)` / `F7 activation (UIA)` line. Test both keys and both buttons,
including F7 confirmation/print dialogs and an EMR restart. Do not send orders
solely to exercise the probe. Record missing, duplicate, or delayed UIA events
and check the chart snapshot against the patient on screen. Only after that
validation should replacing either original listener be considered.

### Chart-Change Comparison

`core/emr_chart_probe.py` subscribes to Name, Value, LegacyName, and LegacyValue
property changes on the exact verified Text control already found by the chart
reader at `(222, 115)`. It does not save or depend on the numeric Automation ID.
The binding is identified by the current EMR scope and UIA runtime ID. Reconnects
or replaced controls remove the old handler and bind to the newly discovered
instance, including virtual UIA controls without their own HWND. Late callbacks
from a replaced binding are ignored.

The chart listener uses the same MTA worker as the button listener for all
registration/removal. Failed subscription retries are bounded to five seconds;
cleanup failure stops this listener without accumulating handlers. Callbacks use
cached process/runtime/type metadata and the event's new-value payload, never a
fresh UIA text read. Invalid values are not displayed, and provider exception text
is not logged. A verified empty field can be subscribed before a patient is selected.

Launcher status distinguishes:

- `UIA chart change subscribed`: listener registration succeeded, not proof of delivery.
- `Chart field event (UIA Name)` (or Value/LegacyName/LegacyValue): a genuine
  property callback, showing only a numeric chart value, a cleared-field status,
  or a redacted unavailable-value status. Multiple properties may report the same change.
- `Chart observed (sampled)`: the existing reader's initial/reconnected baseline.
- `Chart changed (sampled)`: that reader saw a different number; this is not a UIA event.
- `Chart field empty (sampled)`: the reader verified an empty field. Focus loss or
  a read failure is not presented as a cleared patient.

During normal patient changes, compare UIA lines with sampled lines. A value set
before the first subscription may have only a sampled baseline. Same-patient
reloads may not change any chart property. Neither kind of line proves that all
patient fields/orders have finished loading, and property events do not overwrite
F6/F7 snapshots or trigger alerts/DB work. Existing patient-alert monitoring is
unchanged. EMR event delivery still requires live verification; a real property
change on an isolated, hidden Windows test field has verified the callback path.

### Resource Boundaries

The UIA activation and chart listeners add no chart polling or database calls.
They reuse the existing two button handles and roughly 250-ms chart sampling.
That sampling still has UIA/provider cost: the whole diagnostic is not event-only.
Subscriptions are element-scoped, never desktop-wide. Event handlers use a bounded
queue and perform no synchronous UI update. No resource benchmark against EMR's
30-second PACS DB polling has been claimed. A future event-triggered DB queue may
avoid idle queries but could issue more, narrower queries during busy work.

The input-hook constraints follow Microsoft's
[low-level hook guidance](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc)
and pynput's [suppression documentation](https://pynput.readthedocs.io/en/latest/faq.html).
The listeners follow Microsoft's
[UIA event guidance](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-eventsforclients)
and [UIA threading requirements](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-threading).
Chart events use the
[property-change callback](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationpropertychangedeventhandler-handlepropertychangedevent).

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
reviewed-operation API, privilege verification, and production validation of signal
capture remain work to do.
