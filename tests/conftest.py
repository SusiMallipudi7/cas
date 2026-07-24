import pytest

from calibration import calibration_service
from control_plane import control_plane_service
from models import PhaseProgressionAppliedEvent, PhaseTransitionDirection, TransformationPhase
from phase import phase_state
from settings import get_settings
from sync import ReplicaSyncCoordinator, bootstrap_replicas


@pytest.fixture(autouse=True)
def reset_phase2_state():
    phase_state.reset_for_tests()
    calibration_service.reset_for_tests()
    ReplicaSyncCoordinator.reset_registry_for_tests()
    bootstrap_replicas()
    yield
    phase_state.reset_for_tests()
    calibration_service.reset_for_tests()
    ReplicaSyncCoordinator.reset_registry_for_tests()


def set_workflow_integration_phase() -> None:
    event = PhaseProgressionAppliedEvent(
        target_phase=TransformationPhase.WORKFLOW_INTEGRATION,
        previous_phase=TransformationPhase.CONTEXT_ESTABLISHMENT,
        transition_id="test-workflow-integration",
        direction=PhaseTransitionDirection.FORWARD,
        applied_at="2026-01-01T00:00:00+00:00",
        source_replica_count=get_settings().min_replicas,
    )
    control_plane_service.handle_phase_progression_applied(event)
