"""CreateCourse patches, and a tutor re-seed that leaves studio rows in place."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.main import app
from app.models import (
    Course,
    Message,
    Quest,
    Session as TutorSession,
    Student,
    StudioCourse,
    StudioMessage,
    StudioMove,
    StudioQuest,
    StudioQuestClose,
    StudioQuestGoal,
    StudioSettings,
)
from app.seed import seed
from app.studio import description_is_specific, rejection_reply

client = TestClient(app)

REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "009_studio.py"
READY_REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "010_studio_ready.py"
QUIZ_REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "011_studio_quiz_minutes.py"
LIFT_REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "012_quests_on_course.py"


def _wipe(code: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(StudioCourse).where(StudioCourse.code == code))
        db.commit()
    finally:
        db.close()


def _restore_model() -> None:
    db = SessionLocal()
    try:
        row = db.get(StudioSettings, "default")
        if row is not None and row.model != "gpt-4o-mini":
            row.model = "gpt-4o-mini"
            db.commit()
    finally:
        db.close()


def _make(code: str = "ZZGEO", title: str = "Triangles") -> dict:
    _wipe(code)
    created = client.post("/studio/courses", json={"code": code, "title": title})
    assert created.status_code == 200, created.text
    return created.json()


def _full(op: str, kind: str, code: str, **overrides) -> dict:
    body = {
        "op": op,
        "kind": kind,
        "code": code,
        "parent": None,
        "title": None,
        "learning_goal": None,
        "success_criterion": None,
        "position": None,
        "audience": None,
        "focus": None,
        "theme": None,
        "depth": None,
        "sources": None,
        "close": None,
        "close_default": None,
    }
    body.update(overrides)
    return body


def test_revision_adds_studio_tables_only() -> None:
    text = REVISION.read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert "drop_table" not in upgrade
    assert "delete(" not in upgrade
    for name in (
        "studio_courses",
        "studio_units",
        "studio_quests",
        "studio_moves",
        "studio_quest_close",
        "studio_messages",
        "studio_settings",
    ):
        assert f'"{name}"' in upgrade
    for name in ("students", "courses", "units", "quests", "beats", "sessions", "messages"):
        assert f'"{name}"' not in upgrade


def test_ready_revision_adds_one_column() -> None:
    text = READY_REVISION.read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    downgrade = text.split("def downgrade")[1]
    assert 'op.add_column(\n        "studio_courses"' in upgrade
    assert '"ready"' in upgrade
    assert "drop_table" not in upgrade
    assert "delete(" not in upgrade
    assert "seed" not in upgrade
    assert 'op.drop_column("studio_courses", "ready")' in downgrade
    for name in ("students", "courses", "units", "quests", "beats", "sessions", "messages"):
        assert f'"{name}"' not in upgrade


def test_quiz_minutes_revision_adds_one_column() -> None:
    text = QUIZ_REVISION.read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    downgrade = text.split("def downgrade")[1]
    assert 'op.add_column(\n        "studio_courses"' in upgrade
    assert '"quiz_minutes"' in upgrade
    assert "drop_table" not in upgrade
    assert "delete(" not in upgrade
    assert "seed" not in upgrade
    assert 'op.drop_column("studio_courses", "quiz_minutes")' in downgrade
    for name in ("students", "courses", "units", "quests", "beats", "sessions", "messages"):
        assert f'"{name}"' not in upgrade


def test_patch_checker_rejects_unknown_parent_bad_close_and_prose() -> None:
    course = _make()
    course_id = course["id"]
    try:
        unknown = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "This unit does not land.",
                "proposal": {
                    "operations": [
                        _full(
                            "add",
                            "move",
                            "ZZGEO-U9-M1",
                            parent="ZZGEO-U9",
                            title="Missing quest",
                        )
                    ]
                },
            },
        )
        assert unknown.status_code == 422
        assert "parent" in unknown.json()["detail"]

        bad_close = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "The close style is not allowed.",
                "proposal": {
                    "operations": [
                        _full("add", "quest", "ZZGEO-Q1", title="Angles"),
                        _full(
                            "add",
                            "quest",
                            "ZZGEO-Q2",
                            title="Name an angle",
                            close={
                                "close_style": "quiz",
                                "answer_style": "essay",
                                "choice_mode": None,
                                "items": [],
                                "intent": "",
                            },
                        ),
                    ]
                },
            },
        )
        assert bad_close.status_code == 200, bad_close.text
        assert "Close style must be one or several." in bad_close.json()["content"]
        assert "close_style:" not in bad_close.json()["content"]
        assert [op["code"] for op in bad_close.json()["proposal"]["operations"]] == ["ZZGEO-Q1"]

        prose = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "I rewrote the whole course in this paragraph.",
                "proposal": {"course": "Start over and replace every unit with new prose."},
            },
        )
        assert prose.status_code == 422
        assert "patch" in prose.json()["detail"]

        dynamic_items = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "Dynamic choices cannot store items.",
                "proposal": {
                    "operations": [
                        _full("add", "quest", "ZZGEO-Q1", title="Angles"),
                        _full(
                            "add",
                            "quest",
                            "ZZGEO-Q2",
                            title="Classify",
                            close={
                                "close_style": "one",
                                "answer_style": "multiple_choice",
                                "choice_mode": "dynamic",
                                "items": [{"text": "Acute"}, {"text": "Obtuse"}],
                                "intent": "Write a new pair.",
                            },
                        ),
                    ]
                },
            },
        )
        assert dynamic_items.status_code == 200, dynamic_items.text
        assert "Dynamic choices store the intent, not the items." in dynamic_items.json()["content"]
        assert "items:" not in dynamic_items.json()["content"]
        assert [op["code"] for op in dynamic_items.json()["proposal"]["operations"]] == ["ZZGEO-Q1"]

        saved = client.get(f"/studio/courses/{course_id}").json()
        assert saved["quests"] == []
        assert "units" not in saved
        stored = client.get(f"/studio/courses/{course_id}/messages").json()
        assert stored
        assert all(message["applied"] is False for message in stored)
        assert all(
            op["code"] == "ZZGEO-Q1" for message in stored for op in message["proposal"]["operations"]
        )
        tutor_codes = [row["code"] for row in client.get("/courses").json()]
        assert "ZZGEO" not in tutor_codes
    finally:
        _wipe("ZZGEO")


def test_accepted_patch_writes_by_code_and_leaves_an_omitted_close_empty() -> None:
    course = _make()
    course_id = course["id"]
    try:
        prefs = client.patch(
            f"/studio/courses/{course_id}",
            json={
                "title": "Triangles",
                "audience": "9-11",
                "focus": "triangles",
                "theme": "city planning",
                "depth": "go_deep",
                "sources": "none",
                "close_default": {
                    "close_style": "one",
                    "answer_style": "multiple_choice",
                    "choice_mode": "dynamic",
                    "items": [],
                    "intent": "A new triangle question in the city-planning theme.",
                },
            },
        )
        assert prefs.status_code == 200, prefs.text
        assert prefs.json()["sources"] == ""
        assert prefs.json()["depth"] == "go_deep"
        assert prefs.json()["close_default"]["choice_mode"] == "dynamic"
        assert prefs.json()["close_default"]["items"] == []

        draft = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "Add two quests. Nothing is saved until you accept.",
                "proposal": {
                    "operations": [
                        _full(
                            "add",
                            "quest",
                            "ZZGEO-U1-Q1",
                            title="Three sides",
                        ),
                        _full(
                            "add",
                            "quest",
                            "ZZGEO-U1-Q2",
                            title="Angle sum",
                            close={
                                "close_style": "several",
                                "answer_style": "multiple_choice",
                                "choice_mode": "predefined",
                                "items": [
                                    {"text": "90 degrees"},
                                    {"text": "180 degrees"},
                                    {"text": "360 degrees"},
                                ],
                                "intent": "",
                            },
                        ),
                        _full(
                            "add",
                            "move",
                            "ZZGEO-U1-Q1-M1",
                            parent="ZZGEO-U1-Q1",
                            title="Count the sides",
                            learning_goal="Count the sides of a drawn triangle.",
                            success_criterion="The learner says three.",
                        ),
                    ]
                },
            },
        )
        assert draft.status_code == 200, draft.text
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []
        message_id = draft.json()["id"]

        duplicate = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "That code is taken.",
                "proposal": {
                    "operations": [
                        _full("add", "quest", "ZZGEO-Q1", title="Again"),
                        _full("add", "move", "ZZGEO-Q1", parent="ZZGEO-Q1", title="Same code"),
                    ]
                },
            },
        )
        assert duplicate.status_code == 200, duplicate.text
        assert "ZZGEO-Q1 is already a quest." in duplicate.json()["content"]
        assert "code:" not in duplicate.json()["content"]
        assert [op["kind"] for op in duplicate.json()["proposal"]["operations"]] == ["quest"]
        reply = rejection_reply("That code is taken.", "ZZGEO-Q1 is already a quest.")
        assert reply == "ZZGEO-Q1 is already a quest."
        assert "saved" not in reply.lower()
        assert "accepted" not in reply.lower()

        accepted = client.post(f"/studio/courses/{course_id}/messages/{message_id}/accept")
        assert accepted.status_code == 200, accepted.text
        tree = accepted.json()["course"]
        assert [quest["code"] for quest in tree["quests"]] == ["ZZGEO-U1-Q1", "ZZGEO-U1-Q2"]
        assert tree["ready"] is False
        assert tree["close_default"]["choice_mode"] == "dynamic"
        quests = {quest["code"]: quest for quest in tree["quests"]}
        assert quests["ZZGEO-U1-Q1"]["close"] is None
        assert quests["ZZGEO-U1-Q1"]["learning_goal"] == ""
        assert "ZZGEO-U1-Q1: no learning goal" in tree["gaps"]
        assert "ZZGEO-U1-Q1: no close style" in tree["gaps"]
        assert "ZZGEO-U1-Q1-M1: no learning goal" not in tree["gaps"]
        assert "ZZGEO-U1-Q2: no close style" not in tree["gaps"]
        assert quests["ZZGEO-U1-Q2"]["close"]["choice_mode"] == "predefined"
        assert [item["text"] for item in quests["ZZGEO-U1-Q2"]["close"]["items"]] == [
            "90 degrees",
            "180 degrees",
            "360 degrees",
        ]
        assert quests["ZZGEO-U1-Q1"]["moves"][0]["code"] == "ZZGEO-U1-Q1-M1"
        assert accepted.json()["message"]["applied"] is True
        fresh = client.get(f"/studio/courses/{course_id}").json()
        fresh_quests = {quest["code"]: quest for quest in fresh["quests"]}
        assert fresh_quests["ZZGEO-U1-Q1"]["close"] is None
        assert "ZZGEO-U1-Q1: no close style" in fresh["gaps"]
        assert fresh_quests["ZZGEO-U1-Q2"]["close"]["items"][1]["text"] == "180 degrees"

        again = client.post(f"/studio/courses/{course_id}/messages/{message_id}/accept")
        assert again.status_code == 409

        stepped = client.post(f"/studio/courses/{course_id}/phase", json={"name": "quests"})
        assert stepped.status_code == 200, stepped.text
        renamed = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "Rename the angle-sum quest.",
                "proposal": {
                    "operations": [
                        _full("update", "quest", "ZZGEO-U1-Q2", title="Interior angle sum"),
                    ]
                },
            },
        )
        assert renamed.status_code == 200, renamed.text
        renamed_id = renamed.json()["id"]
        removed = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "Remove the first quest.",
                "proposal": {"operations": [_full("remove", "quest", "ZZGEO-U1-Q1")]},
            },
        )
        assert removed.status_code == 200, removed.text
        gone = client.post(f"/studio/courses/{course_id}/messages/{removed.json()['id']}/accept")
        assert gone.status_code == 200, gone.text
        after_remove = gone.json()["course"]["quests"]
        assert [quest["code"] for quest in after_remove] == ["ZZGEO-U1-Q2"]
        stale = client.post(f"/studio/courses/{course_id}/messages/{renamed_id}/accept")
        assert stale.status_code == 200, stale.text
        assert stale.json()["course"]["quests"][0]["title"] == "Interior angle sum"

        panel = client.get(f"/studio/courses/{course_id}").json()
        assert panel["quests"][0]["title"] == "Interior angle sum"
        assert panel["focus"] == "triangles"
    finally:
        _wipe("ZZGEO")


def test_unknown_model_is_rejected_and_prompt_names_the_framework_rule() -> None:
    course = _make()
    course_id = course["id"]
    try:
        client.put("/studio/settings", json={"model": "gpt-4o-mini"})
        unknown = client.put("/studio/settings", json={"model": "gpt-4"})
        assert unknown.status_code == 422
        assert "model" in unknown.json()["detail"]
        assert client.get("/studio/settings").json()["model"] == "gpt-4o-mini"
        assert client.get("/studio/settings").json()["options"] == [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
        ]

        prompt = client.get(f"/studio/courses/{course_id}/prompt").json()
        assert prompt["model"] == "gpt-4o-mini"
        assert "widely known national curricula" in prompt["system_prompt"]
        assert "which framework a suggestion comes from" in prompt["system_prompt"]
        assert "no web search" in prompt["system_prompt"]
        assert "no document upload" in prompt["system_prompt"]
        assert "code, parent code, title, position as an integer from 1" in prompt["system_prompt"]
        assert "learning goal" in prompt["system_prompt"]
        assert "success criterion" in prompt["system_prompt"]
        assert "quest-close choices" in prompt["system_prompt"]
        assert "A position of 0 is invalid." in prompt["system_prompt"]
        assert "Course description: none yet" in prompt["system_prompt"]
        assert "choice_mode is predefined" not in prompt["system_prompt"]
        assert "tools" not in prompt["response_schema"]

        switched = client.put("/studio/settings", json={"model": "gpt-4o"})
        assert switched.status_code == 200
        assert client.get(f"/studio/courses/{course_id}/prompt").json()["model"] == "gpt-4o"
    finally:
        _restore_model()
        _wipe("ZZGEO")


def test_tutor_seed_leaves_every_studio_row() -> None:
    db = SessionLocal()
    session_id = None
    try:
        seed(db)
        quest = db.scalar(select(Quest).where(Quest.code == "ROM-U2-Q1"))
        student = db.scalar(select(Student).where(Student.slug == "storm"))
        assert quest is not None and student is not None
        tutor_session = TutorSession(
            student_id=student.id,
            quest_id=quest.id,
            current_beat_id=quest.beats[0].id,
            status="in_progress",
        )
        db.add(tutor_session)
        db.flush()
        tutor_message = Message(
            session_id=tutor_session.id,
            role="user",
            content="The senate still met after the kings.",
            seq=1,
        )
        db.add(tutor_message)
        db.execute(delete(StudioCourse).where(StudioCourse.code == "ZZSEED"))
        course = StudioCourse(
            code="ZZSEED",
            title="Seed survivor",
            audience="grade 6",
            focus="angles",
            theme="plain language",
            depth="survey",
            sources="Common Core",
            preferences={
                "close_default": {
                    "close_style": "one",
                    "answer_style": "essay",
                    "choice_mode": None,
                    "items": [],
                    "intent": "",
                }
            },
            schema_version=1,
        )
        db.add(course)
        db.flush()
        studio_quest = StudioQuest(
            course_id=course.id,
            code="ZZSEED-U1-Q1",
            position=1,
            title="Name the vertex",
            learning_goal="Name the corner.",
            success_criterion="The learner says vertex.",
        )
        course.quests.append(studio_quest)
        db.flush()
        studio_quest.close = StudioQuestClose(
            close_style="several",
            answer_style="multiple_choice",
            choice_mode="dynamic",
            items=[],
            intent="Ask for a turn the learner can see in the room.",
        )
        move = StudioMove(
            course_id=course.id,
            code="ZZSEED-U1-Q1-M1",
            position=1,
            title="Find a corner",
            learning_goal="Find one corner nearby.",
            success_criterion="The learner names a corner.",
        )
        studio_quest.moves.append(move)
        studio_message = StudioMessage(
            course_id=course.id,
            role="assistant",
            content="This studio note must survive a tutor seed.",
            seq=1,
            proposal=None,
            applied=False,
        )
        db.add(studio_message)
        settings = db.get(StudioSettings, "default")
        if settings is None:
            settings = StudioSettings(id="default", model="gpt-4.1-mini")
            db.add(settings)
        else:
            settings.model = "gpt-4.1-mini"
        db.commit()
        session_id = tutor_session.id
        tutor_message_id = tutor_message.id
        ids = {
            "course": course.id,
            "quest": studio_quest.id,
            "close": studio_quest.close.id,
            "move": move.id,
            "message": studio_message.id,
        }
        before = {
            "courses": db.scalar(select(func.count()).select_from(StudioCourse)),
            "quests": db.scalar(select(func.count()).select_from(StudioQuest)),
            "moves": db.scalar(select(func.count()).select_from(StudioMove)),
            "closes": db.scalar(select(func.count()).select_from(StudioQuestClose)),
            "messages": db.scalar(select(func.count()).select_from(StudioMessage)),
            "settings": db.scalar(select(func.count()).select_from(StudioSettings)),
        }

        seed(db)
        seed(db)
        db.expire_all()

        after = {
            "courses": db.scalar(select(func.count()).select_from(StudioCourse)),
            "quests": db.scalar(select(func.count()).select_from(StudioQuest)),
            "moves": db.scalar(select(func.count()).select_from(StudioMove)),
            "closes": db.scalar(select(func.count()).select_from(StudioQuestClose)),
            "messages": db.scalar(select(func.count()).select_from(StudioMessage)),
            "settings": db.scalar(select(func.count()).select_from(StudioSettings)),
        }
        assert after == before
        kept_course = db.get(StudioCourse, ids["course"])
        kept_quest = db.get(StudioQuest, ids["quest"])
        kept_close = db.get(StudioQuestClose, ids["close"])
        kept_move = db.get(StudioMove, ids["move"])
        kept_studio_message = db.get(StudioMessage, ids["message"])
        kept_settings = db.get(StudioSettings, "default")
        assert kept_course is not None and kept_course.title == "Seed survivor"
        assert kept_course.focus == "angles"
        assert kept_course.schema_version == 1
        assert kept_quest is not None and kept_quest.learning_goal == "Name the corner."
        assert kept_close is not None and kept_close.intent.startswith("Ask for a turn")
        assert kept_close.items == []
        assert kept_move is not None and kept_move.success_criterion == "The learner names a corner."
        assert kept_studio_message is not None
        assert kept_studio_message.content == "This studio note must survive a tutor seed."
        assert kept_settings is not None and kept_settings.model == "gpt-4.1-mini"
        assert db.get(TutorSession, session_id) is not None
        assert db.get(Message, tutor_message_id).content == "The senate still met after the kings."
        assert db.scalar(select(Course.id).where(Course.code == "ZZSEED")) is None
        assert db.scalar(select(func.count()).select_from(Course)) == 3
        assert kept_course.ready is False
    finally:
        if session_id is not None:
            db.execute(delete(TutorSession).where(TutorSession.id == session_id))
        db.execute(delete(StudioCourse).where(StudioCourse.code == "ZZSEED"))
        row = db.get(StudioSettings, "default")
        if row is not None:
            row.model = "gpt-4o-mini"
        db.commit()
        db.close()


def _proposal(course_id: str, content: str, operations: list[dict]):
    return client.post(
        f"/studio/courses/{course_id}/messages",
        json={"role": "assistant", "content": content, "proposal": {"operations": operations}},
    )


def test_rejected_position_does_not_save_or_claim_it_saved() -> None:
    course = _make()
    course_id = course["id"]
    claim = "The structure was accepted and the course was saved."
    try:
        assert course["ready"] is False
        assert course["gaps"] == []
        rejected = _proposal(
            course_id,
            claim,
            [_full("add", "quest", "ZZGEO-U1", parent="ZZGEO", title="Exile", position=0)],
        )
        assert rejected.status_code == 422
        reason = rejected.json()["detail"]
        assert reason == "Position must be an integer from 1 to 200."
        reply = rejection_reply(claim, reason)
        assert reply == reason
        assert "saved" not in reply.lower()
        assert "accepted" not in reply.lower()
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []
        assert client.get(f"/studio/courses/{course_id}/messages").json() == []

        mixed = _proposal(
            course_id,
            claim,
            [
                _full("add", "quest", "ZZGEO-U1", title="Exile", learning_goal="The story begins."),
                _full("add", "quest", "ZZGEO-U1-Q1", title="The bow", position=0),
            ],
        )
        assert mixed.status_code == 200, mixed.text
        assert "Position must be an integer from 1 to 200." in mixed.json()["content"]
        assert [op["code"] for op in mixed.json()["proposal"]["operations"]] == ["ZZGEO-U1"]
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []

        outside = _proposal(
            course_id,
            claim,
            [_full("add", "quest", "ZZGEO-U1", parent="ZZGEO", title="Exile", position=201)],
        )
        assert outside.status_code == 422
        assert outside.json()["detail"] == "Position must be an integer from 1 to 200."
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []

        past = _proposal(
            course_id,
            claim,
            [_full("add", "quest", "ZZGEO-U1", parent="ZZGEO", title="Exile", position=5)],
        )
        assert past.status_code == 422
        assert past.json()["detail"] == "Position is past the end of this list."
        assert "saved" not in past.json()["detail"].lower()
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []
        assert len(client.get(f"/studio/courses/{course_id}/messages").json()) == 1
    finally:
        _wipe("ZZGEO")


def test_missing_position_is_filled_with_the_next_free_number() -> None:
    course = _make()
    course_id = course["id"]
    try:
        omitted = _full("add", "quest", "ZZGEO-U2", parent="ZZGEO", title="Return", learning_goal="The city stands.")
        del omitted["position"]
        draft = _proposal(
            course_id,
            "Two units, and the server chooses their places.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1",
                    parent="ZZGEO",
                    title="Exile",
                    learning_goal="The story begins.",
                    position=None,
                ),
                omitted,
            ],
        )
        assert draft.status_code == 200, draft.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{draft.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        units = accepted.json()["course"]["quests"]
        assert [(unit["code"], unit["position"]) for unit in units] == [("ZZGEO-U1", 1), ("ZZGEO-U2", 2)]
        fresh = client.get(f"/studio/courses/{course_id}").json()
        assert [(unit["code"], unit["position"]) for unit in fresh["quests"]] == [("ZZGEO-U1", 1), ("ZZGEO-U2", 2)]
    finally:
        _wipe("ZZGEO")


def test_partial_quest_is_stored_and_reported_as_a_gap() -> None:
    course = _make()
    course_id = course["id"]
    try:
        draft = _proposal(
            course_id,
            "A quest can be saved before its goal and close are known.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    title="The bow",
                    learning_goal="",
                    position=None,
                    close=None,
                ),
            ],
        )
        assert draft.status_code == 200, draft.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{draft.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        tree = accepted.json()["course"]
        quest = tree["quests"][0]
        assert quest["code"] == "ZZGEO-U1-Q1"
        assert quest["position"] == 1
        assert quest["learning_goal"] == ""
        assert quest["close"] is None
        assert tree["ready"] is False
        assert "ZZGEO-U1-Q1: no learning goal" in tree["gaps"]
        assert "ZZGEO-U1-Q1: no close style" in tree["gaps"]
        assert "ZZGEO-U1: no learning goal" not in tree["gaps"]

        blocked = client.post(f"/studio/courses/{course_id}/ready")
        assert blocked.status_code == 422
        assert "ZZGEO-U1-Q1: no learning goal" in blocked.json()["detail"]
        assert "ZZGEO-U1-Q1: no close style" in blocked.json()["detail"]
        assert "saved" not in blocked.json()["detail"].lower()
        still = client.get(f"/studio/courses/{course_id}").json()
        assert still["ready"] is False
        assert still["quests"][0]["code"] == "ZZGEO-U1-Q1"
        tutor_codes = [row["code"] for row in client.get("/courses").json()]
        assert "ZZGEO" not in tutor_codes
    finally:
        _wipe("ZZGEO")


def test_mark_ready_records_completion_and_reopens_when_a_gap_returns() -> None:
    course = _make()
    course_id = course["id"]
    try:
        draft = _proposal(
            course_id,
            "A complete first quest.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    title="The bow",
                    learning_goal="Name the bow.",
                    success_criterion="States the name of the bow.",
                    close={
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "intent": "",
                    },
                ),
                _full(
                    "add",
                    "move",
                    "ZZGEO-U1-Q1-M1",
                    parent="ZZGEO-U1-Q1",
                    title="Point to the bow",
                    learning_goal="Find the bow in the story.",
                ),
            ],
        )
        assert draft.status_code == 200, draft.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{draft.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["course"]["gaps"] == []
        assert accepted.json()["course"]["ready"] is False

        ready = client.post(f"/studio/courses/{course_id}/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["ready"] is True
        assert ready.json()["gaps"] == []
        assert [row["code"] for row in client.get("/courses").json()].count("ZZGEO") == 0

        again = client.post(f"/studio/courses/{course_id}/ready")
        assert again.status_code == 200, again.text
        assert again.json()["ready"] is True

        reopened = _proposal(
            course_id,
            "Clear the quest goal.",
            [_full("update", "quest", "ZZGEO-U1-Q1", learning_goal="")],
        )
        assert reopened.status_code == 200, reopened.text
        applied = client.post(f"/studio/courses/{course_id}/messages/{reopened.json()['id']}/accept")
        assert applied.status_code == 200, applied.text
        assert applied.json()["course"]["ready"] is False
        assert "ZZGEO-U1-Q1: no learning goal" in applied.json()["course"]["gaps"]
        assert applied.json()["course"]["quests"][0]["title"] == "The bow"
        blocked = client.post(f"/studio/courses/{course_id}/ready")
        assert blocked.status_code == 422
        assert client.get(f"/studio/courses/{course_id}").json()["ready"] is False
    finally:
        _wipe("ZZGEO")


def test_parent_on_an_update_is_ignored_and_the_goal_is_written() -> None:
    course = _make()
    course_id = course["id"]
    claim = "The learning goals were saved and the structure was accepted."
    try:
        structure = _proposal(
            course_id,
            "Add the first quest without a goal.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    title="The bow",
                    learning_goal="",
                    close=None,
                ),
            ],
        )
        assert structure.status_code == 200, structure.text
        planted = client.post(f"/studio/courses/{course_id}/messages/{structure.json()['id']}/accept")
        assert planted.status_code == 200, planted.text
        assert planted.json()["course"]["quests"][0]["close"] is None

        kept = _proposal(
            course_id,
            claim,
            [
                _full(
                    "update",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U9",
                    learning_goal="Name the bow.",
                    success_criterion="States the name of the bow.",
                )
            ],
        )
        assert kept.status_code == 200, kept.text
        assert "does not belong" not in kept.text
        assert "parent:" not in kept.json()["content"]
        applied = client.post(f"/studio/courses/{course_id}/messages/{kept.json()['id']}/accept")
        assert applied.status_code == 200, applied.text
        quest = applied.json()["course"]["quests"][0]
        assert quest["learning_goal"] == "Name the bow."
        assert quest["close"] is None
        assert quest["code"] == "ZZGEO-U1-Q1"
        assert applied.json()["course"]["quests"][0]["code"] == "ZZGEO-U1-Q1"

        echoed = _proposal(
            course_id,
            "Offer a learning goal for ZZGEO-U1-Q1.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    learning_goal="Name the bow.",
                    close=None,
                )
            ],
        )
        assert echoed.status_code == 422
        assert echoed.json()["detail"] == "Close only updates the close for ZZGEO-U1-Q1."
        stored = client.get(f"/studio/courses/{course_id}").json()["quests"][0]
        assert stored["learning_goal"] == "Name the bow."
        assert stored["close"] is None
    finally:
        _wipe("ZZGEO")


def test_goals_phase_limits_the_prompt_to_open_goal_codes() -> None:
    course = _make()
    course_id = course["id"]
    try:
        structure = _proposal(
            course_id,
            "Two quests, one goal already written.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    title="The bow",
                    learning_goal="",
                    close=None,
                ),
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q2",
                    parent="ZZGEO-U1",
                    title="The city",
                    learning_goal="Name the city the story returns to.",
                    success_criterion="States the name of the city.",
                    close=None,
                ),
            ],
        )
        assert structure.status_code == 200, structure.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{structure.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        tree = accepted.json()["course"]
        assert tree["phase"] == {
            "name": "goals",
            "label": "Goals/Success Criteria",
            "open_codes": ["ZZGEO-U1-Q1"],
        }

        prompt = client.get(f"/studio/courses/{course_id}/prompt").json()["system_prompt"]
        open_line = next(line for line in prompt.splitlines() if line.startswith("Codes still open in this phase:"))
        assert open_line == "Codes still open in this phase: ZZGEO-U1-Q1."
        assert "ZZGEO-U1-Q2" not in open_line
        assert "Current phase: Goals/Success Criteria." in prompt
        assert "Patch only those codes." in prompt
        assert "Offer a learning goal for each open quest, addressed by that quest's code." in prompt
        assert "sets parent to null" in prompt
        assert "Do not fill close style in this patch." in prompt

        goals = _proposal(
            course_id,
            "Here is the goal for the open quest.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZGEO-U1-Q1",
                    learning_goal="Name the bow.",
                    success_criterion="States the name of the bow.",
                    close=None,
                )
            ],
        )
        assert goals.status_code == 200, goals.text
        applied = client.post(f"/studio/courses/{course_id}/messages/{goals.json()['id']}/accept")
        assert applied.status_code == 200, applied.text
        quests = {quest["code"]: quest for quest in applied.json()["course"]["quests"]}
        assert quests["ZZGEO-U1-Q1"]["learning_goal"] == "Name the bow."
        assert quests["ZZGEO-U1-Q1"]["close"] is None
        assert quests["ZZGEO-U1-Q2"]["close"] is None
        assert applied.json()["course"]["phase"]["name"] == "close"
        assert applied.json()["course"]["phase"]["open_codes"] == ["ZZGEO-U1-Q1", "ZZGEO-U1-Q2"]
    finally:
        _wipe("ZZGEO")


def test_stepping_back_to_goals_keeps_the_close() -> None:
    course = _make()
    course_id = course["id"]
    try:
        structure = _proposal(
            course_id,
            "Goals are in. One quest still needs a close.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    title="The bow",
                    learning_goal="Name the bow.",
                    success_criterion="States the name of the bow.",
                    close={
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "intent": "",
                    },
                ),
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q2",
                    parent="ZZGEO-U1",
                    title="The city",
                    learning_goal="Name the city.",
                    success_criterion="States the name of the city.",
                    close=None,
                ),
            ],
        )
        assert structure.status_code == 200, structure.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{structure.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        opened = accepted.json()["course"]
        assert opened["phase"]["name"] == "close"
        assert opened["phase"]["open_codes"] == ["ZZGEO-U1-Q2"]
        assert opened["view"] == {"name": "close", "label": "Close", "codes": ["ZZGEO-U1-Q2"]}
        by_name = {item["name"]: item for item in opened["strip"]}
        assert [item["label"] for item in opened["strip"]] == ["Quests", "Goals/Success Criteria", "Close", "Ready"]
        assert by_name["quests"]["filled"] is True and by_name["quests"]["active"] is False
        assert by_name["goals"]["filled"] is True and by_name["goals"]["active"] is False
        assert by_name["close"]["active"] is True and by_name["close"]["filled"] is False
        assert by_name["ready"]["active"] is False and by_name["ready"]["filled"] is False

        stepped = client.post(f"/studio/courses/{course_id}/phase", json={"name": "goals"})
        assert stepped.status_code == 200, stepped.text
        looking = stepped.json()
        assert looking["phase"]["name"] == "close"
        assert looking["view"] == {
            "name": "goals",
            "label": "Goals/Success Criteria",
            "codes": ["ZZGEO-U1-Q1", "ZZGEO-U1-Q2"],
        }
        stepped_strip = {item["name"]: item for item in looking["strip"]}
        assert stepped_strip["goals"]["active"] is True and stepped_strip["goals"]["filled"] is True
        assert stepped_strip["close"]["active"] is False
        prompt = client.get(f"/studio/courses/{course_id}/prompt").json()["system_prompt"]
        codes_line = next(line for line in prompt.splitlines() if line.startswith("Codes in this phase:"))
        assert codes_line == "Codes in this phase: ZZGEO-U1-Q1, ZZGEO-U1-Q2."
        assert "Current phase: Goals/Success Criteria." in prompt
        assert "including items already filled" in prompt
        assert "Do not wipe close style." in prompt
        assert "The next unfinished wave is Close." in prompt

        revised = _proposal(
            course_id,
            "Revise the bow goal.",
            [_full("update", "quest", "ZZGEO-U1-Q1", learning_goal="Name the sacred bow.")],
        )
        assert revised.status_code == 200, revised.text
        applied = client.post(f"/studio/courses/{course_id}/messages/{revised.json()['id']}/accept")
        assert applied.status_code == 200, applied.text
        quests = {quest["code"]: quest for quest in applied.json()["course"]["quests"]}
        assert quests["ZZGEO-U1-Q1"]["learning_goal"] == "Name the sacred bow."
        assert quests["ZZGEO-U1-Q1"]["close"]["answer_style"] == "essay"
        assert quests["ZZGEO-U1-Q1"]["close"]["close_style"] == "one"
        assert quests["ZZGEO-U1-Q2"]["learning_goal"] == "Name the city."
        assert quests["ZZGEO-U1-Q2"]["close"] is None
        assert applied.json()["course"]["phase"]["name"] == "close"
        assert applied.json()["course"]["view"]["name"] == "goals"
        blocked = client.post(f"/studio/courses/{course_id}/ready")
        assert blocked.status_code == 422
        assert client.get(f"/studio/courses/{course_id}").json()["ready"] is False

        returned = client.post(f"/studio/courses/{course_id}/phase", json={"name": "close"})
        assert returned.status_code == 200, returned.text
        assert returned.json()["view"] == {"name": "close", "label": "Close", "codes": ["ZZGEO-U1-Q2"]}
        assert returned.json()["strip"][1]["active"] is False
        assert returned.json()["strip"][1]["filled"] is True
        assert returned.json()["strip"][2]["active"] is True
        again = client.get(f"/studio/courses/{course_id}/prompt").json()["system_prompt"]
        open_line = next(line for line in again.splitlines() if line.startswith("Codes still open in this phase:"))
        assert open_line == "Codes still open in this phase: ZZGEO-U1-Q2."
        kept = client.get(f"/studio/courses/{course_id}").json()["quests"][0]
        assert kept["close"]["close_style"] == "one"
    finally:
        _wipe("ZZGEO")


def test_goal_patch_for_an_existing_quest_code_writes_the_goal() -> None:
    course = _make()
    course_id = course["id"]
    claim = "The learning goal was saved."
    try:
        structure = _proposal(
            course_id,
            "Add a quest that still needs a goal.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    title="The bow",
                    learning_goal="",
                    close={
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "intent": "",
                    },
                ),
            ],
        )
        assert structure.status_code == 200, structure.text
        planted = client.post(f"/studio/courses/{course_id}/messages/{structure.json()['id']}/accept")
        assert planted.status_code == 200, planted.text
        before = planted.json()["course"]["quests"][0]
        assert before["learning_goal"] == ""
        assert before["close"]["close_style"] == "one"

        goals = _proposal(
            course_id,
            claim,
            [
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    title="The bow",
                    learning_goal="Name the bow.",
                    close=None,
                )
            ],
        )
        assert goals.status_code == 200, goals.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{goals.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        quest = accepted.json()["course"]["quests"][0]
        assert quest["learning_goal"] == "Name the bow."
        assert quest["title"] == "The bow"
        assert quest["close"]["close_style"] == "one"
        assert quest["close"]["answer_style"] == "essay"
        stored = client.get(f"/studio/courses/{course_id}").json()["quests"][0]
        assert stored["learning_goal"] == "Name the bow."
        assert stored["close"]["close_style"] == "one"
    finally:
        _wipe("ZZGEO")


def _table_counts() -> dict[str, int]:
    db = SessionLocal()
    try:
        return {
            "courses": db.scalar(select(func.count()).select_from(Course)) or 0,
            "messages": db.scalar(select(func.count()).select_from(Message)) or 0,
            "sessions": db.scalar(select(func.count()).select_from(TutorSession)) or 0,
        }
    finally:
        db.close()


def test_wrong_password_does_nothing_and_the_right_password_deletes_the_studio_course() -> None:
    course = _make("ZZDEL", "Delete me")
    course_id = course["id"]
    kept = _make("ZZKEEP", "Keep me")
    before = _table_counts()
    try:
        planted = _proposal(
            course_id,
            "A quest with a close and a creation chat.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZDEL-U1-Q1",
                    parent="ZZDEL-U1",
                    title="The bow",
                    learning_goal="Name the bow.",
                    close={
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "intent": "",
                    },
                ),
                _full(
                    "add",
                    "move",
                    "ZZDEL-U1-Q1-M1",
                    parent="ZZDEL-U1-Q1",
                    title="Draw the bow",
                    learning_goal="Draw it.",
                ),
            ],
        )
        assert planted.status_code == 200, planted.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{planted.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text

        wrong = client.post(f"/studio/courses/{course_id}/delete", json={"password": "not-the-password"})
        assert wrong.status_code == 422
        assert wrong.json()["detail"] == "The password is wrong."
        assert "password:" not in wrong.json()["detail"]
        still = client.get(f"/studio/courses/{course_id}")
        assert still.status_code == 200
        quest_id = still.json()["quests"][0]["id"]
        assert still.json()["quests"][0]["close"]["close_style"] == "one"
        assert client.get(f"/studio/courses/{course_id}/messages").json()
        assert client.get(f"/studio/courses/{kept['id']}").status_code == 200
        assert _table_counts() == before

        deleted = client.post(f"/studio/courses/{course_id}/delete", json={"password": "BulmerGardens"})
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted"] is True
        assert client.get(f"/studio/courses/{course_id}").status_code == 404
        assert client.get(f"/studio/courses/{kept['id']}").status_code == 200
        codes = [row["code"] for row in client.get("/studio/courses").json()]
        assert "ZZDEL" not in codes
        assert "ZZKEEP" in codes
        assert _table_counts() == before
        db = SessionLocal()
        try:
            assert db.scalar(select(func.count()).select_from(StudioQuest).where(StudioQuest.course_id == course_id)) == 0
            assert db.scalar(select(func.count()).select_from(StudioMove).where(StudioMove.course_id == course_id)) == 0
            assert db.scalar(select(func.count()).select_from(StudioMessage).where(StudioMessage.course_id == course_id)) == 0
            assert (
                db.scalar(select(func.count()).select_from(StudioQuestClose).where(StudioQuestClose.quest_id == quest_id))
                == 0
            )
        finally:
            db.close()
    finally:
        _wipe("ZZDEL")
        _wipe("ZZKEEP")


def test_copy_writes_a_new_code_and_leaves_the_chat_behind() -> None:
    course = _make("ZZMAN", "Manage me")
    course_id = course["id"]
    _wipe("ZZMAN2")
    try:
        prefs = client.patch(
            f"/studio/courses/{course_id}",
            json={
                "title": "Manage me",
                "audience": "9-11",
                "focus": "triangles",
                "theme": "city planning",
                "depth": "go_deep",
                "sources": "none",
                "close_default": {
                    "close_style": "one",
                    "answer_style": "multiple_choice",
                    "choice_mode": "dynamic",
                    "items": [],
                    "intent": "A new triangle question.",
                },
            },
        )
        assert prefs.status_code == 200, prefs.text
        planted = _proposal(
            course_id,
            "Build the course, and keep this chat on the original.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZMAN-U1-Q1",
                    parent="ZZMAN-U1",
                    title="The bow",
                    learning_goal="Name the shape.",
                    close={
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "intent": "",
                    },
                ),
                _full(
                    "add",
                    "move",
                    "ZZMAN-U1-Q1-M1",
                    parent="ZZMAN-U1-Q1",
                    title="Draw it",
                    learning_goal="Draw the shape.",
                ),
            ],
        )
        assert planted.status_code == 200, planted.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{planted.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        assert client.get(f"/studio/courses/{course_id}/messages").json()

        copied = client.post(f"/studio/courses/{course_id}/copy", json={"title": "Copied course"})
        assert copied.status_code == 200, copied.text
        body = copied.json()
        assert body["id"] != course_id
        assert body["code"] == "ZZMAN2"
        assert body["title"] == "Copied course"
        assert body["audience"] == "9-11"
        assert body["focus"] == "triangles"
        assert body["depth"] == "go_deep"
        assert body["theme"] == "city planning"
        assert body["close_default"]["intent"] == "A new triangle question."
        assert body["ready"] is False
        quest = body["quests"][0]
        assert quest["code"] == "ZZMAN2-U1-Q1"
        assert quest["title"] == "The bow"
        assert quest["learning_goal"] == "Name the shape."
        assert quest["close"]["close_style"] == "one"
        assert quest["close"]["answer_style"] == "essay"
        assert quest["moves"][0]["code"] == "ZZMAN2-U1-Q1-M1"
        assert quest["moves"][0]["learning_goal"] == "Draw the shape."
        assert client.get(f"/studio/courses/{body['id']}/messages").json() == []
        source = client.get(f"/studio/courses/{course_id}").json()
        assert source["code"] == "ZZMAN"
        assert source["quests"][0]["code"] == "ZZMAN-U1-Q1"
        assert client.get(f"/studio/courses/{course_id}/messages").json()
        listed = {row["code"]: row["title"] for row in client.get("/studio/courses").json()}
        assert listed["ZZMAN2"] == "Copied course"
        assert "ZZMAN2" not in [row["code"] for row in client.get("/courses").json()]
    finally:
        _wipe("ZZMAN")
        _wipe("ZZMAN2")


def test_preference_save_writes_the_choices_and_cancel_does_not() -> None:
    course = _make("ZZPREFS", "Preferences")
    course_id = course["id"]
    try:
        assert course["depth"] == "standard"
        assert course["quiz_minutes"] == 5
        assert course["audience"] == ""
        # Cancel drops this draft. Nothing is sent, so the stored header stays.
        cancelled = {
            "title": "Preferences",
            "audience": "6-8",
            "focus": "ships",
            "theme": "harbors",
            "depth": "survey",
            "quiz_minutes": 2,
            "sources": "A framework that was not saved",
            "close_default": {
                "close_style": "several",
                "answer_style": "essay",
                "choice_mode": None,
                "items": [],
                "intent": "",
            },
        }
        untouched = client.get(f"/studio/courses/{course_id}").json()
        assert cancelled["depth"] != untouched["depth"]
        assert cancelled["quiz_minutes"] != untouched["quiz_minutes"]
        assert untouched["depth"] == "standard"
        assert untouched["quiz_minutes"] == 5
        assert untouched["audience"] == ""
        assert untouched["theme"] == ""
        assert untouched["sources"] == ""

        saved = client.patch(
            f"/studio/courses/{course_id}",
            json={
                "title": "Preferences",
                "audience": "12-14",
                "focus": "triangles",
                "theme": "city planning",
                "depth": "go_deep",
                "quiz_minutes": 10,
                "sources": "Common Core",
                "close_default": {
                    "close_style": "several",
                    "answer_style": "mixed",
                    "choice_mode": "predefined",
                    "items": [{"text": "90 degrees"}, {"text": "180 degrees"}],
                    "intent": "",
                },
            },
        )
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["depth"] == "go_deep"
        assert body["quiz_minutes"] == 10
        assert body["audience"] == "12-14"
        assert body["theme"] == "city planning"
        assert body["sources"] == "Common Core"
        assert body["focus"] == "triangles"
        assert body["close_default"]["close_style"] == "several"
        assert body["close_default"]["answer_style"] == "mixed"
        assert body["close_default"]["choice_mode"] == "predefined"
        fresh = client.get(f"/studio/courses/{course_id}").json()
        assert fresh["depth"] == "go_deep"
        assert fresh["quiz_minutes"] == 10
        assert fresh["audience"] == "12-14"
        assert fresh["close_default"]["items"][0]["text"] == "90 degrees"
        db = SessionLocal()
        try:
            row = db.scalar(select(StudioCourse).where(StudioCourse.id == course_id))
            assert row is not None
            assert row.quiz_minutes == 10
            assert row.depth == "go_deep"
            assert row.audience == "12-14"
            assert row.schema_version == 2
            prefs = row.preferences
            assert prefs["quiz_minutes"] == 10
            assert prefs["depth"] == "go_deep"
            assert prefs["audience"] == "12-14"
            assert prefs["theme"] == "city planning"
            assert prefs["sources"] == "Common Core"
            assert prefs["close_default"]["close_style"] == "several"
            assert prefs["close_default"]["answer_style"] == "mixed"
            tutor = db.scalar(select(func.count()).select_from(Course))
            chats = db.scalar(select(func.count()).select_from(Message))
            assert tutor is not None
            assert chats is not None
        finally:
            db.close()
        rejected = client.patch(
            f"/studio/courses/{course_id}",
            json={
                "title": "Preferences",
                "audience": "12-14",
                "focus": "triangles",
                "theme": "city planning",
                "depth": "survey",
                "quiz_minutes": 7,
                "sources": "Common Core",
                "close_default": fresh["close_default"],
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["detail"] == "Minimum time before the closing quiz must be 2, 5, or 10 minutes."
        kept = client.get(f"/studio/courses/{course_id}").json()
        assert kept["quiz_minutes"] == 10
        assert kept["depth"] == "go_deep"
    finally:
        _wipe("ZZPREFS")


def test_unit_patch_with_depth_still_writes_the_unit() -> None:
    course = _make("ZZDEPTH", "Premier League History")
    course_id = course["id"]
    try:
        assert course["depth"] == "standard"
        assert course["quests"] == []
        draft = _proposal(
            course_id,
            "Add the opening period.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZDEPTH-U1",
                    title="1992 to 1995",
                    learning_goal="Name the first Premier League winners.",
                    depth="go_deep",
                ),
            ],
        )
        assert draft.status_code == 200, draft.text
        assert draft.json()["content"] == "Add the opening period."
        accepted = client.post(f"/studio/courses/{course_id}/messages/{draft.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        body = accepted.json()["course"]
        assert body["depth"] == "standard"
        assert body["quests"][0]["code"] == "ZZDEPTH-U1"
        assert body["quests"][0]["title"] == "1992 to 1995"
        assert body["quests"][0]["learning_goal"] == "Name the first Premier League winners."
        stored = client.get(f"/studio/courses/{course_id}").json()
        assert stored["depth"] == "standard"
        assert stored["quests"][0]["title"] == "1992 to 1995"

        stepped = client.post(f"/studio/courses/{course_id}/phase", json={"name": "quests"})
        assert stepped.status_code == 200, stepped.text
        revised = _proposal(
            course_id,
            "Rename the opening period.",
            [
                _full("update", "quest", "ZZDEPTH-U1", title="1992 to 1995 winners", depth="survey"),
            ],
        )
        assert revised.status_code == 200, revised.text
        renamed = client.post(f"/studio/courses/{course_id}/messages/{revised.json()['id']}/accept")
        assert renamed.status_code == 200, renamed.text
        renamed_course = renamed.json()["course"]
        assert renamed_course["depth"] == "standard"
        assert renamed_course["quests"][0]["title"] == "1992 to 1995 winners"

        another = _proposal(
            course_id,
            "Add the next period.",
            [
                _full("add", "quest", "ZZDEPTH-U2", title="1995 to 1998", depth="go_deep", sources="records"),
            ],
        )
        assert another.status_code == 200, another.text
        assert "does not belong" not in another.text
        saved = client.post(f"/studio/courses/{course_id}/messages/{another.json()['id']}/accept")
        assert saved.status_code == 200, saved.text
        fresh = saved.json()["course"]
        assert [unit["code"] for unit in fresh["quests"]] == ["ZZDEPTH-U1", "ZZDEPTH-U2"]
        assert fresh["quests"][1]["title"] == "1995 to 1998"
        assert fresh["depth"] == "standard"
        assert fresh["sources"] == ""
        assert fresh["audience"] == ""
    finally:
        _wipe("ZZDEPTH")


def test_recoverable_checker_cases_normalize_and_position_stays_fatal(caplog) -> None:
    course = _make("ZZNORM", "Checker")
    course_id = course["id"]
    claim = "The structure was saved."
    try:
        caplog.set_level("INFO", logger="app.studio")
        out_of_range = _proposal(
            course_id,
            claim,
            [_full("add", "quest", "ZZNORM-U1", parent="ZZNORM", title="Opening", position=0)],
        )
        assert out_of_range.status_code == 422
        reason = out_of_range.json()["detail"]
        assert reason == "Position must be an integer from 1 to 200."
        assert "position:" not in reason
        reply = rejection_reply(claim, reason)
        assert reply == reason
        assert "saved" not in reply.lower()
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []

        past = _proposal(
            course_id,
            claim,
            [_full("add", "quest", "ZZNORM-U1", parent="ZZNORM", title="Opening", position=5)],
        )
        assert past.status_code == 422
        assert past.json()["detail"] == "Position is past the end of this list."
        assert "position:" not in past.json()["detail"]
        assert client.get(f"/studio/courses/{course_id}/messages").json() == []

        draft = _proposal(
            course_id,
            "Add the first period.",
            [
                _full("add", "quest", "ZZNORM-U1", title="Opening", depth="go_deep", sources="records"),
            ],
        )
        assert draft.status_code == 200, draft.text
        assert "does not belong" not in draft.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{draft.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        body = accepted.json()["course"]
        assert body["quests"][0]["code"] == "ZZNORM-U1"
        assert body["quests"][0]["position"] == 1
        assert body["depth"] == "standard"
        assert body["sources"] == ""
        dropped = [record.message for record in caplog.records]
        assert any("dropped sources on quest ZZNORM-U1" in message for message in dropped)
        assert any("dropped depth on quest ZZNORM-U1" in message for message in dropped)

        stepped = client.post(f"/studio/courses/{course_id}/phase", json={"name": "quests"})
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["view"]["name"] == "quests"
        again = _proposal(
            course_id,
            "Rename the period.",
            [
                _full("update", "quest", "ZZNORM-U1", title="1992 to 1995 winners", sources="records"),
            ],
        )
        assert again.status_code == 200, again.text
        renamed = client.post(f"/studio/courses/{course_id}/messages/{again.json()['id']}/accept")
        assert renamed.status_code == 200, renamed.text
        renamed_course = renamed.json()["course"]
        assert [unit["code"] for unit in renamed_course["quests"]] == ["ZZNORM-U1"]
        assert renamed_course["quests"][0]["title"] == "1992 to 1995 winners"
        assert renamed_course["sources"] == ""

        moved = _proposal(
            course_id,
            "Retitle without moving.",
            [_full("update", "quest", "ZZNORM-U1", parent="ZZNORM-U9", title="Opening years", sources="nope")],
        )
        assert moved.status_code == 200, moved.text
        moved_ok = client.post(f"/studio/courses/{course_id}/messages/{moved.json()['id']}/accept")
        assert moved_ok.status_code == 200, moved_ok.text
        assert moved_ok.json()["course"]["quests"][0]["title"] == "Opening years"
        assert any("dropped parent on quest ZZNORM-U1" in record.message for record in caplog.records)

        mixed = _proposal(
            course_id,
            claim,
            [
                _full("add", "quest", "ZZNORM-U2", title="Next", sources="records"),
                _full("add", "quest", "ZZNORM-U2-Q1", title="Winners", position=0),
            ],
        )
        assert mixed.status_code == 200, mixed.text
        assert "Position must be an integer from 1 to 200." in mixed.json()["content"]
        assert "saved" not in rejection_reply(claim, "Position must be an integer from 1 to 200.").lower()
        assert [op["code"] for op in mixed.json()["proposal"]["operations"]] == ["ZZNORM-U2"]
        kept_mixed = client.post(f"/studio/courses/{course_id}/messages/{mixed.json()['id']}/accept")
        assert kept_mixed.status_code == 200, kept_mixed.text
        final = kept_mixed.json()["course"]
        assert [quest["code"] for quest in final["quests"]] == ["ZZNORM-U1", "ZZNORM-U2"]
        assert final["quests"][1]["moves"] == []
    finally:
        _wipe("ZZNORM")


def test_phase_schema_limits_fields_and_goals_skips_a_new_unit() -> None:
    course = _make("ZZPHASE", "Phase check")
    course_id = course["id"]
    try:
        schema = client.get(f"/studio/courses/{course_id}/prompt").json()["response_schema"]
        props = schema["properties"]["patch"]["anyOf"][1]["properties"]["operations"]["items"]["properties"]
        assert set(props) == {"op", "kind", "code", "parent", "title", "position"}
        assert "depth" not in props
        assert "sources" not in props
        assert "learning_goal" not in props
        assert "close" not in props

        structure = _proposal(
            course_id,
            "One quest still needs a goal.",
            [
                _full("add", "quest", "ZZPHASE-U1-Q1", parent="ZZPHASE-U1", title="Winners", learning_goal=""),
            ],
        )
        assert structure.status_code == 200, structure.text
        planted = client.post(f"/studio/courses/{course_id}/messages/{structure.json()['id']}/accept")
        assert planted.status_code == 200, planted.text
        assert planted.json()["course"]["phase"]["name"] == "goals"

        goal_schema = client.get(f"/studio/courses/{course_id}/prompt").json()["response_schema"]
        goal_props = goal_schema["properties"]["patch"]["anyOf"][1]["properties"]["operations"]["items"]["properties"]
        assert set(goal_props) == {"op", "kind", "code", "learning_goal", "success_criterion", "goals"}
        assert "close" not in goal_props
        assert "sources" not in goal_props

        mixed = _proposal(
            course_id,
            "A goal, and a unit outside this phase.",
            [
                _full("add", "quest", "ZZPHASE-Q9", title="Later"),
                _full("update", "quest", "ZZPHASE-U1-Q1", learning_goal="Name the first winners."),
            ],
        )
        assert mixed.status_code == 200, mixed.text
        assert "Goals only updates learning goals" in mixed.json()["content"]
        assert [op["code"] for op in mixed.json()["proposal"]["operations"]] == ["ZZPHASE-U1-Q1"]
        assert "does not belong" not in mixed.text
        accepted = client.post(f"/studio/courses/{course_id}/messages/{mixed.json()['id']}/accept")
        assert accepted.status_code == 200, accepted.text
        body = accepted.json()["course"]
        assert [quest["code"] for quest in body["quests"]] == ["ZZPHASE-U1-Q1"]
        assert body["quests"][0]["learning_goal"] == "Name the first winners."
    finally:
        _wipe("ZZPHASE")


def test_one_item_can_be_accepted_edited_and_undone() -> None:
    course = _make("ZZEDIT", "Edit check")
    course_id = course["id"]
    copy_code = None
    try:
        assert course["undo"] is False
        draft = _proposal(
            course_id,
            "Two periods.",
            [
                _full("add", "quest", "ZZEDIT-U1", title="Opening"),
                _full("add", "quest", "ZZEDIT-U2", title="Later"),
            ],
        )
        assert draft.status_code == 200, draft.text
        assert draft.json()["proposal"]["phase"] == "quests"
        message_id = draft.json()["id"]

        skipped = client.post(
            f"/studio/courses/{course_id}/messages/{message_id}/dismiss",
            json={"indexes": [0]},
        )
        assert skipped.status_code == 200, skipped.text
        assert [op["code"] for op in skipped.json()["proposal"]["operations"]] == ["ZZEDIT-U2"]
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []

        missing = client.post(
            f"/studio/courses/{course_id}/messages/{message_id}/accept",
            json={"indexes": [4]},
        )
        assert missing.status_code == 422
        assert missing.json()["detail"] == "That change is not in this proposal."

        one = client.post(
            f"/studio/courses/{course_id}/messages/{message_id}/accept",
            json={"indexes": [0]},
        )
        assert one.status_code == 200, one.text
        assert [unit["code"] for unit in one.json()["course"]["quests"]] == ["ZZEDIT-U2"]
        assert one.json()["message"]["applied"] is True
        assert [op["code"] for op in one.json()["message"]["proposal"]["operations"]] == ["ZZEDIT-U2"]
        assert one.json()["course"]["undo"] is True

        undone = client.post(f"/studio/courses/{course_id}/undo")
        assert undone.status_code == 200, undone.text
        assert undone.json()["quests"] == []
        assert undone.json()["undo"] is False
        restored = client.get(f"/studio/courses/{course_id}/messages").json()[-1]
        assert restored["applied"] is False
        assert [op["code"] for op in restored["proposal"]["operations"]] == ["ZZEDIT-U2"]

        again = client.post(f"/studio/courses/{course_id}/messages/{message_id}/accept")
        assert again.status_code == 200, again.text
        edited = client.post(
            f"/studio/courses/{course_id}/edit",
            json={"kind": "quest", "code": "ZZEDIT-U2", "title": "Later years"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["quests"][0]["title"] == "Later years"
        assert edited.json()["phase"]["name"] == "goals"
        rolled = client.post(f"/studio/courses/{course_id}/undo")
        assert rolled.status_code == 200, rolled.text
        assert rolled.json()["quests"][0]["title"] == "Later"

        stepped = client.post(f"/studio/courses/{course_id}/phase", json={"name": "quests"})
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["view"]["name"] == "quests", stepped.json()["view"]
        quest = _proposal(
            course_id,
            "One quest, still in Goals after this.",
            [_full("add", "quest", "ZZEDIT-U2-Q1", title="Winners")],
        )
        assert quest.status_code == 200, quest.text
        planted = client.post(f"/studio/courses/{course_id}/messages/{quest.json()['id']}/accept")
        assert planted.status_code == 200, planted.text
        assert planted.json()["course"]["phase"]["name"] == "goals"
        retitled = client.post(
            f"/studio/courses/{course_id}/edit",
            json={"kind": "quest", "code": "ZZEDIT-U2", "title": "Still editable"},
        )
        assert retitled.status_code == 200, retitled.text
        assert retitled.json()["quests"][0]["title"] == "Still editable"
        assert retitled.json()["phase"]["name"] == "goals"

        copied = client.post(f"/studio/courses/{course_id}/copy", json={"title": "Edit copy"})
        assert copied.status_code == 200, copied.text
        copy_code = copied.json()["code"]
        assert copied.json()["undo"] is False
        copy_undo = client.post(f"/studio/courses/{copied.json()['id']}/undo")
        assert copy_undo.status_code == 422
        assert copy_undo.json()["detail"] == "There is nothing to undo."
        assert client.get(f"/studio/courses/{course_id}").json()["quests"][0]["title"] == "Still editable"
        tutor_codes = [row["code"] for row in client.get("/courses").json()]
        assert "ZZEDIT" not in tutor_codes
    finally:
        if copy_code:
            _wipe(copy_code)
        _wipe("ZZEDIT")


def _header(title: str, theme: str) -> dict:
    return {
        "title": title,
        "audience": "12-14",
        "focus": "",
        "theme": theme,
        "depth": "standard",
        "quiz_minutes": 5,
        "sources": "none",
        "close_default": {
            "close_style": "one",
            "answer_style": "essay",
            "choice_mode": None,
            "items": [],
            "intent": "",
        },
    }


def test_stage_advances_only_from_mark_complete_and_push_writes_the_tree() -> None:
    assert not description_is_specific("city planning")
    assert description_is_specific("Triangle interior angles for learners aged 12 to 14")
    theme = "Create a course about the history of Imperial College. Include the founding and later milestones."
    course = _make("ZZYES", "Imperial")
    course_id = course["id"]
    try:
        saved = client.patch(
            f"/studio/courses/{course_id}",
            json={**_header("Imperial", theme), "quest_count": 10, "goals_per_quest": 3},
        )
        assert saved.status_code == 200, saved.text
        opened = client.post(f"/studio/courses/{course_id}/opening")
        assert opened.status_code == 200, opened.text
        opening = opened.json()["messages"][0]["content"]
        assert "one section of the course" in opening
        assert "Should I draft 10 quests from the course description?" in opening
        assert "Push draft to Tree" in opening
        for banned in ("Goals", "Close", "Ready"):
            assert banned not in opening
        assert opened.json()["messages"][0]["proposal"] is None
        assert opened.json()["course"]["quests"] == []
        assert opened.json()["course"]["stage"]["name"] == "quests"

        blocked = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert blocked.status_code == 422
        assert "No quests yet." in blocked.json()["detail"]

        chat = client.post(f"/studio/courses/{course_id}/turns", json={"content": "yes please"})
        assert chat.status_code == 200, chat.text
        assert chat.json()["wrote"] is False
        assert chat.json()["handled"] is False
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []

        drafted = client.post(f"/studio/courses/{course_id}/fallback", json={"content": "yes please"})
        assert drafted.status_code == 200, drafted.text
        assert drafted.json()["wrote"] is False
        assert "Push draft to Tree" in drafted.json()["assistant"]["content"]
        assert "I've added" not in drafted.json()["assistant"]["content"]
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []

        pushed = client.post(f"/studio/courses/{course_id}/push-draft")
        assert pushed.status_code == 200, pushed.text
        titles = [quest["title"] for quest in pushed.json()["quests"]]
        assert len(titles) == 10
        assert all("Imperial College" in title or "imperial college" in title.lower() for title in titles)
        assert ": quest" not in " ".join(titles)
        again = client.post(f"/studio/courses/{course_id}/push-draft")
        assert again.status_code == 200, again.text
        assert len(again.json()["quests"]) == 10

        renamed = client.post(
            f"/studio/courses/{course_id}/tree",
            json={"action": "update_quest", "code": "ZZYES-Q1", "title": "Founding of Imperial College"},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["quests"][0]["title"] == "Founding of Imperial College"
        locked = client.post(
            f"/studio/courses/{course_id}/tree",
            json={"action": "update_goal", "code": "ZZYES-Q1", "position": 1, "learning_goal": "Too soon", "success_criterion": "Too soon"},
        )
        assert locked.status_code == 422
        assert "Goals" in locked.json()["detail"]

        moved = client.post(f"/studio/courses/{course_id}/turns", json={"content": "move on"})
        assert moved.status_code == 200, moved.text
        assert "Mark Complete" in moved.json()["assistant"]["content"]
        assert moved.json()["course"]["stage"]["name"] == "quests"

        advanced = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["stage"]["name"] == "goals"
        goals_text = client.get(f"/studio/courses/{course_id}/messages").json()[-1]["content"]
        assert "success criterion" in goals_text
        assert "3 goals" in goals_text
        assert "Push draft to Tree" in goals_text

        goal_draft = client.post(f"/studio/courses/{course_id}/fallback", json={"content": "draft the goals"})
        assert goal_draft.status_code == 200, goal_draft.text
        goal_push = client.post(f"/studio/courses/{course_id}/push-draft")
        assert goal_push.status_code == 200, goal_push.text
        first = goal_push.json()["quests"][0]
        assert len(first["goals"]) == 3
        assert all(goal["success_criterion"] for goal in first["goals"])

        edited_goal = client.post(
            f"/studio/courses/{course_id}/tree",
            json={
                "action": "update_goal",
                "code": "ZZYES-Q1",
                "position": 1,
                "learning_goal": "Explain the founding of Imperial College.",
                "success_criterion": "States the year the college was founded.",
            },
        )
        assert edited_goal.status_code == 200, edited_goal.text
        assert edited_goal.json()["quests"][0]["goals"][0]["success_criterion"] == "States the year the college was founded."

        to_close = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert to_close.status_code == 200, to_close.text
        assert to_close.json()["stage"]["name"] == "close"
        close_text = client.get(f"/studio/courses/{course_id}/messages").json()[-1]["content"]
        assert "essay" in close_text
        assert "one quest at a time" in close_text

        close_draft = client.post(f"/studio/courses/{course_id}/fallback", json={"content": "draft the closes"})
        assert close_draft.status_code == 200, close_draft.text
        close_push = client.post(f"/studio/courses/{course_id}/push-draft")
        assert close_push.status_code == 200, close_push.text
        assert close_push.json()["quests"][0]["close"]["answer_style"] == "essay"

        essay = client.post(
            f"/studio/courses/{course_id}/tree",
            json={
                "action": "set_close",
                "code": "ZZYES-Q1",
                "close": {
                    "close_style": "one",
                    "answer_style": "essay",
                    "choice_mode": None,
                    "items": [],
                    "questions": [{"text": "Why was Imperial College founded?"}],
                    "intent": "",
                },
            },
        )
        assert essay.status_code == 200, essay.text
        single = client.post(
            f"/studio/courses/{course_id}/tree",
            json={
                "action": "set_close",
                "code": "ZZYES-Q2",
                "close": {
                    "close_style": "one",
                    "answer_style": "multiple_choice",
                    "choice_mode": "predefined",
                    "selection": "single",
                    "items": [{"text": "1907", "correct": True}, {"text": "1807", "correct": False}],
                    "questions": [{"text": "When was it founded?"}],
                    "intent": "",
                },
            },
        )
        assert single.status_code == 200, single.text
        assert single.json()["quests"][1]["close"]["selection"] == "single"
        multi = client.post(
            f"/studio/courses/{course_id}/tree",
            json={
                "action": "set_close",
                "code": "ZZYES-Q3",
                "close": {
                    "close_style": "one",
                    "answer_style": "multiple_choice",
                    "choice_mode": "predefined",
                    "selection": "multi",
                    "items": [
                        {"text": "Science", "correct": True},
                        {"text": "Medicine", "correct": True},
                        {"text": "Farming", "correct": False},
                    ],
                    "questions": [{"text": "Which fields shaped the college?"}],
                    "intent": "",
                },
            },
        )
        assert multi.status_code == 200, multi.text
        assert multi.json()["quests"][2]["close"]["selection"] == "multi"

        thin = client.post(
            f"/studio/courses/{course_id}/tree",
            json={
                "action": "set_close",
                "code": "ZZYES-Q4",
                "close": {
                    "close_style": "one",
                    "answer_style": "multiple_choice",
                    "choice_mode": "predefined",
                    "selection": "single",
                    "items": [{"text": "Only one"}],
                    "questions": [{"text": "Pick one."}],
                    "intent": "",
                },
            },
        )
        assert thin.status_code == 422

        ready = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert ready.status_code == 200, ready.text
        assert ready.json()["stage"]["name"] == "ready"
        assert ready.json()["ready"] is False
        assert ready.json()["can_advance"] is True
        submitted = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["ready"] is True
        assert submitted.json()["can_advance"] is False
    finally:
        _wipe("ZZYES")

def test_course_description_saves_and_a_blank_close_does_not_require_intent() -> None:
    course = _make("ZZDESC", "Described")
    course_id = course["id"]
    theme = "Learners aged 12 to 14 studying interior angles"
    try:
        saved = client.patch(
            f"/studio/courses/{course_id}",
            json={**_header("Described", ""), "description": theme},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["theme"] == theme
        assert "is required for dynamic choices" not in saved.text
        reloaded = client.get(f"/studio/courses/{course_id}").json()
        assert reloaded["theme"] == theme

        revised = "A course about interior angles for learners aged 12 to 14"
        again = client.patch(
            f"/studio/courses/{course_id}",
            json={
                **_header("Described", revised),
                "close_default": {
                    "close_style": "one",
                    "answer_style": "multiple_choice",
                    "choice_mode": "dynamic",
                    "items": [],
                    "intent": "",
                },
            },
        )
        assert again.status_code == 200, again.text
        assert again.json()["theme"] == revised
        assert again.json()["close_default"]["choice_mode"] == "dynamic"
        assert again.json()["close_default"]["intent"] == ""
        assert "is required for dynamic choices" not in again.text
        assert client.get(f"/studio/courses/{course_id}").json()["theme"] == revised

        posted = _proposal(
            course_id,
            "A first unit, with a close that has no intent yet.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZDESC-U1-Q1",
                    parent="ZZDESC-U1",
                    title="Name the angle",
                    close={
                        "close_style": "one",
                        "answer_style": "multiple_choice",
                        "choice_mode": "dynamic",
                        "items": [],
                        "intent": "",
                    },
                ),
            ],
        )
        assert posted.status_code == 200, posted.text
        assert "is required for dynamic choices" not in posted.text
        assert [op["code"] for op in posted.json()["proposal"]["operations"]] == ["ZZDESC-U1-Q1"]
    finally:
        _wipe("ZZDESC")


def test_a_missing_move_parent_is_one_sentence_and_a_quest_in_the_patch_is_not() -> None:
    course = _make("ZZPAR", "Parents")
    course_id = course["id"]
    try:
        missing = _proposal(
            course_id,
            "Two moves under a quest that is not here.",
            [
                _full("add", "move", "ZZPAR-Q9-M1", parent="ZZPAR-Q9", title="Held one"),
                _full("add", "move", "ZZPAR-Q9-M2", parent="ZZPAR-Q9", title="Held two"),
            ],
        )
        assert missing.status_code == 422, missing.text
        detail = missing.json()["detail"]
        assert detail == "The parent ZZPAR-Q9 is not in this course yet."
        assert detail.count("ZZPAR-Q9") == 1
        assert "must be a short code" not in detail
        assert client.get(f"/studio/courses/{course_id}").json()["quests"] == []

        ordered = _proposal(
            course_id,
            "The move is listed before its quest.",
            [
                _full("add", "move", "ZZPAR-Q1-M1", parent=None, title="First move"),
                _full("add", "quest", "ZZPAR-Q1", title="First quest"),
            ],
        )
        assert ordered.status_code == 200, ordered.text
        assert "must be a short code" not in ordered.text
        assert "is not in this course" not in ordered.text
        assert [op["code"] for op in ordered.json()["proposal"]["operations"]] == [
            "ZZPAR-Q1",
            "ZZPAR-Q1-M1",
        ]
        written = client.post(f"/studio/courses/{course_id}/messages/{ordered.json()['id']}/accept")
        assert written.status_code == 200, written.text
        quest = written.json()["course"]["quests"][0]
        assert quest["code"] == "ZZPAR-Q1"
        assert [move["code"] for move in quest["moves"]] == ["ZZPAR-Q1-M1"]
    finally:
        _wipe("ZZPAR")


def test_lift_revision_keeps_quests_and_drops_units() -> None:
    text = LIFT_REVISION.read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert "studio_quest_goals" in upgrade
    assert "UPDATE studio_quests" in upgrade
    assert 'op.drop_table("studio_units")' in upgrade
    assert "DELETE FROM" not in upgrade.upper()
    for name in ("students", "courses", "units", "quests", "beats", "sessions", "messages"):
        assert f'"{name}"' not in upgrade
    listed = client.get("/studio/courses").json()
    geo = next((row for row in listed if row["code"] == "GEO"), None)
    if geo is None:
        return
    course = client.get(f"/studio/courses/{geo['id']}").json()
    assert "units" not in course
    assert any(quest["code"] == "GEO-U1-Q1" for quest in course["quests"])


def test_several_goals_a_missing_criterion_and_an_empty_close() -> None:
    course = _make("ZZGLS", "Several goals")
    course_id = course["id"]
    try:
        draft = _proposal(
            course_id,
            "Three goals, and the second criterion is still open.",
            [
                _full(
                    "add",
                    "quest",
                    "ZZGLS-Q1",
                    title="Triangle angles",
                    goals=[
                        {
                            "position": 1,
                            "learning_goal": "Understand that the angles of a triangle add to 180°",
                            "success_criterion": "States that the three angles add to 180° and uses that to find a missing angle.",
                        },
                        {
                            "position": 2,
                            "learning_goal": "Name an exterior angle",
                            "success_criterion": "",
                        },
                        {
                            "position": 3,
                            "learning_goal": "Find a missing angle",
                            "success_criterion": "Finds the missing angle of a drawn triangle.",
                        },
                    ],
                )
            ],
        )
        assert draft.status_code == 200, draft.text
        planted = client.post(f"/studio/courses/{course_id}/messages/{draft.json()['id']}/accept")
        assert planted.status_code == 200, planted.text
        tree = planted.json()["course"]
        quest = tree["quests"][0]
        assert [goal["position"] for goal in quest["goals"]] == [1, 2, 3]
        assert quest["learning_goal"].startswith("Understand")
        assert tree["phase"]["name"] == "goals"
        assert "ZZGLS-Q1: no success criterion" in tree["gaps"]

        stepped = client.post(f"/studio/courses/{course_id}/phase", json={"name": "goals"})
        assert stepped.status_code == 200, stepped.text
        goals_only = _proposal(
            course_id,
            "Fill the missing criterion.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZGLS-Q1",
                    goals=[
                        {
                            "position": 1,
                            "learning_goal": "Understand that the angles of a triangle add to 180°",
                            "success_criterion": "States that the three angles add to 180° and uses that to find a missing angle.",
                        },
                        {
                            "position": 2,
                            "learning_goal": "Name an exterior angle",
                            "success_criterion": "Points to an exterior angle on a drawn triangle.",
                        },
                        {
                            "position": 3,
                            "learning_goal": "Find a missing angle",
                            "success_criterion": "Finds the missing angle of a drawn triangle.",
                        },
                    ],
                )
            ],
        )
        assert goals_only.status_code == 200, goals_only.text
        wrote_goals = client.post(f"/studio/courses/{course_id}/messages/{goals_only.json()['id']}/accept")
        assert wrote_goals.status_code == 200, wrote_goals.text
        assert "ZZGLS-Q1: no success criterion" not in wrote_goals.json()["course"]["gaps"]
        closed = _proposal(
            course_id,
            "Save an empty question list.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZGLS-Q1",
                    close={
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "questions": [],
                        "intent": "",
                    },
                )
            ],
        )
        assert closed.status_code == 200, closed.text
        wrote_close = client.post(f"/studio/courses/{course_id}/messages/{closed.json()['id']}/accept")
        assert wrote_close.status_code == 200, wrote_close.text
        done = wrote_close.json()["course"]
        assert done["quests"][0]["close"]["questions"] == []
        assert done["phase"]["name"] == "ready"
        assert "no close style" not in " ".join(done["gaps"])
        assert all("question" not in gap for gap in done["gaps"])
    finally:
        _wipe("ZZGLS")


def test_quest_count_and_goals_per_quest_save_and_are_not_a_cap() -> None:
    course = _make("ZZQCNT", "Counts")
    course_id = course["id"]
    try:
        assert course["quest_count"] == 10
        assert course["goals_per_quest"] == 3
        saved = client.patch(
            f"/studio/courses/{course_id}",
            json={**_header("Counts", "city planning"), "quest_count": 4, "goals_per_quest": 2},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["quest_count"] == 4
        assert saved.json()["goals_per_quest"] == 2
        again = client.get(f"/studio/courses/{course_id}").json()
        assert again["quest_count"] == 4
        assert again["goals_per_quest"] == 2
        extra = _proposal(
            course_id,
            "More quests than the target.",
            [
                _full("add", "quest", f"ZZQCNT-Q{index}", title=f"Quest {index}")
                for index in range(1, 6)
            ],
        )
        assert extra.status_code == 200, extra.text
        planted = client.post(f"/studio/courses/{course_id}/messages/{extra.json()['id']}/accept")
        assert planted.status_code == 200, planted.text
        assert len(planted.json()["course"]["quests"]) == 5
        assert planted.json()["course"]["quest_count"] == 4
    finally:
        _wipe("ZZQCNT")


def test_a_close_draft_patches_only_the_quests_it_names() -> None:
    course = _make("ZZPART", "Partial")
    course_id = course["id"]
    try:
        opened = client.post(f"/studio/courses/{course_id}/opening")
        assert opened.status_code == 200, opened.text
        for title in ("First", "Second", "Third"):
            added = client.post(
                f"/studio/courses/{course_id}/tree",
                json={"action": "add_quest", "title": title},
            )
            assert added.status_code == 200, added.text

        retitle = _proposal(
            course_id,
            "Revise the second quest only.",
            [_full("update", "quest", "ZZPART-Q2", title="Second revised")],
        )
        assert retitle.status_code == 200, retitle.text
        quests_push = client.post(f"/studio/courses/{course_id}/push-draft")
        assert quests_push.status_code == 200, quests_push.text
        titles = {quest["code"]: quest["title"] for quest in quests_push.json()["quests"]}
        assert titles == {
            "ZZPART-Q1": "First",
            "ZZPART-Q2": "Second revised",
            "ZZPART-Q3": "Third",
        }

        advanced = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert advanced.status_code == 200, advanced.text
        for code in ("ZZPART-Q1", "ZZPART-Q2", "ZZPART-Q3"):
            goal = client.post(
                f"/studio/courses/{course_id}/tree",
                json={
                    "action": "add_goal",
                    "code": code,
                    "learning_goal": f"Goal for {code}",
                    "success_criterion": f"States a fact from {code}.",
                },
            )
            assert goal.status_code == 200, goal.text

        goals = _proposal(
            course_id,
            "Revise only the second goal.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZPART-Q2",
                    goals=[
                        {
                            "position": 1,
                            "learning_goal": "Goal for ZZPART-Q2 revised",
                            "success_criterion": "States the revised fact.",
                        }
                    ],
                )
            ],
        )
        assert goals.status_code == 200, goals.text
        goals_push = client.post(f"/studio/courses/{course_id}/push-draft")
        assert goals_push.status_code == 200, goals_push.text
        by_code = {quest["code"]: quest for quest in goals_push.json()["quests"]}
        assert by_code["ZZPART-Q1"]["goals"][0]["success_criterion"] == "States a fact from ZZPART-Q1."
        assert by_code["ZZPART-Q2"]["goals"][0]["success_criterion"] == "States the revised fact."
        assert by_code["ZZPART-Q3"]["goals"][0]["success_criterion"] == "States a fact from ZZPART-Q3."

        to_close = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert to_close.status_code == 200, to_close.text

        def essay(text: str) -> dict:
            return {
                "close_style": "one",
                "answer_style": "essay",
                "choice_mode": None,
                "items": [],
                "questions": [{"text": text}],
                "intent": "",
            }

        for code, text in (
            ("ZZPART-Q1", "Essay one"),
            ("ZZPART-Q2", "Essay two"),
            ("ZZPART-Q3", "Essay three"),
        ):
            saved = client.post(
                f"/studio/courses/{course_id}/tree",
                json={"action": "set_close", "code": code, "close": essay(text)},
            )
            assert saved.status_code == 200, saved.text

        multi = {
            "close_style": "one",
            "answer_style": "multiple_choice",
            "choice_mode": "predefined",
            "selection": "multi",
            "items": [
                {"text": "Science", "correct": True},
                {"text": "Medicine", "correct": True},
                {"text": "Farming", "correct": False},
            ],
            "questions": [{"text": "Which fields?"}],
            "intent": "",
        }
        drafted = _proposal(
            course_id,
            "Change only the second close to multi-choice.",
            [
                _full("update", "quest", "ZZPART-Q2", close=multi),
                _full("update", "quest", "ZZPART-Q1", title="Do not rename", close=None),
            ],
        )
        assert drafted.status_code == 200, drafted.text
        pushed = client.post(f"/studio/courses/{course_id}/push-draft")
        assert pushed.status_code == 200, pushed.text
        quests = {quest["code"]: quest for quest in pushed.json()["quests"]}
        assert quests["ZZPART-Q1"]["title"] == "First"
        assert quests["ZZPART-Q1"]["close"]["answer_style"] == "essay"
        assert quests["ZZPART-Q1"]["close"]["questions"][0]["text"] == "Essay one"
        assert quests["ZZPART-Q3"]["close"]["answer_style"] == "essay"
        assert quests["ZZPART-Q3"]["close"]["questions"][0]["text"] == "Essay three"
        close = quests["ZZPART-Q2"]["close"]
        assert close["answer_style"] == "multiple_choice"
        assert close["selection"] == "multi"
        assert [item["text"] for item in close["items"]] == ["Science", "Medicine", "Farming"]
        assert [item.get("correct", False) for item in close["items"]] == [True, True, False]
    finally:
        _wipe("ZZPART")


def test_a_close_draft_does_not_push_while_the_stage_is_goals() -> None:
    course = _make("ZZBACK", "Back to goals")
    course_id = course["id"]
    try:
        opened = client.post(f"/studio/courses/{course_id}/opening")
        assert opened.status_code == 200, opened.text
        added = client.post(
            f"/studio/courses/{course_id}/tree",
            json={"action": "add_quest", "title": "First"},
        )
        assert added.status_code == 200, added.text
        assert client.post(f"/studio/courses/{course_id}/advance-stage").status_code == 200
        goal = client.post(
            f"/studio/courses/{course_id}/tree",
            json={
                "action": "add_goal",
                "code": "ZZBACK-Q1",
                "learning_goal": "Name the first idea.",
                "success_criterion": "States the first idea.",
            },
        )
        assert goal.status_code == 200, goal.text
        assert client.post(f"/studio/courses/{course_id}/advance-stage").status_code == 200

        close = _proposal(
            course_id,
            "An essay close for the first quest.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZBACK-Q1",
                    close={
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "questions": [{"text": "Why does this quest matter?"}],
                        "intent": "",
                    },
                )
            ],
        )
        assert close.status_code == 200, close.text
        assert close.json()["proposal"]["phase"] == "close"
        ready = client.get(f"/studio/courses/{course_id}")
        assert ready.status_code == 200, ready.text
        assert ready.json()["can_push"] is True
        assert ready.json()["stage_view"]["name"] == "close"

        stepped = client.post(f"/studio/courses/{course_id}/stage", json={"name": "goals"})
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["stage_view"]["name"] == "goals"
        assert stepped.json()["can_push"] is False
        ignored = client.post(f"/studio/courses/{course_id}/push-draft")
        assert ignored.status_code == 200, ignored.text
        assert "different stage" not in ignored.text
        quest = ignored.json()["quests"][0]
        assert quest["close"] is None
        assert quest["goals"][0]["success_criterion"] == "States the first idea."
        assert ignored.json()["can_push"] is False

        revised = _proposal(
            course_id,
            "Revise the goal for this stage.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZBACK-Q1",
                    goals=[
                        {
                            "position": 1,
                            "learning_goal": "Name the revised idea.",
                            "success_criterion": "States the revised idea.",
                        }
                    ],
                )
            ],
        )
        assert revised.status_code == 200, revised.text
        assert revised.json()["proposal"]["phase"] == "goals"
        waiting = client.get(f"/studio/courses/{course_id}")
        assert waiting.json()["can_push"] is True
        pushed = client.post(f"/studio/courses/{course_id}/push-draft")
        assert pushed.status_code == 200, pushed.text
        saved = pushed.json()["quests"][0]
        assert saved["goals"][0]["success_criterion"] == "States the revised idea."
        assert saved["close"] is None
        assert pushed.json()["stage_view"]["name"] == "goals"
    finally:
        _wipe("ZZBACK")


def test_stepping_back_can_push_and_mark_complete_returns_to_the_furthest_stage() -> None:
    course = _make("ZZRET", "Return")
    course_id = course["id"]
    try:
        assert client.post(f"/studio/courses/{course_id}/opening").status_code == 200
        added = client.post(
            f"/studio/courses/{course_id}/tree",
            json={"action": "add_quest", "title": "First"},
        )
        assert added.status_code == 200, added.text
        assert client.post(f"/studio/courses/{course_id}/advance-stage").status_code == 200
        goal = client.post(
            f"/studio/courses/{course_id}/tree",
            json={
                "action": "add_goal",
                "code": "ZZRET-Q1",
                "learning_goal": "Name the first idea.",
                "success_criterion": "States the first idea.",
            },
        )
        assert goal.status_code == 200, goal.text
        opened_close = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert opened_close.status_code == 200, opened_close.text
        assert opened_close.json()["stage"]["name"] == "close"

        stepped = client.post(f"/studio/courses/{course_id}/stage", json={"name": "goals"})
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["stage_view"]["name"] == "goals"
        drafted = _proposal(
            course_id,
            "Add one more goal.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZRET-Q1",
                    goals=[
                        {
                            "position": 1,
                            "learning_goal": "Name the first idea.",
                            "success_criterion": "States the first idea.",
                        },
                        {
                            "position": 2,
                            "learning_goal": "Name a second idea.",
                            "success_criterion": "States the second idea.",
                        },
                    ],
                )
            ],
        )
        assert drafted.status_code == 200, drafted.text
        assert drafted.json()["proposal"]["phase"] == "goals"
        pushed = client.post(f"/studio/courses/{course_id}/push-draft")
        assert pushed.status_code == 200, pushed.text
        goals = pushed.json()["quests"][0]["goals"]
        assert [row["learning_goal"] for row in goals] == ["Name the first idea.", "Name a second idea."]
        assert pushed.json()["can_advance"] is True
        assert pushed.json()["stage"]["name"] == "close"
        returned = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert returned.status_code == 200, returned.text
        assert returned.json()["stage"]["name"] == "close"
        assert returned.json()["stage_view"]["name"] == "close"
        assert [row["learning_goal"] for row in returned.json()["quests"][0]["goals"]] == [
            "Name the first idea.",
            "Name a second idea.",
        ]

        back_quests = client.post(f"/studio/courses/{course_id}/stage", json={"name": "quests"})
        assert back_quests.status_code == 200, back_quests.text
        assert back_quests.json()["stage_view"]["name"] == "quests"
        retitle = _proposal(
            course_id,
            "Rename the first quest.",
            [_full("update", "quest", "ZZRET-Q1", title="First revised")],
        )
        assert retitle.status_code == 200, retitle.text
        assert retitle.json()["proposal"]["phase"] == "quests"
        quests_push = client.post(f"/studio/courses/{course_id}/push-draft")
        assert quests_push.status_code == 200, quests_push.text
        assert quests_push.json()["quests"][0]["title"] == "First revised"
        assert quests_push.json()["can_advance"] is True
        quests_back = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert quests_back.status_code == 200, quests_back.text
        assert quests_back.json()["stage"]["name"] == "close"
        assert quests_back.json()["stage_view"]["name"] == "close"
        assert quests_back.json()["quests"][0]["title"] == "First revised"
        assert len(quests_back.json()["quests"][0]["goals"]) == 2

        essay = client.post(
            f"/studio/courses/{course_id}/tree",
            json={
                "action": "set_close",
                "code": "ZZRET-Q1",
                "close": {
                    "close_style": "one",
                    "answer_style": "essay",
                    "choice_mode": None,
                    "items": [],
                    "questions": [{"text": "Why does this quest matter?"}],
                    "intent": "",
                },
            },
        )
        assert essay.status_code == 200, essay.text
        to_ready = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert to_ready.status_code == 200, to_ready.text
        assert to_ready.json()["stage"]["name"] == "ready"
        assert to_ready.json()["ready"] is False
        back_close = client.post(f"/studio/courses/{course_id}/stage", json={"name": "close"})
        assert back_close.status_code == 200, back_close.text
        assert back_close.json()["stage_view"]["name"] == "close"
        revised_close = _proposal(
            course_id,
            "Change the closing question.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZRET-Q1",
                    close={
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "questions": [{"text": "What should you remember?"}],
                        "intent": "",
                    },
                )
            ],
        )
        assert revised_close.status_code == 200, revised_close.text
        close_push = client.post(f"/studio/courses/{course_id}/push-draft")
        assert close_push.status_code == 200, close_push.text
        assert close_push.json()["quests"][0]["close"]["questions"][0]["text"] == "What should you remember?"
        assert close_push.json()["can_advance"] is True
        close_back = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert close_back.status_code == 200, close_back.text
        assert close_back.json()["stage"]["name"] == "ready"
        assert close_back.json()["stage_view"]["name"] == "ready"
        assert close_back.json()["ready"] is False
        assert close_back.json()["quests"][0]["close"]["questions"][0]["text"] == "What should you remember?"
        assert close_back.json()["quests"][0]["title"] == "First revised"
    finally:
        _wipe("ZZRET")


def _goals_stage(code: str) -> str:
    course = _make(code, "Goals")
    course_id = course["id"]
    opened = client.post(f"/studio/courses/{course_id}/opening")
    assert opened.status_code == 200, opened.text
    for title in ("First", "Second"):
        added = client.post(
            f"/studio/courses/{course_id}/tree",
            json={"action": "add_quest", "title": title},
        )
        assert added.status_code == 200, added.text
    advanced = client.post(f"/studio/courses/{course_id}/advance-stage")
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["stage"]["name"] == "goals"
    return course_id


def _goal(position: int, goal: str, criterion: str, **extra) -> dict:
    row = {"position": position, "learning_goal": goal, "success_criterion": criterion}
    row.update(extra)
    return row


def test_a_goals_draft_writes_every_quest_it_names() -> None:
    try:
        course_id = _goals_stage("ZZGOAL2")
        prompt = client.get(f"/studio/courses/{course_id}/prompt").json()
        assert "Do not stop after the first quest." in prompt["system_prompt"]
        assert "one block per quest" in prompt["system_prompt"]
        items = prompt["response_schema"]["properties"]["patch"]["anyOf"][1]["properties"]["operations"]["items"]
        assert items["description"] == "One update per quest code. Do not stop after the first quest."
        assert items["properties"]["goals"]["description"] == "Only this quest's goals. Later quests get their own operation."

        both = _proposal(
            course_id,
            "Goals for both quests.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZGOAL2-Q1",
                    goals=[_goal(1, "Name the first idea.", "States the first idea.")],
                ),
                _full(
                    "update",
                    "quest",
                    "ZZGOAL2-Q2",
                    goals=[_goal(1, "Name the second idea.", "States the second idea.")],
                ),
            ],
        )
        assert both.status_code == 200, both.text
        pushed = client.post(f"/studio/courses/{course_id}/push-draft")
        assert pushed.status_code == 200, pushed.text
        by_code = {quest["code"]: quest for quest in pushed.json()["quests"]}
        assert by_code["ZZGOAL2-Q1"]["goals"][0]["learning_goal"] == "Name the first idea."
        assert by_code["ZZGOAL2-Q1"]["goals"][0]["success_criterion"] == "States the first idea."
        assert by_code["ZZGOAL2-Q2"]["goals"][0]["learning_goal"] == "Name the second idea."
        assert by_code["ZZGOAL2-Q2"]["goals"][0]["success_criterion"] == "States the second idea."
        assert pushed.json()["can_advance"] is True
        advanced = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["stage"]["name"] == "close"
        kept = {quest["code"]: quest for quest in advanced.json()["quests"]}
        assert kept["ZZGOAL2-Q1"]["goals"][0]["success_criterion"] == "States the first idea."
        assert kept["ZZGOAL2-Q2"]["goals"][0]["success_criterion"] == "States the second idea."
    finally:
        _wipe("ZZGOAL2")

    try:
        course_id = _goals_stage("ZZGOAL2")
        reply = "\n".join(
            [
                "ZZGOAL2-Q1",
                "Goal: Name the first idea.",
                "Success criterion: States the first idea.",
                "ZZGOAL2-Q2",
                "Goal: Name the second idea.",
                "Success criterion: States the second idea.",
            ]
        )
        truncated = _proposal(
            course_id,
            reply,
            [
                _full(
                    "update",
                    "quest",
                    "ZZGOAL2-Q1",
                    goals=[_goal(1, "Name the first idea.", "States the first idea.")],
                )
            ],
        )
        assert truncated.status_code == 200, truncated.text
        saved_codes = [op["code"] for op in truncated.json()["proposal"]["operations"]]
        assert saved_codes == ["ZZGOAL2-Q1", "ZZGOAL2-Q2"]
        pushed = client.post(f"/studio/courses/{course_id}/push-draft")
        assert pushed.status_code == 200, pushed.text
        by_code = {quest["code"]: quest for quest in pushed.json()["quests"]}
        assert by_code["ZZGOAL2-Q1"]["goals"][0]["success_criterion"] == "States the first idea."
        assert by_code["ZZGOAL2-Q2"]["goals"][0]["learning_goal"] == "Name the second idea."
        assert by_code["ZZGOAL2-Q2"]["goals"][0]["success_criterion"] == "States the second idea."
        assert pushed.json()["can_advance"] is True
        assert "Skipped" not in pushed.text
    finally:
        _wipe("ZZGOAL2")

    try:
        course_id = _goals_stage("ZZSKIPG")
        only_first = _proposal(
            course_id,
            "A goal for the first quest only.",
            [
                _full(
                    "update",
                    "quest",
                    "ZZSKIPG-Q1",
                    goals=[_goal(1, "Name the first idea.", "States the first idea.")],
                )
            ],
        )
        assert only_first.status_code == 200, only_first.text
        pushed = client.post(f"/studio/courses/{course_id}/push-draft")
        assert pushed.status_code == 200, pushed.text
        by_code = {quest["code"]: quest for quest in pushed.json()["quests"]}
        assert by_code["ZZSKIPG-Q1"]["goals"][0]["success_criterion"] == "States the first idea."
        assert by_code["ZZSKIPG-Q2"]["goals"] == []
        assert pushed.json()["can_advance"] is False
        messages = client.get(f"/studio/courses/{course_id}/messages").json()
        assert messages[-1]["content"] == (
            "Skipped ZZSKIPG-Q2, which still needs a goal and a success criterion."
        )
        assert messages[-1]["proposal"] is None
        blocked = client.post(f"/studio/courses/{course_id}/advance-stage")
        assert blocked.status_code == 422
        assert "ZZSKIPG-Q2" in blocked.json()["detail"]
    finally:
        _wipe("ZZSKIPG")
