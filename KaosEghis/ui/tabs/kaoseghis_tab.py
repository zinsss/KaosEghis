from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.emr_detector import (
    detect_eghis_connection,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import (
    get_item,
    get_settings,
    list_items,
    list_macro_steps,
    validate_macro_dry_run,
)


class KaosEghisTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.connection_dot = QLabel("●")
        self.connection_label = QLabel("Eghis EMR Connection")
        self.connection_state = QLabel()

        connection_row = QHBoxLayout()
        connection_row.addWidget(self.connection_dot)
        connection_row.addWidget(self.connection_label)
        connection_row.addWidget(self.connection_state)
        connection_row.addStretch()

        presets_title = QLabel("Preset Automations")
        self.macros_table = QTableWidget(0, 3)
        self.macros_table.setHorizontalHeaderLabels(["id", "name", "enabled"])
        self.macros_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.macros_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.macros_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_view)

        dry_run_button = QPushButton("Dry Run")
        dry_run_button.clicked.connect(self.dry_run_macro)

        controls = QHBoxLayout()
        controls.addWidget(refresh_button)
        controls.addWidget(dry_run_button)
        controls.addStretch()

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Daily preset status will appear here.")

        layout = QVBoxLayout(self)
        layout.addLayout(connection_row)
        layout.addWidget(presets_title)
        layout.addWidget(self.macros_table)
        layout.addLayout(controls)
        layout.addWidget(self.log)

        self.refresh_view()

    def refresh_view(self) -> None:
        self.refresh_connection_status()
        self.refresh_macros()
        self.log.setPlainText("Preset automations refreshed.")

    def refresh_connection_status(self) -> None:
        initialize_database()
        with connect() as connection:
            settings = get_settings(connection)

        process_name = settings["eghis_process_name"]
        title_fragment = settings["eghis_window_title_contains"]
        status = detect_eghis_connection(process_name, title_fragment)

        if status.connected:
            self.connection_dot.setStyleSheet("color: #a6e3a1;")
            self.connection_state.setText("Connected")
        else:
            self.connection_dot.setStyleSheet("color: #f38ba8;")
            self.connection_state.setText(status.message)

    def refresh_macros(self) -> None:
        initialize_database()
        with connect() as connection:
            macros = list_items(connection, "macro")

        self.macros_table.setRowCount(len(macros))
        for row_index, macro in enumerate(macros):
            self.macros_table.setItem(row_index, 0, QTableWidgetItem(str(macro.id)))
            self.macros_table.setItem(row_index, 1, QTableWidgetItem(macro.name))
            self.macros_table.setItem(row_index, 2, QTableWidgetItem(_yes_no(macro.is_enabled)))
        self.macros_table.resizeColumnsToContents()

    def dry_run_macro(self) -> None:
        item_id = self._selected_macro_id()
        if item_id is None:
            self.log.setPlainText("Select a preset automation to dry run.")
            return

        initialize_database()
        with connect() as connection:
            self.log.setPlainText(_build_dry_run_output(connection, item_id))

    def _selected_macro_id(self) -> int | None:
        selected = self.macros_table.selectedItems()
        if not selected:
            return None
        item = self.macros_table.item(selected[0].row(), 0)
        if item is None:
            return None
        return int(item.text())


def _build_dry_run_output(connection, item_id: int) -> str:
    item = get_item(connection, item_id)
    if item is None:
        return "Macro not found."

    steps = list_macro_steps(connection, item_id)
    errors = validate_macro_dry_run(connection, item_id)
    lines = [f"Dry run: {item.name}"]
    for step in steps:
        lines.append(_dry_run_step_line(step))
    if errors:
        lines.append("")
        missing_target = _missing_target_from_error(errors[0])
        if missing_target:
            lines.append(f"Result: Blocked - missing UI target: {missing_target}")
        else:
            lines.append(f"Result: Blocked - {errors[0]}")
    else:
        if not steps:
            lines.append("No steps defined.")
        lines.append("")
        lines.append("Result: OK - dry run only, no actions executed.")
    return "\n".join(lines)


def _dry_run_step_line(step) -> str:
    target = f" target_id={step.target_id}" if step.target_id else ""
    value = f" value={step.value}" if step.value else ""
    if step.action == "wait_for_target":
        return (
            f"{step.step_order}. wait_for_target{target} "
            f"timeout={step.timeout_seconds} retries={step.retries} (dry run only)"
        )
    if step.action == "wait_ms":
        duration = step.value or ""
        duration_text = f" duration_ms={duration}" if duration else ""
        return f"{step.step_order}. wait_ms{duration_text} (dry run only)"
    return (
        f"{step.step_order}. {step.action}{target}{value} "
        f"timeout={step.timeout_seconds} retries={step.retries}"
    )


def _missing_target_from_error(error: str) -> str | None:
    marker = "target_id '"
    if marker not in error:
        return None
    start = error.index(marker) + len(marker)
    end = error.find("'", start)
    if end == -1:
        return None
    return error[start:end]


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
