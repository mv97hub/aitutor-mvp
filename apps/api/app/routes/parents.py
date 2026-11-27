"""Parent portal: parents, the children they follow, and parent-safe chats and progress."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.blind_evaluator import course_exam_summary
from app.database import get_db
from app.graph2 import build_radar_payload
from app.kc import _course_or_404, network, progress, tutor_courses
from app.parent_copilot import (
    DEFAULT_SHARE_TTL_DAYS,
    apply_parent_intervention,
    create_teacher_share_token,
    get_parent_copilot_summary,
    list_teacher_share_tokens,
    revoke_teacher_share_token,
)
from app.parents import (
    ParentChatDetail,
    ParentChatSummary,
    ParentCreate,
    ParentDashboardOut,
    ParentOut,
    ParentStudentsIn,
    create_parent,
    linked_student_outs,
    list_parents,
    parent_chat_detail,
    parent_chat_summaries,
    parent_dashboard,
    parent_or_404,
    parent_out,
    require_linked_child,
    set_linked_students,
)
from app.schemas import StudentOut

router = APIRouter()


@router.get("/parents", response_model=list[ParentOut])
def get_parents(db: Session = Depends(get_db)) -> list[ParentOut]:
    return list_parents(db)


@router.post("/parents", response_model=ParentOut)
def post_parent(body: ParentCreate, db: Session = Depends(get_db)) -> ParentOut:
    return create_parent(db, body.name)


@router.get("/parents/{parent_id}", response_model=ParentOut)
def get_parent(parent_id: uuid.UUID, db: Session = Depends(get_db)) -> ParentOut:
    return parent_out(db, parent_or_404(db, parent_id))


@router.get("/parents/{parent_id}/dashboard", response_model=ParentDashboardOut)
def get_parent_dashboard(parent_id: uuid.UUID, db: Session = Depends(get_db)) -> ParentDashboardOut:
    return parent_dashboard(db, parent_id)


@router.get("/parents/{parent_id}/students", response_model=list[StudentOut])
def get_parent_students(parent_id: uuid.UUID, db: Session = Depends(get_db)) -> list[StudentOut]:
    return linked_student_outs(db, parent_id)


@router.put("/parents/{parent_id}/students", response_model=list[StudentOut])
def put_parent_students(
    parent_id: uuid.UUID, body: ParentStudentsIn, db: Session = Depends(get_db)
) -> list[StudentOut]:
    return set_linked_students(db, parent_id, body.student_ids)


@router.get(
    "/parents/{parent_id}/children/{student_id}/sessions",
    response_model=list[ParentChatSummary],
)
def get_parent_chats(
    parent_id: uuid.UUID, student_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ParentChatSummary]:
    return parent_chat_summaries(db, parent_id, student_id)


@router.get(
    "/parents/{parent_id}/children/{student_id}/sessions/{session_id}",
    response_model=ParentChatDetail,
)
def get_parent_chat(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ParentChatDetail:
    return parent_chat_detail(db, parent_id, student_id, session_id)


@router.get("/parents/{parent_id}/children/{student_id}/courses")
def get_parent_child_courses(
    parent_id: uuid.UUID, student_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[dict]:
    require_linked_child(db, parent_id, student_id)
    return tutor_courses(db, student_id=student_id)


@router.get("/parents/{parent_id}/children/{student_id}/courses/{course_id}/progress")
def get_parent_child_progress(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    student = require_linked_child(db, parent_id, student_id)
    return progress(db, _course_or_404(db, course_id), student)


@router.get("/parents/{parent_id}/children/{student_id}/courses/{course_id}/network")
def get_parent_child_network(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    require_linked_child(db, parent_id, student_id)
    return network(db, _course_or_404(db, course_id))


@router.get("/parents/{parent_id}/children/{student_id}/radar")
def get_parent_child_radar(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    student = require_linked_child(db, parent_id, student_id)
    return build_radar_payload(db, student.id)


@router.get("/parents/{parent_id}/children/{student_id}/courses/{course_id}/exam")
def get_parent_child_course_exam(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    student = require_linked_child(db, parent_id, student_id)
    course = _course_or_404(db, course_id)
    return course_exam_summary(db, goal_id=course.id, student_id=student.id)


class ParentInterventionIn(BaseModel):
    course_id: uuid.UUID
    course_mode: str | None = None
    locks: dict | None = None


class TeacherShareCreateIn(BaseModel):
    course_id: uuid.UUID | None = None
    label: str = Field(default="", max_length=120)
    expires_in_days: int = Field(default=DEFAULT_SHARE_TTL_DAYS, ge=1, le=180)


@router.get("/parents/{parent_id}/children/{student_id}/copilot")
def get_parent_child_copilot(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    return get_parent_copilot_summary(db, parent_id=parent_id, student_id=student_id)


@router.post("/parents/{parent_id}/children/{student_id}/interventions/apply")
def post_parent_child_intervention(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    body: ParentInterventionIn,
    db: Session = Depends(get_db),
) -> dict:
    out = apply_parent_intervention(
        db,
        parent_id=parent_id,
        student_id=student_id,
        goal_id=body.course_id,
        locks=body.locks,
        course_mode=body.course_mode,
    )
    db.commit()
    return out


@router.get("/parents/{parent_id}/children/{student_id}/teacher-shares")
def get_parent_child_teacher_shares(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_teacher_share_tokens(db, parent_id=parent_id, student_id=student_id)


@router.post("/parents/{parent_id}/children/{student_id}/teacher-shares")
def post_parent_child_teacher_share(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    body: TeacherShareCreateIn,
    db: Session = Depends(get_db),
) -> dict:
    out = create_teacher_share_token(
        db,
        parent_id=parent_id,
        student_id=student_id,
        goal_id=body.course_id,
        label=body.label,
        expires_in_days=body.expires_in_days,
    )
    db.commit()
    return out


@router.delete("/parents/{parent_id}/children/{student_id}/teacher-shares/{share_id}")
def delete_parent_child_teacher_share(
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    share_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    out = revoke_teacher_share_token(
        db,
        parent_id=parent_id,
        student_id=student_id,
        share_id=share_id,
    )
    db.commit()
    return out
