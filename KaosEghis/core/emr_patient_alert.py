from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
import threading
import time
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from KaosEghis.core.eghis_connector import get_cached_eghis_state


DEFAULT_ALERT_MARKER = "***"
DEFAULT_CHART_AUTOMATION_ID = ""
DEFAULT_MEMO_SCOPE_AUTOMATION_ID = ""
DEFAULT_MEMO_TEXT_AUTOMATION_ID = "TreatmentPtntMemo"

_CONTROL_TYPE_SUFFIXES = {
    "도구 모음": "ToolBar",
    "콤보 상자": "ComboBox",
    "탭 항목": "TabItem",
    "창틀": "Pane",
    "그룹": "Group",
    "창": "Window",
    "단추": "Button",
    "버튼": "Button",
    "편집": "Edit",
    "문서": "Document",
    "목록": "List",
    "테이블": "Table",
    "탭": "Tab",
    "텍스트": "Text",
    "toolbar": "ToolBar",
    "combo box": "ComboBox",
    "tab item": "TabItem",
    "window": "Window",
    "pane": "Pane",
    "group": "Group",
    "button": "Button",
    "edit": "Edit",
    "document": "Document",
    "list": "List",
    "table": "Table",
    "tab": "Tab",
    "text": "Text",
}


@dataclass(frozen=True)
class EmrPatientAlertConfiguration:
    enabled: bool = True
    chart_scope_automation_id: str = ""
    chart_automation_id: str = DEFAULT_CHART_AUTOMATION_ID
    chart_name: str = ""
    memo_scope_automation_id: str = DEFAULT_MEMO_SCOPE_AUTOMATION_ID
    memo_automation_id: str = DEFAULT_MEMO_TEXT_AUTOMATION_ID
    memo_name: str = ""
    memo_ancestor_path: str = ""


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

    @property
    def enabled(self) -> bool:
        return self._configuration.enabled

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

        result = self._read_memo_result(state)
        if result.available:
            self._checked_patient_token = patient_token
            self._current_marker_found = result.marker_found
        return result

    def check_for_patient(self, context, is_current: Callable[[Any], bool]) -> EmrPatientAlertResult:
        """Read only the memo, using the shared chart snapshot for identity."""
        if not self.enabled:
            return EmrPatientAlertResult(False, False, False, "Patient-note alert is disabled.")
        state = self._state_provider()
        if not _state_is_connected(state):
            return EmrPatientAlertResult(False, False, False, "EMR is not connected.")
        if (
            context is None or not is_current(context)
            or (state.pid, state.window_handle, state.main_window_handle)
            != (context.scope.pid, context.scope.root, context.scope.treatment)
        ):
            return EmrPatientAlertResult(True, False, False, "Patient identity unavailable; memo check skipped.")
        # Patient panels may be recreated on each load. Resolve within the
        # connected treatment window once, without a second chart-field scan.
        self.reset()
        result = self._read_memo_result(state)
        if not is_current(context):
            return EmrPatientAlertResult(True, False, False, "Patient changed during memo check; result discarded.")
        return result

    def _read_memo_result(self, state) -> EmrPatientAlertResult:
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
                ancestor_path=self._configuration.memo_ancestor_path,
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

        found = bool(self._marker and self._marker in value)
        return EmrPatientAlertResult(
            True, True, found,
            "Important patient-note marker detected." if found else "No patient-note marker detected.",
        )

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
                ancestor_path="",
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
        ancestor_path: str,
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
        except Exception:
            return None

        scopes: list[Any] = []
        if ancestor_path.strip():
            ancestor_scope = _resolve_ancestor_scope(root, ancestor_path)
            if ancestor_scope is not None:
                scopes.append(ancestor_scope)

        if normalized_scope:
            try:
                scope = root.child_window(auto_id=normalized_scope).wrapper_object()
                if all(scope is not existing for existing in scopes):
                    scopes.append(scope)
            except Exception:
                pass
        if not scopes:
            scopes.append(root)

        criteria: dict[str, str] = {}
        if normalized_automation_id:
            criteria["auto_id"] = normalized_automation_id
        if normalized_name:
            criteria["title"] = normalized_name
        candidates = [criteria]
        if preferred_control_type:
            candidates.insert(0, {**criteria, "control_type": preferred_control_type})
        for scope in scopes:
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
        memo_ancestor_path=settings.get(
            "eghis_patient_alert_memo_ancestor_path", ""
        ).strip(),
    )


def parse_patient_alert_ancestor_path(value: str) -> list[dict[str, str]]:
    text = value.strip()
    if not text:
        return []
    try:
        raw_nodes = json.loads(text)
    except json.JSONDecodeError:
        raw_nodes = None
    if isinstance(raw_nodes, list):
        nodes: list[dict[str, str]] = []
        for node in raw_nodes:
            if not isinstance(node, dict):
                continue
            normalized = _normalized_ancestor_node(node)
            if normalized:
                nodes.append(normalized)
        return nodes

    nodes: list[dict[str, str]] = []
    in_ancestors = not any(
        line.strip().lower().startswith("ancestors:") for line in text.splitlines()
    )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("ancestors:"):
            in_ancestors = True
            line = line.partition(":")[2].strip()
            if not line:
                continue
        if not in_ancestors:
            continue
        if line.startswith("[") and "no parent" in line.casefold():
            continue
        name_match = re.match(r'^"([^"]*)"', line)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        if not name:
            continue
        node: dict[str, str] = {"name": name}
        remainder = line[name_match.end() :].strip()
        for suffix, control_type in _CONTROL_TYPE_SUFFIXES.items():
            if remainder.casefold().endswith(suffix.casefold()):
                node["control_type"] = control_type
                break
        auto_match = re.search(
            r"(?:automation[_ ]?id|auto[_ ]?id)\s*[=:]\s*[\"']?([^\s\"']+)",
            line,
            flags=re.IGNORECASE,
        )
        if auto_match:
            node["automation_id"] = auto_match.group(1).strip()
        nodes.append(node)
    return nodes


