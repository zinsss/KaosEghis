import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from KaosEghis.core import current_day_provider_lifecycle as lifecycle
from KaosEghis.core import kaosorders_current_day_orders as facts_model
from KaosEghis.core import kaosorders_current_day_wire as wire


NOW = datetime(2026, 10, 8, 1, 2, 3, 456789, tzinfo=timezone.utc)
DAY = date(2026, 10, 8)
ORDERS_TOKEN = "synthetic-orders-v1-" + "0123456789abcdef" * 4
OTHER_TOKEN = "synthetic-other-v1-" + "fedcba9876543210" * 4


def identity(value):
    return lifecycle.OpaqueIdentity(value)


def lease():
    return lifecycle.SingletonLeaseClaim(identity("synthetic-scope"), identity("synthetic-lease"), True)


def bearer(
    *,
    token=ORDERS_TOKEN,
    audience="orders",
    source_id="synthetic-eghis",
    projection_id="kaosorders-current-day-orders-v1",
    contract_version=1,
    status=wire.SyntheticIdentityStatus.ACTIVE,
):
    return wire.SyntheticBearerIdentity(
        token,
        audience,
        "synthetic-clinic",
        source_id,
        projection_id,
        contract_version,
        status,
        synthetic_fixture=True,
    )


def identity_set(*identities):
    return wire.SyntheticIdentitySet(
        tuple(identities or (bearer(),)), synthetic_fixture=True
    )


def facts(*, empty=False, source_id="synthetic-eghis"):
    if empty:
        return facts_model.validate_synthetic_collection(
            source_id, DAY, (), (), synthetic_fixture=True
        )
    parent = facts_model.SyntheticCurrentDayParent(
        "synthetic-encounter-1",
        "SYNTHETIC-0001",
        "Synthetic Alpha",
        "F",
        42,
        facts_model.IncludedParentState.CONSULTATION_COMPLETED,
        facts_model.ParentQualifiers("N", synthetic_fixture=True),
        synthetic_fixture=True,
    )
    child = facts_model.SyntheticCurrentDayChild(
        facts_model.CurrentDayOrderKey(
            "synthetic-encounter-1", DAY, "7", "2", synthetic_fixture=True
        ),
        "SYN-CATALOG",
        "Synthetic catalog",
        None,
        "",
        "SYN-TYPE",
        "SYN-DEPT",
        facts_model.ChildState.ACTIVE,
        facts_model.ChildQualifiers("N", "Y", synthetic_fixture=True),
        synthetic_fixture=True,
    )
    return facts_model.validate_synthetic_collection(
        source_id, DAY, (parent,), (child,), synthetic_fixture=True
    )


def published(*, empty=False, observed_at=NOW):
    projected = facts(empty=empty)
    owner = lifecycle.start_provider(
        now=NOW,
        provider_session_id=identity("synthetic-session-a"),
        provider_generation=identity("synthetic-generation-a"),
        lease=lease(),
        stable_jitter_seconds=0,
    )
    active, ticket = lifecycle.request_refresh(owner, now=NOW)
    orders = lifecycle.DestinationState(
        lifecycle.ProjectionAvailability.VERIFIED_EMPTY
        if empty
        else lifecycle.ProjectionAvailability.AVAILABLE,
        len(projected.parents) + len(projected.children),
        0 if empty else 17,
    )
    reception = lifecycle.DestinationState(
        lifecycle.ProjectionAvailability.AVAILABLE, 1, 23
    )
    state = lifecycle.complete_success(
        active,
        ticket,
        lifecycle.ObservationCandidate(DAY, observed_at, orders, reception),
        now=max(NOW, observed_at),
        lease=active.lease,
    )
    scope = wire.SyntheticOrdersScope(
        "synthetic-clinic",
        "synthetic-eghis",
        "synthetic-mapping-v1",
        synthetic_fixture=True,
    )
    projection = wire.SyntheticOrdersProjection(
        scope, state.snapshot, projected, synthetic_fixture=True
    )
    return state, projection


