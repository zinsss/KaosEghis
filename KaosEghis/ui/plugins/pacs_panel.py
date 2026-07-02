from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import re

from PySide6.QtCore import QDate, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.clipboard_service import copy_text
from KaosEghis.core.eghis_db import (
    EghisDbQueryRejectedError,
    EghisDbUnavailableError,
    run_readonly_query,
)
from KaosEghis.core.kaospacs_client import (
    check_kaospacs_health,
    reconcile_kaospacs_worklist_to_local,
    sync_local_worklist_to_kaospacs,
)
from KaosEghis.core.kaospacs_gateway_client import get_imaging_worklist
from KaosEghis.core.pacs_polling import poll_eghis_image_orders_into_local_worklist
from KaosEghis.db.database import connect, describe_database_path, initialize_database
from KaosEghis.db.repositories import (
    PacsAuditEventRecord,
    PacsWorklistItemRecord,
    clear_pacs_audit_events,
    create_pacs_audit_event,
    create_pacs_worklist_item,
    get_settings,
    list_pacs_audit_events,
    list_pacs_worklist_items,
    set_settings,
    update_pacs_worklist_item,
    update_pacs_worklist_status,
)
from KaosEghis.ui.plugins.pacs_worklist_dialog import PacsWorklistDialog


class PacsPanel(QWidget):
    health_state_changed = Signal(bool, str)
    DEFAULT_POLL_INTERVAL_SECONDS = 60
    MIN_POLL_INTERVAL_SECONDS = 15
    IMAGING_REFRESH_DELAY_MS = 350
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
    IMAGING_COLUMNS = [
        "state",
        "AccessionNumber",
        "PatientID",
        "PatientName",
        "PatientBirthDate",
        "PatientSex",
        "Modality",
        "ScheduledStationAETitle",
        "ScheduledAt",
        "Description",
        "CompletedAt",
        "ExpiredAt",
        "ExpireReason",
        "CancelledAt",
        "CancelReason",
    ]
    AUDIT_COLUMNS = [
        "Time",
        "Type",
        "Accession / Order ID",
        "Status Before",
        "Status After",
        "Summary",
        "Error",
    ]
    FILTER_BUTTON_SELECTED_STYLE = (
        "background-color: #cba6f7; color: #1e1e2e; "
        "border: 1px solid #cba6f7; font-weight: 700;"
    )
    FILTER_BUTTON_UNSELECTED_STYLE = ""

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()

        self._db_path = db_path
        self._visible_items: list[PacsWorklistItemRecord] = []
        self._visible_audit_events: list[PacsAuditEventRecord] = []
        self._imaging_entries_all: list[dict] = []
        self._visible_imaging_entries: list[dict] = []
        self._kaospacs_available = False
        self._eghis_db_available = False
        self._health_reason = "PACS health unknown"
        self._active_filter = "all"
        self._imaging_filter = "active"
        self._poll_in_progress = False
        self._selected_date = date.today()
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._handle_poll_timer_tick)

        self.page_stack = QStackedWidget()
        self._page_names = ["imaging", "operator_mode", "settings"]
        self.page_buttons: dict[str, QPushButton] = {}

        title = QLabel("PACS Worklist")
        title.setObjectName("pageTitle")

        self._build_imaging_page()
        self._build_operator_mode_page()
        self._build_settings_page()

        self.page_stack.addWidget(self.imaging_page)
        self.page_stack.addWidget(self.operator_mode_page)
        self.page_stack.addWidget(self.settings_page)

        navigation_row = QHBoxLayout()
        navigation_row.addWidget(self._make_page_button("Imaging Worklist", "imaging"))
        navigation_row.addWidget(self._make_page_button("Operator Mode", "operator_mode"))
        navigation_row.addWidget(self._make_page_button("Settings", "settings"))
        navigation_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(navigation_row)
        layout.addWidget(self.page_stack)

        self._set_db_labels()
        self._load_polling_settings()
        self._update_local_filter_button_states()
        self._update_imaging_filter_button_states()
        self._update_startup_readiness_status()
        self._refresh_startup_connection_statuses()
        self._refresh_settings_diagnostics()
        self._show_page("imaging")

    def _build_imaging_page(self) -> None:
        self.imaging_page = QWidget()
        self.imaging_status_label = QLabel("Not loaded yet.")
        self.imaging_search_input = QLineEdit()
        self.imaging_search_input.setPlaceholderText(
            "Search PatientName / PatientID / AccessionNumber / Modality"
        )
        self.imaging_search_input.textChanged.connect(self._refresh_imaging_table)
        self.imaging_refresh_button = QPushButton("Refresh Imaging Worklist")
        self.imaging_refresh_button.clicked.connect(self.refresh_imaging_worklist)

        self.imaging_filter_buttons: dict[str, QPushButton] = {}
        imaging_filter_row = QHBoxLayout()
        for key, label in (
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("completed", "Completed"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("all", "All"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(self._make_imaging_filter_handler(key))
            self.imaging_filter_buttons[key] = button
            imaging_filter_row.addWidget(button)
        imaging_filter_row.addStretch()

        imaging_controls = QHBoxLayout()
        imaging_controls.addWidget(self.imaging_refresh_button)
        imaging_controls.addWidget(self.imaging_search_input)

        self.imaging_table = QTableWidget(0, len(self.IMAGING_COLUMNS))
        self.imaging_table.setHorizontalHeaderLabels(self.IMAGING_COLUMNS)
        self.imaging_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.imaging_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.imaging_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        layout = QVBoxLayout(self.imaging_page)
        layout.addWidget(QLabel("KaosPACS Gateway Imaging Worklist"))
        layout.addWidget(self.imaging_status_label)
        layout.addLayout(imaging_controls)
        layout.addLayout(imaging_filter_row)
        layout.addWidget(self.imaging_table)

    def _build_operator_mode_page(self) -> None:
        self.operator_mode_page = QWidget()
        self.local_orders_page = self.operator_mode_page

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

        self.previous_day_button = QPushButton("Previous day")
        self.previous_day_button.clicked.connect(lambda: self._shift_selected_date(-1))
        self.next_day_button = QPushButton("Next day")
        self.next_day_button.clicked.connect(lambda: self._shift_selected_date(1))
        self.today_button = QPushButton("Today")
        self.today_button.clicked.connect(self._select_today)
        self.date_selector = QDateEdit()
        self.date_selector.setCalendarPopup(True)
        self.date_selector.setDisplayFormat("yyyy-MM-dd")
        self.date_selector.setDate(
            QDate(self._selected_date.year, self._selected_date.month, self._selected_date.day)
        )
        self.date_selector.dateChanged.connect(self._on_date_changed)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Worklist date"))
        date_row.addWidget(self.previous_day_button)
        date_row.addWidget(self.date_selector)
        date_row.addWidget(self.next_day_button)
        date_row.addWidget(self.today_button)
        date_row.addStretch()

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

        self.worklist_table = QTableWidget(0, len(self.WORKLIST_COLUMNS))
        self.worklist_table.setHorizontalHeaderLabels(self.WORKLIST_COLUMNS)
        self.worklist_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.worklist_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.worklist_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.filter_buttons: dict[str, QPushButton] = {}
        filter_bar = QHBoxLayout()
        for key, label in (
            ("active", "Active"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
            ("error", "Error"),
            ("all", "All"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(self._make_filter_handler(key))
            self.filter_buttons[key] = button
            filter_bar.addWidget(button)
        filter_bar.addStretch()
        self.filter_bar = filter_bar

        self.refresh_button = QPushButton("Load from KaosEghis")
        self.refresh_button.clicked.connect(self.refresh_rows)
        self.check_kaospacs_button = QPushButton("Check KaosPACS")
        self.check_kaospacs_button.clicked.connect(self.check_kaospacs_connection)
        self.poll_button = QPushButton("Load from eGHIS")
        self.poll_button.clicked.connect(self.poll_now)
        self.sync_button = QPushButton("Sync to KaosPACS")
        self.sync_button.clicked.connect(self.sync_to_kaospacs)
        self.reconcile_button = QPushButton("Sync from KaosPACS")
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

        self.audit_filter_combo = QComboBox()
        self.audit_filter_combo.addItems(
            ["All", "poll", "manual_insert", "manual_edit", "cancel_selected", "sync", "reconcile", "error"]
        )
        self.audit_filter_combo.currentTextChanged.connect(self.refresh_audit)
        self.refresh_audit_button = QPushButton("Refresh log")
        self.refresh_audit_button.clicked.connect(self.refresh_audit)
        self.clear_audit_button = QPushButton("Clear log")
        self.clear_audit_button.clicked.connect(self.clear_audit)
        self.copy_audit_button = QPushButton("Copy log summary")
        self.copy_audit_button.clicked.connect(self.copy_audit_summary)

        self.audit_table = QTableWidget(0, len(self.AUDIT_COLUMNS))
        self.audit_table.setHorizontalHeaderLabels(self.AUDIT_COLUMNS)
        self.audit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.audit_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.audit_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("PACS Log"))
        controls.addWidget(self.audit_filter_combo)
        controls.addWidget(self.refresh_audit_button)
        controls.addWidget(self.clear_audit_button)
        controls.addWidget(self.copy_audit_button)
        controls.addStretch()

        layout = QVBoxLayout(self.operator_mode_page)
        layout.addWidget(QLabel("Operator Mode / Local Orders"))
        layout.addLayout(status_row)
        layout.addLayout(polling_info_row)
        layout.addLayout(date_row)
        layout.addLayout(polling_settings_row)
        layout.addWidget(self.worklist_table)
        layout.addLayout(self.filter_bar)
        layout.addLayout(action_row)
        layout.addWidget(footer)
        layout.addSpacing(12)
        layout.addLayout(controls)
        layout.addWidget(self.audit_table)

    def _build_settings_page(self) -> None:
        self.settings_page = QWidget()
        self.diagnostics_sqlite_label = QLabel()
        self.diagnostics_api_base_url_label = QLabel()
        self.diagnostics_gateway_url_label = QLabel()
        self.diagnostics_dry_run_label = QLabel()
        self.diagnostics_command_note_label = QLabel(
            "Diagnostics: pacs poll helper is available via KaosEghis tools when needed."
        )

        form = QFormLayout()
        form.addRow("Active SQLite path", self.diagnostics_sqlite_label)
        form.addRow("KaosPACS API base URL", self.diagnostics_api_base_url_label)
        form.addRow("KaosPACS Gateway URL", self.diagnostics_gateway_url_label)
        form.addRow("Dry-run status", self.diagnostics_dry_run_label)

        layout = QVBoxLayout(self.settings_page)
        layout.addWidget(QLabel("Settings / Diagnostics"))
        layout.addLayout(form)
        layout.addWidget(self.diagnostics_command_note_label)
        layout.addStretch()

    def _make_page_button(self, label: str, page_name: str) -> QPushButton:
        button = QPushButton(label)
        button.setCheckable(True)
        button.clicked.connect(lambda: self._show_page(page_name))
        self.page_buttons[page_name] = button
        return button

    def _show_page(self, page_name: str) -> None:
        index = self._page_names.index(page_name)
        self.page_stack.setCurrentIndex(index)
        for key, button in self.page_buttons.items():
            selected = key == page_name
            button.setChecked(selected)
            button.setProperty("pageActive", selected)
            button.setStyleSheet(
                self.FILTER_BUTTON_SELECTED_STYLE if selected else self.FILTER_BUTTON_UNSELECTED_STYLE
            )

        if page_name == "imaging":
            return
        if page_name == "operator_mode":
            self.refresh_rows()
            self.refresh_audit()
        elif page_name == "settings":
            self._refresh_settings_diagnostics()

    def _set_db_labels(self) -> None:
        self.eghis_db_status.setText("Eghis DB: checking...")
        initialize_database(self._db_path)
        self.pacs_server_status.setText("KaosPACS server: checking...")

    def _refresh_startup_connection_statuses(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        self._refresh_kaospacs_status(settings)
        self._refresh_eghis_db_status(settings)

    def _refresh_kaospacs_status(self, settings: dict[str, str] | None = None) -> None:
        if settings is None:
            initialize_database(self._db_path)
            with connect(self._db_path) as connection:
                settings = get_settings(connection)
        try:
            healthy = check_kaospacs_health(settings)
        except RuntimeError:
            healthy = False
        self._kaospacs_available = healthy
        self.pacs_server_status.setText(
            "KaosPACS server: healthy" if healthy else "KaosPACS server: unavailable"
        )
        self._emit_health_state()

    def _refresh_eghis_db_status(self, settings: dict[str, str]) -> None:
        connection_string = (settings.get("eghis_db_connection_string") or "").strip()
        if not connection_string:
            self._eghis_db_available = False
            self.eghis_db_status.setText("Eghis DB: not configured")
            self._emit_health_state()
            return

        try:
            run_readonly_query(connection_string, "SELECT 1")
        except (EghisDbUnavailableError, EghisDbQueryRejectedError, RuntimeError):
            self._eghis_db_available = False
            self.eghis_db_status.setText("Eghis DB: unavailable")
            self._emit_health_state()
            return

        self._eghis_db_available = True
        self.eghis_db_status.setText("Eghis DB: healthy")
        self._emit_health_state()

    def refresh_imaging_worklist(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
        try:
            entries = get_imaging_worklist(settings)
        except RuntimeError:
            self._imaging_entries_all = []
            self._visible_imaging_entries = []
            self.imaging_table.setRowCount(0)
            self.imaging_status_label.setText("KaosPACS Gateway unavailable")
            return

        self._imaging_entries_all = entries
        self.imaging_status_label.setText(
            f"KaosPACS Gateway imaging rows: {len(entries)}"
        )
        self._refresh_imaging_table()

    def _refresh_imaging_table(self) -> None:
        search_value = self.imaging_search_input.text().strip().lower()
        visible = []
        for entry in self._imaging_entries_all:
            state = self._imaging_entry_state(entry)
            if self._imaging_filter != "all" and state != self._imaging_filter:
                continue
            if search_value and not self._matches_imaging_search(entry, search_value):
                continue
            visible.append(entry)

        self._visible_imaging_entries = visible
        self.imaging_table.setRowCount(len(visible))
        for row_index, entry in enumerate(visible):
            values = [
                self._imaging_entry_state(entry),
                self._entry_text(entry, "AccessionNumber"),
                self._entry_text(entry, "PatientID"),
                self._entry_text(entry, "PatientName"),
                self._entry_text(entry, "PatientBirthDate"),
                self._entry_text(entry, "PatientSex"),
                self._entry_text(entry, "Modality"),
                self._entry_text(entry, "ScheduledStationAETitle"),
                self._entry_text(entry, "ScheduledAt"),
                self._imaging_description(entry),
                self._entry_text(entry, "CompletedAt"),
                self._entry_text(entry, "ExpiredAt"),
                self._entry_text(entry, "ExpireReason"),
                self._entry_text(entry, "CancelledAt"),
                self._entry_text(entry, "CancelReason"),
            ]
            for col_index, value in enumerate(values):
                self.imaging_table.setItem(row_index, col_index, QTableWidgetItem(value))
        self.imaging_table.resizeColumnsToContents()

    def _make_imaging_filter_handler(self, state: str):
        def handler() -> None:
            self._imaging_filter = state
            self._update_imaging_filter_button_states()
            self._refresh_imaging_table()

        return handler

    def _update_imaging_filter_button_states(self) -> None:
        for key, button in self.imaging_filter_buttons.items():
            is_selected = key == self._imaging_filter
            button.setChecked(is_selected)
            button.setProperty("filterActive", is_selected)
            button.setStyleSheet(
                self.FILTER_BUTTON_SELECTED_STYLE
                if is_selected
                else self.FILTER_BUTTON_UNSELECTED_STYLE
            )

    def _matches_imaging_search(self, entry: dict, search_value: str) -> bool:
        fields = [
            self._entry_text(entry, "PatientName"),
            self._entry_text(entry, "PatientID"),
            self._entry_text(entry, "AccessionNumber"),
            self._entry_text(entry, "Modality"),
        ]
        return any(search_value in value.lower() for value in fields if value)

    def _entry_text(self, entry: dict, key: str) -> str:
        value = entry.get(key)
        if value is None:
            return ""
        return str(value).strip()

    def _imaging_description(self, entry: dict) -> str:
        return (
            self._entry_text(entry, "Description")
            or self._entry_text(entry, "ScheduledProcedureStepDescription")
            or self._entry_text(entry, "RequestedProcedureDescription")
        )

    def _imaging_entry_state(self, entry: dict) -> str:
        state = self._entry_text(entry, "state").lower()
        if state:
            return state
        if self._entry_text(entry, "CancelledAt"):
            return "cancelled"
        if self._entry_text(entry, "ExpiredAt"):
            return "expired"
        if self._entry_text(entry, "CompletedAt"):
            return "completed"
        return "active"

    def _make_filter_handler(self, status: str):
        def handler() -> None:
            self._active_filter = status
            self._update_local_filter_button_states()
            self.refresh_rows()

        return handler

    def _load_visible_items(self) -> list[PacsWorklistItemRecord]:
        initialize_database(self._db_path)
        status_filter = None if self._active_filter == "all" else self._active_filter

        with connect(self._db_path) as connection:
            items = list_pacs_worklist_items(connection, status_filter)
        return [
            item
            for item in items
            if self._requested_at_matches_selected_date(item.requested_at)
        ]

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

    def refresh_audit(self) -> None:
        initialize_database(self._db_path)
        event_type = self.audit_filter_combo.currentText()
        selected_event_type = None if event_type == "All" else event_type
        with connect(self._db_path) as connection:
            events = list_pacs_audit_events(connection, limit=100, event_type=selected_event_type)

        self._visible_audit_events = events
        self.audit_table.setRowCount(len(events))
        for row_index, event in enumerate(events):
            row = [
                event.created_at,
                event.event_type,
                event.accession_or_order_id or "",
                event.status_before or "",
                event.status_after or "",
                event.summary,
                event.error_message or "",
            ]
            for col_index, value in enumerate(row):
                self.audit_table.setItem(row_index, col_index, QTableWidgetItem(value))
        self.audit_table.resizeColumnsToContents()

    def check_kaospacs_connection(self) -> None:
        self._refresh_startup_connection_statuses()

    def poll_now(self) -> None:
        self._run_poll(refresh_imaging=True)

    def sync_to_kaospacs(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
            items = list_pacs_worklist_items(connection)

        sync_summary = self._build_sync_summary(items)
        if sync_summary["active_rows"] > 0 and not self._confirm_sync(sync_summary):
            self.polling_status.setText("KaosPACS sync: canceled")
            return

        result = sync_local_worklist_to_kaospacs(settings, self._db_path)
        self.refresh_rows()
        dry_run_prefix = "KaosPACS sync (DRY RUN): " if result.dry_run else "KaosPACS sync: "
        summary = (
            f"{dry_run_prefix}"
            f"active rows={sync_summary['active_rows']}, "
            f"cancelled pending rows={sync_summary['cancelled_pending_rows']}, "
            f"sent={result.sent}, cancelled={result.cancelled}, "
            f"errors={result.errors}, skipped={result.skipped}"
        )
        self.polling_status.setText(summary)
        self._log_audit_aggregate(
            event_type="sync",
            summary=self._prefix_dry_run_summary(
                result.dry_run,
                f"sent={result.sent}, cancelled={result.cancelled}, "
                f"errors={result.errors}, skipped={result.skipped}",
            ),
        )
        self.refresh_audit()
        self._schedule_imaging_refresh()

    def reconcile_from_kaospacs(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)

        result = reconcile_kaospacs_worklist_to_local(settings, self._db_path)
        self.refresh_rows()
        if result.message is not None:
            prefix = "KaosPACS reconcile (DRY RUN)" if result.dry_run else "KaosPACS reconcile"
            self.polling_status.setText(f"{prefix}: {result.message}")
            self._log_audit_error(
                summary="reconcile failed",
                error_message=result.message,
                dry_run=result.dry_run,
            )
            self.refresh_audit()
            self._schedule_imaging_refresh()
            return
        summary = (
            f"{'KaosPACS reconcile (DRY RUN): ' if result.dry_run else 'KaosPACS reconcile: '}"
            f"completed={result.completed}, expired={result.expired}, "
            f"skipped={result.skipped}, errors={result.errors}"
        )
        self.polling_status.setText(summary)
        self._log_audit_aggregate(
            event_type="reconcile",
            summary=self._prefix_dry_run_summary(
                result.dry_run,
                f"completed={result.completed}, expired={result.expired}, "
                f"skipped={result.skipped}, errors={result.errors}",
            ),
        )
        self.refresh_audit()
        self._schedule_imaging_refresh()

    def manual_insert_row(self) -> None:
        dialog = PacsWorklistDialog(self)
        if dialog.exec() != PacsWorklistDialog.DialogCode.Accepted:
            return

        payload = dialog.get_form_data()
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            created = create_pacs_worklist_item(
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
            create_pacs_audit_event(
                connection,
                event_type="manual_insert",
                worklist_item_id=created.id,
                accession_or_order_id=created.accession_or_order_id,
                status_before=None,
                status_after=created.status,
                summary="manual local worklist row created",
            )
        self.refresh_rows()
        self.refresh_audit()

    def edit_selected(self) -> None:
        item = self._selected_visible_item()
        if item is None:
            return

        dialog = PacsWorklistDialog(self, item=item)
        if dialog.exec() != PacsWorklistDialog.DialogCode.Accepted:
            return

        payload = dialog.get_form_data()
        with connect(self._db_path) as connection:
            updated = update_pacs_worklist_item(
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
            if updated is not None:
                create_pacs_audit_event(
                    connection,
                    event_type="manual_edit",
                    worklist_item_id=updated.id,
                    accession_or_order_id=updated.accession_or_order_id,
                    status_before=item.status,
                    status_after=updated.status,
                    summary="manual local worklist row updated",
                )
        self.refresh_rows()
        self.refresh_audit()

    def delete_selected(self) -> None:
        item = self._selected_visible_item()
        if item is None:
            return

        with connect(self._db_path) as connection:
            if update_pacs_worklist_status(connection, item.id, "cancelled"):
                create_pacs_audit_event(
                    connection,
                    event_type="cancel_selected",
                    worklist_item_id=item.id,
                    accession_or_order_id=item.accession_or_order_id,
                    status_before=item.status,
                    status_after="cancelled",
                    summary="selected local worklist row marked cancelled",
                )
        self.refresh_rows()
        self.refresh_audit()

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
        self._refresh_settings_diagnostics()

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
        self._run_poll(refresh_imaging=True, is_auto_poll=True)

    def _run_poll(self, *, refresh_imaging: bool = False, is_auto_poll: bool = False) -> None:
        if self._poll_in_progress:
            self.last_poll_result_label.setText("Last poll result: skipped overlap")
            self.polling_status.setText("Polling status: skipped overlap")
            self._log_audit_aggregate(event_type="poll", summary="skipped overlap")
            self.refresh_audit()
            return

        self._poll_in_progress = True
        try:
            initialize_database(self._db_path)
            with connect(self._db_path) as connection:
                settings = get_settings(connection)

            self._refresh_kaospacs_status(settings)
            self._refresh_eghis_db_status(settings)
            if is_auto_poll and (not self._kaospacs_available or not self._eghis_db_available):
                self._poll_timer.stop()
                self.polling_status.setText(f"Auto poll stopped: {self._health_reason}")
                self.last_poll_result_label.setText(
                    f"Last poll result: auto poll stopped - {self._health_reason}"
                )
                return

            result = poll_eghis_image_orders_into_local_worklist(
                settings,
                self._db_path,
                selected_date=self._selected_date,
            )
            self.refresh_rows()
            self.last_poll_time_label.setText(
                f"Last poll time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            if result.message is not None:
                self.last_poll_result_label.setText(f"Last poll result: {result.message}")
                self.polling_status.setText(f"Polling status: {result.message}")
                self._log_audit_aggregate(event_type="poll", summary=result.message)
                self.refresh_audit()
                return
            summary = (
                f"inserted={result.inserted}, updated={result.updated}, skipped={result.skipped}"
            )
            self.last_poll_result_label.setText(f"Last poll result: {summary}")
            self.polling_status.setText(f"Polling status: {summary}")
            self._log_audit_aggregate(event_type="poll", summary=summary)
            self.refresh_audit()
            if refresh_imaging:
                self._schedule_imaging_refresh()
        finally:
            self._poll_in_progress = False

    def _schedule_imaging_refresh(self) -> None:
        self.imaging_status_label.setText(
            f"Waiting {self.IMAGING_REFRESH_DELAY_MS} ms before imaging refresh..."
        )
        QTimer.singleShot(self.IMAGING_REFRESH_DELAY_MS, self.refresh_imaging_worklist)

    @property
    def is_healthy(self) -> bool:
        return self._kaospacs_available and self._eghis_db_available

    @property
    def health_reason(self) -> str:
        return self._health_reason

    def _emit_health_state(self) -> None:
        if not self._kaospacs_available:
            reason = "KaosPACS unavailable"
        elif not self._eghis_db_available:
            reason = "Eghis DB unavailable"
        else:
            reason = "PACS healthy"
        self._health_reason = reason
        self.health_state_changed.emit(self.is_healthy, reason)

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

    def _update_startup_readiness_status(self) -> None:
        self.polling_status.setText(self._build_startup_readiness())

    def _build_startup_readiness(self) -> str:
        try:
            initialize_database(self._db_path)
            with connect(self._db_path) as connection:
                settings = get_settings(connection)
        except Exception:
            return "Startup readiness: configuration unavailable"

        auto_poll_enabled = self._parse_auto_poll_enabled(
            settings.get("pacs_auto_poll_enabled")
        )
        interval_seconds = self._normalize_poll_interval(
            settings.get("pacs_poll_interval_seconds")
        )
        dry_run_enabled = (settings.get("pacs_dry_run") or "").strip().lower() == "true"
        return (
            "Startup readiness: sqlite=ok, settings=ok, "
            f"db={describe_database_path(self._db_path)}, "
            f"auto_poll={'on' if auto_poll_enabled else 'off'}, "
            f"interval={interval_seconds}s, dry_run={'on' if dry_run_enabled else 'off'}"
        )

    def _refresh_settings_diagnostics(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            settings = get_settings(connection)
        self.diagnostics_sqlite_label.setText(describe_database_path(self._db_path))
        self.diagnostics_api_base_url_label.setText(settings.get("kaospacs_api_base_url", ""))
        self.diagnostics_gateway_url_label.setText(settings.get("kaospacs_gateway_url", ""))
        self.diagnostics_dry_run_label.setText(
            "on" if (settings.get("pacs_dry_run") or "").strip().lower() == "true" else "off"
        )

    def _shift_selected_date(self, days: int) -> None:
        self._set_selected_date(self._selected_date + timedelta(days=days))

    def _select_today(self) -> None:
        self._set_selected_date(date.today())

    def _on_date_changed(self, selected: QDate) -> None:
        self._selected_date = date(selected.year(), selected.month(), selected.day())
        self.refresh_rows()

    def _set_selected_date(self, selected: date) -> None:
        self._selected_date = selected
        self.date_selector.blockSignals(True)
        self.date_selector.setDate(QDate(selected.year, selected.month, selected.day))
        self.date_selector.blockSignals(False)
        self.refresh_rows()

    def _requested_at_matches_selected_date(self, requested_at: str | None) -> bool:
        if requested_at is None:
            return False
        digits = re.sub(r"[^0-9]", "", requested_at)
        if len(digits) < 8:
            return False
        return digits[:8] == self._selected_date.strftime("%Y%m%d")

    def _update_local_filter_button_states(self) -> None:
        for key, button in self.filter_buttons.items():
            is_selected = key == self._active_filter
            button.setChecked(is_selected)
            button.setProperty("filterActive", is_selected)
            button.setStyleSheet(
                self.FILTER_BUTTON_SELECTED_STYLE
                if is_selected
                else self.FILTER_BUTTON_UNSELECTED_STYLE
            )

    def clear_audit(self) -> None:
        confirmed = QMessageBox.question(
            self,
            "Clear PACS Log",
            "Clear local PACS log events?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        with connect(self._db_path) as connection:
            clear_pacs_audit_events(connection)
        self.refresh_audit()

    def copy_audit_summary(self) -> None:
        lines = []
        for event in self._visible_audit_events:
            lines.append(
                " | ".join(
                    [
                        event.created_at,
                        event.event_type,
                        event.accession_or_order_id or "",
                        event.status_before or "",
                        event.status_after or "",
                        event.summary,
                        event.error_message or "",
                    ]
                ).strip()
            )
        copy_text("\n".join(lines))

    def _log_audit_aggregate(self, *, event_type: str, summary: str) -> None:
        with connect(self._db_path) as connection:
            create_pacs_audit_event(
                connection,
                event_type=event_type,
                summary=self._sanitize_audit_summary(summary),
            )

    def _log_audit_error(
        self,
        *,
        summary: str,
        error_message: str,
        dry_run: bool = False,
    ) -> None:
        sanitized_error = self._sanitize_audit_error(error_message)
        with connect(self._db_path) as connection:
            create_pacs_audit_event(
                connection,
                event_type="error",
                summary=self._prefix_dry_run_summary(dry_run, sanitized_error),
                error_message=sanitized_error,
            )

    @staticmethod
    def _sanitize_audit_summary(summary: str) -> str:
        normalized = " ".join((summary or "").split())
        if not normalized:
            return "unknown error"

        if "=" in normalized and all(
            token.strip() and "=" in token for token in normalized.split(",")
        ):
            return normalized

        lowered = normalized.lower()
        safe_phrases = {
            "manual local worklist row created",
            "manual local worklist row updated",
            "selected local worklist row marked cancelled",
            "skipped overlap",
        }
        if lowered in safe_phrases:
            return lowered

        return PacsPanel._sanitize_audit_error(normalized)

    @staticmethod
    def _sanitize_audit_error(error_message: str | None) -> str:
        lowered = (error_message or "").strip().lower()
        if not lowered:
            return "unknown error"
        if "timeout" in lowered or "timed out" in lowered:
            return "timeout"
        if any(
            token in lowered
            for token in (
                "connection",
                "connect",
                "refused",
                "unreachable",
                "dns",
                "network",
                "socket",
            )
        ):
            return "connection failed"
        if any(
            token in lowered
            for token in (
                "invalid payload",
                "invalid json",
                "bad payload",
                "missing field",
                "malformed",
                "schema",
                "decode",
                "parse",
            )
        ):
            return "invalid payload"
        if any(
            token in lowered
            for token in (
                "unavailable",
                "not available",
                "query rejected",
                "driver missing",
                "not configured",
                "unsupported",
            )
        ):
            return "unavailable"
        return "unknown error"

    @staticmethod
    def _prefix_dry_run_summary(dry_run: bool, summary: str) -> str:
        if dry_run:
            return f"DRY RUN - {summary}"
        return summary
