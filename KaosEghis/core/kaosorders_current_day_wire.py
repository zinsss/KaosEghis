"""Pure disabled Orders destination serializer and in-process handler.

This module implements only the synthetic H4 contract boundary.  It performs no
I/O, opens no source, reads no credential store, binds no socket, mounts no route,
persists nothing, and is not imported by the application runtime.
"""

from dataclasses import InitVar, dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
from hmac import compare_digest
import json
import re
from unicodedata import category

from KaosEghis.core import current_day_provider_lifecycle as lifecycle
from KaosEghis.core import kaosorders_current_day_orders as facts_model


METHOD = "GET"
PATH = "/api/v1/current-day/orders"
SUCCESS_MEDIA_TYPE = "application/vnd.kaosclinic.current-day-orders+json;version=1"
ERROR_MEDIA_TYPE = "application/vnd.kaosclinic.current-day-orders-error+json;version=1"
SUCCESS_SCHEMA_ID = "kaosorders.current-day-orders-snapshot"
ERROR_SCHEMA_ID = "kaosorders.current-day-orders-error"
SCHEMA_VERSION = 1
AUDIENCE = "orders"
SNAPSHOT_KIND = "FULL"
MAX_BODY_BYTES = 16_777_216
MAX_FRESHNESS_SECONDS = 300
MAX_FUTURE_SECONDS = 30
MAX_IDENTITY_LENGTH = 128
MAX_TOKEN_LENGTH = 512
MIN_SYNTHETIC_TOKEN_LENGTH = 43

_TOKEN = re.compile(r"[A-Za-z0-9\-._~+/]+=*\Z")
_COMMON_HEADERS = (
    ("Cache-Control", "no-store, private, max-age=0"),
    ("Pragma", "no-cache"),
    ("Expires", "0"),
    ("Vary", "Authorization, Accept"),
    ("X-Content-Type-Options", "nosniff"),
)
_ERRORS = {
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


class OrdersWireRejected(ValueError):
    """Fixed nonclinical rejection reasons only."""


class SyntheticIdentityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class _Redacted:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: redacted>"


def _required_text(value: object, *, limit: int = MAX_IDENTITY_LENGTH) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > limit
        or any(category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)
    ):
        raise OrdersWireRejected("invalid_identity")
    return value


def _token(value: object) -> str:
    if (
        type(value) is not str
        or not MIN_SYNTHETIC_TOKEN_LENGTH <= len(value) <= MAX_TOKEN_LENGTH
        or _TOKEN.fullmatch(value) is None
    ):
        raise OrdersWireRejected("invalid_synthetic_identity")
    return value


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticBearerIdentity(_Redacted):
    token: str
    audience: str
    clinic_id: str
    source_id: str
    projection_id: str
    contract_version: int
    status: SyntheticIdentityStatus
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise OrdersWireRejected("synthetic_fixture_required")
        _token(self.token)
        for value in (
            self.audience,
            self.clinic_id,
            self.source_id,
            self.projection_id,
        ):
            _required_text(value)
        if type(self.contract_version) is not int or type(self.status) is not SyntheticIdentityStatus:
            raise OrdersWireRejected("invalid_synthetic_identity")


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticIdentitySet(_Redacted):
    identities: tuple[SyntheticBearerIdentity, ...]
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise OrdersWireRejected("synthetic_fixture_required")
        if type(self.identities) is not tuple or not 1 <= len(self.identities) <= 4:
            raise OrdersWireRejected("invalid_synthetic_identity")
        tokens: set[str] = set()
        for identity in self.identities:
            if type(identity) is not SyntheticBearerIdentity:
                raise OrdersWireRejected("invalid_synthetic_identity")
            identity.__post_init__(True)
            if identity.token in tokens:
                raise OrdersWireRejected("invalid_synthetic_identity")
            tokens.add(identity.token)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticOrdersScope(_Redacted):
    clinic_id: str
    source_id: str
    mapping_revision: str
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise OrdersWireRejected("synthetic_fixture_required")
        for value in (self.clinic_id, self.source_id, self.mapping_revision):
            _required_text(value)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticOrdersProjection(_Redacted):
    scope: SyntheticOrdersScope
    snapshot: lifecycle.ProviderSnapshot
    facts: facts_model.SyntheticCurrentDayFacts
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture: bool) -> None:
        if synthetic_fixture is not True:
            raise OrdersWireRejected("synthetic_fixture_required")
        if (
            type(self.scope) is not SyntheticOrdersScope
            or type(self.snapshot) is not lifecycle.ProviderSnapshot
            or type(self.facts) is not facts_model.SyntheticCurrentDayFacts
        ):
            raise OrdersWireRejected("projection_invalid")
        self.scope.__post_init__(True)
        self.snapshot.__post_init__()
        self.snapshot.orders.__post_init__()
        self.facts.__post_init__(True)
        if (
            self.snapshot.cursor.clinic_day != self.facts.clinic_day
            or lifecycle.clinic_day_at(self.snapshot.observed_at) != self.facts.clinic_day
            or self.scope.source_id != self.facts.source_id
        ):
            raise OrdersWireRejected("projection_invalid")
        empty = not self.facts.parents and not self.facts.children
        expected_availability = (
            lifecycle.ProjectionAvailability.VERIFIED_EMPTY
            if empty
            else lifecycle.ProjectionAvailability.AVAILABLE
        )
        if self.snapshot.orders.availability is not expected_availability:
            raise OrdersWireRejected("projection_invalid")
        if not empty and not self.facts.parents:
            raise OrdersWireRejected("projection_invalid")
        if self.snapshot.orders.item_count != len(self.facts.parents) + len(self.facts.children):
            raise OrdersWireRejected("projection_invalid")


