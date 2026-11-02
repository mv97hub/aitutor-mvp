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


def next_position(values: list[int]) -> int:
    return (max(values) if values else 0) + 1


def quest_in_use(db: Session, quest_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id == quest_id)
        )
    )
