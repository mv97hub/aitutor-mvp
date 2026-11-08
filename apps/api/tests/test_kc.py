"""Knowledge-component studio and tutor. Catalog chats stay put."""

import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, or_, select

from app.database import SessionLocal
from app.kc_prompt import build_kc_prompt
from app.main import app
from app.models import (
    KcCreatorMessage,
    KcEdge,
    KcGoal,
    KcMessage,
    KcModelPrompt,
    KcNode,
    KcSession,
    KcState,
    Message,
    Session as TutorSession,
    Student,
)
from app.seed import seed

client = TestClient(app)

REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "016_kc_tables.py"
PROMPT = Path(__file__).resolve().parents[1] / "app" / "kc_prompt.py"


def _drop_codes(codes: list[str]) -> None:
    if not codes:
        return
    db = SessionLocal()
    try:
        node_ids = list(db.scalars(select(KcNode.id).where(KcNode.code.in_(codes))))
        if not node_ids:
            db.commit()
            return
        session_ids = list(db.scalars(select(KcSession.id).where(KcSession.kc_id.in_(node_ids))))
        if session_ids:
            db.execute(delete(KcModelPrompt).where(KcModelPrompt.session_id.in_(session_ids)))
            db.execute(delete(KcMessage).where(KcMessage.session_id.in_(session_ids)))
            db.execute(delete(KcSession).where(KcSession.id.in_(session_ids)))
        db.execute(delete(KcCreatorMessage).where(KcCreatorMessage.node_id.in_(node_ids)))
        db.execute(delete(KcEdge).where(or_(KcEdge.from_kc.in_(node_ids), KcEdge.to_kc.in_(node_ids))))
        db.execute(delete(KcState).where(KcState.kc_id.in_(node_ids)))
        for goal in db.scalars(select(KcGoal)):
            remaining = [item for item in (goal.target_kc_ids or []) if str(item) not in {str(node_id) for node_id in node_ids}]
            if remaining != list(goal.target_kc_ids or []):
                goal.target_kc_ids = remaining
        db.execute(delete(KcNode).where(KcNode.id.in_(node_ids)))
        db.commit()
    finally:
        db.close()


def _wipe_zz() -> None:
    db = SessionLocal()
    try:
        goals = list(db.scalars(select(KcGoal).where(KcGoal.code.like("zz%"))))
        goal_ids = [goal.id for goal in goals]
        node_ids = list(db.scalars(select(KcNode.id).where(KcNode.code.like("zz-%"))))
        session_ids = []
        if goal_ids:
            session_ids.extend(
                db.scalars(select(KcSession.id).where(KcSession.goal_id.in_(goal_ids)))
            )
        if node_ids:
            session_ids.extend(
                db.scalars(select(KcSession.id).where(KcSession.kc_id.in_(node_ids)))
            )
        session_ids = list(set(session_ids))
        if session_ids:
            db.execute(delete(KcModelPrompt).where(KcModelPrompt.session_id.in_(session_ids)))
            db.execute(delete(KcMessage).where(KcMessage.session_id.in_(session_ids)))
            db.execute(delete(KcSession).where(KcSession.id.in_(session_ids)))
        if node_ids:
            db.execute(delete(KcCreatorMessage).where(KcCreatorMessage.node_id.in_(node_ids)))
        if goal_ids:
            db.execute(delete(KcGoal).where(KcGoal.id.in_(goal_ids)))
        if node_ids:
            db.execute(
                delete(KcEdge).where(or_(KcEdge.from_kc.in_(node_ids), KcEdge.to_kc.in_(node_ids)))
            )
            db.execute(delete(KcState).where(KcState.kc_id.in_(node_ids)))
            db.execute(delete(KcNode).where(KcNode.id.in_(node_ids)))
        db.commit()
    finally:
        db.close()


def _counts() -> dict[str, int]:
    db = SessionLocal()
    try:
        return {
            "nodes": db.scalar(select(func.count()).select_from(KcNode)) or 0,
            "edges": db.scalar(select(func.count()).select_from(KcEdge)) or 0,
            "goals": db.scalar(select(func.count()).select_from(KcGoal)) or 0,
            "states": db.scalar(select(func.count()).select_from(KcState)) or 0,
            "sessions": db.scalar(select(func.count()).select_from(KcSession)) or 0,
            "messages": db.scalar(select(func.count()).select_from(KcMessage)) or 0,
            "chats": db.scalar(select(func.count()).select_from(Message)) or 0,
            "classes": db.scalar(select(func.count()).select_from(TutorSession)) or 0,
        }
    finally:
        db.close()


def _make(
    code: str,
    title: str = "ZZ course",
    description: str = "Tell one idea from another.",
    *,
    kind: str = "mastery",
    minutes: int | None = None,
    audience: str = "12-14",
) -> dict:
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={
            "code": code,
            "title": title,
            "description": description,
            "audience": audience,
            "kind": kind,
            "minutes": minutes,
        },
    )
    assert created.status_code == 200, created.text
    return created.json()


def _component(title: str, **overrides) -> dict:
    body = {
        "title": title,
        "kc_type": "factual",
        "core_truth": f"Truth for {title}.",
        "rubric": [f"Check for {title}."],
        "misconceptions": [],
        "prerequisite_codes": [],
        "encompasses_codes": [],
        "type_fields": {
            "fact": f"Truth for {title}.",
            "retrieval_question": f"What is true of {title}?",
        },
    }
    body.update(overrides)
    return body


def _spec(code: str, title: str, **overrides) -> dict:
    return {"code": code, **_component(title, **overrides)}


def _ready(course: dict, components: list[dict], patches: tuple[str, ...] = ()) -> dict:
    pushed = client.post(
        f"/kc/courses/{course['id']}/push",
        json={"components": [{"code": item["code"], "title": item["title"]} for item in components]},
    )
    assert pushed.status_code == 200, pushed.text
    by_code = {item["code"]: item for item in pushed.json()["components"]}
    for item in components:
        body = {key: value for key, value in item.items() if key != "code"}
        saved = client.put(f"/kc/nodes/{by_code[item['code']]['id']}", json=body)
        assert saved.status_code == 200, saved.text
    if patches:
        db = SessionLocal()
        try:
            goal = db.get(KcGoal, uuid.UUID(course["id"]))
            assert goal is not None
            drop = {
                str(node_id)
                for node_id in db.scalars(select(KcNode.id).where(KcNode.code.in_(patches)))
            }
            goal.target_kc_ids = [item for item in list(goal.target_kc_ids or []) if str(item) not in drop]
            db.commit()
        finally:
            db.close()
    ready = client.post(f"/kc/courses/{course['id']}/ready")
    assert ready.status_code == 200, ready.text
    return _course_by_code(course["code"])


def _storm() -> Student:
    db = SessionLocal()
    try:
        seed(db)
        student = db.scalar(select(Student).where(Student.slug == "storm"))
        assert student is not None
        return student
    finally:
        db.close()


def _clear_progress(student_id) -> None:
    db = SessionLocal()
    try:
        session_ids = list(db.scalars(select(KcSession.id).where(KcSession.student_id == student_id)))
        if session_ids:
            db.execute(delete(KcModelPrompt).where(KcModelPrompt.session_id.in_(session_ids)))
            db.execute(delete(KcMessage).where(KcMessage.session_id.in_(session_ids)))
            db.execute(delete(KcSession).where(KcSession.id.in_(session_ids)))
        db.execute(delete(KcState).where(KcState.student_id == student_id))
        db.commit()
    finally:
        db.close()


def _course_by_code(code: str) -> dict:
    listed = client.get("/kc/courses")
    assert listed.status_code == 200, listed.text
    for course in listed.json():
        if course["code"] == code:
            return course
    raise AssertionError(code)


def _node(course: dict, code: str) -> dict:
    for component in course["components"] + course["patches"]:
        if component["code"] == code:
            return component
    raise AssertionError(code)


def _state(student_id, code: str) -> KcState | None:
    db = SessionLocal()
    try:
        node = db.scalar(select(KcNode).where(KcNode.code == code))
        assert node is not None
        return db.scalar(select(KcState).where(KcState.student_id == student_id, KcState.kc_id == node.id))
    finally:
        db.close()


def _set_known(student_id, code: str) -> None:
    _set_status(student_id, code, "known")


def _set_status(student_id, code: str, status: str) -> None:
    db = SessionLocal()
    try:
        node = db.scalar(select(KcNode).where(KcNode.code == code))
        assert node is not None
        row = db.scalar(select(KcState).where(KcState.student_id == student_id, KcState.kc_id == node.id))
        if row is None:
            row = KcState(student_id=student_id, kc_id=node.id, status=status, stability=1 if status == "known" else 0)
            db.add(row)
        else:
            row.status = status
            row.stability = 1 if status == "known" else 0
        db.commit()
    finally:
        db.close()


def _finish_session(session_id: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(KcSession, uuid.UUID(session_id))
        assert row is not None
        row.status = "completed"
        db.commit()
    finally:
        db.close()


def test_revision_adds_kc_tables_only() -> None:
    text = REVISION.read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert "drop_table" not in upgrade
    assert "delete(" not in upgrade
    for name in ("kc_nodes", "kc_edges", "kc_goals", "kc_states", "kc_sessions", "kc_messages"):
        assert f'"{name}"' in upgrade
    for name in ("students", "courses", "quests", "sessions", "messages", "studio_courses"):
        assert f'"{name}"' not in upgrade
    prompt = PROMPT.read_text()
    assert "engine.assemble" not in prompt
    assert "import assemble" not in prompt
    assert build_kc_prompt.__module__ == "app.kc_prompt"


def test_migrations_do_not_insert_default_kc_courses() -> None:
    api = Path(__file__).resolve().parents[1]
    assert not (api / "app" / "kc_fixtures.py").exists()
    seed_text = (api / "app" / "seed.py").read_text()
    assert "kc_fixtures" not in seed_text
    assert "seed_kc_fixtures" not in seed_text
    banned = ("kc-geometry", "kc-macro", "kc-rome", "kc_fixtures", "seed_kc_fixtures")
    for path in (api / "alembic" / "versions").glob("*.py"):
        text = path.read_text()
        for token in banned:
            assert token not in text, f"{path.name} contains {token}"


def test_seed_keeps_a_saved_kc_course_and_inserts_no_defaults() -> None:
    db = SessionLocal()
    try:
        before = {goal.code: goal.id for goal in db.scalars(select(KcGoal))}
    finally:
        db.close()
    owned_id = None
    if "kc-geometry" not in before:
        created = client.post(
            "/kc/courses",
            json={
                "code": "kc-geometry",
                "title": "A saved geometry course",
                "description": "A person already saved this.",
                "audience": "12-14",
                "kind": "mastery",
            },
        )
        assert created.status_code == 200, created.text
        owned_id = created.json()["id"]
    saved = _make("zz-saved", title="Saved course", description="A person already saved this.")
    try:
        db = SessionLocal()
        try:
            present = {goal.code: goal.id for goal in db.scalars(select(KcGoal))}
            assert "zz-saved" in present
            assert "kc-geometry" in present
            seed(db)
            seed(db)
            after = {goal.code: goal.id for goal in db.scalars(select(KcGoal))}
            assert after == present
            kept = db.get(KcGoal, uuid.UUID(saved["id"]))
            assert kept is not None
            assert kept.title == "Saved course"
            geometry = db.scalar(select(KcGoal).where(KcGoal.code == "kc-geometry"))
            assert geometry is not None
            if owned_id is None:
                assert geometry.id == before["kc-geometry"]
            else:
                assert str(geometry.id) == owned_id
                assert geometry.title == "A saved geometry course"
            for code in ("kc-macro", "kc-rome"):
                assert (code in after) == (code in before)
        finally:
            db.close()
    finally:
        _wipe_zz()
        if owned_id is not None:
            db = SessionLocal()
            try:
                row = db.get(KcGoal, uuid.UUID(owned_id))
                if row is not None:
                    db.delete(row)
                    db.commit()
            finally:
                db.close()


def test_draft_is_not_written_until_push() -> None:
    drafted_codes = ["angle-sum", "missing-angle", "sas-versus-ssa", "congruence"]
    _drop_codes(drafted_codes)
    course = _make(
        "zz-draft",
        description="Name the angle sum, find the missing angle, and tell SAS from SSA.",
    )
    before = _counts()
    try:
        drafted = client.post(
            f"/kc/courses/{course['id']}/draft",
            json={"message": "Angle sum\nMissing angle\nSAS versus SSA\nCongruence"},
        )
        assert drafted.status_code == 200, drafted.text
        assert drafted.json()["draft"]["kind"] == "course"
        assert len(drafted.json()["draft"]["components"]) == 4
        assert "Nothing is saved" in drafted.json()["reply"]
        stored = client.get(f"/kc/courses/{course['id']}").json()
        assert stored["components"] == []
        after_draft = _counts()
        assert after_draft["nodes"] == before["nodes"]
        assert after_draft["edges"] == before["edges"]
        assert after_draft["messages"] == before["messages"]
        assert after_draft["chats"] == before["chats"]
        assert after_draft["classes"] == before["classes"]

        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={"components": drafted.json()["draft"]["components"]},
        )
        assert pushed.status_code == 200, pushed.text
        titles = [item["title"] for item in pushed.json()["components"]]
        assert titles == ["Angle sum", "Missing angle", "SAS versus SSA", "Congruence"]
        assert all(item["outline"] and item["topics"] for item in pushed.json()["components"])
        assert all(not item["description"].startswith("Outline:") for item in pushed.json()["components"])
        structure = client.get(f"/kc/courses/{course['id']}/structure").json()
        shown = [row["description"] for group in structure["groups"] for row in group["components"]]
        assert shown == [item["description"] for item in pushed.json()["components"]]
        assert _counts()["nodes"] == before["nodes"] + 4
        assert _counts()["chats"] == before["chats"]
    finally:
        _wipe_zz()
        _drop_codes(drafted_codes)


