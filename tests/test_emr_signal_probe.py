from dataclasses import replace
import queue
import time
from types import SimpleNamespace

import pytest

from KaosEghis.core import emr_signal_probe as probe


def state():
    return SimpleNamespace(status="yellow", pid=42, window_handle=100, main_window_handle=101)


class Reader:
    def __init__(self):
        self.active = True
        self.modifiers = False
        self.chart = "001234"
        self.discovery_count = 0
        self.buttons = (("F6 button", 106), ("F7 button", 107))
        self.live_buttons = True

    def keyboard_context(self, scope):
        return self.active

    def modifiers_down(self):
        return self.modifiers

    def button_at(self, snapshot, point):
        if self.active:
            return {6: "F6 button", 7: "F7 button"}.get(point[0])

    def treatment_ready(self, scope):
        return self.active

    def discover_buttons(self, scope):
        self.discovery_count += 1
        return self.buttons

    def buttons_live(self, scope, buttons):
        return self.live_buttons

    def chart_number(self, scope):
        return self.chart


@pytest.fixture
def capture():
    output = queue.Queue(maxsize=64)
    reader = Reader()
    current_state = state()
    clock = [10.1]
    result = probe.EmrSignalCapture(reader, output, lambda: current_state, lambda: clock[0])
    result.snapshot = probe.SignalSnapshot(
        probe.connected_scope(current_state), reader.buttons, "001234", 10.0,
    )
    result.test_clock = clock
    result.test_state = current_state
    return result


def key(capture, vk=0x76, message=0x100, flags=0):
    return capture.keyboard_event(message, SimpleNamespace(vkCode=vk, flags=flags))


def mouse(capture, x=7, message=0x201, flags=0):
    return capture.mouse_event(message, SimpleNamespace(pt=SimpleNamespace(x=x, y=1), flags=flags))


@pytest.mark.parametrize("vk,source", [(0x75, "F6"), (0x76, "F7")])
def test_keyboard_reports_source_and_pre_action_snapshot(capture, vk, source):
    assert key(capture, vk) is True
    capture.snapshot = replace(capture.snapshot, chart_no="9999")
    observation = capture.output.get_nowait()
    assert observation.source == source
    assert observation.chart_no == "001234"
    assert observation.age_ms == 100
    assert "snapshot 100 ms" in observation.status_text()
    assert "001234" not in repr(observation)


@pytest.mark.parametrize("x,source", [(6, "F6 button"), (7, "F7 button")])
def test_button_requires_matching_press_and_release(capture, x, source):
    assert mouse(capture, x) is True
    assert capture.output.empty()
    assert mouse(capture, x, 0x202) is True
    observation = capture.output.get_nowait()
    assert observation.source == source
    assert observation.chart_no == "001234"


@pytest.mark.parametrize("release_x", [0, 6])
def test_drag_off_button_is_not_a_button_signal(capture, release_x):
    mouse(capture)
    mouse(capture, release_x, 0x202)
    assert capture.output.empty()


def test_release_without_press_is_ignored(capture):
    mouse(capture, message=0x202)
    assert capture.output.empty()


def test_key_repeat_is_coalesced_but_separate_presses_are_visible(capture):
    key(capture)
    key(capture)
    key(capture, message=0x101)
    key(capture)
    assert capture.output.qsize() == 2


@pytest.mark.parametrize("kind", ["other_app", "claim_page", "modal", "modifier", "disconnected", "restart", "stopped"])
def test_unsafe_keyboard_context_does_not_emit(capture, kind):
    if kind in {"other_app", "claim_page", "modal"}:
        capture.reader.active = False
    elif kind == "modifier":
        capture.reader.modifiers = True
    elif kind == "disconnected":
        capture.test_state.status = "red"
    elif kind == "restart":
        capture.test_state.pid = 43
    else:
        capture.enabled = False
    assert key(capture) is True
    assert capture.output.empty()


def test_injected_input_and_unrelated_keys_or_mouse_moves_are_ignored(capture):
    assert key(capture, flags=0x10) is True
    assert key(capture, vk=0x41) is True
    assert mouse(capture, flags=1) is True
    assert mouse(capture, message=0x200) is True
    assert mouse(capture, message=0x204) is True
    assert capture.output.empty()


@pytest.mark.parametrize("age", [0.751, 5.0, -0.1])
def test_stale_or_invalid_snapshot_never_shows_cached_patient(capture, age):
    capture.test_clock[0] = 10.0 + age
    key(capture)
    observation = capture.output.get_nowait()
    assert not observation.chart_no
    assert "Chart unavailable" in observation.status_text()
    assert "001234" not in observation.status_text()


@pytest.mark.parametrize("change", ["held", "patient"])
def test_button_long_hold_or_patient_change_invalidates_identity(capture, change):
    mouse(capture)
    if change == "held":
        capture.test_clock[0] += 1
    else:
        capture.snapshot = replace(capture.snapshot, chart_no="9999")
    mouse(capture, message=0x202)
    assert capture.output.get_nowait().chart_no == ""


