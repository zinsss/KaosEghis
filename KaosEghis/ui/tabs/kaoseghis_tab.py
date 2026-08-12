from __future__ import annotations

from datetime import datetime
import random
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QEvent, QEventLoop, QPoint, QTimer, Qt, Signal, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.clipboard_service import copy_text
from KaosEghis.core.macro_runner import MacroRunner
from KaosEghis.ui.drag_hover_switch import ButtonFileHoverFilter
from KaosEghis.ui.launcher_agenda_panel import AgendaSuppliesPanel
from KaosEghis.core.eghis_connector import (
    build_connector_settings,
    clear_cached_eghis_state,
    get_cached_eghis_state,
    refresh_cached_eghis_state,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    LAUNCHER_SECTIONS,
    create_item,
    create_macro_step,
    delete_item,
    delete_macro_steps_for_item,
    delete_launcher_collection,
    get_active_emr_target_profile,
    get_item,
    get_launcher_collection,
    get_launcher_collection_for_item,
    get_launcher_collection_for_macro,
    list_clipboard_variants,
    list_launcher_collection_members,
    list_launcher_collections,
    list_launcher_entries,
    list_items,
    list_launcher_items,
    add_item_to_launcher_collection,
    add_macro_to_launcher_collection,
    create_launcher_collection,
    list_macro_steps,
    get_settings,
    rename_launcher_collection,
    reorder_launcher_collection_members,
    reorder_macro_items,
    remove_item_from_launcher_collection,
    resolve_macro_emr_target_profile,
    remove_macro_from_launcher_collection,
    reorder_macro_steps,
    replace_clipboard_variants,
    set_setting,
    update_launcher_collection_placement,
    update_item_launcher_placement,
    update_item,
)
from KaosEghis.ui.tabs.eghis_assist_tab import MacroEditorDialog
from KaosEghis.ui.tabs.emr_targets_page import EmrTargetsPage
from KaosEghis.ui.tabs.flu_report_tab import FluReportTab
from KaosEghis.ui.tabs.service_web_tab import ServiceWebTab
from KaosEghis.ui.tabs.scan_tab import ScanTab
from KaosEghis.ui.tabs.scheduler_tab import SchedulerTab
from KaosEghis.ui.tabs.socl_tab import SoclTab
from KaosEghis.ui.tabs.vaccine_tab import VaccineTab
from KaosEghis.config import DEFAULT_CONFIG


DYNAMIC_CURRENT_DATE_MACROTEXT_ID = -1
FETCH_PATIENT_INFO_FOR_VACCINATION_ACTION_ID = -100


class PlaceholderPage(QWidget):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()

        page_title = QLabel(title)
        page_title.setObjectName("pageTitle")
        description = QLabel(message)
        description.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(page_title)
        layout.addWidget(description)
        layout.addStretch()


class KaosEghisTab(QWidget):
    TOP_PAGES = ["Launcher + Agenda", "SOCL", "Procedures", "Vaccine"]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        self.nav_buttons: dict[str, QPushButton] = {}
        self.top_nav_row = QHBoxLayout()
        self.stacked_widget = QStackedWidget()

        self.launcher_page = LauncherPage(db_path)
        self.socl_page = SoclTab(db_path)
        self.procedures_page = PlaceholderPage(
            "Procedures",
            "Procedures page is not implemented yet.",
        )
        self.vaccine_page = VaccineTab(db_path)

        for page in (
            self.launcher_page,
            self.socl_page,
            self.procedures_page,
            self.vaccine_page,
        ):
            self.stacked_widget.addWidget(page)

        for index, name in enumerate(self.TOP_PAGES):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setAcceptDrops(True)
            button.clicked.connect(
                lambda _checked=False, page_index=index: self.show_page(page_index)
            )
            self.nav_buttons[name] = button
            self.top_nav_row.addWidget(button)
        self.top_nav_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(self.top_nav_row)
        layout.addWidget(self.stacked_widget)

        self.show_page(0)

    def show_page(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        for button_index, name in enumerate(self.TOP_PAGES):
            self.nav_buttons[name].setChecked(button_index == index)

        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, "activate_page"):
            current_widget.activate_page()
        if hasattr(current_widget, "refresh_view"):
            current_widget.refresh_view()


class MacrosTab(QWidget):
    TOP_PAGES = ["Builder", "PresetText", "EMR", "Scheduler"]

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        scheduler_runtime=None,
    ) -> None:
        super().__init__()
        self._db_path = db_path
        self.nav_buttons: dict[str, QPushButton] = {}
        self.top_nav_row = QHBoxLayout()
        self.stacked_widget = QStackedWidget()

        self.builder_page = MacrosPage(db_path)
        self.macrotexts_page = MacroTextsPage(db_path)
        self.emr_page = EmrTargetsPage(db_path)
        self.scheduler_page = SchedulerTab(db_path, runtime=scheduler_runtime)

        self.presets_page = self.macrotexts_page

        for page in (
            self.builder_page,
            self.macrotexts_page,
            self.emr_page,
            self.scheduler_page,
        ):
            self.stacked_widget.addWidget(page)

        for index, name in enumerate(self.TOP_PAGES):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setAcceptDrops(True)
            button.clicked.connect(
                lambda _checked=False, page_index=index: self.show_page(page_index)
            )
            self.nav_buttons[name] = button
            self.top_nav_row.addWidget(button)
        self.top_nav_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(self.top_nav_row)
        layout.addWidget(self.stacked_widget)

        self.show_page(0)

    def show_page(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        for button_index, name in enumerate(self.TOP_PAGES):
            self.nav_buttons[name].setChecked(button_index == index)

        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, "activate_page"):
            current_widget.activate_page()
        if hasattr(current_widget, "refresh_view"):
            current_widget.refresh_view()


class WorkspaceTab(QWidget):
    TOP_PAGES = ["Mail", "Paperless", "PDF", "rHWP", "Flu-Report", "Scan"]

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self.nav_buttons: dict[str, QPushButton] = {}
        self._file_hover_filters: list[ButtonFileHoverFilter] = []
        self.top_nav_row = QHBoxLayout()
        self.stacked_widget = QStackedWidget()

        self.mail_page = PlaceholderPage("Mail", "Mail page is not implemented yet.")
        self.paperless_page = ServiceWebTab(
            profile_name="Paperless",
            setting_key="paperless_url",
            default_url=DEFAULT_CONFIG.paperless_url,
            fallback_text="Paperless webview not available.",
            db_path=db_path,
        )
        self.pdf_page = ServiceWebTab(
            profile_name="StirlingPDF",
            setting_key="stirling_pdf_url",
            default_url=DEFAULT_CONFIG.stirling_pdf_url,
            fallback_text="Stirling-PDF webview not available.",
            db_path=db_path,
        )
        self.rhwp_page = ServiceWebTab(
            profile_name="RHWP",
            setting_key="rhwp_url",
            default_url=DEFAULT_CONFIG.rhwp_url,
            fallback_text="rHWP webview not available.",
            db_path=db_path,
        )
        self.flu_report_page = FluReportTab()
        self.scan_page = ScanTab(db_path)

        for page in (
            self.mail_page,
            self.paperless_page,
            self.pdf_page,
            self.rhwp_page,
            self.flu_report_page,
            self.scan_page,
        ):
            self.stacked_widget.addWidget(page)

        for index, name in enumerate(self.TOP_PAGES):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setAcceptDrops(True)
            button.clicked.connect(
                lambda _checked=False, page_index=index: self.show_page(page_index)
            )
            hover_filter = ButtonFileHoverFilter(self.show_page, index)
            button.installEventFilter(hover_filter)
            self._file_hover_filters.append(hover_filter)
            self.nav_buttons[name] = button
            self.top_nav_row.addWidget(button)
        self.top_nav_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(self.top_nav_row)
        layout.addWidget(self.stacked_widget)

        self.show_page(0)

    def show_page(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        for button_index, name in enumerate(self.TOP_PAGES):
            self.nav_buttons[name].setChecked(button_index == index)

        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, "activate_page"):
            current_widget.activate_page()
        if hasattr(current_widget, "refresh_view"):
            current_widget.refresh_view()


