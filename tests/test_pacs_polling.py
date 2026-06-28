import builtins
import sys

from KaosEghis.core.pacs_polling import (
    PollingUnavailableError,
    QueryRejectedError,
    _map_db_row_to_order,
    poll_eghis_image_orders_into_local_worklist,
    poll_image_orders,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import list_pacs_worklist_items


def test_poll_service_no_db_config_is_noop(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    calls: list[dict[str, str | None]] = []

    def fake_poll_image_orders(_settings: dict[str, str]) -> list[dict[str, str | None]]:
        calls.append({})
        return [
            {
                "status": "active",
                "accession_or_order_id": "X-1",
                "patient_name": "Ghost",
                "chart_no": "000",
            }
        ]

    from KaosEghis.core import pacs_polling

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)

    result = poll_eghis_image_orders_into_local_worklist({}, db_path=db_path)
    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 0
    assert result.updated == 0
    assert result.skipped == 0
    assert not calls
    assert len(rows) == 0


def test_poll_image_orders_no_query_returns_no_rows() -> None:
    rows = poll_image_orders({"eghis_db_connection_string": "Driver=SQLite"})
    assert rows == []


def test_poll_image_orders_rejects_write_sql() -> None:
    try:
        poll_image_orders(
            {
                "eghis_db_connection_string": "Driver=SQLite",
                "eghis_db_image_study_query": "UPDATE orders SET status='done'",
            }
        )
    except QueryRejectedError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected QueryRejectedError")

    assert "rejected" in message


def test_poll_image_orders_returns_no_rows_when_pyodbc_missing(monkeypatch) -> None:
    from KaosEghis.core import pacs_polling

    original_import = builtins.__import__
    monkeypatch.delitem(sys.modules, "pyodbc", raising=False)

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pyodbc":
            raise ImportError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        pacs_polling.poll_image_orders(
            {
                "eghis_db_connection_string": "Driver=SQLite",
                "eghis_db_image_study_query": "SELECT 1",
            }
        )
    except PollingUnavailableError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected PollingUnavailableError")

    assert "pyodbc" in message


def test_map_db_row_aliases_to_canonical_order() -> None:
    order = _map_db_row_to_order(
        ["수진자명", "차트번호", "처방명", "검사구분", "처방일시", "처방번호", "DOB"],
        ("Kim", "C001", "Chest CT", "CT", "2026-06-28 10:00", "ORD-1", "1990-01-01"),
    )

    assert order == {
        "status": "active",
        "patient_name": "Kim",
        "chart_no": "C001",
        "study": "Chest CT",
        "modality": "CT",
        "requested_at": "2026-06-28 10:00",
        "accession_or_order_id": "ORD-1",
        "source": "eghis-db",
    }


def test_poll_service_db_config_without_query_is_noop(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    result = poll_eghis_image_orders_into_local_worklist(
        {
            "eghis_db_connection_string": "Driver=SQLite",
            "eghis_db_image_study_query": "",
        },
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 0
    assert result.updated == 0
    assert result.skipped == 0
    assert rows == []


def test_poll_service_query_rejected_returns_safe_status(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    result = poll_eghis_image_orders_into_local_worklist(
        {
            "eghis_db_connection_string": "Driver=SQLite",
            "eghis_db_image_study_query": "DELETE FROM orders",
        },
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 0
    assert result.updated == 0
    assert result.skipped == 0
    assert result.message == "query rejected"
    assert rows == []


def test_poll_service_adapter_unavailable_returns_safe_status(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    monkeypatch.setattr(
        pacs_polling,
        "poll_image_orders",
        lambda _settings: (_ for _ in ()).throw(PollingUnavailableError("pyodbc missing")),
    )

    result = poll_eghis_image_orders_into_local_worklist(
        {
            "eghis_db_connection_string": "Driver=SQLite",
            "eghis_db_image_study_query": "SELECT 1",
        },
        db_path=db_path,
    )

    assert result.message == "unavailable"


def test_poll_service_inserts_mock_order(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_poll_image_orders(_settings: dict[str, str]) -> list[dict[str, str | None]]:
        return [
            {
                "status": "active",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-001",
                "source": "eghis-poll-mock",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)

    settings = {"eghis_db_connection_string": "read-only-scaffold"}
    result = poll_eghis_image_orders_into_local_worklist(settings, db_path=db_path)

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 1
    assert result.updated == 0
    assert result.skipped == 0
    assert len(rows) == 1
    assert rows[0].accession_or_order_id == "AC-001"
    assert rows[0].patient_name == "Alice"


def test_poll_service_does_not_duplicate_orders(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_poll_image_orders(_settings: dict[str, str]) -> list[dict[str, str | None]]:
        return [
            {
                "status": "active",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-002",
                "source": "eghis-poll-mock",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)
    settings = {"eghis_db_connection_string": "read-only-scaffold"}

    first = poll_eghis_image_orders_into_local_worklist(settings, db_path=db_path)
    second = poll_eghis_image_orders_into_local_worklist(settings, db_path=db_path)

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert first.inserted == 1
    assert first.updated == 0
    assert second.inserted == 0
    assert second.updated == 1
    assert len(rows) == 1
    assert rows[0].accession_or_order_id == "AC-002"


def test_poll_service_skips_rows_without_accession_or_order_id(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_poll_image_orders(
        _settings: dict[str, str],
    ) -> list[dict[str, str | None]]:
        return [
            {
                "status": "active",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "   ",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)
    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "read-only-scaffold"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 0
    assert result.updated == 0
    assert result.skipped == 1
    assert rows == []


def test_poll_image_orders_reads_db_rows_with_alias_mapping(monkeypatch) -> None:
    from KaosEghis.core import pacs_polling

    class FakeCursor:
        description = [
            ("PatientName",),
            ("patient_no",),
            ("order_name",),
            ("modality_code",),
            ("order_datetime",),
            ("order_id",),
            ("phone",),
        ]

        def execute(self, query: str) -> None:
            self.query = query

        def fetchall(self) -> list[tuple[str, ...]]:
            return [
                ("Lee", "C100", "MRI Brain", "MR", "2026-06-28 11:30", "O-100", "01012345678")
            ]

        def close(self) -> None:
            return None

    class FakeConnection:
        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            return None

    class FakePyodbcModule:
        def connect(self, connection_string: str, autocommit: bool = True, readonly: bool = True):
            self.connection_string = connection_string
            self.autocommit = autocommit
            self.readonly = readonly
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "pyodbc", FakePyodbcModule())

    rows = pacs_polling.poll_image_orders(
        {
            "eghis_db_connection_string": "Driver=SQLite",
            "eghis_db_image_study_query": "SELECT * FROM image_orders",
        }
    )

    assert rows == [
        {
            "status": "active",
            "patient_name": "Lee",
            "chart_no": "C100",
            "study": "MRI Brain",
            "modality": "MR",
            "requested_at": "2026-06-28 11:30",
            "accession_or_order_id": "O-100",
            "source": "eghis-db",
        }
    ]