def test_full_queue_and_reader_errors_still_pass_input_through(capture):
    for _ in range(64):
        capture.output.put_nowait("test")
    assert key(capture) is True
    assert mouse(capture) is True
    assert mouse(capture, message=0x202) is True
    assert capture.dropped_count == 2
    capture.reader.keyboard_context = lambda _scope: 1 / 0
    key(capture, message=0x101)
    assert key(capture) is True


def test_hook_does_not_read_chart_or_resolve_uia(capture):
    capture.reader.chart_number = lambda _scope: pytest.fail("read from hook")
    capture.reader.discover_buttons = lambda _scope: pytest.fail("UIA from hook")
    key(capture)
    mouse(capture)
    mouse(capture, message=0x202)
    assert capture.output.qsize() == 2


def test_sampler_caches_buttons_but_rereads_chart_and_recaches_after_restart():
    reader = Reader()
    current_state = state()
    sampler = probe.EmrSignalSampler(reader, lambda: current_state, lambda: 10)
    assert sampler.sample().chart_no == "001234"
    reader.chart = "9999"
    assert sampler.sample().chart_no == "9999"
    assert reader.discovery_count == 1
    current_state.pid += 1
    assert sampler.sample().scope.pid == 43
    assert reader.discovery_count == 2


def test_sampler_retries_missing_buttons_at_bounded_rate():
    reader = Reader()
    reader.buttons = ()
    clock = [10]
    sampler = probe.EmrSignalSampler(reader, state, lambda: clock[0])
    sampler.sample()
    sampler.sample()
    assert reader.discovery_count == 1
    clock[0] += 5
    sampler.sample()
    assert reader.discovery_count == 2


def test_sampler_missing_chart_preserves_signal_detection():
    reader = Reader()
    reader.chart_number = lambda _scope: 1 / 0
    sampler = probe.EmrSignalSampler(reader, state)
    assert sampler.sample().chart_no == ""
    assert len(sampler.sample().buttons) == 2


def test_sampler_clears_disconnected_and_inactive_context():
    reader = Reader()
    current = [state()]
    sampler = probe.EmrSignalSampler(reader, lambda: current[0])
    assert sampler.sample()
    reader.active = False
    assert sampler.sample() is None
    current[0] = None
    assert sampler.sample() is None
    assert sampler._buttons == ()


def test_native_keyboard_scope_rejects_claim_focus_and_menus():
    reader = object.__new__(probe.Win32SignalReader)
    reader._live = lambda scope: True
    focus = [102]
    flags = [0]

    def thread_info(thread, pointer):
        pointer._obj.hwndActive = 100
        pointer._obj.hwndFocus = focus[0]
        pointer._obj.flags = flags[0]
        return True

    reader.user32 = SimpleNamespace(GetGUIThreadInfo=thread_info)
    reader.gui = SimpleNamespace(IsChild=lambda parent, child: (parent, child) == (101, 102))
    scope = probe.connected_scope(state())
    assert reader.keyboard_context(scope)
    focus[0] = 300  # A sibling claim page, not a child of the treatment page.
    assert not reader.keyboard_context(scope)
    focus[0] = 102
    flags[0] = 4
    assert not reader.keyboard_context(scope)


def test_native_text_read_works_on_our_own_hidden_window():
    import win32gui

    handle = win32gui.CreateWindowEx(0, "STATIC", "001234", 0, 0, 0, 1, 1, 0, 0, 0, None)
    try:
        assert probe.Win32SignalReader()._text(handle) == "001234"
    finally:
        win32gui.DestroyWindow(handle)


def test_listener_factory_is_unsuppressed(monkeypatch, capture):
    from pynput import keyboard, mouse as mouse_module

    options = []
    monkeypatch.setattr(keyboard, "Listener", lambda **kwargs: options.append(kwargs))
    monkeypatch.setattr(mouse_module, "Listener", lambda **kwargs: options.append(kwargs))
    probe._listeners(capture)
    assert [option["suppress"] for option in options] == [False, False]
    assert options[0]["win32_event_filter"] == capture.keyboard_event
    assert options[1]["win32_event_filter"] == capture.mouse_event


class Listener:
    def __init__(self):
        self.alive = False

    def start(self):
        self.alive = True

    def wait(self):
        pass

    def stop(self):
        self.alive = False

    def is_alive(self):
        return self.alive


def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_runtime_starts_once_stops_and_discards_late_signals():
    application = app()
    listeners = (Listener(), Listener())
    runtime = probe.EmrSignalProbeRuntime(
        reader_factory=Reader, listener_factory=lambda _capture: listeners, state_provider=state,
    )
    messages = []
    runtime.status_message.connect(messages.append)
    runtime.start()
    thread = runtime._thread
    runtime.start()
    assert runtime._thread is thread
    deadline = time.monotonic() + 3
    while runtime._capture is None or runtime._capture.snapshot is None:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    key(runtime._capture)
    runtime._drain()
    assert any("F7 | Chart 001234" in message for message in messages)
    runtime.stop()
    assert not thread.is_alive()
    assert not any(listener.alive for listener in listeners)
    size = len(messages)
    runtime._output.put_nowait("late")
    runtime._drain()
    assert len(messages) == size
    assert application is not None


