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
from app.models import Beat, Session as TutorSession
from app.queries import choice_widget_visible, latest_result, locate_beat, ordered_beats
from app.tutor_profile import load_profile

PASS_SCORE = 70


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


def _widget(tutor_session: TutorSession, beat: Beat) -> WidgetTask | None:
    quiz = beat.widget if isinstance(beat.widget, dict) else None
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
    result = latest_result(tutor_session, beat.id)
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


def _zpd(tutor_session: TutorSession, beat: Beat | None) -> str:
    if beat is None:
        return "on-level"
    result = latest_result(tutor_session, beat.id)
    if result is None:
        return "on-level"
    if not result.passed:
        return "support"
    if result.score >= 85:
        return "stretch"
    return "on-level"


def _criterion(quest) -> tuple[RubricCriterion, ...]:
    rows = []
    for row in quest.success_criterion or []:
        if isinstance(row, dict) and row.get("id"):
            rows.append(
                RubricCriterion(
                    id=str(row["id"]),
                    text=str(row.get("text") or ""),
                    weight=int(row.get("weight") or 0),
                )
            )
    return tuple(rows)


def _quest_objective(quest) -> str:
    goal = (quest.learning_goal or "").strip()
    if goal:
        return goal
    return (quest.title or "").strip()


def _failed(tutor_session: TutorSession, beat_id) -> int:
    return sum(
        1
        for result in tutor_session.results
        if result.beat_id == beat_id and not result.passed
    )


def load_prompt(tutor_session: TutorSession, *, kickoff: bool = False) -> PromptBundle:
    quest = tutor_session.quest
    unit = quest.unit
    course = unit.course
    student = tutor_session.student
    beats = ordered_beats(quest)
    quest_objective = _quest_objective(quest)
    criterion = _criterion(quest)
    goal = (quest.learning_goal or "").strip()
    current = locate_beat(quest, tutor_session.current_beat_id)
    show = next((beat for beat in beats if beat.role == "show"), None)
    gate_cleared = False
    if show is not None:
        show_result = latest_result(tutor_session, show.id)
        gate_cleared = show_result is not None and show_result.passed
    source = current
    finished = current is None
    if source is None and beats:
        source = beats[-1]
    engage = next((item for item in beats if item.role == "engage"), None)
    opening_idea = (engage.prompt if engage is not None else "").strip()
    held = (
        source is not None
        and not finished
        and isinstance(source.widget, dict)
        and not choice_widget_visible(tutor_session, source)
    )
    if source is None:
        beat_layer = Layer1Beat(
            course_title=course.title,
            unit_title=unit.title,
            continuity=unit.continuity_summary,
            quest_code=quest.code,
            quest_title=quest.title,
            beat_role="",
            beat_position=0,
            beat_count=0,
            bloom_level="",
            cognitive_load="",
            prompt="",
            rubric=(),
            misconceptions=(),
            hint_ladder=HintLadder("", "", ""),
            widget=None,
            pass_score=PASS_SCORE,
            gate_cleared=False,
            finished=True,
            quest_objective=quest_objective,
            beat_objectives=(),
            learning_goal=goal,
            success_criterion=criterion,
            requires_teach_back=bool(quest.requires_teach_back),
            opening_idea=opening_idea,
        )
        attempt_count = 0
    else:
        beat_layer = Layer1Beat(
            course_title=course.title,
            unit_title=unit.title,
            continuity=unit.continuity_summary,
            quest_code=quest.code,
            quest_title=quest.title,
            beat_role=source.role,
            beat_position=source.position,
            beat_count=len(beats),
            bloom_level=source.bloom_level,
            cognitive_load=source.cognitive_load,
            prompt=source.prompt,
            rubric=_rows(source),
            misconceptions=_traps(source),
            hint_ladder=_ladder(source),
            widget=None if finished or held else _widget(tutor_session, source),
            pass_score=PASS_SCORE,
            gate_cleared=gate_cleared,
            finished=finished,
            quest_objective=quest_objective,
            beat_objectives=(),
            learning_goal=goal,
            success_criterion=criterion,
            requires_teach_back=bool(quest.requires_teach_back),
            opening_idea=opening_idea,
        )
        attempt_count = 0 if finished or current is None else _failed(tutor_session, current.id)
    interests = tuple(str(item) for item in (student.interests or []) if str(item).strip())
    student_layer = Layer2Student(
        display_name=student.display_name,
        age_band=age_band_for(student.age),
        reading_level=student.reading_level,
        modality=student.modality,
        interests=interests,
        attempt_count=attempt_count,
        zpd=_zpd(tutor_session, None if finished else current),
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
    )