def test_four_components_stay_separate() -> None:
    course = _make("zz-four")
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-four-a", "title": "Alpha"},
                    {"code": "zz-four-b", "title": "Beta"},
                    {"code": "zz-four-c", "title": "Gamma"},
                    {"code": "zz-four-d", "title": "Delta"},
                ]
            },
        )
        assert pushed.status_code == 200, pushed.text
        components = pushed.json()["components"]
        assert [item["title"] for item in components] == ["Alpha", "Beta", "Gamma", "Delta"]
        assert len({item["id"] for item in components}) == 4
        assert len({item["code"] for item in components}) == 4

        first = components[0]
        others = {item["id"]: item["core_truth"] for item in components[1:]}
        drafted = client.post(f"/kc/nodes/{first['id']}/draft", json={"message": "Draft this fact."})
        assert drafted.status_code == 200, drafted.text
        assert drafted.json()["draft"]["code"] == "zz-four-a"
        assert drafted.json()["draft"]["kind"] == "component"
        reloaded = client.get(f"/kc/courses/{course['id']}").json()
        assert [item["core_truth"] for item in reloaded["components"]] == ["", "", "", ""]

        saved = client.post(f"/kc/nodes/{first['id']}/push", json=drafted.json()["draft"])
        assert saved.status_code == 200, saved.text
        assert saved.json()["core_truth"]
        again = client.get(f"/kc/courses/{course['id']}").json()
        assert len(again["components"]) == 4
        by_id = {item["id"]: item for item in again["components"]}
        assert by_id[first["id"]]["core_truth"] == saved.json()["core_truth"]
        for node_id, truth in others.items():
            assert by_id[node_id]["core_truth"] == truth
            assert by_id[node_id]["kc_type"] is None
    finally:
        _wipe_zz()


def test_editing_one_component_does_not_change_the_others() -> None:
    course = _make("zz-edit")
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-edit-a", "title": "Alpha"},
                    {"code": "zz-edit-b", "title": "Beta"},
                    {"code": "zz-edit-c", "title": "Gamma"},
                    {"code": "zz-edit-d", "title": "Delta"},
                ]
            },
        ).json()["components"]
        for component in pushed:
            saved = client.put(f"/kc/nodes/{component['id']}", json=_component(component["title"]))
            assert saved.status_code == 200, saved.text
        before = {
            item["id"]: client.get(f"/kc/nodes/{item['id']}").json()
            for item in pushed
        }
        changed = client.put(
            f"/kc/nodes/{pushed[0]['id']}",
            json=_component(
                "Alpha renamed",
                core_truth="ONLY THIS ONE",
                rubric=["Only this check"],
                prerequisite_codes=["zz-edit-b"],
                type_fields={
                    "fact": "ONLY THIS ONE",
                    "retrieval_question": "Which one changed?",
                },
            ),
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["core_truth"] == "ONLY THIS ONE"
        for component in pushed[1:]:
            assert client.get(f"/kc/nodes/{component['id']}").json() == before[component["id"]]
    finally:
        _wipe_zz()


def test_ready_requires_truth_a_check_and_real_edges() -> None:
    course = _make("zz-ready")
    storm = _storm()
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-ready-a", "title": "Earlier"},
                    {"code": "zz-ready-b", "title": "Later"},
                ]
            },
        ).json()["components"]
        earlier, later = pushed
        kid = client.get("/kc/tutor/courses")
        assert kid.status_code == 200
        assert all(item["code"] != "zz-ready" for item in kid.json())

        missing_truth = client.put(
            f"/kc/nodes/{later['id']}",
            json=_component("Later", core_truth="", prerequisite_codes=["zz-ready-a"]),
        )
        assert missing_truth.status_code == 200, missing_truth.text
        client.put(f"/kc/nodes/{earlier['id']}", json=_component("Earlier"))
        not_ready = client.post(f"/kc/courses/{course['id']}/ready")
        assert not_ready.status_code == 422
        assert "no truth" in not_ready.text

        missing_check = client.put(
            f"/kc/nodes/{later['id']}",
            json=_component("Later", rubric=[], prerequisite_codes=["zz-ready-a"]),
        )
        assert missing_check.status_code == 200, missing_check.text
        not_ready = client.post(f"/kc/courses/{course['id']}/ready")
        assert not_ready.status_code == 422
        assert "no rubric check" in not_ready.text

        missing_edge = client.put(
            f"/kc/nodes/{later['id']}",
            json=_component("Later", prerequisite_codes=["zz-ready-missing"]),
        )
        assert missing_edge.status_code == 200, missing_edge.text
        structure = client.get(f"/kc/courses/{course['id']}/structure").json()
        later_row = next(
            row
            for group in structure["groups"]
            for row in group["components"]
            if row["code"] == "zz-ready-b"
        )
        assert "a prerequisite that does not exist" in later_row["missing"]
        not_ready = client.post(f"/kc/courses/{course['id']}/ready")
        assert not_ready.status_code == 422
        assert "a prerequisite that does not exist" in not_ready.text
        assert all(item["code"] != "zz-ready" for item in client.get("/kc/tutor/courses").json())

        linked = client.put(
            f"/kc/nodes/{later['id']}",
            json=_component("Later", prerequisite_codes=["zz-ready-a"]),
        )
        assert linked.status_code == 200, linked.text
        ready = client.post(f"/kc/courses/{course['id']}/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["ready"] is True
        listed = client.get("/kc/tutor/courses").json()
        assert any(item["code"] == "zz-ready" for item in listed)
        progress = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        )
        assert progress.status_code == 200, progress.text
    finally:
        _wipe_zz()


def test_kid_prompt_uses_the_tutor_profile() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    original = client.get("/tutor-profile")
    assert original.status_code == 200, original.text
    saved_persona = storm.tutor_persona
    db = SessionLocal()
    try:
        row = db.get(Student, storm.id)
        assert row is not None
        row.tutor_persona = "HARBOR-GUIDE-SHOULD-NOT-APPEAR"
        db.commit()
        age = row.age
        interests = list(row.interests or [])
    finally:
        db.close()
    course = _ready(_make("zz-prompt", title="Prompt course"), [_spec("zz-prompt-fact", "Angle sum")])
    factual = _node(course, "zz-prompt-fact")
    try:
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": factual["id"]},
        )
        assert opened.status_code == 200, opened.text
        assert "persona" not in KcSession.__table__.columns
        for column in ("lexicon", "metaphors", "sidekick", "instructive", "stay_on_course"):
            assert column not in KcSession.__table__.columns
        switched = client.put(
            "/tutor-profile",
            json={
                "instructive": 5,
                "persona": "debate-moderator",
                "lexicon": "analytical-high-school",
                "voice_override": True,
                "metaphors": "policy-cause",
                "sidekick": "pundit",
                "struggle_window": "long",
                "anti_spoiler": True,
                "one_question": True,
                "use_interests": True,
                "stay_on_course": False,
                "growth_praise": True,
            },
        )
        assert switched.status_code == 200, switched.text
        prompt = client.get(f"/kc/tutor/sessions/{opened.json()['id']}/prompt")
        assert prompt.status_code == 200, prompt.text
        text = prompt.json()["system_prompt"]
        assert prompt.json()["recipe"] == "retrieval"
        assert prompt.json()["temperature"] == 0.4
        assert set(prompt.json()["response_schema"]["required"]) >= {
            "reply",
            "decision",
            "rubric_met",
            "misconception",
        }
        assert "debate moderator" in text
        assert "analytical high-school" in text
        assert "cause-and-effect" in text
        assert "pundit" in text
        assert "Teach a little more first, then ask one question." in text
        assert "three tries" in text
        assert "You may follow a tangent." in text
        assert f"{age}-year-old" in text
        for interest in interests:
            assert interest in text
        assert "HARBOR-GUIDE-SHOULD-NOT-APPEAR" not in text
        assert "curious-co-explorer" not in text
        assert "debate-moderator" not in text
        assert "This turn" in text
        assert "What to return" in text
        assert "Layer 1, Component" not in text
        assert "Layer 7, Feedback loop" not in text
        assert "retrieval" in text
        assert "You do not set the type, the edges, the score, or the step index." in text
        db = SessionLocal()
        try:
            stored = db.get(KcSession, opened.json()["id"])
            assert stored is not None
            assert stored.recipe == "retrieval"
            assert not hasattr(stored, "persona") or "persona" not in stored.__table__.columns
        finally:
            db.close()
    finally:
        client.put("/tutor-profile", json=original.json())
        db = SessionLocal()
        try:
            row = db.get(Student, storm.id)
            if row is not None:
                row.tutor_persona = saved_persona
                db.commit()
        finally:
            db.close()
        _clear_progress(storm.id)
        _wipe_zz()


