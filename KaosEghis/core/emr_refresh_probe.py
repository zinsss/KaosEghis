"""Coalesced chart-change requests. No patient data, input, or database access."""

from dataclasses import dataclass, replace
from datetime import date, datetime
import threading
import time


@dataclass(frozen=True)
class RefreshRequest:
    scope: object
    day: date
    reason: str = "Chart cleared"
    follow_up_at: float | None = None


class ChartRefreshTrigger:
    SETTLE_SECONDS = 2.0
    FOLLOW_UP_SECONDS = 30.0
    EXPIRE_AFTER = 120.0

    def __init__(self, emit, *, clock=time.monotonic, today=date.today):
        self.emit = emit
        self.clock = clock
        self.today = today
        self._lock = threading.Lock()
        self._pending = {}
        self._ready = {}
        self._closed = False

    def enqueue(self, context, *, reason="Chart cleared"):
        with self._lock:
            if not self._closed:
                now = self.clock()
                key = (context.scope, self.today())
                previous = self._pending.get(key)
                follow_up_at = previous[0].follow_up_at if previous else None
                if reason == "Chart cleared":
                    follow_up_at = now + self.FOLLOW_UP_SECONDS
                request = RefreshRequest(*key, reason, follow_up_at)
                # Loads can coalesce the fast read but cannot erase a clear's
                # independent verification deadline, including across midnight.
                self._pending[key] = (request, now)

    def close(self):
        with self._lock:
            self._closed = True
            self._pending.clear()
            self._ready.clear()

    def tick(self, scope):
        with self._lock:
            if self._closed:
                return
            now = self.clock()
            for key, (request, changed_at) in list(self._pending.items()):
                elapsed = now - changed_at
                if request.scope != scope or elapsed < 0 or elapsed >= self.EXPIRE_AFTER:
                    del self._pending[key]
                elif elapsed >= self.SETTLE_SECONDS:
                    del self._pending[key]
                    previous = self._ready.get(key)
                    if previous is not None:
                        deadline = max((item.follow_up_at for item in (request, previous)
                                        if item.follow_up_at is not None), default=None)
                        request = replace(request, follow_up_at=deadline)
                    self._ready[key] = request
                    self.emit(f"{datetime.now():%H:%M:%S} | EMR refresh | {request.reason} -> PACS day refresh queued; DB commit unverified")

    def take_ready(self, scope):
        # Separate from diagnostic output, so dropped status lines cannot discard
        # refreshes. Only the GUI dispatcher consumes these requests.
        with self._lock:
            result = [item for item in self._ready.values() if item.scope == scope]
            self._ready.clear()
            return result
