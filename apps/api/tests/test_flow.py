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
        db.execute(delete(TutorSession))
        db.commit()
        seed(db)
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
        prompts = _checkpoint_count(db, "super-prompts")
        shifts = _checkpoint_count(db, "function-shifts")
        ages = {student.slug: student.age for student in db.scalars(select(Student)).all()}
    finally:
        db.close()
    assert again == {
        "students_created": 0,
        "lesson_plans_created": 0,
        "lesson_plans_rewritten": 0,
    }
    assert students == 4
    assert plans == 5
    assert ages["storm"] == 10
    assert ages["wolverine"] == 16
    assert fractions == 5
    assert reading == 3
    assert science == 3
    assert prompts == 4
    assert shifts == 3


def test_reorder_checkpoint_round_trip() -> None:
    plans = client.get("/lesson-plans").json()
    plan_id = next(plan["id"] for plan in plans if plan["slug"] == "fractions")
    plan = client.get(f"/lesson-plans/{plan_id}").json()
    practice = plan["topics"][0]["checkpoints"][1]
    moved = client.post(f"/checkpoints/{practice['id']}/move", json={"direction": "up"})
    assert moved.status_code == 200
    assert [item["kind"] for item in moved.json()["topics"][0]["checkpoints"]] == [
        "quiz",
        "discovery",
        "teach_back",
    ]
    restored = client.post(f"/checkpoints/{practice['id']}/move", json={"direction": "down"})
    assert [item["kind"] for item in restored.json()["topics"][0]["checkpoints"]] == [
        "discovery",
        "quiz",
        "teach_back",
    ]


def _drop_named(name: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(Student).where(Student.display_name == name))
        db.commit()
    finally:
        db.close()


def test_create_student() -> None:
    _drop_named("Ada Lovelace")
    created = client.post("/students", json={"display_name": "Ada Lovelace", "age": 12})
    assert created.status_code == 200
    body = created.json()
    assert body["display_name"] == "Ada Lovelace"
    assert body["age"] == 12
    assert body["slug"] == "ada-lovelace"
    try:
        roster = client.get("/students").json()
        assert [student["display_name"] for student in roster] == [
            "Iron Man",
            "Storm",
            "Spider-Man",
            "Wolverine",
            "Ada Lovelace",
        ]
        duplicate = client.post("/students", json={"display_name": "Ada Lovelace", "age": 9})
        assert duplicate.status_code == 200
        assert duplicate.json()["slug"] == "ada-lovelace-2"
        blank = client.post("/students", json={"display_name": "   ", "age": 10})
        assert blank.status_code == 422
    finally:
        _drop_named("Ada Lovelace")


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
    opened = client.post(
        "/sessions",
        json={"student_id": _storm_id(), "lesson_plan_id": _plan_id("reading"), "fresh": True},
    )
    assert opened.status_code == 200
    session_id = opened.json()["id"]
    assert opened.json()["student"]["display_name"] == "Storm"
    assert opened.json()["lesson_title"] == "Reading"
    assert opened.json()["topics"][0]["checkpoints"][0]["kind"] == "teach"
    assert "tutor_prompt" not in opened.json()["topics"][0]["checkpoints"][0]

    context = client.get(f"/sessions/{session_id}/context")
    assert context.status_code == 200
    body = context.json()
    assert body["student_display_name"] == "Storm"
    assert body["current_checkpoint"]["kind"] == "teach"
    assert "fox" in body["current_checkpoint"]["tutor_prompt"].lower()
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
    assert after_quiz.json()["completed"] is True

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
    try:
        fresh = client.post(
            "/sessions",
            json={"student_id": _storm_id(), "lesson_plan_id": _plan_id("reading"), "fresh": True},
        )
        fresh_context = client.get(f"/sessions/{fresh.json()['id']}/context")
        assert "EDITED CHECKPOINT" in fresh_context.json()["current_checkpoint"]["tutor_prompt"]
    finally:
        restored = client.patch(
            f"/checkpoints/{first_checkpoint_id}",
            json={
                "kind": "teach",
                "tutor_prompt": original_prompt,
                "rubric": "",
                "pass_criteria": "The student says the passage is mostly about the fox finding a warm place to sleep.",
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


def _wolverine_id() -> str:
    students = client.get("/students").json()
    return next(student["id"] for student in students if student["slug"] == "wolverine")


def test_widget_grades_before_the_model_and_age_gate() -> None:
    storm = _storm_id()
    blocked = client.post(
        "/sessions",
        json={"student_id": storm, "lesson_plan_id": _plan_id("function-shifts"), "fresh": True},
    )
    assert blocked.status_code == 400
    assert "15" in blocked.json()["detail"]

    opened = client.post(
        "/sessions",
        json={"student_id": _wolverine_id(), "lesson_plan_id": _plan_id("function-shifts"), "fresh": True},
    )
    assert opened.status_code == 200
    assert opened.json()["lesson_title"] == "Function shifts"

    fractions = client.post(
        "/sessions",
        json={"student_id": storm, "lesson_plan_id": _plan_id("fractions"), "fresh": True},
    )
    assert fractions.status_code == 200
    body = fractions.json()
    session_id = body["id"]
    kinds = [item["kind"] for item in body["topics"][0]["checkpoints"]]
    assert kinds == ["discovery", "quiz", "teach_back"]
    assert "equal parts" in body["topics"][0]["learning_goal"].lower()
    assert body["current_block"]["kind"] == "discovery"
    assert body["current_block"]["quiz"] is None
    assert "pizza" in body["current_block"]["tutor_prompt"].lower()
    assert len(body["steps"]) == 5
    widgets = [
        checkpoint
        for topic in body["topics"]
        for checkpoint in topic["checkpoints"]
        if checkpoint["kind"] == "quiz"
    ]
    assert len(widgets) == 1

    scored = client.post(
        f"/sessions/{session_id}/turn-score",
        json={
            "rubric_met": ["fourths", "denominator"],
            "misconception": None,
            "hint_tier": "nudge",
            "advance": True,
        },
    )
    assert scored.json()["passed"] is True
    assert scored.json()["advanced"] is True

    board = client.get(f"/sessions/{session_id}/board").json()
    quiz = board["current_block"]["quiz"]
    assert quiz["type"] == "single"
    assert "answer" not in quiz
    assert all("misconception" not in choice for choice in quiz["choices"])
    assert board["current_block"]["hint_tier"] == "nudge"

    wrong = client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": "b", "explanation": "I flipped the numbers."},
    )
    assert wrong.json()["ok"] is True
    assert wrong.json()["passed"] is False
    assert "bottom number" in wrong.json()["misconception"].lower()

    hinted = client.get(f"/sessions/{session_id}/board").json()
    assert hinted["current_block"]["hint_tier"] == "analogy"

    right = client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": "a", "explanation": "Two of the three equal pieces."},
    )
    assert right.json()["passed"] is True
    assert right.json()["correct"] is True

    context = client.get(f"/sessions/{session_id}/context").json()
    assert context["current_checkpoint"]["quiz"]["answer"] == "a"
    assert context["current_checkpoint"]["widget_grade"]["passed"] is True

    moved = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["choice", "why"], "misconception": None, "hint_tier": "analogy", "advance": True},
    )
    assert moved.json()["graded_by"] == "widget"
    assert moved.json()["passed"] is True
    assert moved.json()["advanced"] is True
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "teach_back"

    prompts = client.post(
        "/sessions",
        json={"student_id": storm, "lesson_plan_id": _plan_id("super-prompts"), "fresh": True},
    )
    plan = client.get(f"/lesson-plans/{_plan_id('super-prompts')}").json()
    quiz_types = [
        checkpoint["quiz"]["type"]
        for topic in plan["topics"]
        for checkpoint in topic["checkpoints"]
        if checkpoint["quiz"]
    ]
    assert quiz_types == ["flaw", "order"]
    assert prompts.status_code == 200
    older = client.post(
        "/sessions",
        json={
            "student_id": _wolverine_id(),
            "lesson_plan_id": _plan_id("super-prompts"),
            "fresh": True,
        },
    )
    assert older.status_code == 400


