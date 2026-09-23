from __future__ import annotations

import argparse
import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import threading
from urllib.parse import parse_qs, unquote, urlparse

from KaosEghis.core.kaospacs_patient_context import (
    InvalidPatientIdError,
    PatientContextAmbiguousError,
    PatientContextNotFoundError,
    PatientContextSourceUnavailableError,
    get_patient_context,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import get_settings


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
TOKEN_ENV_VAR = "KAOSEGHIS_PACS_API_TOKEN"
TOKEN_ENV_VAR_PROMPT_ALIAS = "KAOSEGHiS_PACS_API_TOKEN"
LEGACY_TOKEN_ENV_VAR = "KAOSPACS_INTEGRATION_TOKEN"
PATIENT_CONTEXT_PATH_PREFIX = "/patients/context/"
LEGACY_PATIENT_CONTEXT_PATH = "/api/kaospacs/patient-context"


class KaosPacsApiServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        db_path: Path | None = None,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.db_path = db_path


class PatientContextApiRuntime:
    def __init__(
        self,
        server: KaosPacsApiServer,
        thread: threading.Thread,
    ) -> None:
        self.server = server
        self.thread = thread

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def create_server(
    host: str | None = None,
    port: int | None = None,
    *,
    db_path: Path | None = None,
) -> KaosPacsApiServer:
    initialize_database(db_path)
    settings = _load_service_settings(db_path)
    resolved_host = _resolve_host(host, settings)
    resolved_port = _resolve_port(port, settings)
    if not _is_loopback_host(resolved_host) and not _configured_token(settings):
        raise RuntimeError(
            "Patient-context API token is required when binding beyond loopback."
        )
    handler = _build_handler(db_path)
    return KaosPacsApiServer((resolved_host, resolved_port), handler, db_path=db_path)


def start_server_in_thread(
    host: str | None = None,
    port: int | None = None,
    *,
    db_path: Path | None = None,
) -> PatientContextApiRuntime:
    server = create_server(host, port, db_path=db_path)
    thread = threading.Thread(
        target=server.serve_forever,
        name="KaosEghisPatientContextApi",
        daemon=True,
    )
    thread.start()
    return PatientContextApiRuntime(server, thread)


def run_server(
    host: str | None = None,
    port: int | None = None,
    *,
    db_path: Path | None = None,
) -> int:
    server = create_server(host, port, db_path=db_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--db-path", default="")
    args = parser.parse_args(argv)
    db_path = Path(args.db_path) if args.db_path else None
    return run_server(
        args.host.strip() or None,
        args.port or None,
        db_path=db_path,
    )


def _build_handler(db_path: Path | None) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "KaosEghisPacsAPI/0.1"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            is_legacy_route = parsed.path == LEGACY_PATIENT_CONTEXT_PATH
            if parsed.path.startswith(PATIENT_CONTEXT_PATH_PREFIX):
                chart_no = unquote(parsed.path.removeprefix(PATIENT_CONTEXT_PATH_PREFIX))
            elif is_legacy_route:
                chart_no = (parse_qs(parsed.query).get("chart_no") or [""])[0]
            else:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return

            if not self._is_authorized():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return

            settings = self._load_settings()
            try:
                patient_context = get_patient_context(settings, chart_no)
            except InvalidPatientIdError:
                error_code = "missing_chart_no" if is_legacy_route and not chart_no else "invalid_patient_id"
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": error_code})
                return
            except PatientContextNotFoundError:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            except PatientContextAmbiguousError:
                self._write_json(HTTPStatus.CONFLICT, {"error": "ambiguous"})
                return
            except PatientContextSourceUnavailableError:
                self._write_json(
                    HTTPStatus.SERVICE_UNAVAILABLE, {"error": "source_unavailable"}
                )
                return

            payload = (
                _legacy_patient_context_payload(patient_context)
                if is_legacy_route
                else _patient_context_payload(patient_context)
            )
            self._write_json(HTTPStatus.OK, payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _load_settings(self) -> dict[str, str]:
            try:
                with connect(db_path) as connection:
                    return get_settings(connection)
            except sqlite3.Error:
                return {}

        def _is_authorized(self) -> bool:
            configured_token = _configured_token(self._load_settings())
            if not configured_token:
                return True
            header_value = self.headers.get("Authorization", "")
            if not header_value.startswith("Bearer "):
                return False
            provided_token = header_value.removeprefix("Bearer ").strip()
            return hmac.compare_digest(provided_token, configured_token)

        def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _load_service_settings(db_path: Path | None) -> dict[str, str]:
    try:
        with connect(db_path) as connection:
            return get_settings(connection)
    except sqlite3.Error:
        return {}


def _resolve_host(host: str | None, settings: dict[str, str]) -> str:
    return (host or settings.get("kaospacs_patient_context_bind_host") or DEFAULT_HOST).strip() or DEFAULT_HOST


def _resolve_port(port: int | None, settings: dict[str, str]) -> int:
    if port is not None:
        return port
    try:
        resolved_port = int((settings.get("kaospacs_patient_context_port") or "").strip())
    except ValueError:
        return DEFAULT_PORT
    if resolved_port <= 0 or resolved_port > 65535:
        return DEFAULT_PORT
    return resolved_port


def _configured_token(settings: dict[str, str]) -> str:
    return (
        os.environ.get(TOKEN_ENV_VAR, "").strip()
        or os.environ.get(TOKEN_ENV_VAR_PROMPT_ALIAS, "").strip()
        or os.environ.get(LEGACY_TOKEN_ENV_VAR, "").strip()
        or settings.get("kaospacs_integration_token", "").strip()
    )


def _is_loopback_host(host: str) -> bool:
    return host.strip().casefold() in {"127.0.0.1", "::1", "localhost"}


def _patient_context_payload(patient_context) -> dict[str, str]:
    return {
        "PatientID": patient_context.chart_no,
        "PatientName": patient_context.patient_name,
        "PatientBirthDate": patient_context.patient_birth_date,
        "PatientSex": patient_context.patient_sex,
        "source": patient_context.source,
    }


def _legacy_patient_context_payload(patient_context) -> dict[str, str]:
    return {
        "chart_no": patient_context.chart_no,
        "patient_name": patient_context.patient_name,
        "patient_birth_date": patient_context.patient_birth_date,
        "patient_sex": patient_context.patient_sex,
        "source": patient_context.source,
        "confidence": patient_context.confidence,
    }


if __name__ == "__main__":
    raise SystemExit(main())
