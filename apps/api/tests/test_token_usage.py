"""Tutor token usage is stored per model call and reported for the admin page."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Student
from app.seed import seed
from app.studio import DELETE_PASSWORD
from sqlalchemy import select

client = TestClient(app)


def _student_id() -> str:
    db = SessionLocal()
    try:
        seed(db)
        row = db.scalars(select(Student).order_by(Student.slug)).first()
        assert row is not None
        return str(row.id)
    finally:
        db.close()


def _open_session(student_id: str, code: str) -> tuple[str, str]:
    created = client.post(
        "/kc/courses",
        json={
            "code": code,
            "title": "ZZ usage course",
            "description": "Token usage.",
            "audience": "9-11",
            "kind": "mastery",
            "minutes": None,
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    pushed = client.post(
        f"/kc/courses/{course_id}/push",
        json={"components": [{"code": f"{code}-fact", "title": "Usage fact"}]},
    )
    assert pushed.status_code == 200, pushed.text
    node_id = pushed.json()["components"][0]["id"]
    saved = client.put(
        f"/kc/nodes/{node_id}",
        json={
            "title": "Usage fact",
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
                    "data": {"topic": "Usage fact", "goal": "Explain the color."},
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
    return opened.json()["id"], course_id


def _drop(code: str) -> None:
    for item in client.get("/kc/courses").json():
        if item["code"] == code:
            client.post(f"/kc/courses/{item['id']}/delete", json={"password": DELETE_PASSWORD})


def test_token_usage_is_stored_and_filtered() -> None:
    student_id = _student_id()
    code = f"zz-usage-{uuid.uuid4().hex[:8]}"
    session_id, course_id = _open_session(student_id, code)
    try:
        saved = client.post(
            f"/kc/sessions/{session_id}/token-usage",
            json={
                "kind": "speak",
                "model": "gpt-4.1",
                "input_tokens": 100,
                "output_tokens": 20,
                "cached_tokens": 40,
            },
        )
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["kind"] == "speak"
        assert body["student_id"] == student_id
        assert body["course_id"] == course_id
        assert body["input_tokens"] == 100
        assert body["output_tokens"] == 20
        assert body["cached_tokens"] == 40
        assert body["total_tokens"] == 120

        answered = client.post(
            f"/kc/sessions/{session_id}/token-usage",
            json={"kind": "answer", "model": "gpt-4.1", "input_tokens": 10, "output_tokens": 5, "cached_tokens": 0},
        )
        assert answered.status_code == 200, answered.text

        detail = client.get(f"/kc/sessions/{session_id}").json()
        assert detail["token_usage"]["total"]["input_tokens"] == 110
        assert detail["token_usage"]["total"]["total_tokens"] == 135
        assert [turn["kind"] for turn in detail["token_usage"]["turns"]] == ["speak", "answer"]

        report = client.get("/kc/token-usage", params={"student_id": student_id, "all_time": True})
        assert report.status_code == 200, report.text
        totals = report.json()["totals"]
        assert totals["input_tokens"] >= 110
        assert totals["output_tokens"] >= 25
        assert totals["cached_tokens"] >= 40
        assert totals["total_tokens"] == totals["input_tokens"] + totals["output_tokens"]
        assert any(child["student_id"] == student_id and child["calls"] >= 2 for child in report.json()["by_child"])
        assert report.json()["by_day"]

        empty = client.get(
            "/kc/token-usage",
            params={"student_id": student_id, "start": "2000-01-01", "end": "2000-01-02"},
        )
        assert empty.status_code == 200, empty.text
        assert empty.json()["totals"] == {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 0,
        }
        assert empty.json()["by_child"] == []
        assert empty.json()["by_day"] == []

        default = client.get("/kc/token-usage")
        assert default.status_code == 200, default.text
        window = default.json()
        today = datetime.now(timezone.utc).date()
        assert window["all_time"] is False
        assert window["start"] == (today - timedelta(days=29)).isoformat()
        assert window["end"] == today.isoformat()

        missing = client.post(
            f"/kc/sessions/{uuid.uuid4()}/token-usage",
            json={"kind": "speak", "model": "gpt-4.1", "input_tokens": 1, "output_tokens": 1, "cached_tokens": 0},
        )
        assert missing.status_code == 404
        bad_kind = client.post(
            f"/kc/sessions/{session_id}/token-usage",
            json={"kind": "other", "model": "gpt-4.1", "input_tokens": 1, "output_tokens": 1, "cached_tokens": 0},
        )
        assert bad_kind.status_code == 422
    finally:
        _drop(code)
