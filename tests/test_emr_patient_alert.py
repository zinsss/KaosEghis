from __future__ import annotations

import os
import sys
import threading
import time
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from KaosEghis.core.emr_patient_alert import (
    EmrPatientAlertConfiguration,
    EmrPatientAlertProbe,
    EmrPatientAlertResult,
    EmrPatientAlertMonitor,
    patient_alert_configuration_from_settings,
)
from KaosEghis.core.emr_signal_probe import PatientChartContext, SignalScope


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _Specification:
    def __init__(self, wrapper) -> None:
        self._wrapper = wrapper

    def wrapper_object(self):
        return self._wrapper


class _Node:
    def __init__(
        self,
        children=None,
        *,
        name="",
        automation_id="",
        control_type="",
        descendants=None,
    ) -> None:
        self.children = children or {}
        self._descendants = descendants or []
        self.child_lookups = 0
        self.last_criteria = None
        self.element_info = SimpleNamespace(
            name=name,
            automation_id=automation_id,
            control_type=control_type,
            class_name="",
        )

    def child_window(self, **criteria):
        self.child_lookups += 1
        self.last_criteria = criteria
        key = (
            criteria.get("auto_id"),
            criteria.get("title"),
            criteria.get("control_type"),
        )
        child = self.children.get(key)
        if child is None:
            child = self.children.get((key[0], key[1], None))
        if child is None:
            raise RuntimeError("not found")
        return _Specification(child)

    def descendants(self):
        return list(self._descendants)


class _Desktop:
    def __init__(self, root) -> None:
        self.root = root

    def window(self, **_criteria):
        return _Specification(self.root)


class _ValueInterface:
    def __init__(self, owner) -> None:
        self._owner = owner

    @property
    def CurrentValue(self):
        self._owner.read_count += 1
        return self._owner.value


class _ValueElement:
    def __init__(self, value: str) -> None:
        self.value = value
        self.read_count = 0
        self.iface_value = _ValueInterface(self)


def _connected_state():
    return SimpleNamespace(
        status="yellow",
        pid=42,
        window_handle=100,
        main_window_handle=101,
    )


def _probe_fixture(*, chart_value="2735", memo_value="note *** detail"):
    chart = _ValueElement(chart_value)
    memo = _ValueElement(memo_value)
    memo_scope = _Node({("eghisRichTextBox", "Memo field", "Edit"): memo})
    root = _Node(
        {
            ("lblChartNo", "Chart number", None): chart,
            ("TreatmentPtntMemoDoctor", None, None): memo_scope,
        }
    )
    configuration = EmrPatientAlertConfiguration(
        chart_automation_id="lblChartNo",
        chart_name="Chart number",
        memo_scope_automation_id="TreatmentPtntMemoDoctor",
        memo_automation_id="eghisRichTextBox",
        memo_name="Memo field",
    )
    probe = EmrPatientAlertProbe(
        configuration=configuration,
        state_provider=_connected_state,
        desktop_factory=lambda **_kwargs: _Desktop(root),
        patient_settle_seconds=0,
    )
    return probe, chart, memo, root, memo_scope


def test_patient_alert_reads_memo_once_for_current_patient() -> None:
    probe, chart, memo, root, memo_scope = _probe_fixture()

    changed = probe.check()
    first_result = probe.check()
    repeated_result = probe.check()

    assert changed.marker_found is False
    assert changed.message == "Patient change detected; waiting for patient memo."
    assert first_result == EmrPatientAlertResult(
        connected=True,
        available=True,
        marker_found=True,
        message="Important patient-note marker detected.",
    )
    assert repeated_result == first_result
    assert chart.read_count == 3
    assert memo.read_count == 1
    assert root.child_lookups == 2
    assert memo_scope.child_lookups == 1
    assert not hasattr(first_result, "patient_chart_no")
    assert not hasattr(first_result, "text_value")


def test_patient_change_clears_old_alert_and_reads_new_memo_once() -> None:
    probe, chart, memo, _root, _memo_scope = _probe_fixture()
    probe.check()
    assert probe.check().marker_found is True

    chart.value = "9999"
    memo.value = "ordinary note"

    changed = probe.check()
    new_patient = probe.check()
    repeated = probe.check()

    assert changed.marker_found is False
    assert new_patient.marker_found is False
    assert repeated.marker_found is False
    assert memo.read_count == 2


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


