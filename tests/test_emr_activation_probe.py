from dataclasses import replace
from types import SimpleNamespace

import pytest

from KaosEghis.core.emr_activation_probe import UiaActivationListener, UiaInvokeBackend
from KaosEghis.core.emr_signal_probe import SignalScope


class Backend:
    def __init__(self):
        self.added = []
        self.removed = []
        self.fail_add = set()
        self.fail_remove = False
        self.attempts = []

    def subscribe(self, pid, automation_id, handle, callback, rejected):
        self.attempts.append(handle)
        if handle in self.fail_add:
            raise RuntimeError("private provider detail")
        result = SimpleNamespace(pid=pid, automation_id=automation_id, handle=handle,
                                 callback=callback, active=True)
        self.added.append(result)
        return result

    def unsubscribe(self, subscription):
        subscription.active = False
        self.removed.append(subscription)
        if self.fail_remove:
            raise RuntimeError("private provider detail")


@pytest.fixture
def listener():
    backend = Backend()
    statuses, events = [], []
    capture = SimpleNamespace(_emit=statuses.append, activation_event=lambda *args: events.append(args))
    live = {106, 107, 108}
    reader = SimpleNamespace(buttons_live=lambda scope, buttons: all(h in live for _, h in buttons))
    clock = [10.0]
    result = UiaActivationListener(capture, reader, backend_factory=lambda: backend, clock=lambda: clock[0])
    result.test = SimpleNamespace(backend=backend, statuses=statuses, events=events, live=live, clock=clock,
                                 scope=SignalScope(42, 100, 101), buttons=(("F6 button", 106), ("F7 button", 107)))
    return result


def test_subscriptions_use_existing_button_handles_and_stay_idle(listener):
    t = listener.test
    listener.sync(t.scope, t.buttons)
    for _ in range(100):
        listener.sync(t.scope, t.buttons)
    assert [(s.automation_id, s.handle) for s in t.backend.added] == [("BtnF6", 106), ("BtnF7", 107)]
    assert t.backend.attempts == [106, 107]
    assert not t.backend.removed
    assert len(t.statuses) == 1
    assert "event delivery not yet verified" in t.statuses[0]
    for subscription in t.backend.added:
        subscription.callback()
    assert t.events == [("F6", t.scope, 106), ("F7", t.scope, 107)]


def test_modal_does_not_remove_subscriptions_but_disconnect_does(listener):
    t = listener.test
    listener.sync(t.scope, t.buttons)
    listener.sync(t.scope, None)
    assert not t.backend.removed
    listener.sync(None, None)
    assert len(t.backend.removed) == 2
    assert all(not s.active for s in t.backend.added)
    listener.sync(t.scope, t.buttons)
    assert len(t.backend.added) == 4


def test_restart_or_recreated_button_rebuilds_only_necessary_subscriptions(listener):
    t = listener.test
    listener.sync(t.scope, t.buttons)
    new_buttons = (("F6 button", 106), ("F7 button", 108))
    listener.sync(t.scope, new_buttons)
    t.clock[0] += 5
    listener.sync(t.scope, new_buttons)
    assert [s.handle for s in t.backend.removed] == [107]
    assert [s.handle for s in t.backend.added] == [106, 107, 108]
    listener.sync(replace(t.scope, pid=43), new_buttons)
    assert [s.pid for s in t.backend.added[-2:]] == [43, 43]


def test_destroyed_buttons_are_removed_even_when_sampler_is_unavailable(listener):
    t = listener.test
    listener.sync(t.scope, t.buttons)
    t.live.remove(107)
    listener.sync(t.scope, None)
    assert [s.handle for s in t.backend.removed] == [107]


def test_failed_registration_retries_at_five_seconds_without_duplicate_handlers(listener):
    t = listener.test
    t.backend.fail_add.add(107)
    listener.sync(t.scope, t.buttons)
    listener.sync(t.scope, t.buttons)
    assert t.backend.attempts == [106, 107]
    t.clock[0] += 5
    t.backend.fail_add.clear()
    listener.sync(t.scope, t.buttons)
    assert t.backend.attempts == [106, 107, 107]
    assert "private provider detail" not in str(t.statuses)


def test_failed_backend_initialization_is_bounded_and_does_not_raise(listener):
    t = listener.test
    calls = []

    def fail():
        calls.append(True)
        raise RuntimeError("private provider detail")

    listener.backend_factory = fail
    listener.sync(t.scope, t.buttons)
    listener.sync(t.scope, t.buttons)
    assert len(calls) == 1
    assert "unavailable" in t.statuses[-1]
    assert "private provider detail" not in str(t.statuses)


def test_cleanup_failure_disables_listener_without_accumulating_subscriptions(listener):
    t = listener.test
    listener.sync(t.scope, t.buttons)
    t.backend.fail_remove = True
    listener.sync(None, None)
    for _ in range(100):
        listener.sync(t.scope, t.buttons)
    assert len(t.backend.added) == 2
    assert all(not s.active for s in t.backend.added)
    assert "cleanup failed" in t.statuses[-1]
    t.backend.fail_remove = False
    listener.close()
    assert not listener._retired


def test_close_is_idempotent_and_disallows_more_subscriptions(listener):
    t = listener.test
    listener.sync(t.scope, t.buttons)
    listener.close()
    listener.close()
    listener.sync(t.scope, t.buttons)
    assert len(t.backend.added) == len(t.backend.removed) == 2


