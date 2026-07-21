from enum import Enum
from pydantic import BaseModel
from typing import List, Optional, Union

class ActionType(str, Enum):
    USER_STORY_REFINEMENT = "User Story Refinement"
    ANALYSIS = "Analysis"
    ASSESSMENT = "Assessment"
    TEST_CASE_DESIGN = "Test Case Design"
    TEST_CASE_GENERATION = "Test Case Generation"
    TEST_CASE_AUTOMATION = "Test Case Automation"
    REQUIREMENTS_REVIEW = "Requirements Review"
    DEFECT_ANALYSIS = "Defect Analysis"
    RISK_ASSESSMENT = "Risk Assessment"
    DOCUMENTATION = "Documentation"
    CODE_REVIEW = "Code Review"
    GENERATE_LOCATORS = "generateLocators"
    EVALUATE = "evaluate"
    OTHER = "Other"

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
    type: ActionType
    target_scope: str
    knowledge_dependencies: Union[float, List[str]]
    reversibility_hint: ReversibilityHint
    system_risk: Optional[float] = None
    precedent_avail: Optional[float] = None

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
    system_risk: float
    precedent_avail: float

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
    system_risk: float
    precedent_avail: float
