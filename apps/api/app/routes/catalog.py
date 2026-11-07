from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.course_io import (
    CourseFileError,
    copy_studio_into_catalog,
    export_course,
    normalize_criterion,
    normalize_goal,
    replace_course,
)
from app.database import get_db
from app.engine.defaults import profile_for_age
from app.flow import apply_student_profile, now, unique_course_code, unique_student_slug
from app.models import (
    AGE_BANDS,
    Course,
    Quest,
    Session as TutorSession,
    Student,
)
from app.present import course_summary, course_tree, quest_detail, quest_list_item, student_out
from app.queries import load_course, load_quest, quest_in_use
from app.schemas import (
    BeatWrite,
    CourseCreate,
    CoursePatch,
    CourseSummary,
    CourseTree,
    StudioImportIn,
    ProfileDefaults,
    QuestDetail,
    QuestListItem,
    QuestPatch,
    StudentCreate,
    StudentOut,
    StudentPatch,
)

router = APIRouter()

ROSTER = ["iron-man", "storm", "spider-man", "wolverine"]


def _provided(body) -> set[str]:
    return set(body.model_fields_set)


def _clean_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [item.strip() for item in values if item and item.strip()]


@router.get("/profile-defaults", response_model=ProfileDefaults)
def profile_defaults(age: int) -> ProfileDefaults:
    if age < 4 or age > 18:
        raise HTTPException(status_code=422, detail="Age must be from 4 to 18")
    profile = profile_for_age(age)
    return ProfileDefaults(
        age_band=profile.age_band,
        reading_level=profile.reading_level,
        modality=profile.modality,
        interests=[],
        tutor_persona=profile.persona,
        tutor_lexicon=profile.lexicon,
        tutor_metaphors=profile.metaphors,
        tutor_sidekick=profile.sidekick,
        tutor_socratic_strictness=profile.socratic_strictness,
        tutor_struggle_window=profile.struggle_window,
        tutor_anti_spoiler=profile.anti_spoiler,
        tutor_pacing=profile.pacing,
    )


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
    student = Student(slug=unique_student_slug(db, name), display_name=name, age=body.age)
    provided = _provided(body)
    if "reading_level" in provided and body.reading_level is not None:
        student.reading_level = body.reading_level.strip()
    if "modality" in provided and body.modality is not None:
        student.modality = body.modality.strip()
    if "interests" in provided:
        student.interests = _clean_list(body.interests)
    if "tutor_persona" in provided and body.tutor_persona is not None:
        student.tutor_persona = body.tutor_persona.strip()
    if "tutor_lexicon" in provided and body.tutor_lexicon is not None:
        student.tutor_lexicon = body.tutor_lexicon.strip()
    if "tutor_metaphors" in provided and body.tutor_metaphors is not None:
        student.tutor_metaphors = body.tutor_metaphors.strip()
    if "tutor_sidekick" in provided and body.tutor_sidekick is not None:
        student.tutor_sidekick = body.tutor_sidekick.strip()
    if "tutor_socratic_strictness" in provided and body.tutor_socratic_strictness is not None:
        student.tutor_socratic_strictness = body.tutor_socratic_strictness.strip()
    if "tutor_struggle_window" in provided and body.tutor_struggle_window is not None:
        student.tutor_struggle_window = body.tutor_struggle_window.strip()
    if "tutor_anti_spoiler" in provided and body.tutor_anti_spoiler is not None:
        student.tutor_anti_spoiler = body.tutor_anti_spoiler
    if "tutor_pacing" in provided and body.tutor_pacing is not None:
        student.tutor_pacing = body.tutor_pacing.strip()
    apply_student_profile(student, provided=provided)
    db.add(student)
    db.flush()
    return student_out(student)