def test_pass_bumps_an_encompassed_component() -> None:
    course = _make("zz-bump", description="The river in this course is blue.")
    storm = _storm()
    _clear_progress(storm.id)
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-bump-earlier", "title": "Earlier fact"},
                    {"code": "zz-bump-later", "title": "Later fact"},
                ]
            },
        ).json()["components"]
        earlier, later = pushed
        assert client.put(
            f"/kc/nodes/{earlier['id']}",
            json=_component("Earlier fact", core_truth="The capital of this course is ZZ."),
        ).status_code == 200
        assert client.put(
            f"/kc/nodes/{later['id']}",
            json=_component(
                "Later fact",
                core_truth="The river in this course is blue.",
                encompasses_codes=["zz-bump-earlier"],
                type_fields={
                    "fact": "The river in this course is blue.",
                    "retrieval_question": "What color is the river in this course?",
                },
            ),
        ).status_code == 200
        ready = client.post(f"/kc/courses/{course['id']}/ready")
        assert ready.status_code == 200, ready.text
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": later["id"]},
        )
        assert opened.status_code == 200, opened.text
        answered = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "The river in this course is blue."},
        )
        assert answered.status_code == 200, answered.text
        done = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={
                "reply": "Yes. The river in this course is blue. This unit is complete.",
                "decision": "complete",
                "rubric_met": ["fact"],
                "affect": "engaged",
                "confidence": "ok",
            },
        )
        assert done.status_code == 200, done.text
        assert done.json()["passed"] is True
        assert done.json()["score"] == 100
        assert done.json()["unit_complete"] is True
        later_state = _state(storm.id, "zz-bump-later")
        earlier_state = _state(storm.id, "zz-bump-earlier")
        assert later_state is not None and later_state.status == "known"
        assert earlier_state is not None
        assert earlier_state.status != "known"
        assert earlier_state.stability >= 0.25
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_misconception_opens_prerequisite_and_pass_does_not_mark_them_known() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    rule = "SAS proves two triangles congruent. SSA does not."
    course = _ready(
        _make("zz-mis", title="Misconception course"),
        [
            _spec(
                "zz-mis-base",
                "What congruence means",
                kc_type="conceptual",
                core_truth="Congruence means the same size and the same shape.",
                rubric=["Says same size and same shape"],
                type_fields={
                    "case_a": "Same size and same shape.",
                    "case_b": "Same shape and longer sides.",
                    "prediction": "Which pair can be placed exactly on top of each other?",
                    "rule": "Congruent triangles have the same size and the same shape.",
                },
            ),
            _spec(
                "zz-mis-patch",
                "The included angle",
                kc_type="conceptual",
                core_truth="The included angle lies between the two sides.",
                rubric=["Points to the angle between the two sides"],
                type_fields={
                    "case_a": "The angle between the two sides.",
                    "case_b": "The angle at the opposite vertex.",
                    "prediction": "Which angle is included?",
                    "rule": "The included angle is the angle formed between the two given sides.",
                },
            ),
            _spec(
                "zz-mis-claim",
                "SAS versus SSA",
                kc_type="conceptual",
                core_truth="SAS fixes a triangle and SSA does not.",
                rubric=["Names SAS as the proving case"],
                prerequisite_codes=["zz-mis-base", "zz-mis-patch"],
                misconceptions=[{"wrong_move": "SSA proves congruence", "broken_kc": "zz-mis-patch"}],
                type_fields={
                    "case_a": "Two sides with the angle between them fixed.",
                    "case_b": "Two sides with an angle that is not between them.",
                    "prediction": "Which description locks one triangle?",
                    "rule": rule,
                },
            ),
        ],
        patches=("zz-mis-patch",),
    )
    sas = _node(course, "zz-mis-claim")
    try:
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": sas["id"]},
        )
        assert opened.status_code == 200, opened.text
        client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "SSA proves congruence"},
        )
        first = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={"reply": "That move is stored. Try the same move again.", "decision": "redirect"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["passed"] is False
        assert first.json()["redirect"] is None
        assert first.json()["status"] == "in_progress"
        client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "SSA proves congruence"},
        )
        failed = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={"reply": "This unit is paused. The next card is the included angle.", "decision": "stay"},
        )
        assert failed.status_code == 200, failed.text
        assert failed.json()["passed"] is False
        assert failed.json()["redirect"]["code"] == "zz-mis-patch"
        board = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert any(card["code"] == "zz-mis-patch" and card["role"] == "patch" for card in board["cards"])
        sas_state = _state(storm.id, "zz-mis-claim")
        assert sas_state is not None and sas_state.status != "known"
        included = _state(storm.id, "zz-mis-patch")
        assert included is None or included.status != "known"
        congruence = _state(storm.id, "zz-mis-base")
        assert congruence is None or congruence.status != "known"

        _clear_progress(storm.id)
        fresh = _course_by_code("zz-mis")
        sas = _node(fresh, "zz-mis-claim")
        rule = sas["type_fields"]["rule"]
        again = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": fresh["id"], "kc_id": sas["id"]},
        )
        assert again.status_code == 200, again.text
        session_id = again.json()["id"]
        steps = (
            ("The case with the included angle locks one triangle.", "advance", []),
            ("The other case leaves two possible triangles.", "advance", []),
            ("One case closes and the other leaves two shapes.", "advance", []),
            (rule, "complete", ["rule"]),
        )
        step = None
        for answer, decision, rubric in steps:
            posted = client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": answer})
            assert posted.status_code == 200, posted.text
            step = client.post(
                f"/kc/tutor/sessions/{session_id}/decision",
                json={"reply": "That holds.", "decision": decision, "rubric_met": rubric},
            )
            assert step.status_code == 200, step.text
        assert step is not None
        assert step.json()["passed"] is True
        assert step.json()["score"] == 100
        assert _state(storm.id, "zz-mis-claim").status == "known"
        included = _state(storm.id, "zz-mis-patch")
        congruence = _state(storm.id, "zz-mis-base")
        assert included is None or included.status != "known"
        assert congruence is None or congruence.status != "known"
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_time_box_synthesis_and_factual_recipe() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    concept = {
        "case_a": "One case.",
        "case_b": "The other case.",
        "prediction": "Which one holds?",
        "rule": "The rule for this course.",
    }
    course = _ready(
        _make("zz-box", title="Timed course", kind="time_boxed", minutes=30),
        [
            _spec(
                "zz-box-fact",
                "Triangle angle sum",
                core_truth="The interior angles of a triangle sum to 180 degrees.",
                type_fields={
                    "fact": "The interior angles of a triangle add up to 180 degrees.",
                    "retrieval_question": "What do the three interior angles of a triangle add up to?",
                },
            ),
            _spec(
                "zz-box-steps",
                "Find the missing angle",
                kc_type="procedural",
                core_truth="The missing angle is 180 minus the other two angles.",
                prerequisite_codes=["zz-box-fact"],
                encompasses_codes=["zz-box-fact"],
                type_fields={
                    "steps": ["Add the two known angles.", "Subtract that sum from 180."],
                    "blanked_step": 1,
                    "solo_problem": "A triangle has angles of 40 and 60. What is the third?",
                    "solo_check": "80",
                },
            ),
            _spec(
                "zz-box-idea",
                "What congruence means",
                kc_type="conceptual",
                core_truth="Congruence means the same size and the same shape.",
                type_fields=concept,
            ),
            _spec(
                "zz-box-patch",
                "The included angle",
                kc_type="conceptual",
                core_truth="The included angle lies between the two sides.",
                type_fields=concept,
            ),
            _spec(
                "zz-box-claim",
                "SAS versus SSA",
                kc_type="conceptual",
                core_truth="SAS fixes a triangle and SSA does not.",
                prerequisite_codes=["zz-box-idea", "zz-box-patch"],
                misconceptions=[{"wrong_move": "SSA proves congruence", "broken_kc": "zz-box-patch"}],
                type_fields=concept,
            ),
            _spec(
                "zz-box-cause",
                "Why SSA fails",
                kc_type="causal",
                core_truth="SSA fails because the given angle is not included.",
                prerequisite_codes=["zz-box-claim"],
                type_fields={
                    "decision_point": "Two sides and an angle that is not between them.",
                    "flawed_claim": "The angle can sit anywhere and the triangle is still fixed.",
                    "causal_chain": "The angle is not between the two sides, so the third side can meet them in two places.",
                },
            ),
            _spec(
                "zz-box-plan",
                "Fix the congruence plan",
                kc_type="synthesis",
                core_truth="Same size and same shape, together with SAS, show congruence.",
                prerequisite_codes=["zz-box-idea", "zz-box-claim"],
                type_fields={
                    "mixes": ["zz-box-idea", "zz-box-claim"],
                    "faulty_plan": "The triangles look the same and SSA locks them.",
                },
            ),
        ],
        patches=("zz-box-patch",),
    )
    try:
        listed = {item["code"] for item in client.get("/kc/tutor/courses").json()}
        assert "zz-box" in listed
        assert course["kind"] == "time_boxed"
        assert course["minutes"] == 30
        assert len(course["components"]) == 6
        assert course["ready"] is True
        claim = _node(course, "zz-box-claim")
        assert claim["misconceptions"][0]["broken_kc"] == "zz-box-patch"
        assert _node(course, "zz-box-patch")["target"] is False
        diagram = client.get(f"/kc/courses/{course['id']}/network").json()
        assert any(node["code"] == "zz-box-patch" and node["patch"] for node in diagram["nodes"])
        assert any(
            edge["kind"] == "prerequisite_of"
            and edge["from_code"] == "zz-box-patch"
            and edge["to_code"] == "zz-box-claim"
            for edge in diagram["edges"]
        )
        assert {item["kc_type"] for item in course["components"]} >= {
            "factual",
            "procedural",
            "conceptual",
            "causal",
            "synthesis",
        }

        factual = _node(course, "zz-box-fact")
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": factual["id"]},
        )
        assert opened.json()["recipe"] == "retrieval"
        assert opened.json()["step_label"] == "Retrieve"
        client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "The interior angles of a triangle add up to 180 degrees."},
        )
        answered = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={
                "reply": "Yes. The interior angles add up to 180 degrees. This unit is complete.",
                "decision": "complete",
                "rubric_met": ["fact"],
            },
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["passed"] is True
        assert answered.json()["step_label"] == "Retrieve"
        assert "180" in answered.json()["reply"]

        _clear_progress(storm.id)
        _set_known(storm.id, "zz-box-fact")
        _set_known(storm.id, "zz-box-steps")
        skipped = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert skipped["minutes"] == 30
        assert skipped["count_label"] == "2 of 6"
        assert all(card["code"] not in {"zz-box-fact", "zz-box-steps"} for card in skipped["cards"])
        assert all(card["code"] != "zz-box-plan" for card in skipped["cards"])

        _set_known(storm.id, "zz-box-idea")
        _set_known(storm.id, "zz-box-claim")
        stretch = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert any(card["code"] == "zz-box-plan" for card in stretch["cards"])
        assert stretch["known"] == 4
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_creator_thread_revises_one_component_and_complete_clears_on_write() -> None:
    course = _make("zz-creator", description="The river in this course is blue.")
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={"components": [{"code": "zz-creator-a", "title": "River fact"}, {"code": "zz-creator-b", "title": "Other"}]},
        ).json()["components"]
        river = pushed[0]
        before_messages = _counts()["messages"]
        opened = client.get(f"/kc/nodes/{river['id']}/thread")
        assert opened.status_code == 200, opened.text
        assert opened.json()["messages"] == []
        assert "River fact" in opened.json()["mirror"]
        assert _counts()["messages"] == before_messages

        first = client.post(f"/kc/nodes/{river['id']}/thread", json={"message": "Draft this fact."})
        assert first.status_code == 200, first.text
        opening = first.json()["messages"][-1]["content"]
        assert opening.index("The topic, before the fields") < opening.index("Core truth:")
        draft = first.json()["draft"]
        assert draft["kind"] == "component"
        assert draft["code"] == "zz-creator-a"
        assert draft["kc_type"] == "factual"
        assert _counts()["messages"] == before_messages
        stored = client.get(f"/kc/nodes/{river['id']}").json()
        assert stored["kc_type"] is None

        revised = client.post(
            f"/kc/nodes/{river['id']}/thread",
            json={"message": "Core truth: The river in this course is blue."},
        )
        assert revised.status_code == 200, revised.text
        assert revised.json()["draft"]["core_truth"] == "The river in this course is blue."
        assert revised.json()["draft"]["kc_type"] == "factual"
        assert "Nothing is saved until you push it." in revised.json()["messages"][-1]["content"]

        written = client.post(f"/kc/nodes/{river['id']}/push", json=revised.json()["draft"])
        assert written.status_code == 200, written.text
        assert written.json()["core_truth"] == "The river in this course is blue."
        assert written.json()["marked_complete"] is False
        other = client.get(f"/kc/nodes/{pushed[1]['id']}").json()
        assert other["kc_type"] is None
        thread = client.get(f"/kc/nodes/{river['id']}/thread").json()
        assert thread["draft"] is None
        assert thread["messages"][-1]["content"] == "The draft was saved."
        assert "The river in this course is blue." in thread["mirror"]

        client.put(f"/kc/nodes/{pushed[1]['id']}", json=_component("Other"))
        ready = client.post(f"/kc/courses/{course['id']}/ready")
        assert ready.status_code == 200, ready.text
        marked = client.post(f"/kc/nodes/{river['id']}/complete")
        assert marked.status_code == 200, marked.text
        assert marked.json()["marked_complete"] is True
        structure = client.get(f"/kc/courses/{course['id']}/structure").json()
        row = next(item for group in structure["groups"] for item in group["components"] if item["code"] == "zz-creator-a")
        assert row["missing"] == []
        assert row["marked_complete"] is True
        saved = client.put(f"/kc/nodes/{river['id']}", json=_component("River fact"))
        assert saved.status_code == 200, saved.text
        assert saved.json()["marked_complete"] is False
        assert client.get(f"/kc/courses/{course['id']}").json()["ready"] is False

        bare = client.post(
            "/kc/courses",
            json={"code": "zz-creator-gap", "title": "Gap", "description": "A gap.", "audience": "12-14", "kind": "mastery"},
        ).json()
        added = client.post(f"/kc/courses/{bare['id']}/components", json={"title": "Empty"}).json()
        empty = added["components"][0]
        refused = client.post(f"/kc/nodes/{empty['id']}/complete")
        assert refused.status_code == 422
        assert "no type" in refused.text
    finally:
        _wipe_zz()