def _resolve_ancestor_scope(root: Any, ancestor_path: str) -> Any | None:
    nodes = parse_patient_alert_ancestor_path(ancestor_path)
    if not nodes:
        return None
    ordered = list(reversed(nodes))
    for start_index in range(len(ordered)):
        current = root
        failed = False
        for node in ordered[start_index:]:
            if _matches_ancestor(current, node):
                continue
            try:
                descendants = current.descendants()
            except Exception:
                failed = True
                break
            matches = [
                element for element in descendants if _matches_ancestor(element, node)
            ]
            if len(matches) != 1:
                failed = True
                break
            current = matches[0]
        if not failed:
            return current
    return None


def _normalized_ancestor_node(node: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(value).strip()
        for key, value in node.items()
        if key in {"name", "automation_id", "control_type", "class_name"}
        and str(value).strip()
    }


def _matches_ancestor(element: Any, node: dict[str, str]) -> bool:
    info = getattr(element, "element_info", None)
    values = {
        "name": str(getattr(info, "name", "") or "").strip(),
        "automation_id": str(getattr(info, "automation_id", "") or "").strip(),
        "control_type": str(getattr(info, "control_type", "") or "").strip(),
        "class_name": str(getattr(info, "class_name", "") or "").strip(),
    }
    return all(
        values.get(key, "").casefold() == expected.casefold()
        for key, expected in node.items()
    )


class EmrPatientAlertMonitor(QObject):
    """One delayed memo read per shared patient-change notification, never a poller."""

    result_changed = Signal(object)
    _check_finished = Signal(object, object)

    def __init__(
        self,
        *,
        probe: EmrPatientAlertProbe | None = None,
        delay_seconds: float = 5.0,
        patient_is_current: Callable[[Any], bool] = lambda _context: False,
        clock: Callable[[], float] = time.monotonic,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._probe = probe or EmrPatientAlertProbe()
        self._delay_seconds = max(float(delay_seconds), 0.0)
        self._patient_is_current = patient_is_current
        self._clock = clock
        self._active = False
        self._context = None
        self._token = object()
        self._attempted_token = None
        self._deadline = 0.0
        self._due = False
        self._thread: threading.Thread | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._begin_check)
        self._check_finished.connect(self._finish_check)

    @property
    def is_running(self) -> bool:
        return self._active

    def start(self) -> None:
        if self.is_running:
            return
        self._active = True
        self._schedule_current()

    def stop(self) -> None:
        self._active = False
        self._context = None
        self._schedule_current()

    def patient_changed(self, context) -> None:
        if context != self._context:
            self._context = context
            self._schedule_current()

    def replace_probe(self, probe: EmrPatientAlertProbe) -> None:
        self._probe = probe
        self._schedule_current()

    def _schedule_current(self) -> None:
        self._timer.stop()
        self._token = object()
        self._due = False
        self.result_changed.emit(EmrPatientAlertResult(
            self._context is not None, True, False, "Patient-note alert cleared.",
        ))
        if self._active and self._context is not None and self._probe.enabled:
            self._deadline = self._clock() + self._delay_seconds
            self._timer.start(math.ceil(self._delay_seconds * 1000))

    def _begin_check(self) -> None:
        if not self._active or self._context is None or not self._probe.enabled:
            return
        if self._attempted_token is self._token:
            return
        remaining = self._deadline - self._clock()
        if remaining > 0:
            self._timer.start(max(1, math.ceil(remaining * 1000)))
            return
        self._timer.stop()
        if self._thread is not None:
            self._due = True
            return
        self._due = False
        token, context, probe = self._token, self._context, self._probe
        self._attempted_token = token

        def is_current(candidate) -> bool:
            return self._active and self._token is token and self._patient_is_current(candidate)

        def worker() -> None:
            initialized = False
            result = EmrPatientAlertResult(True, False, False, "Patient alert check unavailable.")
            try:
                import pythoncom

                pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
                initialized = True
                result = probe.check_for_patient(context, is_current)
            except Exception:
                pass  # UIA errors may contain patient text.
            finally:
                if initialized:
                    pythoncom.CoUninitialize()
                try:
                    self._check_finished.emit(token, result)
                except RuntimeError:
                    pass

        self._thread = threading.Thread(target=worker, name="EMR patient memo check", daemon=True)
        self._thread.start()

    def _finish_check(self, token, result: EmrPatientAlertResult) -> None:
        self._thread = None
        if self._active and token is self._token:
            if not self._patient_is_current(self._context):
                result = EmrPatientAlertResult(True, False, False, "Patient identity unavailable; memo result discarded.")
            self.result_changed.emit(result)
        if self._due:
            self._begin_check()


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
