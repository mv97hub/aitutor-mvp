"""The opening explanation ends four ways, and the reply matches the step change.

Got it - move on, a ready signal the model flags, an on-topic answer, and a cap
of two extra turns. A stuck chat sat on this step for ten turns while the child
asked "What's next?". These tests keep that from happening again.
"""

from copy import deepcopy

from app.kc_loop import (
    EXPLAIN_EXTRA_TURN_CAP,
    answers_during_explanation,
    explain_step_turn,
    resolve_block_turn,
)
from app.kc_prompt import READY_FIELD, build_kc_prompt, default_substep_for_block
from app.models import ALL_BLOCK_TYPES, default_kc_tutor_config
from tests.test_explanation_block import BLOCK as EXPLANATORY
from tests.test_explanation_block import _prompt as _explanatory_prompt
from tests.test_explanation_block import _turn as _explanatory_turn
from tests.test_goal_start import APPLE, APPLE_NEXT, ASK, DEEPEN, REAL_APPLE, _apple_cfg
from tests.test_kc_prompt import _bundle, _goal, _node, _profile, _section, _student

READY_SIGNALS = ("What's next?", "ok", "I get it", "let's go")
SIDE_REMARKS = ("arsenal are great", "What is an apple", "What is a computer?")
WRONG_APPLE = "The Apple I was a phone that people carried"

READY_LINE = (
    "Ready check: If the learner's message means they are ready to go on, such as What's next?, ok, I get it, "
    "or let's go, set ready_to_move_on=true and ask the opening question for this goal instead."
)
NO_TURN_LINE = (
    "Do not tell the learner it is their turn, and do not ask them to put the idea in their own words, "
    "unless this reply asks the goal question."
)
CAP_LINE = (
    "Goal question: The learner has had two extra turns on this explanation, so you ask the goal question now."
)
EARLY_LINE = (
    "Goal answer: The learner answered during the explanation, before the goal question was asked. "
    "Count that answer as their attempt at this goal and score it."
)
SIDE_LINE = (
    "Goal start: The learner typed a side remark. It is not an attempt and it is not a request to learn more. "
    "Answer it inside the safety rules, in one or two sentences, then one line back to the active lesson. "
    "Do not start a new explanation of this topic. "
    "Do not ask the goal question. "
    "Do not ask a question applies to your lesson text, not to the student. "
    "It does not mean ignore the question they typed. "
    "Do not score this reply. Do not say Nice connection. "
    "Set help_requested=true, substep_passed=false, and block_complete=false. "
    "Do not call this reply partial, a close, or a good start."
)
CLARIFICATION = "Do not ask a question applies to your lesson text, not to the student."
HINT_ORDER = (
    "When the learner is stuck, start with a nudge, then an analogy, then a scaffold, "
    "and reveal the goal only after those hints."
)


def _state(**extra: int) -> dict:
    return {"substep": "explain", "dialogue_turns": 1, "elaboration_turns": 0, **extra}


def _turn(
    answer: str,
    state: dict | None = None,
    *,
    ready: bool = False,
    substep_passed: bool = False,
    rubric_met: list[str] | None = None,
    mode: str = "brief_answer_then_return",
):
    return resolve_block_turn(
        decision="stay",
        substep_passed=substep_passed,
        block_complete=False,
        rubric_met=list(rubric_met or []),
        stored_rubric=["kept"],
        matched_wrong="",
        blocks=[dict(APPLE), dict(APPLE_NEXT)],
        step=0,
        active_block_state=dict(state or _state()),
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=_apple_cfg(mode),
        goal=None,
        last_misconception="",
        answer=answer,
        learner_ready=ready,
    )


def _bundle_for(answer: str, state: dict | None = None, *, opening: bool = False) -> dict:
    return _bundle(
        node=_node(blocks=[dict(APPLE), dict(APPLE_NEXT)]),
        profile=_profile(kc_tutor_config=_apple_cfg()),
        opening=opening,
        last_answer=answer,
        attempts=0,
        active_block_state=dict(state or _state()),
    )


