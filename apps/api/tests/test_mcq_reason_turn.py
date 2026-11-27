"""The correct choice and its explanation are separate turns in the learner's chat."""

from uuid import uuid4

import pytest

from tests.test_disclosure_credit import _speak, _state, open_lesson
from tests.test_kc import _decide, client


QUESTION = "Which answer describes a contraction?"
CHOICES = [
    {"id": "a", "text": "A period when real GDP is increasing and unemployment is falling."},
    {"id": "b", "text": "A period when real GDP is decreasing and unemployment is rising.", "is_correct": True},
    {"id": "c", "text": "The high point before the economy shrinks."},
]
REASON = "When people buy less, firms cut production and need fewer workers."
QUIZ = {"id": "contraction", "type": "mcq", "data": {
    "mode": "static", "question_stem": QUESTION, "choices": CHOICES, "correct_explanation": REASON,
}}
INVITATION = "Do you have a question for me before we finish?"
EARLY_CLOSE = "Yes — contraction means the economy shrinks: real GDP goes down, and more people lose jobs. " + INVITATION


def _pick(open_lesson, *, retry=True):
    session = open_lesson([QUIZ])
    _speak(session, QUESTION)
    if retry:
        _decide(session, "A", reply="Think about what happens to jobs when the economy shrinks.")
    url = f"/kc/tutor/sessions/{session}"
    claim = {"turn_id": str(uuid4()), "revision": client.get(url).json()["revision"], "answer": "B"}
    response = client.post(url + "/turn", json=claim)
    assert response.status_code == 200, response.text
    return session, claim, response.json()["system_prompt"]


def _commit(session, claim, reply):
    response = client.post(f"/kc/tutor/sessions/{session}/decision", json={
        "turn_id": claim["turn_id"], "decision": "advance", "substep_passed": True, "reply": reply,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_prompt_asks_for_the_learners_reason_after_a_correct_retry(open_lesson):
    _, _, prompt = _pick(open_lesson)
    turn = prompt.split("This turn\n", 1)[1].split("\n\n", 1)[0]
    assert "ask what helped the learner choose" in turn
    assert "before we finish" not in turn
    assert "The child picks the choice on screen" not in turn
    assert "When the pick is correct, restate why" not in prompt


@pytest.mark.parametrize("draft", [EARLY_CLOSE, "Ready to move on?", "That's it for today!",
                                   "Why does that fit? Any final questions before we finish?"])
def test_early_close_is_replaced_before_the_tutor_reply_is_saved(open_lesson, draft):
    session, claim, _ = _pick(open_lesson)
    result = _commit(session, claim, draft)
    assert result["active_substep"] == "awaiting_why"
    assert result["reply"] == "That’s right. What helped you choose that answer?"
    assert result["messages"][-1]["content"] == result["reply"]
    rows = _state(session)["requirements"]
    assert {row["key"]: row["observation"] for row in rows} == {"choice": "independent", "why": "open"}
    retry = client.post(f"/kc/tutor/sessions/{session}/turn", json=claim).json()
    replay = _commit(session, claim, draft)
    for saved in (retry, replay):
        assert saved["replayed"] and saved["reply"] == result["reply"]
        assert saved["messages"] == result["messages"]
    assert _state(session)["requirements"] == rows
    summary = _decide(session, REASON, reply=INVITATION, substep_passed=True)
    assert (summary["active_substep"], summary["reply"]) == ("summary_check", INVITATION)
    assert _state(session)["requirements"][-1]["observation"] == "independent"


@pytest.mark.parametrize(("reply", "credit"), [
    ("Which clue helped you decide the race would finish earlier?", "independent"),
    (REASON + " Why does that fit your answer?", "assisted"),
])
def test_valid_reason_prompt_and_any_disclosure_reach_the_child(open_lesson, reply, credit):
    session, claim, _ = _pick(open_lesson)
    result = _commit(session, claim, reply)
    assert (result["active_substep"], result["reply"]) == ("awaiting_why", reply)
    _decide(session, REASON, reply=INVITATION, substep_passed=True)
    assert _state(session)["requirements"][-1]["observation"] == credit


def test_clean_first_pick_can_invite_a_final_question(open_lesson):
    session, claim, prompt = _pick(open_lesson, retry=False)
    assert INVITATION in prompt
    result = _commit(session, claim, INVITATION)
    assert (result["active_substep"], result["reply"]) == ("summary_check", INVITATION)
