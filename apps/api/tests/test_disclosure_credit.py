"""Replay what the tutor actually said before awarding independent evidence."""

from uuid import UUID, uuid4

import pytest

from sqlalchemy import select

from app.block_score import remember_tutor_disclosures
from app.database import SessionLocal
from app.models import HarnessChat, HarnessRun, KcRequirement, KcSession
from app.harness import download_chat
from app.studio import DELETE_PASSWORD
from tests.test_kc import _decide, _ready, _spec, _storm, client

QUIZ = {
    "id": "juliet-choice", "type": "mcq",
    "data": {
        "mode": "static", "question_stem": "What do Juliet’s words mean?",
        "choices": [
            {"id": "a", "text": "She is openly declaring her love for Paris."},
            {"id": "b", "text": "She is speaking truthfully about her love for Romeo, but Paris thinks she means him.", "is_correct": True},
            {"id": "c", "text": "She is refusing to confess anything at all."},
        ],
        "correct_explanation": "Juliet’s words are ambiguous: she means Romeo, but Paris assumes she means him.",
    },
}
CHOICE = QUIZ["data"]["choices"][1]["text"]
REVEAL = "C is a trap: Juliet is confessing something. The answer is (b): she truly means Romeo, while Paris thinks she means him. That gap between what she means and what he hears is the double meaning."
MENU = "Which is best? " + " ".join(f"{item['id']}) {item['text']}" for item in QUIZ["data"]["choices"])
GOAL = {
    "id": "juliet-goal", "type": "topic_goal",
    "data": {"topic": "Juliet and Paris", "goal": "Give two readings of a line Juliet speaks.",
             "acceptance_criteria": "Student can point to at least one line from Juliet that has a double meaning and explain both interpretations."},
}


@pytest.fixture
def open_lesson():
    code = f"zz-disclosure-{uuid4().hex[:8]}"
    created = client.post("/kc/courses", json={"code": code, "title": "Two readings", "description": "Close reading.",
                                             "audience": "12-14", "kind": "mastery"})
    assert created.status_code == 200, created.text
    course = created.json()

    def start(blocks):
        ready = _ready(course, [_spec(f"{code}-1", "Juliet and Paris", blocks=blocks)])
        response = client.post("/kc/tutor/sessions", json={"student_id": str(_storm().id),
                               "course_id": course["id"], "kc_id": ready["components"][0]["id"]})
        assert response.status_code == 200, response.text
        return response.json()["id"]

    try:
        yield start
    finally:
        removed = client.post(f"/kc/courses/{course['id']}/delete", json={"password": DELETE_PASSWORD})
        assert removed.status_code == 200, removed.text


def _state(session):
    with SessionLocal() as db:
        return db.get(KcSession, UUID(session)).active_block_state


def _closed(session):
    with SessionLocal() as db:
        return db.get(KcSession, UUID(session)).block_results[-1]


def _speak(session, text):
    response = client.post(f"/kc/tutor/sessions/{session}/speech", json={"content": text})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(("spoken", "choice", "why"), [
    (REVEAL, "assisted", "assisted"),
    ("The correct choice is B. What is your reason?", "assisted", "independent"),
    ("C is a trap. Think about who hears Juliet and who she means.", "independent", "independent"),
])
def test_choice_and_reason_are_credited_separately(open_lesson, spoken, choice, why):
    session = open_lesson([QUIZ])
    _speak(session, MENU)
    _decide(session, QUIZ["data"]["choices"][2]["text"], reply=spoken)
    # Read from storage after the tutor spoke, before the learner has acted again.
    if choice == "assisted":
        state = _state(session)
        assert state["tutor_disclosures"]["choice"] == "b"
        assert next(row for row in state["requirements"] if row["key"] == "choice")["disclosed_choice_id"] == "b"
    _decide(session, CHOICE, reply="Tell me why that reading fits.")
    _decide(session, "Can I have a hint?", reply="Think about the two perspectives.")
    _decide(session, "She means Romeo, but Paris thinks its him.", reply="Shall we finish?", substep_passed=True)
    _decide(session, "No final questions — let's continue!", reply="Done.")
    end = _closed(session)
    rows = {row["key"]: row for row in end["requirements"]}
    if choice == "assisted":
        assert rows["choice"]["disclosed_choice_id"] == "b"
    if why == "assisted":
        assert rows["why"]["tutor_disclosed"] is True
    evidence = {key: row["observation"] for key, row in rows.items()}
    assert evidence == {"choice": choice, "why": why}
    assert end["verdict"] == ("known" if choice == why == "independent" else "fragile")
    with SessionLocal() as db:
        observations = db.scalars(select(KcRequirement).where(KcRequirement.session_id == UUID(session))).all()
        assert {row.requirement_key: row.observation for row in observations} == evidence
        run = HarnessRun(status="completed")
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, session_id=UUID(session), status="completed")
        db.add(chat)
        db.flush()
        assert f": {end['outcome']}" in download_chat(db, chat.id).split("### Block outcomes")[1]



