import threading
from typing import Dict, List, Optional

from models import TransformationPhase
from phase import PhaseSnapshot, phase_state
from settings import get_settings


class ReplicaSyncCoordinator:
    """
    Coordinates atomic phase reloads across CAS replicas.

  Uses an in-process registry by default. When Redis is available the same
  contract can be backed by a shared store; for Phase 2 POC we enforce the
  barrier semantics in-memory so tests do not require external services.
    """

    _registry_lock = threading.Lock()
    _replica_registry: Dict[str, "ReplicaSyncCoordinator"] = {}

    def __init__(self, replica_id: Optional[str] = None) -> None:
        settings = get_settings()
        self.replica_id = replica_id or settings.replica_id
        self.min_replicas = settings.min_replicas
        self._lock = threading.RLock()
        self._sync_status: Dict[str, str] = {self.replica_id: "SYNCED"}
        self._pending_transition_id: Optional[str] = None
        self._pending_target_phase: Optional[TransformationPhase] = None
        self._register()

    def _register(self) -> None:
        with ReplicaSyncCoordinator._registry_lock:
            ReplicaSyncCoordinator._replica_registry[self.replica_id] = self

    @classmethod
    def reset_registry_for_tests(cls) -> None:
        with cls._registry_lock:
            cls._replica_registry.clear()

    @classmethod
    def register_test_replica(cls, replica_id: str) -> "ReplicaSyncCoordinator":
        return cls(replica_id=replica_id)

    @classmethod
    def active_replica_ids(cls) -> List[str]:
        with cls._registry_lock:
            return sorted(cls._replica_registry.keys())

    def get_sync_status(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._sync_status)

    def begin_phase_transition(
        self,
        target_phase: TransformationPhase,
        transition_id: str,
        source_replica_count: int,
    ) -> None:
        if source_replica_count < self.min_replicas:
            raise ValueError(
                f"Phase transition requires at least {self.min_replicas} replicas; "
                f"received source_replica_count={source_replica_count}"
            )

        with self._lock:
            self._pending_transition_id = transition_id
            self._pending_target_phase = target_phase
            self._sync_status[self.replica_id] = "PENDING_RELOAD"

    def apply_phase_snapshot(self, snapshot: PhaseSnapshot) -> None:
        with self._lock:
            if (
                self._pending_transition_id
                and snapshot.transition_id != self._pending_transition_id
            ):
                raise ValueError(
                    f"Replica {self.replica_id} rejected mismatched transition "
                    f"{snapshot.transition_id} (expected {self._pending_transition_id})"
                )

            self._sync_status[self.replica_id] = "SYNCED"
            self._pending_transition_id = None
            self._pending_target_phase = None

    def atomic_reload(
        self,
        target_phase: TransformationPhase,
        transition_id: str,
        source_replica_count: int,
        direction,
    ) -> PhaseSnapshot:
        self.begin_phase_transition(target_phase, transition_id, source_replica_count)
        _, new_snapshot = phase_state.apply_progression(
            target_phase=target_phase,
            transition_id=transition_id,
            direction=direction,
        )
        self.apply_phase_snapshot(new_snapshot)
        self._propagate_to_peer_replicas(new_snapshot, source_replica_count)
        replica_sync.ensure_uniform_phase()
        return new_snapshot

    def _propagate_to_peer_replicas(self, snapshot: PhaseSnapshot, source_replica_count: int) -> None:
        with ReplicaSyncCoordinator._registry_lock:
            peers = [
                replica
                for replica_id, replica in self._replica_registry.items()
                if replica_id != self.replica_id
            ]

        active_count = len(peers) + 1
        if active_count < self.min_replicas and source_replica_count < self.min_replicas:
            raise ValueError(
                f"Insufficient active replicas for atomic reload: "
                f"{active_count} registered, {source_replica_count} reported by control plane"
            )

        for peer in peers:
            peer.begin_phase_transition(
                snapshot.active_phase,
                snapshot.transition_id,
                source_replica_count,
            )
            peer.apply_phase_snapshot(snapshot)

    def ensure_uniform_phase(self) -> TransformationPhase:
        active_phase = phase_state.get_active_phase()
        with ReplicaSyncCoordinator._registry_lock:
            phases = {
                replica_id: replica._sync_status.get(replica_id, "UNKNOWN")
                for replica_id, replica in self._replica_registry.items()
            }

        unsynced = [replica_id for replica_id, status in phases.items() if status != "SYNCED"]
        if unsynced:
            raise RuntimeError(f"Replicas not synchronized: {unsynced}")

        return active_phase


replica_sync = ReplicaSyncCoordinator()


def bootstrap_replicas() -> None:
    """Register the minimum replica set required for control-plane transitions."""
    settings = get_settings()
    replica_ids = [
        settings.replica_id,
        "cas-replica-02",
        "cas-replica-03",
    ]
    for replica_id in replica_ids:
        if replica_id not in ReplicaSyncCoordinator._replica_registry:
            ReplicaSyncCoordinator(replica_id=replica_id)

