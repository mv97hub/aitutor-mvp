from __future__ import annotations

from app.engine.assemble import hint_tier_for
from app.engine.defaults import age_band_for
from app.flow import failed_attempts
from app.models import (
    Course,
    GoalResult,
    Message,
    ModelPrompt,
    Quest,
    Session as TutorSession,
    effective_child_profile,
)
from app.queries import (
    active_close_question,
    choice_widget_visible,
    close_api_parts,
    close_choice_widget,
    close_is_empty,
    latest_result,
    ordered_goals,
)
from app.schemas import (
    BeatOut,
    BlockStep,
    BoardBeat,
    BoardOut,
    BoardResult,
    CatalogQuest,
    CloseOut,
    CourseSummary,
    CourseTree,
    CurrentBlock,
    GoalOut,
    MessageOut,
    ModelPromptOut,
    QuestDetail,
    QuestListItem,
    QuestNode,
    QuizChoiceOut,
    QuizOut,
    ResultOut,
    RubricRowOut,
    SessionAdminOut,
    SessionBeat,
    SessionQuest,
    SessionSummary,
    StudentOut,
)
from app.widgets import hint_text, public_quiz

ROLE_TITLE = {
    "engage": "Engage",
    "try": "Try",
    "name": "Name",
    "show": "Show",
    "teach_back": "Teach back",
}


def student_out(student) -> StudentOut:
    cp = effective_child_profile(student)
    return StudentOut(
        id=student.id,
        slug=student.slug,
        display_name=student.display_name,
        age=student.age,
        age_band=age_band_for(student.age),
        reading_level=student.reading_level or cp["reading_level"],
        modality=student.modality or cp["explanation_style"],
        interests=[str(item) for item in (student.interests or [])],
        grade_band=cp["grade_band"],
        response_length=cp["response_length"],
        expression_style=cp["expression_style"],
        explanation_style=cp["explanation_style"],
        challenge_appetite=cp["challenge_appetite"],
        communication_tone=cp["communication_tone"],
        learning_support=cp["learning_support"],
        interest_tags=list(cp["interest_tags"]),
        child_profile=cp,
        tutor_persona=student.tutor_persona or "",
        tutor_lexicon=student.tutor_lexicon or "",
        tutor_metaphors=student.tutor_metaphors or "",
        tutor_sidekick=student.tutor_sidekick or "",
        tutor_socratic_strictness=student.tutor_socratic_strictness or "balanced",
        tutor_struggle_window=student.tutor_struggle_window or "minimum",
        tutor_anti_spoiler=bool(student.tutor_anti_spoiler),
        tutor_pacing=student.tutor_pacing or "short-turns-one-question",
    )


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        client_id=message.client_id,
        created_at=message.created_at,
    )


def prompt_out(row: ModelPrompt) -> ModelPromptOut:
    return ModelPromptOut(
        id=row.id,
        session_id=row.session_id,
        message_id=row.message_id,
        seq=row.seq,
        system_prompt=row.system_prompt,
        messages=list(row.messages or []),
        model=row.model,
        created_at=row.created_at,
    )


def _goal_out(goal) -> GoalOut:
    return GoalOut(
        position=goal.position,
        learning_goal=goal.learning_goal or "",
        success_criterion=goal.success_criterion or "",
    )


def _close_out(close) -> CloseOut | None:
    if close is None:
        return None
    items, questions, selection = close_api_parts(close)
    return CloseOut(
        close_style=close.close_style,
        answer_style=close.answer_style,
        choice_mode=close.choice_mode,
        items=items,
        questions=questions,
        intent=close.intent or "",
        selection=selection,
    )


def course_summary(course: Course) -> CourseSummary:
    return CourseSummary(
        id=course.id,
        code=course.code,
        title=course.title,
        description=course.description or "",
        audience=course.audience or "",
        quest_count=course.quest_count,
        goals_per_quest=course.goals_per_quest,
        quiz_minutes=course.quiz_minutes,
    )