def test_opening_exposure_survives_an_intervening_hint(open_lesson):
    session = open_lesson([QUIZ])
    _speak(session, "The answer is (B).")
    assert _state(session)["tutor_disclosures"]["choice"] == "b"
    _decide(session, "What is a confession?", reply="An admission. Which option fits?")
    _decide(session, CHOICE, reply="All done.")
    _decide(session, "No final questions — let's continue!", reply="Done.")
    row = _closed(session)["requirements"][0]
    assert (row["observation"], row["attempts"]) == ("assisted", 1)


def test_an_explicit_open_text_reveal_cannot_be_earned_back_by_echoing(open_lesson):
    session = open_lesson([GOAL])
    _speak(session, "We will look for two readings. Ready?")
    _decide(session, "Got it - move on", reply="What does Juliet mean?")
    _decide(session, "yes", reply="Here's the reveal: Paris hears a church errand. Juliet means a secret meeting. Say it back in your own full sentence.")
    _decide(session, "Can I have help?", reply="Which two readings did we discuss?")
    _decide(session, "Paris hears a church errand but Juliet means a secret meeting.", substep_passed=True)
    _decide(session, "No final questions — let's continue!", reply="Done.")
    row = _closed(session)
    assert row["verdict"] == "fragile"
    assert row["requirements"][0]["observation"] == "assisted"

@pytest.mark.parametrize("reply", [
    MENU, " ".join(row["text"] for row in QUIZ["data"]["choices"]), "Is B correct?", "B is not correct.", "The answer is not B.", "The answer is A.",
    "Choose a, b, or c.", "Consider the reasons for both B and C.", "If the answer is B, why?",
    "The answer is not " + CHOICE, "The answer is not B or " + CHOICE,
    "Option B is correct only if Juliet means Paris.",
])
def test_menu_hint_wrong_and_conditional_choices_leave_assessment_open(reply):
    state = {"substep": "choice"}
    assert remember_tutor_disclosures(QUIZ, state, reply) == state


def test_generated_choices_use_the_frozen_key_and_keep_the_actual_choice_id():
    block = {"id": "dynamic", "type": "mcq", "data": {"mode": "dynamic"}}
    state = {"substep": "choice", "mcq": {"frozen_key": 1},
             "generated_mcq": {"correct_index": 0, "choices": [
                 {"id": "red-option", "text": "Red"}, {"id": "blue-option", "text": "Blue"}]}}
    assert "tutor_disclosures" not in remember_tutor_disclosures(block, state, "The answer is A.")
    given = remember_tutor_disclosures(block, state, "Option B is correct.")
    assert given["tutor_disclosures"] == {"choice": "blue-option"}
    assert "tutor_disclosures" not in state


def test_solving_a_fresh_item_still_earns_independent_credit(open_lesson):
    new = {"id": "new-item", "type": "mcq", "data": {
        "mode": "static", "question_stem": "Which speaker is listening here?",
        "choices": [{"id": "a", "text": "Paris", "is_correct": True}, {"id": "b", "text": "Romeo"}]}}
    session = open_lesson([QUIZ, new])
    _speak(session, "The answer is B.")
    first = _decide(session, CHOICE, reply="Ready to move on?")
    if first["active_substep"] == "summary_check":
        _decide(session, "No final questions — let's continue!", reply="Time for the new example.")
    _speak(session, "Which speaker is listening?")
    assert not _state(session).get("tutor_disclosures")
    _decide(session, "Paris", reply="Ready to finish?")
    _decide(session, "No final questions — let's continue!", reply="Done.")
    with SessionLocal() as db:
        first, second = db.get(KcSession, UUID(session)).block_results
        assert [row["verdict"] for row in (first, second)] == ["fragile", "known"]
        assert second["requirements"][0]["observation"] == "independent"


def test_full_choice_wording_can_identify_the_option_without_its_label():
    reply = "The correct answer is " + CHOICE + " Why?"
    saved = remember_tutor_disclosures(QUIZ, {"substep": "choice"}, reply)
    assert saved["tutor_disclosures"]["choice"] == "b"


