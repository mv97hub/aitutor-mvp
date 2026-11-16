"""Close on yes, a blank tutor line, and a giveaway that states the answer and the reason."""

from app.kc import loop_turn_result
from app.kc_loop import (
    SAY_THAT_AGAIN,
    hold_for_blank_reply,
    reply_is_unreadable,
    resolve_block_turn,
)
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _node, _section, _text

CFG = default_kc_tutor_config()
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}
WHO = "The borrower wins."
WHY = "The borrower pays back with dollars that buy less."
LOAN = {
    "id": "loan",
    "type": "worked_example",
    "data": {
        "problem_statement": "Who wins when a loan is paid back after prices rise?",
        "steps": [
            {"step_text": WHO, "rationale": WHY},
            {"step_text": "The worker's raise is smaller than inflation.", "rationale": "The real wage falls."},
        ],
        "faded_step_index": 0,
        "solo_problem": "Who wins on the loan?",
        "solo_expected_answer": "The borrower wins the loan.",
    },
}
GIVEAWAY = f"{WHO} {WHY}"


def _turn(block, answer, substep, *, prior_tutor="", substep_passed=False, state=None):
    active = {"substep": substep, "dialogue_turns": 1, "fragment_prompted": True}
    if state:
        active.update(state)
        active["substep"] = substep
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[block, dict(NEXT)],
        step=0,
        active_block_state=active,
        block_results=[],
        move_attempts=1,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer=answer,
        prior_tutor=prior_tutor,
    )


def test_agreement_after_a_passed_block_closes_in_one_sentence() -> None:
    """yes and Yes, let's move on close. No unit recap, no new lesson, no praise."""
    recall = {
        "id": "recall",
        "type": "retrieval_check",
        "data": {
            "recall_prompt": "What is a menu cost?",
            "expected_fact": "A menu cost is the expense of changing prices.",
            "elaborative_why_prompt": "Why do menu costs matter?",
            "expected_why_rationale": "Firms change prices more often.",
        },
    }
    menu = _text(
        node=_node(blocks=[recall], misconceptions=[]),
        opening=False,
        last_answer="Yes, let's move on.",
        active_block_state={
            "substep": "summary_check",
            "last_task_substep": "elaborate_why",
            "revealed_substep": False,
        },
        block_results=[{"title": "Menu costs", "outcome": "passed", "attempts": 1}],
    )
    turn = _section(menu, "This turn")
    teach = _section(menu, "What to teach")
    how = _section(menu, "How to teach")
    assert "Close in one sentence." in turn
    assert "Do not praise." in turn
    assert "Do not recap." in turn
    assert "Ask no question." in turn
    assert "Summarize what the learner can now do" not in menu
    assert "what to practice" not in menu
    assert "Praise the specific strategy" not in turn
    assert "What is a menu cost?" not in teach
    assert "Do not teach a new lesson." in teach
    assert "Do not teach a new lesson." in how
    assert "Close in one sentence." not in how

    goal = {
        "id": "goal",
        "type": "topic_goal",
        "data": {
            "topic": "Anticipated and unanticipated inflation",
            "goal": "Explain anticipated versus unanticipated inflation and why a surprise hurts more.",
            "acceptance_criteria": (
                "Anticipated inflation is expected. Unanticipated inflation is a surprise "
                "and hurts more because people cannot plan."
            ),
        },
    }
    node = _node(blocks=[goal, dict(NEXT)], misconceptions=[])
    agreed = _text(
        node=node,
        opening=False,
        last_answer="yes",
        active_block_state={"substep": "summary_check", "last_task_substep": "main", "revealed_substep": False},
    )
    agreed_teach = _section(agreed, "What to teach")
    assert "Close in one sentence." in _section(agreed, "This turn")
    assert "Do not praise." in agreed
    assert "Do not recap." in agreed
    assert "Do not teach a new lesson." in agreed_teach
    assert "anticipated" not in agreed_teach.lower()
    assert "How to explain this goal" not in _section(agreed, "How to teach")
    assert "from a fresh angle" not in agreed

    bare = _text(
        node=node,
        opening=False,
        last_answer="yes",
        active_block_state={"substep": "explain", "dialogue_turns": 1, "elaboration_turns": 0},
    )
    bare_turn = _section(bare, "This turn")
    assert "from a fresh angle" not in bare
    assert "Explain what this topic is and why it matters." not in bare
    assert "A bare yes does not start a new lesson." in bare_turn
    assert "Do not explain the topic." in bare_turn
    assert "Ask the opening question" in bare_turn
    opened = _turn(goal, "yes", "explain")
    assert opened.block_results == []
    assert opened.next_block_state["substep"] == "main"
    assert opened.advance_block is False


def test_an_empty_tutor_reply_says_that_again_and_does_not_count_a_try() -> None:
    """Empty model text uses the same hold as a dots-only reply. The faded step stays."""
    for reply in ("", "   ", "...", "…", "\u200b"):
        assert reply_is_unreadable(reply), repr(reply)
    assert not reply_is_unreadable("Say the missing step.")
    state = {
        "substep": "faded_step",
        "dialogue_turns": 3,
        "block_attempts": 1,
    }
    held = hold_for_blank_reply(
        blocks=[LOAN, dict(NEXT)],
        step=0,
        active_block_state=state,
        block_results=[],
        move_attempts=1,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        rubric_met=[],
    )
    assert SAY_THAT_AGAIN == "Say that again?"
    assert held.decision == "stay"
    assert held.advance_block is False
    assert held.move_attempts == 1
    assert held.next_block_state["substep"] == "faded_step"
    assert held.next_block_state["block_attempts"] == 1
    assert held.block_results == []
    facts = loop_turn_result(
        before_step=0,
        before_state=state,
        before_attempts=1,
        before_results=[],
        resolution=held,
    )
    assert facts["attempt_counted"] is False
    assert facts["stayed"] is True
    assert facts["advanced"] is False


def test_stating_the_answer_and_the_reason_stays_revealed() -> None:
    """The tutor already said who wins and why. A later echo does not pass."""
    direct = _turn(
        LOAN,
        "The borrower wins the loan.",
        "solo_solve",
        prior_tutor=GIVEAWAY,
        substep_passed=True,
    )
    assert direct.block_results[-1]["outcome"] == "revealed"

    echoed = _turn(LOAN, GIVEAWAY, "faded_step", prior_tutor=GIVEAWAY, substep_passed=True)
    assert echoed.block_results == []
    assert echoed.next_block_state.get("answer_given_away") is True
    assert echoed.next_block_state["substep"] == "solo_solve"

    later = _turn(
        LOAN,
        "The borrower wins the loan.",
        "solo_solve",
        state=echoed.next_block_state,
        substep_passed=True,
    )
    assert later.block_results[-1]["outcome"] == "revealed"

    cleared = dict(echoed.next_block_state)
    cleared["revealed_substep"] = False
    flipped = _turn(
        LOAN,
        "The borrower wins the loan.",
        "solo_solve",
        state=cleared,
        substep_passed=True,
    )
    assert flipped.block_results[-1]["outcome"] == "revealed"

    only_who = _turn(
        LOAN,
        "The borrower wins the loan.",
        "solo_solve",
        prior_tutor=WHO,
        substep_passed=True,
    )
    assert only_who.next_block_state.get("answer_given_away") is not True
    assert only_who.block_results[-1]["outcome"] == "passed"
