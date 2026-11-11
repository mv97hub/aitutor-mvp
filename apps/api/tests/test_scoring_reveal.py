"""A paraphrase the model already passed must not be marked revealed.

These are the Scarcity transcript cases: topic/goal, worked example, and teach-back.
Literal keyword overlap stays as the fallback when the model omits a pass.
"""

from app.kc_loop import answer_addresses_substep, resolve_block_turn
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _node, _section, _text

CFG = default_kc_tutor_config()

TOPIC = {
    "id": "tg1",
    "type": "topic_goal",
    "data": {
        "topic": "Scarcity",
        "goal": "Explain why scarcity is the central problem in economics and how it leads to choices",
        "acceptance_criteria": "Student can define scarcity, identify examples, and explain why it forces choices",
    },
}
TOPIC_PARAPHRASE = (
    "Scarcity leads to how resources are allocated, picked and bargained between groups. "
    "Scarcity of time for myself is a challenge, between kids and hobbies"
)

WORKED = {
    "id": "we1",
    "type": "worked_example",
    "data": {
        "problem_statement": "Maria spends the afternoon studying instead of seeing friends.",
        "steps": [
            {
                "step_text": "State the opportunity cost of Maria's choice.",
                "rationale": (
                    "The opportunity cost is the value of the next best alternative Maria gives up, "
                    "such as studying for her test."
                ),
            }
        ],
        "faded_step_index": 0,
        "solo_problem": "Jake has $15. A book costs $10. What does he give up?",
        "solo_expected_answer": "The opportunity cost is the movie tickets he cannot buy.",
    },
}
FADED_ANSWER = "She loses the chance to have fun with friends"
SOLO_ANSWER = "A book + $5 for something else"

TEACH = {
    "id": "teach1",
    "type": "teach_back",
    "data": {
        "peer_persona_prompt": "Explain to a friend why scarcity affects everyone",
        "required_concepts": [
            "Scarcity means limited resources for everyone",
            "Unlimited wants",
            "Necessity of making choices",
            "Opportunity cost",
        ],
        "peer_follow_up_question": "Can you give an example of a choice you made recently?",
    },
}
PRICE_ANSWER = (
    "Prices and inflation make goods expensive, so wealthy people still cannot buy "
    "every expensive thing they want."
)
TIME_ANSWER = "Time- looking after kids or taking interest in hobbies or chilling out"

NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}


def _turn(
    block: dict,
    answer: str,
    substep: str,
    *,
    substep_passed: bool = False,
    rubric_met: list[str] | None = None,
    stored_rubric: list[str] | None = None,
    move_attempts: int = 0,
    state: dict | None = None,
    prior_tutor: str = "",
    fragment: bool = False,
):
    active = {"substep": substep, "dialogue_turns": 0}
    if state:
        active.update(state)
        active["substep"] = substep
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=False,
        rubric_met=list(rubric_met or []),
        stored_rubric=list(stored_rubric or []),
        matched_wrong="",
        blocks=[block, dict(NEXT)],
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
        fragment=fragment,
        prior_tutor=prior_tutor,
    )


def _revealed(result) -> bool:
    return any(str(row.get("outcome") or "") == "revealed" for row in result.block_results)


def test_topic_goal_paraphrase_then_move_on_passes() -> None:
    assert answer_addresses_substep(TOPIC, "main", TOPIC_PARAPHRASE, {"substep": "main"}, CFG) is False

    awarded = _turn(TOPIC, TOPIC_PARAPHRASE, "main", rubric_met=["tg1"])
    assert awarded.advance_block is False
    assert awarded.next_block_state["substep"] == "summary_check"
    assert not awarded.next_block_state.get("revealed_substep")
    assert awarded.reveals == 0
    assert "tg1" in awarded.rubric_met

    closed = _turn(
        TOPIC,
        "move on",
        "summary_check",
        stored_rubric=awarded.rubric_met,
        state=awarded.next_block_state,
    )
    assert closed.advance_block is True
    assert closed.block_results[-1]["outcome"] == "passed"
    assert closed.reveals == 0
    assert not _revealed(closed)

    flagged = _turn(TOPIC, TOPIC_PARAPHRASE, "main", substep_passed=True)
    assert flagged.next_block_state["substep"] == "summary_check"
    assert not flagged.next_block_state.get("revealed_substep")

    # The transcript bug: evidence is already met, but the substep was left on main.
    stuck = _turn(TOPIC, "move on", "main", stored_rubric=["tg1"], move_attempts=1)
    assert stuck.block_results[-1]["outcome"] == "passed"
    assert stuck.reveals == 0

    for phrase in ("yes", "next part"):
        closed_phrase = _turn(TOPIC, phrase, "main", stored_rubric=["tg1"], move_attempts=1)
        assert closed_phrase.block_results[-1]["outcome"] == "passed", phrase
        assert closed_phrase.reveals == 0, phrase


def test_move_on_without_evidence_still_reveals_the_goal() -> None:
    gave_up = _turn(TOPIC, "move on", "main")
    assert gave_up.block_results[-1]["outcome"] == "revealed"
    assert gave_up.reveals == 1

    skipped = _turn(TOPIC, "skip", "main")
    assert skipped.block_results[-1]["outcome"] == "revealed"

    omitted = _turn(TOPIC, TOPIC_PARAPHRASE, "main")
    assert omitted.advance_block is False
    assert omitted.block_results == []
    assert omitted.next_block_state["substep"] == "main"
    assert omitted.move_attempts == 1


