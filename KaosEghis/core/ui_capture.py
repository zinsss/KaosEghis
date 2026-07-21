from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class PointInspectionResult:
    success: bool
    x: int
    y: int
    backend: str | None
    handle: int | None
    name: str | None
    automation_id: str | None
    control_type: str | None
    class_name: str | None
    text_value: str | None
    ancestor_summary: str | None
    message: str


class GlobalClickCaptureController(QObject):
    armed_changed = Signal(bool)
    capture_ready = Signal(object)
    capture_failed = Signal(str)

    def __init__(self, parent: QObject | None = None, hotkey: str = "<ctrl>+<shift>+<f8>") -> None:
        super().__init__(parent)
        self._hotkey = hotkey
        self._hotkey_listener: Any | None = None
        self._mouse_listener: Any | None = None
        self._armed_at = 0.0

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def start_hotkey_listener(self) -> bool:
        if self._hotkey_listener is not None:
            return True
        try:
            from pynput import keyboard
        except Exception:
            return False

        self._hotkey_listener = keyboard.GlobalHotKeys({self._hotkey: self.arm_capture})
        self._hotkey_listener.start()
        return True

    def arm_capture(self) -> bool:
        if self._mouse_listener is not None:
            return True
        try:
            from pynput import mouse
        except Exception as error:
            self.capture_failed.emit(f"Global capture is unavailable: {error}")
            return False

        self._armed_at = time.monotonic()
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._mouse_listener.start()
        self.armed_changed.emit(True)
        return True

    def stop(self) -> None:
        if self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None
        self._stop_mouse_listener()

    def _stop_mouse_listener(self) -> None:
        listener = self._mouse_listener
        self._mouse_listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
        self.armed_changed.emit(False)

    def _on_click(self, x: int, y: int, _button: Any, pressed: bool) -> bool:
        if not pressed:
            return True
        if time.monotonic() - self._armed_at < 0.25:
            return True
        self._stop_mouse_listener()
        try:
            result = inspect_ui_at_point(x, y)
        except Exception as error:
            self.capture_failed.emit(f"Capture failed: {error}")
            return False
        self.capture_ready.emit(result)
        return False


def inspect_ui_at_point(x: int, y: int) -> PointInspectionResult:
    try:
        from pywinauto import Desktop
    except ImportError:
        return PointInspectionResult(
            success=False,
            x=x,
            y=y,
            backend=None,
            handle=None,
            name=None,
            automation_id=None,
            control_type=None,
            class_name=None,
            text_value=None,
            ancestor_summary=None,
            message="pywinauto is not installed; screen capture is unavailable.",
        )

    messages: list[str] = []
    for backend in ("uia", "win32"):
        try:
            element = Desktop(backend=backend).from_point(x, y)
        except Exception as error:
            messages.append(f"{backend}: {error}")
            continue
        if element is None:
            continue
        return _build_point_result(element, x, y, backend)

    return PointInspectionResult(
        success=False,
        x=x,
        y=y,
        backend=None,
        handle=None,
        name=None,
        automation_id=None,
        control_type=None,
        class_name=None,
        text_value=None,
        ancestor_summary=None,
        message="UI capture could not resolve a control at the clicked point."
        if not messages
        else " | ".join(messages),
    )


def format_capture_result(result: PointInspectionResult) -> str:
    lines = [
        f"Coordinate: ({result.x}, {result.y})",
        f"Backend: {result.backend or ''}",
        f"Handle: {result.handle or ''}",
        f"Name: {result.name or ''}",
        f"Automation ID: {result.automation_id or ''}",
        f"Control type: {result.control_type or ''}",
        f"Class name: {result.class_name or ''}",
        f"Value: {result.text_value or ''}",
        f"Ancestors: {result.ancestor_summary or ''}",
        f"Message: {result.message}",
    ]
    return "\n".join(lines)


def _build_point_result(element: Any, x: int, y: int, backend: str) -> PointInspectionResult:
    name = _element_name(element)
    text_value = _best_text_value(element)
    return PointInspectionResult(
        success=True,
        x=x,
        y=y,
        backend=backend,
        handle=_element_handle(element),
        name=name,
        automation_id=_element_automation_id(element),
        control_type=_element_control_type(element),
        class_name=_element_class_name(element),
        text_value=text_value,
        ancestor_summary=_ancestor_summary(element),
        message="UI control captured.",
    )


def _element_handle(element: Any) -> int | None:
    try:
        handle = getattr(element, "handle", None)
        if handle is not None:
            return int(handle)
    except Exception:
        pass
    try:
        info = getattr(element, "element_info", None)
        handle = getattr(info, "handle", None)
        if handle is not None:
            return int(handle)
    except Exception:
        pass
    return None


def _element_name(element: Any) -> str | None:
    for getter in (
        lambda: getattr(getattr(element, "element_info", None), "name", None),
        lambda: element.window_text(),
        lambda: getattr(element, "texts", lambda: [])()[0],
    ):
        try:
            value = getter()
        except Exception:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _element_automation_id(element: Any) -> str | None:
    try:
        value = getattr(getattr(element, "element_info", None), "automation_id", None)
    except Exception:
        value = None
    if isinstance(value, str):
        value = value.strip()
    return value or None


def _element_control_type(element: Any) -> str | None:
    try:
        value = getattr(getattr(element, "element_info", None), "control_type", None)
    except Exception:
        value = None
    if isinstance(value, str):
        value = value.strip()
    return value or None


def _element_class_name(element: Any) -> str | None:
    try:
        value = getattr(getattr(element, "element_info", None), "class_name", None)
    except Exception:
        value = None
    if isinstance(value, str):
        value = value.strip()
    return value or None


def _best_text_value(element: Any) -> str | None:
    try:
        iface_value = getattr(element, "iface_value", None)
    except Exception:
        iface_value = None
    if iface_value is not None:
        for attribute in ("CurrentValue", "Value"):
            try:
                value = getattr(iface_value, attribute, None)
            except Exception:
                value = None
            if isinstance(value, str) and value.strip():
                return value.strip()
    try:
        legacy = element.legacy_properties()
    except Exception:
        legacy = None
    if isinstance(legacy, dict):
        for key in ("Value", "Name"):
            value = legacy.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return _element_name(element)


def _ancestor_summary(element: Any, max_depth: int = 8) -> str | None:
    nodes: list[str] = []
    current = element
    for _ in range(max_depth):
        try:
            current = current.parent()
        except Exception:
            break
        if current is None:
            break
        name = _element_name(current) or ""
        control_type = _element_control_type(current) or _element_class_name(current) or "Unknown"
        node = f"{name} ({control_type})".strip()
        nodes.append(node)
    return " > ".join(nodes) if nodes else None
