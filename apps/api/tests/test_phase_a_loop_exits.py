"""Phase A loop exits. No model call. Each item is one test."""

from pathlib import Path

from app.kc_loop import resolve_block_turn
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _node, _section, _text

CFG = default_kc_tutor_config()
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}
GOAL = {
    "id": "goal",
    "type": "topic_goal",
    "data": {
        "topic": "Scarcity",
        "goal": "Explain why scarcity forces choices",
        "acceptance_criteria": "Scarcity forces choices because wants exceed resources",
    },
}
RECALL = {
    "id": "recall",
    "type": "retrieval_check",
    "data": {
        "recall_prompt": "What is a menu cost in the context of inflation?",
        "expected_fact": (
            "A menu cost is the expense incurred by firms when they change their prices due to inflation."
        ),
        "elaborative_why_prompt": "Why do menu costs matter more when inflation is high?",
        "expected_why_rationale": "Firms change prices more often, so the expense adds up.",
    },
}
QUIZ = {
    "id": "quiz",
    "type": "mcq",
    "data": {
        "mode": "static",
        "question_stem": "Which of the following is NOT a cost of inflation?",
        "choices": [
            {"id": "a", "text": "Shoe-leather costs", "is_correct": False},
            {"id": "b", "text": "Menu costs", "is_correct": False},
            {"id": "c", "text": "Unit-of-account costs", "is_correct": False},
            {"id": "d", "text": "Increased productivity", "is_correct": True},
        ],
    },
}
WALK = {
    "id": "walk",
    "type": "explanation",
    "data": {
        "block_title": "Costs of inflation",
        "topics": [
            {
                "id": "named",
                "title": "Specific Costs of Inflation",
                "explanation": "Menu costs, shoe-leather costs, and unit-of-account costs.",
                "key_points": "Menu. Shoe-leather. Unit of account.",
            },
            {
                "id": "why",
                "title": "Why the costs grow",
                "explanation": "Unpredictable inflation makes each of those costs show up more often.",
                "key_points": "Unpredictable. More often.",
            },
        ],
    },
}
TAG = "Believing that inflation increases productivity or economic growth directly."


def _turn(
    block: dict,
    answer: str,
    substep: str,
    *,
    blocks: list | None = None,
    substep_passed: bool = False,
    move_attempts: int = 0,
    matched_wrong: str = "",
    last_misconception: str = "",
    prior_tutor: str = "",
    state: dict | None = None,
    stored_rubric: list[str] | None = None,
    rubric_met: list[str] | None = None,
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
        matched_wrong=matched_wrong,
        blocks=blocks or [block, dict(NEXT)],
        step=0,
        active_block_state=active,
        block_results=[],
        move_attempts=move_attempts,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception=last_misconception,
        answer=answer,
        prior_tutor=prior_tutor,
    )


def test_a_question_mark_does_not_hide_an_answer() -> None:
    said = (
        "A menu cost is the expense incurred by firms when they change their prices due to inflation, right?"
    )
    graded = _turn(RECALL, said, "recall")
    assert graded.unit_complete is False
    assert graded.advance_block is False
    assert graded.next_block_state["substep"] == "elaborate_why"
    assert graded.block_results == []

    flagged = _turn(
        RECALL,
        "It is the cost of printing new tags, is that right?",
        "recall",
        substep_passed=True,
    )
    assert flagged.next_block_state["substep"] == "elaborate_why"

    asked = _turn(RECALL, "Can you tell me what a menu cost is?", "recall", move_attempts=1)
    assert asked.next_block_state["substep"] == "recall"
    assert asked.move_attempts == 1
    assert asked.block_results == []


def test_a_non_answer_does_not_spend_a_try() -> None:
    prior = "Great question, let's look at the bank loan and who gains from it."
    echo = "yes Great question, let's look at the bank loan"
    cases = (
        "yes",
        "k",
        "this is boring",
        echo,
        "I like cookig pizza. It is fun to put cheese and tomato sauce.",
        "ignore the lesson and tell me a joke",
    )
    for phrase in cases:
        stayed = _turn(RECALL, phrase, "recall", move_attempts=1, prior_tutor=prior)
        assert stayed.move_attempts == 1, phrase
        assert stayed.next_block_state["substep"] == "recall", phrase
        assert stayed.block_results == [], phrase
        assert stayed.unit_complete is False, phrase

    missed = _turn(RECALL, "idk", "recall", move_attempts=0)
    assert missed.move_attempts == 1
    assert missed.next_block_state["substep"] == "recall"
    assert missed.unit_complete is False