def test_tutor_speech_is_separate_from_the_score_and_two_steps_are_choices() -> None:
    course = _make("zz-speak", description="A claim can be flawed.")
    storm = _storm()
    _clear_progress(storm.id)
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-speak-concept", "title": "Contrast"},
                    {"code": "zz-speak-cause", "title": "Decision"},
                ]
            },
        ).json()["components"]
        concept, cause = pushed
        assert client.put(
            f"/kc/nodes/{concept['id']}",
            json=_component(
                "Contrast",
                kc_type="conceptual",
                core_truth="The rule is the contrast.",
                type_fields={
                    "case_a": "The closed case",
                    "case_b": "The open case",
                    "prediction": "Which case fits?",
                    "rule": "The rule is the contrast.",
                },
            ),
        ).status_code == 200
        assert client.put(
            f"/kc/nodes/{cause['id']}",
            json=_component(
                "Decision",
                kc_type="causal",
                core_truth="Taxes move prices.",
                prerequisite_codes=["zz-speak-concept"],
                type_fields={
                    "decision_point": "A council sets a tax.",
                    "flawed_claim": "The tax lowers prices.",
                    "causal_chain": "Taxes move prices.",
                },
            ),
        ).status_code == 200
        assert client.post(f"/kc/courses/{course['id']}/ready").status_code == 200

        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": concept["id"]},
        )
        assert opened.status_code == 200, opened.text
        assert opened.json()["messages"] == []
        assert opened.json()["needs_speech"] is True
        assert opened.json()["choice"] is None
        spoken = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/speech",
            json={"content": "Which case fits?"},
        )
        assert spoken.status_code == 200, spoken.text
        assert spoken.json()["needs_speech"] is False
        assert spoken.json()["messages"][-1]["content"] == "Which case fits?"
        assert [item["text"] for item in spoken.json()["choice"]["choices"]] == ["This holds", "This does not hold"]
        assert "The closed case" in spoken.json()["choice"]["prompt"]
        assert "The open case" not in spoken.json()["choice"]["prompt"]
        again = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/speech",
            json={"content": "Asked twice."},
        )
        assert again.json()["messages"][-1]["content"] == "Which case fits?"
        client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "This holds"},
        )
        stepped = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={"reply": "Now the second case.", "decision": "advance"},
        )
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["passed"] is False
        assert stepped.json()["step"] == 1
        assert stepped.json()["needs_speech"] is False
        assert [item["text"] for item in stepped.json()["choice"]["choices"]] == ["This holds", "This does not hold"]
        assert "The open case" in stepped.json()["choice"]["prompt"]
        assert "The closed case" not in stepped.json()["choice"]["prompt"]

        causal = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": cause["id"]},
        ).json()
        client.post(f"/kc/tutor/sessions/{causal['id']}/speech", json={"content": "Taxes move prices."})
        client.post(f"/kc/tutor/sessions/{causal['id']}/turn", json={"answer": "The tax changes the price."})
        client.post(
            f"/kc/tutor/sessions/{causal['id']}/decision",
            json={"reply": "What is at stake?", "decision": "advance"},
        )
        client.post(f"/kc/tutor/sessions/{causal['id']}/turn", json={"answer": "The tax is the stake."})
        client.post(
            f"/kc/tutor/sessions/{causal['id']}/decision",
            json={"reply": "Mark this claim.", "decision": "advance"},
        )
        marked = client.get(f"/kc/tutor/sessions/{causal['id']}").json()
        assert [item["text"] for item in marked["choice"]["choices"]] == ["This claim is flawed", "This claim holds"]
        client.post(f"/kc/tutor/sessions/{causal['id']}/turn", json={"answer": "This claim holds"})
        held = client.post(
            f"/kc/tutor/sessions/{causal['id']}/decision",
            json={"reply": "Look again.", "decision": "advance", "rubric_met": []},
        )
        assert held.json()["passed"] is False
        assert held.json()["step"] == 2
        fresh = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": cause["id"]},
        )
        assert fresh.status_code == 200, fresh.text
        client.post(f"/kc/tutor/sessions/{causal['id']}/turn", json={"answer": "This claim is flawed"})
        done = client.post(
            f"/kc/tutor/sessions/{causal['id']}/decision",
            json={"reply": "Defend the chain.", "decision": "advance", "rubric_met": ["mark"]},
        )
        assert done.status_code == 200, done.text
        assert done.json()["step"] == 3
        assert done.json()["needs_speech"] is False
        assert done.json()["passed"] is False
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def _model_fields(**overrides: object) -> dict:
    body: dict = {
        "discussion": (
            "River fact is the claim that this river is blue, which is why a kid has to recall the color "
            "before any later step in the course."
        ),
        "description": "The river is blue.",
        "outline": "How the river looks.",
        "topics": [{"topic": "color", "goal": "Recall the color"}],
        "title": "River fact",
        "kc_type": "factual",
        "core_truth": "The river in this course is blue.",
        "rubric": ["States that the river is blue"],
        "misconceptions": [{"wrong_move": "The river is red", "broken_kc": "zz-fields-b"}],
        "prerequisite_codes": ["zz-fields-b"],
        "encompasses_codes": [],
        "fact": "The river is blue.",
        "retrieval_question": "What color is the river?",
        "steps": [],
        "blanked_step": 0,
        "solo_problem": "",
        "solo_check": "",
        "case_a": "",
        "case_b": "",
        "prediction": "",
        "rule": "",
        "decision_point": "",
        "flawed_claim": "",
        "causal_chain": "",
        "mix_a": "",
        "mix_b": "",
        "faulty_plan": "",
    }
    body.update(overrides)
    return body


def test_model_draft_recommends_every_field_and_push_keeps_the_description() -> None:
    course = _make("zz-fields", description="The river in this course is blue.")
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {
                        "code": "zz-fields-a",
                        "title": "River fact",
                        "description": "Outline: The river is blue.\nTopics: color\nGoals: Recall the color",
                    },
                    {"code": "zz-fields-b", "title": "Other"},
                ]
            },
        ).json()["components"]
        river = pushed[0]
        saved = client.put(
            f"/kc/nodes/{river['id']}",
            json=_component("River fact", description="Outline: Edited by hand.\nTopics: color\nGoals: Recall it"),
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["description"] == "Edited by hand."
        assert saved.json()["outline"] == "Edited by hand."
        assert saved.json()["topics"] == [{"topic": "color", "goal": "Recall it"}]

        thin = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(outline="", topics=[]),
            },
        )
        assert thin.status_code == 422
        assert "outline" in thin.json()["detail"].lower()

        full = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={"message": "Draft this component.", "discussion": _model_fields()["discussion"], "draft": _model_fields()},
        )
        assert full.status_code == 200, full.text
        draft = full.json()["draft"]
        assert draft["description"] == "The river is blue."
        assert draft["outline"] == "How the river looks."
        assert draft["topics"] == [{"topic": "color", "goal": "Recall the color"}]
        assert draft["kc_type"] == "factual"
        assert draft["type_fields"]["fact"] == "The river is blue."
        assert draft["type_fields"]["retrieval_question"] == "What color is the river?"
        assert draft["misconceptions"][0]["broken_kc"] == "zz-fields-b"
        assert draft["prerequisite_codes"] == ["zz-fields-b"]
        assert "Recommend" not in full.json()["messages"][-1]["content"]
        assert "Description:" in full.json()["messages"][-1]["content"]

        written = client.post(f"/kc/nodes/{river['id']}/push", json=draft)
        assert written.status_code == 200, written.text
        assert written.json()["description"] == "The river is blue."
        assert written.json()["outline"] == "How the river looks."
        assert written.json()["topics"] == [{"topic": "color", "goal": "Recall the color"}]
        assert written.json()["core_truth"] == "The river in this course is blue."
        assert written.json()["type_fields"]["fact"] == "The river is blue."
        assert written.json()["prerequisite_codes"] == ["zz-fields-b"]
        other = client.get(f"/kc/nodes/{pushed[1]['id']}").json()
        assert other["title"] == "Other"
        assert other["kc_type"] is None
    finally:
        _wipe_zz()


def test_push_keeps_every_topic_goal_pair_from_the_model_reply() -> None:
    pairs = [
        {"topic": "color", "goal": "Recall the color"},
        {"topic": "banks", "goal": "Name a bank"},
        {"topic": "current", "goal": "Say which way it flows"},
        {"topic": "source", "goal": "Name where it starts"},
    ]
    course = _make("zz-pairs", description="The river in this course is blue.")
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-pairs-a", "title": "River fact"},
                    {"code": "zz-pairs-b", "title": "Other"},
                ]
            },
        ).json()["components"]
        river = pushed[0]
        full = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this component.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(
                    topics=pairs,
                    prerequisite_codes=["zz-pairs-b"],
                    misconceptions=[{"wrong_move": "The river is red", "broken_kc": "zz-pairs-b"}],
                ),
            },
        )
        assert full.status_code == 200, full.text
        draft = full.json()["draft"]
        assert draft["topics"] == pairs

        written = client.post(f"/kc/nodes/{river['id']}/push", json=draft)
        assert written.status_code == 200, written.text
        assert written.json()["topics"] == pairs
        stored = client.get(f"/kc/nodes/{river['id']}").json()
        assert stored["topics"] == pairs
        assert len(stored["topics"]) == 4
    finally:
        _wipe_zz()


