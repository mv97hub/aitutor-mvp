import copy

from sqlalchemy import delete, func, select

from fastapi.testclient import TestClient

from app.course_io import CourseFileError, update_course_in_place
from app.curriculum import COURSES
from app.database import SessionLocal
from app.main import app
from app.models import Beat, Course, Message, Quest, Session as TutorSession, Student, Unit
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
        macro_units = db.scalar(
            select(func.count()).select_from(Unit).join(Course).where(Course.code == "macro")
        )
        ages = {student.slug: student.age for student in db.scalars(select(Student)).all()}
        storm = db.scalar(select(Student).where(Student.slug == "storm"))
        persona = storm.tutor_persona
        interests = list(storm.interests)
    finally:
        db.close()
    assert again == {"students_created": 0, "courses_created": 0}
    assert students == 4
    assert courses == 3
    assert quests == 50
    assert beats > 48
    assert rome == 16
    assert macro_units == 6
    assert ages["storm"] == 10
    assert ages["wolverine"] == 16
    assert "Co-Explorer" in persona
    assert interests == ["weather", "leadership"]


def test_reseed_keeps_sessions_and_refreshes_quest_text() -> None:
    db = SessionLocal()
    try:
        quest = db.scalar(select(Quest).where(Quest.code == "ROM-U2-Q1"))
        beat = db.scalar(select(Beat).where(Beat.quest_id == quest.id, Beat.position == 1))
        quest_id = quest.id
        beat_id = beat.id
        original_goal = quest.learning_goal
        original_prompt = beat.prompt
        quest.learning_goal = "Edited goal that the seed must replace."
        beat.prompt = "Edited prompt that the seed must replace."
        student = db.scalar(select(Student).where(Student.slug == "storm"))
        tutor_session = TutorSession(
            student_id=student.id,
            quest_id=quest.id,
            current_beat_id=beat.id,
            status="in_progress",
        )
        db.add(tutor_session)
        db.flush()
        message = Message(
            session_id=tutor_session.id,
            role="user",
            content="Two consuls can veto each other.",
            seq=1,
        )
        db.add(message)
        db.commit()
        session_id = tutor_session.id
        message_id = message.id

        again = seed(db)

        kept_session = db.get(TutorSession, session_id)
        kept_message = db.get(Message, message_id)
        refreshed = db.get(Quest, quest_id)
        refreshed_beat = db.get(Beat, beat_id)
        assert again == {"students_created": 0, "courses_created": 0}
        assert kept_session.quest_id == quest_id
        assert kept_session.current_beat_id == beat_id
        assert kept_message.session_id == session_id
        assert kept_message.content == "Two consuls can veto each other."
        assert refreshed.learning_goal == original_goal
        assert refreshed_beat.id == beat_id
        assert refreshed_beat.prompt == original_prompt
    finally:
        db.close()


def test_in_place_update_refuses_to_drop_a_quest_with_a_class() -> None:
    db = SessionLocal()
    try:
        payload = copy.deepcopy(next(course for course in COURSES if course["code"] == "rome"))
        for unit in payload["units"]:
            unit["quests"] = [quest for quest in unit["quests"] if quest["code"] != "ROM-U4-BOSS"]
        quest = db.scalar(select(Quest).where(Quest.code == "ROM-U4-BOSS"))
        quest_id = quest.id
        beat_id = db.scalar(
            select(Beat.id).where(Beat.quest_id == quest.id).order_by(Beat.position)
        )
        student = db.scalar(select(Student).where(Student.slug == "storm"))
        tutor_session = TutorSession(
            student_id=student.id,
            quest_id=quest.id,
            current_beat_id=beat_id,
            status="in_progress",
        )
        db.add(tutor_session)
        db.commit()
        session_id = tutor_session.id
        refused = False
        try:
            update_course_in_place(db, payload)
        except CourseFileError as exc:
            refused = True
            assert exc.field == "quests"
            assert "ROM-U4-BOSS" in exc.message
        assert refused
        assert db.get(TutorSession, session_id) is not None
        assert db.get(Quest, quest_id) is not None
    finally:
        db.close()


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
    finally:
        _drop_named("Ada Lovelace")
        _drop_named("Grace Hopper")


