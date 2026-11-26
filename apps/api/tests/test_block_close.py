"""Stages 0–3. Requirement scores for retrieval, worked example, explanation, and curiosity.

No model call. Topic, question, and the other block types stay on the legacy score.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.block_score import score_supported_turn
from app.database import SessionLocal
from app.kc_loop import resolve_block_turn
from app.kc_prompt import initial_block_state
from app.learn_stars import stars_from_units
from app.main import app
from app.models import (
    KcCourseRun,
    KcMessage,
    KcRequirement,
    KcSession,
    KcState,
    KcTurnReceipt,
    KcVisit,
    Parent,
    ParentStudent,
    default_kc_tutor_config,
)
from app.parents import session_star_unit
from tests.test_kc import _clear_progress, _make, _ready, _spec, _storm, _wipe_zz

client = TestClient(app)
CFG = default_kc_tutor_config()
CONTINUE = "No final questions — let's continue!"
WHY = "Firms change prices more often, so the expense adds up."

RECALL = {
    "id": "menu",
    "type": "retrieval_check",
    "data": {
        "recall_prompt": "What is a menu cost in the context of inflation?",
        "expected_fact": "A menu cost is the expense incurred by firms when they change their prices due to inflation.",
        "elaborative_why_prompt": "Why do menu costs matter more when inflation is high?",
        "expected_why_rationale": WHY,
    },
}
WORKED = {
    "id": "routes",
    "type": "worked_example",
    "data": {
        "problem_statement": "Maya compares a bus route's on-time record with one dramatic delay.",
        "steps": [
            {
                "step_text": "quantitative data than to one dramatic experience",
                "rationale": "A long record is steadier than one memorable trip.",
            },
            {
                "step_text": "the count of on-time buses",
                "rationale": "The long record is the evidence.",
            },
        ],
        "faded_step_index": 0,
        "solo_problem": "Jon checks many lock codes. Leila tries one meaningful number. Who is more reliable?",
        "solo_expected_answer": "Jon is more reliable because he checks many codes.",
    },
}
EXPLAIN = {
    "id": "costs",
    "type": "explanation",
    "data": {
        "block_title": "Costs of inflation",
        "topics": [
            {
                "id": "named",
                "title": "Specific costs",
                "explanation": "Menu costs show up when firms reprint prices.",
                "key_points": "Menu costs.",
            }
        ],
        "summary_takeaway": "Inflation makes price changes expensive.",
    },
}
WONDER = {
    "id": "wonder",
    "type": "curiosity",
    "data": {
        "phenomenon_hook": "A cafe reprints its menu every month.",
        "prediction_question": "What do you think that costs them?",
        "bridge_to_unit": "That expense is a menu cost.",
    },
}
GOAL = {
    "id": "goal",
    "type": "topic_goal",
    "data": {"topic": "Scarcity", "goal": "Explain why scarcity forces choices."},
}
TOPIC = {
    "id": "river",
    "type": "topic_goal",
    "data": {
        "topic": "Rivers",
        "goal": "Say the river is blue.",
        "acceptance_criteria": "The river is blue.",
    },
}
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}


def _legacy(**overrides):
    body = dict(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(TOPIC), dict(NEXT)],
        step=0,
        active_block_state={"substep": "main"},
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer="The river is blue.",
        prior_tutor="",
    )
    body.update(overrides)
    return body


def test_shipped_exits_stay_on_the_legacy_resolver() -> None:
    """Reveal-stop, explanation-to-goal, and a clean middle pass keep their current behavior."""
    revealed = resolve_block_turn(
        **_legacy(
            blocks=[dict(WORKED), dict(NEXT)],
            active_block_state={"substep": "faded_step"},
            answer="the scary story matters more",
            move_attempts=1,
        )
    )
    assert revealed.next_block_state["substep"] == "faded_step"
    assert revealed.next_block_state["revealed_substep"] is True
    assert revealed.block_results == []

    opened = initial_block_state(GOAL, CFG, previous=EXPLAIN)
    assert opened["substep"] == "main"
    assert initial_block_state(GOAL, CFG)["substep"] == "explain"

    closed = resolve_block_turn(**_legacy(substep_passed=True))
    assert closed.advance_block is True
    assert closed.next_block_state.get("substep") != "summary_check"


def _walk(block: dict, turns: list[tuple[str, bool]]) -> tuple[dict, object]:
    state = initial_block_state(block, CFG)
    state["requirements"] = []
    from app.block_score import freeze_requirements

    state["requirements"] = freeze_requirements(block, CFG)
    resolution = None
    results: list[dict] = []
    move = 0
    reveals = 0
    rubric: list[str] = []
    for answer, passed in turns:
        resolution = score_supported_turn(
            **_legacy(
                blocks=[dict(block)],
                active_block_state=dict(state),
                block_results=list(results),
                answer=answer,
                substep_passed=passed,
                move_attempts=move,
                reveals=reveals,
                stored_rubric=list(rubric),
            )
        )
        state = dict(resolution.next_block_state)
        results = list(resolution.block_results)
        move = resolution.move_attempts
        reveals = resolution.reveals
        rubric = list(resolution.rubric_met)
    assert resolution is not None
    return state, resolution


def _by_key(requirements: list[dict]) -> dict[str, dict]:
    return {str(row.get("key")): row for row in requirements}


def test_menu_cost_retrieval_is_fragile_with_both_observations() -> None:
    _state, resolution = _walk(RECALL, [("idk", False), ("idk", False), (WHY, True), (CONTINUE, False)])
    assert resolution.unit_complete is True
    assert resolution.mark_known is False
    assert resolution.mark_fragile is True
    assert resolution.passed is False
    row = resolution.block_results[-1]
    assert row["verdict"] == "fragile"
    assert row["outcome"] == "fragile"
    assert row["passed_on_first_try"] is False
    requirements = _by_key(row["requirements"])
    assert requirements["recall"]["observation"] == "assisted"
    assert requirements["recall"]["attempts"] == 2
    assert requirements["elaborate_why"]["observation"] == "independent"
    assert requirements["elaborate_why"]["attempts"] == 1
    unit = session_star_unit("completed", resolution.block_results, resolution.reveals)
    stars = stars_from_units([unit])
    assert stars["stars"] == 35
    assert stars["star_first_try"] == 0
    assert stars["star_crown"] == 0
    assert "Recall was assisted." in row["summary"]
    assert "The reason was independent." in row["summary"]


def _course(code: str, blocks: list[dict], *, second: dict | None = None) -> dict:
    components = [_spec(f"{code}-a", "Menu costs", blocks=blocks)]
    if second is not None:
        components.append(
            _spec(f"{code}-b", "Next idea", blocks=[second], prerequisite_codes=[f"{code}-a"])
        )
    return _ready(_make(code, title=code), components)


def _open(course: dict, code: str) -> dict:
    storm = _storm()
    opened = client.post(
        "/kc/tutor/sessions",
        json={
            "student_id": str(storm.id),
            "course_id": course["id"],
            "kc_id": next(item["id"] for item in course["components"] if item["code"] == code),
        },
    )
    assert opened.status_code == 200, opened.text
    return opened.json()


def _grade(session_id: str, answer: str, revision: int, *, passed: bool = False, reply: str = "Noted.") -> dict:
    turn_id = str(uuid.uuid4())
    claimed = client.post(
        f"/kc/tutor/sessions/{session_id}/turn",
        json={"answer": answer, "turn_id": turn_id, "revision": revision},
    )
    assert claimed.status_code == 200, claimed.text
    decided = client.post(
        f"/kc/tutor/sessions/{session_id}/decision",
        json={
            "reply": reply,
            "decision": "stay",
            "turn_id": turn_id,
            "substep_passed": passed,
            "rubric_met": [],
        },
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()
    body["_turn_id"] = turn_id
    return body


def _parent_progress(course_id: str) -> dict:
    storm = _storm()
    parent = client.post("/parents", json={"name": "ZZ Block Close"}).json()
    linked = client.put(f"/parents/{parent['id']}/students", json={"student_ids": [str(storm.id)]})
    assert linked.status_code == 200, linked.text
    progress = client.get(f"/parents/{parent['id']}/children/{storm.id}/courses/{course_id}/progress")
    assert progress.status_code == 200, progress.text
    db = SessionLocal()
    try:
        db.execute(ParentStudent.__table__.delete().where(ParentStudent.parent_id == uuid.UUID(parent["id"])))
        db.execute(Parent.__table__.delete().where(Parent.id == uuid.UUID(parent["id"])))
        db.commit()
    finally:
        db.close()
    return progress.json()


def _messages(session_id: str) -> list[KcMessage]:
    db = SessionLocal()
    try:
        return list(
            db.scalars(select(KcMessage).where(KcMessage.session_id == uuid.UUID(session_id)).order_by(KcMessage.seq))
        )
    finally:
        db.close()


def test_retrieval_trace_is_stored_and_a_parent_reads_fragile() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-close", [RECALL])
    try:
        opened = _open(course, "zz-block-close-a")
        assert opened["scoring_version"] == 2
        assert opened["verdict"] is None
        assert opened["revision"] == 0
        session_id = opened["id"]

        claimed = client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "idk", "turn_id": "turn-recall-1", "revision": 0},
        )
        assert claimed.status_code == 200, claimed.text
        assert [row.role for row in _messages(session_id)] == []

        first = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={"reply": "Try once more.", "decision": "stay", "turn_id": "turn-recall-1", "substep_passed": False},
        )
        assert first.status_code == 200, first.text
        assert [row.role for row in _messages(session_id)] == ["user", "assistant"]
        assert first.json()["verdict"] is None
        again = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={"reply": "A different reply.", "decision": "stay", "turn_id": "turn-recall-1", "substep_passed": True},
        )
        assert again.status_code == 200, again.text
        assert again.json()["reply"] == "Try once more."
        assert len(_messages(session_id)) == 2

        conflict = client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "something else", "turn_id": "turn-recall-1", "revision": 0},
        )
        assert conflict.status_code == 409
        stale = client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "idk", "turn_id": "turn-recall-2", "revision": 0},
        )
        assert stale.status_code == 409
        replay = client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "idk", "turn_id": "turn-recall-1", "revision": 0},
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["reply"] == "Try once more."

        second = _grade(session_id, "idk", first.json()["revision"], reply="A menu cost is the expense of changing prices.")
        assert second["active_substep"] == "elaborate_why"
        why = _grade(session_id, WHY, second["revision"], passed=True, reply="Why does that add up?")
        assert why["active_substep"] == "summary_check"
        assert CONTINUE in (why.get("actions") or [])
        refreshed = client.get(f"/kc/tutor/sessions/{session_id}")
        assert refreshed.status_code == 200
        assert refreshed.json()["active_substep"] == "summary_check"
        assert CONTINUE in (refreshed.json().get("actions") or [])
        before = _messages(session_id)
        rubric_before = _session(session_id).rubric_met
        finished = _grade(session_id, CONTINUE, why["revision"], reply="We'll use that next.")
        assert finished["status"] == "completed"
        assert finished["verdict"] == "fragile"
        assert finished["passed"] is False
        assert finished["unit_complete"] is True
        assert len(_messages(session_id)) == len(before) + 2
        stored = _session(session_id)
        assert stored.verdict == "fragile"
        assert stored.rubric_met == rubric_before
        row = stored.block_results[-1]
        requirements = _by_key(row["requirements"])
        assert requirements["recall"]["observation"] == "assisted"
        assert requirements["recall"]["attempts"] == 2
        assert requirements["elaborate_why"]["observation"] == "independent"
        assert requirements["elaborate_why"]["attempts"] == 1
        state = _component_state(storm.id, stored.kc_id)
        assert state is not None
        assert state.status == "fragile"
        assert state.status != "known"

        progress = _parent_progress(course["id"])
        assert progress["stars"] == 35
        assert progress["star_first_try"] == 0
        assert progress["star_crown"] == 0
        unit = progress["units"][0]
        assert unit["mastery"] == "fragile"
        assert unit["child_status"] == "Completed"
        detail = unit["block_details"][0]
        observations = {item["key"]: item for item in detail["observations"]}
        assert observations["recall"]["observation"] == "assisted"
        assert observations["elaborate_why"]["observation"] == "independent"
        assert "Recall was assisted." in unit["score_justification"]
        assert "The reason was independent." in unit["score_justification"]
        assert _visit_rows(session_id) >= 1
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_identical_retry_conflict_and_speech_leave_one_result() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-receipt", [RECALL])
    try:
        opened = _open(course, "zz-block-receipt-a")
        session_id = opened["id"]
        first = client.post(
            f"/kc/tutor/sessions/{session_id}/speech",
            json={"phase": "claim", "turn_id": "speak-a", "revision": 0, "content": ""},
        )
        assert first.status_code == 200, first.text
        assert first.json()["opening_key"]
        assert first.json()["replayed"] is False
        assert _session(session_id).active_block_state.get("generated_mcq") is None
        second = client.post(
            f"/kc/tutor/sessions/{session_id}/speech",
            json={"phase": "claim", "turn_id": "speak-b", "revision": 0, "content": ""},
        )
        assert second.status_code == 200, second.text
        assert second.json()["held"] is True
        assert second.json()["opening_key"] == first.json()["opening_key"]
        assert _receipt_count(session_id, "speech") == 1

        winner = client.post(
            f"/kc/tutor/sessions/{session_id}/speech",
            json={
                "phase": "commit",
                "turn_id": "speak-a",
                "revision": 0,
                "content": "What is a menu cost?",
                "generated_mcq": {"correct_index": 0, "choices": [{"id": "a", "text": "Prices"}]},
            },
        )
        assert winner.status_code == 200, winner.text
        late = client.post(
            f"/kc/tutor/sessions/{session_id}/speech",
            json={
                "phase": "commit",
                "turn_id": "speak-b",
                "revision": 0,
                "content": "A different opening.",
                "generated_mcq": {"correct_index": 1, "choices": [{"id": "b", "text": "Wages"}]},
            },
        )
        assert late.status_code == 200, late.text
        assert late.json()["messages"] == winner.json()["messages"]
        stored = _session(session_id)
        assert stored.active_block_state["generated_mcq"]["correct_index"] == 0
        assert [row.role for row in _messages(session_id)] == ["assistant"]
        retry = client.post(
            f"/kc/tutor/sessions/{session_id}/speech",
            json={
                "phase": "commit",
                "turn_id": "speak-a",
                "revision": 0,
                "content": "What is a menu cost?",
                "generated_mcq": {"correct_index": 2, "choices": [{"id": "c", "text": "Rent"}]},
            },
        )
        assert retry.status_code == 200, retry.text
        assert _session(session_id).active_block_state["generated_mcq"]["correct_index"] == 0
        assert _receipt_count(session_id, "speech") == 1
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_worked_example_reveal_stays_then_solo_is_fragile() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-worked", [WORKED])
    try:
        opened = _open(course, "zz-block-worked-a")
        assert opened["scoring_version"] == 2
        first = _grade(opened["id"], "idk", 0)
        second = _grade(opened["id"], "idk", first["revision"])
        assert second["active_substep"] == "faded_step"
        assert _session(opened["id"]).block_results == []
        solo = _grade(opened["id"], "ok", second["revision"], reply="Who is more reliable?")
        assert solo["active_substep"] == "solo_solve"
        assert solo["loop_result"]["attempt_counted"] is False
        finished = _grade(
            opened["id"],
            "Jon is more reliable because he checks many codes.",
            solo["revision"],
            passed=True,
            reply="That's the solo problem.",
        )
        assert finished["verdict"] == "fragile"
        assert finished["passed"] is False
        requirements = _by_key(_session(opened["id"]).block_results[-1]["requirements"])
        assert requirements["faded_step"]["observation"] == "assisted"
        assert requirements["solo_solve"]["observation"] == "independent"
        progress = _parent_progress(course["id"])
        assert progress["units"][0]["mastery"] == "fragile"
        assert progress["star_crown"] == 0
        observations = {item["key"]: item["observation"] for item in progress["units"][0]["block_details"][0]["observations"]}
        assert observations == {"faded_step": "assisted", "solo_solve": "independent"}
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_explanation_and_curiosity_finish_unassessed_and_open_the_next_topic() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-explain", [EXPLAIN], second=WONDER)
    try:
        opened = _open(course, "zz-block-explain-a")
        assert opened["scoring_version"] == 2
        finished = _grade(opened["id"], "Got it - move on", 0, reply="That's the cost.")
        assert finished["status"] == "completed"
        assert finished["verdict"] == "unassessed"
        assert finished["passed"] is False
        state = _component_state(storm.id, uuid.UUID(opened["kc_id"]))
        assert state is not None
        assert state.status == "unknown"
        assert state.result["verdict"] == "unassessed"
        progress = _parent_progress(course["id"])
        unit = next(item for item in progress["units"] if item["code"] == "zz-block-explain-a")
        assert unit["mastery"] == "unassessed"
        assert unit["status"] == "completed"
        assert progress["stars"] == 35
        assert progress["star_crown"] == 0
        assert "Finished the explanation." in unit["score_justification"]
        nxt = next(item for item in progress["units"] if item["code"] == "zz-block-explain-b")
        assert nxt["status"] != "not_started" or progress["cards"][0]["code"] == "zz-block-explain-b"
        assert any(card["code"] == "zz-block-explain-b" for card in progress["cards"])

        wonder = _open(course, "zz-block-explain-b")
        assert wonder["scoring_version"] == 2
        predicted = _grade(wonder["id"], "I think reprinting costs them money.", 0, passed=True, reply="What else?")
        done = _grade(wonder["id"], CONTINUE, predicted["revision"], reply="That expense is a menu cost.")
        assert done["verdict"] == "unassessed"
        wonder_state = _component_state(storm.id, uuid.UUID(wonder["kc_id"]))
        assert wonder_state is not None
        assert wonder_state.status == "unknown"
        assert wonder_state.result["verdict"] == "unassessed"
        later = _parent_progress(course["id"])
        hook = next(item for item in later["units"] if item["code"] == "zz-block-explain-b")
        assert hook["mastery"] == "unassessed"
        assert "Finished the curiosity hook." in hook["score_justification"]
        assert later["star_crown"] == 0
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_a_later_unassessed_visit_keeps_an_earlier_known_result() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-keep", [EXPLAIN])
    try:
        opened = _open(course, "zz-block-keep-a")
        db = SessionLocal()
        try:
            state = db.scalar(select(KcState).where(KcState.student_id == storm.id, KcState.kc_id == uuid.UUID(opened["kc_id"])))
            if state is None:
                state = KcState(student_id=storm.id, kc_id=uuid.UUID(opened["kc_id"]), status="known", stability=1)
                db.add(state)
            state.status = "known"
            state.result = {"status": "known", "verdict": "known", "justification": "Kept."}
            db.commit()
        finally:
            db.close()
        finished = _grade(opened["id"], "Got it - move on", opened["revision"], reply="That's the explanation.")
        assert finished["verdict"] == "unassessed"
        state = _component_state(storm.id, uuid.UUID(opened["kc_id"]))
        assert state is not None
        assert state.status == "known"
        assert state.result["justification"] == "Kept."
        progress = _parent_progress(course["id"])
        assert progress["units"][0]["mastery"] == "known"
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_recovery_uses_this_sessions_requirements() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-recover", [RECALL])
    try:
        opened = _open(course, "zz-block-recover-a")
        db = SessionLocal()
        try:
            row = db.get(KcSession, uuid.UUID(opened["id"]))
            assert row is not None
            row.block_results = [
                {
                    "id": "menu",
                    "block_id": "menu",
                    "block_type": "retrieval_check",
                    "outcome": "fragile",
                    "verdict": "fragile",
                    "requirements": [
                        {"key": "recall", "role": "assessed", "observation": "assisted", "attempts": 2, "label": "Recall"},
                        {
                            "key": "elaborate_why",
                            "role": "assessed",
                            "observation": "independent",
                            "attempts": 1,
                            "label": "Reason",
                        },
                    ],
                }
            ]
            row.status = "in_progress"
            state = KcState(
                student_id=storm.id,
                kc_id=row.kc_id,
                status="known",
                stability=1,
                result={"status": "known", "justification": "Previous."},
            )
            db.add(state)
            db.commit()
            session_id = row.id
            node_id = row.kc_id
        finally:
            db.close()
        from app.kc import _close_finished_walk, _node_or_404

        db = SessionLocal()
        try:
            session = db.get(KcSession, session_id)
            node = _node_or_404(db, node_id)
            _close_finished_walk(db, session, node, "Closed from the requirements.")
            db.commit()
            assert session.verdict == "fragile"
            assert session.verdict != "known"
        finally:
            db.close()
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_an_in_progress_session_is_not_upgraded() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-running", [RECALL])
    try:
        opened = _open(course, "zz-block-running-a")
        db = SessionLocal()
        try:
            row = db.get(KcSession, uuid.UUID(opened["id"]))
            assert row is not None
            row.scoring_version = 1
            row.active_block_state = {"substep": "recall"}
            db.commit()
        finally:
            db.close()
        again = _open(course, "zz-block-running-a")
        assert again["id"] == opened["id"]
        assert again["scoring_version"] == 1
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_mixed_components_stay_on_the_legacy_score() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-mixed", [TOPIC, RECALL])
    try:
        mixed = _open(course, "zz-block-mixed-a")
        assert mixed["scoring_version"] == 1
        assert mixed["actions"] is None
        db = SessionLocal()
        try:
            row = db.get(KcSession, uuid.UUID(mixed["id"]))
            assert row is not None
            row.scoring_version = 1
            db.commit()
        finally:
            db.close()
        again = _open(course, "zz-block-mixed-a")
        assert again["id"] == mixed["id"]
        assert again["scoring_version"] == 1
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_restart_hides_the_old_completion_from_the_current_run() -> None:
    storm = _storm()
    _clear_progress(storm.id)
    course = _course("zz-block-run", [RECALL])
    try:
        opened = _open(course, "zz-block-run-a")
        first = _grade(opened["id"], "idk", 0)
        second = _grade(opened["id"], "idk", first["revision"])
        why = _grade(opened["id"], WHY, second["revision"], passed=True)
        finished = _grade(opened["id"], CONTINUE, why["revision"])
        assert finished["verdict"] == "fragile"
        before = _session(opened["id"])
        restarted = client.post(f"/kc/tutor/courses/{course['id']}/restart", json={"student_id": str(storm.id)})
        assert restarted.status_code == 200, restarted.text
        assert restarted.json()["known"] == 0
        body = restarted.json()
        assert body["units"][0]["mastery"] != "fragile"
        assert body["stars"] == 0
        kept = _session(opened["id"])
        assert kept.status == "completed"
        assert kept.course_run_id == before.course_run_id
        latest = _latest_run(storm.id, uuid.UUID(course["id"]))
        assert latest is not None
        assert kept.course_run_id != latest
    finally:
        _clear_progress(storm.id)
        _wipe_zz()


def test_an_unfamiliar_outcome_is_not_passed_and_not_a_first_try() -> None:
    from types import SimpleNamespace

    from app.kc import _build_block_details

    unit = session_star_unit("completed", [{"outcome": "banana", "attempts": 1}], 0)
    stars = stars_from_units([unit])
    assert unit["mastery"] != "known"
    assert unit["first_try_blocks_count"] == 0
    assert unit["completed_blocks"] == 0
    assert stars["star_first_try"] == 0
    assert stars["star_crown"] == 0
    legacy = session_star_unit("completed", [{"outcome": "passed", "attempts": 1}], 0)
    assert stars_from_units([legacy])["stars"] == 55

    node = SimpleNamespace(title="Menu", blocks=[dict(RECALL)])
    session = SimpleNamespace(
        block_results=[{"id": "menu", "outcome": "banana", "attempts": 1}],
        step=0,
        active_block_state={},
        move_attempts=0,
    )
    goal = SimpleNamespace(kind="mastery")
    details = _build_block_details(node, session, CFG, goal, unit_status="completed")
    assert details[0]["outcome"] == "banana"
    assert details[0]["passed_on_first_try"] is False


def _session(session_id: str) -> KcSession:
    db = SessionLocal()
    try:
        row = db.get(KcSession, uuid.UUID(session_id))
        assert row is not None
        db.expunge(row)
        return row
    finally:
        db.close()


def _component_state(student_id, kc_id) -> KcState | None:
    db = SessionLocal()
    try:
        row = db.scalar(select(KcState).where(KcState.student_id == student_id, KcState.kc_id == kc_id))
        if row is not None:
            db.expunge(row)
        return row
    finally:
        db.close()


def _receipt_count(session_id: str, route: str) -> int:
    db = SessionLocal()
    try:
        return int(
            db.scalar(
                select(func.count())
                .select_from(KcTurnReceipt)
                .where(KcTurnReceipt.session_id == uuid.UUID(session_id), KcTurnReceipt.route == route)
            )
            or 0
        )
    finally:
        db.close()


def _visit_rows(session_id: str) -> int:
    db = SessionLocal()
    try:
        visits = int(
            db.scalar(select(func.count()).select_from(KcVisit).where(KcVisit.session_id == uuid.UUID(session_id)))
            or 0
        )
        reqs = int(
            db.scalar(
                select(func.count()).select_from(KcRequirement).where(KcRequirement.session_id == uuid.UUID(session_id))
            )
            or 0
        )
        return visits + reqs
    finally:
        db.close()


def _latest_run(student_id, goal_id) -> uuid.UUID | None:
    db = SessionLocal()
    try:
        row = db.scalar(
            select(KcCourseRun)
            .where(KcCourseRun.student_id == student_id, KcCourseRun.goal_id == goal_id)
            .order_by(KcCourseRun.created_at.desc())
        )
        return None if row is None else row.id
    finally:
        db.close()
