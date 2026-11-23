"""The stable prefix does not change on this-turn branches, and the forecast matches the loop."""

from app.kc_loop import (
    _spoken_turn,
    forecast_this_turn,
    hold_for_blank_reply,
    resolve_block_turn,
)
from app.models import default_kc_tutor_config
from app.token_usage import cache_hit_rate
from tests.test_kc_prompt import _node, _text
from tests.test_worked_example_reveal import NEXT, REVERSED, WORKED

CFG = default_kc_tutor_config()
TOPIC = {
    "id": "topic",
    "type": "topic_goal",
    "data": {
        "topic": "River color",
        "goal": "The river is blue.",
        "acceptance_criteria": "The river is blue.",
    },
}
SUMMARY = {"substep": "summary_check", "last_task_substep": "main", "revealed_substep": False}
FADED = {"substep": "faded_step", "dialogue_turns": 1}
MAIN = {"substep": "main"}


def _prefix(text: str) -> str:
    marker = "\n\nThis turn\n"
    assert marker in text
    return text[: text.index(marker)]


def _topic_prompt(answer: str, state: dict | None = None) -> str:
    return _text(
        node=_node(blocks=[dict(TOPIC), dict(NEXT)], misconceptions=[]),
        opening=False,
        attempts=0,
        last_answer=answer,
        active_block_state=dict(state or MAIN),
        fragment=False,
    )


def _worked_prompt(answer: str) -> str:
    return _text(
        node=_node(blocks=[dict(WORKED), dict(NEXT)], misconceptions=[]),
        opening=False,
        attempts=1,
        last_answer=answer,
        active_block_state=dict(FADED),
        fragment=False,
    )


def _forecast(answer: str, state: dict, *, blocks: list | None = None, move_attempts: int = 0):
    return forecast_this_turn(
        blocks=blocks or [dict(TOPIC), dict(NEXT)],
        step=0,
        active_block_state=dict(state),
        block_results=[],
        answer=answer,
        cfg=CFG,
        goal=None,
        stored_rubric=[],
        move_attempts=move_attempts,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        fragment=False,
        prior_tutor="What color is the river?",
        opening=False,
    )


def _resolve(answer: str, state: dict, *, passed: bool, blocks: list | None = None, move_attempts: int = 0):
    return resolve_block_turn(
        decision="advance" if passed else "stay",
        substep_passed=passed,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=blocks or [dict(TOPIC), dict(NEXT)],
        step=0,
        active_block_state=dict(state),
        block_results=[],
        move_attempts=move_attempts,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer=answer,
        fragment=False,
        prior_tutor="What color is the river?",
    )


def _same(forecast_turn, resolution, before_substep: str) -> None:
    spoken = _spoken_turn(resolution, before_substep=before_substep, before_topic=0)
    assert forecast_turn.speech == spoken.speech
    assert forecast_turn.advance_block == spoken.advance_block
    assert forecast_turn.decision == spoken.decision


def test_same_substep_prefix_holds_for_close_reveal_blank_and_side_question() -> None:
    summary = {
        name: _prefix(_topic_prompt(answer, SUMMARY))
        for name, answer in (("close", "yes"), ("aside", "um"), ("blank", ""))
    }
    assert summary["close"] == summary["aside"] == summary["blank"]

    topic = {
        name: _prefix(_topic_prompt(answer, MAIN))
        for name, answer in (
            ("line", "The river is green along the bank."),
            ("side", "Why is the river blue?"),
            ("blank", ""),
        )
    }
    assert topic["line"] == topic["side"] == topic["blank"]

    faded = {
        name: _prefix(_worked_prompt(answer))
        for name, answer in (
            ("reveal", REVERSED),
            ("side", "Why does the record matter?"),
            ("blank", ""),
        )
    }
    assert faded["reveal"] == faded["side"] == faded["blank"]
    assert "This turn" not in faded["reveal"]


def test_forecast_matches_the_loop_on_close_reveal_blank_and_side_question() -> None:
    close = _forecast("yes", SUMMARY)
    assert close.applies is True
    assert close.depends_on_model is False
    assert close.chosen is not None
    assert close.chosen.speech == "close"
    _same(close.chosen, _resolve("yes", SUMMARY, passed=True), "summary_check")
    _same(close.chosen, _resolve("yes", SUMMARY, passed=False), "summary_check")

    side = _forecast("Why is the river blue?", MAIN)
    assert side.applies is True
    assert side.depends_on_model is False
    assert side.chosen is not None
    assert side.chosen.speech == "stay"
    _same(side.chosen, _resolve("Why is the river blue?", MAIN, passed=True), "main")
    _same(side.chosen, _resolve("Why is the river blue?", MAIN, passed=False), "main")

    blank = _forecast("", MAIN)
    assert blank.applies is False
    assert blank.chosen is None
    held = hold_for_blank_reply(
        blocks=[dict(TOPIC), dict(NEXT)],
        step=0,
        active_block_state=dict(MAIN),
        block_results=[],
        move_attempts=1,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        rubric_met=[],
    )
    assert held.advance_block is False
    assert held.decision == "stay"
    assert held.next_block_state["substep"] == "main"
    assert held.move_attempts == 1

    worked = [dict(WORKED), dict(NEXT)]
    reveal = _forecast(REVERSED, FADED, blocks=worked, move_attempts=1)
    assert reveal.applies is True
    missed = _resolve(REVERSED, FADED, passed=False, blocks=worked, move_attempts=1)
    assert reveal.if_not is not None
    _same(reveal.if_not, missed, "faded_step")
    assert missed.hint_tier == "reveal"
    assert missed.next_block_state["substep"] == "faded_step"


def test_cache_hit_rate_is_cached_over_input_and_stays_in_range() -> None:
    assert cache_hit_rate(400, 1000) == 0.4
    assert cache_hit_rate(0, 1000) == 0.0
    assert cache_hit_rate(50, 0) == 0.0
    assert cache_hit_rate(1500, 1000) == 1.0
