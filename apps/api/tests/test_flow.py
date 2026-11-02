from sqlalchemy import delete, func, select

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Checkpoint, LessonPlan, Session as TutorSession, Student, Topic
from app.seed import seed

client = TestClient(app)


def setup_function() -> None:
    db = SessionLocal()
    try:
        seed(db)
        db.execute(delete(TutorSession))
        db.commit()
    finally:
        db.close()


def _checkpoint_count(db, slug: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Checkpoint)
        .join(Topic)
        .join(LessonPlan)
        .where(LessonPlan.slug == slug)
    )


def test_seed_is_idempotent() -> None:
    db = SessionLocal()
    try:
        again = seed(db)
        students = db.scalar(select(func.count()).select_from(Student))
        plans = db.scalar(select(func.count()).select_from(LessonPlan))
        fractions = _checkpoint_count(db, "fractions")
        reading = _checkpoint_count(db, "reading")
        science = _checkpoint_count(db, "science")
    finally:
        db.close()
    assert again == {"students_created": 0, "lesson_plans_created": 0}
    assert students == 4
    assert plans == 3
    assert fractions == 6
    assert reading == 3
    assert science == 3


def test_reorder_checkpoint_round_trip() -> None:
    plans = client.get("/lesson-plans").json()
    plan_id = next(plan["id"] for plan in plans if plan["slug"] == "fractions")
    plan = client.get(f"/lesson-plans/{plan_id}").json()
    practice = plan["topics"][0]["checkpoints"][1]
    moved = client.post(f"/checkpoints/{practice['id']}/move", json={"direction": "up"})
    assert moved.status_code == 200
    assert [item["kind"] for item in moved.json()["topics"][0]["checkpoints"]] == [
        "practice",
        "teach",
        "quiz",
    ]
    restored = client.post(f"/checkpoints/{practice['id']}/move", json={"direction": "down"})
    assert [item["kind"] for item in restored.json()["topics"][0]["checkpoints"]] == [
        "teach",
        "practice",
        "quiz",
    ]


def test_health_and_roster() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"ok": True}
    roster = client.get("/students")
    assert roster.status_code == 200
    assert [student["display_name"] for student in roster.json()] == [
        "Iron Man",
        "Storm",
        "Spider-Man",
        "Wolverine",
    ]


def _storm_id() -> str:
    students = client.get("/students").json()
    return next(student["id"] for student in students if student["slug"] == "storm")


def _plan_id(slug: str) -> str:
    plans = client.get("/lesson-plans").json()
    return next(plan["id"] for plan in plans if plan["slug"] == slug)


def test_session_stays_on_the_chosen_lesson() -> None:
    reading_id = _plan_id("reading")
    fractions_id = _plan_id("fractions")
    opened = client.post(
        "/sessions",
        json={"student_id": _storm_id(), "lesson_plan_id": reading_id, "fresh": True},
    )
    assert opened.status_code == 200
    assert opened.json()["lesson_title"] == "Reading"
    assert opened.json()["topics"][0]["checkpoints"][0]["kind"] == "teach"
    session_id = opened.json()["id"]
    context = client.get(f"/sessions/{session_id}/context")
    assert "fox" in context.json()["current_checkpoint"]["tutor_prompt"].lower()

    resumed = client.post(
        "/sessions",
        json={"student_id": _storm_id(), "lesson_plan_id": reading_id, "fresh": False},
    )
    assert resumed.json()["id"] == session_id

    other = client.post(
        "/sessions",
        json={"student_id": _storm_id(), "lesson_plan_id": fractions_id, "fresh": False},
    )
    assert other.status_code == 200
    assert other.json()["id"] != session_id
    assert other.json()["lesson_title"] == "Fractions"

    fresh = client.post(
        "/sessions",
        json={"student_id": _storm_id(), "lesson_plan_id": reading_id, "fresh": True},
    )
    assert fresh.json()["id"] != session_id
    assert fresh.json()["lesson_title"] == "Reading"


