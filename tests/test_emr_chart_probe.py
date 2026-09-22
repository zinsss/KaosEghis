from dataclasses import replace
from types import SimpleNamespace

import pytest

from KaosEghis.core.emr_chart_probe import ChartFieldObservation, ChartTarget, UiaChartBackend, UiaChartListener
from KaosEghis.core.emr_signal_probe import SignalScope


@pytest.mark.parametrize("value,number,detail", [
    (" 001234 ", "001234", "load completion unverified"),
    ("", "", "cleared"), ("  ", "", "cleared"),
    ("private patient memo", "", "not displayed"), (None, "", "not displayed"),
    (1234, "", "not displayed"), ("1" * 21, "", "not displayed"),
])
def test_property_observation_only_displays_valid_numeric_chart(value, number, detail):
    event = ChartFieldObservation.from_event("Name", value)
    assert event.chart_no == number
    assert detail in event.status_text()
    assert "private patient memo" not in event.status_text()
    assert "001234" not in repr(event)


class Backend:
    def __init__(self):
        self.added = []
        self.removed = []
        self.attempts = 0
        self.fail_add = False
        self.fail_remove = False

    def subscribe(self, target, runtime_id, callback, rejected):
        self.attempts += 1
        if self.fail_add:
            raise RuntimeError("private provider data")
        subscription = SimpleNamespace(target=target, runtime_id=runtime_id, callback=callback, active=True)
        self.added.append(subscription)
        return subscription

    def unsubscribe(self, subscription):
        subscription.active = False
        self.removed.append(subscription)
        if self.fail_remove:
            raise RuntimeError("private provider data")


@pytest.fixture
def listener():
    backend = Backend()
    statuses, events = [], []
    capture = SimpleNamespace(_emit=statuses.append, chart_property_event=lambda *args: events.append(args))
    live = [True]
    reader = SimpleNamespace(chart_target_live=lambda scope, handle: live[0])
    clock = [10.0]
    scope = SignalScope(42, 100, 101)
    target = ChartTarget(scope, SimpleNamespace(element_info=SimpleNamespace(runtime_id=(42, 110))), 110)
    result = UiaChartListener(capture, reader, backend_factory=lambda: backend, clock=lambda: clock[0])
    result.test = SimpleNamespace(backend=backend, statuses=statuses, events=events, live=live,
                                 clock=clock, scope=scope, target=target)
    return result


def test_listener_reuses_discovered_target_without_searching_or_duplicate_registration(listener):
    t = listener.test
    for _ in range(100):
        listener.sync(t.scope, t.target)
    assert t.backend.attempts == 1
    assert len(t.statuses) == 1
    assert "not yet verified" in t.statuses[0]
    t.backend.added[0].callback("Name", "001234")
    assert t.events == [(t.scope, "Name", "001234")]


def test_new_wrapper_for_same_virtual_control_keeps_subscription(listener):
    t = listener.test
    listener.sync(t.scope, t.target)
    replacement = replace(t.target, node=SimpleNamespace(element_info=SimpleNamespace(runtime_id=(42, 110))))
    listener.sync(t.scope, replacement)
    assert t.backend.attempts == 1
    assert not t.backend.removed


def test_recreated_field_rebinds_immediately_and_old_callbacks_are_ignored(listener):
    t = listener.test
    listener.sync(t.scope, t.target)
    old = t.backend.added[0]
    replacement = replace(t.target, node=SimpleNamespace(element_info=SimpleNamespace(runtime_id=(42, 111))))
    listener.sync(t.scope, replacement)
    assert len(t.backend.added) == 2
    assert not old.active
    old.callback("Name", "001234")
    assert not t.events
    t.backend.added[-1].callback("Value", "000456")
    assert t.events == [(t.scope, "Value", "000456")]


def test_restart_does_not_reuse_numeric_automation_id_or_old_scope(listener):
    t = listener.test
    listener.sync(t.scope, t.target)
    new_scope = replace(t.scope, pid=43, root=200, treatment=201)
    new_target = ChartTarget(new_scope, SimpleNamespace(element_info=SimpleNamespace(runtime_id=(43, 9876))), 9876)
    listener.sync(new_scope, new_target)
    assert len(t.backend.added) == 2
    assert t.backend.added[-1].runtime_id == (43, 9876)
    assert t.backend.added[-1].target.scope == new_scope


