from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from KaosEghis.core.eghis_connector import get_cached_eghis_state


DEFAULT_ALERT_MARKER = "***"
DEFAULT_CHART_AUTOMATION_ID = "lblChartNo"
DEFAULT_MEMO_SCOPE_AUTOMATION_ID = "TreatmentPtntMemoDoctor"
DEFAULT_MEMO_TEXT_AUTOMATION_ID = "eghisRichTextBox"


@dataclass(frozen=True)
class EmrPatientAlertConfiguration:
    enabled: bool = True
    chart_scope_automation_id: str = ""
    chart_automation_id: str = DEFAULT_CHART_AUTOMATION_ID
    chart_name: str = ""
    memo_scope_automation_id: str = DEFAULT_MEMO_SCOPE_AUTOMATION_ID
    memo_automation_id: str = DEFAULT_MEMO_TEXT_AUTOMATION_ID
    memo_name: str = ""


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
        configuration: EmrPatientAlertConfiguration | None = None,
        state_provider: Callable[[], Any] = get_cached_eghis_state,
        desktop_factory: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        resolution_retry_seconds: float = 10.0,
        patient_settle_seconds: float = 0.5,
    ) -> None:
        self._marker = marker
        self._configuration = configuration or EmrPatientAlertConfiguration()
        self._state_provider = state_provider
        self._desktop_factory = desktop_factory
        self._clock = clock
        self._resolution_retry_seconds = max(float(resolution_retry_seconds), 0.2)
        self._patient_settle_seconds = max(float(patient_settle_seconds), 0.0)
        self._connection_identity: tuple[int | None, int | None] | None = None
        self._chart_element: Any | None = None
        self._memo_element: Any | None = None
        self._next_chart_resolution_at = 0.0
        self._next_memo_resolution_at = 0.0
        self._current_patient_token = ""
        self._checked_patient_token = ""
        self._patient_changed_at = 0.0
        self._current_marker_found = False

    def reset(self) -> None:
        self._connection_identity = None
        self._chart_element = None
        self._memo_element = None
        self._next_chart_resolution_at = 0.0
        self._next_memo_resolution_at = 0.0
        self._current_patient_token = ""
        self._checked_patient_token = ""
        self._patient_changed_at = 0.0
        self._current_marker_found = False

    def check(self) -> EmrPatientAlertResult:
        if not self._configuration.enabled:
            self.reset()
            return EmrPatientAlertResult(
                connected=False,
                available=False,
                marker_found=False,
                message="Patient-note alert is disabled.",
            )

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

        chart_value, chart_readable = self._read_chart_number(state)
        if not chart_readable:
            return EmrPatientAlertResult(
                connected=True,
                available=False,
                marker_found=False,
                message="Current patient chart-number field is not available.",
            )
        patient_token = chart_value.strip()
        if not patient_token:
            self._clear_current_patient()
            return EmrPatientAlertResult(
                connected=True,
                available=True,
                marker_found=False,
                message="No current patient is selected.",
            )

        if patient_token != self._current_patient_token:
            self._current_patient_token = patient_token
            self._checked_patient_token = ""
            self._patient_changed_at = self._clock()
            self._current_marker_found = False
            return EmrPatientAlertResult(
                connected=True,
                available=True,
                marker_found=False,
                message="Patient change detected; waiting for patient memo.",
            )

        if self._checked_patient_token == patient_token:
            return self._checked_result()

        if self._clock() - self._patient_changed_at < self._patient_settle_seconds:
            return EmrPatientAlertResult(
                connected=True,
                available=True,
                marker_found=False,
                message="Patient change detected; waiting for patient memo.",
            )

        if self._memo_element is None:
            if self._clock() < self._next_memo_resolution_at:
                return EmrPatientAlertResult(
                    connected=True,
                    available=False,
                    marker_found=False,
                    message="Patient memo field is not available.",
                )
            self._memo_element = self._resolve_target_element(
                state,
                scope_automation_id=self._configuration.memo_scope_automation_id,
                automation_id=self._configuration.memo_automation_id,
                name=self._configuration.memo_name,
                preferred_control_type="Edit",
            )
        if self._memo_element is None:
            self._next_memo_resolution_at = (
                self._clock() + self._resolution_retry_seconds
            )
            return EmrPatientAlertResult(
                connected=True,
                available=False,
                marker_found=False,
                message="Patient memo field is not available.",
            )

        value, readable = _read_element_value(self._memo_element)
        if not readable:
            self._memo_element = None
            self._next_memo_resolution_at = self._clock() + min(
                self._resolution_retry_seconds, 2.0
            )
            return EmrPatientAlertResult(
                connected=True,
                available=False,
                marker_found=False,
                message="Patient memo field could not be read.",
            )

        self._checked_patient_token = patient_token
        self._current_marker_found = bool(self._marker and self._marker in value)
        return self._checked_result()

    def _checked_result(self) -> EmrPatientAlertResult:
        return EmrPatientAlertResult(
            connected=True,
            available=True,
            marker_found=self._current_marker_found,
            message=(
                "Important patient-note marker detected."
                if self._current_marker_found
                else "No patient-note marker detected."
            ),
        )

    def _read_chart_number(self, state: Any) -> tuple[str, bool]:
        if self._chart_element is None:
            if self._clock() < self._next_chart_resolution_at:
                return "", False
            self._chart_element = self._resolve_target_element(
                state,
                scope_automation_id=self._configuration.chart_scope_automation_id,
                automation_id=self._configuration.chart_automation_id,
                name=self._configuration.chart_name,
                preferred_control_type=None,
            )
        if self._chart_element is None:
            self._next_chart_resolution_at = (
                self._clock() + self._resolution_retry_seconds
            )
            return "", False
        value, readable = _read_element_value(self._chart_element)
        if not readable:
            self._chart_element = None
            self._next_chart_resolution_at = self._clock() + min(
                self._resolution_retry_seconds, 2.0
            )
        return value, readable

    def _clear_current_patient(self) -> None:
        self._current_patient_token = ""
        self._checked_patient_token = ""
        self._patient_changed_at = 0.0
        self._current_marker_found = False

    def _resolve_target_element(
        self,
        state: Any,
        *,
        scope_automation_id: str,
        automation_id: str,
        name: str,
        preferred_control_type: str | None,
    ) -> Any | None:
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

        normalized_scope = scope_automation_id.strip()
        normalized_automation_id = automation_id.strip()
        normalized_name = name.strip()
        if not normalized_automation_id and not normalized_name:
            return None

        try:
            root = desktop_factory(backend="uia").window(
                handle=root_handle
            ).wrapper_object()
            scope = (
                root.child_window(auto_id=normalized_scope).wrapper_object()
                if normalized_scope
                else root
            )
        except Exception:
            return None

        criteria: dict[str, str] = {}
        if normalized_automation_id:
            criteria["auto_id"] = normalized_automation_id
        if normalized_name:
            criteria["title"] = normalized_name
        candidates = [criteria]
        if preferred_control_type:
            candidates.insert(0, {**criteria, "control_type": preferred_control_type})
        for candidate in candidates:
            try:
                return scope.child_window(**candidate).wrapper_object()
            except Exception:
                continue
        return None


