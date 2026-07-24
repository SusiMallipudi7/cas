# pyrefly: ignore [missing-import]
import pytest
from models import (
    AssessmentRequest, ActionDescriptor, ActionType,
    ReversibilityHint, ComplexityLevel, RiskBand, AutonomyZone
)
from engine import process_assessment
from config import config
from tests.conftest import set_workflow_integration_phase


@pytest.fixture(autouse=True)
def workflow_integration_phase():
    set_workflow_integration_phase()

def get_base_request(target_scope="reporting_ui") -> AssessmentRequest:
    return AssessmentRequest(
        request_id="req-123",
        workflow_instance_id="wf-456",
        action_descriptor=ActionDescriptor(
            type=ActionType.TEST_CASE_AUTOMATION,
            target_scope=target_scope,
            knowledge_dependencies=["db_schema_v2"],
            reversibility_hint=ReversibilityHint.TRIVIALLY_REVERSIBLE
        ),
        context_snapshot_ref="uri://snapshot/1",
        caller_service="AWS@2.3.1",
        trace_id="trace-789"
    )

def test_determinism_invariant():
    """Identical inputs must yield identical outputs."""
    req1 = get_base_request()
    req2 = get_base_request()
    
    resp1 = process_assessment(req1)
    resp2 = process_assessment(req2)
    
    # We ignore assessed_at because it includes the current time
    resp1_dict = resp1.model_dump(exclude={'assessed_at'})
    resp2_dict = resp2.model_dump(exclude={'assessed_at'})
    
    assert resp1_dict == resp2_dict

def test_uninitialized_risk_default():
    """If target system area has no initialized risk entry, system_area_risk defaults to 0.5."""
    req = get_base_request(target_scope="unknown_system")
    resp = process_assessment(req)
    
    # system_risk = 0.5, consequence_scope = 0.2, reversibility = 0.1, precedent_avail = 1.0, visibility = 0.3
    # risk_score = 0.3*0.5 + 0.25*0.2 + 0.15*0.1 + 0.15*1.0 + 0.15*0.3 = 0.41 (MODERATE)
    assert abs(resp.risk_score - 0.41) < 1e-5
    assert resp.risk_band == RiskBand.MODERATE

def test_platform_confidence_poc():
    """Platform confidence is statically 0.3 for the POC."""
    req = get_base_request()
    resp = process_assessment(req)
    assert resp.platform_confidence == 0.3

def test_rule_1_zone_3():
    """Rule 1: If platform_confidence < 0.3 OR cognitive_complexity == HIGH -> ZONE_3"""
    # Test cognitive complexity = HIGH via Analysis action type
    req = get_base_request()
    req.action_descriptor.type = ActionType.ANALYSIS
    resp = process_assessment(req)
    assert resp.zone == AutonomyZone.ZONE_3
    assert resp.justification.rule_matched == 1
    
    # Test cognitive complexity = HIGH via > 5 knowledge dependencies
    req2 = get_base_request()
    req2.action_descriptor.knowledge_dependencies = ["dep1", "dep2", "dep3", "dep4", "dep5", "dep6"]
    resp2 = process_assessment(req2)
    assert resp2.zone == AutonomyZone.ZONE_3
    assert resp2.justification.rule_matched == 1

def test_rule_2_zone_4():
    """Rule 2: If risk_band == HIGH AND (cognitive == HIGH OR operational == HIGH) -> ZONE_4"""
    # Set config system risk for enterprise-wide to 0.9
    config.update_system_risk("enterprise-wide", 0.9)
    
    req = get_base_request(target_scope="enterprise-wide")
    req.action_descriptor.reversibility_hint = ReversibilityHint.IRREVERSIBLE_EFFECTS
    
    resp = process_assessment(req)
    # system_risk = 0.9, consequence_scope = 1.0, reversibility = 1.0
    # risk_score = 0.3*0.9 + 0.25*1.0 + 0.15*1.0 + 0.15*1.0 + 0.15*0.3 = 0.865 (HIGH)
    assert resp.risk_band == RiskBand.HIGH
    assert resp.zone == AutonomyZone.ZONE_4
    assert resp.justification.rule_matched == 2

