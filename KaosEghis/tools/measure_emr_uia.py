"""Bounded, read-only UIA timing probe. Never reads or records patient text."""

import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time


TARGET_IDS = (
    "H2OpdTreatment", "grdSymp", "tree\ucc98\ubc29", "tree\uc0c1\ubcd1",
    "grdOpdList", "txt\ud658\uc790\ubc88\ud638",
)
CHART_ID = "txt\ud658\uc790\ubc88\ud638"
PATIENT_IDS = (
    CHART_ID, "txt\uc8fc\ubbfc\ubc88\ud638", "txt\ud658\uc790\uba85", "lblSexAge", "txtSexAge",
    "dateEdit1", "txt\ud734\ub300\ud3f0", "txt\uc804\ud654", "txt\uc8fc\uc18c",
)


def measure_window(handle, pid, finder):
    started = time.perf_counter()
    matches = finder(TARGET_IDS, root_handle=handle, process_ids=(pid,))
    return {
        "window_handle": handle,
        "process_id": pid,
        "lookup_ms": round((time.perf_counter() - started) * 1000, 1),
        "counts": {key: len(matches.get(key, [])) for key in TARGET_IDS},
    }


def measure_patient_window(handle, pid, finder):
    from pywinauto import Desktop
    from KaosEghis.core.vaccine_patient_context import _nearest_patient_information_scope
    from KaosEghis.core.vaccine_patient_control_cache import PatientControlCache

    started = time.perf_counter()
    charts = finder((CHART_ID,), root_handle=handle, process_ids=(pid,)).get(CHART_ID, [])
    report = {
        "window_handle": handle, "process_id": pid,
        "chart_discovery_ms": round((time.perf_counter() - started) * 1000, 1),
        "chart_matches": len(charts),
    }
    candidates = []
    for chart in charts:
        if chart.is_visible():
            scope = _nearest_patient_information_scope(chart)
            if scope is not None:
                candidates.append((chart, scope))
    if len(candidates) != 1:
        report["patient_scope"] = "missing_or_ambiguous"
        return report
    chart, scope = candidates[0]
    selectors = {"chart_no": (CHART_ID,)}
    selectors.update({key: (key,) for key in PATIENT_IDS if key != CHART_ID})
    desktop = Desktop(backend="uia")
    samples = []
    cache = None
    for trial in range(1, 4):
        started = time.perf_counter()
        matches = finder(PATIENT_IDS, root_element=scope, process_ids=(pid,))
        sample = {
            "trial": trial,
            "scoped_lookup_ms": round((time.perf_counter() - started) * 1000, 1),
            "counts": {key: len(matches.get(key, [])) for key in PATIENT_IDS},
        }
        if cache is None:
            controls = {key: items[0] for key, items in matches.items() if len(items) == 1}
            controls[CHART_ID] = chart
            started = time.perf_counter()
            cache = PatientControlCache.create(pid, handle, scope, controls, selectors)
            sample["cache_creation_ms"] = round((time.perf_counter() - started) * 1000, 1)
        sample["cache_created"] = cache is not None
        if cache is not None:
            started = time.perf_counter()
            resolved = cache.resolve(desktop, pid, handle, selectors)
            sample["cache_validation_ms"] = round((time.perf_counter() - started) * 1000, 1)
            sample["cache_valid"] = resolved is not None
            sample["cached_control_count"] = len(resolved[1]) if resolved is not None else 0
        samples.append(sample)
    report["patient_scope"] = "unique"
    report["samples"] = samples
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--patient-info", action="store_true")
    args = parser.parse_args()
    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "elevated": bool(ctypes.windll.shell32.IsUserAnAdmin()),
        "status": "starting", "measurements": [],
    }
    lock = threading.Lock()

    def save():
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def timeout():
        try:
            with lock:
                report["status"] = "timeout"
                save()
        finally:
            os._exit(2)  # Stop only this diagnostic, including a blocked UIA call.

    watchdog = threading.Timer(30, timeout)
    watchdog.daemon = True
    watchdog.start()
    try:
        save()
        import psutil
        import win32gui
        import win32process
        from KaosEghis.core.uia_fast_lookup import find_uia_elements_by_automation_ids
        from KaosEghis.core.vaccine_patient_context import _visible_process_window_handles

        processes = {
            process.pid for process in psutil.process_iter(["pid", "name"])
            if str(process.info["name"] or "").casefold() in {"eghis.exe", "eghis.forms.exe"}
        }
        handles = [
            handle for handle in _visible_process_window_handles(tuple(processes))
            if not win32gui.IsIconic(handle)
        ][:4]
        for trial in range(1, 2 if args.patient_info else 4):
            for handle in handles:
                pid = win32process.GetWindowThreadProcessId(handle)[1]
                if pid not in processes:
                    continue
                measure = measure_patient_window if args.patient_info else measure_window
                measurement = measure(handle, pid, find_uia_elements_by_automation_ids)
                with lock:
                    report["measurements"].append({"trial": trial, **measurement})
                    report["status"] = "running"
                    save()
            time.sleep(0.5)
        with lock:
            report["status"] = "complete" if handles else "no_visible_emr"
            save()
    except Exception as error:
        with lock:
            report["status"] = "failed"
            report["error_type"] = type(error).__name__
            save()
    finally:
        watchdog.cancel()


if __name__ == "__main__":
    main()