@dataclass(frozen=True, slots=True, repr=False)
class InProcessOrdersRequest(_Redacted):
    method: object
    path: object
    query_string: object
    headers: object
    body: object


@dataclass(frozen=True, slots=True, repr=False)
class InProcessOrdersResponse(_Redacted):
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def __post_init__(self) -> None:
        if (
            type(self.status) is not int
            or type(self.headers) is not tuple
            or type(self.body) is not bytes
        ):
            raise OrdersWireRejected("internal_unavailable")


@dataclass(frozen=True, slots=True, repr=False)
class SerializedOrdersSnapshot(_Redacted):
    canonical_content: bytes
    content_sha256: str
    body: bytes


def _header_map(headers: object) -> dict[str, tuple[str, ...]]:
    if type(headers) is not tuple:
        raise OrdersWireRejected("invalid_request")
    values: dict[str, list[str]] = {}
    for item in headers:
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not str
            or not item[0]
            or any(ord(char) < 33 or ord(char) > 126 or char == ":" for char in item[0])
            or any(char in "\r\n" for char in item[1])
        ):
            raise OrdersWireRejected("invalid_request")
        values.setdefault(item[0].lower(), []).append(item[1])
    return {name: tuple(items) for name, items in values.items()}


def _single_header(headers: dict[str, tuple[str, ...]], name: str) -> str | None:
    values = headers.get(name)
    if values is None:
        return None
    if len(values) != 1:
        raise OrdersWireRejected("invalid_request")
    return values[0]


def _authenticate(
    authorization: str | None,
    identities: SyntheticIdentitySet,
) -> tuple[SyntheticBearerIdentity | None, str | None]:
    if type(identities) is not SyntheticIdentitySet:
        return None, "internal_unavailable"
    if authorization is None or not authorization.startswith("Bearer "):
        return None, "authentication_required"
    presented = authorization[7:]
    if not presented or presented != presented.strip() or _TOKEN.fullmatch(presented) is None:
        return None, "authentication_required"
    matched: SyntheticBearerIdentity | None = None
    for identity in identities.identities:
        if compare_digest(presented, identity.token):
            matched = identity
    if matched is None or matched.status is not SyntheticIdentityStatus.ACTIVE:
        return None, "authentication_required"
    if (
        matched.audience != AUDIENCE
        or matched.projection_id != facts_model.PROJECTION_ID
        or matched.contract_version != facts_model.CONTRACT_VERSION
    ):
        return None, "scope_forbidden"
    return matched, None


