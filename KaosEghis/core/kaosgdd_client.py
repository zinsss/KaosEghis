from __future__ import annotations

import json
import os
from urllib.parse import quote

from PySide6.QtCore import QByteArray, QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


DEFAULT_KAOSGDD_BRAIN_URL = "http://100.94.208.16:8092"


def kaosgdd_brain_url() -> str:
    return (
        os.environ.get("KAOSGDD_BRAIN_URL", "").strip()
        or DEFAULT_KAOSGDD_BRAIN_URL
    ).rstrip("/")


class KaosGddApiClient(QObject):
    request_succeeded = Signal(str, object)
    request_failed = Signal(str, str)

    def __init__(
        self,
        base_url: str | None = None,
        parent: QObject | None = None,
        *,
        network_manager=None,
    ) -> None:
        super().__init__(parent)
        self.base_url = (base_url or kaosgdd_brain_url()).rstrip("/")
        self._manager = network_manager or QNetworkAccessManager(self)

    def load_calendar(self) -> None:
        self._send("calendar", "GET", "/api/calendar/bootstrap")

    def create_task(self, payload: dict) -> None:
        self._send("task_create", "POST", "/api/calendar/tasks", payload)

    def update_task(self, payload: dict) -> None:
        self._send("task_update", "PUT", "/api/calendar/tasks", payload)

    def load_supplies(self, mode: str = "active") -> None:
        normalized = "done" if str(mode).strip().lower() == "done" else "active"
        self._send(
            f"supplies_{normalized}",
            "GET",
            f"/api/supplies?mode={normalized}",
        )

    def create_supply(self, title: str) -> None:
        self._send("supply_create", "POST", "/api/supplies", {"title": title})

    def set_supply_status(self, supply_id: str, status: str) -> None:
        normalized = "done" if str(status).strip().lower() == "done" else "active"
        encoded_id = quote(str(supply_id), safe="")
        self._send(
            "supply_status",
            "POST",
            f"/api/supplies/{encoded_id}/{normalized}",
        )

    def delete_supply(self, supply_id: str) -> None:
        encoded_id = quote(str(supply_id), safe="")
        self._send("supply_delete", "DELETE", f"/api/supplies/{encoded_id}")

    def _send(
        self,
        operation: str,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> None:
        request = QNetworkRequest(QUrl(f"{self.base_url}{path}"))
        request.setRawHeader(b"Accept", b"application/json; charset=utf-8")
        request.setRawHeader(b"X-Forwarded-Host", b"kaosgdd.net")
        request.setTransferTimeout(12_000)

        body = QByteArray()
        if payload is not None:
            request.setHeader(
                QNetworkRequest.KnownHeaders.ContentTypeHeader,
                "application/json; charset=utf-8",
            )
            body = QByteArray(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
            )

        if method == "GET":
            reply = self._manager.get(request)
        elif method == "POST":
            reply = self._manager.post(request, body)
        else:
            reply = self._manager.sendCustomRequest(
                request,
                QByteArray(method.encode("ascii")),
                body,
            )
        reply.finished.connect(
            lambda reply=reply, operation=operation: self._finish_request(
                operation,
                reply,
            )
        )

    def _finish_request(self, operation: str, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.request_failed.emit(operation, "KaosGDD unavailable.")
                return
            try:
                payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.request_failed.emit(operation, "KaosGDD returned invalid data.")
                return
            if not isinstance(payload, dict):
                self.request_failed.emit(operation, "KaosGDD returned invalid data.")
                return
            if payload.get("ok") is False:
                self.request_failed.emit(operation, "KaosGDD request failed.")
                return
            self.request_succeeded.emit(operation, payload)
        finally:
            reply.deleteLater()