@router.patch("/students/{student_id}", response_model=StudentOut)
def patch_student(student_id: UUID, body: StudentPatch, db: Session = Depends(get_db)) -> StudentOut:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    provided = _provided(body)
    if "age" in provided and body.age is not None:
        student.age = body.age
    if "reading_level" in provided and body.reading_level is not None:
        student.reading_level = body.reading_level.strip()
    if "modality" in provided and body.modality is not None:
        student.modality = body.modality.strip()
    if "interests" in provided:
        student.interests = _clean_list(body.interests)
    if "tutor_persona" in provided and body.tutor_persona is not None:
        student.tutor_persona = body.tutor_persona.strip()
    if "tutor_lexicon" in provided and body.tutor_lexicon is not None:
        student.tutor_lexicon = body.tutor_lexicon.strip()
    if "tutor_metaphors" in provided and body.tutor_metaphors is not None:
        student.tutor_metaphors = body.tutor_metaphors.strip()
    if "tutor_sidekick" in provided and body.tutor_sidekick is not None:
        student.tutor_sidekick = body.tutor_sidekick.strip()
    if "tutor_socratic_strictness" in provided and body.tutor_socratic_strictness is not None:
        student.tutor_socratic_strictness = body.tutor_socratic_strictness.strip()
    if "tutor_struggle_window" in provided and body.tutor_struggle_window is not None:
        student.tutor_struggle_window = body.tutor_struggle_window.strip()
    if "tutor_anti_spoiler" in provided and body.tutor_anti_spoiler is not None:
        student.tutor_anti_spoiler = body.tutor_anti_spoiler
    if "tutor_pacing" in provided and body.tutor_pacing is not None:
        student.tutor_pacing = body.tutor_pacing.strip()
    db.flush()
    return student_out(student)


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(audience: str | None = None, db: Session = Depends(get_db)) -> list[CourseSummary]:
    if audience is not None and audience not in AGE_BANDS:
        raise HTTPException(status_code=422, detail="audience must be 6-8, 9-11, 12-14, or 15-17")
    stmt = (
        select(Course)
        .where(Course.in_catalog.is_(True))
        .options(selectinload(Course.quests))
        .order_by(Course.title)
    )
    if audience is not None:
        stmt = stmt.where(Course.audience == audience)
    return [course_summary(course) for course in db.scalars(stmt).all()]


@router.post("/courses", response_model=CourseTree)
def create_course(body: CourseCreate, db: Session = Depends(get_db)) -> CourseTree:
    code = (body.code or unique_course_code(db, body.title)).strip()
    if db.scalar(select(Course.id).where(Course.code == code)):
        raise HTTPException(status_code=409, detail="That course code is already used.")
    course = Course(
        code=code,
        title=body.title.strip(),
        description=(body.description or "").strip(),
        audience=body.audience,
        quest_count=body.quest_count,
        goals_per_quest=body.goals_per_quest,
        quiz_minutes=body.quiz_minutes,
        updated_at=now(),
    )
    db.add(course)
    db.flush()
    return course_tree(load_course(db, course.id))


@router.post("/courses/import", response_model=CourseTree)
def import_course(payload: dict, db: Session = Depends(get_db)) -> CourseTree:
    try:
        course = replace_course(db, payload)
    except CourseFileError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.field}: {exc.message}") from exc
    course.updated_at = now()
    db.flush()
    return course_tree(load_course(db, course.id))


@router.get("/courses/{course_id}", response_model=CourseTree)
def get_course(course_id: UUID, db: Session = Depends(get_db)) -> CourseTree:
    return course_tree(load_course(db, course_id))


@router.get("/courses/{course_id}/export")
def export_course_route(course_id: UUID, db: Session = Depends(get_db)) -> dict:
    return export_course(load_course(db, course_id))


@router.post("/courses/import-studio", response_model=CourseTree)
def import_studio_course(body: StudioImportIn, db: Session = Depends(get_db)) -> CourseTree:
    try:
        course = copy_studio_into_catalog(db, body.studio_course_id)
    except CourseFileError as exc:
        status = 404 if exc.field == "studio_course_id" else 422
        raise HTTPException(status_code=status, detail=f"{exc.field}: {exc.message}") from exc
    return course_tree(load_course(db, course.id))


