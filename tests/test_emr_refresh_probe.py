from dataclasses import replace
import threading
from types import SimpleNamespace

import pytest

from KaosEghis.core import emr_refresh_probe as refresh
from KaosEghis.core.emr_signal_probe import PatientChartContext, SignalScope


SCOPE = SignalScope(42, 100, 101)


@pytest.fixture
def dry():
    clock, messages, scope = [10.0], [], [SCOPE]
    probe = refresh.ClearRefreshDryRun(messages.append, clock=lambda: clock[0])
    return SimpleNamespace(probe=probe, clock=clock, messages=messages, scope=scope,
                           context=PatientChartContext(SCOPE, "001234", 1))


def tick(dry, at):
    dry.clock[0] = at
    dry.probe.tick(dry.scope[0])


def test_waits_full_two_seconds_then_reports_previous_patient_once(dry):
    dry.probe.enqueue(dry.context)
    for at in (10.0, 10.5, 11.0, 11.999):
        tick(dry, at)
        assert not dry.messages
    tick(dry, 12.0)
    assert len(dry.messages) == 1
    assert "Chart 001234" in dry.messages[0]
    assert "2 s delay elapsed -> would query PACS/Orders" in dry.messages[0]
    assert "waited 2.0 s; DB commit unverified" in dry.messages[0]
    assert "dry run" in dry.messages[0]
    tick(dry, 13.0)
    assert len(dry.messages) == 1
    assert not dry.probe._pending


def test_new_patient_does_not_replace_old_chart_or_restart_old_timer(dry):
    dry.probe.enqueue(dry.context)
    dry.clock[0] = 11.0
    dry.probe.enqueue(replace(dry.context, chart_no="000456", revision=2))
    tick(dry, 12.0)
    assert len(dry.messages) == 1 and "001234" in dry.messages[0]
    tick(dry, 12.999)
    assert len(dry.messages) == 1
    tick(dry, 13.0)
    assert len(dry.messages) == 2 and "000456" in dry.messages[1]


def test_duplicate_context_does_not_repeat_or_restart_wait(dry):
    dry.probe.enqueue(dry.context)
    dry.clock[0] = 11.0
    dry.probe.enqueue(dry.context)
    tick(dry, 12.0)
    assert len(dry.messages) == 1
    assert not dry.probe._pending


def test_same_patient_reload_has_separate_wait(dry):
    dry.probe.enqueue(dry.context)
    dry.clock[0] = 11.0
    dry.probe.enqueue(replace(dry.context, revision=2))
    tick(dry, 12.0)
    tick(dry, 13.0)
    assert len(dry.messages) == 2
    assert all("001234" in message for message in dry.messages)


@pytest.mark.parametrize("scope", [None, replace(SCOPE, pid=43), replace(SCOPE, root=200), replace(SCOPE, treatment=102)])
def test_disconnect_or_restarted_emr_cancels_pending_even_when_due(dry, scope):
    dry.probe.enqueue(dry.context)
    dry.scope[0] = scope
    tick(dry, 12.0)
    assert "cancelled" in dry.messages[0]
    assert "would query" not in dry.messages[0]
    dry.scope[0] = SCOPE
    tick(dry, 13.0)
    assert len(dry.messages) == 1


def test_late_worker_reports_actual_delay_not_commit_success(dry):
    dry.probe.enqueue(dry.context)
    tick(dry, 15.0)
    assert "waited 5.0 s; DB commit unverified" in dry.messages[0]


@pytest.mark.parametrize("at,reason", [(130.0, "expired after 120 s"), (9.9, "invalid timing")])
def test_stale_or_invalid_timer_is_not_reported_as_due(dry, at, reason):
    dry.probe.enqueue(dry.context)
    tick(dry, at)
    assert reason in dry.messages[0] and "no query" in dry.messages[0]
    assert "would query" not in dry.messages[0]
    assert not dry.probe._pending


def test_closed_queue_does_not_accept_or_dispatch_work(dry):
    dry.probe.enqueue(dry.context)
    dry.probe.close()
    dry.probe.enqueue(replace(dry.context, revision=2))
    tick(dry, 12.0)
    assert not dry.probe._pending
    assert not dry.messages


def test_queue_is_bounded_and_overflow_is_explicit(dry):
    for index in range(dry.probe.MAX_PENDING + 1):
        dry.probe.enqueue(replace(dry.context, revision=index))
    assert len(dry.probe._pending) == dry.probe.MAX_PENDING
    assert len(dry.messages) == 1 and "queue full" in dry.messages[0]
    assert "001234" not in repr(dry.probe._pending)
    tick(dry, 12.0)
    assert len(dry.messages) == dry.probe.MAX_PENDING + 1


def test_empty_queue_does_not_emit_diagnostics(dry):
    tick(dry, 12.0)
    assert not dry.messages


def test_concurrent_duplicate_enqueues_remain_one_ticket(dry):
    threads = [threading.Thread(target=dry.probe.enqueue, args=(dry.context,)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()
    tick(dry, 12.0)
    assert len(dry.messages) == 1


def test_delay_never_opens_database_or_performs_input(monkeypatch, dry):
    import sqlite3
    import psycopg2
    import pywinauto.keyboard
    import pyautogui

    def forbidden(*args, **kwargs):
        pytest.fail("Delay dry run must not access DB or generate input")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(psycopg2, "connect", forbidden)
    monkeypatch.setattr(pywinauto.keyboard, "send_keys", forbidden)
    monkeypatch.setattr(pyautogui, "press", forbidden)
    monkeypatch.setattr(pyautogui, "click", forbidden)
    dry.probe.enqueue(dry.context)
    tick(dry, 12.0)
    assert len(dry.messages) == 1
