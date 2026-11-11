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
        "outline": f"How {title} works.",
        "core_truth": f"Truth for {title}.",
        "rubric": [f"Check for {title}."],
        "misconceptions": [],
        "prerequisite_codes": [],
        "encompasses_codes": [],
        "blocks": [
            {
                "id": "blk-1",
                "type": "topic_goal",
                "data": {"topic": title, "goal": f"Explain {title}."},
            }
        ],
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


def test_pushed_course_components_keep_plain_descriptions_order_and_prerequisites() -> None:
    codes = ["angle-sum", "missing-angle", "sas-versus-ssa", "congruence"]
    _drop_codes(codes)
    course = _make(
        "zz-draft",
        description="Name the angle sum, find the missing angle, and tell SAS from SSA.",
    )
    before = _counts()
    try:
        drafted = [
            {
                "code": code,
                "title": title,
                "description": f"The child can use {title}. The one idea is {title}. A common mix-up is skipping it.",
                "prerequisite_codes": codes[max(index - 1, 0) : index],
            }
            for index, (code, title) in enumerate(
                zip(codes, ["Angle sum", "Missing angle", "SAS versus SSA", "Congruence"])
            )
        ]
        assert _counts()["nodes"] == before["nodes"]
        pushed = client.post(f"/kc/courses/{course['id']}/push", json={"components": drafted})
        assert pushed.status_code == 200, pushed.text
        components = pushed.json()["components"]
        assert [item["title"] for item in components] == ["Angle sum", "Missing angle", "SAS versus SSA", "Congruence"]
        assert [item["description"] for item in components] == [item["description"] for item in drafted]
        assert all(item["outline"] == "" and item["topics"] == [] for item in components)
        assert all("Recommended blocks" not in item["description"] for item in components)
        assert [item["prerequisite_codes"] for item in components] == [[], ["angle-sum"], ["missing-angle"], ["sas-versus-ssa"]]
        structure = client.get(f"/kc/courses/{course['id']}/structure").json()
        shown = [row["description"] for group in structure["groups"] for row in group["components"]]
        assert shown == [item["description"] for item in components]
        assert _counts()["nodes"] == before["nodes"] + 4
        assert _counts()["edges"] == before["edges"] + 3
        assert _counts()["chats"] == before["chats"]
    finally:
        _wipe_zz()
        _drop_codes(codes)


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
        drafted = client.post(
            f"/kc/nodes/{first['id']}/model-turn",
            json={
                "message": "Draft this fact.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(**{"misconceptions": [{"wrong_move": "The river is red", "broken_kc": "zz-four-b"}], "prerequisite_codes": ["zz-four-b"]}),
            },
        )
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
            json=_component(
                "Later",
                prerequisite_codes=["zz-ready-a"],
                blocks=[{"id": "blk-1", "type": "topic_goal", "data": {"topic": "Later", "goal": ""}}],
            ),
        )
        assert missing_check.status_code == 200, missing_check.text
        not_ready = client.post(f"/kc/courses/{course['id']}/ready")
        assert not_ready.status_code == 422
        assert "needs a topic and a goal" in not_ready.text

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
                "kc_tutor_config": {
                    "overarching": {"stay_on_course": "exploratory"},
                    "blocks": {
                        "topic_goal": {
                            "explanation_depth": 5,
                            "max_retries_before_reveal": 3,
                        }
                    },
                },
            },
        )
        assert switched.status_code == 200, switched.text
        prompt = client.get(f"/kc/tutor/sessions/{opened.json()['id']}/prompt")
        assert prompt.status_code == 200, prompt.text
        text = prompt.json()["system_prompt"]
        assert prompt.json()["recipe"] == "block_walk"
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
        assert "Teach thoroughly with step-by-step scaffolding and an example before asking the question." in text
        assert "Reveal the goal after 3 missed answers." in text
        assert "You may follow a short tangent, then come back to this block." in text
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
        assert "Block 1 of 1: Topic / Goal" in text
        assert "You do not set the block order, the edges, or the final mastery score." in text
        db = SessionLocal()
        try:
            stored = db.get(KcSession, opened.json()["id"])
            assert stored is not None
            assert stored.recipe == "block_walk"
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
        held = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={
                "reply": "The outline is clear.",
                "decision": "complete",
                "rubric_met": [],
                "affect": "engaged",
                "confidence": "ok",
            },
        )
        assert held.status_code == 200, held.text
        assert held.json()["passed"] is False
        assert held.json()["step_label"] == "Block 1 of 1: Topic / Goal"
        _open_goal(opened.json()["id"])
        client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "I can explain the later fact."},
        )
        summary = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={
                "reply": "Summary check.",
                "decision": "stay",
                "substep_passed": True,
                "rubric_met": ["fact"],
            },
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["active_substep"] == "summary_check"
        assert summary.json()["unit_complete"] is False
        done = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={
                "reply": "Yes. The river in this course is blue. This unit is complete.",
                "decision": "complete",
                "block_complete": True,
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
                core_truth="Congruence means the same size and the same shape.",
                rubric=["Says same size and same shape"],
            ),
            _spec(
                "zz-mis-patch",
                "The included angle",
                core_truth="The included angle lies between the two sides.",
                rubric=["Points to the angle between the two sides"],
            ),
            _spec(
                "zz-mis-claim",
                "SAS versus SSA",
                core_truth=rule,
                rubric=["Names SAS as the proving case"],
                prerequisite_codes=["zz-mis-base", "zz-mis-patch"],
                misconceptions=[{"wrong_move": "SSA proves congruence", "broken_kc": "zz-mis-patch"}],
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
        _open_goal(opened.json()["id"])
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
        rule = sas["core_truth"]
        again = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": fresh["id"], "kc_id": sas["id"]},
        )
        assert again.status_code == 200, again.text
        session_id = again.json()["id"]
        _open_goal(session_id)
        steps = (
            ("The outline is clear.", "advance", []),
            ("I can explain SAS versus SSA.", "complete", ["rule"]),
        )
        step = None
        for answer, decision, rubric in steps:
            posted = client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": answer})
            assert posted.status_code == 200, posted.text
            if decision == "complete":
                summary = client.post(
                    f"/kc/tutor/sessions/{session_id}/decision",
                    json={
                        "reply": "Summary check.",
                        "decision": "stay",
                        "substep_passed": True,
                        "rubric_met": rubric,
                    },
                )
                assert summary.status_code == 200, summary.text
                assert summary.json()["active_substep"] == "summary_check"
            step = client.post(
                f"/kc/tutor/sessions/{session_id}/decision",
                json={
                    "reply": "That holds.",
                    "decision": decision,
                    "block_complete": decision == "complete",
                    "rubric_met": rubric,
                },
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
    course = _ready(
        _make("zz-box", title="Timed course", kind="time_boxed", minutes=30),
        [
            _spec(
                "zz-box-fact",
                "Triangle angle sum",
                core_truth="The interior angles of a triangle sum to 180 degrees.",
            ),
            _spec(
                "zz-box-steps",
                "Find the missing angle",
                core_truth="The missing angle is 180 minus the other two angles.",
                prerequisite_codes=["zz-box-fact"],
                encompasses_codes=["zz-box-fact"],
            ),
            _spec(
                "zz-box-idea",
                "What congruence means",
                core_truth="Congruence means the same size and the same shape.",
            ),
            _spec(
                "zz-box-patch",
                "The included angle",
                core_truth="The included angle lies between the two sides.",
            ),
            _spec(
                "zz-box-claim",
                "SAS versus SSA",
                core_truth="SAS fixes a triangle and SSA does not.",
                prerequisite_codes=["zz-box-idea", "zz-box-patch"],
                misconceptions=[{"wrong_move": "SSA proves congruence", "broken_kc": "zz-box-patch"}],
            ),
            _spec(
                "zz-box-cause",
                "Why SSA fails",
                core_truth="SSA fails because the given angle is not included.",
                prerequisite_codes=["zz-box-claim"],
            ),
            _spec(
                "zz-box-plan",
                "Fix the congruence plan",
                core_truth="Same size and same shape, together with SAS, show congruence.",
                prerequisite_codes=["zz-box-idea", "zz-box-claim"],
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
        assert {item["kc_type"] for item in course["components"]} == {None}

        factual = _node(course, "zz-box-fact")
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": factual["id"]},
        )
        assert opened.json()["recipe"] == "block_walk"
        assert opened.json()["step_label"] == "Block 1 of 1: Topic / Goal"
        client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "Not yet."},
        )
        held = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={
                "reply": "The outline is clear.",
                "decision": "complete",
                "rubric_met": [],
            },
        )
        assert held.status_code == 200, held.text
        assert held.json()["passed"] is False
        _open_goal(opened.json()["id"])
        client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "Explain the triangle angle sum."},
        )
        summary = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={
                "reply": "Summary check.",
                "decision": "stay",
                "substep_passed": True,
                "rubric_met": ["fact"],
            },
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["active_substep"] == "summary_check"
        answered = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={
                "reply": "Yes. The interior angles add up to 180 degrees. This unit is complete.",
                "decision": "complete",
                "block_complete": True,
                "rubric_met": ["fact"],
            },
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["passed"] is True
        assert answered.json()["step_label"] == "Block 1 of 1: Topic / Goal"
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

        first = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this fact.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(**{"misconceptions": [{"wrong_move": "The river is red", "broken_kc": "zz-creator-b"}], "prerequisite_codes": ["zz-creator-b"]}),
            },
        )
        assert first.status_code == 200, first.text
        assert first.json()["messages"][-1]["content"].index(_model_fields()["discussion"]) < first.json()["messages"][-1]["content"].index("Core truth:")
        draft = first.json()["draft"]
        assert draft["kind"] == "component"
        assert draft["code"] == "zz-creator-a"
        assert "kc_type" not in draft
        assert any(block.get("type") == "topic_goal" for block in draft["blocks"])
        assert _counts()["messages"] == before_messages
        stored = client.get(f"/kc/nodes/{river['id']}").json()
        assert stored["kc_type"] is None

        revised = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Core truth: The river in this course is blue.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(core_truth="The river in this course is blue.", **{"misconceptions": [{"wrong_move": "The river is red", "broken_kc": "zz-creator-b"}], "prerequisite_codes": ["zz-creator-b"]}),
            },
        )
        assert revised.status_code == 200, revised.text
        assert revised.json()["draft"]["core_truth"] == "The river in this course is blue."
        assert "kc_type" not in revised.json()["draft"]
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
        assert "no blocks" in refused.text
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
            json=_component("Contrast", core_truth="The rule is the contrast."),
        ).status_code == 200
        assert client.put(
            f"/kc/nodes/{cause['id']}",
            json=_component(
                "Decision",
                core_truth="Taxes move prices.",
                prerequisite_codes=["zz-speak-concept"],
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
        assert spoken.json()["choice"] is None
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
            json={"reply": "Now the next block.", "decision": "advance"},
        )
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["passed"] is False
        assert stepped.json()["step"] == 0
        assert stepped.json()["needs_speech"] is False
        assert stepped.json()["choice"] is None
        assert stepped.json()["step_label"] == "Block 1 of 1: Topic / Goal"

        causal = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": cause["id"]},
        ).json()
        client.post(f"/kc/tutor/sessions/{causal['id']}/speech", json={"content": "Taxes move prices."})
        client.post(f"/kc/tutor/sessions/{causal['id']}/turn", json={"answer": "The tax changes the price."})
        held = client.post(
            f"/kc/tutor/sessions/{causal['id']}/decision",
            json={"reply": "What is at stake?", "decision": "advance"},
        )
        assert held.json()["passed"] is False
        assert held.json()["step"] == 0
        assert held.json()["choice"] is None
        fresh = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": cause["id"]},
        )
        assert fresh.status_code == 200, fresh.text
        assert fresh.json()["id"] == causal["id"]
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def _block(block_id: str, block_type: str, **data: object) -> dict:
    return {"id": block_id, "type": block_type, "data": data}


