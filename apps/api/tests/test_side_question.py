"""A who/what/where/why question pauses the step. It is not scored."""

from app.kc_loop import resolve_block_turn
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _goal, _node, _section, _text

GOAL = {
    "id": "goal",
    "type": "topic_goal",
    "data": {
        "topic": "The Rubicon",
        "goal": "Explain why Caesar crossing the Rubicon started a war with Pompey.",
        "acceptance_criteria": "Pompey",
    },
}
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}
RECALL = {
    "id": "recall",
    "type": "retrieval_check",
    "data": {
        "recall_prompt": "Who led the senate's armies?",
        "expected_fact": "Pompey led the senate's armies.",
    },
}


def _turn(
    answer: str,
    substep: str,
    *,
    block: dict | None = None,
    blocks: list | None = None,
    substep_passed: bool = True,
    block_complete: bool = True,
    move_attempts: int = 1,
    rubric_met: list[str] | None = None,
    stored_rubric: list[str] | None = None,
    state: dict | None = None,
):
    active = {"substep": substep, "dialogue_turns": 0, "block_attempts": 1}
    if state:
        active.update(state)
    chosen = block or GOAL
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=block_complete,
        rubric_met=["goal"] if rubric_met is None else rubric_met,
        stored_rubric=["kept"] if stored_rubric is None else stored_rubric,
        matched_wrong="",
        blocks=blocks or [chosen, NEXT],
        step=0,
        active_block_state=active,
        block_results=[],
        move_attempts=move_attempts,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=default_kc_tutor_config(),
        goal=None,
        last_misconception="",
        answer=answer,
    )


def _prompt(answer: str, substep: str, *, block: dict | None = None, blocks: list | None = None) -> str:
    chosen = blocks or [block or GOAL]
    return _text(
        node=_node(blocks=chosen),
        goal=_goal(),
        opening=False,
        last_answer=answer,
        attempts=1,
        active_block_state={"substep": substep, "last_task_substep": "main", "revealed_substep": False},
    )


def test_what_is_a_province_stays_on_the_summary_and_the_prompt_defines_it() -> None:
    stayed = _turn(
        "what is a province",
        "summary_check",
        blocks=[GOAL],
        state={"substep": "summary_check", "last_task_substep": "main", "block_attempts": 1},
    )
    assert stayed.decision == "stay"
    assert stayed.passed is False
    assert stayed.advance_block is False
    assert stayed.unit_complete is False
    assert stayed.move_attempts == 1
    assert stayed.next_block_state["substep"] == "summary_check"
    assert stayed.next_block_state["block_attempts"] == 1
    assert stayed.block_results == []
    assert stayed.rubric_met == ["kept"]

    text = _prompt("what is a province", "summary_check", blocks=[GOAL])
    turn = _section(text, "This turn")
    assert "Their question: what is a province." in turn
    assert "define it" in turn
    assert "Answer that question in one or two sentences." in turn
    assert "repeat the active question unchanged" in turn
    assert "help_requested=true" in turn
    assert "substep_passed=false" in turn
    assert "block_complete=false" in turn
    assert "Do not say the reply was partial, close, or a good start." in turn
    assert "keep discussing or move on" not in turn
    assert "concrete partial step" not in text


def test_who_is_pompey_is_not_a_partial_pass_and_the_prompt_reasks() -> None:
    stayed = _turn("who is Pompey?", "main")
    assert stayed.decision == "stay"
    assert stayed.passed is False
    assert stayed.advance_block is False
    assert stayed.move_attempts == 1
    assert stayed.next_block_state["substep"] == "main"
    assert stayed.next_block_state["block_attempts"] == 1
    assert stayed.block_results == []
    assert stayed.rubric_met == ["kept"]

    text = _prompt("who is Pompey?", "main")
    turn = _section(text, "This turn")
    assert "Their question: who is Pompey?." in turn
    assert "Answer that question in one or two sentences." in turn
    assert "define it" in turn
    assert "repeat the active question unchanged" in turn
    assert "ask the goal again" in turn
    assert "help_requested=true" in turn
    assert "substep_passed=false" in turn
    assert "block_complete=false" in turn
    assert "Do not say the reply was partial, close, or a good start." in turn
    assert "do not offer to move on" in turn.lower()
    assert "concrete partial step" not in text


def test_a_side_question_on_another_substep_is_not_an_attempt() -> None:
    stayed = _turn("where is the senate?", "recall", block=RECALL)
    assert stayed.decision == "stay"
    assert stayed.passed is False
    assert stayed.move_attempts == 1
    assert stayed.next_block_state["substep"] == "recall"
    assert stayed.rubric_met == ["kept"]

    why = _turn("why did Caesar cross?", "elaborate_why", block=RECALL)
    assert why.next_block_state["substep"] == "elaborate_why"
    assert why.move_attempts == 1

    text = _prompt("where is the senate?", "recall", block=RECALL)
    turn = _section(text, "This turn")
    assert "Answer that question in one or two sentences." in turn
    assert "repeat the active question unchanged" in turn
    assert "substep_passed=false" in turn


def test_a_real_attempt_and_a_move_on_keep_today_behavior() -> None:
    answered = _turn("Pompey led the senate's armies.", "main", rubric_met=[], stored_rubric=[])
    assert answered.next_block_state["substep"] == "summary_check"
    assert answered.passed is False

    closed = _turn("move on", "main", substep_passed=False, block_complete=False, rubric_met=[], stored_rubric=[])
    assert closed.advance_block is True
    assert closed.next_step == 1

    text = _prompt("Pompey led the senate's armies.", "main")
    assert "Side question:" not in text
    assert "ask whether the learner wants to continue discussing" in _section(text, "This turn")
