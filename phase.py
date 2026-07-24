import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from models import PhaseTransitionDirection, TransformationPhase
from settings import get_settings


PHASE_ORDER = [
    TransformationPhase.CONTEXT_ESTABLISHMENT,
    TransformationPhase.WORKFLOW_INTEGRATION,
    TransformationPhase.AI_NATIVE_OPERATION,
]


@dataclass(frozen=True)
class PhaseSnapshot:
    active_phase: TransformationPhase
    phase_version: int
    previous_phase: Optional[TransformationPhase]
    transition_id: str
    applied_at: str


class PhaseStateManager:
    """Thread-safe phase state with rollback support."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        settings = get_settings()
        initial_phase = TransformationPhase(settings.default_phase)
        transition_id = str(uuid.uuid4())
        self._history: List[PhaseSnapshot] = [
            PhaseSnapshot(
                active_phase=initial_phase,
                phase_version=1,
                previous_phase=None,
                transition_id=transition_id,
                applied_at=datetime.now(timezone.utc).isoformat(),
            )
        ]
        self._calibration_ready_domains: set[str] = set()

    def get_snapshot(self) -> PhaseSnapshot:
        with self._lock:
            return self._history[-1]

    def get_active_phase(self) -> TransformationPhase:
        return self.get_snapshot().active_phase

    def get_phase_version(self) -> int:
        return self.get_snapshot().phase_version

    def get_previous_phase(self) -> Optional[TransformationPhase]:
        return self.get_snapshot().previous_phase

    def get_transition_id(self) -> str:
        return self.get_snapshot().transition_id

    def mark_domain_calibration_ready(self, knowledge_domain: str) -> bool:
        with self._lock:
            if knowledge_domain in self._calibration_ready_domains:
                return False
            self._calibration_ready_domains.add(knowledge_domain)
            return True

    def get_calibration_ready_domains(self) -> List[str]:
        with self._lock:
            return sorted(self._calibration_ready_domains)

    def apply_progression(
        self,
        target_phase: TransformationPhase,
        transition_id: str,
        direction: PhaseTransitionDirection = PhaseTransitionDirection.FORWARD,
    ) -> Tuple[PhaseSnapshot, PhaseSnapshot]:
        with self._lock:
            current = self._history[-1]
            if current.transition_id == transition_id and current.active_phase == target_phase:
                return current, current

            if direction == PhaseTransitionDirection.ROLLBACK:
                previous = self._find_snapshot_for_rollback(target_phase, transition_id)
                if previous is None:
                    raise ValueError(
                        f"No rollback target found for phase={target_phase.value}, "
                        f"transition_id={transition_id}"
                    )
                new_snapshot = PhaseSnapshot(
                    active_phase=previous.active_phase,
                    phase_version=current.phase_version + 1,
                    previous_phase=current.active_phase,
                    transition_id=transition_id or str(uuid.uuid4()),
                    applied_at=datetime.now(timezone.utc).isoformat(),
                )
            else:
                new_snapshot = PhaseSnapshot(
                    active_phase=target_phase,
                    phase_version=current.phase_version + 1,
                    previous_phase=current.active_phase,
                    transition_id=transition_id,
                    applied_at=datetime.now(timezone.utc).isoformat(),
                )

            self._history.append(new_snapshot)
            return current, new_snapshot

    def _find_snapshot_for_rollback(
        self,
        target_phase: TransformationPhase,
        transition_id: Optional[str],
    ) -> Optional[PhaseSnapshot]:
        if transition_id:
            for snapshot in reversed(self._history[:-1]):
                if snapshot.transition_id == transition_id:
                    return snapshot

        for snapshot in reversed(self._history[:-1]):
            if snapshot.active_phase == target_phase:
                return snapshot
        return None

    def next_phase(self) -> Optional[TransformationPhase]:
        current = self.get_active_phase()
        try:
            index = PHASE_ORDER.index(current)
        except ValueError:
            return None
        if index + 1 >= len(PHASE_ORDER):
            return None
        return PHASE_ORDER[index + 1]

    def reset_for_tests(self) -> None:
        with self._lock:
            settings = get_settings()
            initial_phase = TransformationPhase(settings.default_phase)
            transition_id = str(uuid.uuid4())
            self._history = [
                PhaseSnapshot(
                    active_phase=initial_phase,
                    phase_version=1,
                    previous_phase=None,
                    transition_id=transition_id,
                    applied_at=datetime.now(timezone.utc).isoformat(),
                )
            ]
            self._calibration_ready_domains.clear()


phase_state = PhaseStateManager()
