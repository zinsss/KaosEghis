# KaosEghis-emr

Last updated: 2026-09-29

Status: the first shared-read stage is implemented. Verified chart clears can now
refresh the existing whole-day PACS query; Poll Now remains a manual fallback.
PACS, flu-report, health, and patient-context reads share one FIFO worker per
process and a Windows machine-wide mutex. Each source connection is read-only and
closed before the next read or any downstream delivery. This is not yet a separate
broker executable or an all-orders/reception-status reader for KaosOrders.
F6/F7 observations remain diagnostic only. The patient-memo alert is unchanged.

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
- Chart discovery uses the latest operator-captured screen point `(205, 115)`. The point
  must belong to a visible Text control in the connected EMR window and process.
  The background worker reads its current UIA Value/Legacy/Name using the same
  helper as the capture inspector, approximately every 250 ms. It never opens
  patient information. A native window caption is not used as chart identity.
  Native hit-testing may return the text's parent: the UIA target must still
  contain the point and have verified EMR ownership, but HWND equality is not
  required. Virtual targets use a bounded ancestor check, not a tree scan.
  Ownership follows a bounded native parent/owner chain to the connected EMR
  root, with a matching process at every step. Same-process membership alone is
  insufficient. This also accepts eGHIS-owned header windows that are not children
  of the main window; the keyboard treatment-focus restrictions are unchanged.
  The verified UIA control is cached by connection scope, runtime ID, and native
  owner. Subsequent reads follow that control's current bounds, not the old pixel.
  A newly discovered control must first expose a numeric chart value before it
  is cached or subscribed. Focus loss and a temporarily empty known chart discard
  the sample but keep that verified control. Non-numeric text invalidates the cache
  and detaches its property listener; it cannot keep reporting from that control
  indefinitely. Failed discovery/read attempts retry at most once per second in
  the worker, with no tree scan or input injection. A new EMR scope can retry immediately.
  Stale/hidden controls, provider failures, changed identity, and connection changes
  trigger reacquisition. Every successful sample reads fresh text and revalidates
  identity and focus; a previous chart number or property event is never substituted.
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
  discovery point outside the EMR hierarchy, changed focus/target, or provider/access
  failure. The discovery error does not assume that a window is covered.
  A failed read is not mislabeled as an expired snapshot. Both keyboard and
  button observations preserve the pre-action failure reason. Sampling time is
  measured before the UIA read, so a slow provider cannot make old text look fresh.
  Even a recent snapshot is provisional: a patient switch between sampling and
  the input can race. Live validation is required before downstream use.
- Observations remain only in memory and the bounded existing status text area.
  No chart numbers are written to files, databases, or network destinations.
  Queue overload is reported, rather than silently implying complete coverage.
- F6/F7 input observations do not request DB work. Each physical press/click
  remains visible for diagnosis; only verified clears feed the refresh path below.

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

On 2026-09-23, real chart Name-change events arrived while F7 repeatedly reported
the point as "outside EMR or covered." Read-only native diagnostics found that the
header Text window belonged to eGHIS through an owned host window, not an IsChild
relationship with the main window. On that live hierarchy, the old child-only
check returned false and the bounded parent/owner check returned true. No patient
text was read or input sent for this diagnostic. Regression tests cover the owned
host, foreign/unrelated windows, bounded walks, moved cached controls, focus loss,
fresh values, and replaced runtime identities. Post-restart F7 chart identity still
requires observation during ordinary clinical work.

A later capture at `(205, 115)` confirmed a numeric Text control with matching
Name and Value while the probe had reported persistent non-numeric cached text.
Both the old and new points hit the same native label during the read-only check,
so the exact original misbinding was not reproduced. The confirmed code defect
was indefinite reuse of a non-numeric cached control. Discovery now uses the
latest captured point, nearer the label's left edge, and invalid text forces
bounded reacquisition. No numeric HWND/Automation ID or patient value from the
capture is saved. Tests cover rejected initial blank/text controls, cache replacement,
listener removal/late-event rejection, narrow labels, and retry limits.

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
reader at `(205, 115)`. It does not save or depend on the numeric Automation ID.
The binding is identified by the current EMR scope and UIA runtime ID. Reconnects
or replaced controls remove the old handler and bind to the newly discovered
instance, including virtual UIA controls without their own HWND. Late callbacks
from a replaced binding are ignored.

The chart listener uses the same MTA worker as the button listener for all
registration/removal. Failed subscription retries are bounded to five seconds;
cleanup failure stops this listener without accumulating handlers. Callbacks use
cached process/runtime/type metadata and the event's new-value payload, never a
fresh UIA text read. Invalid values are not displayed, and provider exception text
is not logged. An already-verified chart field remains subscribed when cleared;
an unknown empty Text control is not subscribed before numeric verification.

Launcher status distinguishes:

