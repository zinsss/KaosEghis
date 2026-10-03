from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import sys
import threading
import time
from types import MappingProxyType, SimpleNamespace

import pytest

from KaosEghis.core import eghis_db, emr_read_queue


@pytest.fixture(autouse=True)
def isolated_coordinator(monkeypatch):
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="KaosEghis-emr-test")
    retained = []
    monkeypatch.setattr(emr_read_queue, "_worker", worker)
    monkeypatch.setattr(emr_read_queue, "_capacity", threading.BoundedSemaphore(64))
    monkeypatch.setattr(emr_read_queue, "_unhealthy", threading.Event())
    monkeypatch.setattr(emr_read_queue, "_retained_mutexes", retained)
    yield

    def release_test_locks():
        if sys.platform == "win32":
            import win32api
            import win32event
            for handle in retained:
                win32event.ReleaseMutex(handle)
                win32api.CloseHandle(handle)

    # Mutex ownership belongs to the worker, not the pytest main thread.
    worker.submit(release_test_locks).result(5)
    worker.shutdown(wait=True)


def test_pacs_flu_health_context_and_future_orders_reads_are_fifo(monkeypatch):
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
    queries = ["SELECT 'pacs'", "SELECT 'flu'", "SELECT 1", "SELECT 'context'", "SELECT 'future-orders'"]
    with ThreadPoolExecutor(len(queries)) as callers:
        futures = []
        try:
            for number, query in enumerate(queries):
                futures.append(callers.submit(eghis_db.run_readonly_query, "mock", query))
                if number == 0:
                    assert started.wait(2)
                else:
                    deadline = time.monotonic() + 2
                    while emr_read_queue._worker._work_queue.qsize() < number:
                        assert time.monotonic() < deadline
                        time.sleep(0.005)
            assert index[0] == 1
        finally:
            release.set()
        assert [future.result(3)[1] for future in futures] == [[(n,)] for n in range(1, 6)]
    assert [entry[1] for entry in events if entry[1].startswith("SELECT")] == queries


@pytest.mark.parametrize("failure", ["connect", "readonly", "cursor", "timeout_setup", "query", "fetch", "cursor_close"])
@pytest.mark.parametrize("bound", [False, True])
def test_failed_read_releases_exclusive_slot_and_closes_connection(monkeypatch, failure, bound):
    events = []
    query = "SELECT %s" if bound else "SELECT 1"
    params = (1,) if bound else None

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
        def execute(self, query, params=None):
            if query.startswith("SELECT"):
                fail("query")
            else:
                fail("timeout_setup")
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
        eghis_db.run_readonly_query("mock", query, params=params)
    assert events[-1] == "unlock"
    if failure != "connect":
        assert events[-2] == "close"
    failure = None
    assert eghis_db.run_readonly_query("mock", query, params=params) == (["value"], [(1,)])


@pytest.mark.parametrize("params", [None, ("synthetic",)])
def test_rejected_write_never_connects(monkeypatch, params):
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=lambda *a, **k: pytest.fail("write connected")))
    with pytest.raises(eghis_db.EghisDbQueryRejectedError):
        eghis_db.run_readonly_query("mock", "DELETE FROM orders WHERE id = %s", params=params)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process mutex")
def test_named_mutex_serializes_another_process_without_opening_db():
    import subprocess

    script = (
        "from KaosEghis.core import emr_read_queue as queue\n"
        f"queue._mutex_name = {emr_read_queue._mutex_name!r}\n"
        "with queue._exclusive_reader():\n print('acquired', flush=True)"
    )
    with emr_read_queue._exclusive_reader():
        process = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(0.3)
        assert process.poll() is None
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, stderr
    assert stdout.strip() == "acquired"


