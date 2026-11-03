from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.catalog import router as catalog_router
from app.routes.sessions import router as sessions_router
from app.routes.tutor_profile import router as tutor_profile_router

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


@app.get("/health")
def health() -> dict:
    return {"ok": True}
