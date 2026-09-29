from dataclasses import replace
from datetime import date
import threading
from types import SimpleNamespace

import pytest

from KaosEghis.core.emr_refresh_probe import ClearRefreshTrigger, RefreshRequest
from KaosEghis.core.emr_signal_probe import PatientChartContext, SignalScope


SCOPE = SignalScope(42, 100, 101)
DAY = date(2026, 9, 29)


@pytest.fixture
def trigger():
    clock, messages, today = [10.0], [], [DAY]
    probe = ClearRefreshTrigger(messages.append, clock=lambda: clock[0], today=lambda: today[0])
    return SimpleNamespace(probe=probe, clock=clock, messages=messages, today=today,
                           context=PatientChartContext(SCOPE, "001234", 1))


def tick(trigger, at, scope=SCOPE):
    trigger.clock[0] = at
    trigger.probe.tick(scope)


def test_waits_two_seconds_and_emits_one_day_request_without_patient_data(trigger):
    trigger.probe.enqueue(trigger.context)
    for at in (10, 10.5, 11.999):
        tick(trigger, at)
        assert trigger.probe.take_ready(SCOPE) == []
    tick(trigger, 12)
    assert trigger.probe.take_ready(SCOPE) == [RefreshRequest(SCOPE, DAY)]
    assert trigger.probe.take_ready(SCOPE) == []
    assert "DB commit unverified" in trigger.messages[0]
    assert "001234" not in repr(trigger.messages) + repr(trigger.probe._pending)


def test_burst_coalesces_and_waits_after_latest_clear(trigger):
    trigger.probe.enqueue(trigger.context)
    trigger.clock[0] = 11
    for index in range(100):
        trigger.probe.enqueue(replace(trigger.context, revision=index, chart_no="5678"))
    assert len(trigger.probe._pending) == 1
    tick(trigger, 12)
    assert trigger.probe.take_ready(SCOPE) == []
    tick(trigger, 13)
    assert trigger.probe.take_ready(SCOPE) == [RefreshRequest(SCOPE, DAY)]


def test_same_patient_reload_after_refresh_can_request_again(trigger):
    for at in (10, 20):
        trigger.clock[0] = at
        trigger.probe.enqueue(trigger.context)
        tick(trigger, at + 2)
        assert trigger.probe.take_ready(SCOPE) == [RefreshRequest(SCOPE, DAY)]


@pytest.mark.parametrize("scope", [None, replace(SCOPE, pid=43), replace(SCOPE, root=200), replace(SCOPE, treatment=102)])
def test_disconnect_or_changed_emr_cancels_pending_and_ready(trigger, scope):
    trigger.probe.enqueue(trigger.context)
    tick(trigger, 12, scope)
    assert trigger.probe.take_ready(SCOPE) == []
    trigger.probe.enqueue(trigger.context)
    tick(trigger, 14)
    assert trigger.probe.take_ready(scope) == []
    assert trigger.probe.take_ready(SCOPE) == []


@pytest.mark.parametrize("at", [130, 9.9])
def test_invalid_or_expired_timer_does_not_refresh(trigger, at):
    trigger.probe.enqueue(trigger.context)
    tick(trigger, at)
    assert trigger.probe.take_ready(SCOPE) == []
    assert not trigger.probe._pending


def test_close_discards_pending_and_ready(trigger):
    trigger.probe.enqueue(trigger.context)
    tick(trigger, 12)
    trigger.probe.close()
    trigger.probe.enqueue(trigger.context)
    tick(trigger, 14)
    assert not trigger.probe._pending
    assert trigger.probe.take_ready(SCOPE) == []


def test_midnight_preserves_clear_date(trigger):
    trigger.probe.enqueue(trigger.context)
    trigger.today[0] = date(2026, 9, 30)
    tick(trigger, 12)
    assert trigger.probe.take_ready(SCOPE) == [RefreshRequest(SCOPE, DAY)]


def test_concurrent_enqueues_and_slow_diagnostic_consumer_coalesce(trigger):
    threads = [threading.Thread(target=trigger.probe.enqueue, args=(trigger.context,)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    tick(trigger, 12)
    trigger.probe.enqueue(trigger.context)
    tick(trigger, 14)
    assert trigger.probe.take_ready(SCOPE) == [RefreshRequest(SCOPE, DAY)]


def test_trigger_never_opens_database_or_performs_input(monkeypatch, trigger):
    import psycopg2
    import pywinauto.keyboard
    import pyautogui

    def forbidden(*args, **kwargs):
        pytest.fail("A clear trigger must not open DB or generate input")

    monkeypatch.setattr(psycopg2, "connect", forbidden)
    monkeypatch.setattr(pywinauto.keyboard, "send_keys", forbidden)
    monkeypatch.setattr(pyautogui, "click", forbidden)
    trigger.probe.enqueue(trigger.context)
    tick(trigger, 12)
    assert trigger.probe.take_ready(SCOPE)