def test_confirming_a_correct_choice_does_not_rewrite_prior_independent_evidence(open_lesson):
    session = open_lesson([QUIZ])
    _speak(session, MENU)
    _decide(session, QUIZ["data"]["choices"][2]["text"], reply="Try a different reading.")
    _decide(session, CHOICE, reply=REVEAL)
    _decide(session, "She means Romeo, but Paris thinks its him.", substep_passed=True)
    _decide(session, "No final questions — let's continue!", reply="Done.")
    end = _closed(session)
    assert {r["key"]: r["observation"] for r in end["requirements"]} == {"choice": "independent", "why": "assisted"}
    assert end["verdict"] == "fragile"

def test_label_before_a_because_clause_discloses_the_chosen_option():
    state = remember_tutor_disclosures(QUIZ, {"substep": "choice"}, "The correct answer is B because she means Romeo.")
    assert state["tutor_disclosures"]["choice"] == "b"


@pytest.mark.parametrize("tutor_line", [
    "The answer is B: 10%.",
    "The answer is B. The rate is 10%.",
    "The answer is B. It is not true that dividing the change by the starting price shows an increase of 10%.",
])
def test_naming_the_rate_or_denying_its_reason_leaves_the_why_independent(open_lesson, tutor_line):
    reason = "Dividing the change by the starting price shows an increase of 10%."
    block = {"id": "rate", "type": "mcq", "data": {
        "mode": "static", "question_stem": "What is the rate of inflation?",
        "choices": [{"id": "a", "text": "5%"}, {"id": "b", "text": "10%", "is_correct": True}],
        "correct_explanation": reason,
    }}
    session = open_lesson([block])
    _speak(session, "Which rate is correct?")
    _decide(session, "5%", reply=tutor_line)
    assert _state(session)["tutor_disclosures"] == {"choice": "b"}
    _decide(session, "10%", reply="How did you calculate it?")
    _decide(session, reason, substep_passed=True, reply="Ready to finish?")
    _decide(session, "No final questions — let's continue!", reply="Done.")
    rows = _closed(session)["requirements"]
    assert {r["key"]: r["observation"] for r in rows} == {"choice": "assisted", "why": "independent"}
    supplied = remember_tutor_disclosures(block, {"substep": "choice"}, "The answer is B: 10%. " + reason)
    assert supplied["tutor_disclosures"] == {"choice": "b", "why": True}


BAG_HINT = "A flying animal fits what Evie saw in the sky. Noah looks in his baseball bag. What does he think she means?"
BAG_REASON = "The fact he looks in his bag"


@pytest.mark.parametrize(("tutor_feedback", "reason", "extra_clue", "choice_credit", "reason_credit"), [
    pytest.param("Take another look. Which option do you choose?", BAG_REASON, "",
                 "independent", "independent", id="general-encouragement"),
    pytest.param(BAG_HINT, BAG_REASON, "", "independent", "assisted", id="used-highlighted-clue"),
    pytest.param(BAG_HINT, "He puts on his batting helmet, so he is getting ready to play.",
                 " He puts on his batting helmet.", "independent", "independent", id="used-another-clue"),
    pytest.param("The answer is C because Noah looks in the baseball bag and thinks Evie means the bat used to hit a ball.",
                 BAG_REASON, "", "assisted", "assisted", id="given-choice-and-reason"),
])
def test_reason_credit_depends_on_using_the_highlighted_clue(
    open_lesson, tutor_feedback, reason, extra_clue, choice_credit, reason_credit,
):
    question = (
        "Evie points at the sky and says, “Look at that bat!” Noah looks in his baseball bag."
        + extra_clue + " What does Noah think Evie means?"
    )
    block = {"id": "bat-meaning", "type": "mcq", "data": {
        "mode": "static", "question_stem": question,
        "choices": [
            {"id": "a", "text": "A flying animal."},
            {"id": "b", "text": "A baseball glove."},
            {"id": "c", "text": "A bat for hitting a ball.", "is_correct": True},
        ],
        "correct_explanation": "Noah looks in the baseball bag because he thinks Evie means the bat used to hit a ball.",
    }}
    session = open_lesson([block])
    _speak(session, question)
    _decide(session, "A", reply=tutor_feedback)
    picked = _decide(session, "C", reply="Yes. What clue tells you which kind of bat Noah is thinking of?")
    assert picked["active_substep"] == "awaiting_why"
    _decide(session, reason, reply="Ready to finish?", substep_passed=True)
    _decide(session, "No final questions — let's continue!", reply="Done.")
    result = _closed(session)
    expected = {"choice": choice_credit, "why": reason_credit}
    assert {r["key"]: r["observation"] for r in result["requirements"]} == expected
    assert result["verdict"] == ("known" if reason_credit == "independent" else "fragile")
    with SessionLocal() as db:
        observations = db.scalars(select(KcRequirement).where(KcRequirement.session_id == UUID(session)))
        assert {r.requirement_key: r.observation for r in observations} == expected
