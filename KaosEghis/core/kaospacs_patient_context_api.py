from __future__ import annotations

import hmac
import json
import logging
import os
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from KaosEghis.db.database import connect, get_database_path

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PatientContextApiConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8765
    token: str = ""
    db_path: Path | None = None
    allow_loopback_without_token: bool = True


@dataclass(frozen=True)
class PatientContextApiServer:
    server: ThreadingHTTPServer
    thread: threading.Thread

    def stop(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()


def config_from_settings(settings: dict[str, str]) -> PatientContextApiConfig:
    token = (
        os.getenv("KAOSPACS_INTEGRATION_TOKEN", "").strip()
        or settings.get("kaospacs_patient_context_api_token", "").strip()
        or settings.get("kaospacs_gateway_api_token", "").strip()
    )
    return PatientContextApiConfig(
        enabled=_bool_setting(settings.get("kaospacs_patient_context_api_enabled"), True),
        host=(
            os.getenv("KAOSPACS_PATIENT_CONTEXT_API_HOST", "").strip()
            or settings.get("kaospacs_patient_context_api_host", "").strip()
            or "0.0.0.0"
        ),
        port=_int_setting(
            os.getenv("KAOSPACS_PATIENT_CONTEXT_API_PORT", "").strip()
            or settings.get("kaospacs_patient_context_api_port", "").strip(),
            8765,
        ),
        token=token,
        db_path=get_database_path(),
        allow_loopback_without_token=_bool_setting(
            settings.get("kaospacs_patient_context_api_allow_loopback_without_token"),
            True,
        ),
    )


def start_patient_context_api(config: PatientContextApiConfig) -> PatientContextApiServer | None:
    if not config.enabled:
        LOGGER.info("KaosPACS patient-context API disabled")
        return None

    handler = create_patient_context_handler(config)
    server = ThreadingHTTPServer((config.host, config.port), handler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="kaospacs-patient-context-api",
        daemon=True,
    )
    thread.start()
    LOGGER.info(
        "KaosPACS patient-context API started host=%s port=%s auth_enabled=%s",
        config.host,
        config.port,
        bool(config.token),
    )
    return PatientContextApiServer(server=server, thread=thread)


def create_patient_context_handler(
    config: PatientContextApiConfig,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "KaosEghisPatientContext/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._json({"status": "ok", "service": "kaoseghis-pacs"})
                return
            if parsed.path != "/api/kaospacs/patient-context":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not self._authorized():
                self._json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return

            params = parse_qs(parsed.query)
            chart_no = (params.get("chart_no", [""])[0] or "").strip()
            if not chart_no:
                self._json({"error": "missing_chart_no"}, HTTPStatus.BAD_REQUEST)
                return

            result = lookup_patient_context(chart_no, config.db_path)
            if result.status == "not_found":
                self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            if result.status == "ambiguous":
                self._json({"error": "ambiguous"}, HTTPStatus.CONFLICT)
                return
            self._json(result.payload)

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, fmt: str, *args: Any) -> None:
            parsed = urlparse(getattr(self, "path", ""))
            client_ip = self.client_address[0] if self.client_address else "-"
            LOGGER.info(
                "Patient-context API request method=%s path=%s client_ip=%s",
                getattr(self, "command", "-"),
                parsed.path or "-",
                client_ip,
            )

        def _authorized(self) -> bool:
            if config.allow_loopback_without_token and self._is_loopback_client():
                return True
            if not config.token:
                return True
            header = self.headers.get("Authorization", "")
            prefix = "Bearer "
            if not header.startswith(prefix):
                return False
            supplied = header[len(prefix) :].strip()
            return hmac.compare_digest(supplied, config.token)

        def _is_loopback_client(self) -> bool:
            client_ip = self.client_address[0] if self.client_address else ""
            return client_ip in {"127.0.0.1", "::1"}

        def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_cors_headers(self) -> None:
            origin = self.headers.get("Origin", "")
            if _allowed_origin(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Accept, Authorization")
                self.send_header("Access-Control-Allow-Private-Network", "true")

    return Handler


@dataclass(frozen=True)
class LookupResult:
    status: str
    payload: dict[str, str]


def lookup_patient_context(chart_no: str, db_path: Path | None = None) -> LookupResult:
    chart_no = str(chart_no or "").strip()
    if not chart_no:
        return LookupResult("not_found", {})

    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT patient_name, patient_birth_date, patient_sex, chart_no, source
            FROM pacs_worklist_items
            WHERE chart_no = ?
              AND COALESCE(patient_name, '') != ''
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT 20
            """,
            (chart_no,),
        ).fetchall()

    candidates = []
    seen = set()
    for row in rows:
        candidate = {
            "chart_no": str(row[3] or "").strip(),
            "patient_name": str(row[0] or "").strip(),
            "patient_birth_date": str(row[1] or "").strip(),
            "patient_sex": str(row[2] or "").strip(),
            "source": str(row[4] or "eghis").strip() or "eghis",
        }
        identity = (
            candidate["patient_name"],
            candidate["patient_birth_date"],
            candidate["patient_sex"],
        )
        if identity not in seen:
            seen.add(identity)
            candidates.append(candidate)

    if not candidates:
        return LookupResult("not_found", {})
    if len(candidates) > 1:
        return LookupResult("ambiguous", {})

    payload = candidates[0] | {"confidence": "exact"}
    return LookupResult("ok", payload)


def _bool_setting(raw: str | None, default: bool) -> bool:
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_setting(raw: str | None, default: int) -> int:
    try:
        return int(raw or "")
    except ValueError:
        return default


def _allowed_origin(origin: str) -> bool:
    return origin in {
        "http://192.168.0.200",
        "http://192.168.0.200:8070",
        "http://127.0.0.1",
        "http://127.0.0.1:8070",
        "http://localhost",
        "http://localhost:8070",
    }
