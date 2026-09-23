from dataclasses import replace
import queue
import threading
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


def test_shared_patient_context_deduplicates_samples_and_same_value_events(capture):
    snapshot = capture.snapshot
    capture.update_snapshot(snapshot)
    context = capture.patient_context
    assert context.chart_no == snapshot.chart_no
    assert capture.patient_is_current(context)
    capture.chart_property_event(snapshot.scope, "Name", snapshot.chart_no)
    capture.update_snapshot(replace(snapshot, sampled_at=10.1))
    assert capture.patient_context == context
    assert capture.patient_is_current(context)
    assert snapshot.chart_no not in repr(context)


def test_chart_clear_immediately_invalidates_patient_and_old_inflight_samples(capture):
    snapshot = capture.snapshot
    capture.update_snapshot(snapshot)
    context = capture.patient_context
    capture.chart_property_event(snapshot.scope, "Name", "")
    assert capture.patient_context is None
    assert not capture.patient_is_current(context)
    capture.update_snapshot(snapshot)
    assert capture.patient_context is None
    capture.test_clock[0] += 0.3
    capture.update_snapshot(replace(snapshot, sampled_at=capture.test_clock[0]))
    reloaded = capture.patient_context
    assert reloaded.chart_no == context.chart_no
    assert reloaded.revision > context.revision
    assert capture.patient_is_current(reloaded)
    assert not capture.patient_is_current(context)


def test_patient_context_survives_focus_gap_but_cannot_validate_stale_snapshot(capture):
    snapshot = capture.snapshot
    capture.update_snapshot(snapshot)
    context = capture.patient_context
    capture.update_snapshot(None)
    assert capture.patient_context == context
    assert not capture.patient_is_current(context)
    capture.update_snapshot(snapshot)
    assert capture.patient_context == context
    capture.test_clock[0] += 1
    assert not capture.patient_is_current(context)
    capture.update_snapshot(replace(snapshot, sampled_at=capture.test_clock[0]))
    assert capture.patient_is_current(context)


def test_sampled_clear_and_connection_change_invalidate_patient(capture):
    snapshot = capture.snapshot
    capture.update_snapshot(snapshot)
    context = capture.patient_context
    capture.update_snapshot(replace(snapshot, chart_no="", unavailable_reason="chart UIA text is empty"))
    assert capture.patient_context is None
    capture.update_snapshot(snapshot)
    assert capture.patient_context != context
    capture.test_state.pid += 1
    assert not capture.patient_is_current(capture.patient_context)
    capture.update_snapshot(None)
    assert capture.patient_context is None


def test_runtime_publishes_shared_patient_changes_even_if_status_queue_is_full(capture):
    app()
    runtime = probe.EmrSignalProbeRuntime(state_provider=lambda: capture.test_state)
    runtime._running = True
    runtime._capture = capture
    contexts = []
    runtime.patient_changed.connect(contexts.append)
    try:
        capture.update_snapshot(capture.snapshot)
        context = capture.patient_context
        for _ in range(runtime._output.maxsize):
            runtime._output.put_nowait("diagnostic")
        runtime._drain()
        runtime._drain()
        assert contexts == [context]
        assert runtime.is_patient_current(context)
        capture.chart_property_event(context.scope, "Name", "")
        assert not runtime.is_patient_current(context)
        runtime._drain()
        assert contexts == [context, None]
    finally:
        runtime.stop()


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
    assert "snapshot expired" in observation.status_text() if age >= 0 else "timing invalid" in observation.status_text()


@pytest.mark.parametrize("source", ["key", "button"])
def test_missing_chart_shows_read_failure_not_stale_snapshot(capture, source):
    capture.snapshot = replace(
        capture.snapshot, chart_no="", unavailable_reason="chart UIA text is empty",
    )
    if source == "key":
        key(capture)
    else:
        mouse(capture)
        mouse(capture, message=0x202)
    observation = capture.output.get_nowait()
    assert "Chart unavailable (chart UIA text is empty)" in observation.status_text()
    assert "no fresh snapshot" not in observation.status_text()


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


