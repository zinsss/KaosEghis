"""Passive, memory-only order-signal diagnostics. No DB access or input injection."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
import queue
import re
import sys
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from KaosEghis.core.eghis_connector import get_cached_eghis_state
from KaosEghis.core.emr_activation_probe import UiaActivationListener
from KaosEghis.core.emr_chart_probe import ChartFieldObservation, ChartTarget, UiaChartListener
from KaosEghis.core.ui_capture import _best_text_value
from KaosEghis.core.uia_fast_lookup import find_uia_elements_by_automation_ids


CHART_POINT = (205, 115)
CHART_REDISCOVERY_INTERVAL = 1.0
MAX_SNAPSHOT_AGE = 0.75
TREATMENT_TITLE = "\uc9c4\ub8cc\uc2e4"


@dataclass(frozen=True)
class SignalScope:
    pid: int
    root: int
    treatment: int


def connected_scope(state) -> SignalScope | None:
    if state is None or state.status not in {"green", "yellow"}:
        return None
    if not (state.pid and state.window_handle and state.main_window_handle):
        return None
    return SignalScope(state.pid, state.window_handle, state.main_window_handle)


@dataclass(frozen=True)
class SignalSnapshot:
    scope: SignalScope
    buttons: tuple[tuple[str, int], ...]
    chart_no: str = field(repr=False)
    sampled_at: float
    unavailable_reason: str = ""


@dataclass(frozen=True)
class SignalObservation:
    source: str
    chart_no: str = field(repr=False)
    age_ms: int | None
    clock_text: str
    unavailable_reason: str = ""

    def status_text(self) -> str:
        detail = (
            f"Chart {self.chart_no} (snapshot {self.age_ms} ms)"
            if self.chart_no else
            f"Chart unavailable ({self.unavailable_reason or 'no fresh snapshot'})"
        )
        return f"{self.clock_text} | EMR probe | {self.source} | {detail}"


class _ChartUnavailable(Exception):
    """Only fixed, non-patient diagnostic messages belong in this exception."""


def _chart_error_reason(error: Exception) -> str:
    if isinstance(error, _ChartUnavailable):
        return str(error)
    if getattr(error, "hresult", None) == -2147024891 or getattr(error, "winerror", None) == 5:
        return "UIA access denied; check KaosEghis/EMR administrator levels"
    return "UIA chart read failed; target will be reacquired"


class _GuiThreadInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class Win32SignalReader:
    def __init__(self, *, clock=time.monotonic) -> None:
        import win32api
        import win32gui
        import win32process

        self.gui = win32gui
        self.api = win32api
        self.process = win32process
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetGUIThreadInfo.argtypes = [
            wintypes.DWORD, ctypes.POINTER(_GuiThreadInfo),
        ]
        self.user32.GetGUIThreadInfo.restype = wintypes.BOOL
        self.user32.SendMessageTimeoutW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
            wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
        ]
        self.user32.SendMessageTimeoutW.restype = wintypes.LPARAM
        self._chart_identity = None
        self._chart_node = None
        self._chart_retry = None
        self._clock = clock
        self.chart_target = None

    def _belongs(self, parent: int, child: int) -> bool:
        return bool(child and (parent == child or self.gui.IsChild(parent, child)))

    def _live(self, scope: SignalScope, *, require_foreground=True) -> bool:
        return bool(
            self.gui.IsWindow(scope.root)
            and self.gui.IsWindow(scope.treatment)
            and self.process.GetWindowThreadProcessId(scope.root)[1] == scope.pid
            and self._belongs(scope.root, scope.treatment)
            and self.gui.IsWindowVisible(scope.treatment)
            and self.gui.IsWindowEnabled(scope.root)
            and self.gui.IsWindowEnabled(scope.treatment)
            and (not require_foreground or self.gui.GetForegroundWindow() == scope.root)
        )

    def keyboard_context(self, scope: SignalScope) -> bool:
        if not self._live(scope):
            return False
        info = _GuiThreadInfo(cbSize=ctypes.sizeof(_GuiThreadInfo))
        if not self.user32.GetGUIThreadInfo(0, ctypes.byref(info)):
            return False
        # Menus, moving windows, modals and other MDI pages are not order entry.
        return bool(
            not info.flags & 0x1E
            and int(info.hwndActive or 0) == scope.root
            and self._belongs(scope.treatment, int(info.hwndFocus or 0))
        )

    def modifiers_down(self) -> bool:
        return any(self.api.GetAsyncKeyState(key) & 0x8000 for key in (16, 17, 18, 91, 92))

    def button_at(self, snapshot: SignalSnapshot, point: tuple[int, int]) -> str | None:
        if not self._live(snapshot.scope, require_foreground=False):
            return None
        hit = self.gui.WindowFromPoint(point)
        for source, handle in snapshot.buttons:
            if (
                self._belongs(snapshot.scope.treatment, handle)
                and self.gui.IsWindowVisible(handle)
                and self.gui.IsWindowEnabled(handle)
                and self._belongs(handle, hit)
            ):
                return source
        return None

    def _text(self, handle: int) -> str:
        # Only the sampling worker calls WM_GETTEXT; never an input-hook thread.
        buffer = ctypes.create_unicode_buffer(128)
        result = ctypes.c_size_t()
        ok = self.user32.SendMessageTimeoutW(
            handle, 0x000D, len(buffer), ctypes.addressof(buffer),
            0x0002 | 0x0020, 30, ctypes.byref(result),
        )
        return buffer.value.strip() if ok else ""

    def treatment_ready(self, scope: SignalScope) -> bool:
        return (
            self._live(scope, require_foreground=False)
            and self._text(scope.treatment) == TREATMENT_TITLE
        )

    def discover_buttons(self, scope: SignalScope) -> tuple[tuple[str, int], ...]:
        matches = find_uia_elements_by_automation_ids(
            ("BtnF6", "BtnF7"), root_handle=scope.treatment,
            process_ids=(scope.pid,), control_type="Button",
        )
        result = []
        for key in ("F6", "F7"):
            handles = {
                int(node.element_info.handle or 0)
                for node in matches.get(f"Btn{key}", [])
                if node.is_visible() and node.is_enabled()
            }
            handles.discard(0)
            if len(handles) == 1:
                result.append((f"{key} button", handles.pop()))
        return tuple(result)

    def buttons_live(self, scope: SignalScope, buttons) -> bool:
        return all(
            self.gui.IsWindow(handle) and self._belongs(scope.treatment, handle)
            for _, handle in buttons
        )

    def chart_target_live(self, scope: SignalScope, handle: int) -> bool:
        identity = self._chart_identity
        return bool(
            identity is not None and identity[0] == scope and identity[2] == handle
            and self._chart_node is not None and self._chart_window_belongs(scope, handle)
        )

    def _chart_window_belongs(self, scope, handle) -> bool:
        if (
            not self.gui.IsWindow(scope.root)
            or self.process.GetWindowThreadProcessId(scope.root)[1] != scope.pid
        ):
            return False
        # eGHIS can host the chart label in a small owned window. IsChild alone
        # rejects it; follow a bounded parent/owner chain, checking every PID.
        pending, seen = [handle], set()
        while pending and len(seen) < 16:
            current = int(pending.pop() or 0)
            if not current or current in seen:
                continue
            seen.add(current)
            if (
                not self.gui.IsWindow(current)
                or self.process.GetWindowThreadProcessId(current)[1] != scope.pid
            ):
                continue
            if current == scope.root:
                return True
            pending.extend((self.gui.GetParent(current), self.gui.GetWindow(current, 4)))  # GW_OWNER
        return False

    def _chart_target_owner(self, scope, node, *, point=None) -> int:
        info = node.element_info
        if info.control_type != "Text":
            raise _ChartUnavailable("chart target is not a Text control")
        if info.process_id != scope.pid:
            raise _ChartUnavailable("chart target is not owned by the connected EMR")
        rect = info.rectangle
        if not info.visible or rect.right <= rect.left or rect.bottom <= rect.top:
            raise _ChartUnavailable("chart target is hidden or has invalid bounds")
        if point is not None and not (rect.left <= point[0] < rect.right and rect.top <= point[1] < rect.bottom):
            raise _ChartUnavailable("chart discovery point no longer matches the Text control")
        # Virtual UIA text can inherit its native window from an ancestor.
        for _ in range(8):
            handle = int(info.handle or 0)
            if handle:
                if self._chart_window_belongs(scope, handle):
                    return handle
                break
            info = info.parent
            if info is None or info.process_id != scope.pid:
                break
        raise _ChartUnavailable("chart target window ownership could not be confirmed")

    def chart_number(self, scope: SignalScope) -> str:
        self.chart_target = None
        if self._chart_identity is not None and self._chart_identity[0] != scope:
            self._chart_identity = self._chart_node = None
        # Focus loss invalidates a sample, not the discovered control itself.
        if not self.keyboard_context(scope):
            raise _ChartUnavailable("EMR treatment entry was not focused at sampling")
        node = self._chart_node
        if node is not None:
            try:
                owner = self._chart_target_owner(scope, node)
                identity = (scope, tuple(node.element_info.runtime_id or ()), owner)
                if identity != self._chart_identity:
                    node = None
            except Exception:
                node = None
        discovering = node is None
        if discovering and self._chart_retry is not None:
            retry_scope, retry_at, reason = self._chart_retry
            if retry_scope == scope and self._clock() < retry_at:
                raise _ChartUnavailable(reason)
        try:
            if discovering:
                self._chart_identity = self._chart_node = None
                hit = self.gui.WindowFromPoint(CHART_POINT)
                if not self._chart_window_belongs(scope, hit):
                    raise _ChartUnavailable(f"discovery point {CHART_POINT} is not in the connected EMR window hierarchy")
                from pywinauto import Desktop

                node = Desktop(backend="uia").from_point(*CHART_POINT)
                node.element_info.set_cache_strategy(False)
                owner = self._chart_target_owner(scope, node, point=CHART_POINT)
                runtime_id = tuple(node.element_info.runtime_id or ())
                if not runtime_id:
                    raise _ChartUnavailable("chart target runtime identity unavailable")
                identity = (scope, runtime_id, owner)
            # Follow the verified UIA instance, not a fixed desktop pixel, and
            # read current text every time. No previous patient value is reused.
            value = (_best_text_value(node) or "").strip()
            owner = self._chart_target_owner(scope, node, point=CHART_POINT if discovering else None)
            if (scope, tuple(node.element_info.runtime_id or ()), owner) != identity:
                raise _ChartUnavailable("chart target identity changed while reading")
            if discovering and self.gui.WindowFromPoint(CHART_POINT) != hit:
                raise _ChartUnavailable("chart discovery point changed while reading")
            # An arbitrary blank/non-numeric Text control must not become the
            # chart binding. A known chart may briefly clear during a switch.
            if value and not re.fullmatch(r"[0-9]{1,20}", value):
                raise _ChartUnavailable("chart UIA text is not numeric; rediscovering chart field")
            if discovering and not value:
                raise _ChartUnavailable("chart field not yet verified (empty text); retrying discovery")
        except Exception as error:
            self._chart_identity = self._chart_node = None
            self._chart_retry = (scope, self._clock() + CHART_REDISCOVERY_INTERVAL, _chart_error_reason(error))
            raise
        self._chart_identity, self._chart_node = identity, node
        self._chart_retry = None
        if not self.keyboard_context(scope):
            raise _ChartUnavailable("EMR focus changed while reading")
        self.chart_target = ChartTarget(scope, node, owner)
        if not value:
            raise _ChartUnavailable("chart UIA text is empty")
        return value


class EmrSignalSampler:
    def __init__(self, reader, state_provider=get_cached_eghis_state, clock=time.monotonic):
        self.reader = reader
        self.state_provider = state_provider
        self.clock = clock
        self._scope = None
        self._buttons = ()
        self._next_discovery = 0.0

    def sample(self) -> SignalSnapshot | None:
        scope = connected_scope(self.state_provider())
        if scope != self._scope:
            self._scope, self._buttons, self._next_discovery = scope, (), 0.0
        if scope is None or not self.reader.treatment_ready(scope):
            return None
        if not self.reader.buttons_live(scope, self._buttons):
            self._buttons, self._next_discovery = (), 0.0
        if len(self._buttons) != 2 and self.clock() >= self._next_discovery:
            self._next_discovery = self.clock() + 5.0
            try:
                self._buttons = self.reader.discover_buttons(scope)
            except Exception:
                self._buttons = ()
        sampled_at = self.clock()
        reason = ""
        try:
            chart_no = self.reader.chart_number(scope)
            if not chart_no:
                reason = "chart text unavailable"
        except Exception as error:
            chart_no = ""
            reason = _chart_error_reason(error)
        return SignalSnapshot(scope, self._buttons, chart_no, sampled_at, reason)


class EmrSignalCapture:
    """Hook callbacks only inspect native context and enqueue immutable snapshots."""

    def __init__(self, reader, output, state_provider=get_cached_eghis_state,
                 clock=time.monotonic):
        self.reader = reader
        self.output = output
        self.state_provider = state_provider
        self.clock = clock
        self.snapshot: SignalSnapshot | None = None
        self.enabled = True
        self.dropped_count = 0
        self._keys_down = set()
        self._mouse_down = None
        self._sample_scope = None
        self._sample_chart = ""

    def update_snapshot(self, snapshot) -> None:
        self.snapshot = snapshot
        scope = connected_scope(self.state_provider())
        if scope != self._sample_scope:
            self._sample_scope, self._sample_chart = scope, ""
        if not self.enabled or snapshot is None or snapshot.scope != scope:
            return
        if snapshot.chart_no and snapshot.chart_no != self._sample_chart:
            source = "Chart changed (sampled)" if self._sample_chart else "Chart observed (sampled)"
            self._sample_chart = snapshot.chart_no
            self._emit(ChartFieldObservation(
                source, snapshot.chart_no, "not a UIA event; load completion unverified",
                datetime.now().strftime("%H:%M:%S"),
            ))
        elif self._sample_chart and snapshot.unavailable_reason == "chart UIA text is empty":
            self._sample_chart = ""
            self._emit(ChartFieldObservation(
                "Chart field empty (sampled)", "", "not a UIA event", datetime.now().strftime("%H:%M:%S"),
            ))

    def chart_property_event(self, scope, property_name, value) -> None:
        if (
            self.enabled and connected_scope(self.state_provider()) == scope
            and property_name in {"Name", "Value", "LegacyName", "LegacyValue"}
        ):
            self._emit(ChartFieldObservation.from_event(property_name, value))

    def _current(self) -> SignalSnapshot | None:
        snapshot = self.snapshot
        if not self.enabled or snapshot is None:
            return None
        if connected_scope(self.state_provider()) != snapshot.scope:
            return None
        return snapshot

    def _observation(self, source, snapshot) -> SignalObservation:
        age = self.clock() - snapshot.sampled_at
        fresh = 0 <= age <= MAX_SNAPSHOT_AGE
        reason = snapshot.unavailable_reason
        if not fresh:
            reason = f"snapshot expired ({round(age * 1000)} ms)" if age >= 0 else "snapshot timing invalid"
        return SignalObservation(
            source, snapshot.chart_no if fresh else "",
            round(age * 1000) if fresh else None, datetime.now().strftime("%H:%M:%S"),
            reason,
        )

    def _emit(self, observation) -> None:
        try:
            self.output.put_nowait(observation)
        except queue.Full:
            self.dropped_count += 1

    def activation_event(self, source, scope, handle) -> None:
        try:
            if (
                not self.enabled or source not in {"F6", "F7"}
                or connected_scope(self.state_provider()) != scope
                or not self.reader.buttons_live(scope, ((f"{source} button", handle),))
            ):
                return
            label = f"{source} activation (UIA)"
            snapshot = self._current()
            if snapshot is not None and (f"{source} button", handle) in snapshot.buttons:
                observation = self._observation(label, snapshot)
            else:
                observation = SignalObservation(
                    label, "", None, datetime.now().strftime("%H:%M:%S"),
                    "no fresh snapshot at activation",
                )
            # Activation can arrive after a dialog takes focus. Its exact
            # subscribed source is still useful even without patient identity.
            self._emit(observation)
        except Exception:
            pass

    def keyboard_event(self, message, data) -> bool:
        try:
            key = int(data.vkCode)
            if key not in (0x75, 0x76) or data.flags & 0x10:
                return True
            if message in (0x0101, 0x0105):
                self._keys_down.discard(key)
                return True
            if message not in (0x0100, 0x0104) or key in self._keys_down:
                return True
            self._keys_down.add(key)
            snapshot = self._current()
            if (
                snapshot is not None and not self.reader.modifiers_down()
                and self.reader.keyboard_context(snapshot.scope)
            ):
                self._emit(self._observation("F6" if key == 0x75 else "F7", snapshot))
        except Exception:
            pass
        return True

    def mouse_event(self, message, data) -> bool:
        try:
            if message not in (0x0201, 0x0202) or data.flags & 0x01:
                return True
            snapshot = self._current()
            point = (int(data.pt.x), int(data.pt.y))
            source = self.reader.button_at(snapshot, point) if snapshot else None
            if message == 0x0201:
                self._mouse_down = (
                    (snapshot.scope, source, self._observation(source, snapshot), self.clock())
                    if source else None
                )
            else:
                pending, self._mouse_down = self._mouse_down, None
                if pending and source and (snapshot.scope, source) == pending[:2]:
                    observation = pending[2]
                    age_ms = (
                        observation.age_ms + round((self.clock() - pending[3]) * 1000)
                        if observation.age_ms is not None else None
                    )
                    if not observation.chart_no:
                        pass  # Preserve the reason from the pre-click snapshot.
                    elif age_ms is None or not 0 <= age_ms <= MAX_SNAPSHOT_AGE * 1000:
                        observation = SignalObservation(
                            source, "", None, observation.clock_text, "snapshot expired during click",
                        )
                    elif snapshot.chart_no != observation.chart_no:
                        observation = SignalObservation(
                            source, "", None, observation.clock_text,
                            snapshot.unavailable_reason or "chart changed during click",
                        )
                    else:
                        observation = SignalObservation(
                            source, observation.chart_no, age_ms, observation.clock_text,
                        )
                    self._emit(observation)
        except Exception:
            self._mouse_down = None
        # Always pass through. Never return False or call suppress_event().
        return True


def _listeners(capture):
    from pynput import keyboard, mouse

    return (
        keyboard.Listener(suppress=False, win32_event_filter=capture.keyboard_event),
        mouse.Listener(suppress=False, win32_event_filter=capture.mouse_event),
    )


class EmrSignalProbeRuntime(QObject):
    status_message = Signal(str)

    def __init__(self, parent=None, *, reader_factory=Win32SignalReader,
                 listener_factory=_listeners, state_provider=get_cached_eghis_state,
                 activation_factory=UiaActivationListener, chart_factory=UiaChartListener):
        super().__init__(parent)
        self.reader_factory = reader_factory
        self.listener_factory = listener_factory
        self.state_provider = state_provider
        self.activation_factory = activation_factory
        self.chart_factory = chart_factory
        self._output = queue.Queue(maxsize=64)
        self._stop = threading.Event()
        self._thread = None
        self._listeners = ()
        self._capture = None
        self._running = False
        self._reported_drops = 0
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._drain)

    def start(self) -> None:
        if sys.platform != "win32" or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._running = True
        self._reported_drops = 0
        self._thread = threading.Thread(target=self._run, name="emr-signal-probe", daemon=True)
        self._thread.start()
        self._timer.start()

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        self._timer.stop()
        if self._capture:
            self._capture.enabled = False
            self._capture.snapshot = None
        for listener in self._listeners:
            try:
                listener.stop()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=0.25)
        self._drain()

    def _run(self) -> None:
        import pythoncom

        initialized = False
        activation = None
        chart_listener = None
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            initialized = True
            reader = self.reader_factory()
            sampler = EmrSignalSampler(reader, self.state_provider)
            capture = EmrSignalCapture(reader, self._output, self.state_provider)
            self._capture = capture
            self._listeners = self.listener_factory(capture)
            for listener in self._listeners:
                if self._stop.is_set():
                    return
                listener.start()
                listener.wait()
            self._output.put_nowait("EMR signal probe active (observation only).")
            try:
                activation = self.activation_factory(capture, reader)
            except Exception:
                capture._emit("EMR probe | UIA activation listener unavailable. Keyboard/mouse probe remains active.")
            try:
                chart_listener = self.chart_factory(capture, reader)
            except Exception:
                capture._emit("EMR probe | UIA chart listener unavailable. Other probes remain active.")
            while not self._stop.is_set():
                if not all(listener.is_alive() for listener in self._listeners):
                    raise RuntimeError("Signal listener stopped")
                try:
                    capture.update_snapshot(sampler.sample())
                except Exception:
                    capture.update_snapshot(None)
                if activation is not None:
                    try:
                        activation.sync(
                            connected_scope(self.state_provider()),
                            capture.snapshot.buttons if capture.snapshot else None,
                        )
                    except Exception:
                        try:
                            activation.close()
                        except Exception:
                            pass
                        activation = None
                        capture._emit("EMR probe | UIA activation listener stopped. Keyboard/mouse probe remains active.")
                if chart_listener is not None:
                    try:
                        chart_listener.sync(
                            connected_scope(self.state_provider()),
                            getattr(reader, "chart_target", None) if capture.snapshot else None,
                        )
                    except Exception:
                        try:
                            chart_listener.close()
                        except Exception:
                            pass
                        chart_listener = None
                        capture._emit("EMR probe | UIA chart listener stopped. Other probes remain active.")
                self._stop.wait(0.25)
        except Exception:
            try:
                self._output.put_nowait("EMR signal probe unavailable. Restart KaosEghis to retry.")
            except queue.Full:
                pass
        finally:
            if self._capture:
                self._capture.enabled = False
                self._capture.snapshot = None
            if activation is not None:
                try:
                    activation.close()
                except Exception:
                    pass
                activation = None
            if chart_listener is not None:
                try:
                    chart_listener.close()
                except Exception:
                    pass
                chart_listener = None
            for listener in self._listeners:
                try:
                    listener.stop()
                except Exception:
                    pass
            if initialized:
                pythoncom.CoUninitialize()

    def _drain(self) -> None:
        for _ in range(64):
            try:
                item = self._output.get_nowait()
            except queue.Empty:
                break
            if self._running:
                self.status_message.emit(
                    item.status_text() if isinstance(item, (SignalObservation, ChartFieldObservation)) else item
                )
        if self._running and self._capture and self._capture.dropped_count != self._reported_drops:
            self._reported_drops = self._capture.dropped_count
            self.status_message.emit(
                f"EMR probe overloaded: {self._reported_drops} observations dropped."
            )
