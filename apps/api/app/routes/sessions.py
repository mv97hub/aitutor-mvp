from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.flow import advance, append_message, open_session, record_result
from app.models import Session as TutorSession
from app.present import board, context_out, current_step, message_out, session_admin, session_summary
from app.queries import load_session
from app.schemas import (
    BoardOut,
    ContextOut,
    CurrentStepOut,
    MessageIn,
    MessageOut,
    ResultIn,
    SessionAdminOut,
    SessionOpen,
    SessionSummary,
)

router = APIRouter()


def _summaries(db: Session, student_id: UUID | None) -> list[SessionSummary]:
    stmt = (
        select(TutorSession)
        .options(
            selectinload(TutorSession.student),
            selectinload(TutorSession.lesson_plan),
            selectinload(TutorSession.messages),
            selectinload(TutorSession.results),
        )
        .order_by(TutorSession.updated_at.desc())
    )
    if student_id is not None:
        stmt = stmt.where(TutorSession.student_id == student_id)
    return [session_summary(item) for item in db.scalars(stmt).all()]


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    student_id: UUID | None = None, db: Session = Depends(get_db)
) -> list[SessionSummary]:
    return _summaries(db, student_id)


@router.post("/sessions", response_model=BoardOut)
def create_session(body: SessionOpen, db: Session = Depends(get_db)) -> BoardOut:
    tutor_session = open_session(db, body.student_id, body.fresh)
    db.flush()
    return board(load_session(db, tutor_session.id))


@router.get("/sessions/{session_id}", response_model=SessionAdminOut)
def get_session(session_id: UUID, db: Session = Depends(get_db)) -> SessionAdminOut:
    return session_admin(load_session(db, session_id))


@router.get("/sessions/{session_id}/board", response_model=BoardOut)
def get_board(session_id: UUID, db: Session = Depends(get_db)) -> BoardOut:
    return board(load_session(db, session_id))


@router.get("/sessions/{session_id}/context", response_model=ContextOut)
def get_context(session_id: UUID, db: Session = Depends(get_db)) -> ContextOut:
    return context_out(load_session(db, session_id))


@router.get("/sessions/{session_id}/current-step", response_model=CurrentStepOut)
def get_current_step(session_id: UUID, db: Session = Depends(get_db)) -> CurrentStepOut:
    return current_step(load_session(db, session_id))


@router.post("/sessions/{session_id}/messages", response_model=MessageOut)
def create_message(
    session_id: UUID, body: MessageIn, db: Session = Depends(get_db)
) -> MessageOut:
    tutor_session = load_session(db, session_id)
    message = append_message(db, tutor_session, body.role, body.content.strip(), body.client_id)
    return message_out(message)


@router.post("/sessions/{session_id}/checkpoint-results")
def create_result(session_id: UUID, body: ResultIn, db: Session = Depends(get_db)) -> dict:
    tutor_session = load_session(db, session_id)
    return record_result(db, tutor_session, body.score, body.passed, body.feedback)


@router.post("/sessions/{session_id}/advance")
def advance_session(session_id: UUID, db: Session = Depends(get_db)) -> dict:
    tutor_session = load_session(db, session_id)
    return advance(db, tutor_session)