def _prompt(answer: str, state: dict | None = None, *, opening: bool = False) -> str:
    return _bundle_for(answer, state, opening=opening)["system_prompt"]


def _opened_without_a_score(result) -> None:
    assert result.next_block_state["substep"] == "main"
    assert result.next_step == 0
    assert result.advance_block is False
    assert result.unit_complete is False
    assert result.passed is False
    assert result.block_results == []
    assert result.move_attempts == 0
    assert result.next_block_state["elaboration_turns"] == 0
    assert result.next_block_state["side_turns"] == 0
    assert "block_attempts" not in result.next_block_state


# Exit 1. The button is unchanged.


def test_the_button_still_opens_the_goal_question() -> None:
    opened = _turn("Got it - move on")
    _opened_without_a_score(opened)
    turn = _section(_prompt("Got it - move on"), "This turn")
    assert ASK in turn
    assert READY_LINE not in turn
    assert NO_TURN_LINE not in turn


# Exit 2. A ready signal, read from one more field on the decision.


def test_a_ready_signal_the_model_flags_opens_the_goal_question() -> None:
    for phrase in READY_SIGNALS:
        opened = _turn(phrase, ready=True, substep_passed=True, rubric_met=["apple"])
        _opened_without_a_score(opened)
        # A ready signal scores nothing, whatever else the model set.
        assert opened.rubric_met == ["kept"], phrase


def test_the_stuck_whats_next_chat_stays_without_the_flag_and_moves_with_it() -> None:
    # Before: the reply was read as a side question, so the step never changed.
    stayed = _turn("What's next?")
    assert stayed.next_block_state["substep"] == "explain"
    assert stayed.next_block_state["side_turns"] == 1
    # After: the same reply with the model's ready flag opens the question.
    moved = _turn("What's next?", stayed.next_block_state, ready=True)
    _opened_without_a_score(moved)


def test_a_staying_turn_asks_the_model_for_the_ready_flag() -> None:
    for phrase in (*READY_SIGNALS, *SIDE_REMARKS, "I don't know"):
        bundle = _bundle_for(phrase)
        schema = bundle["response_schema"]
        turn = _section(bundle["system_prompt"], "This turn")
        assert READY_LINE in turn, phrase
        assert "Otherwise set ready_to_move_on=false." in turn, phrase
        assert turn.count("Ready check:") == 1, phrase
        # The flag comes first, so it is settled before the reply is written.
        assert list(schema["properties"])[0] == READY_FIELD, phrase
        assert schema["required"][0] == READY_FIELD, phrase
        assert schema["properties"][READY_FIELD]["type"] == "boolean", phrase


def test_the_ready_flag_is_asked_for_only_where_the_loop_reads_it() -> None:
    cases = (
        ("", _state(), True),
        ("Tell me more", _state(), False),
        ("Got it - move on", _state(), False),
        (REAL_APPLE, _state(), False),
        ("What is a computer?", _state(side_turns=EXPLAIN_EXTRA_TURN_CAP), False),
        ("What's next?", {"substep": "main", "dialogue_turns": 2}, False),
        ("What's next?", {"substep": "summary_check", "dialogue_turns": 3}, False),
    )
    for answer, state, opening in cases:
        bundle = _bundle_for(answer, state, opening=opening)
        assert READY_FIELD not in bundle["response_schema"]["properties"], (answer, state)
        assert READY_FIELD not in bundle["response_schema"]["required"], (answer, state)
        assert "Ready check:" not in bundle["system_prompt"], (answer, state)


def test_the_ready_flag_does_not_override_tell_me_more_or_a_later_step() -> None:
    deeper = _turn("Tell me more", ready=True)
    assert deeper.next_block_state["substep"] == "explain"
    assert deeper.next_block_state["elaboration_turns"] == 1
    later = _turn("What's next?", {"substep": "main", "dialogue_turns": 2}, ready=True)
    assert later.next_block_state["substep"] == "main"
    assert later.block_results == []
    assert later.advance_block is False


# Exit 3. An on-topic answer is scored in the same turn as the first try.


