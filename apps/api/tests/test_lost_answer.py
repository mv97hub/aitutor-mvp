"""Retry answer receipts through the real turn and decision endpoints, with a controlled grader."""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import KcTurnReceipt
from app.turn_receipt import payload_hash
from tests.test_block_close import (
    CONTINUE, RECALL, WHY, _by_key, _course, _grade, _messages, _open, _receipt_count, _session, client,
)
from tests.test_block_close_stage4 import MCQ
from tests.test_kc import _wipe_zz


def test_retry_after_final_answer_commits_returns_the_original_closed_session():
    course = _course("zz-lost-final", [RECALL])
    try:
        opened = _open(course, "zz-lost-final-a")
        path = f"/kc/tutor/sessions/{opened['id']}"
        # Two legitimately distinct submissions with the same text.
        first = _grade(opened["id"], "idk", 0)
        second = _grade(opened["id"], "idk", first["revision"])
        why = _grade(opened["id"], WHY, second["revision"], passed=True)
        final = _grade(opened["id"], CONTINUE, why["revision"])
        assert final["status"] == "completed"
        submit = {"answer": CONTINUE, "turn_id": final.pop("_turn_id"), "revision": why["revision"]}
        replay = client.post(f"{path}/turn", json=submit)
        assert replay.status_code == 200, replay.text
        body = replay.json()
        assert body.pop("replayed") is True
        assert body == final
        # A late duplicate decision has no second opportunity to score or write a reply.
        duplicate = client.post(f"{path}/decision", json={"turn_id": submit["turn_id"], "decision": "stay", "reply": "Again?"})
        assert duplicate.status_code == 200
        duplicate_body = duplicate.json()
        assert duplicate_body.pop("replayed") is True
        assert duplicate_body == final
        assert client.post(f"{path}/turn", json={**submit, "answer": "changed"}).status_code == 409
        assert client.post(f"{path}/turn", json={**submit, "turn_id": "genuinely-new"}).status_code == 422
        session = _session(opened["id"])
        assert session.revision == 4
        assert len(session.block_results) == 1
        assert _by_key(session.block_results[0]["requirements"])["recall"]["attempts"] == 2
        assert _receipt_count(opened["id"], "answer") == 4
        assert [m.content for m in _messages(opened["id"]) if m.role == "user"] == ["idk", "idk", WHY, CONTINUE]
    finally:
        _wipe_zz()


def test_choice_retry_preserves_original_submission_before_and_after_commit():
    course = _course("zz-lost-choice", [MCQ])
    try:
        opened = _open(course, "zz-lost-choice-a")
        path = f"/kc/tutor/sessions/{opened['id']}"
        claim = {"phase": "claim", "turn_id": "opening", "revision": 0, "content": ""}
        assert client.post(f"{path}/speech", json=claim).status_code == 200
        speak = client.post(f"{path}/speech", json={**claim, "phase": "commit", "content": MCQ["data"]["question_stem"]})
        assert speak.status_code == 200, speak.text
        assert speak.json()["choice"]
        submit = {"answer": "a. Blue water", "turn_id": "answer-a", "revision": speak.json()["revision"]}
        claim = client.post(f"{path}/turn", json=submit)
        assert claim.status_code == 200, claim.text
        before = client.post(f"{path}/turn", json=submit)
        assert before.status_code == 200, before.text
        assert "system_prompt" in before.json()
        assert _receipt_count(opened["id"], "answer") == 1
        graded = client.post(f"{path}/decision", json={"turn_id": "answer-a", "decision": "advance",
                                                      "substep_passed": True, "reply": "Why is that?"})
        assert graded.status_code == 200, graded.text
        assert graded.json()["choice"] is None
        assert _messages(opened["id"])[-2].content.startswith("a. Blue water\na. Blue water\nb. Red paint")
        for legacy in (False, True):
            if legacy:
                # A pre-upgrade receipt hashed the decorated transcript with the original choices.
                with SessionLocal() as db:
                    receipt = db.scalar(select(KcTurnReceipt).where(
                        KcTurnReceipt.session_id == _session(opened["id"]).id, KcTurnReceipt.client_turn_id == "answer-a",
                    ))
                    receipt.payload_hash = payload_hash(receipt.payload)
                    db.commit()
            again = client.post(f"{path}/turn", json=submit)
            assert again.status_code == 200, again.text
            body = again.json()
            assert body.pop("replayed") is True
            assert body == graded.json()
            assert client.post(f"{path}/turn", json={**submit, "answer": "b. Red paint"}).status_code == 409
        assert len(_messages(opened["id"])) == 3
    finally:
        _wipe_zz()