def test_advance_rules_and_checkpoint_edits() -> None:
    opened = client.post("/sessions", json={"student_id": _storm_id(), "fresh": True})
    assert opened.status_code == 200
    session_id = opened.json()["id"]
    assert opened.json()["student"]["display_name"] == "Storm"
    assert opened.json()["topics"][0]["checkpoints"][0]["kind"] == "teach"
    assert "equal parts" in opened.json()["topics"][0]["learning_goal"].lower()
    assert "tutor_prompt" not in opened.json()["topics"][0]["checkpoints"][0]

    context = client.get(f"/sessions/{session_id}/context")
    assert context.status_code == 200
    body = context.json()
    assert body["student_display_name"] == "Storm"
    assert body["current_checkpoint"]["kind"] == "teach"
    assert "pizza" in body["current_checkpoint"]["tutor_prompt"].lower()
    first_checkpoint_id = opened.json()["topics"][0]["checkpoints"][0]["id"]
    original_prompt = body["current_checkpoint"]["tutor_prompt"]

    teach_advance = client.post(f"/sessions/{session_id}/advance")
    assert teach_advance.status_code == 200
    assert teach_advance.json()["ok"] is True
    assert teach_advance.json()["current_step"]["checkpoint_kind"] == "practice"

    blocked = client.post(f"/sessions/{session_id}/advance")
    assert blocked.json()["ok"] is False
    assert "practice" in blocked.json()["reason"]

    failed = client.post(
        f"/sessions/{session_id}/checkpoint-results",
        json={"score": 40, "passed": False, "feedback": "Not 2/3 yet."},
    )
    assert failed.json()["ok"] is True
    assert failed.json()["passed"] is False
    still_blocked = client.post(f"/sessions/{session_id}/advance")
    assert still_blocked.json()["ok"] is False

    passed = client.post(
        f"/sessions/{session_id}/checkpoint-results",
        json={"score": 100, "passed": True, "feedback": "2/3 is right."},
    )
    assert passed.json()["passed"] is True
    moved = client.post(f"/sessions/{session_id}/advance")
    assert moved.json()["ok"] is True
    assert moved.json()["current_step"]["checkpoint_kind"] == "quiz"

    skip_quiz = client.post(f"/sessions/{session_id}/advance")
    assert skip_quiz.json()["ok"] is False
    assert "quiz" in skip_quiz.json()["reason"].lower()

    quiz_pass = client.post(
        f"/sessions/{session_id}/checkpoint-results",
        json={"score": 100, "passed": True, "feedback": "3/8, numerator 3."},
    )
    assert quiz_pass.json()["kind"] == "quiz"
    after_quiz = client.post(f"/sessions/{session_id}/advance")
    assert after_quiz.json()["ok"] is True
    assert after_quiz.json()["current_step"]["topic_title"] == "Same denominator"

    detail = client.get(f"/sessions/{session_id}")
    assert detail.status_code == 200
    transcript = detail.json()
    assert len(transcript["results"]) == 3
    assert transcript["results"][-1]["passed"] is True
    assert transcript["results"][-1]["checkpoint_kind"] == "quiz"

    edited = client.patch(
        f"/checkpoints/{first_checkpoint_id}",
        json={
            "kind": "teach",
            "tutor_prompt": "EDITED CHECKPOINT prompt for the next session.",
            "rubric": "",
            "pass_criteria": "Student notices the edit.",
        },
    )
    assert edited.status_code == 200
    fresh = client.post("/sessions", json={"student_id": _storm_id(), "fresh": True})
    fresh_context = client.get(f"/sessions/{fresh.json()['id']}/context")
    assert "EDITED CHECKPOINT" in fresh_context.json()["current_checkpoint"]["tutor_prompt"]

    restored = client.patch(
        f"/checkpoints/{first_checkpoint_id}",
        json={
            "kind": "teach",
            "tutor_prompt": original_prompt,
            "rubric": "",
            "pass_criteria": (
                "The student says 1/4 or one fourth, and knows the bottom number is how many "
                "equal slices the pizza was cut into."
            ),
        },
    )
    assert restored.status_code == 200

    saved = client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "user", "content": "Hi! I'm ready to learn.", "client_id": "msg-1"},
    )
    assert saved.status_code == 200
    again = client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "user", "content": "Hi! I'm ready to learn.", "client_id": "msg-1"},
    )
    assert again.json()["id"] == saved.json()["id"]
    admin = client.get(f"/sessions/{session_id}")
    assert len(admin.json()["messages"]) == 1
