"""Global AI safety settings and the review list for flagged turns."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai_safety import (
    AiSafetyError,
    ensure_ai_safety,
    list_safety_events,
    mark_safety_event_reviewed,
    normalize_ai_safety,
    reset_ai_safety,
    safety_payload,
    save_ai_safety,
)
from app.database import get_db

router = APIRouter()


class ReviewIn(BaseModel):
    reviewed_by: str = Field(default="admin", max_length=120)


def _settings_or_422(action):
    try:
        return action()
    except AiSafetyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ai-safety")
def get_ai_safety(db: Session = Depends(get_db)) -> dict:
    return safety_payload(ensure_ai_safety(db))


@router.put("/ai-safety")
def put_ai_safety(body: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    settings = _settings_or_422(lambda: save_ai_safety(db, body))
    return safety_payload(settings)


@router.post("/ai-safety/reset")
def post_ai_safety_reset(db: Session = Depends(get_db)) -> dict:
    return safety_payload(reset_ai_safety(db))


@router.post("/ai-safety/preview")
def post_ai_safety_preview(body: dict = Body(...), age: int | None = None) -> dict:
    """The Safety section for a draft. Nothing is saved."""
    settings = _settings_or_422(lambda: normalize_ai_safety(body, strict=True))
    return safety_payload(settings, age=age)


@router.get("/safety-events")
def get_safety_events(
    student_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    category: str | None = None,
    reviewed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    return _settings_or_422(
        lambda: list_safety_events(
            db,
            student_id=student_id,
            session_id=session_id,
            category=category,
            reviewed=reviewed,
            limit=limit,
            offset=offset,
        )
    )


@router.post("/safety-events/{event_id}/review")
def post_safety_event_review(
    event_id: uuid.UUID,
    body: ReviewIn | None = None,
    db: Session = Depends(get_db),
) -> dict:
    reviewed_by = body.reviewed_by if body is not None else "admin"
    found = _settings_or_422(lambda: mark_safety_event_reviewed(db, event_id, reviewed_by))
    if not found:
        raise HTTPException(status_code=404, detail="That safety event was not found.")
    return found