@pytest.mark.parametrize("failure", ["raises", "still_open", "missing_close"])
@pytest.mark.parametrize("bound", [False, True])
def test_uncertain_connection_close_blocks_queued_and_future_reads(monkeypatch, failure, bound):
    entered, release = threading.Event(), threading.Event()
    connects = []
    query = "SELECT %s" if bound else "SELECT 1"
    params = (1,) if bound else None

    class Cursor:
        description = [("value",)]
        def execute(self, query, params=None):
            pass
        def fetchall(self):
            return [(1,)]
        def close(self):
            pass

    class Connection:
        closed = False
        def set_session(self, **kwargs):
            pass
        def cursor(self):
            return Cursor()
        def close(self):
            entered.set()
            assert release.wait(3)
            if failure == "raises":
                raise RuntimeError("simulated private driver detail")

    def connect(*_args, **_kwargs):
        connects.append(True)
        connection = Connection()
        if failure == "missing_close":
            connection.close = None
        return connection

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    timings = {}
    with ThreadPoolExecutor(2) as callers:
        first = callers.submit(eghis_db.run_readonly_query, "mock", query, params=params, timings=timings)
        try:
            if failure != "missing_close":
                assert entered.wait(2)
            second = callers.submit(eghis_db.run_readonly_query, "mock", query, params=params)
        finally:
            release.set()
        with pytest.raises(emr_read_queue.EmrConnectionCloseError) as error:
            first.result(3)
        assert "private" not in str(error.value)
        with pytest.raises(emr_read_queue.EmrReadSafetyError):
            second.result(3)
    with pytest.raises(emr_read_queue.EmrReadSafetyError):
        eghis_db.run_readonly_query("mock", query, params=params)
    assert connects == [True]
    assert "connection_closed" not in timings
    if sys.platform == "win32":
        assert len(emr_read_queue._retained_mutexes) == 1


