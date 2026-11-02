from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Checkpoint, CheckpointResult, LessonPlan, Session as TutorSession, Topic


def load_plan(db: Session, plan_id: uuid.UUID) -> LessonPlan:
    plan = db.scalar(
        select(LessonPlan)
        .where(LessonPlan.id == plan_id)
        .options(selectinload(LessonPlan.topics).selectinload(Topic.checkpoints))
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    return plan


def load_session(db: Session, session_id: uuid.UUID) -> TutorSession:
    tutor_session = db.scalar(
        select(TutorSession)
        .where(TutorSession.id == session_id)
        .options(
            selectinload(TutorSession.student),
            selectinload(TutorSession.lesson_plan)
            .selectinload(LessonPlan.topics)
            .selectinload(Topic.checkpoints),
            selectinload(TutorSession.messages),
            selectinload(TutorSession.results).selectinload(CheckpointResult.checkpoint).selectinload(
                Checkpoint.topic
            ),
        )
    )
    if tutor_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return tutor_session


def active_plan(db: Session) -> LessonPlan:
    plan = db.scalar(
        select(LessonPlan)
        .where(LessonPlan.is_active.is_(True))
        .options(selectinload(LessonPlan.topics).selectinload(Topic.checkpoints))
    )
    if plan is None:
        raise HTTPException(
            status_code=400,
            detail="No active lesson plan. Activate one in admin.",
        )
    return plan


def flat_checkpoints(plan: LessonPlan) -> list[tuple[Topic, Checkpoint]]:
    rows: list[tuple[Topic, Checkpoint]] = []
    for topic in sorted(plan.topics, key=lambda item: item.position):
        for checkpoint in sorted(topic.checkpoints, key=lambda item: item.position):
            rows.append((topic, checkpoint))
    return rows


def locate(
    plan: LessonPlan, checkpoint_id: uuid.UUID | None
) -> tuple[Topic, Checkpoint] | None:
    if checkpoint_id is None:
        return None
    for topic, checkpoint in flat_checkpoints(plan):
        if checkpoint.id == checkpoint_id:
            return topic, checkpoint
    return None


def latest_result(
    tutor_session: TutorSession, checkpoint_id: uuid.UUID
) -> CheckpointResult | None:
    matches = [
        result
        for result in tutor_session.results
        if result.checkpoint_id == checkpoint_id
    ]
    if not matches:
        return None
    return max(matches, key=lambda result: result.seq)


def next_position(values: list[int]) -> int:
    return (max(values) if values else 0) + 1


def checkpoint_in_use(db: Session, checkpoint_id: uuid.UUID) -> bool:
    results = db.scalar(
        select(func.count())
        .select_from(CheckpointResult)
        .where(CheckpointResult.checkpoint_id == checkpoint_id)
    )
    current = db.scalar(
        select(func.count())
        .select_from(TutorSession)
        .where(TutorSession.current_checkpoint_id == checkpoint_id)
    )
    return bool(results or current)
