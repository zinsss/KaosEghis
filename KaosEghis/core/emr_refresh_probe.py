"""In-memory clear -> settling-delay diagnostics. No UIA, input, or DB access."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import threading
import time


@dataclass(frozen=True)
class _PendingClear:
    context: object = field(repr=False)
    cleared_at: float


class ClearRefreshDryRun:
    MAX_PENDING = 32
    SETTLE_SECONDS = 2.0
    EXPIRE_AFTER = 120.0

    def __init__(self, emit, *, clock=time.monotonic):
        self.emit = emit
        self.clock = clock
        self._lock = threading.Lock()
        self._pending = []
        self._closed = False

    def _message(self, ticket, detail):
        self.emit(f"{datetime.now():%H:%M:%S} | EMR probe | Chart {ticket.context.chart_no} | {detail} (dry run)")

    def enqueue(self, context):
        # Called by the clear callback. Preserve the departing patient, not the
        # current chart at dispatch time. Reloads have distinct context revisions.
        with self._lock:
            if self._closed or any(ticket.context == context for ticket in self._pending):
                return
            if len(self._pending) >= self.MAX_PENDING:
                self._message(_PendingClear(context, self.clock()), "Refresh wait not queued: diagnostic queue full")
                return
            self._pending.append(_PendingClear(context, self.clock()))

    def close(self):
        with self._lock:
            self._closed = True
            self._pending.clear()

    def tick(self, scope):
        with self._lock:
            if self._closed:
                return
            now = self.clock()
            for ticket in self._pending[:]:
                elapsed = now - ticket.cleared_at
                if ticket.context.scope != scope:
                    detail = "Refresh wait cancelled: EMR disconnected or changed; no query"
                elif elapsed < 0:
                    detail = "Refresh wait cancelled: invalid timing; no query"
                elif elapsed >= self.EXPIRE_AFTER:
                    detail = "Refresh wait expired after 120 s; no query"
                elif elapsed >= self.SETTLE_SECONDS:
                    detail = (f"{self.SETTLE_SECONDS:g} s delay elapsed -> would query PACS/Orders for this previous patient; "
                              f"waited {elapsed:.1f} s; DB commit unverified")
                else:
                    continue
                self._message(ticket, detail)
                self._pending.remove(ticket)