def test_wrong_password_keeps_a_kc_course_and_the_right_password_deletes_it() -> None:
    _wipe_zz()
    before = _counts()
    first = client.post(
        "/kc/courses",
        json={
            "code": "zz-del",
            "title": "Delete me",
            "description": "A course to remove.",
            "audience": "12-14",
            "kind": "mastery",
        },
    )
    assert first.status_code == 200, first.text
    course = first.json()
    kept = client.post(
        "/kc/courses",
        json={
            "code": "zz-keep",
            "title": "Keep me",
            "description": "A course to keep.",
            "audience": "12-14",
            "kind": "mastery",
        },
    ).json()
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={"components": [{"code": "zz-del-a", "title": "Gone"}]},
        ).json()["components"]
        node_id = pushed[0]["id"]
        opened = client.post(f"/kc/nodes/{node_id}/thread", json={"message": "Draft this fact."})
        assert opened.status_code == 200, opened.text
        assert opened.json()["messages"]

        wrong = client.post(f"/kc/courses/{course['id']}/delete", json={"password": "not-the-password"})
        assert wrong.status_code == 422
        assert wrong.json()["detail"] == "The password is wrong."
        assert "BulmerGardens" not in wrong.text
        assert client.get(f"/kc/courses/{course['id']}").status_code == 200
        assert client.get(f"/kc/nodes/{node_id}").status_code == 200
        assert client.get(f"/kc/courses/{kept['id']}").status_code == 200

        deleted = client.post(f"/kc/courses/{course['id']}/delete", json={"password": "BulmerGardens"})
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["deleted"] is True
        assert client.get(f"/kc/courses/{course['id']}").status_code == 404
        assert client.get(f"/kc/nodes/{node_id}").status_code == 404
        assert client.get(f"/kc/courses/{kept['id']}").status_code == 200
        codes = [row["code"] for row in client.get("/kc/courses").json()]
        assert "zz-del" not in codes
        assert "zz-keep" in codes
        db = SessionLocal()
        try:
            goal_id = uuid.UUID(course["id"])
            component_id = uuid.UUID(node_id)
            assert db.get(KcGoal, goal_id) is None
            assert db.get(KcNode, component_id) is None
            assert (
                db.scalar(
                    select(func.count()).select_from(KcCreatorMessage).where(KcCreatorMessage.node_id == component_id)
                )
                == 0
            )
        finally:
            db.close()
        after = _counts()
        assert after["chats"] == before["chats"]
        assert after["classes"] == before["classes"]
    finally:
        _wipe_zz()


PROMPT_REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "019_kc_model_prompts.py"


def test_kc_model_prompt_revision_adds_one_table() -> None:
    text = PROMPT_REVISION.read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert "drop_table" not in upgrade
    assert "delete(" not in upgrade
    assert '"kc_model_prompts"' in upgrade
    assert '"kc_sessions.id"' in upgrade
    assert '"kc_messages.id"' in upgrade
    for name in ("model_prompts", "sessions", "students", "courses"):
        assert f'"{name}"' not in upgrade


def test_kc_chat_admin_lists_the_session_and_the_stored_prompt() -> None:
    course = _make("zz-chat-admin", title="ZZ chat course")
    storm = _storm()
    _clear_progress(storm.id)
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={"components": [{"code": "zz-chat-fact", "title": "River fact"}]},
        ).json()["components"]
        node = pushed[0]
        assert client.put(f"/kc/nodes/{node['id']}", json=_component("River fact")).status_code == 200
        assert client.post(f"/kc/courses/{course['id']}/ready").status_code == 200
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": node["id"]},
        )
        assert opened.status_code == 200, opened.text
        session_id = opened.json()["id"]
        spoken = client.post(
            f"/kc/tutor/sessions/{session_id}/speech",
            json={"content": "What is true of River fact?"},
        )
        assert spoken.status_code == 200, spoken.text
        message_id = spoken.json()["messages"][-1]["id"]
        saved = client.post(
            f"/kc/sessions/{session_id}/model-prompts",
            json={
                "system_prompt": "You are the knowledge-component tutor.",
                "messages": [
                    {"role": "user", "content": "Say this step to the student now."},
                    {"role": "request", "content": {"temperature": 0.2}},
                ],
                "model": "gpt-4o-mini",
                "message_id": message_id,
            },
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["model"] == "gpt-4o-mini"
        assert saved.json()["message_id"] == message_id

        listed = client.get("/kc/sessions")
        assert listed.status_code == 200, listed.text
        row = next(item for item in listed.json() if item["id"] == session_id)
        assert row["student_id"] == str(storm.id)
        assert row["kc_title"] == "River fact"
        assert row["course_title"] == "ZZ chat course"
        assert row["message_count"] == 1
        assert row["score"] is None
        assert row["step_label"]
        filtered = client.get(f"/kc/sessions?student_id={storm.id}")
        assert [item["id"] for item in filtered.json() if item["id"] == session_id] == [session_id]
        assert client.get(f"/kc/sessions?student_id={uuid.uuid4()}").json() == []
        kid = client.get("/sessions").json()
        assert all(item["id"] != session_id for item in kid)

        detail = client.get(f"/kc/sessions/{session_id}")
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["student"]["id"] == str(storm.id)
        assert body["component"]["code"] == "zz-chat-fact"
        assert body["messages"][0]["content"] == "What is true of River fact?"
        assert body["prompts"][0]["system_prompt"] == "You are the knowledge-component tutor."
        assert body["prompts"][0]["messages"][0]["content"] == "Say this step to the student now."
        assert body["prompts"][0]["messages"][1]["role"] == "request"

        missing = client.post(
            f"/kc/sessions/{session_id}/model-prompts",
            json={
                "system_prompt": "Missing message.",
                "messages": [],
                "message_id": str(uuid.uuid4()),
            },
        )
        assert missing.status_code == 400
        assert client.get(f"/kc/sessions/{uuid.uuid4()}").status_code == 404
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def _variable_map(response) -> dict[str, str]:
    assert response.status_code == 200, response.text
    rows = response.json()["variables"]
    names = [row["name"] for row in rows]
    assert len(names) == len(set(names))
    return {row["name"]: row["value"] for row in rows}


def test_tutor_variables_list_inputs_and_keep_empty_layers() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _make("zz-vars", title="ZZ variables", description="One idea, said plainly.")
    try:
        blank = _variable_map(client.get("/kc/tutor/variables"))
        layers = [row["layer"] for row in client.get("/kc/tutor/variables").json()["variables"]]
        assert layers[:1] == ["Layer 1, Component"]
        assert "Layer 7, Feedback loop" in layers
        for name in (
            "Course title",
            "Course description",
            "Audience",
            "Kind",
            "Minutes",
            "Component title",
            "Component code",
            "Type",
            "Component description",
            "Core truth",
            "Type fields",
            "Rubric lines",
            "Misconceptions",
            "Prerequisite codes",
            "Encompass codes",
            "Move index",
            "Move name",
            "Evidence",
            "Choice widget",
            "Course position",
            "Move content",
            "Display name",
            "Age",
            "Reading level",
            "Modality",
            "Interests",
            "Attempts on this move",
            "Last answer",
            "Last misconception",
            "Minutes used",
            "Support band",
            "Score",
            "Status",
            "Affect",
            "Last four messages",
        ):
            assert blank[name] == ""
        assert blank["Persona"]
        assert blank["Lexicon"]
        assert blank["Instructive"]
        assert blank["Stay on course"] in {"yes", "no"}
        assert blank["Use interests"] in {"yes", "no"}
        assert blank["Misconception policy"] == "retry_once"
        assert blank["Self-explanation"] in {"yes", "no"}
        assert blank["Enrichment"] in {"direct", "on_request", "offer"}
        assert blank["Growth-mindset praise"] in {"yes", "no"}
        assert blank["Anti-spoiler"] in {"yes", "no"}
        assert blank["One question"] in {"yes", "no"}
        assert blank["Unit close"] == "no"
        assert blank["Course outro"] == "no"
        for unused in ("Voice override", "Tutor persona"):
            assert unused not in blank

        picked = _variable_map(
            client.get("/kc/tutor/variables", params={"student_id": str(storm.id), "course_id": course["id"]})
        )
        assert picked["Course title"] == "ZZ variables"
        assert picked["Course description"] == "One idea, said plainly."
        assert picked["Audience"] == "12-14"
        assert picked["Kind"] == "mastery"
        assert picked["Minutes"] == ""
        assert picked["Display name"] == "Storm"
        assert picked["Age"] == "10"
        assert picked["Component title"] == ""
        assert picked["Type fields"] == ""
        assert picked["Move index"] == ""
        assert picked["Redirect pending"] == "no"

        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-vars-other", "title": "Other fact"},
                    {"code": "zz-vars-fact", "title": "River fact"},
                ]
            },
        ).json()["components"]
        other, node = pushed
        assert client.put(f"/kc/nodes/{other['id']}", json=_component("Other fact")).status_code == 200
        assert client.put(
            f"/kc/nodes/{node['id']}",
            json=_component(
                "River fact",
                description="A short brief.",
                misconceptions=[{"wrong_move": "The river is red.", "broken_kc": "zz-vars-other"}],
                prerequisite_codes=["zz-vars-other"],
            ),
        ).status_code == 200
        assert client.post(f"/kc/courses/{course['id']}/ready").status_code == 200
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": node["id"]},
        )
        assert opened.status_code == 200, opened.text
        session_id = opened.json()["id"]
        live = _variable_map(client.get("/kc/tutor/variables", params={"session_id": session_id}))
        assert live["Component title"] == "River fact"
        assert live["Component code"] == "zz-vars-fact"
        assert live["Type"] == "factual (Factual)"
        assert live["Component description"] == "A short brief."
        assert live["Core truth"] == "Truth for River fact."
        assert live["Type field: Fact"] == "Truth for River fact."
        assert live["Type field: Retrieval question"] == "What is true of River fact?"
        assert "Type fields" not in live
        assert live["Rubric lines"] == "Check for River fact."
        assert live["Misconceptions"] == "The river is red. -> zz-vars-other"
        assert live["Prerequisite codes"] == "zz-vars-other"
        assert live["Encompass codes"] == ""
        assert live["Recipe"] == "retrieval"
        assert live["Move index"] == "1 of 1"
        assert live["Move name"] == "Retrieve"
        assert live["Move content"] == "What is true of River fact?"
        assert live["Evidence"] == "fact"
        assert live["Support band"] == "hold"
        assert live["Score"] == ""
        assert live["Status"] == "in_progress"
        assert live["Redirect pending"] == "no"
        assert live["Unit close"] == "no"
        assert "weather" in live["Interests"]

        client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "Truth for River fact."},
        )
        done = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={
                "reply": "Yes. Truth for River fact. This unit is complete.",
                "decision": "complete",
                "rubric_met": ["fact"],
            },
        )
        assert done.status_code == 200, done.text
        after = _variable_map(client.get("/kc/tutor/variables", params={"session_id": session_id}))
        assert after["Move index"] == "1 of 1"
        assert after["Move name"] == "Retrieve"
        assert after["Score"] == "100"
        assert after["Status"] == "completed"
        assert after["Unit close"] == "yes"
        assert after["Course outro"] == "no"
        assert after["Redirect pending"] == "no"
        assert client.get("/kc/tutor/variables", params={"session_id": str(uuid.uuid4())}).status_code == 404
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


LAYER_REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "021_kc_seven_layer.py"


