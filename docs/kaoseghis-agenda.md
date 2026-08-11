# KaosEghis Agenda and Supplies

## Purpose

The Launcher page embeds KaosGDD's compact Agenda and Supplies web surface.
KaosEghis does not reproduce KaosGDD calendar, task, or supplies behavior.

The embedded page contains three KaosGDD-owned pages:

- **Calendar**: default month view and selected-day events;
- **Tasks**: Active/Done filtering, ordering, add/edit/delete, and
  complete/reopen actions;
- **Supplies**: the existing KaosGDD supply workflow.

## Internal Architecture

```text
KaosEghis Launcher QWebEngineView
        |
        | private HTTP
        v
KaosGDD internal embed listener :8090
        |
        v
KaosGDD Brain and calendar adapters
        |
        v
Radicale calendar and VTODO collections
```

KaosGDD remains authoritative for presentation, calendar events, normal tasks,
and the `Kaos_Supplies` collection. KaosEghis stores none of these records in
its SQLite database.

## Internal URL

The default URL is:

```text
http://100.94.208.16:8090/embed/agenda-supplies
```

This endpoint is intended for the private network only. KaosEghis does not use
the public `kaosgdd.net` hostname for the embedded Launcher surface.

Set `KAOSGDD_EMBED_URL` before starting KaosEghis to override the endpoint.
The override must point to the internal KaosGDD embed route.

## Runtime Behavior

- The web view does not load during widget construction.
- KaosEghis loads it asynchronously when the Launcher page is activated.
- Reload always returns to the configured embed URL.
- Open in Browser provides an explicit fallback.
- If Qt WebEngine is unavailable, KaosEghis shows the internal URL and keeps
  the external-browser fallback available.
- A failed page load does not block EMR connection or macro execution.

## Security Boundary

- No KaosGDD token, password, or cookie is placed in the URL.
- KaosEghis does not proxy or log Agenda/Supplies payloads.
- KaosGDD Brain and Radicale remain private backend services.
- Access control for the internal listener is enforced by the KaosGDD host,
  Tailscale policy, and host firewall.