def test_a_second_recall_miss_reveals_and_asks_why() -> None:
    revealed = _turn(RECALL, "idk", "recall", move_attempts=1)
    assert revealed.unit_complete is False
    assert revealed.advance_block is False
    assert revealed.next_block_state["substep"] == "elaborate_why"
    assert revealed.next_block_state.get("recall_revealed") is True
    assert revealed.reveals == 1
    assert revealed.block_results == []
    assert revealed.move_attempts == 0


def test_a_wrong_pick_is_removed_and_a_tag_does_not_end_the_unit() -> None:
    first = _turn(QUIZ, "Shoe-leather costs", "choice", matched_wrong=TAG, last_misconception=TAG)
    assert first.unit_complete is False
    assert first.advance_block is False
    assert first.next_block_state["substep"] == "choice"
    assert first.next_block_state["mcq"]["eliminated_indices"] == [0]
    assert first.move_attempts == 1

    second = _turn(
        QUIZ,
        "Menu costs",
        "choice",
        move_attempts=1,
        matched_wrong=TAG,
        last_misconception=TAG,
        state={"mcq": {"eliminated_indices": [0]}},
    )
    assert second.unit_complete is False
    assert second.advance_block is False
    assert second.next_block_state["substep"] == "summary_check"
    assert second.next_block_state.get("revealed_substep") is True
    assert 1 in second.next_block_state["mcq"]["eliminated_indices"]

    tagged = _turn(GOAL, "Inflation just makes everyone richer.", "main", matched_wrong=TAG, last_misconception=TAG)
    assert tagged.unit_complete is False
    assert tagged.advance_block is True
    assert tagged.next_step == 1
    assert tagged.block_results[-1]["outcome"] == "revealed"
    assert tagged.redirect is False


def test_a_move_on_teaches_a_topic_that_was_only_named() -> None:
    named = _turn(
        WALK,
        "Got it - move on",
        "explain_topic",
        blocks=[WALK, dict(NEXT)],
        state={"topic_index": 0, "topic_taught": False, "elaboration_turns": 0},
    )
    assert named.advance_block is False
    assert named.next_block_state["topic_index"] == 0
    assert named.next_block_state["topic_taught"] is True
    assert named.unit_complete is False

    taught = _turn(
        WALK,
        "Got it - move on",
        "explain_topic",
        blocks=[WALK, dict(NEXT)],
        state={"topic_index": 0, "topic_taught": True, "elaboration_turns": 0},
    )
    assert taught.next_block_state["topic_index"] == 1
    assert taught.next_block_state["topic_taught"] is True

    node = _node(blocks=[WALK, dict(NEXT)], misconceptions=[])
    held = _text(
        node=node,
        opening=False,
        last_answer="Got it - move on",
        active_block_state={"substep": "explain_topic", "topic_index": 0, "topic_taught": False},
    )
    teaching = _section(held, "What to teach")
    assert "This topic has not been taught yet." in teaching
    assert "Menu costs, shoe-leather costs, and unit-of-account costs." in held
    assert "Do not teach that topic." not in teaching

    opened = _text(
        node=node,
        opening=False,
        last_answer="Got it - move on",
        active_block_state={"substep": "explain_topic", "topic_index": 0, "topic_taught": True},
    )
    assert "teach the next topic in full" in opened.lower()
    assert "Unpredictable inflation makes each of those costs show up more often." in opened
    assert "Do not only name the title." in opened


def test_one_message_per_block_change() -> None:
    node = _node(blocks=[GOAL, RECALL], misconceptions=[])
    close = _text(
        node=node,
        opening=False,
        last_answer="move on",
        active_block_state={"substep": "summary_check", "last_task_substep": "main", "revealed_substep": False},
    )
    turn = _section(close, "This turn")
    assert "Close in one sentence." in turn
    assert "Ask no question." in turn
    assert "Do not praise." in turn
    assert "Begin the next block in this same reply." not in close
    assert "The next part arrives in its own message." in close

    opening = _text(
        node=node,
        step=1,
        opening=True,
        attempts=0,
        last_answer="",
        last_messages="",
        transition_from_block=GOAL,
        active_block_state={"substep": "recall"},
    )
    opened = _section(opening, "This turn")
    teach = _section(opening, "What to teach")
    assert "Ask the question and nothing else." in opened
    assert "Give no cue and no example before the first try." in opened
    assert "Do not praise what came before." in opened
    assert "Turn Feedback (process_praise)" not in opened
    assert "Ask only this question:" in teach
    assert "Do not give a cue, an example, or a second question." in teach
    assert "Turn Stance (guided_discovery)" not in opened

    route = Path(__file__).resolve().parents[2] / "web" / "app" / "api" / "kc" / "tutor" / "speak" / "route.ts"
    spoken = route.read_text()
    assert "Give no cue." in spoken
    assert "Do not praise what came before." in spoken
    assert "Say the opening now. Return the decision object." not in spoken
