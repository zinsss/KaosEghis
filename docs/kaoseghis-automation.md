# KaosEghis Automation

Last updated: 2026-06-30

## Purpose

This document describes the automation boundary of KaosEghis:

- what is read-only
- what is manual test only
- what is dry-run only
- what is actually executable

The project deliberately avoids mixing these categories.

## Layers

### Detection

Modules:

- [KaosEghis/core/emr_detector.py](/E:/Kaos/KaosEghis/KaosEghis/core/emr_detector.py)
- [KaosEghis/core/eghis_connector.py](/E:/Kaos/KaosEghis/KaosEghis/core/eghis_connector.py)

Responsibilities:

- process detection
- window detection
- active-window checks
- connector readiness state

### Read-Only UI Inspection

Modules:

- [KaosEghis/core/uia_inspector.py](/E:/Kaos/KaosEghis/KaosEghis/core/uia_inspector.py)
- [KaosEghis/core/wait_engine.py](/E:/Kaos/KaosEghis/KaosEghis/core/wait_engine.py)

Responsibilities:

- locate UI targets
- inspect enabled/visible/text state
- wait on conditions without changing UI state

### Manual Explicit Write Tests

Modules:

- [KaosEghis/core/paste_test.py](/E:/Kaos/KaosEghis/KaosEghis/core/paste_test.py)
- [KaosEghis/core/write_test.py](/E:/Kaos/KaosEghis/KaosEghis/core/write_test.py)
- [KaosEghis/core/eghis_key_paste_test.py](/E:/Kaos/KaosEghis/KaosEghis/core/eghis_key_paste_test.py)

Responsibilities:

- explicit operator-triggered target tests
- narrow, test-only write methods
- logging of result/failure

These are not background automation engines.

### Stored Macro Automation

Modules:

- [KaosEghis/core/macro_runner.py](/E:/Kaos/KaosEghis/KaosEghis/core/macro_runner.py)
- [KaosEghis/core/safety_gate.py](/E:/Kaos/KaosEghis/KaosEghis/core/safety_gate.py)

Responsibilities:

- connector-gated run execution
- cancellation
- limited supported actions
- future EMR profile-aware resolution boundary

Current transition state:

- macros can now be bound to an EMR target profile
- dry run can report the resolved profile name
- actual click/send/paste target resolution is intentionally not switched over yet

### EMR Target Foundation

Modules:

- [KaosEghis/ui/tabs/emr_targets_page.py](/E:/Kaos/KaosEghis/KaosEghis/ui/tabs/emr_targets_page.py)
- [KaosEghis/db/repositories.py](/E:/Kaos/KaosEghis/KaosEghis/db/repositories.py)

Responsibilities:

- store named EMR target profiles
- store per-profile UI target definitions
- expose the active/default EMR profile for future macro runs
- keep credentials and secrets out of the profile model

## Current Automation Safety Posture

### Allowed

- read-only Eghis process/window detection
- read-only PostgreSQL reporting/polling
- dry-run macro validation
- explicit manual test actions initiated by the user

### Restricted

- real EMR automation is still deliberately limited
- not all stored macro actions are executable
- no broad unattended runner

### Not Present

- scheduler-driven production automation
- hidden background macro service
- generic recorder
- unconstrained mouse automation

## Connector Requirement

Real macro execution must pass the Eghis connector gate.

That means:

- Eghis must be discovered
- process and window identity must match
- connector validity must hold
- blocked states must stop execution

## Read-Only Database Automation

The same safety stance applies to PostgreSQL access:

- read-only only
- write-like SQL rejected
- unavailable driver handled safely
- results normalized before local persistence

## Completed

- process/window detection
- connector state model
- read-only UI inspection
- conditional wait engine
- manual target write tests
- real runner skeleton
- read-only Eghis PostgreSQL adapter foundation
- EMR target profile persistence for future macro targeting

## Removed or Avoided

- silent runtime fake data generation in production polling paths
- broad unsafe UI writing through unreviewed automation flows

## Maintenance Triggers

Update this document whenever:

- a manual write path is added or removed
- a macro action becomes really executable
- connector gate rules change
- new unattended automation is introduced
