"""Stay on course is enforced in the loop, not only as a prompt sentence."""

from copy import deepcopy

from app.kc_loop import resolve_block_turn, unscored_side_request
from app.kc_prompt import is_fragment
from app.models import default_kc_tutor_config
from tests.test_goal_start import EXPLAIN, TOPIC, _node_for
from tests.test_kc_prompt import _goal, _profile, _section, _student, _text

STORY = "Yesterday my dog chased a ball at the park."
TELL = "tell me"
WRONG = "I think the river is red."
GOAL = "The river is blue."
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain next."}}

HOLD_FLAGS = "Set substep_passed=false and block_complete=false."
NO_LABEL = "Do not call this reply partial, a close, or a good start."
FOLLOW = (
    "You may follow this tangent. Do not force a return to the question. "
    "The score still comes only from this step."
)


def _cfg(mode: str = "brief_answer_then_return") -> dict:
    cfg = deepcopy(default_kc_tutor_config())
    cfg["overarching"]["stay_on_course"] = mode
    return cfg


def _turn(
    answer: str,
    *,
    mode: str = "brief_answer_then_return",
    substep: str = "main",
    move_attempts: int = 1,
    substep_passed: bool = True,
    block_complete: bool = True,
    fragment: bool | None = None,
):
    return resolve_block_turn(
        decision="advance",
        substep_passed=substep_passed,
        block_complete=block_complete,
        rubric_met=["topic:main"],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(TOPIC), dict(NEXT)],
        step=0,
        active_block_state={"substep": substep, "dialogue_turns": 1},
        block_results=[],
        move_attempts=move_attempts,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=_cfg(mode),
        goal=None,
        last_misconception="",
        answer=answer,
        fragment=is_fragment(answer, GOAL) if fragment is None else fragment,
    )


def _prompt(answer: str, *, mode: str = "brief_answer_then_return", substep: str = "main", opening: bool = False) -> str:
    cfg = _cfg(mode)
    return _text(
        node=_node_for(),
        profile=_profile(kc_tutor_config=cfg, stay_on_course=mode != "exploratory"),
        student=_student(),
        goal=_goal(),
        opening=opening,
        last_answer=answer,
        attempts=0,
        fragment=is_fragment(answer, GOAL),
        active_block_state={"substep": substep, "dialogue_turns": 1},
    )


def test_tell_me_and_a_side_story_stay_when_the_setting_is_on() -> None:
    for phrase in (TELL, STORY):
        assert unscored_side_request(TOPIC, "main", phrase, {"substep": "main"}, _cfg()), phrase
        held = _turn(phrase, move_attempts=2)
        assert held.advance_block is False, phrase
        assert held.passed is False, phrase
        assert held.unit_complete is False, phrase
        assert held.move_attempts == 2, phrase
        assert held.next_step == 0, phrase
        assert held.next_block_state["substep"] == "main", phrase
        assert held.block_results == [], phrase
        assert held.rubric_met == [], phrase
        text = _prompt(phrase)
        turn = _section(text, "This turn")
        assert "then repeat the active question" in turn, phrase
        assert HOLD_FLAGS in turn, phrase
        assert "ask the goal again" in turn, phrase
        assert NO_LABEL in text, phrase
        assert "inside the safety rules" in turn, phrase
        assert "Summary close" not in text, phrase
        assert "1-2 word fragment" not in text, phrase


def test_the_same_lines_are_not_forced_to_stay_when_the_setting_is_off() -> None:
    for phrase in (TELL, STORY):
        assert unscored_side_request(TOPIC, "main", phrase, {"substep": "main"}, _cfg("exploratory")), phrase
        left = _turn(phrase, mode="exploratory", move_attempts=2)
        assert left.next_block_state["substep"] == "summary_check", phrase
        assert left.move_attempts != 2 or left.next_block_state["substep"] != "main", phrase
        text = _prompt(phrase, mode="exploratory")
        assert FOLLOW in text, phrase
        assert "then repeat the active question" not in text, phrase
        assert "The score still comes only from this step." in text, phrase


def test_a_real_answer_a_wrong_try_and_move_on_keep_todays_path() -> None:
    assert not unscored_side_request(TOPIC, "main", WRONG, {"substep": "main"}, _cfg())
    missed = _turn(WRONG, substep_passed=False, block_complete=False, move_attempts=0)
    assert missed.next_block_state["substep"] == "main"
    assert missed.move_attempts == 1
    assert "then repeat the active question" not in _prompt(WRONG)

    answered = _turn(GOAL, move_attempts=0)
    assert answered.next_block_state["substep"] == "summary_check"
    assert answered.advance_block is False

    moved = _turn("move on", substep_passed=False, block_complete=False, move_attempts=0)
    assert moved.advance_block is True
    assert moved.next_step == 1


def test_do_not_ask_still_blocks_a_quiz_and_a_student_question_is_answered() -> None:
    opening = _prompt("", substep="explain", opening=True)
    opening_turn = _section(opening, "This turn")
    how = _section(opening, "How to teach")
    assert EXPLAIN in opening_turn
    assert "Do not ask any question." in opening_turn
    assert "End a teaching or probing turn with a single clear question." not in how

    asked = "Why does the river look that way?"
    text = _prompt(asked, substep="explain")
    turn = _section(text, "This turn")
    teach = _section(text, "How to teach")
    assert "Answer that question first, in a sentence or two" in turn
    assert "Do not ask the goal question." in turn
    assert "does not mean ignore the question they typed" in turn
    assert "End a teaching or probing turn with a single clear question." not in teach
    assert "Do not ask any question." not in text
    stayed = _turn(asked, substep="explain", move_attempts=2, substep_passed=True, block_complete=True)
    assert stayed.advance_block is False
    assert stayed.next_block_state["substep"] == "explain"
    assert stayed.passed is False
