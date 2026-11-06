"""Build the seven layer objects from a class and call the prompt engine.

The engine package itself does not import the database.
"""

from __future__ import annotations

from sqlalchemy.orm import object_session

from app.engine.assemble import assemble
from app.engine.choices import pacing_for, strictness_for
from app.engine.defaults import age_band_for
from app.engine.placeholders import memory_layer, metacognition_layer
from app.engine.types import (
    GoalPoint,
    HintLadder,
    Layer1Beat,
    Layer2Student,
    Layer3Tutor,
    Layer4Discourse,
    Layer5Affect,
    MisconceptionTrap,
    PromptBundle,
    RubricCriterion,
    WidgetChoice,
    WidgetGrade,
    WidgetTask,
)
from app.models import Session as TutorSession
from app.queries import (
    awaiting_tap_reply,
    choice_offer,
    choice_submitted,
    close_choice_widget,
    close_is_empty,
    close_question_texts,
    latest_result,
    locate_goal,
    ordered_goals,
)
from app.tutor_profile import load_profile

PASS_SCORE = 70


def course_scope_on(profile: object) -> bool:
    """Read the course guard. A missing attribute or a null older row counts as on."""
    value = getattr(profile, "stay_on_course", True)
    if value is None:
        return True
    return bool(value)


def _rows(beat: Beat) -> tuple[RubricCriterion, ...]:
    rows = []
    for row in beat.rubric or []:
        if isinstance(row, dict) and row.get("id"):
            rows.append(
                RubricCriterion(
                    id=str(row["id"]),
                    text=str(row.get("text") or ""),
                    weight=int(row.get("weight") or 0),
                )
            )
    return tuple(rows)


def _traps(beat: Beat) -> tuple[MisconceptionTrap, ...]:
    traps = []
    for trap in beat.misconception_map or []:
        if isinstance(trap, dict) and trap.get("trap"):
            traps.append(
                MisconceptionTrap(
                    id=str(trap.get("id") or "trap"),
                    trap=str(trap.get("trap") or ""),
                    note=str(trap.get("note") or ""),
                )
            )
    return tuple(traps)


def _ladder(beat: Beat) -> HintLadder:
    raw = beat.hint_ladder if isinstance(beat.hint_ladder, dict) else {}
    return HintLadder(
        nudge=str(raw.get("nudge") or ""),
        analogy=str(raw.get("analogy") or ""),
        scaffold=str(raw.get("scaffold") or ""),
    )


def _widget(
    tutor_session: TutorSession,
    *,
    include_grade: bool,
    quiz: dict | None = None,
) -> WidgetTask | None:
    if quiz is None:
        return None
    choices = tuple(
        WidgetChoice(
            id=str(choice.get("id")),
            text=str(choice.get("text") or ""),
            misconception=str(choice.get("misconception") or ""),
        )
        for choice in quiz.get("choices") or []
        if isinstance(choice, dict)
    )
    answer = quiz.get("answer")
    if isinstance(answer, list):
        shown: str | tuple[str, ...] = tuple(str(item) for item in answer)
    else:
        shown = str(answer or "")
    grade = None
    if include_grade:
        matches = [
            result
            for result in tutor_session.results
            if result.goal_id is None
            and isinstance(result.choice, dict)
            and result.choice.get("ids")
        ]
        result = max(matches, key=lambda item: item.seq) if matches else None
        if result is not None and isinstance(result.choice, dict):
            ids = tuple(str(item) for item in result.choice.get("ids") or [])
            grade = WidgetGrade(
                correct=bool(result.passed and result.score == 100),
                score=result.score,
                passed=result.passed,
                misconception=result.misconception,
                choice_ids=ids,
                explanation=str(result.choice.get("explanation") or ""),
            )
    return WidgetTask(
        type=str(quiz.get("type") or ""),
        prompt=str(quiz.get("prompt") or ""),
        choices=choices,
        answer=shown,
        explain=bool(quiz.get("explain")),
        grade=grade,
    )


def _zpd(tutor_session: TutorSession, goal_id) -> str:
    if tutor_session.status == "completed":
        return "on-level"
    result = latest_result(tutor_session, goal_id)
    if result is None:
        return "on-level"
    if not result.passed:
        return "support"
    if result.score >= 85:
        return "stretch"
    return "on-level"


def _criterion(goal) -> tuple[RubricCriterion, ...]:
    if goal is None:
        return ()
    text = (goal.success_criterion or "").strip()
    if not text:
        return ()
    return (RubricCriterion(id="criterion", text=text, weight=100),)


def _quest_objective(quest) -> str:
    goals = ordered_goals(quest)
    if goals and (goals[0].learning_goal or "").strip():
        return goals[0].learning_goal.strip()
    return (quest.title or "").strip()


def _failed(tutor_session: TutorSession, goal_id) -> int:
    return sum(
        1
        for result in tutor_session.results
        if result.goal_id == goal_id and not result.passed
    )


