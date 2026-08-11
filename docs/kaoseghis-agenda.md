# KaosEghis Agenda and Supplies

## Purpose

The Launcher page presents compact daily context beside its macro lists:

- **Agenda** shows KaosGDD calendar events and tasks.
- **Supplies** shows supply tasks owned by KaosGDD.

KaosEghis is a presentation and operator surface only. It does not copy calendar,
task, or supplies records into the KaosEghis SQLite database.

## Ownership

```text
KaosEghis Launcher
        |
        | UTF-8 JSON over the private network
        v
KaosGDD Brain
        |
        v
Radicale calendar and VTODO collections
```

KaosGDD remains authoritative for:

- calendar events;
- normal tasks;
- the `Kaos_Supplies` VTODO collection;
- task completion and reactivation state.

## API Contract

Agenda uses:

- `GET /api/calendar/bootstrap`
- `POST /api/calendar/tasks`
- `PUT /api/calendar/tasks`

Supplies uses:

- `GET /api/supplies?mode=active|done`
- `POST /api/supplies`
- `POST /api/supplies/{id}/done`
- `POST /api/supplies/{id}/active`
- `DELETE /api/supplies/{id}`

The Qt network client sends `X-Forwarded-Host: kaosgdd.net` so a direct private
Brain connection uses the main KaosGDD profile.

## Connection

The default Brain endpoint is:

```text
http://100.94.208.16:8092
```

Set `KAOSGDD_BRAIN_URL` before starting KaosEghis to override it. The URL should
point to the KaosGDD Brain service, not directly to Radicale.

## Runtime Behavior

- Launcher construction does not perform a blocking HTTP request.
- Agenda loads asynchronously when the Launcher page is activated.
- Supplies loads when the operator opens the Supplies subpage.
- Network errors stay inside the panel and do not block macros or app startup.
- KaosEghis does not store a second offline copy of KaosGDD data.

## Future Work

- Add event editing only if the compact launcher workflow needs it.
- Add a visible configurable Brain URL after the service settings are
  consolidated.
- Consider recurrence expansion if KaosGDD exposes expanded occurrences in its
  API contract.
