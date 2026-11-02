from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.blocks import apply_checkpoint
from app.flow import (
    append_checkpoint,
    append_topic,
    clear_active,
    move_item,
    now,
    topic_in_use,
    unique_slug,
    unique_student_slug,
)
from app.models import Checkpoint, LessonPlan, Session as TutorSession, Student, Topic
from app.present import lesson_plan_out, lesson_summary, student_out
from app.queries import checkpoint_in_use, load_plan
from app.schemas import (
    CheckpointWrite,
    LessonPlanCreate,
    LessonPlanOut,
    LessonPlanPatch,
    LessonPlanSummary,
    MoveBody,
    StudentCreate,
    StudentOut,
    TopicCreate,
    TopicPatch,
)

router = APIRouter()


ROSTER = ["iron-man", "storm", "spider-man", "wolverine"]


@router.get("/students", response_model=list[StudentOut])
def list_students(db: Session = Depends(get_db)) -> list[StudentOut]:
    students = list(db.scalars(select(Student)).all())
    students.sort(
        key=lambda student: (
            ROSTER.index(student.slug) if student.slug in ROSTER else len(ROSTER),
            student.display_name.lower(),
        )
    )
    return [student_out(student) for student in students]


@router.post("/students", response_model=StudentOut)
def create_student(body: StudentCreate, db: Session = Depends(get_db)) -> StudentOut:
    name = body.display_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    student = Student(
        slug=unique_student_slug(db, name),
        display_name=name,
        age=body.age,
    )
    db.add(student)
    db.flush()
    return student_out(student)


@router.get("/lesson-plans", response_model=list[LessonPlanSummary])
def list_plans(db: Session = Depends(get_db)) -> list[LessonPlanSummary]:
    plans = db.scalars(
        select(LessonPlan)
        .options(selectinload(LessonPlan.topics))
        .order_by(LessonPlan.created_at)
    ).all()
    return [lesson_summary(plan) for plan in plans]


@router.post("/lesson-plans", response_model=LessonPlanOut)
def create_plan(body: LessonPlanCreate, db: Session = Depends(get_db)) -> LessonPlanOut:
    if body.is_active:
        clear_active(db)
    plan = LessonPlan(
        slug=unique_slug(db, body.title),
        title=body.title.strip(),
        preamble=body.preamble.strip(),
        is_active=body.is_active,
        age_min=body.age_min,
        age_max=body.age_max,
        updated_at=now(),
    )
    db.add(plan)
    db.flush()
    return lesson_plan_out(load_plan(db, plan.id))


@router.get("/lesson-plans/{plan_id}", response_model=LessonPlanOut)
def get_plan(plan_id: UUID, db: Session = Depends(get_db)) -> LessonPlanOut:
    return lesson_plan_out(load_plan(db, plan_id))


@router.patch("/lesson-plans/{plan_id}", response_model=LessonPlanOut)
def patch_plan(
    plan_id: UUID, body: LessonPlanPatch, db: Session = Depends(get_db)
) -> LessonPlanOut:
    plan = load_plan(db, plan_id)
    if body.is_active and not plan.is_active:
        clear_active(db)
    plan.title = body.title.strip()
    plan.preamble = body.preamble.strip()
    plan.is_active = body.is_active
    if "age_min" in body.model_fields_set:
        plan.age_min = body.age_min
    if "age_max" in body.model_fields_set:
        plan.age_max = body.age_max
    plan.updated_at = now()
    db.flush()
    return lesson_plan_out(plan)


@router.delete("/lesson-plans/{plan_id}", status_code=204)
def delete_plan(plan_id: UUID, db: Session = Depends(get_db)) -> None:
    plan = load_plan(db, plan_id)
    in_use = db.scalar(
        select(func.count())
        .select_from(TutorSession)
        .where(TutorSession.lesson_plan_id == plan.id)
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="This lesson plan has sessions, so it cannot be deleted. Edit it instead.",
        )
    db.delete(plan)


@router.post("/lesson-plans/{plan_id}/topics", response_model=LessonPlanOut)
def create_topic(
    plan_id: UUID, body: TopicCreate, db: Session = Depends(get_db)
) -> LessonPlanOut:
    plan = load_plan(db, plan_id)
    append_topic(db, plan, body.title, body.learning_goal, body.tutor_instructions)
    return lesson_plan_out(plan)


