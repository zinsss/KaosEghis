# KaosClinic Eghis Worker

Work primarily in this KaosEghis repository. Inspect existing architecture and
tests before editing. This is a Windows/PySide6 companion for Eghis EMR; never
exercise automation against live EMR or real patient data. Use synthetic test
fixtures.

Baseline checks:

- install: `python -m pip install -r requirements.txt`
- tests: `python -m pytest`
- run only when explicitly needed: `python main.py`

Create a task branch, avoid unrelated changes, never force-push, merge, or
deploy. Report cross-repository contracts using the KaosClinic handoff schema,
including PACS/Orders/Reception implications.

## Repository synchronization

Before repository work, confirm this is the registered H4 development clone and
record the starting branch, commit, upstream, and worktree status. Run
`git fetch --prune`, compare `HEAD` with its upstream, and run
`git pull --ff-only` only when the worktree is clean, the upstream is intended,
and the update is fast-forward-safe. Otherwise preserve all existing work and
report the blocker; never stash, discard, reset, rebase, or force-push it. This
preflight never authorizes access to or changes on a live clinic checkout. See
the central `/srv/projects/KaosClinic/orchestration/architecture/repository-sync-policy-v1.md`.

## Durable documentation

Before reporting a task complete, create or update Markdown for material ideas;
plan, scope, or acceptance changes; decisions and rationale; blockers, risks,
and durable follow-ups; and cross-project dependencies or operational impact.
Use `docs/plans/<topic>.md` for active project plans and
`docs/decisions/<topic>.md` for settled project decisions, updating an existing
topic document instead of duplicating it.

As applicable, include status and date, affected projects, context, the original
plan and plan delta, rationale, impact, dependencies, safety constraints,
evidence, open questions, next action, and a dated revision history. Never record
credentials, patient information, live clinical payloads, or unredacted
production logs. The structured handoff must name changed Markdown documents or
explain why none was needed. See the central
`/srv/projects/KaosClinic/orchestration/architecture/documentation-policy-v1.md`.