def test_temporary_unavailable_sample_keeps_listener_but_disconnect_does_not(listener):
    t = listener.test
    listener.sync(t.scope, t.target)
    listener.sync(t.scope, None)
    assert not t.backend.removed
    listener.sync(None, None)
    assert len(t.backend.removed) == 1
    t.backend.added[0].callback("Name", "001234")
    assert not t.events


def test_dead_owner_or_uncertain_new_identity_removes_old_listener(listener):
    t = listener.test
    listener.sync(t.scope, t.target)
    replacement = replace(t.target, node=SimpleNamespace(element_info=SimpleNamespace(runtime_id=())))
    listener.sync(t.scope, replacement)
    assert len(t.backend.removed) == 1
    t.clock[0] += 5
    listener.sync(t.scope, t.target)
    t.live[0] = False
    listener.sync(t.scope, None)
    assert len(t.backend.removed) == 2


def test_failed_subscription_retries_at_bounded_rate_without_raw_exception(listener):
    t = listener.test
    t.backend.fail_add = True
    for _ in range(100):
        listener.sync(t.scope, t.target)
    assert t.backend.attempts == 1
    assert "private provider data" not in str(t.statuses)
    t.clock[0] += 5
    t.backend.fail_add = False
    listener.sync(t.scope, t.target)
    assert t.backend.attempts == 2


def test_failed_cleanup_stops_rebinding_and_close_discards_late_callbacks(listener):
    t = listener.test
    listener.sync(t.scope, t.target)
    t.backend.fail_remove = True
    listener.sync(None, None)
    listener.sync(t.scope, t.target)
    assert t.backend.attempts == 1
    assert "cleanup failed" in t.statuses[-1]
    t.backend.added[0].callback("Name", "001234")
    assert not t.events
    t.backend.fail_remove = False
    listener.close()
    listener.close()
    assert listener._retired is None


@pytest.fixture
def com_backend(monkeypatch):
    import comtypes
    import comtypes.client

    dll = comtypes.client.GetModule("UIAutomationCore.dll")
    properties, added, removed = [], [], []
    cache = SimpleNamespace(AddProperty=properties.append)
    uia = SimpleNamespace(
        CreateCacheRequest=lambda: cache,
        AddPropertyChangedEventHandlerNativeArray=lambda *args: added.append(args),
        RemovePropertyChangedEventHandler=lambda *args: removed.append(args),
    )
    monkeypatch.setattr(comtypes, "CoCreateInstance", lambda *args, **kwargs: uia)
    result = UiaChartBackend()
    element = SimpleNamespace(CurrentProcessId=42, GetRuntimeId=lambda: (42, 110),
                              CurrentControlType=dll.UIA_TextControlTypeId)
    target = ChartTarget(SignalScope(42, 100, 101), SimpleNamespace(element_info=SimpleNamespace(element=element)), 110)
    result.test = SimpleNamespace(properties=properties, added=added, removed=removed, element=element,
                                 cache=cache, target=target)
    return result


def test_backend_only_subscribes_relevant_properties_on_exact_element(com_backend):
    b, t, dll = com_backend, com_backend.test, com_backend.dll
    subscription = b.subscribe(t.target, (42, 110), lambda *args: None, lambda: None)
    assert t.added == [(t.element, dll.TreeScope_Element, t.cache, subscription.handler, b.properties, 4)]
    assert set(b.properties) == {
        dll.UIA_NamePropertyId, dll.UIA_ValueValuePropertyId,
        dll.UIA_LegacyIAccessibleNamePropertyId, dll.UIA_LegacyIAccessibleValuePropertyId,
    }
    assert set(t.properties) == {dll.UIA_ProcessIdPropertyId, dll.UIA_RuntimeIdPropertyId, dll.UIA_ControlTypePropertyId}
    b.unsubscribe(subscription)
    assert not subscription.handler.active
    assert t.removed == [(t.element, subscription.handler)]