def request(*, method="GET", path=wire.PATH, query="", headers=None, body=b""):
    return wire.InProcessOrdersRequest(
        method,
        path,
        query,
        headers
        if headers is not None
        else (
            ("Accept", wire.SUCCESS_MEDIA_TYPE),
            ("Authorization", f"Bearer {ORDERS_TOKEN}"),
        ),
        body,
    )


def handle(req=None, *, state=None, projection=None, identities=None, now=NOW, rate=None):
    if state is None and projection is None:
        state, projection = published()
    return wire.handle_orders_request(
        req or request(),
        state=state,
        projection=projection,
        identities=identities or identity_set(),
        now=now,
        rate_limit_retry_after=rate,
    )


def decoded(response):
    return json.loads(response.body.decode("utf-8"))


def unsafe_replace(instance, **changes):
    """Build malformed synthetic inputs that exercise downstream fail-closed guards."""

    clone = object.__new__(type(instance))
    for field in fields(instance):
        object.__setattr__(
            clone,
            field.name,
            changes.get(field.name, getattr(instance, field.name)),
        )
    return clone


def forged_sequence(sequence):
    state, projection = published()
    cursor = unsafe_replace(state.snapshot.cursor, snapshot_sequence=sequence)
    snapshot = unsafe_replace(state.snapshot, cursor=cursor)
    return (
        unsafe_replace(state, snapshot=snapshot),
        unsafe_replace(projection, snapshot=snapshot),
    )


def test_literal_contract_values_are_not_derived_from_implementation():
    assert wire.METHOD == "GET"
    assert wire.PATH == "/api/v1/current-day/orders"
    assert wire.SUCCESS_MEDIA_TYPE == "application/vnd.kaosclinic.current-day-orders+json;version=1"
    assert wire.ERROR_MEDIA_TYPE == "application/vnd.kaosclinic.current-day-orders-error+json;version=1"
    assert wire.SUCCESS_SCHEMA_ID == "kaosorders.current-day-orders-snapshot"
    assert wire.ERROR_SCHEMA_ID == "kaosorders.current-day-orders-error"
    assert wire.SCHEMA_VERSION == 1
    assert wire.AUDIENCE == "orders"
    assert wire.SNAPSHOT_KIND == "FULL"
    assert wire.MAX_BODY_BYTES == 16_777_216
    assert wire.MAX_FRESHNESS_SECONDS == 300
    assert wire.MAX_FUTURE_SECONDS == 30
    assert wire.MAX_SNAPSHOT_SEQUENCE == 9_007_199_254_740_991
    assert lifecycle.MAX_SNAPSHOT_SEQUENCE == 9_007_199_254_740_991


def test_literal_maximum_snapshot_sequence_has_exact_canonical_json_parity():
    state, projection = published()
    cursor = replace(
        state.snapshot.cursor, snapshot_sequence=9_007_199_254_740_991
    )
    snapshot = replace(state.snapshot, cursor=cursor)
    bounded_state = replace(state, snapshot=snapshot)
    bounded_projection = wire.SyntheticOrdersProjection(
        projection.scope, snapshot, projection.facts, synthetic_fixture=True
    )

    serialized = wire.serialize_orders_success(bounded_projection, bearer())
    assert b'"snapshot_sequence":9007199254740991' in serialized.canonical_content
    assert json.loads(serialized.body)["snapshot_sequence"] == 9_007_199_254_740_991
    assert handle(state=bounded_state, projection=bounded_projection).status == 200


@pytest.mark.parametrize(
    "invalid",
    [
        9_007_199_254_740_992,
        9_007_199_254_740_993,
        9_223_372_036_854_775_807,
        True,
        "9007199254740991",
    ],
)
def test_serializer_and_handler_reject_sequence_overflow_and_coercion(invalid):
    state, projection = forged_sequence(invalid)
    with pytest.raises(wire.OrdersWireRejected, match="^projection_invalid$"):
        wire.serialize_orders_success(projection, bearer())

    response = handle(state=state, projection=projection)
    assert response.status == 503
    assert decoded(response)["code"] == "projection_invalid"


