from __future__ import annotations

from app.flow import checkpoint_state, failed_attempts
from app.models import Checkpoint, CheckpointResult, LessonPlan, Message, Session as TutorSession, Topic
from app.queries import flat_checkpoints, locate, latest_result
from app.schemas import (
    AdminCheckpoint,
    AdminTopic,
    BlockStep,
    BoardCheckpoint,
    BoardOut,
    BoardResult,
    BoardTopic,
    CheckpointContext,
    ContextOut,
    CurrentBlock,
    CurrentStepOut,
    LessonPlanOut,
    LessonPlanSummary,
    MessageOut,
    OutlineCheckpoint,
    OutlineTopic,
    QuizChoiceOut,
    QuizOut,
    ResultOut,
    RubricRowOut,
    SessionAdminOut,
    SessionSummary,
    StudentOut,
    TopicContext,
    WidgetGradeOut,
)
from app.widgets import hint_text, hint_tier_for, public_quiz


def student_out(student) -> StudentOut:
    return StudentOut(
        id=student.id,
        slug=student.slug,
        display_name=student.display_name,
        age=student.age,
    )


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        client_id=message.client_id,
        created_at=message.created_at,
    )


def admin_checkpoint(checkpoint: Checkpoint) -> AdminCheckpoint:
    return AdminCheckpoint(
        id=checkpoint.id,
        kind=checkpoint.kind,
        position=checkpoint.position,
        tutor_prompt=checkpoint.tutor_prompt,
        rubric=checkpoint.rubric,
        pass_criteria=checkpoint.pass_criteria,
        objective=checkpoint.objective,
        rubric_rows=list(checkpoint.rubric_rows or []),
        hint_ladder=dict(checkpoint.hint_ladder or {}),
        pass_score=checkpoint.pass_score or 70,
        quiz=checkpoint.quiz if isinstance(checkpoint.quiz, dict) else None,
    )


def admin_topic(topic: Topic) -> AdminTopic:
    return AdminTopic(
        id=topic.id,
        title=topic.title,
        position=topic.position,
        learning_goal=topic.learning_goal,
        tutor_instructions=topic.tutor_instructions,
        checkpoints=[
            admin_checkpoint(checkpoint)
            for checkpoint in sorted(topic.checkpoints, key=lambda item: item.position)
        ],
    )


def lesson_plan_out(plan: LessonPlan) -> LessonPlanOut:
    return LessonPlanOut(
        id=plan.id,
        slug=plan.slug,
        title=plan.title,
        preamble=plan.preamble,
        is_active=plan.is_active,
        age_min=plan.age_min,
        age_max=plan.age_max,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        topics=[
            admin_topic(topic)
            for topic in sorted(plan.topics, key=lambda item: item.position)
        ],
    )


def lesson_summary(plan: LessonPlan) -> LessonPlanSummary:
    return LessonPlanSummary(
        id=plan.id,
        slug=plan.slug,
        title=plan.title,
        is_active=plan.is_active,
        updated_at=plan.updated_at,
        topic_count=len(plan.topics),
        age_min=plan.age_min,
        age_max=plan.age_max,
    )


def board_result(result: CheckpointResult) -> BoardResult:
    return BoardResult(
        id=result.id,
        score=result.score,
        passed=result.passed,
        feedback=result.feedback,
        created_at=result.created_at,
    )


def board(tutor_session: TutorSession) -> BoardOut:
    topics: list[BoardTopic] = []
    for topic in sorted(tutor_session.lesson_plan.topics, key=lambda item: item.position):
        checkpoints: list[BoardCheckpoint] = []
        for checkpoint in sorted(topic.checkpoints, key=lambda item: item.position):
            result = latest_result(tutor_session, checkpoint.id)
            checkpoints.append(
                BoardCheckpoint(
                    id=checkpoint.id,
                    kind=checkpoint.kind,
                    position=checkpoint.position,
                    latest_result=board_result(result) if result else None,
                )
            )
        topics.append(
            BoardTopic(
                id=topic.id,
                title=topic.title,
                position=topic.position,
                learning_goal=topic.learning_goal,
                checkpoints=checkpoints,
            )
        )
    steps, current = _board_blocks(tutor_session)
    return BoardOut(
        id=tutor_session.id,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        student=student_out(tutor_session.student),
        lesson_title=tutor_session.lesson_plan.title,
        lesson_plan_id=tutor_session.lesson_plan_id,
        current_topic_id=tutor_session.current_topic_id,
        current_checkpoint_id=tutor_session.current_checkpoint_id,
        topics=topics,
        messages=[message_out(message) for message in tutor_session.messages],
        steps=steps,
        current_block=current,
    )


