"""Walkthrough navigation and the following assessed answer report distinct kinds of progress."""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.harness_download import render_download
from app.models import KcRequirement, KcSession
from tests.test_disclosure_credit import _speak, open_lesson
from tests.test_explanation_block import BLOCK
from tests.test_kc import _decide


CHECK = {
    "id": "fraction-check", "type": "mcq",
    "data": {
        "mode": "static", "question_stem": "Which number names the number of equal parts?",
        "choices": [
            {"id": "a", "text": "The denominator.", "is_correct": True},
            {"id": "b", "text": "The numerator."},
        ],
    },
}


@pytest.mark.parametrize("last_topic", [False, True], ids=["next-topic", "close-walkthrough"])
def test_walkthrough_help_at_the_topic_limit_uses_no_attempt(open_lesson, last_topic):
    session = open_lesson([BLOCK, CHECK])
    _speak(session, BLOCK["data"]["topics"][0]["explanation"])
    if last_topic:
        _decide(session, "Got it - move on", reply=BLOCK["data"]["topics"][1]["explanation"])
    for _ in range(2):
        earlier = _decide(session, "Tell me more", reply="Imagine cutting a pizza into equal pieces.")
        assert earlier["loop_result"]["stayed"] and not earlier["loop_result"]["attempt_counted"]

    reply = "That was the last topic." if last_topic else BLOCK["data"]["topics"][1]["explanation"]
    result = _decide(session, "Tell me more", reply=reply)
    if last_topic:
        assert result["loop_result"]["closed"] == "unassessed" and result["step"] == 1
    else:
        assert result["loop_result"]["advanced"] and result["step"] == 0
    with SessionLocal() as db:
        stored = db.get(KcSession, UUID(session))
        assert stored.attempts == 0
        rows = db.scalars(select(KcRequirement).where(KcRequirement.session_id == stored.id)).all()
        assert rows and all(row.attempts == 0 for row in rows)
        if last_topic:
            assert stored.block_results[0]["attempts"] == 0
        else:
            assert stored.active_block_state["topic_index"] == 1
    assert not result["loop_result"]["attempt_counted"]
    markdown = render_download({}, [{"turns": [{
        "seq": 3, "child_text": "Tell me more",
        "session_after": {"tutor_reply": reply, "loop_result": result["loop_result"],
                          "loop_decision": result["loop_decision"]},
    }]}])
    assert '"attempt_counted": false' in markdown and "try not counted" in markdown


def test_a_genuine_assessment_after_the_walkthrough_counts_once(open_lesson):
    session = open_lesson([BLOCK, CHECK])
    _speak(session, BLOCK["data"]["topics"][0]["explanation"])
    _decide(session, "Got it - move on", reply=BLOCK["data"]["topics"][1]["explanation"])
    _decide(session, "Got it - move on", reply="Time to check that idea.")
    _speak(session, CHECK["data"]["question_stem"])
    assessed = _decide(session, "A", substep_passed=True, reply="Yes, the denominator names the parts.")
    assert assessed["loop_result"]["attempt_counted"]
    with SessionLocal() as db:
        stored = db.get(KcSession, UUID(session))
        assert stored.attempts == 1
        choice = db.scalar(select(KcRequirement).where(KcRequirement.session_id == stored.id,
                                                       KcRequirement.requirement_key == "choice"))
        assert choice.attempts == 1 and choice.observation == "independent"


@pytest.mark.parametrize("scoring_version", [1, 2])
def test_resuming_an_older_walkthrough_does_not_add_to_prior_attempts(open_lesson, scoring_version):
    session = open_lesson([BLOCK])
    _speak(session, BLOCK["data"]["topics"][0]["explanation"])
    with SessionLocal.begin() as db:
        stored = db.get(KcSession, UUID(session))
        stored.scoring_version = scoring_version
        stored.attempts = 3
        stored.active_block_state = {**stored.active_block_state, "block_attempts": 2}
    stayed = _decide(session, "Tell me more", reply="Imagine a pizza split into four equal parts.")
    assert stayed["loop_result"]["stayed"] and not stayed["loop_result"]["attempt_counted"]
    with SessionLocal() as db:
        stored = db.get(KcSession, UUID(session))
        assert stored.active_block_state.get("block_attempts", 0) == 0
        assert stored.attempts == 3
        assert stored.scoring_version == scoring_version
