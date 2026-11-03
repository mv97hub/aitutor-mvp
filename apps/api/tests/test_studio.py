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
from app.studio import rejection_reply

client = TestClient(app)

REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "009_studio.py"
READY_REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "010_studio_ready.py"


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


def test_accepted_patch_writes_by_code_and_leaves_an_omitted_close_empty() -> None:
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
        assert tree["ready"] is False
        assert tree["close_default"]["choice_mode"] == "dynamic"
        quests = {quest["code"]: quest for quest in tree["units"][0]["quests"]}
        assert quests["ZZGEO-U1-Q1"]["close"] is None
        assert quests["ZZGEO-U1-Q1"]["learning_goal"] == ""
        assert "ZZGEO-U1-Q1: no learning goal" in tree["gaps"]
        assert "ZZGEO-U1-Q1: no close style" in tree["gaps"]
        assert "ZZGEO-U1: no learning goal" not in tree["gaps"]
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
        fresh_quests = {quest["code"]: quest for quest in fresh["units"][0]["quests"]}
        assert fresh_quests["ZZGEO-U1-Q1"]["close"] is None
        assert "ZZGEO-U1-Q1: no close style" in fresh["gaps"]
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
        assert "code, parent code, title, position as an integer from 1" in prompt["system_prompt"]
        assert "learning goal" in prompt["system_prompt"]
        assert "success criterion" in prompt["system_prompt"]
        assert "quest-close choices" in prompt["system_prompt"]
        assert "A position of 0 is invalid." in prompt["system_prompt"]
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
            [
                _full("add", "unit", "ZZGEO-U1", parent="ZZGEO", title="Exile", learning_goal="The story begins."),
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
                    title="The bow",
                    position=0,
                ),
            ],
        )
        assert rejected.status_code == 422
        reason = rejected.json()["detail"]
        assert reason == "Position must be an integer from 1 to 200."
        reply = rejection_reply(claim, reason)
        assert reply == reason
        assert "saved" not in reply.lower()
        assert "accepted" not in reply.lower()
        assert client.get(f"/studio/courses/{course_id}").json()["units"] == []
        assert client.get(f"/studio/courses/{course_id}/messages").json() == []

        outside = _proposal(
            course_id,
            claim,
            [_full("add", "unit", "ZZGEO-U1", parent="ZZGEO", title="Exile", position=201)],
        )
        assert outside.status_code == 422
        assert outside.json()["detail"] == "Position must be an integer from 1 to 200."
        assert client.get(f"/studio/courses/{course_id}").json()["units"] == []

        past = _proposal(
            course_id,
            claim,
            [_full("add", "unit", "ZZGEO-U1", parent="ZZGEO", title="Exile", position=5)],
        )
        assert past.status_code == 422
        assert past.json()["detail"] == "Position is past the end of this list."
        assert "saved" not in past.json()["detail"].lower()
        assert client.get(f"/studio/courses/{course_id}/messages").json() == []
    finally:
        _wipe("ZZGEO")


def test_missing_position_is_filled_with_the_next_free_number() -> None:
    course = _make()
    course_id = course["id"]
    try:
        omitted = _full("add", "unit", "ZZGEO-U2", parent="ZZGEO", title="Return", learning_goal="The city stands.")
        del omitted["position"]
        draft = _proposal(
            course_id,
            "Two units, and the server chooses their places.",
            [
                _full(
                    "add",
                    "unit",
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
        units = accepted.json()["course"]["units"]
        assert [(unit["code"], unit["position"]) for unit in units] == [("ZZGEO-U1", 1), ("ZZGEO-U2", 2)]
        fresh = client.get(f"/studio/courses/{course_id}").json()
        assert [(unit["code"], unit["position"]) for unit in fresh["units"]] == [("ZZGEO-U1", 1), ("ZZGEO-U2", 2)]
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
                    "unit",
                    "ZZGEO-U1",
                    parent="ZZGEO",
                    title="Exile",
                    learning_goal="The story begins.",
                    position=None,
                ),
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
        quest = tree["units"][0]["quests"][0]
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
        assert still["units"][0]["quests"][0]["code"] == "ZZGEO-U1-Q1"
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
                    "unit",
                    "ZZGEO-U1",
                    parent="ZZGEO",
                    title="Exile",
                    learning_goal="The story begins.",
                ),
                _full(
                    "add",
                    "quest",
                    "ZZGEO-U1-Q1",
                    parent="ZZGEO-U1",
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
        assert applied.json()["course"]["units"][0]["quests"][0]["title"] == "The bow"
        blocked = client.post(f"/studio/courses/{course_id}/ready")
        assert blocked.status_code == 422
        assert client.get(f"/studio/courses/{course_id}").json()["ready"] is False
    finally:
        _wipe("ZZGEO")