def _rubric_rows(checkpoint: Checkpoint, met_ids: set[str]) -> list[RubricRowOut]:
    rows: list[RubricRowOut] = []
    for row in checkpoint.rubric_rows or []:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "")
        if not row_id:
            continue
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


def _board_blocks(tutor_session: TutorSession) -> tuple[list[BlockStep], CurrentBlock | None]:
    rows = flat_checkpoints(tutor_session.lesson_plan)
    lesson_complete = tutor_session.current_checkpoint_id is None
    seen_current = False
    steps: list[BlockStep] = []
    current: CurrentBlock | None = None
    for index, (topic, checkpoint) in enumerate(rows, start=1):
        result = latest_result(tutor_session, checkpoint.id)
        state = checkpoint_state(
            checkpoint,
            tutor_session.current_checkpoint_id,
            result,
            seen_current,
            lesson_complete,
        )
        if checkpoint.id == tutor_session.current_checkpoint_id:
            seen_current = True
            tier = hint_tier_for(failed_attempts(tutor_session, checkpoint.id))
            met = set(result.rubric_met or []) if result is not None else set()
            current = CurrentBlock(
                id=checkpoint.id,
                kind=checkpoint.kind,
                title=topic.title,
                objective=(checkpoint.objective or "").strip(),
                tutor_prompt=checkpoint.tutor_prompt,
                rubric=_rubric_rows(checkpoint, met),
                hint_tier=tier,  # type: ignore[arg-type]
                hint_text=hint_text(checkpoint.hint_ladder, tier),
                quiz=_quiz_out(checkpoint.quiz if isinstance(checkpoint.quiz, dict) else None),
            )
        steps.append(
            BlockStep(
                id=checkpoint.id,
                position=index,
                kind=checkpoint.kind,
                title=topic.title,
                state=state,
            )
        )
    return steps, current


def result_out(result: CheckpointResult) -> ResultOut:
    checkpoint = result.checkpoint
    topic = checkpoint.topic
    return ResultOut(
        id=result.id,
        checkpoint_id=checkpoint.id,
        topic_title=topic.title,
        checkpoint_kind=checkpoint.kind,
        checkpoint_position=checkpoint.position,
        score=result.score,
        passed=result.passed,
        feedback=result.feedback,
        misconception=result.misconception,
        hint_tier=result.hint_tier,
        created_at=result.created_at,
    )


def session_admin(tutor_session: TutorSession) -> SessionAdminOut:
    return SessionAdminOut(
        id=tutor_session.id,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        student=student_out(tutor_session.student),
        lesson_plan=lesson_plan_out(tutor_session.lesson_plan),
        current_topic_id=tutor_session.current_topic_id,
        current_checkpoint_id=tutor_session.current_checkpoint_id,
        messages=[message_out(message) for message in tutor_session.messages],
        results=[result_out(result) for result in tutor_session.results],
    )


def session_summary(tutor_session: TutorSession) -> SessionSummary:
    return SessionSummary(
        id=tutor_session.id,
        student_id=tutor_session.student_id,
        student_display_name=tutor_session.student.display_name,
        lesson_plan_id=tutor_session.lesson_plan_id,
        lesson_title=tutor_session.lesson_plan.title,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        message_count=len(tutor_session.messages),
        result_count=len(tutor_session.results),
    )


