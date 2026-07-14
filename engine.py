from datetime import datetime, timezone
from typing import Tuple, Dict

from models import (
    AssessmentRequest, AssessmentResponse, Justification, AutonomyZone,
    ReversibilityHint, RiskBand, ComplexityLevel
)
from config import config
from audit import emit_audit_fragment

def map_reversibility(hint: ReversibilityHint) -> float:
    mapping = {
        ReversibilityHint.TRIVIALLY_REVERSIBLE: 0.1,
        ReversibilityHint.REVERSIBLE_WITH_COST: 0.5,
        ReversibilityHint.IRREVERSIBLE_EFFECTS: 1.0
    }
    return mapping.get(hint, 1.0)

def calculate_risk(request: AssessmentRequest) -> Tuple[float, RiskBand]:
    # system_area_risk: defaults to 0.5 if not found in config or for POC
    system_risk = config.get_system_risk(request.action_descriptor.target_scope)
    if system_risk is None:
        system_risk = 0.5

    # action_consequence_scope mapping from target_scope
    scope_mapping = {
        "enterprise-wide": 1.0,
        "functional-area": 0.7,
        "single-requirement": 0.4,
        "intra-step": 0.2
    }
    consequence_scope = scope_mapping.get(request.action_descriptor.target_scope.lower(), 0.2)

    weights = config.get_weights()
    reversibility_score = map_reversibility(request.action_descriptor.reversibility_hint)
    
    # precedent_availability: For POC, we set it to 1.0.
    precedent_avail = 1.0
    
    # stakeholder_visibility: For POC, we take individual-contributor-visible (0.3).
    visibility = 0.3

    risk_score = (
        weights["system_area_risk"] * system_risk +
        weights["action_consequence_scope"] * consequence_scope +
        weights["reversibility"] * reversibility_score +
        weights["precedent_availability"] * precedent_avail +
        weights["stakeholder_visibility"] * visibility
    )
    
    risk_score = max(0.0, min(1.0, risk_score))
    
    if risk_score <= 0.4:
        band = RiskBand.LOW
    elif risk_score <= 0.7:
        band = RiskBand.MODERATE
    else:
        band = RiskBand.HIGH
        
    return risk_score, band

def classify_complexity(request: AssessmentRequest) -> Tuple[ComplexityLevel, ComplexityLevel]:
    # 1. Cognitive Complexity
    num_deps = len(request.action_descriptor.knowledge_dependencies)
    action_type_lower = request.action_descriptor.type.lower()
    is_rca_analysis = any(kw in action_type_lower for kw in ["rca", "analysis", "assessment"])

    if num_deps > 5 or is_rca_analysis:
        cognitive = ComplexityLevel.HIGH
    elif 3 <= num_deps <= 5:
        cognitive = ComplexityLevel.MODERATE
    else:
        cognitive = ComplexityLevel.LOW

    # 2. Operational Complexity
    target_scope_lower = request.action_descriptor.target_scope.lower()
    if target_scope_lower == "enterprise-wide":
        operational = ComplexityLevel.HIGH
    elif target_scope_lower == "functional-area":
        operational = ComplexityLevel.MODERATE
    else:
        # single-requirement or intra-step or default
        operational = ComplexityLevel.LOW

    return cognitive, operational

def evaluate_rules(
    platform_confidence: float,
    cognitive_complexity: ComplexityLevel,
    operational_complexity: ComplexityLevel,
    risk_band: RiskBand
) -> Tuple[AutonomyZone, int]:
    
    # Rule 1: If platform_confidence < 0.3 OR cognitive_complexity == "HIGH" -> ZONE_3
    if platform_confidence < 0.3 or cognitive_complexity == ComplexityLevel.HIGH:
        return AutonomyZone.ZONE_3, 1
        
    # Rule 2: If risk_band == "HIGH" AND (cognitive == "HIGH" OR operational == "HIGH") -> ZONE_4
    if risk_band == RiskBand.HIGH and (cognitive_complexity == ComplexityLevel.HIGH or operational_complexity == ComplexityLevel.HIGH):
        return AutonomyZone.ZONE_4, 2
        
    # Rule 3: If risk_band == "HIGH" -> ZONE_3
    if risk_band == RiskBand.HIGH:
        return AutonomyZone.ZONE_3, 3
        
    # Rule 4: If operational == "HIGH" AND platform_confidence < 0.7 -> ZONE_3
    if operational_complexity == ComplexityLevel.HIGH and platform_confidence < 0.7:
        return AutonomyZone.ZONE_3, 4
        
    # Rule 5: If risk_band == "MODERATE" OR operational == "MODERATE" -> ZONE_2
    if risk_band == RiskBand.MODERATE or operational_complexity == ComplexityLevel.MODERATE:
        return AutonomyZone.ZONE_2, 5
        
    # DEFAULT
    return AutonomyZone.ZONE_1, 6

def process_assessment(request: AssessmentRequest) -> AssessmentResponse:
    # 1. Calculations
    risk_score, risk_band = calculate_risk(request)
    cognitive_complexity, operational_complexity = classify_complexity(request)
    
    # platform_confidence is set to 0.3 for POC
    platform_confidence = 0.3
    
    # 2. Rule Evaluation
    zone, rule_matched = evaluate_rules(
        platform_confidence=platform_confidence,
        cognitive_complexity=cognitive_complexity,
        operational_complexity=operational_complexity,
        risk_band=risk_band
    )
    
    # 3. Construct Response Payload
    justification = Justification(
        risk_score=risk_score,
        risk_band=risk_band,
        cognitive_complexity=cognitive_complexity,
        operational_complexity=operational_complexity,
        platform_confidence=platform_confidence,
        rule_matched=rule_matched
    )
    
    response = AssessmentResponse(
        request_id=request.request_id,
        zone=zone,
        justification=justification,
        risk_score=risk_score,
        risk_band=risk_band,
        cognitive_complexity=cognitive_complexity,
        operational_complexity=operational_complexity,
        platform_confidence=platform_confidence,
        staleness_flag=False,
        transformation_phase_modifier=None,
        formula_version=config.get_formula_version(),
        assessed_at=datetime.now(timezone.utc).isoformat(),
        assessor_identity="cas-worker-01" # Mock identity for Phase 1
    )
    
    # 4. Synchronous Audit Transaction
    emit_audit_fragment(
        request_payload=request.model_dump(mode='json'),
        response_payload=response.model_dump(mode='json'),
        formula_weights=config.get_weights(),
        rule_matched=rule_matched
    )
    
    # 5. Return mapped zone
    return response
