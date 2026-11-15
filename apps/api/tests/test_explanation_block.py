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


def test_ready_moves_to_the_next_topic_then_closes() -> None:
    first = _turn("got it", {"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 1, "elaboration_turns": 2})
    assert first.decision == "stay"
    assert first.unit_complete is False
    assert first.next_block_state["topic_index"] == 1
    assert first.next_block_state["substep"] == "explain_topic"
    assert first.next_block_state["elaboration_turns"] == 0
    second = _turn("Got it — ready for the next topic!", first.next_block_state)
    assert second.decision == "complete"
    assert second.unit_complete is True
    assert second.next_block_state.get("substep") != "summary_check"
    assert second.mark_fragile is False
    assert second.mark_known is True
    assert second.block_results[-1]["outcome"] == "engaged"
    assert second.reveals == 0


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
    assert "teach the next topic in full" in teaching.lower()
    assert "Do not teach that topic." not in teaching
    assert "Do not only name the title." in teaching
    assert "ask if they have questions or want elaboration" not in teaching.lower()
    assert "Causes" in teaching
    assert "Spending, jobs, and confidence push the cycle from one phase to the next." in teaching
    held = _cycle_turn("Why are there four phases?")
    assert held.next_block_state["topic_index"] == 0


LAGS = {
    "id": "blk_lags",
    "type": "explanation",
    "data": {
        "block_title": "Fiscal policy lags",
        "topics": [
            {
                "id": "top_recognition",
                "title": "Recognition lag",
                "explanation": "A recognition lag is the time before anyone sees the economy has turned.",
                "key_points": "Seeing the turn.",
                "examples_or_analogies": "",
            },
            {
                "id": "top_decision",
                "title": "Decision lag",
                "explanation": "A decision lag is the time lawmakers spend choosing a policy.",
                "key_points": "Choosing the policy.",
                "examples_or_analogies": "",
            },
            {
                "id": "top_implementation",
                "title": "Implementation lag",
                "explanation": "An implementation lag is the time to put that policy into action.",
                "key_points": "Putting it into action.",
                "examples_or_analogies": "",
            },
            {
                "id": "top_impact",
                "title": "Impact lag",
                "explanation": "An impact lag is the time before the policy changes spending.",
                "key_points": "Spending changes later.",
                "examples_or_analogies": "",
            },
        ],
        "summary_takeaway": "Fiscal policy takes time to recognize, decide, implement, and change spending.",
    },
}

WORKED = {
    "id": "blk_worked",
    "type": "worked_example",
    "data": {"problem_statement": "A government cuts taxes during a recession."},
}

_LAG_STATE = {"substep": "explain_topic", "topic_index": 3, "dialogue_turns": 4, "elaboration_turns": 0}

_OTHER_LAGS = (
    "A recognition lag is the time before anyone sees the economy has turned.",
    "A decision lag is the time lawmakers spend choosing a policy.",
    "An implementation lag is the time to put that policy into action.",
)


def _lags_prompt(answer: str) -> str:
    student = _student(
        child_profile={
            "response_length": "bite_sized",
            "reading_level": "on_grade",
            "explanation_style": "concrete_examples",
        }
    )
    return build_kc_prompt(
        student=student,
        profile=_profile_for(4),
        node=_node(blocks=[deepcopy(LAGS), deepcopy(WORKED)]),
        goal=_goal(),
        step=0,
        opening=False,
        choice_on_screen=False,
        prerequisite_status="",
        support_band="ready",
        course_position="1 of 2",
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
        active_block_state=dict(_LAG_STATE),
    )["system_prompt"]


def _lags_turn(answer: str, *, substep_passed: bool = False, block_complete: bool = False):
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=block_complete,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[deepcopy(LAGS), deepcopy(WORKED)],
        step=0,
        active_block_state=dict(_LAG_STATE),
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


RUHR = {
    "id": "blk_ruhr",
    "type": "explanation",
    "data": {
        "block_title": "The Ruhr crisis",
        "topics": [
            {
                "id": "top_ruhr",
                "title": "The Ruhr occupation",
                "explanation": (
                    "French and Belgian troops occupied the Ruhr. "
                    "Many Germans felt that occupation was an invasion."
                ),
                "key_points": "Occupation. Invasion.",
                "examples_or_analogies": "",
            },
            {
                "id": "top_passive",
                "title": "Passive Resistance",
                "explanation": (
                    "Workers in the Ruhr refused to work for the occupiers. "
                    "The government printed money to pay them, and prices rose."
                ),
                "key_points": "Refusal to work. Printed money.",
                "examples_or_analogies": "A strike against the occupation.",
            },
        ],
        "summary_takeaway": "The Ruhr occupation met passive resistance.",
    },
}
RUHR_NEXT = {"id": "blk_after", "type": "topic_goal", "data": {"topic": "Hyperinflation", "goal": "Explain hyperinflation."}}
RUHR_LINE = "The Ruhr occupation felt like an invasion."
RUHR_QUESTION = "So did they realize too late that Hitler could take control of those institutions too?"
PASSIVE_EXPLANATION = (
    "Workers in the Ruhr refused to work for the occupiers. "
    "The government printed money to pay them, and prices rose."
)


def _ruhr_prompt(answer: str) -> str:
    return build_kc_prompt(
        student=_student(),
        profile=_profile(),
        node=_node(blocks=[deepcopy(RUHR), deepcopy(RUHR_NEXT)]),
        goal=_goal(),
        step=0,
        opening=False,
        choice_on_screen=False,
        prerequisite_status="",
        support_band="ready",
        course_position="1 of 2",
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
        active_block_state={"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 2, "elaboration_turns": 0},
    )["system_prompt"]


def _ruhr_turn(answer: str, *, substep_passed: bool = False):
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[deepcopy(RUHR), deepcopy(RUHR_NEXT)],
        step=0,
        active_block_state={"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 2, "elaboration_turns": 0},
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


def test_a_ruhr_style_advance_is_short_and_does_not_teach_the_next_topic() -> None:
    """An accepted line moves on in one or two sentences, then the next topic's first line.

    It does not teach Passive Resistance, and it does not ask whether to elaborate.
    """
    moved = _ruhr_turn(RUHR_LINE, substep_passed=True)
    assert moved.next_block_state["topic_index"] == 1
    assert moved.next_block_state["substep"] == "explain_topic"
    assert moved.advance_block is False
    text = _ruhr_prompt(RUHR_LINE)
    teaching = text.split("What to teach", 1)[-1].split("Who you are talking to", 1)[0]
    lowered = text.lower()
    assert "one sentence" in lowered or "one or two sentences" in lowered
    assert "teach the next topic in full" in teaching.lower()
    assert "Topic 2 of 2: Passive Resistance." in teaching
    assert "Do not teach that topic." not in teaching
    assert "Do not only name the title." in teaching
    assert PASSIVE_EXPLANATION in text
    assert "A strike against the occupation." not in text
    assert "ask if they have questions or want elaboration" not in lowered
    assert "would you like me to elaborate" not in lowered
    assert "ask one question only: move on, or ask one more question" not in lowered


def test_a_question_on_an_unfinished_topic_stays_short() -> None:
    """A real question is one or two sentences, then one line back. It does not advance."""
    held = _ruhr_turn(RUHR_QUESTION, substep_passed=True)
    assert held.next_block_state["topic_index"] == 0
    assert held.advance_block is False
    text = _ruhr_prompt(RUHR_QUESTION)
    teaching = text.split("What to teach", 1)[-1].split("Who you are talking to", 1)[0]
    lowered = text.lower()
    assert "one or two sentences" in lowered
    assert "one line back" in lowered
    assert "Explain this topic from:" not in teaching
    assert PASSIVE_EXPLANATION not in text
    assert "ask if they have questions or want elaboration" not in lowered
    assert "would you like me to elaborate" not in lowered


def test_got_it_move_on_on_the_last_topic_opens_the_next_block() -> None:
    """Got it - move on closes the walkthrough. The next block arrives in its own message."""
    closed = _lags_turn("Got it - move on", substep_passed=True, block_complete=True)
    assert closed.advance_block is True
    assert closed.next_step == 1
    assert closed.next_block_id == "blk_worked"
    assert closed.next_block_state["substep"] == "faded_step"
    assert closed.next_block_state.get("substep") != "summary_check"
    assert closed.block_results[-1]["block_type"] == "explanation"
    text = _lags_prompt("Got it - move on")
    assert "The close is one or two sentences: what the block was, and that they are done." in text
    assert "Do not restate each topic." in text
    assert "Do not ask whether to move on." in text
    assert "Begin the next block in this same reply." not in text
    assert "The next block arrives in its own message." in text
    assert "First line:" not in text
    lowered = text.lower()
    assert "summarize every topic" not in lowered
    assert "topics to include in that summary" not in lowered
    assert "ask one question only: move on, or ask one more question" not in lowered
    for explanation in _OTHER_LAGS:
        assert explanation not in text
    assert "An impact lag is the time before the policy changes spending." not in text


def test_a_question_on_the_last_topic_is_answered_then_the_block_closes() -> None:
    question = "Why does the impact lag take time?"
    closed = _lags_turn(question, substep_passed=True, block_complete=True)
    assert closed.advance_block is True
    assert closed.next_step == 1
    assert closed.next_block_id == "blk_worked"
    assert closed.next_block_state["substep"] == "faded_step"
    text = _lags_prompt(question)
    assert "Answer the question in one or two sentences, then close the block." in text
    assert "The close is one or two sentences: what the block was, and that they are done." in text
    assert "Do not restate each topic." in text
    assert "Do not ask whether to move on." in text
    assert "Topic point, for the one-or-two-sentence answer only:" in text
    assert "An impact lag is the time before the policy changes spending." in text
    lowered = text.lower()
    assert "summarize every topic" not in lowered
    assert "topics to include in that summary" not in lowered
    assert "ask one question only: move on, or ask one more question" not in lowered
    for explanation in _OTHER_LAGS:
        assert explanation not in text