def test_rule_3_zone_3():
    """Rule 3: If risk_band == HIGH -> ZONE_3"""
    # Set config system risk for single-requirement to 0.9
    config.update_system_risk("single-requirement", 0.9)
    
    req = get_base_request(target_scope="single-requirement")
    req.action_descriptor.reversibility_hint = ReversibilityHint.IRREVERSIBLE_EFFECTS
    
    resp = process_assessment(req)
    # system_risk = 0.9, consequence_scope = 0.4, reversibility = 1.0
    # risk_score = 0.3*0.9 + 0.25*0.4 + 0.15*1.0 + 0.15*1.0 + 0.15*0.3 = 0.715 (HIGH)
    # operational complexity is LOW since target_scope is single-requirement
    assert resp.risk_band == RiskBand.HIGH
    assert resp.zone == AutonomyZone.ZONE_3
    assert resp.justification.rule_matched == 3

def test_rule_4_zone_3():
    """Rule 4: If operational_complexity == HIGH AND platform_confidence < 0.7 -> ZONE_3"""
    # Set config system risk to 0.2 to keep risk band MODERATE
    config.update_system_risk("enterprise-wide", 0.2)
    
    req = get_base_request(target_scope="enterprise-wide")
    resp = process_assessment(req)
    # system_risk = 0.2, consequence_scope = 1.0, reversibility = 0.1
    # risk_score = 0.3*0.2 + 0.25*1.0 + 0.15*0.1 + 0.15*1.0 + 0.15*0.3 = 0.52 (MODERATE)
    # operational complexity is HIGH (target_scope = enterprise-wide)
    # platform_confidence = 0.3 (< 0.7)
    assert resp.risk_band == RiskBand.MODERATE
    assert resp.zone == AutonomyZone.ZONE_3
    assert resp.justification.rule_matched == 4

def test_rule_5_zone_2():
    """Rule 5: If risk_band == MODERATE OR operational_complexity == MODERATE -> ZONE_2"""
    # Test via operational complexity = MODERATE (target_scope = functional-area)
    config.update_system_risk("functional-area", 0.2)
    req = get_base_request(target_scope="functional-area")
    resp = process_assessment(req)
    
    # system_risk = 0.2, consequence_scope = 0.7, reversibility = 0.1
    # risk_score = 0.3*0.2 + 0.25*0.7 + 0.15*0.1 + 0.15*1.0 + 0.15*0.3 = 0.445 (MODERATE)
    assert resp.zone == AutonomyZone.ZONE_2
    assert resp.justification.rule_matched == 5

def test_default_zone_1():
    """DEFAULT: ZONE_1"""
    req = get_base_request() # Low risk reporting_ui
    resp = process_assessment(req)
    assert resp.zone == AutonomyZone.ZONE_1
    assert resp.justification.rule_matched == 6

def test_custom_system_risk_and_precedent_avail():
    """Verify that passing custom system_risk and precedent_avail correctly overrides configuration/defaults."""
    req = get_base_request(target_scope="reporting_ui")
    # Pass custom system_risk and precedent_avail
    req.action_descriptor.system_risk = 0.8
    req.action_descriptor.precedent_avail = 0.2
    
    resp = process_assessment(req)
    
    # system_risk = 0.8, consequence_scope = 0.2 (reporting_ui defaults to 0.2 in engine), reversibility = 0.1, precedent_avail = 0.2, visibility = 0.3
    # risk_score = 0.3*0.8 + 0.25*0.2 + 0.15*0.1 + 0.15*0.2 + 0.15*0.3 = 0.24 + 0.05 + 0.015 + 0.03 + 0.045 = 0.38 (LOW)
    assert abs(resp.risk_score - 0.38) < 1e-5
    assert resp.risk_band == RiskBand.LOW
    assert resp.system_risk == 0.8
    assert resp.precedent_avail == 0.2
    assert resp.justification.system_risk == 0.8
    assert resp.justification.precedent_avail == 0.2
