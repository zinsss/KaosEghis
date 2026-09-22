# Startup Stall Diagnostics

## 2026-09-22 Observation

The operator reported the splash screen becoming unresponsive at `Building workspace`.
The third launch succeeded. The shortcut still points to Python 3.11 and `main.py` in
the correct repository directory; the PACS/flu relationship investigation made no edits.

A hidden diagnostic construction with EMR auto-connect, scheduler execution, automatic
PACS polling, and local migrations disabled completed in about six seconds. The PACS
panel, including its synchronous health checks, took under one second in that run.
This did not reproduce or identify the blocked call in the failed attempts. EMR
auto-connect and PACS startup health checks can still block the GUI thread.

## Trace Files

- `data/startup-diagnostics.log`: current launch phases and cumulative elapsed times.
- `data/startup-diagnostics.previous.log`: immediately preceding attempt.

For a phase lasting over ten seconds, Python's diagnostic watchdog writes a one-shot
thread stack to the same file. It does not depend on Qt's event loop, restart the app,
abort a call, retry a connection, send EMR input or change settings. Only one previous
attempt is retained, and each phase emits at most one stack snapshot.

The watchdog is cancelled and the file closed before the master-password prompt.
Records include phase labels, timestamps, source filenames, function names and line
numbers, not local variable values, credential values, patient fields or raw exception
messages. Failure records name only the exception class. Inaccessible log files must
not prevent startup.

On recurrence, inspect the blocked main-thread stack before changing startup behavior.
The trace is diagnostic coverage, not a confirmed fix for the intermittent stall.
