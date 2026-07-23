from datetime import datetime
from enum import Enum
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union


class TransformationPhase(str, Enum):
    CONTEXT_ESTABLISHMENT = "CONTEXT_ESTABLISHMENT"
    WORKFLOW_INTEGRATION = "WORKFLOW_INTEGRATION"
    AI_NATIVE_OPERATION = "AI_NATIVE_OPERATION"


class CalibrationSignalType(str, Enum):
    OUTCOME = "outcome"
    HUMAN_FEEDBACK = "human_feedback"
    RETROSPECTIVE = "retrospective"


class CalibrationOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CORRECTION = "correction"
    ESCALATION = "escalation"
    WARRANTED = "warranted"
    UNWARRANTED = "unwarranted"
    UNDER_CAUTIOUS = "under_cautious"
    OVER_CAUTIOUS = "over_cautious"


class PhaseTransitionDirection(str, Enum):
    FORWARD = "forward"
    ROLLBACK = "rollback"

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
    knowledge_domain: Optional[str] = None

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
    original_zone: str
    shifted_zone: str
    calibration_signal_count: int

class AssessmentResponse(BaseModel):
    request_id: str
    zone: AutonomyZone
    base_zone: Optional[AutonomyZone] = None
    justification: Justification
    risk_score: float
    risk_band: RiskBand
    cognitive_complexity: ComplexityLevel
    operational_complexity: ComplexityLevel
    platform_confidence: float
    staleness_flag: bool
    transformation_phase_modifier: Optional[str] = None
    active_phase: Optional[TransformationPhase] = None
    formula_version: str
    assessed_at: str
    assessor_identity: str
    system_risk: float
    precedent_avail: float
    original_zone: str
    shifted_zone: str
    calibration_signal_count: int


class CalibrationSignalRequest(BaseModel):
    knowledge_domain: str
    action_type: ActionType
    signal_type: CalibrationSignalType
    outcome: CalibrationOutcome
    request_id: str
    assignment_id: Optional[str] = None
    trace_id: Optional[str] = None


class CalibrationCounterState(BaseModel):
    knowledge_domain: str
    action_type: ActionType
    count: int
    threshold: int = 20


class DomainCalibrationSummary(BaseModel):
    knowledge_domain: str
    total_signals: int
    threshold: int = 20
    ready_for_progression: bool
    counters: List[CalibrationCounterState]


class CalibrationReadinessEvent(BaseModel):
    event_type: str = "CalibrationReadinessReached"
    knowledge_domain: str
    total_signals: int
    threshold: int
    emitted_at: str


class PhaseProgressionAppliedEvent(BaseModel):
    event_type: str = "PhaseProgressionApplied"
    target_phase: TransformationPhase
    previous_phase: TransformationPhase
    transition_id: str
    direction: PhaseTransitionDirection = PhaseTransitionDirection.FORWARD
    applied_at: str
    source_replica_count: int = Field(ge=1)


class PhaseStateResponse(BaseModel):
    active_phase: TransformationPhase
    phase_version: int
    previous_phase: Optional[TransformationPhase] = None
    transition_id: Optional[str] = None
    replica_id: str
    replica_sync_status: Dict[str, str]
    calibration_ready_domains: List[str]


class PhaseRollbackRequest(BaseModel):
    transition_id: Optional[str] = None
    reason: str = "post_transition_regression"


class HealthResponse(BaseModel):
    status: str
    replica_id: str
    active_phase: TransformationPhase
    phase_version: int
