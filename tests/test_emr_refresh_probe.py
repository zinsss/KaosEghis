from dataclasses import replace
from types import SimpleNamespace

import pytest

from KaosEghis.core import emr_refresh_probe as refresh
from KaosEghis.core.emr_signal_probe import PatientChartContext, SignalScope, Win32SignalReader


SCOPE = SignalScope(42, 100, 101)


@pytest.fixture
def dry():
    clock, messages, scope = [10.0], [], [SCOPE]
    probe = refresh.ClearRefreshDryRun(messages.append, clock=lambda: clock[0])
    return SimpleNamespace(probe=probe, clock=clock, messages=messages, scope=scope,
                           context=PatientChartContext(SCOPE, "001234", 1))


def tick(dry, at, ready=True, check=None):
    dry.clock[0] = at
    dry.probe.tick(lambda: dry.scope[0], check or (lambda scope: (ready, "no caret")))


def test_clear_waits_for_two_fresh_ready_samples_and_keeps_previous_patient(dry):
    dry.probe.enqueue(dry.context)
    tick(dry, 10.0)  # Same instant as the clear is not a post-clear sample.
    tick(dry, 10.5)
    assert not dry.messages
    tick(dry, 11.0)
    assert len(dry.messages) == 1
    assert "Chart 001234" in dry.messages[0]
    assert "F1 caret ready -> would query PACS/Orders" in dry.messages[0]
    assert "DB commit unverified" in dry.messages[0]
    tick(dry, 12.0, check=lambda _: pytest.fail("No readiness polling when idle"))


def test_no_db_job_and_multiple_departing_patients_are_not_overwritten(dry):
    dry.probe.enqueue(dry.context)
    dry.clock[0] += 0.1
    dry.probe.enqueue(replace(dry.context, chart_no="000456", revision=2))
    tick(dry, 10.6)
    tick(dry, 11.1)
    assert len(dry.messages) == 2
    assert "001234" in dry.messages[0] and "000456" in dry.messages[1]


def test_missing_caret_defers_once_then_can_become_ready(dry):
    dry.probe.enqueue(dry.context)
    for at in (10.1, 11, 24.9, 25.5, 28):
        tick(dry, at, False)
    assert len(dry.messages) == 1
    assert "Still waiting for F1: no caret; deferred, no query" in dry.messages[0]
    tick(dry, 30)
    tick(dry, 32)
    assert len(dry.messages) == 2
    assert "would query" in dry.messages[1]


def test_wait_expires_explicitly_and_stops_extra_uia_checks(dry):
    dry.probe.enqueue(dry.context)
    tick(dry, 130, check=lambda _: pytest.fail("Expired ticket must not check UIA"))
    assert "expired after 120 s; no query" in dry.messages[0]
    tick(dry, 131, check=lambda _: pytest.fail("No idle polling"))


@pytest.mark.parametrize("scope", [None, replace(SCOPE, pid=43), replace(SCOPE, treatment=102)])
def test_disconnect_or_restarted_emr_cancels_pending(dry, scope):
    dry.probe.enqueue(dry.context)
    dry.scope[0] = scope
    tick(dry, 10.1, check=lambda _: pytest.fail("Changed scope must not inspect UIA"))
    assert "cancelled" in dry.messages[0]
    assert "would query" not in dry.messages[0]


@pytest.mark.parametrize("change", ["scope", "close", "slow", "error"])
def test_late_or_failed_readiness_cannot_report_success(dry, change):
    dry.probe.enqueue(dry.context)
    tick(dry, 10.1)

    def read(scope):
        if change == "scope":
            dry.scope[0] = None
        elif change == "close":
            dry.probe.close()
        elif change == "slow":
            dry.clock[0] += 2
        else:
            raise RuntimeError("PRIVATE provider text")
        return True, "ready"

    tick(dry, 10.6, check=read)
    assert not any("would query" in text for text in dry.messages)
    assert "PRIVATE" not in repr(dry.messages)


