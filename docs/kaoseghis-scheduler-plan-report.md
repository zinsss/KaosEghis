# KaosEghis Scheduler Plan Report

Last updated: 2026-08-03

## Decision

The generic Scheduler foundation is implemented. It schedules saved macros; it does
not implement backup behavior itself.

Current readiness:

| Area | State | Decision |
| --- | --- | --- |
| Schedule persistence | Implemented | Ready |
| Weekday/time calculation | Implemented | Ready |
| Countdown/cancel | Implemented | Ready |
| Missed-run handling | Implemented | Ready |
| Run history | Implemented | Ready |
| Macro overlap prevention | Implemented | Ready |
| Backup macro | Not implemented | Await workflow details |
| eGHIS close/backup macro | Not implemented | Await live target capture |
| Claim-day macro | Planning only | Defer |

## Implemented Architecture

```text
Visible KaosEghis desktop app
  -> SchedulerRuntime (time/weekday and countdown)
      -> saved macro item
          -> MacroRunner safety gate and action engine
```

This is intentionally an in-process implementation:

- jobs run only while KaosEghis is open
- startup schedules the next future occurrence and runs nothing immediately
- jobs are disabled by default
- automatic runs have a 10-second cancellation window
- more-than-60-second-late jobs are missed, not replayed
- `prompt` jobs require Run now
- scheduled and manual real macros cannot overlap

## Backup Plan

The backup process will be a saved macro selected by a Scheduler job. This avoids a
second execution engine and keeps status, cancellation, and history consistent with
other automations.

Required facts before implementation:

- completed backup source path
- completed filename pattern
- stable-file signal
- destination path or paths
- Dropbox policy
- overwrite/version rule
- temporary-copy and verification rule
- desired lunch time and weekdays

Proposed first backup macro behavior:

1. Validate the approved source and destination boundaries.
2. Select only completed, stable backup artifacts.
3. Copy to a temporary destination filename.
4. Verify size and optionally hash.
5. Rename to the final filename.
6. Return a safe success/failure result to Scheduler history.

No source deletion and no live PostgreSQL-directory copy should be included initially.

## End-of-Day Plan

The later eGHIS end-of-day backup workflow will also be a macro. It needs verified UI
targets for graceful close, the exact backup prompt, the shutdown-after-backup checkbox,
and the confirmation control.

Implementation must retain:

- manual cached EMR connection requirement
- exact process/window ownership checks
- no unknown modal interaction
- stop on first failure
- no forced process kill
- no blind keyboard confirmation
- no operating-system shutdown fallback

## Claim-Day Plan

Claim-day statistical preparation remains requirements work only. The Scheduler does
not authorize submission, approval, billing changes, or secret handling.

## Production Gate

The Scheduler structure may merge independently of the backup macro because all jobs
are disabled by default and no schedule is seeded. Production use of a backup schedule
should wait until:

- a representative backup macro dry run is reviewed
- manual Run now succeeds
- sleep/resume and cancellation are tested on the clinic workstation
- destination failure is tested
- logs are confirmed free of patient data and secrets

See `docs/kaoseghis-scheduler.md` for the full current specification.
