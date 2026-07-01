import json
from urllib import error

from KaosEghis.core.kaospacs_gateway_client import get_imaging_worklist


class _FakeResponse:
    def __init__(self, payload) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_get_imaging_worklist_calls_gateway_with_bearer_token(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_gateway_client as client

    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        return _FakeResponse({"entries": []})

    monkeypatch.setattr(client.request, "urlopen", fake_urlopen)

    get_imaging_worklist(
        {
            "kaospacs_gateway_url": "http://127.0.0.1:8060",
            "kaospacs_gateway_api_token": "token-123",
            "kaospacs_api_timeout_seconds": "5",
        }
    )

    assert captured["url"].endswith("/imaging/worklist")
    assert captured["headers"]["Authorization"] == "Bearer token-123"
    assert captured["headers"]["Accept"] == "application/json; charset=utf-8"


def test_get_imaging_worklist_preserves_korean_text(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_gateway_client as client

    monkeypatch.setattr(
        client.request,
        "urlopen",
        lambda req, timeout=0: _FakeResponse(
            {
                "entries": [
                    {
                        "state": "active",
                        "PatientName": "홍길동",
                        "Description": "골밀도 검사",
                    }
                ]
            }
        ),
    )

    rows = get_imaging_worklist({"kaospacs_gateway_url": "http://127.0.0.1:8060"})

    assert rows[0]["PatientName"] == "홍길동"
    assert rows[0]["Description"] == "골밀도 검사"


def test_get_imaging_worklist_gateway_unavailable(monkeypatch) -> None:
    import KaosEghis.core.kaospacs_gateway_client as client

    monkeypatch.setattr(
        client.request,
        "urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(error.URLError("down")),
    )

    try:
        get_imaging_worklist({"kaospacs_gateway_url": "http://127.0.0.1:8060"})
    except RuntimeError as exc:
        assert "down" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
