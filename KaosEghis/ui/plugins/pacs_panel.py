from pathlib import Path
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    PacsWorklistItemRecord,
    create_pacs_worklist_item,
    get_settings,
    list_pacs_worklist_items,
    update_pacs_worklist_item,
    update_pacs_worklist_status,
)
from KaosEghis.core.kaospacs_client import (
    check_kaospacs_health,
    sync_local_worklist_to_kaospacs,
)
from KaosEghis.core.pacs_polling import poll_eghis_image_orders_into_local_worklist
from KaosEghis.ui.plugins.pacs_worklist_dialog import PacsWorklistDialog


class PacsPanel(QWidget):
    WORKLIST_COLUMNS = [
        "Status",
        "Patient",
        "Chart No",
        "Study",
        "Modality",
        "Requested At",
        "Accession / Order ID",
        "KaosPACS Status",
        "Last Synced",
        "Sync Error",
    ]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()

        self._db_path = db_path
        self._visible_items: list[PacsWorklistItemRecord] = []
        self._active_filter = "all"

        title = QLabel("PACS Worklist")
        title.setObjectName("pageTitle")
        self.eghis_db_status = QLabel("Eghis DB: not connected")
        self.pacs_server_status = QLabel("KaosPACS server: not checked")
        self.polling_status = QLabel("Polling status: stopped")

        status_row = QHBoxLayout()
        status_row.addWidget(self.eghis_db_status)
        status_row.addWidget(self.pacs_server_status)
        status_row.addWidget(self.polling_status)
        status_row.addStretch()

        self.worklist_table = QTableWidget(0, len(self.WORKLIST_COLUMNS))
        self.worklist_table.setHorizontalHeaderLabels(self.WORKLIST_COLUMNS)
        self.worklist_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.worklist_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.worklist_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.filter_buttons = []
        for status in ("Active", "Done", "Cancelled", "Error", "All"):
            button = QPushButton(status)
            button.clicked.connect(self._make_filter_handler(status.lower()))
            self.filter_buttons.append(button)

        self.filter_bar = QHBoxLayout()
        for button in self.filter_buttons:
            self.filter_bar.addWidget(button)
        self.filter_bar.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_rows)
        self.check_kaospacs_button = QPushButton("Check KaosPACS")
        self.check_kaospacs_button.clicked.connect(self.check_kaospacs_connection)
        self.poll_button = QPushButton("Poll now")
        self.poll_button.clicked.connect(self.poll_now)
        self.sync_button = QPushButton("Sync to KaosPACS")
        self.sync_button.clicked.connect(self.sync_to_kaospacs)
        self.manual_insert_button = QPushButton("Manual insert")
        self.manual_insert_button.clicked.connect(self.manual_insert_row)
        self.edit_button = QPushButton("Edit selected")
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button = QPushButton("Delete / Cancel selected")
        self.delete_button.clicked.connect(self.delete_selected)

        action_row = QHBoxLayout()
        action_row.addWidget(self.refresh_button)
        action_row.addWidget(self.check_kaospacs_button)
        action_row.addWidget(self.poll_button)
        action_row.addWidget(self.sync_button)
        action_row.addWidget(self.manual_insert_button)
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.delete_button)
        action_row.addStretch()

        footer = QLabel(
            "Local PACS worklist. Poll from Eghis DB and sync to KaosPACS are manual only."
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(status_row)
        layout.addWidget(self.worklist_table)
        layout.addLayout(self.filter_bar)
        layout.addLayout(action_row)
        layout.addWidget(footer)

        self._set_db_labels()
        self.refresh_rows()

    def _set_db_labels(self) -> None:
        self.eghis_db_status.setText("Eghis DB: local sqlite")
        initialize_database(self._db_path)
        self.pacs_server_status.setText("KaosPACS server: not checked")

    def _refresh_kaospacs_status(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
        try:
            healthy = check_kaospacs_health(settings)
        except RuntimeError:
            healthy = False
        if healthy:
            self.pacs_server_status.setText("KaosPACS server: healthy")
        else:
            self.pacs_server_status.setText("KaosPACS server: unavailable")

    def _make_filter_handler(self, status: str):
        def handler() -> None:
            self._active_filter = status
            self.refresh_rows()

        return handler

    def _load_visible_items(self) -> list[PacsWorklistItemRecord]:
        initialize_database(self._db_path)
        status_filter = None if self._active_filter == "all" else self._active_filter

        with connect(self._db_path) as connection:
            return list_pacs_worklist_items(connection, status_filter)

    def refresh_rows(self) -> None:
        items = self._load_visible_items()
        self._visible_items = items
        self.worklist_table.setRowCount(len(items))
        for row_index, item in enumerate(items):
            row = [
                item.status,
                item.patient_name or "",
                item.chart_no or "",
                item.study or "",
                item.modality or "",
                item.requested_at or "",
                item.accession_or_order_id or "",
                item.kaospacs_mwl_status or "",
                item.kaospacs_mwl_last_synced_at or "",
                item.kaospacs_mwl_error or "",
            ]
            for col_index, value in enumerate(row):
                self.worklist_table.setItem(row_index, col_index, QTableWidgetItem(value))

        self.worklist_table.resizeColumnsToContents()

    def check_kaospacs_connection(self) -> None:
        self._refresh_kaospacs_status()

    def poll_now(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        result = poll_eghis_image_orders_into_local_worklist(settings, self._db_path)
        self.refresh_rows()
        if result.message is not None:
            self.polling_status.setText(f"Polling status: {result.message}")
            return
        self.polling_status.setText(
            "Polling status: "
            f"inserted={result.inserted}, updated={result.updated}, skipped={result.skipped}"
        )

    def sync_to_kaospacs(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
            items = list_pacs_worklist_items(connection)

        sync_summary = self._build_sync_summary(items)
        if sync_summary["active_rows"] > 0 and not self._confirm_sync(sync_summary):
            self.polling_status.setText("KaosPACS sync: canceled")
            return

        self._refresh_kaospacs_status()
        result = sync_local_worklist_to_kaospacs(settings, self._db_path)
        self.refresh_rows()
        self.polling_status.setText(
            "KaosPACS sync: "
            f"active rows={sync_summary['active_rows']}, "
            f"cancelled pending rows={sync_summary['cancelled_pending_rows']}, "
            f"sent={result.sent}, cancelled={result.cancelled}, "
            f"errors={result.errors}, skipped={result.skipped}"
        )

    def manual_insert_row(self) -> None:
        dialog = PacsWorklistDialog(self)
        if dialog.exec() != PacsWorklistDialog.DialogCode.Accepted:
            return

        payload = dialog.get_form_data()
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            create_pacs_worklist_item(
                connection,
                status=payload["status"] or "active",
                patient_name=payload["patient_name"],
                chart_no=payload["chart_no"],
                study=payload["study"],
                modality=payload["modality"],
                requested_at=payload["requested_at"],
                accession_or_order_id=payload["accession_or_order_id"],
                source="manual",
            )
        self.refresh_rows()

    def edit_selected(self) -> None:
        item = self._selected_visible_item()
        if item is None:
            return

        dialog = PacsWorklistDialog(self, item=item)
        if dialog.exec() != PacsWorklistDialog.DialogCode.Accepted:
            return

        payload = dialog.get_form_data()
        with connect(self._db_path) as connection:
            update_pacs_worklist_item(
                connection,
                item.id,
                status=payload["status"],
                patient_name=payload["patient_name"],
                chart_no=payload["chart_no"],
                study=payload["study"],
                modality=payload["modality"],
                requested_at=payload["requested_at"],
                accession_or_order_id=payload["accession_or_order_id"],
                source=item.source,
                error_message=item.error_message,
            )
        self.refresh_rows()

    def delete_selected(self) -> None:
        item = self._selected_visible_item()
        if item is None:
            return

        with connect(self._db_path) as connection:
            update_pacs_worklist_status(connection, item.id, "cancelled")
        self.refresh_rows()

    def _build_sync_summary(self, items: list[PacsWorklistItemRecord]) -> dict[str, int]:
        return {
            "active_rows": sum(1 for item in items if item.status == "active"),
            "cancelled_pending_rows": sum(
                1
                for item in items
                if item.status == "cancelled" and item.kaospacs_mwl_status == "sent"
            ),
        }

    def _confirm_sync(self, sync_summary: dict[str, int]) -> bool:
        message = (
            "Sync local PACS worklist to KaosPACS?\n\n"
            f"Active rows: {sync_summary['active_rows']}\n"
            f"Cancelled pending rows: {sync_summary['cancelled_pending_rows']}"
        )
        return (
            QMessageBox.question(
                self,
                "Confirm KaosPACS Sync",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _selected_visible_item(self) -> PacsWorklistItemRecord | None:
        selected = self.worklist_table.selectedItems()
        if not selected:
            return None

        row = selected[0].row()
        if row < 0 or row >= len(self._visible_items):
            return None
        return self._visible_items[row]