def test_populated_canonical_fixture_bytes_and_digest_are_exact():
    _state, projection = published()
    result = wire.serialize_orders_success(projection, bearer())
    assert result.content_sha256 == "97816f3a382ed17703c817c5c0cea6cf16f9590e94de0112adb6af5c66651b0d"
    assert sha256(result.canonical_content).hexdigest() == result.content_sha256
    assert b'"content_sha256"' not in result.canonical_content
    assert result.body == (
        b'{"audience":"orders","clinic_day":"2026-10-08","clinic_id":"synthetic-clinic",'
        b'"complete":true,"content_sha256":"97816f3a382ed17703c817c5c0cea6cf16f9590e94de0112adb6af5c66651b0d",'
        b'"encounters":[{"age":42,"chart_number":"SYNTHETIC-0001","encounter_id":"synthetic-encounter-1",'
        b'"patient_name":"Synthetic Alpha","qualifiers":{"hold_yn":"N"},"sex":"F",'
        b'"state":"CONSULTATION_COMPLETED"}],"mapping_revision":"synthetic-mapping-v1",'
        b'"observed_at":"2026-10-08T01:02:03.456789Z","orders":[{"catalog_code":"SYN-CATALOG",'
        b'"catalog_name":"Synthetic catalog","department_code":"SYN-DEPT","key":{'
        b'"encounter_id":"synthetic-encounter-1","order_date":"2026-10-08","order_number":"7",'
        b'"order_sequence":"2"},"order_type":"SYN-TYPE","qualifiers":{"act_yn":"Y","dc_yn":"N"},'
        b'"state":"ACTIVE","user_code":null,"user_name":""}],'
        b'"projection_id":"kaosorders-current-day-orders-v1","provider_generation":"synthetic-generation-a",'
        b'"provider_session_id":"synthetic-session-a","schema_id":"kaosorders.current-day-orders-snapshot",'
        b'"schema_version":1,"snapshot_kind":"FULL","snapshot_sequence":1,'
        b'"source_id":"synthetic-eghis","verified_empty":false}'
    )


def test_verified_empty_canonical_fixture_bytes_and_digest_are_exact():
    _state, projection = published(empty=True)
    result = wire.serialize_orders_success(projection, bearer())
    assert result.content_sha256 == "0adc8179c48148fb09e3918f571d89c27b26b56e31b08131ae43ae1bf4f584c1"
    assert sha256(result.canonical_content).hexdigest() == result.content_sha256
    assert b'"content_sha256"' not in result.canonical_content
    assert result.body == (
        b'{"audience":"orders","clinic_day":"2026-10-08","clinic_id":"synthetic-clinic",'
        b'"complete":true,"content_sha256":"0adc8179c48148fb09e3918f571d89c27b26b56e31b08131ae43ae1bf4f584c1",'
        b'"encounters":[],"mapping_revision":"synthetic-mapping-v1",'
        b'"observed_at":"2026-10-08T01:02:03.456789Z","orders":[],'
        b'"projection_id":"kaosorders-current-day-orders-v1","provider_generation":"synthetic-generation-a",'
        b'"provider_session_id":"synthetic-session-a","schema_id":"kaosorders.current-day-orders-snapshot",'
        b'"schema_version":1,"snapshot_kind":"FULL","snapshot_sequence":1,'
        b'"source_id":"synthetic-eghis","verified_empty":true}'
    )


def test_runtime_fixture_factory_builds_verified_empty_projection_inside_wire_boundary():
    state, projection = wire.build_empty_synthetic_fixture(NOW)

    assert state.snapshot is projection.snapshot
    assert projection.scope.source_id == "synthetic-eghis"
    assert projection.facts.parents == projection.facts.children == ()
    assert (
        state.snapshot.orders.availability
        is lifecycle.ProjectionAvailability.VERIFIED_EMPTY
    )