def test_any_age_can_open_any_course() -> None:
    storm = _student("storm")["id"]
    wolverine = _student("wolverine")["id"]
    courses = {course["code"]: course["age_band"] for course in client.get("/courses").json()}
    assert courses["rome"] == "9-11"
    assert courses["geometry"] == "12-14"
    assert courses["macro"] == "15-17"
    macro = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("MAC-U5-Q1")["id"], "fresh": True},
    )
    assert macro.status_code == 200
    assert macro.json()["quest_code"] == "MAC-U5-Q1"
    rome = client.post(
        "/sessions",
        json={"student_id": wolverine, "quest_id": _quest("ROM-U2-Q1")["id"], "fresh": True},
    )
    assert rome.status_code == 200
    assert rome.json()["course_code"] == "rome"
    geometry = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("GEO-U2-Q2")["id"], "fresh": True},
    )
    assert geometry.status_code == 200
    assert geometry.json()["course_code"] == "geometry"
    branch = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("ROM-U4-Q2A")["id"], "fresh": True},
    )
    assert branch.status_code == 200
    opened = branch.json()
    detail = client.get(f"/quests/{_quest('ROM-U4-Q2A')['id']}").json()
    assert opened["current_block"]["kind"] == detail["beats"][0]["role"]
    assert len(opened["steps"]) == len(detail["beats"])
    assert opened["current_block"]["kind"] != "mystery_hook"


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
    assert "curious co-explorer" in prompt["system_prompt"]
    assert "weather" in prompt["system_prompt"]
    assert "what finished work looks like" in prompt["system_prompt"]
    assert "Do not invent a different topic" in prompt["system_prompt"]
    assert "Do not preview later moves" in prompt["system_prompt"]
    assert "494" not in prompt["system_prompt"]
    assert "worked answer" not in prompt["system_prompt"].lower()
    assert prompt["temperature"] == 0.4
    assert "reply" in prompt["response_schema"]["properties"]

    scored = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["advantage", "problem"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert scored.json()["passed"] is True
    assert scored.json()["advanced"] is True
    waiting = client.get(f"/sessions/{session_id}/board").json()
    assert waiting["current_block"]["kind"] == "try"
    assert waiting["current_block"]["quiz"] is None
    _speak(session_id, "try")
    early = client.get(f"/sessions/{session_id}/board").json()
    assert early["current_block"]["kind"] == "try"
    assert early["current_block"]["quiz"] is None
    _answer_in_words(session_id, "try")
    board = client.get(f"/sessions/{session_id}/board").json()
    quiz = board["current_block"]["quiz"]
    assert quiz["type"] == "single"
    assert "answer" not in quiz
    wrong = client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": "walkout", "explanation": "They left the city."},
    )
    assert wrong.json()["passed"] is False
    assert "later" in wrong.json()["misconception"].lower()
    right = client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": "deadlock", "explanation": ""},
    )
    assert right.json()["passed"] is True
    moved = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["choice"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert moved.json()["graded_by"] == "widget"
    assert moved.json()["advanced"] is True
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "name"


def test_choice_widget_waits_until_the_tutor_has_spoken_for_the_move() -> None:
    storm = _student("storm")["id"]
    opened = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("ROM-U1-Q1")["id"], "fresh": True},
    )
    session_id = opened.json()["id"]
    assert opened.json()["current_block"]["kind"] == "try"
    assert opened.json()["current_block"]["quiz"] is None

    kickoff = client.get(f"/sessions/{session_id}/prompt", params={"kickoff": True}).json()
    assert "what finished work looks like" in kickoff["system_prompt"]
    assert "choice widget is not on screen" in kickoff["system_prompt"]
    assert "Invite them to choose" not in kickoff["system_prompt"]
    assert "pottery" not in kickoff["system_prompt"].lower()
    assert "one question" in kickoff["system_prompt"].lower()
    assert "short teaching of the first idea" in kickoff["system_prompt"]
    assert "First idea to teach:" in kickoff["system_prompt"]

    client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "user", "content": "Hi! I'm ready to learn.", "client_id": "open-user"},
    )
    held = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["choice"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert held.json()["graded_by"] == "opening"
    assert held.json()["advanced"] is False
    board = client.get(f"/sessions/{session_id}/board").json()
    assert board["current_block"]["kind"] == "try"
    assert board["current_block"]["quiz"] is None
    assert board["beats"][0]["latest_result"] is None

    client.post(
        f"/sessions/{session_id}/messages",
        json={
            "role": "assistant",
            "content": "The goal is to tell a legend from a clue. A story can carry a meaning, and a find can be checked.",
            "client_id": "open-tutor",
        },
    )
    taught = client.get(f"/sessions/{session_id}/board").json()
    assert taught["current_block"]["kind"] == "try"
    assert taught["current_block"]["quiz"] is None
    still_held = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
    assert "Invite them to choose" not in still_held
    assert "not on screen yet" in still_held
    _answer_in_words(session_id, "open")
    shown = client.get(f"/sessions/{session_id}/board").json()
    assert shown["current_block"]["quiz"]["type"] == "multi"
    assert "answer" not in shown["current_block"]["quiz"]
    follow = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
    assert "Invite them to choose" in follow
    assert "own words" in follow
    assert "Correct answer, for you only" not in follow

    banker = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("MAC-U5-Q1")["id"], "fresh": True},
    )
    assert banker.json()["current_block"]["kind"] == "try"
    assert banker.json()["current_block"]["quiz"] is None
    banker_id = banker.json()["id"]
    banker_kickoff = client.get(f"/sessions/{banker_id}/prompt", params={"kickoff": True}).json()
    assert "FOMC" not in banker_kickoff["system_prompt"]
    assert "simultaneously cure" not in banker_kickoff["system_prompt"].lower()
    _speak(banker_id, "bank")
    assert client.get(f"/sessions/{banker_id}/board").json()["current_block"]["quiz"] is None
    _answer_in_words(banker_id, "bank")
    ready = client.get(f"/sessions/{banker_id}/board").json()
    assert ready["current_block"]["quiz"]["type"] == "single"
    assert "FOMC" not in ready["current_block"]["quiz"]["prompt"]
    client.post(
        f"/sessions/{banker_id}/grade-widget",
        json={"choice": "shift", "explanation": ""},
    )
    client.post(
        f"/sessions/{banker_id}/turn-score",
        json={"rubric_met": ["choice"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert client.get(f"/sessions/{banker_id}/board").json()["current_block"]["kind"] == "name"
    client.post(
        f"/sessions/{banker_id}/turn-score",
        json={"rubric_met": ["link"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    show = client.get(f"/sessions/{banker_id}/board").json()
    assert show["current_block"]["kind"] == "show"
    assert show["current_block"]["quiz"] is None
    _speak(banker_id, "show")
    assert client.get(f"/sessions/{banker_id}/board").json()["current_block"]["quiz"] is None
    _answer_in_words(banker_id, "show")
    show = client.get(f"/sessions/{banker_id}/board").json()
    assert show["current_block"]["quiz"]["type"] == "flaw"
    assert "memo" in show["current_block"]["quiz"]["prompt"].lower()


def test_unstick_comes_before_the_answer_and_a_later_check_is_a_new_message() -> None:
    storm = _student("storm")["id"]
    client.put("/tutor-profile", json=_profile(struggle_window="standard"))
    opened = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("ROM-U1-Q1")["id"], "fresh": True},
    )
    session_id = opened.json()["id"]
    client.post(
        f"/sessions/{session_id}/messages",
        json={
            "role": "assistant",
            "content": "A find is an object you can dig up. A story is not.",
            "client_id": "stuck-teach",
        },
    )
    client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "user", "content": "I don't know which pile is which.", "client_id": "stuck-words"},
    )
    missed = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": [], "misconception": "Sorted the story with the finds.", "hint_tier": "nudge", "advance": True},
    )
    assert missed.json()["graded_by"] == "discussion"
    assert missed.json()["advanced"] is False
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["quiz"] is None
    client.post(
        f"/sessions/{session_id}/messages",
        json={
            "role": "assistant",
            "content": "The wall is something you could hold. The wolf story is not.",
            "client_id": "stuck-follow",
        },
    )
    offered = client.get(f"/sessions/{session_id}/board").json()
    assert offered["current_block"]["quiz"]["type"] == "multi"
    unstick = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
    assert "one structured try" in unstick
    assert "about to open" in unstick
    assert "Correct answer, for you only" not in unstick
    assert "The struggle window is over" not in unstick
    wrong = client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": ["wolf"], "explanation": ""},
    )
    assert wrong.json()["passed"] is False
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["quiz"] is None
    revealed = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
    assert "The struggle window is over" in revealed
    assert "Correct answer, for you only" in revealed

    widened = client.put("/tutor-profile", json=_profile(struggle_window="long"))
    assert widened.status_code == 200
    try:
        again = client.post(
            "/sessions",
            json={"student_id": storm, "quest_id": _quest("ROM-U1-Q1")["id"], "fresh": True},
        )
        later_id = again.json()["id"]
        client.post(
            f"/sessions/{later_id}/messages",
            json={"role": "assistant", "content": "A find can be checked again. A story carries a meaning.", "client_id": "later-teach"},
        )
        _answer_in_words(later_id, "later")
        assert client.get(f"/sessions/{later_id}/board").json()["current_block"]["quiz"]["type"] == "multi"
        client.post(
            f"/sessions/{later_id}/grade-widget",
            json={"choice": ["wolf"], "explanation": ""},
        )
        assert client.get(f"/sessions/{later_id}/board").json()["current_block"]["quiz"] is None
        client.post(
            f"/sessions/{later_id}/messages",
            json={
                "role": "assistant",
                "content": "That pile was the story. A find is the object in the ground.",
                "client_id": "later-reply",
            },
        )
        client.post(
            f"/sessions/{later_id}/messages",
            json={"role": "user", "content": "The wall and the pottery are the finds.", "client_id": "later-again"},
        )
        client.post(
            f"/sessions/{later_id}/messages",
            json={"role": "assistant", "content": "You named the objects. We can check that list.", "client_id": "later-again-follow"},
        )
        retry = client.get(f"/sessions/{later_id}/board").json()
        assert retry["current_block"]["quiz"]["type"] == "multi"
        retry_prompt = client.get(f"/sessions/{later_id}/prompt").json()["system_prompt"]
        assert "explained in their own words" in retry_prompt
        assert "They have not submitted the widget yet." in retry_prompt
    finally:
        client.put("/tutor-profile", json=_profile(struggle_window="standard"))


