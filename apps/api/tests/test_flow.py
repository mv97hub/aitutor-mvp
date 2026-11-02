from sqlalchemy import delete, func, select

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Beat, Course, Quest, Session as TutorSession, Student, Unit
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


def _drop_named(name: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(Student).where(Student.display_name == name))
        db.commit()
    finally:
        db.close()


def _student(slug: str) -> dict:
    students = client.get("/students").json()
    return next(student for student in students if student["slug"] == slug)


def _quest(code: str) -> dict:
    courses = client.get("/courses").json()
    for course in courses:
        quests = client.get(f"/courses/{course['id']}/quests").json()
        for quest in quests:
            if quest["code"] == code:
                return quest
    raise AssertionError(code)


def test_seed_is_idempotent_and_counts_the_map() -> None:
    db = SessionLocal()
    try:
        again = seed(db)
        students = db.scalar(select(func.count()).select_from(Student))
        courses = db.scalar(select(func.count()).select_from(Course))
        quests = db.scalar(select(func.count()).select_from(Quest))
        beats = db.scalar(select(func.count()).select_from(Beat))
        rome = db.scalar(select(func.count()).select_from(Quest).join(Unit).join(Course).where(Course.code == "rome"))
        ages = {student.slug: student.age for student in db.scalars(select(Student)).all()}
        storm = db.scalar(select(Student).where(Student.slug == "storm"))
        persona = storm.tutor_persona
        interests = list(storm.interests)
    finally:
        db.close()
    assert again == {"students_created": 0, "courses_created": 0}
    assert students == 4
    assert courses == 3
    assert quests == 48
    assert beats == 192
    assert rome == 16
    assert ages["storm"] == 10
    assert ages["wolverine"] == 16
    assert "Co-Explorer" in persona
    assert interests == ["weather", "leadership"]


def test_health_roster_and_age_filter() -> None:
    assert client.get("/health").json() == {"ok": True}
    roster = client.get("/students").json()
    assert [student["display_name"] for student in roster] == [
        "Iron Man",
        "Storm",
        "Spider-Man",
        "Wolverine",
    ]
    assert roster[1]["age_band"] == "9-11"
    assert client.get("/courses", params={"age_band": "9-11"}).json()[0]["code"] == "rome"
    assert client.get("/courses", params={"age_band": "15-17"}).json()[0]["code"] == "macro"
    assert len(client.get("/courses").json()) == 3


def test_create_student_keeps_layer_2_apart_from_tutor_settings() -> None:
    _drop_named("Ada Lovelace")
    created = client.post(
        "/students",
        json={
            "display_name": "Ada Lovelace",
            "age": 12,
            "reading_level": "grade-level",
            "modality": "visual",
            "interests": ["patterns"],
            "tutor_persona": "Custom Commander",
            "tutor_lexicon": "visual-spatial",
            "tutor_metaphors": "hinges",
            "tutor_sidekick": "a rookie",
            "tutor_socratic_strictness": "balanced",
            "tutor_struggle_window": "minimum",
            "tutor_anti_spoiler": True,
            "tutor_pacing": "short-turns-one-question",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["slug"] == "ada-lovelace"
    assert body["age_band"] == "12-14"
    assert body["reading_level"] == "grade-level"
    assert body["interests"] == ["patterns"]
    assert body["tutor_persona"] == "Custom Commander"
    try:
        blank = client.post("/students", json={"display_name": "   ", "age": 10})
        assert blank.status_code == 422
        defaults = client.get("/profile-defaults", params={"age": 16}).json()
        assert "Moderator" in defaults["tutor_persona"]
        assert defaults["reading_level"] == "high-school"
    finally:
        _drop_named("Ada Lovelace")


def test_age_gate_and_any_quest_in_band() -> None:
    storm = _student("storm")["id"]
    wolverine = _student("wolverine")["id"]
    macro = _quest("MAC-U4-Q1")
    branch = _quest("ROM-U4-Q2A")
    blocked = client.post("/sessions", json={"student_id": storm, "quest_id": macro["id"], "fresh": True})
    assert blocked.status_code == 400
    assert "15-17" in blocked.json()["detail"]
    opened = client.post("/sessions", json={"student_id": storm, "quest_id": branch["id"], "fresh": True})
    assert opened.status_code == 200
    body = opened.json()
    assert body["quest_code"] == "ROM-U4-Q2A"
    assert body["current_block"]["kind"] == "mystery_hook"
    assert len(body["steps"]) == 4
    older = client.post(
        "/sessions",
        json={"student_id": wolverine, "quest_id": _quest("ROM-U2-Q1")["id"], "fresh": True},
    )
    assert older.status_code == 400


def test_widget_grades_before_the_model_and_prompt_has_seven_layers() -> None:
    storm = _student("storm")["id"]
    quest = _quest("ROM-U2-Q1")
    opened = client.post("/sessions", json={"student_id": storm, "quest_id": quest["id"], "fresh": True})
    assert opened.status_code == 200
    session_id = opened.json()["id"]
    assert "veto" in opened.json()["current_block"]["tutor_prompt"].lower()
    assert opened.json()["current_block"]["quiz"] is None

    prompt = client.get(f"/sessions/{session_id}/prompt", params={"kickoff": True}).json()
    assert "Layer 7 — Memory" in prompt["system_prompt"]
    assert "Curious Co-Explorer" in prompt["system_prompt"]
    assert "weather" in prompt["system_prompt"]
    assert prompt["temperature"] == 0.4
    assert "reply" in prompt["response_schema"]["properties"]

    scored = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["advantage", "problem"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert scored.json()["passed"] is True
    assert scored.json()["advanced"] is True
    board = client.get(f"/sessions/{session_id}/board").json()
    quiz = board["current_block"]["quiz"]
    assert quiz["type"] == "single"
    assert "answer" not in quiz
    wrong = client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": "greece", "explanation": "I asked another country."},
    )
    assert wrong.json()["passed"] is False
    assert "greece" in wrong.json()["misconception"].lower()
    right = client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": "walkout", "explanation": ""},
    )
    assert right.json()["passed"] is True
    moved = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["walkout"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert moved.json()["graded_by"] == "widget"
    assert moved.json()["advanced"] is True
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "diagnostic_gate"


def test_four_beats_finish_the_quest() -> None:
    storm = _student("storm")["id"]
    opened = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("ROM-U1-Q1")["id"], "fresh": True},
    )
    session_id = opened.json()["id"]
    for rubric in (
        ["story", "clue"],
        ["choice"],
        ["keep", "trust"],
        ["myth", "clue"],
    ):
        if rubric == ["choice"]:
            graded = client.post(
                f"/sessions/{session_id}/grade-widget",
                json={"choice": "wall", "explanation": ""},
            )
            assert graded.json()["passed"] is True
        result = client.post(
            f"/sessions/{session_id}/turn-score",
            json={"rubric_met": rubric, "misconception": None, "hint_tier": "nudge", "advance": True},
        )
        assert result.json()["ok"] is True
    assert client.get(f"/sessions/{session_id}/board").json()["status"] == "completed"


