from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.course_io import CourseFileError, export_course, replace_course, validate_beat
from app.database import get_db
from app.engine.defaults import profile_for_age
from app.flow import apply_student_profile, blank_beats, now, unique_course_code, unique_student_slug
from app.models import (
    AGE_BANDS,
    BEAT_ROLES,
    Course,
    Quest,
    Session as TutorSession,
    Student,
    Unit,
)
from app.present import course_summary, course_tree, quest_detail, quest_list_item, student_out
from app.queries import load_course, load_quest, next_position, quest_in_use
from app.schemas import (
    BeatWrite,
    CourseCreate,
    CoursePatch,
    CourseSummary,
    CourseTree,
    ProfileDefaults,
    QuestCreate,
    QuestDetail,
    QuestListItem,
    QuestPatch,
    StudentCreate,
    StudentOut,
    UnitCreate,
    UnitPatch,
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


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(age_band: str | None = None, db: Session = Depends(get_db)) -> list[CourseSummary]:
    if age_band is not None and age_band not in AGE_BANDS:
        raise HTTPException(status_code=422, detail="age_band must be 6-8, 9-11, 12-14, or 15-17")
    stmt = select(Course).options(selectinload(Course.units).selectinload(Unit.quests)).order_by(Course.title)
    if age_band is not None:
        stmt = stmt.where(Course.age_band == age_band)
    return [course_summary(course) for course in db.scalars(stmt).all()]


@router.post("/courses", response_model=CourseTree)
def create_course(body: CourseCreate, db: Session = Depends(get_db)) -> CourseTree:
    code = (body.code or unique_course_code(db, body.title)).strip()
    if db.scalar(select(Course.id).where(Course.code == code)):
        raise HTTPException(status_code=409, detail="That course code is already used.")
    course = Course(
        code=code,
        title=body.title.strip(),
        age_band=body.age_band,
        standards_alignment=body.standards_alignment.strip(),
        competency_dictionary=[],
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


@router.get("/courses/{course_id}/quests", response_model=list[QuestListItem])
def list_course_quests(course_id: UUID, db: Session = Depends(get_db)) -> list[QuestListItem]:
    course = load_course(db, course_id)
    rows: list[QuestListItem] = []
    for unit in sorted(course.units, key=lambda item: item.number):
        for quest in sorted(unit.quests, key=lambda item: item.position):
            rows.append(quest_list_item(quest))
    return rows


@router.patch("/courses/{course_id}", response_model=CourseTree)
def patch_course(course_id: UUID, body: CoursePatch, db: Session = Depends(get_db)) -> CourseTree:
    course = load_course(db, course_id)
    code = body.code.strip()
    clash = db.scalar(select(Course.id).where(Course.code == code, Course.id != course.id))
    if clash is not None:
        raise HTTPException(status_code=409, detail="That course code is already used.")
    course.code = code
    course.title = body.title.strip()
    course.age_band = body.age_band
    course.standards_alignment = body.standards_alignment.strip()
    course.competency_dictionary = [item.model_dump() for item in body.competency_dictionary]
    course.updated_at = now()
    db.flush()
    return course_tree(course)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: UUID, db: Session = Depends(get_db)) -> None:
    course = load_course(db, course_id)
    quest_ids = [quest.id for unit in course.units for quest in unit.quests]
    if quest_ids:
        in_use = db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id.in_(quest_ids))
        )
        if in_use:
            raise HTTPException(status_code=409, detail="This course has classes, so it cannot be deleted.")
    db.delete(course)


@router.post("/courses/{course_id}/units", response_model=CourseTree)
def create_unit(course_id: UUID, body: UnitCreate, db: Session = Depends(get_db)) -> CourseTree:
    course = load_course(db, course_id)
    number = body.number or next_position([unit.number for unit in course.units])
    if any(unit.number == number for unit in course.units):
        raise HTTPException(status_code=409, detail="That unit number is already used.")
    course.units.append(
        Unit(
            number=number,
            title=body.title.strip(),
            enduring_understanding=body.enduring_understanding.strip(),
            continuity_summary=body.continuity_summary.strip(),
            is_diagnostic=body.is_diagnostic,
            is_capstone=body.is_capstone,
        )
    )
    course.updated_at = now()
    db.flush()
    return course_tree(course)


