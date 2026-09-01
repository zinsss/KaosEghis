# KaosEghis Agenda and Supplies (Removed from Launcher)

## Purpose

The Launcher previously embedded KaosGDD's compact Agenda and Supplies web surface.
That embedded surface was removed from Launcher after KaosGDD changed and the daily
KaosEghis workflow no longer required it there.

The released Launcher now keeps three equal-width launcher lists and opens SOCL in an
independently movable window with separate `S` and `O` tabs. KaosEghis still does not
reproduce or store KaosGDD calendar, task, or supplies data.

The removed embedded page contained three KaosGDD-owned pages:

- **Calendar**: default month view and selected-day events;
- **Tasks**: Active/Done filtering, ordering, add/edit/delete, and
  complete/reopen actions;
- **Supplies**: the existing KaosGDD supply workflow.

## Current Architecture

```text
KaosEghis Launcher -> independently movable local SOCL S/O window

KaosGDD -> its own calendar, task, and supplies surfaces
```

KaosGDD remains authoritative for presentation, calendar events, normal tasks,
and the `Kaos_Supplies` collection. KaosEghis stores none of these records in
its SQLite database.

## Removal Behavior

- The launcher-only web panel module and its dedicated tests were removed.
- Opening Launcher performs no KaosGDD Agenda/Supplies network request.
- `KAOSGDD_EMBED_URL` is no longer read by KaosEghis.
- KaosGDD changes or availability cannot block Launcher or macro execution.

## Security Boundary

- No KaosGDD token, password, or cookie is placed in the URL.
- KaosEghis does not proxy or log Agenda/Supplies payloads.
- KaosGDD Brain and Radicale remain private backend services.
- Access control for the internal listener is enforced by the KaosGDD host,
  Tailscale policy, and host firewall.