def _model_fields(**overrides: object) -> dict:
    body: dict = {
        "discussion": (
            "River fact is the claim that this river is blue, which is why a kid has to recall the color "
            "before any later step in the course."
        ),
        "description": "The river is blue.",
        "outline": "How the river looks.",
        "title": "River fact",
        "core_truth": "The river in this course is blue.",
        "blocks": [_block("blk_color", "topic_goal", topic="color", goal="Recall the color")],
        "misconceptions": [{"wrong_move": "The river is red", "broken_kc": "zz-fields-b"}],
        "prerequisite_codes": ["zz-fields-b"],
        "encompasses_codes": [],
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
            json=_component(
                "River fact",
                description="Outline: Edited by hand.\nTopics: color\nGoals: Recall it",
                outline=None,
            ),
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
                "draft": _model_fields(outline=""),
            },
        )
        assert thin.status_code == 422
        assert "outline" in thin.json()["detail"].lower()

        missing_blocks = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(blocks=[]),
            },
        )
        assert missing_blocks.status_code == 422
        assert "block" in missing_blocks.json()["detail"].lower()

        off_scope = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(blocks=[_block("blk_s", "socratic", target_synthesis="No")]),
                "allowed_block_types": ["topic_goal"],
            },
        )
        assert off_scope.status_code == 422
        assert "allowed" in off_scope.json()["detail"].lower()

        full = client.post(
            f"/kc/nodes/{river['id']}/model-turn",
            json={
                "message": "Draft this component.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(),
                "allowed_block_types": ["topic_goal"],
            },
        )
        assert full.status_code == 200, full.text
        draft = full.json()["draft"]
        assert draft["description"] == "The river is blue."
        assert draft["outline"] == "How the river looks."
        assert "topics" not in draft
        assert "kc_type" not in draft
        assert "type_fields" not in draft
        assert draft["blocks"] == [_block("blk_color", "topic_goal", topic="color", goal="Recall the color")]
        assert draft["rubric"] == ["Recall the color"]
        assert draft["misconceptions"][0]["broken_kc"] == "zz-fields-b"
        assert draft["prerequisite_codes"] == ["zz-fields-b"]
        assert "Recommend" not in full.json()["messages"][-1]["content"]
        assert "Description:" in full.json()["messages"][-1]["content"]

        written = client.post(f"/kc/nodes/{river['id']}/push", json=draft)
        assert written.status_code == 200, written.text
        assert written.json()["description"] == "The river is blue."
        assert written.json()["outline"] == "How the river looks."
        assert written.json()["blocks"] == draft["blocks"]
        assert written.json()["rubric"] == ["Recall the color"]
        assert written.json()["core_truth"] == "The river in this course is blue."
        assert written.json()["prerequisite_codes"] == ["zz-fields-b"]
        other = client.get(f"/kc/nodes/{pushed[1]['id']}").json()
        assert other["title"] == "Other"
        assert other["kc_type"] is None
    finally:
        _wipe_zz()


def test_push_keeps_every_block_from_the_model_reply() -> None:
    blocks = [
        _block("blk_1", "topic_goal", topic="color", goal="Recall the color"),
        _block("blk_2", "topic_goal", topic="banks", goal="Name a bank"),
        _block("blk_3", "retrieval_check", recall_prompt="What color?", expected_fact="The river is blue."),
        _block(
            "blk_4",
            "curiosity",
            phenomenon_hook="A blue river",
            prediction_question="Why blue?",
            bridge_to_unit="Light scatters.",
        ),
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
                    blocks=blocks,
                    prerequisite_codes=["zz-pairs-b"],
                    misconceptions=[{"wrong_move": "The river is red", "broken_kc": "zz-pairs-b"}],
                ),
                "allowed_block_types": ["topic_goal", "retrieval_check", "curiosity"],
            },
        )
        assert full.status_code == 200, full.text
        draft = full.json()["draft"]
        assert draft["blocks"] == blocks
        assert "topics" not in draft

        written = client.post(f"/kc/nodes/{river['id']}/push", json=draft)
        assert written.status_code == 200, written.text
        assert written.json()["blocks"] == blocks
        assert written.json()["rubric"] == [
            "Recall the color",
            "Name a bank",
            "The river is blue.",
        ]
        stored = client.get(f"/kc/nodes/{river['id']}").json()
        assert stored["blocks"] == blocks
        assert len(stored["blocks"]) == 4
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
        opened = client.post(
            f"/kc/nodes/{node_id}/model-turn",
            json={
                "message": "Draft this fact.",
                "discussion": _model_fields()["discussion"],
                "draft": _model_fields(misconceptions=[], prerequisite_codes=[]),
            },
        )
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
        assert layers[:3] == ["Safety", "Safety", "Layer 1, Component"]
        assert blank["Safety text"].startswith("Safety\n")
        assert blank["Latest safety flag"] == "none"
        assert "Layer 7, Feedback loop" in layers
        for name in (
            "Course title",
            "Course description",
            "Audience",
            "Kind",
            "Minutes",
            "Component title",
            "Component code",
            "Outline",
            "Core truth",
            "Derived rubric",
            "Misconceptions",
            "Prerequisite codes",
            "Encompass codes",
            "Prerequisite status",
            "Block index",
            "Block type",
            "Substep",
            "Choice on screen",
            "Display name",
            "Age",
            "Grade band",
            "Reading level",
            "Response length",
            "Expression style",
            "Explanation style",
            "Challenge appetite",
            "Communication tone",
            "Learning support",
            "Interest tags",
            "Interests",
            "Attempts",
            "Last answer",
            "Last misconception",
            "Minutes used",
            "Support band",
            "Affect",
            "Last four messages",
            "Eliminated choices",
            "Finished blocks",
        ):
            assert blank[name] == ""
        assert blank["Persona"]
        assert blank["Vocabulary register"]
        assert blank["Interest weaving"] in {
            "subtle_natural (Subtle & natural (Hook or 1 example when it fits naturally))",
            "frequent_thematic (Frequent thematic (Frame scenarios around child interests))",
            "off (Off (Neutral curriculum examples or fallback metaphor domain))",
        }
        assert blank["Humor and wit"]
        assert blank["Effective analogy source"] in {"child_interests", "fallback_metaphors"}
        assert blank["Effective vocabulary rule"]
        assert blank["Effective humor rule"]
        assert blank["Orient framing"] == "elaborate_outline"
        assert blank["Instructional stance"] == "guided_discovery"
        assert blank["Scaffolding escalation"] == "progressive_nudge_then_scaffold"
        assert blank["Stay on course"] == "brief_answer_then_return"
        assert blank["Misconception policy"] == "explain_and_retry_once"
        assert blank["Prerequisite support policy"] == "inline_micro_recap"
        assert blank["Encouragement style"] == "process_praise"
        assert blank["Close summary depth"] == "diagnostic_strengths_and_gaps"
        assert blank["Close component"] == "no"
        assert blank["Close course"] == "no"
        for retired in (
            "Type",
            "Type fields",
            "Component description",
            "Move index",
            "Move name",
            "Evidence",
            "Choice widget",
            "Move content",
            "Lexicon",
            "Use interests",
            "Instructive",
            "Struggle window",
            "Effective struggle window",
            "Anti-spoiler",
            "One question",
            "Enrichment",
            "Effective enrichment",
            "Growth-mindset praise",
            "Self-explanation",
            "Asks why",
            "Stability",
            "Score",
            "Status",
            "Recipe",
            "Voice override",
            "Tutor persona",
        ):
            assert retired not in blank

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
        assert picked["Grade band"] == "upper_elementary"
        assert picked["Reading level"] in {"early_fluent", "on_grade", "emerging", "advanced"}
        assert picked["Response length"] == "balanced"
        assert picked["Expression style"] == "short_phrases"
        assert picked["Explanation style"] == "story_and_analogy"
        assert picked["Challenge appetite"] == "steady"
        assert picked["Communication tone"] == "warm_and_encouraging"
        assert picked["Learning support"] == "none"
        assert picked["Component title"] == ""
        assert picked["Block index"] == ""
        assert picked["Outline"] == ""
        assert picked["Redirect pending"] == "no"
        assert "Type fields" not in picked
        assert "Move index" not in picked

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
        assert live["Outline"] == "How River fact works."
        assert live["Core truth"] == "Truth for River fact."
        assert live["Derived rubric"] == "Explain River fact."
        assert "Type" not in live
        assert "Type fields" not in live
        assert "Component description" not in live
        assert live["Misconceptions"] == "The river is red. -> zz-vars-other"
        assert live["Prerequisite codes"] == "zz-vars-other"
        assert live["Encompass codes"] == ""
        assert live["Block index"] == "1 of 1"
        assert live["Block type"] == "topic_goal (Topic / Goal)"
        assert live["Substep"] == "explain"
        assert live["Choice on screen"] == "no"
        assert live["Topic"] == "River fact"
        assert live["Goal"] == "Explain River fact."
        assert live["Acceptance criteria"] == ""
        assert "Question stem" not in live
        assert live["Explanation depth"] == "3"
        assert live["Ask for a full sentence"] == "yes"
        assert "Retry attempts" not in live
        assert live["Support band"] == "hold"
        assert live["Redirect pending"] == "no"
        assert live["Close component"] == "no"
        assert live["Close course"] == "no"
        assert live["Finished blocks"] == ""
        assert "weather" in live["Interests"]

        client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "The outline is clear."},
        )
        held = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={"reply": "The outline is clear.", "decision": "advance"},
        )
        assert held.status_code == 200, held.text
        assert held.json()["passed"] is False
        _open_goal(session_id)
        client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "Explain the river fact."},
        )
        summary = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={
                "reply": "Summary check.",
                "decision": "stay",
                "substep_passed": True,
                "rubric_met": ["fact"],
            },
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["active_substep"] == "summary_check"
        done = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={
                "reply": "Yes. Truth for River fact. This unit is complete.",
                "decision": "complete",
                "block_complete": True,
                "rubric_met": ["fact"],
            },
        )
        assert done.status_code == 200, done.text
        after = _variable_map(client.get("/kc/tutor/variables", params={"session_id": session_id}))
        assert after["Block index"] == "1 of 1"
        assert after["Block type"] == "topic_goal (Topic / Goal)"
        assert after["Close component"] == "yes"
        assert after["Close course"] == "no"
        assert "Score" not in after
        assert "Status" not in after
        assert "passed after" in after["Finished blocks"]
        assert after["Redirect pending"] == "no"
        assert client.get("/kc/tutor/variables", params={"session_id": str(uuid.uuid4())}).status_code == 404
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


LAYER_REVISION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "021_kc_seven_layer.py"


