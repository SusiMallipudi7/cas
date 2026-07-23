import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from models import (
    ActionType,
    CalibrationCounterState,
    CalibrationOutcome,
    CalibrationReadinessEvent,
    CalibrationSignalRequest,
    DomainCalibrationSummary,
)
from phase import phase_state
from settings import get_settings


VALID_OUTCOMES = set(CalibrationOutcome)


class CalibrationCounterService:
    """Atomic counters per (knowledge_domain, action_type) with domain readiness events."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[Tuple[str, ActionType], int] = defaultdict(int)
        self._readiness_events: List[CalibrationReadinessEvent] = []
        self._processed_signal_ids: Set[str] = set()

    def ingest_signal(self, signal: CalibrationSignalRequest) -> Tuple[DomainCalibrationSummary, Optional[CalibrationReadinessEvent]]:
        if signal.outcome not in VALID_OUTCOMES:
            raise ValueError(f"Invalid calibration outcome: {signal.outcome}")

        signal_id = signal.assignment_id or signal.request_id

        settings = get_settings()
        key = (signal.knowledge_domain, signal.action_type)

        with self._lock:
            if signal_id in self._processed_signal_ids:
                raise ValueError(f"Duplicate calibration signal rejected: Assessment ID '{signal_id}' has already been processed.")

            self._processed_signal_ids.add(signal_id)
            self._counters[key] += 1
            summary = self._build_domain_summary_locked(signal.knowledge_domain, settings.calibration_threshold)
            readiness_event = None

            if summary.ready_for_progression:
                if phase_state.mark_domain_calibration_ready(signal.knowledge_domain):
                    readiness_event = CalibrationReadinessEvent(
                        knowledge_domain=signal.knowledge_domain,
                        total_signals=summary.total_signals,
                        threshold=settings.calibration_threshold,
                        emitted_at=datetime.now(timezone.utc).isoformat(),
                    )
                    self._readiness_events.append(readiness_event)

            return summary, readiness_event

    def get_domain_summary(self, knowledge_domain: str) -> DomainCalibrationSummary:
        settings = get_settings()
        with self._lock:
            return self._build_domain_summary_locked(knowledge_domain, settings.calibration_threshold)

    def get_all_summaries(self) -> List[DomainCalibrationSummary]:
        settings = get_settings()
        with self._lock:
            domains = {domain for domain, _ in self._counters.keys()}
            return [
                self._build_domain_summary_locked(domain, settings.calibration_threshold)
                for domain in sorted(domains)
            ]

    def get_readiness_events(self) -> List[CalibrationReadinessEvent]:
        with self._lock:
            return list(self._readiness_events)

    def reset_for_tests(self) -> None:
        with self._lock:
            self._counters.clear()
            self._readiness_events.clear()
            self._processed_signal_ids.clear()

    def _build_domain_summary_locked(
        self,
        knowledge_domain: str,
        threshold: int,
    ) -> DomainCalibrationSummary:
        counters: List[CalibrationCounterState] = []
        total = 0
        for (domain, action_type), count in self._counters.items():
            if domain != knowledge_domain:
                continue
            total += count
            counters.append(
                CalibrationCounterState(
                    knowledge_domain=domain,
                    action_type=action_type,
                    count=count,
                    threshold=threshold,
                )
            )

        return DomainCalibrationSummary(
            knowledge_domain=knowledge_domain,
            total_signals=total,
            threshold=threshold,
            ready_for_progression=total >= threshold,
            counters=sorted(counters, key=lambda item: item.action_type.value),
        )


calibration_service = CalibrationCounterService()
