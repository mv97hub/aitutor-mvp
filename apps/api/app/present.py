from __future__ import annotations

from app.flow import checkpoint_state
from app.models import Checkpoint, CheckpointResult, LessonPlan, Message, Session as TutorSession, Topic
from app.queries import flat_checkpoints, locate, latest_result
from app.schemas import (
    AdminCheckpoint,
    AdminTopic,
    BoardCheckpoint,
    BoardOut,
    BoardResult,
    BoardTopic,
    CheckpointContext,
    ContextOut,
    CurrentStepOut,
    LessonPlanOut,
    LessonPlanSummary,
    MessageOut,
    OutlineCheckpoint,
    OutlineTopic,
    ResultOut,
    SessionAdminOut,
    SessionSummary,
    StudentOut,
    TopicContext,
)


def student_out(student) -> StudentOut:
    return StudentOut(id=student.id, slug=student.slug, display_name=student.display_name)


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
                checkpoints=checkpoints,
            )
        )
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
    )


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
        current_checkpoint = CheckpointContext(
            kind=checkpoint.kind,
            position=checkpoint.position,
            checkpoints_in_topic=len(topic.checkpoints),
            tutor_prompt=checkpoint.tutor_prompt,
            rubric=checkpoint.rubric,
            pass_criteria=checkpoint.pass_criteria,
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
