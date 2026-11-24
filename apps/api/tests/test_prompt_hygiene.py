"""Teach-back names the node's misconception. Explanation settings are not dropped."""

from tests.test_kc_prompt import _node, _profile, _section, _text

TEACH = {
    "id": "teach",
    "type": "teach_back",
    "data": {
        "peer_persona_prompt": "Explain the idea to a friend.",
        "required_concepts": ["The idea applies widely."],
        "peer_follow_up_question": "Give one example.",
    },
}
EXPLAIN = {
    "id": "explain",
    "type": "explanation",
    "data": {
        "block_title": "Rivers",
        "topics": [
            {
                "title": "Color",
                "explanation": "The river is blue.",
                "key_points": "Blue.",
                "examples_or_analogies": "The sky.",
            }
        ],
        "summary_takeaway": "The river is blue.",
    },
}


def test_teach_back_uses_the_node_misconception_or_a_neutral_guard() -> None:
    named = _text(
        node=_node(
            blocks=[TEACH],
            misconceptions=[{"wrong_move": "The river is only blue at noon.", "broken_kc": ""}],
        ),
        opening=False,
        active_block_state={"substep": "initial_explanation"},
        prerequisite_status="none",
        support_band="ready",
    )
    teach = _section(named, "What to teach")
    assert 'do not tag "The river is only blue at noon."' in teach
    assert "Thinking scarcity only applies to money or poor people" not in named
    assert "follow-up example prompt" in teach

    bare = _text(
        node=_node(blocks=[TEACH], misconceptions=[]),
        opening=False,
        active_block_state={"substep": "initial_explanation"},
        prerequisite_status="none",
        support_band="ready",
    )
    guard = _section(bare, "What to teach")
    assert "do not tag a stored wrong move" in guard
    assert "scarcity" not in guard.lower()


def test_explanation_check_in_and_summary_style_reach_the_prompt() -> None:
    profile = _profile(
        kc_tutor_config={
            "blocks": {
                "explanation": {
                    "check_in_prompt_style": "brief_ready_check",
                    "end_of_block_summary_style": "concise_takeaway_only",
                }
            }
        }
    )
    text = _text(
        profile=profile,
        node=_node(blocks=[EXPLAIN], misconceptions=[]),
        opening=True,
        active_block_state={"substep": "explain_topic", "topic_index": 0},
        prerequisite_status="none",
        support_band="ready",
    )
    how = _section(text, "How to teach")
    turn = _section(text, "This turn")
    assert "Check-in style (brief_ready_check)" in how
    assert "ready for the next topic" in how
    assert "End-of-block summary (concise_takeaway_only)" in turn
    assert "only the takeaway" in turn
    assert "questions_or_elaborate" not in text
    assert "bulleted_recap_with_takeaway" not in text


def test_stability_stays_stored_and_out_of_the_prompt() -> None:
    text = _text(stability="zz-stability-kept")
    assert "zz-stability-kept" not in text
    assert "Stability:" not in text