def _parent_object(parent: facts_model.SyntheticCurrentDayParent) -> dict[str, object]:
    return {
        "encounter_id": parent.encounter_id,
        "chart_number": parent.chart_number,
        "patient_name": parent.patient_name,
        "sex": parent.sex,
        "age": parent.age,
        "state": parent.state.value,
        "qualifiers": {"hold_yn": parent.qualifiers.hold_yn},
    }


def _child_object(child: facts_model.SyntheticCurrentDayChild) -> dict[str, object]:
    return {
        "key": {
            "encounter_id": child.key.encounter_id,
            "order_date": child.key.order_date.isoformat(),
            "order_number": child.key.order_number,
            "order_sequence": child.key.order_sequence,
        },
        "catalog_code": child.catalog_code,
        "catalog_name": child.catalog_name,
        "user_code": child.user_code,
        "user_name": child.user_name,
        "order_type": child.order_type,
        "department_code": child.department_code,
        "state": child.state.value,
        "qualifiers": {
            "dc_yn": child.qualifiers.dc_yn,
            "act_yn": child.qualifiers.act_yn,
        },
    }


def _json_value(value: object) -> None:
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str and key.isascii() for key in value):
        for item in value.values():
            _json_value(item)
        return
    raise OrdersWireRejected("projection_invalid")


