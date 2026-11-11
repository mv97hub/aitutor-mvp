"""A correct worked-example solo answer closes the block. One yes after a continue question does too."""

from app.kc_loop import resolve_block_turn
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _node, _section, _text

WORKED = {
    "id": "work",
    "type": "worked_example",
    "data": {
        "problem_statement": "Name the color.",
        "steps": [{"step_text": "Look at the water."}],
        "solo_problem": "What color is the river?",
        "solo_expected_answer": "The river is blue.",
    },
}
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain next."}}
CFG = default_kc_tutor_config()


def _node_for():
    return _node(blocks=[dict(WORKED), dict(NEXT)], misconceptions=[])


def _prompt(*, last_answer: str, last_messages: str, substep: str, **state):
    return _text(
        node=_node_for(),
        opening=False,
        attempts=0,
        last_answer=last_answer,
        last_messages=last_messages,
        active_block_state={"substep": substep, **state},
        fragment=False,
    )


def _turn(answer: str, substep: str, *, substep_passed: bool = False, prior_tutor: str = "", move_attempts: int = 0, **state):
    active = {"substep": substep, "dialogue_turns": 0}
    active.update(state)
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(WORKED), dict(NEXT)],
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
        prior_tutor=prior_tutor,
    )


def test_a_correct_solo_answer_completes_the_block_without_a_follow_up_question() -> None:
    text = _prompt(
        last_answer="The river is blue.",
        last_messages="assistant: What color is the river? | user: The river is blue.",
        substep="solo_solve",
    )
    turn = _section(text, "This turn")
    how = _section(text, "How to teach")
    teach = _section(text, "What to teach")
    assert "short affirmation of that answer" in turn
    assert "Do not ask Ready for the next challenge." in turn
    assert "Do not summarize the block" in turn
    assert "do not ask whether to discuss or move on" in turn
    assert "Set substep_passed=true and block_complete=true." in turn
    assert "Ask no question." in turn
    assert "ask whether the learner wants to continue discussing" not in text
    assert "Give a short summary of what this block covered" not in text
    assert "End a teaching or probing turn with a single clear question." not in how
    assert "Ask the learner to solve solo problem" not in teach
    assert "Do not ask them to solve it again." in teach

    solved = _turn("The river is blue.", "solo_solve", substep_passed=True)
    assert solved.advance_block is True
    assert solved.next_step == 1
    assert solved.block_results[-1]["outcome"] == "passed"
    assert solved.next_block_state.get("substep") != "summary_check"


def test_one_yes_or_move_on_after_a_continue_question_closes_without_asking_again() -> None:
    cases = (
        ("Ready for the next challenge?", "yes"),
        ("Ready for the next challenge?", "move on"),
        ("Shall we move on to the next part?", "next part"),
    )
    for prior, answer in cases:
        text = _prompt(
            last_answer=answer,
            last_messages=f"assistant: {prior} | user: {answer}",
            substep="summary_check",
            last_task_substep="solo_solve",
        )
        turn = _section(text, "This turn")
        assert "one short closing line and no question" in turn, answer
        assert "Do not restate the summary." in turn, answer
        assert "Do not ask again." in turn, answer
        assert "Set block_complete=true." in turn, answer
        assert "ask whether the learner wants to continue discussing" not in text, answer
        assert "Give a short summary of what this block covered" not in text, answer
        assert "End a teaching or probing turn with a single clear question." not in _section(text, "How to teach"), answer

        closed = _turn(
            answer,
            "summary_check",
            prior_tutor=prior,
            last_task_substep="solo_solve",
            block_attempts=1,
        )
        assert closed.advance_block is True, answer
        assert closed.next_step == 1, answer
        assert closed.block_results[-1]["outcome"] == "passed", answer


def test_a_bare_yes_on_an_ordinary_worked_step_is_not_a_close() -> None:
    text = _prompt(
        last_answer="yes",
        last_messages="assistant: What color is the river? | user: yes",
        substep="solo_solve",
    )
    assert "A bare yes is not a close on this worked step." in text
    assert "The learner is answering a continue question." not in text
    assert "This solo answer is correct." not in text

    stayed = _turn("yes", "solo_solve", prior_tutor="What color is the river?")
    assert stayed.advance_block is False
    assert stayed.next_block_state["substep"] == "solo_solve"
    assert stayed.block_results == []

    faded = _turn(
        "Look at the water and name the color.",
        "faded_step",
        substep_passed=True,
        prior_tutor="Supply the missing step.",
    )
    assert faded.advance_block is False
    assert faded.next_block_state["substep"] == "solo_solve"
