"""Coalesced chart-clear requests. No patient data, input, or database access."""

from dataclasses import dataclass
from datetime import date, datetime
import threading
import time


@dataclass(frozen=True)
class RefreshRequest:
    scope: object
    day: date


class ClearRefreshTrigger:
    SETTLE_SECONDS = 2.0
    EXPIRE_AFTER = 120.0

    def __init__(self, emit, *, clock=time.monotonic, today=date.today):
        self.emit = emit
        self.clock = clock
        self.today = today
        self._lock = threading.Lock()
        self._pending = {}
        self._ready = set()
        self._closed = False

    def enqueue(self, context):
        with self._lock:
            if not self._closed:
                # A burst becomes one day-wide read after its last clear. Keep
                # the clear's date even if dispatch crosses midnight.
                request = RefreshRequest(context.scope, self.today())
                self._pending[request] = self.clock()

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
            for request, cleared_at in list(self._pending.items()):
                elapsed = now - cleared_at
                if request.scope != scope or elapsed < 0 or elapsed >= self.EXPIRE_AFTER:
                    del self._pending[request]
                elif elapsed >= self.SETTLE_SECONDS:
                    del self._pending[request]
                    self._ready.add(request)
                    self.emit(f"{datetime.now():%H:%M:%S} | EMR refresh | Chart cleared -> PACS day refresh queued; DB commit unverified")

    def take_ready(self, scope):
        # Separate from diagnostic output, so dropped status lines cannot discard
        # refreshes. Only the GUI dispatcher consumes this set.
        with self._lock:
            result = [item for item in self._ready if item.scope == scope]
            self._ready.clear()
            return result