def test_seven_layer_revision_adds_columns_only() -> None:
    text = LAYER_REVISION.read_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert "drop_table" not in upgrade
    assert "delete(" not in upgrade
    assert "misconception_policy" in upgrade
    assert "self_explanation" in upgrade
    assert "enrichment" in upgrade
    assert "hint_tier" in upgrade
    assert "enrichment_turns" in upgrade
    loop = Path(__file__).resolve().parents[1].joinpath("app", "kc_loop.py").read_text()
    prompt = Path(__file__).resolve().parents[1].joinpath("app", "kc_prompt.py").read_text()
    assert "engine.assemble" not in loop
    assert "engine.assemble" not in prompt
    assert "import assemble" not in loop


def test_decision_overrides_and_course_outro() -> None:
    course = _make("zz-layers", description="Two facts, then the course is done.")
    storm = _storm()
    _clear_progress(storm.id)
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-layers-a", "title": "First fact"},
                    {"code": "zz-layers-b", "title": "Second fact"},
                ]
            },
        ).json()["components"]
        first, second = pushed
        assert client.put(f"/kc/nodes/{first['id']}", json=_component("First fact")).status_code == 200
        conceptual = _component(
            "Second fact",
            kc_type="conceptual",
            core_truth="The rule is the contrast.",
            type_fields={
                "case_a": "Closed",
                "case_b": "Open",
                "prediction": "Which fits?",
                "rule": "The rule is the contrast.",
                "transfer_case": "A third case the child already knows.",
            },
        )
        assert client.put(f"/kc/nodes/{second['id']}", json=conceptual).status_code == 200
        assert client.post(f"/kc/courses/{course['id']}/ready").status_code == 200

        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": first["id"]},
        ).json()
        prompt = client.get(f"/kc/tutor/sessions/{opened['id']}/prompt").json()
        assert prompt["temperature"] == 0.4
        assert "How to sound" in prompt["system_prompt"]
        assert "Layer 3, Voice" not in prompt["system_prompt"]
        assert "Layer 6, Metacognition" not in prompt["system_prompt"]
        client.post(f"/kc/tutor/sessions/{opened['id']}/turn", json={"answer": "180"})
        held = client.post(
            f"/kc/tutor/sessions/{opened['id']}/decision",
            json={"reply": "Say the whole fact.", "decision": "complete", "rubric_met": ["fact"]},
        )
        assert held.status_code == 200, held.text
        assert held.json()["passed"] is False
        assert held.json()["status"] == "in_progress"
        assert held.json()["step_label"] == "Restate"
        client.post(
            f"/kc/tutor/sessions/{opened['id']}/turn",
            json={"answer": "Truth for First fact is the whole line."},
        )
        finished = client.post(
            f"/kc/tutor/sessions/{opened['id']}/decision",
            json={
                "reply": "This unit is complete. You can state the fact.",
                "decision": "complete",
                "rubric_met": ["restatement"],
            },
        )
        assert finished.json()["passed"] is True
        assert finished.json()["unit_complete"] is True
        assert finished.json()["course_complete"] is False

        other = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": second["id"]},
        ).json()
        other_prompt = client.get(f"/kc/tutor/sessions/{other['id']}/prompt").json()["system_prompt"]
        assert "Case one: Closed" in other_prompt
        assert "A third case the child already knows." not in other_prompt
        assert "The rule is the contrast." not in other_prompt
        for answer, decision, rubric in (
            ("Closed", "advance", []),
            ("They differ.", "advance", []),
            ("The rule is the contrast.", "advance", []),
        ):
            client.post(f"/kc/tutor/sessions/{other['id']}/turn", json={"answer": answer})
            step = client.post(
                f"/kc/tutor/sessions/{other['id']}/decision",
                json={"reply": "Stay with the rule.", "decision": decision, "rubric_met": rubric},
            )
            assert step.status_code == 200, step.text
        assert step.json()["status"] == "in_progress"
        assert step.json()["passed"] is False
        client.post(f"/kc/tutor/sessions/{other['id']}/turn", json={"answer": "The rule is the contrast."})
        blocked = client.post(
            f"/kc/tutor/sessions/{other['id']}/decision",
            json={"reply": "Not yet.", "decision": "complete", "rubric_met": []},
        )
        assert blocked.json()["status"] == "in_progress"
        assert blocked.json()["step_label"] == "State the rule"
        client.post(
            f"/kc/tutor/sessions/{other['id']}/turn",
            json={"answer": "Use it on the third case."},
        )
        # The blocked complete did not advance, so this answer is still on the rule move.
        # Finish the rule, then the transfer move.
        ruled = client.post(
            f"/kc/tutor/sessions/{other['id']}/decision",
            json={"reply": "The rule holds. Try the third case.", "decision": "advance", "rubric_met": ["rule"]},
        )
        assert ruled.json()["step_label"] == "Transfer"
        assert ruled.json()["passed"] is False
        client.post(f"/kc/tutor/sessions/{other['id']}/turn", json={"answer": "The third case follows the rule."})
        outro = client.post(
            f"/kc/tutor/sessions/{other['id']}/decision",
            json={
                "reply": "This unit is complete. The course is complete.",
                "decision": "complete",
                "rubric_met": ["transfer"],
            },
        )
        assert outro.status_code == 200, outro.text
        assert outro.json()["passed"] is True
        assert outro.json()["course_complete"] is True
        assert outro.json()["unit_complete"] is True
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_restart_clears_this_childs_course_and_a_later_component_still_opens() -> None:
    storm = _storm()
    db = SessionLocal()
    try:
        other = db.scalar(select(Student).where(Student.slug == "iron-man"))
        assert other is not None
        other_id = other.id
    finally:
        db.close()
    _clear_progress(storm.id)
    _clear_progress(other_id)
    draft = _make("zz-restart", title="Restart course")
    try:
        not_ready = client.post(
            f"/kc/tutor/courses/{draft['id']}/restart",
            json={"student_id": str(storm.id)},
        )
        assert not_ready.status_code == 422

        course = _ready(
            draft,
            [
                _spec("zz-restart-a", "First fact"),
                _spec("zz-restart-b", "Second fact", prerequisite_codes=["zz-restart-a"]),
                _spec("zz-restart-patch", "Foundation fact"),
            ],
            patches=("zz-restart-patch",),
        )
        kept = client.post(
            "/kc/courses",
            json={
                "code": "zz-keep",
                "title": "Keep course",
                "description": "Leave this progress alone.",
                "audience": "12-14",
                "kind": "mastery",
            },
        )
        assert kept.status_code == 200, kept.text
        kept_course = _ready(kept.json(), [_spec("zz-keep-a", "Kept fact")])

        _set_known(storm.id, "zz-restart-a")
        _set_known(storm.id, "zz-restart-b")
        _set_known(storm.id, "zz-restart-patch")
        _set_known(storm.id, "zz-keep-a")
        _set_known(other_id, "zz-restart-a")

        finished = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": _node(course, "zz-restart-a")["id"]},
        )
        assert finished.status_code == 200, finished.text
        resumed = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": _node(course, "zz-restart-b")["id"]},
        )
        assert resumed.status_code == 200, resumed.text
        db = SessionLocal()
        try:
            row = db.get(KcSession, uuid.UUID(finished.json()["id"]))
            patch = db.scalar(select(KcNode).where(KcNode.code == "zz-restart-patch"))
            assert row is not None and patch is not None
            row.status = "completed"
            row.score = 0
            row.redirect_kc_id = patch.id
            db.commit()
        finally:
            db.close()

        missing = client.post(
            f"/kc/tutor/courses/{course['id']}/restart",
            json={"student_id": str(uuid.uuid4())},
        )
        assert missing.status_code == 404

        restarted = client.post(
            f"/kc/tutor/courses/{course['id']}/restart",
            json={"student_id": str(storm.id)},
        )
        assert restarted.status_code == 200, restarted.text
        body = restarted.json()
        assert body["known"] == 0
        assert body["count_label"] == "0 of 2"
        assert [item["code"] for item in body["ring"]] == ["zz-restart-a", "zz-restart-b"]
        assert all(item["status"] == "not_started" for item in body["ring"])
        assert body["cards"][0]["code"] == "zz-restart-a"
        assert all(card["code"] != "zz-restart-patch" for card in body["cards"])
        assert _state(storm.id, "zz-restart-a") is None
        assert _state(storm.id, "zz-restart-b") is None
        assert _state(storm.id, "zz-restart-patch").status == "known"
        assert _state(storm.id, "zz-keep-a").status == "known"
        assert _state(other_id, "zz-restart-a").status == "known"

        db = SessionLocal()
        try:
            rows = list(
                db.scalars(
                    select(KcSession).where(
                        KcSession.student_id == storm.id,
                        KcSession.goal_id == uuid.UUID(course["id"]),
                    )
                )
            )
        finally:
            db.close()
        assert len(rows) == 1
        assert str(rows[0].id) == finished.json()["id"]
        assert rows[0].status == "completed"
        assert rows[0].redirect_kc_id is None
        assert client.get(f"/kc/tutor/sessions/{resumed.json()['id']}").status_code == 404

        kept_board = client.get(
            f"/kc/tutor/courses/{kept_course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert kept_board["count_label"] == "1 of 1"

        jumped = client.post(
            "/kc/tutor/sessions",
            json={
                "student_id": str(storm.id),
                "course_id": course["id"],
                "kc_id": _node(course, "zz-restart-b")["id"],
            },
        )
        assert jumped.status_code == 200, jumped.text
        assert jumped.json()["code"] == "zz-restart-b"
        assert jumped.json()["step"] == 0
        assert jumped.json()["status"] == "in_progress"
        assert _state(storm.id, "zz-restart-a") is None
    finally:
        _clear_progress(storm.id)
        _clear_progress(other_id)
        _wipe_zz()


def test_closing_a_component_saves_the_result_on_that_child() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _make("zz-result", description="Boats and cubes in a harbor.")
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={"components": [{"code": "zz-result-float", "title": "Floating"}]},
        ).json()["components"][0]
        saved = client.put(
            f"/kc/nodes/{pushed['id']}",
            json=_component(
                "Floating",
                description=(
                    "Outline: A principle about floating.\n"
                    "Topics: shape; density\n"
                    "Goals: Say why shape matters; Say why density matters"
                ),
                kc_type="conceptual",
                core_truth="Spread-out objects float.",
                rubric=["Say why shape matters", "Say why density matters", "States the rule"],
                type_fields={
                    "case_a": "A wide boat",
                    "case_b": "A solid cube",
                    "prediction": "What happens to this one?",
                    "rule": "Spread-out objects float.",
                    "transfer_case": "",
                },
            ),
        )
        assert saved.status_code == 200, saved.text
        assert client.post(f"/kc/courses/{course['id']}/ready").status_code == 200
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": pushed["id"]},
        )
        assert opened.status_code == 200, opened.text
        session_id = opened.json()["id"]
        assert opened.json()["step_label"] == "Orient"
        prompt = client.get(f"/kc/tutor/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "A principle about floating." in prompt
        assert "density" not in prompt
        assert "Spread-out objects float" not in prompt
        assert "Boats and cubes in a harbor." not in prompt

        def decide(answer: str, decision: str, rubric: list[str]) -> dict:
            posted = client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": answer})
            assert posted.status_code == 200, posted.text
            body = client.post(
                f"/kc/tutor/sessions/{session_id}/decision",
                json={"reply": "Stay with this step.", "decision": decision, "rubric_met": rubric},
            )
            assert body.status_code == 200, body.text
            return body.json()

        assert decide("The outline is clear.", "advance", [])["step_label"] == "shape"
        topic_prompt = client.get(f"/kc/tutor/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "The topic is shape." in topic_prompt
        assert "The goal is Say why shape matters." in topic_prompt
        for hidden in (
            "density",
            "Say why density matters",
            "Spread-out objects float",
            "A wide boat",
            "A solid cube",
            "A principle about floating",
            "Boats and cubes in a harbor.",
        ):
            assert hidden not in topic_prompt, hidden
        assert "The child will type." in topic_prompt
        missed = decide("Something else.", "advance", [])
        assert missed["step_label"] == "shape"
        assert decide("Shape changes how the water pushes.", "advance", ["goal-1"])["step_label"] == "density"
        assert decide("Density is the other part.", "advance", ["goal-2"])["step_label"] == "Predict case one"
        assert decide("This holds", "advance", [])["step_label"] == "Predict case two"
        assert decide("This does not hold", "advance", [])["step_label"] == "Contrast"
        assert decide("The wide one floats and the cube sinks.", "advance", [])["step_label"] == "State the rule"
        finished = decide("Spread-out objects float.", "complete", ["rule"])
        assert finished["passed"] is True
        assert finished["unit_complete"] is True
        board = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert "course_score" not in board
        assert "score" not in board
        unit = next(item for item in board["units"] if item["code"] == "zz-result-float")
        result = unit["result"]
        assert result["status"] == "known"
        assert result["rubric_met"] == ["goal-1", "goal-2", "rule"]
        assert "Say why shape matters" in result["justification"]
        assert result["strong"]
        assert result["work_on"]
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_course_progress_reports_percent_and_unit_status() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _ready(
        _make("zz-progress", title="Progress course"),
        [
            _spec("zz-prog-known", "Known fact", prerequisite_codes=["zz-prog-patch"]),
            _spec("zz-prog-fragile", "Fragile fact"),
            _spec("zz-prog-open", "Open fact"),
            _spec("zz-prog-closed", "Closed fact"),
            _spec("zz-prog-known-open", "Known and open"),
            _spec("zz-prog-patch", "Patch fact"),
        ],
        patches=("zz-prog-patch",),
    )
    try:
        _set_known(storm.id, "zz-prog-known")
        _set_status(storm.id, "zz-prog-fragile", "fragile")
        _set_known(storm.id, "zz-prog-known-open")
        before = _counts()["sessions"]
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": _node(course, "zz-prog-open")["id"]},
        )
        assert opened.status_code == 200, opened.text
        known_open = client.post(
            "/kc/tutor/sessions",
            json={
                "student_id": str(storm.id),
                "course_id": course["id"],
                "kc_id": _node(course, "zz-prog-known-open")["id"],
            },
        )
        assert known_open.status_code == 200, known_open.text
        closed = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": _node(course, "zz-prog-closed")["id"]},
        )
        assert closed.status_code == 200, closed.text
        _finish_session(closed.json()["id"])
        sessions_after_open = _counts()["sessions"]
        assert sessions_after_open == before + 3

        board = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        )
        assert board.status_code == 200, board.text
        body = board.json()
        assert _counts()["sessions"] == sessions_after_open
        assert body["known"] == 2
        assert body["total"] == 5
        assert body["percent"] == 40
        assert body["count_label"] == "2 of 5"
        assert [item["code"] for item in body["units"]] == [
            "zz-prog-known",
            "zz-prog-fragile",
            "zz-prog-open",
            "zz-prog-closed",
            "zz-prog-known-open",
            "zz-prog-patch",
        ]
        status = {item["code"]: item["status"] for item in body["units"]}
        assert status == {
            "zz-prog-known": "completed",
            "zz-prog-fragile": "in_progress",
            "zz-prog-open": "in_progress",
            "zz-prog-closed": "not_started",
            "zz-prog-known-open": "completed",
            "zz-prog-patch": "not_started",
        }
        assert body["units"][-1]["patch"] is True
        assert body["units"][-1]["title"] == "Patch fact"
        assert all(item["patch"] is False for item in body["units"][:-1])
        ring = {item["code"]: item["status"] for item in body["ring"]}
        assert ring["zz-prog-known"] == "known"
        assert ring["zz-prog-fragile"] == "fragile"
        assert ring["zz-prog-open"] == "not_started"
        assert "zz-prog-patch" not in ring

        again = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert again["units"] == body["units"]
        assert again["percent"] == body["percent"]
        assert _counts()["sessions"] == sessions_after_open
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def _history_lines(text: str) -> list[str]:
    return [line for line in (text or "").splitlines() if line.strip()]


