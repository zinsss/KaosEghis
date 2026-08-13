from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from KaosEghis.core.emr_patient_alert import (
    EmrPatientAlertProbe,
    EmrPatientAlertResult,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _Specification:
    def __init__(self, wrapper) -> None:
        self._wrapper = wrapper

    def wrapper_object(self):
        return self._wrapper


class _Node:
    def __init__(self, children=None) -> None:
        self.children = children or {}
        self.child_lookups = 0

    def child_window(self, **criteria):
        self.child_lookups += 1
        key = (criteria.get("auto_id"), criteria.get("control_type"))
        child = self.children.get(key) or self.children.get((key[0], None))
        if child is None:
            raise RuntimeError("not found")
        return _Specification(child)


class _Desktop:
    def __init__(self, root) -> None:
        self.root = root

    def window(self, **_criteria):
        return _Specification(self.root)


class _ValueElement:
    def __init__(self, value: str) -> None:
        self.iface_value = SimpleNamespace(CurrentValue=value)


def _connected_state():
    return SimpleNamespace(
        status="yellow",
        pid=42,
        window_handle=100,
        main_window_handle=101,
    )


def test_patient_alert_probe_detects_marker_without_returning_memo_text() -> None:
    memo = _ValueElement("private patient note *** private detail")
    scope = _Node({("eghisRichTextBox", "Edit"): memo})
    root = _Node({("TreatmentPtntMemoDoctor", None): scope})
    probe = EmrPatientAlertProbe(
        state_provider=_connected_state,
        desktop_factory=lambda **_kwargs: _Desktop(root),
    )

    result = probe.check()

    assert result == EmrPatientAlertResult(
        connected=True,
        available=True,
        marker_found=True,
        message="Important patient-note marker detected.",
    )
    assert "private" not in result.message
    assert not hasattr(result, "text_value")


def test_patient_alert_probe_reuses_resolved_element_for_same_connection() -> None:
    memo = _ValueElement("no marker")
    scope = _Node({("eghisRichTextBox", "Edit"): memo})
    root = _Node({("TreatmentPtntMemoDoctor", None): scope})
    probe = EmrPatientAlertProbe(
        state_provider=_connected_state,
        desktop_factory=lambda **_kwargs: _Desktop(root),
    )

    assert probe.check().available is True
    assert probe.check().available is True

    assert root.child_lookups == 1
    assert scope.child_lookups == 1


def test_patient_alert_probe_does_not_inspect_when_emr_disconnected() -> None:
    desktop_calls = []
    probe = EmrPatientAlertProbe(
        state_provider=lambda: None,
        desktop_factory=lambda **kwargs: desktop_calls.append(kwargs),
    )

    result = probe.check()

    assert result.connected is False
    assert result.marker_found is False
    assert desktop_calls == []


def test_patient_alert_probe_backs_off_after_failed_resolution() -> None:
    now = [100.0]
    root = _Node()
    probe = EmrPatientAlertProbe(
        state_provider=_connected_state,
        desktop_factory=lambda **_kwargs: _Desktop(root),
        clock=lambda: now[0],
        resolution_retry_seconds=10.0,
    )

    assert probe.check().available is False
    assert probe.check().available is False
    assert root.child_lookups == 1

    now[0] += 10.0
    assert probe.check().available is False
    assert root.child_lookups == 2


def test_patient_alert_popup_is_always_on_top_and_contains_no_memo_text() -> None:
    _app()

    from KaosEghis.ui.emr_patient_alert import EmrPatientAlertPopup

    popup = EmrPatientAlertPopup()
    labels = " ".join(
        label.text() for label in popup.findChildren(QLabel)
    )

    assert (
        popup.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    ) == Qt.WindowType.WindowStaysOnTopHint
    assert (
        popup.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    ) == Qt.WindowType.WindowDoesNotAcceptFocus
    assert "***" in labels
    assert "IMPORTANT PATIENT NOTE" in labels
    assert "patient memo" in labels.lower()
    assert "private" not in labels.lower()
    assert "#b00020" in popup.styleSheet()
