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
    if goal_id is None:
        return close_failed_attempts(tutor_session)
    return sum(
        1
        for result in tutor_session.results
        if result.goal_id == goal_id and not result.passed
    )


def _stored_close(close):
    """The JSON a close row or a close dict keeps its questions in."""
    if close is None:
        return None
    if isinstance(close, dict):
        items = close.get("items")
        questions = close.get("questions") if isinstance(close.get("questions"), list) else []
        selection = close.get("selection") if close.get("selection") in {"single", "multi"} else None
        if isinstance(items, dict):
            stored = dict(items)
            if questions and not stored.get("questions"):
                stored["questions"] = questions
            if selection and stored.get("selection") not in {"single", "multi"}:
                stored["selection"] = selection
            return stored
        if questions or selection:
            packed = {"choices": list(items) if isinstance(items, list) else [], "questions": questions}
            if selection:
                packed["selection"] = selection
            return packed
        if isinstance(items, list):
            return items
        return {"choices": [], "questions": []}
    return getattr(close, "items", None)


def _clean_choice_rows(raw) -> list[dict]:
    rows = []
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
            correct = False
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            correct = item.get("correct") is True
        else:
            continue
        if text:
            rows.append({"text": text, "correct": correct})
    return rows


def _close_parts(close) -> tuple[list, list, str | None]:
    stored = _stored_close(close)
    if isinstance(stored, dict):
        choices = stored.get("choices") if isinstance(stored.get("choices"), list) else []
        questions = stored.get("questions") if isinstance(stored.get("questions"), list) else []
        selection = stored.get("selection") if stored.get("selection") in {"single", "multi"} else None
        return choices, questions, selection
    if isinstance(stored, list):
        return list(stored), [], None
    return [], [], None


def _one_correct(choices: list[dict]) -> list[dict]:
    """A multiple-choice question has one right option. The first marked one stays."""
    chosen = False
    rows = []
    for choice in choices:
        correct = choice["correct"] is True and not chosen
        if correct:
            chosen = True
        rows.append({"text": choice["text"], "correct": correct})
    if rows and not chosen:
        rows[0] = {"text": rows[0]["text"], "correct": True}
    return rows


def _canonical_question(text: str, kind: str | None, choices: list[dict]) -> dict:
    """single is a typed answer. multiple is one pick from the stored options.

    An older essay, or a single with no choices, is typed. An older single or
    multi that already has choices is multiple choice, and only the first
    correct option stays correct.
    """
    if kind == "essay" or not choices:
        return {"text": text, "kind": "single", "choices": []}
    return {"text": text, "kind": "multiple", "choices": _one_correct(choices)}


def close_questions(close) -> list[dict]:
    """Each question is text, kind, and its own choices.

    An older close kept one shared choice list and questions that were only
    text. One question keeps that list. Several questions stay separate and
    do not inherit each other's answers.
    """
    stored = _stored_close(close)
    if isinstance(stored, dict):
        shared = _clean_choice_rows(stored.get("choices"))
        raw_questions = stored.get("questions") if isinstance(stored.get("questions"), list) else []
    elif isinstance(stored, list):
        shared = _clean_choice_rows(stored)
        raw_questions = []
    else:
        return []
    built = []
    for item in raw_questions:
        if isinstance(item, str):
            text = item.strip()
            choices: list[dict] = []
            kind = None
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            choices = _clean_choice_rows(item.get("choices"))
            kind = item.get("kind") if item.get("kind") in {"essay", "single", "multi", "multiple"} else None
        else:
            continue
        if not text:
            continue
        built.append(_canonical_question(text, kind, choices))
    if len(built) == 1 and not built[0]["choices"] and shared:
        built[0] = _canonical_question(built[0]["text"], "multiple", shared)
    return built


def close_question_texts(close) -> list[str]:
    return [question["text"] for question in close_questions(close)]


def close_api_parts(close) -> tuple[list, list, str | None]:
    """Items stay empty once each question carries its own choices."""
    items, _raw_questions, _selection = _close_parts(close)
    rich = close_questions(close)
    if not rich:
        return _clean_choice_rows(items), [], None
    if any(question["choices"] for question in rich) or len(rich) > 1:
        items = []
    else:
        items = _clean_choice_rows(items)
    return items, rich, None


def close_question_index_of(tutor_session: TutorSession) -> int:
    return int(getattr(tutor_session, "close_question_index", 0) or 0)


def result_question_index(result) -> int | None:
    choice = result.choice if result is not None else None
    index = choice.get("question_index") if isinstance(choice, dict) else None
    if isinstance(index, bool) or not isinstance(index, int):
        return None
    return index


def latest_close_result(tutor_session: TutorSession):
    """The latest result for the question on screen, not an earlier one."""
    index = close_question_index_of(tutor_session)
    found = None
    for result in tutor_session.results:
        if result.goal_id is not None or result_question_index(result) != index:
            continue
        found = result
    return found


def close_failed_attempts(tutor_session: TutorSession) -> int:
    index = close_question_index_of(tutor_session)
    return sum(
        1
        for result in tutor_session.results
        if result.goal_id is None and not result.passed and result_question_index(result) == index
    )


def close_running_score(tutor_session: TutorSession, *, index: int, passed: bool) -> int:
    """How many close questions have been answered correctly so far."""
    seen: set[int] = set()
    for result in tutor_session.results:
        if result.goal_id is not None or not result.passed:
            continue
        found = result_question_index(result)
        if found is not None:
            seen.add(found)
    if passed:
        seen.add(index)
    return len(seen)


def active_close_question(close, tutor_session: TutorSession) -> dict | None:
    questions = close_questions(close)
    index = close_question_index_of(tutor_session)
    if questions:
        if index < 0 or index >= len(questions):
            return None
        return questions[index]
    if index != 0:
        return None
    choices, _questions, _selection = _close_parts(close)
    shared = _clean_choice_rows(choices)
    if len(shared) < 2:
        return None
    return {"text": "Choose the best answer.", "kind": "multiple", "choices": _one_correct(shared)}


def close_is_empty(quest: Quest) -> bool:
    """An essay with no questions, or no close at all, ends the quest."""
    close = quest.close
    if close is None:
        return True
    if close_questions(close):
        return False
    if close.answer_style == "essay":
        return True
    return False


def close_choice_widget(quest: Quest, tutor_session: TutorSession) -> dict | None:
    """The card for the active question, and only after the close has started."""
    if not tutor_session.close_started:
        return None
    close = quest.close
    if close is None:
        return None
    question = active_close_question(close, tutor_session)
    if question is None or question["kind"] != "multiple":
        return None
    built = []
    answers = []
    for index, item in enumerate(question["choices"], start=1):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        correct = item.get("correct") is True
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
    return {
        "type": "single",
        "prompt": question["text"] or "Choose the best answer.",
        "choices": built,
        "answer": answers[0],
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
    return latest_close_result(tutor_session) is not None


def _window_closed_on(tutor_session: TutorSession) -> bool:
    if latest_close_result(tutor_session) is None:
        return False
    window = load_profile(object_session(tutor_session)).struggle_window or "standard"
    return close_failed_attempts(tutor_session) >= struggle_limit(window)


def choice_offer(tutor_session: TutorSession) -> str | None:
    if close_choice_widget(tutor_session.quest, tutor_session) is None:
        return None
    latest = latest_close_result(tutor_session)
    if latest is not None and latest.passed:
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
    latest = latest_close_result(tutor_session)
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
