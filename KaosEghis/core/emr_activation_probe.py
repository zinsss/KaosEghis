"""Scoped UIA Invoked-event observation; no control invocation or DB access."""

from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class _Subscription:
    element: object
    handler: object


class UiaInvokeBackend:
    """Created, subscribed and released on the probe's single MTA worker."""

    def __init__(self):
        import comtypes
        import comtypes.client

        dll = comtypes.client.GetModule("UIAutomationCore.dll")
        self.dll = dll
        self.uia = comtypes.CoCreateInstance(
            dll.CUIAutomation._reg_clsid_, interface=dll.IUIAutomation,
            clsctx=comtypes.CLSCTX_INPROC_SERVER,
        )
        event_id = dll.UIA_Invoke_InvokedEventId

        class Handler(comtypes.COMObject):
            _com_interfaces_ = [dll.IUIAutomationEventHandler]

            def __init__(self, identity, callback, rejected):
                super().__init__()
                self.identity = identity
                self.callback = callback
                self.rejected = rejected
                self.reported_invalid = False
                self.active = True

            def HandleAutomationEvent(self, sender, received_id):
                try:
                    if self.active and received_id == event_id and sender:
                        # Event-cache metadata only. Never read patient text or
                        # query the live provider from a callback thread.
                        identity = (
                            sender.CachedProcessId, sender.CachedAutomationId,
                            sender.CachedNativeWindowHandle, sender.CachedControlType,
                        )
                        if identity == self.identity and self.active:
                            self.callback()
                        elif self.active:
                            self._invalid()
                except Exception:
                    self._invalid()
                return 0

            def _invalid(self):
                if self.active and not self.reported_invalid:
                    self.reported_invalid = True
                    try:
                        self.rejected()
                    except Exception:
                        pass

        self.handler_type = Handler
        self.cache = self.uia.CreateCacheRequest()
        self.cache.TreeScope = dll.TreeScope_Element
        self.cache.AutomationElementMode = dll.AutomationElementMode_None
        for property_id in (
            dll.UIA_ProcessIdPropertyId, dll.UIA_AutomationIdPropertyId,
            dll.UIA_NativeWindowHandlePropertyId, dll.UIA_ControlTypePropertyId,
        ):
            self.cache.AddProperty(property_id)

    def subscribe(self, pid, automation_id, handle, callback, rejected):
        element = self.uia.ElementFromHandle(handle)
        identity = (pid, automation_id, handle, self.dll.UIA_ButtonControlTypeId)
        if (
            element.CurrentProcessId, element.CurrentAutomationId,
            element.CurrentNativeWindowHandle, element.CurrentControlType,
        ) != identity:
            raise ValueError("Activation target identity changed")
        handler = self.handler_type(identity, callback, rejected)
        try:
            self.uia.AddAutomationEventHandler(
                self.dll.UIA_Invoke_InvokedEventId, element,
                self.dll.TreeScope_Element, self.cache, handler,
            )
        except Exception:
            handler.active = False
            raise
        return _Subscription(element, handler)

    def unsubscribe(self, subscription):
        # Late COM callbacks can arrive during/after removal.
        subscription.handler.active = False
        self.uia.RemoveAutomationEventHandler(
            self.dll.UIA_Invoke_InvokedEventId, subscription.element, subscription.handler,
        )


class UiaActivationListener:
    """Maintain only the two already-discovered treatment-button subscriptions."""

    def __init__(self, capture, reader, *, backend_factory=UiaInvokeBackend, clock=time.monotonic):
        self.capture = capture
        self.reader = reader
        self.backend_factory = backend_factory
        self.clock = clock
        self._backend = None
        self._scope = None
        self._subscriptions = {}
        self._retired = []
        self._next_attempt = 0.0
        self._last_status = ""
        self._disabled = False

    def _status(self, text):
        if text != self._last_status:
            self._last_status = text
            self.capture._emit(f"EMR probe | {text}")

    def _remove(self, key):
        subscription = self._subscriptions.pop(key)
        try:
            self._backend.unsubscribe(subscription)
        except Exception:
            self._retired.append(subscription)
            self._disabled = True

    def sync(self, scope, buttons):
        if self._disabled:
            return
        if scope != self._scope:
            for key in tuple(self._subscriptions):
                self._remove(key)
            self._scope = scope
            self._next_attempt = 0.0
        if self._disabled:
            self._cleanup_failure()
            return
        if scope is None:
            self._status("UIA activation listener waiting for EMR connection.")
            return

        # A modal may temporarily prevent sampling. Keep subscriptions on the
        # still-existing buttons so an activation delivered after it opens is seen.
        wanted = set(self._subscriptions) if buttons is None else {
            (source.split()[0], handle) for source, handle in buttons
            if source in {"F6 button", "F7 button"} and handle
        }
        wanted = {
            key for key in wanted
            if self.reader.buttons_live(scope, ((f"{key[0]} button", key[1]),))
        }
        for key in tuple(self._subscriptions):
            if key not in wanted:
                self._remove(key)
        if self._disabled:
            self._cleanup_failure()
            return

        missing = wanted - self._subscriptions.keys()
        if missing and self.clock() >= self._next_attempt:
            self._next_attempt = self.clock() + 5.0
            for source, handle in sorted(missing):
                try:
                    if self._backend is None:
                        self._backend = self.backend_factory()
                    subscription = self._backend.subscribe(
                        scope.pid, f"Btn{source}", handle,
                        lambda source=source, handle=handle, scope=scope:
                            self.capture.activation_event(source, scope, handle),
                        lambda source=source: self.capture._emit(
                            f"EMR probe | {source} UIA callback received, but sender identity was not verified."
                        ),
                    )
                    self._subscriptions[(source, handle)] = subscription
                except Exception:
                    if self._backend is None:
                        break
        registered = sorted(source for source, _ in self._subscriptions)
        if registered:
            text = f"UIA activation subscribed: {', '.join(registered)} (event delivery not yet verified)."
            if wanted - self._subscriptions.keys():
                text += " Other button subscription failed; retrying."
            self._status(text)
        elif wanted:
            self._status("UIA activation subscription unavailable; retrying. Keyboard/mouse probe remains active.")
        else:
            self._status("UIA activation listener waiting for EMR F6/F7 buttons.")

    def _cleanup_failure(self):
        self.close()
        self._status("UIA activation cleanup failed; listener stopped. Keyboard/mouse probe remains active.")

    def close(self):
        self._disabled = True
        for key in tuple(self._subscriptions):
            self._remove(key)
        # Keep failed removals inert and referenced; retry only at cleanup,
        # never accumulate another set of subscriptions on every sample.
        retired, self._retired = self._retired, []
        for subscription in retired:
            try:
                self._backend.unsubscribe(subscription)
            except Exception:
                self._retired.append(subscription)
