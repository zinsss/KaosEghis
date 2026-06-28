# KaosEghis Clip

Last updated: 2026-06-28

## Purpose

This document tracks the clipboard/snippet direction for KaosEghis.

## Current State

Visible surface:

- [KaosEghis/ui/tabs/kaosclip_tab.py](/E:/Kaos/KaosEghis/KaosEghis/ui/tabs/kaosclip_tab.py)

Current UI state:

- placeholder only
- read-only descriptive text
- no production organizer workflow

Current placeholder scope text:

- clipboard history
- favorites
- snippets
- search
- randomized clipboard presets

## Important Direction Change

Prior direction:

- KaosClip as a standalone app concept

Current direction:

- KaosClip will be redesigned as part of the KaosEghis plugin ecosystem
- it should be treated as a KaosEghis capability, not a separate product boundary

This is now the controlling design assumption for future work.

## Existing Clipboard Foundations

Relevant modules:

- [KaosEghis/core/clipboard_service.py](/E:/Kaos/KaosEghis/KaosEghis/core/clipboard_service.py)
- [KaosEghis/core/paste_test.py](/E:/Kaos/KaosEghis/KaosEghis/core/paste_test.py)

What exists already:

- clipboard copy utility support
- clipboard restoration handling in manual test paths
- stored macro model support for clipboard-related actions

What does not exist yet:

- end-user clipboard organizer
- searchable snippet management UI
- snippet tagging/favorites/history persistence
- plugin-integrated clip workflow

## Planned Destination

KaosClip should likely become one of:

- a plugin panel under `Plugins`
- a richer workflow integrated with KaosEghis daily-use actions
- a hybrid snippet/preset helper for macros and PACS/flu workflows

The exact final placement is not fixed, but standalone app scope is no longer the plan.

## Completed

- placeholder tab exists
- clipboard utility foundation exists

## Removed or Superseded

- standalone KaosClip app direction: superseded

## Maintenance Triggers

Update this document whenever:

- KaosClip moves from placeholder to real workflow
- its hosting location changes
- snippet/history persistence is added
- the standalone-vs-plugin decision changes