def context_out(tutor_session: TutorSession) -> ContextOut:
    plan = tutor_session.lesson_plan
    rows = flat_checkpoints(plan)
    lesson_complete = tutor_session.current_checkpoint_id is None
    seen_current = False
    outline: list[OutlineTopic] = []
    grouped: dict = {}
    for topic, checkpoint in rows:
        result = latest_result(tutor_session, checkpoint.id)
        state = checkpoint_state(
            checkpoint,
            tutor_session.current_checkpoint_id,
            result,
            seen_current,
            lesson_complete,
        )
        if checkpoint.id == tutor_session.current_checkpoint_id:
            seen_current = True
        grouped.setdefault(topic.id, OutlineTopic(title=topic.title, position=topic.position, checkpoints=[]))
        grouped[topic.id].checkpoints.append(
            OutlineCheckpoint(kind=checkpoint.kind, position=checkpoint.position, state=state)
        )
    for topic, _checkpoint in rows:
        if topic.id in grouped and grouped[topic.id] not in outline:
            outline.append(grouped[topic.id])
    located = locate(plan, tutor_session.current_checkpoint_id)
    current_topic = None
    current_checkpoint = None
    if located is not None:
        topic, checkpoint = located
        current_topic = TopicContext(
            title=topic.title,
            position=topic.position,
            learning_goal=topic.learning_goal,
            tutor_instructions=topic.tutor_instructions,
        )
        result = latest_result(tutor_session, checkpoint.id)
        tier = hint_tier_for(failed_attempts(tutor_session, checkpoint.id))
        grade = None
        if result is not None and isinstance(result.choice, dict):
            ids = [str(item) for item in result.choice.get("ids") or []]
            grade = WidgetGradeOut(
                correct=result.passed,
                score=result.score,
                passed=result.passed,
                misconception=result.misconception,
                choice_ids=ids,
                explanation=str(result.choice.get("explanation") or ""),
            )
        current_checkpoint = CheckpointContext(
            kind=checkpoint.kind,
            position=checkpoint.position,
            checkpoints_in_topic=len(topic.checkpoints),
            tutor_prompt=checkpoint.tutor_prompt,
            rubric=checkpoint.rubric,
            pass_criteria=checkpoint.pass_criteria,
            objective=checkpoint.objective,
            rubric_rows=list(checkpoint.rubric_rows or []),
            hint_tier=tier,
            hint_text=hint_text(checkpoint.hint_ladder, tier),
            pass_score=checkpoint.pass_score or 70,
            quiz=checkpoint.quiz if isinstance(checkpoint.quiz, dict) else None,
            widget_grade=grade,
        )
    return ContextOut(
        session_id=tutor_session.id,
        status=tutor_session.status,
        student_display_name=tutor_session.student.display_name,
        lesson_title=plan.title,
        preamble=plan.preamble,
        topic_count=len({topic.id for topic, _checkpoint in rows}),
        outline=outline,
        current_topic=current_topic,
        current_checkpoint=current_checkpoint,
    )


def current_step(tutor_session: TutorSession) -> CurrentStepOut:
    plan = tutor_session.lesson_plan
    located = locate(plan, tutor_session.current_checkpoint_id)
    if located is None:
        return CurrentStepOut(
            status=tutor_session.status,
            message="The lesson is finished. Congratulate the student and do not start a new topic.",
        )
    topic, checkpoint = located
    rows = flat_checkpoints(plan)
    return CurrentStepOut(
        status=tutor_session.status,
        message="This is the only step you may teach right now.",
        topic_title=topic.title,
        topic_position=topic.position,
        topic_count=len({item.id for item, _checkpoint in rows}),
        learning_goal=topic.learning_goal,
        tutor_instructions=topic.tutor_instructions,
        checkpoint_kind=checkpoint.kind,
        checkpoint_position=checkpoint.position,
        checkpoints_in_topic=len(topic.checkpoints),
        tutor_prompt=checkpoint.tutor_prompt,
        rubric=checkpoint.rubric,
        pass_criteria=checkpoint.pass_criteria,
    )