@pytest.mark.parametrize("changed", ["process", "type", "runtime"])
def test_backend_rejects_changed_identity_before_subscription(com_backend, changed):
    element = com_backend.test.element
    if changed == "process":
        element.CurrentProcessId = 43
    elif changed == "type":
        element.CurrentControlType = 0
    else:
        element.GetRuntimeId = lambda: (42, 111)
    with pytest.raises(ValueError, match="identity changed"):
        com_backend.subscribe(com_backend.test.target, (42, 110), lambda *args: None, lambda: None)
    assert not com_backend.test.added


def test_handler_accepts_cached_identity_and_variant_payload_without_live_reads(com_backend):
    from comtypes.automation import VARIANT

    b = com_backend
    calls, rejected = [], []
    subscription = b.subscribe(b.test.target, (42, 110), lambda *args: calls.append(args), lambda: rejected.append(True))
    sender = SimpleNamespace(CachedProcessId=42, GetCachedPropertyValue=lambda prop: (42, 110),
                             CachedControlType=b.dll.UIA_TextControlTypeId)
    handler = subscription.handler
    handler.HandlePropertyChangedEvent(sender, b.dll.UIA_NamePropertyId, VARIANT("000456"))
    assert calls == [("Name", "000456")]
    handler.HandlePropertyChangedEvent(sender, b.dll.UIA_IsEnabledPropertyId, VARIANT(True))
    assert len(calls) == 1
    sender.GetCachedPropertyValue = lambda prop: (42, 111)
    handler.HandlePropertyChangedEvent(sender, b.dll.UIA_NamePropertyId, "001234")
    handler.HandlePropertyChangedEvent(SimpleNamespace(), b.dll.UIA_NamePropertyId, "001234")
    assert rejected == [True]
    b.unsubscribe(subscription)
    sender.GetCachedPropertyValue = lambda prop: (42, 110)
    handler.HandlePropertyChangedEvent(sender, b.dll.UIA_NamePropertyId, "001234")
    assert len(calls) == 1
    interface = handler.QueryInterface(b.dll.IUIAutomationPropertyChangedEventHandler)
    interface.HandlePropertyChangedEvent(None, b.dll.UIA_NamePropertyId, VARIANT("001234"))


def test_real_property_event_on_our_own_hidden_text():
    import os
    import threading
    import time

    import pythoncom
    import win32gui
    import comtypes  # Bootstrap on this STA thread before the MTA worker.

    parent = win32gui.CreateWindowEx(0, "STATIC", "probe-test", 0, 0, 0, 100, 100, 0, 0, 0, None)
    text = win32gui.CreateWindowEx(0, "STATIC", "001234", 0x40000000, 0, 0, 80, 20, parent, 1234, 0, None)
    done = threading.Event()
    ready, stop = threading.Event(), threading.Event()
    errors = []
    received, rejected = [], []

    def run():
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        backend = subscription = None
        try:
            backend = UiaChartBackend()
            element = backend.uia.ElementFromHandle(text)
            target = ChartTarget(SignalScope(os.getpid(), parent, parent),
                                 SimpleNamespace(element_info=SimpleNamespace(element=element)), text)
            subscription = backend.subscribe(
                target, tuple(element.GetRuntimeId()), lambda *args: received.append(args),
                lambda: rejected.append(True),
            )
            ready.set()
            stop.wait(10)
        except Exception as error:
            errors.append(error)
        finally:
            if subscription is not None:
                backend.unsubscribe(subscription)
            pythoncom.CoUninitialize()
            done.set()

    worker = threading.Thread(target=run, daemon=True)
    try:
        worker.start()
        deadline = time.monotonic() + 10
        changed = False
        while not received and not done.is_set() and time.monotonic() < deadline:
            win32gui.PumpWaitingMessages()
            if ready.is_set() and not changed:
                win32gui.SetWindowText(text, "000456")
                changed = True
            time.sleep(0.01)
        assert ("Name", "000456") in received
        assert not rejected
        assert not errors
    finally:
        stop.set()
        deadline = time.monotonic() + 5
        while not done.wait(0.01) and time.monotonic() < deadline:
            win32gui.PumpWaitingMessages()
        win32gui.DestroyWindow(parent)
        worker.join(timeout=1)
        assert not worker.is_alive()