@router.patch("/units/{unit_id}", response_model=CourseTree)
def patch_unit(unit_id: UUID, body: UnitPatch, db: Session = Depends(get_db)) -> CourseTree:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    course = load_course(db, unit.course_id)
    current = next(item for item in course.units if item.id == unit.id)
    if any(item.number == body.number and item.id != current.id for item in course.units):
        raise HTTPException(status_code=409, detail="That unit number is already used.")
    current.number = body.number
    current.title = body.title.strip()
    current.enduring_understanding = body.enduring_understanding.strip()
    current.continuity_summary = body.continuity_summary.strip()
    current.is_diagnostic = body.is_diagnostic
    current.is_capstone = body.is_capstone
    course.updated_at = now()
    db.flush()
    return course_tree(course)


@router.delete("/units/{unit_id}", response_model=CourseTree)
def delete_unit(unit_id: UUID, db: Session = Depends(get_db)) -> CourseTree:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    course = load_course(db, unit.course_id)
    current = next(item for item in course.units if item.id == unit.id)
    if any(quest_in_use(db, quest.id) for quest in current.quests):
        raise HTTPException(status_code=409, detail="This unit has classes, so it cannot be deleted.")
    course.units.remove(current)
    course.updated_at = now()
    db.flush()
    return course_tree(course)


@router.post("/units/{unit_id}/quests", response_model=QuestDetail)
def create_quest(unit_id: UUID, body: QuestCreate, db: Session = Depends(get_db)) -> QuestDetail:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found")
    code = body.code.strip()
    if db.scalar(select(Quest.id).where(Quest.code == code)):
        raise HTTPException(status_code=409, detail="That quest code is already used.")
    course = load_course(db, unit.course_id)
    current = next(item for item in course.units if item.id == unit.id)
    quest = Quest(
        code=code,
        title=body.title.strip(),
        quest_type=body.quest_type,
        prerequisite_codes=_clean_list(body.prerequisite_codes),
        competency_tags=_clean_list(body.competency_tags)[:2],
        dinner_prompt=body.dinner_prompt.strip(),
        position=next_position([item.position for item in current.quests]),
    )
    current.quests.append(quest)
    db.flush()
    for index, beat_body in enumerate(blank_beats(), start=1):
        from app.models import Beat

        quest.beats.append(
            Beat(
                position=index,
                role=beat_body["role"],
                bloom_level=beat_body["bloom_level"],
                cognitive_load=beat_body["cognitive_load"],
                prompt=beat_body["prompt"],
                rubric=beat_body["rubric"],
                misconception_map=beat_body["misconception_map"],
                hint_ladder=beat_body["hint_ladder"],
                widget=beat_body["widget"],
            )
        )
    course.updated_at = now()
    db.flush()
    return quest_detail(load_quest(db, quest.id))


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
    quest.code = code
    quest.title = body.title.strip()
    quest.quest_type = body.quest_type
    quest.prerequisite_codes = _clean_list(body.prerequisite_codes)
    quest.competency_tags = tags
    quest.dinner_prompt = body.dinner_prompt.strip()
    quest.unit.course.updated_at = now()
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
    quest = load_quest(db, quest_id)
    if len(body.beats) != 4:
        raise HTTPException(status_code=422, detail="beats: must contain exactly four beats")
    normalized = []
    for index, beat_body in enumerate(body.beats):
        role = BEAT_ROLES[index]
        try:
            normalized.append(
                validate_beat(beat_body.model_dump(), f"beats[{index}]", role=role)
            )
        except CourseFileError as exc:
            raise HTTPException(status_code=422, detail=f"{exc.field}: {exc.message}") from exc
    existing = sorted(quest.beats, key=lambda item: item.position)
    for beat, fields in zip(existing, normalized, strict=True):
        beat.role = fields["role"]
        beat.bloom_level = fields["bloom_level"]
        beat.cognitive_load = fields["cognitive_load"]
        beat.prompt = fields["prompt"]
        beat.rubric = fields["rubric"]
        beat.misconception_map = fields["misconception_map"]
        beat.hint_ladder = fields["hint_ladder"]
        beat.widget = fields["widget"]
    quest.unit.course.updated_at = now()
    db.flush()
    return quest_detail(quest)
