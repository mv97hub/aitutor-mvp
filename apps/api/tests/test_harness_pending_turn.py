"""Recover submissions across claims, tutor commits and lost acknowledgements."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.database import SessionLocal
from app.harness import claim_chat, download_chat, prepare_harness_turn, record_turn, resume_run
from app.models import HarnessChat, HarnessEvaluation, HarnessRun, HarnessTurn, KcGoal, KcNode, KcSession, KcTurnReceipt, Student


def test_pending_answer_survives_reclaim_and_counts_once():
    with SessionLocal() as db:
        code = uuid.uuid4().hex
        student = Student(slug=code, display_name="Test learner", is_test=True)
        goal, node = KcGoal(code=code, title="Test course"), KcNode(code=code, title="Test component")
        run = HarnessRun(status="running")
        db.add_all([student, goal, node, run])
        db.flush()
        session = KcSession(student_id=student.id, goal_id=goal.id, kc_id=node.id, revision=3)
        db.add(session)
        db.flush()
        chat = HarnessChat(run_id=run.id, session_id=session.id, status="running", claim_generation=1)
        db.add(chat)
        db.flush()

        def envelope(seq, revision):
            return {"seq": seq, "turn_id": str(uuid.uuid4()), "revision": revision, "child_text": "yes",
                    "intent": "continue", "session_before": {"substep": "summary_check"}, "child_tokens": {}}

        submitted = envelope(1, 3)
        request = {"seq": 1, "claim_generation": 1, "submission": submitted}
        assert prepare_harness_turn(db, chat.id, request)["submission"] == submitted
        assert prepare_harness_turn(db, chat.id, request)["submission"] == submitted
        with pytest.raises(HTTPException, match="409"):
            prepare_harness_turn(db, chat.id, {**request, "submission": {**submitted, "child_text": "different"}})
        final = {**submitted, "claim_generation": 1, "session_after": {"delivery_status": "unknown", "error": "connection lost"}}
        assert record_turn(db, chat.id, final)["pending"]
        assert chat.turn_count == 0 and run.status == "paused"
        assert "Tutor receipt: unknown" in download_chat(db, chat.id)
        resume_run(db, run.id)
        db.flush()
        claimed = claim_chat(db, run.id)
        assert claimed["pending_turn"] == submitted and claimed["claim_generation"] == 2
        with pytest.raises(HTTPException, match="409"):
            record_turn(db, chat.id, final)
        final["claim_generation"] = 2
        with pytest.raises(HTTPException, match="409"):
            record_turn(db, chat.id, {"child_text": "bypass pending"})

        def commit_receipt(submission):
            db.add(KcTurnReceipt(session_id=session.id, client_turn_id=submission["turn_id"], route="answer",
                                 revision=submission["revision"], status="committed", payload=submission["child_text"],
                                 result={"revision": submission["revision"] + 1}))
            session.revision += 1
            db.flush()

        commit_receipt(submitted)
        assert record_turn(db, chat.id, final)["recover"]
        assert chat.turn_count == 0 and run.status == "running"
        final["session_after"] = {"delivery_status": "recovered", "tutor_reply": "Tell me more.", "revision": 4}
        assert record_turn(db, chat.id, final)["turn"] == 1
        assert record_turn(db, chat.id, final)["replayed"] and chat.turn_count == 1
        second = envelope(2, 4)
        prepare_harness_turn(db, chat.id, {"claim_generation": 2, "seq": 2, "submission": second})
        commit_receipt(second)
        second_write = {**second, "claim_generation": 2, "session_after": {
            "status": "completed", "revision": 5, "delivery_status": "delivered", "tutor_reply": "Well done."}}
        assert record_turn(db, chat.id, second_write)["stop"] == "completed"
        assert record_turn(db, chat.id, second_write)["replayed"]
        with pytest.raises(HTTPException, match="409"):
            record_turn(db, chat.id, {**second_write, "child_text": "Different"})
        assert chat.turn_count == 2 and chat.pending_turn is None
        assert db.scalar(select(func.count()).select_from(HarnessTurn).where(HarnessTurn.chat_id == chat.id)) == 2
        assert db.scalar(select(func.count()).select_from(HarnessEvaluation).where(HarnessEvaluation.chat_id == chat.id)) == 1
        assert "Delivery: recovered" in download_chat(db, chat.id)


def test_run_cap_reconciles_committed_siblings_and_preserves_uncertain_submissions(request):
    from app import harness

    with SessionLocal() as db:
        code = uuid.uuid4().hex
        goal, node = KcGoal(code=code, title="Test"), KcNode(code=code, title="Test")
        run = HarnessRun(status="paused", plan={"run_cap_cents": 10}, totals={"priced_cents": 10})
        db.add_all([goal, node, run])
        db.flush()
        paid = HarnessChat(run_id=run.id, status="completed", cost_usd="0.10")
        fresh = HarnessChat(run_id=run.id, status="queued")
        db.add_all([paid, fresh])
        pending = []
        for index in range(2):
            student = Student(slug=f"{code}{index}", display_name="Test", is_test=True)
            db.add(student)
            db.flush()
            session = KcSession(student_id=student.id, goal_id=goal.id, kc_id=node.id, revision=1)
            db.add(session)
            db.flush()
            turn = {"seq": 1, "turn_id": str(uuid.uuid4()), "revision": 1, "child_text": "yes",
                    "session_before": {}, "child_tokens": {}, "intent": "continue"}
            chat = HarnessChat(run_id=run.id, status="running", student_id=student.id, session_id=session.id,
                               claim_generation=1, pending_turn=turn)
            db.add(chat)
            db.flush()
            pending.append((chat, turn))
        first, second = pending
        reply = {"revision": 2, "status": "in_progress", "messages": []}
        receipt = KcTurnReceipt(session_id=first[0].session_id, client_turn_id=first[1]["turn_id"],
                                route="answer", revision=1, status="committed", payload="yes", result=reply)
        db.add(receipt)
        db.flush()

        resume_run(db, run.id)
        run_id, goal_id, node_id = run.id, goal.id, node.id
        db.commit()

        def clean_up():
            with SessionLocal.begin() as cleanup:
                harness.delete_run(cleanup, run_id)
                cleanup.execute(delete(KcGoal).where(KcGoal.id == goal_id))
                cleanup.execute(delete(KcNode).where(KcNode.id == node_id))

        request.addfinalizer(clean_up)
        starts = Barrier(2)

        def worker():
            with SessionLocal.begin() as connection:
                starts.wait(timeout=5)
                return claim_chat(connection, run_id)

        # Separate transactions race to claim the same queue. A third idle worker
        # must not close a run while the two winners are reconciling receipts.
        with ThreadPoolExecutor(max_workers=2) as pool:
            workers = [pool.submit(worker) for _ in range(2)]
            claims = [worker.result(timeout=10) for worker in workers]
        assert all(claims), "both checkpoints must still be claimable at the cap"
        assert {c["id"] for c in claims} == {first[0].id, second[0].id}
        assert claim_chat(db, run.id) is None and run.status == "running"
        assert fresh.status == "cancelled" and fresh.session_id is None
        assert harness.pending_answer_result(db, first[0].id, uuid.UUID(first[1]["turn_id"]))["result"] == reply
        assert harness.pending_answer_result(db, second[0].id, uuid.UUID(second[1]["turn_id"]))["result"] is None

        def write(pair, delivery):
            chat, turn = pair
            return record_turn(db, chat.id, {**turn, "claim_generation": chat.claim_generation,
                "session_after": {"status": "in_progress", "delivery_status": delivery, "tutor_reply": "Try another."}})

        assert write(second, "unknown")["pending"]
        assert write(second, "unknown")["pending"]  # lost pause acknowledgement
        assert run.status == "running" and second[0].status == "paused"
        assert write(first, "recovered")["stop"] == "run_cap"
        assert write(first, "recovered")["replayed"]
        assert first[0].turn_count == 1 and run.status == "paused"
        assert second[0].turn_count == 0 and second[0].pending_turn == second[1]
        # A late receipt can still be reconciled when the operator resumes the capped run.
        db.add(KcTurnReceipt(session_id=second[0].session_id, client_turn_id=second[1]["turn_id"],
                             route="answer", revision=1, status="committed", payload="yes", result=reply))
        db.flush()
        resume_run(db, run.id)
        db.flush()
        assert claim_chat(db, run.id)["id"] == second[0].id
        assert write(second, "recovered")["stop"] == "run_cap"
        assert run.status == "completed" and second[0].turn_count == 1


@pytest.mark.parametrize("already_dispatched", [False, True])
def test_saved_child_usage_and_dispatch_state_survive_restart_at_cap(already_dispatched, request):
    from app import harness

    turn_id = uuid.uuid4()
    tokens = {"model": "gpt-4o-mini", "input_tokens": 1_000_000, "output_tokens": 0}
    turn = {"turn_id": str(turn_id), "seq": 1, "revision": 0, "child_text": "yes",
            "child_tokens": tokens, "dispatch_state": "prepared"}
    with SessionLocal.begin() as db:
        code = uuid.uuid4().hex
        goal, node = KcGoal(code=code, title="Test"), KcNode(code=code, title="Test")
        run = HarnessRun(status="running", plan={"run_cap_cents": 16})
        student = Student(slug=code, display_name="Test", is_test=True)
        db.add_all([goal, node, run, student])
        db.flush()
        session = KcSession(student_id=student.id, goal_id=goal.id, kc_id=node.id, revision=0)
        db.add(session)
        db.flush()
        chat = HarnessChat(run_id=run.id, student_id=student.id, session_id=session.id, status="running", claim_generation=1)
        sibling = HarnessChat(run_id=run.id, status="completed", cost_usd="0")
        db.add_all([chat, sibling])
        db.flush()
        chat_id, run_id, goal_id, node_id, sibling_id = chat.id, run.id, goal.id, node.id, sibling.id

    def cleanup():
        with SessionLocal.begin() as db:
            harness.delete_run(db, run_id)
            db.execute(delete(KcGoal).where(KcGoal.id == goal_id))
            db.execute(delete(KcNode).where(KcNode.id == node_id))
    request.addfinalizer(cleanup)
    with SessionLocal.begin() as db:
        envelope = {"claim_generation": 1, "seq": 1, "submission": turn}
        for _ in range(2):
            assert prepare_harness_turn(db, chat_id, envelope)["submission"] == turn
        assert db.get(HarnessRun, run_id).totals["priced_cents"] == 15
        harness.pause_run(db, run_id)
        db.flush()
        assert harness.dispatch_harness_turn(db, chat_id, turn_id, 1)["action"] == "paused"
        assert db.get(HarnessChat, chat_id).pending_turn["dispatch_state"] == "prepared"
        resume_run(db, run_id)
        db.flush()
        assert claim_chat(db, run_id)["claim_generation"] == 2
        if already_dispatched:
            assert harness.dispatch_harness_turn(db, chat_id, turn_id, 2)["action"] == "send"
        # A sibling finishes a paid call before any response reaches this worker.
        db.get(HarnessChat, sibling_id).cost_usd = "0.01"
        db.flush()
        harness._refresh_totals(db, db.get(HarnessRun, run_id))
    with SessionLocal.begin() as db:
        resume_run(db, run_id)
        db.flush()
        resumed = claim_chat(db, run_id)
        assert resumed["pending_turn"]["dispatch_state"] == ("dispatched" if already_dispatched else "prepared")
        assert resumed["claim_generation"] == 3
        for _ in range(2):  # An acknowledgement from the dispatch API may itself be lost.
            action = harness.dispatch_harness_turn(db, chat_id, turn_id, 3)["action"]
            assert action == ("read_receipt" if already_dispatched else "run_cap")
    with SessionLocal() as db:
        chat = db.get(HarnessChat, chat_id)
        assert chat.turn_count == 0
        assert db.scalar(select(func.count()).select_from(KcTurnReceipt).where(KcTurnReceipt.session_id == chat.session_id)) == 0
        assert db.get(HarnessRun, run_id).totals["priced_cents"] == 16
        if already_dispatched:
            assert chat.pending_turn is not None and chat.status == "running"
        else:
            assert chat.pending_turn is None and chat.ended_how == "run_cap"
            assert db.get(HarnessRun, run_id).status == "completed"
            assert chat.tokens["unsent_child"]["child_tokens"] == tokens
            assert "Child tokens: 1000000 in, 0 out" in download_chat(db, chat_id)
            harness._refresh_chat_cost(db, chat)
            assert chat.cost_usd == "0.15"
