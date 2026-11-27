"""A stuck synthetic learner gets two nudges only while the chat may continue."""

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.harness import claim_chat, dispatch_harness_turn, download_chat, get_chat, prepare_harness_turn, record_turn, save_evaluation
from app.models import HarnessChat, HarnessEvaluation, HarnessRun, HarnessTurn, KcGoal, KcNode, KcSession, KcTurnReceipt, Student

from app.token_usage import record_token_usage


def running_chat(db, *, run_cap=False):
    key = uuid4().hex
    student = Student(slug=key, display_name="Test learner", is_test=True)
    goal, node = KcGoal(code=key, title="Test course"), KcNode(code=key, title="Test component")
    run = HarnessRun(status="running", plan={
        "stuck_limit": 2, "stop_on_safety": True, "chat_cap_cents": 1, "luna_token_ceiling": 1000,
    })
    if run_cap:
        run.plan = {**run.plan, "run_cap_cents": 1}
    db.add_all([student, goal, node, run])
    db.flush()
    session = KcSession(student_id=student.id, goal_id=goal.id, kc_id=node.id, revision=1)
    db.add(session)
    db.flush()
    chat = HarnessChat(run_id=run.id, session_id=session.id, status="running", claim_generation=1)
    db.add(chat)
    db.flush()
    return run, session, chat


@pytest.mark.parametrize("reason, queued_nudges", [
    ("cap", 0), ("luna_ceiling", 0), ("safety", 0), ("route_error", 0),
    ("safety", 2), ("run_cap", 0), ("run_cap", 1),
])
def test_recovered_turn_stops_even_when_the_stuck_limit_is_reached(reason, queued_nudges):
    with SessionLocal() as db:
        run, session, chat = running_chat(db, run_cap=reason == "run_cap")

        same_step = {"status": "in_progress", "block_id": "cpi", "substep": "recall"}
        previous = dict(same_step, error="Empty reply") if reason == "route_error" else same_step
        assert record_turn(db, chat.id, {"intent": "guess", "session_after": previous})["stop"] == ""
        if queued_nudges:
            signal = record_turn(db, chat.id, {"intent": "guess", "session_after": same_step})
            assert signal["stop"] == "" and signal["pending_nudges"] == 2
            if queued_nudges == 1:
                first = record_turn(db, chat.id, {"intent": "nudge", "session_after": same_step})
                assert first["stop"] == "" and first["pending_nudges"] == 1

        tokens = {}
        if reason == "cap":
            tokens = {"model": "gpt-4.1-mini", "input_tokens": 25_000}  # Exactly one cent.
        if reason == "luna_ceiling":
            tokens = {"model": "gpt-6-luna", "input_tokens": 1000}
        seq = chat.turn_count + 1
        submission = {"turn_id": str(uuid4()), "seq": seq, "revision": session.revision, "child_text": "Maybe.",
                      "intent": "nudge" if queued_nudges else "guess", "child_tokens": {}, "session_before": same_step}
        submission["dispatch_state"] = "prepared"
        prepare_harness_turn(db, chat.id, {"seq": seq, "claim_generation": 1, "submission": submission})
        assert dispatch_harness_turn(db, chat.id, UUID(submission["turn_id"]), 1)["action"] == "send"
        if tokens:
            # This tutor usage becomes known after dispatch.
            record_token_usage(db, session, kind="answer", model=tokens["model"], input_tokens=tokens["input_tokens"],
                               output_tokens=0, cached_tokens=0)
        if reason == "run_cap":
            # Another chat's recorded usage reaches the threshold while the answer is in flight.
            sibling = HarnessChat(run_id=run.id, status="completed", judge_model="gpt-4.1-mini")
            db.add(sibling)
            db.flush()
            save_evaluation(db, sibling.id, {"usage": {"input_tokens": 25_000}})
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
        stopped = record_turn(db, chat.id, body)
        assert stopped["stop"] == reason
        assert stopped["pending_nudges"] == stopped["stuck_answers"] == 0
        assert chat.ended_how == reason and run.status == "completed"
        replay = record_turn(db, chat.id, body)
        assert replay["replayed"] and replay["stop"] == reason
        assert replay["pending_nudges"] == replay["stuck_answers"] == 0
        assert chat.pending_nudges == chat.stuck_answers == 0
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
    with SessionLocal() as db:
        run = HarnessRun(status="completed", plan={"chat_cap_cents": 1, "luna_token_ceiling": 1000})
        db.add(run)
        db.flush()
        # Historical completed rows can retain pending nudge counters and lack a complete price ledger.
        chat = HarnessChat(run_id=run.id, status="completed", ended_how=ending, cost_usd=cost,
                           luna_tokens=luna, pending_nudges=2, stuck_answers=1)
        db.add(chat)
        db.flush()
        detail = get_chat(db, chat.id)
        assert detail["judge_budget_reached"] is expected
        assert detail["pending_nudges"] == detail["stuck_answers"] == 0
        assert not db.is_modified(chat) and not db.is_modified(run)


