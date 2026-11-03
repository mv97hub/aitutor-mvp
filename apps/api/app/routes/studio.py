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
    StudioMessageIn,
    StudioMessageOut,
    StudioPhaseIn,
    StudioPreferencesIn,
    StudioPromptOut,
    StudioSettingsIn,
    StudioSettingsOut,
)
from app.studio import (
    STUDIO_MODELS,
    STUDIO_RESPONSE_SCHEMA,
    STUDIO_TEMPERATURE,
    StudioError,
    accept_proposal,
    add_message,
    copy_studio_course,
    course_out,
    create_course,
    delete_studio_course,
    dismiss_proposal,
    ensure_settings,
    list_courses,
    list_messages,
    load_course,
    mark_ready,
    message_out,
    set_model,
    set_phase_view,
    summary_out,
    system_prompt,
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
    course_id: UUID, message_id: UUID, db: Session = Depends(get_db)
) -> StudioAcceptOut:
    course = _course(db, course_id)
    message = _message(db, course_id, message_id)
    try:
        accept_proposal(db, course, message)
    except StudioError as exc:
        raise _fail(exc) from exc
    return StudioAcceptOut(course=course_out(course), message=message_out(message))


@router.post("/courses/{course_id}/messages/{message_id}/dismiss", response_model=StudioMessageOut)
def post_dismiss(
    course_id: UUID, message_id: UUID, db: Session = Depends(get_db)
) -> StudioMessageOut:
    course = _course(db, course_id)
    message = _message(db, course_id, message_id)
    try:
        dismiss_proposal(course, message)
    except StudioError as exc:
        raise _fail(exc) from exc
    return message_out(message)


@router.get("/courses/{course_id}/prompt", response_model=StudioPromptOut)
def get_prompt(course_id: UUID, db: Session = Depends(get_db)) -> StudioPromptOut:
    course = _course(db, course_id)
    settings = ensure_settings(db)
    messages = list_messages(db, course)
    return StudioPromptOut(
        model=settings.model,
        system_prompt=system_prompt(course, messages),
        response_schema=STUDIO_RESPONSE_SCHEMA,
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
