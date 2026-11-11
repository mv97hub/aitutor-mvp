"""Parents, the child links, and the parent-safe chat and progress endpoints."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.main import app
from app.models import Parent, Student
from app.seed import seed
from app.studio import DELETE_PASSWORD

client = TestClient(app)


def _children() -> dict[str, str]:
    db = SessionLocal()
    try:
        seed(db)
        rows = db.scalars(select(Student).order_by(Student.slug)).all()
        return {row.slug: str(row.id) for row in rows}
    finally:
        db.close()


def _parent(name: str | None = None) -> dict:
    created = client.post("/parents", json={"name": name or f"ZZ Parent {uuid.uuid4().hex[:6]}"})
    assert created.status_code == 200, created.text
    return created.json()


def _drop_parents(*ids: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(Parent).where(Parent.id.in_([uuid.UUID(item) for item in ids])))
        db.commit()
    finally:
        db.close()


def _course_with_chat(student_id: str, code: str) -> tuple[str, str]:
    created = client.post(
        "/kc/courses",
        json={
            "code": code,
            "title": "ZZ parent course",
            "description": "A parent check.",
            "audience": "9-11",
            "kind": "mastery",
            "minutes": None,
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    pushed = client.post(
        f"/kc/courses/{course_id}/push",
        json={"components": [{"code": f"{code}-fact", "title": "Parent fact"}]},
    )
    assert pushed.status_code == 200, pushed.text
    node_id = pushed.json()["components"][0]["id"]
    saved = client.put(
        f"/kc/nodes/{node_id}",
        json={
            "title": "Parent fact",
            "outline": "How the fact works.",
            "core_truth": "The river is blue.",
            "rubric": ["Names the color."],
            "misconceptions": [],
            "prerequisite_codes": [],
            "encompasses_codes": [],
            "blocks": [
                {
                    "id": "blk-1",
                    "type": "topic_goal",
                    "data": {"topic": "Parent fact", "goal": "Explain the color."},
                }
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    assert client.post(f"/kc/courses/{course_id}/ready").status_code == 200
    opened = client.post(
        "/kc/tutor/sessions",
        json={"student_id": student_id, "course_id": course_id, "kc_id": node_id},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["id"]
    spoken = client.post(
        f"/kc/tutor/sessions/{session_id}/speech",
        json={"content": "What color is the river?"},
    )
    assert spoken.status_code == 200, spoken.text
    answered = client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": "I think it is blue."})
    assert answered.status_code == 200, answered.text
    tutor_message = next(item for item in spoken.json()["messages"] if item["role"] == "assistant")
    prompt = client.post(
        f"/kc/sessions/{session_id}/model-prompts",
        json={
            "system_prompt": "SECRET-SYSTEM-PROMPT",
            "messages": [{"role": "user", "content": "SECRET-PROMPT-MESSAGE"}],
            "model": "gpt-test",
            "message_id": tutor_message["id"],
        },
    )
    assert prompt.status_code == 200, prompt.text
    return course_id, session_id


def _drop_course(code: str) -> None:
    for item in client.get("/kc/courses").json():
        if item["code"] == code:
            client.post(f"/kc/courses/{item['id']}/delete", json={"password": DELETE_PASSWORD})


def test_upgrade_head_includes_the_parent_tables() -> None:
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    script = ScriptDirectory.from_config(Config(str(ini)))
    assert script.get_heads() == ["034_tutor_token_usage"]
    revisions = {rev.revision for rev in script.walk_revisions()}
    assert {"030_parent_portal", "031_course_standards"} <= revisions


def test_create_list_and_name_checks() -> None:
    parent = _parent("  ZZ   Parent  Spacing ")
    try:
        assert parent["name"] == "ZZ Parent Spacing"
        assert parent["child_count"] == 0
        listed = client.get("/parents")
        assert listed.status_code == 200
        assert any(item["id"] == parent["id"] for item in listed.json())
        assert client.get(f"/parents/{parent['id']}").json()["name"] == "ZZ Parent Spacing"
        assert client.post("/parents", json={"name": "   "}).status_code == 422
        assert client.post("/parents", json={}).status_code == 422
        assert client.get(f"/parents/{uuid.uuid4()}").status_code == 404
        assert client.get(f"/parents/{uuid.uuid4()}/students").status_code == 404
    finally:
        _drop_parents(parent["id"])


def test_link_and_unlink_children_and_two_parents_share_a_child() -> None:
    children = _children()
    first_id, second_id = list(children.values())[:2]
    one = _parent()
    two = _parent()
    try:
        assert client.get(f"/parents/{one['id']}/students").json() == []

        linked = client.put(f"/parents/{one['id']}/students", json={"student_ids": [first_id, second_id, first_id]})
        assert linked.status_code == 200, linked.text
        assert {item["id"] for item in linked.json()} == {first_id, second_id}
        assert client.get(f"/parents/{one['id']}").json()["child_count"] == 2

        shared = client.put(f"/parents/{two['id']}/students", json={"student_ids": [first_id]})
        assert [item["id"] for item in shared.json()] == [first_id]

        unlinked = client.put(f"/parents/{one['id']}/students", json={"student_ids": [second_id]})
        assert [item["id"] for item in unlinked.json()] == [second_id]
        assert [item["id"] for item in client.get(f"/parents/{two['id']}/students").json()] == [first_id]

        cleared = client.put(f"/parents/{one['id']}/students", json={"student_ids": []})
        assert cleared.json() == []
        assert client.get(f"/parents/{one['id']}").json()["child_count"] == 0

        unknown = client.put(f"/parents/{one['id']}/students", json={"student_ids": [str(uuid.uuid4())]})
        assert unknown.status_code == 422
        missing = client.put(f"/parents/{uuid.uuid4()}/students", json={"student_ids": []})
        assert missing.status_code == 404
    finally:
        _drop_parents(one["id"], two["id"])


def test_parent_chats_omit_prompts_and_refuse_an_unlinked_child() -> None:
    children = _children()
    linked_id, other_id = list(children.values())[:2]
    code = f"zz-parent-{uuid.uuid4().hex[:8]}"
    parent = _parent()
    other_parent = _parent()
    try:
        course_id, session_id = _course_with_chat(linked_id, code)
        _, other_session_id = _course_with_chat(other_id, f"{code}-b")
        client.put(f"/parents/{parent['id']}/students", json={"student_ids": [linked_id]})
        client.put(f"/parents/{other_parent['id']}/students", json={"student_ids": [other_id]})

        admin = client.get(f"/kc/sessions/{session_id}").json()
        assert admin["prompts"], "the admin view still carries the prompts"

        base = f"/parents/{parent['id']}/children/{linked_id}"
        chats = client.get(f"{base}/sessions")
        assert chats.status_code == 200, chats.text
        rows = [row for row in chats.json() if row["id"] == session_id]
        assert len(rows) == 1
        assert rows[0]["kc_title"] == "Parent fact"
        assert rows[0]["message_count"] == 2
        assert all("safety_event_count" not in row for row in chats.json())
        assert all(row["student_id"] == linked_id for row in chats.json())

        detail = client.get(f"{base}/sessions/{session_id}")
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert "prompts" not in body
        assert "token_usage" not in body
        assert "input_tokens" not in body
        assert "SECRET-SYSTEM-PROMPT" not in detail.text
        assert "SECRET-PROMPT-MESSAGE" not in detail.text
        assert set(body["student"]) == {"id", "display_name"}
        assert [item["role"] for item in body["messages"]] == ["assistant", "user"]
        assert body["messages"][0]["content"] == "What color is the river?"
        assert body["component"]["title"] == "Parent fact"

        refused = client.get(f"/parents/{parent['id']}/children/{other_id}/sessions")
        assert refused.status_code == 403
        refused_detail = client.get(f"/parents/{parent['id']}/children/{other_id}/sessions/{other_session_id}")
        assert refused_detail.status_code == 403
        wrong_pair = client.get(f"{base}/sessions/{other_session_id}")
        assert wrong_pair.status_code == 404
        assert client.get(f"/parents/{other_parent['id']}/children/{linked_id}/sessions/{session_id}").status_code == 403
        assert client.get(f"/parents/{uuid.uuid4()}/children/{linked_id}/sessions").status_code == 404
        assert client.get(f"{base}/sessions/{uuid.uuid4()}").status_code == 404

        courses = client.get(f"{base}/courses")
        assert courses.status_code == 200, courses.text
        assert any(item["id"] == course_id for item in courses.json())
        progress = client.get(f"{base}/courses/{course_id}/progress")
        assert progress.status_code == 200, progress.text
        assert progress.json()["title"] == "ZZ parent course"
        network = client.get(f"{base}/courses/{course_id}/network")
        assert network.status_code == 200, network.text
        assert client.get(f"/parents/{parent['id']}/children/{other_id}/courses").status_code == 403
        assert client.get(f"/parents/{parent['id']}/children/{other_id}/courses/{course_id}/progress").status_code == 403
        assert client.get(f"/parents/{parent['id']}/children/{other_id}/courses/{course_id}/network").status_code == 403

        client.put(f"/parents/{parent['id']}/students", json={"student_ids": []})
        assert client.get(f"{base}/sessions").status_code == 403
    finally:
        _drop_parents(parent["id"], other_parent["id"])
        _drop_course(code)
        _drop_course(f"{code}-b")
