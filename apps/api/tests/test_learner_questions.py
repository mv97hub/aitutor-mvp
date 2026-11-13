"""Learner questions are answered before the block advances.

Session 2f5608a5-6281-486c-8eec-288c6eab25e2 asked "what's a lemonade cup?" during
the topic explanation and "can you please elaborate?" on the explanatory
summary. Both were swallowed. These tests keep that from happening again.
"""

from app.kc_loop import (
    learner_asks_clarification,
    learner_may_complete_explanation_summary,
    learner_wants_deeper_explanation,
    learner_wants_recap_elaboration,
    resolve_block_turn,
)
from app.models import default_kc_tutor_config
from tests.test_explanation_block import BLOCK
from tests.test_goal_start import DEEPEN, _prompt, _turn
from tests.test_kc_prompt import _section

SUPPLY = {
    "id": "supply",
    "type": "topic_goal",
    "data": {
        "topic": "Supply",
        "goal": "A higher price leads to a higher quantity supplied.",
        "acceptance_criteria": "Price and quantity supplied move together.",
    },
}

NEXT = {"id": "next", "type": "mcq", "data": {"question_stem": "A smartphone price rises."}}

CLARIFY = (
    "Answer that question first, in a sentence or two, then one line back to the active lesson."
)


def test_session_questions_are_clarifications_and_tell_me_more_is_not() -> None:
    for phrase in (
        "what's a lemonade cup?",
        "what is a lemonade cup?",
        "can you explain what a price and supply?",
    ):
        assert learner_asks_clarification(phrase), phrase
        assert not learner_wants_deeper_explanation(phrase), phrase
    assert learner_wants_deeper_explanation("Tell me more")
    assert not learner_asks_clarification("Tell me more")
    assert learner_wants_deeper_explanation("Can you explain more?")
    assert not learner_asks_clarification("Can you explain more?")


def test_lemonade_cup_is_answered_before_the_topic_moves_on() -> None:
    for phrase in (
        "what's a lemonade cup?",
        "what is a lemonade cup?",
        "can you explain what a price and supply?",
    ):
        text = _prompt(opening=False, last_answer=phrase)
        turn = _section(text, "This turn")
        assert CLARIFY in turn, phrase
        assert "one line back to the active lesson" in turn, phrase
        assert "Do not start a new explanation of this block." in turn, phrase
        assert "Set help_requested=true." in text, phrase
        assert "The child has asked for help." in text, phrase
        assert "The child has not asked for help." not in text, phrase
        assert DEEPEN not in text, phrase
        assert "Do not ask any question." not in text, phrase
        assert "Do not end this turn with a question." not in text, phrase
        stayed = _turn(phrase, state={"substep": "explain", "elaboration_turns": 0})
        assert stayed.advance_block is False, phrase
        assert stayed.unit_complete is False, phrase
        assert stayed.passed is False, phrase
        assert stayed.rubric_met == [], phrase
        assert stayed.next_block_state["substep"] == "explain", phrase
        assert stayed.next_block_state["elaboration_turns"] == 0, phrase
        forced = resolve_block_turn(
            decision="complete",
            substep_passed=True,
            block_complete=True,
            rubric_met=["topic"],
            stored_rubric=[],
            matched_wrong="",
            blocks=[SUPPLY, NEXT],
            step=0,
            active_block_state={"substep": "explain", "elaboration_turns": 1},
            block_results=[],
            move_attempts=0,
            hint_tier="nudge",
            reveals=0,
            enrichment_turns=0,
            cfg=default_kc_tutor_config(),
            goal=None,
            last_misconception="",
            answer=phrase,
        )
        assert forced.advance_block is False, phrase
        assert forced.next_step == 0, phrase
        assert forced.passed is False, phrase
        assert forced.rubric_met == [], phrase
        assert forced.next_block_state["substep"] == "explain", phrase
        assert forced.next_block_state["elaboration_turns"] == 1, phrase


def test_tell_me_more_with_no_question_still_deepens() -> None:
    text = _prompt(opening=False, last_answer="Tell me more")
    turn = _section(text, "This turn")
    assert DEEPEN in turn
    assert "Do not ask any question." in turn
    assert CLARIFY not in text
    assert "The child has not asked for help." in text
    stayed = _turn("Tell me more")
    assert stayed.next_block_state["substep"] == "explain"
    assert stayed.advance_block is False


def test_session_elaborate_requests_hold_the_summary() -> None:
    for phrase in ("can you please elaborate?", "elaborate", "tell me more"):
        assert learner_wants_recap_elaboration(phrase), phrase
        assert not learner_may_complete_explanation_summary(phrase), phrase
        held = _summary_turn(phrase, substep_passed=True, block_complete=True, decision="complete")
        assert held.decision == "stay", phrase
        assert held.advance_block is False, phrase
        assert held.unit_complete is False, phrase
        assert held.next_step == 0, phrase
        assert held.next_block_state["substep"] == "summary_check", phrase
        assert held.block_results == [], phrase
        text = _summary_prompt(phrase)
        assert "Elaborate on the summary" in text, phrase
        assert "Set substep_passed=false and block_complete=false." in text, phrase
        assert "set substep_passed=true and block_complete=true" not in text, phrase
        assert "this reply only affirms and closes the active block" not in text, phrase
        assert "reply affirms this block only" not in text, phrase


def test_only_an_explicit_move_on_completes_the_explanatory_summary() -> None:
    for phrase in ("got it - move on", "no final questions", "let's continue"):
        assert learner_may_complete_explanation_summary(phrase), phrase
        closed = _summary_turn(phrase, substep_passed=False, block_complete=False)
        assert closed.advance_block is True, phrase
        assert closed.unit_complete is False, phrase
        assert closed.next_step == 1, phrase
    shrugged = _summary_turn("ok", substep_passed=True, block_complete=True, decision="complete")
    assert shrugged.advance_block is False
    assert shrugged.next_block_state["substep"] == "summary_check"


def _summary_prompt(answer: str) -> str:
    from tests.test_explanation_block import _prompt as explain_prompt

    return explain_prompt(
        opening=False,
        last_answer=answer,
        node=_supply_node(),
        active_block_state={"substep": "summary_check", "topic_index": 1, "dialogue_turns": 4, "elaboration_turns": 0},
    )


def _supply_node():
    from tests.test_kc_prompt import _node

    return _node(blocks=[dict(BLOCK), dict(NEXT)])


def _summary_turn(answer: str, *, substep_passed: bool, block_complete: bool, decision: str = "stay"):
    return resolve_block_turn(
        decision=decision,
        substep_passed=substep_passed,
        block_complete=block_complete,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(BLOCK), dict(NEXT)],
        step=0,
        active_block_state={"substep": "summary_check", "topic_index": 1, "dialogue_turns": 4, "elaboration_turns": 0},
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=default_kc_tutor_config(),
        goal=None,
        last_misconception="",
        answer=answer,
    )