def test_lost_caret_resets_stability_and_new_ticket_during_read_needs_own_samples(dry):
    dry.probe.enqueue(dry.context)
    tick(dry, 10.1)
    tick(dry, 10.6, False)

    def read(scope):
        dry.probe.enqueue(replace(dry.context, chart_no="000456", revision=2))
        return True, "ready"

    tick(dry, 11.1, check=read)
    tick(dry, 11.6)
    assert len(dry.messages) == 1 and "001234" in dry.messages[0]
    tick(dry, 12.1)
    assert len(dry.messages) == 2 and "000456" in dry.messages[1]


def test_queue_is_bounded_and_closed_queue_does_not_accept_work(dry):
    for index in range(dry.probe.MAX_PENDING + 1):
        dry.probe.enqueue(replace(dry.context, revision=index))
    assert len(dry.probe._pending) == dry.probe.MAX_PENDING
    assert len(dry.messages) == 1 and "queue full" in dry.messages[0]
    assert "001234" not in repr(dry.probe._pending)
    dry.probe.close()
    dry.probe.enqueue(dry.context)
    tick(dry, 11, check=lambda _: pytest.fail("Stopped probe"))
    assert not dry.probe._pending


def test_checks_are_rate_limited(dry):
    calls = []
    dry.probe.enqueue(dry.context)
    for i in range(20):
        tick(dry, 10 + i * 0.05, check=lambda scope: (calls.append(scope) or False, "no caret"))
    assert len(calls) == 2


def test_new_clear_cannot_shorten_previous_tickets_ready_stability_window(dry):
    dry.probe.enqueue(dry.context)
    tick(dry, 10.1)
    dry.clock[0] = 10.2
    dry.probe.enqueue(replace(dry.context, chart_no="000456", revision=2))
    tick(dry, 10.3)
    assert not dry.messages
    tick(dry, 10.9)
    assert len(dry.messages) == 1
    tick(dry, 11.5)
    assert len(dry.messages) == 2


class Node:
    def __init__(self, auto_id, handle, parent=None):
        self.element_info = SimpleNamespace(automation_id=auto_id, handle=handle, process_id=42,
                                            class_name="EditClass", control_type="Edit")
        self._parent = parent
        self.visible = self.enabled = self.focused = True

    def parent(self):
        return self._parent

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def has_keyboard_focus(self):
        return self.focused

    def window_text(self):
        pytest.fail("Never read symptom text")


@pytest.fixture
def caret():
    treatment = Node("Treatment", 101)
    container = Node("TreatmentSymp", 120, treatment)
    field = Node("eghisRichTextBox", 130, container)
    focused = Node("", 130, field)
    reader = SimpleNamespace(caret_context=lambda scope: (130, 130), _belongs=lambda p, c: p == c)
    target = refresh.F1Target("eghisRichTextBox", "TreatmentSymp", "Treatment", "Edit", "EditClass")
    loads, lookups = [], []
    probe = refresh.F1CaretProbe(reader, target_loader=lambda: loads.append(1) or target,
                                focused_element=lambda: lookups.append(1) or focused)
    return SimpleNamespace(probe=probe, reader=reader, field=field, container=container,
                           focused=focused, treatment=treatment, loads=loads, lookups=lookups)


def test_f1_caret_requires_scoped_configured_field_without_reading_text(caret):
    assert caret.probe.check(SCOPE) == (True, "F1 caret ready")
    assert caret.probe.check(SCOPE)[0]
    assert len(caret.loads) == 1


@pytest.mark.parametrize("change", ["caret", "focus", "field", "scope", "pid", "class", "type",
                                    "hidden", "disabled", "treatment", "handle", "foreign_caret"])
