"""A revealed faded step states the answer and stops. A solved one still opens the solo problem."""

from app.kc_loop import resolve_block_turn
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _node, _section, _text

CFG = default_kc_tutor_config()
STEP = "quantitative data than to one dramatic experience"
REVERSED = "the scary story matters more than the count of on-time buses"
SOLO = "Jon checks many lock codes. Leila tries one meaningful number. Who is more reliable?"
SOLO_ANSWER = "Jon is more reliable because he checks many codes."
WORKED = {
    "id": "routes",
    "type": "worked_example",
    "data": {
        "problem_statement": "Maya compares a bus route's on-time record with one dramatic delay.",
        "steps": [
            {
                "step_text": STEP,
                "rationale": "A long record is steadier than one memorable trip.",
            }
        ],
        "faded_step_index": 0,
        "solo_problem": SOLO,
        "solo_expected_answer": SOLO_ANSWER,
    },
}
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}
RECALL = {
    "id": "recall",
    "type": "retrieval_check",
    "data": {
        "recall_prompt": "What is a menu cost?",
        "expected_fact": "A menu cost is the expense of changing prices.",
        "elaborative_why_prompt": "Why do menu costs matter?",
        "expected_why_rationale": "Firms change prices less often.",
    },
}


def _prompt(block: dict, answer: str, substep: str, *, attempts: int = 0, **state):
    return _text(
        node=_node(blocks=[dict(block), dict(NEXT)], misconceptions=[]),
        opening=False,
        attempts=attempts,
        last_answer=answer,
        last_messages=f"assistant: Fill the blank. | user: {answer}",
        active_block_state={"substep": substep, **state},
        fragment=False,
    )


def _turn(block: dict, answer: str, substep: str, *, substep_passed: bool = False, move_attempts: int = 0, **state):
    active = {"substep": substep, "dialogue_turns": 1}
    active.update(state)
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(block), dict(NEXT)],
        step=0,
        active_block_state=active,
        block_results=[],
        move_attempts=move_attempts,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer=answer,
    )


def _if_not_lines(text: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        if line.startswith("If not:"):
            found.append(line)
        elif " If not: " in line:
            found.append(line.split(" If not: ", 1)[1])
    return found


def test_a_revealed_faded_step_states_the_answer_and_does_not_open_solo() -> None:
    """The second reversed fill is a reveal. The reply stops on the given answer."""
    revealed = _turn(WORKED, REVERSED, "faded_step", move_attempts=1)
    assert revealed.advance_block is False
    assert revealed.decision == "stay"
    assert revealed.hint_tier == "reveal"
    assert revealed.next_block_state["substep"] == "faded_step"
    assert revealed.next_block_state["revealed_substep"] is True
    assert revealed.next_block_state.get("faded_answer_given") is True
    assert revealed.reveals == 1

    text = _prompt(WORKED, REVERSED, "faded_step", attempts=1)
    turn = _section(text, "This turn")
    teach = _section(text, "What to teach")
    assert "Ask no question." in turn
    assert "Do not open the next step." in turn
    assert "move to the next step" not in turn.lower()
    assert "present the solo problem" in text
    assert "Do not present the solo problem." in text
    for line in _if_not_lines(text):
        assert "ask no question" in line.lower(), line
        assert "move to the next step" not in line.lower(), line
        assert "present the solo problem" not in line.lower(), line

    known = _prompt(WORKED, "no idea", "faded_step", attempts=1)
    assert "Ask no question." in known
    assert "Do not present the solo problem." in known
    assert "present the solo problem in your reply" not in known
    assert "move to the next step" not in known.lower()
    assert "End a teaching or probing turn with a single clear question." not in known
    assert "then a guiding question" not in known
    stopped = _turn(WORKED, "no idea", "faded_step", move_attempts=1)
    assert stopped.next_block_state["substep"] == "faded_step"
    assert stopped.next_block_state["revealed_substep"] is True


def test_a_solved_faded_step_still_presents_the_solo_problem() -> None:
    text = _prompt(WORKED, STEP, "faded_step", attempts=0)
    assert "present the solo problem" in text
    assert "When this turn reveals the faded step" not in text
    solved = _turn(WORKED, STEP, "faded_step", substep_passed=True)
    assert solved.advance_block is False
    assert solved.next_block_state["substep"] == "solo_solve"
    assert not solved.next_block_state.get("revealed_substep")
    assert solved.hint_tier != "reveal"


def test_the_turn_after_a_reveal_asks_the_solo_problem() -> None:
    revealed = _turn(WORKED, "no idea", "faded_step", move_attempts=1)
    held = dict(revealed.next_block_state)
    held.pop("substep", None)
    opened = _turn(WORKED, "ok", "faded_step", **held)
    assert opened.advance_block is False
    assert opened.next_block_state["substep"] == "solo_solve"
    assert opened.next_block_state.get("faded_answer_given") is True
    assert not opened.next_block_state.get("revealed_substep")
    assert opened.move_attempts == 0

    text = _prompt(
        WORKED,
        "ok",
        "faded_step",
        attempts=0,
        revealed_substep=True,
        faded_answer_given=True,
    )
    teach = _section(text, "What to teach")
    turn = _section(text, "This turn")
    assert "Ask the learner to solve solo problem" in teach
    assert SOLO in teach
    assert "Do not present the solo problem." not in teach
    assert "move to the next step" not in turn.lower()
    assert "Active step:" in turn and "Solo Problem" in turn

    carried = dict(opened.next_block_state)
    carried.pop("substep", None)
    finished = _turn(WORKED, SOLO_ANSWER, "solo_solve", substep_passed=True, **carried)
    assert finished.advance_block is True
    assert finished.block_results[-1]["outcome"] == "revealed"


def test_a_solo_pass_still_stops_and_asks_no_question() -> None:
    text = _prompt(WORKED, SOLO_ANSWER, "solo_solve")
    turn = _section(text, "This turn")
    assert "Ask no question." in turn
    assert "Close in one sentence." in turn
    closed = _turn(WORKED, SOLO_ANSWER, "solo_solve", substep_passed=True)
    assert closed.advance_block is True
    assert closed.next_step == 1
    assert closed.block_results[-1]["outcome"] == "passed"
    assert closed.next_block_state.get("substep") != "summary_check"


def test_a_retrieval_reveal_still_moves_to_the_next_step() -> None:
    """Other block types keep the advance sentence. This reveal still asks why."""
    text = _prompt(RECALL, "no idea", "recall", attempts=1)
    assert "The reply then moves to the next step of this block." in text
    moved = _turn(RECALL, "no idea", "recall", move_attempts=1)
    assert moved.next_block_state["substep"] == "elaborate_why"
    assert moved.next_block_state.get("recall_revealed") is True
