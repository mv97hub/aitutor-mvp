"""Phase C: length, a blank reply, a one-sentence close, and no block in that close."""

import re

from app.harness_checks import automatic_checks
from app.kc import loop_turn_result
from app.kc_loop import SAY_THAT_AGAIN, hold_for_blank_reply, reply_is_unreadable
from tests.test_explanation_block import _profile_for, _prompt
from tests.test_kc_prompt import _section, _text, _topic_node


def test_a_bite_sized_first_teaching_keeps_the_childs_length() -> None:
    text = _prompt(profile=_profile_for(4))
    who = _section(text, "Who you are talking to")
    assert "Keep response length bite-sized: 1 to 2 short sentences." in who
    assert "CROSS-LAYER LENGTH OVERRIDE" not in text
    assert "Length override is on" not in text
    assert "stays inside the learner's response_length" in text
    assert "5 to 8 sentences" not in text


def test_tell_me_more_unlocks_the_longer_explanation() -> None:
    text = _prompt(
        profile=_profile_for(4),
        opening=False,
        last_answer="Tell me more",
        active_block_state={
            "substep": "explain_topic",
            "topic_index": 0,
            "dialogue_turns": 1,
            "elaboration_turns": 0,
        },
    )
    who = _section(text, "Who you are talking to")
    assert "CROSS-LAYER LENGTH OVERRIDE" not in who
    assert "Keep response length bite-sized" in who
    assert "They asked to hear more" in text
    assert "may run longer than their response_length" in text


def test_a_blank_reply_stays_without_counting_a_try() -> None:
    assert reply_is_unreadable("")
    assert reply_is_unreadable("   ")
    assert reply_is_unreadable("...")
    assert reply_is_unreadable("…")
    assert not reply_is_unreadable("The surprise one hurts more.")
    state = {
        "substep": "explain_topic",
        "topic_index": 1,
        "dialogue_turns": 4,
        "block_attempts": 2,
    }
    held = hold_for_blank_reply(
        blocks=[{"id": "blk_costs", "type": "explanation", "data": {}}],
        step=0,
        active_block_state=state,
        block_results=[],
        move_attempts=3,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        rubric_met=[],
    )
    assert SAY_THAT_AGAIN == "Say that again?"
    assert held.decision == "stay"
    assert held.advance_block is False
    assert held.unit_complete is False
    assert held.next_step == 0
    assert held.next_block_state["topic_index"] == 1
    assert held.next_block_state["substep"] == "explain_topic"
    assert held.move_attempts == 3
    assert held.next_block_state["block_attempts"] == 2
    facts = loop_turn_result(
        before_step=0,
        before_state=state,
        before_attempts=3,
        before_results=[],
        resolution=held,
    )
    assert facts == {
        "stayed": True,
        "advanced": False,
        "closed": "",
        "ended_unit": False,
        "attempt_counted": False,
    }


def test_a_bare_yes_closes_in_one_sentence_and_does_not_say_block() -> None:
    text = _text(
        node=_topic_node(),
        opening=False,
        last_answer="yes",
        active_block_state={"substep": "summary_check", "last_task_substep": "main", "revealed_substep": False},
        block_results=[
            {
                "title": "River fact",
                "outcome": "passed",
                "attempts": 1,
                "strong": "River fact",
                "work_on": "not noted",
            }
        ],
    )
    turn = _section(text, "This turn")
    how = _section(text, "How to teach")
    returned = _section(text, "What to return")
    happened = _section(text, "What just happened")
    assert "Close in one sentence." in turn
    assert "Do not praise." in turn
    assert "Do not recap." in turn
    assert "Ask no question." in turn
    assert "congratulate" not in turn.lower()
    assert "Summarize what the learner can now do" not in text
    assert "Close in one sentence." not in how
    assert "reply is the only text the child reads." in returned
    assert "decision is the move for this reply." in returned
    assert "congratulate" not in returned.lower()
    assert "Recent messages:" in happened
    assert "River fact: passed." in happened
    assert "What was strong:" not in happened
    spoken = "\n".join(line for line in turn.splitlines() if not line.startswith("Active step:"))
    spoken = spoken.replace("Never say the word block to the learner.", "")
    spoken = spoken.replace("Never say the word block.", "")
    spoken = spoken.replace("before this block can pass.", "")
    spoken = spoken.replace("return to this block.", "")
    spoken = spoken.replace("block_complete", "")
    assert re.search(r"\bblock\b", spoken, re.I) is None


def test_saying_block_without_a_number_is_a_leak() -> None:
    checks = automatic_checks(
        [
            {
                "tutor_reply": "Nice work finishing this block.",
                "intent": "say_yes",
                "child_text": "yes",
            }
        ],
        ended_how="completed",
        response_length="balanced",
    )
    assert checks["leaks"] == [0]
    numbered = automatic_checks(
        [{"tutor_reply": "We are on block 3.", "intent": "say_yes", "child_text": "yes"}],
        ended_how="completed",
        response_length="balanced",
    )
    assert numbered["leaks"] == [0]
    clean = automatic_checks(
        [{"tutor_reply": "Shoe-leather costs are the extra trips.", "intent": "say_yes", "child_text": "yes"}],
        ended_how="completed",
        response_length="balanced",
    )
    assert clean["leaks"] == []
