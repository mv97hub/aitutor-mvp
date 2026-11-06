from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.engine.assemble import hint_tier_for, struggle_limit
from app.engine.defaults import profile_for_age
from app.tutor_profile import load_profile
from app.models import Course, GoalResult, Message, ModelPrompt, Quest, Session as TutorSession, Student
from app.prompt_loader import PASS_SCORE
from app.queries import (
    active_close_question,
    awaiting_tap_reply,
    choice_offer,
    choice_submitted,
    close_choice_widget,
    close_failed_attempts,
    close_is_empty,
    close_question_index_of,
    close_questions,
    close_running_score,
    latest_close_result,
    latest_result,
    locate_goal,
    ordered_goals,
    replied_after_teaching,
)
from app.widgets import choice_ids, grade_choice, hint_text

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


def unique_student_slug(db: Session, name: str) -> str:
    return _unique_slug(
        lambda slug: db.scalar(select(Student.id).where(Student.slug == slug)) is not None,
        name,
        "learner",
    )


def unique_course_code(db: Session, title: str) -> str:
    return _unique_slug(
        lambda code: db.scalar(select(Course.id).where(Course.code == code)) is not None,
        title,
        "course",
    )


def apply_student_profile(student: Student, *, provided: set[str]) -> None:
    """Fill any layer field the request left out from the age-band defaults."""
    profile = profile_for_age(student.age)
    if "reading_level" not in provided:
        student.reading_level = profile.reading_level
    if "modality" not in provided:
        student.modality = profile.modality
    if "interests" not in provided:
        student.interests = []
    if "tutor_persona" not in provided:
        student.tutor_persona = profile.persona
    if "tutor_lexicon" not in provided:
        student.tutor_lexicon = profile.lexicon
    if "tutor_metaphors" not in provided:
        student.tutor_metaphors = profile.metaphors
    if "tutor_sidekick" not in provided:
        student.tutor_sidekick = profile.sidekick
    if "tutor_socratic_strictness" not in provided:
        student.tutor_socratic_strictness = profile.socratic_strictness
    if "tutor_struggle_window" not in provided:
        student.tutor_struggle_window = profile.struggle_window
    if "tutor_anti_spoiler" not in provided:
        student.tutor_anti_spoiler = profile.anti_spoiler
    if "tutor_pacing" not in provided:
        student.tutor_pacing = profile.pacing


