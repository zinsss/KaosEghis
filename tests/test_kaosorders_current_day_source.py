from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from KaosEghis.core import kaosorders_current_day_source as source


DAY = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 12, tzinfo=source.KST)


def test_windows_timezone_dependency_is_declared():
    root = Path(__file__).resolve().parents[1]
    requirement = 'tzdata>=2024.1; sys_platform == "win32"'
    package_requirement = "tzdata>=2024.1; sys_platform == 'win32'"
    assert requirement in (root / "requirements.txt").read_text(encoding="utf-8")
    assert package_requirement in (root / "pyproject.toml").read_text(encoding="utf-8")


def row(**changes):
    values = dict(zip(source.FIELDS, (
        "DATA", "candidate_rows", NOW, True, 1, 1, 0, 1, "20261012",
        "SYNTHETIC-E1", "10", "N", True, "SYNTHETIC-E1", "20261012", 1, 2,
        "SYNTHETIC-C", "Synthetic catalog", "SYNTHETIC-U", "Synthetic order",
        Decimal("1.250"), Decimal("3.00"), None, "SYNTHETIC-T", "SYNTHETIC-D",
        "N", "N",
    )))
    values.update(changes)
    return tuple(values[name] for name in source.FIELDS)


def batch(rows):
    return source._DetachedRows(source.FIELDS, rows, len(rows))


def empty_row():
    changes = {name: None for name in source.FIELDS[8:]}
    changes.update(row_kind="META", order_present=False, encounter_count=0, order_count=0,
                   no_order_encounter_count=0, expected_result_rows=1)
    return row(**changes)


def test_default_off_does_not_touch_settings(tmp_path):
    missing = tmp_path / "missing.sqlite"
    result = source.read_current_day_orders(missing, clinic_day=DAY, now=lambda: NOW)
    assert result.status == "disabled" and result.snapshot is None
    assert not missing.exists()


def test_settings_are_read_through_sqlite_read_only_uri(tmp_path):
    path = tmp_path / "settings.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO app_settings VALUES (?, ?)",
                       ("eghis_db_connection_string", "  postgresql://synthetic  "))
    connection.commit()
    connection.close()
    before = path.read_bytes()
    assert source.load_connection_string_readonly(path) == "postgresql://synthetic"
    assert path.read_bytes() == before


@pytest.mark.parametrize("code,state", list(source._RECEPTION_STATES.items()))
def test_approved_reception_mapping_and_cancelled_parent_filter(code, state):
    result, diagnostics = source._map_rows(batch([row(source_reception_code=code)]), DAY)
    if state == "CANCELLED":
        assert result.encounters == result.orders == ()
    else:
        assert result.encounters[0].state.value == state
        assert len(result.orders) == 1
    assert dict(diagnostics)["complete"] is True


@pytest.mark.parametrize("dc,state", [("N", "ACTIVE"), ("Y", "CANCELLED")])
def test_dc_flag_maps_order_state_and_numeric_tuple_is_lossless(dc, state):
    result, _ = source._map_rows(batch([row(dc_yn=dc)]), DAY)
    item = result.orders[0]
    assert item.state.value == state
    assert item.daily_quantity.as_tuple() == Decimal("1.250").as_tuple()
    assert item.frequency_count.as_tuple() == Decimal("3.00").as_tuple()
    assert item.day_count is None


@pytest.mark.parametrize("changes,reason", [
    ({"source_reception_code": "99"}, "unknown_reception_state"),
    ({"hold_yn": None}, "invalid_reception_qualifier"),
    ({"hold_yn": ""}, "invalid_reception_qualifier"),
    ({"dc_yn": None}, "invalid_order_qualifiers"),
    ({"dc_yn": ""}, "invalid_order_qualifiers"),
    ({"act_yn": "?"}, "invalid_order_qualifiers"),
    ({"source_order_date": "20261011"}, "invalid_order_scope"),
    ({"source_qty": 1.25}, "invalid_exact_decimal"),
])
def test_ambiguous_source_value_rejects_whole_snapshot(changes, reason):
    with pytest.raises(source.CurrentDaySourceRejected, match=f"^{reason}$"):
        source._map_rows(batch([row(**changes)]), DAY)


