"""Explicit supervised UI/DB status comparison; never enable production mappings."""

import argparse
from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

from KaosEghis.core.eghis_db import run_readonly_query
from KaosEghis.tools.inspect_reception_status import inspect_ui, safe_header


LABELS = {"hold": "\ubcf4\ub958", "closed": "\uc644\ub8cc", "cancelled": "\ucde8\uc18c", "waiting": "\uc9c4\ub8cc\ub300\uae30"}
CHART_HEADER = "\ud658\uc790\ubc88\ud638"


class ComparisonStopped(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class UiSample:
    owner: tuple
    charts: tuple[str, ...]

    def __repr__(self):
        return "<UiSample: redacted>"


def read_chart_sample(root, tabs, grids, expected_label):
    selected = [item["status"] for item in tabs if item["selected"] is True and item["visible"]]
    if selected != [expected_label] or len(grids) != 1:
        raise ComparisonStopped("unexpected_ui_selection")
    deadline = time.monotonic() + 5
    panels = [child for child in grids[0].children()
              if child.element_info.control_type == "Custom" and child.element_info.name == "Data Panel"]
    if len(panels) != 1:
        raise ComparisonStopped("data_panel_not_unique")
    rows = [child for child in panels[0].children()
            if child.element_info.control_type == "ListItem" and child.is_visible()]
    charts = []
    for row in rows[:5]:
        if time.monotonic() >= deadline:
            raise ComparisonStopped("ui_sample_timed_out")
        cells = [child for child in row.children()
                 if child.element_info.control_type == "DataItem"
                 and safe_header(child.element_info.name or "") == CHART_HEADER]
        if len(cells) != 1:
            raise ComparisonStopped("chart_cell_not_unique")
        try:
            value = cells[0].iface_value.CurrentValue
        except Exception:
            try:
                value = cells[0].legacy_properties().get("Value")
            except Exception:
                raise ComparisonStopped("chart_value_unavailable") from None
        if not isinstance(value, str) or re.fullmatch(r"[0-9]{1,20}", value.strip()) is None:
            raise ComparisonStopped("chart_value_not_numeric")
        charts.append(value.strip())
    if not charts or len(charts) != len(set(charts)):
        raise ComparisonStopped("empty_or_duplicate_ui_sample")
    info = root.element_info
    return UiSample((info.process_id, tuple(info.runtime_id)), tuple(charts))


def build_status_query(clinic_day, charts):
    if type(clinic_day) is not date or not 1 <= len(charts) <= 5 or len(set(charts)) != len(charts):
        raise ComparisonStopped("invalid_sample")
    if any(not isinstance(value, str) or re.fullmatch(r"[0-9]{1,20}", value) is None for value in charts):
        raise ComparisonStopped("invalid_sample")
    # Legacy diagnostic: only validated ASCII digits and a parsed date enter SQL.
    # This is not the parameterized production day-reader contract.
    literals = ",".join("'" + value + "'" for value in charts)
    return f"""WITH matched AS (
      SELECT ptnt_no, proc_gb, hold_yn, hold_opd FROM public.h1opdin
      WHERE clinic_ymd = '{clinic_day:%Y%m%d}' AND ptnt_no IN ({literals})
    ) SELECT proc_gb, hold_yn, hold_opd, COUNT(*),
        (SELECT COUNT(*) FROM matched), (SELECT COUNT(DISTINCT ptnt_no) FROM matched)
      FROM matched GROUP BY proc_gb, hold_yn, hold_opd LIMIT 21"""


def summarize_states(rows, sample_size):
    if not rows or len(rows) > sample_size:
        raise ComparisonStopped("no_unambiguous_day_match")
    result = []
    for row in rows:
        if len(row) != 6 or row[4] != sample_size or row[5] != sample_size:
            raise ComparisonStopped("no_unambiguous_day_match")
        if type(row[3]) is not int or not 1 <= row[3] <= sample_size:
            raise ComparisonStopped("invalid_count")
        codes = []
        for value in row[:3]:
            if value is None:
                codes.append(None)
            elif isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{0,10}", value.strip()):
                codes.append(value.strip())
            else:
                raise ComparisonStopped("unexpected_status_format")
        result.append(dict(zip(("proc_gb", "hold_yn", "hold_opd", "count"), (*codes, row[3]))))
    if sum(item["count"] for item in result) != sample_size:
        raise ComparisonStopped("invalid_count")
    return result


def compare_samples(before, after, clinic_day, rows):
    if before != after:
        raise ComparisonStopped("ui_changed_sample_discarded")
    return {"status": "observed_not_enabled", "operator_confirmed_day": clinic_day.isoformat(),
            "sample_size": len(before.charts), "source_states": summarize_states(rows, len(before.charts)),
            "actions_sent": 0, "production_mapping_enabled": False}


def connection_setting():
    folder = Path(os.environ.get("KAOSEGHIS_DATA_DIR") or Path(os.environ["LOCALAPPDATA"]) / "KaosEghis")
    connection = sqlite3.connect((folder / "KaosEghis.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        row = connection.execute("SELECT value FROM app_settings WHERE key = ?", ("eghis_db_connection_string",)).fetchone()
        if not row or not row[0].strip():
            raise ComparisonStopped("source_not_configured")
        return row[0]
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--point", nargs=2, type=int, required=True)
    parser.add_argument("--clinic-day", type=date.fromisoformat, required=True)
    parser.add_argument("--state", choices=LABELS, required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists() or not output.parent.is_dir():
        raise SystemExit("Output must be a new file in an existing directory")

    def finish(report):
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False)

    # Guard UI calls only. Never terminate while the shared reader may own a
    # source connection; synchronize cancellation to prevent a timer race.
    gate = threading.Lock()
    phase = {"ui": False}

    def capture(wait):
        def timeout():
            with gate:
                if phase["ui"]:
                    finish({"status": "ui_read_timeout", "actions_sent": 0})
                    os._exit(2)
        with gate:
            phase["ui"] = True
        timer = threading.Timer(wait + 25, timeout)
        timer.daemon = True
        timer.start()
        samples = []
        try:
            report = inspect_ui(args.point, wait, observer=lambda root, tabs, grids:
                                samples.append(read_chart_sample(root, tabs, grids, LABELS[args.state])))
            if report["status"] != "passive_ui_read_complete" or len(samples) != 1:
                raise ComparisonStopped("ui_sample_unavailable")
            return samples[0]
        finally:
            with gate:
                phase["ui"] = False
                timer.cancel()
            timer.join()

    try:
        before = capture(60)
        timing = {}
        _, rows = run_readonly_query(connection_setting(), build_status_query(args.clinic_day, before.charts),
                                    connect_timeout_seconds=3, statement_timeout_seconds=2,
                                    application_name="KaosEghis-status-comparison", timings=timing)
        after = capture(0)
        result = compare_samples(before, after, args.clinic_day, rows)
        result.update(ui_list=LABELS[args.state], source_connection_closed="connection_closed" in timing,
                      source_seconds=timing.get("connection_closed"))
    except ComparisonStopped as exc:
        result = {"status": "stopped", "reason": str(exc), "actions_sent": 0}
    except Exception as exc:
        result = {"status": "stopped", "exception_type": type(exc).__name__, "actions_sent": 0}
    finish(result)


if __name__ == "__main__":
    main()