def test_patient_alert_probe_backs_off_after_failed_chart_resolution() -> None:
    now = [100.0]
    root = _Node()
    probe = EmrPatientAlertProbe(
        configuration=EmrPatientAlertConfiguration(
            chart_automation_id="ChartId",
        ),
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


def test_patient_alert_configuration_uses_editable_uia_fields() -> None:
    configuration = patient_alert_configuration_from_settings(
        {
            "eghis_patient_alert_enabled": "false",
            "eghis_patient_alert_chart_scope_automation_id": "PatientHeader",
            "eghis_patient_alert_chart_automation_id": "ChartId",
            "eghis_patient_alert_chart_name": "Chart No",
            "eghis_patient_alert_memo_scope_automation_id": "MemoArea",
            "eghis_patient_alert_memo_automation_id": "MemoText",
            "eghis_patient_alert_memo_name": "Important memo",
            "eghis_patient_alert_memo_ancestor_path": "Ancestors:\n\"Memo pane\" pane",
        }
    )

    assert configuration == EmrPatientAlertConfiguration(
        enabled=False,
        chart_scope_automation_id="PatientHeader",
        chart_automation_id="ChartId",
        chart_name="Chart No",
        memo_scope_automation_id="MemoArea",
        memo_automation_id="MemoText",
        memo_name="Important memo",
        memo_ancestor_path='Ancestors:\n"Memo pane" pane',
    )


def test_patient_alert_configuration_does_not_guess_chart_target_defaults() -> None:
    configuration = patient_alert_configuration_from_settings({})

    assert configuration.chart_automation_id == ""
    assert configuration.memo_scope_automation_id == ""
    assert configuration.memo_automation_id == "TreatmentPtntMemo"
    assert configuration.memo_name == ""


def test_patient_alert_ancestor_path_scopes_generic_memo_target() -> None:
    from KaosEghis.core.emr_patient_alert import parse_patient_alert_ancestor_path

    chart = _ValueElement("2735")
    wrong_memo = _ValueElement("ordinary note")
    right_memo = _ValueElement("allergy ***")
    wrong_scope = _Node(
        {("eghisRichTextBox", "eghisRichTexbox", "Edit"): wrong_memo},
        name="Other memo",
        automation_id="OtherMemo",
        control_type="Pane",
    )
    right_scope = _Node(
        {("eghisRichTextBox", "eghisRichTexbox", "Edit"): right_memo},
        name="Patient memo",
        automation_id="TreatmentPtntMemoDoctor",
        control_type="Pane",
    )
    root = _Node(
        {
            ("lblChartNo", None, None): chart,
            ("TreatmentPtntMemoDoctor", None, None): wrong_scope,
        },
        name="진료실",
        automation_id="H2OpdTreatment",
        control_type="Window",
        descendants=[wrong_scope, right_scope],
    )
    ancestor_text = 'Ancestors:\n"Patient memo" pane\n"진료실" window\n[ No Parent ]'
    configuration = EmrPatientAlertConfiguration(
        chart_automation_id="lblChartNo",
        memo_scope_automation_id="TreatmentPtntMemoDoctor",
        memo_automation_id="eghisRichTextBox",
        memo_name="eghisRichTexbox",
        memo_ancestor_path=ancestor_text,
    )
    probe = EmrPatientAlertProbe(
        configuration=configuration,
        state_provider=_connected_state,
        desktop_factory=lambda **_kwargs: _Desktop(root),
        patient_settle_seconds=0,
    )

    assert parse_patient_alert_ancestor_path(ancestor_text) == [
        {"name": "Patient memo", "control_type": "Pane"},
        {"name": "진료실", "control_type": "Window"},
    ]
    assert probe.check().marker_found is False
    assert probe.check().marker_found is True
    assert right_memo.read_count == 1
    assert wrong_memo.read_count == 0


def test_patient_alert_popup_is_always_on_top_and_contains_no_memo_text() -> None:
    _app()

    from KaosEghis.ui.emr_patient_alert import EmrPatientAlertPopup

    popup = EmrPatientAlertPopup()
    labels = " ".join(label.text() for label in popup.findChildren(QLabel))

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


def _context(chart="2735", revision=1):
    return PatientChartContext(SignalScope(42, 100, 101), chart, revision)


def test_shared_patient_probe_reads_only_memo_not_old_chart_target():
    probe, chart, memo, _root, _scope = _probe_fixture()
    result = probe.check_for_patient(_context(), lambda _context: True)
    assert result.marker_found
    assert chart.read_count == 0
    assert memo.read_count == 1
    assert "note *** detail" not in repr(result)


@pytest.mark.parametrize("when", ["before", "during"])
def test_patient_identity_is_checked_before_and_after_memo_read(when):
    probe, chart, memo, _root, _scope = _probe_fixture()
    checks = []

    def current(_context):
        checks.append(True)
        return when == "during" and len(checks) == 1

    result = probe.check_for_patient(_context(), current)
    assert not result.marker_found
    assert not result.available
    assert chart.read_count == 0
    assert memo.read_count == (1 if when == "during" else 0)


def test_shared_patient_probe_checks_connection_identity_and_disabled_setting():
    probe, _chart, memo, _root, _scope = _probe_fixture()
    wrong = PatientChartContext(SignalScope(99, 100, 101), "2735", 1)
    assert not probe.check_for_patient(wrong, lambda _context: True).available
    assert memo.read_count == 0
    disabled = EmrPatientAlertProbe(configuration=EmrPatientAlertConfiguration(enabled=False))
    assert not disabled.check_for_patient(_context(), lambda _context: True).marker_found


@pytest.fixture
def event_monitor(monkeypatch):
    _app()
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        COINIT_MULTITHREADED=0, CoInitializeEx=lambda _mode: None, CoUninitialize=lambda: None,
    ))
    now, current, calls, results = [0.0], [None], [], []

    def check(context, is_current):
        calls.append((context, threading.get_ident()))
        return EmrPatientAlertResult(True, True, is_current(context), "Test result.")

    fake_probe = SimpleNamespace(enabled=True, check_for_patient=check)
    monitor = EmrPatientAlertMonitor(
        probe=fake_probe, clock=lambda: now[0], patient_is_current=lambda ctx: ctx == current[0],
    )
    monitor.result_changed.connect(results.append)
    monitor.start()
    fixture = SimpleNamespace(
        monitor=monitor, now=now, current=current, calls=calls, results=results, probe=fake_probe,
    )
    yield fixture
    monitor.stop()
    _wait_for_memo(monitor)
    monitor.deleteLater()
    QApplication.instance().processEvents()


