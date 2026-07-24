import uuid
from datetime import datetime, timezone

# pyrefly: ignore [missing-import]
import pytest

from calibration import calibration_service
from control_plane import control_plane_service
from engine import process_assessment
from models import (
    ActionType,
    AutonomyZone,
    CalibrationOutcome,
    CalibrationSignalRequest,
    CalibrationSignalType,
    ComplexityLevel,
    PhaseProgressionAppliedEvent,
    PhaseRollbackRequest,
    PhaseTransitionDirection,
    ReversibilityHint,
    RiskBand,
    TransformationPhase,
)
from phase import phase_state
from posture import posture_engine
from settings import get_settings
from tests.test_engine import get_base_request


def test_context_establishment_shifts_zone_up_by_one():
    req = get_base_request()
    resp = process_assessment(req)

    assert resp.base_zone == AutonomyZone.ZONE_1
    assert resp.zone == AutonomyZone.ZONE_2
    assert resp.original_zone == "ZONE_1"
    assert resp.shifted_zone == "ZONE_2"
    assert resp.justification.original_zone == "ZONE_1"
    assert resp.justification.shifted_zone == "ZONE_2"
    assert resp.transformation_phase_modifier == "CONTEXT_ESTABLISHMENT:+1_ZONE"
    assert resp.active_phase == TransformationPhase.CONTEXT_ESTABLISHMENT


def test_context_establishment_caps_zone_3_and_zone_4():
    from config import config

    config.update_system_risk("enterprise-wide", 0.9)
    req = get_base_request(target_scope="enterprise-wide")
    req.action_descriptor.reversibility_hint = ReversibilityHint.IRREVERSIBLE_EFFECTS
    resp = process_assessment(req)

    assert resp.base_zone == AutonomyZone.ZONE_4
    assert resp.zone == AutonomyZone.ZONE_4


def test_workflow_integration_removes_modifier():
    event = PhaseProgressionAppliedEvent(
        target_phase=TransformationPhase.WORKFLOW_INTEGRATION,
        previous_phase=TransformationPhase.CONTEXT_ESTABLISHMENT,
        transition_id=str(uuid.uuid4()),
        direction=PhaseTransitionDirection.FORWARD,
        applied_at=datetime.now(timezone.utc).isoformat(),
        source_replica_count=get_settings().min_replicas,
    )
    control_plane_service.handle_phase_progression_applied(event)

    req = get_base_request()
    resp = process_assessment(req)

    assert resp.zone == AutonomyZone.ZONE_1
    assert resp.base_zone == AutonomyZone.ZONE_1
    assert resp.transformation_phase_modifier is None
    assert resp.active_phase == TransformationPhase.WORKFLOW_INTEGRATION


def test_ai_native_operation_locks_zone_4_for_high_risk_high_complexity():
    zone, modifier = posture_engine.apply_posture(
        base_zone=AutonomyZone.ZONE_2,
        phase=TransformationPhase.AI_NATIVE_OPERATION,
        risk_band=RiskBand.HIGH,
        cognitive_complexity=ComplexityLevel.HIGH,
        operational_complexity=ComplexityLevel.LOW,
    )
    assert zone == AutonomyZone.ZONE_4
    assert modifier == "AI_NATIVE_OPERATION:ZONE_4_LOCK"


def test_calibration_counter_reaches_readiness_at_threshold():
    domain = "payments"
    threshold = get_settings().calibration_threshold

    readiness_events = []
    for index in range(threshold):
        signal = CalibrationSignalRequest(
            knowledge_domain=domain,
            action_type=ActionType.TEST_CASE_DESIGN,
            signal_type=CalibrationSignalType.OUTCOME,
            outcome=CalibrationOutcome.SUCCESS,
            request_id=f"req-{index}",
        )
        summary, readiness_event = calibration_service.ingest_signal(signal)
        if readiness_event:
            readiness_events.append(readiness_event)

    assert summary.total_signals == threshold
    assert summary.ready_for_progression is True
    assert len(readiness_events) == 1
    assert readiness_events[0].knowledge_domain == domain
    assert domain in phase_state.get_calibration_ready_domains()


def test_assessment_reports_active_domain_calibration_count():
    domain = "payments"
    for index in range(3):
        calibration_service.ingest_signal(
            CalibrationSignalRequest(
                knowledge_domain=domain,
                action_type=ActionType.TEST_CASE_AUTOMATION,
                signal_type=CalibrationSignalType.OUTCOME,
                outcome=CalibrationOutcome.SUCCESS,
                request_id=f"assessment-count-{index}",
            )
        )

    request = get_base_request()
    request.action_descriptor.knowledge_domain = domain
    response = process_assessment(request)

    assert response.calibration_signal_count == 3
    assert response.justification.calibration_signal_count == 3


def test_phase_rollback_restores_previous_phase():
    forward = PhaseProgressionAppliedEvent(
        target_phase=TransformationPhase.WORKFLOW_INTEGRATION,
        previous_phase=TransformationPhase.CONTEXT_ESTABLISHMENT,
        transition_id="transition-1",
        direction=PhaseTransitionDirection.FORWARD,
        applied_at=datetime.now(timezone.utc).isoformat(),
        source_replica_count=get_settings().min_replicas,
    )
    control_plane_service.handle_phase_progression_applied(forward)
    assert phase_state.get_active_phase() == TransformationPhase.WORKFLOW_INTEGRATION

    _, state = control_plane_service.rollback_phase(
        PhaseRollbackRequest(transition_id="transition-1", reason="regression")
    )
    assert state.active_phase == TransformationPhase.CONTEXT_ESTABLISHMENT
    assert state.previous_phase == TransformationPhase.WORKFLOW_INTEGRATION


def test_duplicate_calibration_signal_rejected():
    signal1 = CalibrationSignalRequest(
        knowledge_domain="checkout",
        action_type=ActionType.TEST_CASE_DESIGN,
        signal_type=CalibrationSignalType.OUTCOME,
        outcome=CalibrationOutcome.SUCCESS,
        request_id="req-dup-100",
    )
    summary, _ = calibration_service.ingest_signal(signal1)
    assert summary.total_signals == 1

    # Ingesting same signal request_id again must be rejected
    # pyrefly: ignore [missing-import]
    import pytest
    with pytest.raises(ValueError, match="Duplicate calibration signal rejected"):
        calibration_service.ingest_signal(signal1)