def open_session(db: Session, student_id: uuid.UUID, quest_id: uuid.UUID, fresh: bool) -> TutorSession:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    from app.queries import load_quest

    quest = load_quest(db, quest_id)
    if not fresh:
        existing = db.scalar(
            select(TutorSession)
            .where(
                TutorSession.student_id == student.id,
                TutorSession.quest_id == quest.id,
                TutorSession.status == "in_progress",
            )
            .order_by(TutorSession.updated_at.desc())
        )
        if existing is not None:
            return existing
    goals = ordered_goals(quest)
    tutor_session = TutorSession(
        student_id=student.id,
        quest_id=quest.id,
        current_goal_id=goals[0].id if goals else None,
        close_started=not goals,
        close_question_index=0,
        status="completed" if not goals and close_is_empty(quest) else "in_progress",
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
                raise HTTPException(status_code=409, detail="That client_id belongs to another session.")
            existing.content = content
            tutor_session.updated_at = now()
            return existing
    seq = db.scalar(select(func.max(Message.seq)).where(Message.session_id == tutor_session.id))
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


def append_model_prompt(
    db: Session,
    tutor_session: TutorSession,
    system_prompt: str,
    messages: list,
    model: str,
    message_id: uuid.UUID | None = None,
) -> ModelPrompt:
    linked = None
    if message_id is not None:
        linked = db.get(Message, message_id)
        if linked is None or linked.session_id != tutor_session.id:
            raise HTTPException(status_code=400, detail="That message is not part of this class.")
    seq = db.scalar(
        select(func.max(ModelPrompt.seq)).where(ModelPrompt.session_id == tutor_session.id)
    )
    row = ModelPrompt(
        session_id=tutor_session.id,
        message_id=linked.id if linked is not None else None,
        seq=(seq or 0) + 1,
        system_prompt=system_prompt,
        messages=messages,
        model=model.strip(),
    )
    db.add(row)
    db.flush()
    return row


def failed_attempts(tutor_session: TutorSession, goal_id: uuid.UUID | None) -> int:
    if goal_id is None:
        return close_failed_attempts(tutor_session)
    return sum(1 for result in tutor_session.results if result.goal_id == goal_id and not result.passed)


HINTS = {
    "nudge": "What is the question actually asking?",
    "analogy": "Picture the idea with one concrete object.",
    "scaffold": "Say the idea in one sentence, then the part you are sure about.",
}


def _active_goal_id(tutor_session: TutorSession) -> uuid.UUID | None:
    if tutor_session.close_started or tutor_session.status == "completed":
        return None
    return tutor_session.current_goal_id


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
    if tutor_session.status == "completed":
        return {"ok": False, "reason": "This quest is finished, so there is nothing to score."}
    goal = locate_goal(tutor_session.quest, tutor_session.current_goal_id)
    if tutor_session.close_started:
        goal = None
    elif goal is None:
        return {"ok": False, "reason": "This quest is finished, so there is nothing to score."}
    seq = db.scalar(select(func.max(GoalResult.seq)).where(GoalResult.session_id == tutor_session.id))
    criterion = ""
    answer = ""
    if goal is not None:
        criterion = goal.success_criterion or ""
    else:
        index = close_question_index_of(tutor_session)
        active = active_close_question(tutor_session.quest.close, tutor_session)
        answer = active["text"] if active else ""
        if not isinstance(choice, dict):
            choice = {"question_index": index}
        else:
            choice = dict(choice)
            choice["question_index"] = index
        score = close_running_score(tutor_session, index=index, passed=passed)
    result = GoalResult(
        session_id=tutor_session.id,
        goal_id=goal.id if goal is not None else None,
        seq=(seq or 0) + 1,
        score=score,
        passed=passed,
        feedback=feedback.strip(),
        criterion=criterion,
        answer=answer,
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
        "goal_id": str(goal.id) if goal is not None else None,
        "role": "goal" if goal is not None else "close",
        "score": score,
        "passed": passed,
        "feedback": result.feedback,
    }


def _complete(db: Session, tutor_session: TutorSession) -> dict:
    tutor_session.current_goal_id = None
    tutor_session.close_started = True
    tutor_session.status = "completed"
    tutor_session.updated_at = now()
    db.flush()
    return {"ok": True, "completed": True}


def advance(db: Session, tutor_session: TutorSession, *, allow_unpassed: bool = False) -> dict:
    if tutor_session.status == "completed":
        return {"ok": False, "reason": "This quest is already finished."}
    goal = None if tutor_session.close_started else locate_goal(tutor_session.quest, tutor_session.current_goal_id)
    goal_id = None if tutor_session.close_started else (goal.id if goal is not None else None)
    result = latest_result(tutor_session, goal_id)
    if result is None or (not result.passed and not allow_unpassed):
        return {"ok": False, "reason": "This goal needs a passing result before moving on."}
    tutor_session.updated_at = now()
    if tutor_session.close_started:
        questions = close_questions(tutor_session.quest.close)
        index = close_question_index_of(tutor_session)
        if index + 1 < len(questions):
            tutor_session.close_question_index = index + 1
            db.flush()
            return {"ok": True, "completed": False}
        return _complete(db, tutor_session)
    goals = ordered_goals(tutor_session.quest)
    index = next(i for i, item in enumerate(goals) if item.id == goal.id)
    if index + 1 < len(goals):
        tutor_session.current_goal_id = goals[index + 1].id
        tutor_session.close_started = False
        tutor_session.close_question_index = 0
        db.flush()
        return {"ok": True, "completed": False}
    tutor_session.current_goal_id = None
    tutor_session.close_started = True
    tutor_session.close_question_index = 0
    if close_is_empty(tutor_session.quest):
        return _complete(db, tutor_session)
    db.flush()
    return {"ok": True, "completed": False}


def grade_widget(
    db: Session,
    tutor_session: TutorSession,
    choice: str | list[str],
    explanation: str,
) -> dict:
    if tutor_session.status == "completed":
        return {"ok": False, "reason": "This quest is finished, so there is nothing to score."}
    quiz = close_choice_widget(tutor_session.quest, tutor_session)
    if quiz is None:
        return {"ok": False, "reason": "This step is a typed reply, not a choice card."}
    ids = choice_ids(choice)
    if awaiting_tap_reply(tutor_session):
        latest = latest_result(tutor_session, None)
        same = (
            latest is not None
            and isinstance(latest.choice, dict)
            and list(latest.choice.get("ids") or []) == ids
        )
        if same:
            return {
                "ok": True,
                "correct": bool(latest.passed),
                "passed": latest.passed,
                "score": latest.score,
                "misconception": latest.misconception,
                "hint_tier": latest.hint_tier,
                "hint_text": hint_text(HINTS, latest.hint_tier or "nudge"),
            }
    if not ids:
        return {"ok": False, "reason": "Choose an answer before sending."}
    graded = grade_choice(quiz, ids if quiz.get("type") in {"multi", "order"} else ids[0])
    passed = graded["correct"] is True
    tier = hint_tier_for(failed_attempts(tutor_session, None))
    tried = ", ".join(
        str(item.get("text") or "")
        for item in quiz.get("choices") or []
        if isinstance(item, dict) and item.get("id") in ids
    ) or "that choice"
    if graded["correct"]:
        feedback = f"They picked {tried}. It answers the question."
        graded["misconception"] = None
    else:
        feedback = f"They picked {tried}. It does not answer the question."
        graded["misconception"] = feedback
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
        "hint_text": hint_text(HINTS, tier),
    }