@pytest.mark.parametrize("source,handle", [("F6", 106), ("F7", 107)])
def test_uia_activation_is_distinct_from_key_or_mouse_and_does_not_read(capture, source, handle):
    capture.reader.chart_number = lambda scope: pytest.fail("UIA callback read chart")
    capture.reader.keyboard_context = lambda scope: pytest.fail("UIA callback queried foreground")
    capture.reader.discover_buttons = lambda scope: pytest.fail("UIA callback scanned tree")
    capture.activation_event(source, capture.snapshot.scope, handle)
    observation = capture.output.get_nowait()
    assert observation.source == f"{source} activation (UIA)"
    assert observation.chart_no == "001234"
    assert observation.age_ms == 100


@pytest.mark.parametrize("context", ["modal", "expired", "unreadable"])
def test_uia_activation_remains_visible_without_fresh_chart(capture, context):
    scope = capture.snapshot.scope
    if context == "modal":
        capture.snapshot = None
    elif context == "expired":
        capture.test_clock[0] += 1
    else:
        capture.snapshot = replace(capture.snapshot, chart_no="", unavailable_reason="chart UIA text is empty")
    capture.activation_event("F7", scope, 107)
    observation = capture.output.get_nowait()
    assert observation.source == "F7 activation (UIA)"
    assert not observation.chart_no
    assert observation.unavailable_reason


@pytest.mark.parametrize("context", ["disconnected", "restart", "stopped", "destroyed", "other_source"])
def test_uia_activation_discards_obsolete_or_invalid_sources(capture, context):
    scope = capture.snapshot.scope
    source = "F7"
    if context == "disconnected":
        capture.test_state.status = "red"
    elif context == "restart":
        capture.test_state.pid += 1
    elif context == "stopped":
        capture.enabled = False
    elif context == "destroyed":
        capture.reader.live_buttons = False
    else:
        source = "F8"
    capture.activation_event(source, scope, 107)
    assert capture.output.empty()


def test_sampled_chart_changes_are_distinct_and_do_not_repeat(capture):
    first = capture.snapshot
    capture.update_snapshot(first)
    initial = capture.output.get_nowait()
    assert initial.source == "Chart observed (sampled)"
    assert "not a UIA event" in initial.status_text()
    capture.update_snapshot(first)
    capture.update_snapshot(None)  # Foreground/modal transitions are not patient changes.
    capture.update_snapshot(first)
    assert capture.output.empty()
    capture.update_snapshot(replace(first, chart_no="000456"))
    changed = capture.output.get_nowait()
    assert changed.source == "Chart changed (sampled)"
    assert changed.chart_no == "000456"
    assert "000456" not in repr(changed)


def test_sampled_chart_clears_only_on_verified_empty_value_and_resets_on_restart(capture):
    first = capture.snapshot
    capture.update_snapshot(first)
    capture.output.get_nowait()
    capture.update_snapshot(replace(first, chart_no="", unavailable_reason="EMR not focused"))
    assert capture.output.empty()
    capture.update_snapshot(replace(first, chart_no="", unavailable_reason="chart UIA text is empty"))
    assert capture.output.get_nowait().source == "Chart field empty (sampled)"
    capture.update_snapshot(first)
    assert capture.output.get_nowait().source == "Chart observed (sampled)"
    capture.test_state.pid += 1
    capture.update_snapshot(replace(first, scope=probe.connected_scope(capture.test_state)))
    assert capture.output.get_nowait().source == "Chart observed (sampled)"


