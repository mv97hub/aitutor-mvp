"""Idempotent seed: four students and three courses.

Running this twice does not duplicate students. Rome, Geometry, and AP Macro are
updated in place. Sessions and messages stay. Any other course code is left as edited.
Students keep a tutor persona that was already saved. Blank tutor fields are filled
from the age band. The default tutor profile is inserted when it is missing and
is not overwritten.

Studio tables (studio_*) are not read or written here. A re-seed leaves them in place.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.course_io import replace_course, update_course_in_place
from app.curriculum import COURSES
from app.database import SessionLocal
from app.engine.defaults import profile_for_age
from app.models import Course, Student
from app.tutor_profile import ensure_default_profile

STUDENTS = [
    {
        "slug": "iron-man",
        "display_name": "Iron Man",
        "age": 10,
        "interests": ["inventions", "teams"],
    },
    {
        "slug": "storm",
        "display_name": "Storm",
        "age": 10,
        "interests": ["weather", "leadership"],
    },
    {
        "slug": "spider-man",
        "display_name": "Spider-Man",
        "age": 11,
        "interests": ["cities", "fairness"],
    },
    {
        "slug": "wolverine",
        "display_name": "Wolverine",
        "age": 16,
        "interests": ["history", "hard choices"],
    },
]


def _fill_student(student: Student, spec: dict) -> None:
    if student.age is None:
        student.age = spec["age"]
    if student.tutor_persona:
        return
    profile = profile_for_age(student.age)
    student.reading_level = profile.reading_level
    student.modality = profile.modality
    student.interests = list(spec["interests"])
    student.tutor_persona = profile.persona
    student.tutor_lexicon = profile.lexicon
    student.tutor_metaphors = profile.metaphors
    student.tutor_sidekick = profile.sidekick
    student.tutor_socratic_strictness = profile.socratic_strictness
    student.tutor_struggle_window = profile.struggle_window
    student.tutor_anti_spoiler = profile.anti_spoiler
    student.tutor_pacing = profile.pacing


def seed(db: Session) -> dict[str, int]:
    created_students = 0
    for spec in STUDENTS:
        student = db.scalar(select(Student).where(Student.slug == spec["slug"]))
        if student is None:
            student = Student(slug=spec["slug"], display_name=spec["display_name"], age=spec["age"])
            db.add(student)
            db.flush()
            created_students += 1
        _fill_student(student, spec)
    db.flush()

    created_courses = 0
    for payload in COURSES:
        exists = db.scalar(select(Course.id).where(Course.code == payload["code"]))
        if exists is None:
            replace_course(db, payload)
            created_courses += 1
        else:
            update_course_in_place(db, payload)
    ensure_default_profile(db)
    db.commit()
    return {"students_created": created_students, "courses_created": created_courses}


def main() -> None:
    db = SessionLocal()
    try:
        result = seed(db)
    finally:
        db.close()
    print(
        "students_created={students_created} courses_created={courses_created}".format(**result)
    )


if __name__ == "__main__":
    main()