def test_fractions_rewrites_in_place_under_an_open_class() -> None:
    opened = client.post(
        "/sessions",
        json={"student_id": _storm_id(), "lesson_plan_id": _plan_id("fractions"), "fresh": True},
    )
    assert opened.status_code == 200
    lesson_id = opened.json()["lesson_plan_id"]
    session_id = opened.json()["id"]
    current_id = opened.json()["current_checkpoint_id"]
    db = SessionLocal()
    try:
        plan = db.get(LessonPlan, lesson_id)
        for topic in plan.topics:
            for checkpoint in topic.checkpoints:
                checkpoint.kind = {1: "teach", 2: "practice"}.get(checkpoint.position, "quiz")
                checkpoint.quiz = None
                checkpoint.rubric_rows = []
                checkpoint.objective = None
                checkpoint.tutor_prompt = "OLD PROMPT that should be replaced."
        db.commit()
        rewritten = seed(db)
        again = seed(db)
    finally:
        db.close()
    assert rewritten["lesson_plans_rewritten"] == 1
    assert again["lesson_plans_created"] == 0
    assert again["lesson_plans_rewritten"] == 0
    board = client.get(f"/sessions/{session_id}/board")
    assert board.status_code == 200
    body = board.json()
    assert body["lesson_plan_id"] == lesson_id
    assert body["current_checkpoint_id"] == current_id
    assert body["current_block"]["kind"] == "discovery"
    assert "pizza" in body["current_block"]["tutor_prompt"].lower()
    quiz_blocks = [
        checkpoint
        for topic in body["topics"]
        for checkpoint in topic["checkpoints"]
        if checkpoint["kind"] == "quiz"
    ]
    assert len(quiz_blocks) == 1


def test_model_prompt_round_trip() -> None:
    opened = client.post(
        "/sessions",
        json={"student_id": _storm_id(), "lesson_plan_id": _plan_id("fractions"), "fresh": True},
    )
    assert opened.status_code == 200
    session_id = opened.json()["id"]
    payload = {
        "system_prompt": "You are the tutor for Storm.\n\nStay on the current block.",
        "messages": [
            {"role": "user", "content": "Hi! I'm ready to learn."},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi Storm."}]},
        ],
        "model": "gpt-4o-mini",
    }
    saved = client.post(f"/sessions/{session_id}/model-prompts", json=payload)
    assert saved.status_code == 200
    body = saved.json()
    assert body["seq"] == 1
    assert body["system_prompt"] == payload["system_prompt"]
    assert body["messages"] == payload["messages"]
    assert body["model"] == "gpt-4o-mini"
    again = client.post(
        f"/sessions/{session_id}/model-prompts",
        json={"system_prompt": "Second turn.", "messages": [{"role": "user", "content": "1/2"}], "model": "gpt-4o-mini"},
    )
    assert again.status_code == 200
    assert again.json()["seq"] == 2
    listed = client.get(f"/sessions/{session_id}/model-prompts")
    assert listed.status_code == 200
    rows = listed.json()
    assert [row["seq"] for row in rows] == [1, 2]
    assert rows[0]["messages"][1]["content"][0]["text"] == "Hi Storm."
    missing = client.get("/sessions/00000000-0000-0000-0000-000000000000/model-prompts")
    assert missing.status_code == 404
