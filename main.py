# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse, FileResponse
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from pydantic import ValidationError

from audit import AuditPublishError
from calibration import calibration_service
from control_plane import control_plane_service
from engine import process_assessment
from models import (
    AssessmentRequest,
    AssessmentResponse,
    CalibrationSignalRequest,
    HealthResponse,
    PhaseProgressionAppliedEvent,
    PhaseRollbackRequest,
    PhaseStateResponse,
)
from phase import phase_state
from settings import get_settings
from sync import bootstrap_replicas, replica_sync


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_replicas()
    yield


app = FastAPI(title="CAS Phase 2 Engine", version="2.0.0", lifespan=lifespan)


@app.post("/v1/assess", response_model=AssessmentResponse)
async def assess(request: AssessmentRequest):
    try:
        response = process_assessment(request)
        return response
    except AuditPublishError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during assessment",
        )


@app.post("/v1/calibration/signals")
async def ingest_calibration_signal(signal: CalibrationSignalRequest):
    try:
        summary, readiness_event = calibration_service.ingest_signal(signal)
        payload = {
            "summary": summary.model_dump(mode="json"),
            "readiness_event": readiness_event.model_dump(mode="json") if readiness_event else None,
        }
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.get("/v1/calibration/domains/{knowledge_domain}")
async def get_calibration_domain(knowledge_domain: str):
    return calibration_service.get_domain_summary(knowledge_domain).model_dump(mode="json")


@app.get("/v1/posture", response_model=PhaseStateResponse)
async def get_posture_state():
    return control_plane_service.get_phase_state()


@app.post("/v1/control-plane/events", response_model=PhaseStateResponse)
async def receive_control_plane_event(event: PhaseProgressionAppliedEvent):
    try:
        _, state = control_plane_service.handle_phase_progression_applied(event)
        return state
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.post("/v1/control-plane/rollback", response_model=PhaseStateResponse)
async def rollback_phase(request: PhaseRollbackRequest):
    try:
        _, state = control_plane_service.rollback_phase(request)
        return state
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.get("/health", response_model=HealthResponse)
async def health():
    snapshot = phase_state.get_snapshot()
    return HealthResponse(
        status="ok",
        replica_id=get_settings().replica_id,
        active_phase=snapshot.active_phase,
        phase_version=snapshot.phase_version,
    )


@app.get("/ready")
async def ready():
    try:
        replica_sync.ensure_uniform_phase()
        return {"status": "ready", "replica_id": replica_sync.replica_id}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Invalid Request", "errors": exc.errors()},
    )


@app.get("/")
async def root():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
