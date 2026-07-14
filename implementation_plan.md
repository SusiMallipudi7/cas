# Context Autonomy Service (CAS) - Phase 1 Engine

This document outlines the implementation plan for Phase 1 of the Context Autonomy Service (CAS), a deterministic governance microservice for an STLC automation platform.

## User Review Required

> [!IMPORTANT]
> Please review the Open Questions below. The input payload provided in the requirements does not specify how certain variables (like `cognitive_complexity`, `operational_complexity`, `precedent_strength`, etc.) are passed to the service. We need to decide if they belong in the `action_descriptor` or elsewhere in the request payload.

> [!WARNING]
> The Risk Score Formula specifies that if an uninitialized risk entry is encountered, `risk_score` defaults to 0.8 immediately. This short-circuits the rest of the risk score calculation. Please confirm this behavior is intended.

> [!NOTE]
> The audit stream publisher will be mocked using an abstract interface and an in-memory implementation for Phase 1, to simulate the blocking/synchronous behavior. Is there a specific protocol or broker (e.g., Kafka) SDK you'd like to prepare for in the interface design?

## Open Questions

1. **Missing Input Fields**: The rules reference `cognitive_complexity` and `operational_complexity`, but they are not listed in the Request Schema (Section 5.1). Should these be added to the `action_descriptor`?
2. **Additional Factors**: Factors like `action_consequence_scope`, `stakeholder_visibility`, `precedent_availability`, `context_confidence`, `knowledge_coverage`, and `precedent_strength` need to be provided to the engine. Should these be part of a `context_metrics` object in the request payload?
3. **Knowledge Dependencies**: The Platform Confidence formula mentions checking if a knowledge domain dependency is "uninitialized" and calculating `knowledge_coverage` based on `element_confidence >= 0.5`. Should `knowledge_dependencies` be a list of objects containing `domain_id` and `element_confidence`, rather than a simple array of strings?
4. **Configuration Cache**: You mentioned an "in-memory configuration cache" and a "Read-Write Lock Pattern". Should we implement a basic Thread-safe Singleton for this configuration (e.g., for `system_area_risk`), and provide endpoints to update it?

## Proposed Changes

We will build this service using **FastAPI** due to its high performance, built-in Pydantic validation (for strict schemas), and support for asynchronous operations. 

---

### API Layer & Configuration
#### [NEW] [main.py](file:///d:/CAS%20experiment/main.py)
- Setup FastAPI application.
- Exception handlers for malformed requests (`Invalid Request`).
- POST `/v1/assess` endpoint for handling the assessment request.

#### [NEW] [config.py](file:///d:/CAS%20experiment/config.py)
- Configuration Singleton implementing the Read-Write Lock Pattern.
- Holds weights for formulas, risk metrics for system areas, and other tunable parameters.
- Allows thread-safe updates and reads.

---

### Core Data Models (Schemas)
#### [NEW] [models.py](file:///d:/CAS%20experiment/models.py)
- Defines strict Pydantic models for incoming requests (`AssessmentRequest`, `ActionDescriptor`).
- Defines Pydantic models for the response payload (`AssessmentResponse`, `Justification`).
- Defines Enums (`ReversibilityHint`, `AutonomyZone`, `RiskBand`, `ComplexityLevel`).

---

### Evaluation Engine
#### [NEW] [engine.py](file:///d:/CAS%20experiment/engine.py)
- `evaluate_assessment(request: AssessmentRequest) -> AssessmentResponse`
- Implementation of the Deterministic Core:
    - **Reversibility Mapping**: qualitative to numeric.
    - **Risk Score Formula**: Weight calculations, uninitialized risk short-circuit, and risk band mapping.
    - **Platform Confidence Formula**: Calculation and uninitialized cap check.
    - **Matrix Rule Evaluation**: Sequential rules to determine the Autonomy Zone.

---

### Audit Subsystem
#### [NEW] [audit.py](file:///d:/CAS%20experiment/audit.py)
- `AuditPublisher` abstract interface.
- `MockAuditPublisher` implementation that simulates a synchronous blocking write (and can be configured to fail/timeout for testing).
- `emit_audit_fragment` function that takes request, response, formula metadata and matches, and raises an exception if the write fails.

---

### Testing
#### [NEW] [test_engine.py](file:///d:/CAS%20experiment/tests/test_engine.py)
- Pytest suite covering the golden dataset to guarantee 100% determinism.
- Tests for all rule combinations, missing configuration short-circuits, and audit failures.

## Verification Plan

### Automated Tests
- `pytest tests/ -v --cov=.` to ensure complete coverage of the determinism rules and edge cases.
- Mocking the audit streamer to throw errors and ensure the assessment request fails completely, preventing un-audited decisions.

### Manual Verification
- Start the FastAPI server using `uvicorn main:app --reload`.
- Use curl/Postman to send various valid and invalid request payloads to verify Pydantic validation and zone output.
- Concurrently send requests (using a tool like `wrk` or `ab`) while modifying the configuration cache to verify the Read-Write lock prevents race conditions and ensures sub-500ms P99 latency.