@router.patch("/topics/{topic_id}", response_model=LessonPlanOut)
def patch_topic(
    topic_id: UUID, body: TopicPatch, db: Session = Depends(get_db)
) -> LessonPlanOut:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    plan = load_plan(db, topic.lesson_plan_id)
    current = next(item for item in plan.topics if item.id == topic.id)
    current.title = body.title.strip()
    current.learning_goal = body.learning_goal.strip()
    current.tutor_instructions = body.tutor_instructions.strip()
    plan.updated_at = now()
    return lesson_plan_out(plan)


@router.delete("/topics/{topic_id}", response_model=LessonPlanOut)
def delete_topic(topic_id: UUID, db: Session = Depends(get_db)) -> LessonPlanOut:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    plan = load_plan(db, topic.lesson_plan_id)
    current = next(item for item in plan.topics if item.id == topic.id)
    if topic_in_use(db, current):
        raise HTTPException(
            status_code=409,
            detail="This topic is used by a session or a saved score, so it cannot be deleted.",
        )
    plan.topics.remove(current)
    plan.updated_at = now()
    db.flush()
    return lesson_plan_out(plan)


@router.post("/topics/{topic_id}/move", response_model=LessonPlanOut)
def move_topic(
    topic_id: UUID, body: MoveBody, db: Session = Depends(get_db)
) -> LessonPlanOut:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    plan = load_plan(db, topic.lesson_plan_id)
    current = next(item for item in plan.topics if item.id == topic.id)
    move_item(db, list(plan.topics), current, body.direction)
    plan.updated_at = now()
    return lesson_plan_out(plan)


@router.post("/topics/{topic_id}/checkpoints", response_model=LessonPlanOut)
def create_checkpoint(
    topic_id: UUID, body: CheckpointWrite, db: Session = Depends(get_db)
) -> LessonPlanOut:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    plan = load_plan(db, topic.lesson_plan_id)
    current = next(item for item in plan.topics if item.id == topic.id)
    append_checkpoint(db, current, body)
    return lesson_plan_out(plan)


@router.patch("/checkpoints/{checkpoint_id}", response_model=LessonPlanOut)
def patch_checkpoint(
    checkpoint_id: UUID, body: CheckpointWrite, db: Session = Depends(get_db)
) -> LessonPlanOut:
    checkpoint = db.get(Checkpoint, checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    topic = db.get(Topic, checkpoint.topic_id)
    plan = load_plan(db, topic.lesson_plan_id)
    current = _checkpoint_on(plan, checkpoint.id)
    apply_checkpoint(current, body, body.model_fields_set)
    plan.updated_at = now()
    return lesson_plan_out(plan)


@router.delete("/checkpoints/{checkpoint_id}", response_model=LessonPlanOut)
def delete_checkpoint(checkpoint_id: UUID, db: Session = Depends(get_db)) -> LessonPlanOut:
    checkpoint = db.get(Checkpoint, checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    if checkpoint_in_use(db, checkpoint.id):
        raise HTTPException(
            status_code=409,
            detail="This checkpoint is used by a session or a saved score, so it cannot be deleted.",
        )
    topic = db.get(Topic, checkpoint.topic_id)
    plan = load_plan(db, topic.lesson_plan_id)
    current_topic = next(item for item in plan.topics if item.id == topic.id)
    current = _checkpoint_on(plan, checkpoint.id)
    current_topic.checkpoints.remove(current)
    plan.updated_at = now()
    db.flush()
    return lesson_plan_out(plan)


@router.post("/checkpoints/{checkpoint_id}/move", response_model=LessonPlanOut)
def move_checkpoint(
    checkpoint_id: UUID, body: MoveBody, db: Session = Depends(get_db)
) -> LessonPlanOut:
    checkpoint = db.get(Checkpoint, checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    topic = db.get(Topic, checkpoint.topic_id)
    plan = load_plan(db, topic.lesson_plan_id)
    current_topic = next(item for item in plan.topics if item.id == topic.id)
    current = _checkpoint_on(plan, checkpoint.id)
    move_item(db, list(current_topic.checkpoints), current, body.direction)
    plan.updated_at = now()
    return lesson_plan_out(plan)


def _checkpoint_on(plan: LessonPlan, checkpoint_id: UUID) -> Checkpoint:
    for topic in plan.topics:
        for checkpoint in topic.checkpoints:
            if checkpoint.id == checkpoint_id:
                return checkpoint
    raise HTTPException(status_code=404, detail="Checkpoint not found")
