# KaosEghis Launcher Collections Plan

Last updated: 2026-08-03

## Purpose

This document defines the next launcher evolution for KaosEghis.

The launcher should support two visible item types:

- simple macro
- macro collection

A simple macro runs immediately.
A macro collection opens a chooser or context menu so the operator can pick one
macro from a related group.

This plan is intentionally split into:

- apply now
- planned for future

so we can implement the safe version first without overcomplicating daily use.

## Current State

Today, the launcher displays executable macros directly in its three columns and
double-click runs the selected macro immediately.

Current launcher strengths:

- fast daily access
- saved cross-column ordering
- drag/drop placement
- EMR connection control in the launcher itself
- quick notes beside the launcher columns

Current launcher gap:

- there is no grouped launcher behavior yet
- one visible launcher item always maps to one direct action
- related workflows can clutter the launcher columns

## Apply Now

Status: first version implemented

### Core Rule

The launcher now supports two launcher entry behaviors:

1. simple macro
   - double-click runs the macro directly

2. macro collection
   - double-click opens a chooser dialog
   - the operator selects one macro from the collection
   - the selected macro then runs or dry-runs

### Default Launcher Behavior

- executable macros appear in the launcher by default
- non-executable macros do not appear in the launcher by default
- the launcher remains the daily-use execution surface
- the Builder remains the authoring/configuration surface

### Drag and Drop Rules

#### Macro -> empty space

- reorder within the same launcher column
- or move to another launcher column

#### Macro -> macro

- show confirmation dialog:
  - `Create a collection from these macros?`
- if confirmed, ask for collection name
- if the name dialog is cancelled, do nothing
- if confirmed, replace the target launcher entry with a new collection entry
- both macros become members of that collection

#### Macro -> collection

- show confirmation dialog:
  - `Add this macro to collection '<collection name>'?`
- if confirmed, add the macro to that collection
- if cancelled, do nothing

#### Collection -> empty space

- reorder collection entry normally
- or move it between launcher columns

#### Collection -> macro

- not supported in the first implementation

#### Collection -> collection

- not supported in the first implementation

### Collection Membership Rule

Current rule:

one macro may belong to only one launcher context:

- direct launcher item
- or one collection

It must not exist in multiple collections yet.

This keeps the first version predictable and reversible.

### Collection UI Behavior

#### Double-click

Double-clicking a collection opens a chooser dialog.

The chooser should:

- show the collection name
- list macros in saved order
- allow `Run`
- allow `Dry run`
- allow `Cancel`

#### Right-click

Right-clicking a collection opens a context menu listing its member macros
directly.

Recommended structure:

- macro item 1
- macro item 2
- macro item 3
- separator
- `Edit collection...`

Clicking a macro in this context menu runs that macro immediately without
opening the chooser dialog.

### Collection Editing

The first implementation now includes a dedicated edit dialog for collections.

The editor should allow:

- rename collection
- reorder collection members by drag/drop
- remove a macro from the collection

Recommended member context menu:

- `Remove from collection`
- `Run`
- `Dry run`
- `Open in Builder` optional

### Reverse / Undo Behavior

Removing one macro from a collection:

- makes that macro a simple launcher item again
- restores it in the same launcher column
- places it just below the collection by default

Unpacking a collection:

- deletes the collection wrapper only
- restores all member macros as simple launcher items
- preserves their saved order

Automatic collection collapse:

- 2 or more members = valid collection
- 1 member left = auto-collapse back to simple macro
- 0 members left = remove the collection entirely

### Data Model Direction

Recommended new tables:

- `launcher_entries`
- `macro_collections`
- `macro_collection_members`

Recommended launcher entry types:

- `macro`
- `macro_collection`

This should be implemented as a proper launcher layer rather than overloading the
macro item table further.

### Apply-Now Safety Goals

- never create a collection silently
- always confirm drag-to-collection operations
- always ask for collection name on macro-to-macro merge
- cancel must restore the original launcher state cleanly
- launcher remains manual only; no background execution change

## Planned for Future

These are intentionally out of scope for the first collection milestone.

### Multiple Collection Membership

Future possibility:

- one macro may appear in multiple collections
- one macro may also remain directly visible in the launcher while belonging to a collection

Not now, because it introduces ambiguity around:

- move vs copy
- delete vs remove reference
- rename behavior
- ordering in multiple places
- enable/disable behavior across multiple appearances

### Nested Collections

Not planned for the first version.

- collection inside collection
- collection dropped onto collection to merge

This is intentionally blocked at first.

### Collection Templates / Smart Collections

Possible future ideas:

- auto-generated collections
- collections based on macro tags
- collections by EMR profile
- collections by specialty or workflow

These should not be attempted before manual collections are stable.

### Shared Macro Appearance Across Surfaces

Future possibility:

- the same macro could appear in Launcher
- in one or more collections
- and in other quick-access surfaces

This should only happen after the launcher ownership model is changed into a
reference model.

### Advanced Context Menus

Possible later additions:

- dry-run submenu directly in launcher
- duplicate macro from collection
- move macro between collections
- convert collection back to simple launcher items without opening editor

### Search / Filter in Collection Dialog

Not needed initially.

Only add search if collections become meaningfully large.

## Recommended Implementation Order

### Phase 1

Implemented

- add launcher entry and collection data model
- migrate existing executable launcher macros into direct launcher entries
- preserve current direct-run behavior for simple macro entries

### Phase 2

Implemented

- support macro-to-macro collection creation with confirmation and naming
- support macro-to-collection add with confirmation

### Phase 3

Implemented first version

- add collection chooser dialog
- add collection right-click direct-run context menu

### Phase 4

Partially implemented

- add collection edit dialog
- add unpack and remove-from-collection behaviors
- add auto-collapse when only one member remains

## Recommended UX Summary

Simple macro:

- double-click = run
- right-click = macro actions

Collection:

- double-click = open chooser
- right-click = show member macro run menu
- edit separately through collection editor

Drag/drop:

- onto empty space = reorder/move
- macro onto macro = confirm collection creation, then ask name
- macro onto collection = confirm add to collection

## Documentation Rule

When launcher collections are:

- added
- implemented
- renamed
- expanded
- deferred

the following docs should be updated together:

- `docs/kaoseghis-launcher-plan.md`
- `docs/kaoseghis-macro.md`
- `docs/kaoseghis-design.md`
- `docs/kaoseghis-plans.md`
