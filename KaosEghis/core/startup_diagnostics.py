"""Record startup phases and a one-shot Python stack for a stalled phase."""

from datetime import datetime, timezone
import faulthandler
import json
from pathlib import Path
from time import perf_counter


class StartupDiagnostics:
    STALL_SECONDS = 10

    def __init__(self, path: Path | None = None) -> None:
        self._stream = None
        self._armed = False
        self._started = perf_counter()
        try:
            if path is None:
                from KaosEghis.db.database import get_data_dir

                path = get_data_dir() / "startup-diagnostics.log"
            if path.exists():
                path.replace(path.with_name("startup-diagnostics.previous.log"))
            self._stream = path.open("w", encoding="utf-8")
        except OSError:
            pass

    def stage(self, name: str) -> None:
        if self._stream is None:
            return
        self._cancel_watchdog()
        self._write("stage", name)
        try:
            # This watchdog can report a blocked GUI thread without Qt processing events.
            faulthandler.dump_traceback_later(
                self.STALL_SECONDS, repeat=False, file=self._stream, exit=False,
            )
            self._armed = True
        except (OSError, RuntimeError, ValueError):
            pass

    def close(self, outcome: str = "finished") -> None:
        if self._stream is None:
            return
        self._cancel_watchdog()
        self._write("outcome", outcome)
        try:
            self._stream.close()
        except OSError:
            pass
        self._stream = None

    def _cancel_watchdog(self) -> None:
        if self._armed:
            faulthandler.cancel_dump_traceback_later()
            self._armed = False

    def _write(self, key: str, value: str) -> None:
        try:
            self._stream.write(json.dumps({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": round(perf_counter() - self._started, 3),
                key: value,
            }) + "\n")
            self._stream.flush()
        except OSError:
            pass
