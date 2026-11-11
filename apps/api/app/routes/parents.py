"""Parent portal: parents, the children they follow, and parent-safe chats and progress."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.kc import _course_or_404, network, progress, tutor_courses
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