def test_tutor_variables_follow_the_active_block() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    patched = client.patch(
        f"/students/{storm.id}",
        json={
            "age": 12,
            "grade_band": "middle_school",
            "reading_level": "advanced",
            "response_length": "bite_sized",
            "expression_style": "one_word_or_taps",
            "explanation_style": "visual_spatial",
            "challenge_appetite": "loves_a_challenge",
            "communication_tone": "playful_and_curious",
            "learning_support": "adhd_focus_friendly",
            "interest_tags": ["space_and_science", "video_games"],
            "interests": ["Minecraft redstone", "telescopes"],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["grade_band"] == "middle_school"
    assert patched.json()["reading_level"] == "advanced"
    assert patched.json()["response_length"] == "bite_sized"
    assert patched.json()["expression_style"] == "one_word_or_taps"
    assert patched.json()["explanation_style"] == "visual_spatial"
    assert patched.json()["challenge_appetite"] == "loves_a_challenge"
    assert patched.json()["communication_tone"] == "playful_and_curious"
    assert patched.json()["learning_support"] == "adhd_focus_friendly"
    assert patched.json()["interest_tags"] == ["space_and_science", "video_games"]
    course = _ready(
        _make("zz-varblock", title="Block variables"),
        [
            _spec(
                "zz-varblock-color",
                "Sky light",
                blocks=[
                    {
                        "id": "topic",
                        "type": "topic_goal",
                        "data": {"topic": "Sky light", "goal": "The sky sends blue light."},
                    },
                    {
                        "id": "quiz",
                        "type": "mcq",
                        "data": {
                            "mode": "static",
                            "question_stem": "What sends the blue light?",
                            "choices": [
                                {"id": "a", "text": "The sky", "is_correct": True},
                                {"id": "b", "text": "The mud", "is_correct": False},
                            ],
                            "correct_explanation": "The sky sends blue light.",
                        },
                    },
                ],
            )
        ],
    )
    try:
        opened = client.post(
            "/kc/tutor/sessions",
            json={
                "student_id": str(storm.id),
                "course_id": course["id"],
                "kc_id": _node(course, "zz-varblock-color")["id"],
            },
        )
        assert opened.status_code == 200, opened.text
        session_id = opened.json()["id"]
        topic = _variable_map(client.get("/kc/tutor/variables", params={"session_id": session_id}))
        assert topic["Grade band"] == "middle_school"
        assert topic["Reading level"] == "advanced"
        assert topic["Response length"] == "bite_sized"
        assert topic["Expression style"] == "one_word_or_taps"
        assert topic["Explanation style"] == "visual_spatial"
        assert topic["Challenge appetite"] == "loves_a_challenge"
        assert topic["Communication tone"] == "playful_and_curious"
        assert topic["Learning support"] == "adhd_focus_friendly"
        assert topic["Interest tags"] == "space_and_science, video_games"
        assert "Minecraft redstone" in topic["Interests"]
        prompt_text = client.get(f"/kc/tutor/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "Middle school (Grades 6-8)" in prompt_text
        assert "bite-sized" in prompt_text
        assert "one-word replies or taps" in prompt_text
        assert "visual-spatial framing" in prompt_text
        assert "loves a challenge" in prompt_text
        assert "playful and curious" in prompt_text
        assert "ADHD focus-friendly" in prompt_text
        assert "Space & science" in prompt_text
        assert "Video games" in prompt_text
        assert "Minecraft redstone" in prompt_text
        assert topic["Block index"] == "1 of 2"
        assert topic["Block type"] == "topic_goal (Topic / Goal)"
        assert topic["Substep"] == "explain"
        assert topic["Choice on screen"] == "no"
        assert topic["Topic"] == "Sky light"
        assert topic["Goal"] == "The sky sends blue light."
        assert "Question stem" not in topic
        assert topic["Explanation depth"] == "3"
        assert "Retry attempts" not in topic
        assert topic["Close component"] == "no"

        moved = _finish_block(
            session_id,
            "The sky sends blue light.",
            reply="Next is the choice.",
        )
        assert moved["step"] == 1
        quiz = _variable_map(client.get("/kc/tutor/variables", params={"session_id": session_id}))
        assert quiz["Block index"] == "2 of 2"
        assert quiz["Block type"] == "mcq (Multiple Choice Question)"
        assert quiz["Substep"] == "choice"
        assert quiz["Choice on screen"] == "yes"
        assert quiz["Question stem"] == "What sends the blue light?"
        assert "The sky" in quiz["Choices"]
        assert "The mud" in quiz["Choices"]
        assert "Topic" not in quiz
        assert "Explanation depth" not in quiz
        assert quiz["Retry attempts"] == "2"
        assert quiz["Disable eliminated choices"] == "yes"
        assert quiz["Close component"] == "no"
        assert "passed after" in quiz["Finished blocks"]
    finally:
        client.patch(
            f"/students/{storm.id}",
            json={
                "age": 10,
                "grade_band": "upper_elementary",
                "reading_level": "middle-grade",
                "response_length": "balanced",
                "expression_style": "short_phrases",
                "explanation_style": "story_and_analogy",
                "modality": "story",
                "challenge_appetite": "steady",
                "communication_tone": "warm_and_encouraging",
                "learning_support": "none",
                "interest_tags": [],
                "interests": ["weather", "leadership"],
            },
        )
        _clear_progress(storm.id)
        _wipe_zz()


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
        assert client.put(
            f"/kc/nodes/{second['id']}",
            json=_component("Second fact", core_truth="The rule is the contrast."),
        ).status_code == 200
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
        _open_goal(opened["id"])
        client.post(f"/kc/tutor/sessions/{opened['id']}/turn", json={"answer": "180"})
        held = client.post(
            f"/kc/tutor/sessions/{opened['id']}/decision",
            json={"reply": "Say the whole fact.", "decision": "complete", "rubric_met": ["fact"]},
        )
        assert held.status_code == 200, held.text
        assert held.json()["passed"] is False
        assert held.json()["status"] == "in_progress"
        assert held.json()["step_label"] == "Block 1 of 1: Topic / Goal"
        client.post(
            f"/kc/tutor/sessions/{opened['id']}/turn",
            json={"answer": "Truth for First fact is the whole line."},
        )
        summary = client.post(
            f"/kc/tutor/sessions/{opened['id']}/decision",
            json={
                "reply": "Summary check.",
                "decision": "stay",
                "substep_passed": True,
                "rubric_met": ["restatement"],
            },
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["active_substep"] == "summary_check"
        finished = client.post(
            f"/kc/tutor/sessions/{opened['id']}/decision",
            json={
                "reply": "This unit is complete. You can state the fact.",
                "decision": "complete",
                "block_complete": True,
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
        assert "How Second fact works." in other_prompt
        _open_goal(other["id"])
        client.post(f"/kc/tutor/sessions/{other['id']}/turn", json={"answer": "The outline is clear."})
        stepped = client.post(
            f"/kc/tutor/sessions/{other['id']}/decision",
            json={"reply": "Stay with this step.", "decision": "advance", "rubric_met": []},
        )
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["status"] == "in_progress"
        assert stepped.json()["passed"] is False
        assert stepped.json()["step_label"] == "Block 1 of 1: Topic / Goal"
        client.post(
            f"/kc/tutor/sessions/{other['id']}/turn",
            json={"answer": "Explain the second fact. The rule is the contrast."},
        )
        summary = client.post(
            f"/kc/tutor/sessions/{other['id']}/decision",
            json={
                "reply": "Summary check.",
                "decision": "stay",
                "substep_passed": True,
                "rubric_met": ["transfer"],
            },
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["active_substep"] == "summary_check"
        outro = client.post(
            f"/kc/tutor/sessions/{other['id']}/decision",
            json={
                "reply": "This unit is complete. The course is complete.",
                "decision": "complete",
                "block_complete": True,
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
                outline=None,
                core_truth="Spread-out objects float.",
                rubric=["Say why shape matters", "Say why density matters", "States the rule"],
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
        assert opened.json()["step_label"] == "Block 1 of 1: Topic / Goal"
        prompt = client.get(f"/kc/tutor/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "A principle about floating." in prompt
        assert "density" not in prompt
        assert "Spread-out objects float" not in prompt
        assert "Boats and cubes in a harbor." not in prompt

        posted = client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "The outline is clear."},
        )
        assert posted.status_code == 200, posted.text
        stepped = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={"reply": "Stay with this step.", "decision": "advance", "rubric_met": []},
        )
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["step_label"] == "Block 1 of 1: Topic / Goal"
        topic_prompt = client.get(f"/kc/tutor/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "Topic / Goal" in topic_prompt
        assert "Explain Floating." in topic_prompt
        assert "The child will type." in topic_prompt
        _open_goal(session_id)
        client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "I can explain floating."},
        )
        summary = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={
                "reply": "Summary check.",
                "decision": "stay",
                "substep_passed": True,
                "rubric_met": ["goal-1", "goal-2"],
            },
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["active_substep"] == "summary_check"
        finished = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={
                "reply": "You can explain why floating works. Practice the next shape.",
                "decision": "complete",
                "block_complete": True,
                "rubric_met": ["goal-1", "goal-2"],
                "score_justification": "Say why shape matters.",
                "what_was_strong": "Named the floating idea.",
                "what_to_work_on": "Try a new object.",
            },
        )
        assert finished.status_code == 200, finished.text
        assert finished.json()["passed"] is True
        assert finished.json()["unit_complete"] is True
        board = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert "course_score" not in board
        assert "score" not in board
        unit = next(item for item in board["units"] if item["code"] == "zz-result-float")
        result = unit["result"]
        assert result["status"] == "known"
        assert "blk-1" in result["rubric_met"]
        assert "goal-1" in result["rubric_met"]
        assert "Say why shape matters" in result["justification"]
        assert result["strong"]
        assert result["work_on"]
        assert "?" not in result["reply"]
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def _open_goal(session_id: str) -> None:
    """Leave the opening explanation so the next answer is the goal answer."""
    current = client.get(f"/kc/tutor/sessions/{session_id}")
    assert current.status_code == 200, current.text
    if current.json().get("active_substep") != "explain":
        return
    posted = client.post(
        f"/kc/tutor/sessions/{session_id}/turn",
        json={"answer": "Got it - move on"},
    )
    assert posted.status_code == 200, posted.text
    decided = client.post(
        f"/kc/tutor/sessions/{session_id}/decision",
        json={"reply": "What is the idea?", "decision": "stay", "rubric_met": []},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["active_substep"] == "main"


def _decide(session_id: str, answer: str, decision: str = "stay", reply: str = "Noted.", **extra: object) -> dict:
    # A goal answer is graded only after the learner leaves the opening explanation.
    if extra.get("substep_passed"):
        current = client.get(f"/kc/tutor/sessions/{session_id}")
        if current.status_code == 200 and current.json().get("active_substep") == "explain":
            _decide(session_id, "Got it - move on", reply="What is the idea?")
    posted = client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": answer})
    assert posted.status_code == 200, posted.text
    body = {"reply": reply, "decision": decision, "rubric_met": [], **extra}
    decided = client.post(f"/kc/tutor/sessions/{session_id}/decision", json=body)
    assert decided.status_code == 200, decided.text
    return decided.json()


def _finish_block(session_id: str, answer: str, reply: str = "Noted.", **extra: object) -> dict:
    """Pass the last task substep, then close the summary check."""
    landed = _decide(session_id, answer, reply="Summary check.", substep_passed=True, **extra)
    assert landed["active_substep"] == "summary_check", landed
    assert landed["unit_complete"] is False
    closing = {key: value for key, value in extra.items() if key != "substep_passed"}
    closing["block_complete"] = True
    return _decide(session_id, "move on", reply=reply, **closing)


def _assessments(session_id: str) -> list[dict]:
    db = SessionLocal()
    try:
        row = db.get(KcSession, uuid.UUID(session_id))
        assert row is not None
        return [dict(item) for item in (row.block_results or []) if isinstance(item, dict)]
    finally:
        db.close()


def test_topic_then_static_mcq_checks_the_answer_and_stores_assessments() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    original = client.get("/tutor-profile")
    assert original.status_code == 200, original.text
    course = _ready(
        _make("zz-loop", title="River course", description="A river and its color."),
        [
            _spec(
                "zz-loop-color",
                "River color",
                blocks=[
                    {
                        "id": "topic",
                        "type": "topic_goal",
                        "data": {
                            "topic": "River color",
                            "goal": "Explain the river color.",
                            "acceptance_criteria": "The river is blue.",
                        },
                    },
                    {
                        "id": "quiz",
                        "type": "mcq",
                        "data": {
                            "mode": "static",
                            "question_stem": "Which color is the river?",
                            "choices": [
                                {"id": "a", "text": "Blue water", "is_correct": True},
                                {"id": "b", "text": "Red water", "is_correct": False},
                                {"id": "c", "text": "Green water", "is_correct": False},
                            ],
                            "correct_explanation": "Blue water reflects the sky.",
                        },
                    },
                ],
            ),
            _spec(
                "zz-loop-why",
                "Why the color",
                blocks=[
                    {
                        "id": "topic",
                        "type": "topic_goal",
                        "data": {
                            "topic": "Sky light",
                            "goal": "Explain the sky light.",
                            "acceptance_criteria": "The sky sends blue light.",
                        },
                    },
                    {
                        "id": "quiz",
                        "type": "mcq",
                        "data": {
                            "mode": "static",
                            "question_stem": "What sends the blue light?",
                            "choices": [
                                {"id": "a", "text": "The sky", "is_correct": True},
                                {"id": "b", "text": "The mud", "is_correct": False},
                            ],
                            "correct_explanation": "The sky sends blue light.",
                        },
                    },
                ],
            ),
            _spec(
                "zz-loop-open",
                "Two topics",
                blocks=[
                    {
                        "id": "first",
                        "type": "topic_goal",
                        "data": {"topic": "First idea", "goal": "Explain the first idea."},
                    },
                    {
                        "id": "second",
                        "type": "topic_goal",
                        "data": {"topic": "Second idea", "goal": "Explain the second idea."},
                    },
                ],
            ),
            _spec(
                "zz-loop-dynamic",
                "Generated question",
                blocks=[
                    {
                        "id": "live",
                        "type": "mcq",
                        "data": {
                            "mode": "dynamic",
                            "target_skill": "Name the river color",
                            "distractor_guidance": "A color the river is not",
                        },
                    }
                ],
            ),
            _spec(
                "zz-loop-wonder",
                "A wonder",
                blocks=[
                    {
                        "id": "wonder",
                        "type": "curiosity",
                        "data": {
                            "phenomenon_hook": "Why is the river blue?",
                            "prediction_question": "Guess first.",
                            "bridge_to_unit": "The color comes from the sky.",
                        },
                    }
                ],
            ),
        ],
    )
    try:
        color = _node(course, "zz-loop-color")
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": color["id"]},
        )
        assert opened.status_code == 200, opened.text
        session_id = opened.json()["id"]
        assert opened.json()["choice"] is None
        assert opened.json()["step"] == 0
        progress = opened.json()["block_progress"]
        assert [item["status"] for item in progress] == ["active", "upcoming"]
        assert opened.json()["completed_blocks"] == 0
        prompt = client.get(f"/kc/tutor/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "River color" in prompt
        assert "Explain the river color." in prompt
        assert "The river is blue." in prompt
        assert "The unit is not finished." in prompt
        assert "Do not say this component is finished." in prompt

        ignored = _decide(
            session_id,
            "I do not know this yet.",
            decision="complete",
            reply="This component is finished.",
            block_complete=True,
            substep_passed=True,
        )
        assert ignored["passed"] is False
        assert ignored["unit_complete"] is False
        assert ignored["step"] == 0
        assert ignored["status"] == "in_progress"
        assert _assessments(session_id) == []

        advanced = _finish_block(
            session_id,
            "The river is blue.",
            decision="stay",
            reply="The river color is in place.",
        )
        assert advanced["passed"] is False
        assert advanced["step"] == 1
        assert advanced["status"] == "in_progress"
        assert advanced["needs_speech"] is True
        assert advanced["choice"] is None
        assert "?" not in advanced["reply"]
        assert advanced["messages"][-1]["role"] == "assistant"
        assert advanced["messages"][-1]["step"] == 0
        spoken_next = client.post(
            f"/kc/tutor/sessions/{session_id}/speech",
            json={"content": "Next we pick the river color."},
        )
        assert spoken_next.status_code == 200, spoken_next.text
        opened_next = spoken_next.json()
        assert opened_next["needs_speech"] is False
        assert opened_next["messages"][-1]["step"] == 1
        assert opened_next["messages"][-1]["content"] == "Next we pick the river color."
        assert opened_next["choice"]["prompt"] == "Which color is the river?"
        assert [item["text"] for item in opened_next["choice"]["choices"]] == [
            "Blue water",
            "Red water",
            "Green water",
        ]
        assert [item["status"] for item in advanced["block_progress"]] == ["completed", "active"]
        topic_done = _assessments(session_id)
        assert len(topic_done) == 1
        assert topic_done[0]["block_id"] == "topic"
        assert topic_done[0]["outcome"] == "passed"
        assert topic_done[0]["strong"]
        mcq_prompt = client.get(f"/kc/tutor/sessions/{session_id}/prompt").json()["system_prompt"]
        assert "Which color is the river?" in mcq_prompt
        assert "Blue water" in mcq_prompt
        assert "If the first pick is correct, move to the summary check." in mcq_prompt
        assert "River color: passed after" in mcq_prompt
        assert "Summary close:" in mcq_prompt
        assert "The unit is not finished." in mcq_prompt

        wrong = _decide(
            session_id,
            "Red water",
            decision="complete",
            reply="Look again.",
            block_complete=True,
        )
        assert wrong["passed"] is False
        assert wrong["unit_complete"] is False
        assert wrong["step"] == 1
        assert wrong["status"] == "in_progress"
        assert [item["status"] for item in wrong["block_progress"]] == ["completed", "active"]
        assert "Red water" not in [item["text"] for item in wrong["choice"]["choices"]]
        assert len(_assessments(session_id)) == 1

        retried = _decide(
            session_id,
            "Blue water",
            decision="complete",
            reply="Why is that the right color?",
            block_complete=True,
        )
        assert retried["passed"] is False
        assert retried["unit_complete"] is False
        assert retried["step"] == 1
        assert "Explain Why" in retried["step_label"]
        assert len(_assessments(session_id)) == 1
        finished = _finish_block(
            session_id,
            "Blue water reflects the sky.",
            decision="stay",
            reply="You can name the river color and pick it out. Practice the next river.",
            score_justification="Named the color and picked blue water.",
            what_was_strong="Named the color.",
            what_to_work_on="Practice the next river.",
        )
        assert finished["passed"] is True
        assert finished["unit_complete"] is True
        assert finished["status"] == "completed"
        assert "?" not in finished["reply"]
        assert [item["status"] for item in finished["block_progress"]] == ["completed", "completed"]
        both = _assessments(session_id)
        assert [item["block_id"] for item in both] == ["topic", "quiz"]
        assert [item["outcome"] for item in both] == ["passed", "passed"]
        state = _state(storm.id, "zz-loop-color")
        assert state is not None and state.status == "known"
        assert state.result["reply"] == finished["reply"]
        assert "?" not in state.result["reply"]

        switched = client.put(
            "/tutor-profile",
            json={
                **{key: value for key, value in original.json().items() if key != "updated_at"},
                "kc_tutor_config": {
                    "blocks": {"mcq": {"confirm_why_on_correct": "always"}},
                },
            },
        )
        assert switched.status_code == 200, switched.text
        why_node = _node(course, "zz-loop-why")
        why = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": why_node["id"]},
        ).json()
        _finish_block(why["id"], "The sky sends blue light.", reply="On to the choice.")
        why_prompt = client.get(f"/kc/tutor/sessions/{why['id']}/prompt").json()["system_prompt"]
        assert "A correct pick must include why that option is right before the summary check." in why_prompt
        assert "The unit is not finished." in why_prompt
        held = _decide(why["id"], "The sky", decision="complete", reply="Why does that option work?", block_complete=True)
        assert held["passed"] is False
        assert held["unit_complete"] is False
        assert held["step"] == 1
        assert "Explain Why" in held["step_label"]
        why_next = client.get(f"/kc/tutor/sessions/{why['id']}/prompt").json()["system_prompt"]
        assert "Summary close:" in why_next
        assert "The unit is not finished." in why_next
        closed = _finish_block(
            why["id"],
            "The sky sends blue light.",
            reply="You can explain the sky light and why that choice holds.",
        )
        assert closed["passed"] is True
        assert closed["status"] == "completed"
        assert _state(storm.id, "zz-loop-why").status == "known"

        client.put("/tutor-profile", json=original.json())
        open_node = _node(course, "zz-loop-open")
        partial = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": open_node["id"]},
        ).json()
        moved = _finish_block(
            partial["id"],
            "Explain the first idea.",
            reply="The first idea holds.",
        )
        assert moved["step"] == 1
        assert [item["status"] for item in moved["block_progress"]] == ["completed", "active"]
        db = SessionLocal()
        try:
            row = db.get(KcSession, uuid.UUID(partial["id"]))
            assert row is not None
            row.status = "completed"
            db.commit()
        finally:
            db.close()
        forced = client.get(f"/kc/tutor/sessions/{partial['id']}")
        assert forced.status_code == 200, forced.text
        assert [item["status"] for item in forced.json()["block_progress"]] == ["completed", "upcoming"]
        assert forced.json()["completed_blocks"] == 1

        dynamic_node = _node(course, "zz-loop-dynamic")
        dynamic = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": dynamic_node["id"]},
        ).json()
        assert dynamic["choice"] is None
        spoken = client.post(
            f"/kc/tutor/sessions/{dynamic['id']}/speech",
            json={
                "content": "Pick the river color.",
                "generated_mcq": {
                    "question_stem": "Pick the river color",
                    "choices": [
                        {"id": "a", "text": "Blue"},
                        {"id": "b", "text": "Red"},
                    ],
                    "correct_index": 0,
                },
            },
        )
        assert spoken.status_code == 200, spoken.text
        assert spoken.json()["choice"]["prompt"] == "Pick the river color"
        missed = _decide(dynamic["id"], "Red", decision="complete", reply="Try the other color.", block_complete=True)
        assert missed["passed"] is False
        assert missed["status"] == "in_progress"
        stored = client.get(f"/kc/sessions/{dynamic['id']}")
        assert stored.status_code == 200, stored.text
        picked_text = next(
            message["content"]
            for message in reversed(stored.json()["messages"])
            if message["role"] == "user"
        )
        assert picked_text.splitlines()[0] == "Red"
        assert "a. Blue" in picked_text
        assert "b. Red" in picked_text
        picked = _decide(dynamic["id"], "Blue", decision="complete", reply="Say why that color fits.", block_complete=True)
        assert picked["passed"] is False
        assert "Explain Why" in picked["step_label"]
        known = _finish_block(
            dynamic["id"],
            "Blue is the color of this river.",
            reply="You can name the river color now.",
        )
        assert known["passed"] is True
        assert known["status"] == "completed"
        assert _assessments(dynamic["id"])[0]["outcome"] == "passed"

        wonder_node = _node(course, "zz-loop-wonder")
        wonder = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": wonder_node["id"]},
        ).json()
        counted_off = _finish_block(
            wonder["id"],
            "I wonder why.",
            reply="Here is the wonder, and you can ask it again later.",
        )
        assert counted_off["passed"] is True
        assert _state(storm.id, "zz-loop-wonder").status == "known"

        counting = client.put(
            "/tutor-profile",
            json={
                **{key: value for key, value in original.json().items() if key != "updated_at"},
                "kc_tutor_config": {
                    "blocks": {
                        "curiosity": {
                            "counts_toward_mastery_score": True,
                            "max_wonder_turns": 1,
                        }
                    }
                },
            },
        )
        assert counting.status_code == 200, counting.text
        _clear_progress(storm.id)
        again = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": wonder_node["id"]},
        ).json()
        revealed = _decide(again["id"], "Nope", reply="The wonder stays open for another look.")
        assert revealed["passed"] is False
        assert revealed["unit_complete"] is False
        assert revealed["active_substep"] == "summary_check"
        revealed = _decide(again["id"], "move on anyway", reply="Moving on.", block_complete=True)
        assert revealed["passed"] is False
        assert revealed["unit_complete"] is True
        assert _state(storm.id, "zz-loop-wonder").status == "fragile"
        assert _assessments(again["id"])[0]["outcome"] == "revealed"
    finally:
        client.put("/tutor-profile", json=original.json())
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
            "zz-prog-fragile": "completed",
            "zz-prog-open": "in_progress",
            "zz-prog-closed": "completed",
            "zz-prog-known-open": "completed",
            "zz-prog-patch": "not_started",
        }
        mastery = {item["code"]: item["mastery"] for item in body["units"]}
        assert mastery["zz-prog-known"] == "known"
        assert mastery["zz-prog-fragile"] == "fragile"
        assert mastery["zz-prog-open"] == ""
        opened_unit = next(item for item in body["units"] if item["code"] == "zz-prog-open")
        assert opened_unit["finished_blocks"] == 0
        assert opened_unit["total_blocks"] == 1
        assert "Explain Open fact." in opened_unit["rubric"]
        known_unit = next(item for item in body["units"] if item["code"] == "zz-prog-known")
        assert "Explain Known fact." in known_unit["rubric"]
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

        db = SessionLocal()
        try:
            row = db.get(KcSession, uuid.UUID(opened.json()["id"]))
            assert row is not None
            assert row.status == "in_progress"
            row.block_results = [
                {
                    "id": "blk-1",
                    "block_id": "blk-1",
                    "outcome": "passed",
                    "attempts": 1,
                    "title": "Open fact",
                }
            ]
            db.commit()
        finally:
            db.close()
        left_open = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        left = {item["code"]: item for item in left_open["units"]}
        assert left["zz-prog-open"]["status"] == "completed"
        assert left["zz-prog-open"]["mastery"] == "known"
        assert left["zz-prog-open"]["finished_blocks"] == 1
        refused = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/decision",
            json={"reply": "This unit is complete.", "decision": "complete"},
        )
        assert refused.status_code == 422
        db = SessionLocal()
        try:
            row = db.get(KcSession, uuid.UUID(opened.json()["id"]))
            assert row is not None
            assert row.status == "completed"
            state = db.scalar(select(KcState).where(KcState.student_id == storm.id, KcState.kc_id == row.kc_id))
            assert state is not None
            assert state.status == "known"
            assert state.result["strong"]
            assert state.result["work_on"]
        finally:
            db.close()
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def _miss_until_revealed(session_id: str, **extra: object) -> dict:
    current = client.get(f"/kc/tutor/sessions/{session_id}").json()
    if current.get("active_substep") == "explain":
        opened = _decide(session_id, "Got it - move on", reply="What is the idea?")
        assert opened["active_substep"] == "main"
    revealed = {}
    for index in range(4):
        revealed = _decide(
            session_id,
            f"This reply number {index} misses the idea on purpose.",
            reply="The answer stays covered for now.",
            **extra,
        )
        if revealed.get("unit_complete"):
            return revealed
        if revealed.get("active_substep") == "summary_check":
            return _decide(session_id, "move on", reply="Moving on.", block_complete=True, **extra)
    raise AssertionError(revealed)


