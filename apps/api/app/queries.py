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


def _spoken(tutor_session: TutorSession) -> tuple[int, int]:
    users = 0
    assistants = 0
    for message in tutor_session.messages:
        text = (message.content or "").strip()
        if not text:
            continue
        if message.role == "user":
            users += 1
        elif message.role == "assistant":
            assistants += 1
    return users, assistants


def opening_exchange_done(tutor_session: TutorSession) -> bool:
    """Kickoff plus the student's reply, and the tutor's answer to that reply."""
    users, assistants = _spoken(tutor_session)
    return users >= 2 and assistants >= 2


def choice_widget_visible(tutor_session: TutorSession, beat: Beat) -> bool:
    """The choice box waits until Try, after Engage and the opening exchange.

    A Show quiz is the last check. It is not the first thing on screen.
    """
    quiz = beat.widget if isinstance(beat.widget, dict) else None
    if not quiz or beat.role == "engage":
        return False
    result = latest_result(tutor_session, beat.id)
    if result is not None and isinstance(result.choice, dict) and result.choice.get("ids"):
        return True
    beats = ordered_beats(tutor_session.quest)
    if beats and beat.id != beats[0].id:
        return beat.role in {"try", "show"}
    if beat.role not in {"try", "show"}:
        return False
    return opening_exchange_done(tutor_session)


def next_position(values: list[int]) -> int:
    return (max(values) if values else 0) + 1


def quest_in_use(db: Session, quest_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id == quest_id)
        )
    )
