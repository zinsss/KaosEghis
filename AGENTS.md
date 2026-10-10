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
deploy. A concise result is sufficient for routine local work. Use the
KaosClinic handoff schema only when PACS/Orders/Reception interfaces,
authentication, schemas, migrations, or deployment ordering actually change.

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

Follow the central documentation policy. Routine bug fixes, small features,
local refactors, tests, and completed same-task plans need no new Markdown.
Document only durable architecture, cross-project contracts, operational or
safety decisions, migrations, and unresolved follow-up. Never record
credentials, patient information, live clinical payloads, or unredacted logs.
