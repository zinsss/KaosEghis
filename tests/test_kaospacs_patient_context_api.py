from __future__ import annotations

import json
import threading
import time
from urllib import error, request

import pytest

from KaosEghis.core.eghis_db import EghisDbUnavailableError
from KaosEghis.core.kaospacs_patient_context import (
    InvalidPatientIdError,
    PatientContextAmbiguousError,
    PatientContextNotFoundError,
    PatientContextRecord,
    PatientContextSourceUnavailableError,
    get_patient_context,
)
from KaosEghis.db.database import connect, initialize_database
from KaosEghis.db.repositories import set_settings
from KaosEghis.service import kaospacs_api


def test_patient_context_exact_chart_match_returns_normalized_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        "KaosEghis.core.kaospacs_patient_context.run_readonly_query",
        lambda _conn, _query: (
            ["chart_no", "patient_name", "patient_birth_date", "patient_sex"],
            [("2735", "홍길동", "1970-01-01", "남")],
        ),
    )

    result = get_patient_context({"eghis_db_connection_string": "dbname=test"}, "2735")

    assert result == PatientContextRecord(
        chart_no="2735",
        patient_name="홍길동",
        patient_birth_date="19700101",
        patient_sex="M",
        source="egHis",
        confidence="exact",
    )


def test_patient_context_not_found_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "KaosEghis.core.kaospacs_patient_context.run_readonly_query",
        lambda _conn, _query: (
            ["chart_no", "patient_name", "patient_birth_date", "patient_sex"],
            [],
        ),
    )

    with pytest.raises(PatientContextNotFoundError):
        get_patient_context({"eghis_db_connection_string": "dbname=test"}, "2735")


def test_patient_context_ambiguous_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "KaosEghis.core.kaospacs_patient_context.run_readonly_query",
        lambda _conn, _query: (
            ["chart_no", "patient_name", "patient_birth_date", "patient_sex"],
            [
                ("2735", "홍길동", "19700101", "M"),
                ("2735", "홍길동", "19700101", "M"),
            ],
        ),
    )

    with pytest.raises(PatientContextAmbiguousError):
        get_patient_context({"eghis_db_connection_string": "dbname=test"}, "2735")


def test_patient_context_source_unavailable_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "KaosEghis.core.kaospacs_patient_context.run_readonly_query",
        lambda _conn, _query: (_ for _ in ()).throw(EghisDbUnavailableError("db down")),
    )

    with pytest.raises(PatientContextSourceUnavailableError):
        get_patient_context({"eghis_db_connection_string": "dbname=test"}, "2735")


def test_patient_context_sex_normalizes_to_other(monkeypatch) -> None:
    monkeypatch.setattr(
        "KaosEghis.core.kaospacs_patient_context.run_readonly_query",
        lambda _conn, _query: (
            ["chart_no", "patient_name", "patient_birth_date", "patient_sex"],
            [("2735", "홍길동", "", "X")],
        ),
    )

    result = get_patient_context({"eghis_db_connection_string": "dbname=test"}, "2735")

    assert result.patient_sex == "O"


def test_invalid_patient_id_is_rejected_before_db_query(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(
        "KaosEghis.core.kaospacs_patient_context.run_readonly_query",
        lambda *_args: called.append(True),
    )

    with pytest.raises(InvalidPatientIdError):
        get_patient_context({"eghis_db_connection_string": "dbname=test"}, "../2735")

    assert called == []


def test_missing_chart_no_returns_400(tmp_path) -> None:
    response = _request_json(tmp_path, "/api/kaospacs/patient-context")
    assert response["status"] == 400
    assert response["body"] == {"error": "missing_chart_no"}


def test_exact_chart_match_endpoint_returns_utf8_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: PatientContextRecord(
            chart_no="2735",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="F",
        ),
    )

    response = _request_json(tmp_path, "/api/kaospacs/patient-context?chart_no=2735")

    assert response["status"] == 200
    assert response["body"] == {
        "chart_no": "2735",
        "patient_name": "홍길동",
        "patient_birth_date": "19700101",
        "patient_sex": "F",
        "source": "egHis",
        "confidence": "exact",
    }
    assert "diagnosis" not in response["body"]
    assert "phone" not in response["body"]
    assert "resident_id" not in response["body"]


