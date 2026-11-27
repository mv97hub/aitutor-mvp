"""A stuck synthetic learner gets two nudges only while the chat may continue."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.harness import claim_chat, prepare_harness_turn, record_turn
from app.models import HarnessChat, HarnessEvaluation, HarnessRun, HarnessTurn, KcGoal, KcNode, KcSession, KcTurnReceipt, Student


@pytest.mark.parametrize("reason, already_nudging", [
    ("cap", False), ("luna_ceiling", False), ("safety", False), ("route_error", False),
    ("safety", True),
])
def test_recovered_turn_stops_even_when_the_stuck_limit_is_reached(reason, already_nudging):
    with SessionLocal() as db:
        key = uuid4().hex
        student = Student(slug=key, display_name="Test learner", is_test=True)
        goal, node = KcGoal(code=key, title="Test course"), KcNode(code=key, title="Test component")
        run = HarnessRun(status="running", plan={
            "stuck_limit": 2, "stop_on_safety": True, "chat_cap_cents": 1, "luna_token_ceiling": 1000,
        })
        db.add_all([student, goal, node, run])
        db.flush()
        session = KcSession(student_id=student.id, goal_id=goal.id, kc_id=node.id, revision=1)
        db.add(session)
        db.flush()
        chat = HarnessChat(run_id=run.id, session_id=session.id, status="running", claim_generation=1)
        db.add(chat)
        db.flush()

        same_step = {"status": "in_progress", "block_id": "cpi", "substep": "recall"}
        previous = dict(same_step, error="Empty reply") if reason == "route_error" else same_step
        assert record_turn(db, chat.id, {"intent": "guess", "session_after": previous})["stop"] == ""
        if already_nudging:
            signal = record_turn(db, chat.id, {"intent": "guess", "session_after": same_step})
            assert signal["stop"] == "" and signal["pending_nudges"] == 2

        tokens = {}
        if reason == "cap":
            tokens = {"model": "gpt-4.1-mini", "input_tokens": 25_000}  # Exactly one cent.
        if reason == "luna_ceiling":
            tokens = {"model": "gpt-6-luna", "input_tokens": 1000}
        seq = chat.turn_count + 1
        submission = {"turn_id": str(uuid4()), "seq": seq, "revision": session.revision, "child_text": "Maybe.",
                      "intent": "nudge" if already_nudging else "guess", "child_tokens": tokens, "session_before": same_step}
        prepare_harness_turn(db, chat.id, {"seq": seq, "claim_generation": 1, "submission": submission})
        db.add(KcTurnReceipt(session_id=session.id, client_turn_id=submission["turn_id"], route="answer",
                             revision=session.revision, status="committed", payload=submission["child_text"],
                             result={"revision": session.revision + 1}))
        session.revision += 1
        db.flush()
        after = dict(same_step, delivery_status="recovered", tutor_reply="Think about prices.")
        if reason == "safety":
            after["safety_flag"] = "manipulation"
        if reason == "route_error":
            after.update(delivery_status="committed_empty", tutor_reply="", error="Empty reply")
        body = {**submission, "session_after": after, "claim_generation": 1}
        assert record_turn(db, chat.id, body)["stop"] == reason
        assert chat.ended_how == reason and run.status == "completed"
        replay = record_turn(db, chat.id, body)
        assert replay["replayed"] and replay["stop"] == reason
        assert chat.turn_count == seq and chat.pending_turn is None
        assert db.get(HarnessTurn, submission["turn_id"]).seq == seq
        checks = db.scalars(select(HarnessEvaluation).where(HarnessEvaluation.chat_id == chat.id)).one().checks
        assert checks["ended_how"] == reason and checks["turns"] == seq
        assert claim_chat(db, run.id) is None
        with pytest.raises(HTTPException, match="409"):
            prepare_harness_turn(db, chat.id, {"seq": seq + 1, "claim_generation": 1, "submission": {}})


@pytest.mark.parametrize(("ending", "cost", "luna", "expected"), [
    ("completed", "0.0099999", 999, False),
    ("completed", "0.0100000", 999, True),
    ("turn_limit", None, 1000, True),
    ("cap", None, 0, True),
    ("luna_ceiling", None, 0, True),
    ("run_cap", None, 0, True),
])
def test_judge_admission_uses_saved_ending_and_exact_chat_limits(ending, cost, luna, expected):
    from app.harness import get_chat

    with SessionLocal() as db:
        run = HarnessRun(status="completed", plan={"chat_cap_cents": 1, "luna_token_ceiling": 1000})
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, status="completed", ended_how=ending, cost_usd=cost, luna_tokens=luna)
        db.add(chat)
        db.flush()
        detail = get_chat(db, chat.id)
        assert detail["judge_budget_reached"] is expected
        assert not db.is_modified(chat) and not db.is_modified(run)
