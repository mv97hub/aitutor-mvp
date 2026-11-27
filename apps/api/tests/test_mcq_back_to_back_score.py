"""Regression tests for back-to-back MCQ first-try scoring (found on Treaty of Versailles run ec557ce0)."""

from __future__ import annotations

from types import SimpleNamespace

from app.block_score import _passed, freeze_requirements, score_supported_turn
from app.kc_loop import initial_block_state


def _mcq_block(bid: str, title: str, correct_text: str) -> dict:
    return {
        "id": bid,
        "type": "mcq",
        "data": {
            "mode": "static",
            "question_stem": title,
            "choices": [
                {"id": "a", "text": correct_text, "is_correct": True},
                {"id": "b", "text": "An unrelated option.", "is_correct": False},
            ],
            "correct_explanation": "That matches the historical record.",
        },
    }


def test_passed_recognizes_mcq_choice_closing_into_another_mcq() -> None:
    assert (
        _passed(
            "mcq",
            "choice",
            {"substep": "choice"},
            {"substep": "choice"},
            True,
            "passed",
        )
        is True
    )
    # A revealed MCQ closing into another MCQ (or a different block) must NOT be treated as an independent pass.
    assert (
        _passed(
            "mcq",
            "choice",
            {"substep": "choice"},
            {"substep": "choice"},
            False,
            "revealed",
        )
        is False
    )
    assert (
        _passed(
            "mcq",
            "choice",
            {"substep": "choice"},
            {"substep": "walkthrough"},
            False,
            "revealed",
        )
        is False
    )


def test_back_to_back_mcq_first_try_passes_as_known_not_fragile() -> None:
    blocks = [
        _mcq_block("mcq-1", "Main terms imposed on Germany", "Colonies surrendered and army limited to 100,000."),
        _mcq_block("mcq-2", "Reasons for German resentment", "Germany had no voice in writing the terms."),
        _mcq_block("mcq-3", "League of Nations effectiveness", "It lacked its own enforcement army and US membership."),
    ]
    cfg: dict = {}
    state = initial_block_state(blocks[0], cfg)
    state["requirements"] = freeze_requirements(blocks[0], cfg)
    results: list[dict] = []
    rubric: list[str] = []
    step = 0
    move = 0
    reveals = 0

    answers = [
        ("mcq-1", "Colonies surrendered and army limited to 100,000."),
        ("mcq-2", "Germany had no voice in writing the terms."),
        ("mcq-3", "It lacked its own enforcement army and US membership."),
    ]

    for expected_id, answer in answers:
        res = score_supported_turn(
            decision="advance",
            substep_passed=True,
            block_complete=True,
            rubric_met=[expected_id],
            stored_rubric=list(rubric),
            matched_wrong="",
            blocks=blocks,
            step=step,
            active_block_state=dict(state),
            block_results=list(results),
            move_attempts=move,
            hint_tier="nudge",
            reveals=reveals,
            enrichment_turns=0,
            cfg=cfg,
            goal=SimpleNamespace(kind="mastery"),
            last_misconception="",
            answer=answer,
            prior_tutor="Pick the best answer below.",
        )
        state = dict(res.next_block_state)
        results = list(res.block_results)
        rubric = list(res.rubric_met)
        step = res.next_step
        move = res.move_attempts
        reveals = res.reveals

    # On the final block, mcq-3 enters summary_check; confirm mcq-1 and mcq-2 are already known!
    assert len(results) == 2
    for row, bid in zip(results, ["mcq-1", "mcq-2"]):
        assert row["block_id"] == bid
        assert row["verdict"] == "known"
        assert row["outcome"] == "passed"
        assert row["passed_on_first_try"] is True
        choice_req = next(r for r in row["requirements"] if r["key"] == "choice")
        assert choice_req["observation"] == "independent"

    # Close the component on summary_check and verify all 3 MCQs are known + component mark_known is True.
    close = score_supported_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=list(rubric),
        matched_wrong="",
        blocks=blocks,
        step=step,
        active_block_state=dict(state),
        block_results=list(results),
        move_attempts=move,
        hint_tier="nudge",
        reveals=reveals,
        enrichment_turns=0,
        cfg=cfg,
        goal=SimpleNamespace(kind="mastery"),
        last_misconception="",
        answer="Ready to finish!",
        prior_tutor="Great work — ready to wrap up?",
    )
    assert close.unit_complete is True
    assert close.mark_known is True
    assert close.mark_fragile is False
    assert [row["verdict"] for row in close.block_results] == ["known", "known", "known"]
    assert all(row["passed_on_first_try"] is True for row in close.block_results)


def test_back_to_back_mcq_wrong_then_retry_still_records_insufficient_first_attempt() -> None:
    blocks = [
        _mcq_block("mcq-1", "Main terms imposed on Germany", "Colonies surrendered and army limited to 100,000."),
        _mcq_block("mcq-2", "Reasons for German resentment", "Germany had no voice in writing the terms."),
    ]
    cfg: dict = {}
    state = initial_block_state(blocks[0], cfg)
    state["requirements"] = freeze_requirements(blocks[0], cfg)

    miss = score_supported_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=blocks,
        step=0,
        active_block_state=dict(state),
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=SimpleNamespace(kind="mastery"),
        last_misconception="",
        answer="An unrelated option.",
        prior_tutor="Pick the best answer below.",
    )
    assert miss.advance_block is False
    assert miss.block_results == []
    choice_req = next(r for r in miss.next_block_state["requirements"] if r["key"] == "choice")
    assert choice_req["observation"] == "insufficient"
    assert choice_req["attempts"] == 1
