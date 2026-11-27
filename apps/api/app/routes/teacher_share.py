"""Public read-only revocable Teacher Snapshot API route (F6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.parent_copilot import resolve_teacher_snapshot

router = APIRouter()


@router.get("/teacher/share/{token}")
def get_teacher_snapshot(token: str, db: Session = Depends(get_db)) -> dict:
    return resolve_teacher_snapshot(db, token)