def test_runtime_listener_failure_is_reported_without_exception_details():
    application = app()
    runtime = probe.EmrSignalProbeRuntime(reader_factory=lambda: 1 / 0)
    runtime._run()
    runtime._running = True
    messages = []
    runtime.status_message.connect(messages.append)
    runtime._drain()
    assert messages == ["EMR signal probe unavailable. Restart KaosEghis to retry."]
    runtime.stop()
    assert application is not None


def test_launcher_appends_to_existing_status_without_new_widgets():
    application = app()
    from PySide6.QtWidgets import QPlainTextEdit
    from KaosEghis.ui.tabs.kaoseghis_tab import LauncherPage

    log = QPlainTextEdit()
    log.setPlainText("Macro completed.")
    LauncherPage.show_emr_signal_status(SimpleNamespace(log=log), "F7 | Chart 001234")
    assert log.toPlainText() == "Macro completed.\nF7 | Chart 001234"
    log.close()
    assert application is not None


def test_chart_read_is_scoped_to_text_at_configured_point(monkeypatch):
    import pywinauto

    reader = object.__new__(probe.Win32SignalReader)
    reader.keyboard_context = lambda scope: True
    reader._chart_identity = None
    reader._belongs = lambda parent, child: parent == 100 and child == 110
    reader.gui = SimpleNamespace(
        WindowFromPoint=lambda point: 110,
        GetWindowRect=lambda handle: (210, 100, 260, 120),
    )
    native_reads = []
    reader._text = lambda handle: native_reads.append(handle) or "001234"
    info = SimpleNamespace(handle=110, control_type="Text")
    lookups = []

    def from_point(x, y):
        lookups.append((x, y))
        return SimpleNamespace(element_info=info)

    monkeypatch.setattr(pywinauto, "Desktop", lambda **kwargs: SimpleNamespace(from_point=from_point))
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    assert reader.chart_number(scope) == "001234"
    assert lookups == [(222, 115)]
    assert native_reads == [110, 110]
    reader._text = lambda handle: "Not a chart number"
    assert reader.chart_number(scope) == ""
    reader._chart_identity = None
    info.control_type = "Button"
    assert reader.chart_number(scope) == ""


def test_chart_never_reads_other_application_at_coordinate():
    reader = object.__new__(probe.Win32SignalReader)
    reader.keyboard_context = lambda scope: True
    reader._belongs = lambda parent, child: False
    reader.gui = SimpleNamespace(WindowFromPoint=lambda point: 999)
    reader._text = lambda handle: pytest.fail("Read another app")
    assert reader.chart_number(probe.connected_scope(state())) == ""


def test_button_discovery_requires_unique_exact_id_in_treatment_scope(monkeypatch):
    reader = object.__new__(probe.Win32SignalReader)
    calls = []

    def node(handle):
        return SimpleNamespace(element_info=SimpleNamespace(handle=handle),
                               is_visible=lambda: True, is_enabled=lambda: True)

    def find(ids, **kwargs):
        calls.append((ids, kwargs))
        return {"BtnF6": [node(106)], "BtnF7": [node(107), node(108)]}

    monkeypatch.setattr(probe, "find_uia_elements_by_automation_ids", find)
    assert reader.discover_buttons(probe.connected_scope(state())) == (("F6 button", 106),)
    assert calls == [(("BtnF6", "BtnF7"), {
        "root_handle": 101, "process_ids": (42,), "control_type": "Button",
    })]


def test_main_window_runtime_lifecycle_includes_probe():
    application = app()
    from KaosEghis.ui.main_window import MainWindow
    from PySide6.QtGui import QCloseEvent

    calls = []

    def service(name):
        return SimpleNamespace(
            start=lambda: calls.append((name, "start")) or True,
            stop=lambda: calls.append((name, "stop")),
        )

    window = SimpleNamespace(**{
        name: service(name) for name in (
            "launcher_hotkey_runtime", "socl_hotkey_runtime", "pw_runtime",
            "patient_alert_monitor", "emr_signal_probe",
        )
    })
    MainWindow.initialize_runtime_services(window)
    assert calls[-1] == ("emr_signal_probe", "start")
    # Use a real MainWindow type without constructing integrations or connecting EMR.
    from PySide6.QtWidgets import QMainWindow
    shell = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(shell)
    for name, value in vars(window).items():
        setattr(shell, name, value)
    shell.scheduler_runtime = service("scheduler")
    shell.patient_alert_popup = SimpleNamespace(close=lambda: None)
    shell.kaoseghis_tab = SimpleNamespace(close_socl_window=lambda: None)
    MainWindow.closeEvent(shell, QCloseEvent())
    assert ("emr_signal_probe", "stop") in calls
    assert application is not None