def test_success_handler_has_exact_closed_envelope_headers_and_ordered_facts():
    response = handle()
    assert response.status == 200
    assert response.headers == (
        ("Content-Type", "application/vnd.kaosclinic.current-day-orders+json;version=1"),
        ("Cache-Control", "no-store, private, max-age=0"),
        ("Pragma", "no-cache"),
        ("Expires", "0"),
        ("Vary", "Authorization, Accept"),
        ("X-Content-Type-Options", "nosniff"),
    )
    body = decoded(response)
    assert set(body) == {
        "schema_id", "schema_version", "audience", "clinic_id", "source_id",
        "projection_id", "mapping_revision", "provider_session_id",
        "provider_generation", "snapshot_sequence", "clinic_day", "observed_at",
        "snapshot_kind", "complete", "verified_empty", "content_sha256",
        "encounters", "orders",
    }
    assert body["schema_id"] == "kaosorders.current-day-orders-snapshot"
    assert body["schema_version"] == 1 and type(body["schema_version"]) is int
    assert body["audience"] == "orders"
    assert body["projection_id"] == "kaosorders-current-day-orders-v1"
    assert body["snapshot_kind"] == "FULL" and body["complete"] is True
    assert body["verified_empty"] is False
    assert body["clinic_day"] == "2026-10-08"
    assert body["observed_at"] == "2026-10-08T01:02:03.456789Z"
    assert set(body["encounters"][0]) == {
        "encounter_id", "chart_number", "patient_name", "sex", "age", "state", "qualifiers"
    }
    assert set(body["orders"][0]) == {
        "key", "catalog_code", "catalog_name", "user_code", "user_name",
        "order_type", "department_code", "state", "qualifiers"
    }
    assert body["orders"][0]["catalog_name"] == "Synthetic catalog"
    assert body["orders"][0]["user_code"] is None
    assert body["orders"][0]["user_name"] == ""


@pytest.mark.parametrize(
    "req,status,code",
    [
        (request(method="POST"), 405, "method_not_allowed"),
        (request(path="/api/v1/order-snapshots"), 400, "invalid_request"),
        (request(query="x=1"), 400, "invalid_request"),
        (request(body=b"{}"), 400, "invalid_request"),
        (request(headers=(("Accept", wire.SUCCESS_MEDIA_TYPE), ("Authorization", f"Bearer {ORDERS_TOKEN}"), ("Content-Encoding", "identity"))), 400, "invalid_request"),
        (request(headers=(("Authorization", f"Bearer {ORDERS_TOKEN}"),)), 406, "contract_not_acceptable"),
        (request(headers=(("Accept", "application/json"), ("Authorization", f"Bearer {ORDERS_TOKEN}"))), 406, "contract_not_acceptable"),
        (request(headers=(("Accept", wire.SUCCESS_MEDIA_TYPE), ("Accept", wire.SUCCESS_MEDIA_TYPE), ("Authorization", f"Bearer {ORDERS_TOKEN}"))), 400, "invalid_request"),
    ],
)
def test_request_negotiation_is_exact_and_never_reuses_legacy_route(req, status, code):
    response = handle(req)
    assert response.status == status
    assert decoded(response)["code"] == code


def test_authentication_audience_revocation_and_source_scope_fail_closed():
    missing = request(headers=(("Accept", wire.SUCCESS_MEDIA_TYPE),))
    unknown = request(headers=(("Accept", wire.SUCCESS_MEDIA_TYPE), ("Authorization", f"Bearer {OTHER_TOKEN}")))
    malformed = request(headers=(("Accept", wire.SUCCESS_MEDIA_TYPE), ("Authorization", ORDERS_TOKEN)))
    for req in (missing, unknown, malformed):
        response = handle(req)
        assert response.status == 401
        assert decoded(response)["code"] == "authentication_required"
        assert ("WWW-Authenticate", "Bearer") in response.headers

    revoked = identity_set(bearer(status=wire.SyntheticIdentityStatus.REVOKED))
    assert decoded(handle(identities=revoked))["code"] == "authentication_required"
    wrong_audience = identity_set(bearer(audience="reception"))
    response = handle(identities=wrong_audience)
    assert response.status == 403 and decoded(response)["code"] == "scope_forbidden"
    wrong_projection = identity_set(bearer(projection_id="other-projection"))
    assert decoded(handle(identities=wrong_projection))["code"] == "scope_forbidden"
    wrong_clinic = identity_set(
        wire.SyntheticBearerIdentity(
            OTHER_TOKEN,
            "orders",
            "synthetic-other-clinic",
            "synthetic-eghis",
            "kaosorders-current-day-orders-v1",
            1,
            wire.SyntheticIdentityStatus.ACTIVE,
            synthetic_fixture=True,
        )
    )
    wrong_clinic_request = request(
        headers=(
            ("Accept", wire.SUCCESS_MEDIA_TYPE),
            ("Authorization", f"Bearer {OTHER_TOKEN}"),
        )
    )
    assert decoded(handle(wrong_clinic_request, identities=wrong_clinic))["code"] == "scope_forbidden"
    wrong_source = identity_set(bearer(source_id="synthetic-other-source"))
    assert decoded(handle(identities=wrong_source))["code"] == "scope_forbidden"


