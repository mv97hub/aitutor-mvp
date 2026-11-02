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
)
from app.models import ModelPrompt, Quest, Session as TutorSession, Unit
from app.present import board, message_out, prompt_out, session_admin, session_summary
from app.prompt_loader import load_prompt
from app.queries import load_session
from app.schemas import (
    BoardOut,
    MessageIn,
    MessageOut,
    ModelPromptIn,
    ModelPromptOut,
    PromptBundleOut,
    SessionAdminOut,
    SessionOpen,
    SessionSummary,
    TurnScoreIn,
    WidgetIn,
)

router = APIRouter()


def _session_options():
    return (
        selectinload(TutorSession.student),
        selectinload(TutorSession.quest).selectinload(Quest.unit).selectinload(Unit.course),
        selectinload(TutorSession.messages),
        selectinload(TutorSession.results),
    )


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(student_id: UUID | None = None, db: Session = Depends(get_db)) -> list[SessionSummary]:
    stmt = select(TutorSession).options(*_session_options()).order_by(TutorSession.updated_at.desc())
    if student_id is not None:
        stmt = stmt.where(TutorSession.student_id == student_id)
    return [session_summary(item) for item in db.scalars(stmt).all()]


@router.post("/sessions", response_model=BoardOut)
def create_session(body: SessionOpen, db: Session = Depends(get_db)) -> BoardOut:
    tutor_session = open_session(db, body.student_id, body.quest_id, body.fresh)
    db.flush()
    return board(load_session(db, tutor_session.id))


@router.get("/sessions/{session_id}", response_model=SessionAdminOut)
def get_session(session_id: UUID, db: Session = Depends(get_db)) -> SessionAdminOut:
    return session_admin(load_session(db, session_id))


@router.get("/sessions/{session_id}/board", response_model=BoardOut)
def get_board(session_id: UUID, db: Session = Depends(get_db)) -> BoardOut:
    return board(load_session(db, session_id))


@router.get("/sessions/{session_id}/prompt", response_model=PromptBundleOut)
def get_prompt(
    session_id: UUID, kickoff: bool = False, db: Session = Depends(get_db)
) -> PromptBundleOut:
    bundle = load_prompt(load_session(db, session_id), kickoff=kickoff)
    return PromptBundleOut(
        system_prompt=bundle.system_prompt,
        response_schema=bundle.response_schema,
        temperature=bundle.temperature,
    )


@router.post("/sessions/{session_id}/messages", response_model=MessageOut)
def create_message(session_id: UUID, body: MessageIn, db: Session = Depends(get_db)) -> MessageOut:
    tutor_session = load_session(db, session_id)
    message = append_message(db, tutor_session, body.role, body.content.strip(), body.client_id)
    return message_out(message)


@router.post("/sessions/{session_id}/advance")
def advance_session(session_id: UUID, db: Session = Depends(get_db)) -> dict:
    return advance(db, load_session(db, session_id))


@router.post("/sessions/{session_id}/grade-widget")
def grade_widget_route(session_id: UUID, body: WidgetIn, db: Session = Depends(get_db)) -> dict:
    return grade_widget(db, load_session(db, session_id), body.choice, body.explanation)


@router.get("/sessions/{session_id}/model-prompts", response_model=list[ModelPromptOut])
def list_model_prompts(session_id: UUID, db: Session = Depends(get_db)) -> list[ModelPromptOut]:
    tutor_session = load_session(db, session_id)
    rows = db.scalars(
        select(ModelPrompt).where(ModelPrompt.session_id == tutor_session.id).order_by(ModelPrompt.seq)
    ).all()
    return [prompt_out(row) for row in rows]


@router.post("/sessions/{session_id}/model-prompts", response_model=ModelPromptOut)
def create_model_prompt(
    session_id: UUID, body: ModelPromptIn, db: Session = Depends(get_db)
) -> ModelPromptOut:
    tutor_session = load_session(db, session_id)
    row = append_model_prompt(
        db, tutor_session, body.system_prompt, list(body.messages), body.model, body.message_id
    )
    return prompt_out(row)


@router.post("/sessions/{session_id}/turn-score")
def turn_score_route(session_id: UUID, body: TurnScoreIn, db: Session = Depends(get_db)) -> dict:
    return apply_turn_score(
        db, load_session(db, session_id), body.rubric_met, body.misconception, body.advance
    )