- `UIA chart change subscribed`: listener registration succeeded, not proof of delivery.
- `Chart field event (UIA Name)` (or Value/LegacyName/LegacyValue): a genuine
  property callback, showing only a numeric chart value, a cleared-field status,
  or a redacted unavailable-value status. Multiple properties may report the same change.
  Rejected payloads distinguish missing values, non-text values, non-numeric text,
  and numeric text exceeding the 20-digit limit. No rejected content is displayed
  or coerced to a chart number. A missing payload is not a confirmed cleared field.
  These messages alone do not say whether the independent sampled/F6/F7 chart
  read succeeded; compare the following sampled and input-signal lines.
- `Chart observed (sampled)`: the existing reader's initial/reconnected baseline.
- `Chart changed (sampled)`: that reader saw a different number; this is not a UIA event.
- `Chart field empty (sampled)`: the reader verified an empty field. Focus loss or
  a read failure is not presented as a cleared patient.

During normal patient changes, compare UIA lines with sampled lines. A value set
before the first subscription may have only a sampled baseline. Same-patient
reloads may not change any chart property. Neither kind of line proves that all
patient fields/orders have finished loading, and property events do not overwrite
F6/F7 snapshots. Verified clears and sampled numeric loads/changes can request a
day-wide PACS refresh; raw numeric events wait for a verified sample. Clear/change events invalidate pending memo
checks; subsequent sampled chart identity schedules a delayed alert check as
described below. Live logs now confirm eGHIS Name-change event delivery, including clear
and numeric transitions, but not complete coverage or patient-load completion.
A real property change on an isolated, hidden Windows test field also verified
the callback path. Button activation-event delivery remains unverified.

### Chart-Triggered PACS Refresh

- A previously verified numeric chart changing to a verified empty field requests
  refresh. UIA properties and sampled clears are deduplicated under the patient
  lock. Missing/unreadable text, focus loss, and initial empty fields are not clears.
- A verified numeric sample requests refresh when first observed or changed,
  including the same patient after a confirmed clear. Repeated samples of the same
  number and temporary unreadable/focus gaps do not create duplicate load requests.
  Patient identity still uses the 750-ms freshness rule, but day-wide refresh does
  not: no departing chart number is passed to the database reader.
- Wait two seconds after the latest clear/load in a burst, then emit a separate Qt
  request. No F1, caret readiness, focus, typing, or mouse input is needed.
  A new patient loading cannot redirect the request to another patient's query.
- Each request retains its event date across midnight. Automatic refresh does
  not use an operator's currently selected historical worklist date. Poll Now does.
- The PACS worker uses the existing imaging query and cancellation reconciliation,
  then existing KaosPACS delivery. It does not infer completion/cancellation from
  a clear and does not yet read all orders or reception statuses.
- Each clear also schedules one follow-up at 30 seconds after that clear, not
  after the first read finishes. A new load neither cancels nor postpones it and
  does not create its own follow-up. A later clear replaces the pending deadline
  with its own +30 seconds. Neither delay proves that EMR has committed.
- Fast reads and follow-ups have separate pending slots per day. If both are due,
  one read covers both; a read begun before the follow-up deadline cannot consume
  it merely by finishing late. Follow-ups do not recursively schedule follow-ups.
- Only one PACS operation runs at a time. Further requests coalesce by day and
  remain pending rather than being dropped during an active refresh.
- Event mode performs startup and detected EMR-reconnection refreshes, each with
  a +30-second follow-up. F6/F7 keys, clicks and activation events remain diagnostic
  only; they do not request database reads.
- A safety check requests today's refresh after five minutes without a successful
  current-day read, even if no more chart events arrive. A five-second local timer
  checks the deadline only, not the database. It does not require EMR focus or a
  chart signal. In-flight/queued work for today coalesces with this check.
- Safety-check failures retry after 60, 120, 240, then 300 seconds (capped there).
  A successful current-day read resets the five-minute deadline and backoff;
  events, historical reads and failures do not count as success. Delivery errors
  returned by KaosPACS do not invalidate a successful source read. Day rollover
  requests the new day without discarding the previous day's pending follow-up.
- Chart requests are independent of the bounded diagnostic queue. Disconnects,
  changed EMR scope, stop, invalid timing, or a 120-second UIA worker stall discard
  pending trigger candidates. Startup/reconnection and safety reads reconcile missed work.
- Existing automatic-refresh enable/disable and PACS dry-run settings are honored.
  The default `pacs_refresh_mode=chart_clear` (shown as `Chart clear/load`) disables
  the legacy regular polling timer. Disabling automatic refresh also stops the
  safety timer and cancels pending automatic work; Poll Now remains available.
  `timer` is an explicit rollback option in PACS Operator Mode or Settings > PACS.
- Launcher status shows each refresh's reason, date, outcome and total elapsed
  time (including queue wait and delivery). PACS shows the last successful source
  read time; failures do not advance it. Memo timing remains unchanged.

