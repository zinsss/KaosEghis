"""Legacy board-specific shadow reference. No SQL, files, logs or networking.

Shared source comparison lives in emr_source_shadow; this prototype's board rules
and single-destination acknowledgement model are not the shared source contract.
"""

from dataclasses import dataclass
from datetime import date, datetime
import threading
from uuid import uuid4

from KaosEghis.core.kaosorders_source import (
    DailySnapshot, DayReader, EghisKaosOrdersDayReader, MappingPolicy,
    NormalizedEncounter, OrderState, ReceptionState, SnapshotRejected,
    SourceDayRead, _PrivateModel, normalize_day,
)


@dataclass(frozen=True, repr=False)
class OrderWithdrawal(_PrivateModel):
    encounter_id: str
    order_id: str
    reason: str


@dataclass(frozen=True, repr=False)
class EncounterWithdrawal(_PrivateModel):
    encounter_id: str
    reason: str


@dataclass(frozen=True, repr=False)
class ShadowChange(_PrivateModel):
    batch_id: str
    snapshot: DailySnapshot
    restart_reconciliation: bool
    encounter_upserts: tuple[NormalizedEncounter, ...]
    order_withdrawals: tuple[OrderWithdrawal, ...]
    encounter_withdrawals: tuple[EncounterWithdrawal, ...]

    def summary(self) -> dict[str, int | str]:
        return {
            "status": "shadow_only", "encounter_upserts": len(self.encounter_upserts),
            "order_withdrawals": len(self.order_withdrawals),
            "encounter_withdrawals": len(self.encounter_withdrawals),
            "visible_encounters": sum(item.board_eligible for item in self.snapshot.encounters),
        }


class ShadowLedger:
    """One pending proposal at a time; advance the baseline only on explicit ack.

    Restart requires a fresh complete authoritative day. There is no durable outbox
    and no automatic delivery. Retry returns the same proposal and idempotency ID.
    """

    def __init__(self, *, retained_days=2):
        if type(retained_days) is not int or retained_days < 1:
            raise ValueError("invalid_retention")
        self._retained_days = retained_days
        self._baselines = {}
        self._pending = None
        self._lock = threading.Lock()

    @property
    def pending(self) -> ShadowChange | None:
        with self._lock:
            return self._pending

    def prepare(self, read: SourceDayRead, policy: MappingPolicy) -> ShadowChange:
        with self._lock:
            return self._prepare(read, policy)

    def _prepare(self, read: SourceDayRead, policy: MappingPolicy) -> ShadowChange:
        # Normalization completes before any baseline or pending state is changed.
        snapshot = normalize_day(read, policy)
        if self._pending is not None:
            if snapshot == self._pending.snapshot:
                return self._pending
            raise SnapshotRejected("proposal_pending")
        previous = self._baselines.get(snapshot.clinic_day)
        if previous is not None:
            if snapshot.observed_at < previous.observed_at:
                raise SnapshotRejected("stale_observation")
            if snapshot.observed_at == previous.observed_at and snapshot != previous:
                raise SnapshotRejected("conflicting_observation")
        old = {item.encounter_id: item for item in previous.encounters} if previous else {}
        current = {item.encounter_id: item for item in snapshot.encounters}
        upserts, order_withdrawals, encounter_withdrawals = [], [], []
        for identifier, encounter in current.items():
            prior = old.get(identifier)
            if prior is not None and encounter.chart_no != prior.chart_no:
                raise SnapshotRejected("encounter_identity_changed")
            if encounter.state == ReceptionState.CANCELLED:
                if prior is None or prior.state != ReceptionState.CANCELLED:
                    encounter_withdrawals.append(EncounterWithdrawal(identifier, "source_cancelled"))
                continue
            if encounter != prior:
                upserts.append(encounter)
            prior_orders = {item.order_id: item for item in prior.orders} if prior else {}
            current_orders = {item.order_id: item for item in encounter.orders}
            for order_id, order in current_orders.items():
                previous_order = prior_orders.get(order_id)
                if order.state == OrderState.WITHDRAWN and (previous_order is None or previous_order.state != order.state):
                    order_withdrawals.append(OrderWithdrawal(identifier, order_id, "source_withdrawn"))
            for order_id, order in prior_orders.items():
                if order_id not in current_orders and order.state != OrderState.WITHDRAWN:
                    order_withdrawals.append(OrderWithdrawal(identifier, order_id, "absent_from_complete_day"))
        for identifier, encounter in old.items():
            if identifier not in current and encounter.state != ReceptionState.CANCELLED:
                encounter_withdrawals.append(EncounterWithdrawal(identifier, "absent_from_complete_day"))
        proposal = ShadowChange(str(uuid4()), snapshot, previous is None, tuple(upserts),
                                tuple(order_withdrawals), tuple(encounter_withdrawals))
        self._pending = proposal
        return proposal

    def acknowledge(self, batch_id: str) -> None:
        with self._lock:
            self._acknowledge(batch_id)

    def _acknowledge(self, batch_id: str) -> None:
        if self._pending is None or self._pending.batch_id != batch_id:
            raise SnapshotRejected("acknowledgement_mismatch")
        snapshot = self._pending.snapshot
        self._baselines[snapshot.clinic_day] = snapshot
        self._pending = None
        # Memory eviction is not a source withdrawal. Old days require a full read again.
        for day in sorted(self._baselines)[:-self._retained_days]:
            del self._baselines[day]


