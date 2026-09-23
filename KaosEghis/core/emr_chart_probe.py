"""Passive chart-field property events, separate from sampled patient identity."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from datetime import datetime
import re
import time


@dataclass(frozen=True)
class ChartTarget:
    scope: object
    node: object = field(repr=False)
    owner_handle: int


@dataclass(frozen=True)
class ChartFieldObservation:
    source: str
    chart_no: str = field(repr=False)
    detail: str
    clock_text: str

    @classmethod
    def from_event(cls, property_name, value):
        source = f"Chart field event (UIA {property_name})"
        chart_no = ""
        detail = "Event payload is not text; not displayed"
        if value is None:
            detail = "Event payload missing; chart clear/change not confirmed"
        elif isinstance(value, str):
            value = value.strip()
            if not value:
                detail = "Chart field cleared"
            elif re.fullmatch(r"[0-9]{1,20}", value):
                chart_no = value
                detail = "load completion unverified"
            elif re.fullmatch(r"[0-9]+", value):
                detail = "Event numeric text exceeds chart-number length limit; not displayed"
            else:
                detail = "Event text is not a numeric chart number; not displayed"
        return cls(source, chart_no, detail, datetime.now().strftime("%H:%M:%S"))

    def status_text(self):
        detail = f"Chart {self.chart_no} ({self.detail})" if self.chart_no else self.detail
        return f"{self.clock_text} | EMR probe | {self.source} | {detail}"


@dataclass
class _Subscription:
    element: object = field(repr=False)
    handler: object = field(repr=False)


class UiaChartBackend:
    """Used only by the same MTA worker that manages button event handlers."""

    def __init__(self):
        import comtypes
        import comtypes.client
        from comtypes.automation import VARIANT

        dll = comtypes.client.GetModule("UIAutomationCore.dll")
        self.dll = dll
        self.uia = comtypes.CoCreateInstance(
            dll.CUIAutomation._reg_clsid_, interface=dll.IUIAutomation,
            clsctx=comtypes.CLSCTX_INPROC_SERVER,
        )
        properties = {
            dll.UIA_NamePropertyId: "Name",
            dll.UIA_ValueValuePropertyId: "Value",
            dll.UIA_LegacyIAccessibleNamePropertyId: "LegacyName",
            dll.UIA_LegacyIAccessibleValuePropertyId: "LegacyValue",
        }
        self.properties = (ctypes.c_int * len(properties))(*properties)

        class Handler(comtypes.COMObject):
            _com_interfaces_ = [dll.IUIAutomationPropertyChangedEventHandler]

            def __init__(self, identity, callback, rejected):
                super().__init__()
                self.identity = identity
                self.callback = callback
                self.rejected = rejected
                self.active = True
                self.reported_invalid = False

            def HandlePropertyChangedEvent(self, sender, property_id, new_value):
                try:
                    if self.active and sender and property_id in properties:
                        identity = (
                            sender.CachedProcessId,
                            tuple(sender.GetCachedPropertyValue(dll.UIA_RuntimeIdPropertyId)),
                            sender.CachedControlType,
                        )
                        if identity == self.identity and self.active:
                            value = new_value.value if isinstance(new_value, VARIANT) else new_value
                            self.callback(properties[property_id], value)
                        else:
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
        for property_id in (dll.UIA_ProcessIdPropertyId, dll.UIA_RuntimeIdPropertyId, dll.UIA_ControlTypePropertyId):
            self.cache.AddProperty(property_id)

    def subscribe(self, target, runtime_id, callback, rejected):
        element = target.node.element_info.element
        identity = (target.scope.pid, runtime_id, self.dll.UIA_TextControlTypeId)
        if (element.CurrentProcessId, tuple(element.GetRuntimeId()), element.CurrentControlType) != identity:
            raise ValueError("Chart event target identity changed")
        handler = self.handler_type(identity, callback, rejected)
        try:
            self.uia.AddPropertyChangedEventHandlerNativeArray(
                element, self.dll.TreeScope_Element, self.cache, handler,
                self.properties, len(self.properties),
            )
        except Exception:
            handler.active = False
            raise
        return _Subscription(element, handler)

    def unsubscribe(self, subscription):
        subscription.handler.active = False
        self.uia.RemovePropertyChangedEventHandler(subscription.element, subscription.handler)


class UiaChartListener:
    def __init__(self, capture, reader, *, backend_factory=UiaChartBackend, clock=time.monotonic):
        self.capture = capture
        self.reader = reader
        self.backend_factory = backend_factory
        self.clock = clock
        self._backend = None
        self._scope = None
        self._target = None
        self._runtime_id = None
        self._subscription = None
        self._retired = None
        self._generation = 0
        self._next_attempt = 0.0
        self._last_status = ""
        self._disabled = False

    def _status(self, text):
        if text != self._last_status:
            self._last_status = text
            self.capture._emit(f"EMR probe | {text}")

    def _detach(self):
        self._generation += 1
        subscription, self._subscription = self._subscription, None
        self._target = self._runtime_id = None
        if subscription is not None:
            try:
                self._backend.unsubscribe(subscription)
            except Exception:
                self._retired = subscription
                self._disabled = True
                self._status("UIA chart listener cleanup failed; stopped. Other probes remain active.")

    def sync(self, scope, target):
        if self._disabled:
            return
        if scope != self._scope:
            self._detach()
            self._scope = scope
            self._next_attempt = 0.0
        if self._disabled:
            return
        if scope is None:
            self._status("UIA chart listener waiting for EMR connection.")
            return
        if self._target and not self.reader.chart_target_live(scope, self._target.owner_handle):
            self._detach()
        if self._disabled:
            return
        if target is None or target.scope != scope:
            if self._subscription is None:
                self._status("UIA chart listener waiting for a verified numeric chart field.")
            return
        if not self.reader.chart_target_live(scope, target.owner_handle):
            return
        if self._subscription and self._target.node is target.node:
            return
        try:
            runtime_id = tuple(target.node.element_info.runtime_id or ())
            if not runtime_id:
                raise ValueError("Chart field runtime identity unavailable")
        except Exception:
            self._detach()
            self._status("UIA chart listener could not verify the current field identity.")
            return
        if self._subscription and runtime_id == self._runtime_id:
            self._target = target
            return
        if self._subscription is not None:
            self._next_attempt = 0.0
        self._detach()
        if self._disabled or self.clock() < self._next_attempt:
            return
        self._next_attempt = self.clock() + 5.0
        generation = self._generation

        def active():
            return not self._disabled and generation == self._generation

        def changed(property_name, value):
            if active():
                self.capture.chart_property_event(scope, property_name, value)

        def rejected():
            if active():
                self.capture._emit("EMR probe | Chart UIA callback received, but sender identity was not verified.")

        try:
            if self._backend is None:
                self._backend = self.backend_factory()
            self._subscription = self._backend.subscribe(target, runtime_id, changed, rejected)
            self._target, self._runtime_id = target, runtime_id
            self._status("UIA chart change subscribed (Name/Value; event delivery not yet verified).")
        except Exception:
            self._status("UIA chart subscription unavailable; retrying. Sampled chart probe remains active.")

    def close(self):
        self._disabled = True
        self._detach()
        if self._retired is not None:
            try:
                self._backend.unsubscribe(self._retired)
                self._retired = None
            except Exception:
                pass