def test_fragile_finishes_the_course_without_becoming_known() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _ready(
        _make("zz-amber", title="zzz Amber handoff"),
        [
            _spec("zz-amber-gap", "Gap fact"),
            _spec("zz-amber-next", "Next fact", prerequisite_codes=["zz-amber-gap"]),
        ],
    )
    later = client.post(
        "/kc/courses",
        json={
            "code": "zz-next",
            "title": "zzzz Next handoff",
            "description": "The course that opens after a fragile finish.",
            "audience": "12-14",
            "kind": "mastery",
        },
    )
    assert later.status_code == 200, later.text
    _ready(later.json(), [_spec("zz-next-fact", "Next course fact")])
    try:
        gap = _node(course, "zz-amber-gap")
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": gap["id"]},
        )
        assert opened.status_code == 200, opened.text
        revealed = _miss_until_revealed(
            opened.json()["id"],
            what_was_strong="You stayed with the question.",
            what_to_work_on="Name the idea in your own words.",
            score_justification="A required block was revealed.",
        )
        assert revealed["unit_complete"] is True
        assert revealed["course_complete"] is False
        assert _state(storm.id, "zz-amber-gap").status == "fragile"

        board = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert board["course_complete"] is False
        assert board["next_course"] is None
        assert any(card["code"] == "zz-amber-next" for card in board["cards"])
        assert all(card["code"] != "zz-amber-gap" for card in board["cards"])
        nxt = _node(course, "zz-amber-next")
        follow = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": nxt["id"]},
        )
        assert follow.status_code == 200, follow.text
        assert _state(storm.id, "zz-amber-gap").status == "fragile"

        closed = _miss_until_revealed(follow.json()["id"])
        assert closed["unit_complete"] is True
        assert closed["course_complete"] is True
        assert _state(storm.id, "zz-amber-gap").status == "fragile"
        assert _state(storm.id, "zz-amber-next").status == "fragile"

        done = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert done["known"] == 0
        assert done["course_complete"] is True
        assert done["next_course"]["title"] == "zzzz Next handoff"
        assert done["cards"] == []
        gap_unit = next(item for item in done["units"] if item["code"] == "zz-amber-gap")
        assert gap_unit["mastery"] == "fragile"
        assert gap_unit["finished_blocks"] == 1
        assert gap_unit["blocks"][0]["type"] == "topic_goal"
        assert gap_unit["blocks"][0]["outcome"] == "revealed"
        assert gap_unit["blocks"][0]["attempts"] >= 1
        assert gap_unit["blocks"][0]["rubric"] == "Explain Gap fact."
        assert gap_unit["result"]["strong"] == "You stayed with the question."
        assert gap_unit["result"]["work_on"] == "Name the idea in your own words."
        assert gap_unit["result"]["justification"] == "A required block was revealed."
        assert "score" not in gap_unit
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_curiosity_adds_a_rubric_line_only_when_it_counts() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    original = client.get("/tutor-profile")
    assert original.status_code == 200, original.text
    course = _ready(
        _make("zz-wonder-line", title="ZZ wonder line"),
        [
            _spec(
                "zz-wonder-line-a",
                "Wonder",
                blocks=[
                    {
                        "id": "blk-c",
                        "type": "curiosity",
                        "data": {
                            "phenomenon_hook": "A quiet river",
                            "prediction_question": "Why is the river quiet?",
                            "bridge_to_unit": "Still water hides the current.",
                        },
                    }
                ],
            )
        ],
    )
    try:
        node = _node(course, "zz-wonder-line-a")
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": node["id"]},
        )
        assert opened.status_code == 200, opened.text
        quiet = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        block = next(item for item in quiet["units"] if item["code"] == "zz-wonder-line-a")["blocks"][0]
        assert block["status"] == "active"
        assert block["type"] == "curiosity"
        assert "outcome" not in block
        assert "rubric" not in block

        counting = client.put(
            "/tutor-profile",
            json={
                **{key: value for key, value in original.json().items() if key != "updated_at"},
                "kc_tutor_config": {"blocks": {"curiosity": {"counts_toward_mastery_score": True}}},
            },
        )
        assert counting.status_code == 200, counting.text
        counted = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        line = next(item for item in counted["units"] if item["code"] == "zz-wonder-line-a")["blocks"][0]
        assert line["rubric"] == "Still water hides the current."
        assert "outcome" not in line
    finally:
        client.put("/tutor-profile", json=original.json())
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



