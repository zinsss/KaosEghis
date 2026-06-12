# KaosEghis

KaosEghis is a local Windows companion app for Eghis EMR. This scaffold starts the project in Python with PySide6, SQLite-backed local storage, and safe placeholder modules for future EMR automation.

The current app is only an initial shell. It does not perform real EMR automation, does not store passwords in SQLite, does not include patient examples, and does not implement cloud sync, a macro recorder, or an installer.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Current UI

- Eghis Assist
- KaosGDD web tab loading `https://kaosgdd.net`
- Settings

## Safe Stubs

The automation, macro execution, UIA targeting, clipboard, credential, scheduler, printer, and database modules are prepared as safe local foundations. Dangerous macro actions currently return blocked results or raise `NotImplementedError`.
