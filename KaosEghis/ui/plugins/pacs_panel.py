from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
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
    set_settings,
    update_pacs_worklist_item,
    update_pacs_worklist_status,
)
from KaosEghis.core.kaospacs_client import (
    check_kaospacs_health,
    reconcile_kaospacs_worklist_to_local,
    sync_local_worklist_to_kaospacs,
)
from KaosEghis.core.pacs_polling import poll_eghis_image_orders_into_local_worklist
from KaosEghis.ui.plugins.pacs_worklist_dialog import PacsWorklistDialog


class PacsPanel(QWidget):
    DEFAULT_POLL_INTERVAL_SECONDS = 60
    MIN_POLL_INTERVAL_SECONDS = 15
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
        self._poll_in_progress = False
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._handle_poll_timer_tick)

        title = QLabel("PACS Worklist")
        title.setObjectName("pageTitle")
        self.eghis_db_status = QLabel("Eghis DB: not connected")
        self.pacs_server_status = QLabel("KaosPACS server: not checked")
        self.polling_status = QLabel("Polling status: stopped")
        self.last_poll_time_label = QLabel("Last poll time: never")
        self.last_poll_result_label = QLabel("Last poll result: none")

        status_row = QHBoxLayout()
        status_row.addWidget(self.eghis_db_status)
        status_row.addWidget(self.pacs_server_status)
        status_row.addWidget(self.polling_status)
        status_row.addStretch()

        polling_info_row = QHBoxLayout()
        polling_info_row.addWidget(self.last_poll_time_label)
        polling_info_row.addWidget(self.last_poll_result_label)
        polling_info_row.addStretch()

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

        self.auto_poll_checkbox = QCheckBox("Auto poll")
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setMinimum(self.MIN_POLL_INTERVAL_SECONDS)
        self.interval_spinbox.setMaximum(86400)
        self.interval_spinbox.setValue(self.DEFAULT_POLL_INTERVAL_SECONDS)
        self.apply_polling_settings_button = QPushButton("Apply polling settings")
        self.apply_polling_settings_button.clicked.connect(self.apply_polling_settings)

        polling_settings_row = QHBoxLayout()
        polling_settings_row.addWidget(self.auto_poll_checkbox)
        polling_settings_row.addWidget(QLabel("Interval seconds"))
        polling_settings_row.addWidget(self.interval_spinbox)
        polling_settings_row.addWidget(self.apply_polling_settings_button)
        polling_settings_row.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_rows)
        self.check_kaospacs_button = QPushButton("Check KaosPACS")
        self.check_kaospacs_button.clicked.connect(self.check_kaospacs_connection)
        self.poll_button = QPushButton("Poll now")
        self.poll_button.clicked.connect(self.poll_now)
        self.sync_button = QPushButton("Sync to KaosPACS")
        self.sync_button.clicked.connect(self.sync_to_kaospacs)
        self.reconcile_button = QPushButton("Reconcile from KaosPACS")
        self.reconcile_button.clicked.connect(self.reconcile_from_kaospacs)
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
        action_row.addWidget(self.reconcile_button)
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
        layout.addLayout(polling_info_row)
        layout.addLayout(polling_settings_row)
        layout.addWidget(self.worklist_table)
        layout.addLayout(self.filter_bar)
        layout.addLayout(action_row)
        layout.addWidget(footer)

        self._set_db_labels()
        self._load_polling_settings()
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
        self._run_poll()

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

    def reconcile_from_kaospacs(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        result = reconcile_kaospacs_worklist_to_local(settings, self._db_path)
        self.refresh_rows()
        if result.message is not None:
            self.polling_status.setText(f"KaosPACS reconcile: {result.message}")
            return
        self.polling_status.setText(
            "KaosPACS reconcile: "
            f"done={result.done}, cancelled={result.cancelled}, "
            f"skipped={result.skipped}, errors={result.errors}"
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

    def apply_polling_settings(self) -> None:
        enabled_value = "true" if self.auto_poll_checkbox.isChecked() else "false"
        interval_seconds = self._normalize_poll_interval(self.interval_spinbox.value())
        self.interval_spinbox.setValue(interval_seconds)

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            set_settings(
                connection,
                {
                    "pacs_auto_poll_enabled": enabled_value,
                    "pacs_poll_interval_seconds": str(interval_seconds),
                },
            )

        self._apply_polling_state(enabled_value == "true", interval_seconds)
        self.polling_status.setText(
            f"Polling settings applied: enabled={enabled_value}, interval={interval_seconds}s"
        )

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

    def _load_polling_settings(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        enabled = self._parse_auto_poll_enabled(settings.get("pacs_auto_poll_enabled"))
        interval_seconds = self._normalize_poll_interval(
            settings.get("pacs_poll_interval_seconds")
        )
        self.auto_poll_checkbox.setChecked(enabled)
        self.interval_spinbox.setValue(interval_seconds)
        self._apply_polling_state(enabled, interval_seconds)

    def _apply_polling_state(self, enabled: bool, interval_seconds: int) -> None:
        if enabled:
            self._poll_timer.start(interval_seconds * 1000)
        else:
            self._poll_timer.stop()

    def _handle_poll_timer_tick(self) -> None:
        self._run_poll()

    def _run_poll(self) -> None:
        if self._poll_in_progress:
            self.last_poll_result_label.setText("Last poll result: skipped overlap")
            self.polling_status.setText("Polling status: skipped overlap")
            return

        self._poll_in_progress = True
        try:
            initialize_database(self._db_path)
            with connect(self._db_path) as connection:
                settings = get_settings(connection)

            result = poll_eghis_image_orders_into_local_worklist(settings, self._db_path)
            self.refresh_rows()
            self.last_poll_time_label.setText(
                f"Last poll time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            if result.message is not None:
                self.last_poll_result_label.setText(f"Last poll result: {result.message}")
                self.polling_status.setText(f"Polling status: {result.message}")
                return
            summary = (
                f"inserted={result.inserted}, updated={result.updated}, skipped={result.skipped}"
            )
            self.last_poll_result_label.setText(f"Last poll result: {summary}")
            self.polling_status.setText(f"Polling status: {summary}")
        finally:
            self._poll_in_progress = False

    @classmethod
    def _parse_auto_poll_enabled(cls, value: str | None) -> bool:
        return (value or "").strip().lower() == "true"

    @classmethod
    def _normalize_poll_interval(cls, value: str | int | None) -> int:
        try:
            interval = int(value) if value is not None else cls.DEFAULT_POLL_INTERVAL_SECONDS
        except (TypeError, ValueError):
            return cls.DEFAULT_POLL_INTERVAL_SECONDS
        if interval < cls.MIN_POLL_INTERVAL_SECONDS:
            return cls.MIN_POLL_INTERVAL_SECONDS
        return interval
