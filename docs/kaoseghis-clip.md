# KaosEghis Clip

Last updated: 2026-07-21

## Purpose

This document tracks the clipboard/snippet direction for KaosEghis.

## Current State

Visible surfaces:

- `Macros -> MacroTexts` manages reusable fixed and randomized text
- `Macros -> Launcher -> Comments` provides one-action clipboard copy

Current behavior:

- fixed MacroText copies its complete body, including multiple lines
- randomized MacroText stores one option per line and copies one option per use
- double-clicking a MacroText in `Comments` copies only; it does not paste or run EMR automation
- macro `preset_text` steps select and reuse the same saved MacroText

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
- MacroText add/edit/delete UI
- fixed and randomized text persistence through `clipboard_variants`
- direct Launcher copy from the `Comments` column
- MacroText selection for macro `preset_text` steps

What does not exist yet:

- searchable snippet management UI
- snippet tagging/favorites/history persistence
- clipboard history

## Planned Destination

The reusable text foundation now lives inside KaosEghis rather than a standalone
KaosClip application. Future search, tags, favorites, and history should extend the
MacroTexts/Comments workflow rather than create a second writable text store.

## Completed

- placeholder tab exists
- clipboard utility foundation exists
- MacroTexts can be copied directly or reused by macros
- Launcher category `Medical Documents` was renamed to `Comments`

## Removed or Superseded

- standalone KaosClip app direction: superseded

## Maintenance Triggers

Update this document whenever:

- KaosClip moves from placeholder to real workflow
- its hosting location changes
- snippet/history persistence is added
- the standalone-vs-plugin decision changes