@pytest.mark.parametrize(("model", "amount", "ending"), [
    ("gpt-4.1-mini", 24_999, ""), ("gpt-4.1-mini", 25_000, "cap"),
    ("gpt-6-luna", 999, ""), ("gpt-6-luna", 1_000, "luna_ceiling"),
])
def test_child_generation_alone_can_close_an_unsent_answer(model, amount, ending):
    with SessionLocal() as db:
        run, session, chat = running_chat(db)
        sibling = HarnessChat(run_id=run.id, status="running")
        db.add(sibling)
        db.flush()
        turn_id = uuid4()
        tokens = {"model": model, "input_tokens": amount, "output_tokens": 0}
        submission = {"seq": 1, "turn_id": str(turn_id), "revision": session.revision, "intent": "guess",
                      "child_text": "Maybe.", "child_tokens": tokens, "dispatch_state": "prepared"}
        prepare_harness_turn(db, chat.id, {"seq": 1, "claim_generation": 1, "submission": submission})
        for _ in range(2):
            result = dispatch_harness_turn(db, chat.id, turn_id, 1)
            assert result["action"] == ("run_cap" if ending else "send")
        assert chat.ended_how == ending and run.status == sibling.status == "running"
        if ending:
            assert result["ended_how"] == ending
            assert chat.turn_count == 0 and chat.pending_turn is None
            assert chat.tokens["unsent_child"]["child_tokens"] == tokens
            assert db.scalars(select(HarnessTurn).where(HarnessTurn.chat_id == chat.id)).first() is None
            assert db.scalars(select(KcTurnReceipt).where(KcTurnReceipt.session_id == session.id)).first() is None
            saved = get_chat(db, chat.id)
            assert saved["judge_budget_reached"] is True and not saved["run_cap_reached"]
            if ending == "cap":
                assert saved["cost_usd"] == "0.01"
                assert "chat reached its spending cap" in download_chat(db, chat.id)
            else:
                assert saved["luna_tokens"] == amount
                assert "chat reached its Luna token ceiling" in download_chat(db, chat.id)


@pytest.mark.parametrize("legacy", [True, False])
def test_uncertain_pending_at_chat_cap_only_reads_its_receipt(legacy):
    with SessionLocal() as db:
        run, session, chat = running_chat(db)
        sibling = HarnessChat(run_id=run.id, status="running")
        db.add(sibling)
        db.flush()
        turn_id = uuid4()
        unknown = {"seq": 1, "turn_id": str(turn_id), "revision": session.revision, "intent": "guess",
                   "child_text": "Maybe.", "child_tokens": {"model": "gpt-4.1-mini", "input_tokens": 25_000}}
        if not legacy:
            unknown["dispatch_state"] = "dispatched"
        chat.pending_turn = unknown
        chat.cost_usd = "0.01"  # Durable checkpoint from a previous worker.
        db.flush()
        with pytest.raises(HTTPException, match="409"):
            dispatch_harness_turn(db, chat.id, turn_id, 0)
        assert dispatch_harness_turn(db, chat.id, turn_id, 1)["action"] == "read_receipt"
        body = {**unknown, "claim_generation": 1, "session_after": {"delivery_status": "unknown"}}
        assert record_turn(db, chat.id, body)["stop"] == "awaiting_retry"
        assert chat.pending_turn == unknown and chat.turn_count == 0 and chat.status == "paused"
        assert sibling.status == run.status == "running"


@pytest.mark.parametrize(("model", "amount", "stop"), [
    ("gpt-4.1-mini", 25_000, "cap"), ("gpt-4.1-mini", 24_999, None), ("gpt-6-luna", 1_000, "luna_ceiling"),
])
def test_run_status_identifies_a_chat_that_used_its_budget_on_opening_speech(model, amount, stop):
    from app.harness import get_run, refresh_harness_session_cost

    with SessionLocal() as db:
        run, session, chat = running_chat(db)
        other = HarnessChat(run_id=run.id, status="running")
        db.add(other)
        db.flush()
        record_token_usage(db, session, kind="speak", model=model, input_tokens=amount, output_tokens=0, cached_tokens=0)
        refresh_harness_session_cost(db, session.id)
        latest = get_run(db, run.id)
        assert not latest["run_cap_reached"]
        assert {row["id"]: row["chat_budget_stop"] for row in latest["chat_rows"]} == {chat.id: stop, other.id: None}