@router.post("/courses/{course_id}/remove", status_code=204)
def remove_course(course_id: UUID, db: Session = Depends(get_db)) -> None:
    """Drop the course from the kid catalog. Sessions and messages stay."""
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    course.in_catalog = False
    course.updated_at = now()


@router.get("/courses/{course_id}/quests", response_model=list[QuestListItem])
def list_course_quests(course_id: UUID, db: Session = Depends(get_db)) -> list[QuestListItem]:
    course = load_course(db, course_id)
    return [
        quest_list_item(quest)
        for quest in sorted(course.quests, key=lambda item: item.position)
    ]


@router.patch("/courses/{course_id}", response_model=CourseTree)
def patch_course(course_id: UUID, body: CoursePatch, db: Session = Depends(get_db)) -> CourseTree:
    course = load_course(db, course_id)
    code = body.code.strip()
    clash = db.scalar(select(Course.id).where(Course.code == code, Course.id != course.id))
    if clash is not None:
        raise HTTPException(status_code=409, detail="That course code is already used.")
    course.code = code
    course.title = body.title.strip()
    course.description = body.description.strip()
    course.audience = body.audience
    course.quest_count = body.quest_count
    course.goals_per_quest = body.goals_per_quest
    course.quiz_minutes = body.quiz_minutes
    course.updated_at = now()
    db.flush()
    return course_tree(course)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: UUID, db: Session = Depends(get_db)) -> None:
    course = load_course(db, course_id)
    quest_ids = [quest.id for quest in course.quests]
    if quest_ids:
        in_use = db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id.in_(quest_ids))
        )
        if in_use:
            raise HTTPException(status_code=409, detail="This course has classes, so it cannot be deleted.")
    db.delete(course)


@router.get("/quests/{quest_id}", response_model=QuestDetail)
def get_quest(quest_id: UUID, db: Session = Depends(get_db)) -> QuestDetail:
    return quest_detail(load_quest(db, quest_id))


@router.patch("/quests/{quest_id}", response_model=QuestDetail)
def patch_quest(quest_id: UUID, body: QuestPatch, db: Session = Depends(get_db)) -> QuestDetail:
    quest = load_quest(db, quest_id)
    code = body.code.strip()
    clash = db.scalar(select(Quest.id).where(Quest.code == code, Quest.id != quest.id))
    if clash is not None:
        raise HTTPException(status_code=409, detail="That quest code is already used.")
    tags = _clean_list(body.competency_tags)
    if len(tags) > 2:
        raise HTTPException(status_code=422, detail="competency_tags: needs one or two tags")
    try:
        goal = normalize_goal(body.learning_goal, "learning_goal")
        criterion = normalize_criterion(body.success_criterion, "success_criterion")
    except CourseFileError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.field}: {exc.message}") from exc
    quest.code = code
    quest.title = body.title.strip()
    if goal or criterion:
        from app.models import QuestGoal

        if not quest.goals:
            quest.goals.append(QuestGoal(position=1, learning_goal=goal, success_criterion=criterion or goal))
        else:
            first = sorted(quest.goals, key=lambda item: item.position)[0]
            first.learning_goal = goal or first.learning_goal
            first.success_criterion = criterion or first.success_criterion
    quest.course.updated_at = now()
    db.flush()
    return quest_detail(quest)


@router.delete("/quests/{quest_id}", status_code=204)
def delete_quest(quest_id: UUID, db: Session = Depends(get_db)) -> None:
    quest = load_quest(db, quest_id)
    if quest_in_use(db, quest.id):
        raise HTTPException(status_code=409, detail="This quest has classes, so it cannot be deleted.")
    db.delete(quest)


@router.put("/quests/{quest_id}/beats", response_model=QuestDetail)
def put_beats(quest_id: UUID, body: BeatWrite, db: Session = Depends(get_db)) -> QuestDetail:
    raise HTTPException(status_code=422, detail="A move is not part of this course.")
