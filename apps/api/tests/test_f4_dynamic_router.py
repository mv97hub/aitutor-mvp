"""Comprehensive tests for F4: Dynamic Block Policy Router (no second ICAP scale)."""

from __future__ import annotations

from types import SimpleNamespace

from app.block_score import classify_stored_outcome, freeze_requirements, score_supported_turn
from app.graph2.signals import analyze_component_close
from app.kc import _last_block_finished, _walk_fragile
from app.kc_loop import (
    HIGH_DEMAND_BLOCKS,
    LOWER_DEMAND_BLOCKS,
    forecast_this_turn,
    initial_block_state,
    resolve_block_turn,
    select_next_block,
)
from app.kc_moves import AFFECTS as MOVES_AFFECTS
from app.kc_prompt import AFFECTS as PROMPT_AFFECTS


def _spec() -> dict:
    return {
        "archetype": "causal_systems",
        "target_level": 2,
        "skills": ["causes", "transfer", "errors"],
        "claims": [
            {"id": "c1", "statement": "Explain how reparations caused inflation.", "skills": ["causes"]},
            {"id": "c2", "statement": "Spot a flawed claim about the League of Nations.", "skills": ["errors"]},
        ],
    }


def _blocks() -> list[dict]:
    return [
        {
            "id": "blk_teach",
            "type": "teach_back",
            "claim_ids": ["c1"],
            "data": {
                "peer_persona_prompt": "Explain why printing money to pay reparations drove inflation.",
                "required_concepts": ["printing money", "prices rose"],
                "follow_up_question": "What happened to ordinary families?",
            },
        },
        {
            "id": "blk_mcq",
            "type": "mcq",
            "claim_ids": ["c1"],
            "data": {
                "mode": "static",
                "question_stem": "What happened to German prices after reparations?",
                "choices": [
                    {"id": "a", "text": "Prices rose rapidly.", "is_correct": True},
                    {"id": "b", "text": "Prices stayed frozen.", "is_correct": False},
                ],
            },
        },
        {
            "id": "blk_flaw",
            "type": "spot_the_flaw",
            "claim_ids": ["c2"],
            "data": {
                "flawed_work": "The League of Nations had a huge army to force countries to obey.",
                "flaw_description": "The League had no army of its own.",
                "corrected_version": "The League lacked its own army and could not easily enforce rules.",
            },
        },
    ]


def test_affects_enum_includes_bored_and_curious_stretch() -> None:
    for enum_tuple in (PROMPT_AFFECTS, MOVES_AFFECTS):
        assert "bored" in enum_tuple
        assert "curious_stretch" in enum_tuple
        assert {"engaged", "stuck", "guessing", "frustrated"} <= set(enum_tuple)


def test_dylan_rule_fast_tracks_redundant_lower_demand_blocks_without_second_icap_scale() -> None:
    blocks = _blocks()
    results = [
        {
            "id": "blk_teach",
            "block_id": "blk_teach",
            "block_type": "teach_back",
            "outcome": "passed",
            "attempts": 1,
        }
    ]
    route = select_next_block(
        blocks=blocks,
        index=0,
        results=results,
        last_outcome="passed",
        last_attempts=1,
        reveals=0,
        affect="bored",
        confidence="high",
        mastery_spec=_spec(),
    )
    assert route.pivot_reason == "dylan_fast_track"
    assert route.next_step == 2  # Jumped over blk_mcq (index 1) straight to uncovered blk_flaw (index 2)!
    assert len(route.fast_tracked_rows) == 1
    ft = route.fast_tracked_rows[0]
    assert ft["block_id"] == "blk_mcq"
    assert ft["outcome"] == "fast_tracked"
    assert ft["verdict"] == "known"
    assert ft["fast_tracked"] is True

    # Legacy empty mastery_spec stays strictly sequential (index 0 -> index 1).
    legacy = select_next_block(
        blocks=blocks,
        index=0,
        results=results,
        last_outcome="passed",
        last_attempts=1,
        reveals=0,
        affect="bored",
        confidence="high",
        mastery_spec={},
    )
    assert legacy.next_step == 1
    assert legacy.fast_tracked_rows == ()

    # Revealed or multi-try pass never triggers fast-track compression.
    retry = select_next_block(
        blocks=blocks,
        index=0,
        results=results,
        last_outcome="passed",
        last_attempts=2,
        reveals=0,
        affect="bored",
        confidence="high",
        mastery_spec=_spec(),
    )
    assert retry.next_step == 1
    assert retry.fast_tracked_rows == ()