def patient_alert_configuration_from_settings(
    settings: dict[str, str],
) -> EmrPatientAlertConfiguration:
    return EmrPatientAlertConfiguration(
        enabled=(settings.get("eghis_patient_alert_enabled", "true").strip().lower() == "true"),
        chart_scope_automation_id=settings.get(
            "eghis_patient_alert_chart_scope_automation_id", ""
        ).strip(),
        chart_automation_id=settings.get(
            "eghis_patient_alert_chart_automation_id", DEFAULT_CHART_AUTOMATION_ID
        ).strip(),
        chart_name=settings.get("eghis_patient_alert_chart_name", "").strip(),
        memo_scope_automation_id=settings.get(
            "eghis_patient_alert_memo_scope_automation_id",
            DEFAULT_MEMO_SCOPE_AUTOMATION_ID,
        ).strip(),
        memo_automation_id=settings.get(
            "eghis_patient_alert_memo_automation_id",
            DEFAULT_MEMO_TEXT_AUTOMATION_ID,
        ).strip(),
        memo_name=settings.get("eghis_patient_alert_memo_name", "").strip(),
    )


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
        self._probe_lock = threading.Lock()
        self._pending_probe: EmrPatientAlertProbe | None = None

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

    def replace_probe(self, probe: EmrPatientAlertProbe) -> None:
        with self._probe_lock:
            self._pending_probe = probe

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
                with self._probe_lock:
                    if self._pending_probe is not None:
                        self._probe = self._pending_probe
                        self._pending_probe = None
                        self._last_result = None
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