def _model_turn(node_id: str, draft: dict, allowed: list[str] | None = None):
    body: dict = {
        "message": "Draft this component.",
        "discussion": f"{_model_fields()['discussion']} MIX-LOG-SECRET",
        "draft": draft,
    }
    if allowed is not None:
        body["allowed_block_types"] = allowed
    return client.post(f"/kc/nodes/{node_id}/model-turn", json=body)


def test_creator_drafts_store_blocks_instead_of_synthesis_mixes() -> None:
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

        blocks = [
            _block("blk_1", "topic_goal", topic="color", goal="Recall the color"),
            _block(
                "blk_2",
                "spot_the_flaw",
                rookie_work="The river is red.",
                flaw_description="It is blue.",
                underlying_misconception="Color swap",
                corrected_version="The river is blue.",
            ),
        ]
        turned = _model_turn(
            river["id"],
            _model_fields(
                blocks=blocks,
                misconceptions=[{"wrong_move": "The river is red", "broken_kc": "zz-mix-b"}],
                prerequisite_codes=["zz-mix-b"],
            ),
            ["topic_goal", "spot_the_flaw"],
        )
        assert turned.status_code == 200, turned.text
        draft = turned.json()["draft"]
        assert "kc_type" not in draft
        assert "type_fields" not in draft
        assert draft["blocks"] == blocks
        assert draft["rubric"] == ["Recall the color", "The river is blue."]

        written = client.post(f"/kc/nodes/{river['id']}/push", json=draft)
        assert written.status_code == 200, written.text
        assert written.json()["blocks"] == blocks
        assert written.json()["rubric"] == ["Recall the color", "The river is blue."]
        assert "mixes" not in written.json()["type_fields"]

        refused = _model_turn(
            river["id"],
            {
                "description": "The river is blue.",
                "outline": "How the river looks.",
                "title": "River fact",
                "kc_type": "synthesis",
                "core_truth": "The river in this course is blue.",
                "rubric": ["States that the river is blue"],
                "misconceptions": [{"wrong_move": "The river is red", "broken_kc": "zz-mix-b"}],
                "prerequisite_codes": ["zz-mix-b"],
                "mix_a": "zz-mix-b",
                "mix_b": "zz-mix-c",
                "faulty_plan": "A rookie swaps the two earlier facts.",
            },
        )
        assert refused.status_code == 422
        assert "block" in refused.json()["detail"].lower()
    finally:
        _wipe_zz()


