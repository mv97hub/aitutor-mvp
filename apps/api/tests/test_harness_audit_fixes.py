"""Regression tests for tutor loop, prompt, and harness-check fixes surfaced by live harness run 1ac2db6e."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from app.database import SessionLocal
from app.harness import (
    FIXTURE_CODE,
    _has_legacy_fixture_stubs,
    ensure_fixture,
    fixture_document,
    load_targets,
)
from app.harness_checks import UNSCORED_INTENTS, automatic_checks, instruction_rows
from app.block_catalog import BLOCK_FIELDS
from app.kc_course_io import _BLOCK_EXAMPLES
from app.kc_loop import resolve_block_turn
from app.kc_prompt import _decision_sentence, _ending, _passage_teach_lines
from app.models import KcGoal


def test_passage_ela_prompt_includes_next_substep_question_for_handoff() -> None:
    block = {"id": "blk_passage_ela", "type": "passage_ela", "data": dict(_BLOCK_EXAMPLES["passage_ela"])}

    central_lines = "\n".join(_passage_teach_lines(block, "central_idea"))
    assert "Cite two sentences from the passage that support the central idea." in central_lines

    cite_lines = "\n".join(_passage_teach_lines(block, "cite_evidence"))
    assert "What can a reader infer about a town far from a river?" in cite_lines
    assert "analysis focus: inference" in cite_lines


def test_unit_close_prompt_signals_projected_fragile_verdict() -> None:
    known_close = _ending(
        close_depth="concise",
        kind="mastery",
        unit_complete=True,
        course_complete=False,
        others_known=False,
        course_title="River Trade",
        is_final_block_and_substep=True,
        projected_fragile=False,
    )
    assert "Projected unit status is fragile" not in known_close

    fragile_close = _ending(
        close_depth="concise",
        kind="mastery",
        unit_complete=True,
        course_complete=False,
        others_known=False,
        course_title="River Trade",
        is_final_block_and_substep=True,
        projected_fragile=True,
    )
    assert "Projected unit status is fragile" in fragile_close
    assert "do not call the unit complete" in fragile_close


def test_last_try_reveal_instruction_forbids_contradictory_praise() -> None:
    reveal_stop_turn = SimpleNamespace(
        speech="stay",
        unit_complete=False,
        advance_block=False,
        revealed=True,
        next_substep="faded_step",
        decision="stay",
        reveal_stop=True,
        probe_advanced=False,
    )
    advance_reveal_turn = SimpleNamespace(
        speech="advance",
        unit_complete=False,
        advance_block=False,
        revealed=True,
        next_substep="solo_solve",
        decision="advance",
        reveal_stop=False,
        probe_advanced=False,
    )
    assert "Do not praise the learner's reply as right before giving the answer." in _decision_sentence(
        reveal_stop_turn, "If not"
    )
    assert "Do not praise the learner's reply as right before giving the answer." in _decision_sentence(
        advance_reveal_turn, "If not"
    )


def test_curiosity_off_course_holds_attempt_even_with_hook_word_overlap_and_caps_stalls() -> None:
    block = {
        "id": "blk_curiosity",
        "type": "curiosity",
        "data": {
            "phenomenon_hook": "In a wolf pack, the strongest wolf lets the hungriest wolf eat first.",
            "prediction_question": "Why would the strongest wolf let the hungriest wolf eat first?",
            "bridge_to_unit": "Keeping every pack member strong helps the whole pack survive.",
            "wonder_branches": None,
        },
    }
    prior_tutor = "Why would the strongest wolf step back and let the hungriest one eat first?"
    state = {"substep": "hook_and_predict", "block_attempts": 0}

    def _call(cur_state: dict, answer: str, move_attempts: int, reveals: int, enrichment: int):
        return resolve_block_turn(
            decision="stay",
            substep_passed=False,
            block_complete=False,
            rubric_met=[],
            stored_rubric=[],
            matched_wrong="",
            blocks=[block],
            step=0,
            active_block_state=cur_state,
            block_results=[],
            move_attempts=move_attempts,
            hint_tier="nudge",
            reveals=reveals,
            enrichment_turns=enrichment,
            cfg={},
            goal=SimpleNamespace(kind="mastery"),
            last_misconception="",
            answer=answer,
            prior_tutor=prior_tutor,
            off_course=True,
        )

    # Turn 1: off-topic remark mentioning "wolf" stays unscored without burning an attempt.
    res1 = _call(state, "I wonder if wolf pups like playing in the snow.", 0, 0, 0)
    assert res1.move_attempts == 0
    assert res1.next_step == 0
    assert res1.block_results == []
    assert res1.next_block_state.get("stall_turns") == 1

    # Turn 2: second off-topic remark still stays unscored (2 free stalls).
    res2 = _call(
        res1.next_block_state,
        "I wonder if wolf pups make little snow tunnels to play in.",
        res1.move_attempts,
        res1.reveals,
        res1.enrichment_turns,
    )
    assert res2.move_attempts == 0
    assert res2.next_step == 0
    assert res2.block_results == []
    assert res2.next_block_state.get("stall_turns") == 2

    # Turn 3: third consecutive off-topic stall exceeds _MAX_FREE_STALL_TURNS so the loop cannot livelock.
    res3 = _call(
        res2.next_block_state,
        "I wonder if wolf pups chase snowflakes.",
        res2.move_attempts,
        res2.reveals,
        res2.enrichment_turns,
    )
    assert res3.move_attempts == 1 or bool(res3.block_results)


def test_idk_is_not_flagged_as_misread_in_harness_checks() -> None:
    assert "idk" not in UNSCORED_INTENTS
    checks = automatic_checks(
        [
            {
                "intent": "idk",
                "child_text": "idk",
                "tutor_reply": "Let's break it down together. What do rivers carry?",
                "block_before": "blk_passage_ela",
                "block_id": "blk_passage_ela",
                "substep_before": "craft_or_inference",
                "substep": "craft_or_inference",
                "expected": "A town far from a river would have a harder time moving food and people.",
                "loop_result": {"stayed": True, "advanced": False, "closed": "", "attempt_counted": True},
            }
        ],
        ended_how="completed",
        response_length="balanced",
    )
    assert checks["misread"] == []


def test_ask_no_question_respects_conditional_close_branches() -> None:
    conditional_prompt = (
        "If correct: close. Set decision to advance. Close in one sentence. Ask no question.\n"
        "If not: stay. Set decision to stay. Stay on this step."
    )
    # Stayed on a miss -> asking a follow-up question is expected, not a violation.
    stayed_rows = {
        r["id"]: r
        for r in instruction_rows(
            conditional_prompt,
            "Try again: what stays the same in both cases?",
            loop_result={"stayed": True, "advanced": False, "closed": "", "ended_unit": False},
        )
    }
    assert stayed_rows["ask_no_question"]["present"] is False

    # Closed on a pass -> ask_no_question IS active and flags a trailing question.
    closed_rows = {
        r["id"]: r
        for r in instruction_rows(
            conditional_prompt,
            "Nice work! Ready for the next one?",
            loop_result={"stayed": False, "advanced": False, "closed": "passed", "ended_unit": False},
        )
    }
    assert closed_rows["ask_no_question"]["present"] is True
    assert closed_rows["ask_no_question"]["obeyed"] is False

    # Unconditional close prompt -> always active even when loop_result has no closed flag.
    unconditional_prompt = "Decision: close. Set decision to complete. This reply ends the unit. Close it. Ask no question."
    uncond_rows = {
        r["id"]: r
        for r in instruction_rows(
            unconditional_prompt,
            "Want to keep going?",
            loop_result={"stayed": False, "advanced": False, "closed": "", "ended_unit": False},
        )
    }
    assert uncond_rows["ask_no_question"]["present"] is True
    assert uncond_rows["ask_no_question"]["obeyed"] is False


def test_course_title_containing_block_is_not_flagged_as_leak() -> None:
    clean_outro = automatic_checks(
        [
            {
                "intent": "answer_right",
                "child_text": "A town far from a river would have a harder time moving food and people.",
                "tutor_reply": "The unit is paused for one more look. Harness fixture: every block type is complete.",
                "course_title": "Harness fixture: every block type",
            }
        ],
        ended_how="completed",
        response_length="balanced",
    )
    assert clean_outro["leaks"] == []

    real_leak = automatic_checks(
        [
            {
                "intent": "answer_right",
                "child_text": "A town far from a river would have a harder time moving food and people.",
                "tutor_reply": "Nice work finishing this block. Harness fixture: every block type is complete.",
                "course_title": "Harness fixture: every block type",
            }
        ],
        ended_how="completed",
        response_length="balanced",
    )
    assert real_leak["leaks"] == [0]


def test_fixture_document_has_concrete_keys_and_ensure_fixture_upgrades_legacy_stubs() -> None:
    doc = fixture_document()
    blocks = doc["units"][0]["components"][0]["blocks"]
    assert len(blocks) == 11
    assert {b["type"] for b in blocks} == set(BLOCK_FIELDS)
    assert not _has_legacy_fixture_stubs(blocks)

    by_type = {b["type"]: b["data"] for b in blocks}
    assert by_type["worked_example"]["solo_expected_answer"] != "The answer."
    assert by_type["spot_the_flaw"]["flaw_description"] != "What is wrong."
    assert by_type["spot_the_flaw"]["corrected_version"] != "The fixed solution."

    with SessionLocal() as db:
        first = ensure_fixture(db)
        course = db.scalar(select(KcGoal).where(KcGoal.code == FIXTURE_CODE))
        assert course is not None
        node = next(n for n in load_targets(db, course) if n.code == "harness-every-block-all")
        # Simulate an older DB still holding legacy stub blocks and verify ensure_fixture upgrades in place.
        node.blocks = [{"id": f"blk_{kind}", "type": kind, "data": dict(data)} for kind, data in _BLOCK_EXAMPLES.items()]
        db.flush()
        assert _has_legacy_fixture_stubs(node.blocks)

        second = ensure_fixture(db)
        db.refresh(node)
        assert second["id"] == first["id"]
        assert not _has_legacy_fixture_stubs(node.blocks)
        db.rollback()
