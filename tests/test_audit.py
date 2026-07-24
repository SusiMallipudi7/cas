# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
import audit
from main import app
from audit import set_publisher_failure
from tests.test_engine import get_base_request
from tests.conftest import set_workflow_integration_phase


@pytest.fixture(autouse=True)
def workflow_integration_phase():
    set_workflow_integration_phase()

client = TestClient(app)

def test_audit_failure_blocks_response():
    """If the message broker fails, the assessment response MUST be withheld (500 Error)."""
    set_publisher_failure(True)
    
    req = get_base_request()
    
    response = client.post("/v1/assess", json=req.model_dump())
    
    assert response.status_code == 500
    assert "Message broker failed" in response.json()["detail"]
    
    # Reset for other tests
    set_publisher_failure(False)

def test_audit_success_returns_response():
    """If audit succeeds, response is returned normally."""
    set_publisher_failure(False)
    
    req = get_base_request(target_scope="reporting_ui")
    
    response = client.post("/v1/assess", json=req.model_dump())
    
    assert response.status_code == 200
    data = response.json()
    assert data["zone"] == "ZONE_1"


def test_audit_fragment_tracks_original_and_shifted_zones(monkeypatch):
    class CapturingPublisher:
        def __init__(self):
            self.fragment = None

        def publish(self, fragment):
            self.fragment = fragment
            return True

    publisher = CapturingPublisher()
    monkeypatch.setattr(audit, "_publisher", publisher)

    req = get_base_request(target_scope="reporting_ui")
    response = client.post("/v1/assess", json=req.model_dump(mode="json"))

    assert response.status_code == 200
    assert publisher.fragment["original_zone"] == "ZONE_1"
    assert publisher.fragment["shifted_zone"] == "ZONE_1"
    assert publisher.fragment["response"]["original_zone"] == "ZONE_1"
    assert publisher.fragment["response"]["shifted_zone"] == "ZONE_1"