def test_patient_context_path_returns_minimal_dicom_fields_utf8(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: PatientContextRecord(
            chart_no="2735",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="F",
        ),
    )

    response = _request_json(tmp_path, "/patients/context/2735")

    assert response["status"] == 200
    assert response["body"] == {
        "PatientID": "2735",
        "PatientName": "홍길동",
        "PatientBirthDate": "19700101",
        "PatientSex": "F",
        "source": "egHis",
    }


@pytest.mark.parametrize(
    "path",
    [
        "/patients/context/",
        "/patients/context/invalid%2Fid",
        "/patients/context/%27%20OR%201%3D1",
    ],
)
def test_patient_context_path_rejects_invalid_patient_id(tmp_path, path) -> None:
    response = _request_json(tmp_path, path)

    assert response["status"] == 400
    assert response["body"] == {"error": "invalid_patient_id"}


def test_not_found_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: (_ for _ in ()).throw(PatientContextNotFoundError()),
    )

    response = _request_json(tmp_path, "/api/kaospacs/patient-context?chart_no=2735")
    assert response["status"] == 404
    assert response["body"] == {"error": "not_found"}


def test_patient_context_path_not_found_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: (_ for _ in ()).throw(PatientContextNotFoundError()),
    )

    response = _request_json(tmp_path, "/patients/context/2735")
    assert response["status"] == 404
    assert response["body"] == {"error": "not_found"}


def test_ambiguous_returns_409(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: (_ for _ in ()).throw(PatientContextAmbiguousError()),
    )

    response = _request_json(tmp_path, "/api/kaospacs/patient-context?chart_no=2735")
    assert response["status"] == 409
    assert response["body"] == {"error": "ambiguous"}


def test_source_unavailable_returns_503(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: (_ for _ in ()).throw(
            PatientContextSourceUnavailableError()
        ),
    )

    response = _request_json(tmp_path, "/api/kaospacs/patient-context?chart_no=2735")
    assert response["status"] == 503
    assert response["body"] == {"error": "source_unavailable"}