def _quest_walk(quest, *, reveal_close: bool) -> tuple[tuple[GoalPoint, ...], bool, str]:
    """Goals, then the close. Questions stay hidden until the close is on screen."""
    rows = ordered_goals(quest)
    points = tuple(
        GoalPoint(row.learning_goal or "", row.success_criterion or "")
        for row in rows
        if str(row.learning_goal or "").strip() or str(row.success_criterion or "").strip()
    )
    close = quest.close
    if close_is_empty(quest):
        return points, True, "Close: No questions."
    questions = close_question_texts(close)
    if close.answer_style == "essay":
        if not reveal_close:
            return points, False, "Close: Essay."
        listed = "; ".join(questions) if questions else "Ask for a short written answer."
        return points, False, f"Close: Essay. Question: {listed}"
    label = "Multi-choice" if close.choice_mode == "predefined" and _selection(close) == "multi" else "Choice"
    if not reveal_close:
        return points, False, f"Close: {label}."
    choices = []
    stored = close.items if isinstance(close.items, dict) else {}
    for item in stored.get("choices") or []:
        if isinstance(item, dict) and str(item.get("text") or "").strip():
            choices.append(str(item["text"]).strip())
    choice_line = f" Choices: {'; '.join(choices)}." if choices else ""
    question = questions[0] if questions else "Choose the best answer."
    return points, False, f"Close: {label}. Question: {question}{choice_line}"


def _selection(close) -> str | None:
    stored = close.items if isinstance(close.items, dict) else {}
    return stored.get("selection") if stored.get("selection") in {"single", "multi"} else None


def load_prompt(tutor_session: TutorSession, *, kickoff: bool = False) -> PromptBundle:
    quest = tutor_session.quest
    course = quest.course
    student = tutor_session.student
    goals = ordered_goals(quest)
    finished = tutor_session.status == "completed"
    on_close = bool(tutor_session.close_started) and not finished
    current = None if on_close or finished else locate_goal(quest, tutor_session.current_goal_id)
    if current is None and not on_close and not finished and goals:
        current = goals[0]
    quest_objective = _quest_objective(quest)
    active = current
    criterion = _criterion(active if active is not None else None)
    learning_goal = (active.learning_goal if active is not None else quest_objective).strip()
    offer = choice_offer(tutor_session) if on_close else None
    submitted = choice_submitted(tutor_session) if on_close else False
    answering_tap = awaiting_tap_reply(tutor_session) if on_close else False
    close_card = close_choice_widget(quest, tutor_session) if on_close else None
    include_widget = close_card is not None and (offer == "ask" or answering_tap)
    reveal_close = finished or on_close
    studio_goals, empty_close, close_line = _quest_walk(quest, reveal_close=reveal_close)
    held = False
    grade_writing = False
    withhold_answer = offer == "ask"
    if on_close:
        prompt = close_line or "Ask the closing question."
        role = "close"
        position = len(goals) + 1
        rubric = ()
    elif active is not None:
        prompt = (
            f"Teach this goal, then ask one question. Goal: {active.learning_goal}. "
            f"Finished work: {active.success_criterion}."
        )
        role = "goal"
        position = active.position
        rubric = criterion
    else:
        prompt = ""
        role = ""
        position = 0
        rubric = ()
    opening_idea = prompt if role == "goal" and position == 1 else ""
    beat_layer = Layer1Beat(
        course_title=course.title,
        unit_title="",
        continuity="",
        quest_code=quest.code,
        quest_title=quest.title,
        beat_role=role,
        beat_position=position,
        beat_count=len(goals) + 1,
        bloom_level="understand",
        cognitive_load="medium",
        prompt=prompt,
        rubric=rubric,
        misconceptions=(),
        hint_ladder=HintLadder(
            "What is the question actually asking?",
            "Picture the idea with one concrete object.",
            "Say the idea in one sentence.",
        ),
        widget=None
        if finished or not include_widget
        else _widget(tutor_session, include_grade=submitted or answering_tap, quiz=close_card),
        pass_score=PASS_SCORE,
        gate_cleared=False,
        finished=finished,
        quest_objective=quest_objective,
        beat_objectives=(),
        learning_goal=learning_goal,
        success_criterion=criterion,
        requires_teach_back=False,
        opening_idea=opening_idea,
        course_code=course.code,
        goals=studio_goals,
        empty_close=empty_close,
        close_line=close_line,
    )
    attempt_count = 0 if finished else _failed(tutor_session, None if on_close else (active.id if active else None))
    interests = tuple(str(item) for item in (student.interests or []) if str(item).strip())
    student_layer = Layer2Student(
        display_name=student.display_name,
        age_band=age_band_for(student.age),
        reading_level=student.reading_level,
        modality=student.modality,
        interests=interests,
        attempt_count=attempt_count,
        zpd=_zpd(tutor_session, None if on_close or finished or active is None else active.id),
    )
    profile = load_profile(object_session(tutor_session))
    level = min(5, max(1, int(profile.instructive or 3)))
    tutor_layer = Layer3Tutor(
        persona=profile.persona,
        lexicon=profile.lexicon,
        metaphors=profile.metaphors,
        sidekick=profile.sidekick,
    )
    discourse = Layer4Discourse(
        socratic_strictness=strictness_for(level),
        struggle_window=profile.struggle_window,
        anti_spoiler=bool(profile.anti_spoiler),
        pacing=pacing_for(level),
        instructive=level,
        one_question=bool(profile.one_question),
        use_interests=bool(profile.use_interests),
        stay_on_course=course_scope_on(profile),
    )
    affect = Layer5Affect(
        praise="growth-mindset-only" if profile.growth_praise else "result-or-effort"
    )
    return assemble(
        beat_layer,
        student_layer,
        tutor_layer,
        discourse,
        affect,
        metacognition_layer(),
        memory_layer(),
        kickoff=kickoff,
        hold_widget=held,
        grade_writing=grade_writing,
        widget_offer=offer,
        withhold_answer=withhold_answer,
    )
