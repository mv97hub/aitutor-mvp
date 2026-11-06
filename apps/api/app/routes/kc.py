"""Knowledge-component studio and kid tutor. Catalog and kid chat stay on their own routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.kc import (
    add_component,
    apply_component,
    course_out,
    create_course,
    delete_node,
    draft_component,
    draft_course,
    load_patches,
    load_targets,
    mark_ready,
    network,
    open_session,
    progress,
    prompt_for,
    push_course,
    rename_component,
    reorder_course,
    session_out,
    structure,
    tutor_courses,
    turn,
    update_course,
    _course_or_404,
    _node_or_404,
    _student_or_404,
)

router = APIRouter()


class CourseIn(BaseModel):
    title: str
    description: str = ""
    audience: str = "9-11"
    kind: str = "mastery"
    minutes: int | None = None
    code: str | None = None


class CoursePatch(BaseModel):
    title: str | None = None
    description: str | None = None
    audience: str | None = None
    kind: str | None = None
    minutes: int | None = None


class DraftIn(BaseModel):
    message: str = ""


class PushCourseIn(BaseModel):
    components: list[dict]


class AddComponentIn(BaseModel):
    title: str


class ReorderIn(BaseModel):
    ids: list[str]


class RenameIn(BaseModel):
    title: str


class ComponentIn(BaseModel):
    title: str | None = None
    kc_type: str
    core_truth: str = ""
    rubric: list[str] = Field(default_factory=list)
    misconceptions: list[dict] = Field(default_factory=list)
    prerequisite_codes: list[str] = Field(default_factory=list)
    encompasses_codes: list[str] = Field(default_factory=list)
    type_fields: dict = Field(default_factory=dict)


class OpenSessionIn(BaseModel):
    student_id: uuid.UUID
    course_id: uuid.UUID
    kc_id: uuid.UUID


class TurnIn(BaseModel):
    answer: str


@router.get("/kc/courses")
def list_courses(db: Session = Depends(get_db)) -> list[dict]:
    from sqlalchemy import select

    from app.models import KcGoal

    goals = db.scalars(select(KcGoal).order_by(KcGoal.title))
    return [course_out(db, goal) for goal in goals]


@router.post("/kc/courses")
def post_course(body: CourseIn, db: Session = Depends(get_db)) -> dict:
    goal = create_course(
        db,
        title=body.title,
        description=body.description,
        audience=body.audience,
        kind=body.kind,
        minutes=body.minutes,
        code=body.code,
    )
    return course_out(db, goal)


@router.get("/kc/courses/{course_id}")
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return course_out(db, _course_or_404(db, course_id))


@router.patch("/kc/courses/{course_id}")
def patch_course(course_id: uuid.UUID, body: CoursePatch, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    fields = body.model_dump(exclude_unset=True)
    return course_out(db, update_course(db, goal, fields))


@router.post("/kc/courses/{course_id}/draft")
def post_course_draft(course_id: uuid.UUID, body: DraftIn, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    return draft_course(goal, body.message)


@router.post("/kc/courses/{course_id}/push")
def post_course_push(course_id: uuid.UUID, body: PushCourseIn, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    return course_out(db, push_course(db, goal, body.components))


@router.post("/kc/courses/{course_id}/components")
def post_component(course_id: uuid.UUID, body: AddComponentIn, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    add_component(db, goal, body.title)
    return course_out(db, goal)


@router.post("/kc/courses/{course_id}/reorder")
def post_reorder(course_id: uuid.UUID, body: ReorderIn, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    return course_out(db, reorder_course(db, goal, body.ids))


@router.get("/kc/courses/{course_id}/structure")
def get_structure(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return structure(db, _course_or_404(db, course_id))


@router.get("/kc/courses/{course_id}/network")
def get_network(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return network(db, _course_or_404(db, course_id))


@router.post("/kc/courses/{course_id}/ready")
def post_ready(course_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    goal = _course_or_404(db, course_id)
    return course_out(db, mark_ready(db, goal))


@router.get("/kc/nodes/{node_id}")
def get_node(node_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    from app.kc import _detail

    return _detail(_node_or_404(db, node_id), target=True)


@router.put("/kc/nodes/{node_id}")
def put_node(node_id: uuid.UUID, body: ComponentIn, db: Session = Depends(get_db)) -> dict:
    from app.kc import _detail

    node = apply_component(db, _node_or_404(db, node_id), body.model_dump())
    return _detail(node, target=True)


@router.patch("/kc/nodes/{node_id}")
def patch_node(node_id: uuid.UUID, body: RenameIn, db: Session = Depends(get_db)) -> dict:
    from app.kc import _detail

    node = rename_component(db, _node_or_404(db, node_id), body.title)
    return _detail(node, target=True)


@router.post("/kc/nodes/{node_id}/draft")
def post_node_draft(node_id: uuid.UUID, body: DraftIn, db: Session = Depends(get_db)) -> dict:
    node = _node_or_404(db, node_id)
    from sqlalchemy import select

    from app.models import KcGoal

    goal = None
    ordered: list = []
    for candidate in db.scalars(select(KcGoal)):
        targets = load_targets(db, candidate)
        if any(item.id == node.id for item in targets) or any(
            item.id == node.id for item in load_patches(db, targets)
        ):
            goal = candidate
            ordered = targets
            break
    if goal is None:
        raise HTTPException(status_code=422, detail="Draft a component that is on a course.")
    return draft_component(goal, node, ordered, body.message)


@router.post("/kc/nodes/{node_id}/push")
def post_node_push(node_id: uuid.UUID, body: ComponentIn, db: Session = Depends(get_db)) -> dict:
    from app.kc import _detail

    node = apply_component(db, _node_or_404(db, node_id), body.model_dump())
    return _detail(node, target=True)


@router.delete("/kc/nodes/{node_id}")
def remove_node(node_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    delete_node(db, _node_or_404(db, node_id))
    return {"ok": True}


@router.get("/kc/tutor/courses")
def get_tutor_courses(db: Session = Depends(get_db)) -> list[dict]:
    return tutor_courses(db)


@router.get("/kc/tutor/courses/{course_id}")
def get_tutor_course(
    course_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    return progress(db, _course_or_404(db, course_id), _student_or_404(db, student_id))


@router.post("/kc/tutor/sessions")
def post_tutor_session(body: OpenSessionIn, db: Session = Depends(get_db)) -> dict:
    student = _student_or_404(db, body.student_id)
    goal = _course_or_404(db, body.course_id)
    node = _node_or_404(db, body.kc_id)
    return session_out(db, open_session(db, student, goal, node))


def _session_or_404(db: Session, session_id: uuid.UUID):
    from app.models import KcSession

    row = db.get(KcSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That session is not open.")
    return row


@router.get("/kc/tutor/sessions/{session_id}")
def get_tutor_session(session_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return session_out(db, _session_or_404(db, session_id))


@router.get("/kc/tutor/sessions/{session_id}/prompt")
def get_tutor_prompt(session_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    return prompt_for(db, _session_or_404(db, session_id))


@router.post("/kc/tutor/sessions/{session_id}/turn")
def post_tutor_turn(session_id: uuid.UUID, body: TurnIn, db: Session = Depends(get_db)) -> dict:
    return turn(db, _session_or_404(db, session_id), body.answer)