def read_shadow_day(settings: dict[str, str], clinic_day: date, observed_at: datetime) -> SourceDayRead | None:
    """No runtime hook calls this. Even opting in cannot bypass the schema gate."""
    if settings.get("kaosorders_shadow_enabled", "false") != "true":
        return None
    if settings.get("kaosorders_publish_enabled", "false") != "false":
        raise SnapshotRejected("publishing_not_implemented")
    reader: DayReader = EghisKaosOrdersDayReader()
    return reader.read_day(clinic_day, observed_at)


def proposed_v2_payload(change: ShadowChange, *, synthetic_fixture: bool = False) -> dict:
    """Offline proposal only, never passed to v1 or an HTTP transport.

    Production export is blocked. The explicit marker prevents examples being
    mistaken for an approved real-patient payload or a server contract.
    """
    if not synthetic_fixture:
        raise SnapshotRejected("synthetic_export_only")

    def stamp(value):
        return value.isoformat() if value is not None else None

    def encounter(item):
        return {
            "encounter_id": item.encounter_id, "chart_no": item.chart_no,
            "patient_name": item.patient_name, "sex_age": item.sex_age,
            "reception_state": item.state.value, "received_at": stamp(item.received_at),
            "orders": [{
                "order_id": order.order_id, "category": order.category.value,
                "source_state": order.state.value, "display_spec": dict(order.display_spec),
                "ordered_at": stamp(order.ordered_at), "updated_at": stamp(order.updated_at),
            } for order in item.orders],
        }

    return {
        "contract": "kaosorders.v2.proposal", "synthetic": True,
        "mode": "authoritative_day_snapshot", "batch_id": change.batch_id,
        "clinic_day": change.snapshot.clinic_day.isoformat(),
        "observed_at": stamp(change.snapshot.observed_at), "complete": True,
        "restart_reconciliation": change.restart_reconciliation,
        # Reception states without demographics let a receiver distinguish a
        # no-order encounter from removal, even after the source client restarts.
        "encounter_states": [{"encounter_id": item.encounter_id, "state": item.state.value}
                             for item in change.snapshot.encounters],
        "encounters": [encounter(item) for item in change.snapshot.encounters
                       if item.orders and item.state != ReceptionState.CANCELLED],
        "order_withdrawals": [{"encounter_id": item.encounter_id, "order_id": item.order_id,
                               "reason": item.reason} for item in change.order_withdrawals],
        "encounter_withdrawals": [{"encounter_id": item.encounter_id, "reason": item.reason}
                                   for item in change.encounter_withdrawals],
    }