Before relying on this during normal work, verify F6/F7 keys and buttons, the last
patient of the day, fast patient switches, edits/deletions, and offline recovery.
Compare PACS after the follow-up with Poll Now. The safety check improves recovery
but does not guarantee immediate delivery, especially while the app is closed or
source/destination services are unavailable. Do not create clinical orders just
for testing. No production DB or UI input was exercised during implementation.

### Shared Read Queue (Stage One)

`core/eghis_db.py` routes every existing reader through `core/emr_read_queue.py`.
The one-worker FIFO covers PACS, flu-report, SELECT 1 health checks, patient-context
API calls, and the diagnostic tool. A named Windows mutex additionally excludes
connections from other updated Kaos processes on the machine. It does not block
eGHIS's own connections, or coordinate older versions that bypass this helper.

No connection pool is used. Cursor/connection cleanup is inside the exclusive
operation, on success and failure, before local SQLite work or HTTP delivery.
Read-only session setup must succeed. Default connect and statement limits are
five seconds; flu-report retains its existing shorter three-second statement limit.
The in-process queue is bounded to 64 callers; mutex waiting is bounded to 60 seconds.
Neither SQL nor connection strings nor patient data are logged by the queue.

This is the foundation, not the full future broker below. Pending work is in memory;
durable delivery, all-orders snapshots and reception status semantics remain future
work. Serialization may reduce contention but does not prove the flu-report/EMR
timeout issue is resolved.

### Delayed Patient-Memo Alert

With `Enable *** patient-note alert` enabled, the shared chart observer schedules
one memo check **five seconds after observing a new patient context**. The existing
red, always-on-top popup and configurable memo target are reused. The default memo
Automation ID remains `TreatmentPtntMemo`.

- The alert no longer starts its own 1.5-second chart polling loop. It does not
  resolve the old chart-target settings; it uses the shared sampled identity.
- Duplicate numeric UIA events/samples do not restart the timer or repeat a check.
- A clear or different patient cancels pending work and clears the old alert.
  A clear followed by the same chart number is a new visit and gets a new check.
- The timer never fires early. A five-second delay is an operator-selected settling
  period, not proof that EMR finished loading every field.
- Memo UIA access runs off the GUI thread, once per context. The shared snapshot
  must still be fresh and identify the same EMR process/window/patient both before
  and after reading. UIA change callbacks invalidate it immediately; samples that
  started before that change cannot restore it.
- Checks are serialized. A slow old read cannot overlap a new one or display a
  stale alert. Stop, disconnect, and settings changes invalidate in-flight results.
- An unreadable memo is unavailable, not a confirmed absence of `***`. There is
  no endless retry or memo polling after this attempt. Reloading the patient or
  saving the alert settings can schedule another delayed check.
- No patient memo contents are logged, persisted, or sent through Qt signals.
  The enabled setting is preserved; installing the change does not silently turn
  a disabled alert back on.

### Resource Boundaries

The UIA activation and chart listeners add no chart polling or database calls.
They reuse the existing two button handles and roughly 250-ms chart sampling.
That sampling still has UIA/provider cost: the whole diagnostic is not event-only.
Pending clear diagnostics only check in-memory deadlines and cached connection
identity. The earlier F1 caret/focus probe and local target lookup have been removed.
Subscriptions are element-scoped, never desktop-wide. Event handlers use a bounded
queue and perform no synchronous UI update. No resource benchmark against EMR's
30-second PACS DB polling has been claimed. Event mode replaces that timer with
clear/load reads, bounded follow-ups and a five-minute successful-read safety
deadline. Whole-day reads and existing delivery can still be frequent during busy work.

The input-hook constraints follow Microsoft's
[low-level hook guidance](https://learn.microsoft.com/en-us/windows/win32/winmsg/lowlevelkeyboardproc)
and pynput's [suppression documentation](https://pynput.readthedocs.io/en/latest/faq.html).
The listeners follow Microsoft's
[UIA event guidance](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-eventsforclients)
and [UIA threading requirements](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-threading).
Chart events use the
[property-change callback](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationpropertychangedeventhandler-handlepropertychangedevent).

## Future Broker Scope

The following sections describe the full target architecture, beyond the PACS-only
stage above; they are not a claim that all acceptance gates are implemented.

KaosEghis-emr will be the shared eGHIS read adapter for KaosEghis-pacs,
KaosOrders, on-demand flu reporting, and patient-context database lookups.

- Observe F6/F7 and the verified BtnF6/BtnF7 controls without suppressing, replaying,
  or generating those inputs. Signals indicate intent, not successful order saves.
- Capture verified chart identity before the EMR action opens another window.
- Validate the initial and follow-up timing during normal clinical work. The
  earlier per-chart 20-second F7 proposal in [KaosOrders signal capture](kaosorders.md)
  is superseded by day-wide chart-clear/load refreshes.
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
