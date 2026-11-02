from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Beat, BeatResult, Course, Quest, Session as TutorSession, Unit


def load_course(db: Session, course_id: uuid.UUID) -> Course:
    course = db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(selectinload(Course.units).selectinload(Unit.quests))
    )
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def load_quest(db: Session, quest_id: uuid.UUID) -> Quest:
    quest = db.scalar(
        select(Quest)
        .where(Quest.id == quest_id)
        .options(
            selectinload(Quest.beats),
            selectinload(Quest.unit).selectinload(Unit.course),
        )
    )
    if quest is None:
        raise HTTPException(status_code=404, detail="Quest not found")
    return quest


def load_session(db: Session, session_id: uuid.UUID) -> TutorSession:
    tutor_session = db.scalar(
        select(TutorSession)
        .where(TutorSession.id == session_id)
        .options(
            selectinload(TutorSession.student),
            selectinload(TutorSession.quest)
            .selectinload(Quest.beats),
            selectinload(TutorSession.quest)
            .selectinload(Quest.unit)
            .selectinload(Unit.course),
            selectinload(TutorSession.messages),
            selectinload(TutorSession.prompts),
            selectinload(TutorSession.results).selectinload(BeatResult.beat).selectinload(Beat.quest),
        )
    )
    if tutor_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return tutor_session


def ordered_beats(quest: Quest) -> list[Beat]:
    return sorted(quest.beats, key=lambda beat: beat.position)


def locate_beat(quest: Quest, beat_id: uuid.UUID | None) -> Beat | None:
    if beat_id is None:
        return None
    for beat in ordered_beats(quest):
        if beat.id == beat_id:
            return beat
    return None


def latest_result(tutor_session: TutorSession, beat_id: uuid.UUID) -> BeatResult | None:
    matches = [result for result in tutor_session.results if result.beat_id == beat_id]
    if not matches:
        return None
    return max(matches, key=lambda result: result.seq)


def tutor_has_spoken_for_move(tutor_session: TutorSession, beat: Beat) -> bool:
    """True after a tutor reply that belongs to this move.

    The reply that finishes the previous move is stored after that move's result,
    so it does not count. The next student message, then a tutor reply, does.
    On the first move, the opening lesson is that reply.
    """
    beats = ordered_beats(tutor_session.quest)
    index = next((i for i, item in enumerate(beats) if item.id == beat.id), None)
    if index is None:
        return False
    if index == 0:
        return any(
            message.role == "assistant" and (message.content or "").strip()
            for message in tutor_session.messages
        )
    previous = latest_result(tutor_session, beats[index - 1].id)
    if previous is None or previous.created_at is None:
        return False
    heard_student = False
    for message in tutor_session.messages:
        text = (message.content or "").strip()
        if not text or message.created_at is None or message.created_at <= previous.created_at:
            continue
        if message.role == "user":
            heard_student = True
        elif message.role == "assistant" and heard_student:
            return True
    return False


def choice_widget_visible(tutor_session: TutorSession, beat: Beat) -> bool:
    """The choice box is the check. It waits until Try or Show has been taught."""
    quiz = beat.widget if isinstance(beat.widget, dict) else None
    if not quiz or beat.role not in {"try", "show"}:
        return False
    result = latest_result(tutor_session, beat.id)
    if result is not None and isinstance(result.choice, dict) and result.choice.get("ids"):
        return True
    return tutor_has_spoken_for_move(tutor_session, beat)


def next_position(values: list[int]) -> int:
    return (max(values) if values else 0) + 1


def quest_in_use(db: Session, quest_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id == quest_id)
        )
    )
