import ast
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from KaosEghis.core import reception_current_day_patients as source


DAY = date(2026, 10, 7)
NOW = datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc)  # 10:00 Asia/Seoul


def row(identifier="synthetic-2", *, name="Synthetic Patient", code="30", day=DAY):
    return source.build_synthetic_source_row(
        {
            "clinic_ymd": day,
            "recept_no": identifier,
            "ptnt_nm": name,
            "proc_gb": code,
        },
        synthetic_fixture=True,
    )


def read(*rows, day=DAY, observed_at=NOW - timedelta(seconds=5), **changes):
    values = {
        "clinic_day": day,
        "observed_at": observed_at,
        "status": source.SourceReadStatus.COMPLETE,
        "rows": tuple(rows),
        "whole_day": True,
        "untruncated": True,
        "consistent_snapshot": True,
        "connection_closed": True,
    }
    values.update(changes)
    return source.SyntheticReceptionDayRead(**values, synthetic_fixture=True)


def project(candidate, *, now=NOW, freshness=timedelta(seconds=30)):
    return source.project_synthetic_current_day(
        candidate,
        now=now,
        freshness_limit=freshness,
        synthetic_fixture=True,
    )


def test_exact_source_fields_and_literal_status_contract():
    assert source.CLINIC_TIME_ZONE_NAME == "Asia/Seoul"
    assert source.PROVIDER_ID == "eghis.reception-current-day-patients"
    assert source.PROJECTION_ID == "reception-current-day-patients-v1"
    assert source.SOURCE_STATUS_MAPPING == (
        ("10", None),
        ("25", None),
        ("30", source.IncludedPatientState.CONSULTATION_COMPLETED),
        ("40", source.IncludedPatientState.PAYMENT_COMPLETED),
    )
    assert [item.name for item in fields(row())] == [
        "clinic_day", "selection_id", "display_name", "source_status_code"
    ]


def test_only_consultation_and_payment_completed_are_included():
    result = project(read(
        row("synthetic-10", code="10"),
        row("synthetic-25", code="25"),
        row("synthetic-30", code="30"),
        row("synthetic-40", code="40"),
        row("synthetic-50", code="50"),
        row("synthetic-new", code="UNREVIEWED"),
        row("synthetic-null", code=None),
        row("synthetic-blank", code=""),
        row("synthetic-padded", code=" 30 "),
    ))
    assert [(item.selection_id, item.state.value) for item in result.patients] == [
        ("synthetic-30", "CONSULTATION_COMPLETED"),
        ("synthetic-40", "PAYMENT_COMPLETED"),
    ]


def test_current_day_is_resolved_in_clinic_timezone_not_utc_date():
    before_utc_midnight = datetime(2026, 10, 6, 23, 59, 59, tzinfo=timezone.utc)
    result = project(
        read(row(), observed_at=before_utc_midnight),
        now=datetime(2026, 10, 7, 0, 0, 5, tzinfo=timezone.utc),
        freshness=timedelta(seconds=10),
    )
    assert result.clinic_day == DAY
    with pytest.raises(source.CurrentDayPatientsRejected, match="^not_current_clinic_day$"):
        project(read(row(day=date(2026, 10, 6)), day=date(2026, 10, 6)))


def test_freshness_is_explicit_and_stale_or_future_reads_fail_closed():
    assert project(read(row()), freshness=timedelta(seconds=5)).patients
    with pytest.raises(source.CurrentDayPatientsRejected, match="^stale_read$"):
        project(read(row()), freshness=timedelta(seconds=4))
    with pytest.raises(source.CurrentDayPatientsRejected, match="^future_observation$"):
        project(read(row(), observed_at=NOW + timedelta(microseconds=1)))
    for invalid in (timedelta(0), timedelta(seconds=-1), 30, None):
        with pytest.raises(source.CurrentDayPatientsRejected, match="^invalid_freshness$"):
            project(read(row()), freshness=invalid)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": source.SourceReadStatus.PARTIAL},
        {"status": source.SourceReadStatus.FAILED},
        {"status": source.SourceReadStatus.UNAVAILABLE},
        {"whole_day": False},
        {"untruncated": False},
        {"consistent_snapshot": False},
        {"connection_closed": False},
    ],
)
def test_only_complete_detached_reads_have_selection_authority(changes):
    with pytest.raises(source.CurrentDayPatientsRejected, match="^incomplete_read$"):
        project(read(row(), **changes))


def test_identity_order_and_dedup_do_not_depend_on_patient_name():
    later = row("synthetic-20", name="Alpha", code="40")
    earlier = row("synthetic-10", name="Zulu", code="30")
    result = project(read(later, earlier, earlier))
    assert [item.selection_id for item in result.patients] == ["synthetic-10", "synthetic-20"]
    assert [item.display_name for item in result.patients] == ["Zulu", "Alpha"]
    assert [item.name for item in fields(result.patients[0])] == [
        "selection_id", "display_name", "state"
    ]


@pytest.mark.parametrize("change", [{"name": "Other"}, {"code": "40"}])
def test_same_selection_identity_with_conflicting_facts_rejects_whole_read(change):
    original = row("synthetic-1")
    conflicting = row("synthetic-1", **change)
    with pytest.raises(source.CurrentDayPatientsRejected, match="^conflicting_duplicate$"):
        project(read(original, conflicting))


@pytest.mark.parametrize("missing_or_extra", ["missing", "extra"])
def test_source_alias_boundary_is_closed(missing_or_extra):
    values = {
        "clinic_ymd": DAY,
        "recept_no": "synthetic-1",
        "ptnt_nm": "Synthetic Patient",
        "proc_gb": "30",
    }
    if missing_or_extra == "missing":
        values.pop("ptnt_nm")
    else:
        values["chart_number"] = "FORBIDDEN"
    with pytest.raises(source.CurrentDayPatientsRejected, match="^invalid_fields$"):
        source.build_synthetic_source_row(values, synthetic_fixture=True)


def test_models_and_failures_are_redacted_and_not_persistable():
    item = row()
    result = project(read(item))
    assert repr(item) == "<SyntheticReceptionRow: redacted>"
    assert repr(result.patients[0]) == "<CurrentDayPatient: redacted>"
    with pytest.raises(source.CurrentDayPatientsRejected) as error:
        project(read(row(name="PRIVATE MARKER")), freshness=timedelta(seconds=4))
    assert str(error.value) == "stale_read" and "PRIVATE" not in repr(error.value)

    tree = ast.parse(Path(source.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imports.intersection(
        {"psycopg2", "sqlite3", "requests", "httpx", "logging", "pathlib"}
    )
    assert not any(
        name in Path(source.__file__).read_text(encoding="utf-8")
        for name in ("run_readonly_query", "eghis_db_connection_string", "open(", "print(")
    )


def test_synthetic_permission_and_row_bounds_are_explicit(monkeypatch):
    with pytest.raises(source.CurrentDayPatientsRejected, match="^synthetic_fixture_required$"):
        source.build_synthetic_source_row({})
    with pytest.raises(source.CurrentDayPatientsRejected, match="^synthetic_fixture_required$"):
        source.project_synthetic_current_day(read(), now=NOW, freshness_limit=timedelta(seconds=1))
    monkeypatch.setattr(source, "MAX_ROWS", 0)
    with pytest.raises(source.CurrentDayPatientsRejected, match="^invalid_row_bound$"):
        read(row())
