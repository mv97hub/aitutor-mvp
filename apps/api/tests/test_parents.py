"""Parents, the child links, and the parent-safe chat and progress endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.learn_stars import stars_from_units
from app.main import app
from app.models import KcSession, KcState, Parent, Student
from app.parents import PARENT_WEEK_ZONE, _child_progress, _week_counts, parent_week_start, session_star_unit
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
    assert script.get_heads() == ["035_gpt6_luna_model"]
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


def test_parent_week_starts_on_monday_and_a_finished_topic_uses_child_stars() -> None:
    # Wednesday 11 Nov 2026, noon in New York (UTC-5).
    start = parent_week_start(datetime(2026, 11, 11, 17, 0, tzinfo=timezone.utc))
    local = start.astimezone(PARENT_WEEK_ZONE)
    assert local.weekday() == 0
    assert (local.hour, local.minute) == (0, 0)
    assert (local.year, local.month, local.day) == (2026, 11, 9)
    finished = session_star_unit("completed", [{"outcome": "passed", "attempts": 1}], 0)
    assert stars_from_units([finished])["stars"] == 55
    still_open = session_star_unit("in_progress", [{"outcome": "passed", "attempts": 1}], 0)
    assert stars_from_units([still_open])["stars"] == 15

    student = uuid.uuid4()
    topic = uuid.uuid4()
    counts = _week_counts(
        [
            SimpleNamespace(
                id=uuid.uuid4(),
                student_id=student,
                kc_id=topic,
                status="completed",
                updated_at=datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc),
                block_results=[
                    {"outcome": "passed", "attempts": 1},
                    {"outcome": "revealed", "attempts": 3},
                ],
                reveals=1,
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                student_id=student,
                kc_id=uuid.uuid4(),
                status="in_progress",
                updated_at=datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc),
                block_results=[{"outcome": "passed", "attempts": 2}],
                reveals=0,
            ),
        ]
    )[student]
    assert counts["blocks_passed"] == 2
    assert counts["blocks_revealed"] == 1
    assert counts["days_active"] == 2
    assert counts["sessions"] == 2
    assert counts["topics_finished"] == 1

    fractions = uuid.uuid4()
    decimals = uuid.uuid4()
    percents = uuid.uuid4()
    progress = _child_progress(
        [
            {
                "id": str(fractions),
                "title": "Fractions",
                "started": True,
                "course_complete": False,
                "stars": 40,
                "finished_topic_count": 3,
                "known_count": 2,
                "fragile_count": 1,
                "last_active_at": None,
                "current_topic": {"title": "Halves"},
                "opportunities_preview": [
                    {"component_title": "Thirds", "summary": "Revisit thirds."},
                    {"component_title": "Quarters", "summary": "Revisit quarters."},
                ],
            },
            {
                "id": str(decimals),
                "title": "Decimals",
                "started": True,
                "course_complete": True,
                "stars": 15,
                "finished_topic_count": 1,
                "known_count": 0,
                "fragile_count": 1,
                "last_active_at": None,
                "current_topic": None,
                "opportunities_preview": [
                    {"component_title": "Tenths", "summary": "Tenths are fragile."},
                ],
            },
            {
                "id": str(percents),
                "title": "Percents",
                "started": False,
                "course_complete": False,
                "stars": 0,
                "finished_topic_count": 0,
                "known_count": 1,
                "fragile_count": 0,
                "last_active_at": None,
                "opportunities_preview": [
                    {"component_title": "Rates", "summary": "This one must be cut."},
                ],
            },
        ]
    )
    assert progress["topics_mastered"] == 3
    assert progress["topics_fragile"] == 2
    assert [item["title"] for item in progress["attention"]] == ["Fractions", "Thirds", "Quarters"]
    assert len(progress["attention"]) == 3
    assert "fragile" in progress["attention"][0]["detail"]
    assert all(item["course_id"] != percents for item in progress["attention"])
    assert all("content" not in item and "message" not in item for item in progress["attention"])


def _student(name: str) -> str:
    created = client.post("/students", json={"display_name": name, "age": 10})
    assert created.status_code == 200, created.text
    return created.json()["id"]


def _drop_students(*ids: str) -> None:
    db = SessionLocal()
    try:
        keys = [uuid.UUID(item) for item in ids]
        db.execute(delete(KcState).where(KcState.student_id.in_(keys)))
        db.execute(delete(KcSession).where(KcSession.student_id.in_(keys)))
        db.execute(delete(Student).where(Student.id.in_(keys)))
        db.commit()
    finally:
        db.close()


def test_parent_dashboard_is_the_last_ten_chats_progress_and_this_week() -> None:
    suffix = uuid.uuid4().hex[:8]
    linked_id = _student(f"ZZ Dash Active {suffix}")
    quiet_id = _student(f"ZZ Dash Quiet {suffix}")
    other_id = _student(f"ZZ Dash Other {suffix}")
    code = f"zz-dash-{suffix}"
    parent = _parent()
    outsider = _parent()
    try:
        course_id, session_id = _course_with_chat(linked_id, code)
        _, outside_session = _course_with_chat(other_id, f"{code}-out")
        client.put(
            f"/parents/{parent['id']}/students",
            json={"student_ids": [linked_id, quiet_id]},
        )
        client.put(f"/parents/{outsider['id']}/students", json={"student_ids": [other_id]})

        db = SessionLocal()
        try:
            opened = db.get(KcSession, uuid.UUID(session_id))
            assert opened is not None
            opened.status = "completed"
            opened.block_results = [{"outcome": "passed", "attempts": 1}]
            opened.reveals = 0
            opened.updated_at = datetime.now(timezone.utc)
            state = db.scalar(
                select(KcState).where(KcState.student_id == opened.student_id, KcState.kc_id == opened.kc_id)
            )
            if state is None:
                db.add(KcState(student_id=opened.student_id, kc_id=opened.kc_id, status="fragile"))
            else:
                state.status = "fragile"
            old = KcSession(
                student_id=opened.student_id,
                goal_id=opened.goal_id,
                kc_id=opened.kc_id,
                status="completed",
                block_results=[{"outcome": "passed", "attempts": 1}],
                updated_at=datetime.now(timezone.utc) - timedelta(days=14),
            )
            db.add(old)
            db.flush()
            old_id = str(old.id)
            for minute in range(9):
                db.add(
                    KcSession(
                        student_id=opened.student_id,
                        goal_id=opened.goal_id,
                        kc_id=opened.kc_id,
                        status="in_progress",
                        block_results=[{"outcome": "revealed", "attempts": 2}] if minute == 0 else [],
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=minute + 1),
                    )
                )
            db.commit()
        finally:
            db.close()

        missing = client.get(f"/parents/{uuid.uuid4()}/dashboard")
        assert missing.status_code == 404

        body = client.get(f"/parents/{parent['id']}/dashboard")
        assert body.status_code == 200, body.text
        payload = body.json()
        assert "prompts" not in body.text
        assert "What color is the river?" not in body.text
        assert "SECRET-SYSTEM-PROMPT" not in body.text
        recent = payload["recent"]
        assert len(recent) == 10
        assert old_id not in {item["id"] for item in recent}
        assert outside_session not in {item["id"] for item in recent}
        moments = [item["updated_at"] for item in recent]
        assert moments == sorted(moments, reverse=True)
        assert recent[0]["kc_title"] == "Parent fact"
        assert recent[0]["course_title"] == "ZZ parent course"
        assert recent[0]["status"] == "completed"
        assert all("message" not in item for item in recent)

        by_child = {item["student_id"]: item for item in payload["children"]}
        assert set(by_child) == {linked_id, quiet_id}
        active = by_child[linked_id]
        assert active["week"] == {
            "sessions": 10,
            "topics_finished": 1,
            "stars": 55,
            "blocks_passed": 1,
            "blocks_revealed": 1,
            "days_active": 1,
        }
        assert active["topics_mastered"] == 0
        assert active["topics_fragile"] == 1
        assert active["courses_started"] >= 1
        assert 1 <= len(active["attention"]) <= 3
        assert active["attention"][0]["title"] == "ZZ parent course"
        assert "fragile" in active["attention"][0]["detail"]
        if active["current_course_id"]:
            assert active["current_course_id"] == course_id
            assert active["current_course_title"] == "ZZ parent course"
        else:
            assert active["courses_finished"] >= 1
        assert by_child[quiet_id]["week"] == {
            "sessions": 0,
            "topics_finished": 0,
            "stars": 0,
            "blocks_passed": 0,
            "blocks_revealed": 0,
            "days_active": 0,
        }
        assert by_child[quiet_id]["topics_mastered"] == 0
        assert by_child[quiet_id]["topics_fragile"] == 0
        assert by_child[quiet_id]["attention"] == []
        assert by_child[quiet_id]["courses_started"] == 0
        assert payload["week_starts_at"]
        for child in payload["children"]:
            assert "message" not in child
            for item in child["attention"]:
                assert set(item) == {"course_id", "title", "detail"}
                assert "What color is the river?" not in item["detail"]

        outsider_body = client.get(f"/parents/{outsider['id']}/dashboard").json()
        assert [item["student_id"] for item in outsider_body["children"]] == [other_id]
        assert outside_session in {item["id"] for item in outsider_body["recent"]}
    finally:
        _drop_parents(parent["id"], outsider["id"])
        _drop_course(code)
        _drop_course(f"{code}-out")
        _drop_students(linked_id, quiet_id, other_id)
