"""Synthetic-only local outbox proof. No runtime imports, transport or EMR access.

Files contain plaintext synthetic fixtures. This is NOT production PHI storage.
Acknowledgements are internal test objects, not an approved network contract.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import UUID

from KaosEghis.core.emr_source import SnapshotRejected, SourceSnapshot, _PrivateModel
from KaosEghis.core.kaosorders_normalized_source import (
    MAX_SEQUENCE_VALUE, SyntheticDeliveryMetadata, _model, _sequence, _wire_text,
    calculate_content_sha256, serialize_normalized_source,
)


APPLICATION_ID = 0x4B4F5348
SCHEMA_VERSION = 1
MAX_SYNTHETIC_BYTES = 16 * 1024 * 1024


class OutboxRejected(ValueError):
    """Fixed redacted reason; never include payloads, SQL or filesystem paths."""


@dataclass(frozen=True, repr=False)
class DeliveryScope(_PrivateModel):
    clinic_id: str
    source_id: str
    projection_id: str
    clinic_day: date
    mapping_revision: str


@dataclass(frozen=True, repr=False)
class BatchCursor(_PrivateModel):
    scope: DeliveryScope
    source_epoch: int
    revision: int
    batch_id: str
    content_sha256: str


@dataclass(frozen=True, repr=False)
class PendingBatch(_PrivateModel):
    cursor: BatchCursor
    body: bytes
    refresh_generation: int


@dataclass(frozen=True, repr=False)
class SyntheticAcknowledgement(_PrivateModel):
    outcome: str
    receiver_generation: str
    request: BatchCursor
    committed: BatchCursor | None


@dataclass(frozen=True, repr=False)
class QueueState(_PrivateModel):
    requested_generation: int = 0
    acknowledged_generation: int = 0
    allocated_revision: int = 0
    acknowledged_revision: int = 0
    paused_reason: str = ""

    @property
    def refresh_required(self):
        return self.requested_generation > self.acknowledged_generation


def _uuid(value):
    if type(value) is not str:
        raise OutboxRejected("invalid_identity")
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise OutboxRejected("invalid_identity") from None
    return value


def _day(value):
    if type(value) is not date:
        raise OutboxRejected("invalid_day")
    return value.isoformat()


def _path(value):
    if not isinstance(value, (str, Path)) or not str(value):
        raise OutboxRejected("invalid_path")
    try:
        return Path(value).absolute()
    except (ValueError, OSError):
        raise OutboxRejected("invalid_path") from None


def _body(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _cursor(value):
    _model(value, BatchCursor)
    _model(value.scope, DeliveryScope)
    for field in ("clinic_id", "source_id", "projection_id", "mapping_revision"):
        _wire_text(vars(value.scope)[field])
    _day(value.scope.clinic_day)
    _sequence(value.source_epoch)
    _sequence(value.revision)
    _uuid(value.batch_id)
    digest = value.content_sha256
    if type(digest) is not str or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise OutboxRejected("invalid_digest")


class SyntheticOutbox(_PrivateModel):
    """One synthetic producer lineage, per-day revisions and pending batches.

    Every operation opens/closes its own local SQLite connection. No persistent
    connection, default path, scheduler, credentials or network client is supplied.
    """

    def __init__(self, path, *, synthetic_fixture=False):
        if synthetic_fixture is not True:
            raise OutboxRejected("synthetic_fixture_required")
        self._path = _path(path)
        with self._transaction():
            pass

    @classmethod
    def create(cls, path, *, clinic_id, source_id, projection_id, mapping_revision,
               source_epoch, receiver_generation, synthetic_fixture=False):
        if synthetic_fixture is not True:
            raise OutboxRejected("synthetic_fixture_required")
        try:
            values = tuple(_wire_text(v) for v in (clinic_id, source_id, projection_id, mapping_revision))
            _sequence(source_epoch)
            _uuid(receiver_generation)
        except SnapshotRejected:
            raise OutboxRejected("invalid_identity") from None
        path = _path(path)
        connection = None
        try:
            # Exclusive creation cannot truncate an existing queue or app database.
            with path.open("xb"):
                pass
            connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=1)
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            connection.execute("""CREATE TABLE producer (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                clinic_id TEXT NOT NULL, source_id TEXT NOT NULL,
                projection_id TEXT NOT NULL, mapping_revision TEXT NOT NULL,
                source_epoch INTEGER NOT NULL, receiver_generation TEXT NOT NULL)""")
            connection.execute("INSERT INTO producer VALUES (1, ?, ?, ?, ?, ?, ?)",
                               (*values, source_epoch, receiver_generation))
            connection.execute("""CREATE TABLE days (
                clinic_day TEXT PRIMARY KEY, requested INTEGER NOT NULL DEFAULT 0,
                acknowledged_generation INTEGER NOT NULL DEFAULT 0,
                allocated INTEGER NOT NULL DEFAULT 0, acknowledged INTEGER NOT NULL DEFAULT 0,
                paused_reason TEXT NOT NULL DEFAULT '')""")
            connection.execute("""CREATE TABLE batches (
                batch_id TEXT PRIMARY KEY, clinic_day TEXT NOT NULL REFERENCES days(clinic_day),
                revision INTEGER NOT NULL, refresh_generation INTEGER NOT NULL,
                digest TEXT NOT NULL, body_sha256 TEXT NOT NULL, body BLOB,
                UNIQUE(clinic_day, revision))""")
            connection.execute("CREATE UNIQUE INDEX one_pending ON batches(clinic_day) WHERE body IS NOT NULL")
            connection.commit()
        except FileExistsError:
            raise OutboxRejected("store_already_exists") from None
        except (OSError, sqlite3.Error):
            raise OutboxRejected("store_unavailable") from None
        finally:
            if connection is not None:
                connection.close()
        return cls(path, synthetic_fixture=True)

    @contextmanager
    def _transaction(self):
        connection = None
        try:
            # mode=rw must fail on missing state; it must never enroll a new lineage.
            connection = sqlite3.connect(self._path.as_uri() + "?mode=rw", uri=True, timeout=1)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            if (connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                    or connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
                raise OutboxRejected("store_unverified")
            self._producer(connection)
            yield connection
            connection.commit()
        except SnapshotRejected:
            raise OutboxRejected("invalid_input") from None
        except sqlite3.Error:
            raise OutboxRejected("store_unavailable") from None
        finally:
            if connection is not None:
                # Closing rolls back any transaction that failed before commit.
                connection.close()

    @staticmethod
    def _producer(connection):
        rows = connection.execute("SELECT * FROM producer").fetchall()
        if len(rows) != 1 or rows[0]["singleton"] != 1:
            raise OutboxRejected("store_corrupt")
        row = rows[0]
        for name in ("clinic_id", "source_id", "projection_id", "mapping_revision"):
            _wire_text(row[name])
        _sequence(row["source_epoch"])
        _uuid(row["receiver_generation"])
        return row

    @staticmethod
    def _state(connection, day):
        row = connection.execute("SELECT * FROM days WHERE clinic_day=?", (day,)).fetchone()
        if row is None:
            return QueueState()
        values = tuple(row[name] for name in ("requested", "acknowledged_generation", "allocated", "acknowledged"))
        if (any(type(v) is not int or not 0 <= v <= MAX_SEQUENCE_VALUE for v in values)
                or not values[0] >= values[1] >= values[3]
                or values[2] > values[0] or values[2] not in (values[3], values[3] + 1)
                or row["paused_reason"] not in ("", "stale", "conflict", "resync_required")):
            raise OutboxRejected("store_corrupt")
        latest = connection.execute("SELECT COALESCE(MAX(revision), 0) FROM batches WHERE clinic_day=?", (day,)).fetchone()[0]
        receipt = connection.execute("SELECT refresh_generation, body FROM batches WHERE clinic_day=? AND revision=?",
                                     (day, values[3])).fetchone()
        if (latest != values[2] or (values[3] and (receipt is None
                or receipt["refresh_generation"] != values[1] or receipt["body"] is not None))):
            raise OutboxRejected("store_corrupt")
        return QueueState(*values, row["paused_reason"])

    def state(self, clinic_day):
        with self._transaction() as connection:
            return self._state(connection, _day(clinic_day))

    def request_refresh(self, clinic_day):
        day = _day(clinic_day)
        with self._transaction() as connection:
            state = self._state(connection, day)
            if state.requested_generation == MAX_SEQUENCE_VALUE:
                raise OutboxRejected("sequence_exhausted")
            connection.execute("INSERT OR IGNORE INTO days(clinic_day) VALUES (?)", (day,))
            generation = state.requested_generation + 1
            connection.execute("UPDATE days SET requested=? WHERE clinic_day=?", (generation, day))
            return generation

    @staticmethod
    def _row_cursor(producer, row):
        try:
            day = date.fromisoformat(row["clinic_day"])
            if day.isoformat() != row["clinic_day"]:
                raise ValueError
            scope = DeliveryScope(producer["clinic_id"], producer["source_id"], producer["projection_id"],
                                  day, producer["mapping_revision"])
            cursor = BatchCursor(scope, producer["source_epoch"], row["revision"], row["batch_id"], row["digest"])
            _cursor(cursor)
            _sequence(row["refresh_generation"])
        except (ValueError, TypeError, SnapshotRejected):
            raise OutboxRejected("store_corrupt") from None
        return cursor

    def _pending(self, connection, day):
        producer = self._producer(connection)
        state = self._state(connection, day)
        rows = connection.execute("SELECT * FROM batches WHERE clinic_day=? AND body IS NOT NULL", (day,)).fetchall()
        if len(rows) > 1 or (bool(rows) != (state.allocated_revision > state.acknowledged_revision)):
            raise OutboxRejected("store_corrupt")
        if not rows:
            return None
        row = rows[0]
        cursor = self._row_cursor(producer, row)
        body = row["body"]
        if (type(body) is not bytes or not 0 < len(body) <= MAX_SYNTHETIC_BYTES
                or cursor.revision != state.allocated_revision
                or not state.acknowledged_generation < row["refresh_generation"] <= state.requested_generation
                or hashlib.sha256(body).hexdigest() != row["body_sha256"]):
            raise OutboxRejected("store_corrupt")
        try:
            payload = json.loads(body)
            if (_body(payload) != body or calculate_content_sha256(payload) != cursor.content_sha256
                    or payload["content_sha256"] != cursor.content_sha256
                    or payload["batch_id"] != cursor.batch_id or payload["source_epoch"] != cursor.source_epoch
                    or payload["revision"] != cursor.revision
                    or payload["scope"] != {**vars(cursor.scope), "clinic_day": day}):
                raise ValueError
        except (ValueError, TypeError, KeyError, UnicodeError, SnapshotRejected):
            raise OutboxRejected("store_corrupt") from None
        return PendingBatch(cursor, body, row["refresh_generation"])

    def pending(self, clinic_day):
        with self._transaction() as connection:
            return self._pending(connection, _day(clinic_day))

    def seal(self, snapshot, *, batch_id, refresh_generation):
        """The generation ticket must be captured before acquiring the snapshot."""
        with self._transaction() as connection:
            producer = self._producer(connection)
            # Validate before allocating: failed source/serialization consumes no revision.
            _model(snapshot, SourceSnapshot)
            day = _day(snapshot.clinic_day)
            state = self._state(connection, day)
            if state.paused_reason:
                raise OutboxRejected("scope_paused")
            if self._pending(connection, day) is not None:
                raise OutboxRejected("pending_unresolved")
            _sequence(refresh_generation)
            if not state.acknowledged_generation < refresh_generation <= state.requested_generation:
                raise OutboxRejected("invalid_refresh_generation")
            if state.allocated_revision == MAX_SEQUENCE_VALUE:
                raise OutboxRejected("sequence_exhausted")
            revision = state.allocated_revision + 1
            payload = serialize_normalized_source(snapshot, SyntheticDeliveryMetadata(
                producer["clinic_id"], batch_id, producer["source_epoch"], revision), synthetic_fixture=True)
            if any(payload["scope"][name] != producer[name] for name in
                   ("source_id", "projection_id", "mapping_revision")):
                raise OutboxRejected("scope_mismatch")
            if connection.execute("SELECT 1 FROM batches WHERE batch_id=?", (batch_id,)).fetchone():
                raise OutboxRejected("batch_id_reused")
            body = _body(payload)
            if len(body) > MAX_SYNTHETIC_BYTES:
                raise OutboxRejected("batch_too_large")
            connection.execute("UPDATE days SET allocated=? WHERE clinic_day=?", (revision, day))
            connection.execute("INSERT INTO batches VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (batch_id, day, revision, refresh_generation, payload["content_sha256"],
                                hashlib.sha256(body).hexdigest(), body))
            return self._pending(connection, day)

    def acknowledge(self, ack):
        """Internal synthetic receipt, not authentication or an HTTP response parser."""
        with self._transaction() as connection:
            _model(ack, SyntheticAcknowledgement)
            _cursor(ack.request)
            if ack.committed is not None:
                _cursor(ack.committed)
            _uuid(ack.receiver_generation)
            producer = self._producer(connection)
            if ack.receiver_generation != producer["receiver_generation"]:
                raise OutboxRejected("receiver_generation_mismatch")
            if type(ack.outcome) is not str or ack.outcome not in ("accepted", "duplicate", "stale", "conflict", "resync_required"):
                raise OutboxRejected("invalid_ack_outcome")
            day = _day(ack.request.scope.clinic_day)
            row = connection.execute("SELECT * FROM batches WHERE batch_id=?", (ack.request.batch_id,)).fetchone()
            if row is None or self._row_cursor(producer, row) != ack.request:
                raise OutboxRejected("ack_mismatch")
            pending = self._pending(connection, day)
            if ack.outcome not in ("accepted", "duplicate"):
                if pending is None or pending.cursor != ack.request:
                    raise OutboxRejected("ack_mismatch")
                connection.execute("UPDATE days SET paused_reason=? WHERE clinic_day=?", (ack.outcome, day))
                return "paused"
            if ack.committed != ack.request:
                raise OutboxRejected("receiver_cursor_mismatch")
            state = self._state(connection, day)
            if state.paused_reason:
                raise OutboxRejected("scope_paused")
            if row["body"] is None:
                if pending is not None or state.acknowledged_revision != ack.request.revision:
                    raise OutboxRejected("ack_mismatch")
                return "already_acknowledged"
            if pending is None or pending.cursor != ack.request:
                raise OutboxRejected("ack_mismatch")
            connection.execute("UPDATE days SET acknowledged=?, acknowledged_generation=? WHERE clinic_day=?",
                               (ack.request.revision, pending.refresh_generation, day))
            connection.execute("UPDATE batches SET body=NULL WHERE batch_id=?", (ack.request.batch_id,))
            return "acknowledged"
