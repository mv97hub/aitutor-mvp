"""The turn grades the child line just sent, and a stated chain finishes main."""

from app.kc_loop import resolve_block_turn
from app.kc_prompt import build_kc_prompt
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _goal, _node, _profile, _section, _student

PREVIOUS = "The economy moves up and down. That is the business cycle."
SIDE = "Did steve jobs have a favorite animal? I like dolphins."
CHAIN = (
    "When the government borrows more money, interest rates go up, "
    "so a business holds off on a tractor."
)

CYCLE = {
    "id": "blk_cycle",
    "type": "explanation",
    "data": {
        "block_title": "The business cycle",
        "topics": [
            {
                "id": "top_cycle",
                "title": "The business cycle",
                "explanation": (
                    "The business cycle is the up and down movement of the economy. "
                    "The four phases are expansion, peak, contraction, and trough."
                ),
                "key_points": "Up and down. Four phases.",
                "examples_or_analogies": "",
            },
            {
                "id": "top_causes",
                "title": "Causes",
                "explanation": "Spending and jobs push the cycle from one phase to the next.",
                "key_points": "Spending. Jobs.",
                "examples_or_analogies": "",
            },
        ],
        "summary_takeaway": "The economy rises and falls.",
    },
}
NEXT_BLOCK = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}
CROWDING = {
    "id": "crowd",
    "type": "topic_goal",
    "data": {
        "topic": "Crowding out",
        "goal": "Explain how government borrowing raises interest rates and makes a business hold off on a tractor.",
        "acceptance_criteria": (
            "When the government borrows more, interest rates rise, "
            "and a business holds off on a new tractor."
        ),
    },
}


def _explain_bundle(answer: str, last_messages: str) -> dict:
    return build_kc_prompt(
        student=_student(),
        profile=_profile(),
        node=_node(blocks=[CYCLE, NEXT_BLOCK]),
        goal=_goal(),
        step=0,
        opening=False,
        choice_on_screen=False,
        prerequisite_status="",
        support_band="ready",
        course_position="1 of 1",
        unit_complete=False,
        course_complete=False,
        attempts=0,
        hint_tier="nudge",
        reveals=0,
        off_course_count=0,
        affect="",
        enrichment_turns=0,
        help_requested=False,
        minutes_used=0,
        component_status="unknown",
        stability="0",
        last_answer=answer,
        last_misconception="",
        last_messages=last_messages,
        rubric_met=[],
        redirect_pending=False,
        fragment=False,
        others_known=False,
        active_block_state={"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 2, "elaboration_turns": 0},
    )


def _explain_turn(answer: str, *, substep_passed: bool = False):
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[CYCLE, NEXT_BLOCK],
        step=0,
        active_block_state={"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 2, "elaboration_turns": 0},
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


def _goal_turn(
    answer: str,
    *,
    substep: str = "main",
    substep_passed: bool = False,
    block_complete: bool = False,
    state: dict | None = None,
):
    active = {
        "substep": substep,
        "dialogue_turns": 2,
        "fragment_prompted": True,
        "block_attempts": 1,
    }
    if state:
        active.update(state)
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=block_complete,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[CROWDING, NEXT_BLOCK],
        step=0,
        active_block_state=active,
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=default_kc_tutor_config(),
        goal=None,
        last_misconception="",
        answer=answer,
        fragment=False,
    )


def test_a_side_question_is_graded_instead_of_the_previous_line() -> None:
    """The previous line restates the topic. The line just sent is a side question.

    A pass flag about that earlier line must not score the side question, and the
    prompt's last user message is the side question.
    """
    transcript = f"user: {PREVIOUS} | assistant: That's the cycle."
    bundle = _explain_bundle(SIDE, transcript)
    text = bundle["system_prompt"]
    happened = _section(text, "What just happened")
    turn = _section(text, "This turn")
    assert bundle["user_message"] == SIDE
    assert f"The last answer was: {SIDE}." in happened
    assert happened.rfind(f"user: {SIDE}") > happened.rfind(f"user: {PREVIOUS}")
    assert "Answer the side remark in one or two sentences" in turn
    assert "The learner already restated this point." not in turn

    previous = _explain_turn(PREVIOUS)
    assert previous.next_block_state["topic_index"] == 1

    side = _explain_turn(SIDE, substep_passed=True)
    assert side.next_block_state["topic_index"] == 0
    assert side.next_block_state["substep"] == "explain_topic"
    assert side.advance_block is False
    assert side.block_results == []


def test_a_topic_goal_answer_that_states_the_chain_finishes_main() -> None:
    finished = _goal_turn(CHAIN, substep_passed=False)
    assert finished.advance_block is True
    assert finished.next_step == 1
    assert finished.block_results[-1]["outcome"] == "passed"
    assert finished.next_block_state.get("revealed_substep") is not True


def test_whats_next_on_an_open_goal_does_not_pass() -> None:
    for flagged in (False, True):
        stayed = _goal_turn("What's next?", substep_passed=flagged)
        assert stayed.next_block_state["substep"] == "main", flagged
        assert stayed.advance_block is False, flagged
        assert stayed.block_results == [], flagged
        assert stayed.passed is False, flagged


def test_an_unfinished_summary_still_clears_a_late_correct_answer() -> None:
    cleared = _goal_turn(
        CHAIN,
        substep="summary_check",
        substep_passed=True,
        state={
            "substep": "summary_check",
            "last_task_substep": "main",
            "revealed_substep": True,
            "block_attempts": 2,
        },
    )
    assert cleared.advance_block is False
    assert cleared.next_block_state["substep"] == "summary_check"
    assert cleared.next_block_state.get("revealed_substep") is False
    assert cleared.block_results == []