def test_an_on_topic_answer_that_passes_is_scored_in_the_same_turn() -> None:
    assert answers_during_explanation(APPLE, REAL_APPLE, _state(), _apple_cfg())
    passed = _turn(REAL_APPLE, substep_passed=True, rubric_met=["apple"])
    assert passed.next_block_state["substep"] == "summary_check"
    assert passed.next_block_state["block_attempts"] == 1
    assert passed.rubric_met == ["kept", "apple"]
    assert passed.move_attempts == 0
    # The block is not finished until the summary check closes it.
    assert passed.advance_block is False
    assert passed.block_results == []


def test_an_on_topic_answer_that_misses_opens_the_question_and_counts_as_a_try() -> None:
    assert answers_during_explanation(APPLE, WRONG_APPLE, _state(), _apple_cfg())
    missed = _turn(WRONG_APPLE)
    assert missed.next_block_state["substep"] == "main"
    assert missed.next_block_state["block_attempts"] == 1
    assert missed.move_attempts == 1
    assert missed.passed is False
    assert missed.advance_block is False
    assert missed.block_results == []
    assert missed.rubric_met == ["kept"]


def test_the_goal_must_still_be_passed_after_an_early_miss() -> None:
    missed = _turn(WRONG_APPLE)
    answered = resolve_block_turn(
        decision="stay",
        substep_passed=True,
        block_complete=False,
        rubric_met=["apple"],
        stored_rubric=list(missed.rubric_met),
        matched_wrong="",
        blocks=[dict(APPLE), dict(APPLE_NEXT)],
        step=0,
        active_block_state=dict(missed.next_block_state),
        block_results=[],
        move_attempts=missed.move_attempts,
        hint_tier=missed.hint_tier,
        reveals=0,
        enrichment_turns=0,
        cfg=_apple_cfg(),
        goal=None,
        last_misconception="",
        answer=REAL_APPLE,
    )
    assert answered.next_block_state["substep"] == "summary_check"
    assert answered.next_block_state["block_attempts"] == 2
    assert answered.advance_block is False


def test_an_early_answer_gets_the_goal_question_prompt() -> None:
    for answer in (REAL_APPLE, WRONG_APPLE):
        text = _prompt(answer)
        turn = _section(text, "This turn")
        assert EARLY_LINE in turn, answer
        assert "If it does not pass, acknowledge what they said, then ask the opening question for this goal." in turn
        assert "Active substep: main." in _section(text, "What just happened"), answer
        assert "If this answer satisfies the substep, set substep_passed=true" in turn, answer
        assert "Goal start:" not in text, answer
        assert "Do not ask the learner to state the goal yet." not in text, answer
        assert NO_TURN_LINE not in text, answer
        assert "1-2 word fragment" not in text, answer


def test_remarks_questions_and_requests_are_not_early_answers() -> None:
    for phrase in (*SIDE_REMARKS, *READY_SIGNALS, "Tell me more", "Got it - move on", "I don't know", "apple"):
        assert not answers_during_explanation(APPLE, phrase, _state(), _apple_cfg()), phrase
    # A long reply that shares only filler words with the goal is not on topic.
    assert not answers_during_explanation(
        APPLE, "I think that this is what my brother said about football", _state(), _apple_cfg()
    )


# Exit 4. The cap.


def test_two_tell_me_more_turns_deepen_and_the_third_asks_the_question() -> None:
    first = _turn("Tell me more")
    assert first.next_block_state["substep"] == "explain"
    assert first.next_block_state["elaboration_turns"] == 1
    second = _turn("Tell me more", first.next_block_state)
    assert second.next_block_state["substep"] == "explain"
    assert second.next_block_state["elaboration_turns"] == EXPLAIN_EXTRA_TURN_CAP
    for state in (_state(), first.next_block_state):
        assert DEEPEN in _section(_prompt("Tell me more", state), "This turn")
    third = _turn("Tell me more", second.next_block_state, substep_passed=True, rubric_met=["apple"])
    _opened_without_a_score(third)
    assert third.rubric_met == ["kept"]


