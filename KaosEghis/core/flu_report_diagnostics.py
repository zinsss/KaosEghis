"""Bounded local timing records; never record SQL, credentials or patient data."""

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading


_WRITE_LOCK = threading.Lock()
_STAGES = (
    "connected", "session_ready", "timeout_set", "query_finished",
    "rows_fetched", "cursor_closed", "connection_closed",
)


def write_flu_report_diagnostic(
    path: Path, *, year: int, week: int, outcome: str,
    elapsed_seconds: float, stages: dict[str, float],
) -> None:
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "year": year,
        "week": week,
        "outcome": outcome if outcome in {
            "loaded", "unconfigured", "timeout", "unavailable", "error",
        } else "error",
        "elapsed_seconds": round(elapsed_seconds, 4),
        "stages_seconds": {name: stages[name] for name in _STAGES if name in stages},
    }
    try:
        with _WRITE_LOCK:
            handler = RotatingFileHandler(path, maxBytes=65536, backupCount=1, encoding="utf-8")
            try:
                handler.emit(logging.LogRecord(
                    "kaoseghis.flu", logging.INFO, __file__, 0,
                    json.dumps(record, ensure_ascii=True), (), None,
                ))
            finally:
                handler.close()
    except OSError:
        pass  # Diagnostics must not change the report result.
