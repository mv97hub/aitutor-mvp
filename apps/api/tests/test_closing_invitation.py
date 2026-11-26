"""A final question belongs to the learner; accepting an invitation is not a question yet."""

from uuid import UUID, uuid4

import pytest

from app.database import SessionLocal
from app.models import KcSession
from app.kc_loop import summary_needs_learner_question
from app.studio import DELETE_PASSWORD
from tests.test_kc import _decide, _ready, _spec, _storm, client
from tests.test_kc_prompt import _node, _section, _text

INVITE = "Do you have a question for me before we finish?"
BLOCK = {"id": "rate", "type": "topic_goal", "data": {
    "topic": "Reading a price index", "goal": "Distinguish index points from percentages.",
    "acceptance_criteria": "The difference is measured in index points."}}
ANSWER = BLOCK["data"]["acceptance_criteria"]


def test_successful_reply_invites_the_learner_to_ask():
    text = _text(node=_node(blocks=[BLOCK]), opening=False, last_answer=ANSWER,
                 active_block_state={"substep": "main"}, attempts=0,
                 last_messages=f"assistant: What are the units? | user: {ANSWER}")
    assert INVITE in _section(text, "This turn")
    assert "move on, or ask one more question" not in text


@pytest.mark.parametrize(("invite", "accept", "finish"), [
    (INVITE, "Ask me one more question.", "What is an index point?"),
    (INVITE, "Yes please.", "No final questions — let's continue!"),
    ("Any questions before we finish? You can also choose Continue.", "Yes please.", "What is an index point?"),
    ("You can always ask me later. Are you ready to move on?", "", "Yes please."),
    (INVITE, "", "What is an index point?"),
    (INVITE, "", "No final questions — let's continue!"),
])
def test_summary_acceptance_waits_for_a_question_and_closes_once(invite, accept, finish):
    code = f"zz-closing-{uuid4().hex[:8]}"
    created = client.post("/kc/courses", json={
        "code": code, "title": "Read a graph", "description": "Reading an index.", "audience": "12-14", "kind": "mastery",
    })
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    try:
        course = _ready(created.json(), [_spec(f"{code}-1", "Index points", blocks=[BLOCK])])
        opened = client.post("/kc/tutor/sessions", json={"student_id": str(_storm().id), "course_id": course_id,
                             "kc_id": course["components"][0]["id"]})
        assert opened.status_code == 200, opened.text
        session = opened.json()["id"]
        path = f"/kc/tutor/sessions/{session}"
        assert client.post(f"{path}/speech", json={"content": "We will look at an index."}).status_code == 200
        _decide(session, "Got it - move on", reply="Tell me the units of the difference.")
        correct = _decide(session, ANSWER, reply=invite, substep_passed=True)
        assert correct["active_substep"] == "summary_check"
        with SessionLocal() as db:
            evidence = db.get(KcSession, UUID(session)).active_block_state["requirements"]
        if accept:
            posted = client.post(f"{path}/turn", json={"answer": accept})
            assert posted.status_code == 200, posted.text
            assert "What would you like to ask me?" in _section(posted.json()["system_prompt"], "This turn")
            held = client.post(f"{path}/decision", json={"decision": "complete", "substep_passed": True,
                               "block_complete": True, "reply": "What would you like to ask me?"})
            assert held.status_code == 200, held.text
            assert not held.json()["unit_complete"]
            assert held.json()["active_substep"] == "summary_check"
            with SessionLocal() as db:
                waiting = db.get(KcSession, UUID(session))
                assert waiting.active_block_state["requirements"] == evidence
                assert waiting.block_results == []
        turn_id = str(uuid4())
        revision = client.get(path).json()["revision"]
        posted = client.post(f"{path}/turn", json={"turn_id": turn_id, "revision": revision, "answer": finish})
        assert posted.status_code == 200, posted.text
        if finish.endswith("?"):
            assert "Answer that question" in _section(posted.json()["system_prompt"], "This turn")
            reply = "One index point is a one-unit change on the index scale."
        else:
            reply = "You’ve finished."
        decision = {"turn_id": turn_id, "decision": "complete", "block_complete": True, "reply": reply}
        for _ in range(2):
            closed = client.post(f"{path}/decision", json=decision)
            assert closed.status_code == 200, closed.text
            assert closed.json()["unit_complete"] and closed.json()["reply"] == reply
        with SessionLocal() as db:
            saved = db.get(KcSession, UUID(session))
            assert len(saved.block_results) == 1
            assert saved.block_results[0]["requirements"] == evidence
        completed = client.get(path).json()
        assert [m["content"] for m in completed["messages"]].count(reply) == 1
    finally:
        removed = client.post(f"/kc/courses/{course_id}/delete", json={"password": DELETE_PASSWORD})
        assert removed.status_code == 200, removed.text


@pytest.mark.parametrize(("answer", "prior", "waiting"), [
    ("yes please", "Do you want to move on?", False),
    ("yes", "Do you want to move on?", False),
    ("yes please", "Any questions before we finish? You can also choose Continue.", True),
    ("yes please", "Do you have one last question before we finish?", True),
    ("yeah", "That's the lesson. Let me know if you have any final questions.", True),
    ("yes", "You can ask me later. Ready to move on", False),
    ("Sure.", "Before we finish, is there anything you'd like to ask?", True),
    ("I’m not sure what you mean.", INVITE, True),
    ("yes", "You can always ask me later. Are you ready to move on?", False),
    ("yes", "Any final questions? Or would you like to move on?", False),
    ("yes", INVITE, True),
    ("I'm not sure what you mean.", INVITE, True),
    ("Can I ask a question?", INVITE, True),
    ("Ask me another question please.", "Should I ask you one more question about this?", True),
    ("I have a question: why did prices fall?", INVITE, False),
    ("Yes, why did prices fall?", INVITE, False),
    ("No final questions — let's continue!", INVITE, False),
])
def test_clarification_uses_both_the_request_and_the_previous_invitation(answer, prior, waiting):
    assert summary_needs_learner_question(answer, prior) is waiting
