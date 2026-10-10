from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from KaosEghis.core.kaosorders_current_day_wire import SUCCESS_MEDIA_TYPE
from KaosEghis.service import kaosorders_synthetic_api as api


TOKEN = "synthetic-orders-v1-" + "0123456789abcdef" * 4


def test_runtime_is_disabled_unless_explicitly_enabled(monkeypatch):
    monkeypatch.delenv(api.ENABLED_ENV, raising=False)
    assert api.start_server_in_thread() is None
    monkeypatch.setenv(api.ENABLED_ENV, "true")
    assert api.start_server_in_thread() is None


def test_loopback_http_adapter_serves_only_authenticated_synthetic_fixture():
    server = api.create_server(port=0, token=TOKEN)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/api/v1/current-day/orders"
    try:
        request = Request(
            endpoint,
            headers={"Accept": SUCCESS_MEDIA_TYPE, "Authorization": f"Bearer {TOKEN}"},
        )
        with urlopen(request, timeout=2) as response:
            body = response.read()
            assert response.status == 200
            assert response.headers["Content-Type"] == SUCCESS_MEDIA_TYPE
            assert b'"verified_empty":true' in body

        try:
            urlopen(Request(endpoint, headers={"Accept": SUCCESS_MEDIA_TYPE}), timeout=2)
        except HTTPError as error:
            assert error.code == 401
            assert b'"authentication_required"' in error.read()
        else:
            raise AssertionError("missing bearer must fail")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_adapter_rejects_non_loopback_bind():
    try:
        api.create_server(host="0.0.0.0", port=0, token=TOKEN)
    except RuntimeError as error:
        assert str(error) == "synthetic_orders_loopback_required"
    else:
        raise AssertionError("non-loopback bind must fail")