class LauncherPage(QWidget):
    ENTRY_ID_ROLE = LauncherListWidget.ITEM_ID_ROLE if "LauncherListWidget" in globals() else 256
    ENTRY_KIND_ROLE = 258
    ITEM_TYPE_ROLE = LauncherListWidget.ITEM_TYPE_ROLE if "LauncherListWidget" in globals() else 257
    LAUNCHER_COLUMN_STRETCH = 1
    AGENDA_COLUMN_STRETCH = 3

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path
        self._startup_auto_connect_attempted = False

        title = QLabel("Launcher")
        title.setObjectName("pageTitle")

        self.connection_toggle = QPushButton("Connect EMR")
        self.connection_toggle.setCheckable(True)
        self.connection_toggle.toggled.connect(self.toggle_connection)
        self.connection_status_label = QLabel("EMR: disconnected.")

        connection_row = QHBoxLayout()
        connection_row.addWidget(self.connection_toggle)
        connection_row.addWidget(self.connection_status_label, 1)
        connection_row.addStretch()

        self.launcher_lists: dict[str, LauncherListWidget] = {}
        columns = QGridLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setHorizontalSpacing(12)
        for index, section in enumerate(LAUNCHER_SECTIONS):
            section_label = QLabel(section)
            section_label.setObjectName("launcherSectionTitle")
            section_list = LauncherListWidget(section, self)
            section_list.itemDoubleClicked.connect(
                lambda item, list_widget=section_list: self.activate_launcher_item(
                    list_widget, item
                )
            )
            self.launcher_lists[section] = section_list
            columns.addWidget(section_label, 0, index)
            columns.addWidget(section_list, 1, index)
            columns.setColumnStretch(index, self.LAUNCHER_COLUMN_STRETCH)

        notes_index = len(LAUNCHER_SECTIONS)
        self.agenda_label = QLabel("Agenda / Supplies")
        self.agenda_label.setObjectName("launcherSectionTitle")
        self.agenda_panel = AgendaSuppliesPanel()
        columns.addWidget(self.agenda_label, 0, notes_index)
        columns.addWidget(self.agenda_panel, 1, notes_index)
        columns.setColumnStretch(notes_index, self.AGENDA_COLUMN_STRETCH)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)
        self.dry_run_button = QPushButton("Dry run")
        self.dry_run_button.clicked.connect(self.dry_run_macro)
        self.run_macro_button = QPushButton("Run selected macro")
        self.run_macro_button.clicked.connect(self.run_macro)

        controls = QHBoxLayout()
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.dry_run_button)
        controls.addWidget(self.run_macro_button)
        controls.addStretch()

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Macro status will appear here.")
        self.log.setFixedHeight(72)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(connection_row)
        layout.addLayout(columns, 1)
        layout.addLayout(controls)
        layout.addWidget(self.log)

        self.refresh_view()
        self._attempt_startup_auto_connect()

    def refresh_view(self) -> None:
        launcher_entries = _load_launcher_entries(self._db_path)
        self._populate_launcher_lists(launcher_entries)
        self._refresh_connection_status()

    def activate_page(self) -> None:
        self.agenda_panel.ensure_loaded()

    def toggle_connection(self, checked: bool) -> None:
        if checked:
            self.connect_active_profile()
            return
        clear_cached_eghis_state()
        self._refresh_connection_status()
        self.log.setPlainText("EMR disconnected.")

    def connect_active_profile(self, *, silent: bool = False) -> bool:
        settings = self._active_profile_connector_settings()
        if settings is None:
            self._set_toggle_checked(False)
            if not silent:
                self.log.setPlainText("No enabled EMR profile is available.")
            self._refresh_connection_status()
            return False

        state = refresh_cached_eghis_state(settings, eager_grid_cache=True)
        connected = state.status in {"green", "yellow"} and state.pid is not None
        self._set_toggle_checked(connected)
        self._refresh_connection_status()
        if not silent or connected:
            self.log.setPlainText(state.message)
        return connected

    def _attempt_startup_auto_connect(self) -> None:
        if self._startup_auto_connect_attempted:
            return
        self._startup_auto_connect_attempted = True
        state = get_cached_eghis_state()
        if state is not None and state.status in {"green", "yellow"} and state.pid is not None:
            self._refresh_connection_status()
            return
        try:
            self.connect_active_profile(silent=True)
        except Exception:
            self._set_toggle_checked(False)
            self._refresh_connection_status()

    def _active_profile_connector_settings(self) -> dict[str, str] | None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = get_active_emr_target_profile(connection)
            settings = get_settings(connection)
        if profile is None:
            return None
        return build_connector_settings(
            settings,
            process_name=profile.process_name or settings.get("eghis_process_name"),
            window_title_contains=profile.window_title_contains
            or settings.get("eghis_window_title_contains"),
            executable_path=profile.executable_path or settings.get("eghis_executable_path"),
            main_window_automation_id=getattr(profile, "main_window_automation_id", None)
            or settings.get("eghis_main_window_automation_id"),
            patient_status_tab_automation_id=getattr(profile, "patient_status_tab_automation_id", None)
            or settings.get("eghis_patient_status_tab_automation_id")
            or "tabProc",
            prescription_grid_automation_id=getattr(profile, "prescription_grid_automation_id", None)
            or settings.get("eghis_prescription_grid_automation_id")
            or "tree처방",
            symptom_grid_automation_id=getattr(profile, "symptom_grid_automation_id", None)
            or settings.get("eghis_symptom_grid_automation_id")
            or "grdSymp",
            diagnosis_grid_automation_id=getattr(profile, "diagnosis_grid_automation_id", None)
            or settings.get("eghis_diagnosis_grid_automation_id")
            or "tree상병",
            patient_list_grid_automation_id=getattr(profile, "patient_list_grid_automation_id", None)
            or settings.get("eghis_patient_list_grid_automation_id")
            or "grdOpdList",
        )

    def _refresh_connection_status(self) -> None:
        state = get_cached_eghis_state()
        settings = self._active_profile_connector_settings()
        profile_name = self._active_profile_name()
        if state is None:
            self.connection_status_label.setText(
                f"EMR: disconnected{f' ({profile_name})' if profile_name else ''}."
            )
            self.connection_toggle.setText("Connect EMR")
            self._set_connection_visual_state("disconnected")
            self._set_toggle_checked(False)
            return
        if settings is not None:
            configured_process = (settings.get("eghis_process_name") or "").strip()
            cached_process = (state.process_name or "").strip()
            configured_path = (settings.get("eghis_executable_path") or "").strip()
            cached_path = (state.exe_path or "").strip()
            mismatch = bool(
                (configured_process and cached_process and configured_process.casefold() != cached_process.casefold())
                or (
                    configured_path
                    and cached_path
                    and Path(configured_path).name.casefold() != Path(cached_path).name.casefold()
                )
            )
            if mismatch:
                self.connection_status_label.setText(
                    f"EMR: reconnect required{f' ({profile_name})' if profile_name else ''}."
                )
                self.connection_toggle.setText("Reconnect EMR")
                self._set_connection_visual_state("stale")
                self._set_toggle_checked(False)
                return
        self.connection_status_label.setText(
            f"EMR: {state.message}{f' ({profile_name})' if profile_name else ''}"
        )
        if state.status in {"green", "yellow"}:
            self.connection_toggle.setText("EMR Connected")
            self._set_connection_visual_state("connected")
        else:
            self.connection_toggle.setText("Reconnect EMR")
            self._set_connection_visual_state("stale")
        self._set_toggle_checked(state.status in {"green", "yellow"})

    def _active_profile_name(self) -> str | None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            profile = get_active_emr_target_profile(connection)
        if profile is None:
            return None
        return profile.name

    def _set_toggle_checked(self, checked: bool) -> None:
        self.connection_toggle.blockSignals(True)
        self.connection_toggle.setChecked(checked)
        self.connection_toggle.blockSignals(False)

    def _set_connection_visual_state(self, state: str) -> None:
        self.connection_toggle.setProperty("emrConnectionState", state)
        style = self.connection_toggle.style()
        style.unpolish(self.connection_toggle)
        style.polish(self.connection_toggle)
        self.connection_toggle.update()

    def dry_run_macro(self) -> None:
        entry = self._selected_launcher_entry()
        if entry is None:
            self.log.setPlainText("Select a macro to dry run.")
            return
        if entry["entry_kind"] == "collection":
            self._open_collection(entry["entry_id"], dry_run=True)
            return
        item_id = entry.get("item_id")
        item_type = entry.get("item_type")
        if not isinstance(item_id, int) or item_type != "macro":
            self.log.setPlainText("Select a macro to dry run.")
            return
        result = MacroRunner(self._db_path).execute_macro(item_id, dry_run=True)
        self.log.setPlainText(result.message)

    def run_macro(self) -> None:
        entry = self._selected_launcher_entry()
        if entry is None:
            self.log.setPlainText("Select a macro to run.")
            return
        if entry["entry_kind"] == "collection":
            self._open_collection(entry["entry_id"], dry_run=False)
            return
        item_id = entry.get("item_id")
        item_type = entry.get("item_type")
        if not isinstance(item_id, int) or item_type != "macro":
            self.log.setPlainText("Select a macro to run.")
            return
        self._run_macro_by_id(item_id)

    def activate_launcher_item(
        self,
        list_widget: "LauncherListWidget",
        item: QListWidgetItem,
    ) -> None:
        item_id = item.data(list_widget.ITEM_ID_ROLE)
        item_type = item.data(list_widget.ITEM_TYPE_ROLE)
        entry_kind = item.data(self.ENTRY_KIND_ROLE) or "item"
        if not isinstance(item_id, int):
            return
        list_widget.setCurrentItem(item)
        if entry_kind == "collection":
            self._open_collection(item_id, dry_run=False)
            return
        if item_type == "macro":
            self._run_macro_by_id(item_id)
            return
        if item_type in {"clipboard", "randomized_clipboard"}:
            self._copy_macrotext_by_id(item_id)
            return
        if item_type == "action":
            self._run_launcher_action(item_id)

    # Compatibility name retained for callers that still invoke the old handler.
    def run_macro_from_list(
        self,
        list_widget: "LauncherListWidget",
        item: QListWidgetItem,
    ) -> None:
        self.activate_launcher_item(list_widget, item)

    def _copy_macrotext_by_id(self, item_id: int) -> None:
        success, message = _copy_macrotext(self._db_path, item_id)
        self.log.setPlainText(message)

    def _run_launcher_action(self, item_id: int) -> None:
        if item_id == FETCH_PATIENT_INFO_FOR_VACCINATION_ACTION_ID:
            parent_tab = self.parentWidget()
            if parent_tab is not None and not hasattr(parent_tab, "show_page"):
                parent_tab = parent_tab.parentWidget()
            if hasattr(parent_tab, "show_page"):
                try:
                    parent_tab.show_page(3)
                except Exception:
                    pass
            vaccine_page = getattr(parent_tab, "vaccine_page", None)
            if vaccine_page is None or not hasattr(
                vaccine_page, "fetch_current_patient_from_emr"
            ):
                self.log.setPlainText("Vaccine page is not available.")
                return
            success = vaccine_page.fetch_current_patient_from_emr()
            self.log.setPlainText(
                "Loaded patient context for vaccination."
                if success
                else "Failed to load patient context for vaccination."
            )
            return
        self.log.setPlainText("Action not found.")

    def _activate_collection_item_by_id(self, item_id: int) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = get_item(connection, item_id)
        if item is None:
            self.log.setPlainText("Collection item not found.")
            return
        self._activate_item_record(item)

    def _activate_item_record(self, item) -> None:
        if item.item_type == "macro":
            self._run_macro_by_id(item.id)
            return
        if item.item_type in {"clipboard", "randomized_clipboard"}:
            self._copy_macrotext_by_id(item.id)
            return
        self.log.setPlainText("Launcher item type is not supported.")

    def _run_macro_by_id(self, item_id: int) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = get_item(connection, item_id)
        if item is None:
            self.log.setPlainText("Macro not found.")
            return
        if item.item_type != "macro":
            self.log.setPlainText("Select a macro to run.")
            return

        self.log.setPlainText(f"Running '{item.name}'...")
        application = QApplication.instance()
        if application is not None:
            application.processEvents(
                QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
            )

        result = MacroRunner(self._db_path).execute_macro(item_id, dry_run=False)
        if not result.success and "reconnect manually and retry" in (result.message or "").casefold():
            self._refresh_connection_status()
        if not result.success and "reconnect manually and retry" in (result.message or "").casefold():
            QMessageBox.warning(
                self,
                "Application reconnection required",
                result.message,
            )
        outcome = "Completed" if result.success else "Stopped"
        self.log.setPlainText(
            f"{outcome} '{item.name}'.\n\n{_format_macro_run_result(result)}"
        )

    def persist_launcher_layout(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            for section, list_widget in self.launcher_lists.items():
                for index in range(list_widget.count()):
                    item = list_widget.item(index)
                    item_id = item.data(list_widget.ITEM_ID_ROLE)
                    entry_kind = item.data(self.ENTRY_KIND_ROLE) or "item"
                    if isinstance(item_id, int) and entry_kind == "item":
                        update_item_launcher_placement(
                            connection,
                            item_id,
                            section,
                            index + 1,
                        )
                    elif isinstance(item_id, int) and entry_kind == "collection":
                        update_launcher_collection_placement(
                            connection,
                            item_id,
                            section,
                            index + 1,
                        )

    def _populate_launcher_lists(self, launcher_items: list) -> None:
        by_section = {section: [] for section in LAUNCHER_SECTIONS}
        for launcher_item in launcher_items:
            by_section.setdefault(launcher_item.launcher_section, []).append(
                launcher_item
            )
        macro_profile_texts = _launcher_macro_profile_texts(
            self._db_path,
            [
                getattr(launcher_item, "macro_item_id", getattr(launcher_item, "id", None))
                for launcher_item in launcher_items
                if getattr(launcher_item, "item_type", None) == "macro"
                and getattr(launcher_item, "entry_kind", getattr(launcher_item, "entry_type", "item")) == "item"
            ],
        )
        for section, list_widget in self.launcher_lists.items():
            list_widget.blockSignals(True)
            list_widget.clear()
            for launcher_item in by_section.get(section, []):
                item = QListWidgetItem(launcher_item.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDropEnabled)
                entry_id = getattr(launcher_item, "id", getattr(launcher_item, "entry_id", None))
                item.setData(list_widget.ITEM_ID_ROLE, entry_id)
                item.setData(
                    self.ENTRY_KIND_ROLE,
                    getattr(launcher_item, "entry_kind", getattr(launcher_item, "entry_type", "item")),
                )
                item.setData(list_widget.ITEM_TYPE_ROLE, launcher_item.item_type)
                if getattr(launcher_item, "entry_kind", getattr(launcher_item, "entry_type", "item")) == "collection":
                    item.setToolTip("Collection")
                    item.setText(f"[+] {launcher_item.name}")
                elif launcher_item.item_type == "macro":
                    macro_item_id = getattr(
                        launcher_item,
                        "macro_item_id",
                        getattr(launcher_item, "id", None),
                    )
                    item.setToolTip(
                        macro_profile_texts.get(
                            macro_item_id,
                            "Profile: (No EMR profile)",
                        )
                    )
                elif launcher_item.item_type in {"clipboard", "randomized_clipboard"}:
                    mode = (
                        "Random selection"
                        if launcher_item.item_type == "randomized_clipboard"
                        else "Simple copy"
                    )
                    item.setToolTip(f"MacroText: {mode}")
                elif launcher_item.item_type == "action":
                    item.setToolTip("Action")
                list_widget.addItem(item)
            list_widget.blockSignals(False)

    def _selected_macro_id(self) -> int | None:
        for list_widget in self.launcher_lists.values():
            current = list_widget.currentItem()
            if current is None:
                continue
            item_id = current.data(list_widget.ITEM_ID_ROLE)
            item_type = current.data(list_widget.ITEM_TYPE_ROLE)
            if isinstance(item_id, int) and item_type == "macro":
                return item_id
        return None

    def _selected_launcher_entry(self) -> dict[str, object] | None:
        for list_widget in self.launcher_lists.values():
            current = list_widget.currentItem()
            if current is None:
                continue
            entry_id = current.data(list_widget.ITEM_ID_ROLE)
            if not isinstance(entry_id, int):
                continue
            return {
                "entry_id": entry_id,
                "entry_kind": current.data(self.ENTRY_KIND_ROLE) or "item",
                "item_id": entry_id,
                "item_type": current.data(list_widget.ITEM_TYPE_ROLE),
            }
        return None

    def _open_collection(self, collection_id: int, dry_run: bool) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            collection = get_launcher_collection(connection, collection_id)
            members = list_launcher_collection_members(connection, collection_id)
            items = [get_item(connection, member.macro_item_id) for member in members]
        if collection is None or not items:
            self.log.setPlainText("Collection is empty.")
            return
        resolved_items = [entry for entry in items if entry is not None]
        dialog = LauncherCollectionChooserDialog(collection.name, resolved_items, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_item_id = dialog.selected_item_id()
        if selected_item_id is None:
            return
        with connect(self._db_path) as connection:
            selected_item = get_item(connection, selected_item_id)
        if selected_item is None:
            self.log.setPlainText("Collection item not found.")
            return
        if dry_run:
            if selected_item.item_type != "macro":
                self.log.setPlainText("Select a macro to dry run.")
            else:
                result = MacroRunner(self._db_path).execute_macro(selected_item_id, dry_run=True)
                self.log.setPlainText(result.message)
            return
        self._activate_item_record(selected_item)

    def create_collection_from_drop(
        self,
        source_item_id: int,
        target_item_id: int,
        launcher_section: str,
        launcher_position: int,
    ) -> bool:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            source = get_item(connection, source_item_id)
            target = get_item(connection, target_item_id)
        if source is None or target is None:
            return False
        if (
            QMessageBox.question(
                self,
                "Create collection",
                f"Create a collection from '{source.name}' and '{target.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return False
        name, accepted = QInputDialog.getText(
            self,
            "Collection name",
            "Collection name",
            text=target.name,
        )
        if not accepted or not name.strip():
            return False
        with connect(self._db_path) as connection:
            collection = create_launcher_collection(
                connection,
                name.strip(),
                launcher_section,
                launcher_position,
            )
            add_item_to_launcher_collection(connection, collection.id, target_item_id)
            add_item_to_launcher_collection(connection, collection.id, source_item_id)
        self.refresh_view()
        self.log.setPlainText(f"Created collection '{name.strip()}'.")
        return True

    def add_item_to_collection_from_drop(
        self,
        source_item_id: int,
        collection_id: int,
    ) -> bool:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            source = get_item(connection, source_item_id)
            collection = get_launcher_collection(connection, collection_id)
        if source is None or collection is None:
            return False
        if (
            QMessageBox.question(
                self,
                "Add to collection",
                f"Add '{source.name}' to collection '{collection.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return False
        with connect(self._db_path) as connection:
            add_item_to_launcher_collection(connection, collection_id, source_item_id)
        self.refresh_view()
        self.log.setPlainText(f"Added '{source.name}' to '{collection.name}'.")
        return True

    def show_collection_context_menu(
        self,
        list_widget: "LauncherListWidget",
        item: QListWidgetItem,
        global_pos,
    ) -> None:
        collection_id = item.data(list_widget.ITEM_ID_ROLE)
        if not isinstance(collection_id, int):
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            collection = get_launcher_collection(connection, collection_id)
            members = list_launcher_collection_members(connection, collection_id)
            items = [get_item(connection, member.macro_item_id) for member in members]
        if collection is None:
            return
        menu = QMenu(self)
        for entry in [entry for entry in items if entry is not None]:
            action = menu.addAction(entry.name)
            action.triggered.connect(
                lambda _checked=False, item_id=entry.id: self._activate_collection_item_by_id(item_id)
            )
        if menu.actions():
            menu.addSeparator()
        edit_action = menu.addAction("Edit collection...")
        unpack_action = menu.addAction("Unpack collection")
        chosen = menu.exec(global_pos)
        if chosen == edit_action:
            self.edit_collection(collection_id)
        elif chosen == unpack_action:
            self.unpack_collection(collection_id)

    def edit_collection(self, collection_id: int) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            collection = get_launcher_collection(connection, collection_id)
            members = list_launcher_collection_members(connection, collection_id)
            items = [get_item(connection, member.macro_item_id) for member in members]
        if collection is None:
            return
        dialog = LauncherCollectionEditorDialog(
            collection.name,
            [entry for entry in items if entry is not None],
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        member_ids = dialog.member_item_ids()
        with connect(self._db_path) as connection:
            current_collection = get_launcher_collection(connection, collection_id)
            if current_collection is None:
                return
            rename_launcher_collection(connection, collection_id, dialog.collection_name())
            original_ids = [member.macro_item_id for member in list_launcher_collection_members(connection, collection_id)]
            removed_ids = [macro_id for macro_id in original_ids if macro_id not in member_ids]
            insert_position = current_collection.launcher_position + 1
            for removed_id in removed_ids:
                removed, _collapsed_macro_id = remove_macro_from_launcher_collection(
                    connection,
                    collection_id,
                    removed_id,
                )
                if removed:
                    update_item_launcher_placement(
                        connection,
                        removed_id,
                        current_collection.launcher_section,
                        insert_position,
                    )
                    insert_position += 1
            remaining_collection = get_launcher_collection(connection, collection_id)
            if remaining_collection is None:
                if member_ids:
                    update_item_launcher_placement(
                        connection,
                        member_ids[0],
                        current_collection.launcher_section,
                        current_collection.launcher_position,
                    )
                self.refresh_view()
                self.log.setPlainText("Collection collapsed back to a single macro.")
                return
            reorder_launcher_collection_members(connection, collection_id, member_ids)
        self.refresh_view()
        self.log.setPlainText("Collection updated.")

    def unpack_collection(self, collection_id: int) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            collection = get_launcher_collection(connection, collection_id)
            members = list_launcher_collection_members(connection, collection_id)
        if collection is None:
            return
        if (
            QMessageBox.question(
                self,
                "Unpack collection",
                f"Unpack collection '{collection.name}' into simple launcher items?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        with connect(self._db_path) as connection:
            delete_launcher_collection(connection, collection_id)
            for offset, member in enumerate(members):
                update_item_launcher_placement(
                    connection,
                    member.macro_item_id,
                    collection.launcher_section,
                    collection.launcher_position + offset,
                )
        self.refresh_view()
        self.log.setPlainText(f"Unpacked '{collection.name}'.")


class MacrosPage(QWidget):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        title = QLabel("Builder")
        title.setObjectName("pageTitle")

        self.automation_summary = QLabel("Create and edit saved macros.")
        self.automation_summary.setObjectName("macroSummary")

        self.executable_macros_table = _create_macro_table()
        self.non_executable_macros_table = _create_macro_table()
        self.collections_table = _create_collection_table()
        self.macros_table = self.executable_macros_table
        self.executable_macros_table.rows_reordered.connect(
            lambda: self._persist_macro_table_order(self.executable_macros_table)
        )
        self.non_executable_macros_table.rows_reordered.connect(
            lambda: self._persist_macro_table_order(self.non_executable_macros_table)
        )

        self.add_macro_button = QPushButton("Add macro")
        self.add_macro_button.clicked.connect(self.add_macro)
        self.copy_macro_button = QPushButton("Copy selected macro")
        self.copy_macro_button.clicked.connect(self.copy_macro)
        self.edit_macro_button = QPushButton("Edit selected macro")
        self.edit_macro_button.clicked.connect(self.edit_macro)
        self.dry_run_button = QPushButton("Dry run")
        self.dry_run_button.clicked.connect(self.dry_run_macro)
        self.run_macro_button = QPushButton("Run selected macro")
        self.run_macro_button.clicked.connect(self.run_macro)
        self.delete_macro_button = QPushButton("Delete selected macro")
        self.delete_macro_button.clicked.connect(self.delete_macro)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)
        self.edit_collection_button = QPushButton("Edit selected collection")
        self.edit_collection_button.clicked.connect(self.edit_collection)
        self.unpack_collection_button = QPushButton("Unpack selected collection")
        self.unpack_collection_button.clicked.connect(self.unpack_collection)

        controls = QHBoxLayout()
        controls.addWidget(self.add_macro_button)
        controls.addWidget(self.copy_macro_button)
        controls.addWidget(self.edit_macro_button)
        controls.addWidget(self.dry_run_button)
        controls.addWidget(self.run_macro_button)
        controls.addWidget(self.delete_macro_button)
        controls.addWidget(self.refresh_button)
        controls.addStretch()

        collection_controls = QHBoxLayout()
        collection_controls.addWidget(self.edit_collection_button)
        collection_controls.addWidget(self.unpack_collection_button)
        collection_controls.addStretch()

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Macro status will appear here.")

        executable_column = QVBoxLayout()
        executable_column.addWidget(QLabel("Executable macros"))
        executable_column.addWidget(self.executable_macros_table)

        non_executable_column = QVBoxLayout()
        non_executable_column.addWidget(QLabel("Non-executable macros"))
        non_executable_column.addWidget(self.non_executable_macros_table)

        tables_row = QGridLayout()
        tables_row.setContentsMargins(0, 0, 0, 0)
        tables_row.setHorizontalSpacing(12)
        tables_row.addLayout(executable_column, 0, 0)
        tables_row.addLayout(non_executable_column, 0, 1)
        tables_row.setColumnStretch(0, 1)
        tables_row.setColumnStretch(1, 1)

        collections_column = QVBoxLayout()
        collections_column.addWidget(QLabel("Collections"))
        collections_column.addWidget(self.collections_table)
        collections_column.addLayout(collection_controls)

        self.executable_macros_table.itemSelectionChanged.connect(
            lambda: self._sync_macro_selection(self.executable_macros_table)
        )
        self.non_executable_macros_table.itemSelectionChanged.connect(
            lambda: self._sync_macro_selection(self.non_executable_macros_table)
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.automation_summary)
        layout.addLayout(tables_row)
        layout.addLayout(collections_column)
        layout.addLayout(controls)
        layout.addWidget(self.log)

        self.refresh_view()

    def refresh_view(self) -> None:
        macros = _load_macros(self._db_path)
        executable_macros = [macro for macro in macros if macro.is_enabled]
        non_executable_macros = [macro for macro in macros if not macro.is_enabled]
        _populate_macro_table(
            self.executable_macros_table, executable_macros, self._db_path
        )
        _populate_macro_table(
            self.non_executable_macros_table, non_executable_macros, self._db_path
        )
        _populate_collection_table(self.collections_table, self._db_path)
        macro_ids = ", ".join(str(macro.id) for macro in macros) or "None"
        collection_count = self.collections_table.rowCount()
        self.automation_summary.setText(
            f"Saved automation IDs: {macro_ids} | Collections: {collection_count}"
        )

    def add_macro(self) -> None:
        dialog = MacroEditorDialog(self, db_path=self._db_path)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["name"]:
            self.log.setPlainText("Macro name is required.")
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = create_item(
                connection,
                values["name"],
                "macro",
                values["is_enabled"],
                values["emr_target_profile_id"],
                is_launcher_exposed=values["is_launcher_exposed"],
            )
            for step in values["steps"]:
                create_macro_step(connection, item.id, **step)
            reorder_macro_steps(connection, item.id)
        self.refresh_view()
        self.log.setPlainText("Macro added.")

    def edit_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to edit.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = _get_required_item(connection, item_id)
            steps = list_macro_steps(connection, item_id)

        dialog = MacroEditorDialog(self, item, steps, db_path=self._db_path)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        values = dialog.values()
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            update_item(
                connection,
                item_id,
                values["name"],
                "macro",
                values["is_enabled"],
                values["emr_target_profile_id"],
                is_launcher_exposed=values["is_launcher_exposed"],
            )
            delete_macro_steps_for_item(connection, item_id)
            for step in values["steps"]:
                create_macro_step(connection, item_id, **step)
            reorder_macro_steps(connection, item_id)
        self.refresh_view()
        self.log.setPlainText("Macro updated.")

    def copy_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to copy.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = _get_required_item(connection, item_id)
            steps = list_macro_steps(connection, item_id)
            copied = create_item(
                connection,
                _next_macro_copy_name(connection, item.name),
                "macro",
                item.is_enabled,
                item.emr_target_profile_id,
                launcher_section=item.launcher_section,
                is_launcher_exposed=item.is_launcher_exposed,
            )
            for step in steps:
                create_macro_step(
                    connection,
                    copied.id,
                    step.step_order,
                    step.action,
                    target_id=step.target_id,
                    value=step.value,
                    timeout_seconds=step.timeout_seconds,
                    retries=step.retries,
                    press_enter_before=getattr(step, "press_enter_before", False),
                    press_enter_after=step.press_enter_after,
                    wait_before_enabled=step.wait_before_enabled,
                    wait_before_ms=step.wait_before_ms,
                )
            reorder_macro_steps(connection, copied.id)
        self.refresh_view()
        self.log.setPlainText("Macro copied.")

    def dry_run_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to dry run.")
            return

        result = MacroRunner(self._db_path).execute_macro(item_id, dry_run=True)
        self.log.setPlainText(result.message)

    def run_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to run.")
            return

        if (
            QMessageBox.question(
                self,
                "Confirm Macro Execution",
                "Run the selected macro now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            self.log.setPlainText("Macro execution canceled.")
            return

        result = MacroRunner(self._db_path).execute_macro(item_id, dry_run=False)
        if not result.success and "reconnect manually and retry" in (result.message or "").casefold():
            QMessageBox.warning(
                self,
                "Application reconnection required",
                result.message,
            )
        self.log.setPlainText(_format_macro_run_result(result))

    def delete_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a macro to delete.")
            return
        if (
            QMessageBox.question(self, "Confirm", "Delete selected macro?")
            != QMessageBox.StandardButton.Yes
        ):
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            deleted = delete_item(connection, item_id)
        self.refresh_view()
        self.log.setPlainText("Macro deleted." if deleted else "Macro not found.")

    def edit_collection(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id is None:
            self.log.setPlainText("Select a collection to edit.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            collection = get_launcher_collection(connection, collection_id)
            members = list_launcher_collection_members(connection, collection_id)
            items = [get_item(connection, member.macro_item_id) for member in members]
        if collection is None:
            self.log.setPlainText("Collection not found.")
            return

        dialog = LauncherCollectionEditorDialog(
            collection.name,
            [entry for entry in items if entry is not None],
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        member_ids = dialog.member_item_ids()
        with connect(self._db_path) as connection:
            current_collection = get_launcher_collection(connection, collection_id)
            if current_collection is None:
                self.log.setPlainText("Collection not found.")
                return
            rename_launcher_collection(
                connection, collection_id, dialog.collection_name()
            )
            original_ids = [
                member.macro_item_id
                for member in list_launcher_collection_members(connection, collection_id)
            ]
            removed_ids = [item_id for item_id in original_ids if item_id not in member_ids]
            insert_position = current_collection.launcher_position + 1
            for removed_id in removed_ids:
                removed, _collapsed_macro_id = remove_macro_from_launcher_collection(
                    connection,
                    collection_id,
                    removed_id,
                )
                if removed:
                    update_item_launcher_placement(
                        connection,
                        removed_id,
                        current_collection.launcher_section,
                        insert_position,
                    )
                    insert_position += 1
            remaining_collection = get_launcher_collection(connection, collection_id)
            if remaining_collection is None:
                for offset, item_id in enumerate(member_ids, start=0):
                    update_item_launcher_placement(
                        connection,
                        item_id,
                        current_collection.launcher_section,
                        current_collection.launcher_position + offset,
                    )
                self.refresh_view()
                self.log.setPlainText("Collection updated.")
                return
            reorder_launcher_collection_members(connection, collection_id, member_ids)

        self.refresh_view()
        self.log.setPlainText("Collection updated.")

    def unpack_collection(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id is None:
            self.log.setPlainText("Select a collection to unpack.")
            return

        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            collection = get_launcher_collection(connection, collection_id)
            members = list_launcher_collection_members(connection, collection_id)
        if collection is None:
            self.log.setPlainText("Collection not found.")
            return
        if (
            QMessageBox.question(
                self,
                "Unpack collection",
                f"Unpack collection '{collection.name}' into simple launcher items?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        member_ids = [member.macro_item_id for member in members]
        with connect(self._db_path) as connection:
            delete_launcher_collection(connection, collection_id)
            for offset, item_id in enumerate(member_ids, start=0):
                update_item_launcher_placement(
                    connection,
                    item_id,
                    collection.launcher_section,
                    collection.launcher_position + offset,
                )
        self.refresh_view()
        self.log.setPlainText(f"Unpacked '{collection.name}'.")

    def _selected_macro_id(self) -> int | None:
        for table in (self.executable_macros_table, self.non_executable_macros_table):
            item_id = _selected_macro_id(table)
            if item_id is not None:
                return item_id
        return None

    def _selected_collection_id(self) -> int | None:
        selected = self.collections_table.selectedItems()
        if not selected:
            return None
        item = self.collections_table.item(selected[0].row(), 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except (TypeError, ValueError):
            return None

    def _sync_macro_selection(self, active_table: QTableWidget) -> None:
        if active_table.selectedItems():
            other_table = (
                self.non_executable_macros_table
                if active_table is self.executable_macros_table
                else self.executable_macros_table
            )
            other_table.blockSignals(True)
            other_table.clearSelection()
            other_table.blockSignals(False)
            self.collections_table.clearSelection()
            self.macros_table = active_table

    def _persist_macro_table_order(self, active_table: QTableWidget) -> None:
        ordered_ids: list[int] = []
        for table in (self.executable_macros_table, self.non_executable_macros_table):
            source_table = active_table if table is active_table else table
            for row in range(source_table.rowCount()):
                item = source_table.item(row, 0)
                if item is None:
                    continue
                try:
                    ordered_ids.append(int(item.text()))
                except (TypeError, ValueError):
                    continue
        if not ordered_ids:
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            reorder_macro_items(connection, ordered_ids)
        self.refresh_view()
        self.log.setPlainText("Macro order updated.")


class MacroTextsPage(QWidget):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self._db_path = db_path

        title = QLabel("MacroTexts")
        title.setObjectName("pageTitle")

        self.presets_table = QTableWidget(0, 5)
        self.presets_table.setHorizontalHeaderLabels(
            ["id", "name", "mode", "options", "exposed"]
        )
        self.presets_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.presets_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.presets_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.empty_state = QLabel("No preset strings configured.")
        self.empty_state.setObjectName("presetEmptyState")

        self.add_button = QPushButton("Add MacroText")
        self.add_button.clicked.connect(self.add_macrotext)
        self.edit_button = QPushButton("Edit MacroText")
        self.edit_button.clicked.connect(self.edit_macrotext)
        self.delete_button = QPushButton("Delete MacroText")
        self.delete_button.clicked.connect(self.delete_macrotext)
        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_macrotext)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)
        self.collections_table = _create_collection_table()
        self.create_collection_button = QPushButton("Create collection")
        self.create_collection_button.clicked.connect(self.create_collection)
        self.edit_collection_button = QPushButton("Edit selected collection")
        self.edit_collection_button.clicked.connect(self.edit_collection)
        self.unpack_collection_button = QPushButton("Unpack selected collection")
        self.unpack_collection_button.clicked.connect(self.unpack_collection)

        self.status_label = QLabel("")
        self.presets_table.cellDoubleClicked.connect(
            lambda _row, _column: self.copy_macrotext()
        )

        controls = QHBoxLayout()
        controls.addWidget(self.add_button)
        controls.addWidget(self.edit_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.copy_button)
        controls.addWidget(self.refresh_button)
        controls.addStretch()

        collection_controls = QHBoxLayout()
        collection_controls.addWidget(self.create_collection_button)
        collection_controls.addWidget(self.edit_collection_button)
        collection_controls.addWidget(self.unpack_collection_button)
        collection_controls.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.presets_table)
        layout.addLayout(controls)
        layout.addWidget(QLabel("Preset Text collections"))
        layout.addWidget(self.collections_table)
        layout.addLayout(collection_controls)
        layout.addWidget(self.status_label)

        self.refresh_view()

    def refresh_view(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            preset_items = []
            for item_type in ("clipboard", "randomized_clipboard"):
                preset_items.extend(list_items(connection, item_type))
            variant_counts = {
                item.id: len(list_clipboard_variants(connection, item.id))
                for item in preset_items
            }

        all_rows = [("dynamic_current_date", None)] + [
            ("db_item", item) for item in preset_items
        ]

        self.presets_table.setRowCount(len(all_rows))
        for row_index, (row_type, item) in enumerate(all_rows):
            if row_type == "dynamic_current_date":
                self.presets_table.setItem(
                    row_index, 0, QTableWidgetItem(str(DYNAMIC_CURRENT_DATE_MACROTEXT_ID))
                )
                self.presets_table.setItem(
                    row_index, 1, QTableWidgetItem("Current Date")
                )
                self.presets_table.setItem(
                    row_index, 2, QTableWidgetItem("Dynamic")
                )
                self.presets_table.setItem(
                    row_index, 3, QTableWidgetItem("Live")
                )
                self.presets_table.setItem(
                    row_index, 4, QTableWidgetItem("Yes")
                )
                continue
            self.presets_table.setItem(row_index, 0, QTableWidgetItem(str(item.id)))
            self.presets_table.setItem(row_index, 1, QTableWidgetItem(item.name))
            mode = (
                "Random selection"
                if item.item_type == "randomized_clipboard"
                else "Simple copy"
            )
            self.presets_table.setItem(row_index, 2, QTableWidgetItem(mode))
            self.presets_table.setItem(
                row_index, 3, QTableWidgetItem(str(variant_counts[item.id]))
            )
            self.presets_table.setItem(
                row_index, 4, QTableWidgetItem(_yes_no(item.is_launcher_exposed))
            )
        self.presets_table.resizeColumnsToContents()
        _populate_collection_table(self.collections_table, self._db_path, "Comments")
        has_presets = bool(all_rows)
        self.empty_state.setVisible(not has_presets)
        self.presets_table.setVisible(has_presets)

    def add_macrotext(self) -> None:
        dialog = MacroTextDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not self._validate_values(values):
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = create_item(
                connection,
                values["name"],
                values["item_type"],
                True,
                launcher_section="Comments",
                is_launcher_exposed=dialog.launcher_exposed.isChecked(),
            )
            replace_clipboard_variants(connection, item.id, values["bodies"])
        self.refresh_view()
        self.status_label.setText("MacroText added.")

    def edit_macrotext(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            self.status_label.setText("Select a MacroText to edit.")
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            item = get_item(connection, item_id)
            variants = list_clipboard_variants(connection, item_id)
        if item is None:
            self.status_label.setText("MacroText not found.")
            return
        dialog = MacroTextDialog(self, item, [variant.body for variant in variants])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not self._validate_values(values):
            return
        with connect(self._db_path) as connection:
            update_item(
                connection,
                item_id,
                values["name"],
                values["item_type"],
                True,
                launcher_section="Comments",
                is_launcher_exposed=dialog.launcher_exposed.isChecked(),
            )
            replace_clipboard_variants(connection, item_id, values["bodies"])
        self.refresh_view()
        self.status_label.setText("MacroText updated.")

    def delete_macrotext(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            self.status_label.setText("Select a MacroText to delete.")
            return
        if (
            QMessageBox.question(self, "Confirm", "Delete selected MacroText?")
            != QMessageBox.StandardButton.Yes
        ):
            return
        with connect(self._db_path) as connection:
            deleted = delete_item(connection, item_id)
        self.refresh_view()
        self.status_label.setText(
            "MacroText deleted." if deleted else "MacroText not found."
        )

    def copy_macrotext(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            self.status_label.setText("Select a MacroText to copy.")
            return
        _success, message = _copy_macrotext(self._db_path, item_id)
        self.status_label.setText(message)

    def create_collection(self) -> None:
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            candidates = [
                item
                for item_type in ("clipboard", "randomized_clipboard")
                for item in list_items(connection, item_type)
                if item.is_launcher_exposed
                and get_launcher_collection_for_item(connection, item.id) is None
            ]
        if len(candidates) < 2:
            self.status_label.setText(
                "At least two exposed, ungrouped MacroTexts are required."
            )
            return

        dialog = LauncherCollectionCreateDialog("Preset Text", candidates, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name = dialog.collection_name()
        item_ids = dialog.selected_item_ids()
        if not name:
            self.status_label.setText("Collection name is required.")
            return
        if len(item_ids) < 2:
            self.status_label.setText("Select at least two MacroTexts.")
            return

        with connect(self._db_path) as connection:
            collection = create_launcher_collection(connection, name, "Comments")
            for item_id in item_ids:
                add_item_to_launcher_collection(connection, collection.id, item_id)
        self.refresh_view()
        self.status_label.setText(f"Created collection '{name}'.")

    def edit_collection(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id is None:
            self.status_label.setText("Select a Preset Text collection to edit.")
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            collection = get_launcher_collection(connection, collection_id)
            members = list_launcher_collection_members(connection, collection_id)
            items = [get_item(connection, member.macro_item_id) for member in members]
        if collection is None:
            self.status_label.setText("Collection not found.")
            return

        dialog = LauncherCollectionEditorDialog(
            collection.name,
            [entry for entry in items if entry is not None],
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not dialog.collection_name():
            self.status_label.setText("Collection name is required.")
            return

        member_ids = dialog.member_item_ids()
        with connect(self._db_path) as connection:
            current = get_launcher_collection(connection, collection_id)
            if current is None:
                self.status_label.setText("Collection not found.")
                return
            rename_launcher_collection(connection, collection_id, dialog.collection_name())
            original_ids = [
                member.macro_item_id
                for member in list_launcher_collection_members(connection, collection_id)
            ]
            insert_position = current.launcher_position + 1
            for removed_id in [item_id for item_id in original_ids if item_id not in member_ids]:
                removed, _collapsed_item_id = remove_item_from_launcher_collection(
                    connection, collection_id, removed_id
                )
                if removed:
                    update_item_launcher_placement(
                        connection, removed_id, "Comments", insert_position
                    )
                    insert_position += 1
            if get_launcher_collection(connection, collection_id) is not None:
                reorder_launcher_collection_members(connection, collection_id, member_ids)
        self.refresh_view()
        self.status_label.setText("Preset Text collection updated.")

    def unpack_collection(self) -> None:
        collection_id = self._selected_collection_id()
        if collection_id is None:
            self.status_label.setText("Select a Preset Text collection to unpack.")
            return
        initialize_database(self._db_path)
        with connect(self._db_path) as connection:
            collection = get_launcher_collection(connection, collection_id)
            members = list_launcher_collection_members(connection, collection_id)
        if collection is None:
            self.status_label.setText("Collection not found.")
            return
        if (
            QMessageBox.question(
                self,
                "Unpack collection",
                f"Unpack collection '{collection.name}' into simple launcher items?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        with connect(self._db_path) as connection:
            delete_launcher_collection(connection, collection_id)
            for offset, member in enumerate(members):
                update_item_launcher_placement(
                    connection,
                    member.macro_item_id,
                    "Comments",
                    collection.launcher_position + offset,
                )
        self.refresh_view()
        self.status_label.setText(f"Unpacked '{collection.name}'.")

    def _selected_item_id(self) -> int | None:
        selected = self.presets_table.selectedItems()
        if not selected:
            return None
        id_item = self.presets_table.item(selected[0].row(), 0)
        return int(id_item.text()) if id_item is not None else None

    def _selected_collection_id(self) -> int | None:
        selected = self.collections_table.selectedItems()
        if not selected:
            return None
        id_item = self.collections_table.item(selected[0].row(), 0)
        if id_item is None:
            return None
        return int(id_item.text())

    def _validate_values(self, values: dict) -> bool:
        if not values["name"]:
            self.status_label.setText("MacroText name is required.")
            return False
        if not values["bodies"]:
            self.status_label.setText("MacroText content is required.")
            return False
        return True


class MacroTextDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        item=None,
        bodies: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("MacroText")
        self.name = QLineEdit(item.name if item is not None else "")
        self.randomized = QCheckBox("Choose one option at random")
        self.randomized.setChecked(
            item is not None and item.item_type == "randomized_clipboard"
        )
        self.launcher_exposed = QCheckBox()
        self.launcher_exposed.setChecked(
            getattr(item, "is_launcher_exposed", True) if item is not None else True
        )
        self.content = QPlainTextEdit()
        self.content.setPlaceholderText("Enter text to copy.")
        self.content.setPlainText(
            self._display_content(bodies or [], self.randomized.isChecked())
        )
        self.randomized.toggled.connect(self._update_content_hint)
        self._update_content_hint(self.randomized.isChecked())

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Mode", self.randomized)
        form.addRow("Exposed in Launcher", self.launcher_exposed)
        form.addRow("Text", self.content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(560, 420)

    def values(self) -> dict:
        content = self.content.toPlainText().strip()
        if self.randomized.isChecked():
            bodies = self._randomized_bodies(content)
            item_type = "randomized_clipboard"
        else:
            bodies = [content] if content else []
            item_type = "clipboard"
        return {
            "name": self.name.text().strip(),
            "item_type": item_type,
            "bodies": bodies,
        }

    def _display_content(self, bodies: list[str], randomized: bool) -> str:
        return ("\n---\n" if randomized else "\n").join(bodies)

    def _randomized_bodies(self, content: str) -> list[str]:
        bodies: list[str] = []
        current_lines: list[str] = []
        for line in content.splitlines():
            if line.strip() == "---":
                body = "\n".join(current_lines).strip()
                if body:
                    bodies.append(body)
                current_lines = []
                continue
            current_lines.append(line)

        body = "\n".join(current_lines).strip()
        if body:
            bodies.append(body)
        return bodies

    def _update_content_hint(self, randomized: bool) -> None:
        self.content.setPlaceholderText(
            "Separate options with --- on its own line. Options may be multiline."
            if randomized
            else "Enter the text to copy. Multiline text is supported."
        )


PresetsPage = MacroTextsPage


class LauncherCollectionCreateDialog(QDialog):
    def __init__(
        self,
        item_label: str,
        items: list,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Create {item_label} collection")
        self.name_input = QLineEdit()
        self.items_list = QListWidget()
        for entry in items:
            item = QListWidgetItem(entry.name)
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.items_list.addItem(item)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Collection name", self.name_input)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel(f"Select at least two {item_label}s"))
        layout.addWidget(self.items_list)
        layout.addWidget(buttons)
        self.resize(440, 420)

    def collection_name(self) -> str:
        return self.name_input.text().strip()

    def selected_item_ids(self) -> list[int]:
        selected: list[int] = []
        for row in range(self.items_list.count()):
            item = self.items_list.item(row)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            item_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(item_id, int):
                selected.append(item_id)
        return selected


class LauncherCollectionChooserDialog(QDialog):
    def __init__(self, collection_name: str, items: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(collection_name)
        self._items = items
        self.list_widget = QListWidget()
        for entry in items:
            item = QListWidgetItem(entry.name)
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select item"))
        layout.addWidget(self.list_widget)
        layout.addWidget(buttons)

    def selected_item_id(self) -> int | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, int) else None


class LauncherCollectionEditorListWidget(QListWidget):
    ITEM_ID_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self) -> None:
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def item_ids(self) -> list[int]:
        ids: list[int] = []
        for index in range(self.count()):
            item = self.item(index)
            value = item.data(self.ITEM_ID_ROLE)
            if isinstance(value, int):
                ids.append(value)
        return ids


class LauncherCollectionEditorDialog(QDialog):
    def __init__(self, collection_name: str, items: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit collection")
        self.name_input = QLineEdit(collection_name)
        self.members_list = LauncherCollectionEditorListWidget()
        for entry in items:
            item = QListWidgetItem(entry.name)
            item.setData(self.members_list.ITEM_ID_ROLE, entry.id)
            self.members_list.addItem(item)
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.clicked.connect(self._remove_selected)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Collection name", self.name_input)
        layout.addLayout(form)
        layout.addWidget(QLabel("Items"))
        layout.addWidget(self.members_list)
        controls = QHBoxLayout()
        controls.addWidget(self.remove_button)
        controls.addStretch()
        layout.addLayout(controls)
        layout.addWidget(buttons)

    def _remove_selected(self) -> None:
        row = self.members_list.currentRow()
        if row >= 0:
            self.members_list.takeItem(row)

    def collection_name(self) -> str:
        return self.name_input.text().strip()

    def member_item_ids(self) -> list[int]:
        return self.members_list.item_ids()


class LauncherListWidget(QListWidget):
    ITEM_ID_ROLE = 256
    ITEM_TYPE_ROLE = 257
    ENTRY_KIND_ROLE = 258

    def __init__(self, section: str, launcher_page: LauncherPage) -> None:
        super().__init__()
        self.section = section
        self.launcher_page = launcher_page
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setStyleSheet(
            "QListWidget {"
            " border: 1px solid #4c566a;"
            " border-radius: 6px;"
            " padding: 4px;"
            " background-color: #2e3440;"
            "}"
        )

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def dropEvent(self, event) -> None:
        source = event.source()
        if source is not self:
            event.ignore()
            return

        source_item = self.currentItem()
        drop_point = self._event_position(event)
        target_item = self.itemAt(drop_point)
        if self._is_collection_drop(source_item, target_item, drop_point):
            source_id = source_item.data(self.ITEM_ID_ROLE)
            target_id = target_item.data(self.ITEM_ID_ROLE)
            target_kind = target_item.data(self.ENTRY_KIND_ROLE) or "item"
            handled = False
            if isinstance(source_id, int) and isinstance(target_id, int):
                if target_kind == "collection":
                    handled = self.launcher_page.add_item_to_collection_from_drop(
                        source_id,
                        target_id,
                    )
                else:
                    handled = self.launcher_page.create_collection_from_drop(
                        source_id,
                        target_id,
                        self.section,
                        self.row(target_item) + 1,
                    )
            if handled:
                event.setDropAction(Qt.DropAction.MoveAction)
                event.accept()
            else:
                event.ignore()
            return

        super().dropEvent(event)
        if event.isAccepted():
            QTimer.singleShot(0, self.launcher_page.persist_launcher_layout)

    def _is_collection_drop(
        self,
        source_item: QListWidgetItem | None,
        target_item: QListWidgetItem | None,
        drop_point: QPoint,
    ) -> bool:
        if source_item is None or target_item is None or source_item is target_item:
            return False
        if self.section == "Actions":
            return False
        if (source_item.data(self.ENTRY_KIND_ROLE) or "item") != "item":
            return False
        if (
            self.dropIndicatorPosition()
            == QAbstractItemView.DropIndicatorPosition.OnItem
        ):
            return True
        target_rect = self.visualItemRect(target_item)
        center_margin = max(2, target_rect.height() // 4)
        return (
            target_rect.top() + center_margin
            <= drop_point.y()
            <= target_rect.bottom() - center_margin
        )

    @staticmethod
    def _event_position(event) -> QPoint:
        position = getattr(event, "position", None)
        if callable(position):
            return position().toPoint()
        legacy_position = getattr(event, "pos", None)
        if callable(legacy_position):
            return legacy_position()
        return QPoint()

    def _move_item(self, source_row: int, destination_row: int) -> None:
        if not 0 <= source_row < self.count():
            return
        destination_row = max(0, min(destination_row, self.count() - 1))
        if source_row == destination_row:
            return

        item = self.takeItem(source_row)
        if item is None:
            return
        self.insertItem(destination_row, item)
        self.setCurrentItem(item)

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        if (item.data(self.ENTRY_KIND_ROLE) or "item") != "collection":
            return
        self.setCurrentItem(item)
        self.launcher_page.show_collection_context_menu(
            self,
            item,
            self.viewport().mapToGlobal(pos),
        )

class ReorderableMacroTable(QTableWidget):
    rows_reordered = Signal()
    MIME_TYPE = "application/x-kaoseghis-macro-row"

    def __init__(self, rows: int, columns: int, parent: QWidget | None = None) -> None:
        super().__init__(rows, columns, parent)
        self._drag_start_pos: QPoint | None = None
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.viewport().installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_start_pos = event.position().toPoint()
            elif event.type() == QEvent.Type.MouseMove:
                if (
                    self._drag_start_pos is not None
                    and event.buttons() & Qt.MouseButton.LeftButton
                    and (
                        event.position().toPoint() - self._drag_start_pos
                    ).manhattanLength()
                    >= QApplication.startDragDistance()
                ):
                    self._begin_drag()
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_start_pos = None
        return super().eventFilter(watched, event)

    def _begin_drag(self) -> None:
        source_row = self.currentRow()
        if source_row < 0:
            source_row = self.rowAt((self._drag_start_pos or QPoint()).y())
        if source_row < 0:
            self._drag_start_pos = None
            return

        self.selectRow(source_row)
        mime_data = QMimeData()
        mime_data.setData(self.MIME_TYPE, str(source_row).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)
        self._drag_start_pos = None

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def dragEnterEvent(self, event) -> None:
        if event.source() is self and event.mimeData().hasFormat(self.MIME_TYPE):
            self._debug_drag("dragEnter accepted")
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        self._debug_drag("dragEnter passed to super")
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.source() is self and event.mimeData().hasFormat(self.MIME_TYPE):
            self._debug_drag(f"dragMove accepted at pos={event.position().toPoint()}")
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        self._debug_drag("dragMove passed to super")
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.source() is not self or not event.mimeData().hasFormat(self.MIME_TYPE):
            self._debug_drag("dropEvent passed to super")
            super().dropEvent(event)
            return

        try:
            source_row = int(bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8"))
        except Exception:
            self._debug_drag("dropEvent ignored: invalid mime payload")
            event.ignore()
            return
        if source_row < 0:
            self._debug_drag(f"dropEvent ignored: source_row={source_row}")
            event.ignore()
            return

        target_index = self.indexAt(event.position().toPoint())
        if target_index.isValid():
            insertion_row = target_index.row()
            if (
                self.dropIndicatorPosition()
                == QAbstractItemView.DropIndicatorPosition.BelowItem
            ):
                insertion_row += 1
        else:
            insertion_row = self.rowCount()

        final_row = insertion_row - (1 if insertion_row > source_row else 0)
        self._debug_drag(
            f"dropEvent reorder source_row={source_row} insertion_row={insertion_row} "
            f"final_row={final_row}"
        )
        self.move_row(source_row, final_row)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def move_row(self, source_row: int, destination_row: int) -> None:
        if not 0 <= source_row < self.rowCount():
            return
        destination_row = max(0, min(destination_row, self.rowCount() - 1))
        if source_row == destination_row:
            return

        row_values = []
        for column in range(self.columnCount()):
            item = self.item(source_row, column)
            row_values.append(item.text() if item is not None else "")
        self.removeRow(source_row)
        self.insertRow(destination_row)
        for column, value in enumerate(row_values):
            self.setItem(destination_row, column, QTableWidgetItem(value))
        self.selectRow(destination_row)
        self.rows_reordered.emit()
        self._debug_drag(
            f"move_row completed: source_row={source_row} destination_row={destination_row}"
        )

    def _debug_drag(self, message: str) -> None:
        print(f"[MacroTableDrag] {message}")


def _create_macro_table() -> QTableWidget:
    table = ReorderableMacroTable(0, 5)
    table.setHorizontalHeaderLabels(
        ["id", "name", "EMR profile", "executable", "exposed"]
    )
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    return table


def _create_collection_table() -> QTableWidget:
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["id", "name", "section", "members"])
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    return table


def _load_macros(db_path: Path | None) -> list:
    initialize_database(db_path)
    with connect(db_path) as connection:
        return list_items(connection, "macro")


def _load_launcher_entries(db_path: Path | None) -> list:
    initialize_database(db_path)
    with connect(db_path) as connection:
        items = list_launcher_entries(connection)
    return [
        SimpleNamespace(
            id=DYNAMIC_CURRENT_DATE_MACROTEXT_ID,
            name="Current Date",
            entry_kind="item",
            item_type="clipboard",
            is_enabled=True,
            emr_target_profile_id=None,
            launcher_section="Actions",
            launcher_position=0,
            created_at="",
            updated_at="",
        ),
        SimpleNamespace(
            id=FETCH_PATIENT_INFO_FOR_VACCINATION_ACTION_ID,
            name="Fetch Pt. Info for Vaccination",
            entry_kind="action",
            item_type="action",
            is_enabled=True,
            emr_target_profile_id=None,
            launcher_section="Actions",
            launcher_position=1,
            created_at="",
            updated_at="",
        ),
        *items,
    ]


def _load_launcher_macros(db_path: Path | None) -> list:
    return [
        item
        for item in _load_launcher_entries(db_path)
        if getattr(item, "entry_kind", "item") == "item" and item.item_type == "macro"
    ]


def _copy_macrotext(db_path: Path | None, item_id: int) -> tuple[bool, str]:
    if item_id == DYNAMIC_CURRENT_DATE_MACROTEXT_ID:
        text = _format_current_date_macrotext()
        try:
            copy_text(text)
        except Exception:
            return False, "Clipboard copy failed."
        return True, "Copied current date to clipboard."

    initialize_database(db_path)
    with connect(db_path) as connection:
        item = get_item(connection, item_id)
        variants = list_clipboard_variants(connection, item_id)
    if item is None or item.item_type not in {"clipboard", "randomized_clipboard"}:
        return False, "MacroText not found."
    if not variants:
        return False, f"MacroText '{item.name}' has no text."
    text = (
        random.choice(variants).body
        if item.item_type == "randomized_clipboard"
        else variants[0].body
    )
    try:
        copy_text(text)
    except Exception:
        return False, "Clipboard copy failed."
    return True, f"Copied '{item.name}' to clipboard."


def _format_current_date_macrotext(now: datetime | None = None) -> str:
    current = now or datetime.now()
    meridiem = "오전" if current.hour < 12 else "오후"
    return f"{current.year:04d}년 {current.month:02d}월 {current.day:02d}일 {meridiem}"


def _populate_macro_table(
    table: QTableWidget, macros: list, db_path: Path | None
) -> None:
    table.setRowCount(len(macros))
    with connect(db_path) as connection:
        for row_index, macro in enumerate(macros):
            profile = resolve_macro_emr_target_profile(connection, macro)
            table.setItem(row_index, 0, QTableWidgetItem(str(macro.id)))
            table.setItem(row_index, 1, QTableWidgetItem(macro.name))
            table.setItem(
                row_index,
                2,
                QTableWidgetItem(profile.name if profile is not None else ""),
            )
            table.setItem(
                row_index, 3, QTableWidgetItem(_yes_no(macro.is_enabled))
            )
            table.setItem(
                row_index,
                4,
                QTableWidgetItem(_yes_no(macro.is_launcher_exposed)),
            )
    table.resizeColumnsToContents()


def _populate_collection_table(
    table: QTableWidget,
    db_path: Path | None,
    launcher_section: str = "Macro",
) -> None:
    initialize_database(db_path)
    with connect(db_path) as connection:
        collections = list_launcher_collections(connection, launcher_section)
        member_counts = {
            collection.id: len(list_launcher_collection_members(connection, collection.id))
            for collection in collections
        }
    table.setRowCount(len(collections))
    for row_index, collection in enumerate(collections):
        table.setItem(row_index, 0, QTableWidgetItem(str(collection.id)))
        table.setItem(row_index, 1, QTableWidgetItem(collection.name))
        table.setItem(row_index, 2, QTableWidgetItem(collection.launcher_section))
        table.setItem(
            row_index,
            3,
            QTableWidgetItem(str(member_counts.get(collection.id, 0))),
        )
    table.resizeColumnsToContents()


def _selected_macro_id(table: QTableWidget) -> int | None:
    selected = table.selectedItems()
    if not selected:
        return None
    item = table.item(selected[0].row(), 0)
    if item is None:
        return None
    return int(item.text())


def _get_required_item(connection, item_id: int):
    item = get_item(connection, item_id)
    if item is not None:
        return item
    raise RuntimeError("Item not found.")


def _next_macro_copy_name(connection, base_name: str) -> str:
    existing_names = {
        item.name
        for item in list_items(connection, "macro")
    }
    if f"{base_name} Copy" not in existing_names:
        return f"{base_name} Copy"
    index = 2
    while True:
        candidate = f"{base_name} Copy {index}"
        if candidate not in existing_names:
            return candidate
        index += 1


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _macro_profile_text(db_path: Path | None, macro) -> str:
    with connect(db_path) as connection:
        macro_record = macro
        macro_item_id = getattr(macro, "macro_item_id", None)
        if isinstance(macro_item_id, int):
            resolved = get_item(connection, macro_item_id)
            if resolved is not None:
                macro_record = resolved
        profile = resolve_macro_emr_target_profile(connection, macro_record)
    return f"Profile: {profile.name if profile is not None else '(No EMR profile)'}"


def _launcher_macro_profile_texts(
    db_path: Path | None,
    macro_item_ids: list[int | None],
) -> dict[int, str]:
    valid_ids = [macro_item_id for macro_item_id in macro_item_ids if isinstance(macro_item_id, int)]
    if not valid_ids:
        return {}
    texts: dict[int, str] = {}
    with connect(db_path) as connection:
        for macro_item_id in valid_ids:
            macro = get_item(connection, macro_item_id)
            profile = resolve_macro_emr_target_profile(connection, macro)
            texts[macro_item_id] = (
                f"Profile: {profile.name if profile is not None else '(No EMR profile)'}"
            )
    return texts


def _format_macro_run_result(result) -> str:
    if result.success:
        return f"Completed. Steps: {result.executed_steps}"

    if result.failed_step:
        return (
            f"Stopped at step {result.failed_step}. "
            f"{result.message}"
        )

    if result.executed_steps:
        return f"Stopped after {result.executed_steps} step(s). {result.message}"

    return result.message
