"""Global AI safety settings, the Safety prompt section, and review events."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai_safety import BLOCKED_IDS, default_ai_safety
from app.database import SessionLocal
from app.kc_prompt import build_kc_prompt
from app.main import app
from app.models import AiSafetyEvent, KcGoal, KcNode, KcSession, Student, TutorProfile
from app.seed import seed
from app.studio import DELETE_PASSWORD

client = TestClient(app)


def _profile(**overrides: object) -> TutorProfile:
    values: dict[str, object] = {
        "id": "default",
        "instructive": 3,
        "persona": "curious-co-explorer",
        "lexicon": "middle-grade-vivid",
        "metaphors": "playground-sports",
        "sidekick": "bumbling-partner",
        "struggle_window": "standard",
        "anti_spoiler": True,
        "one_question": True,
        "use_interests": True,
        "stay_on_course": True,
        "growth_praise": True,
        "misconception_policy": "retry_once",
        "self_explanation": True,
        "enrichment": "on_request",
    }
    values.update(overrides)
    return TutorProfile(**values)


def _student(**overrides: object) -> Student:
    values: dict[str, object] = {
        "slug": "ada",
        "display_name": "Ada",
        "age": 10,
        "reading_level": "middle-grade",
        "modality": "story",
        "interests": ["birds"],
    }
    values.update(overrides)
    return Student(**values)


def _text(**overrides: object) -> str:
    student = overrides.pop("student", _student())
    safety = overrides.pop("safety", None)
    node = KcNode(
        code="zz-hidden-code",
        title="River fact",
        description="The color of this river.",
        core_truth="The river is blue.",
    )
    goal = KcGoal(code="rivers", title="Rivers", description="How a river moves.", audience="9-11", kind="mastery")
    bundle = build_kc_prompt(
        student=student,
        profile=_profile(),
        node=node,
        goal=goal,
        step=0,
        opening=True,
        choice_on_screen=False,
        prerequisite_status="",
        support_band="ready",
        course_position="1 of 1",
        unit_complete=False,
        course_complete=False,
        attempts=0,
        hint_tier="nudge",
        reveals=0,
        off_course_count=0,
        affect="",
        enrichment_turns=0,
        help_requested=False,
        minutes_used=0,
        component_status="unknown",
        stability="0",
        last_answer="",
        last_misconception="",
        last_messages="",
        rubric_met=[],
        redirect_pending=False,
        fragment=False,
        others_known=False,
        safety=safety,
    )
    assert "safety_flag" in bundle["response_schema"]["required"]
    return bundle["system_prompt"]


def test_safety_section_is_first_and_a_stricter_setting_changes_it() -> None:
    text = _text()
    assert text.startswith("Safety\n")
    assert text.index("\n\nThis turn\n") > 0
    assert "They override persona, child preferences, humor, and block rules." in text
    assert "first sign of a boundary" in text
    assert "Also return safety_flag as none" in text.split("What to return", 1)[1]
    standard = _text(safety={**default_ai_safety(), "safety_strictness": "standard"})
    assert "Safety strictness is standard" in standard
    assert standard != text
    young = _text(student=_student(age=7))
    assert "This child is under 8" in young
    assert "This child is under 8" not in _text(student=_student(age=10))
    off = _text(student=_student(age=7), safety={**default_ai_safety(), "age_scaling": False})
    assert "This child is under 8" not in off
    assert "Age scaling is off" in off


def _storm() -> Student:
    db = SessionLocal()
    try:
        seed(db)
        student = db.scalar(select(Student).where(Student.slug == "storm"))
        assert student is not None
        return student
    finally:
        db.close()


def _event_count(session_id: str | None = None) -> int:
    db = SessionLocal()
    try:
        stmt = select(func.count()).select_from(AiSafetyEvent)
        if session_id is not None:
            stmt = stmt.where(AiSafetyEvent.kc_session_id == uuid.UUID(session_id))
        return int(db.scalar(stmt) or 0)
    finally:
        db.close()


def _attempts(session_id: str) -> tuple[int, int | None, str]:
    db = SessionLocal()
    try:
        row = db.get(KcSession, uuid.UUID(session_id))
        assert row is not None
        return int(row.attempts or 0), row.score, row.status
    finally:
        db.close()


def _open(student_id: uuid.UUID, code: str) -> str:
    created = client.post(
        "/kc/courses",
        json={
            "code": code,
            "title": "ZZ safety",
            "description": "A safety check.",
            "audience": "9-11",
            "kind": "mastery",
            "minutes": None,
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    pushed = client.post(
        f"/kc/courses/{course_id}/push",
        json={"components": [{"code": f"{code}-fact", "title": "Safety fact"}]},
    )
    assert pushed.status_code == 200, pushed.text
    node_id = pushed.json()["components"][0]["id"]
    saved = client.put(
        f"/kc/nodes/{node_id}",
        json={
            "title": "Safety fact",
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
                    "data": {"topic": "Safety fact", "goal": "Explain the color."},
                }
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    ready = client.post(f"/kc/courses/{course_id}/ready")
    assert ready.status_code == 200, ready.text
    opened = client.post(
        "/kc/tutor/sessions",
        json={"student_id": str(student_id), "course_id": course_id, "kc_id": node_id},
    )
    assert opened.status_code == 200, opened.text
    return opened.json()["id"]


def _decide(
    session_id: str,
    *,
    flag: str,
    reply: str,
    decision: str = "complete",
    substep_passed: bool = True,
    block_complete: bool = True,
) -> dict:
    answered = client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": "The river is blue."})
    assert answered.status_code == 200, answered.text
    done = client.post(
        f"/kc/tutor/sessions/{session_id}/decision",
        json={
            "reply": reply,
            "decision": decision,
            "safety_flag": flag,
            "rubric_met": ["blk-1"] if substep_passed else [],
            "substep_passed": substep_passed,
            "block_complete": block_complete,
            "affect": "engaged",
            "confidence": "ok",
        },
    )
    assert done.status_code == 200, done.text
    return done.json()


def test_settings_defaults_invalid_values_and_events() -> None:
    storm = _storm()
    code = f"zz-safety-{uuid.uuid4().hex[:8]}"
    client.post("/ai-safety/reset")
    try:
        loaded = client.get("/ai-safety")
        assert loaded.status_code == 200, loaded.text
        settings = loaded.json()["settings"]
        assert settings["safety_strictness"] == "strict"
        assert settings["age_scaling"] is True
        assert settings["flag_safety_moments"] is True
        assert settings["no_secrets"] is True
        assert set(settings["blocked_topics"]) == set(BLOCKED_IDS)
        assert loaded.json()["safety_text"].startswith("Safety\n")

        rejected = client.put("/ai-safety", json={"safety_strictness": "loose"})
        assert rejected.status_code == 422, rejected.text
        assert client.get("/ai-safety").json()["settings"]["safety_strictness"] == "strict"

        preview = client.post(
            "/ai-safety/preview",
            json={**settings, "safety_strictness": "standard"},
        )
        assert preview.status_code == 200, preview.text
        assert "Safety strictness is standard" in preview.json()["safety_text"]
        assert client.get("/ai-safety").json()["settings"]["safety_strictness"] == "strict"

        session_id = _open(storm.id, code)
        before = _event_count(session_id)
        quiet = _decide(
            session_id,
            flag="none",
            reply="Yes. The river is blue.",
            decision="stay",
            substep_passed=False,
            block_complete=False,
        )
        assert quiet.get("safety_flag", "none") == "none"
        assert _event_count(session_id) == before
        attempts, score, status = _attempts(session_id)
        assert attempts >= 1

        flagged = _decide(session_id, flag="distress", reply="I am glad you told me. Please tell a trusted adult.")
        assert flagged["safety_flag"] == "distress"
        assert flagged["unit_complete"] is False
        assert flagged["passed"] is False
        held_attempts, held_score, held_status = _attempts(session_id)
        assert held_attempts == attempts
        assert held_score == score
        assert held_status == status
        assert _event_count(session_id) == before + 1

        listed = client.get("/safety-events", params={"session_id": session_id, "category": "distress", "reviewed": False})
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert body["total"] == 1
        event = body["events"][0]
        assert event["category"] == "distress"
        assert event["student_display_name"] == "Storm"
        assert event["course_title"] == "ZZ safety"
        assert event["component_title"] == "Safety fact"
        assert event["child_message"] == "The river is blue."
        assert "trusted adult" in event["tutor_reply"]
        assert event["reviewed_at"] is None
        other = client.get("/safety-events", params={"session_id": session_id, "category": "other"})
        assert other.json()["total"] == 0

        long_reply = "x" * 600
        _decide(session_id, flag="manipulation", reply=long_reply)
        trimmed = client.get("/safety-events", params={"session_id": session_id, "category": "manipulation"})
        assert len(trimmed.json()["events"][0]["tutor_reply"]) == 500

        reviewed = client.post(f"/safety-events/{event['id']}/review", json={"reviewed_by": "admin"})
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["reviewed_by"] == "admin"
        assert reviewed.json()["reviewed_at"]
        still_open = client.get("/safety-events", params={"session_id": session_id, "reviewed": False})
        assert all(item["id"] != event["id"] for item in still_open.json()["events"])
        closed = client.get("/safety-events", params={"session_id": session_id, "reviewed": True})
        assert any(item["id"] == event["id"] for item in closed.json()["events"])

        client.put("/ai-safety", json={"flag_safety_moments": False})
        quiet_count = _event_count(session_id)
        skipped = _decide(session_id, flag="personal_info", reply="Please do not share that here.")
        assert skipped["safety_flag"] == "personal_info"
        assert skipped["unit_complete"] is False
        assert _event_count(session_id) == quiet_count
        missing = client.post(f"/safety-events/{uuid.uuid4()}/review", json={})
        assert missing.status_code == 404
    finally:
        client.post("/ai-safety/reset")
        course = client.get("/kc/courses")
        for item in course.json():
            if item["code"] == code:
                client.post(f"/kc/courses/{item['id']}/delete", json={"password": DELETE_PASSWORD})
