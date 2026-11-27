"""Quarantined Blind Pre/Post Exam API routes (F2)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.blind_evaluator import (
    DEFAULT_EXAM_ITEM_COUNT,
    build_transfer_grade_bundle,
    course_exam_summary,
    grade_and_record_attempt,
    prepare_exam_prompt_or_cached,
    validate_and_store_exam,
)
from app.database import get_db
from app.models import BlindExam

router = APIRouter()


class ExamPromptRequest(BaseModel):
    phase: str = Field(..., pattern="^(pre|post)$")
    num_items: int = Field(default=DEFAULT_EXAM_ITEM_COUNT, ge=3, le=20)
    force_regenerate: bool = False


class ExamStoreRequest(BaseModel):
    phase: str = Field(..., pattern="^(pre|post)$")
    spec_fingerprint: str | None = None
    items: list[dict] | None = None
    model: str | None = None
    use_deterministic_fallback: bool = False
    num_items: int = Field(default=DEFAULT_EXAM_ITEM_COUNT, ge=3, le=20)


class ExamGradePromptRequest(BaseModel):
    exam_id: uuid.UUID
    answers: dict[str, str] = Field(default_factory=dict)


class ExamAttemptRequest(BaseModel):
    exam_id: uuid.UUID
    student_id: uuid.UUID | None = None
    answers: dict[str, str] = Field(default_factory=dict)
    transfer_grades: list[dict] | None = None
    mode: str = Field(default="human", pattern="^(human|epistemic_sandbox)$")
    harness_chat_id: uuid.UUID | None = None


@router.get("/kc/tutor/courses/{course_id}/exam")
def get_course_exam(
    course_id: uuid.UUID,
    student_id: uuid.UUID | None = Query(default=None),
    phase: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return course_exam_summary(db, goal_id=course_id, student_id=student_id, phase=phase)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/kc/tutor/courses/{course_id}/exam/prompt")
def post_course_exam_prompt(
    course_id: uuid.UUID,
    body: ExamPromptRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return prepare_exam_prompt_or_cached(
            db,
            goal_id=course_id,
            phase=body.phase,
            num_items=body.num_items,
            force_regenerate=body.force_regenerate,
        )
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/kc/tutor/courses/{course_id}/exam")
def post_course_exam(
    course_id: uuid.UUID,
    body: ExamStoreRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        out = validate_and_store_exam(
            db,
            goal_id=course_id,
            phase=body.phase,
            raw_items=body.items,
            spec_fingerprint=body.spec_fingerprint,
            model=body.model,
            use_deterministic_fallback=body.use_deterministic_fallback,
            num_items=body.num_items,
        )
        db.commit()
        return out
    except ValueError as exc:
        db.rollback()
        status = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/kc/tutor/courses/{course_id}/exam/grade-prompt")
def post_course_exam_grade_prompt(
    course_id: uuid.UUID,
    body: ExamGradePromptRequest,
    db: Session = Depends(get_db),
) -> dict:
    exam = db.get(BlindExam, body.exam_id)
    if exam is None or exam.goal_id != course_id:
        raise HTTPException(status_code=404, detail="Blind exam not found for this course.")
    return build_transfer_grade_bundle(exam, body.answers)


@router.post("/kc/tutor/courses/{course_id}/exam/attempts")
def post_course_exam_attempt(
    course_id: uuid.UUID,
    body: ExamAttemptRequest,
    db: Session = Depends(get_db),
) -> dict:
    exam = db.get(BlindExam, body.exam_id)
    if exam is None or exam.goal_id != course_id:
        raise HTTPException(status_code=404, detail="Blind exam not found for this course.")
    try:
        out = grade_and_record_attempt(
            db,
            exam=exam,
            answers=body.answers,
            transfer_grades=body.transfer_grades,
            student_id=body.student_id,
            mode=body.mode,
            harness_chat_id=body.harness_chat_id,
        )
        db.commit()
        return out
    except ValueError as exc:
        db.rollback()
        status = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