def test_zero_rows_are_not_authoritative_empty_day():
    with pytest.raises(source.CurrentDaySourceRejected, match="^empty_day_unverified$"):
        source._map_rows(batch([empty_row()]), DAY)


def test_no_order_metadata_cannot_contradict_child_rows():
    first = row(encounter_count=1, no_order_encounter_count=1, expected_result_rows=2)
    second = row(encounter_count=1, no_order_encounter_count=1, expected_result_rows=2,
                 order_present=False, **{name: None for name in source.FIELDS[13:]})
    with pytest.raises(source.CurrentDaySourceRejected, match="^inconsistent_result$"):
        source._map_rows(batch([first, second]), DAY)


def test_reader_maps_only_after_detached_read_and_clears_rows(tmp_path, monkeypatch):
    path = tmp_path / "settings.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO app_settings VALUES (?, ?)",
                       ("eghis_db_connection_string", "mock-secret"))
    connection.commit()
    connection.close()
    detached = batch([row()])
    monkeypatch.setattr(source, "run_serialized_read", lambda operation: operation())
    monkeypatch.setattr(source, "_read_source", lambda connection_string, query, params: detached)
    result = source.read_current_day_orders(path, clinic_day=DAY, now=lambda: NOW, enabled=True)
    assert result.status == "complete" and len(result.snapshot.orders) == 1
    assert detached.rows == []
    assert "mock-secret" not in repr(result)


def test_source_connection_is_readonly_and_physically_closed(monkeypatch):
    events = []

    class Cursor:
        closed = False
        description = tuple((name,) for name in source.FIELDS)
        rowcount = 1

        def execute(self, statement, params=None):
            events.append(("execute", statement, params))

        def fetchone(self):
            return "on", "2s", "read committed"

        def fetchmany(self, count):
            assert count == source.RESULT_CAP + 1
            return [row()]

        def close(self):
            self.closed = True
            events.append(("cursor_closed",))

    class Connection:
        closed = 0

        def set_session(self, **kwargs):
            assert kwargs == {"readonly": True, "autocommit": True,
                              "isolation_level": "READ COMMITTED"}
            events.append(("readonly",))

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = 1
            events.append(("connection_closed",))

    def connect(value, **kwargs):
        assert value == "mock-secret"
        assert kwargs == {"connect_timeout": 3,
                          "application_name": "KaosEghis-current-day-orders"}
        events.append(("connected",))
        return Connection()

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    result = source._read_source("mock-secret", "SELECT synthetic", {"day": "20261012"})
    assert result.rows == [row()]
    assert events[-2:] == [("cursor_closed",), ("connection_closed",)]
    assert events.count(("connected",)) == events.count(("connection_closed",)) == 1


def test_query_is_pinned_read_only_and_product_owned():
    query = source._query_text()
    assert "public.h1opdin" in query and "public.h2opd_doct_ord" in query
    assert "hold_opd" not in query
    assert not source._WRITE_SQL_PATTERN.search(query)


def test_canonical_validator_rejects_noncanonical_and_cross_day_graph():
    snapshot, _ = source._map_rows(batch([row()]), DAY)
    assert source.validate_canonical_snapshot(snapshot) is snapshot
    bad = source.CanonicalSnapshot(
        DAY, NOW, snapshot.encounters,
        (source.CanonicalOrder(
            source.CanonicalOrderKey("SYNTHETIC-E1", date(2026, 10, 11), "1", "2"),
            None, None, None, None, None, None, None, None, None,
            source.OrderState.ACTIVE, source.Flag.NO, source.Flag.NO,
        ),),
    )
    with pytest.raises(source.CurrentDaySourceRejected, match="^invalid_order_scope$"):
        source.validate_canonical_snapshot(bad)
