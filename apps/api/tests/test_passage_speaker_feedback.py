"""The child hears the same source attribution that the evidence step grades."""

from uuid import uuid4

import pytest

from app.kc_blocks import corrected_citation
from tests.test_disclosure_credit import _speak, _state, open_lesson
from tests.test_kc import _decide, client
from tests.test_reviewed_lessons import _component

WRONG = 'Paris to Juliet; “I luv him”!'
FALSE_PRAISE = 'You got the speakers: Paris talks to Juliet. Juliet says, "I will confess to you that I love him"—and "him" is Romeo, not Paris. Which words show she is dodging Paris?'


@pytest.fixture
def dialogue(open_lesson):
    cell = _component("romeo-and-juliet")["blocks"][2]
    session = open_lesson([cell])
    data = cell["data"]
    _speak(session, data["passage_text"] + "\n\n" + data["central_idea_question"])
    result = _decide(session, data["expected_central_idea"], reply=data["evidence_prompt"], substep_passed=True)
    assert result["active_substep"] == "cite_evidence"
    return session


@pytest.mark.parametrize(("answer", "model_pass"), [
    (WRONG, False),
    ('Paris tells Juliet “I will confess to you that I love him.”', True),
    ('Paris tells Juliet “I love him” and means Romeo.', True),
])
def test_reversed_speaker_gets_a_source_correction_and_a_retry(dialogue, answer, model_pass):
    base = f"/kc/tutor/sessions/{dialogue}"
    submit = {"turn_id": str(uuid4()), "revision": client.get(base).json()["revision"], "answer": answer}
    assert client.post(f"{base}/turn", json=submit).status_code == 200
    decision = {"turn_id": submit["turn_id"], "substep_passed": model_pass,
                "decision": "advance" if model_pass else "stay", "reply": FALSE_PRAISE}
    result = client.post(f"{base}/decision", json=decision).json()
    assert result["active_substep"] == "cite_evidence"
    assert result["loop_result"]["attempt_counted"]
    assert "You got the speakers" not in result["reply"]
    assert "Juliet" in result["reply"] and "to Paris" in result["reply"]
    assert result["reply"].endswith("?")
    assert result["messages"][-1]["content"] == result["reply"]
    replay = client.post(f"{base}/turn", json=submit).json()
    assert replay["replayed"] and replay["reply"] == result["reply"]
    row = next(r for r in _state(dialogue)["requirements"] if r["key"] == "cite_evidence")
    assert (row["observation"], row["attempts"]) == ("insufficient", 1)
    feedback = "Yes, she uses ‘him’ so Paris never hears her name the person. What does Paris think she means?"
    repaired = _decide(dialogue, 'Juliet tells Paris “I love him” and means Romeo.', reply=feedback, substep_passed=True)
    assert repaired["active_substep"] == "craft_or_inference" and repaired["reply"] == feedback


def test_repeated_misattribution_keeps_reveal_limit_and_asks_the_next_question(dialogue):
    _decide(dialogue, WRONG, reply=FALSE_PRAISE)
    result = _decide(dialogue, WRONG, reply=FALSE_PRAISE)
    data = _component("romeo-and-juliet")["blocks"][2]["data"]
    assert result["active_substep"] == "craft_or_inference"
    assert "You got the speakers" not in result["reply"]
    assert 'Juliet says “I love him” to Paris' in result["reply"]
    assert result["reply"].endswith(data["analysis_question"])
    row = next(r for r in _state(dialogue)["requirements"] if r["key"] == "cite_evidence")
    assert row["observation"] == "assisted" and row["attempts"] == 2


@pytest.mark.parametrize("echo", ["Juliet speaks to Paris.", "You found the line where Juliet speaks to Paris."])
def test_repeating_the_supplied_names_after_a_hint_is_not_independent_citation(dialogue, echo):
    _decide(dialogue, WRONG, reply=FALSE_PRAISE)
    _decide(dialogue, "Can you give me a hint?", reply="What do the words tell us?")
    result = _decide(dialogue, echo, decision="advance", reply="Yes, you explained that.", substep_passed=True)
    data = _component("romeo-and-juliet")["blocks"][2]["data"]
    assert result["active_substep"] == "craft_or_inference"  # The normal second-try limit.
    assert result["reply"].endswith(data["analysis_question"])
    assert 'Juliet says “I love him” to Paris' in result["reply"]
    assert "you explained" not in result["reply"]
    state = _state(dialogue)
    assert "citation_speaker_hint" not in state
    row = next(r for r in state["requirements"] if r["key"] == "cite_evidence")
    assert (row["observation"], row["attempts"]) == ("assisted", 2)


@pytest.mark.parametrize(("answer", "expected"), [
    ('Rani says to Sam, "Bring the red box."', {"speaker": "Sam", "listener": "Rani", "quote": "Bring the red box"}),
    ('Sam to Rani; "Bring the red box."', {}),
    ('Rani to Sam; "It is time."', {}),  # The same line appears under both labels.
    ('Rani to Sam; "Where is the dog?"', {}),
    ('Did Rani say "Bring the red box"?', {}),
    ('Rani says "Bring the red box"? No, Sam said it.', {}),
    ('Rani says "It is time" and Sam says "Bring the red box."', {}),
])
def test_only_an_explicit_unambiguous_claim_gets_a_source_correction(answer, expected):
    block = {"type": "passage_ela", "data": {
        "evidence_context": "Sam replies to Rani.",
        "passage_text": "RANI\nIt is time.\n\nSAM\nIt is time.\nBring the red box.",
    }}
    assert corrected_citation(block, "cite_evidence", answer) == expected
    assert corrected_citation(block, "central_idea", answer) == {}
    del block["data"]["evidence_context"]
    assert corrected_citation(block, "cite_evidence", answer) == {}


@pytest.mark.parametrize("context", [
    "The class wonders whether Sam replies to Rani or the Friar.",
    "Sam replies to Rani or the Friar.",
    "Sam replies to Rani. Sam speaks to Jo.",
])
def test_a_speaker_label_does_not_establish_an_uncertain_listener(context):
    data = {"evidence_context": context, "passage_text": "JO\nWhen?\n\nRANI\nIs it time?\n\nSAM\nBring the red box."}
    assert corrected_citation({"type": "passage_ela", "data": data}, "cite_evidence",
                                       'Rani says “Bring the red box.”') == {"speaker": "Sam", "listener": "", "quote": "Bring the red box"}
