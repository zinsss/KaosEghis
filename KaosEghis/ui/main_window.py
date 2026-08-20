import os
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QMainWindow,
    QSizePolicy,
    QTabWidget,
    QWidget,
)

from pywinauto.keyboard import send_keys

from KaosEghis.core.credential_vault import CredentialEntry
from KaosEghis.core.emr_patient_alert import (
    EmrPatientAlertMonitor,
    EmrPatientAlertProbe,
    EmrPatientAlertResult,
    patient_alert_configuration_from_settings,
)
from KaosEghis.core.launcher_hotkey import LauncherHotkeyRuntime
from KaosEghis.core.pw_runtime import ForegroundWindowContext, PwRuntime
from KaosEghis.core.scheduler import SchedulerRuntime
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings
from KaosEghis.ui.drag_hover_switch import TabBarFileHoverFilter
from KaosEghis.ui.plugins.pacs_panel import PacsPanel
from KaosEghis.ui.dialogs.master_password_dialog import MasterPasswordDialog
from KaosEghis.ui.dialogs.pw_popup_dialog import (
    CredentialEntryDialog,
    CredentialPopupDialog,
)
from KaosEghis.ui.emr_patient_alert import EmrPatientAlertPopup
from KaosEghis.ui.tabs.memos_tab import MemosTab
from KaosEghis.ui.tabs.kaoseghis_tab import (
    KaosEghisTab,
    MacrosTab,
    PlaceholderPage,
    WorkspaceTab,
)
from KaosEghis.ui.tabs.settings_tab import SettingsTab


