"""Knowledge-component studio and tutor. Catalog chats stay put."""

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


def _make(code: str, title: str = "ZZ course", description: str = "Tell one idea from another.") -> dict:
    _wipe_zz()
    created = client.post(
        "/kc/courses",
        json={
            "code": code,
            "title": title,
            "description": description,
            "audience": "12-14",
            "kind": "mastery",
            "minutes": None,
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
    db = SessionLocal()
    try:
        node = db.scalar(select(KcNode).where(KcNode.code == code))
        assert node is not None
        row = db.scalar(select(KcState).where(KcState.student_id == student_id, KcState.kc_id == node.id))
        if row is None:
            row = KcState(student_id=student_id, kc_id=node.id, status="known", stability=1)
            db.add(row)
        else:
            row.status = "known"
            row.stability = 1
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
        assert all(item["description"].startswith("Outline:") for item in pushed.json()["components"])
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
    course = _course_by_code("kc-geometry")
    factual = _node(course, "geo-angle-sum")
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
        assert "debate-moderator" in text
        assert "analytical-high-school" in text
        assert "policy-cause" in text
        assert "pundit" in text
        assert "Explain before the question: level 5" in text
        assert "Struggle window: long" in text
        assert "Stay on course: no" in text
        assert f"Age: {age}" in text
        for interest in interests:
            assert interest in text
        assert "HARBOR-GUIDE-SHOULD-NOT-APPEAR" not in text
        assert "curious-co-explorer" not in text
        assert "one retrieval question, then a short confirmation" in text
        assert "Settings do not change the type, the edges, or the score." in text
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
        done = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "The river in this course is blue."},
        )
        assert done.status_code == 200, done.text
        assert done.json()["passed"] is True
        assert done.json()["score"] == 100
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
    course = _course_by_code("kc-geometry")
    sas = _node(course, "geo-sas-ssa")
    try:
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": sas["id"]},
        )
        assert opened.status_code == 200, opened.text
        failed = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "SSA proves congruence"},
        )
        assert failed.status_code == 200, failed.text
        assert failed.json()["passed"] is False
        assert failed.json()["redirect"]["code"] == "geo-included-angle"
        board = client.get(
            f"/kc/tutor/courses/{course['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert any(card["code"] == "geo-included-angle" and card["role"] == "patch" for card in board["cards"])
        sas_state = _state(storm.id, "geo-sas-ssa")
        assert sas_state is not None and sas_state.status != "known"
        included = _state(storm.id, "geo-included-angle")
        assert included is None or included.status != "known"
        congruence = _state(storm.id, "geo-congruence")
        assert congruence is None or congruence.status != "known"

        _clear_progress(storm.id)
        fresh = _course_by_code("kc-geometry")
        sas = _node(fresh, "geo-sas-ssa")
        rule = sas["type_fields"]["rule"]
        again = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": fresh["id"], "kc_id": sas["id"]},
        )
        assert again.status_code == 200, again.text
        session_id = again.json()["id"]
        for answer in (
            "The case with the included angle locks one triangle.",
            "One case closes and the other leaves two shapes.",
            rule,
        ):
            step = client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": answer})
            assert step.status_code == 200, step.text
        assert step.json()["passed"] is True
        assert step.json()["score"] == 100
        assert _state(storm.id, "geo-sas-ssa").status == "known"
        included = _state(storm.id, "geo-included-angle")
        congruence = _state(storm.id, "geo-congruence")
        assert included is None or included.status != "known"
        assert congruence is None or congruence.status != "known"
    finally:
        _clear_progress(storm.id)


