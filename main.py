# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, status
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse, FileResponse
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from pydantic import ValidationError

from models import AssessmentRequest, AssessmentResponse
from engine import process_assessment
from audit import AuditPublishError

app = FastAPI(title="CAS Phase 1 Engine", version="1.0.0")

@app.post("/v1/assess", response_model=AssessmentResponse)
async def assess(request: AssessmentRequest):
    try:
        response = process_assessment(request)
        return response
    except AuditPublishError as e:
        # If audit fails, assessment MUST fail and not return the zone.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        # Catch unexpected errors to avoid leaking internal state
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during assessment"
        )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Invalid Request", "errors": exc.errors()},
    )

@app.get("/")
async def root():
    return FileResponse("static/index.html")

# Mount static files for other assets (css, js, images)
app.mount("/static", StaticFiles(directory="static"), name="static")
