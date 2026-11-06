"""Idempotent seed: four learners and the default tutor profile.

Running this twice does not duplicate students. It does not write courses.
Kid chat reads tutor_profiles, so this seed does not copy a tutor voice onto
the student. Age is filled when missing. Reading level, modality, and interests
are filled when blank.

Studio tables (studio_*) are not read or written here. A re-seed leaves them in place.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.engine.defaults import profile_for_age
from app.models import Student
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
    profile = profile_for_age(student.age)
    if not (student.reading_level or "").strip():
        student.reading_level = profile.reading_level
    if not (student.modality or "").strip():
        student.modality = profile.modality
    if not student.interests:
        student.interests = list(spec["interests"])


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
    ensure_default_profile(db)
    db.commit()
    return {"students_created": created_students, "courses_created": 0}


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
