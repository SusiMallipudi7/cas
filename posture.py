from typing import Optional, Tuple

from models import AutonomyZone, ComplexityLevel, RiskBand, TransformationPhase


ZONE_SHIFT_MAP = {
    AutonomyZone.ZONE_1: AutonomyZone.ZONE_2,
    AutonomyZone.ZONE_2: AutonomyZone.ZONE_3,
    AutonomyZone.ZONE_3: AutonomyZone.ZONE_3,
    AutonomyZone.ZONE_4: AutonomyZone.ZONE_4,
}


class TransformationPostureEngine:
    """Applies transformation-phase modifiers as the final mapping step."""

    def apply_posture(
        self,
        base_zone: AutonomyZone,
        phase: TransformationPhase,
        risk_band: RiskBand,
        cognitive_complexity: ComplexityLevel,
        operational_complexity: ComplexityLevel,
    ) -> Tuple[AutonomyZone, Optional[str]]:
        if phase == TransformationPhase.CONTEXT_ESTABLISHMENT:
            shifted = ZONE_SHIFT_MAP[base_zone]
            modifier = "CONTEXT_ESTABLISHMENT:+1_ZONE"
            return shifted, modifier

        if phase == TransformationPhase.WORKFLOW_INTEGRATION:
            return base_zone, None

        if phase == TransformationPhase.AI_NATIVE_OPERATION:
            if self._is_high_risk_high_complexity(
                risk_band, cognitive_complexity, operational_complexity
            ):
                return AutonomyZone.ZONE_4, "AI_NATIVE_OPERATION:ZONE_4_LOCK"
            return base_zone, None

        return base_zone, None

    @staticmethod
    def _is_high_risk_high_complexity(
        risk_band: RiskBand,
        cognitive_complexity: ComplexityLevel,
        operational_complexity: ComplexityLevel,
    ) -> bool:
        return risk_band == RiskBand.HIGH and (
            cognitive_complexity == ComplexityLevel.HIGH
            or operational_complexity == ComplexityLevel.HIGH
        )


posture_engine = TransformationPostureEngine()
