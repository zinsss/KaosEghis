from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class PacsPanel(QWidget):
    """Visible working-status scaffold for the KaosEghis-pacs plugin."""

    WORKLIST_COLUMNS = [
        "Status",
        "Patient",
        "Chart No",
        "Study",
        "Modality",
        "Requested At",
        "Accession / Order ID",
    ]

    MOCK_ROWS = [
        ["Active", "", "", "Chest X-ray", "CR", "", ""],
        ["Done", "", "", "", "", "", ""],
        ["Cancelled", "", "", "", "", "", ""],
        ["Error", "", "", "", "", "", ""],
    ]

    def __init__(self) -> None:
        super().__init__()

        title = QLabel("KaosEghis-pacs")
        title.setObjectName("pluginTitle")

        self.eghis_db_status = QLabel("Eghis DB: not connected")
        self.kaospacs_status = QLabel("KaosPACS server: not connected")
        self.polling_status = QLabel("Polling: idle")

        status_row = QHBoxLayout()
        status_row.addWidget(self.eghis_db_status)
        status_row.addWidget(self.kaospacs_status)
        status_row.addWidget(self.polling_status)
        status_row.addStretch()

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Active", "Done", "Cancelled", "Error", "All"])
        self.status_filter.currentTextChanged.connect(self.apply_filter)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_worklist)

        poll_button = QPushButton("Poll now")
        poll_button.clicked.connect(self.poll_now)

        insert_button = QPushButton("Manual insert")
        insert_button.clicked.connect(self.manual_insert)

        cancel_button = QPushButton("Delete / Cancel selected")
        cancel_button.clicked.connect(self.cancel_selected)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Filter:"))
        controls.addWidget(self.status_filter)
        controls.addWidget(refresh_button)
        controls.addWidget(poll_button)
        controls.addWidget(insert_button)
        controls.addWidget(cancel_button)
        controls.addStretch()

        self.worklist_table = QTableWidget(0, len(self.WORKLIST_COLUMNS))
        self.worklist_table.setHorizontalHeaderLabels(self.WORKLIST_COLUMNS)
        self.worklist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.worklist_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.worklist_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.footer_status = QLabel("UI scaffold only. No PACS DB polling or MWL push is active yet.")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(status_row)
        layout.addLayout(controls)
        layout.addWidget(self.worklist_table)
        layout.addWidget(self.footer_status)

        self._rows = [row[:] for row in self.MOCK_ROWS]
        self.apply_filter()

    def refresh_worklist(self) -> None:
        self.footer_status.setText("Worklist refreshed from local scaffold data only.")
        self.apply_filter()

    def poll_now(self) -> None:
        self.polling_status.setText("Polling: not connected")
        self.footer_status.setText("Poll now requested, but real PACS polling is not implemented in this PR.")

    def manual_insert(self) -> None:
        self._rows.append(["Active", "Manual patient", "", "Manual study", "", "", "manual-local"])
        self.footer_status.setText("Added local mock worklist row. No backend write was performed.")
        self.apply_filter()

    def cancel_selected(self) -> None:
        selected_row = self._selected_source_row_index()
        if selected_row is None:
            self.footer_status.setText("Select a worklist row to delete/cancel.")
            return
        self._rows[selected_row][0] = "Cancelled"
        self.footer_status.setText("Selected local mock worklist row marked Cancelled.")
        self.apply_filter()

    def apply_filter(self) -> None:
        current_filter = self.status_filter.currentText()
        filtered_rows = [
            (index, row)
            for index, row in enumerate(self._rows)
            if current_filter == "All" or row[0] == current_filter
        ]
        self.worklist_table.setRowCount(len(filtered_rows))
        for table_row, (source_index, row) in enumerate(filtered_rows):
            for column, value in enumerate(row):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(256, source_index)
                self.worklist_table.setItem(table_row, column, item)
        self.worklist_table.resizeColumnsToContents()

    def _selected_source_row_index(self) -> int | None:
        selected = self.worklist_table.selectedItems()
        if not selected:
            return None
        first_item = self.worklist_table.item(selected[0].row(), 0)
        if first_item is None:
            return None
        value = first_item.data(256)
        return int(value) if value is not None else None
