import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from KaosEghis.core.kaospacs_patient_context_api import (
    PatientContextApiConfig,
    config_from_settings,
    lookup_patient_context,
    start_patient_context_api,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import create_pacs_worklist_item


def test_patient_context_config_defaults_bind_lan() -> None:
    config = config_from_settings({})

    assert config.enabled is True
    assert config.host == "0.0.0.0"
    assert config.port == 8765
    assert config.allow_loopback_without_token is True


def test_patient_context_config_uses_gateway_token() -> None:
    config = config_from_settings({"kaospacs_gateway_api_token": "secret-token"})

    assert config.token == "secret-token"


def test_lookup_patient_context_returns_korean_identity(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="M",
            chart_no="2735",
            study="흉부",
            modality="CR",
            requested_at="2026-07-16T09:00:00",
            accession_or_order_id="ACC-1",
            source="eghis-db",
        )

    result = lookup_patient_context("2735", db_path)

    assert result.status == "ok"
    assert result.payload == {
        "chart_no": "2735",
        "patient_name": "홍길동",
        "patient_birth_date": "19700101",
        "patient_sex": "M",
        "source": "eghis-db",
        "confidence": "exact",
    }


def test_lookup_patient_context_not_found(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)

    result = lookup_patient_context("2735", db_path)

    assert result.status == "not_found"


def test_lookup_patient_context_ambiguous_conflicting_identity(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="M",
            chart_no="2735",
        )
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="다른사람",
            patient_birth_date="19800101",
            patient_sex="F",
            chart_no="2735",
        )

    result = lookup_patient_context("2735", db_path)

    assert result.status == "ambiguous"


def test_patient_context_http_endpoint_allows_loopback_without_token(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        create_pacs_worklist_item(
            connection,
            status="active",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="M",
            chart_no="2735",
        )

    server = start_patient_context_api(
        PatientContextApiConfig(host="127.0.0.1", port=0, token="secret", db_path=db_path)
    )
    assert server is not None
    try:
        host, port = server.server.server_address
        response = urlopen(
            f"http://{host}:{port}/api/kaospacs/patient-context?chart_no=2735",
            timeout=3,
        )
        payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert payload["patient_name"] == "홍길동"
        assert payload["patient_birth_date"] == "19700101"
    finally:
        server.stop()


def test_patient_context_http_endpoint_requires_bearer_token_for_non_loopback(tmp_path) -> None:
    handler = start_patient_context_api(
        PatientContextApiConfig(
            host="127.0.0.1",
            port=0,
            token="secret",
            db_path=tmp_path / "missing.sqlite",
            allow_loopback_without_token=False,
        )
    )
    assert handler is not None
    try:
        host, port = handler.server.server_address
        try:
            urlopen(f"http://{host}:{port}/api/kaospacs/patient-context?chart_no=2735", timeout=3)
            raise AssertionError("expected unauthorized")
        except HTTPError as exc:
            assert exc.code == 401
    finally:
        handler.stop()


def test_patient_context_options_returns_cors_for_kaospacs_origin(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    server = start_patient_context_api(
        PatientContextApiConfig(host="127.0.0.1", port=0, token="secret", db_path=db_path)
    )
    assert server is not None
    try:
        host, port = server.server.server_address
        request = Request(
            f"http://{host}:{port}/api/kaospacs/patient-context?chart_no=2735",
            method="OPTIONS",
            headers={"Origin": "http://192.168.0.200"},
        )
        response = urlopen(request, timeout=3)

        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == "http://192.168.0.200"
    finally:
        server.stop()


def test_patient_context_health_does_not_require_auth(tmp_path) -> None:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    server = start_patient_context_api(
        PatientContextApiConfig(host="127.0.0.1", port=0, token="secret", db_path=db_path)
    )
    assert server is not None
    try:
        host, port = server.server.server_address
        response = urlopen(f"http://{host}:{port}/health", timeout=3)
        payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert payload["status"] == "ok"
    finally:
        server.stop()
