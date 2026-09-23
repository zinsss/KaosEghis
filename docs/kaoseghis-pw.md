# KaosEghis-pw

Last updated: 2026-08-08

## Purpose

KaosEghis-pw is a hidden infrastructure module for credentials inside the KaosEghis
ecosystem.

It is not intended to become:

- a standalone password manager
- a visible workflow tab
- a general browser-login replacement
- a consumer password vault for unrelated personal accounts

Its purpose is narrower:

- unlock one local credential vault with a master password
- provide credential access to KaosEghis internal service surfaces
- provide a guarded manual credential typing popup for external applications

## Product Position

KaosEghis-pw is an infrastructure module, not a daily-use workflow tab.

It should stay:

- hidden from normal top-level navigation
- available at startup through an unlock prompt
- available later through a complex global hotkey

It serves:

- KaosEghis embedded/internal service surfaces
- explicit manual credential entry for external apps

It does not own:

- PACS business logic
- EMR macro logic
- vaccine workflow
- general workspace content

## Intended Runtime Model

### Startup

On KaosEghis startup:

1. show a master-password prompt once
2. if the password is accepted:
   - unlock the credential vault in memory
   - allow internal credential-backed surfaces to use saved credentials
3. if the prompt is cancelled or the password is wrong:
   - KaosEghis still opens
   - credential-backed actions remain locked
   - do not keep nagging automatically

### Locked State

When locked:

- the rest of KaosEghis remains usable
- only credential-backed actions are blocked
- internal services fall back to manual login
- no stored secrets are typed or injected

### Unlock Retry

If the operator presses the KaosEghis-pw global hotkey while locked:

- show the master-password prompt again

If the operator presses the same hotkey while unlocked:

- open the credential action popup

## UI Surface Rules

### No Top-Level Tab

KaosEghis-pw should not add:

- a top-level tab
- a visible launcher column entry
- a normal front-surface dashboard

### Hidden Popup

The normal interactive surface is a popup opened only by a complex global hotkey.

The popup may include:

- service/app selector
- action selector:
  - type ID
  - type password
  - type ID + password
- manage/edit credentials action
- lock/unlock status

## Internal vs External Behavior

### Internal Services Inside KaosEghis

For services rendered inside KaosEghis, KaosEghis-pw may support more automatic
behavior after unlock.

Examples:

- fill ID
- fill password
- fill both

This applies only to KaosEghis-controlled surfaces and should still be triggered by
an explicit operator action.

### External Applications

For external desktop apps or websites outside KaosEghis:

- do not auto-fill silently
- require explicit operator action
- type into the current foreground window only
- abort if focus/window state is not what the operator expects

## Storage Model

### Allowed

Persist locally:

- service name
- username or ID
- target metadata
- encrypted credential blob
- non-secret service notes

### Not Allowed

Do not store:

- master password
- plaintext passwords
- copied password clipboard history
- secrets in SQLite plaintext
- secrets in logs

## Security Model

### Master Password

- prompt on startup once
- never store it
- use it only to unlock the local encrypted vault
- if locked again, require prompt again

### Clipboard

Password handling should default to typing, not clipboard paste.

Rules:

- do not leave passwords on the clipboard
- avoid clipboard-based credential flow by default
- only consider clipboard for credentials if a later exceptional case demands it

### Logging

Do not log:

- passwords
- decrypted secrets
- typed secret contents
- full target field contents

Allowed operational logs:

- locked/unlocked
- service selected
- action attempted
- success/failure category

## Recommended Backend

Preferred model:

- encrypted local vault under KaosEghis data directory
- key derived from master password

Credential references for other modules should flow through KaosEghis-pw rather than
duplicating password storage in each module.

## First Implementation Slice

1. startup master-password prompt
2. locked/unlocked runtime state
3. local encrypted credential entry model
4. hidden popup on global hotkey
5. manual external typing actions:
   - type ID
   - type password
   - type ID + password
6. no visible tab
7. no embedded autofill yet

## Later Expansion

After the foundation works:

1. internal embedded-service autofill helpers
2. manual lock command
3. optional idle relock
4. per-service target typing metadata

## Explicit Non-Goals

KaosEghis-pw should not become:

- Bitwarden replacement
- browser extension replacement
- passkey manager
- multi-user enterprise credential platform
- cloud-synced password system

It is a local infrastructure helper for KaosEghis only.