def _quest_node(quest: Quest) -> QuestNode:
    return QuestNode(
        id=quest.id,
        code=quest.code,
        title=quest.title,
        position=quest.position,
    )


def _catalog_quest(quest: Quest) -> CatalogQuest:
    return CatalogQuest(
        id=quest.id,
        code=quest.code,
        title=quest.title,
        position=quest.position,
        goals=[_goal_out(goal) for goal in sorted(quest.goals, key=lambda item: item.position)],
        close=_close_out(quest.close),
    )


def course_tree(course: Course) -> CourseTree:
    return CourseTree(
        id=course.id,
        code=course.code,
        title=course.title,
        description=course.description or "",
        audience=course.audience or "",
        quest_count=course.quest_count,
        goals_per_quest=course.goals_per_quest,
        quiz_minutes=course.quiz_minutes,
        quests=[
            _catalog_quest(quest)
            for quest in sorted(course.quests, key=lambda item: item.position)
        ],
    )


def quest_list_item(quest: Quest) -> QuestListItem:
    return QuestListItem(
        id=quest.id,
        code=quest.code,
        title=quest.title,
        position=quest.position,
    )


def beat_out(beat: Beat) -> BeatOut:
    return BeatOut(
        id=beat.id,
        position=beat.position,
        role=beat.role,
        bloom_level=beat.bloom_level,
        cognitive_load=beat.cognitive_load,
        prompt=beat.prompt,
        rubric=list(beat.rubric or []),
        misconception_map=list(beat.misconception_map or []),
        hint_ladder=dict(beat.hint_ladder or {}),
        widget=beat.widget if isinstance(beat.widget, dict) else None,
    )


def quest_detail(quest: Quest) -> QuestDetail:
    return QuestDetail(
        **_quest_node(quest).model_dump(),
        course_id=quest.course_id,
        goals=[_goal_out(goal) for goal in ordered_goals(quest)],
        close=_close_out(quest.close),
    )


def _rubric_rows(beat: Beat, met_ids: set[str]) -> list[RubricRowOut]:
    rows = []
    for row in beat.rubric or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        row_id = str(row["id"])
        rows.append(
            RubricRowOut(
                id=row_id,
                text=str(row.get("text") or ""),
                weight=int(row.get("weight") or 0),
                met=row_id in met_ids,
            )
        )
    return rows


def _quiz_out(quiz: dict | None) -> QuizOut | None:
    public = public_quiz(quiz)
    if public is None:
        return None
    return QuizOut(
        type=public["type"],
        prompt=public["prompt"],
        choices=[QuizChoiceOut(id=item["id"], text=item["text"]) for item in public["choices"]],
        explain=public["explain"],
    )


def _step_state(current: bool, upcoming: bool, result, complete: bool) -> str:
    if complete:
        if result is not None and result.passed:
            return "passed"
        if result is not None:
            return "failed"
        return "done"
    if current:
        return "current"
    if upcoming:
        return "upcoming"
    if result is not None and result.passed:
        return "passed"
    if result is not None:
        return "failed"
    return "done"


