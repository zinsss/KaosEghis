from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    create_pacs_worklist_item,
    get_pacs_worklist_item,
    list_pacs_audit_events,
    update_pacs_worklist_status,
)


def test_pacs_revalidation_does_not_hold_local_write_lock(tmp_path, monkeypatch):
    from KaosEghis.core import pacs_polling

    path = tmp_path / "test.sqlite"
    initialize_database(path)
    order = {
        "status": "active",
        "accession_or_order_id": "TEST-ORDER",
        "requested_at": "2026-09-22 09:00:00",
        "source": "eghis-db",
    }
    with connect(path) as connection:
        create_pacs_worklist_item(connection, **order)

    def revalidate(_settings, _ymd, accessions):
        assert accessions == ["TEST-ORDER"]
        # A second feature must be able to write while the EMR query is pending.
        with connect(path, timeout=0.02) as other:
            other.execute("BEGIN IMMEDIATE")
            other.rollback()
        return set(accessions)

    monkeypatch.setattr(pacs_polling, "_fetch_existing_mwl_order_ids", revalidate)
    result = pacs_polling.poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "test-only"},
        path,
        poller=lambda _settings: [order],
        selected_date="2026-09-22",
    )
    assert result.updated == 1
    assert result.removed_active == 0


@pytest.mark.parametrize("new_status", ["completed", "cancelled"])
def test_pacs_revalidation_preserves_edits_made_during_remote_query(
    tmp_path, monkeypatch, new_status
):
    from KaosEghis.core import pacs_polling

    path = tmp_path / "test.sqlite"
    initialize_database(path)
    with connect(path) as connection:
        item = create_pacs_worklist_item(
            connection,
            status="active",
            accession_or_order_id="TEST-ORDER",
            requested_at="2026-09-22 09:00:00",
            source="eghis-db",
        )

    def revalidate(*_args):
        with connect(path, timeout=0.02) as other:
            update_pacs_worklist_status(other, item.id, new_status)
        return set()

    monkeypatch.setattr(pacs_polling, "_fetch_existing_mwl_order_ids", revalidate)
    result = pacs_polling.poll_eghis_image_orders_into_local_worklist(
        {"eghis_db_connection_string": "test-only"},
        path,
        poller=lambda _settings: [],
        selected_date="2026-09-22",
    )
    with connect(path) as connection:
        assert get_pacs_worklist_item(connection, item.id).status == new_status
        assert list_pacs_audit_events(connection) == []
    assert result.removed_active == 0


def test_vaccine_refresh_is_read_only_while_other_feature_is_writing(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from KaosEghis.db import database
    from KaosEghis.ui.tabs import vaccine_tab
    from KaosEghis.ui.tabs.vaccine_tab import VaccineTab

    app = QApplication.instance() or QApplication([])
    path = tmp_path / "test.sqlite"
    page = VaccineTab(path)
    original_connect = database.connect
    migration_calls = []

    def track_initialization(path=None):
        migration_calls.append(path)
        initialize_database(path)

    @contextmanager
    def short_connection(path=None, **_kwargs):
        with original_connect(path, timeout=0.02) as connection:
            yield connection

    monkeypatch.setattr(database, "connect", short_connection)
    monkeypatch.setattr(vaccine_tab, "initialize_database", track_initialization)
    try:
        with original_connect(path) as writer:
            writer.execute("BEGIN IMMEDIATE")
            page.activate_page()
            page.vaccine_types_list.setCurrentRow(1)
            assert page.vaccine_types_list.count() >= 4
            assert migration_calls == []
            writer.rollback()
    finally:
        page.close()
        page.deleteLater()
    assert app is not None


def test_vaccine_fetch_setup_does_not_need_local_write_lock(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from KaosEghis.ui.tabs import vaccine_tab

    app = QApplication.instance() or QApplication([])
    path = tmp_path / "test.sqlite"
    page = vaccine_tab.VaccineTab(path)
    calls = []

    def forbidden_migration(*_args):
        pytest.fail("Fetch setup must not run database migrations")

    def fake_fetch(*_args):
        calls.append("fetch")
        return SimpleNamespace(success=False, context=None, message="Test-only result")

    monkeypatch.setattr(vaccine_tab, "initialize_database", forbidden_migration)
    monkeypatch.setattr(vaccine_tab, "fetch_vaccine_patient_context", fake_fetch)
    try:
        with connect(path) as writer:
            writer.execute("BEGIN IMMEDIATE")
            assert page.fetch_current_patient_from_emr() is False
            assert calls == ["fetch"]
            writer.rollback()
    finally:
        page.close()
        page.deleteLater()
    assert app is not None


def test_open_vaccine_refreshes_once():
    from KaosEghis.ui.tabs.kaoseghis_tab import KaosEghisTab

    calls = []
    page = SimpleNamespace(
        activate_page=lambda: calls.append("activate"),
        refresh_view=lambda: calls.append("refresh"),
    )
    tab = SimpleNamespace(
        stacked_widget=SimpleNamespace(
            setCurrentIndex=lambda index: None,
            currentWidget=lambda: page,
        ),
        STACKED_PAGE_NAMES=["Vaccine"],
        nav_buttons={},
    )
    KaosEghisTab.show_page(tab, 0)
    assert calls == ["activate"]