def test_property_event_uses_its_payload_not_previous_snapshot(capture):
    scope = capture.snapshot.scope
    capture.reader.chart_number = lambda scope: pytest.fail("Callback read chart")
    capture.chart_property_event(scope, "Name", "000456")
    event = capture.output.get_nowait()
    assert event.chart_no == "000456"
    assert "UIA Name" in event.status_text()
    assert capture.snapshot.chart_no == "001234"  # Probe events do not authorize patient identity.
    capture.test_state.pid += 1
    capture.chart_property_event(scope, "Name", "000789")
    assert capture.output.empty()
    capture.enabled = False
    capture.chart_property_event(probe.connected_scope(capture.test_state), "Name", "000789")
    assert capture.output.empty()


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
    assert sampler.sample().unavailable_reason == "UIA chart read failed; target will be reacquired"


@pytest.mark.parametrize("access_denied", [False, True])
def test_sampler_failure_reason_never_includes_exception_or_patient_values(access_denied):
    reader = Reader()
    error = RuntimeError("patient value 001234")
    if access_denied:
        error.hresult = -2147024891

    def fail(_scope):
        raise error

    reader.chart_number = fail
    snapshot = probe.EmrSignalSampler(reader, state).sample()
    assert "001234" not in snapshot.unavailable_reason
    assert not snapshot.chart_no
    assert ("access denied" in snapshot.unavailable_reason) == access_denied


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
    activation_calls = []
    chart_calls = []

    def activation_factory(capture, reader):
        activation_calls.append(("create", threading.get_ident()))
        return SimpleNamespace(
            sync=lambda scope, buttons: activation_calls.append(("sync", threading.get_ident())),
            close=lambda: activation_calls.append(("close", threading.get_ident())),
        )

    def chart_factory(capture, reader):
        chart_calls.append(("create", threading.get_ident()))
        return SimpleNamespace(
            sync=lambda scope, target: chart_calls.append(("sync", threading.get_ident())),
            close=lambda: chart_calls.append(("close", threading.get_ident())),
        )

    runtime = probe.EmrSignalProbeRuntime(
        reader_factory=Reader, listener_factory=lambda _capture: listeners, state_provider=state,
        activation_factory=activation_factory,
        chart_factory=chart_factory,
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
    assert [name for name, _ in activation_calls][0] == "create"
    assert [name for name, _ in activation_calls][-1] == "close"
    assert {ident for _, ident in activation_calls} == {thread.ident}
    assert thread.ident != threading.get_ident()
    assert chart_calls[0][0] == "create"
    assert chart_calls[-1][0] == "close"
    assert {ident for _, ident in chart_calls} == {thread.ident}
    size = len(messages)
    runtime._output.put_nowait("late")
    runtime._drain()
    assert len(messages) == size
    assert application is not None


@pytest.mark.parametrize("failure", ["factory", "sync"])
@pytest.mark.parametrize("kind", ["activation", "chart"])
def test_uia_listener_failure_does_not_stop_existing_probe(failure, kind):
    application = app()
    listeners = (Listener(), Listener())
    failed = threading.Event()

    def fail(*args):
        failed.set()
        raise RuntimeError("provider detail must not be logged")

    factories = {
        "activation_factory": lambda *args: SimpleNamespace(sync=lambda *args: None, close=lambda: None),
        "chart_factory": lambda *args: SimpleNamespace(sync=lambda *args: None, close=lambda: None),
    }
    factories[f"{kind}_factory"] = fail if failure == "factory" else lambda *args: SimpleNamespace(sync=fail, close=fail)
    runtime = probe.EmrSignalProbeRuntime(
        reader_factory=Reader, listener_factory=lambda capture: listeners, state_provider=state,
        **factories,
    )
    runtime.start()
    try:
        assert failed.wait(3)
        deadline = time.monotonic() + 3
        while runtime._capture.snapshot is None:
            assert time.monotonic() < deadline
            time.sleep(0.01)
        key(runtime._capture)
        items = []
        while not runtime._output.empty():
            items.append(runtime._output.get_nowait())
        assert any(isinstance(item, probe.SignalObservation) for item in items)
        assert all(listener.alive for listener in listeners)
        assert "provider detail" not in repr(items)
    finally:
        runtime.stop()
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


@pytest.fixture
def chart_reader(monkeypatch):
    import pywinauto

    reader = object.__new__(probe.Win32SignalReader)
    reader.keyboard_context = lambda scope: True
    reader._chart_identity = None
    reader._chart_node = None
    reader._chart_retry = None
    clock = [10.0]
    reader._clock = lambda: clock[0]
    reader._belongs = lambda parent, child: parent == child or (parent == 100 and child in (110, 111))
    reader.process = SimpleNamespace(GetWindowThreadProcessId=lambda handle: (1, 42))
    reader.gui = SimpleNamespace(
        WindowFromPoint=lambda point: 110,
        GetWindowRect=lambda handle: (197, 107, 237, 128),
        IsWindow=lambda handle: handle > 0,
        GetParent=lambda handle: 100 if handle in (110, 111) else 0,
        GetWindow=lambda handle, flag: 0,
    )
    reader._text = lambda handle: pytest.fail("Must read UIA value, not native caption")
    cache_options = []
    info = SimpleNamespace(
        handle=110, control_type="Text", process_id=42, name="001234", visible=True,
        runtime_id=(42, 110),
        rectangle=SimpleNamespace(left=197, top=107, right=237, bottom=128),
        set_cache_strategy=cache_options.append,
    )
    node = SimpleNamespace(element_info=info)
    discovered = [node]
    lookups = []

    def from_point(x, y):
        lookups.append((x, y))
        return discovered[0]

    monkeypatch.setattr(pywinauto, "Desktop", lambda **kwargs: SimpleNamespace(from_point=from_point))
    return SimpleNamespace(reader=reader, node=node, info=info, lookups=lookups,
                           cache_options=cache_options, clock=clock, discovered=discovered)


def test_chart_read_reuses_control_but_reads_fresh_uia_text(chart_reader):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    info.name = "000456"
    assert reader.chart_number(scope) == "000456"
    assert chart_reader.lookups == [(205, 115)]
    assert chart_reader.cache_options == [False]
    assert reader.chart_target.node is chart_reader.node
    assert reader.chart_target.owner_handle == 110


def test_known_chart_clearing_keeps_verified_target_for_property_listener(chart_reader):
    scope = probe.connected_scope(state())
    chart_reader.reader.chart_number(scope)
    chart_reader.info.name = ""
    with pytest.raises(probe._ChartUnavailable, match="empty"):
        chart_reader.reader.chart_number(scope)
    assert chart_reader.reader.chart_target.node is chart_reader.node
    chart_reader.reader.keyboard_context = lambda scope: False
    with pytest.raises(probe._ChartUnavailable, match="not focused"):
        chart_reader.reader.chart_number(scope)
    assert chart_reader.reader.chart_target is None


@pytest.mark.parametrize("initial", ["", "Patient", "Patient 001234", "1" * 21])
def test_discovery_requires_numeric_text_and_retries_at_bounded_rate(chart_reader, initial):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    info.name = initial
    with pytest.raises(probe._ChartUnavailable):
        reader.chart_number(scope)
    assert reader._chart_node is None
    assert reader.chart_target is None
    assert not reader.chart_target_live(scope, 110)
    info.name = "000456"
    for elapsed in (0, 0.25, 0.5, 0.99):
        chart_reader.clock[0] = 10.0 + elapsed
        with pytest.raises(probe._ChartUnavailable):
            reader.chart_number(scope)
    assert chart_reader.lookups == [(205, 115)]
    chart_reader.clock[0] = 10.0 + probe.CHART_REDISCOVERY_INTERVAL
    assert reader.chart_number(scope) == "000456"
    assert len(chart_reader.lookups) == 2
    assert reader.chart_target_live(scope, 110)


def test_nonnumeric_cache_is_removed_and_replaced_by_new_chart_control(chart_reader):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    info.name = "Patient 000456"
    with pytest.raises(probe._ChartUnavailable, match="not numeric; rediscovering"):
        reader.chart_number(scope)
    assert reader._chart_node is None
    assert reader.chart_target is None
    assert not reader.chart_target_live(scope, 110)

    replacement = SimpleNamespace(element_info=SimpleNamespace(**{
        **vars(info), "name": "000789", "handle": 111, "runtime_id": (42, 111),
    }))
    chart_reader.discovered[0] = replacement
    chart_reader.clock[0] += probe.CHART_REDISCOVERY_INTERVAL
    assert reader.chart_number(scope) == "000789"
    assert reader.chart_target.node is replacement
    assert reader.chart_target_live(scope, 111)
    assert not reader.chart_target_live(scope, 110)
    assert len(chart_reader.lookups) == 2


def test_invalid_chart_cache_detaches_listener_and_rejects_late_events(chart_reader):
    reader, scope = chart_reader.reader, probe.connected_scope(state())
    subscriptions, removed, events = [], [], []

    def subscribe(target, runtime_id, callback, rejected):
        subscription = SimpleNamespace(callback=callback)
        subscriptions.append(subscription)
        return subscription

    backend = SimpleNamespace(subscribe=subscribe, unsubscribe=removed.append)
    capture = SimpleNamespace(_emit=lambda text: None, chart_property_event=lambda *args: events.append(args))
    listener = probe.UiaChartListener(capture, reader, backend_factory=lambda: backend)
    reader.chart_number(scope)
    listener.sync(scope, reader.chart_target)
    assert len(subscriptions) == 1
    chart_reader.info.name = "Patient"
    with pytest.raises(probe._ChartUnavailable):
        reader.chart_number(scope)
    listener.sync(scope, reader.chart_target)
    assert removed == subscriptions
    subscriptions[0].callback("Name", "001234")
    assert not events


def test_discovery_retry_does_not_delay_new_emr_scope(chart_reader):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    info.name = "Patient"
    with pytest.raises(probe._ChartUnavailable):
        reader.chart_number(scope)
    info.name, info.process_id = "000456", 43
    reader.process.GetWindowThreadProcessId = lambda handle: (1, 43)
    assert reader.chart_number(replace(scope, pid=43)) == "000456"
    assert len(chart_reader.lookups) == 2


def test_chart_anchor_stays_inside_a_narrow_label(chart_reader):
    # The latest capture is near the label's left edge, not its variable right edge.
    chart_reader.info.rectangle.right = 215
    chart_reader.info.name = "12"
    assert chart_reader.reader.chart_number(probe.connected_scope(state())) == "12"
    assert chart_reader.lookups == [(205, 115)]


@pytest.mark.parametrize("path", ["value", "legacy", "name"])
def test_chart_read_uses_same_value_paths_as_capture_inspector(chart_reader, path):
    node = chart_reader.node
    if path == "value":
        node.iface_value = SimpleNamespace(CurrentValue="000456")
    elif path == "legacy":
        node.legacy_properties = lambda: {"Value": "000456"}
    else:
        node.element_info.name = "000456"
    assert chart_reader.reader.chart_number(probe.connected_scope(state())) == "000456"


@pytest.mark.parametrize("virtual", [False, True])
def test_chart_read_accepts_native_parent_hit_only_for_verified_uia_text(chart_reader, virtual):
    reader, info = chart_reader.reader, chart_reader.info
    info.handle = 0 if virtual else 111
    info.parent = SimpleNamespace(handle=110, process_id=42)
    reader._belongs = lambda parent, child: parent == child or (parent, child) in {
        (100, 110), (100, 111), (110, 111),
    }
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    info.name = "000456"
    assert reader.chart_number(scope) == "000456"
    assert chart_reader.lookups == [(205, 115)]


@pytest.mark.parametrize("change,reason", [
    ("empty", "text is empty"), ("nonnumeric", "text is not numeric"),
    ("type", "not a Text"), ("pid", "not owned"),
    ("hidden", "hidden or has invalid bounds"), ("moved", "hidden or has invalid bounds"),
    ("other_window", "ownership could not be confirmed"),
])
def test_chart_read_rejects_unverified_or_unreadable_target(chart_reader, change, reason):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    if change in {"empty", "nonnumeric"}:
        info.name = "" if change == "empty" else "Patient 001234"
    elif change == "type":
        info.control_type = "Button"
    elif change == "pid":
        info.process_id = 43
    elif change == "hidden":
        info.visible = False
    elif change == "moved":
        info.rectangle.top = 200
    else:
        info.handle = 999
    with pytest.raises(probe._ChartUnavailable, match=reason):
        reader.chart_number(scope)
    if change == "empty":
        assert reader._chart_node is chart_reader.node
    else:
        assert reader._chart_identity is None
        assert reader._chart_node is None


def test_chart_read_reacquires_after_value_failure_and_emr_restart(chart_reader):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    info.name = ""
    with pytest.raises(probe._ChartUnavailable):
        reader.chart_number(scope)
    info.name = "000456"
    assert reader.chart_number(scope) == "000456"
    info.process_id = 43
    reader.process.GetWindowThreadProcessId = lambda handle: (1, 43)
    assert reader.chart_number(replace(scope, pid=43)) == "000456"
    assert len(chart_reader.lookups) == 2


def test_chart_read_reacquires_invalid_cached_element(chart_reader, monkeypatch):
    import pywinauto

    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    info.visible = False
    new_info = SimpleNamespace(**vars(info))
    new_info.visible = True
    new_info.name = "000456"
    monkeypatch.setattr(pywinauto, "Desktop", lambda **kwargs: SimpleNamespace(
        from_point=lambda *point: SimpleNamespace(element_info=new_info),
    ))
    assert reader.chart_number(scope) == "000456"


@pytest.mark.parametrize("change", ["focus", "point", "moved", "pid"])
def test_chart_read_discards_value_when_context_changes_mid_read(chart_reader, monkeypatch, change):
    reader, info = chart_reader.reader, chart_reader.info

    def value(_node):
        if change == "focus":
            reader.keyboard_context = lambda scope: False
        elif change == "point":
            reader.gui.WindowFromPoint = lambda point: 999
        elif change == "moved":
            info.rectangle.left = 300
        else:
            info.process_id = 43
        return "001234"

    monkeypatch.setattr(probe, "_best_text_value", value)
    with pytest.raises(probe._ChartUnavailable):
        reader.chart_number(probe.connected_scope(state()))
    assert (reader._chart_node is not None) == (change == "focus")
    assert reader.chart_target is None


def test_chart_never_reads_other_application_at_coordinate():
    reader = object.__new__(probe.Win32SignalReader)
    reader.keyboard_context = lambda scope: True
    reader._chart_identity = reader._chart_node = None
    reader._chart_retry = None
    reader._clock = lambda: 10.0
    reader._belongs = lambda parent, child: False
    reader._chart_window_belongs = lambda scope, handle: False
    reader.gui = SimpleNamespace(WindowFromPoint=lambda point: 999)
    reader._text = lambda handle: pytest.fail("Read another app")
    with pytest.raises(probe._ChartUnavailable, match="discovery point.*not in the connected EMR"):
        reader.chart_number(probe.connected_scope(state()))


@pytest.mark.parametrize("case,expected", [
    ("child", True), ("owned", True), ("owned_child", True),
    ("unrelated_same_process", False), ("other_process", False),
    ("foreign_owner", False), ("cycle", False), ("destroyed", False),
    ("reused_root", False),
])
def test_chart_window_membership_follows_bounded_same_process_ownership(chart_reader, case, expected):
    reader = chart_reader.reader
    parents, owners, pids = {}, {}, {}
    if case == "child":
        parents[110] = 100
    elif case == "owned":
        owners[110] = 100
    elif case in {"owned_child", "foreign_owner"}:
        parents[110] = 200
        owners[200] = 100
        if case == "foreign_owner":
            pids[200] = 43
    elif case == "other_process":
        parents[110] = 100
        pids[110] = 43
    elif case == "cycle":
        parents.update({110: 200, 200: 110})
    elif case in {"destroyed", "reused_root"}:
        parents[110] = 100
        if case == "reused_root":
            pids[100] = 43
    reader.gui.GetParent = lambda handle: parents.get(handle, 0)
    reader.gui.GetWindow = lambda handle, flag: owners.get(handle, 0)
    reader.gui.IsWindow = lambda handle: bool(handle) and not (case == "destroyed" and handle == 110)
    reader.process.GetWindowThreadProcessId = lambda handle: (1, pids.get(handle, 42))
    scope = probe.connected_scope(state())
    assert reader._chart_window_belongs(scope, 110) is expected
    reader._chart_identity, reader._chart_node = (scope, (42, 110), 110), chart_reader.node
    assert reader.chart_target_live(scope, 110) is expected


def test_chart_read_accepts_emr_owned_header_window_seen_in_live_diagnostics(chart_reader):
    reader = chart_reader.reader
    reader._belongs = lambda parent, child: parent == child  # Owned windows are not children.
    reader.gui.GetParent = lambda handle: 200 if handle == 110 else 0
    reader.gui.GetWindow = lambda handle, flag: 100 if handle == 200 else 0
    assert not reader._belongs(100, 110)
    assert reader.chart_number(probe.connected_scope(state())) == "001234"
    assert reader.chart_target.owner_handle == 110


def test_chart_window_membership_has_a_finite_walk_budget(chart_reader):
    reader = chart_reader.reader
    visited = []
    reader.gui.GetParent = lambda handle: visited.append(handle) or handle + 1
    reader.gui.GetWindow = lambda handle, flag: 0
    assert not reader._chart_window_belongs(probe.connected_scope(state()), 200)
    assert len(visited) == 16


def test_cached_chart_follows_live_control_not_old_screen_point(chart_reader):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    info.rectangle = SimpleNamespace(left=450, top=210, right=500, bottom=230)
    info.name = "000456"
    reader.gui.WindowFromPoint = lambda point: pytest.fail("Cached chart must not depend on old coordinates")
    assert reader.chart_number(scope) == "000456"
    assert chart_reader.lookups == [(205, 115)]


def test_focus_change_keeps_control_but_never_reuses_previous_patient_value(chart_reader):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    reader.keyboard_context = lambda scope: False
    with pytest.raises(probe._ChartUnavailable, match="not focused"):
        reader.chart_number(scope)
    assert reader.chart_target is None
    info.name = "000456"
    reader.keyboard_context = lambda scope: True
    reader.gui.WindowFromPoint = lambda point: pytest.fail("Focus change must not require rediscovery")
    assert reader.chart_number(scope) == "000456"
    assert chart_reader.lookups == [(205, 115)]


def test_changed_runtime_identity_is_reacquired_and_mid_read_change_is_rejected(chart_reader, monkeypatch):
    reader, info = chart_reader.reader, chart_reader.info
    scope = probe.connected_scope(state())
    assert reader.chart_number(scope) == "001234"
    info.runtime_id = (42, 111)
    info.name = "000456"
    assert reader.chart_number(scope) == "000456"
    assert len(chart_reader.lookups) == 2

    def value(node):
        info.runtime_id = (42, 112)
        return "000789"

    monkeypatch.setattr(probe, "_best_text_value", value)
    with pytest.raises(probe._ChartUnavailable, match="identity changed"):
        reader.chart_number(scope)
    assert reader.chart_target is None
    assert reader._chart_node is None


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