def test_a_one_word_goal_reply_does_not_pass_on_the_model_flag() -> None:
    fragment = _turn(TOPIC, "choices", "main", substep_passed=True, rubric_met=["tg1"], fragment=True)
    assert fragment.advance_block is False
    assert fragment.block_results == []
    assert fragment.next_block_state["substep"] == "main"


def test_worked_example_faded_paraphrase_advances_and_solo_passes() -> None:
    assert answer_addresses_substep(WORKED, "faded_step", FADED_ANSWER, {"substep": "faded_step"}, CFG) is False
    assert answer_addresses_substep(WORKED, "solo_solve", SOLO_ANSWER, {"substep": "solo_solve"}, CFG) is False

    faded = _turn(WORKED, FADED_ANSWER, "faded_step", rubric_met=["we1:faded_step"])
    assert faded.advance_block is False
    assert faded.next_block_state["substep"] == "solo_solve"
    assert not faded.next_block_state.get("revealed_substep")
    assert faded.reveals == 0
    assert faded.move_attempts == 0
    assert faded.block_results == []

    solo = _turn(
        WORKED,
        SOLO_ANSWER,
        "solo_solve",
        rubric_met=["we1:solo_solve"],
        stored_rubric=faded.rubric_met,
        state=faded.next_block_state,
    )
    assert solo.advance_block is True
    assert solo.block_results[-1]["outcome"] == "passed"
    assert solo.reveals == 0
    assert not _revealed(solo)

    flagged = _turn(WORKED, FADED_ANSWER, "faded_step", substep_passed=True)
    assert flagged.next_block_state["substep"] == "solo_solve"
    assert flagged.reveals == 0


def test_a_stuck_faded_step_grades_the_next_answer_as_solo() -> None:
    """Evidence for the faded step is stored, but the substep was never advanced."""
    solo = _turn(
        WORKED,
        SOLO_ANSWER,
        "faded_step",
        rubric_met=["we1:solo_solve"],
        stored_rubric=["we1:faded_step"],
        move_attempts=1,
        state={"block_attempts": 1},
    )
    assert solo.next_block_state.get("substep") != "faded_step"
    assert solo.block_results[-1]["outcome"] == "passed"
    assert solo.reveals == 0
    assert not _revealed(solo)


def test_yes_after_a_passed_solo_does_not_reveal() -> None:
    closed = _turn(
        WORKED,
        "yes",
        "solo_solve",
        stored_rubric=["we1:solo_solve"],
        prior_tutor="Ready for the next challenge?",
        move_attempts=1,
        state={"block_attempts": 1},
    )
    assert closed.block_results[-1]["outcome"] == "passed"
    assert closed.reveals == 0

    moved = _turn(
        WORKED,
        "move on",
        "solo_solve",
        stored_rubric=["we1:solo_solve"],
        prior_tutor="Ready for the next challenge?",
    )
    assert moved.block_results[-1]["outcome"] == "passed"
    assert moved.reveals == 0


def test_teach_back_follow_up_example_passes_instead_of_revealing() -> None:
    assert answer_addresses_substep(TEACH, "initial_explanation", PRICE_ANSWER, {}, CFG) is False
    assert answer_addresses_substep(TEACH, "initial_explanation", TIME_ANSWER, {}, CFG) is False

    first = _turn(TEACH, PRICE_ANSWER, "initial_explanation")
    assert first.block_results == []
    assert first.next_block_state["substep"] == "initial_explanation"
    assert first.move_attempts == 1
    assert first.reveals == 0

    second = _turn(
        TEACH,
        TIME_ANSWER,
        "initial_explanation",
        rubric_met=["teach1:initial_explanation"],
        stored_rubric=first.rubric_met,
        move_attempts=first.move_attempts,
        state=first.next_block_state,
    )
    assert second.reveals == 0
    assert not _revealed(second)
    assert second.next_block_state["substep"] == "peer_follow_up"
    assert second.move_attempts == 0

    flagged = _turn(
        TEACH,
        TIME_ANSWER,
        "initial_explanation",
        substep_passed=True,
        move_attempts=1,
        state={"block_attempts": 1},
    )
    assert flagged.reveals == 0
    assert not _revealed(flagged)
    assert flagged.next_block_state["substep"] == "peer_follow_up"

    follow = _turn(
        TEACH,
        TIME_ANSWER,
        "peer_follow_up",
        rubric_met=["teach1:follow_up_question"],
        stored_rubric=["teach1:initial_explanation"],
        move_attempts=1,
    )
    assert follow.reveals == 0
    assert not _revealed(follow)
    assert follow.next_block_state["substep"] == "summary_check"
    assert not follow.next_block_state.get("revealed_substep")

    # The model kept the explanation id while scoring the follow-up example.
    same_id = _turn(
        TEACH,
        TIME_ANSWER,
        "peer_follow_up",
        rubric_met=["teach1:initial_explanation"],
        move_attempts=1,
    )
    assert same_id.reveals == 0
    assert not _revealed(same_id)
    assert same_id.next_block_state["substep"] == "summary_check"


def test_teach_back_prompt_does_not_tag_a_fair_price_or_follow_up_example() -> None:
    node = _node(
        blocks=[TEACH],
        misconceptions=[
            {
                "wrong_move": "Thinking scarcity only applies to money or poor people.",
                "broken_kc": "",
            }
        ],
    )
    text = _text(
        node=node,
        opening=False,
        active_block_state={"substep": "initial_explanation"},
        prerequisite_status="none",
        support_band="ready",
    )
    teach = _section(text, "What to teach")
    assert "Thinking scarcity only applies to money or poor people" in teach
    assert "prices or inflation" in teach
    assert "follow-up example prompt" in teach
    assert "wealthy people" in teach
