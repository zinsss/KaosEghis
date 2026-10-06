"""Synthetic order-text proposal, not a v1/v2 fact or session wire schema.

No source reader, conversion from v2, display fallback, serializer or runtime
importer. Field names and bounds need receiver agreement before production use.
"""

from dataclasses import InitVar, dataclass
from datetime import date
from unicodedata import category

from KaosEghis.core.emr_source import OrderKey


CODE_LIMIT = 128
NAME_LIMIT = 256
TEXT_FIELDS = ("catalog_code", "catalog_name", "user_code", "user_name")
KEY_FIELDS = ("encounter_id", "order_date", "order_number", "order_sequence")


class OrderTextRejected(ValueError):
    """Only fixed reasons; never source values or provider exceptions."""


def _text(value, limit):
    if value is None:
        return
    if type(value) is not str or len(value) > limit:
        raise OrderTextRejected("invalid_order_text")
    if any(category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value):
        raise OrderTextRejected("invalid_order_text")


def _key(key):
    if type(key) is not OrderKey or set(vars(key)) != set(KEY_FIELDS):
        raise OrderTextRejected("invalid_order_key")
    if type(key.order_date) is not date:
        raise OrderTextRejected("invalid_order_key")
    for value in (key.encounter_id, key.order_number, key.order_sequence):
        if (type(value) is not str or not value or len(value) > CODE_LIMIT
                or value != value.strip()
                or any(category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for char in value)):
            raise OrderTextRejected("invalid_order_key")


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticOrderText:
    key: OrderKey
    catalog_code: str | None
    catalog_name: str | None
    user_code: str | None
    user_name: str | None
    synthetic_fixture: InitVar[bool] = False

    def __post_init__(self, synthetic_fixture):
        if synthetic_fixture is not True:
            raise OrderTextRejected("synthetic_fixture_required")
        _key(self.key)
        for field in TEXT_FIELDS:
            _text(getattr(self, field), CODE_LIMIT if field.endswith("code") else NAME_LIMIT)
        # Detach the existing non-slotted key from caller-owned dictionaries.
        object.__setattr__(self, "key", OrderKey(*(getattr(self.key, field) for field in KEY_FIELDS)))

    def __repr__(self):
        return "<SyntheticOrderText: redacted>"


def build_synthetic_order_text(row, *, synthetic_fixture=False):
    """Validate detached synthetic fields; not JSON parsing or a DB-row adapter."""
    if synthetic_fixture is not True:
        raise OrderTextRejected("synthetic_fixture_required")
    if type(row) is not dict or set(row) != {"key", *TEXT_FIELDS}:
        raise OrderTextRejected("invalid_fields")
    key = row["key"]
    if type(key) is not dict or set(key) != set(KEY_FIELDS):
        raise OrderTextRejected("invalid_fields")
    return SyntheticOrderText(
        OrderKey(*(key[field] for field in KEY_FIELDS)),
        *(row[field] for field in TEXT_FIELDS), synthetic_fixture=True,
    )
