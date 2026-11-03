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
    StudioSettings,
    StudioUnit,
)
from app.seed import seed

client = TestClient(app)

REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "009_studio.py"


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
                            "quest",
                            "ZZGEO-U9-Q1",
                            parent="ZZGEO-U9",
                            title="Missing unit",
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
                        _full("add", "unit", "ZZGEO-U1", parent="ZZGEO", title="Angles"),
                        _full(
                            "add",
                            "quest",
                            "ZZGEO-U1-Q1",
                            parent="ZZGEO-U1",
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
        assert bad_close.status_code == 422
        assert "close_style" in bad_close.json()["detail"]

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
                        _full("add", "unit", "ZZGEO-U1", parent="ZZGEO", title="Angles"),
                        _full(
                            "add",
                            "quest",
                            "ZZGEO-U1-Q1",
                            parent="ZZGEO-U1",
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
        assert dynamic_items.status_code == 422
        assert "items" in dynamic_items.json()["detail"]

        saved = client.get(f"/studio/courses/{course_id}").json()
        assert saved["units"] == []
        assert client.get(f"/studio/courses/{course_id}/messages").json() == []
        tutor_codes = [row["code"] for row in client.get("/courses").json()]
        assert "ZZGEO" not in tutor_codes
    finally:
        _wipe("ZZGEO")


def test_accepted_patch_writes_by_code_and_uses_the_close_default() -> None:
    course = _make()
    course_id = course["id"]
    try:
        prefs = client.patch(
            f"/studio/courses/{course_id}",
            json={
                "title": "Triangles",
                "audience": "Grade 6, new to polygons",
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
                "content": "Add the first unit and two quests. Nothing is saved until you accept.",
                "proposal": {
                    "operations": [
                        _full(
                            "add",
                            "unit",
                            "ZZGEO-U1",
                            parent="ZZGEO",
                            title="Triangles",
                            learning_goal="A triangle is a three-sided polygon.",
                            success_criterion="The learner names three sides.",
                        ),
                        _full(
                            "add",
                            "quest",
                            "ZZGEO-U1-Q1",
                            parent="ZZGEO-U1",
                            title="Three sides",
                        ),
                        _full(
                            "add",
                            "quest",
                            "ZZGEO-U1-Q2",
                            parent="ZZGEO-U1",
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
        assert client.get(f"/studio/courses/{course_id}").json()["units"] == []
        message_id = draft.json()["id"]

        duplicate = client.post(
            f"/studio/courses/{course_id}/messages",
            json={
                "role": "assistant",
                "content": "That code is taken.",
                "proposal": {
                    "operations": [
                        _full("add", "unit", "ZZGEO-U1", parent="ZZGEO", title="Again"),
                        _full("add", "quest", "ZZGEO-U1", parent="ZZGEO-U1", title="Same code"),
                    ]
                },
            },
        )
        assert duplicate.status_code == 422
        assert "code" in duplicate.json()["detail"]

        accepted = client.post(f"/studio/courses/{course_id}/messages/{message_id}/accept")
        assert accepted.status_code == 200, accepted.text
        tree = accepted.json()["course"]
        assert tree["units"][0]["code"] == "ZZGEO-U1"
        quests = {quest["code"]: quest for quest in tree["units"][0]["quests"]}
        assert quests["ZZGEO-U1-Q1"]["close"]["choice_mode"] == "dynamic"
        assert quests["ZZGEO-U1-Q1"]["close"]["items"] == []
        assert quests["ZZGEO-U1-Q1"]["close"]["intent"].startswith("A new triangle")
        assert quests["ZZGEO-U1-Q2"]["close"]["choice_mode"] == "predefined"
        assert [item["text"] for item in quests["ZZGEO-U1-Q2"]["close"]["items"]] == [
            "90 degrees",
            "180 degrees",
            "360 degrees",
        ]
        assert quests["ZZGEO-U1-Q1"]["moves"][0]["code"] == "ZZGEO-U1-Q1-M1"
        assert accepted.json()["message"]["applied"] is True
        fresh = client.get(f"/studio/courses/{course_id}").json()
        fresh_quests = {quest["code"]: quest for quest in fresh["units"][0]["quests"]}
        assert fresh_quests["ZZGEO-U1-Q1"]["close"]["choice_mode"] == "dynamic"
        assert fresh_quests["ZZGEO-U1-Q1"]["close"]["items"] == []
        assert fresh_quests["ZZGEO-U1-Q2"]["close"]["items"][1]["text"] == "180 degrees"

        again = client.post(f"/studio/courses/{course_id}/messages/{message_id}/accept")
        assert again.status_code == 409

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
        after_remove = gone.json()["course"]["units"][0]
        assert [quest["code"] for quest in after_remove["quests"]] == ["ZZGEO-U1-Q2"]
        stale = client.post(f"/studio/courses/{course_id}/messages/{renamed_id}/accept")
        assert stale.status_code == 200, stale.text
        assert stale.json()["course"]["units"][0]["quests"][0]["title"] == "Interior angle sum"

        panel = client.get(f"/studio/courses/{course_id}").json()
        assert panel["units"][0]["quests"][0]["title"] == "Interior angle sum"
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
        unit = StudioUnit(
            course_id=course.id,
            code="ZZSEED-U1",
            position=1,
            title="Angles",
            learning_goal="An angle is a turn.",
            success_criterion="The learner points to the vertex.",
        )
        course.units.append(unit)
        db.flush()
        studio_quest = StudioQuest(
            course_id=course.id,
            code="ZZSEED-U1-Q1",
            position=1,
            title="Name the vertex",
            learning_goal="Name the corner.",
            success_criterion="The learner says vertex.",
        )
        unit.quests.append(studio_quest)
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
            "unit": unit.id,
            "quest": studio_quest.id,
            "close": studio_quest.close.id,
            "move": move.id,
            "message": studio_message.id,
        }
        before = {
            "courses": db.scalar(select(func.count()).select_from(StudioCourse)),
            "units": db.scalar(select(func.count()).select_from(StudioUnit)),
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
            "units": db.scalar(select(func.count()).select_from(StudioUnit)),
            "quests": db.scalar(select(func.count()).select_from(StudioQuest)),
            "moves": db.scalar(select(func.count()).select_from(StudioMove)),
            "closes": db.scalar(select(func.count()).select_from(StudioQuestClose)),
            "messages": db.scalar(select(func.count()).select_from(StudioMessage)),
            "settings": db.scalar(select(func.count()).select_from(StudioSettings)),
        }
        assert after == before
        kept_course = db.get(StudioCourse, ids["course"])
        kept_unit = db.get(StudioUnit, ids["unit"])
        kept_quest = db.get(StudioQuest, ids["quest"])
        kept_close = db.get(StudioQuestClose, ids["close"])
        kept_move = db.get(StudioMove, ids["move"])
        kept_studio_message = db.get(StudioMessage, ids["message"])
        kept_settings = db.get(StudioSettings, "default")
        assert kept_course is not None and kept_course.title == "Seed survivor"
        assert kept_course.focus == "angles"
        assert kept_course.schema_version == 1
        assert kept_unit is not None and kept_unit.code == "ZZSEED-U1"
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
    finally:
        if session_id is not None:
            db.execute(delete(TutorSession).where(TutorSession.id == session_id))
        db.execute(delete(StudioCourse).where(StudioCourse.code == "ZZSEED"))
        row = db.get(StudioSettings, "default")
        if row is not None:
            row.model = "gpt-4o-mini"
        db.commit()
        db.close()
