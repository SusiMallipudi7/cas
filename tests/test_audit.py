# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from main import app
from audit import set_publisher_failure
from tests.test_engine import get_base_request

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