def _wait_for_memo(monitor):
    deadline = time.monotonic() + 3
    while monitor._thread is not None and time.monotonic() < deadline:
        QApplication.instance().processEvents()
        time.sleep(0.005)
    assert monitor._thread is None


def _load_patient(fixture, context):
    fixture.current[0] = context
    fixture.monitor.patient_changed(context)


def test_memo_checks_once_after_five_seconds_and_duplicate_events_do_not_restart(event_monitor):
    f = event_monitor
    main_thread = threading.get_ident()
    _load_patient(f, _context())
    assert f.monitor._timer.interval() == 5000
    f.now[0] = 3
    _load_patient(f, _context())
    assert f.monitor._deadline == 5
    f.now[0] = 4.99
    f.monitor._begin_check()
    assert f.calls == []
    f.now[0] = 5
    f.monitor._begin_check()
    _wait_for_memo(f.monitor)
    assert len(f.calls) == 1
    assert f.calls[0][1] != main_thread
    assert f.results[-1].marker_found
    assert not f.monitor._timer.isActive()
    f.now[0] = 100
    _load_patient(f, _context())
    f.monitor._begin_check()
    assert len(f.calls) == 1


def test_patient_change_restarts_five_second_wait_and_clear_cancels_it(event_monitor):
    f = event_monitor
    _load_patient(f, _context())
    f.now[0] = 3
    next_patient = _context("9999", 2)
    _load_patient(f, next_patient)
    f.now[0] = 5
    f.monitor._begin_check()
    assert f.calls == []
    assert f.monitor._deadline == 8
    _load_patient(f, None)
    f.now[0] = 8
    f.monitor._begin_check()
    assert f.calls == []
    assert not f.monitor._timer.isActive()
    _load_patient(f, _context("9999", 3))
    f.now[0] = 13
    f.monitor._begin_check()
    _wait_for_memo(f.monitor)
    assert len(f.calls) == 1


