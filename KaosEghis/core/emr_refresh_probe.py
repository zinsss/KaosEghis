"""Passive, in-memory clear -> F1-caret diagnostics. Never queries the EMR DB."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
import sqlite3
import threading
import time


@dataclass(frozen=True)
class F1Target:
    automation_id: str
    scope_automation_id: str
    treatment_automation_id: str
    control_type: str | None = None
    class_name: str | None = None


def load_f1_target() -> F1Target | None:
    # Read local configuration only, without migrations or a writable connection.
    from KaosEghis.db.database import get_database_path
    from KaosEghis.db.repositories import get_active_emr_target_profile, get_emr_ui_target_by_key

    with closing(sqlite3.connect(get_database_path().as_uri() + "?mode=ro", uri=True, timeout=0.2)) as connection:
        profile = get_active_emr_target_profile(connection)
        target = get_emr_ui_target_by_key(connection, profile.id, "sx") if profile else None
        if not target or not target.automation_id or target.name_match:
            return None  # Never read symptom text to match a field's Name/Value.
        scope_id = target.scope_automation_id
        if not scope_id and target.parent_target_key:
            parent = get_emr_ui_target_by_key(connection, profile.id, target.parent_target_key)
            scope_id = parent.automation_id if parent else None
        if not scope_id or not profile.main_window_automation_id:
            return None
        return F1Target(target.automation_id, scope_id, profile.main_window_automation_id,
                        target.control_type, target.class_name)


def _focused_element():
    from pywinauto.uia_defines import IUIA
    from pywinauto.uia_element_info import UIAElementInfo
    from pywinauto.controls.uiawrapper import UIAWrapper

    return UIAWrapper(UIAElementInfo(IUIA().iuia.GetFocusedElement()))


class F1CaretProbe:
    """Inspect only the focused element and a bounded ancestor chain in the MTA worker."""

    def __init__(self, reader, *, target_loader=load_f1_target, focused_element=_focused_element):
        self.reader = reader
        self.target_loader = target_loader
        self.focused_element = focused_element
        self._scope = None
        self._target = None

    def check(self, scope) -> tuple[bool, str]:
        try:
            if scope != self._scope:
                self._scope, self._target = scope, None
                self._target = self.target_loader()
            target = self._target
            if target is None:
                return False, "F1 target configuration unavailable; restart after checking sx settings"
            caret = self.reader.caret_context(scope)
            if caret is None:
                return False, "no caret in focused EMR treatment entry"
            node = self.focused_element()
            if not node.has_keyboard_focus():
                return False, "F1 keyboard focus unconfirmed"
            field_found = scope_found = False
            for _ in range(16):
                if node is None:
                    break
                info = node.element_info
                if info.process_id != scope.pid or not node.is_visible() or not node.is_enabled():
                    break
                if not field_found and info.automation_id == target.automation_id:
                    if ((target.control_type and info.control_type != target.control_type)
                            or (target.class_name and info.class_name != target.class_name)):
                        break
                    handle = int(info.handle or 0)
                    if not handle or not all(self.reader._belongs(handle, item) for item in caret):
                        break
                    field_found = True
                elif field_found and info.automation_id == target.scope_automation_id:
                    scope_found = True
                if int(info.handle or 0) == scope.treatment:
                    if (field_found and scope_found
                            and info.automation_id == target.treatment_automation_id
                            and self.reader.caret_context(scope) == caret):
                        return True, "F1 caret ready"
                    break
                node = node.parent()
            return False, "caret is not in the configured F1 symptom field"
        except Exception:
            return False, "F1 readiness unavailable; no query attempted"


@dataclass
class _PendingClear:
    context: object = field(repr=False)
    cleared_at: float
    ready_since: float | None = None
    deferred: bool = False


class ClearRefreshDryRun:
    MAX_PENDING = 32
    DEFER_AFTER = 15.0
    EXPIRE_AFTER = 120.0
    SAMPLE_INTERVAL = 0.5
    DEFERRED_INTERVAL = 2.0
    MAX_READ_TIME = 1.0

    def __init__(self, emit, *, clock=time.monotonic):
        self.emit = emit
        self.clock = clock
        self._lock = threading.Lock()
        self._pending = []
        self._next_check = 0.0
        self._closed = False

    def _message(self, ticket, detail):
        self.emit(f"{datetime.now():%H:%M:%S} | EMR probe | Chart {ticket.context.chart_no} | {detail} (dry run)")

    def enqueue(self, context):
        # Called by the clear callback. No UIA, local settings, or EMR reads here.
        with self._lock:
            if self._closed:
                return
            if len(self._pending) >= self.MAX_PENDING:
                self._message(_PendingClear(context, self.clock()), "F1 wait not queued: diagnostic queue full")
                return
            was_empty = not self._pending
            self._pending.append(_PendingClear(context, self.clock()))
            self._next_check = 0.0 if was_empty else min(self._next_check, self.clock() + self.SAMPLE_INTERVAL)

    def close(self):
        with self._lock:
            self._closed = True
            self._pending.clear()

    def tick(self, scope_provider, check):
        started = self.clock()
        scope = scope_provider()
        with self._lock:
            if self._closed:
                return
            for ticket in self._pending[:]:
                if ticket.context.scope != scope:
                    self._message(ticket, "F1 wait cancelled: EMR disconnected or changed; no query")
                    self._pending.remove(ticket)
                elif started - ticket.cleared_at >= self.EXPIRE_AFTER:
                    self._message(ticket, "F1 wait expired after 120 s; no query")
                    self._pending.remove(ticket)
            if not self._pending or started < self._next_check:
                return
            tickets = tuple(self._pending)
            self._next_check = started + self.SAMPLE_INTERVAL
        # Never hold the callback lock across a potentially slow UIA provider.
        try:
            ready, reason = check(scope)
        except Exception:
            ready, reason = False, "F1 readiness unavailable"
        finished = self.clock()
        current_scope = scope_provider()
        with self._lock:
            if self._closed:
                return
            for ticket in tickets:
                if ticket not in self._pending:
                    continue
                if current_scope != ticket.context.scope:
                    self._message(ticket, "F1 wait cancelled: EMR disconnected or changed; no query")
                    self._pending.remove(ticket)
                    continue
                fresh = 0 <= finished - started <= self.MAX_READ_TIME and started > ticket.cleared_at
                if fresh and ready and finished - ticket.cleared_at < self.EXPIRE_AFTER:
                    gap = started - ticket.ready_since if ticket.ready_since is not None else None
                    if gap is not None and self.SAMPLE_INTERVAL <= gap <= 3.0:
                        elapsed = finished - ticket.cleared_at
                        self._message(ticket, f"F1 caret ready -> would query PACS/Orders for this previous patient; waited {elapsed:.1f} s; DB commit unverified")
                        self._pending.remove(ticket)
                        continue
                    if gap is None or gap < 0 or gap > 3.0:
                        ticket.ready_since = started
                else:
                    ticket.ready_since = None
                if not ticket.deferred and finished - ticket.cleared_at >= self.DEFER_AFTER:
                    ticket.deferred = True
                    detail = reason if fresh and not ready else "readiness not yet stable"
                    self._message(ticket, f"Still waiting for F1: {detail}; deferred, no query")
            if self._pending and all(ticket.deferred for ticket in self._pending):
                self._next_check = finished + self.DEFERRED_INTERVAL