def test_struggle_window_then_worked_answer_advances() -> None:
    storm = _student("storm")["id"]
    opened = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("ROM-U2-Q1")["id"], "fresh": True},
    )
    session_id = opened.json()["id"]
    held = {"rubric_met": [], "misconception": None, "hint_tier": "nudge", "advance": True}
    first = client.post(f"/sessions/{session_id}/turn-score", json=held)
    assert first.json()["passed"] is False
    assert first.json()["advanced"] is False
    second = client.post(f"/sessions/{session_id}/turn-score", json=held)
    assert second.json()["advanced"] is False
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "engage"
    revealed = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
    assert "The struggle window is over" in revealed
    assert "worked answer" in revealed.lower()
    assert "Correct answer, for you only" not in revealed
    third = client.post(f"/sessions/{session_id}/turn-score", json=held)
    assert third.json()["passed"] is False
    assert third.json()["advanced"] is True
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "try"


def test_moves_finish_the_quest_and_a_met_criterion_skips_teach_back() -> None:
    storm = _student("storm")["id"]
    opened = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("ROM-U1-Q1")["id"], "fresh": True},
    )
    session_id = opened.json()["id"]
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "try"
    graded = client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": ["wall", "pottery"], "explanation": ""},
    )
    assert graded.json()["passed"] is True
    client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["choice"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "name"
    client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": [], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "show"
    done = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["story", "find"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert done.json()["advanced"] is True
    assert client.get(f"/sessions/{session_id}/board").json()["status"] == "completed"

    consuls = client.post(
        "/sessions",
        json={"student_id": storm, "quest_id": _quest("ROM-U2-Q1")["id"], "fresh": True},
    )
    session_id = consuls.json()["id"]
    client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["advantage", "problem"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    client.post(
        f"/sessions/{session_id}/grade-widget",
        json={"choice": "deadlock", "explanation": ""},
    )
    client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["choice"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert client.get(f"/sessions/{session_id}/board").json()["current_block"]["kind"] == "name"
    client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": [], "misconception": None, "hint_tier": "nudge", "advance": False},
    )
    show = client.get(f"/sessions/{session_id}/board").json()
    assert show["current_block"]["kind"] == "show"
    assert any(step["kind"] == "teach_back" for step in show["steps"])
    finished = client.post(
        f"/sessions/{session_id}/turn-score",
        json={"rubric_met": ["veto", "deadlock"], "misconception": None, "hint_tier": "nudge", "advance": True},
    )
    assert finished.json()["advanced"] is True
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
                        "learning_goal": "The file practices one idea.",
                        "success_criterion": [
                            {"id": "part-a", "text": "Names the first part of the idea.", "weight": 50},
                            {"id": "part-b", "text": "Names the second part of the idea.", "weight": 50},
                        ],
                        "requires_teach_back": False,
                        "beats": _cycle_moves(),
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
    good["units"][0]["quests"][0]["beats"] = _cycle_moves()
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


def _answer_in_words(session_id: str, label: str) -> None:
    client.post(
        f"/sessions/{session_id}/messages",
        json={
            "role": "user",
            "content": "I can say the idea in my own words.",
            "client_id": f"{label}-words",
        },
    )
    client.post(
        f"/sessions/{session_id}/messages",
        json={
            "role": "assistant",
            "content": "You explained it. The next step is to check that idea.",
            "client_id": f"{label}-follow",
        },
    )


def _speak(session_id: str, label: str) -> None:
    client.post(
        f"/sessions/{session_id}/messages",
        json={"role": "user", "content": "Tell me the idea.", "client_id": f"{label}-user"},
    )
    client.post(
        f"/sessions/{session_id}/messages",
        json={
            "role": "assistant",
            "content": "Here is the idea, and then one question.",
            "client_id": f"{label}-tutor",
        },
    )


def _cycle_moves() -> list[dict]:
    criterion = [
        {"id": "part-a", "text": "Names the first part of the idea.", "weight": 50},
        {"id": "part-b", "text": "Names the second part of the idea.", "weight": 50},
    ]
    moves = []
    for role in ("try", "name", "show"):
        widget = None
        rubric = [
            {"id": "link", "text": "Connects the try to the idea.", "weight": 100},
        ]
        if role == "try":
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
        if role == "show":
            rubric = criterion
        moves.append(
            {
                "role": role,
                "bloom_level": "understand",
                "cognitive_load": "low",
                "prompt": f"Work the {role.replace('_', ' ')} move.",
                "rubric": rubric,
                "misconception_map": [
                    {"id": "miss", "trap": "A nearby idea answers it.", "note": "Stay on this move."}
                ],
                "hint_ladder": {
                    "nudge": "What is the question asking?",
                    "analogy": "A small picture of the same idea.",
                    "scaffold": "The first part is ____.",
                },
                "widget": widget,
            }
        )
    return moves


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
        "growth_praise": True,
    }
    body.update(overrides)
    return body


def test_one_tutor_profile_applies_to_every_student() -> None:
    current = client.get("/tutor-profile")
    assert current.status_code == 200
    assert current.json()["instructive"] == 3
    assert current.json()["struggle_window"] == "standard"
    rejected = client.put("/tutor-profile", json=_profile(persona="wizard"))
    assert rejected.status_code == 422

    followed = client.put(
        "/tutor-profile",
        json=_profile(persona="tactical-coach", lexicon="early-concrete", voice_override=False),
    )
    assert followed.status_code == 200
    assert followed.json()["lexicon"] == "precise-visual"
    assert followed.json()["voice_override"] is False
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
    saved = overridden.json()
    assert saved["lexicon"] == "early-concrete"
    assert saved["voice_override"] is True
    assert saved["instructive"] == 1

    storm = _student("storm")
    assert "Co-Explorer" in storm["tutor_persona"]
    try:
        opened = client.post(
            "/sessions",
            json={"student_id": storm["id"], "quest_id": _quest("ROM-U2-Q1")["id"], "fresh": True},
        )
        session_id = opened.json()["id"]
        prompt = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "debate moderator" in prompt.lower()
        assert "Curious Co-Explorer" not in prompt
        assert "One short question" in prompt
        assert "plain language only" in prompt.lower()
        patched = client.patch(
            f"/students/{storm['id']}",
            json={"tutor_persona": "Harbor Guide", "tutor_struggle_window": "long"},
        )
        assert patched.status_code == 200
        assert patched.json()["tutor_persona"] == "Harbor Guide"
        again = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "Harbor Guide" not in again
        assert "debate moderator" in again.lower()

        wolverine = client.post(
            "/sessions",
            json={"student_id": _student("wolverine")["id"], "quest_id": _quest("ROM-U2-Q1")["id"], "fresh": True},
        )
        other = client.get(f"/sessions/{wolverine.json()['id']}/prompt").json()["system_prompt"]
        assert "debate moderator" in other.lower()
        assert "One short question" in other

        held = {"rubric_met": [], "misconception": None, "hint_tier": "nudge", "advance": True}
        first = client.post(f"/sessions/{session_id}/turn-score", json=held)
        assert first.json()["advanced"] is False
        revealed = client.get(f"/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "The struggle window is over" in revealed
        second = client.post(f"/sessions/{session_id}/turn-score", json=held)
        assert second.json()["advanced"] is True
    finally:
        client.patch(
            f"/students/{storm['id']}",
            json={"tutor_persona": storm["tutor_persona"], "tutor_struggle_window": "minimum"},
        )


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
