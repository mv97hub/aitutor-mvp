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
from app.blocks import apply_checkpoint
from app.queries import (
    active_plan,
    checkpoint_in_use,
    flat_checkpoints,
    load_plan,
    locate,
    latest_result,
    next_position,
)
from app.schemas import CheckpointWrite
from app.widgets import choice_ids, grade_choice, hint_text, hint_tier_for

SCORED_KINDS = {"practice", "quiz", "discovery", "teach_back"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _unique_slug(taken, title: str, fallback: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or fallback
    slug = base
    suffix = 2
    while taken(slug):
        slug = f"{base[:40]}-{suffix}"
        suffix += 1
    return slug


def unique_slug(db: Session, title: str) -> str:
    return _unique_slug(
        lambda slug: db.scalar(select(LessonPlan.id).where(LessonPlan.slug == slug)) is not None,
        title,
        "lesson",
    )


def unique_student_slug(db: Session, name: str) -> str:
    return _unique_slug(
        lambda slug: db.scalar(select(Student.id).where(Student.slug == slug)) is not None,
        name,
        "learner",
    )


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


def plan_fits(student: Student, plan: LessonPlan) -> bool:
    if student.age is None:
        return plan.age_min is None or plan.age_min < 15
    if plan.age_min is not None and student.age < plan.age_min:
        return False
    if plan.age_max is not None and student.age > plan.age_max:
        return False
    return True


def age_block_reason(student: Student, plan: LessonPlan) -> str | None:
    if plan_fits(student, plan):
        return None
    if plan.age_min is not None and plan.age_max is not None:
        band = f"ages {plan.age_min}–{plan.age_max}"
    elif plan.age_min is not None:
        band = f"ages {plan.age_min} and up"
    elif plan.age_max is not None:
        band = f"ages {plan.age_max} and under"
    else:
        band = "a different age"
    who = (
        f"{student.display_name} is {student.age}"
        if student.age is not None
        else f"{student.display_name} has no age on file"
    )
    return f"This lesson is for {band}. {who}."


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
    reason = age_block_reason(student, plan)
    if reason is not None:
        raise HTTPException(status_code=400, detail=reason)
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
    rubric_met: list | None = None,
    misconception: str | None = None,
    hint_tier: str | None = None,
    choice: dict | None = None,
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
        rubric_met=list(rubric_met or []),
        misconception=blank_to_none(misconception),
        hint_tier=hint_tier,
        choice=choice,
    )
    db.add(result)
    tutor_session.updated_at = now()
    db.flush()
    db.expire(tutor_session, ["results"])
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
    if checkpoint.kind in SCORED_KINDS and (result is None or not result.passed):
        label = "quiz" if checkpoint.kind == "quiz" else checkpoint.kind.replace("_", " ")
        return {
            "ok": False,
            "reason": f"This {label} step needs a passing result before moving on.",
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


def append_checkpoint(db: Session, topic: Topic, body: CheckpointWrite) -> Checkpoint:
    checkpoint = Checkpoint(
        topic_id=topic.id,
        kind=body.kind,
        tutor_prompt=body.tutor_prompt.strip(),
        position=next_position([item.position for item in topic.checkpoints]),
    )
    apply_checkpoint(checkpoint, body, None)
    topic.checkpoints.append(checkpoint)
    if topic.lesson_plan is not None:
        topic.lesson_plan.updated_at = now()
    db.flush()
    return checkpoint


def failed_attempts(tutor_session: TutorSession, checkpoint_id: uuid.UUID) -> int:
    return sum(
        1
        for result in tutor_session.results
        if result.checkpoint_id == checkpoint_id and not result.passed
    )


def grade_widget(
    db: Session,
    tutor_session: TutorSession,
    choice: str | list[str],
    explanation: str,
) -> dict:
    if tutor_session.current_checkpoint_id is None:
        return {"ok": False, "reason": "This lesson is finished, so there is nothing to score."}
    located = locate(tutor_session.lesson_plan, tutor_session.current_checkpoint_id)
    if located is None:
        return {"ok": False, "reason": "The current checkpoint is missing."}
    _topic, checkpoint = located
    quiz = checkpoint.quiz if isinstance(checkpoint.quiz, dict) else None
    if quiz is None:
        return {"ok": False, "reason": "This block is a typed reply, not a choice widget."}
    ids = choice_ids(choice)
    if not ids:
        return {"ok": False, "reason": "Choose an answer before sending."}
    graded = grade_choice(quiz, ids if quiz.get("type") in {"multi", "order"} else ids[0])
    passed = graded["score"] >= (checkpoint.pass_score or 70)
    tier = hint_tier_for(failed_attempts(tutor_session, checkpoint.id))
    feedback = "That choice is right." if graded["correct"] else "That choice is not right."
    if graded["misconception"]:
        feedback = f"{feedback} {graded['misconception']}"
    recorded = record_result(
        db,
        tutor_session,
        graded["score"],
        passed,
        feedback.strip(),
        misconception=graded["misconception"],
        hint_tier=tier,
        choice={"ids": ids, "explanation": explanation.strip()},
    )
    return {
        **recorded,
        "correct": graded["correct"],
        "misconception": graded["misconception"],
        "hint_tier": tier,
        "hint_text": hint_text(checkpoint.hint_ladder, tier),
    }


def _row_ids(checkpoint: Checkpoint) -> dict[str, int]:
    weights: dict[str, int] = {}
    for row in checkpoint.rubric_rows or []:
        if isinstance(row, dict) and row.get("id"):
            weights[str(row["id"])] = int(row.get("weight") or 0)
    return weights


def apply_turn_score(
    db: Session,
    tutor_session: TutorSession,
    rubric_met: list[str],
    misconception: str | None,
    advance_flag: bool,
) -> dict:
    if tutor_session.current_checkpoint_id is None:
        return {"ok": False, "reason": "This lesson is finished.", "advanced": False}
    located = locate(tutor_session.lesson_plan, tutor_session.current_checkpoint_id)
    if located is None:
        return {"ok": False, "reason": "The current checkpoint is missing.", "advanced": False}
    _topic, checkpoint = located
    weights = _row_ids(checkpoint)
    met = [row_id for row_id in rubric_met if row_id in weights]
    latest = latest_result(tutor_session, checkpoint.id)
    quiz = checkpoint.quiz if isinstance(checkpoint.quiz, dict) else None
    note = blank_to_none(misconception)

    if quiz is not None and latest is not None and isinstance(latest.choice, dict):
        latest.rubric_met = met
        if not latest.misconception and note and not latest.passed:
            latest.misconception = note
        tutor_session.updated_at = now()
        db.flush()
        should_advance = bool(advance_flag and latest.passed) or (
            latest.passed and not quiz.get("explain")
        )
        advanced = False
        if should_advance:
            moved = advance(db, tutor_session)
            advanced = bool(moved.get("ok"))
        return {
            "ok": True,
            "graded_by": "widget",
            "score": latest.score,
            "passed": latest.passed,
            "advanced": advanced,
            "misconception": latest.misconception,
        }

    if quiz is not None:
        recorded = record_result(
            db,
            tutor_session,
            0,
            False,
            "Choose an answer on the widget.",
            rubric_met=met,
            hint_tier=hint_tier_for(failed_attempts(tutor_session, checkpoint.id)),
        )
        return {**recorded, "advanced": False, "graded_by": "widget"}

    total = sum(weights.values()) or 0
    earned = sum(weights[row_id] for row_id in met)
    score = round(100 * earned / total) if total else 0
    passed = score >= (checkpoint.pass_score or 70)
    tier = hint_tier_for(failed_attempts(tutor_session, checkpoint.id))
    feedback = "That meets this step." if passed else "Not yet. Use the hint and try again."
    recorded = record_result(
        db,
        tutor_session,
        score,
        passed,
        feedback,
        rubric_met=met,
        misconception=None if passed else note,
        hint_tier=tier,
    )
    advanced = False
    if advance_flag and passed:
        moved = advance(db, tutor_session)
        advanced = bool(moved.get("ok"))
    return {**recorded, "advanced": advanced, "graded_by": "model"}