def test_identity_and_outputs_are_immutable_redacted_and_never_echo_token():
    credential = bearer()
    assert repr(credential) == "<SyntheticBearerIdentity: redacted>"
    assert repr(identity_set(credential)) == "<SyntheticIdentitySet: redacted>"
    with pytest.raises(FrozenInstanceError):
        credential.token = OTHER_TOKEN
    response = handle(
        request(headers=(("Accept", wire.SUCCESS_MEDIA_TYPE), ("Authorization", "Bearer invalid")))
    )
    assert ORDERS_TOKEN.encode() not in response.body
    assert b"invalid" not in response.body
    assert ORDERS_TOKEN not in repr(response)


def test_verified_empty_is_distinct_from_unavailable():
    state, projection = published(empty=True)
    response = handle(state=state, projection=projection)
    assert response.status == 200
    body = decoded(response)
    assert body["verified_empty"] is True
    assert body["encounters"] == [] and body["orders"] == []

    starting = lifecycle.start_provider(
        now=NOW,
        provider_session_id=identity("synthetic-session-b"),
        provider_generation=identity("synthetic-generation-b"),
        lease=lease(),
        stable_jitter_seconds=0,
    )
    response = handle(state=starting, projection=None)
    assert response.status == 503
    assert decoded(response)["code"] == "provider_starting"


def test_current_day_freshness_and_projection_reference_are_fenced():
    state, projection = published()
    assert handle(state=state, projection=projection, now=NOW + timedelta(seconds=300)).status == 200
    expired = handle(
        state=state,
        projection=projection,
        now=NOW + timedelta(seconds=300, microseconds=1),
    )
    assert decoded(expired)["code"] == "freshness_expired"

    future_snapshot = replace(state.snapshot, observed_at=NOW + timedelta(seconds=31))
    future_state = replace(state, snapshot=future_snapshot)
    future_projection = wire.SyntheticOrdersProjection(
        projection.scope, future_snapshot, projection.facts, synthetic_fixture=True
    )
    assert decoded(handle(state=future_state, projection=future_projection))["code"] == "projection_invalid"

    other_state, other_projection = published(empty=True)
    mismatched = handle(state=state, projection=other_projection)
    assert decoded(mismatched)["code"] == "projection_invalid"


def test_rollover_rate_limit_response_bound_and_error_controls(monkeypatch):
    state, projection = published()
    rolled = lifecycle.rollover(
        state,
        now=NOW + timedelta(days=1),
        provider_generation=identity("synthetic-generation-next"),
        lease=state.lease,
    )
    response = handle(state=rolled, projection=None, now=NOW + timedelta(days=1))
    assert decoded(response)["code"] == "day_rollover"

    limited = handle(state=state, projection=projection, rate=7)
    assert limited.status == 429
    assert decoded(limited) == {
        "schema_id": "kaosorders.current-day-orders-error",
        "schema_version": 1,
        "code": "rate_limited",
        "retryable": True,
        "retry_after_seconds": 7,
    }
    assert ("Retry-After", "7") in limited.headers

    monkeypatch.setattr(wire, "MAX_BODY_BYTES", 1)
    oversized = handle(state=state, projection=projection)
    assert oversized.status == 413
    assert decoded(oversized)["code"] == "response_bound_exceeded"


