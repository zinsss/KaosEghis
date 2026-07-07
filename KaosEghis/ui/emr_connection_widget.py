from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from KaosEghis.core.eghis_connector import (
    EghisConnectorState,
    cached_state_matches_settings,
    clear_cached_eghis_state,
    get_cached_eghis_state,
    refresh_cached_eghis_state,
)


ConnectionContextProvider = Callable[[], tuple[dict[str, str] | None, str | None]]
StatusCallback = Callable[[str], None]


class EmrConnectionWidget(QWidget):
    def __init__(
        self,
        context_provider: ConnectionContextProvider,
        *,
        status_callback: StatusCallback | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context_provider = context_provider
        self._status_callback = status_callback

        self.toggle_button = QPushButton("Connect EMR")
        self.toggle_button.setCheckable(True)
        self.toggle_button.clicked.connect(self.toggle_connection)
        self.status_label = QLabel("Disconnected")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.refresh_state()

    def toggle_connection(self) -> None:
        settings, preset_name = self._context_provider()
        state = get_cached_eghis_state()
        if settings is None:
            clear_cached_eghis_state()
            self.refresh_state()
            self._emit_status("Reconnect required")
            return

        if self._is_connected_for_preset(state, settings):
            clear_cached_eghis_state()
            self.refresh_state()
            self._emit_status("Disconnected")
            return

        clear_cached_eghis_state()
        refreshed = refresh_cached_eghis_state(settings)
        self.refresh_state(refreshed, preset_name)
        self._emit_status(refreshed.message)

    def refresh_state(
        self,
        state: EghisConnectorState | None = None,
        preset_name: str | None = None,
    ) -> None:
        if state is None:
            state = get_cached_eghis_state()
        settings, context_preset_name = self._context_provider()
        preset_name = preset_name or context_preset_name
        classification = self._classify_state(state, settings)
        if classification == "connected":
            self.toggle_button.setText("EMR Connected")
            self.toggle_button.setChecked(True)
            self.status_label.setText(f"Connected: {preset_name or 'Preset'}")
        elif classification == "stale":
            self.toggle_button.setText("Reconnect EMR")
            self.toggle_button.setChecked(False)
            self.status_label.setText("Reconnect required")
        else:
            self.toggle_button.setText("Connect EMR")
            self.toggle_button.setChecked(False)
            self.status_label.setText("Disconnected")
        self.toggle_button.setProperty("connectionState", classification)
        self.toggle_button.style().unpolish(self.toggle_button)
        self.toggle_button.style().polish(self.toggle_button)

    def _classify_state(
        self,
        state: EghisConnectorState | None,
        settings: dict[str, str] | None,
    ) -> str:
        if state is None or settings is None:
            return "disconnected"
        if self._is_connected_for_preset(state, settings):
            return "connected"
        return "stale"

    @staticmethod
    def _is_connected_for_preset(
        state: EghisConnectorState | None,
        settings: dict[str, str],
    ) -> bool:
        if state is None:
            return False
        return state.status in {"green", "yellow"} and cached_state_matches_settings(
            state, settings
        )

    def _emit_status(self, message: str) -> None:
        if self._status_callback is not None:
            self._status_callback(message)
