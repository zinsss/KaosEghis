from __future__ import annotations

import json

from PySide6.QtCore import QByteArray, QObject, Signal
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class FakeKaosGddClient(QObject):
    request_succeeded = Signal(str, object)
    request_failed = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple] = []

    def load_calendar(self) -> None:
        self.calls.append(("load_calendar",))

    def create_task(self, payload: dict) -> None:
        self.calls.append(("create_task", payload))

    def update_task(self, payload: dict) -> None:
        self.calls.append(("update_task", payload))

    def load_supplies(self, mode: str) -> None:
        self.calls.append(("load_supplies", mode))

    def create_supply(self, title: str) -> None:
        self.calls.append(("create_supply", title))

    def set_supply_status(self, supply_id: str, status: str) -> None:
        self.calls.append(("set_supply_status", supply_id, status))

    def delete_supply(self, supply_id: str) -> None:
        self.calls.append(("delete_supply", supply_id))


class FakeReply(QObject):
    finished = Signal()

    def error(self):
        return QNetworkReply.NetworkError.NoError

    def readAll(self):
        return QByteArray(b'{"items": []}')

    def deleteLater(self) -> None:
        pass


class FakeNetworkManager:
    def __init__(self) -> None:
        self.requests: list[tuple] = []

    def get(self, request):
        self.requests.append(("GET", request, QByteArray()))
        return FakeReply()

    def post(self, request, body):
        self.requests.append(("POST", request, body))
        return FakeReply()

    def sendCustomRequest(self, request, method, body):
        self.requests.append((bytes(method).decode("ascii"), request, body))
        return FakeReply()


def test_launcher_panel_defers_calendar_load_until_activation() -> None:
    _app()
    from KaosEghis.ui.launcher_agenda_panel import AgendaSuppliesPanel

    client = FakeKaosGddClient()
    panel = AgendaSuppliesPanel(client)

    assert client.calls == []
    assert panel.stacked_widget.currentWidget() is panel.agenda_page
    assert list(panel.page_buttons) == ["Agenda", "Supplies"]

    panel.ensure_loaded()
    assert client.calls == [("load_calendar",)]


def test_agenda_renders_kaosgdd_events_and_tasks() -> None:
    _app()
    from KaosEghis.ui.launcher_agenda_panel import AgendaSuppliesPanel

    client = FakeKaosGddClient()
    panel = AgendaSuppliesPanel(client)
    selected = panel.calendar.selectedDate().toString("yyyy-MM-dd")

    client.request_succeeded.emit(
        "calendar",
        {
            "configured": True,
            "live": True,
            "collections": [
                {"id": "tasks", "name": "Tasks", "components": ["VTODO"]}
            ],
            "events": [
                {
                    "uid": "event-1",
                    "summary": "Clinic event",
                    "startDate": selected,
                    "endDate": selected,
                    "startTime": "09:00",
                }
            ],
            "tasks": [
                {
                    "uid": "task-1",
                    "collection": "tasks",
                    "summary": "Call supplier",
                    "due": selected,
                    "status": "NEEDS-ACTION",
                }
            ],
        },
    )

    assert "Clinic event" in panel.events_list.item(0).text()
    assert "Call supplier" in panel.tasks_list.item(0).text()
    assert "1 events, 1 tasks" in panel.agenda_status.text()


def test_supplies_page_uses_kaosgdd_supply_api() -> None:
    _app()
    from KaosEghis.ui.launcher_agenda_panel import AgendaSuppliesPanel

    client = FakeKaosGddClient()
    panel = AgendaSuppliesPanel(client)

    panel.page_buttons["Supplies"].click()
    assert client.calls[-1] == ("load_supplies", "active")

    client.request_succeeded.emit(
        "supplies_active",
        {
            "items": [
                {
                    "id": "supply-1",
                    "title": "Printer labels",
                    "status": "active",
                }
            ]
        },
    )
    assert panel.supplies_list.item(0).text() == "Printer labels"

    panel.supplies_list.setCurrentRow(0)
    panel.toggle_selected_supply()
    assert client.calls[-1] == ("set_supply_status", "supply-1", "done")

    panel.supply_name_input.setText("Syringes")
    panel.add_supply()
    assert client.calls[-1] == ("create_supply", "Syringes")


def test_kaosgdd_client_uses_utf8_json_and_main_profile_header() -> None:
    _app()
    from KaosEghis.core.kaosgdd_client import KaosGddApiClient

    manager = FakeNetworkManager()
    client = KaosGddApiClient(
        "http://brain.test:8092/",
        network_manager=manager,
    )

    client.create_supply("한글 라벨")

    method, request, body = manager.requests[-1]
    assert method == "POST"
    assert request.url().toString() == "http://brain.test:8092/api/supplies"
    assert bytes(request.rawHeader("X-Forwarded-Host")) == b"kaosgdd.net"
    assert json.loads(bytes(body).decode("utf-8")) == {"title": "한글 라벨"}


def test_kaosgdd_brain_url_supports_environment_override(monkeypatch) -> None:
    from KaosEghis.core.kaosgdd_client import kaosgdd_brain_url

    monkeypatch.setenv("KAOSGDD_BRAIN_URL", "http://brain.example:9000/")
    assert kaosgdd_brain_url() == "http://brain.example:9000"
