"""A topic or goal starts with an explanation. The question waits for move on."""

from app.kc_loop import learner_done_with_explanation, resolve_block_turn
from app.kc_prompt import build_kc_prompt, default_substep_for_block, substeps_for_block
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _goal, _node, _profile, _section, _student, _text

TOPIC = {
    "id": "topic",
    "type": "topic_goal",
    "data": {
        "topic": "River color",
        "goal": "The river is blue.",
        "acceptance_criteria": "The river is blue.",
    },
}

EXPLAIN = (
    "Goal start: Explain what this topic is and why it matters. "
    "Write it as teaching, not a question. Do not ask the goal question. Do not ask any question."
)
DEEPEN = (
    "Goal start: The learner wants to keep learning. Explain this same topic more deeply, from a fresh angle. "
    "Write it as teaching, not a question. Do not ask the goal question. Do not ask any question."
)
ASK = (
    "Goal question: The learner moved on. Ask the opening question for this goal. "
    "One question, and it comes last. Do not answer it."
)


def _node_for():
    return _node(blocks=[dict(TOPIC), {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain next."}}])


def _prompt(*, opening: bool, last_answer: str, substep: str = "explain") -> str:
    return _text(
        node=_node_for(),
        opening=opening,
        last_answer=last_answer,
        attempts=0,
        active_block_state={"substep": substep, "dialogue_turns": 0, "elaboration_turns": 0},
    )


def test_a_new_topic_starts_on_the_explanation() -> None:
    assert default_substep_for_block(TOPIC) == "explain"
    assert substeps_for_block(TOPIC) == ["explain", "main", "summary_check"]


def test_the_first_turn_explains_and_does_not_ask() -> None:
    text = _prompt(opening=True, last_answer="")
    turn = _section(text, "This turn")
    how = _section(text, "How to teach")
    teach = _section(text, "What to teach")
    assert EXPLAIN in turn
    assert "Do not ask the goal question." in turn
    assert ASK not in text
    assert "End a teaching or probing turn with a single clear question." not in how
    assert "Do not ask the learner to state the goal yet." in teach
    assert "Turn Stance (guided_discovery)" not in turn


def test_tell_me_more_keeps_explaining_without_the_goal_question() -> None:
    for phrase in ("Tell me more", "keep learning", "Can you explain more?"):
        text = _prompt(opening=False, last_answer=phrase)
        turn = _section(text, "This turn")
        assert DEEPEN in turn, phrase
        assert ASK not in text, phrase
        assert "Do not ask any question." in turn, phrase


def test_move_on_is_the_only_prompt_path_to_the_opening_question() -> None:
    for phrase in ("Got it - move on", "move on", "I don't want to learn more"):
        assert learner_done_with_explanation(phrase), phrase
        text = _prompt(opening=False, last_answer=phrase)
        turn = _section(text, "This turn")
        how = _section(text, "How to teach")
        assert ASK in turn, phrase
        assert "Do not ask the goal question." not in turn, phrase
        assert "Ask the opening question for this goal." in how, phrase
        assert "End a teaching or probing turn with a single clear question." in how, phrase
    assert not learner_done_with_explanation("Tell me more")
    assert not learner_done_with_explanation("I want to keep learning")


def test_tell_me_more_stays_on_the_explanation() -> None:
    stayed = _turn("Tell me more")
    assert stayed.advance_block is False
    assert stayed.unit_complete is False
    assert stayed.move_attempts == 0
    assert stayed.next_block_state["substep"] == "explain"
    assert stayed.next_block_state["elaboration_turns"] == 1
    again = _turn("keep learning", state=stayed.next_block_state)
    assert again.next_block_state["substep"] == "explain"
    assert again.next_block_state["elaboration_turns"] == 2


def test_move_on_opens_the_question_and_does_not_finish_the_goal() -> None:
    for phrase in ("Got it - move on", "move on", "I don't want to learn more"):
        opened = _turn(phrase)
        assert opened.advance_block is False, phrase
        assert opened.unit_complete is False, phrase
        assert opened.passed is False, phrase
        assert opened.next_block_state["substep"] == "main", phrase
        assert opened.block_results == [], phrase


def test_a_goal_answer_during_the_explanation_does_not_open_the_question() -> None:
    stayed = _turn("The river is blue.")
    assert stayed.next_block_state["substep"] == "explain"
    assert stayed.advance_block is False


def test_the_question_phase_still_checks_the_goal() -> None:
    answered = resolve_block_turn(
        decision="stay",
        substep_passed=True,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[TOPIC],
        step=0,
        active_block_state={"substep": "main"},
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=default_kc_tutor_config(),
        goal=None,
        last_misconception="",
        answer="The river is blue.",
    )
    assert answered.next_block_state["substep"] == "summary_check"


def test_prompt_builder_uses_the_same_goal_start_lines() -> None:
    text = build_kc_prompt(
        student=_student(),
        profile=_profile(),
        node=_node_for(),
        goal=_goal(),
        step=0,
        opening=True,
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
        last_answer="",
        last_misconception="",
        last_messages="",
        rubric_met=[],
        redirect_pending=False,
        fragment=False,
        others_known=False,
        active_block_state={"substep": "explain"},
    )["system_prompt"]
    assert EXPLAIN in text


def _turn(answer: str, state: dict | None = None):
    return resolve_block_turn(
        decision="stay",
        substep_passed=True,
        block_complete=True,
        rubric_met=["topic"],
        stored_rubric=[],
        matched_wrong="",
        blocks=[TOPIC, {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain next."}}],
        step=0,
        active_block_state=state or {"substep": "explain", "elaboration_turns": 0},
        block_results=[],
        move_attempts=2,
        hint_tier="scaffold",
        reveals=0,
        enrichment_turns=0,
        cfg=default_kc_tutor_config(),
        goal=None,
        last_misconception="",
        answer=answer,
    )
