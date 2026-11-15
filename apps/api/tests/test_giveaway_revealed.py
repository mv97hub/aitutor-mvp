"""A tutor giveaway is stored as revealed. A later correct line does not make it passed."""

from app.kc_loop import resolve_block_turn
from app.models import default_kc_tutor_config

CFG = default_kc_tutor_config()
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}
CHAIN = (
    "When the government borrows more, interest rates rise, "
    "and a business holds off on a new tractor."
)
GOAL = {
    "id": "goal",
    "type": "topic_goal",
    "data": {
        "topic": "Crowding out",
        "goal": "Explain how government borrowing raises interest rates and makes a business hold off on a tractor.",
        "acceptance_criteria": CHAIN,
    },
}
FACT = "A menu cost is the expense incurred by firms when they change their prices due to inflation."
WHY = "Firms change prices more often, so the expense adds up."
RECALL = {
    "id": "recall",
    "type": "retrieval_check",
    "data": {
        "recall_prompt": "What is a menu cost in the context of inflation?",
        "expected_fact": FACT,
        "elaborative_why_prompt": "Why do menu costs matter more when inflation is high?",
        "expected_why_rationale": WHY,
    },
}
QUIZ = {
    "id": "quiz",
    "type": "mcq",
    "data": {
        "mode": "static",
        "question_stem": "Which of the following is NOT a cost of inflation?",
        "choices": [
            {"id": "a", "text": "Shoe-leather costs", "is_correct": False},
            {"id": "b", "text": "Menu costs", "is_correct": False},
            {"id": "c", "text": "Unit-of-account costs", "is_correct": False},
            {"id": "d", "text": "Increased productivity", "is_correct": True},
        ],
    },
}
WORKED = {
    "id": "work",
    "type": "worked_example",
    "data": {
        "problem_statement": "Name the color.",
        "steps": [{"step_text": "Look at the water."}],
        "solo_expected_answer": "The river is blue.",
    },
}
READ_CHOICE = "I'm giving you the answer now: it's d) Increased productivity."


def _turn(
    block: dict,
    answer: str,
    substep: str,
    *,
    substep_passed: bool = False,
    move_attempts: int = 0,
    prior_tutor: str = "",
    state: dict | None = None,
):
    active = {"substep": substep, "dialogue_turns": 0, "fragment_prompted": True}
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
        move_attempts=move_attempts,
        hint_tier="nudge",
        reveals=int((state or {}).get("reveals") or 0),
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer=answer,
        prior_tutor=prior_tutor,
    )


def _close(block: dict, state: dict, answer: str = "yes") -> str:
    closed = _turn(block, answer, "summary_check", state=state, substep_passed=True)
    assert closed.block_results, answer
    return str(closed.block_results[-1]["outcome"])


def test_a_read_aloud_choice_closes_as_revealed() -> None:
    """Child 5: the tutor read Increased productivity, and yes closed the block as passed."""
    closed = _turn(
        QUIZ,
        "yes",
        "summary_check",
        prior_tutor=READ_CHOICE,
        substep_passed=True,
        state={"last_task_substep": "choice", "revealed_substep": False, "block_attempts": 2},
    )
    assert closed.advance_block is True
    assert closed.block_results[-1]["outcome"] == "revealed"
    assert closed.reveals == 1


def test_a_later_correct_choice_does_not_become_passed() -> None:
    stayed = _turn(QUIZ, "yes", "choice", prior_tutor=READ_CHOICE)
    assert stayed.block_results == []
    assert stayed.next_block_state.get("answer_given_away") is True

    picked = _turn(QUIZ, "Increased productivity", "choice", state=stayed.next_block_state)
    assert picked.block_results == []
    assert picked.next_block_state["substep"] == "summary_check"
    assert picked.next_block_state.get("answer_given_away") is True

    assert _close(QUIZ, picked.next_block_state) == "revealed"


def test_a_correct_line_after_the_reveal_flag_stays_revealed() -> None:
    """The summary redemption clears revealed_substep. A giveaway still closes revealed."""
    demonstrated = _turn(
        QUIZ,
        "Increased productivity",
        "summary_check",
        prior_tutor=READ_CHOICE,
        substep_passed=True,
        state={
            "last_task_substep": "choice",
            "revealed_substep": True,
            "block_attempts": 2,
            "reveals": 1,
        },
    )
    assert demonstrated.block_results == []
    assert demonstrated.next_block_state.get("revealed_substep") is False
    assert demonstrated.next_block_state.get("answer_given_away") is True
    assert _close(QUIZ, demonstrated.next_block_state, "move on") == "revealed"


def test_a_stated_chain_asked_back_stays_revealed() -> None:
    prior = f"{CHAIN} Now say it back in your own words."
    said = _turn(GOAL, CHAIN, "main", prior_tutor=prior, substep_passed=True)
    assert said.block_results == []
    assert said.next_block_state["substep"] == "summary_check"
    assert said.next_block_state.get("answer_given_away") is True
    assert _close(GOAL, said.next_block_state) == "revealed"


def test_a_retrieval_answer_asked_back_stays_revealed() -> None:
    prior = f"The answer is {FACT} Say it back."
    repeated = _turn(RECALL, FACT, "recall", prior_tutor=prior, substep_passed=True)
    assert repeated.block_results == []
    assert repeated.next_block_state.get("answer_given_away") is True
    assert repeated.next_block_state["substep"] == "elaborate_why"

    why = _turn(RECALL, WHY, "elaborate_why", state=repeated.next_block_state, substep_passed=True)
    assert why.block_results == []
    assert why.next_block_state.get("answer_given_away") is True
    assert _close(RECALL, why.next_block_state) == "revealed"


def test_a_correct_answer_with_no_giveaway_still_passes() -> None:
    said = _turn(GOAL, CHAIN, "main", substep_passed=True)
    assert said.next_block_state.get("answer_given_away") is not True
    assert said.next_block_state.get("revealed_substep") is not True
    assert _close(GOAL, said.next_block_state, "move on") == "passed"

    picked = _turn(QUIZ, "Increased productivity", "choice")
    assert picked.next_block_state.get("answer_given_away") is not True
    assert _close(QUIZ, picked.next_block_state) == "passed"

    solved = _turn(WORKED, "The river is blue.", "solo_solve", substep_passed=True)
    assert solved.block_results[-1]["outcome"] == "passed"


def test_listing_every_choice_is_not_a_giveaway() -> None:
    menu = (
        "Which of the following is NOT a cost of inflation? "
        "Shoe-leather costs, Menu costs, Unit-of-account costs, or Increased productivity?"
    )
    picked = _turn(QUIZ, "Increased productivity", "choice", prior_tutor=menu)
    assert picked.next_block_state.get("answer_given_away") is not True
    assert _close(QUIZ, picked.next_block_state) == "passed"


def test_stating_the_chain_without_asking_for_it_back_is_not_a_giveaway() -> None:
    said = _turn(GOAL, CHAIN, "main", prior_tutor=CHAIN, substep_passed=True)
    assert said.next_block_state.get("answer_given_away") is not True
    assert _close(GOAL, said.next_block_state, "move on") == "passed"
