from enum import Enum
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid

class ReversibilityHint(str, Enum):
    IRREVERSIBLE_EFFECTS = "irreversible"
    REVERSIBLE_WITH_COST = "reversible with cost"
    TRIVIALLY_REVERSIBLE = "trivially reversible"

class ComplexityLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"

class RiskBand(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"

class AutonomyZone(str, Enum):
    ZONE_1 = "ZONE_1"
    ZONE_2 = "ZONE_2"
    ZONE_3 = "ZONE_3"
    ZONE_4 = "ZONE_4"

class ActionDescriptor(BaseModel):
    type: str
    target_scope: str
    knowledge_dependencies: List[str] = []
    reversibility_hint: ReversibilityHint

# Additional context passed either through the upstream parameter generator or another layer.
class ContextMetrics(BaseModel):
    action_consequence_scope: float = Field(default=0.2, ge=0.0, le=1.0) # Enterprise-wide=1.0, Functional=0.7, Single=0.4, Intra=0.2
    stakeholder_visibility: float = Field(default=0.3, ge=0.0, le=1.0) # Release=1.0, Lead=0.6, IC=0.3
    precedent_availability: float = Field(default=0.1, ge=0.0, le=1.0) # 1.0 down to 0.1
    context_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    knowledge_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    precedent_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    cognitive_complexity: ComplexityLevel = ComplexityLevel.LOW
    operational_complexity: ComplexityLevel = ComplexityLevel.LOW
    uninitialized_knowledge_domains: bool = False # Flag for confidence floor invariant

class AssessmentRequest(BaseModel):
    request_id: str
    workflow_instance_id: str
    action_descriptor: ActionDescriptor
    context_snapshot_ref: str
    caller_service: str
    trace_id: str

class Justification(BaseModel):
    risk_score: float
    risk_band: RiskBand
    cognitive_complexity: ComplexityLevel
    operational_complexity: ComplexityLevel
    platform_confidence: float
    rule_matched: int

class AssessmentResponse(BaseModel):
    request_id: str
    zone: AutonomyZone
    justification: Justification
    risk_score: float
    risk_band: RiskBand
    cognitive_complexity: ComplexityLevel
    operational_complexity: ComplexityLevel
    platform_confidence: float
    staleness_flag: bool
    transformation_phase_modifier: Optional[str] = None
    formula_version: str
    assessed_at: str
    assessor_identity: str
