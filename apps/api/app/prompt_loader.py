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
    active_close_question,
    awaiting_tap_reply,
    choice_offer,
    choice_submitted,
    close_choice_widget,
    close_is_empty,
    close_question_index_of,
    close_questions,
    latest_close_result,
    latest_result,
    locate_goal,
    ordered_goals,
    result_question_index,
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
        index = close_question_index_of(tutor_session)
        matches = [
            result
            for result in tutor_session.results
            if result.goal_id is None
            and isinstance(result.choice, dict)
            and result.choice.get("ids")
            and result_question_index(result) == index
        ]
        result = max(matches, key=lambda item: item.seq) if matches else None
        if result is not None and isinstance(result.choice, dict):
            ids = tuple(str(item) for item in result.choice.get("ids") or [])
            grade = WidgetGrade(
                correct=bool(result.passed),
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


def _quest_walk(quest, *, reveal_close: bool, active: dict | None = None) -> tuple[tuple[GoalPoint, ...], bool, str]:
    """Goals, then the close. The prompt names only the question on screen."""
    rows = ordered_goals(quest)
    points = tuple(
        GoalPoint(row.learning_goal or "", row.success_criterion or "")
        for row in rows
        if str(row.learning_goal or "").strip() or str(row.success_criterion or "").strip()
    )
    close = quest.close
    if close_is_empty(quest):
        return points, True, "Close: No questions."
    questions = close_questions(close)
    if questions and all(question["kind"] == "single" for question in questions):
        label = "Single choice"
    elif questions and all(question["kind"] == "multiple" for question in questions):
        label = "Multiple choice"
    elif questions:
        label = "Mixed"
    elif close is not None and close.answer_style == "essay":
        label = "Single choice"
    else:
        label = "Multiple choice"
    if not reveal_close:
        return points, False, f"Close: {label}."
    target = active or (questions[0] if questions else None)
    if target is None:
        return points, False, f"Close: {label}."
    if target["kind"] == "single":
        return points, False, f"Close: Single choice. Question: {target['text']}. The kid types the answer."
    return points, False, f"Close: Multiple choice. Card question: {target['text']}. Do not read this question aloud."


def _goal_standard(goals) -> str:
    parts = []
    for goal in goals:
        if str(goal.learning_goal or "").strip():
            parts.append(str(goal.learning_goal).strip())
        if str(goal.success_criterion or "").strip():
            parts.append(str(goal.success_criterion).strip())
    return " ".join(parts) or "the idea this quest taught"


def _picked_label(question: dict, result) -> str:
    choice = result.choice if result is not None and isinstance(result.choice, dict) else {}
    ids = {str(item) for item in choice.get("ids") or []}
    labels = [
        str(item.get("text") or "")
        for index, item in enumerate(question.get("choices") or [], start=1)
        if f"c{index}" in ids and str(item.get("text") or "").strip()
    ]
    return ", ".join(labels) or "that option"


def _close_task(question: dict | None, goals, latest, *, card: bool) -> str:
    """One question, asked in one place, judged against the quest goals."""
    standard = _goal_standard(goals)
    if question is None:
        return "The close has no question."
    if question["kind"] == "multiple" and card:
        if latest is not None and latest.passed:
            picked = _picked_label(question, latest)
            return (
                f"They picked {picked}, and it is correct. "
                f"Explain in one or two sentences why that pick answers the question, using these goals: {standard}. "
                "Do not ask the question again. Do not list the options. Set advance to true."
            )
        if latest is not None and not latest.passed:
            picked = _picked_label(question, latest)
            return (
                f"They picked {picked}. It does not answer the question. "
                f"The question was: {question['text']}. The goals are: {standard}. "
                "Explain that pick in one or two sentences. "
                "Do not repeat the question. Do not ask them to type an answer. "
                "Do not name the correct option. The card stays up for another pick. Set advance to false."
            )
        return (
            "The choice card is the question. "
            "Your reply is exactly: Pick one answer on the card. "
            "Do not repeat the question. Do not ask for a typed answer. Set advance to false."
        )
    if question["kind"] == "multiple":
        return (
            f"The struggle window is over for this multiple-choice question: {question['text']}. "
            f"Explain the answer using these goals: {standard}. "
            "Do not ask the question again. Set advance to true."
        )
    return (
        f"Ask this question once: {question['text']}. "
        "The kid types the answer. Do not offer choices. "
        f"A good answer fits these goals: {standard}. "
        "When they have answered, reply to the words they wrote and say what was right or missing. "
        'If it fits, set rubric_met to ["criterion"] and advance to true. '
        "If it does not, set rubric_met to [] and advance to false. "
        "Do not ask the same question as a choice card."
    )


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
    latest_close = latest_close_result(tutor_session) if on_close else None
    spoken = offer
    if spoken is None and close_card is not None and latest_close is not None and latest_close.passed:
        spoken = "correct"
    include_widget = close_card is not None
    reveal_close = finished or on_close
    close_question = active_close_question(quest.close, tutor_session) if reveal_close else None
    studio_goals, empty_close, close_line = _quest_walk(quest, reveal_close=reveal_close, active=close_question)
    held = False
    grade_writing = False
    withhold_answer = offer == "ask"
    if on_close:
        prompt = _close_task(close_question, goals, latest_close, card=close_card is not None and offer == "ask")
        if close_question and close_question["kind"] == "multiple" and latest_close is not None and latest_close.passed:
            prompt = _close_task(close_question, goals, latest_close, card=True)
        role = "close"
        position = len(goals) + 1
        if close_question and close_question["kind"] == "single":
            rubric = (
                RubricCriterion(
                    id="criterion",
                    text=f"The typed answer fits: {_goal_standard(goals)}",
                    weight=100,
                ),
            )
        else:
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
        widget_offer=spoken,
        withhold_answer=withhold_answer,
    )
