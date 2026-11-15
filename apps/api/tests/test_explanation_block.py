"""An explanatory walkthrough teaches topics, then summarizes. It never quizzes."""

from copy import deepcopy

from app.kc_loop import resolve_block_turn
from app.kc_prompt import build_kc_prompt
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _goal, _node, _profile, _student

BLOCK = {
    "id": "blk_explain",
    "type": "explanation",
    "data": {
        "block_title": "Fractions",
        "topics": [
            {
                "id": "top_1",
                "title": "Denominator",
                "explanation": "The denominator is the bottom number. It names how many equal parts the whole is split into.",
                "key_points": "Bottom number. Equal parts.",
                "examples_or_analogies": "A pizza cut into 8 slices.",
            },
            {
                "id": "top_2",
                "title": "Numerator",
                "explanation": "The numerator is the top number. It names how many of those equal parts we have.",
                "key_points": "Top number. Parts we have.",
                "examples_or_analogies": "3 of the 8 slices.",
            },
        ],
        "summary_takeaway": "The denominator names the parts, and the numerator names how many we have.",
    },
}


def _prompt(**overrides: object) -> str:
    student = _student(
        child_profile={
            "response_length": "bite_sized",
            "reading_level": "on_grade",
            "explanation_style": "concrete_examples",
        }
    )
    node = _node(blocks=[deepcopy(BLOCK)])
    profile = overrides.pop("profile", _profile())
    values: dict[str, object] = {
        "student": student,
        "profile": profile,
        "node": node,
        "goal": _goal(),
        "step": 0,
        "opening": True,
        "choice_on_screen": False,
        "prerequisite_status": "",
        "support_band": "ready",
        "course_position": "1 of 1",
        "unit_complete": False,
        "course_complete": False,
        "attempts": 0,
        "hint_tier": "nudge",
        "reveals": 0,
        "off_course_count": 0,
        "affect": "",
        "enrichment_turns": 0,
        "help_requested": False,
        "minutes_used": 0,
        "component_status": "unknown",
        "stability": "0",
        "last_answer": "",
        "last_misconception": "",
        "last_messages": "",
        "rubric_met": [],
        "redirect_pending": False,
        "fragment": False,
        "others_known": False,
        "active_block_state": {"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 0, "elaboration_turns": 0},
    }
    values.update(overrides)
    return build_kc_prompt(**values)["system_prompt"]


def _cfg(depth: int = 4, allow: bool = True) -> dict:
    cfg = default_kc_tutor_config()
    cfg["blocks"]["explanation"]["explanation_depth"] = depth
    cfg["blocks"]["explanation"]["allow_depth_override_student_length"] = allow
    return cfg


def _profile_for(depth: int = 4, allow: bool = True):
    return _profile(kc_tutor_config=_cfg(depth, allow))


def test_depth_four_overrides_bite_sized_length() -> None:
    text = _prompt(profile=_profile_for(4))
    assert "CROSS-LAYER LENGTH OVERRIDE FOR EXPLANATORY BLOCK" in text
    assert "bite_sized" in text
    assert "on_grade" in text
    assert "concrete_examples" in text
    assert "Keep response length bite-sized" not in text
    assert "Do NOT quiz" in text
    assert "Denominator" in text
    assert "Numerator" not in text.split("What to teach", 1)[-1].split("Who you are talking to", 1)[0]


def test_depth_one_keeps_response_length_and_names_elaboration() -> None:
    text = _prompt(profile=_profile_for(1))
    assert "CROSS-LAYER LENGTH OVERRIDE" not in text
    assert "Keep response length bite-sized" in text
    assert "If the learner asks to elaborate, do NOT truncate" in text
    assert "Explanation depth 1 of 5" in text


def test_summary_lists_every_topic() -> None:
    text = _prompt(
        profile=_profile_for(4),
        opening=False,
        active_block_state={"substep": "summary_check", "topic_index": 1, "dialogue_turns": 3, "elaboration_turns": 0},
    )
    teaching = text.split("What to teach", 1)[-1].split("Who you are talking to", 1)[0]
    assert "Denominator" in teaching
    assert "Numerator" in teaching
    assert "summary_check" in teaching
    assert "congratulate the learner once for finishing this block" in teaching.lower()
    assert "ask one question only: move on, or ask one more question" in teaching.lower()
    assert "do not offer one more example" in teaching.lower()
    assert "any other final questions" not in teaching.lower()
    assert "do not open the next block" in teaching.lower()
    how = text.split("How to teach", 1)[-1].split("How to sound", 1)[0]
    assert "then ask if there are any final questions" not in how.lower()
    assert "any other final questions" not in how.lower()
    assert "congratulate the learner once for finishing this block" in how.lower()
    assert "ask one question only: move on, or ask one more question" in how.lower()


def _turn(answer: str, state: dict, *, substep_passed: bool = False, block_complete: bool = False):
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=block_complete,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[deepcopy(BLOCK)],
        step=0,
        active_block_state=state,
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=_cfg(),
        goal=None,
        last_misconception="",
        answer=answer,
    )