def test_auth_required_when_token_configured(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(kaospacs_api.TOKEN_ENV_VAR, "shared-secret")

    response = _request_json(tmp_path, "/api/kaospacs/patient-context?chart_no=2735")
    assert response["status"] == 401
    assert response["body"] == {"error": "unauthorized"}


def test_wrong_token_returns_401(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(kaospacs_api.TOKEN_ENV_VAR, "shared-secret")

    response = _request_json(
        tmp_path,
        "/api/kaospacs/patient-context?chart_no=2735",
        token="wrong-token",
    )
    assert response["status"] == 401
    assert response["body"] == {"error": "unauthorized"}


def test_correct_token_allows_request(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(kaospacs_api.TOKEN_ENV_VAR, "shared-secret")
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: PatientContextRecord(
            chart_no="2735",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="M",
        ),
    )

    response = _request_json(
        tmp_path,
        "/api/kaospacs/patient-context?chart_no=2735",
        token="shared-secret",
    )
    assert response["status"] == 200
    assert response["body"]["patient_name"] == "홍길동"


def test_patient_context_path_requires_and_accepts_bearer_token(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(kaospacs_api.TOKEN_ENV_VAR, "shared-secret")
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: PatientContextRecord(
            chart_no="2735",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="M",
        ),
    )

    missing = _request_json(tmp_path, "/patients/context/2735")
    wrong = _request_json(tmp_path, "/patients/context/2735", token="wrong")
    accepted = _request_json(
        tmp_path, "/patients/context/2735", token="shared-secret"
    )

    assert missing["status"] == 401
    assert wrong["status"] == 401
    assert accepted["status"] == 200


def test_settings_token_allows_request_without_env_override(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(kaospacs_api.TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: PatientContextRecord(
            chart_no="2735",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="M",
        ),
    )

    response = _request_json(
        tmp_path,
        "/api/kaospacs/patient-context?chart_no=2735",
        token="settings-secret",
        settings={"kaospacs_integration_token": "settings-secret"},
    )

    assert response["status"] == 200
    assert response["body"]["patient_name"] == "홍길동"


def test_env_token_overrides_settings_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(kaospacs_api.TOKEN_ENV_VAR, "env-secret")
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: PatientContextRecord(
            chart_no="2735",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="M",
        ),
    )

    response = _request_json(
        tmp_path,
        "/api/kaospacs/patient-context?chart_no=2735",
        token="settings-secret",
        settings={"kaospacs_integration_token": "settings-secret"},
    )

    assert response["status"] == 401
    assert response["body"] == {"error": "unauthorized"}


def test_endpoint_request_path_does_not_initialize_local_db(tmp_path, monkeypatch) -> None:
    called = []
    monkeypatch.setattr(kaospacs_api, "initialize_database", lambda *_args, **_kwargs: called.append(True))
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: PatientContextRecord(
            chart_no="2735",
            patient_name="홍길동",
            patient_birth_date="19700101",
            patient_sex="M",
        ),
    )

    response = _request_json(tmp_path, "/api/kaospacs/patient-context?chart_no=2735")
    assert response["status"] == 200
    assert called == []


def test_resolve_host_and_port_use_settings_defaults() -> None:
    settings = {
        "kaospacs_patient_context_bind_host": "192.168.0.100",
        "kaospacs_patient_context_port": "8877",
    }

    assert kaospacs_api._resolve_host(None, settings) == "192.168.0.100"
    assert kaospacs_api._resolve_port(None, settings) == 8877


def test_resolve_port_falls_back_safely_on_invalid_setting() -> None:
    settings = {"kaospacs_patient_context_port": "not-a-port"}

    assert kaospacs_api._resolve_port(None, settings) == kaospacs_api.DEFAULT_PORT


def test_lan_bind_requires_configured_token(tmp_path, monkeypatch) -> None:
    for name in (
        kaospacs_api.TOKEN_ENV_VAR,
        kaospacs_api.TOKEN_ENV_VAR_PROMPT_ALIAS,
        kaospacs_api.LEGACY_TOKEN_ENV_VAR,
    ):
        monkeypatch.delenv(name, raising=False)
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        set_settings(
            connection,
            {
                "kaospacs_patient_context_bind_host": "0.0.0.0",
                "kaospacs_integration_token": "",
            },
        )

    with pytest.raises(RuntimeError, match="token is required"):
        kaospacs_api.run_server(db_path=db_path)


def test_patient_context_runtime_starts_and_stops_server(monkeypatch) -> None:
    events: list[str] = []

    class FakeServer:
        def serve_forever(self) -> None:
            events.append("serve")

        def shutdown(self) -> None:
            events.append("shutdown")

        def server_close(self) -> None:
            events.append("close")

    fake_server = FakeServer()
    monkeypatch.setattr(
        kaospacs_api,
        "create_server",
        lambda *_args, **_kwargs: fake_server,
    )

    runtime = kaospacs_api.start_server_in_thread()
    for _ in range(20):
        if "serve" in events:
            break
        time.sleep(0.01)
    runtime.stop()

    assert events == ["serve", "shutdown", "close"]


def test_patient_context_response_and_logs_exclude_unapproved_phi(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        kaospacs_api,
        "get_patient_context",
        lambda _settings, _chart_no: PatientContextRecord(
            chart_no="2735",
            patient_name="비공개이름",
            patient_birth_date="19700101",
            patient_sex="F",
        ),
    )

    response = _request_json(tmp_path, "/patients/context/2735")
    captured = capsys.readouterr()

    assert set(response["body"]) == {
        "PatientID",
        "PatientName",
        "PatientBirthDate",
        "PatientSex",
        "source",
    }
    assert "비공개이름" not in captured.out
    assert "비공개이름" not in captured.err
    assert "19700101" not in captured.out
    assert "19700101" not in captured.err


def _request_json(
    tmp_path,
    path: str,
    token: str | None = None,
    settings: dict[str, str] | None = None,
) -> dict[str, object]:
    db_path = tmp_path / "KaosEghis.sqlite"
    initialize_database(db_path)
    with connect(db_path) as connection:
        persisted_settings = {"eghis_db_connection_string": "dbname=test"}
        if settings:
            persisted_settings.update(settings)
        set_settings(connection, persisted_settings)

    handler = kaospacs_api._build_handler(db_path)
    server = kaospacs_api.KaosPacsApiServer(("127.0.0.1", 0), handler, db_path=db_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        headers = {"Accept": "application/json; charset=utf-8"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        req = request.Request(
            f"http://127.0.0.1:{server.server_port}{path}",
            headers=headers,
        )
        try:
            with request.urlopen(req, timeout=5) as resp:
                return {
                    "status": resp.status,
                    "body": json.loads(resp.read().decode("utf-8")),
                }
        except error.HTTPError as exc:
            return {
                "status": exc.code,
                "body": json.loads(exc.read().decode("utf-8")),
            }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
