from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Checkpoint,
    CheckpointResult,
    LessonPlan,
    Message,
    Session as TutorSession,
    Student,
    Topic,
)
from app.queries import (
    active_plan,
    checkpoint_in_use,
    flat_checkpoints,
    load_plan,
    locate,
    latest_result,
    next_position,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def unique_slug(db: Session, title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "lesson"
    slug = base
    suffix = 2
    while db.scalar(select(LessonPlan.id).where(LessonPlan.slug == slug)):
        slug = f"{base[:40]}-{suffix}"
        suffix += 1
    return slug


def clear_active(db: Session) -> None:
    db.execute(
        update(LessonPlan)
        .where(LessonPlan.is_active.is_(True))
        .values(is_active=False, updated_at=now())
    )
    db.flush()


def move_item(db: Session, items: list, item, direction: str) -> None:
    ordered = sorted(items, key=lambda row: row.position)
    index = next(i for i, row in enumerate(ordered) if row.id == item.id)
    other_index = index - 1 if direction == "up" else index + 1
    if other_index < 0 or other_index >= len(ordered):
        return
    other = ordered[other_index]
    item_position = item.position
    other_position = other.position
    item.position = -1
    db.flush()
    other.position = item_position
    db.flush()
    item.position = other_position
    db.flush()


def open_session(
    db: Session,
    student_id: uuid.UUID,
    fresh: bool,
    lesson_plan_id: uuid.UUID | None = None,
) -> TutorSession:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    plan = active_plan(db) if lesson_plan_id is None else load_plan(db, lesson_plan_id)
    if not fresh:
        existing = db.scalar(
            select(TutorSession)
            .where(
                TutorSession.student_id == student.id,
                TutorSession.lesson_plan_id == plan.id,
                TutorSession.status == "in_progress",
            )
            .order_by(TutorSession.updated_at.desc())
        )
        if existing is not None:
            return existing
    rows = flat_checkpoints(plan)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="This lesson has no checkpoints.",
        )
    topic, checkpoint = rows[0]
    tutor_session = TutorSession(
        student_id=student.id,
        lesson_plan_id=plan.id,
        current_topic_id=topic.id,
        current_checkpoint_id=checkpoint.id,
        status="in_progress",
        updated_at=now(),
    )
    db.add(tutor_session)
    db.flush()
    return tutor_session


def append_message(
    db: Session,
    tutor_session: TutorSession,
    role: str,
    content: str,
    client_id: str | None,
) -> Message:
    if client_id:
        existing = db.scalar(select(Message).where(Message.client_id == client_id))
        if existing is not None:
            if existing.session_id != tutor_session.id:
                raise HTTPException(
                    status_code=409, detail="That client_id belongs to another session."
                )
            existing.content = content
            tutor_session.updated_at = now()
            return existing
    seq = db.scalar(
        select(func.max(Message.seq)).where(Message.session_id == tutor_session.id)
    )
    message = Message(
        session_id=tutor_session.id,
        role=role,
        content=content,
        client_id=client_id,
        seq=(seq or 0) + 1,
    )
    db.add(message)
    tutor_session.updated_at = now()
    db.flush()
    return message


def record_result(
    db: Session,
    tutor_session: TutorSession,
    score: int,
    passed: bool,
    feedback: str,
) -> dict:
    if tutor_session.current_checkpoint_id is None:
        return {
            "ok": False,
            "reason": "This lesson is finished, so there is nothing to score.",
        }
    located = locate(tutor_session.lesson_plan, tutor_session.current_checkpoint_id)
    if located is None:
        return {"ok": False, "reason": "The current checkpoint is missing."}
    _topic, checkpoint = located
    seq = db.scalar(
        select(func.max(CheckpointResult.seq)).where(
            CheckpointResult.session_id == tutor_session.id
        )
    )
    result = CheckpointResult(
        session_id=tutor_session.id,
        checkpoint_id=checkpoint.id,
        seq=(seq or 0) + 1,
        score=score,
        passed=passed,
        feedback=feedback.strip(),
    )
    db.add(result)
    tutor_session.updated_at = now()
    db.flush()
    return {
        "ok": True,
        "checkpoint_id": str(checkpoint.id),
        "kind": checkpoint.kind,
        "score": score,
        "passed": passed,
        "feedback": result.feedback,
    }


def advance(db: Session, tutor_session: TutorSession) -> dict:
    if (
        tutor_session.status == "completed"
        or tutor_session.current_checkpoint_id is None
    ):
        return {"ok": False, "reason": "This lesson is already finished."}
    located = locate(tutor_session.lesson_plan, tutor_session.current_checkpoint_id)
    if located is None:
        return {"ok": False, "reason": "The current checkpoint is missing."}
    topic, checkpoint = located
    result = latest_result(tutor_session, checkpoint.id)
    if checkpoint.kind == "quiz" and (result is None or not result.passed):
        return {
            "ok": False,
            "reason": "Refusing to skip this quiz until it has a passing score.",
        }
    if checkpoint.kind == "practice" and (result is None or not result.passed):
        return {
            "ok": False,
            "reason": "This practice step needs a passing result before moving on.",
        }
    rows = flat_checkpoints(tutor_session.lesson_plan)
    index = next(
        i for i, (_topic, item) in enumerate(rows) if item.id == checkpoint.id
    )
    tutor_session.updated_at = now()
    if index + 1 >= len(rows):
        tutor_session.current_topic_id = None
        tutor_session.current_checkpoint_id = None
        tutor_session.status = "completed"
        db.flush()
        return {"ok": True, "completed": True, "current_step": None}
    next_topic, next_checkpoint = rows[index + 1]
    tutor_session.current_topic_id = next_topic.id
    tutor_session.current_checkpoint_id = next_checkpoint.id
    db.flush()
    return {
        "ok": True,
        "completed": False,
        "from_kind": checkpoint.kind,
        "current_step": {
            "topic_title": next_topic.title,
            "topic_position": next_topic.position,
            "checkpoint_kind": next_checkpoint.kind,
            "checkpoint_position": next_checkpoint.position,
        },
    }


def checkpoint_state(
    checkpoint: Checkpoint,
    current_id: uuid.UUID | None,
    result: CheckpointResult | None,
    seen_current: bool,
    lesson_complete: bool,
) -> str:
    if lesson_complete:
        if result is not None and result.passed:
            return "passed"
        if result is not None:
            return "failed"
        return "done"
    if checkpoint.id == current_id:
        return "current"
    if seen_current:
        return "upcoming"
    if result is not None and result.passed:
        return "passed"
    if result is not None:
        return "failed"
    return "done"


def topic_in_use(db: Session, topic: Topic) -> bool:
    current = db.scalar(
        select(func.count())
        .select_from(TutorSession)
        .where(TutorSession.current_topic_id == topic.id)
    )
    if current:
        return True
    return any(checkpoint_in_use(db, checkpoint.id) for checkpoint in topic.checkpoints)


def append_topic(db: Session, plan: LessonPlan, title: str, goal: str, instructions: str) -> Topic:
    topic = Topic(
        lesson_plan_id=plan.id,
        title=title.strip(),
        learning_goal=goal.strip(),
        tutor_instructions=instructions.strip(),
        position=next_position([item.position for item in plan.topics]),
    )
    plan.topics.append(topic)
    plan.updated_at = now()
    db.flush()
    return topic


def append_checkpoint(db: Session, topic: Topic, kind: str, prompt: str, rubric: str, criteria: str) -> Checkpoint:
    checkpoint = Checkpoint(
        topic_id=topic.id,
        kind=kind,
        tutor_prompt=prompt.strip(),
        rubric=blank_to_none(rubric),
        pass_criteria=blank_to_none(criteria),
        position=next_position([item.position for item in topic.checkpoints]),
    )
    topic.checkpoints.append(checkpoint)
    if topic.lesson_plan is not None:
        topic.lesson_plan.updated_at = now()
    db.flush()
    return checkpoint
