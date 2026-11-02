from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.engine.assemble import hint_tier_for
from app.engine.defaults import age_band_for, profile_for_age
from app.models import Beat, BeatResult, Course, Message, ModelPrompt, Quest, Session as TutorSession, Student
from app.prompt_loader import PASS_SCORE
from app.queries import latest_result, locate_beat, next_position, ordered_beats
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


def age_block_reason(student: Student, course: Course) -> str | None:
    band = age_band_for(student.age)
    if band == course.age_band:
        return None
    who = (
        f"{student.display_name} is {student.age}"
        if student.age is not None
        else f"{student.display_name} has no age on file"
    )
    return f"This course is for ages {course.age_band}. {who}."


def open_session(db: Session, student_id: uuid.UUID, quest_id: uuid.UUID, fresh: bool) -> TutorSession:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    from app.queries import load_quest

    quest = load_quest(db, quest_id)
    reason = age_block_reason(student, quest.unit.course)
    if reason is not None:
        raise HTTPException(status_code=400, detail=reason)
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
    beats = ordered_beats(quest)
    if len(beats) != 4:
        raise HTTPException(status_code=400, detail="This quest does not have four beats.")
    tutor_session = TutorSession(
        student_id=student.id,
        quest_id=quest.id,
        current_beat_id=beats[0].id,
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


def failed_attempts(tutor_session: TutorSession, beat_id: uuid.UUID) -> int:
    return sum(1 for result in tutor_session.results if result.beat_id == beat_id and not result.passed)


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
    beat = locate_beat(tutor_session.quest, tutor_session.current_beat_id)
    if beat is None:
        return {"ok": False, "reason": "This quest is finished, so there is nothing to score."}
    seq = db.scalar(
        select(func.max(BeatResult.seq)).where(BeatResult.session_id == tutor_session.id)
    )
    result = BeatResult(
        session_id=tutor_session.id,
        beat_id=beat.id,
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
        "beat_id": str(beat.id),
        "role": beat.role,
        "score": score,
        "passed": passed,
        "feedback": result.feedback,
    }


def advance(db: Session, tutor_session: TutorSession) -> dict:
    beat = locate_beat(tutor_session.quest, tutor_session.current_beat_id)
    if tutor_session.status == "completed" or beat is None:
        return {"ok": False, "reason": "This quest is already finished."}
    result = latest_result(tutor_session, beat.id)
    if result is None or not result.passed:
        return {"ok": False, "reason": "This beat needs a passing result before moving on."}
    beats = ordered_beats(tutor_session.quest)
    index = next(i for i, item in enumerate(beats) if item.id == beat.id)
    tutor_session.updated_at = now()
    if index + 1 >= len(beats):
        tutor_session.current_beat_id = None
        tutor_session.status = "completed"
        db.flush()
        return {"ok": True, "completed": True, "current_beat": None}
    nxt = beats[index + 1]
    tutor_session.current_beat_id = nxt.id
    db.flush()
    return {
        "ok": True,
        "completed": False,
        "from_role": beat.role,
        "current_beat": {"role": nxt.role, "position": nxt.position},
    }


def beat_state(
    beat: Beat,
    current_id: uuid.UUID | None,
    result: BeatResult | None,
    seen_current: bool,
    quest_complete: bool,
) -> str:
    if quest_complete:
        if result is not None and result.passed:
            return "passed"
        if result is not None:
            return "failed"
        return "done"
    if beat.id == current_id:
        return "current"
    if seen_current:
        return "upcoming"
    if result is not None and result.passed:
        return "passed"
    if result is not None:
        return "failed"
    return "done"


def grade_widget(
    db: Session,
    tutor_session: TutorSession,
    choice: str | list[str],
    explanation: str,
) -> dict:
    beat = locate_beat(tutor_session.quest, tutor_session.current_beat_id)
    if beat is None:
        return {"ok": False, "reason": "This quest is finished, so there is nothing to score."}
    quiz = beat.widget if isinstance(beat.widget, dict) else None
    if quiz is None:
        return {"ok": False, "reason": "This beat is a typed reply, not a choice widget."}
    ids = choice_ids(choice)
    if not ids:
        return {"ok": False, "reason": "Choose an answer before sending."}
    graded = grade_choice(quiz, ids if quiz.get("type") == "order" else ids[0])
    passed = graded["score"] >= PASS_SCORE
    tier = hint_tier_for(failed_attempts(tutor_session, beat.id))
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
        "hint_text": hint_text(beat.hint_ladder, tier),
    }


def _weights(beat: Beat) -> dict[str, int]:
    weights: dict[str, int] = {}
    for row in beat.rubric or []:
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
    beat = locate_beat(tutor_session.quest, tutor_session.current_beat_id)
    if beat is None:
        return {"ok": False, "reason": "This quest is finished.", "advanced": False}
    weights = _weights(beat)
    met = [row_id for row_id in rubric_met if row_id in weights]
    latest = latest_result(tutor_session, beat.id)
    quiz = beat.widget if isinstance(beat.widget, dict) else None
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
            hint_tier=hint_tier_for(failed_attempts(tutor_session, beat.id)),
        )
        return {**recorded, "advanced": False, "graded_by": "widget"}
    total = sum(weights.values()) or 0
    earned = sum(weights[row_id] for row_id in met)
    score = round(100 * earned / total) if total else 0
    passed = score >= PASS_SCORE
    tier = hint_tier_for(failed_attempts(tutor_session, beat.id))
    feedback = "That meets this beat." if passed else "Not yet. Use the hint and try again."
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


def blank_beats() -> list[dict]:
    roles = (
        ("mystery_hook", "understand", "Ask one question that opens the mystery of this quest."),
        ("interactive_toy", "apply", "Which choice matches the idea this quest is building?"),
        ("diagnostic_gate", "analyze", "Explain the idea in two parts the rubric can score."),
        ("feynman_flip", "evaluate", "Teach the sidekick who states the misconception."),
    )
    beats = []
    for role, bloom, prompt in roles:
        widget = None
        if role == "interactive_toy":
            widget = {
                "type": "single",
                "prompt": prompt,
                "choices": [
                    {"id": "match", "text": "The choice that matches the quest idea.", "misconception": ""},
                    {
                        "id": "trap",
                        "text": "A nearby idea that does not answer this question.",
                        "misconception": "That choice belongs to a different question.",
                    },
                ],
                "answer": "match",
                "explain": False,
                "misconception": "Stay on the question this quest asked.",
            }
        beats.append(
            {
                "role": role,
                "bloom_level": bloom,
                "cognitive_load": "medium",
                "prompt": prompt,
                "rubric": [
                    {"id": "part-a", "text": "Names the first part of the idea.", "weight": 50},
                    {"id": "part-b", "text": "Names the second part of the idea.", "weight": 50},
                ]
                if role != "interactive_toy"
                else [{"id": "choice", "text": "Selects the choice that matches the quest idea.", "weight": 100}],
                "misconception_map": [
                    {
                        "id": "nearby",
                        "trap": "A nearby idea answers this question.",
                        "note": "Stay on the idea named in the quest.",
                    }
                ],
                "hint_ladder": {
                    "nudge": "What is the question actually asking?",
                    "analogy": "Picture the idea with one concrete object.",
                    "scaffold": "The first part is ____. The second part is ____.",
                },
                "widget": widget,
            }
        )
    return beats