def test_two_side_remarks_are_answered_and_the_third_asks_the_question() -> None:
    state = _state()
    for count, phrase in enumerate(SIDE_REMARKS[:2], start=1):
        assert SIDE_LINE in _section(_prompt(phrase, state), "This turn"), phrase
        stayed = _turn(phrase, state)
        assert stayed.next_block_state["substep"] == "explain", phrase
        assert stayed.next_block_state["side_turns"] == count, phrase
        assert stayed.next_block_state["elaboration_turns"] == 0, phrase
        assert stayed.rubric_met == ["kept"], phrase
        state = stayed.next_block_state
    third = _turn(SIDE_REMARKS[2], state, substep_passed=True, rubric_met=["apple"])
    _opened_without_a_score(third)
    assert third.rubric_met == ["kept"]


def test_a_side_remark_and_a_tell_me_more_share_the_cap() -> None:
    aside = _turn("arsenal are great")
    deeper = _turn("Tell me more", aside.next_block_state)
    assert deeper.next_block_state["substep"] == "explain"
    assert explain_step_turn(APPLE, "What is a computer?", deeper.next_block_state, _apple_cfg()) == "cap"
    _opened_without_a_score(_turn("What is a computer?", deeper.next_block_state))


def test_the_capped_reply_asks_the_goal_question_and_does_not_explain_again() -> None:
    cases = (
        ("What is a computer?", _state(side_turns=2)),
        ("arsenal are great", _state(side_turns=1, elaboration_turns=1)),
        ("Tell me more", _state(elaboration_turns=2)),
    )
    for answer, state in cases:
        text = _prompt(answer, state)
        turn = _section(text, "This turn")
        assert CAP_LINE in turn, answer
        assert "If their last message was a question or a remark, answer it in one sentence first." in turn, answer
        assert "Ask the opening question for this goal. One question, and it comes last." in turn, answer
        assert "Ask the opening question for this goal now." in _section(text, "What to teach"), answer
        assert SIDE_LINE not in text, answer
        assert DEEPEN not in text, answer
        assert NO_TURN_LINE not in text, answer
        assert "Do not ask the learner to state the goal yet." not in text, answer
        assert "The goal question waits" not in text, answer
        assert "repeat the active question" not in text, answer
        assert "Ask no question." not in turn, answer


def test_the_cap_does_not_block_the_button_or_an_answer() -> None:
    spent = _state(side_turns=2, elaboration_turns=2)
    cfg = _apple_cfg()
    assert explain_step_turn(APPLE, "Got it - move on", spent, cfg) == "ask"
    assert explain_step_turn(APPLE, REAL_APPLE, spent, cfg) == "attempt"
    passed = _turn(REAL_APPLE, spent, substep_passed=True, rubric_met=["apple"])
    assert passed.next_block_state["substep"] == "summary_check"


def test_leaving_the_explanation_clears_the_extra_turn_counts() -> None:
    spent = _state(side_turns=1, elaboration_turns=1)
    for answer, ready in (("Got it - move on", False), ("ok", True), (WRONG_APPLE, False)):
        left = _turn(answer, spent, ready=ready)
        assert left.next_block_state["substep"] == "main", answer
        assert left.next_block_state["elaboration_turns"] == 0, answer
        assert left.next_block_state["side_turns"] == 0, answer


# The reply and the step change come from one reading of the message.


def test_the_prompt_and_the_loop_read_each_message_the_same_way() -> None:
    cfg = _apple_cfg()
    cases = (
        ("Got it - move on", _state(), "ask", "main"),
        ("I don't want to learn more", _state(), "ask", "main"),
        (REAL_APPLE, _state(), "attempt", "summary_check"),
        ("Tell me more", _state(), "deepen", "explain"),
        ("ok", _state(), "deepen", "explain"),
        ("arsenal are great", _state(), "aside", "explain"),
        ("What's next?", _state(), "aside", "explain"),
        ("Tell me more", _state(elaboration_turns=2), "cap", "main"),
        ("What's next?", _state(side_turns=2), "cap", "main"),
    )
    markers = {
        "ask": ASK,
        "attempt": EARLY_LINE,
        "deepen": DEEPEN,
        "aside": SIDE_LINE,
        "cap": CAP_LINE,
    }
    for answer, state, kind, landed in cases:
        assert explain_step_turn(APPLE, answer, state, cfg) == kind, answer
        turn = _section(_prompt(answer, state), "This turn")
        for name, marker in markers.items():
            assert (marker in turn) == (name == kind), (answer, name)
        result = _turn(answer, state, substep_passed=True, rubric_met=["apple"])
        assert result.next_block_state["substep"] == landed, answer
        assert result.next_step == 0, answer
        assert result.advance_block is False, answer


