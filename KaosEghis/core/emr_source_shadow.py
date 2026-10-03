"""Memory-only source comparison, independent of destination acknowledgement.

No runtime subscriber, delivery, persistence, category rules or production reader.
"""

from dataclasses import dataclass
import threading
from uuid import uuid4

from KaosEghis.core.emr_source import (
    EmrDayRead, EncounterFacts, OrderFacts, OrderKey, SnapshotRejected,
    SourcePolicy, SourceSnapshot, _PrivateModel, normalize_source_day,
)


@dataclass(frozen=True, repr=False)
class SourceObservation(_PrivateModel):
    observation_id: str
    snapshot: SourceSnapshot
    full_reconciliation: bool
    encounter_upserts: tuple[EncounterFacts, ...]
    order_upserts: tuple[OrderFacts, ...]
    missing_encounter_ids: tuple[str, ...]
    missing_order_keys: tuple[OrderKey, ...]

    def summary(self) -> dict[str, int | str]:
        return {
            "status": "source_shadow_only",
            "encounter_upserts": len(self.encounter_upserts),
            "order_upserts": len(self.order_upserts),
            "missing_encounters": len(self.missing_encounter_ids),
            "missing_orders": len(self.missing_order_keys),
        }


class SourceLedger:
    """Advance only on validated observations, not on receiver delivery/ack.

    Consumers must recover with the included full snapshot after missed delivery.
    This bounded offline baseline is not a durable outbox or a delta-only protocol.
    """

    def __init__(self, *, retained_snapshots=2):
        if type(retained_snapshots) is not int or retained_snapshots < 1:
            raise ValueError("invalid_retention")
        self._retained_snapshots = retained_snapshots
        self._observations = {}
        self._policies = {}
        self._lock = threading.Lock()

    def observe(self, read: EmrDayRead, policy: SourcePolicy) -> SourceObservation:
        with self._lock:
            snapshot = normalize_source_day(read, policy)
            policy_signature = (
                policy.revision,
                tuple(sorted((code, state) for code, state in policy.reception_states)),
                tuple(sorted((code, state) for code, state in policy.order_states)),
            )
            previous = self._observations.get(snapshot.scope)
            if previous is not None:
                prior = previous.snapshot
                if policy_signature != self._policies[snapshot.scope]:
                    raise SnapshotRejected("mapping_revision_changed")
                if snapshot.observed_at < prior.observed_at:
                    raise SnapshotRejected("stale_observation")
                if snapshot.observed_at == prior.observed_at:
                    if snapshot != prior:
                        raise SnapshotRejected("conflicting_observation")
                    return previous
            old_encounters = {item.encounter_id: item for item in previous.snapshot.encounters} if previous else {}
            old_orders = {item.key: item for item in previous.snapshot.orders} if previous else {}
            encounters = {item.encounter_id: item for item in snapshot.encounters}
            orders = {item.key: item for item in snapshot.orders}
            for key, encounter in encounters.items():
                if key in old_encounters and encounter.chart_no != old_encounters[key].chart_no:
                    raise SnapshotRejected("encounter_identity_changed")

            # Missing means absent within this complete scope, not clinical cancellation.
            observation = SourceObservation(
                str(uuid4()), snapshot, previous is None,
                tuple(item for key, item in encounters.items() if old_encounters.get(key) != item),
                tuple(item for key, item in orders.items() if old_orders.get(key) != item),
                tuple(sorted(old_encounters.keys() - encounters.keys())),
                tuple(sorted(old_orders.keys() - orders.keys())),
            )
            self._observations[snapshot.scope] = observation
            self._policies[snapshot.scope] = policy_signature
            # Eviction is local memory cleanup, never a source disappearance.
            while len(self._observations) > self._retained_snapshots:
                oldest = min(self._observations, key=lambda key: self._observations[key].snapshot.observed_at)
                del self._observations[oldest]
                del self._policies[oldest]
            return observation
