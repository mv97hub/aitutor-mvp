"""The prompt tester calls build_kc_prompt and does not write."""

import inspect
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.kc_prompt_tester import PromptTesterIn, preview_kc_prompt
from app.main import app
from app.models import KcGoal, KcSession
from app.routes.kc import post_prompt_tester
from app.studio import DELETE_PASSWORD

client = TestClient(app)
ROUTE = Path(__file__).resolve().parents[1] / "app" / "kc_prompt_tester.py"


def _sessions() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(func.count()).select_from(KcSession)) or 0
    finally:
        db.close()


def _body(**overrides) -> dict:
    body = {
        "course_title": "Triangles",
        "course_description": "See why the angles add up.",
        "audience": "12-14",
        "kind": "mastery",
        "minutes": None,
        "component_title": "Angle sum",
        "component_code": "angles",
        "component_description": "Why a triangle's angles add up.",
        "kc_type": "factual",
        "core_truth": "The angles of a triangle add to one hundred eighty degrees.",
        "rubric": ["States 180."],
        "misconceptions": [{"wrong_move": "They add to 90.", "broken_kc": "right-angle"}],
        "prerequisite_codes": ["lines"],
        "encompasses_codes": ["polygons"],
        "transfer_case": "",
        "counterfactual": "",
        "type_fields": {"fact": "The angles of a triangle add to one hundred eighty degrees."},
        "move_index": 1,
        "choice_on_screen": "no",
        "prerequisite_status": "lines: unknown",
        "course_position": "1 of 2; previous: none; next: Exterior angle",
        "display_name": "Ada",
        "age": 12,
        "reading_level": "grade-level",
        "modality": "visual",
        "interests": ["kites"],
        "attempts": 0,
        "hint_tier": "nudge",
        "component_status": "unknown",
        "stability": "0",
        "last_answer": "",
        "last_misconception": "",
        "minutes_used": 0,
        "support_band": "hold",
        "persona": "curious-co-explorer",
        "lexicon": "middle-grade-vivid",
        "metaphors": "playground-sports",
        "sidekick": "bumbling-partner",
        "use_interests": "yes",
        "instructive": 3,
        "struggle_window": "long",
        "stay_on_course": "yes",
        "anti_spoiler": "yes",
        "one_question": "yes",
        "misconception_policy": "retry_once",
        "enrichment": "on_request",
        "growth_praise": "yes",
        "self_explanation": "yes",
        "reveals": 0,
        "off_course_count": 0,
        "rubric_met": [],
        "last_messages": "",
        "affect": "",
        "help_requested": "no",
        "last_practiced": "",
        "redirect_pending": "no",
        "enrichment_turns": 0,
        "unit_close": "no",
        "course_outro": "no",
    }
    body.update(overrides)
    return body


def _direct(body: dict) -> dict:
    return preview_kc_prompt(PromptTesterIn.model_validate(body))


def test_prompt_tester_matches_build_kc_prompt_and_writes_nothing() -> None:
    assert "db" not in inspect.signature(post_prompt_tester).parameters
    assert "build_kc_prompt(" in ROUTE.read_text()
    code = f"zz-tester-{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/kc/courses",
        json={
            "code": code,
            "title": "Draft preview",
            "description": "A course that is not ready.",
            "audience": "9-11",
            "kind": "mastery",
            "minutes": None,
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    assert created.json()["ready"] is False
    before = _sessions()
    try:
        balanced = _body(instructive=3, unit_close="no")
        first = client.post("/kc/prompt-tester", json=balanced)
        assert first.status_code == 200, first.text
        taught = _body(instructive=5, unit_close="no")
        second = client.post("/kc/prompt-tester", json=taught)
        assert second.status_code == 200, second.text
        direct = _direct(taught)
        assert second.json()["system_prompt"] == direct["system_prompt"]
        assert second.json()["system_prompt"] != first.json()["system_prompt"]
        assert "explanation_depth=5" in second.json()["system_prompt"]
        assert "Teach thoroughly with step-by-step scaffolding" in second.json()["system_prompt"]
        assert "Ask the question first with almost no preliminary explanation" not in second.json()["system_prompt"]
        closed = _body(instructive=5, unit_close="yes")
        third = client.post("/kc/prompt-tester", json=closed)
        assert third.status_code == 200, third.text
        closed_direct = _direct(closed)
        assert third.json()["system_prompt"] == closed_direct["system_prompt"]
        assert third.json()["system_prompt"] != second.json()["system_prompt"]
        assert "End the unit in this reply." in third.json()["system_prompt"]
        assert second.json()["active_block_type"] == "topic_goal"
        assert "Topic / Goal" in second.json()["move_name"]
        assert second.json()["evidence"] == "blk_1"
        assert second.json()["active_substep"] == "main"
        boxed = _body(kind="time_boxed", minutes=20, struggle_window="long", enrichment="offer")
        timed = client.post("/kc/prompt-tester", json=boxed)
        assert timed.status_code == 200, timed.text
        timed_direct = _direct(boxed)
        assert timed.json()["system_prompt"] == timed_direct["system_prompt"]
        assert "max_retries_before_reveal=1" in timed.json()["system_prompt"]
        assert "enrichment_mode=direct" in timed.json()["system_prompt"]
        assert "Course kind is time_boxed" in timed.json()["system_prompt"]
        unknown = _body(persona="wizard")
        rejected = client.post("/kc/prompt-tester", json=unknown)
        assert rejected.status_code == 422, rejected.text
        assert "Persona must be one of:" in rejected.text
        maybe = client.post("/kc/prompt-tester", json=_body(unit_close="maybe"))
        assert maybe.status_code == 422, maybe.text
        saved = client.get(f"/kc/courses/{course_id}")
        assert saved.status_code == 200, saved.text
        assert saved.json()["title"] == "Draft preview"
        assert saved.json()["ready"] is False
        assert saved.json()["description"] == "A course that is not ready."
        assert _sessions() == before
        goal_row = SessionLocal()
        try:
            stored = goal_row.get(KcGoal, uuid.UUID(course_id))
            assert stored is not None
            assert stored.title == "Draft preview"
        finally:
            goal_row.close()
        assert closed_direct["active_block_type"] == "topic_goal"
    finally:
        deleted = client.post(f"/kc/courses/{course_id}/delete", json={"password": DELETE_PASSWORD})
        assert deleted.status_code == 200, deleted.text
