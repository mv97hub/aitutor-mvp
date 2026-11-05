from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.engine.assemble import struggle_limit
from app.models import Beat, BeatResult, Course, Message, Quest, Session as TutorSession
from app.tutor_profile import load_profile

KICKOFF_TEXT = "Hi! I'm ready to learn."


def load_course(db: Session, course_id: uuid.UUID) -> Course:
    course = db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.quests).selectinload(Quest.goals),
            selectinload(Course.quests).selectinload(Quest.close),
            selectinload(Course.quests).selectinload(Quest.beats),
        )
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
            selectinload(Quest.goals),
            selectinload(Quest.close),
            selectinload(Quest.course),
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
            selectinload(TutorSession.quest).selectinload(Quest.beats),
            selectinload(TutorSession.quest).selectinload(Quest.goals),
            selectinload(TutorSession.quest).selectinload(Quest.close),
            selectinload(TutorSession.quest).selectinload(Quest.course),
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


def _message_text(message: Message) -> str:
    return (message.content or "").strip()


def _own_words(message: Message) -> bool:
    text = _message_text(message)
    return message.role == "user" and bool(text) and text != KICKOFF_TEXT


def _failed_attempts(tutor_session: TutorSession, beat_id: uuid.UUID) -> int:
    return sum(
        1
        for result in tutor_session.results
        if result.beat_id == beat_id and not result.passed
    )


def _move_messages(tutor_session: TutorSession, beat: Beat) -> list[Message]:
    """Talk that belongs to this move, after the previous move's result."""
    beats = ordered_beats(tutor_session.quest)
    index = next((i for i, item in enumerate(beats) if item.id == beat.id), None)
    messages = [message for message in tutor_session.messages if _message_text(message)]
    if index is None:
        return []
    if index == 0:
        return messages
    previous = latest_result(tutor_session, beats[index - 1].id)
    if previous is None or previous.created_at is None:
        return []
    return [
        message
        for message in messages
        if message.created_at is not None and message.created_at > previous.created_at
    ]


def _latest_choice(tutor_session: TutorSession, beat: Beat) -> BeatResult | None:
    matches = [
        result
        for result in tutor_session.results
        if result.beat_id == beat.id
        and isinstance(result.choice, dict)
        and result.choice.get("ids")
    ]
    if not matches:
        return None
    return max(matches, key=lambda result: result.seq)


def choice_submitted(tutor_session: TutorSession, beat: Beat) -> bool:
    return _latest_choice(tutor_session, beat) is not None


def _offer_span(tutor_session: TutorSession, beat: Beat) -> tuple[list[Message], bool]:
    """Messages since the last submitted choice.

    The submitted choice is saved before the tutor replies, so a user message
    that arrives before that reply is the choice itself, not a new explanation.
    """
    messages = _move_messages(tutor_session, beat)
    latest = _latest_choice(tutor_session, beat)
    if latest is None or latest.created_at is None:
        return messages, False
    span = [
        message
        for message in messages
        if message.created_at is not None and message.created_at > latest.created_at
    ]
    cleaned: list[Message] = []
    seen_tutor = False
    for message in span:
        if message.role == "assistant":
            seen_tutor = True
            cleaned.append(message)
        elif message.role == "user" and not seen_tutor:
            continue
        else:
            cleaned.append(message)
    return cleaned, True


def _check_ready(span: list[Message]) -> bool:
    """True once a tutor reply follows the student's own words.

    The first tutor message is not enough, and neither is the move role.
    """
    seen_tutor = False
    seen_words = False
    ready = False
    for message in span:
        if message.role == "assistant":
            if seen_words:
                ready = True
            seen_tutor = True
        elif _own_words(message) and seen_tutor:
            seen_words = True
            ready = False
    return ready


def replied_after_teaching(tutor_session: TutorSession, beat: Beat) -> bool:
    """The idea has been said, and the student has answered in their own words."""
    span, _submitted = _offer_span(tutor_session, beat)
    seen_tutor = False
    for message in span:
        if message.role == "assistant":
            seen_tutor = True
        elif _own_words(message) and seen_tutor:
            return True
    return False


def awaiting_tap_reply(tutor_session: TutorSession, beat: Beat) -> bool:
    """True after a choice is stored and before the tutor has answered it."""
    latest = _latest_choice(tutor_session, beat)
    if latest is None or latest.created_at is None:
        return False
    for message in _move_messages(tutor_session, beat):
        if message.created_at is None or message.created_at <= latest.created_at:
            continue
        if message.role == "assistant":
            return False
    return True


def choice_offer(tutor_session: TutorSession, beat: Beat) -> str | None:
    """Why the live choices are on screen: "check", "unstick", or nothing.

    Check: the idea was explained and the student answered in their own words.
    Unstick: they are stuck and the struggle window is about to open, so the
    choices are the structured try before the answer. Opening, Engage, and
    Name stay talk. A stored Try is not enough, and the first tutor message
    is not enough.
    """
    quiz = beat.widget if isinstance(beat.widget, dict) else None
    if not quiz or beat.role not in {"try", "show"}:
        return None
    if tutor_session.current_beat_id != beat.id:
        return None
    span, submitted = _offer_span(tutor_session, beat)
    if not _check_ready(span):
        return None
    failed = _failed_attempts(tutor_session, beat.id)
    window = load_profile(object_session(tutor_session)).struggle_window or "standard"
    limit = struggle_limit(window)
    if not submitted:
        if failed >= max(limit - 1, 1):
            return "unstick"
        return "check"
    if failed >= limit:
        return None
    return "check"


def choice_widget_visible(tutor_session: TutorSession, beat: Beat) -> bool:
    """The live choice message. It is gone once that offer has been answered."""
    return choice_offer(tutor_session, beat) is not None


def next_position(values: list[int]) -> int:
    return (max(values) if values else 0) + 1


def quest_in_use(db: Session, quest_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id == quest_id)
        )
    )
