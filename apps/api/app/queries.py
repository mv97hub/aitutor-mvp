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


def _placeholder_widget(widget: dict) -> bool:
    choices = widget.get("choices") or []
    return any(
        isinstance(choice, dict) and choice.get("text") == "The choice that matches the quest idea."
        for choice in choices
    )


def _widget_from_close(close) -> dict | None:
    items = close.items if isinstance(close.items, list) else []
    choices = []
    answers = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        choice_id = f"c{index}"
        choices.append(
            {
                "id": choice_id,
                "text": text,
                "misconception": "" if item.get("correct") else "That choice answers a different question.",
            }
        )
        if item.get("correct"):
            answers.append(choice_id)
    if len(choices) < 2:
        return None
    if not answers:
        answers = [choices[0]["id"]]
    kind = "multi" if close.kind == "multi" else "single"
    return {
        "type": kind,
        "prompt": (close.question or "").strip() or "Choose the best answer.",
        "choices": choices,
        "answer": answers if kind == "multi" else answers[0],
        "explain": False,
        "misconception": "Stay on the question this quest asked.",
    }


def close_choice_widget(quest, beat: Beat) -> dict | None:
    """The quest close, when it is a single or multi-choice card.

    Engage, Name, and Try stay talk. A placeholder Try widget is not a card.
    Essay and empty closes are typed, or they end the quest.
    """
    if beat is None or beat.role != "show":
        return None
    close = getattr(quest, "close", None)
    if close is not None and close.kind in {"none", "essay"}:
        return None
    widget = beat.widget if isinstance(beat.widget, dict) else None
    if widget and (_placeholder_widget(widget) or widget.get("type") not in {"single", "multi", "flaw"}):
        widget = None
    if widget is not None:
        return widget
    if close is not None and close.kind in {"single", "multi"}:
        return _widget_from_close(close)
    return None


def _window_closed_on(tutor_session: TutorSession, beat: Beat) -> bool:
    if _latest_choice(tutor_session, beat) is None:
        return False
    window = load_profile(object_session(tutor_session)).struggle_window or "standard"
    return _failed_attempts(tutor_session, beat.id) >= struggle_limit(window)


def choice_offer(tutor_session: TutorSession, beat: Beat) -> str | None:
    """"ask" when this turn's prompt should know the close card is on screen.

    The card is the quest close, and only the close. After a wrong choice the
    window can replace another try with the worked answer.
    """
    if close_choice_widget(tutor_session.quest, beat) is None:
        return None
    if tutor_session.current_beat_id != beat.id:
        return None
    if _window_closed_on(tutor_session, beat):
        return None
    return "ask"


def _invited(tutor_session: TutorSession, beat: Beat) -> bool:
    """The reply that asks for the pick is already in the chat."""
    latest = _latest_choice(tutor_session, beat)
    for message in _move_messages(tutor_session, beat):
        if latest is not None and latest.created_at is not None:
            if message.created_at is None or message.created_at <= latest.created_at:
                continue
        if message.role == "assistant" and _message_text(message):
            return True
    return False


def choice_widget_visible(tutor_session: TutorSession, beat: Beat) -> bool:
    """The card hangs on the inviting reply, not on a teaching turn."""
    if choice_offer(tutor_session, beat) is None:
        return False
    return _invited(tutor_session, beat)


def next_position(values: list[int]) -> int:
    return (max(values) if values else 0) + 1


def quest_in_use(db: Session, quest_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id == quest_id)
        )
    )