def _assert_et_stamp(line: str) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    stamp = line.split(" ", 2)[:2]
    parsed = datetime.strptime(" ".join(stamp), "%Y-%m-%d %H:%M:%S")
    now = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
    assert abs((now - parsed).total_seconds()) < 180
    assert " ET " in f"{line} "


def test_a_bad_broken_kc_is_repaired_and_creation_continues() -> None:
    course = _make("zz-repair", description="The river in this course is blue.")
    storm = _storm()
    _clear_progress(storm.id)
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-repair-a", "title": "River fact"},
                    {"code": "zz-repair-b", "title": "Other"},
                ]
            },
        ).json()
        river, other = pushed["components"]
        assert river["history"] == ""
        assert other["history"] == ""
        assert pushed["history"] == ""

        prompt = client.post(
            f"/kc/nodes/{river['id']}/creator-prompt",
            json={"message": "Draft this component.", "model": "gpt-4.1"},
        )
        assert prompt.status_code == 200, prompt.text
        enum = prompt.json()["schema"]["properties"]["misconceptions"]["items"]["properties"]["broken_kc"]["enum"]
        assert enum == ["zz-repair-b"]
        assert "zz-repair-a" not in enum
        instructions = prompt.json()["system_prompt"]
        assert "Copy one code from the other component codes into broken_kc." in instructions
        assert "It is not a description and not this component's code." in instructions
        assert "empty misconception" not in instructions.lower()

        missing = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this component.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(misconceptions=[], prerequisite_codes=["zz-repair-b"]),
            },
        )
        assert missing.status_code == 422
        assert "Recommend a misconception" in missing.json()["detail"]
        assert client.get(f"/kc/nodes/{river['id']}").json()["history"] == ""

        bad = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this component.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(
                    misconceptions=[{"wrong_move": "The river is purple", "broken_kc": "not-a-component"}],
                    prerequisite_codes=["zz-repair-b"],
                ),
            },
        )
        assert bad.status_code == 200, bad.text
        assert bad.json()["messages"]
        assert bad.json()["draft"]["misconceptions"] == []
        assert "not-a-component" not in str(bad.json()["draft"]["misconceptions"])
        assert "zz-repair-b" not in str(bad.json()["draft"]["misconceptions"])

        mixed = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Revise the draft.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(
                    misconceptions=[
                        {"wrong_move": "The river is red", "broken_kc": "zz-repair-b"},
                        {"wrong_move": "The river is green", "broken_kc": "zz-repair-a"},
                    ],
                    prerequisite_codes=["zz-repair-b"],
                ),
            },
        )
        assert mixed.status_code == 200, mixed.text
        assert mixed.json()["draft"]["misconceptions"] == [
            {"wrong_move": "The river is red", "broken_kc": "zz-repair-b"}
        ]

        node = client.get(f"/kc/nodes/{river['id']}").json()
        stored = client.get(f"/kc/courses/{course['id']}").json()
        lines = _history_lines(node["history"])
        assert lines == _history_lines(stored["history"])
        assert len(lines) == 2
        assert all("Warning:" in line for line in lines)
        assert "not-a-component" in lines[0]
        assert "not another component on this course" in lines[0]
        assert "zz-repair-b" in lines[0]
        assert 'Changed broken_kc from "not-a-component" to removed' in lines[0]
        assert "zz-repair-a" in lines[1]
        assert 'Changed broken_kc from "zz-repair-a" to removed' in lines[1]
        assert "so creation could continue" in lines[0]
        for line in lines:
            _assert_et_stamp(line)
        assert client.get(f"/kc/nodes/{other['id']}").json()["history"] == ""

        fresh = client.post(
            f"/kc/nodes/{river['id']}/creator-prompt",
            json={"message": "Draft this component again.", "model": "gpt-4.1"},
        )
        assert fresh.status_code == 200, fresh.text
        for line in lines:
            assert line not in fresh.text
        assert "history" not in fresh.json()["schema"]["properties"]

        written = client.post(f"/kc/nodes/{river['id']}/push", json=mixed.json()["draft"])
        assert written.status_code == 200, written.text
        assert written.json()["misconceptions"] == [
            {"wrong_move": "The river is red", "broken_kc": "zz-repair-b"}
        ]
        pushed_lines = _history_lines(written.json()["history"])
        assert pushed_lines[:2] == lines
        _stamp, note = pushed_lines[2].split(" ET ", 1)
        assert note == "Push from AI."
        _assert_et_stamp(pushed_lines[2])
        assert client.get(f"/kc/courses/{course['id']}").json()["history"] == written.json()["history"]

        saved = client.put(f"/kc/nodes/{river['id']}", json=_component("River fact", prerequisite_codes=["zz-repair-b"]))
        assert saved.status_code == 200, saved.text
        assert saved.json()["history"] == written.json()["history"]
        assert client.put(
            f"/kc/nodes/{other['id']}",
            json=_component("Other"),
        ).status_code == 200
        assert client.get(f"/kc/nodes/{other['id']}").json()["history"] == ""
        assert client.post(f"/kc/courses/{course['id']}/ready").status_code == 200

        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": river["id"]},
        )
        assert opened.status_code == 200, opened.text
        tutor = client.get(f"/kc/tutor/sessions/{opened.json()['id']}/prompt")
        variables = client.get(
            "/kc/tutor/variables",
            params={"session_id": opened.json()["id"]},
        )
        assert tutor.status_code == 200, tutor.text
        names = [row["name"] for row in variables.json()["variables"]]
        assert "History" not in names
        for line in _history_lines(client.get(f"/kc/nodes/{river['id']}").json()["history"]):
            assert line not in tutor.text
            assert line not in variables.text
            assert line not in fresh.text
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_a_course_with_no_sibling_clears_a_bad_broken_kc() -> None:
    course = _make("zz-alone", description="The river in this course is blue.")
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={"components": [{"code": "zz-alone-a", "title": "River fact"}]},
        ).json()
        river = pushed["components"][0]
        assert river["history"] == ""
        assert pushed["history"] == ""

        prompt = client.post(
            f"/kc/nodes/{river['id']}/creator-prompt",
            json={"message": "Draft this component.", "model": "gpt-4.1"},
        )
        assert prompt.status_code == 200, prompt.text
        misconceptions = prompt.json()["schema"]["properties"]["misconceptions"]
        assert misconceptions["maxItems"] == 0
        assert "broken_kc" not in misconceptions["items"].get("properties", {})
        instructions = prompt.json()["system_prompt"]
        assert "Return an empty misconceptions array." in instructions
        assert "Do not ask for a broken_kc." in instructions
        assert "Copy one code from the other component codes" not in instructions

        turned = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this component.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(
                    misconceptions=[{"wrong_move": "The river is purple", "broken_kc": "not-a-component"}],
                    prerequisite_codes=[],
                ),
            },
        )
        assert turned.status_code == 200, turned.text
        assert turned.json()["draft"]["misconceptions"] == [
            {"wrong_move": "The river is purple", "broken_kc": ""}
        ]
        node = client.get(f"/kc/nodes/{river['id']}").json()
        stored = client.get(f"/kc/courses/{course['id']}").json()
        lines = _history_lines(node["history"])
        assert lines == _history_lines(stored["history"])
        assert len(lines) == 1
        assert 'broken_kc "not-a-component"' in lines[0]
        assert "not another component on this course" in lines[0]
        assert 'Changed broken_kc from "not-a-component" to ""' in lines[0]
        assert "Allowed codes: none." in lines[0]
        _assert_et_stamp(lines[0])
        again = client.post(
            f"/kc/nodes/{river['id']}/creator-prompt",
            json={"message": "Draft this component again.", "model": "gpt-4.1"},
        )
        assert again.status_code == 200, again.text
        assert lines[0] not in again.text
        assert "history" not in again.json()["schema"]["properties"]

        written = client.post(f"/kc/nodes/{river['id']}/push", json=turned.json()["draft"])
        assert written.status_code == 200, written.text
        assert written.json()["misconceptions"][0]["broken_kc"] == ""
        pushed_lines = _history_lines(written.json()["history"])
        assert pushed_lines[0] == lines[0]
        assert pushed_lines[1].split(" ET ", 1)[1] == "Push from AI."
        assert client.get(f"/kc/courses/{course['id']}").json()["history"] == written.json()["history"]
    finally:
        _wipe_zz()


