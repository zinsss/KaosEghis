# KaosEghis Macro

Last updated: 2026-06-30

## Purpose

The macro subsystem defines, validates, and eventually executes structured automation steps for KaosEghis workflows.

Today, the project supports:

- macro item persistence
- macro step persistence
- dry-run rendering
- guarded real runner skeleton
- cancellation support
- EMR target profile foundation for future target resolution
- macro-to-EMR-profile binding

It does not yet support broad real UI automation execution across the stored macro model.

## Current Data Model

Relevant repositories:

- [KaosEghis/db/repositories.py](/E:/Kaos/KaosEghis/KaosEghis/db/repositories.py)

Current macro-related tables:

- `items`
- `macro_steps`
- `macro_runs`
- `emr_target_profiles`
- `emr_ui_targets`

Macro items now also carry:

- `emr_target_profile_id` nullable

Meaning:

- when set, the macro is configured against that EMR target profile
- when null, the macro falls back to the default EMR target profile

Supported item types:

- `clipboard`
- `randomized_clipboard`
- `macro`
- `workflow`

## Macro Definition Structure

Current step fields:

- `step_order`
- `action`
- `target_id`
- `value`
- `timeout_seconds`
- `retries`

Current target binding behavior:

- `target_id` remains the stored step field name
- for profile-bound macros, the editor now offers `emr_ui_targets.target_key` values from the selected EMR profile
- legacy `ui_targets` are still tolerated for compatibility during dry-run validation and current execution

Allowed stored actions in the model:

- `check_process`
- `wait_for_target`
- `read_text_uia`
- `type_text_keyboard`
- `type_text_clipboard`
- `set_text_uia`
- `mouse_click`
- `wait_ms`

Important:

- the storage model is intentionally broader than the currently allowed real execution engine
- some actions exist only as definitions or dry-run-visible intent right now

## Current UI Surfaces

Daily-use macro access:

- [KaosEghis/ui/tabs/kaoseghis_tab.py](/E:/Kaos/KaosEghis/KaosEghis/ui/tabs/kaoseghis_tab.py)
- shows macro list
- supports dry run and manual run
- shows the resolved EMR profile name for each macro

EMR targeting foundation:

- [KaosEghis/ui/tabs/emr_targets_page.py](/E:/Kaos/KaosEghis/KaosEghis/ui/tabs/emr_targets_page.py)
- lives under `KaosEghis -> EMR`
- stores profile-level process/window identity and a profile-scoped UI target library

Editor behavior:

- the macro editor exposes an EMR profile selector
- the step editor exposes a target selector populated from the selected profile's EMR UI target keys

Configuration/editing surfaces:

- historically handled through macro-related builder/configuration UI work
- not all builder surfaces are currently visible in the simplified plugin layout

## Dry Run

Current dry-run behavior:

- validates referenced `target_id`
- renders planned steps
- never performs a real action
- reports blocked state when a UI target is missing

Dry run remains the safe review path for stored macros.

Dry run now also shows:

- resolved EMR profile name
- planned target keys as stored in each step

## Real Runner State

Relevant modules:

- [KaosEghis/core/macro_runner.py](/E:/Kaos/KaosEghis/KaosEghis/core/macro_runner.py)
- [KaosEghis/core/macro_models.py](/E:/Kaos/KaosEghis/KaosEghis/core/macro_models.py)

Current real runner scope:

- sequential execution
- connector gate required
- cancellation supported
- supported runner actions are intentionally narrow

Current real runner actions are more limited than the stored macro action vocabulary.

## Safety Rules

Every real execution path must pass connector readiness checks.

Current non-negotiables:

- no hidden EMR execution
- stop on first failure
- cancellation must interrupt the run
- dry-run-only actions must not silently turn real

## Completed

- macro CRUD foundation
- macro step CRUD foundation
- dry-run validation and rendering
- guarded runner skeleton
- cancellation handling
- EMR target profile and EMR UI target local persistence

## Not Done

- full stored macro execution for all defined step types
- recorder
- scheduler-driven macro execution
- broad UIA/mouse-driven step support

## Maintenance Triggers

Update this document whenever:

- a macro action is added or removed
- real runner scope changes
- dry-run format changes materially
- macro UI moves tabs or changes responsibility