def test_a_question_stays_on_the_topic() -> None:
    result = _turn(
        "Why is the denominator on the bottom?",
        {"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 1, "elaboration_turns": 0},
    )
    assert result.decision == "stay"
    assert result.mark_fragile is False
    assert result.next_block_state["topic_index"] == 0
    assert result.next_block_state["substep"] == "explain_topic"
    assert result.next_block_state["elaboration_turns"] == 1
    assert result.block_results == []


def test_got_it_wrong_does_not_advance() -> None:
    result = _turn(
        "I got it wrong",
        {"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 1, "elaboration_turns": 0},
    )
    assert result.next_block_state["topic_index"] == 0
    assert result.next_block_state["elaboration_turns"] == 1


def test_ready_moves_to_the_next_topic_then_the_summary() -> None:
    first = _turn("got it", {"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 1, "elaboration_turns": 2})
    assert first.decision == "stay"
    assert first.unit_complete is False
    assert first.next_block_state["topic_index"] == 1
    assert first.next_block_state["substep"] == "explain_topic"
    assert first.next_block_state["elaboration_turns"] == 0
    second = _turn("Got it — ready for the next topic!", first.next_block_state)
    assert second.next_block_state["substep"] == "summary_check"
    assert second.unit_complete is False
    done = _turn("No final questions — let's continue!", second.next_block_state)
    assert done.decision == "complete"
    assert done.unit_complete is True
    assert done.mark_fragile is False
    assert done.mark_known is True
    assert done.block_results[-1]["outcome"] == "engaged"
    assert done.reveals == 0


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
                    "The four phases are expansion, peak, contraction, and trough. "
                    "GDP rises in an expansion and falls in a contraction. "
                    "The Great Recession was a deep contraction."
                ),
                "key_points": "Up and down. Four phases. GDP. The Great Recession.",
                "examples_or_analogies": "A roller coaster.",
            },
            {
                "id": "top_causes",
                "title": "Causes",
                "explanation": "Spending, jobs, and confidence push the cycle from one phase to the next.",
                "key_points": "Spending. Jobs. Confidence.",
                "examples_or_analogies": "",
            },
        ],
        "summary_takeaway": "The economy rises and falls.",
    },
}


def _cycle_prompt(answer: str) -> str:
    student = _student(
        child_profile={
            "response_length": "bite_sized",
            "reading_level": "on_grade",
            "explanation_style": "concrete_examples",
        }
    )
    return build_kc_prompt(
        student=student,
        profile=_profile_for(5),
        node=_node(blocks=[deepcopy(CYCLE), deepcopy(BLOCK)]),
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
        last_messages="",
        rubric_met=[],
        redirect_pending=False,
        fragment=False,
        others_known=False,
        active_block_state={"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 1, "elaboration_turns": 0},
    )["system_prompt"]


def _cycle_turn(answer: str):
    return resolve_block_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[deepcopy(CYCLE), deepcopy(BLOCK)],
        step=0,
        active_block_state={"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 1, "elaboration_turns": 0},
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=_cfg(5),
        goal=None,
        last_misconception="",
        answer=answer,
    )


def test_a_side_remark_on_an_explanatory_topic_stays_one_or_two_sentences() -> None:
    dog = "Why does my dog bark at the mail?"
    text = _cycle_prompt(dog)
    teaching = text.split("What to teach", 1)[-1].split("Who you are talking to", 1)[0]
    how = text.split("How to teach", 1)[-1].split("How to sound", 1)[0]
    assert "one or two sentences" in text
    assert "one line back to the active lesson" in teaching
    assert "Do not start a new explanation of this block." in teaching
    assert "Explain this topic from:" not in teaching
    assert "The Great Recession was a deep contraction." not in text
    assert "CROSS-LAYER LENGTH OVERRIDE" not in text
    assert "Explanation depth" not in how
    assert "break the topic into a new step-by-step" not in text
    assert "as many sentences" not in text.lower()
    assert "Do not re-teach this topic." in how
    stayed = _cycle_turn(dog)
    assert stayed.next_block_state["topic_index"] == 0
    assert stayed.next_block_state["substep"] == "explain_topic"
    assert stayed.advance_block is False


def test_an_explanatory_restatement_moves_to_the_next_topic() -> None:
    said = "The economy moves up and down. That is the business cycle."
    moved = _cycle_turn(said)
    assert moved.next_block_state["topic_index"] == 1
    assert moved.next_block_state["substep"] == "explain_topic"
    assert moved.advance_block is False
    assert moved.block_results == []
    text = _cycle_prompt(said)
    teaching = text.split("What to teach", 1)[-1].split("Who you are talking to", 1)[0]
    assert "Name anything missed in one sentence." in teaching
    assert "Do not re-teach the whole topic." in teaching
    assert "Explain this topic from:" not in teaching
    assert "Topic point, already said, for the one-sentence gap only:" in teaching
    assert "explain the next topic" in teaching.lower()
    assert "Causes" in teaching
    held = _cycle_turn("Why are there four phases?")
    assert held.next_block_state["topic_index"] == 0
