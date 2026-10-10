# Windows Offscreen UI Tests

The 26 repeated vaccine UI failures were caused by the test font environment,
not a confirmed production layout defect. On this Windows/PySide6 installation,
`QT_QPA_PLATFORM=offscreen` exposed zero system fonts. Requested Malgun Gothic
and default UI text were measured/rendered as missing-glyph boxes. That distorted
title fitting, pill ink coverage and shortcut button size hints.

Loading the installed regular/bold Malgun Gothic and Segoe UI fonts made all
284 tests in `test_vaccine_label.py` and `test_vaccine_shortcuts.py` pass without
changing either test's assertions or any production UI/printing code.

`tests/conftest.py` now registers those four Windows font files once per offscreen
test session and retains the QApplication reference for that session. Missing
fonts fail setup explicitly instead of silently exercising substitute boxes.
Other platforms and normal Windows display mode are unchanged. No font files are
copied into the repository or downloaded.

During the first broad verification, a native Windows breakpoint occurred during
worker-thread garbage collection. Offscreen teardown now collects widget cycles and
drains deferred deletion on the test's main thread, before another test starts a
mocked database worker. This is test lifecycle cleanup, not a production reader
or Qt runtime change.

`test_qt_test_environment.py` verifies both real font families and weights,
proportional Latin glyph metrics, and Korean glyph support for label text.
Existing pixel bounds, equal title sizes, pill contrast, divider/detail coverage
and shortcut layout assertions remain unchanged.

Run with `QT_QPA_PLATFORM=offscreen`, a temporary `KAOSEGHIS_DATA_DIR`, and the
repository's existing mocked database/network/desktop guards. Tests do not submit
print jobs, access EMR, restart the app or change patient records.

## Verification: 2026-10-10

- Original label/shortcut assertions with installed fonts: **284 passed**.
- All Vaccine tests plus four font-environment regressions: **851 passed**.
- Final full isolated suite with main-thread teardown: **5,002 passed** in
  617.58 seconds, with no failures or native process interruption.
- Six synthetic 203-DPI label previews were visually checked for Korean text,
  outlined/filled pills, dividers and patient-detail placement. No physical
  printer was used and no preview was committed.

Commands: `python -m pytest tests/test_qt_test_environment.py tests/test_vaccine*.py -q`
(expand the wildcard in PowerShell), and `python -m pytest -q --tb=short`.
The main-thread collection adds test-suite overhead only; application startup,
EMR reads, printer behavior and runtime garbage collection are unchanged.