def test_slow_connection_close_keeps_next_reader_waiting(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    live, maximum, connects = [0], [0], []

    class Cursor:
        description = [("value",)]
        def execute(self, query):
            pass
        def fetchall(self):
            return [(1,)]
        def close(self):
            pass

    class Connection:
        closed = False
        def set_session(self, **kwargs):
            pass
        def cursor(self):
            return Cursor()
        def close(self):
            if len(connects) == 1:
                entered.set()
                assert release.wait(3)
            live[0] -= 1
            self.closed = True

    def connect(*_args, **_kwargs):
        live[0] += 1
        maximum[0] = max(maximum[0], live[0])
        connects.append(True)
        return Connection()

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    with ThreadPoolExecutor(2) as callers:
        first = callers.submit(eghis_db.run_readonly_query, "mock", "SELECT 1")
        try:
            assert entered.wait(2)
            second = callers.submit(eghis_db.run_readonly_query, "mock", "SELECT 2")
            deadline = time.monotonic() + 2
            while emr_read_queue._worker._work_queue.qsize() < 1:
                assert time.monotonic() < deadline
                time.sleep(0.005)
            assert len(connects) == live[0] == 1
            assert not first.done() and not second.done()
        finally:
            release.set()
        assert first.result(3) == second.result(3) == (["value"], [(1,)])
    assert maximum == [1] and live == [0]


def test_nested_read_is_rejected_instead_of_deadlocking():
    with pytest.raises(RuntimeError, match="Nested EMR reads"):
        emr_read_queue.run_serialized_read(lambda: emr_read_queue.run_serialized_read(lambda: None))
    assert emr_read_queue.run_serialized_read(lambda: "healthy") == "healthy"


def test_queue_capacity_rejects_without_running_operation(monkeypatch):
    capacity = threading.BoundedSemaphore(1)
    assert capacity.acquire(False)
    monkeypatch.setattr(emr_read_queue, "_capacity", capacity)
    with pytest.raises(RuntimeError, match="queue full"):
        emr_read_queue.run_serialized_read(lambda: pytest.fail("full queue ran operation"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process mutex")
def test_cleanup_failure_keeps_other_process_blocked():
    import subprocess

    def uncertain_cleanup():
        raise emr_read_queue.EmrConnectionCloseError("simulated close failure")

    with pytest.raises(emr_read_queue.EmrConnectionCloseError):
        emr_read_queue.run_serialized_read(uncertain_cleanup)
    script = (
        "from KaosEghis.core import emr_read_queue as queue\n"
        "import win32event\n"
        f"queue._mutex_name = {emr_read_queue._mutex_name!r}\n"
        "original_wait = win32event.WaitForSingleObject\n"
        "win32event.WaitForSingleObject = lambda handle, timeout: original_wait(handle, 100)\n"
        "try:\n"
        " with queue._exclusive_reader():\n  raise AssertionError('unsafe connection slot acquired')\n"
        "except RuntimeError as error:\n print(str(error), flush=True)\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                            text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr
    assert "queue busy; no connection opened" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Windows abandoned mutex")
def test_abandoned_mutex_blocks_without_running_operation():
    import subprocess
    import win32api
    import win32event

    observer = win32event.CreateMutex(None, False, emr_read_queue._mutex_name)
    try:
        script = (
            "import win32event\n"
            f"handle = win32event.CreateMutex(None, False, {emr_read_queue._mutex_name!r})\n"
            "assert win32event.WaitForSingleObject(handle, 1000) == win32event.WAIT_OBJECT_0\n"
            "print('owned', flush=True)\n"
        )
        result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "owned"
        with pytest.raises(emr_read_queue.EmrReadSafetyError, match="Previous EMR reader"):
            emr_read_queue.run_serialized_read(lambda: pytest.fail("abandoned lock ran read"))
        assert emr_read_queue._unhealthy.is_set()
    finally:
        win32api.CloseHandle(observer)


@pytest.mark.parametrize("consumer", ["pacs", "flu", "context", "health"])
def test_existing_consumers_finish_source_cleanup_before_returning(monkeypatch, consumer):
    from KaosEghis.core import pacs_polling, weekly_age_reporting, kaospacs_patient_context
    from KaosEghis.ui.plugins.pacs_panel import PacsPanel

    settings = {"eghis_db_connection_string": "mock"}
    events = []
    columns, rows = {
        "pacs": (["patient_id", "order_name"], [("TEST", "Test image")]),
        "flu": (["age_group", "visit_count", "patient_count"], [("19-49", 1, 1)]),
        "context": (["patient_name", "patient_birth_date", "patient_sex"], [("Test", "19900101", "M")]),
        "health": (["value"], [(1,)]),
    }[consumer]

    class Cursor:
        description = [(name,) for name in columns]
        def execute(self, query):
            events.append("execute")
        def fetchall(self):
            return rows
        def close(self):
            events.append("cursor_closed")

    class Connection:
        closed = False
        def set_session(self, **options):
            assert options == {"readonly": True, "autocommit": True}
        def cursor(self):
            return Cursor()
        def close(self):
            self.closed = True
            events.append("connection_closed")

    def connect(*args, **kwargs):
        assert threading.current_thread().name.startswith("KaosEghis-emr")
        events.append("connect")
        return Connection()

    def require_closed(original):
        def map_result(*args, **kwargs):
            assert events[-1] == "connection_closed"
            return original(*args, **kwargs)
        return map_result

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    if consumer == "pacs":
        monkeypatch.setattr(pacs_polling, "_map_db_row_to_order", require_closed(pacs_polling._map_db_row_to_order))
        assert pacs_polling.poll_image_orders(settings)
    elif consumer == "flu":
        monkeypatch.setattr(weekly_age_reporting, "_map_weekly_age_row", require_closed(weekly_age_reporting._map_weekly_age_row))
        assert weekly_age_reporting.fetch_weekly_age_report(settings, year=2026, start_week=1)
    elif consumer == "context":
        monkeypatch.setattr(kaospacs_patient_context, "_normalize_text", require_closed(kaospacs_patient_context._normalize_text))
        assert kaospacs_patient_context.get_patient_context(settings, "TEST")
    else:
        panel = SimpleNamespace(
            eghis_db_status=SimpleNamespace(setText=lambda _text: None),
            _emit_health_state=require_closed(lambda: None),
        )
        PacsPanel._refresh_eghis_db_status(panel, settings)
        assert panel._eghis_db_available
    assert events.count("connect") == 1
    assert events[-2:] == ["cursor_closed", "connection_closed"]


def test_postgres_driver_is_only_imported_at_shared_connection_boundary():
    import ast
    from pathlib import Path

    package = Path(__file__).resolve().parents[1] / "KaosEghis"
    drivers = {"psycopg2", "psycopg", "pg8000", "pyodbc", "sqlalchemy"}
    users = set()
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                       else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            if any(name.split(".")[0] in drivers for name in modules):
                users.add(path.relative_to(package).as_posix())
    assert users == {"core/eghis_db.py"}


@pytest.fixture
def parameter_db(monkeypatch):
    state = SimpleNamespace(
        events=[], connections=[], query_error=None, query_errors={}, block_first=False,
        entered=threading.Event(), release=threading.Event(), live=0, maximum=0,
    )

    class Cursor:
        description = [("value",)]

        def __init__(self, number):
            self.number = number

        def execute(self, *args):
            state.events.append((self.number, "execute", args))
            if args[0].startswith("SELECT"):
                if state.block_first and self.number == 1:
                    state.entered.set()
                    assert state.release.wait(5)
                error = state.query_errors.get(self.number, state.query_error)
                if error is not None:
                    raise error

        def fetchall(self):
            return [(self.number,)]

        def close(self):
            state.events.append((self.number, "cursor_closed"))

    class Connection:
        closed = False

        def __init__(self, number):
            self.number = number

        def set_session(self, **options):
            assert options == {"readonly": True, "autocommit": True}

        def cursor(self):
            return Cursor(self.number)

        def close(self):
            self.closed = True
            state.live -= 1
            state.events.append((self.number, "connection_closed"))

    def connect(_connection_string, **options):
        assert options["connect_timeout"] == 5
        assert threading.current_thread().name.startswith("KaosEghis-emr")
        number = len(state.connections) + 1
        connection = Connection(number)
        state.connections.append(connection)
        state.live += 1
        state.maximum = max(state.maximum, state.live)
        state.events.append((number, "connected"))
        return connection

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    return state


@pytest.mark.parametrize("query, params, expected", [
    ("SELECT '100% synthetic'", None, None),
    ("SELECT 1", (), ()),
    ("SELECT 1", [], ()),
    ("SELECT 1", {}, {}),
    ("SELECT %s, %s, %s, %s, %s",
     (date(2026, 10, 1), Decimal("1.25"), None, True, b"test"),
     (date(2026, 10, 1), Decimal("1.25"), None, True, b"test")),
    ("SELECT %s", ["quote'; DELETE FROM synthetic_orders; -- 100%"],
     ("quote'; DELETE FROM synthetic_orders; -- 100%",)),
    ("SELECT %(day)s, %(codes)s", MappingProxyType({"day": date(2026, 10, 1), "codes": ["TEST"]}),
     {"day": date(2026, 10, 1), "codes": ["TEST"]}),
])
def test_parameters_reach_driver_separately_and_results_follow_close(parameter_db, query, params, expected):
    timings = {}
    assert eghis_db.run_readonly_query("mock", query, params=params, timings=timings) == (["value"], [(1,)])
    expected_args = (query,) if expected is None else (query, expected)
    assert parameter_db.events == [
        (1, "connected"),
        (1, "execute", ("SET statement_timeout = 5000",)),
        (1, "execute", expected_args),
        (1, "cursor_closed"),
        (1, "connection_closed"),
    ]
    assert parameter_db.connections[0].closed
    assert parameter_db.live == 0
    assert "connection_closed" in timings
    assert all(isinstance(value, float) for value in timings.values())


@pytest.mark.parametrize("params", ["private synthetic value", b"private", 1, {1, 2}, iter([1])])
def test_invalid_parameter_container_never_enters_queue(monkeypatch, params):
    monkeypatch.setattr(eghis_db, "run_serialized_read", lambda *_a: pytest.fail("invalid parameters queued"))
    with pytest.raises(TypeError, match="tuple, list, or mapping") as error:
        eghis_db.run_readonly_query("mock", "SELECT %s", params=params)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("named", [False, True])
def test_queued_parameters_are_a_detached_snapshot(parameter_db, named):
    parameter_db.block_first = True
    params = {"day": date(2026, 10, 1), "codes": ["TEST"]} if named else [date(2026, 10, 1), ["TEST"]]
    expected = {"day": date(2026, 10, 1), "codes": ["TEST"]} if named else (date(2026, 10, 1), ["TEST"])
    query = "SELECT %(day)s, %(codes)s" if named else "SELECT %s, %s"
    with ThreadPoolExecutor(2) as callers:
        first = callers.submit(eghis_db.run_readonly_query, "mock", "SELECT 1")
        try:
            assert parameter_db.entered.wait(2)
            second = callers.submit(eghis_db.run_readonly_query, "mock", query, params=params)
            deadline = time.monotonic() + 2
            while emr_read_queue._worker._work_queue.qsize() < 1:
                assert time.monotonic() < deadline
                time.sleep(0.005)
            if named:
                params["codes"].append("CHANGED")
                params["day"] = date(2026, 10, 2)
            else:
                params[1].append("CHANGED")
                params[0] = date(2026, 10, 2)
            assert len(parameter_db.connections) == 1
            assert not second.done()
        finally:
            parameter_db.release.set()
        assert first.result(3) == (["value"], [(1,)])
        assert second.result(3) == (["value"], [(2,)])
    assert (2, "execute", (query, expected)) in parameter_db.events
    assert parameter_db.events.index((1, "connection_closed")) < parameter_db.events.index((2, "connected"))
    assert parameter_db.maximum == 1 and parameter_db.live == 0


@pytest.mark.parametrize("failure", ["adaptation", "timeout"])
def test_bound_execute_errors_close_without_retry_and_leave_reader_usable(parameter_db, failure):
    class QueryCancelled(RuntimeError):
        pgcode = "57014"

    error = TypeError("synthetic adaptation failure") if failure == "adaptation" else QueryCancelled("synthetic timeout")
    parameter_db.query_error = error
    timings = {}
    with pytest.raises(type(error)) as caught:
        eghis_db.run_readonly_query("mock", "SELECT %s", params=("TEST",), timings=timings)
    assert caught.value is error
    assert len(parameter_db.connections) == 1
    assert parameter_db.connections[0].closed
    assert parameter_db.events[-2:] == [(1, "cursor_closed"), (1, "connection_closed")]
    assert "connection_closed" in timings and "query_finished" not in timings
    parameter_db.query_error = None
    assert eghis_db.run_readonly_query("mock", "SELECT %s", params=("NEXT",)) == (["value"], [(2,)])
    assert parameter_db.maximum == 1 and parameter_db.live == 0


@pytest.mark.parametrize("failure", [RuntimeError, TimeoutError])
def test_failed_flu_read_closes_before_queued_orders_health_and_pacs(parameter_db, failure):
    parameter_db.block_first = True
    parameter_db.query_errors[1] = failure("synthetic read failure")
    consumers = ("TEST_FLU", "TEST_KAOSORDERS", "TEST_HEALTH", "TEST_PACS")
    timings = [{} for _ in consumers]
    with ThreadPoolExecutor(len(consumers)) as callers:
        futures = []
        try:
            for index, consumer in enumerate(consumers):
                futures.append(callers.submit(
                    eghis_db.run_readonly_query, "mock", "SELECT %s",
                    params=(consumer,), timings=timings[index],
                ))
                if index == 0:
                    assert parameter_db.entered.wait(2)
                else:
                    deadline = time.monotonic() + 2
                    while emr_read_queue._worker._work_queue.qsize() < index:
                        assert time.monotonic() < deadline
                        time.sleep(0.005)
            assert len(parameter_db.connections) == 1
            assert all(not future.done() for future in futures)
        finally:
            parameter_db.release.set()
        with pytest.raises(failure, match="synthetic read failure"):
            futures[0].result(5)
        for number, future in enumerate(futures[1:], start=2):
            assert future.result(5) == (["value"], [(number,)])

    for number, consumer in enumerate(consumers, start=1):
        assert (number, "execute", ("SELECT %s", (consumer,))) in parameter_db.events
        closed = parameter_db.events.index((number, "connection_closed"))
        assert parameter_db.events.index((number, "cursor_closed")) < closed
        if number < len(consumers):
            assert closed < parameter_db.events.index((number + 1, "connected"))
    assert all(connection.closed for connection in parameter_db.connections)
    assert all("connection_closed" in stages for stages in timings)
    assert parameter_db.maximum == 1 and parameter_db.live == 0
