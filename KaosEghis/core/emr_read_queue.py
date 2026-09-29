"""One FIFO worker for all Kaos-managed EMR reads; no connections are pooled."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import sys
import threading


_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="KaosEghis-emr")
_capacity = threading.BoundedSemaphore(64)


@contextmanager
def _exclusive_reader():
    # The service/API and tools can run in separate processes. Keep their
    # physical connections exclusive too, including elevated instances.
    if sys.platform != "win32":
        yield
        return
    import win32api
    import win32event

    handle = win32event.CreateMutex(None, False, "Global\\KaosEghis-EMR-read")
    acquired = False
    try:
        result = win32event.WaitForSingleObject(handle, 60000)
        acquired = result in (win32event.WAIT_OBJECT_0, win32event.WAIT_ABANDONED)
        if not acquired:
            raise RuntimeError("EMR read queue busy; no connection opened.")
        yield
    finally:
        if acquired:
            win32event.ReleaseMutex(handle)
        win32api.CloseHandle(handle)


def run_serialized_read(operation):
    if not _capacity.acquire(blocking=False):
        raise RuntimeError("EMR read queue full; no connection opened.")

    def run():
        with _exclusive_reader():
            return operation()

    try:
        return _worker.submit(run).result()
    finally:
        _capacity.release()
