"""Parents, their linked children, and the parent-safe chat views.

There is no login. A parent id in the URL is the only gate, the same as the kid
pages. The link check below keeps one parent's pages on the children they chose.
A parent never receives model prompts: the chat detail here has no prompts key.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.kc import kc_chat_detail, kc_chat_summaries
from app.models import KcSession, Parent, ParentStudent, Student
from app.present import student_out
from app.schemas import KcChatComponent, KcChatCourse, KcChatMessage, StudentOut


class ParentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ParentStudentsIn(BaseModel):
    student_ids: list[uuid.UUID] = Field(default_factory=list)


class ParentOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    child_count: int = 0


class ParentChatSummary(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_display_name: str
    course_id: uuid.UUID
    course_code: str
    course_title: str
    kc_id: uuid.UUID
    kc_code: str
    kc_title: str
    step_label: str
    status: str
    score: int | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int


class ParentChatStudent(BaseModel):
    id: uuid.UUID
    display_name: str


class ParentChatDetail(BaseModel):
    """Same shape the admin chat view reads, minus the prompts and the student profile."""

    id: uuid.UUID
    status: str
    step_label: str
    score: int | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
    student: ParentChatStudent
    course: KcChatCourse
    component: KcChatComponent
    messages: list[KcChatMessage]


def _clean_name(value: str) -> str:
    name = " ".join(value.split())
    if not name:
        raise HTTPException(status_code=422, detail="Write a name for the parent.")
    return name[:120]


def _child_count(db: Session, parent_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(ParentStudent).where(ParentStudent.parent_id == parent_id)
        )
        or 0
    )


def parent_out(db: Session, parent: Parent) -> ParentOut:
    return ParentOut(
        id=parent.id,
        name=parent.name,
        created_at=parent.created_at,
        child_count=_child_count(db, parent.id),
    )


def parent_or_404(db: Session, parent_id: uuid.UUID) -> Parent:
    parent = db.get(Parent, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="That parent was not found.")
    return parent


def list_parents(db: Session) -> list[ParentOut]:
    rows = db.scalars(select(Parent).order_by(func.lower(Parent.name), Parent.created_at)).all()
    return [parent_out(db, row) for row in rows]


def create_parent(db: Session, name: str) -> ParentOut:
    parent = Parent(name=_clean_name(name))
    db.add(parent)
    db.flush()
    return parent_out(db, parent)


def linked_students(db: Session, parent_id: uuid.UUID) -> list[Student]:
    rows = db.scalars(
        select(Student)
        .join(ParentStudent, ParentStudent.student_id == Student.id)
        .where(ParentStudent.parent_id == parent_id)
    ).all()
    return sorted(rows, key=lambda student: (student.display_name or "").lower())


def linked_student_outs(db: Session, parent_id: uuid.UUID) -> list[StudentOut]:
    parent_or_404(db, parent_id)
    return [student_out(student) for student in linked_students(db, parent_id)]


def set_linked_students(db: Session, parent_id: uuid.UUID, student_ids: list[uuid.UUID]) -> list[StudentOut]:
    parent_or_404(db, parent_id)
    wanted = list(dict.fromkeys(student_ids))
    if wanted:
        found = set(db.scalars(select(Student.id).where(Student.id.in_(wanted))).all())
        missing = [item for item in wanted if item not in found]
        if missing:
            raise HTTPException(status_code=422, detail="One of those children was not found.")
    current = set(db.scalars(select(ParentStudent.student_id).where(ParentStudent.parent_id == parent_id)).all())
    removed = current - set(wanted)
    if removed:
        db.execute(
            delete(ParentStudent).where(
                ParentStudent.parent_id == parent_id, ParentStudent.student_id.in_(removed)
            )
        )
    for student_id in wanted:
        if student_id not in current:
            db.add(ParentStudent(parent_id=parent_id, student_id=student_id))
    db.flush()
    return [student_out(student) for student in linked_students(db, parent_id)]


def require_linked_child(db: Session, parent_id: uuid.UUID, student_id: uuid.UUID) -> Student:
    """404 for an unknown parent, 403 when the child is not one of theirs."""
    parent_or_404(db, parent_id)
    linked = db.scalar(
        select(ParentStudent.id).where(
            ParentStudent.parent_id == parent_id, ParentStudent.student_id == student_id
        )
    )
    student = db.get(Student, student_id) if linked is not None else None
    if student is None:
        raise HTTPException(status_code=403, detail="That child is not linked to this parent.")
    return student


def parent_chat_summaries(db: Session, parent_id: uuid.UUID, student_id: uuid.UUID) -> list[ParentChatSummary]:
    require_linked_child(db, parent_id, student_id)
    return [ParentChatSummary(**row) for row in kc_chat_summaries(db, student_id)]


def parent_chat_detail(
    db: Session, parent_id: uuid.UUID, student_id: uuid.UUID, session_id: uuid.UUID
) -> ParentChatDetail:
    require_linked_child(db, parent_id, student_id)
    row = db.get(KcSession, session_id)
    if row is None or row.student_id != student_id:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    detail = kc_chat_detail(db, session_id)
    detail.pop("prompts", None)
    detail["student"] = {"id": detail["student"]["id"], "display_name": detail["student"]["display_name"]}
    return ParentChatDetail(**detail)
