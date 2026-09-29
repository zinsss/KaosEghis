from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from KaosEghis.core import eghis_db, emr_read_queue


def test_pacs_flu_and_context_reads_are_fifo_and_close_before_next_connect(monkeypatch):
    events = []
    started, release = threading.Event(), threading.Event()
    index = [0]

    class Connection:
        def __init__(self, number):
            self.number = number

        def set_session(self, **kwargs):
            assert kwargs == {"readonly": True, "autocommit": True}

        def cursor(self):
            return Cursor(self.number)

        def close(self):
            events.append((self.number, "closed"))

    class Cursor:
        description = [("value",)]

        def __init__(self, number):
            self.number = number

        def execute(self, query):
            if query.startswith("SELECT"):
                events.append((self.number, query))
                if self.number == 1:
                    started.set()
                    assert release.wait(3)

        def fetchall(self):
            return [(self.number,)]

        def close(self):
            events.append((self.number, "cursor_closed"))

    def connect(*args, **kwargs):
        assert threading.current_thread().name.startswith("KaosEghis-emr")
        assert kwargs["connect_timeout"] == 5
        assert kwargs["application_name"] == "KaosEghis-emr"
        index[0] += 1
        if index[0] > 1:
            assert events[-1] == (index[0] - 1, "closed")
        events.append((index[0], "connected"))
        return Connection(index[0])

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    with ThreadPoolExecutor(3) as callers:
        first = callers.submit(eghis_db.run_readonly_query, "mock", "SELECT 'pacs'")
        assert started.wait(2)
        second = callers.submit(eghis_db.run_readonly_query, "mock", "SELECT 'flu'")
        deadline = time.monotonic() + 2
        while emr_read_queue._worker._work_queue.qsize() < 1:
            assert time.monotonic() < deadline
            time.sleep(0.005)
        third = callers.submit(eghis_db.run_readonly_query, "mock", "SELECT 'context'")
        assert index[0] == 1
        release.set()
        assert [future.result(3)[1] for future in (first, second, third)] == [[(1,)], [(2,)], [(3,)]]
    assert [entry[1] for entry in events if entry[1].startswith("SELECT")] == ["SELECT 'pacs'", "SELECT 'flu'", "SELECT 'context'"]


@pytest.mark.parametrize("failure", ["connect", "readonly", "cursor", "query", "fetch", "cursor_close"])
def test_failed_read_releases_exclusive_slot_and_closes_connection(monkeypatch, failure):
    events = []

    @contextmanager
    def exclusive():
        events.append("lock")
        try:
            yield
        finally:
            events.append("unlock")

    def fail(stage):
        if stage == failure:
            raise RuntimeError(stage)

    class Cursor:
        description = [("value",)]
        def execute(self, query):
            if query.startswith("SELECT"):
                fail("query")
        def fetchall(self):
            fail("fetch")
            return [(1,)]
        def close(self):
            events.append("cursor_close")
            fail("cursor_close")

    class Connection:
        def set_session(self, **kwargs):
            fail("readonly")
        def cursor(self):
            fail("cursor")
            return Cursor()
        def close(self):
            events.append("close")

    def connect(*args, **kwargs):
        fail("connect")
        return Connection()

    monkeypatch.setattr(emr_read_queue, "_exclusive_reader", exclusive)
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    with pytest.raises(RuntimeError):
        eghis_db.run_readonly_query("mock", "SELECT 1")
    assert events[-1] == "unlock"
    if failure != "connect":
        assert events[-2] == "close"
    failure = None
    assert eghis_db.run_readonly_query("mock", "SELECT 1") == (["value"], [(1,)])


def test_rejected_write_never_connects(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=lambda *a, **k: pytest.fail("write connected")))
    with pytest.raises(eghis_db.EghisDbQueryRejectedError):
        eghis_db.run_readonly_query("mock", "DELETE FROM orders")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process mutex")
def test_named_mutex_serializes_another_process_without_opening_db():
    import subprocess

    script = "from KaosEghis.core.emr_read_queue import _exclusive_reader\nwith _exclusive_reader():\n print('acquired', flush=True)"
    with emr_read_queue._exclusive_reader():
        process = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(0.3)
        assert process.poll() is None
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, stderr
    assert stdout.strip() == "acquired"