def test_f1_rejects_other_fields_contexts_and_inaccessible_targets(caret, change):
    if change == "caret":
        caret.reader.caret_context = lambda scope: None
    elif change == "focus":
        caret.focused.focused = False
    elif change == "field":
        caret.field.element_info.automation_id = "TreatmentPtntMemo"
    elif change == "scope":
        caret.container.element_info.automation_id = "OtherRichTextArea"
    elif change == "pid":
        caret.focused.element_info.process_id = 43
    elif change == "class":
        caret.field.element_info.class_name = "OtherClass"
    elif change == "type":
        caret.field.element_info.control_type = "Button"
    elif change == "hidden":
        caret.field.visible = False
    elif change == "disabled":
        caret.field.enabled = False
    elif change == "treatment":
        caret.treatment.element_info.automation_id = "Claims"
    elif change == "handle":
        caret.field.element_info.handle = 0
    else:
        caret.reader.caret_context = lambda scope: (140, 140)
    assert not caret.probe.check(SCOPE)[0]
    if change == "caret":
        assert not caret.lookups


def test_caret_focus_change_during_uia_read_is_rejected(caret):
    contexts = iter([(130, 130), None])
    caret.reader.caret_context = lambda scope: next(contexts)
    assert not caret.probe.check(SCOPE)[0]


def test_missing_settings_and_provider_errors_are_sanitized(caret):
    caret.probe.target_loader = lambda: None
    assert not caret.probe.check(SCOPE)[0]
    assert not caret.lookups
    caret.probe.target_loader = lambda: (_ for _ in ()).throw(RuntimeError("PRIVATE"))
    result = caret.probe.check(replace(SCOPE, pid=43))
    assert not result[0] and "PRIVATE" not in repr(result)


def test_ancestor_walk_is_bounded(caret):
    caret.field._parent = caret.focused
    assert not caret.probe.check(SCOPE)[0]


@pytest.mark.parametrize("bad", [None, "missing", "menu", "other_app", "claim", "foreign_pid", "hidden", "disabled", "rect"])
def test_native_caret_context_guards(bad):
    reader = object.__new__(Win32SignalReader)
    reader.keyboard_context = lambda scope: bad != "other_app"
    reader._belongs = lambda p, c: bool(c and (p == c or (p == 101 and c == 130)))
    reader.gui = SimpleNamespace(IsWindowVisible=lambda h: bad != "hidden", IsWindowEnabled=lambda h: bad != "disabled")
    reader.process = SimpleNamespace(GetWindowThreadProcessId=lambda h: (1, 43 if bad == "foreign_pid" else 42))

    def info(thread, pointer):
        obj = pointer._obj
        obj.hwndActive = 100
        obj.hwndFocus = 140 if bad == "claim" else 130
        obj.hwndCaret = 0 if bad == "missing" else obj.hwndFocus
        obj.flags = 4 if bad == "menu" else 0
        obj.rcCaret.bottom = 0 if bad == "rect" else 16
        return True

    reader.user32 = SimpleNamespace(GetGUIThreadInfo=info)
    assert (reader.caret_context(SCOPE) == (130, 130)) is (bad is None)


@pytest.mark.parametrize("missing", [False, True])
def test_local_settings_connection_is_read_only_and_closed(monkeypatch, tmp_path, missing):
    from KaosEghis.db import database, repositories

    calls = []
    connection = SimpleNamespace(close=lambda: calls.append("close"))
    monkeypatch.setattr(database, "get_database_path", lambda: tmp_path / "local.db")
    monkeypatch.setattr(refresh.sqlite3, "connect", lambda path, **kw: calls.append((path, kw)) or connection)
    monkeypatch.setattr(repositories, "get_active_emr_target_profile", lambda c: SimpleNamespace(id=1, main_window_automation_id="Treatment"))
    monkeypatch.setattr(repositories, "get_emr_ui_target_by_key", lambda *a: None if missing else SimpleNamespace(
        automation_id="eghisRichTextBox", scope_automation_id="TreatmentSymp", name_match=None,
        control_type=None, class_name=None,
    ))
    result = refresh.load_f1_target()
    assert (result is None) is missing
    assert calls[0][0].endswith("?mode=ro")
    assert calls[0][1]["uri"] is True
    assert calls[-1] == "close"
