import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app
from models import PhaseProgressionAppliedEvent, PhaseTransitionDirection, TransformationPhase
from settings import get_settings


client = TestClient(app)


def test_control_plane_event_updates_posture_state():
    event = {
        "target_phase": TransformationPhase.WORKFLOW_INTEGRATION.value,
        "previous_phase": TransformationPhase.CONTEXT_ESTABLISHMENT.value,
        "transition_id": str(uuid.uuid4()),
        "direction": PhaseTransitionDirection.FORWARD.value,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "source_replica_count": get_settings().min_replicas,
    }

    response = client.post("/v1/control-plane/events", json=event)
    assert response.status_code == 200
    data = response.json()
    assert data["active_phase"] == TransformationPhase.WORKFLOW_INTEGRATION.value
    assert data["phase_version"] >= 2


def test_calibration_signal_endpoint():
    payload = {
        "knowledge_domain": "identity",
        "action_type": "Test Case Design",
        "signal_type": "outcome",
        "outcome": "success",
        "request_id": "req-cal-1",
    }
    response = client.post("/v1/calibration/signals", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["knowledge_domain"] == "identity"
    assert data["summary"]["total_signals"] == 1


def test_health_and_ready_endpoints():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