@pytest.fixture
def com_backend(monkeypatch):
    import comtypes
    import comtypes.client

    dll = comtypes.client.GetModule("UIAutomationCore.dll")
    properties, added, removed = [], [], []
    cache = SimpleNamespace(AddProperty=properties.append)
    element = SimpleNamespace(CurrentProcessId=42, CurrentAutomationId="BtnF7",
                              CurrentNativeWindowHandle=107, CurrentControlType=dll.UIA_ButtonControlTypeId)
    uia = SimpleNamespace(
        CreateCacheRequest=lambda: cache, ElementFromHandle=lambda handle: element,
        AddAutomationEventHandler=lambda *args: added.append(args),
        RemoveAutomationEventHandler=lambda *args: removed.append(args),
    )
    monkeypatch.setattr(comtypes, "CoCreateInstance", lambda *args, **kwargs: uia)
    result = UiaInvokeBackend()
    result.test = SimpleNamespace(properties=properties, added=added, removed=removed, element=element, cache=cache)
    return result


def test_backend_subscribes_exact_element_with_non_patient_metadata_cache(com_backend):
    backend, t, dll = com_backend, com_backend.test, com_backend.dll
    subscription = backend.subscribe(42, "BtnF7", 107, lambda: None, lambda: None)
    assert t.added == [(dll.UIA_Invoke_InvokedEventId, t.element, dll.TreeScope_Element, t.cache, subscription.handler)]
    assert set(t.properties) == {
        dll.UIA_ProcessIdPropertyId, dll.UIA_AutomationIdPropertyId,
        dll.UIA_NativeWindowHandlePropertyId, dll.UIA_ControlTypePropertyId,
    }
    assert t.cache.AutomationElementMode == dll.AutomationElementMode_None
    backend.unsubscribe(subscription)
    assert not subscription.handler.active
    assert t.removed == [(dll.UIA_Invoke_InvokedEventId, t.element, subscription.handler)]


@pytest.mark.parametrize("property_name,value", [
    ("CurrentProcessId", 43), ("CurrentAutomationId", "Other"),
    ("CurrentNativeWindowHandle", 999), ("CurrentControlType", 0),
])
def test_backend_does_not_subscribe_changed_target(com_backend, property_name, value):
    setattr(com_backend.test.element, property_name, value)
    with pytest.raises(ValueError, match="identity changed"):
        com_backend.subscribe(42, "BtnF7", 107, lambda: None, lambda: None)
    assert not com_backend.test.added


def test_com_handler_uses_cached_identity_and_ignores_other_events_or_late_callbacks(com_backend):
    backend = com_backend
    calls, rejected = [], []
    subscription = backend.subscribe(42, "BtnF7", 107, lambda: calls.append(True), lambda: rejected.append(True))
    sender = SimpleNamespace(CachedProcessId=42, CachedAutomationId="BtnF7",
                             CachedNativeWindowHandle=107, CachedControlType=backend.dll.UIA_ButtonControlTypeId)
    handler = subscription.handler
    event_id = backend.dll.UIA_Invoke_InvokedEventId
    assert handler.HandleAutomationEvent(sender, event_id + 1) == 0
    assert not calls
    assert handler.HandleAutomationEvent(sender, event_id) == 0
    assert calls == [True]
    sender.CachedProcessId = 43
    handler.HandleAutomationEvent(sender, event_id)
    handler.HandleAutomationEvent(SimpleNamespace(), event_id)
    assert calls == [True]
    assert rejected == [True]
    backend.unsubscribe(subscription)
    sender.CachedProcessId = 42
    handler.HandleAutomationEvent(sender, event_id)
    assert calls == [True]
    # Exercise the generated COM vtable, without invoking any actual UI control.
    interface = handler.QueryInterface(backend.dll.IUIAutomationEventHandler)
    interface.HandleAutomationEvent(None, event_id)


def test_com_removal_failure_still_makes_late_callbacks_inert(com_backend):
    subscription = com_backend.subscribe(42, "BtnF7", 107, lambda: pytest.fail("late callback"), lambda: None)
    com_backend.uia.RemoveAutomationEventHandler = lambda *args: 1 / 0
    with pytest.raises(ZeroDivisionError):
        com_backend.unsubscribe(subscription)
    assert not subscription.handler.active


def test_real_uia_registration_roundtrip_on_our_own_hidden_button():
    import os
    import threading
    import time

    import pythoncom
    import win32gui

    parent = win32gui.CreateWindowEx(0, "STATIC", "probe-test", 0, 0, 0, 100, 100, 0, 0, 0, None)
    button = win32gui.CreateWindowEx(0, "BUTTON", "probe-test", 0x40000000, 0, 0, 80, 20, parent, 1234, 0, None)
    done = threading.Event()
    errors = []

    def run():
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        try:
            backend = UiaInvokeBackend()
            element = backend.uia.ElementFromHandle(button)
            subscription = backend.subscribe(
                os.getpid(), element.CurrentAutomationId, button, lambda: None, lambda: None,
            )
            backend.unsubscribe(subscription)
        except Exception as error:
            errors.append(error)
        finally:
            pythoncom.CoUninitialize()
            done.set()

    worker = threading.Thread(target=run, daemon=True)
    try:
        worker.start()
        deadline = time.monotonic() + 10
        while not done.wait(0.01) and time.monotonic() < deadline:
            win32gui.PumpWaitingMessages()
        assert done.is_set(), "Our test button's UIA registration did not complete"
        assert not errors
    finally:
        win32gui.DestroyWindow(parent)
        worker.join(timeout=1)
