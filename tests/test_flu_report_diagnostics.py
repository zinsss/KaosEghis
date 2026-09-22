import json

from KaosEghis.core.flu_report_diagnostics import write_flu_report_diagnostic


def test_flu_diagnostics_only_include_timings_and_safe_metadata(tmp_path):
    path = tmp_path / "flu-report.jsonl"
    write_flu_report_diagnostic(
        path, year=2026, week=38, outcome="loaded", elapsed_seconds=0.12345,
        stages={"connected": 0.1, "connection_closed": 0.12, "sql": "private data"},
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["stages_seconds"] == {"connected": 0.1, "connection_closed": 0.12}
    assert record["elapsed_seconds"] == 0.1235
    assert record["outcome"] == "loaded"
    assert "private" not in path.read_text(encoding="utf-8")
    path.unlink()  # The diagnostic file handle must not be held open.


def test_flu_diagnostics_rotate_and_do_not_record_raw_error_text(tmp_path):
    path = tmp_path / "flu-report.jsonl"
    path.write_text("x" * 65536, encoding="utf-8")
    write_flu_report_diagnostic(
        path, year=2026, week=38, outcome="secret exception", elapsed_seconds=3, stages={},
    )
    assert (tmp_path / "flu-report.jsonl.1").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["outcome"] == "error"
    assert path.stat().st_size < 1024


def test_missing_diagnostics_directory_does_not_break_report(tmp_path):
    write_flu_report_diagnostic(
        tmp_path / "missing" / "flu-report.jsonl", year=2026, week=38,
        outcome="timeout", elapsed_seconds=3, stages={},
    )
