from __future__ import annotations

import json
from urllib import error, request


def get_imaging_worklist(settings: dict[str, str]) -> list[dict]:
    payload = _request_json(settings, "GET", "/imaging/worklist")
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("entries"), list):
            entries = payload["entries"]
        elif isinstance(payload.get("items"), list):
            entries = payload["items"]
        elif isinstance(payload.get("worklist"), list):
            entries = payload["worklist"]
        else:
            raise RuntimeError("invalid gateway payload")
    else:
        raise RuntimeError("invalid gateway payload")

    normalized = []
    for entry in entries:
        if isinstance(entry, dict):
            normalized.append(entry)
    return normalized


def _request_json(
    settings: dict[str, str],
    method: str,
    path: str,
) -> dict | list:
    base_url = (
        settings.get("kaospacs_gateway_url") or "http://127.0.0.1:8060"
    ).strip().rstrip("/")
    timeout_seconds = float(settings.get("kaospacs_api_timeout_seconds") or "5")
    token = (settings.get("kaospacs_gateway_api_token") or "").strip()
    headers = {"Accept": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    http_request = request.Request(
        f"{base_url}{path}",
        method=method,
        headers=headers,
    )

    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raise RuntimeError(exc.reason or "gateway unavailable") from exc
    except error.URLError as exc:
        raise RuntimeError(exc.reason or "gateway unavailable") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid gateway payload") from exc
