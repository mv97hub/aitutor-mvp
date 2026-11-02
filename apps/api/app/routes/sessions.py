from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.flow import (
    advance,
    append_message,
    append_model_prompt,
    apply_turn_score,
    grade_widget,
    open_session,
    record_result,
)
from app.models import ModelPrompt
from app.models import Session as TutorSession
from app.present import (
    board,
    context_out,
    current_step,
    message_out,
    prompt_out,
    session_admin,
    session_summary,
)
from app.queries import load_session
from app.schemas import (
    BoardOut,
    ContextOut,
    CurrentStepOut,
    MessageIn,
    MessageOut,
    ModelPromptIn,
    ModelPromptOut,
    ResultIn,
    SessionAdminOut,
    SessionOpen,
    SessionSummary,
    TurnScoreIn,
    WidgetIn,
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
    tutor_session = open_session(db, body.student_id, body.fresh, body.lesson_plan_id)
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


@router.post("/sessions/{session_id}/grade-widget")
def grade_widget_route(
    session_id: UUID, body: WidgetIn, db: Session = Depends(get_db)
) -> dict:
    tutor_session = load_session(db, session_id)
    return grade_widget(db, tutor_session, body.choice, body.explanation)


@router.get("/sessions/{session_id}/model-prompts", response_model=list[ModelPromptOut])
def list_model_prompts(
    session_id: UUID, db: Session = Depends(get_db)
) -> list[ModelPromptOut]:
    tutor_session = load_session(db, session_id)
    rows = db.scalars(
        select(ModelPrompt)
        .where(ModelPrompt.session_id == tutor_session.id)
        .order_by(ModelPrompt.seq)
    ).all()
    return [prompt_out(row) for row in rows]


@router.post("/sessions/{session_id}/model-prompts", response_model=ModelPromptOut)
def create_model_prompt(
    session_id: UUID, body: ModelPromptIn, db: Session = Depends(get_db)
) -> ModelPromptOut:
    tutor_session = load_session(db, session_id)
    row = append_model_prompt(
        db, tutor_session, body.system_prompt, list(body.messages), body.model
    )
    return prompt_out(row)


@router.post("/sessions/{session_id}/turn-score")
def turn_score_route(
    session_id: UUID, body: TurnScoreIn, db: Session = Depends(get_db)
) -> dict:
    tutor_session = load_session(db, session_id)
    return apply_turn_score(
        db, tutor_session, body.rubric_met, body.misconception, body.advance
    )