def _window_closed(db: Session, tutor_session: TutorSession, goal_id: uuid.UUID | None) -> bool:
    return failed_attempts(tutor_session, goal_id) >= struggle_limit(load_profile(db).struggle_window)


def apply_turn_score(
    db: Session,
    tutor_session: TutorSession,
    rubric_met: list[str],
    misconception: str | None,
    advance_flag: bool,
) -> dict:
    if tutor_session.status == "completed":
        return {"ok": False, "reason": "This quest is finished.", "advanced": False}
    on_close = tutor_session.close_started
    goal = None if on_close else locate_goal(tutor_session.quest, tutor_session.current_goal_id)
    if not on_close and goal is None:
        return {"ok": False, "reason": "This quest is finished.", "advanced": False}
    goal_id = None if on_close else goal.id
    quiz = close_choice_widget(tutor_session.quest, tutor_session) if on_close else None
    if on_close:
        latest_close = latest_close_result(tutor_session)
        if latest_close is not None and latest_close.passed:
            advanced = False
            if advance_flag:
                moved = advance(db, tutor_session, allow_unpassed=False)
                advanced = bool(moved.get("ok"))
            return {
                "ok": True,
                "graded_by": "widget" if quiz is not None else "model",
                "score": latest_close.score,
                "passed": True,
                "advanced": advanced,
                "feedback": latest_close.feedback,
            }
    met = [row_id for row_id in rubric_met if row_id == "criterion"]
    passed = "criterion" in met
    score = 100 if passed else 0
    note = blank_to_none(misconception)
    reveal = _window_closed(db, tutor_session, goal_id)
    quiz = close_choice_widget(tutor_session.quest, tutor_session) if on_close else None
    if quiz is not None and choice_offer(tutor_session) == "ask" and not awaiting_tap_reply(tutor_session):
        return {
            "ok": True,
            "advanced": False,
            "graded_by": "widget",
            "passed": False,
            "score": 0,
            "feedback": "Choose an answer on the card.",
        }
    if quiz is not None and awaiting_tap_reply(tutor_session):
        latest = latest_result(tutor_session, None)
        advanced = False
        if latest is not None and advance_flag and (latest.passed or reveal):
            moved = advance(db, tutor_session, allow_unpassed=reveal and not latest.passed)
            advanced = bool(moved.get("ok"))
        return {
            "ok": True,
            "graded_by": "widget",
            "score": latest.score if latest is not None else 0,
            "passed": bool(latest.passed) if latest is not None else False,
            "advanced": advanced,
        }
    if on_close and quiz is None and not replied_after_teaching(tutor_session) and not close_is_empty(tutor_session.quest):
        return {
            "ok": True,
            "advanced": False,
            "graded_by": "opening",
            "passed": False,
            "score": 0,
            "feedback": "The close is still being taught.",
        }
    feedback = "That meets this goal." if passed else "Not yet. The idea still needs another try."
    if on_close:
        feedback = "That answers the close." if passed else "Not yet. The close still needs another try."
    if reveal and not passed:
        feedback = "The struggle window is over. A worked answer can move this on."
    recorded = record_result(
        db,
        tutor_session,
        score,
        passed,
        feedback,
        rubric_met=met,
        misconception=None if passed else note,
        hint_tier=hint_tier_for(failed_attempts(tutor_session, goal_id)),
    )
    advanced = False
    if advance_flag and (passed or reveal):
        moved = advance(db, tutor_session, allow_unpassed=reveal and not passed)
        advanced = bool(moved.get("ok"))
    return {**recorded, "advanced": advanced, "graded_by": "model"}

