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