def board(tutor_session: TutorSession) -> BoardOut:
    quest = tutor_session.quest
    goals = ordered_goals(quest)
    complete = tutor_session.status == "completed"
    on_close = bool(tutor_session.close_started) and not complete
    steps: list[BlockStep] = []
    current = None
    seen = False
    hints = {
        "nudge": "What is the question actually asking?",
        "analogy": "Picture the idea with one concrete object.",
        "scaffold": "Say the idea in one sentence.",
    }
    for goal in goals:
        result = latest_result(tutor_session, goal.id)
        is_current = (not on_close) and tutor_session.current_goal_id == goal.id and not complete
        state = _step_state(is_current, seen, result, complete)
        if is_current:
            seen = True
            tier = hint_tier_for(failed_attempts(tutor_session, goal.id))
            current = CurrentBlock(
                id=goal.id,
                kind="goal",
                title=f"Goal {goal.position}",
                objective=goal.learning_goal or goal.success_criterion or quest.title,
                tutor_prompt=goal.learning_goal or "",
                rubric=[
                    RubricRowOut(
                        id="criterion",
                        text=goal.success_criterion or "",
                        weight=100,
                        met=False,
                    )
                ],
                hint_tier=tier,  # type: ignore[arg-type]
                hint_text=hint_text(hints, tier),
                quiz=None,
            )
        steps.append(
            BlockStep(
                id=goal.id,
                position=goal.position,
                kind="goal",
                title=f"Goal {goal.position}",
                state=state,
            )
        )
    close_id = quest.close.id if quest.close is not None else quest.id
    close_result = latest_result(tutor_session, None) if on_close or complete else None
    close_state = _step_state(on_close, seen or bool(goals), close_result, complete)
    if on_close:
        tier = hint_tier_for(failed_attempts(tutor_session, None))
        question = active_close_question(quest.close, tutor_session)
        question_text = question["text"] if question else "The close has no question."
        current = CurrentBlock(
            id=close_id,
            kind="close",
            title="Close",
            objective=question_text,
            tutor_prompt=question_text if question else "",
            rubric=[],
            hint_tier=tier,  # type: ignore[arg-type]
            hint_text=hint_text(hints, tier),
            quiz=_quiz_out(close_choice_widget(quest, tutor_session) if choice_widget_visible(tutor_session) else None),
        )
    if not close_is_empty(quest) or quest.close is not None:
        steps.append(
            BlockStep(
                id=close_id,
                position=len(goals) + 1,
                kind="close",
                title="Close",
                state=close_state,
            )
        )
    return BoardOut(
        id=tutor_session.id,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        student=student_out(tutor_session.student),
        course_code=quest.course.code,
        course_title=quest.course.title,
        quest_id=quest.id,
        quest_code=quest.code,
        quest_title=quest.title,
        enduring_understanding=quest.course.description or "",
        current_goal_id=None if on_close or complete else tutor_session.current_goal_id,
        close_started=bool(tutor_session.close_started),
        messages=[message_out(message) for message in tutor_session.messages],
        steps=steps,
        current_block=current,
    )


def result_out(result: GoalResult) -> ResultOut:
    goal = result.goal
    quest = result.session.quest
    return ResultOut(
        id=result.id,
        goal_id=result.goal_id,
        role="close" if result.goal_id is None else "goal",
        position=goal.position if goal is not None else len(ordered_goals(quest)) + 1,
        quest_title=quest.title,
        criterion=result.criterion or "",
        answer=result.answer or "",
        score=result.score,
        passed=result.passed,
        feedback=result.feedback,
        misconception=result.misconception,
        hint_tier=result.hint_tier,
        created_at=result.created_at,
    )


def session_summary(tutor_session: TutorSession) -> SessionSummary:
    quest = tutor_session.quest
    return SessionSummary(
        id=tutor_session.id,
        student_id=tutor_session.student_id,
        student_display_name=tutor_session.student.display_name,
        quest_id=quest.id,
        quest_code=quest.code,
        quest_title=quest.title,
        course_title=quest.course.title,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        message_count=len(tutor_session.messages),
        result_count=len(tutor_session.results),
    )


def session_admin(tutor_session: TutorSession) -> SessionAdminOut:
    quest = tutor_session.quest
    return SessionAdminOut(
        id=tutor_session.id,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        student=student_out(tutor_session.student),
        quest=SessionQuest(
            id=quest.id,
            code=quest.code,
            title=quest.title,
            course_code=quest.course.code,
            course_title=quest.course.title,
        ),
        current_goal_id=tutor_session.current_goal_id,
        close_started=bool(tutor_session.close_started),
        messages=[message_out(message) for message in tutor_session.messages],
        results=[result_out(result) for result in tutor_session.results],
        prompts=[prompt_out(row) for row in tutor_session.prompts],
    )
