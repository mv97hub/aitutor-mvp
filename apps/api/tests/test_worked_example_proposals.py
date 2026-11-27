"""A tentative answer to a worked example's solo problem is still an answer."""

from uuid import uuid4

import pytest

from app.kc_loop import proposed_step_answer
from tests.test_disclosure_credit import _closed, _speak, _state, open_lesson
from tests.test_kc import _decide, client

SOLO = ("Leo shows little outward distress during separation and turns away from his caregiver "
        "on reunion. What attachment pattern is this consistent with, and what does it not establish?")
EXPECTED = ("The behavior is consistent with insecure-avoidant attachment in this observation. "
            "Little outward distress does not prove the absence of attachment or internal distress. "
            "The observation does not establish one cause, diagnose Leo, or determine his future relationships.")
# Synthetic AP Psychology chat 55cad424, turn 13. The child named the pattern first.
PARTIAL = "Is that avoidant attachment, since Leo avoids his caregiver after she returns?"
COMPLETE = "Is it avoidant attachment, without proving how Leo feels inside or predicting his future relationships?"
FADED = "Describe what the observer saw before drawing a conclusion."
BLOCK = {"id": "attachment", "type": "worked_example", "data": {
    "problem_statement": "How can we describe an observation without overinterpreting it?",
    "steps": [{"step_text": FADED, "rationale": "One observation cannot predict the future."},
              {"step_text": "Describe what the observation supports.", "rationale": "Keep the conclusion bounded."}],
    "faded_step_index": 0, "solo_problem": SOLO, "solo_expected_answer": EXPECTED,
}}


def _claim(session, answer):
    path = f"/kc/tutor/sessions/{session}"
    claim = {"turn_id": str(uuid4()), "revision": client.get(path).json()["revision"], "answer": answer}
    response = client.post(path + "/turn", json=claim)
    assert response.status_code == 200, response.text
    return path, claim, response.json()["system_prompt"]


def _grade(path, claim, **decision):
    response = client.post(path + "/decision", json={"turn_id": claim["turn_id"], **decision})
    assert response.status_code == 200, response.text
    return response.json()


def _solo_session(open_lesson, tutor_reply=SOLO):
    session = open_lesson([BLOCK])
    _speak(session, "How should we begin an observation?")
    first = _decide(session, FADED, substep_passed=True, reply=tutor_reply)
    assert first["active_substep"] == "solo_solve"
    return session


def test_partial_and_complete_solo_proposals_are_counted_once(open_lesson):
    session = _solo_session(open_lesson)
    path, claim, prompt = _claim(session, PARTIAL)
    assert "This typed line is unscored help" not in prompt
    assert "ask only for the missing part" in prompt
    reply = "You've named the pattern. What can one observation tell us about his future?"
    partial = _grade(path, claim, decision="stay", substep_passed=False, reply=reply)
    assert partial["reply"] == reply and partial["active_substep"] == "solo_solve"
    row = next(r for r in _state(session)["requirements"] if r["key"] == "solo_solve")
    assert (row["observation"], row["attempts"]) == ("insufficient", 1)
    replay = client.post(path + "/turn", json=claim).json()
    assert replay["replayed"] and replay["messages"] == partial["messages"]

    path, claim, prompt = _claim(session, COMPLETE)
    assert "Grade the learner's proposed answer" in prompt
    result = _grade(path, claim, decision="advance", substep_passed=True, reply="You identified the pattern and its limits.")
    assert result["unit_complete"]
    rows = {r["key"]: (r["observation"], r["attempts"]) for r in _closed(session)["requirements"]}
    assert rows == {"faded_step": ("independent", 1), "solo_solve": ("independent", 2)}
    replay = client.post(path + "/turn", json=claim).json()
    assert replay["replayed"] and replay["messages"] == result["messages"]


@pytest.mark.parametrize("question", [
    "What does avoidant attachment mean?", "Can I have a hint?", "Is it my turn?",
    "Is it time for lunch?", "Is that something you can explain?",
    "Is the answer supposed to be a pattern or a number?", "Is the answer somewhere in the passage?",
    "Is the answer somewhere in the attachment passage?", "Is that the attachment question again?", "Could it be explained with a different observation?",
])
def test_solo_clarification_is_free_even_if_the_grader_checks_pass(open_lesson, question):
    session = _solo_session(open_lesson)
    path, claim, prompt = _claim(session, question)
    assert "This typed line is unscored help" in prompt
    result = _grade(path, claim, decision="advance", substep_passed=True, reply="Here is some context.")
    assert result["active_substep"] == "solo_solve"
    row = next(r for r in _state(session)["requirements"] if r["key"] == "solo_solve")
    assert (row["observation"], row["attempts"]) == ("open", 0)


def test_only_authored_solo_targets_enable_worked_example_proposals():
    assert proposed_step_answer(BLOCK, "faded_step", PARTIAL) is None
    legacy = {**BLOCK, "data": {**BLOCK["data"], "solo_expected_answer": ""}}
    assert proposed_step_answer(legacy, "solo_solve", PARTIAL) is None


@pytest.mark.parametrize("answer", ["Is it 15 dollars?", "Is it fifteen dollars?", "Is the answer 15 dollars?", "Is it twelve?"])
def test_solo_result_can_be_proposed_without_repeating_the_key_calculation(answer):
    block = {**BLOCK, "data": {**BLOCK["data"], "solo_expected_answer": "Five plus ten dollars = 15 dollars."}}
    assert proposed_step_answer(block, "solo_solve", answer)


@pytest.mark.parametrize("answer", [
    "Is it secure attachment because his caregiver came back?", "Could it be secure?", "Is the answer ambivalent?",
])
def test_incorrect_but_on_topic_answer_is_still_an_attempt(open_lesson, answer):
    session = _solo_session(open_lesson)
    path, claim, prompt = _claim(session, answer)
    assert "Grade the learner's proposed answer" in prompt
    result = _grade(path, claim, decision="stay", substep_passed=False, reply="Look at how Leo responded on reunion.")
    assert result["active_substep"] == "solo_solve"
    row = next(r for r in _state(session)["requirements"] if r["key"] == "solo_solve")
    assert (row["observation"], row["attempts"]) == ("insufficient", 1)


def test_tentative_response_after_the_solo_answer_was_given_stays_assisted(open_lesson):
    session = _solo_session(open_lesson, "Here is the answer: " + EXPECTED + " Say it back.")
    path, claim, prompt = _claim(session, COMPLETE)
    assert "Grade the learner's proposed answer" in prompt
    result = _grade(path, claim, decision="advance", substep_passed=True, reply="Yes, that is the limit.")
    assert result["unit_complete"]
    row = next(r for r in _closed(session)["requirements"] if r["key"] == "solo_solve")
    assert (row["observation"], row["attempts"]) == ("assisted", 1)