def test_a_block_draft_is_valid_without_mixes() -> None:
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

        empty = _model_turn(
            alone["id"],
            _model_fields(blocks=[_block("blk_1", "topic_goal", topic="color", goal="Recall the color")], misconceptions=[], prerequisite_codes=[]),
        )
        assert empty.status_code == 200, empty.text
        assert empty.json()["draft"]["blocks"][0]["type"] == "topic_goal"
        assert "type_fields" not in empty.json()["draft"]
        assert empty.json()["draft"]["misconceptions"] == []

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
        assert prompt.json()["schema"]["properties"]["misconceptions"]["items"]["properties"]["broken_kc"]["enum"] == [
            "zz-mixone-b"
        ]
        assert "Do not ask for two mixes." not in prompt.json()["system_prompt"]

        named = _model_turn(
            pair["zz-mixone-a"]["id"],
            _model_fields(
                blocks=[_block("blk_1", "topic_goal", topic="color", goal="Recall the color")],
                misconceptions=[{"wrong_move": "The river is red", "broken_kc": "zz-mixone-b"}],
                prerequisite_codes=["zz-mixone-b"],
            ),
        )
        assert named.status_code == 200, named.text
        assert named.json()["draft"]["blocks"][0]["data"]["goal"] == "Recall the color"
        assert named.json()["draft"]["misconceptions"] == [
            {"wrong_move": "The river is red", "broken_kc": "zz-mixone-b"}
        ]
        assert "type_fields" not in named.json()["draft"]
    finally:
        _wipe_zz()


