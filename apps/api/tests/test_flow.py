"""Goal, then close. Seed inserts learners and does not write courses."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.course_io import CourseFileError, update_course_in_place
from app.database import SessionLocal
from app.main import app
from app.models import (
    Course,
    Quest,
    Session as TutorSession,
    Student,
    StudioCourse,
    StudioQuest,
    StudioQuestClose,
    StudioQuestGoal,
)
from app.prompt_loader import course_scope_on
from app.seed import seed
from app.tutor_profile import reset_default_profile

client = TestClient(app)


def setup_function() -> None:
    db = SessionLocal()
    try:
        db.execute(delete(TutorSession))
        db.commit()
        seed(db)
        reset_default_profile(db)
        db.commit()
    finally:
        db.close()


def _drop_named(name: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(Student).where(Student.display_name == name))
        db.commit()
    finally:
        db.close()


def _drop_course(code: str) -> None:
    db = SessionLocal()
    try:
        course = db.scalar(select(Course).where(Course.code == code))
        if course is None:
            return
        quest_ids = list(db.scalars(select(Quest.id).where(Quest.course_id == course.id)))
        if quest_ids:
            db.execute(delete(TutorSession).where(TutorSession.quest_id.in_(quest_ids)))
        db.delete(course)
        db.commit()
    finally:
        db.close()


def _student(slug: str) -> dict:
    students = client.get("/students").json()
    return next(student for student in students if student["slug"] == slug)


def _goals() -> list[dict]:
    return [
        {
            "position": 1,
            "learning_goal": "Name the sum.",
            "success_criterion": "States that the angles add to 180.",
        },
        {
            "position": 2,
            "learning_goal": "Use the sum.",
            "success_criterion": "Finds a missing angle.",
        },
    ]


def _essay(question: str = "") -> dict:
    questions = [{"text": question}] if question else []
    return {
        "close_style": "one",
        "answer_style": "essay",
        "choice_mode": None,
        "items": {"choices": [], "questions": questions, "selection": None},
        "intent": "",
    }


def _choice() -> dict:
    return {
        "close_style": "one",
        "answer_style": "multiple_choice",
        "choice_mode": "predefined",
        "items": {
            "choices": [
                {"text": "180 degrees", "correct": True},
                {"text": "90 degrees", "correct": False},
            ],
            "questions": [{"text": "What do the angles add to?"}],
            "selection": "single",
        },
        "intent": "",
    }


def _publish(code: str, *, audience: str = "12-14", goals: list[dict] | None = None, close: dict | None = None, title: str = "Angles") -> dict:
    payload = {
        "code": code,
        "title": title,
        "description": "Triangle angles.",
        "audience": audience,
        "quest_count": 1,
        "goals_per_quest": len(goals or _goals()),
        "quiz_minutes": 5,
        "quests": [
            {
                "code": f"{code}-Q1",
                "title": "The angles",
                "goals": goals if goals is not None else _goals(),
                "close": close if close is not None else _essay(),
            }
        ],
    }
    response = client.post("/courses/import", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _open(code: str) -> dict:
    tree = _publish(code)
    quest_id = tree["quests"][0]["id"]
    opened = client.post(
        "/sessions",
        json={"student_id": _student("storm")["id"], "quest_id": quest_id, "fresh": True},
    )
    assert opened.status_code == 200, opened.text
    return opened.json()


def _score(session_id: str, *, met: bool = True, advance: bool = True) -> dict:
    body = {
        "rubric_met": ["criterion"] if met else [],
        "misconception": None,
        "advance": advance,
    }
    response = client.post(f"/sessions/{session_id}/turn-score", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _profile(**overrides) -> dict:
    body = {
        "instructive": 3,
        "persona": "curious-co-explorer",
        "lexicon": "middle-grade-vivid",
        "voice_override": False,
        "metaphors": "playground-sports",
        "sidekick": "bumbling-partner",
        "struggle_window": "standard",
        "anti_spoiler": True,
        "one_question": True,
        "use_interests": True,
        "stay_on_course": True,
        "growth_praise": True,
    }
    body.update(overrides)
    return body


def test_health_roster_and_audience_filter() -> None:
    assert client.get("/health").json() == {"ok": True}
    roster = client.get("/students").json()
    names = [student["display_name"] for student in roster]
    assert names[:4] == ["Iron Man", "Storm", "Spider-Man", "Wolverine"]
    assert roster[1]["age_band"] == "9-11"
    try:
        younger = _publish("ZZAGE9", audience="9-11", title="Younger")
        older = _publish("ZZAGE15", audience="15-17", title="Older")
        nine = [course["code"] for course in client.get("/courses", params={"audience": "9-11"}).json()]
        older_codes = [course["code"] for course in client.get("/courses", params={"audience": "15-17"}).json()]
        assert younger["code"] in nine
        assert older["code"] not in nine
        assert older["code"] in older_codes
        assert client.get("/courses", params={"audience": "nope"}).status_code == 422
    finally:
        _drop_course("ZZAGE9")
        _drop_course("ZZAGE15")


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
        named = client.post("/students", json={"display_name": "Grace Hopper", "age": 10})
        assert named.status_code == 200
        assert named.json()["reading_level"] == "middle-grade"
        assert "Co-Explorer" in named.json()["tutor_persona"]
        patched = client.patch(
            f"/students/{named.json()['id']}",
            json={
                "reading_level": "early-reader",
                "modality": "hands-on",
                "interests": ["ships"],
                "tutor_persona": "Harbor Guide",
                "tutor_lexicon": "short concrete words",
                "tutor_metaphors": "ships and maps",
                "tutor_sidekick": "a cabin kid",
                "tutor_socratic_strictness": "balanced",
                "tutor_struggle_window": "minimum",
                "tutor_anti_spoiler": True,
                "tutor_pacing": "short-turns-one-question",
            },
        )
        assert patched.status_code == 200
        assert patched.json()["reading_level"] == "early-reader"
        assert patched.json()["interests"] == ["ships"]
        assert patched.json()["tutor_persona"] == "Harbor Guide"
        assert patched.json()["age"] == 10
        aged = client.patch(f"/students/{named.json()['id']}", json={"age": 11})
        assert aged.status_code == 200
        assert aged.json()["age"] == 11
        assert aged.json()["reading_level"] == "early-reader"
        too_young = client.patch(f"/students/{named.json()['id']}", json={"age": 3})
        assert too_young.status_code == 422
    finally:
        _drop_named("Ada Lovelace")
        _drop_named("Grace Hopper")


def test_seed_inserts_learners_and_does_not_write_courses() -> None:
    db = SessionLocal()
    try:
        before = db.scalar(select(func.count()).select_from(Course))
        first = seed(db)
        second = seed(db)
        assert first["courses_created"] == 0
        assert second["students_created"] == 0
        assert second["courses_created"] == 0
        assert db.scalar(select(func.count()).select_from(Course)) == before
        storm = db.scalar(select(Student).where(Student.slug == "storm"))
        assert storm is not None
        storm.tutor_persona = ""
        storm.tutor_lexicon = ""
        storm.tutor_metaphors = ""
        storm.tutor_sidekick = ""
        storm.tutor_pacing = ""
        db.commit()
        seed(db)
        db.refresh(storm)
        assert storm.tutor_persona == ""
        assert storm.tutor_pacing == ""
        assert storm.age == 10
        assert (storm.reading_level or "").strip()
    finally:
        db.close()


def test_reseed_keeps_a_class_on_a_course_the_seed_did_not_write() -> None:
    try:
        opened = _open("ZZKEEP")
        client.post(
            f"/sessions/{opened['id']}/messages",
            json={"role": "user", "content": "The angles add to 180.", "client_id": "zzkeep-1"},
        )
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()
        detail = client.get(f"/sessions/{opened['id']}")
        assert detail.status_code == 200
        assert any(message["content"] == "The angles add to 180." for message in detail.json()["messages"])
    finally:
        _drop_course("ZZKEEP")


def test_goals_then_an_empty_close() -> None:
    try:
        opened = _open("ZZEMPTY")
        assert opened["current_block"]["kind"] == "goal"
        assert [step["kind"] for step in opened["steps"]] == ["goal", "goal", "close"]
        assert opened["current_block"]["quiz"] is None
        first = _score(opened["id"])
        assert first["advanced"] is True
        board = client.get(f"/sessions/{opened['id']}/board").json()
        assert board["close_started"] is False
        assert board["current_block"]["kind"] == "goal"
        second = _score(opened["id"])
        assert second["advanced"] is True
        done = client.get(f"/sessions/{opened['id']}/board").json()
        assert done["status"] == "completed"
    finally:
        _drop_course("ZZEMPTY")


def test_a_quest_with_no_goals_and_an_empty_close_is_already_finished() -> None:
    try:
        tree = _publish("ZZDONE", goals=[], close=_essay())
        opened = client.post(
            "/sessions",
            json={
                "student_id": _student("storm")["id"],
                "quest_id": tree["quests"][0]["id"],
                "fresh": True,
            },
        )
        assert opened.status_code == 200
        assert opened.json()["status"] == "completed"
    finally:
        _drop_course("ZZDONE")


def test_choice_card_waits_until_the_tutor_has_spoken_on_the_close() -> None:
    try:
        tree = _publish(
            "ZZCARD",
            goals=[_goals()[0]],
            close=_choice(),
        )
        opened = client.post(
            "/sessions",
            json={
                "student_id": _student("storm")["id"],
                "quest_id": tree["quests"][0]["id"],
                "fresh": True,
            },
        )
        session_id = opened.json()["id"]
        assert opened.json()["current_block"]["quiz"] is None
        early = client.post(
            f"/sessions/{session_id}/grade-widget",
            json={"choice": "c1", "explanation": ""},
        )
        assert early.json()["ok"] is False
        scored = _score(session_id)
        assert scored["advanced"] is True
        waiting = client.get(f"/sessions/{session_id}/board").json()
        assert waiting["close_started"] is True
        assert waiting["current_block"]["kind"] == "close"
        assert waiting["current_block"]["quiz"] is None
        client.post(
            f"/sessions/{session_id}/messages",
            json={"role": "assistant", "content": "What do the angles add to?"},
        )
        asking = client.get(f"/sessions/{session_id}/board").json()
        quiz = asking["current_block"]["quiz"]
        assert quiz is not None
        assert len(quiz["choices"]) >= 2
        wrong = client.post(
            f"/sessions/{session_id}/grade-widget",
            json={"choice": "c2", "explanation": "I picked the right angle."},
        )
        assert wrong.json()["ok"] is True
        assert wrong.json()["correct"] is False
        right = client.post(
            f"/sessions/{session_id}/grade-widget",
            json={"choice": "c1", "explanation": "They add to a straight line."},
        )
        assert right.json()["correct"] is True
    finally:
        _drop_course("ZZCARD")


def test_struggle_window_then_advance() -> None:
    try:
        tree = _publish("ZZWIN", goals=[_goals()[0]], close=_essay())
        client.put("/tutor-profile", json=_profile(struggle_window="short"))
        opened = client.post(
            "/sessions",
            json={
                "student_id": _student("storm")["id"],
                "quest_id": tree["quests"][0]["id"],
                "fresh": True,
            },
        )
        session_id = opened.json()["id"]
        held = {"rubric_met": [], "misconception": None, "hint_tier": "nudge", "advance": True}
        first = client.post(f"/sessions/{session_id}/turn-score", json=held)
        assert first.json()["advanced"] is False
        revealed = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "The struggle window is over" in revealed
        second = client.post(f"/sessions/{session_id}/turn-score", json=held)
        assert second.json()["advanced"] is True
        done = client.get(f"/sessions/{session_id}/board").json()
        assert done["status"] == "completed"
    finally:
        client.put("/tutor-profile", json=_profile())
        _drop_course("ZZWIN")


def test_moves_are_rejected() -> None:
    try:
        tree = _publish("ZZMOVE", goals=[_goals()[0]])
        quest_id = tree["quests"][0]["id"]
        rejected = client.put(f"/quests/{quest_id}/beats", json={"beats": []})
        assert rejected.status_code == 422
        assert rejected.json()["detail"] == "A move is not part of this course."
    finally:
        _drop_course("ZZMOVE")


def test_in_place_update_refuses_to_drop_a_quest_with_a_class() -> None:
    try:
        tree = _publish("ZZHOLD")
        quest = tree["quests"][0]
        opened = client.post(
            "/sessions",
            json={"student_id": _student("storm")["id"], "quest_id": quest["id"], "fresh": True},
        )
        assert opened.status_code == 200
        db = SessionLocal()
        try:
            try:
                update_course_in_place(
                    db,
                    {
                        "code": "ZZHOLD",
                        "title": "Angles",
                        "description": "Triangle angles.",
                        "audience": "12-14",
                        "quest_count": 1,
                        "goals_per_quest": 1,
                        "quiz_minutes": 5,
                        "quests": [],
                    },
                )
            except CourseFileError as exc:
                assert "still has classes" in exc.message
            else:
                raise AssertionError("the quest with a class was dropped")
        finally:
            db.close()
    finally:
        _drop_course("ZZHOLD")


def test_one_tutor_profile_applies_to_every_student() -> None:
    current = client.get("/tutor-profile")
    assert current.status_code == 200
    assert current.json()["instructive"] == 3
    rejected = client.put("/tutor-profile", json=_profile(persona="wizard"))
    assert rejected.status_code == 422
    try:
        tree = _publish("ZZVOICE", goals=[_goals()[0]], title="Voice")
        overridden = client.put(
            "/tutor-profile",
            json=_profile(
                persona="debate-moderator",
                lexicon="early-concrete",
                voice_override=True,
                instructive=1,
                struggle_window="short",
                metaphors="none",
                sidekick="off",
            ),
        )
        assert overridden.status_code == 200
        storm = _student("storm")
        opened = client.post(
            "/sessions",
            json={"student_id": storm["id"], "quest_id": tree["quests"][0]["id"], "fresh": True},
        )
        session_id = opened.json()["id"]
        prompt = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "debate moderator" in prompt.lower()
        patched = client.patch(
            f"/students/{storm['id']}",
            json={"tutor_persona": "Harbor Guide", "tutor_struggle_window": "long"},
        )
        assert patched.status_code == 200
        again = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "Harbor Guide" not in again
        assert "debate moderator" in again.lower()
        other = client.post(
            "/sessions",
            json={
                "student_id": _student("wolverine")["id"],
                "quest_id": tree["quests"][0]["id"],
                "fresh": True,
            },
        )
        other_prompt = client.get(f"/sessions/{other.json()['id']}/prompt").json()["system_prompt"]
        assert "debate moderator" in other_prompt.lower()
    finally:
        client.put("/tutor-profile", json=_profile())
        _drop_course("ZZVOICE")


def test_stay_on_course_rule_follows_the_profile_switch() -> None:
    class OlderRow:
        pass

    class BlankRow:
        stay_on_course = None

    class OffRow:
        stay_on_course = False

    assert course_scope_on(OlderRow()) is True
    assert course_scope_on(BlankRow()) is True
    assert course_scope_on(OffRow()) is False
    try:
        tree = _publish("ZZSTAY", title="Triangle Angles")
        opened = client.post(
            "/sessions",
            json={
                "student_id": _student("storm")["id"],
                "quest_id": tree["quests"][0]["id"],
                "fresh": True,
            },
        )
        session_id = opened.json()["id"]
        on = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "Stay on Triangle Angles." in on.split("Layer 1", 1)[0]
        assert "and quest The angles" in on
        assert "Walk these goals in order" in on
        assert "Goal 1:" in on
        assert "Goal 2:" in on
        assert "Close: No questions." in on
        assert "Teach, then ask." in on
        saved = client.put("/tutor-profile", json=_profile(stay_on_course=False))
        assert saved.json()["stay_on_course"] is False
        off = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "Stay on Triangle Angles." not in off
        assert "If they wander off, answer in one sentence and come back." in off
    finally:
        client.put("/tutor-profile", json=_profile())
        _drop_course("ZZSTAY")


def test_model_prompt_round_trip() -> None:
    try:
        opened = _open("ZZPROMPT")
        first = client.post(
            f"/sessions/{opened['id']}/messages",
            json={"role": "user", "content": "Hi! I'm ready to learn.", "client_id": "turn-1"},
        )
        saved = client.post(
            f"/sessions/{opened['id']}/model-prompts",
            json={
                "system_prompt": "Layer 1\n\nLayer 7",
                "messages": [{"role": "user", "content": "Hi! I'm ready to learn."}],
                "model": "gpt-4o-mini",
                "message_id": first.json()["id"],
            },
        )
        assert saved.status_code == 200
        assert saved.json()["model"] == "gpt-4o-mini"
        detail = client.get(f"/sessions/{opened['id']}").json()
        assert detail["prompts"][0]["message_id"] == first.json()["id"]
        assert detail["current_goal_id"]
        assert detail["close_started"] is False
    finally:
        _drop_course("ZZPROMPT")


def test_close_question_index_migration_keeps_chats() -> None:
    text = Path(__file__).resolve().parents[1].joinpath(
        "alembic", "versions", "015_close_question_index.py"
    ).read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert "close_question_index" in upgrade
    assert "DELETE" not in upgrade.upper()
    assert "drop_table" not in upgrade


def _two_questions() -> dict:
    return {
        "close_style": "several",
        "answer_style": "mixed",
        "choice_mode": "predefined",
        "items": [],
        "intent": "",
        "selection": None,
        "questions": [
            {
                "text": "What do the angles add to?",
                "kind": "single",
                "choices": [
                    {"text": "180 degrees", "correct": True},
                    {"text": "90 degrees", "correct": False},
                ],
            },
            {
                "text": "Which shape has three sides?",
                "kind": "single",
                "choices": [
                    {"text": "A triangle", "correct": True},
                    {"text": "A square", "correct": False},
                ],
            },
        ],
    }


def test_import_copies_each_close_question() -> None:
    db = SessionLocal()
    studio_id = None
    try:
        studio = StudioCourse(
            code="ZZQIMP",
            title="Separate questions",
            audience="12-14",
            theme="Triangle angles for learners aged 12 to 14.",
            quest_count=1,
            goals_per_quest=1,
            quiz_minutes=5,
        )
        db.add(studio)
        db.flush()
        quest = StudioQuest(course_id=studio.id, code="ZZQIMP-Q1", position=1, title="Angles")
        db.add(quest)
        db.flush()
        quest.goals.append(
            StudioQuestGoal(
                position=1,
                learning_goal="Name the sum.",
                success_criterion="States that the angles add to 180.",
            )
        )
        quest.close = StudioQuestClose(
            close_style="several",
            answer_style="mixed",
            choice_mode="predefined",
            items={
                "choices": [],
                "questions": _two_questions()["questions"]
                + [
                    {"text": "Why do the angles add to 180?", "kind": "essay", "choices": []},
                    {
                        "text": "Which of these are polygons?",
                        "kind": "multi",
                        "choices": [
                            {"text": "Triangle", "correct": True},
                            {"text": "Circle", "correct": False},
                            {"text": "Square", "correct": True},
                        ],
                    },
                ],
            },
            intent="",
        )
        db.commit()
        studio_id = str(studio.id)
    finally:
        db.close()
    try:
        imported = client.post("/courses/import-studio", json={"studio_course_id": studio_id})
        assert imported.status_code == 200, imported.text
        questions = imported.json()["quests"][0]["close"]["questions"]
        assert imported.json()["quests"][0]["close"]["items"] == []
        assert [question["text"] for question in questions] == [
            "What do the angles add to?",
            "Which shape has three sides?",
            "Why do the angles add to 180?",
            "Which of these are polygons?",
        ]
        assert [question["kind"] for question in questions] == ["multiple", "multiple", "single", "multiple"]
        assert questions[0]["choices"][0] == {"text": "180 degrees", "correct": True}
        assert questions[1]["choices"][1]["text"] == "A square"
        assert questions[2]["choices"] == []
        assert [choice["correct"] for choice in questions[3]["choices"]] == [True, False, False]
    finally:
        _drop_course("ZZQIMP")
        db = SessionLocal()
        try:
            if studio_id is not None:
                row = db.get(StudioCourse, studio_id)
                if row is not None:
                    db.delete(row)
                    db.commit()
        finally:
            db.close()


def test_tutor_asks_close_questions_one_at_a_time() -> None:
    try:
        tree = _publish("ZZASK", goals=[_goals()[0]], close=_two_questions())
        opened = client.post(
            "/sessions",
            json={"student_id": _student("storm")["id"], "quest_id": tree["quests"][0]["id"], "fresh": True},
        )
        assert opened.status_code == 200, opened.text
        session_id = opened.json()["id"]
        assert _score(session_id)["advanced"] is True
        client.post(
            f"/sessions/{session_id}/messages",
            json={"role": "assistant", "content": "What do the angles add to?"},
        )
        asking = client.get(f"/sessions/{session_id}/board").json()
        quiz = asking["current_block"]["quiz"]
        assert asking["current_block"]["objective"] == "What do the angles add to?"
        assert [choice["text"] for choice in quiz["choices"]] == ["180 degrees", "90 degrees"]
        first_prompt = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        close_line = first_prompt.split("Close:", 1)[1]
        assert "What do the angles add to?" in close_line
        assert "Which shape has three sides?" not in close_line
        assert "Pick one answer on the card" in first_prompt
        assert "Your reply is exactly this question" not in first_prompt
        wrong = client.post(
            f"/sessions/{session_id}/grade-widget",
            json={"choice": "c2", "explanation": "I picked the right angle."},
        )
        assert wrong.json()["correct"] is False
        assert wrong.json()["score"] == 0
        assert wrong.json()["feedback"] == "They picked 90 degrees. It does not answer the question."
        missed_prompt = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "They picked 90 degrees" in missed_prompt
        assert "Do not repeat the question" in missed_prompt
        assert "Your reply is exactly this question" not in missed_prompt
        right = client.post(
            f"/sessions/{session_id}/grade-widget",
            json={"choice": "c1", "explanation": "They add to a straight line."},
        )
        assert right.json()["correct"] is True
        assert right.json()["score"] == 1
        assert right.json()["feedback"] == "They picked 180 degrees. It answers the question."
        moved = client.post(
            f"/sessions/{session_id}/turn-score",
            json={"rubric_met": ["criterion"], "misconception": None, "advance": True},
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["advanced"] is True
        assert moved.json()["score"] == 1
        client.post(
            f"/sessions/{session_id}/messages",
            json={"role": "assistant", "content": "Which shape has three sides?"},
        )
        second = client.get(f"/sessions/{session_id}/board").json()
        second_quiz = second["current_block"]["quiz"]
        assert second["current_block"]["objective"] == "Which shape has three sides?"
        assert [choice["text"] for choice in second_quiz["choices"]] == ["A triangle", "A square"]
        second_prompt = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        second_close = second_prompt.split("Close:", 1)[1]
        assert "Which shape has three sides?" in second_close
        assert "180 degrees" not in second_close
        again = client.post(
            f"/sessions/{session_id}/grade-widget",
            json={"choice": "c1", "explanation": "A triangle has three sides."},
        )
        assert again.json()["correct"] is True
        assert again.json()["score"] == 2
        finished = client.post(
            f"/sessions/{session_id}/turn-score",
            json={"rubric_met": ["criterion"], "misconception": None, "advance": True},
        )
        assert finished.json()["advanced"] is True
        assert client.get(f"/sessions/{session_id}/board").json()["status"] == "completed"

        essay = _publish(
            "ZZTYPE",
            goals=[_goals()[0]],
            close={
                "close_style": "one",
                "answer_style": "essay",
                "choice_mode": None,
                "items": [],
                "intent": "",
                "questions": [{"text": "Explain the angle sum.", "kind": "essay", "choices": []}],
            },
        )
        typed = client.post(
            "/sessions",
            json={"student_id": _student("storm")["id"], "quest_id": essay["quests"][0]["id"], "fresh": True},
        )
        typed_id = typed.json()["id"]
        assert _score(typed_id)["advanced"] is True
        client.post(
            f"/sessions/{typed_id}/messages",
            json={"role": "assistant", "content": "Explain the angle sum."},
        )
        board = client.get(f"/sessions/{typed_id}/board").json()
        assert board["current_block"]["quiz"] is None
        assert board["current_block"]["objective"] == "Explain the angle sum."
        typed_prompt = client.get(f"/sessions/{typed_id}/prompt").json()["system_prompt"]
        assert "Explain the angle sum." in typed_prompt
        assert "States that the angles add to 180." in typed_prompt
        assert "Pick one answer on the card" not in typed_prompt
        assert "Do not offer choices" in typed_prompt
        client.post(
            f"/sessions/{typed_id}/messages",
            json={"role": "user", "content": "The angles make a straight line."},
        )
        scored = client.post(
            f"/sessions/{typed_id}/turn-score",
            json={"rubric_met": ["criterion"], "misconception": None, "advance": True},
        )
        assert scored.status_code == 200, scored.text
        assert scored.json()["passed"] is True
        assert scored.json()["score"] == 1
        assert client.get(f"/sessions/{typed_id}/board").json()["status"] == "completed"
    finally:
        _drop_course("ZZASK")
        _drop_course("ZZTYPE")


def test_tutor_revision_lifts_quests_and_keeps_chat_tables() -> None:
    text = Path(__file__).resolve().parents[1].joinpath(
        "alembic", "versions", "013_tutor_quests_on_course.py"
    ).read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert 'op.drop_table("units")' in upgrade
    assert '"quest_goals"' in upgrade
    assert '"quest_closes"' in upgrade
    assert "DELETE FROM sessions" not in upgrade
    assert "DELETE FROM messages" not in upgrade


def test_import_copies_a_draft_and_remove_keeps_the_chat() -> None:
    db = SessionLocal()
    studio_id = None
    try:
        studio = StudioCourse(
            code="ZZIMP",
            title="Imported angles",
            audience="12-14",
            description="",
            theme="Triangle angles for learners aged 12 to 14.",
            focus="Why a triangle's angles add to 180 degrees.",
            quest_count=4,
            goals_per_quest=2,
            quiz_minutes=10,
            preferences={
                "quest_count": 4,
                "goals_per_quest": 2,
                "quiz_minutes": 10,
                "audience": "12-14",
                "theme": "Triangle angles for learners aged 12 to 14.",
            },
        )
        db.add(studio)
        db.flush()
        quest = StudioQuest(course_id=studio.id, code="ZZIMP-Q1", position=1, title="Angles")
        db.add(quest)
        db.flush()
        quest.goals.append(
            StudioQuestGoal(
                position=1,
                learning_goal="Understand that the angles of a triangle add to 180 degrees.",
                success_criterion="States that the three angles add to 180 degrees.",
            )
        )
        quest.goals.append(
            StudioQuestGoal(
                position=2,
                learning_goal="Name an exterior angle.",
                success_criterion="Points to an exterior angle on a drawn triangle.",
            )
        )
        quest.close = StudioQuestClose(
            close_style="one",
            answer_style="multiple_choice",
            choice_mode="predefined",
            items={
                "choices": [
                    {"text": "180 degrees", "correct": True},
                    {"text": "90 degrees", "correct": False},
                ],
                "questions": [{"text": "What do the angles add to?"}],
                "selection": "single",
            },
            intent="",
        )
        db.commit()
        studio_id = str(studio.id)
    finally:
        db.close()

    try:
        imported = client.post("/courses/import-studio", json={"studio_course_id": studio_id})
        assert imported.status_code == 200, imported.text
        body = imported.json()
        assert body["code"] == "ZZIMP"
        assert body["description"] == "Triangle angles for learners aged 12 to 14."
        assert body["audience"] == "12-14"
        assert body["quest_count"] == 4
        assert body["goals_per_quest"] == 2
        assert body["quiz_minutes"] == 10
        quest_body = body["quests"][0]
        assert [goal["learning_goal"] for goal in quest_body["goals"]] == [
            "Understand that the angles of a triangle add to 180 degrees.",
            "Name an exterior angle.",
        ]
        assert quest_body["close"]["answer_style"] == "multiple_choice"
        assert quest_body["close"]["selection"] is None
        assert quest_body["close"]["questions"][0]["kind"] == "multiple"
        assert quest_body["close"]["questions"][0]["text"] == "What do the angles add to?"
        kept = client.get(f"/studio/courses/{studio_id}")
        assert kept.status_code == 200

        opened = client.post(
            "/sessions",
            json={
                "student_id": _student("storm")["id"],
                "quest_id": quest_body["id"],
                "fresh": True,
            },
        )
        session_id = opened.json()["id"]
        client.post(
            f"/sessions/{session_id}/messages",
            json={"role": "user", "content": "The angles add to 180.", "client_id": "zzimp-keep"},
        )
        prompt = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "Walk these goals in order" in prompt
        assert "Close: Multiple choice." in prompt
        assert "What do the angles add to?" not in prompt.split("Close:", 1)[1]
        removed = client.post(f"/courses/{body['id']}/remove")
        assert removed.status_code == 204
        detail = client.get(f"/sessions/{session_id}")
        assert detail.status_code == 200
        assert any(message["content"] == "The angles add to 180." for message in detail.json()["messages"])
        assert client.get(f"/studio/courses/{studio_id}").status_code == 200
    finally:
        _drop_course("ZZIMP")
        db = SessionLocal()
        try:
            if studio_id is not None:
                row = db.get(StudioCourse, studio_id)
                if row is not None:
                    db.delete(row)
                    db.commit()
        finally:
            db.close()
