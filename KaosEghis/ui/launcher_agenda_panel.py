from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCalendarWidget,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from KaosEghis.core.kaosgdd_client import KaosGddApiClient


ITEM_DATA_ROLE = int(Qt.ItemDataRole.UserRole)


class AgendaSuppliesPanel(QWidget):
    def __init__(
        self,
        client: KaosGddApiClient | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.client = client or KaosGddApiClient(parent=self)
        self._calendar_loaded = False
        self._supplies_loaded = False
        self._events: list[dict] = []
        self._tasks: list[dict] = []
        self._collections: list[dict] = []
        self._supplies_mode = "active"
        self._highlighted_dates: list[QDate] = []

        self.page_buttons: dict[str, QPushButton] = {}
        page_row = QHBoxLayout()
        page_row.setContentsMargins(0, 0, 0, 0)
        for index, name in enumerate(("Agenda", "Supplies")):
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, page_index=index: self.show_page(page_index)
            )
            self.page_buttons[name] = button
            page_row.addWidget(button)
        page_row.addStretch()

        self.stacked_widget = QStackedWidget()
        self.agenda_page = self._build_agenda_page()
        self.supplies_page = self._build_supplies_page()
        self.stacked_widget.addWidget(self.agenda_page)
        self.stacked_widget.addWidget(self.supplies_page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(page_row)
        layout.addWidget(self.stacked_widget, 1)

        self.client.request_succeeded.connect(self._request_succeeded)
        self.client.request_failed.connect(self._request_failed)
        self.show_page(0)

    def _build_agenda_page(self) -> QWidget:
        page = QWidget()
        self.agenda_status = QLabel("Not loaded yet.")
        self.agenda_status.setObjectName("secondaryText")

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self.calendar.selectionChanged.connect(self._render_selected_date)

        selected_day_label = QLabel("Selected day")
        selected_day_label.setObjectName("launcherSectionTitle")
        self.events_list = QListWidget()
        self.events_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.events_list.setMaximumHeight(96)

        tasks_header = QHBoxLayout()
        tasks_label = QLabel("Tasks")
        tasks_label.setObjectName("launcherSectionTitle")
        self.refresh_agenda_button = QPushButton("Refresh")
        self.refresh_agenda_button.clicked.connect(self.refresh_agenda)
        self.add_task_button = QPushButton("Add task")
        self.add_task_button.clicked.connect(self.add_task)
        self.toggle_task_button = QPushButton("Complete / reopen")
        self.toggle_task_button.clicked.connect(self.toggle_selected_task)
        tasks_header.addWidget(tasks_label)
        tasks_header.addStretch()
        tasks_header.addWidget(self.refresh_agenda_button)
        tasks_header.addWidget(self.add_task_button)
        tasks_header.addWidget(self.toggle_task_button)

        self.tasks_list = QListWidget()
        self.tasks_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.agenda_status)
        layout.addWidget(self.calendar, 3)
        layout.addWidget(selected_day_label)
        layout.addWidget(self.events_list)
        layout.addLayout(tasks_header)
        layout.addWidget(self.tasks_list, 2)
        return page

    def _build_supplies_page(self) -> QWidget:
        page = QWidget()
        self.supplies_status = QLabel("Not loaded yet.")
        self.supplies_status.setObjectName("secondaryText")

        filters = QHBoxLayout()
        self.supply_filter_buttons: dict[str, QPushButton] = {}
        for mode, name in (("active", "Active"), ("done", "Done")):
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, selected_mode=mode: self.set_supplies_mode(
                    selected_mode
                )
            )
            self.supply_filter_buttons[mode] = button
            filters.addWidget(button)
        self.refresh_supplies_button = QPushButton("Refresh")
        self.refresh_supplies_button.clicked.connect(self.refresh_supplies)
        filters.addStretch()
        filters.addWidget(self.refresh_supplies_button)

        self.supplies_list = QListWidget()
        self.supplies_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        add_row = QHBoxLayout()
        self.supply_name_input = QLineEdit()
        self.supply_name_input.setPlaceholderText("Supply item")
        self.supply_name_input.returnPressed.connect(self.add_supply)
        self.add_supply_button = QPushButton("Add")
        self.add_supply_button.clicked.connect(self.add_supply)
        add_row.addWidget(self.supply_name_input, 1)
        add_row.addWidget(self.add_supply_button)

        action_row = QHBoxLayout()
        self.toggle_supply_button = QPushButton("Mark done")
        self.toggle_supply_button.clicked.connect(self.toggle_selected_supply)
        self.delete_supply_button = QPushButton("Delete")
        self.delete_supply_button.clicked.connect(self.delete_selected_supply)
        action_row.addWidget(self.toggle_supply_button)
        action_row.addWidget(self.delete_supply_button)
        action_row.addStretch()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.supplies_status)
        layout.addLayout(filters)
        layout.addWidget(self.supplies_list, 1)
        layout.addLayout(add_row)
        layout.addLayout(action_row)
        return page

    def ensure_loaded(self) -> None:
        if not self._calendar_loaded:
            self.refresh_agenda()

    def show_page(self, index: int) -> None:
        self.stacked_widget.setCurrentIndex(index)
        for button_index, name in enumerate(("Agenda", "Supplies")):
            self.page_buttons[name].setChecked(button_index == index)
        if index == 1 and not self._supplies_loaded:
            self.refresh_supplies()

    def refresh_agenda(self) -> None:
        self.agenda_status.setText("Loading KaosGDD agenda...")
        self.client.load_calendar()

    def refresh_supplies(self) -> None:
        self.supplies_status.setText("Loading KaosGDD supplies...")
        self.client.load_supplies(self._supplies_mode)

    def set_supplies_mode(self, mode: str) -> None:
        self._supplies_mode = "done" if mode == "done" else "active"
        for name, button in self.supply_filter_buttons.items():
            button.setChecked(name == self._supplies_mode)
        self.toggle_supply_button.setText(
            "Reactivate" if self._supplies_mode == "done" else "Mark done"
        )
        self.refresh_supplies()

    def add_task(self) -> None:
        collection = self._task_collection()
        if collection is None:
            self.agenda_status.setText("No KaosGDD task collection is available.")
            return
        title, accepted = QInputDialog.getText(self, "Add task", "Task")
        title = title.strip()
        if not accepted or not title:
            return
        self.agenda_status.setText("Adding task...")
        self.client.create_task(
            {
                "collectionId": collection.get("id", ""),
                "title": title,
                "dueDate": self.calendar.selectedDate().toString("yyyy-MM-dd"),
                "dueTime": "",
                "priority": "",
                "memo": "",
            }
        )

    def toggle_selected_task(self) -> None:
        current = self.tasks_list.currentItem()
        task = current.data(ITEM_DATA_ROLE) if current is not None else None
        if not isinstance(task, dict):
            self.agenda_status.setText("Select a task first.")
            return
        completed = str(task.get("status", "")).upper() == "COMPLETED"
        self.agenda_status.setText("Updating task...")
        self.client.update_task(
            {
                "uid": task.get("uid", ""),
                "collectionId": task.get("collection", ""),
                "title": task.get("summary", ""),
                "memo": task.get("description", ""),
                "dueDate": task.get("due", ""),
                "dueTime": task.get("dueTime", ""),
                "priority": task.get("priority", ""),
                "status": "NEEDS-ACTION" if completed else "COMPLETED",
            }
        )

    def add_supply(self) -> None:
        title = self.supply_name_input.text().strip()
        if not title:
            self.supplies_status.setText("Enter a supply item first.")
            return
        self.supplies_status.setText("Adding supply item...")
        self.client.create_supply(title)

    def toggle_selected_supply(self) -> None:
        current = self.supplies_list.currentItem()
        supply = current.data(ITEM_DATA_ROLE) if current is not None else None
        if not isinstance(supply, dict) or not supply.get("id"):
            self.supplies_status.setText("Select a supply item first.")
            return
        status = "active" if self._supplies_mode == "done" else "done"
        self.supplies_status.setText("Updating supply item...")
        self.client.set_supply_status(str(supply["id"]), status)

    def delete_selected_supply(self) -> None:
        current = self.supplies_list.currentItem()
        supply = current.data(ITEM_DATA_ROLE) if current is not None else None
        if not isinstance(supply, dict) or not supply.get("id"):
            self.supplies_status.setText("Select a supply item first.")
            return
        if (
            QMessageBox.question(
                self,
                "Delete supply item",
                "Delete the selected supply item from KaosGDD?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.supplies_status.setText("Deleting supply item...")
        self.client.delete_supply(str(supply["id"]))

    def _request_succeeded(self, operation: str, payload: object) -> None:
        if not isinstance(payload, dict):
            self._request_failed(operation, "KaosGDD returned invalid data.")
            return
        if operation == "calendar":
            self._calendar_loaded = True
            self._events = _dict_list(payload.get("events"))
            self._tasks = _dict_list(payload.get("tasks"))
            self._collections = _dict_list(payload.get("collections"))
            self.agenda_status.setText(
                f"KaosGDD: {len(self._events)} events, {len(self._tasks)} tasks"
            )
            self._render_calendar_marks()
            self._render_selected_date()
            self._render_tasks()
            return
        if operation in {"task_create", "task_update"}:
            self.refresh_agenda()
            return
        if operation.startswith("supplies_"):
            self._supplies_loaded = True
            items = _dict_list(payload.get("items"))
            self._render_supplies(items)
            self.supplies_status.setText(
                f"KaosGDD Supplies: {len(items)} {self._supplies_mode}"
            )
            return
        if operation in {"supply_create", "supply_status", "supply_delete"}:
            self.supply_name_input.clear()
            self.refresh_supplies()

    def _request_failed(self, operation: str, message: str) -> None:
        if operation.startswith("suppl"):
            self.supplies_status.setText(message)
        else:
            self.agenda_status.setText(message)

    def _render_calendar_marks(self) -> None:
        empty_format = QTextCharFormat()
        for marked_date in self._highlighted_dates:
            self.calendar.setDateTextFormat(marked_date, empty_format)
        self._highlighted_dates = []

        event_format = QTextCharFormat()
        event_format.setForeground(QColor("#cba6f7"))
        event_format.setFontWeight(600)
        task_format = QTextCharFormat()
        task_format.setBackground(QColor("#45475a"))
        for item in self._events:
            self._mark_iso_date(str(item.get("startDate") or ""), event_format)
        for item in self._tasks:
            if str(item.get("status", "")).upper() != "COMPLETED":
                self._mark_iso_date(str(item.get("due") or ""), task_format)

    def _mark_iso_date(self, value: str, text_format: QTextCharFormat) -> None:
        marked_date = QDate.fromString(value, "yyyy-MM-dd")
        if not marked_date.isValid():
            return
        self.calendar.setDateTextFormat(marked_date, text_format)
        self._highlighted_dates.append(marked_date)

    def _render_selected_date(self) -> None:
        selected = self.calendar.selectedDate().toString("yyyy-MM-dd")
        self.events_list.clear()
        selected_events = [
            item for item in self._events if _event_includes_date(item, selected)
        ]
        if not selected_events:
            self.events_list.addItem("No events for this date.")
            return
        for event in sorted(
            selected_events,
            key=lambda item: (str(item.get("startTime") or ""), str(item.get("summary") or "")),
        ):
            time_text = str(event.get("startTime") or "All day")
            self.events_list.addItem(
                f"{time_text}  {str(event.get('summary') or 'Untitled event')}"
            )

    def _render_tasks(self) -> None:
        self.tasks_list.clear()
        ordered = sorted(
            self._tasks,
            key=lambda item: (
                str(item.get("status", "")).upper() == "COMPLETED",
                str(item.get("due") or "9999-12-31"),
                str(item.get("summary") or ""),
            ),
        )
        for task in ordered:
            completed = str(task.get("status", "")).upper() == "COMPLETED"
            marker = "[x]" if completed else "[ ]"
            due = str(task.get("due") or "No date")
            item = QListWidgetItem(
                f"{marker} {due}  {str(task.get('summary') or 'Untitled task')}"
            )
            item.setData(ITEM_DATA_ROLE, task)
            self.tasks_list.addItem(item)
        if not ordered:
            empty = QListWidgetItem("No tasks configured.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tasks_list.addItem(empty)

    def _render_supplies(self, supplies: list[dict]) -> None:
        self.supplies_list.clear()
        for supply in supplies:
            item = QListWidgetItem(str(supply.get("title") or "Untitled supply"))
            item.setData(ITEM_DATA_ROLE, supply)
            self.supplies_list.addItem(item)
        if not supplies:
            empty = QListWidgetItem("No supply tasks.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.supplies_list.addItem(empty)

    def _task_collection(self) -> dict | None:
        for collection in self._collections:
            components = collection.get("components") or []
            if not components or "VTODO" in components:
                return collection
        return None


def _dict_list(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _event_includes_date(event: dict, selected_date: str) -> bool:
    try:
        selected = date.fromisoformat(selected_date)
        start = date.fromisoformat(str(event.get("startDate") or ""))
        end = date.fromisoformat(str(event.get("endDate") or event.get("startDate") or ""))
    except ValueError:
        return False
    return start <= selected <= end