def test_kc_progress_analytics_and_accomplishments_opportunities() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _ready(
        _make("zz-analytics", title="Analytics Course"),
        [
            _spec("zz-an-known", "Known Concept"),
            _spec("zz-an-fragile", "Fragile Concept", prerequisite_codes=["zz-an-known"]),
            _spec("zz-an-open", "Open Concept", prerequisite_codes=["zz-an-fragile"]),
        ],
    )
    try:
        known_node = _node(course, "zz-an-known")
        fragile_node = _node(course, "zz-an-fragile")
        open_node = _node(course, "zz-an-open")

        s_known = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": known_node["id"]},
        ).json()
        _finish_block(
            s_known["id"],
            "Explains known concept clearly.",
            reply="Great explanation.",
            block_complete=True,
            what_was_strong="Explained the core mechanism on the first try.",
            what_to_work_on="Keep applying this rule.",
            score_justification="Passed every counting block on the first try.",
        )

        s_fragile = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": fragile_node["id"]},
        ).json()
        _miss_until_revealed(
            s_fragile["id"],
            what_was_strong="Stayed engaged through the hints.",
            what_to_work_on="Practice stating the rule without a prompt.",
            score_justification="Required a reveal after max retries.",
        )

        client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": open_node["id"]},
        )

        courses_resp = client.get(
            "/kc/tutor/courses",
            params={"student_id": str(storm.id)},
        )
        assert courses_resp.status_code == 200, courses_resp.text
        tile = next(item for item in courses_resp.json() if item["code"] == "zz-analytics")
        assert tile["component_count"] == 3
        assert tile["completed_count"] == 2
        assert tile["known_count"] == 1
        assert tile["fragile_count"] == 1
        assert tile["in_progress_count"] == 1
        assert tile["not_started_count"] == 0
        assert tile["total_blocks_count"] == 3
        assert tile["completed_blocks_count"] == 2
        assert tile["first_try_pass_count"] == 1
        assert tile["stars"] == 90
        assert tile["star_block"] == 20
        assert tile["star_first_try"] == 5
        assert tile["star_topic"] == 50
        assert tile["star_crown"] == 15
        assert tile["started"] is True
        assert tile["course_complete"] is False
        assert tile["last_active_at"] is not None
        assert len(tile["accomplishments_preview"]) >= 1
        assert len(tile["opportunities_preview"]) >= 1

        detail = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert detail["total_blocks_count"] == 3
        assert detail["completed_blocks_count"] == 2
        assert detail["first_try_pass_count"] == 1
        assert detail["stars"] == 90
        assert detail["last_active_at"] is not None
        assert any(a["kind"] == "strength" for a in detail["accomplishments"])
        assert any(a["kind"] == "mastered" for a in detail["accomplishments"])
        assert any(o["kind"] == "weakness" for o in detail["opportunities"])
        assert any(o["kind"] == "revealed_block" for o in detail["opportunities"])
        assert any(o["kind"] == "in_progress" for o in detail["opportunities"])

        units_by_code = {u["code"]: u for u in detail["units"]}
        ku = units_by_code["zz-an-known"]
        assert ku["child_status"] == "Mastered"
        assert ku["practice_bonus"] is False
        assert ku["dependent_codes"] == ["zz-an-fragile"]
        assert ku["passed_blocks_count"] == 1
        assert ku["first_try_blocks_count"] == 1
        assert ku["block_details"][0]["passed_on_first_try"] is True
        assert ku["block_details"][0]["outcome"] == "passed"
        assert ku["what_was_strong"] == "Explained the core mechanism on the first try."

        fu = units_by_code["zz-an-fragile"]
        assert fu["child_status"] == "Completed"
        assert "fragile" not in fu["child_status"].lower()
        assert fu["practice_bonus"] is True
        assert fu["prerequisite_codes"] == ["zz-an-known"]
        assert fu["dependent_codes"] == ["zz-an-open"]
        assert fu["revealed_blocks_count"] == 1
        assert fu["block_details"][0]["outcome"] == "revealed"
        assert fu["what_to_work_on"] == "Practice stating the rule without a prompt."
        assert units_by_code["zz-an-open"]["child_status"] == "In Progress"
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_multi_tutor_profiles_catalog_and_student_session_resolution() -> None:
    from app.tutor_profile import AVATAR_PRESET_CATEGORIES, AVATAR_PRESETS

    assert len(AVATAR_PRESET_CATEGORIES) == 8
    assert all(len(group) == 8 for group in AVATAR_PRESET_CATEGORIES.values())
    assert len(AVATAR_PRESETS) == 64
    assert AVATAR_PRESETS[0] == "default_circle"

    storm = _storm()
    _clear_progress(storm.id)
    course = _make("zz-multi-tutor", title="ZZ Multi Tutor", description="Tutor switching check.")
    created_ids: list[str] = []
    try:
        listed = client.get("/tutor-profiles")
        assert listed.status_code == 200, listed.text
        profiles = listed.json()
        assert len(profiles) >= 1
        default_prof = profiles[0]
        assert default_prof["id"] == "default"
        assert default_prof["name"] == "Default"
        assert default_prof["slug"] == "default"
        assert default_prof["is_default"] is True
        assert default_prof["avatar_preset"] == "default_circle"

        # Default profile cannot be deleted
        del_def = client.delete("/tutor-profiles/default")
        assert del_def.status_code == 400

        # Invalid avatar preset is rejected
        bad_avatar = client.post(
            "/tutor-profiles",
            json={"name": "Invalid Avatar", "avatar_preset": "not_in_64"},
        )
        assert bad_avatar.status_code == 422

        # Create a custom tutor profile
        athena_resp = client.post(
            "/tutor-profiles",
            json={
                "name": "Professor Athena",
                "description": "Calm Socratic owl mentor who probes reasoning with precision.",
                "avatar_preset": "owl",
                "persona": "socratic_mentor",
                "vocabulary_register": "academic_precision",
                "humor_and_wit": "none_straightforward",
                "metaphors": "nature",
                "sidekick": "barnaby",
            },
        )
        assert athena_resp.status_code == 200, athena_resp.text
        athena = athena_resp.json()
        created_ids.append(athena["id"])
        assert athena["id"] == "professor-athena"
        assert athena["slug"] == "professor-athena"
        assert athena["is_default"] is False
        assert athena["avatar_preset"] == "owl"
        assert athena["persona"] == "socratic_mentor"
        assert athena["vocabulary_register"] == "academic_precision"

        # Clone from Professor Athena
        clone_resp = client.post(
            "/tutor-profiles",
            json={
                "name": "Professor Athena",
                "description": "Cloned cosmic owl mentor.",
                "avatar_preset": "telescope",
                "source_profile_id": athena["id"],
            },
        )
        assert clone_resp.status_code == 200, clone_resp.text
        cloned = clone_resp.json()
        created_ids.append(cloned["id"])
        assert cloned["slug"] == "professor-athena-2"
        assert cloned["persona"] == "socratic_mentor"
        assert cloned["vocabulary_register"] == "academic_precision"
        assert cloned["avatar_preset"] == "telescope"

        # Assign Professor Athena to Storm
        assign_resp = client.put(
            f"/students/{storm.id}/tutor-profile",
            json={"tutor_profile_id": athena["id"]},
        )
        assert assign_resp.status_code == 200, assign_resp.text
        assert assign_resp.json()["preferred_tutor_profile_id"] == athena["id"]

        pushed = client.post(
            f"/kc/courses/{course['id']}/push",
            json={"components": [{"code": "zz-mt-fact", "title": "Athena fact"}]},
        ).json()["components"][0]
        assert client.put(f"/kc/nodes/{pushed['id']}", json=_component("Athena fact")).status_code == 200
        assert client.post(f"/kc/courses/{course['id']}/ready").status_code == 200

        sess_resp = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": pushed["id"]},
        )
        assert sess_resp.status_code == 200, sess_resp.text
        sess = sess_resp.json()
        assert sess["tutor_profile_id"] == athena["id"]
        assert sess["tutor_name"] == "Professor Athena"
        assert sess["avatar_preset"] == "owl"

        vars_resp = client.get("/kc/tutor/variables", params={"session_id": sess["id"]})
        assert vars_resp.status_code == 200, vars_resp.text
        vars_json = vars_resp.json()
        assert vars_json["tutor_profile_id"] == athena["id"]
        assert vars_json["tutor_name"] == "Professor Athena"
        assert vars_json["avatar_preset"] == "owl"
        vmap = _variable_map(vars_resp)
        assert vmap["Tutor profile"] == "Professor Athena (professor-athena)"
        assert vmap["Tutor avatar"] == "owl"
        assert "socratic_mentor" in vmap["Persona"]

        prompt_resp = client.get(f"/kc/tutor/sessions/{sess['id']}/prompt")
        assert prompt_resp.status_code == 200, prompt_resp.text
        assert "Active tutor profile (Professor Athena): Calm Socratic owl mentor" in prompt_resp.json()["system_prompt"]

        # Switching student's active tutor updates the open session immediately
        switch_resp = client.put(
            f"/students/{storm.id}/tutor-profile",
            json={"tutor_profile_id": cloned["id"]},
        )
        assert switch_resp.status_code == 200
        reloaded = client.get(f"/kc/tutor/sessions/{sess['id']}").json()
        assert reloaded["tutor_profile_id"] == cloned["id"]
        assert reloaded["avatar_preset"] == "telescope"

        # Resetting a custom tutor profile restores default Layer 3/4 settings while keeping its name
        reset_resp = client.post(f"/tutor-profiles/{cloned['id']}/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json()["name"] == "Professor Athena"
        assert reset_resp.json()["persona"] == "coach"

        # Deleting the custom tutor clears student and session references back to default
        del_resp = client.delete(f"/tutor-profiles/{cloned['id']}")
        assert del_resp.status_code == 200
        created_ids.remove(cloned["id"])
        fallback_sess = client.get(f"/kc/tutor/sessions/{sess['id']}").json()
        assert fallback_sess["tutor_profile_id"] == "default"
        assert fallback_sess["tutor_name"] == "Default"
    finally:
        client.put(f"/students/{storm.id}/tutor-profile", json={"tutor_profile_id": None})
        for pid in created_ids:
            client.delete(f"/tutor-profiles/{pid}")
        _clear_progress(storm.id)
        _wipe_zz()


def test_child_avatar_stars_and_per_course_tutor() -> None:
    from app.learn_stars import child_status_label, explorer_progress, stars_from_units

    assert child_status_label("completed", "known") == "Mastered"
    assert child_status_label("completed", "fragile") == "Completed"
    assert "fragile" not in child_status_label("completed", "fragile").lower()
    assert child_status_label("in_progress", "") == "In Progress"
    assert child_status_label("not_started", "", locked=True) == "Locked"
    rolled = stars_from_units(
        [
            {
                "patch": False,
                "status": "completed",
                "mastery": "known",
                "completed_blocks": 2,
                "first_try_blocks_count": 1,
                "revealed_blocks_count": 0,
            },
            {
                "patch": False,
                "status": "completed",
                "mastery": "fragile",
                "completed_blocks": 1,
                "first_try_blocks_count": 0,
                "revealed_blocks_count": 1,
            },
            {
                "patch": True,
                "status": "completed",
                "mastery": "known",
                "completed_blocks": 9,
                "first_try_blocks_count": 9,
                "revealed_blocks_count": 0,
            },
        ]
    )
    assert rolled["stars"] == 100
    assert explorer_progress(0)["explorer_rank"] == "Curious Spark"
    assert explorer_progress(74)["explorer_level"] == 1
    assert explorer_progress(75)["explorer_rank"] == "Concept Builder"
    assert explorer_progress(600)["explorer_rank"] == "Grand Scholar"
    assert explorer_progress(600)["explorer_next"] is None

    storm = _storm()
    _clear_progress(storm.id)
    created_ids: list[str] = []
    course_a = _ready(
        _make("zz-learn-a", title="Fractions Quest", description="Share fairly."),
        [_spec("zz-learn-a1", "Halves"), _spec("zz-learn-a2", "Thirds")],
    )
    try:
        avatar = client.patch(
            f"/students/{storm.id}",
            json={"child_profile": {"avatar_preset": "fox"}},
        )
        assert avatar.status_code == 200, avatar.text
        assert avatar.json()["child_profile"]["avatar_preset"] == "fox"
        invalid = client.patch(
            f"/students/{storm.id}",
            json={"child_profile": {"avatar_preset": "not_a_real_icon"}},
        )
        assert invalid.status_code == 200, invalid.text
        assert invalid.json()["child_profile"]["avatar_preset"] == ""

        owl = client.post(
            "/tutor-profiles",
            json={"name": "Coach Owl", "description": "A calm owl.", "avatar_preset": "owl"},
        )
        assert owl.status_code == 200, owl.text
        fox = client.post(
            "/tutor-profiles",
            json={"name": "Coach Fox", "description": "A playful fox.", "avatar_preset": "fox"},
        )
        assert fox.status_code == 200, fox.text
        created_ids.extend([owl.json()["id"], fox.json()["id"]])

        started = client.post(
            "/kc/tutor/start",
            json={
                "student_id": str(storm.id),
                "course_id": course_a["id"],
                "tutor_profile_id": owl.json()["id"],
            },
        )
        assert started.status_code == 200, started.text
        assert started.json()["tutor_profile_id"] == owl.json()["id"]

        course_b = client.post(
            "/kc/courses",
            json={
                "code": "zz-learn-b",
                "title": "Decimal Quest",
                "description": "Tenths and hundredths.",
                "audience": "12-14",
                "kind": "mastery",
            },
        )
        assert course_b.status_code == 200, course_b.text
        course_b = _ready(course_b.json(), [_spec("zz-learn-b1", "Tenths")])
        started_b = client.post(
            "/kc/tutor/start",
            json={
                "student_id": str(storm.id),
                "course_id": course_b["id"],
                "tutor_profile_id": fox.json()["id"],
            },
        )
        assert started_b.status_code == 200, started_b.text
        assert started_b.json()["tutor_profile_id"] == fox.json()["id"]

        listed = client.get("/kc/tutor/courses", params={"student_id": str(storm.id)}).json()
        by_code = {item["code"]: item for item in listed}
        assert by_code["zz-learn-a"]["tutor"]["id"] == owl.json()["id"]
        assert by_code["zz-learn-a"]["tutor"]["source"] == "course"
        assert by_code["zz-learn-a"]["started"] is True
        assert by_code["zz-learn-b"]["tutor"]["id"] == fox.json()["id"]
        assert by_code["zz-learn-b"]["tutor"]["source"] == "course"

        lynx = client.post(
            "/tutor-profiles",
            json={"name": "Coach Lynx", "description": "A steady guide.", "avatar_preset": "badger"},
        )
        assert lynx.status_code == 200, lynx.text
        created_ids.append(lynx.json()["id"])
        switched_a = client.post(
            f"/kc/tutor/courses/{course_a['id']}/tutor",
            json={"student_id": str(storm.id), "tutor_profile_id": lynx.json()["id"]},
        )
        assert switched_a.status_code == 200, switched_a.text
        listed = client.get("/kc/tutor/courses", params={"student_id": str(storm.id)}).json()
        by_code = {item["code"]: item for item in listed}
        assert by_code["zz-learn-a"]["tutor"]["id"] == lynx.json()["id"]
        assert by_code["zz-learn-b"]["tutor"]["id"] == fox.json()["id"]

        db = SessionLocal()
        try:
            row = db.get(Student, storm.id)
            assert row is not None
            row.preferred_tutor_profile_id = fox.json()["id"]
            db.commit()
        finally:
            db.close()

        topic_two = _node(course_a, "zz-learn-a2")
        resumed = client.post(
            "/kc/tutor/start",
            json={"student_id": str(storm.id), "course_id": course_a["id"], "kc_id": topic_two["id"]},
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["tutor_profile_id"] == lynx.json()["id"]
        preferred = next(item for item in client.get("/students").json() if item["id"] == str(storm.id))
        assert preferred["preferred_tutor_profile_id"] == fox.json()["id"]

        changed = client.post(
            f"/kc/tutor/courses/{course_b['id']}/tutor",
            json={"student_id": str(storm.id), "tutor_profile_id": owl.json()["id"]},
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["id"] == owl.json()["id"]
        listed = client.get("/kc/tutor/courses", params={"student_id": str(storm.id)}).json()
        by_code = {item["code"]: item for item in listed}
        assert by_code["zz-learn-b"]["tutor"]["id"] == owl.json()["id"]
        assert by_code["zz-learn-a"]["tutor"]["id"] == lynx.json()["id"]
        reloaded_b = client.get(f"/kc/tutor/sessions/{started_b.json()['id']}").json()
        assert reloaded_b["tutor_profile_id"] == owl.json()["id"]
        reloaded_a = client.get(f"/kc/tutor/sessions/{started.json()['id']}").json()
        assert reloaded_a["tutor_profile_id"] == lynx.json()["id"]

        missing = client.post(
            "/kc/tutor/start",
            json={
                "student_id": str(storm.id),
                "course_id": course_a["id"],
                "tutor_profile_id": "missing-tutor",
            },
        )
        assert missing.status_code == 404

        roster = client.get("/kc/tutor/learners")
        assert roster.status_code == 200, roster.text
        mine = next(item for item in roster.json() if item["student"]["id"] == str(storm.id))
        assert mine["in_progress_course_count"] >= 1
        assert mine["explorer_rank"] == "Curious Spark"
        assert mine["student"]["child_profile"]["avatar_preset"] == ""
    finally:
        client.patch(f"/students/{storm.id}", json={"child_profile": {"avatar_preset": ""}})
        client.put(f"/students/{storm.id}/tutor-profile", json={"tutor_profile_id": None})
        for pid in created_ids:
            client.delete(f"/tutor-profiles/{pid}")
        _clear_progress(storm.id)
        _wipe_zz()


def test_word_overlap_does_not_finish_a_block_the_model_kept_open() -> None:
    from app.kc_loop import resolve_block_turn
    from app.models import default_kc_tutor_config

    blocks = [
        {
            "id": "topic",
            "type": "topic_goal",
            "data": {
                "topic": "River color",
                "goal": "The river is blue.",
                "acceptance_criteria": "The river is blue.",
            },
        },
        {
            "id": "quiz",
            "type": "mcq",
            "data": {"mode": "static", "question_stem": "Which color?", "choices": []},
        },
    ]

    def turn(
        *,
        move_attempts: int,
        block_complete: bool = False,
        substep_passed: bool = False,
        decision: str = "stay",
        answer: str = "The river is blue.",
        state: dict | None = None,
    ):
        return resolve_block_turn(
            decision=decision,
            substep_passed=substep_passed,
            block_complete=block_complete,
            rubric_met=[],
            stored_rubric=[],
            matched_wrong="",
            blocks=blocks,
            step=0,
            active_block_state=state or {"substep": "main"},
            block_results=[],
            move_attempts=move_attempts,
            hint_tier="nudge",
            reveals=0,
            enrichment_turns=0,
            cfg=default_kc_tutor_config(),
            goal=None,
            last_misconception="",
            answer=answer,
        )

    held = turn(move_attempts=0)
    assert held.next_step == 0
    assert held.advance_block is False
    assert held.next_block_state["substep"] == "main"
    still = turn(move_attempts=1)
    assert still.next_step == 0
    assert still.next_block_state["substep"] == "main"
    agreed = turn(move_attempts=0, block_complete=True, substep_passed=True)
    assert agreed.next_step == 0
    assert agreed.advance_block is False
    assert agreed.next_block_state["substep"] == "summary_check"
    assert not agreed.next_block_state.get("revealed_substep")
    exhausted = turn(move_attempts=2)
    assert exhausted.next_step == 0
    assert exhausted.advance_block is False
    assert exhausted.next_block_state["substep"] == "summary_check"
    assert exhausted.next_block_state["revealed_substep"] is True


def test_summary_check_closes_topic_guided_and_assessment_blocks() -> None:
    from copy import deepcopy

    from app.kc_loop import learner_ready_to_proceed, resolve_block_turn
    from app.models import default_kc_tutor_config

    cfg = default_kc_tutor_config()
    for phrase in ("close", "close and move on", "move on", "continue to next", "done", "skip", "move on anyway"):
        assert learner_ready_to_proceed(phrase, False), phrase
    assert not learner_ready_to_proceed("Can you explain the blue?", False)

    def run(
        block: dict,
        substep: str,
        answer: str,
        *,
        state: dict | None = None,
        substep_passed: bool = False,
        block_complete: bool = False,
        move_attempts: int = 0,
        tutor_cfg: dict | None = None,
    ):
        active = {"substep": substep, "dialogue_turns": 0}
        if state:
            active.update(state)
        return resolve_block_turn(
            decision="stay",
            substep_passed=substep_passed,
            block_complete=block_complete,
            rubric_met=[],
            stored_rubric=[],
            matched_wrong="",
            blocks=[block, {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain next."}}],
            step=0,
            active_block_state=active,
            block_results=[],
            move_attempts=move_attempts,
            hint_tier="nudge",
            reveals=0,
            enrichment_turns=0,
            cfg=tutor_cfg or cfg,
            goal=None,
            last_misconception="",
            answer=answer,
        )

    topic = {
        "id": "topic",
        "type": "topic_goal",
        "data": {"topic": "River color", "goal": "The river is blue.", "acceptance_criteria": "The river is blue."},
    }
    passed = run(topic, "main", "The river is blue.", substep_passed=True)
    assert passed.advance_block is False
    assert passed.next_block_state["substep"] == "summary_check"
    assert passed.next_block_state["last_task_substep"] == "main"
    assert not passed.next_block_state.get("revealed_substep")
    closed = run(
        topic,
        "summary_check",
        "move on",
        state=passed.next_block_state,
        block_complete=True,
    )
    assert closed.advance_block is True
    assert closed.block_results[-1]["outcome"] == "passed"

    missed = run(topic, "main", "I am not sure yet.", move_attempts=2)
    assert missed.next_block_state["substep"] == "summary_check"
    assert missed.next_block_state["revealed_substep"] is True
    assert missed.hint_tier == "reveal"
    still_open = run(
        topic,
        "summary_check",
        "Can you explain the blue?",
        state=missed.next_block_state,
    )
    assert still_open.advance_block is False
    assert still_open.next_block_state["revealed_substep"] is True
    assert still_open.next_block_state["substep"] == "summary_check"
    redeemed = run(
        topic,
        "summary_check",
        "The river is blue.",
        state=missed.next_block_state,
        substep_passed=True,
    )
    assert redeemed.advance_block is False
    assert redeemed.next_block_state["revealed_substep"] is False
    assert redeemed.next_block_state["substep"] == "summary_check"
    redeemed_close = run(
        topic,
        "summary_check",
        "close and move on",
        state=redeemed.next_block_state,
        block_complete=True,
    )
    assert redeemed_close.block_results[-1]["outcome"] == "passed"
    revealed_close = run(
        topic,
        "summary_check",
        "move on anyway",
        state=missed.next_block_state,
        block_complete=True,
    )
    assert revealed_close.block_results[-1]["outcome"] == "revealed"

    socratic_cfg = deepcopy(cfg)
    socratic_cfg["blocks"]["socratic"]["dialogue_depth_turns"] = 1
    socratic = {
        "id": "talk",
        "type": "socratic",
        "data": {"central_dilemma": "Is the river blue?", "target_synthesis": "The river is blue."},
    }
    talked = run(
        socratic,
        "counterexample_probe",
        "The river is blue.",
        substep_passed=True,
        tutor_cfg=socratic_cfg,
    )
    assert talked.next_block_state["substep"] == "summary_check"

    case = {
        "id": "cases",
        "type": "case_study",
        "data": {"invariant_principle": "Blue water reflects the sky.", "case_a": "Morning", "case_b": "Evening"},
    }
    contrasted = run(case, "contrast_and_rule", "Blue water reflects the sky.", substep_passed=True)
    assert contrasted.next_block_state["substep"] == "summary_check"

    teach = {
        "id": "peer",
        "type": "teach_back",
        "data": {"peer_persona_prompt": "A friend", "required_concepts": ["blue water"]},
    }
    taught = run(teach, "peer_follow_up", "I told them about blue water.", substep_passed=True)
    assert taught.next_block_state["substep"] == "summary_check"

    curiosity = {
        "id": "wonder",
        "type": "curiosity",
        "data": {"phenomenon_hook": "Why is the river blue?", "prediction_question": "Guess."},
    }
    wondered = run(curiosity, "hook_and_predict", "I wonder why.", substep_passed=True)
    assert wondered.next_block_state["substep"] == "summary_check"
    wonder_done = resolve_block_turn(
        decision="stay",
        substep_passed=False,
        block_complete=True,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[curiosity],
        step=0,
        active_block_state=wondered.next_block_state,
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception="",
        answer="done",
    )
    assert wonder_done.block_results[-1]["outcome"] == "engaged"
    assert wonder_done.mark_known is True

    quiz = {
        "id": "quiz",
        "type": "mcq",
        "data": {
            "mode": "static",
            "question_stem": "Which color?",
            "choices": [
                {"id": "a", "text": "Blue water", "is_correct": True},
                {"id": "b", "text": "Red water", "is_correct": False},
            ],
            "correct_explanation": "Blue water reflects the sky.",
        },
    }
    picked = run(quiz, "choice", "Blue water", substep_passed=True)
    assert picked.next_block_state["substep"] == "summary_check"
    assert picked.advance_block is False
    why = run(quiz, "choice", "Blue water", move_attempts=1, substep_passed=True)
    assert why.next_block_state["substep"] == "awaiting_why"
    explained = run(quiz, "awaiting_why", "Blue water reflects the sky.", substep_passed=True)
    assert explained.next_block_state["substep"] == "summary_check"
    missed_quiz = run(quiz, "choice", "Red water", move_attempts=1)
    assert missed_quiz.next_block_state["substep"] == "summary_check"
    assert missed_quiz.next_block_state["revealed_substep"] is True

    worked = {
        "id": "work",
        "type": "worked_example",
        "data": {
            "problem_statement": "Name the color.",
            "steps": [{"step_text": "Look at the water."}],
            "solo_expected_answer": "The river is blue.",
        },
    }
    faded = run(worked, "faded_step", "no idea", move_attempts=1)
    assert faded.next_block_state["substep"] == "solo_solve"
    assert faded.next_block_state["revealed_substep"] is True
    solved = run(worked, "solo_solve", "The river is blue.", substep_passed=True)
    assert solved.advance_block is True
    assert solved.next_step == 1
    assert solved.block_results[-1]["outcome"] == "passed"

    flaw = {
        "id": "flaw",
        "type": "spot_the_flaw",
        "data": {"flaw_description": "The river is red.", "corrected_version": "The river is blue."},
    }
    critiqued = run(
        flaw,
        "critique",
        "The flaw is the river is red. The river is blue.",
        substep_passed=True,
    )
    assert critiqued.next_block_state["substep"] == "summary_check"
    missed_flaw = run(flaw, "critique", "Looks fine to me.", move_attempts=1)
    assert missed_flaw.next_block_state["revealed_substep"] is True

    recall = {
        "id": "recall",
        "type": "retrieval_check",
        "data": {"recall_prompt": "What color?", "expected_fact": "The river is blue.", "expected_why_rationale": "It reflects the sky."},
    }
    elaborated = run(recall, "elaborate_why", "It reflects the sky.", substep_passed=True)
    assert elaborated.next_block_state["substep"] == "summary_check"
    missed_recall = run(recall, "elaborate_why", "I forget.", move_attempts=1)
    assert missed_recall.next_block_state["substep"] == "summary_check"
    assert missed_recall.next_block_state["revealed_substep"] is True


def test_first_move_on_and_next_part_finish_the_block() -> None:
    from app.kc_loop import learner_ready_to_proceed, resolve_block_turn
    from app.models import default_kc_tutor_config

    for phrase in ("move on", "next part", "we can move to the next part", "move to the next part"):
        assert learner_ready_to_proceed(phrase, False), phrase
    assert not learner_ready_to_proceed("Why is the river blue?", False)
    assert not learner_ready_to_proceed("Can you give me the background?", False)

    topic = {
        "id": "topic",
        "type": "topic_goal",
        "data": {"topic": "River color", "goal": "The river is blue.", "acceptance_criteria": "The river is blue."},
    }
    blocks = [topic, {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain next."}}]

    def turn(answer: str, *, fragment: bool = False, move_attempts: int = 0):
        return resolve_block_turn(
            decision="stay",
            substep_passed=False,
            block_complete=False,
            rubric_met=[],
            stored_rubric=[],
            matched_wrong="",
            blocks=blocks,
            step=0,
            active_block_state={"substep": "main"},
            block_results=[],
            move_attempts=move_attempts,
            hint_tier="nudge",
            reveals=0,
            enrichment_turns=0,
            cfg=default_kc_tutor_config(),
            goal=None,
            last_misconception="",
            answer=answer,
            fragment=fragment,
        )

    for phrase in ("move on", "next part", "we can move to the next part"):
        closed = turn(phrase, fragment=phrase in {"move on", "next part"})
        assert closed.advance_block is True, phrase
        assert closed.next_step == 1
        assert closed.block_results[-1]["outcome"] == "revealed"
        assert closed.next_block_state.get("substep") != "summary_check"

    met = turn("The river is blue, so we can move on.")
    assert met.advance_block is True
    assert met.block_results[-1]["outcome"] == "passed"


def test_a_question_or_background_request_does_not_count_as_a_miss() -> None:
    from app.kc_loop import resolve_block_turn
    from app.models import default_kc_tutor_config

    topic = {
        "id": "topic",
        "type": "topic_goal",
        "data": {"topic": "River color", "goal": "The river is blue.", "acceptance_criteria": "The river is blue."},
    }
    blocks = [topic, {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain next."}}]

    def turn(answer: str, *, move_attempts: int = 0):
        return resolve_block_turn(
            decision="stay",
            substep_passed=False,
            block_complete=False,
            rubric_met=[],
            stored_rubric=[],
            matched_wrong="",
            blocks=blocks,
            step=0,
            active_block_state={"substep": "main"},
            block_results=[],
            move_attempts=move_attempts,
            hint_tier="nudge",
            reveals=0,
            enrichment_turns=0,
            cfg=default_kc_tutor_config(),
            goal=None,
            last_misconception="",
            answer=answer,
        )

    for phrase in ("Why is the river blue?", "Can you give me the background?", "Tell me the background of this"):
        stayed = turn(phrase, move_attempts=1)
        assert stayed.advance_block is False, phrase
        assert stayed.move_attempts == 1, phrase
        assert stayed.next_block_state["substep"] == "main"
        assert stayed.block_results == []

    missed = turn("I think the river is red.")
    assert missed.advance_block is False
    assert missed.move_attempts == 1
    assert missed.next_block_state["substep"] == "main"


def test_session_block_progress_short_title() -> None:
    from types import SimpleNamespace

    from app.kc import _session_block_progress

    node = SimpleNamespace(
        title="Rome",
        blocks=[
            {
                "id": "goal",
                "type": "topic_goal",
                "data": {"block_title": "Rise of Julius Caesar", "topic": "Rome", "goal": "Explain the rise."},
            },
            {
                "id": "walk",
                "type": "explanation",
                "data": {"topics": [{"id": "t1", "title": "The Senate", "explanation": "They debated."}]},
            },
            {
                "id": "check",
                "type": "retrieval_check",
                "data": {"recall_prompt": "Why did the rise matter?"},
            },
        ],
    )
    session = SimpleNamespace(step=0, status="in_progress", active_block_state={}, block_results=[])
    progress = _session_block_progress(node, session)["block_progress"]
    assert [item["short_title"] for item in progress] == ["Rise of Julius Caesar", "The Senate", ""]
    assert progress[2]["title"] == "Why did the rise matter?"