def test_the_tutor_says_it_is_the_learners_turn_only_when_the_step_changes() -> None:
    staying = (
        ("", _state(), True),
        ("Tell me more", _state(), False),
        ("ok", _state(), False),
        ("arsenal are great", _state(), False),
        ("What's next?", _state(), False),
    )
    for answer, state, opening in staying:
        turn = _section(_prompt(answer, state, opening=opening), "This turn")
        assert turn.count(NO_TURN_LINE) == 1, answer
    changing = (
        ("Got it - move on", _state()),
        (REAL_APPLE, _state()),
        ("Tell me more", _state(elaboration_turns=2)),
        ("What's next?", {"substep": "main", "dialogue_turns": 2}),
    )
    for answer, state in changing:
        assert NO_TURN_LINE not in _prompt(answer, state), answer


# The three edited lines.


def test_tell_me_more_asks_for_two_or_three_sentences_and_no_question() -> None:
    assert DEEPEN == (
        "Goal start: The learner is still on the explanation. Explain this same topic in two or three sentences, "
        "from a fresh angle. Ask no question."
    )
    turn = _section(_prompt("Tell me more"), "This turn")
    assert turn.count(DEEPEN) == 1
    assert "more deeply" not in turn
    assert "Do not ask any question." not in turn


def test_the_side_remark_line_says_the_way_back_once_and_keeps_its_flags() -> None:
    for phrase in SIDE_REMARKS:
        turn = _section(_prompt(phrase), "This turn")
        assert turn.count(SIDE_LINE) == 1, phrase
        assert turn.count("then one line back to the active lesson") == 1, phrase
        assert "Answer that question first" not in turn, phrase
        assert "Set help_requested=true, substep_passed=false, and block_complete=false." in turn, phrase


def test_the_lesson_text_clarification_reaches_a_side_remark_turn_once() -> None:
    for phrase in SIDE_REMARKS:
        text = _prompt(phrase)
        assert text.count(CLARIFICATION) == 1, phrase
        assert CLARIFICATION in _section(text, "This turn"), phrase
        how = _section(text, "How to teach")
        assert CLARIFICATION not in how, phrase
        assert (
            "On this goal-start turn, answer the side remark in one or two sentences, "
            "then one line back to the lesson. Do not start a new explanation."
        ) in how, phrase
        assert (
            "Answer the side remark in one or two sentences, then one line back to the active lesson. "
            "Do not start a new explanation of this topic. "
            "The goal question waits until the learner moves on."
        ) in how, phrase
    assert CLARIFICATION not in _prompt("Tell me more")


def test_the_hint_order_sentence_is_still_in_how_to_teach() -> None:
    for answer, state in (("", _state()), ("Tell me more", _state()), ("arsenal are great", _state()), (REAL_APPLE, _state())):
        assert HINT_ORDER in _section(_prompt(answer, state), "How to teach"), answer


# The other block with Tell me more and Got it - move on: an explanatory topic.


def _topic_state(**extra: int) -> dict:
    return {"substep": "explain_topic", "topic_index": 0, "dialogue_turns": 1, "elaboration_turns": 0, **extra}


def test_only_these_two_block_types_open_on_an_explanation() -> None:
    opening = {kind: default_substep_for_block({"type": kind, "data": {}}) for kind in ALL_BLOCK_TYPES}
    assert {kind for kind, step in opening.items() if step in {"explain", "explain_topic"}} == {
        "topic_goal",
        "explanation",
    }


