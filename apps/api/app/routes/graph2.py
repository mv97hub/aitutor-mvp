"""Graph-2 API endpoints: shared eight-spoke radar and post-close batch judge handshakes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.graph2 import (
    apply_judge_results,
    build_radar_payload,
    mark_judge_failed,
    prepare_judge_request,
)
from app.models import KcSession, Student

router = APIRouter()


class JudgeGradeIn(BaseModel):
    skill: str
    grade: int = Field(ge=0, le=3)
    quote: str = ""
    rationale: str = ""


class JudgeResultIn(BaseModel):
    grades: list[JudgeGradeIn] = Field(default_factory=list)
    multi_perspective_synthesis: bool = False


def _student_or_404(db: Session, student_id: uuid.UUID) -> Student:
    row = db.get(Student, student_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That student was not found.")
    return row


def _session_or_404(db: Session, session_id: uuid.UUID) -> KcSession:
    row = db.get(KcSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That session is not open.")
    return row


@router.get("/kc/students/{student_id}/radar")
def get_student_radar(student_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Shared eight-spoke radar payload for child Detailed Progress."""
    student = _student_or_404(db, student_id)
    return build_radar_payload(db, student.id)


@router.post("/kc/tutor/sessions/{session_id}/graph2/judge-prompt")
def post_graph2_judge_prompt(session_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Build the single post-close 0-3 batch judge prompt + strict JSON schema."""
    return prepare_judge_request(db, _session_or_404(db, session_id))


@router.post("/kc/tutor/sessions/{session_id}/graph2/judge-result")
def post_graph2_judge_result(
    session_id: uuid.UUID,
    body: JudgeResultIn,
    db: Session = Depends(get_db),
) -> dict:
    """Validate and apply post-close batch judge grades (idempotent per session+skill)."""
    session = _session_or_404(db, session_id)
    try:
        return apply_judge_results(db, session, body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/kc/tutor/sessions/{session_id}/graph2/judge-failed")
def post_graph2_judge_failed(session_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    """Record a batch judge failure while preserving sync biomarkers, end card, and prior note."""
    return mark_judge_failed(db, _session_or_404(db, session_id))
