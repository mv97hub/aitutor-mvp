from __future__ import annotations

from app.engine.assemble import hint_tier_for
from app.engine.defaults import age_band_for
from app.flow import beat_state, failed_attempts
from app.models import Beat, BeatResult, Course, Message, ModelPrompt, Quest, Session as TutorSession
from app.queries import choice_widget_visible, close_choice_widget, latest_result, locate_beat, ordered_beats
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
    return StudentOut(
        id=student.id,
        slug=student.slug,
        display_name=student.display_name,
        age=student.age,
        age_band=age_band_for(student.age),
        reading_level=student.reading_level or "",
        modality=student.modality or "",
        interests=[str(item) for item in (student.interests or [])],
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
    return CloseOut(
        kind=close.kind,
        question=close.question or "",
        items=list(close.items or []),
    )


def course_summary(course: Course) -> CourseSummary:
    return CourseSummary(
        id=course.id,
        code=course.code,
        title=course.title,
        age_band=course.age_band,
        standards_alignment=course.standards_alignment,
        description=course.description or "",
        audience=course.audience or course.age_band,
        quest_count=len(course.quests),
        goals_per_quest=course.goals_per_quest,
        quiz_minutes=course.quiz_minutes,
    )


def _quest_node(quest: Quest) -> QuestNode:
    return QuestNode(
        id=quest.id,
        code=quest.code,
        title=quest.title,
        quest_type=quest.quest_type,
        prerequisite_codes=list(quest.prerequisite_codes or []),
        competency_tags=list(quest.competency_tags or []),
        dinner_prompt=quest.dinner_prompt,
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
        age_band=course.age_band,
        standards_alignment=course.standards_alignment,
        description=course.description or "",
        audience=course.audience or course.age_band,
        quest_count=course.quest_count,
        goals_per_quest=course.goals_per_quest,
        quiz_minutes=course.quiz_minutes,
        competency_dictionary=list(course.competency_dictionary or []),
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
        quest_type=quest.quest_type,
        prerequisite_codes=list(quest.prerequisite_codes or []),
        competency_tags=list(quest.competency_tags or []),
        unit_number=0,
        unit_title="",
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
        goals=[_goal_out(goal) for goal in sorted(quest.goals, key=lambda item: item.position)],
        close=_close_out(quest.close),
        learning_goal=quest.learning_goal or "",
        success_criterion=list(quest.success_criterion or []),
        requires_teach_back=bool(quest.requires_teach_back),
        beats=[beat_out(beat) for beat in ordered_beats(quest)],
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


def board(tutor_session: TutorSession) -> BoardOut:
    quest = tutor_session.quest
    beats = ordered_beats(quest)
    complete = tutor_session.current_beat_id is None
    seen = False
    steps: list[BlockStep] = []
    board_beats: list[BoardBeat] = []
    current = None
    for beat in beats:
        result = latest_result(tutor_session, beat.id)
        state = beat_state(beat, tutor_session.current_beat_id, result, seen, complete)
        if beat.id == tutor_session.current_beat_id:
            seen = True
            tier = hint_tier_for(failed_attempts(tutor_session, beat.id))
            met = set(result.rubric_met or []) if result is not None else set()
            current = CurrentBlock(
                id=beat.id,
                kind=beat.role,
                title=ROLE_TITLE.get(beat.role, beat.role),
                objective=f"{ROLE_TITLE.get(beat.role, beat.role)} · {beat.bloom_level}",
                tutor_prompt=beat.prompt,
                rubric=_rubric_rows(beat, met),
                hint_tier=tier,  # type: ignore[arg-type]
                hint_text=hint_text(beat.hint_ladder, tier),
                quiz=_quiz_out(
                    close_choice_widget(quest, beat) if choice_widget_visible(tutor_session, beat) else None
                ),
            )
        steps.append(
            BlockStep(
                id=beat.id,
                position=beat.position,
                kind=beat.role,
                title=ROLE_TITLE.get(beat.role, beat.role),
                state=state,
            )
        )
        board_beats.append(
            BoardBeat(
                id=beat.id,
                position=beat.position,
                role=beat.role,
                latest_result=BoardResult(
                    id=result.id,
                    score=result.score,
                    passed=result.passed,
                    feedback=result.feedback,
                    created_at=result.created_at,
                )
                if result
                else None,
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
        current_beat_id=tutor_session.current_beat_id,
        beats=board_beats,
        messages=[message_out(message) for message in tutor_session.messages],
        steps=steps,
        current_block=current,
    )


def result_out(result: BeatResult) -> ResultOut:
    beat = result.beat
    return ResultOut(
        id=result.id,
        beat_id=beat.id,
        beat_role=beat.role,
        beat_position=beat.position,
        quest_title=beat.quest.title,
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
        current_beat_id=tutor_session.current_beat_id,
        beats=[
            SessionBeat(id=beat.id, position=beat.position, role=beat.role)
            for beat in ordered_beats(quest)
        ],
        messages=[message_out(message) for message in tutor_session.messages],
        results=[result_out(result) for result in tutor_session.results],
        prompts=[prompt_out(row) for row in tutor_session.prompts],
    )