def _synthesis_fields(**overrides: object) -> dict:
    body = {
        "kc_type": "synthesis",
        "faulty_plan": "A rookie swaps the two earlier facts.",
        "mix_a": "zz-mix-b",
        "mix_b": "zz-mix-c",
        "misconceptions": [{"wrong_move": "The river is red", "broken_kc": "zz-mix-b"}],
        "prerequisite_codes": ["zz-mix-b"],
    }
    body.update(overrides)
    return _model_fields(**body)


def _model_turn(node_id: str, draft: dict):
    return client.post(
        f"/kc/nodes/{node_id}/model-turn",
        json={
            "message": "Draft this component.",
            "discussion": f"{_model_fields()['discussion']} MIX-LOG-SECRET",
            "draft": draft,
        },
    )


def _mix_logs(caplog, action: str) -> list[str]:
    return [record.getMessage() for record in caplog.records if f"kc mix {action}" in record.getMessage()]


def test_a_repeated_mix_is_repaired_and_creation_continues(caplog) -> None:
    course = _make("zz-mix", description="The river in this course is blue.")
    try:
        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-mix-a", "title": "River fact"},
                    {"code": "zz-mix-b", "title": "Other fact"},
                    {"code": "zz-mix-c", "title": "Third fact"},
                ]
            },
        ).json()
        river = pushed["components"][0]
        assert river["history"] == ""
        assert pushed["history"] == ""

        prompt = client.post(
            f"/kc/nodes/{river['id']}/creator-prompt",
            json={"message": "Draft this component.", "model": "gpt-4.1"},
        )
        assert prompt.status_code == 200, prompt.text
        schema = prompt.json()["schema"]["properties"]
        assert "mix_a" not in schema
        assert "mix_b" not in schema
        assert schema["blocks"]["type"] == "array"
        assert "ordered blocks[] array" in prompt.json()["system_prompt"]
        assert "history" not in schema

        caplog.set_level("WARNING", logger="app.kc")
        caplog.clear()
        kept = _model_turn(river["id"], _synthesis_fields())
        assert kept.status_code == 200, kept.text
        assert kept.json()["draft"]["type_fields"]["mixes"] == ["zz-mix-b", "zz-mix-c"]
        assert client.get(f"/kc/nodes/{river['id']}").json()["history"] == ""
        assert _mix_logs(caplog, "repaired") == []
        assert _mix_logs(caplog, "rejected") == []

        caplog.clear()
        repeated = _model_turn(river["id"], _synthesis_fields(mix_a="zz-mix-b", mix_b="zz-mix-b"))
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["draft"]["type_fields"]["mixes"] == []
        assert "zz-mix-c" not in repeated.json()["draft"]["type_fields"]["mixes"]
        node = client.get(f"/kc/nodes/{river['id']}").json()
        stored = client.get(f"/kc/courses/{course['id']}").json()
        lines = _history_lines(node["history"])
        assert lines == _history_lines(stored["history"])
        assert len(lines) == 1
        assert lines[0].split(" Warning: ", 1)[1] == (
            'mix_a "zz-mix-b" and mix_b "zz-mix-b" are not two different other components. '
            "Allowed codes: zz-mix-b, zz-mix-c. "
            'Changed mixes from "zz-mix-b" and "zz-mix-b" to cleared (kept nothing) '
            "so creation could continue."
        )
        _assert_et_stamp(lines[0])
        repaired = _mix_logs(caplog, "repaired")
        assert len(repaired) == 1
        assert f"node_id={river['id']}" in repaired[0]
        assert "mix_a='zz-mix-b'" in repaired[0]
        assert "mix_b='zz-mix-b'" in repaired[0]
        assert "allowed=zz-mix-b, zz-mix-c" in repaired[0]
        assert "MIX-LOG-SECRET" not in repaired[0]
        assert "A rookie swaps" not in repaired[0]

        written = client.post(f"/kc/nodes/{river['id']}/push", json=repeated.json()["draft"])
        assert written.status_code == 200, written.text
        assert written.json()["type_fields"]["mixes"] == []
        pushed_lines = _history_lines(written.json()["history"])
        assert pushed_lines[0] == lines[0]
        assert pushed_lines[1].split(" ET ", 1)[1] == "Push from AI."
        assert client.get(f"/kc/courses/{course['id']}").json()["history"] == written.json()["history"]

        titled = _model_turn(river["id"], _synthesis_fields(mix_a="zz-mix-b", mix_b="River fact"))
        assert titled.status_code == 200, titled.text
        assert titled.json()["draft"]["type_fields"]["mixes"] == []
        own = _model_turn(river["id"], _synthesis_fields(mix_a="zz-mix-a", mix_b="zz-mix-c"))
        assert own.status_code == 200, own.text
        assert own.json()["draft"]["type_fields"]["mixes"] == []
        single = _model_turn(river["id"], _synthesis_fields(mix_a="zz-mix-b", mix_b=""))
        assert single.status_code == 200, single.text
        assert single.json()["draft"]["type_fields"]["mixes"] == []
        fresh = _history_lines(client.get(f"/kc/nodes/{river['id']}").json()["history"])
        assert len(fresh) == 5
        assert 'mix_b "River fact"' in fresh[2]
        assert 'mix_a "zz-mix-a"' in fresh[3]
        assert 'mix_b ""' in fresh[4]
        assert all("to cleared (kept nothing)" in line for line in fresh[2:])
        assert 'to "zz-mix-c"' not in "\n".join(fresh[2:])
        assert client.get(f"/kc/courses/{course['id']}").json()["history"] == "\n".join(fresh)

        before = client.get(f"/kc/nodes/{river['id']}").json()["history"]
        caplog.clear()
        empty = _model_turn(river["id"], _synthesis_fields(mix_a="", mix_b=""))
        assert empty.status_code == 422
        detail = empty.json()["detail"]
        assert detail.startswith("Recommend two different components for the mix.")
        assert 'Rejected: "" and "".' in detail
        assert "Allowed codes: zz-mix-b, zz-mix-c." in detail
        assert client.get(f"/kc/nodes/{river['id']}").json()["history"] == before
        rejected = _mix_logs(caplog, "rejected")
        assert len(rejected) == 1
        assert f"node_id={river['id']}" in rejected[0]
        assert "mix_a=''" in rejected[0]
        assert "mix_b=''" in rejected[0]
        assert "allowed=zz-mix-b, zz-mix-c" in rejected[0]
        assert "MIX-LOG-SECRET" not in rejected[0]
    finally:
        _wipe_zz()


def test_fewer_than_two_other_components_allow_empty_mixes(caplog) -> None:
    course = _make("zz-mixone", description="The river in this course is blue.")
    try:
        alone = client.post(
            f"/kc/courses/{course['id']}/push",
            json={"components": [{"code": "zz-mixone-a", "title": "River fact"}]},
        ).json()["components"][0]
        prompt = client.post(
            f"/kc/nodes/{alone['id']}/creator-prompt",
            json={"message": "Draft this component.", "model": "gpt-4.1"},
        )
        assert prompt.status_code == 200, prompt.text
        assert "mix_a" not in prompt.json()["schema"]["properties"]
        assert "mix_b" not in prompt.json()["schema"]["properties"]
        assert "This course has no other component." in prompt.json()["system_prompt"]

        caplog.set_level("WARNING", logger="app.kc")
        caplog.clear()
        empty = _model_turn(
            alone["id"],
            _synthesis_fields(mix_a="", mix_b="", misconceptions=[], prerequisite_codes=[]),
        )
        assert empty.status_code == 200, empty.text
        assert empty.json()["draft"]["type_fields"]["mixes"] == []
        assert client.get(f"/kc/nodes/{alone['id']}").json()["history"] == ""
        assert _mix_logs(caplog, "repaired") == []

        titled = _model_turn(
            alone["id"],
            _synthesis_fields(
                mix_a="River fact",
                mix_b="",
                misconceptions=[],
                prerequisite_codes=[],
            ),
        )
        assert titled.status_code == 200, titled.text
        assert titled.json()["draft"]["type_fields"]["mixes"] == []
        line = _history_lines(client.get(f"/kc/nodes/{alone['id']}").json()["history"])[0]
        assert 'mix_a "River fact" and mix_b ""' in line
        assert "Allowed codes: none." in line
        assert "to cleared (kept nothing)" in line
        _assert_et_stamp(line)
        assert client.get(f"/kc/courses/{course['id']}").json()["history"] == line

        added = client.post(
            f"/kc/courses/{course['id']}/push",
            json={
                "components": [
                    {"code": "zz-mixone-a", "title": "River fact"},
                    {"code": "zz-mixone-b", "title": "Other fact"},
                ]
            },
        )
        assert added.status_code == 200, added.text
        pair = {item["code"]: item for item in added.json()["components"]}
        prompt = client.post(
            f"/kc/nodes/{pair['zz-mixone-a']['id']}/creator-prompt",
            json={"message": "Draft this component.", "model": "gpt-4.1"},
        )
        assert prompt.status_code == 200, prompt.text
        assert "mix_a" not in prompt.json()["schema"]["properties"]
        assert "mix_b" not in prompt.json()["schema"]["properties"]
        assert prompt.json()["schema"]["properties"]["misconceptions"]["items"]["properties"]["broken_kc"]["enum"] == [
            "zz-mixone-b"
        ]
        assert "Do not ask for two mixes." not in prompt.json()["system_prompt"]

        empty_pair = _model_turn(
            pair["zz-mixone-a"]["id"],
            _synthesis_fields(
                mix_a="",
                mix_b="",
                misconceptions=[{"wrong_move": "The river is red", "broken_kc": "zz-mixone-b"}],
                prerequisite_codes=["zz-mixone-b"],
            ),
        )
        assert empty_pair.status_code == 200, empty_pair.text
        assert empty_pair.json()["draft"]["type_fields"]["mixes"] == []

        named = _model_turn(
            pair["zz-mixone-a"]["id"],
            _synthesis_fields(
                mix_a="zz-mixone-b",
                mix_b="River fact",
                misconceptions=[{"wrong_move": "The river is red", "broken_kc": "zz-mixone-b"}],
                prerequisite_codes=["zz-mixone-b"],
            ),
        )
        assert named.status_code == 200, named.text
        assert named.json()["draft"]["type_fields"]["mixes"] == ["zz-mixone-b"]
        kept_line = _history_lines(client.get(f"/kc/nodes/{pair['zz-mixone-a']['id']}").json()["history"])[-1]
        assert 'Changed mixes from "zz-mixone-b" and "River fact" to "zz-mixone-b"' in kept_line
        assert "zz-mixone-c" not in kept_line
        assert client.get(f"/kc/courses/{course['id']}").json()["history"].endswith(kept_line)
    finally:
        _wipe_zz()
