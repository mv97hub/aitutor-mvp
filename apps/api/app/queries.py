from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.engine.assemble import struggle_limit
from app.models import Course, GoalResult, Message, Quest, Session as TutorSession
from app.tutor_profile import load_profile

KICKOFF_TEXT = "Hi! I'm ready to learn."


def load_course(db: Session, course_id: uuid.UUID) -> Course:
    course = db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.quests).selectinload(Quest.goals),
            selectinload(Course.quests).selectinload(Quest.close),
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
            selectinload(TutorSession.quest).selectinload(Quest.goals),
            selectinload(TutorSession.quest).selectinload(Quest.close),
            selectinload(TutorSession.quest).selectinload(Quest.course),
            selectinload(TutorSession.messages),
            selectinload(TutorSession.prompts),
            selectinload(TutorSession.results).selectinload(GoalResult.goal),
            selectinload(TutorSession.current_goal),
        )
    )
    if tutor_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return tutor_session


def ordered_goals(quest: Quest) -> list:
    return sorted(quest.goals, key=lambda goal: goal.position)


def locate_goal(quest: Quest, goal_id: uuid.UUID | None):
    if goal_id is None:
        return None
    for goal in ordered_goals(quest):
        if goal.id == goal_id:
            return goal
    return None


def latest_result(tutor_session: TutorSession, goal_id: uuid.UUID | None) -> GoalResult | None:
    found = None
    for result in tutor_session.results:
        if result.goal_id == goal_id:
            found = result
    return found


def _message_text(message: Message) -> str:
    return (message.content or "").strip()


def _failed_attempts(tutor_session: TutorSession, goal_id: uuid.UUID | None) -> int:
    return sum(
        1
        for result in tutor_session.results
        if result.goal_id == goal_id and not result.passed
    )


def _close_parts(close) -> tuple[list, list, str | None]:
    stored = close.items if close is not None else None
    if isinstance(stored, dict):
        choices = stored.get("choices") if isinstance(stored.get("choices"), list) else []
        questions = stored.get("questions") if isinstance(stored.get("questions"), list) else []
        selection = stored.get("selection") if stored.get("selection") in {"single", "multi"} else None
        return choices, questions, selection
    if isinstance(stored, list):
        return list(stored), [], None
    return [], [], None


def close_question_texts(close) -> list[str]:
    _choices, questions, _selection = _close_parts(close)
    texts = []
    for item in questions:
        if isinstance(item, str) and item.strip():
            texts.append(item.strip())
        elif isinstance(item, dict) and str(item.get("text") or "").strip():
            texts.append(str(item["text"]).strip())
    return texts


def close_is_empty(quest: Quest) -> bool:
    """An essay with no questions, or no close at all, ends the quest."""
    close = quest.close
    if close is None:
        return True
    if close.answer_style == "essay" and not close_question_texts(close):
        return True
    return False


def close_choice_widget(quest: Quest, tutor_session: TutorSession) -> dict | None:
    """A predefined choice card, and only after the close has started."""
    if not tutor_session.close_started:
        return None
    close = quest.close
    if close is None or close.answer_style == "essay" or close.choice_mode != "predefined":
        return None
    choices, questions, selection = _close_parts(close)
    built = []
    answers = []
    for index, item in enumerate(choices, start=1):
        if isinstance(item, str):
            text = item.strip()
            correct = False
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            correct = item.get("correct") is True
        else:
            continue
        if not text:
            continue
        choice_id = f"c{index}"
        built.append(
            {
                "id": choice_id,
                "text": text,
                "misconception": "" if correct else "That choice answers a different question.",
            }
        )
        if correct:
            answers.append(choice_id)
    if len(built) < 2:
        return None
    if not answers:
        answers = [built[0]["id"]]
    kind = "multi" if selection == "multi" else "single"
    prompt = close_question_texts(close)
    return {
        "type": kind,
        "prompt": prompt[0] if prompt else "Choose the best answer.",
        "choices": built,
        "answer": answers if kind == "multi" else answers[0],
        "explain": False,
        "misconception": "Stay on the question this quest asked.",
    }


def _close_messages(tutor_session: TutorSession) -> list[Message]:
    """Messages since the close started, after the last goal result."""
    latest_goal = None
    for result in tutor_session.results:
        if result.goal_id is not None:
            latest_goal = result
    rows = []
    for message in tutor_session.messages:
        if latest_goal is not None and latest_goal.created_at is not None:
            if message.created_at is None or message.created_at <= latest_goal.created_at:
                continue
        rows.append(message)
    return rows


def choice_submitted(tutor_session: TutorSession) -> bool:
    return latest_result(tutor_session, None) is not None


def _window_closed_on(tutor_session: TutorSession) -> bool:
    if latest_result(tutor_session, None) is None:
        return False
    window = load_profile(object_session(tutor_session)).struggle_window or "standard"
    return _failed_attempts(tutor_session, None) >= struggle_limit(window)


def choice_offer(tutor_session: TutorSession) -> str | None:
    if close_choice_widget(tutor_session.quest, tutor_session) is None:
        return None
    if _window_closed_on(tutor_session):
        return None
    return "ask"


def _invited(tutor_session: TutorSession) -> bool:
    latest = latest_result(tutor_session, None)
    for message in _close_messages(tutor_session):
        if latest is not None and latest.created_at is not None:
            if message.created_at is None or message.created_at <= latest.created_at:
                continue
        if message.role == "assistant" and _message_text(message):
            return True
    return False


def choice_widget_visible(tutor_session: TutorSession) -> bool:
    if choice_offer(tutor_session) is None:
        return False
    return _invited(tutor_session)


def awaiting_tap_reply(tutor_session: TutorSession) -> bool:
    if not choice_submitted(tutor_session):
        return False
    latest = latest_result(tutor_session, None)
    if latest is None or latest.passed:
        return False
    for message in _close_messages(tutor_session):
        if latest.created_at is not None and (message.created_at is None or message.created_at <= latest.created_at):
            continue
        if message.role == "user" and _message_text(message) and _message_text(message) != KICKOFF_TEXT:
            return True
    return False


def replied_after_teaching(tutor_session: TutorSession) -> bool:
    for message in _close_messages(tutor_session):
        if message.role == "user" and _message_text(message) and _message_text(message) != KICKOFF_TEXT:
            return True
    return False


def next_position(values: list[int]) -> int:
    return (max(values) if values else 0) + 1


def quest_in_use(db: Session, quest_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id == quest_id)
        )
    )
