"""The question the tutor asked determines whether the next answer is practice."""

from uuid import uuid4

import pytest

from app.database import SessionLocal
from app.models import Student
from tests.test_disclosure_credit import _speak, _state, open_lesson
from tests.test_kc import _decide, _storm, client
from tests.test_passage_ela import BLOCK

QUESTION = BLOCK["data"]["central_idea_question"]
MAIN_IDEA = BLOCK["data"]["expected_central_idea"]
EXAMPLE = "Imagine a boat taking apples to town. What else could the boat carry?"


@pytest.fixture
def reader(open_lesson, request):
    student_id = _storm().id
    with SessionLocal.begin() as db:
        student = db.get(Student, student_id)
        original_profile = student.child_profile
        student.child_profile = {**original_profile, "reading_level": "emerging",
                                 "response_length": getattr(request, "param", "bite_sized")}
    try:
        session = open_lesson([BLOCK])
        _speak(session, f"{BLOCK['data']['passage_text']}\n\n{QUESTION}")
        yield session
    finally:
        with SessionLocal.begin() as db:
            db.get(Student, student_id).child_profile = original_profile


def test_practice_feedback_returns_to_the_assessed_question_without_spending_a_try(reader):
    first = _decide(reader, "I do not know yet.", reply=QUESTION)
    assert first["loop_result"]["attempt_counted"]
    requirements = _state(reader)["requirements"]
    _decide(reader, "Tell me more", reply=EXAMPLE, help_requested=True)
    repeat = _decide(reader, "Tell me more", reply=EXAMPLE, help_requested=True)
    base = f"/kc/tutor/sessions/{reader}"
    submit = {"answer": "Pears!", "turn_id": str(uuid4()), "revision": repeat["revision"]}
    turn = client.post(f"{base}/turn", json=submit)
    assert turn.status_code == 200, turn.text
    feedback = f"Yes, a boat could carry pears. {QUESTION}"
    grade = {"reply": feedback, "turn_id": submit["turn_id"], "decision": "advance", "substep_passed": True,
             "rubric_met": ["blk_passage:central_idea"]}
    result = client.post(f"{base}/decision", json=grade).json()
    assert result["active_substep"] == "central_idea" and not result["loop_result"]["attempt_counted"]
    assert _state(reader)["requirements"] == requirements
    assert "return to the current passage question" in turn.json()["system_prompt"]
    replay = client.post(f"{base}/turn", json=submit).json()
    assert replay["replayed"] and replay["reply"] == feedback
    assert replay["messages"][-1]["content"] == feedback
    assert _state(reader)["requirements"] == requirements
    # The next genuine miss reaches the original two-attempt limit.
    next_turn = _decide(reader, "I do not know yet.", reply="The river helps towns move things. Which line shows this?")
    assert next_turn["loop_result"]["attempt_counted"] and next_turn["active_substep"] == "cite_evidence"


def test_a_direct_passage_answer_still_counts_after_an_example(reader):
    _decide(reader, "Tell me more", reply=EXAMPLE)
    result = _decide(reader, MAIN_IDEA, substep_passed=True, reply="Which sentence shows that?")
    assert result["active_substep"] == "cite_evidence" and result["loop_result"]["attempt_counted"]


def test_a_detail_shared_with_the_expected_answer_is_still_practice(reader):
    _decide(reader, "Tell me more", reply=EXAMPLE)
    requirements = _state(reader)["requirements"]
    result = _decide(reader, "Food and people.", substep_passed=True, reply=f"Yes, those can travel by boat. {QUESTION}")
    assert not result["loop_result"]["attempt_counted"] and result["active_substep"] == "central_idea"
    assert _state(reader)["requirements"] == requirements


def test_rereading_ends_example_practice(reader):
    _decide(reader, "Tell me more", reply=EXAMPLE)
    _decide(reader, "Show me the passage again", reply=f"{BLOCK['data']['passage_text']}\n\n{QUESTION}")
    miss = _decide(reader, "Pears!", reply=QUESTION)
    assert miss["loop_result"]["attempt_counted"]


@pytest.mark.parametrize("reader", ["balanced"], indirect=True)
def test_other_response_lengths_keep_their_ordinary_scored_question(reader):
    _decide(reader, "Tell me more", reply=EXAMPLE)
    miss = _decide(reader, "Pears!", reply=QUESTION)
    assert miss["loop_result"]["attempt_counted"]


@pytest.mark.parametrize("reply", [f"Boats move food to towns. {QUESTION}", "Boats move food to towns."])
def test_only_an_actual_followup_offers_practice(reader, reply):
    _decide(reader, "Tell me more", reply=reply)
    miss = _decide(reader, "Pears!", reply=QUESTION)
    assert miss["loop_result"]["attempt_counted"]