def test_dylan_rule_end_to_end_score_supported_turn_and_f3_skips_fast_tracked_evidence() -> None:
    blocks = _blocks()
    cfg = {"blocks": {"teach_back": {"follow_up_questions_count": 0}}}
    state = initial_block_state(blocks[0], cfg)
    state["requirements"] = freeze_requirements(blocks[0], cfg)

    res = score_supported_turn(
        decision="advance",
        substep_passed=True,
        block_complete=True,
        rubric_met=["blk_teach"],
        stored_rubric=[],
        matched_wrong="",
        blocks=blocks,
        step=0,
        active_block_state=state,
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=SimpleNamespace(kind="mastery"),
        last_misconception="",
        answer="Printing money to pay reparations meant prices rose dramatically for everyone.",
        prior_tutor="Can you explain why prices went up?",
        affect="curious_stretch",
        confidence="high",
        mastery_spec=_spec(),
    )
    assert res.advance_block is True
    assert res.next_step == 2
    assert res.next_block_id == "blk_flaw"
    assert [r["block_id"] for r in res.block_results] == ["blk_teach", "blk_mcq"]
    assert res.block_results[0]["outcome"] == "passed"
    assert res.block_results[1]["outcome"] == "fast_tracked"
    assert res.block_results[1]["verdict"] == "known"
    assert res.block_results[1]["requirements"] == []
    assert classify_stored_outcome(res.block_results[1]) == ("passed", False)

    # Complete final block and verify _walk_fragile + _last_block_finished credit fast_tracked cleanly!
    final_results = [
        *res.block_results,
        {
            "id": "blk_flaw",
            "block_id": "blk_flaw",
            "block_type": "spot_the_flaw",
            "outcome": "passed",
            "verdict": "known",
            "attempts": 1,
        },
    ]
    assert _walk_fragile(blocks, final_results, cfg) is False
    node_stub = SimpleNamespace(blocks=blocks)
    sess_stub = SimpleNamespace(block_results=final_results, step=2)
    assert _last_block_finished(node_stub, sess_stub) is True

    # F3 analyze_component_close MUST ignore fast_tracked blocks (zero fake affinity/skill evidence for blk_mcq).
    analysis = analyze_component_close(
        mastery_spec=_spec(),
        blocks=blocks,
        block_results=final_results,
        messages=[
            {"role": "assistant", "content": "Explain why prices rose.", "step": 0, "seq": 1},
            {"role": "user", "content": "Printing money made prices shoot up.", "step": 0, "seq": 2},
            {"role": "assistant", "content": "Find the flaw.", "step": 2, "seq": 3},
            {"role": "user", "content": "The League had no army of its own.", "step": 2, "seq": 4},
        ],
        component_verdict="known",
    )
    assert "mcq" not in analysis.block_affinity_deltas
    assert "blk_mcq" not in {ev.block_id for ev in analysis.eligible_skills.values()}