def test_same_patient_reload_rearms_alert_for_new_visit(event_monitor):
    f = event_monitor
    for revision in (1, 2):
        _load_patient(f, _context(revision=revision))
        assert not f.results[-1].marker_found
        f.now[0] += 5
        f.monitor._begin_check()
        _wait_for_memo(f.monitor)
        assert f.results[-1].marker_found
    assert len(f.calls) == 2


def test_disabled_alert_and_stopped_monitor_do_no_memo_work(event_monitor):
    f = event_monitor
    f.probe.enabled = False
    _load_patient(f, _context())
    f.now[0] = 5
    f.monitor._begin_check()
    assert not f.monitor._timer.isActive()
    assert f.calls == []
    f.probe.enabled = True
    f.monitor.replace_probe(f.probe)
    assert f.monitor._timer.isActive()
    f.monitor.stop()
    f.now[0] = 10
    f.monitor._begin_check()
    assert f.calls == []


def test_slow_old_patient_read_is_discarded_and_new_check_waits_without_overlap(event_monitor):
    f = event_monitor
    started, release = threading.Event(), threading.Event()
    original = f.probe.check_for_patient

    def slow_check(context, is_current):
        if context.revision == 1:
            f.calls.append((context, threading.get_ident()))
            started.set()
            assert release.wait(2)
            return EmrPatientAlertResult(True, True, True, "Stale result.")
        return original(context, is_current)

    f.probe.check_for_patient = slow_check
    _load_patient(f, _context())
    f.now[0] = 5
    f.monitor._begin_check()
    try:
        assert started.wait(1)
        _load_patient(f, _context("9999", 2))
        f.now[0] = 10
        f.monitor._begin_check()
        assert len(f.calls) == 1
        assert f.monitor._due
    finally:
        release.set()
        _wait_for_memo(f.monitor)
    assert [ctx.revision for ctx, _thread in f.calls] == [1, 2]
    assert not any(result.message == "Stale result." for result in f.results)
    assert f.results[-1].marker_found


def test_unavailable_memo_is_reported_once_without_background_retry(event_monitor):
    f = event_monitor

    def fail(context, is_current):
        f.calls.append((context, threading.get_ident()))
        raise RuntimeError("private patient text")

    f.probe.check_for_patient = fail
    _load_patient(f, _context())
    f.now[0] = 5
    f.monitor._begin_check()
    _wait_for_memo(f.monitor)
    assert not f.results[-1].available
    assert not f.results[-1].marker_found
    assert "private patient" not in repr(f.results)
    f.now[0] = 100
    f.monitor._begin_check()
    assert len(f.calls) == 1


@pytest.mark.parametrize("action", ["stop", "disable"])
def test_stop_or_settings_change_discards_inflight_result(event_monitor, action):
    f = event_monitor
    started, release = threading.Event(), threading.Event()

    def slow_check(context, is_current):
        started.set()
        assert release.wait(2)
        return EmrPatientAlertResult(True, True, True, "Stale result.")

    f.probe.check_for_patient = slow_check
    _load_patient(f, _context())
    f.now[0] = 5
    f.monitor._begin_check()
    try:
        assert started.wait(1)
        if action == "stop":
            f.monitor.stop()
        else:
            f.monitor.replace_probe(SimpleNamespace(enabled=False))
        f.results.clear()
    finally:
        release.set()
        _wait_for_memo(f.monitor)
    assert f.results == []
    assert not f.monitor._timer.isActive()


def test_lost_snapshot_is_unavailable_not_a_clear_memo_result(event_monitor):
    f = event_monitor

    def check(context, is_current):
        f.current[0] = None
        return EmrPatientAlertResult(True, True, True, "Old marker result.")

    f.probe.check_for_patient = check
    _load_patient(f, _context())
    f.now[0] = 5
    f.monitor._begin_check()
    _wait_for_memo(f.monitor)
    assert not f.results[-1].marker_found
    assert not f.results[-1].available
    assert "identity unavailable" in f.results[-1].message
