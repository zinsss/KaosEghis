"""One FIFO worker for all Kaos-managed EMR reads; no connections are pooled."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import sys
import threading


_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="KaosEghis-emr")
_capacity = threading.BoundedSemaphore(64)
_mutex_name = "Global\\KaosEghis-EMR-read"
_unhealthy = threading.Event()
_worker_state = threading.local()
_retained_mutexes = []


class EmrReadSafetyError(RuntimeError):
    """Further reads are unsafe until uncertain connection ownership is resolved."""


class EmrConnectionCloseError(EmrReadSafetyError):
    """The source connection could not be confirmed closed."""


def _check_health():
    if _unhealthy.is_set():
        raise EmrReadSafetyError(
            "EMR reader stopped after uncertain connection cleanup. "
            "Operator recovery is required; no new connection opened."
        )


@contextmanager
def _exclusive_reader():
    # The service/API and tools can run in separate processes. Keep their
    # physical connections exclusive too, including elevated instances.
    if sys.platform != "win32":
        yield
        return
    import win32api
    import win32event

    handle = win32event.CreateMutex(None, False, _mutex_name)
    acquired = False
    retained = False
    try:
        result = win32event.WaitForSingleObject(handle, 60000)
        acquired = result in (win32event.WAIT_OBJECT_0, win32event.WAIT_ABANDONED)
        if not acquired:
            raise RuntimeError("EMR read queue busy; no connection opened.")
        if result == win32event.WAIT_ABANDONED:
            raise EmrReadSafetyError(
                "Previous EMR reader exited without releasing connection ownership. "
                "Operator recovery is required; no new connection opened."
            )
        yield
    except EmrReadSafetyError:
        _unhealthy.set()
        if acquired:
            # Keep ownership on this worker thread, including against other
            # processes. Releasing here could overlap an unclosed connection.
            _retained_mutexes.append(handle)
            retained = True
        raise
    finally:
        if not retained:
            try:
                if acquired:
                    win32event.ReleaseMutex(handle)
            finally:
                win32api.CloseHandle(handle)


def run_serialized_read(operation):
    _check_health()
    if getattr(_worker_state, "running", False):
        raise RuntimeError("Nested EMR reads are not allowed; no connection opened.")
    capacity = _capacity
    if not capacity.acquire(blocking=False):
        raise RuntimeError("EMR read queue full; no connection opened.")

    def run():
        _worker_state.running = True
        try:
            _check_health()
            with _exclusive_reader():
                _check_health()
                return operation()
        except EmrReadSafetyError:
            _unhealthy.set()
            raise
        finally:
            _worker_state.running = False

    try:
        future = _worker.submit(run)
    except BaseException:
        capacity.release()
        raise
    future.add_done_callback(lambda _future: capacity.release())
    return future.result()
