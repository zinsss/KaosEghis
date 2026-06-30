import builtins
import sys
from datetime import date

from KaosEghis.core.pacs_polling import (
    PollingUnavailableError,
    QueryRejectedError,
    _DEFAULT_IMAGE_ORDER_QUERY,
    _map_db_row_to_order,
    poll_eghis_image_orders_into_local_worklist,
    poll_image_orders,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import list_pacs_worklist_items


def test_poll_image_orders_without_db_config_returns_no_rows() -> None:
    assert poll_image_orders({}) == []


def test_poll_image_orders_uses_default_postgres_query_when_query_blank(
    monkeypatch,
) -> None:
    from KaosEghis.core import pacs_polling

    executed_queries: list[str] = []

    class FakeCursor:
        description = [
            ("patient_name",),
            ("patient_id",),
            ("order_name",),
            ("modality_code",),
            ("order_datetime",),
            ("accession_or_order_id",),
            ("status",),
            ("dc_yn",),
        ]

        def execute(self, query: str) -> None:
            executed_queries.append(query)

        def fetchall(self) -> list[tuple[str, ...]]:
            return [
                ("Lee", "C100", "MRI Brain", "MR", "2026-06-28 11:30", "O-100", "active", "N")
            ]

        def close(self) -> None:
            return None

    class FakeConnection:
        def __init__(self) -> None:
            self.readonly = None
            self.autocommit = None

        def set_session(self, readonly: bool, autocommit: bool) -> None:
            self.readonly = readonly
            self.autocommit = autocommit

        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            return None

    class FakePsycopg2Module:
        def connect(self, connection_string: str):
            self.connection_string = connection_string
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg2", FakePsycopg2Module())

    rows = pacs_polling.poll_image_orders(
        {
            "eghis_db_connection_string": "postgresql://example",
            "eghis_db_image_study_query": "",
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
    assert executed_queries == [_DEFAULT_IMAGE_ORDER_QUERY]
    assert "public.mwl" in executed_queries[0]
    assert "public.h2opd_doct_ord" in executed_queries[0]
    assert "m.scheduled_proc_status = '100'" in executed_queries[0]
    assert "proc_dept_cd = 'XRAY'" in executed_queries[0]
    assert "m.patient_id AS patient_id" in executed_queries[0]
    assert "m.patient_name AS patient_name" in executed_queries[0]
    assert "o.recept_no = split_part(m.eghis_key, '_', 1)" in executed_queries[0]
    assert "CAST(o.ord_no AS text) = split_part(m.eghis_key, '_', 2)" in executed_queries[0]
    assert "CAST(o.ord_seq_no AS text) = split_part(m.eghis_key, '_', 3)" in executed_queries[0]
    assert "dc_yn != 'Y'" not in executed_queries[0]
    assert "COALESCE(o.dc_yn, 'N') = 'Y'" in executed_queries[0]


def test_poll_image_orders_selected_date_is_applied_to_default_query(
    monkeypatch,
) -> None:
    from KaosEghis.core import pacs_polling

    executed_queries: list[str] = []

    class FakeCursor:
        description = []

        def execute(self, query: str) -> None:
            executed_queries.append(query)

        def fetchall(self) -> list[tuple]:
            return []

        def close(self) -> None:
            return None

    class FakeConnection:
        def set_session(self, readonly: bool, autocommit: bool) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            return None

    class FakePsycopg2Module:
        def connect(self, connection_string: str):
            return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg2", FakePsycopg2Module())

    pacs_polling.poll_image_orders(
        {
            "eghis_db_connection_string": "postgresql://example",
            "eghis_db_image_study_query": "",
        },
        selected_date=date(2026, 6, 30),
    )

    assert "20260630" in executed_queries[0]
    assert "regexp_replace" in executed_queries[0]


def test_fetch_existing_mwl_order_ids_query_does_not_apply_active_filters(
    monkeypatch,
) -> None:
    from KaosEghis.core import pacs_polling

    executed_queries: list[str] = []

    monkeypatch.setattr(
        pacs_polling,
        "run_readonly_query",
        lambda connection_string, query: executed_queries.append(query)
        or (["accession_or_order_id"], []),
    )

    result = pacs_polling._fetch_existing_mwl_order_ids(
        {"eghis_db_connection_string": "postgresql://example"},
        "20260630",
        ["ACC-1"],
    )

    assert result == set()
    assert "proc_dept_cd = 'XRAY'" not in executed_queries[0]
    assert "scheduled_proc_status = '100'" not in executed_queries[0]
    assert "HC342" not in executed_queries[0]


def test_poll_image_orders_rejects_write_sql() -> None:
    try:
        poll_image_orders(
            {
                "eghis_db_connection_string": "postgresql://example",
                "eghis_db_image_study_query": "UPDATE orders SET status='done'",
            }
        )
    except QueryRejectedError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected QueryRejectedError")

    assert "rejected" in message


def test_poll_image_orders_returns_unavailable_when_psycopg2_missing(
    monkeypatch,
) -> None:
    from KaosEghis.core import pacs_polling

    original_import = builtins.__import__
    monkeypatch.delitem(sys.modules, "psycopg2", raising=False)

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "psycopg2":
            raise ImportError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        pacs_polling.poll_image_orders(
            {
                "eghis_db_connection_string": "postgresql://example",
                "eghis_db_image_study_query": "",
            }
        )
    except PollingUnavailableError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected PollingUnavailableError")

    assert "psycopg2" in message


def test_map_db_row_aliases_to_canonical_order_and_ignores_extra_fields() -> None:
    order = _map_db_row_to_order(
        [
            "수진자명",
            "차트번호",
            "study",
            "modality",
            "requested_at",
            "처방번호",
            "status",
            "DOB",
            "phone",
            "diagnosis",
        ],
        (
            "Kim",
            "C001",
            "Chest CT",
            "CT",
            "2026-06-28 10:00",
            "ORD-1",
            "cancelled",
            "1990-01-01",
            "01012345678",
            "sensitive",
        ),
    )

    assert order == {
        "status": "cancelled",
        "patient_name": "Kim",
        "chart_no": "C001",
        "study": "Chest CT",
        "modality": "CT",
        "requested_at": "2026-06-28 10:00",
        "accession_or_order_id": "ORD-1",
        "source": "eghis-db",
    }


def test_poll_service_query_rejected_returns_safe_status(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    result = poll_eghis_image_orders_into_local_worklist(
        {
            "eghis_db_connection_string": "postgresql://example",
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


def test_poll_service_adapter_unavailable_returns_safe_status(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    monkeypatch.setattr(
        pacs_polling,
        "poll_image_orders",
        lambda _settings, selected_date=None: (_ for _ in ()).throw(
            PollingUnavailableError("psycopg2 missing")
        ),
    )

    result = poll_eghis_image_orders_into_local_worklist(
        {
            "eghis_db_connection_string": "postgresql://example",
            "eghis_db_image_study_query": "",
        },
        db_path=db_path,
    )

    assert result.message == "unavailable"


def test_poll_service_inserts_realistic_order(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_poll_image_orders(
        _settings: dict[str, str],
        selected_date=None,
    ) -> list[dict[str, str | None]]:
        return [
            {
                "status": "active",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-001",
                "source": "eghis-db",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)

    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 1
    assert result.updated == 0
    assert result.skipped == 0
    assert len(rows) == 1
    assert rows[0].accession_or_order_id == "AC-001"
    assert rows[0].patient_name == "Alice"


def test_poll_service_duplicate_order_updates_instead_of_insert(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_active_order(
        _settings: dict[str, str],
        selected_date=None,
    ) -> list[dict[str, str | None]]:
        return [
            {
                "status": "active",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-002",
                "source": "eghis-db",
            }
        ]

    def fake_cancelled_order(
        _settings: dict[str, str],
        selected_date=None,
    ) -> list[dict[str, str | None]]:
        return [
            {
                "status": "cancelled",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-002",
                "source": "eghis-db",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_active_order)
    first = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
    )

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_cancelled_order)
    second = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert first.inserted == 1
    assert second.inserted == 0
    assert second.updated == 1
    assert len(rows) == 1
    assert rows[0].status == "cancelled"


def test_poll_service_skips_cancelled_order_without_existing_local_row(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_cancelled_order(
        _settings: dict[str, str],
        selected_date=None,
    ) -> list[dict[str, str | None]]:
        return [
            {
                "status": "cancelled",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-003",
                "source": "eghis-db",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_cancelled_order)
    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 0
    assert result.updated == 0
    assert result.skipped == 1
    assert rows == []


def test_pacs_local_storage_does_not_include_sensitive_fields(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_poll_image_orders(
        _settings: dict[str, str],
        selected_date=None,
    ) -> list[dict[str, str | None]]:
        return [
            {
                "status": "active",
                "patient_name": "Alice",
                "chart_no": "C001",
                "study": "Chest",
                "modality": "CR",
                "requested_at": "2026-01-01T00:00:00",
                "accession_or_order_id": "AC-004",
                "source": "eghis-db",
                "patient_birth_date": "1990-01-01",
                "patient_sex": "F",
                "resident_id": "123456-1234567",
                "phone": "01012345678",
                "address": "secret",
                "diagnosis": "secret",
                "raw_row": "secret",
            }
        ]

    monkeypatch.setattr(pacs_polling, "poll_image_orders", fake_poll_image_orders)
    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(pacs_worklist_items)")
        }
        row = connection.execute(
            """
            SELECT patient_name, chart_no, study, modality, requested_at,
                   accession_or_order_id, status, source, error_message
            FROM pacs_worklist_items
            WHERE accession_or_order_id = ?
            """,
            ("AC-004",),
        ).fetchone()

    assert result.inserted == 1
    assert "patient_birth_date" not in columns
    assert "patient_sex" not in columns
    assert "resident_id" not in columns
    assert row == (
        "Alice",
        "C001",
        "Chest",
        "CR",
        "2026-01-01T00:00:00",
        "AC-004",
        "active",
        "eghis-db",
        None,
    )


def test_poll_service_skips_rows_without_accession_or_order_id(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    def fake_poll_image_orders(
        _settings: dict[str, str],
        selected_date=None,
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
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.inserted == 0
    assert result.updated == 0
    assert result.skipped == 1
    assert rows == []


def test_poll_service_missing_mwl_row_changes_active_to_cancelled_and_audits(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling
    from KaosEghis.db.repositories import (
        create_pacs_worklist_item,
        list_pacs_audit_events,
    )

    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="Alice",
            study="Chest",
            modality="CR",
            requested_at="2026-06-30 09:30:00",
            accession_or_order_id="ACC-REMOVE",
            source="eghis-db",
        )

    monkeypatch.setattr(
        pacs_polling,
        "poll_image_orders",
        lambda _settings, selected_date=None: [],
    )
    monkeypatch.setattr(
        pacs_polling,
        "_fetch_existing_mwl_order_ids",
        lambda settings, selected_ymd, accession_or_order_ids: set(),
    )
    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
        selected_date=date(2026, 6, 30),
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)
        audit_rows = list_pacs_audit_events(connection)

    assert result.removed_active == 1
    assert len(rows) == 1
    assert rows[0].status == "cancelled"
    assert rows[0].error_message == "order removed from eGHIS MWL"
    assert audit_rows[0].event_type == "poll"
    assert audit_rows[0].summary == "active order removed from eGHIS MWL -> marked cancelled"
    assert audit_rows[0].status_before == "active"
    assert audit_rows[0].status_after == "cancelled"
    assert "Alice" not in audit_rows[0].summary


def test_poll_service_missing_mwl_row_preserves_done_and_cancelled(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling
    from KaosEghis.db.repositories import create_pacs_worklist_item, list_pacs_audit_events

    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="done",
            study="Chest",
            modality="CR",
            requested_at="2026-06-30 09:30:00",
            accession_or_order_id="ACC-DONE",
            source="eghis-db",
        )
        create_pacs_worklist_item(
            connection,
            status="cancelled",
            study="Chest",
            modality="CR",
            requested_at="2026-06-30 09:31:00",
            accession_or_order_id="ACC-CANCELLED",
            source="eghis-db",
        )

    monkeypatch.setattr(
        pacs_polling,
        "poll_image_orders",
        lambda _settings, selected_date=None: [],
    )
    monkeypatch.setattr(
        pacs_polling,
        "_fetch_existing_mwl_order_ids",
        lambda settings, selected_ymd, accession_or_order_ids: set(),
    )
    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
        selected_date="2026-06-30",
    )

    with connect(db_path) as connection:
        rows = sorted(list_pacs_worklist_items(connection), key=lambda row: row.id)
        audit_rows = list_pacs_audit_events(connection)

    assert result.removed_active == 0
    assert [row.status for row in rows] == ["done", "cancelled"]
    assert audit_rows == []


def test_active_row_present_in_mwl_but_excluded_by_active_order_filter_remains_active(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling

    with connect(db_path) as connection:
        create = connection.execute
        from KaosEghis.db.repositories import create_pacs_worklist_item

        create_pacs_worklist_item(
            connection,
            status="active",
            study="BMD",
            modality="BMD",
            requested_at="2026-06-30 10:00:00",
            accession_or_order_id="ACC-BMD",
            source="eghis-db",
        )

    monkeypatch.setattr(
        pacs_polling,
        "poll_image_orders",
        lambda _settings, selected_date=None: [],
    )
    monkeypatch.setattr(
        pacs_polling,
        "_fetch_existing_mwl_order_ids",
        lambda settings, selected_ymd, accession_or_order_ids: {"ACC-BMD"},
    )

    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
        selected_date="2026-06-30",
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.removed_active == 0
    assert rows[0].status == "active"


def test_active_row_present_with_non_100_status_remains_active(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling
    from KaosEghis.db.repositories import create_pacs_worklist_item

    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            study="Chest",
            modality="CR",
            requested_at="2026-06-30 10:00:00",
            accession_or_order_id="ACC-NON100",
            source="eghis-db",
        )

    monkeypatch.setattr(
        pacs_polling,
        "poll_image_orders",
        lambda _settings, selected_date=None: [],
    )
    monkeypatch.setattr(
        pacs_polling,
        "_fetch_existing_mwl_order_ids",
        lambda settings, selected_ymd, accession_or_order_ids: {"ACC-NON100"},
    )

    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
        selected_date="2026-06-30",
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.removed_active == 0
    assert rows[0].status == "active"


def test_active_bmd_row_present_but_excluded_by_xray_filter_remains_active(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling
    from KaosEghis.db.repositories import create_pacs_worklist_item

    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            study="BMD",
            modality="BMD",
            requested_at="2026-06-30 10:00:00",
            accession_or_order_id="ACC-BMD-XRAY",
            source="eghis-db",
        )

    monkeypatch.setattr(
        pacs_polling,
        "poll_image_orders",
        lambda _settings, selected_date=None: [],
    )
    monkeypatch.setattr(
        pacs_polling,
        "_fetch_existing_mwl_order_ids",
        lambda settings, selected_ymd, accession_or_order_ids: {"ACC-BMD-XRAY"},
    )

    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
        selected_date="2026-06-30",
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)

    assert result.removed_active == 0
    assert rows[0].status == "active"


def test_db_unavailable_does_not_cancel_local_rows(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    from KaosEghis.core import pacs_polling
    from KaosEghis.db.repositories import create_pacs_worklist_item, list_pacs_audit_events

    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            study="Chest",
            modality="CR",
            requested_at="2026-06-30 10:00:00",
            accession_or_order_id="ACC-KEEP",
            source="eghis-db",
        )

    monkeypatch.setattr(
        pacs_polling,
        "poll_image_orders",
        lambda _settings, selected_date=None: [],
    )
    monkeypatch.setattr(
        pacs_polling,
        "_fetch_existing_mwl_order_ids",
        lambda settings, selected_ymd, accession_or_order_ids: None,
    )

    result = poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "postgresql://example"},
        db_path=db_path,
        selected_date="2026-06-30",
    )

    with connect(db_path) as connection:
        rows = list_pacs_worklist_items(connection)
        audit_rows = list_pacs_audit_events(connection)

    assert result.removed_active == 0
    assert rows[0].status == "active"
    assert audit_rows == []