def test_every_error_is_closed_fixed_nonclinical_and_noncacheable():
    cases = (
        handle(request(method="POST")),
        handle(request(headers=(("Accept", wire.SUCCESS_MEDIA_TYPE),))),
        handle(rate=3),
    )
    for response in cases:
        body = decoded(response)
        assert set(body) == {
            "schema_id", "schema_version", "code", "retryable", "retry_after_seconds"
        }
        assert body["schema_id"] == "kaosorders.current-day-orders-error"
        assert body["schema_version"] == 1
        assert response.headers[:6] == (
            ("Content-Type", wire.ERROR_MEDIA_TYPE),
            ("Cache-Control", "no-store, private, max-age=0"),
            ("Pragma", "no-cache"),
            ("Expires", "0"),
            ("Vary", "Authorization, Accept"),
            ("X-Content-Type-Options", "nosniff"),
        )
        assert not any(name in {"ETag", "Last-Modified", "Content-Encoding"} for name, _ in response.headers)
        assert b"synthetic-encounter" not in response.body
        assert b"content_sha256" not in response.body


def test_every_literal_error_code_status_and_retryability_is_exact():
    expected = {
        "invalid_request": (400, False),
        "authentication_required": (401, False),
        "scope_forbidden": (403, False),
        "method_not_allowed": (405, False),
        "contract_not_acceptable": (406, False),
        "response_bound_exceeded": (413, False),
        "rate_limited": (429, True),
        "provider_starting": (503, True),
        "day_rollover": (503, True),
        "source_unavailable": (503, True),
        "projection_invalid": (503, True),
        "freshness_expired": (503, True),
        "internal_unavailable": (503, True),
    }
    assert set(wire._ERRORS) == set(expected)
    for code, (status, retryable) in expected.items():
        response = wire._error_response(code, retry_after=9)
        body = decoded(response)
        assert response.status == status
        assert body["code"] == code and body["retryable"] is retryable
        assert body["retry_after_seconds"] == (9 if retryable else None)
        assert (("Retry-After", "9") in response.headers) is retryable


@pytest.mark.parametrize("invalid", ["short", "contains space" + "x" * 40, "x" * 513])
def test_synthetic_identity_requires_bounded_opaque_bearer_syntax(invalid):
    with pytest.raises(wire.OrdersWireRejected, match="^invalid_synthetic_identity$"):
        bearer(token=invalid)


def test_projection_requires_one_atomic_lifecycle_snapshot_and_exact_count():
    state, projection = published()
    wrong_count = replace(
        state.snapshot,
        orders=lifecycle.DestinationState(
            lifecycle.ProjectionAvailability.AVAILABLE, 1, 17
        ),
    )
    with pytest.raises(wire.OrdersWireRejected, match="^projection_invalid$"):
        wire.SyntheticOrdersProjection(
            projection.scope, wrong_count, projection.facts, synthetic_fixture=True
        )
    with pytest.raises(wire.OrdersWireRejected, match="^synthetic_fixture_required$"):
        wire.SyntheticOrdersProjection(projection.scope, state.snapshot, projection.facts)
    wrong_scope = wire.SyntheticOrdersScope(
        "synthetic-clinic",
        "synthetic-other-source",
        "synthetic-mapping-v1",
        synthetic_fixture=True,
    )
    with pytest.raises(wire.OrdersWireRejected, match="^projection_invalid$"):
        wire.SyntheticOrdersProjection(
            wrong_scope, state.snapshot, projection.facts, synthetic_fixture=True
        )


def test_wire_module_stays_pure_and_only_opt_in_adapter_imports_it():
    path = Path(wire.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports == {
        "dataclasses", "datetime", "enum", "hashlib", "hmac", "json", "re",
        "unicodedata", "KaosEghis.core",
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not calls & {"open", "print", "eval", "exec", "__import__"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {
        "socket", "requests", "urllib", "sqlite3", "psycopg2", "keyring",
        "settings", "QApplication", "threading", "subprocess",
    }
    root = path.parents[1]
    importers = []
    for other in root.rglob("*.py"):
        if other != path and "kaosorders_current_day_wire" in other.read_text(
            encoding="utf-8-sig"
        ):
            importers.append(other.relative_to(root).as_posix())
    assert importers == ["service/kaosorders_synthetic_api.py"]
