"""Opt-in loopback adapter for the synthetic current-day Orders contract."""

from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import threading
from urllib.parse import urlsplit

from KaosEghis.core import current_day_provider_lifecycle as lifecycle
from KaosEghis.core import kaosorders_current_day_orders as facts_model
from KaosEghis.core import kaosorders_current_day_wire as wire

ENABLED_ENV = "KAOSEGHIS_ORDERS_SYNTHETIC_ENABLED"
TOKEN_ENV = "KAOSEGHIS_ORDERS_SYNTHETIC_TOKEN"
HOST_ENV = "KAOSEGHIS_ORDERS_SYNTHETIC_HOST"
PORT_ENV = "KAOSEGHIS_ORDERS_SYNTHETIC_PORT"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766


def is_enabled() -> bool:
    return os.environ.get(ENABLED_ENV, "").strip() == "1"


def _identity(value: str) -> lifecycle.OpaqueIdentity:
    return lifecycle.OpaqueIdentity(value)


def _build_fixture(now: datetime):
    day = lifecycle.clinic_day_at(now)
    facts = facts_model.validate_synthetic_collection(
        "synthetic-eghis", day, (), (), synthetic_fixture=True
    )
    lease = lifecycle.SingletonLeaseClaim(
        _identity("synthetic-orders-runtime"),
        _identity("synthetic-orders-runtime-lease"),
        True,
    )
    state = lifecycle.start_provider(
        now=now,
        provider_session_id=_identity("synthetic-runtime-session"),
        provider_generation=_identity("synthetic-runtime-generation"),
        lease=lease,
        stable_jitter_seconds=0,
    )
    state, ticket = lifecycle.request_refresh(state, now=now)
    empty = lifecycle.DestinationState(
        lifecycle.ProjectionAvailability.VERIFIED_EMPTY, 0, 0
    )
    state = lifecycle.complete_success(
        state,
        ticket,
        lifecycle.ObservationCandidate(day, now, empty, empty),
        now=now,
        lease=lease,
    )
    scope = wire.SyntheticOrdersScope(
        "synthetic-clinic",
        "synthetic-eghis",
        "synthetic-mapping-v1",
        synthetic_fixture=True,
    )
    return state, wire.SyntheticOrdersProjection(
        scope, state.snapshot, facts, synthetic_fixture=True
    )


class SyntheticOrdersRuntime:
    def __init__(self, server: ThreadingHTTPServer, thread: threading.Thread) -> None:
        self.server = server
        self.thread = thread

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def create_server(
    host: str | None = None, port: int | None = None, *, token: str | None = None
) -> ThreadingHTTPServer:
    resolved_host = (host or os.environ.get(HOST_ENV, DEFAULT_HOST)).strip()
    if resolved_host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("synthetic_orders_loopback_required")
    resolved_port = port if port is not None else int(os.environ.get(PORT_ENV, DEFAULT_PORT))
    resolved_token = (token or os.environ.get(TOKEN_ENV, "")).strip()
    identity = wire.SyntheticBearerIdentity(
        resolved_token, wire.AUDIENCE, "synthetic-clinic", "synthetic-eghis",
        "kaosorders-current-day-orders-v1", wire.SCHEMA_VERSION,
        wire.SyntheticIdentityStatus.ACTIVE, synthetic_fixture=True,
    )
    identities = wire.SyntheticIdentitySet((identity,), synthetic_fixture=True)

    class Handler(BaseHTTPRequestHandler):
        server_version = "KaosEghisSyntheticOrders/1"

        def do_GET(self) -> None:  # noqa: N802
            now = datetime.now(timezone.utc)
            state, projection = _build_fixture(now)
            parsed = urlsplit(self.path)
            request = wire.InProcessOrdersRequest(
                "GET", parsed.path, parsed.query,
                tuple(
                    (name, value)
                    for name in ("Accept", "Authorization", "Content-Encoding")
                    if (value := self.headers.get(name)) is not None
                ),
                b"",
            )
            response = wire.handle_orders_request(
                request, state=state, projection=projection,
                identities=identities, now=now,
            )
            self.send_response(response.status)
            for name, value in response.headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return ThreadingHTTPServer((resolved_host, resolved_port), Handler)


def start_server_in_thread() -> SyntheticOrdersRuntime | None:
    if not is_enabled():
        return None
    server = create_server()
    thread = threading.Thread(
        target=server.serve_forever, name="KaosEghisSyntheticOrdersApi", daemon=True
    )
    thread.start()
    return SyntheticOrdersRuntime(server, thread)