class AppNotificationArea(QWidget):
    TONES = {"neutral", "info", "success", "warning", "error"}

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("appNotificationArea")
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.dot = QLabel("\u25cf")
        self.dot.setObjectName("appNotificationDot")
        self.text = QLabel("Ready")
        self.text.setObjectName("appNotificationText")
        self.text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 12, 0)
        layout.setSpacing(6)
        layout.addStretch()
        layout.addWidget(self.dot)
        layout.addWidget(self.text)

        self.show_message("Ready", "neutral")

    def show_message(self, message: str, tone: str = "info") -> None:
        safe_message = " ".join(str(message).split()).strip() or "Ready"
        safe_tone = tone if tone in self.TONES else "info"
        self.text.setText(safe_message)
        self.setToolTip(safe_message)
        for widget in (self.dot, self.text):
            widget.setProperty("notificationTone", safe_tone)
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class MainWindow(QMainWindow):
    PACS_TAB_HEALTHY_COLOR = QColor("#d8dee9")
    PACS_TAB_UNHEALTHY_COLOR = QColor("#bf616a")

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KaosEghis")
        self.setFixedSize(1438, 1194)
        self.launcher_hotkey_runtime = LauncherHotkeyRuntime(self)
        self.pw_runtime = PwRuntime(self)
        self.patient_alert_popup = EmrPatientAlertPopup()
        self.patient_alert_monitor = EmrPatientAlertMonitor(
            probe=self._create_patient_alert_probe(), parent=self
        )
        self.patient_alert_monitor.result_changed.connect(
            self._handle_patient_alert_result
        )

        tabs = QTabWidget()
        self.tabs = tabs
        self.notification_area = AppNotificationArea()
        tabs.setCornerWidget(
            self.notification_area, Qt.Corner.TopRightCorner
        )
        self.kaoseghis_tab = KaosEghisTab()
        self.scheduler_runtime = SchedulerRuntime(parent=self)
        tabs.addTab(self.kaoseghis_tab, "KaosEghis")
        self.memos_tab = MemosTab()
        tabs.addTab(self.memos_tab, "Memos")
        self.workspace_tab = WorkspaceTab()
        tabs.addTab(self.workspace_tab, "Workspace")
        self.pacs_panel = PacsPanel()
        self.pacs_tab_index = tabs.addTab(self.pacs_panel, "PACS")
        self.macros_tab = MacrosTab(scheduler_runtime=self.scheduler_runtime)
        tabs.addTab(self.macros_tab, "Macros")
        self.settings_tab = SettingsTab()
        self.settings_tab.general_settings_saved.connect(
            self._reload_patient_alert_configuration
        )
        tabs.addTab(self.settings_tab, "Settings")
        self._file_hover_tab_filter = TabBarFileHoverFilter(tabs.setCurrentIndex)
        tabs.tabBar().setAcceptDrops(True)
        tabs.tabBar().installEventFilter(self._file_hover_tab_filter)
        self.pacs_panel.health_state_changed.connect(self._update_pacs_tab_health)
        self.macros_tab.emr_page.app_notification.connect(
            self.show_notification
        )
        self.scheduler_runtime.notification_requested.connect(
            self.show_notification
        )
        self.kaoseghis_tab.socl_page.notification_requested.connect(
            self.show_notification
        )
        self.pw_runtime.state_changed.connect(self._handle_pw_state_changed)
        self.pw_runtime.action_requested.connect(self._handle_pw_hotkey)
        self.launcher_hotkey_runtime.activated.connect(self._handle_launcher_hotkey)
        self._update_pacs_tab_health(self.pacs_panel.is_healthy, self.pacs_panel.health_reason)

        self.setCentralWidget(tabs)
        self.scheduler_runtime.start()

    def show_notification(self, message: str, tone: str = "info") -> None:
        self.notification_area.show_message(message, tone)

    def _update_pacs_tab_health(self, healthy: bool, reason: str) -> None:
        color = self.PACS_TAB_HEALTHY_COLOR if healthy else self.PACS_TAB_UNHEALTHY_COLOR
        self.tabs.tabBar().setTabTextColor(self.pacs_tab_index, color)
        self.tabs.tabBar().setTabToolTip(self.pacs_tab_index, reason)

    def closeEvent(self, event) -> None:
        self.patient_alert_monitor.stop()
        self.patient_alert_popup.close()
        self.launcher_hotkey_runtime.stop()
        self.pw_runtime.stop()
        self.scheduler_runtime.stop()
        super().closeEvent(event)

    def initialize_runtime_services(self) -> None:
        if not self.launcher_hotkey_runtime.start():
            self.show_notification(
                "Launcher shortcut unavailable. Ctrl+Alt+Shift+F11 could not be registered.",
                "warning",
            )
        self.pw_runtime.start()
        self.patient_alert_monitor.start()

    def _handle_launcher_hotkey(self) -> None:
        self.tabs.setCurrentWidget(self.kaoseghis_tab)
        self.kaoseghis_tab.show_page(0)
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        if os.environ.get("QT_QPA_PLATFORM", "").strip().lower() != "offscreen":
            try:
                _activate_hwnd(int(self.winId()))
            except Exception:
                pass
        self.show_notification("Launcher opened (Ctrl+Alt+Shift+F11).", "info")

    def _handle_patient_alert_result(self, result: EmrPatientAlertResult) -> None:
        if result.marker_found:
            was_visible = self.patient_alert_popup.isVisible()
            self.patient_alert_popup.show_alert()
            if not was_visible:
                self.show_notification(
                    "Important patient-note marker detected in EMR.", "error"
                )
            return
        self.patient_alert_popup.clear_alert()
        if result.connected and not result.available:
            self.show_notification(
                "Patient alert monitor unavailable. Check EMR target settings.",
                "warning",
            )

    def _create_patient_alert_probe(self) -> EmrPatientAlertProbe:
        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)
        return EmrPatientAlertProbe(
            configuration=patient_alert_configuration_from_settings(settings)
        )

    def _reload_patient_alert_configuration(self) -> None:
        self.patient_alert_popup.clear_alert()
        self.patient_alert_monitor.replace_probe(self._create_patient_alert_probe())

    def prompt_startup_master_password(self) -> None:
        if os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen":
            return
        dialog = MasterPasswordDialog(vault_exists=self.pw_runtime.vault.exists(), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.show_notification("KaosEghis-pw locked.", "warning")
            return
        success, message = self.pw_runtime.initialize_or_unlock(dialog.password())
        self.show_notification(message, "success" if success else "warning")

    def _handle_pw_state_changed(self, unlocked: bool) -> None:
        self.show_notification(
            "KaosEghis-pw unlocked." if unlocked else "KaosEghis-pw locked.",
            "success" if unlocked else "warning",
        )

    def _handle_pw_hotkey(self, context: ForegroundWindowContext) -> None:
        if not self.pw_runtime.is_unlocked:
            dialog = MasterPasswordDialog(
                vault_exists=self.pw_runtime.vault.exists(),
                parent=self,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            success, message = self.pw_runtime.initialize_or_unlock(dialog.password())
            self.show_notification(message, "success" if success else "warning")
            return

        session = self.pw_runtime.session
        if session is None:
            return
        popup = CredentialPopupDialog(
            session.list_entries(),
            locked=False,
            context_title=context.title,
            parent=self,
        )
        if popup.exec() != QDialog.DialogCode.Accepted:
            return
        action = popup.selected_action
        if action == "manage":
            self._open_pw_manage_dialog()
            return
        if action == "lock":
            self.pw_runtime.lock()
            return
        service_name = popup.selected_service_name()
        if not service_name:
            return
        entry = session.get_entry(service_name)
        if entry is None:
            QMessageBox.warning(self, "KaosEghis-pw", "Credential entry was not found.")
            return
        self._type_credential_action(entry, action or "", context)

    def _open_pw_manage_dialog(self) -> None:
        session = self.pw_runtime.session
        if session is None:
            return
        popup = CredentialPopupDialog(
            session.list_entries(),
            locked=False,
            context_title=self.pw_runtime.current_context().title,
            parent=self,
        )
        popup.status_label.setText("Manage KaosEghis-pw entries.")
        popup.type_id_button.hide()
        popup.type_password_button.hide()
        popup.type_both_button.hide()
        popup.lock_button.hide()
        popup.cancel_button.setText("Done")
        popup.manage_button.setText("Add / Edit")
        if popup.exec() != QDialog.DialogCode.Accepted:
            return
        service_name = popup.selected_service_name()
        existing = session.get_entry(service_name) if service_name else None
        dialog = CredentialEntryDialog(self, existing)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.delete_requested:
            if not service_name:
                QMessageBox.warning(self, "KaosEghis-pw", "Credential entry was not found.")
                return
            removed = session.delete_entry(service_name)
            if not removed:
                QMessageBox.warning(self, "KaosEghis-pw", "Credential entry was not found.")
                return
            self.show_notification("KaosEghis-pw entry deleted.", "success")
            return
        values = dialog.values()
        session.set_entry(
            service_name=values.service_name,
            username=values.username,
            password=values.password,
            target_type=values.target_type,
            notes=values.notes,
        )
        self.show_notification("KaosEghis-pw entry saved.", "success")

    def _type_credential_action(
        self,
        entry: CredentialEntry,
        action: str,
        context: ForegroundWindowContext,
    ) -> None:
        if context.hwnd is None:
            QMessageBox.warning(self, "KaosEghis-pw", "Foreground window is not available.")
            return
        try:
            _activate_hwnd(context.hwnd)
            time.sleep(0.12)
            if action == CredentialPopupDialog.ACTION_TYPE_ID:
                send_keys(entry.username, with_spaces=True, with_tabs=True, with_newlines=True)
            elif action == CredentialPopupDialog.ACTION_TYPE_PASSWORD:
                send_keys(entry.password, with_spaces=True, with_tabs=True, with_newlines=True)
            elif action == CredentialPopupDialog.ACTION_TYPE_BOTH:
                send_keys(entry.username, with_spaces=True, with_tabs=True, with_newlines=True)
                send_keys("{TAB}")
                send_keys(entry.password, with_spaces=True, with_tabs=True, with_newlines=True)
            else:
                return
        except Exception:
            QMessageBox.warning(self, "KaosEghis-pw", "Credential typing failed.")
            return
        self.show_notification(f"Typed credentials for {entry.service_name}.", "success")

def _activate_hwnd(hwnd: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