def test_struggle_modality_pivot_and_non_premature_walk_closure() -> None:
    blocks = _blocks()
    # Child struggles on blk_teach (revealed); frozen affinity shows strong success on spot_the_flaw vs weak on mcq.
    affinity = {
        "mcq": {"completed": 4, "independent": 0, "revealed": 4},
        "spot_the_flaw": {"completed": 4, "independent": 4, "revealed": 0},
    }
    results = [{"id": "blk_teach", "block_id": "blk_teach", "block_type": "teach_back", "outcome": "revealed"}]
    route = select_next_block(
        blocks=blocks,
        index=0,
        results=results,
        last_outcome="revealed",
        last_attempts=2,
        reveals=1,
        affect="frustrated",
        modality_affinity=affinity,
    )
    assert route.pivot_reason == "modality_pivot"
    assert route.next_step == 2  # Pivoted to high-affinity spot_the_flaw!

    # After completing blk_flaw (index 2), blk_mcq (index 1) is STILL uncompleted -> router returns to index 1!
    results_after_flaw = [
        *results,
        {"id": "blk_flaw", "block_id": "blk_flaw", "block_type": "spot_the_flaw", "outcome": "passed"},
    ]
    back = select_next_block(
        blocks=blocks,
        index=2,
        results=results_after_flaw,
        last_outcome="passed",
        last_attempts=1,
        reveals=1,
        modality_affinity=affinity,
    )
    assert back.next_step == 1

    # _last_block_finished must NOT prematurely close while session.step points to uncompleted index 1!
    node_stub = SimpleNamespace(blocks=blocks)
    sess_stub = SimpleNamespace(block_results=results_after_flaw, step=1)
    assert _last_block_finished(node_stub, sess_stub) is False


def test_broken_kc_redirect_and_forecast_resolve_parity() -> None:
    blocks = _blocks()
    # 1. Broken prerequisite misconception on revealed miss triggers immediate redirect when mastery_spec is actionable.
    route = select_next_block(
        blocks=blocks,
        index=0,
        results=[{"id": "blk_teach", "block_id": "blk_teach", "outcome": "revealed"}],
        last_outcome="revealed",
        reveals=1,
        mastery_spec=_spec(),
        broken_kc_code="PREREQ-INFLATION-1",
    )
    assert route.redirect is True
    assert route.next_step is None
    assert route.pivot_reason == "broken_kc_redirect"

    # Legacy empty mastery_spec preserves existing non-redirect behavior on revealed misses.
    legacy_route = select_next_block(
        blocks=blocks,
        index=0,
        results=[{"id": "blk_teach", "block_id": "blk_teach", "outcome": "revealed"}],
        last_outcome="revealed",
        reveals=1,
        mastery_spec={},
        broken_kc_code="PREREQ-INFLATION-1",
    )
    assert legacy_route.redirect is False
    assert legacy_route.next_step == 1

    # 2. Forecast and resolve agree on Dylan Rule fast-track closure when passing the final uncovered block.
    two_blocks = [blocks[0], blocks[1]]  # both cover c1 -> passing blk_teach fast-tracks blk_mcq and closes unit!
    cfg = {"blocks": {"teach_back": {"follow_up_questions_count": 0}}}
    state = initial_block_state(two_blocks[0], cfg)
    fc = forecast_this_turn(
        blocks=two_blocks,
        step=0,
        active_block_state=state,
        block_results=[],
        answer="Printing money to pay reparations meant prices rose dramatically.",
        cfg=cfg,
        goal=SimpleNamespace(kind="mastery"),
        stored_rubric=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        affect="bored",
        confidence="high",
        mastery_spec=_spec(),
    )
    res = resolve_block_turn(
        decision="advance",
        substep_passed=True,
        block_complete=True,
        rubric_met=["blk_teach"],
        stored_rubric=[],
        matched_wrong="",
        blocks=two_blocks,
        step=0,
        active_block_state=state,
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=SimpleNamespace(kind="mastery"),
        last_misconception="",
        answer="Printing money to pay reparations meant prices rose dramatically.",
        affect="bored",
        confidence="high",
        mastery_spec=_spec(),
    )
    assert res.unit_complete is True
    assert res.mark_known is True
    assert fc.applies is True
    assert fc.if_correct is not None and fc.if_correct.unit_complete is True
    assert HIGH_DEMAND_BLOCKS.isdisjoint(LOWER_DEMAND_BLOCKS)
