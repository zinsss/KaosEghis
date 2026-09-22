import json
import sys
from types import SimpleNamespace

import pytest

from KaosEghis.core import startup_diagnostics as module


def test_startup_trace_rearms_per_phase_and_closes_before_reusing_file(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(module.faulthandler, "dump_traceback_later", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(module.faulthandler, "cancel_dump_traceback_later", lambda: calls.append("cancel"))
    path = tmp_path / "startup-diagnostics.log"
    trace = module.StartupDiagnostics(path)
    trace.stage("Building workspace...")
    stream = calls[0][1]["file"]
    assert calls[0][0] == (10,)
    assert calls[0][1]["repeat"] is False
    assert calls[0][1]["exit"] is False
    assert not stream.closed
    trace.stage("Starting runtime services...")
    assert calls[1] == "cancel"
    trace.close("ready")
    trace.close()
    assert calls[-1] == "cancel"
    assert stream.closed
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [record.get("stage", record.get("outcome")) for record in records] == [
        "Building workspace...", "Starting runtime services...", "ready",
    ]
    path.unlink()


def test_startup_trace_retains_previous_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(module.faulthandler, "dump_traceback_later", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.faulthandler, "cancel_dump_traceback_later", lambda: None)
    path = tmp_path / "startup-diagnostics.log"
    previous = tmp_path / "startup-diagnostics.previous.log"
    path.write_text("last failed attempt", encoding="utf-8")
    previous.write_text("older attempt", encoding="utf-8")
    trace = module.StartupDiagnostics(path)
    trace.stage("Building workspace...")
    trace.close("ready")
    assert previous.read_text(encoding="utf-8") == "last failed attempt"
    assert "older attempt" not in path.read_text(encoding="utf-8")


def test_unavailable_diagnostic_path_does_not_block_startup(tmp_path, monkeypatch):
    monkeypatch.setattr(module.faulthandler, "dump_traceback_later", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no file")))
    trace = module.StartupDiagnostics(tmp_path / "missing" / "startup.log")
    trace.stage("Building workspace...")
    trace.close("ready")


def test_unavailable_watchdog_still_records_phases(tmp_path, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("watchdog unavailable")

    monkeypatch.setattr(module.faulthandler, "dump_traceback_later", unavailable)
    path = tmp_path / "startup-diagnostics.log"
    trace = module.StartupDiagnostics(path)
    trace.stage("Building workspace...")
    trace.close("ready")
    assert "ready" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("fail_build", [False, True])
def test_app_closes_startup_trace_before_password_prompt_or_on_failure(tmp_path, monkeypatch, fail_build):
    from KaosEghis import app as app_module
    from KaosEghis.db import database

    path = tmp_path / "startup-diagnostics.log"
    trace = module.StartupDiagnostics(path)
    events = []
    monkeypatch.setattr(module.faulthandler, "dump_traceback_later", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.faulthandler, "cancel_dump_traceback_later", lambda: None)
    monkeypatch.setattr(app_module, "StartupDiagnostics", lambda: trace)
    application = SimpleNamespace(processEvents=lambda: None, exec=lambda: 0)
    monkeypatch.setattr(app_module, "QApplication", SimpleNamespace(instance=lambda: application))
    monkeypatch.setattr(app_module, "apply_nord_theme", lambda _app: None)
    monkeypatch.setattr(app_module, "StartupSplash", lambda: SimpleNamespace(
        show=lambda: None, set_status=lambda message: events.append(message),
        finish=lambda _window: None, close=lambda: events.append("splash_closed"),
    ))
    monkeypatch.setattr(database, "initialize_database", lambda: None)
    monkeypatch.setitem(sys.modules, "KaosEghis.service.kaospacs_api", SimpleNamespace(
        start_server_in_thread=lambda: None,
    ))

    def prompt():
        assert trace._stream is None
        events.append("password_prompt")

    def build():
        if fail_build:
            raise RuntimeError("sensitive error details")
        return SimpleNamespace(
            initialize_runtime_services=lambda: None, show=lambda: None,
            prompt_startup_master_password=prompt,
        )

    monkeypatch.setitem(sys.modules, "KaosEghis.ui.main_window", SimpleNamespace(MainWindow=build))
    if fail_build:
        with pytest.raises(RuntimeError):
            app_module.run()
        assert "password_prompt" not in events
        assert "splash_closed" in events
    else:
        assert app_module.run() == 0
        assert events[-1] == "password_prompt"
    assert trace._stream is None
    text = path.read_text(encoding="utf-8")
    records = [json.loads(line) for line in text.splitlines()]
    assert records[-1]["outcome"] == ("failed:RuntimeError" if fail_build else "ready")
    assert "sensitive" not in text