def test_fixtures_time_box_synthesis_and_factual_recipe() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    try:
        codes = {item["code"]: item for item in client.get("/kc/tutor/courses").json()}
        assert set(codes) >= {"kc-geometry", "kc-macro", "kc-rome"}
        geometry = _course_by_code("kc-geometry")
        assert geometry["kind"] == "time_boxed"
        assert geometry["minutes"] == 30
        assert len(geometry["components"]) == 6
        assert geometry["ready"] is True
        sas = _node(geometry, "geo-sas-ssa")
        assert sas["misconceptions"][0]["broken_kc"] == "geo-included-angle"
        assert _node(geometry, "geo-included-angle")["target"] is False
        diagram = client.get(f"/kc/courses/{geometry['id']}/network").json()
        assert any(node["code"] == "geo-included-angle" and node["patch"] for node in diagram["nodes"])
        assert any(
            edge["kind"] == "prerequisite_of"
            and edge["from_code"] == "geo-included-angle"
            and edge["to_code"] == "geo-sas-ssa"
            for edge in diagram["edges"]
        )
        macro = _course_by_code("kc-macro")
        rome = _course_by_code("kc-rome")
        assert {item["kc_type"] for item in macro["components"]} >= {
            "factual",
            "procedural",
            "conceptual",
            "causal",
            "synthesis",
        }
        assert {item["kc_type"] for item in rome["components"]} >= {
            "factual",
            "conceptual",
            "causal",
            "synthesis",
        }

        factual = _node(geometry, "geo-angle-sum")
        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": geometry["id"], "kc_id": factual["id"]},
        )
        assert opened.json()["recipe"] == "retrieval"
        assert opened.json()["step_label"] == "Retrieval question"
        answered = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "180"},
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["passed"] is True
        assert answered.json()["step_label"] == "Short confirmation"
        assert "180" in answered.json()["reply"]

        _clear_progress(storm.id)
        _set_known(storm.id, "geo-angle-sum")
        _set_known(storm.id, "geo-missing-angle")
        skipped = client.get(
            f"/kc/tutor/courses/{geometry['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert skipped["minutes"] == 30
        assert skipped["count_label"] == "2 of 6"
        assert all(card["code"] not in {"geo-angle-sum", "geo-missing-angle"} for card in skipped["cards"])
        assert all(card["code"] != "geo-congruence-plan" for card in skipped["cards"])

        _set_known(storm.id, "geo-congruence")
        _set_known(storm.id, "geo-sas-ssa")
        stretch = client.get(
            f"/kc/tutor/courses/{geometry['id']}",
            params={"student_id": str(storm.id)},
        ).json()
        assert any(card["code"] == "geo-congruence-plan" for card in stretch["cards"])
        assert stretch["known"] == 4
    finally:
        _clear_progress(storm.id)


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
        assert [item["text"] for item in spoken.json()["choice"]["choices"]] == ["The closed case", "The open case"]
        assert spoken.json()["choice"]["prompt"] == "Which case fits?"
        again = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/speech",
            json={"content": "Asked twice."},
        )
        assert again.json()["messages"][-1]["content"] == "Which case fits?"
        stepped = client.post(
            f"/kc/tutor/sessions/{opened.json()['id']}/turn",
            json={"answer": "The closed case"},
        )
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["passed"] is False
        assert stepped.json()["step"] == 1
        assert stepped.json()["needs_speech"] is True

        causal = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": cause["id"]},
        ).json()
        client.post(f"/kc/tutor/sessions/{causal['id']}/turn", json={"answer": "The tax is the stake."})
        client.post(f"/kc/tutor/sessions/{causal['id']}/speech", json={"content": "Mark the claim."})
        marked = client.get(f"/kc/tutor/sessions/{causal['id']}").json()
        assert [item["text"] for item in marked["choice"]["choices"]] == ["This claim is flawed", "This claim holds"]
        held = client.post(f"/kc/tutor/sessions/{causal['id']}/turn", json={"answer": "This claim holds"})
        assert held.json()["passed"] is False
        assert held.json()["step"] == 1
        fresh = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(storm.id), "course_id": course["id"], "kc_id": cause["id"]},
        )
        assert fresh.status_code == 200, fresh.text
        # The in-progress session is reused, so finish it and the flawed mark passes the choice step.
        done = client.post(f"/kc/tutor/sessions/{causal['id']}/turn", json={"answer": "This claim is flawed"})
        assert done.status_code == 200, done.text
        assert done.json()["step"] == 2
        assert done.json()["needs_speech"] is True
        assert done.json()["passed"] is False
    finally:
        _clear_progress(storm.id)
        _wipe_zz()
