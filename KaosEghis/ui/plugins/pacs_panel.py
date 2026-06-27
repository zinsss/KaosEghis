from pathlib import Path
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
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
    update_pacs_worklist_status,
)
from KaosEghis.core.pacs_polling import poll_eghis_image_orders_into_local_worklist


class PacsPanel(QWidget):
    WORKLIST_COLUMNS = [
        "Status",
        "Patient",
        "Chart No",
        "Study",
        "Modality",
        "Requested At",
        "Accession / Order ID",
    ]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()

        self._db_path = db_path
        self._visible_items: list[PacsWorklistItemRecord] = []
        self._active_filter = "all"

        title = QLabel("KaosEghis-pacs")
        title.setObjectName("pageTitle")
        self.eghis_db_status = QLabel("Eghis DB: not connected")
        self.pacs_server_status = QLabel("KaosPACS server: unknown")
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

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_rows)
        poll_button = QPushButton("Poll now")
        poll_button.clicked.connect(self.poll_now)
        manual_insert_button = QPushButton("Manual insert")
        manual_insert_button.clicked.connect(self.manual_insert_row)
        delete_button = QPushButton("Delete / Cancel selected")
        delete_button.clicked.connect(self.delete_selected)

        action_row = QHBoxLayout()
        action_row.addWidget(refresh_button)
        action_row.addWidget(poll_button)
        action_row.addWidget(manual_insert_button)
        action_row.addWidget(delete_button)
        action_row.addStretch()

        footer = QLabel(
            "Local PACS worklist only. No Eghis polling or KaosPACS push yet."
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
        self.pacs_server_status.setText("KaosPACS server: not connected")

    def _make_filter_handler(self, status: str):
        def handler() -> None:
            self._active_filter = status
            self.refresh_rows()

        return handler

    def refresh_rows(self) -> None:
        initialize_database(self._db_path)
        status_filter = None if self._active_filter == "all" else self._active_filter

        with connect(self._db_path) as connection:
            items = list_pacs_worklist_items(connection, status_filter)

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
            ]
            for col_index, value in enumerate(row):
                self.worklist_table.setItem(row_index, col_index, QTableWidgetItem(value))

        self.worklist_table.resizeColumnsToContents()

    def poll_now(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        self.polling_status.setText("Polling status: manual poll requested")
        result = poll_eghis_image_orders_into_local_worklist(settings, self._db_path)
        self.polling_status.setText(
            "Polling status: inserted="
            f"{result.inserted}, updated={result.updated}, skipped={result.skipped}"
        )
        self.refresh_rows()
        self.polling_status.setText("Polling status: idle")

    def manual_insert_row(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            create_pacs_worklist_item(
                connection,
                status="active",
                patient_name="Manual Sample",
                chart_no="CH-MANUAL",
                study="Manual Entry",
                modality="UNK",
                requested_at="now",
                accession_or_order_id="AC-MANUAL",
            )
        self.refresh_rows()

    def delete_selected(self) -> None:
        selected = self.worklist_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        if row < 0 or row >= len(self._visible_items):
            return

        with connect(self._db_path) as connection:
            item_id = self._visible_items[row].id
            update_pacs_worklist_status(connection, item_id, "cancelled")
        self.refresh_rows()