def _canonical_json(value: dict[str, object]) -> bytes:
    """Encode the closed ASCII-key schema using its RFC 8785 representation."""

    _json_value(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise OrdersWireRejected("projection_invalid") from None


def _utc_timestamp(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise OrdersWireRejected("projection_invalid")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def serialize_orders_success(
    projection: SyntheticOrdersProjection,
    identity: SyntheticBearerIdentity,
) -> SerializedOrdersSnapshot:
    """Serialize one injected immutable synthetic observation deterministically."""

    if type(projection) is not SyntheticOrdersProjection or type(identity) is not SyntheticBearerIdentity:
        raise OrdersWireRejected("projection_invalid")
    projection.__post_init__(True)
    identity.__post_init__(True)
    if (
        identity.audience != AUDIENCE
        or identity.projection_id != facts_model.PROJECTION_ID
        or identity.contract_version != facts_model.CONTRACT_VERSION
        or identity.status is not SyntheticIdentityStatus.ACTIVE
        or identity.clinic_id != projection.scope.clinic_id
        or identity.source_id != projection.scope.source_id
    ):
        raise OrdersWireRejected("scope_forbidden")
    cursor = projection.snapshot.cursor
    verified_empty = (
        projection.snapshot.orders.availability
        is lifecycle.ProjectionAvailability.VERIFIED_EMPTY
    )
    content: dict[str, object] = {
        "schema_id": SUCCESS_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "audience": AUDIENCE,
        "clinic_id": projection.scope.clinic_id,
        "source_id": projection.scope.source_id,
        "projection_id": facts_model.PROJECTION_ID,
        "mapping_revision": projection.scope.mapping_revision,
        "provider_session_id": cursor.provider_session_id.value,
        "provider_generation": cursor.provider_generation.value,
        "snapshot_sequence": cursor.snapshot_sequence,
        "clinic_day": cursor.clinic_day.isoformat(),
        "observed_at": _utc_timestamp(projection.snapshot.observed_at),
        "snapshot_kind": SNAPSHOT_KIND,
        "complete": True,
        "verified_empty": verified_empty,
        "encounters": [_parent_object(parent) for parent in projection.facts.parents],
        "orders": [_child_object(child) for child in projection.facts.children],
    }
    canonical_content = _canonical_json(content)
    digest = sha256(canonical_content).hexdigest()
    body_object = dict(content)
    body_object["content_sha256"] = digest
    body = _canonical_json(body_object)
    if len(body) > MAX_BODY_BYTES:
        raise OrdersWireRejected("response_bound_exceeded")
    return SerializedOrdersSnapshot(canonical_content, digest, body)


def _response_headers(
    media_type: str,
    *,
    authenticate: bool = False,
    retry_after: int | None = None,
) -> tuple[tuple[str, str], ...]:
    headers = (("Content-Type", media_type), *_COMMON_HEADERS)
    if authenticate:
        headers += (("WWW-Authenticate", "Bearer"),)
    if retry_after is not None:
        headers += (("Retry-After", str(retry_after)),)
    return headers


def _error_response(code: str, *, retry_after: int | None = None) -> InProcessOrdersResponse:
    if code not in _ERRORS:
        code = "internal_unavailable"
    status, retryable = _ERRORS[code]
    if retryable:
        if type(retry_after) is not int or not 1 <= retry_after <= 60:
            retry_after = 60
    else:
        retry_after = None
    body = _canonical_json(
        {
            "schema_id": ERROR_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "code": code,
            "retryable": retryable,
            "retry_after_seconds": retry_after,
        }
    )
    return InProcessOrdersResponse(
        status,
        _response_headers(
            ERROR_MEDIA_TYPE,
            authenticate=code == "authentication_required",
            retry_after=retry_after,
        ),
        body,
    )


def _provider_error(state: lifecycle.ProviderState) -> str:
    if state.phase is lifecycle.ProviderPhase.STARTING:
        return "provider_starting"
    if state.reason is lifecycle.ProviderReason.DAY_ROLLOVER:
        return "day_rollover"
    if state.phase is lifecycle.ProviderPhase.STOPPING:
        return "internal_unavailable"
    if state.snapshot is None:
        return "source_unavailable"
    if state.snapshot.orders.availability is lifecycle.ProjectionAvailability.UNAVAILABLE:
        return "projection_invalid"
    return "internal_unavailable"


def handle_orders_request(
    request: InProcessOrdersRequest,
    *,
    state: lifecycle.ProviderState,
    projection: SyntheticOrdersProjection | None,
    identities: SyntheticIdentitySet,
    now: datetime,
    rate_limit_retry_after: int | None = None,
) -> InProcessOrdersResponse:
    """Handle one exact request in process without network, source, or runtime I/O."""

    if type(request) is not InProcessOrdersRequest:
        return _error_response("invalid_request")
    try:
        headers = _header_map(request.headers)
        if request.method != METHOD:
            return _error_response("method_not_allowed")
        if (
            request.path != PATH
            or request.query_string != ""
            or type(request.body) is not bytes
            or request.body
            or "content-encoding" in headers
        ):
            return _error_response("invalid_request")
        if _single_header(headers, "accept") != SUCCESS_MEDIA_TYPE:
            return _error_response("contract_not_acceptable")
        authorization = _single_header(headers, "authorization")
    except OrdersWireRejected:
        return _error_response("invalid_request")

    identity, auth_error = _authenticate(authorization, identities)
    if auth_error is not None:
        return _error_response(auth_error)
    if rate_limit_retry_after is not None:
        if type(rate_limit_retry_after) is not int or not 1 <= rate_limit_retry_after <= 60:
            return _error_response("internal_unavailable")
        return _error_response("rate_limited", retry_after=rate_limit_retry_after)
    if (
        type(state) is not lifecycle.ProviderState
        or type(now) is not datetime
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        return _error_response("internal_unavailable")
    current_day = lifecycle.clinic_day_at(now)
    if state.clinic_day != current_day or state.reason is lifecycle.ProviderReason.DAY_ROLLOVER:
        return _error_response("day_rollover")
    snapshot = lifecycle.read_snapshot(state)
    if snapshot is None or snapshot.orders.availability is lifecycle.ProjectionAvailability.UNAVAILABLE:
        return _error_response(_provider_error(state))
    if (
        projection is None
        or type(projection) is not SyntheticOrdersProjection
        or projection.snapshot is not snapshot
    ):
        return _error_response("projection_invalid")
    observed_at = snapshot.observed_at
    if observed_at > now + timedelta(seconds=MAX_FUTURE_SECONDS):
        return _error_response("projection_invalid")
    if now - observed_at > timedelta(seconds=MAX_FRESHNESS_SECONDS):
        return _error_response("freshness_expired")
    try:
        serialized = serialize_orders_success(projection, identity)
    except OrdersWireRejected as error:
        if str(error) == "scope_forbidden":
            return _error_response("scope_forbidden")
        if str(error) == "response_bound_exceeded":
            return _error_response("response_bound_exceeded")
        return _error_response("projection_invalid")
    return InProcessOrdersResponse(
        200,
        _response_headers(SUCCESS_MEDIA_TYPE),
        serialized.body,
    )
