import uuid
from datetime import datetime, timezone
from typing import Tuple

from models import (
    PhaseProgressionAppliedEvent,
    PhaseRollbackRequest,
    PhaseStateResponse,
    PhaseTransitionDirection,
    TransformationPhase,
)
from phase import PhaseSnapshot, phase_state
from settings import get_settings
from sync import ReplicaSyncCoordinator, replica_sync


class ControlPlaneService:
    """Handles PhaseProgressionApplied events and rollback operations."""

    def handle_phase_progression_applied(
        self,
        event: PhaseProgressionAppliedEvent,
    ) -> Tuple[PhaseSnapshot, PhaseStateResponse]:
        snapshot = replica_sync.atomic_reload(
            target_phase=event.target_phase,
            transition_id=event.transition_id,
            source_replica_count=event.source_replica_count,
            direction=event.direction,
        )
        return snapshot, self.get_phase_state()

    def rollback_phase(self, request: PhaseRollbackRequest) -> Tuple[PhaseSnapshot, PhaseStateResponse]:
        current = phase_state.get_snapshot()
        rollback_target = current.previous_phase or TransformationPhase.CONTEXT_ESTABLISHMENT
        transition_id = request.transition_id or str(uuid.uuid4())

        event = PhaseProgressionAppliedEvent(
            target_phase=rollback_target,
            previous_phase=current.active_phase,
            transition_id=transition_id,
            direction=PhaseTransitionDirection.ROLLBACK,
            applied_at=datetime.now(timezone.utc).isoformat(),
            source_replica_count=max(get_settings().min_replicas, len(ReplicaSyncCoordinator.active_replica_ids())),
        )
        return self.handle_phase_progression_applied(event)

    def get_phase_state(self) -> PhaseStateResponse:
        snapshot = phase_state.get_snapshot()
        return PhaseStateResponse(
            active_phase=snapshot.active_phase,
            phase_version=snapshot.phase_version,
            previous_phase=snapshot.previous_phase,
            transition_id=snapshot.transition_id,
            replica_id=replica_sync.replica_id,
            replica_sync_status=replica_sync.get_sync_status(),
            calibration_ready_domains=phase_state.get_calibration_ready_domains(),
        )


control_plane_service = ControlPlaneService()
