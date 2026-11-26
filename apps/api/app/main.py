import logging
import re

from alembic.runtime.migration import MigrationContext
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.harness import deployed_commit

from app.routes.ai_safety import router as ai_safety_router
from app.routes.harness import router as harness_router
from app.routes.catalog import router as catalog_router
from app.routes.kc import router as kc_router
from app.routes.parents import router as parents_router
from app.routes.sessions import router as sessions_router
from app.routes.studio import router as studio_router
from app.routes.tutor_profile import router as tutor_profile_router

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="AI Tutor", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(catalog_router)
app.include_router(sessions_router)
app.include_router(tutor_profile_router)
app.include_router(studio_router)
app.include_router(kc_router)
app.include_router(ai_safety_router)
app.include_router(parents_router)
app.include_router(harness_router)


@app.exception_handler(IntegrityError)
async def integrity_conflict(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.exception("Save conflict on %s", request.url.path)
    return JSONResponse(
        status_code=409,
        content={"detail": "That save conflicted with another update. Try again."},
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "The tutor service hit an error."})


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/health/revision")
def deployment_revision(db: Session = Depends(get_db)) -> dict:
    """Identify the running API and the revisions stamped in its database."""
    commit = deployed_commit()
    revisions = MigrationContext.configure(db.connection()).get_current_heads()
    return {
        "api_commit": commit if re.fullmatch(r"[0-9a-fA-F]{40}", commit) else None,
        "database_revisions": sorted(revisions),
    }
