from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from KaosEghis.core.eghis_connector import get_cached_eghis_state


DEFAULT_ALERT_MARKER = "***"
DEFAULT_MEMO_SCOPE_AUTOMATION_ID = "TreatmentPtntMemoDoctor"
DEFAULT_MEMO_TEXT_AUTOMATION_ID = "eghisRichTextBox"


@dataclass(frozen=True)
class EmrPatientAlertResult:
    connected: bool
    available: bool
    marker_found: bool
    message: str


class EmrPatientAlertProbe:
    """Read the configured patient memo without retaining or returning its contents."""

    def __init__(
        self,
        *,
        marker: str = DEFAULT_ALERT_MARKER,
        scope_automation_id: str = DEFAULT_MEMO_SCOPE_AUTOMATION_ID,
        text_automation_id: str = DEFAULT_MEMO_TEXT_AUTOMATION_ID,
        state_provider: Callable[[], Any] = get_cached_eghis_state,
        desktop_factory: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        resolution_retry_seconds: float = 10.0,
    ) -> None:
        self._marker = marker
        self._scope_automation_id = scope_automation_id
        self._text_automation_id = text_automation_id
        self._state_provider = state_provider
        self._desktop_factory = desktop_factory
        self._clock = clock
        self._resolution_retry_seconds = max(float(resolution_retry_seconds), 0.2)
        self._connection_identity: tuple[int | None, int | None] | None = None
        self._memo_element: Any | None = None
        self._next_resolution_at = 0.0

    def reset(self) -> None:
        self._connection_identity = None
        self._memo_element = None
        self._next_resolution_at = 0.0

    def check(self) -> EmrPatientAlertResult:
        state = self._state_provider()
        if not _state_is_connected(state):
            self.reset()
            return EmrPatientAlertResult(
                connected=False,
                available=False,
                marker_found=False,
                message="EMR is not connected.",
            )

        identity = (getattr(state, "pid", None), getattr(state, "window_handle", None))
        if identity != self._connection_identity:
            self.reset()
            self._connection_identity = identity

        if self._memo_element is None:
            if self._clock() < self._next_resolution_at:
                return EmrPatientAlertResult(
                    connected=True,
                    available=False,
                    marker_found=False,
                    message="Patient memo field is not available.",
                )
            self._memo_element = self._resolve_memo_element(state)
        if self._memo_element is None:
            self._next_resolution_at = self._clock() + self._resolution_retry_seconds
            return EmrPatientAlertResult(
                connected=True,
                available=False,
                marker_found=False,
                message="Patient memo field is not available.",
            )

        value, readable = _read_element_value(self._memo_element)
        if not readable:
            self._memo_element = None
            self._next_resolution_at = self._clock() + min(
                self._resolution_retry_seconds, 2.0
            )
            return EmrPatientAlertResult(
                connected=True,
                available=False,
                marker_found=False,
                message="Patient memo field could not be read.",
            )

        return EmrPatientAlertResult(
            connected=True,
            available=True,
            marker_found=bool(self._marker and self._marker in value),
            message=(
                "Important patient-note marker detected."
                if self._marker and self._marker in value
                else "No patient-note marker detected."
            ),
        )

    def _resolve_memo_element(self, state: Any) -> Any | None:
        desktop_factory = self._desktop_factory
        if desktop_factory is None:
            try:
                from pywinauto import Desktop
            except ImportError:
                return None
            desktop_factory = Desktop

        root_handle = getattr(state, "main_window_handle", None) or getattr(
            state, "window_handle", None
        )
        if root_handle is None:
            return None

        try:
            root = desktop_factory(backend="uia").window(
                handle=root_handle
            ).wrapper_object()
            scope = root.child_window(
                auto_id=self._scope_automation_id
            ).wrapper_object()
        except Exception:
            return None

        for criteria in (
            {"auto_id": self._text_automation_id, "control_type": "Edit"},
            {"auto_id": self._text_automation_id},
        ):
            try:
                return scope.child_window(**criteria).wrapper_object()
            except Exception:
                continue
        return None


class EmrPatientAlertMonitor(QObject):
    result_changed = Signal(object)

    def __init__(
        self,
        *,
        probe: EmrPatientAlertProbe | None = None,
        poll_interval_seconds: float = 1.5,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._probe = probe or EmrPatientAlertProbe()
        self._poll_interval_seconds = max(float(poll_interval_seconds), 0.2)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_result: EmrPatientAlertResult | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="KaosEghis patient alert monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.5)
        self._thread = None
        self._probe.reset()

    def _run(self) -> None:
        pythoncom = None
        try:
            import pythoncom as imported_pythoncom

            pythoncom = imported_pythoncom
            pythoncom.CoInitialize()
        except (ImportError, OSError):
            pythoncom = None

        try:
            while not self._stop_event.is_set():
                try:
                    result = self._probe.check()
                except Exception:
                    self._probe.reset()
                    result = EmrPatientAlertResult(
                        connected=False,
                        available=False,
                        marker_found=False,
                        message="Patient alert check unavailable.",
                    )
                if result != self._last_result:
                    self._last_result = result
                    self.result_changed.emit(result)
                self._stop_event.wait(self._poll_interval_seconds)
        finally:
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except OSError:
                    pass


def _state_is_connected(state: Any) -> bool:
    return bool(
        state is not None
        and getattr(state, "status", "") in {"green", "yellow"}
        and getattr(state, "pid", None) is not None
        and getattr(state, "window_handle", None) is not None
    )


def _read_element_value(element: Any) -> tuple[str, bool]:
    try:
        iface_value = element.iface_value
        value = iface_value.CurrentValue
        return str(value or ""), True
    except Exception:
        pass

    try:
        iface_text = element.iface_text
        value = iface_text.DocumentRange.GetText(-1)
        return str(value or ""), True
    except Exception:
        pass

    for method_name in ("get_value", "window_text"):
        try:
            value = getattr(element, method_name)()
            return str(value or ""), True
        except Exception:
            continue
    return "", False