def test_an_explanatory_topic_moves_on_after_two_extra_turns() -> None:
    first = _explanatory_turn("Why is the denominator on the bottom?", _topic_state())
    assert first.next_block_state["topic_index"] == 0
    second = _explanatory_turn("Tell me more", first.next_block_state)
    assert second.next_block_state["topic_index"] == 0
    assert second.next_block_state["elaboration_turns"] == EXPLAIN_EXTRA_TURN_CAP
    third = _explanatory_turn("Tell me more", second.next_block_state)
    assert third.next_block_state["topic_index"] == 1
    assert third.next_block_state["substep"] == "explain_topic"
    assert third.next_block_state["elaboration_turns"] == 0
    assert third.unit_complete is False
    last = _explanatory_turn("what about pizza", {**third.next_block_state, "elaboration_turns": 2})
    assert last.unit_complete is True
    assert last.next_block_state.get("substep") != "summary_check"
    assert last.block_results[-1]["outcome"] == "engaged"


def test_an_explanatory_topic_moves_on_when_the_model_flags_ready() -> None:
    for phrase in READY_SIGNALS:
        moved = _explanatory_turn(phrase, _topic_state(), substep_passed=True)
        assert moved.next_block_state["topic_index"] == 1, phrase
        held = _explanatory_turn(phrase, _topic_state())
        assert held.next_block_state["topic_index"] == 0, phrase
    flagged = resolve_block_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[deepcopy(EXPLANATORY)],
        step=0,
        active_block_state=_topic_state(),
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=default_kc_tutor_config(),
        goal=None,
        last_misconception="",
        answer="What's next?",
        learner_ready=True,
    )
    assert flagged.next_block_state["topic_index"] == 1


def test_the_explanatory_summary_closes_after_one_question() -> None:
    summary = {"substep": "summary_check", "topic_index": 1, "dialogue_turns": 6, "elaboration_turns": 5}
    closed = _explanatory_turn(
        "Why is the denominator on the bottom?",
        summary,
        substep_passed=True,
        block_complete=True,
    )
    assert closed.unit_complete is True
    assert closed.block_results[-1]["outcome"] == "engaged"
    moved = _explanatory_turn("What's next?", summary, substep_passed=True, block_complete=True)
    assert moved.unit_complete is True
    assert moved.block_results[-1]["outcome"] == "engaged"


def test_the_explanatory_prompt_names_ready_signals_and_the_cap() -> None:
    open_text = _explanatory_prompt(opening=False, last_answer="What's next?", active_block_state=_topic_state())
    assert (
        "If the learner is good to proceed, for example What's next?, ok, I get it, or let's go, "
        "set substep_passed=true and, in this same reply, teach the next topic in full"
    ) in open_text
    assert "Do not move on while they still have questions." in open_text
    assert "two extra turns" not in open_text

    capped = _explanatory_prompt(
        opening=False,
        last_answer="Tell me more",
        active_block_state=_topic_state(elaboration_turns=2),
    )
    assert "The learner has had two extra turns on this topic, so the lesson moves on now." in capped
    assert "If their last message was a question or a remark, answer it in one sentence first." in capped
    assert (
        "The learner has used the two extra turns on this topic. Set substep_passed=true and, "
        "in this same reply, teach the next topic in full"
    ) in capped
    assert "On this turn set substep_passed=true." in capped
    assert "Do not move on while they still have questions." not in capped
    assert "stay on this topic and answer" not in capped
    assert READY_FIELD not in _explanatory_schema(_topic_state(elaboration_turns=2))
    assert READY_FIELD not in _explanatory_schema(_topic_state())


def _explanatory_schema(state: dict) -> dict:
    bundle = build_kc_prompt(
        student=_student(),
        profile=_profile(),
        node=_node(blocks=[deepcopy(EXPLANATORY)]),
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
        last_answer="Tell me more",
        last_misconception="",
        last_messages="",
        rubric_met=[],
        redirect_pending=False,
        fragment=False,
        others_known=False,
        active_block_state=state,
    )
    return bundle["response_schema"]["properties"]
