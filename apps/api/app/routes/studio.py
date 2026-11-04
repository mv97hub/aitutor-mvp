"""CreateCourse HTTP API. These routes do not read or write tutor sessions."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudioMessage
from app.schemas import (
    StudioAcceptOut,
    StudioCopyIn,
    StudioCourseCreate,
    StudioCourseOut,
    StudioCourseSummary,
    StudioDeleteIn,
    StudioDraftIn,
    StudioEditIn,
    StudioFallbackIn,
    StudioTreeEditIn,
    StudioIndexesIn,
    StudioMessageIn,
    StudioMessageOut,
    StudioOpeningOut,
    StudioPhaseIn,
    StudioPreferencesIn,
    StudioPromptOut,
    StudioSettingsIn,
    StudioSettingsOut,
    StudioTurnIn,
    StudioTurnOut,
)
from app.studio import (
    STUDIO_MODELS,
    STUDIO_TEMPERATURE,
    StudioError,
    accept_proposal,
    add_message,
    advance_stage,
    attach_fallback_draft,
    chat_turn,
    copy_studio_course,
    course_out,
    create_course,
    delete_studio_course,
    dismiss_proposal,
    edit_item,
    edit_tree,
    ensure_settings,
    list_courses,
    list_messages,
    load_course,
    mark_ready,
    message_out,
    response_schema,
    seed_opening,
    push_draft,
    set_model,
    set_phase_view,
    set_stage_view,
    summary_out,
    system_prompt,
    undo_last,
    update_preferences,
)

router = APIRouter(prefix="/studio")


def _fail(exc: StudioError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.plain)


def _course(db: Session, course_id: UUID):
    course = load_course(db, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _message(db: Session, course_id: UUID, message_id: UUID) -> StudioMessage:
    message = db.get(StudioMessage, message_id)
    if message is None or message.course_id != course_id:
        raise HTTPException(status_code=404, detail="Message not found")
    return message


@router.get("/courses", response_model=list[StudioCourseSummary])
def get_courses(db: Session = Depends(get_db)) -> list[StudioCourseSummary]:
    return [summary_out(course) for course in list_courses(db)]


@router.post("/courses", response_model=StudioCourseOut)
def post_course(body: StudioCourseCreate, db: Session = Depends(get_db)) -> StudioCourseOut:
    try:
        course = create_course(db, code=body.code, title=body.title)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/delete")
def post_delete(course_id: UUID, body: StudioDeleteIn, db: Session = Depends(get_db)) -> dict:
    course = _course(db, course_id)
    try:
        delete_studio_course(db, course, body.password)
    except StudioError as exc:
        raise _fail(exc) from exc
    return {"deleted": True}


@router.post("/courses/{course_id}/copy", response_model=StudioCourseOut)
def post_copy(course_id: UUID, body: StudioCopyIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        copied = copy_studio_course(db, course, body.title)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(copied)


@router.get("/courses/{course_id}", response_model=StudioCourseOut)
def get_course(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    return course_out(_course(db, course_id))


@router.patch("/courses/{course_id}", response_model=StudioCourseOut)
def patch_course(
    course_id: UUID, body: StudioPreferencesIn, db: Session = Depends(get_db)
) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        update_preferences(course, body.model_dump())
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/ready", response_model=StudioCourseOut)
def post_ready(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        mark_ready(course)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/phase", response_model=StudioCourseOut)
def post_phase(course_id: UUID, body: StudioPhaseIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        set_phase_view(course, body.name)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.get("/courses/{course_id}/messages", response_model=list[StudioMessageOut])
def get_messages(course_id: UUID, db: Session = Depends(get_db)) -> list[StudioMessageOut]:
    course = _course(db, course_id)
    return [message_out(message) for message in list_messages(db, course)]


@router.post("/courses/{course_id}/opening", response_model=StudioOpeningOut)
def post_opening(course_id: UUID, db: Session = Depends(get_db)) -> StudioOpeningOut:
    course = _course(db, course_id)
    try:
        messages = seed_opening(db, course)
    except StudioError as exc:
        raise _fail(exc) from exc
    fresh = load_course(db, course_id) or course
    return StudioOpeningOut(course=course_out(fresh), messages=[message_out(message) for message in messages])


@router.post("/courses/{course_id}/turns", response_model=StudioTurnOut)
def post_turn(course_id: UUID, body: StudioTurnIn, db: Session = Depends(get_db)) -> StudioTurnOut:
    course = _course(db, course_id)
    try:
        result = chat_turn(db, course, body.content)
    except StudioError as exc:
        raise _fail(exc) from exc
    assistant = result.get("assistant")
    return StudioTurnOut(
        wrote=False,
        handled=bool(result.get("handled")),
        user=message_out(result["user"]) if result.get("user") else None,
        assistant=message_out(assistant) if assistant else None,
        course=course_out(result["course"]) if result.get("course") else None,
    )


@router.post("/courses/{course_id}/fallback", response_model=StudioTurnOut)
def post_fallback(course_id: UUID, body: StudioFallbackIn, db: Session = Depends(get_db)) -> StudioTurnOut:
    course = _course(db, course_id)
    try:
        result = attach_fallback_draft(db, course, body.content)
    except StudioError as exc:
        raise _fail(exc) from exc
    return StudioTurnOut(
        wrote=False,
        handled=True,
        assistant=message_out(result["assistant"]),
        course=course_out(result["course"]),
    )


@router.post("/courses/{course_id}/push-draft", response_model=StudioCourseOut)
def post_push_draft(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        fresh = push_draft(db, course)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(fresh)


@router.post("/courses/{course_id}/advance-stage", response_model=StudioCourseOut)
def post_advance_stage(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        fresh = advance_stage(db, course)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(fresh)


@router.post("/courses/{course_id}/stage", response_model=StudioCourseOut)
def post_stage(course_id: UUID, body: StudioPhaseIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        set_stage_view(course, body.name)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/tree", response_model=StudioCourseOut)
def post_tree(course_id: UUID, body: StudioTreeEditIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        edit_tree(
            db,
            course,
            action=body.action,
            code=body.code,
            title=body.title,
            position=body.position,
            learning_goal=body.learning_goal,
            success_criterion=body.success_criterion,
            close=body.close,
        )
    except StudioError as exc:
        raise _fail(exc) from exc
    fresh = load_course(db, course_id) or course
    return course_out(fresh)


@router.post("/courses/{course_id}/messages", response_model=StudioMessageOut)
def post_message(
    course_id: UUID, body: StudioMessageIn, db: Session = Depends(get_db)
) -> StudioMessageOut:
    course = _course(db, course_id)
    try:
        message = add_message(
            db,
            course,
            role=body.role,
            content=body.content,
            proposal=body.proposal,
        )
    except StudioError as exc:
        raise _fail(exc) from exc
    return message_out(message)


@router.post("/courses/{course_id}/messages/{message_id}/accept", response_model=StudioAcceptOut)
def post_accept(
    course_id: UUID,
    message_id: UUID,
    body: StudioIndexesIn | None = None,
    db: Session = Depends(get_db),
) -> StudioAcceptOut:
    course = _course(db, course_id)
    message = _message(db, course_id, message_id)
    try:
        accept_proposal(db, course, message, None if body is None else body.indexes)
    except StudioError as exc:
        raise _fail(exc) from exc
    return StudioAcceptOut(course=course_out(course), message=message_out(message))


@router.post("/courses/{course_id}/messages/{message_id}/dismiss", response_model=StudioMessageOut)
def post_dismiss(
    course_id: UUID,
    message_id: UUID,
    body: StudioIndexesIn | None = None,
    db: Session = Depends(get_db),
) -> StudioMessageOut:
    course = _course(db, course_id)
    message = _message(db, course_id, message_id)
    try:
        dismiss_proposal(course, message, None if body is None else body.indexes)
    except StudioError as exc:
        raise _fail(exc) from exc
    return message_out(message)


@router.post("/courses/{course_id}/edit", response_model=StudioCourseOut)
def post_edit(course_id: UUID, body: StudioEditIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        edit_item(
            db,
            course,
            kind=body.kind,
            code=body.code,
            title=body.title,
            learning_goal=body.learning_goal,
            success_criterion=body.success_criterion,
        )
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/undo", response_model=StudioCourseOut)
def post_undo(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        undo_last(db, course)
    except StudioError as exc:
        raise _fail(exc) from exc
    fresh = load_course(db, course_id)
    return course_out(fresh or course)


@router.get("/courses/{course_id}/prompt", response_model=StudioPromptOut)
def get_prompt(course_id: UUID, db: Session = Depends(get_db)) -> StudioPromptOut:
    course = _course(db, course_id)
    settings = ensure_settings(db)
    messages = list_messages(db, course)
    return StudioPromptOut(
        model=settings.model,
        system_prompt=system_prompt(course, messages),
        response_schema=response_schema(course),
        temperature=STUDIO_TEMPERATURE,
    )


@router.get("/settings", response_model=StudioSettingsOut)
def get_settings(db: Session = Depends(get_db)) -> StudioSettingsOut:
    row = ensure_settings(db)
    return StudioSettingsOut(model=row.model, options=list(STUDIO_MODELS))


@router.put("/settings", response_model=StudioSettingsOut)
def put_settings(body: StudioSettingsIn, db: Session = Depends(get_db)) -> StudioSettingsOut:
    try:
        row = set_model(db, body.model)
    except StudioError as exc:
        raise _fail(exc) from exc
    return StudioSettingsOut(model=row.model, options=list(STUDIO_MODELS))