def test_import_rejects_the_field_and_replaces_by_code() -> None:
    bad = {
        "code": "trial",
        "title": "Trial course",
        "age_band": "12-14",
        "standards_alignment": "A local standard.",
        "competency_dictionary": [{"code": "idea", "description": "One idea."}],
        "units": [
            {
                "number": 1,
                "title": "Only unit",
                "enduring_understanding": "One idea is enough to practice the file.",
                "continuity_summary": "This unit stands alone. The next file can replace it.",
                "quests": [
                    {
                        "code": "TRY-Q1",
                        "title": "Try the file",
                        "quest_type": "core",
                        "prerequisite_codes": [],
                        "competency_tags": ["idea"],
                        "dinner_prompt": "Ask what the file was for.",
                        "beats": _four_beats(),
                    }
                ],
            }
        ],
    }
    bad["units"][0]["quests"][0]["beats"][0]["rubric"] = [
        {"id": "a", "text": "Names a reason.", "weight": 40},
        {"id": "b", "text": "Names a second reason.", "weight": 40},
    ]
    rejected = client.post("/courses/import", json=bad)
    assert rejected.status_code == 422
    assert "beats[0].rubric" in rejected.json()["detail"]

    good = bad
    good["units"][0]["quests"][0]["beats"] = _four_beats()
    created = client.post("/courses/import", json=good)
    assert created.status_code == 200
    assert created.json()["code"] == "trial"
    try:
        good["title"] = "Trial course replaced"
        replaced = client.post("/courses/import", json=good)
        assert replaced.status_code == 200
        assert replaced.json()["title"] == "Trial course replaced"
        codes = [course["code"] for course in client.get("/courses").json()]
        assert codes.count("trial") == 1
    finally:
        course_id = next(course["id"] for course in client.get("/courses").json() if course["code"] == "trial")
        assert client.delete(f"/courses/{course_id}").status_code == 204


def _four_beats() -> list[dict]:
    roles = ["mystery_hook", "interactive_toy", "diagnostic_gate", "feynman_flip"]
    beats = []
    for role in roles:
        widget = None
        rubric = [
            {"id": "a", "text": "Names the first part.", "weight": 50},
            {"id": "b", "text": "Names the second part.", "weight": 50},
        ]
        if role == "interactive_toy":
            rubric = [{"id": "choice", "text": "Picks the matching choice.", "weight": 100}]
            widget = {
                "type": "single",
                "prompt": "Which choice matches?",
                "choices": [
                    {"id": "yes", "text": "The matching choice.", "misconception": ""},
                    {"id": "no", "text": "A different idea.", "misconception": "That idea is not this quest."},
                ],
                "answer": "yes",
                "explain": False,
                "misconception": "Match the question.",
            }
        beats.append(
            {
                "role": role,
                "bloom_level": "understand",
                "cognitive_load": "low",
                "prompt": f"Work the {role.replace('_', ' ')}.",
                "rubric": rubric,
                "misconception_map": [
                    {"id": "miss", "trap": "A nearby idea answers it.", "note": "Stay on this beat."}
                ],
                "hint_ladder": {
                    "nudge": "What is the question asking?",
                    "analogy": "A small picture of the same idea.",
                    "scaffold": "The first part is ____.",
                },
                "widget": widget,
            }
        )
    return beats


def test_model_prompt_round_trip() -> None:
    storm = _student("storm")["id"]
    opened = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("ROM-U1-Q1")["id"], "fresh": True},
    )
    session_id = opened.json()["id"]
    first = client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "user", "content": "Hi! I'm ready to learn.", "client_id": "turn-1"},
    )
    saved = client.post(
        f"/sessions/{session_id}/model-prompts",
        json={
            "system_prompt": "Layer 1\n\nLayer 7",
            "messages": [{"role": "user", "content": "Hi! I'm ready to learn."}],
            "model": "gpt-4o-mini",
            "message_id": first.json()["id"],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["model"] == "gpt-4o-mini"
    detail = client.get(f"/sessions/{session_id}").json()
    assert detail["prompts"][0]["message_id"] == first.json()["id"]
    assert detail["quest"]["code"] == "ROM-U1-Q1"
