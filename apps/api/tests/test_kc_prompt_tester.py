"""The prompt tester calls build_kc_prompt and does not write."""

import inspect
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.kc_prompt import (
    asks_why,
    build_kc_prompt,
    effective_enrichment,
    effective_window_name,
    is_fragment,
    moves_for,
    struggle_tries,
)
from app.main import app
from app.models import KcGoal, KcNode, KcSession, Student, TutorProfile
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


def _direct(body: dict) -> tuple[dict, TutorProfile, KcGoal, object]:
    fields = dict(body["type_fields"])
    fields["transfer_case"] = body["transfer_case"]
    fields["counterfactual"] = body["counterfactual"]
    student = Student(
        slug="prompt-tester",
        display_name=body["display_name"],
        age=body["age"],
        reading_level=body["reading_level"],
        modality=body["modality"],
        interests=list(body["interests"]),
    )
    profile = TutorProfile(
        id="prompt-tester",
        instructive=body["instructive"],
        persona=body["persona"],
        lexicon=body["lexicon"],
        voice_override=False,
        metaphors=body["metaphors"],
        sidekick=body["sidekick"],
        struggle_window=body["struggle_window"],
        anti_spoiler=body["anti_spoiler"] == "yes",
        one_question=body["one_question"] == "yes",
        use_interests=body["use_interests"] == "yes",
        stay_on_course=body["stay_on_course"] == "yes",
        growth_praise=body["growth_praise"] == "yes",
        misconception_policy=body["misconception_policy"],
        self_explanation=body["self_explanation"] == "yes",
        enrichment=body["enrichment"],
    )
    node = KcNode(
        code=body["component_code"],
        title=body["component_title"],
        description=body["component_description"],
        kc_type=body["kc_type"] or None,
        core_truth=body["core_truth"],
        type_fields=fields,
        rubric=list(body["rubric"]),
        misconceptions=list(body["misconceptions"]),
        prerequisite_codes=list(body["prerequisite_codes"]),
        encompasses_codes=list(body["encompasses_codes"]),
    )
    goal = KcGoal(
        code="prompt-tester",
        title=body["course_title"],
        description=body["course_description"],
        audience=body["audience"],
        kind=body["kind"],
        minutes=body["minutes"],
        target_kc_ids=[],
        ready=False,
    )
    fact = str(fields.get("fact") or body["core_truth"] or "")
    fragment = bool(node.kc_type == "factual" and is_fragment(body["last_answer"], fact))
    opening = not any(
        part.strip().lower().startswith("assistant:") for part in body["last_messages"].split(" | ")
    )
    moves = moves_for(node, profile, goal, fragment=fragment)
    prompt = build_kc_prompt(
        student=student,
        profile=profile,
        node=node,
        goal=goal,
        step=body["move_index"] - 1,
        moves=moves,
        opening=opening,
        choice_on_screen=body["choice_on_screen"] == "yes",
        prerequisite_status=body["prerequisite_status"],
        support_band=body["support_band"],
        course_position=body["course_position"],
        unit_complete=body["unit_close"] == "yes",
        course_complete=body["course_outro"] == "yes",
        attempts=body["attempts"],
        hint_tier=body["hint_tier"],
        reveals=body["reveals"],
        off_course_count=body["off_course_count"],
        affect=body["affect"],
        enrichment_turns=body["enrichment_turns"],
        help_requested=body["help_requested"] == "yes",
        minutes_used=body["minutes_used"],
        component_status=body["component_status"],
        stability=body["stability"],
        last_answer=body["last_answer"],
        last_misconception=body["last_misconception"],
        last_messages=body["last_messages"],
        rubric_met=list(body["rubric_met"]),
        redirect_pending=body["redirect_pending"] == "yes",
        fragment=fragment,
        others_known=False,
    )
    return prompt, profile, goal, moves


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
        direct, profile, goal, moves = _direct(taught)
        assert second.json()["system_prompt"] == direct["system_prompt"]
        assert second.json()["system_prompt"] != first.json()["system_prompt"]
        assert "Teach a little more first, then ask one question." in second.json()["system_prompt"]
        assert "Open on the question. Almost no explanation first." not in second.json()["system_prompt"]
        closed = _body(instructive=5, unit_close="yes")
        third = client.post("/kc/prompt-tester", json=closed)
        assert third.status_code == 200, third.text
        closed_direct, _, _, closed_moves = _direct(closed)
        assert third.json()["system_prompt"] == closed_direct["system_prompt"]
        assert third.json()["system_prompt"] != second.json()["system_prompt"]
        assert "End the unit in this reply." in third.json()["system_prompt"]
        index = min(max(taught["move_index"] - 1, 0), len(moves) - 1)
        move = moves[index]
        window = effective_window_name(profile, goal)
        assert second.json()["move_name"] == move.name
        assert second.json()["evidence"] == ", ".join(move.evidence)
        assert second.json()["effective_struggle_window"] == f"{window} ({struggle_tries(window)} tries)"
        assert second.json()["effective_enrichment"] == effective_enrichment(profile, goal)
        assert second.json()["asks_why"] == ("yes" if asks_why(profile, move) else "no")
        boxed = _body(kind="time_boxed", minutes=20, struggle_window="long", enrichment="offer")
        timed = client.post("/kc/prompt-tester", json=boxed)
        assert timed.status_code == 200, timed.text
        timed_direct, timed_profile, timed_goal, _ = _direct(boxed)
        assert timed.json()["system_prompt"] == timed_direct["system_prompt"]
        assert timed.json()["effective_struggle_window"].startswith("minimum")
        assert timed.json()["effective_enrichment"] == "direct"
        assert effective_window_name(timed_profile, timed_goal) == "minimum"
        assert effective_enrichment(timed_profile, timed_goal) == "direct"
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
        assert closed_moves
    finally:
        deleted = client.post(f"/kc/courses/{course_id}/delete", json={"password": DELETE_PASSWORD})
        assert deleted.status_code == 200, deleted.text
