"""Recover submissions across claims, tutor commits and lost acknowledgements."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

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
