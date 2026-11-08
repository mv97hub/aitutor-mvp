"""Apply a model decision to the active block and substep in a KC session.

Deterministic grading is used strictly for MCQ option index matching
(`picked_index == correct_index`). Open-ended substeps use the model's
structured evaluation (`substep_passed`, `block_complete`, `rubric_met`).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kc_prompt import (
    HINTS,
    block_evidence_id,
    default_substep_for_block,
    max_retries_for_block,
    substeps_for_block,
)
from app.models import KcGoal

ENRICHMENT_CAP = 2


@dataclass(frozen=True)
class BlockResolution:
    decision: str
    hint_tier: str
    move_attempts: int
    reveals: int
    enrichment_turns: int
    rubric_met: list[str]
    misconception: str
    next_step: int
    next_block_id: str | None
    next_block_state: dict
    block_results: list[dict]
    mark_known: bool
    mark_fragile: bool
    redirect: bool
    unit_complete: bool
    advance_block: bool
    passed: bool


def _next_tier(tier: str) -> str:
    try:
        index = HINTS.index(tier)
    except ValueError:
        index = 0
    return HINTS[min(index + 1, len(HINTS) - 1)]


def _clean_ids(values: list[str]) -> list[str]:
    seen: list[str] = []
    for item in values:
        text = str(item).strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def match_mcq_choice_index(answer: str, choices: list[dict]) -> int | None:
    """Deterministically resolve which 0-based choice index the learner picked."""
    cleaned = (answer or "").strip()
    if not cleaned or not choices:
        return None
    first_line = cleaned.splitlines()[0].strip()
    lower = first_line.lower()
    for idx, ch in enumerate(choices):
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").strip().lower()
        ctext = str(ch.get("text") or "").strip().lower()
        if lower == cid or (ctext and lower == ctext):
            return idx
    for idx, ch in enumerate(choices):
        if not isinstance(ch, dict):
            continue
        ctext = str(ch.get("text") or "").strip().lower()
        if ctext and ctext in lower:
            return idx
    return None


def _block_title(block: dict, step_index: int) -> str:
    btype = str(block.get("type") or "topic_goal").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    if btype == "topic_goal":
        return str(data.get("topic") or f"Block {step_index + 1}").strip()
    if btype == "mcq":
        return str(data.get("question_stem") or data.get("target_skill") or f"Block {step_index + 1}").strip()
    if btype == "case_study":
        return str(data.get("invariant_principle") or f"Block {step_index + 1}").strip()
    if btype == "socratic":
        return str(data.get("central_dilemma") or f"Block {step_index + 1}").strip()
    if btype == "curiosity":
        return str(data.get("phenomenon_hook") or f"Block {step_index + 1}").strip()
    if btype == "worked_example":
        return str(data.get("problem_statement") or f"Block {step_index + 1}").strip()
    if btype == "spot_the_flaw":
        return str(data.get("flaw_description") or f"Block {step_index + 1}").strip()
    if btype == "teach_back":
        return str(data.get("peer_persona_prompt") or f"Block {step_index + 1}").strip()
    if btype == "retrieval_check":
        return str(data.get("recall_prompt") or f"Block {step_index + 1}").strip()
    return f"Block {step_index + 1}"


def resolve_block_turn(
    *,
    decision: str,
    substep_passed: bool,
    block_complete: bool,
    rubric_met: list[str],
    stored_rubric: list[str],
    matched_wrong: str,
    blocks: list[dict],
    step: int,
    active_block_state: dict,
    block_results: list[dict],
    move_attempts: int,
    hint_tier: str,
    reveals: int,
    enrichment_turns: int,
    cfg: dict,
    goal: KcGoal | None,
    last_misconception: str,
    answer: str,
    fragment: bool = False,
) -> BlockResolution:
    tier = hint_tier if hint_tier in HINTS else "nudge"
    fresh = _clean_ids(list(rubric_met))
    met = _clean_ids([*stored_rubric, *fresh])
    index = min(max(int(step or 0), 0), len(blocks) - 1)
    block = blocks[index]
    btype = str(block.get("type") or "topic_goal").strip()
    bid = str(block.get("id") or f"blk_{index + 1}").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    bcfg = ((cfg.get("blocks") or {}).get(btype)) or {}
    over = cfg.get("overarching") or {}
    misc_policy = str(over.get("misconception_policy") or "explain_and_retry_once")

    state = dict(active_block_state or {})
    substeps = substeps_for_block(block, cfg)
    substep = str(state.get("substep") or (substeps[0] if substeps else "main"))
    if substep not in substeps and not (btype == "mcq" and substep == "awaiting_why"):
        substep = substeps[0] if substeps else "main"
    dialogue_turns = int(state.get("dialogue_turns") or 0) + 1
    state["dialogue_turns"] = dialogue_turns
    state["substep"] = substep

    results = [dict(r) for r in (block_results or []) if isinstance(r, dict)]
    max_retries = max_retries_for_block(block, cfg, goal)

    # Misconception handling
    if matched_wrong:
        should_redirect = misc_policy == "immediate_redirect" or last_misconception == matched_wrong
        if should_redirect:
            results.append(
                {
                    "block_id": bid,
                    "block_type": btype,
                    "title": _block_title(block, index),
                    "attempts": move_attempts + 1,
                    "hints_used": reveals + 1,
                    "outcome": "fragile",
                    "summary": f"Redirected on misconception: {matched_wrong}",
                }
            )
            return BlockResolution(
                decision="redirect",
                hint_tier=tier,
                move_attempts=move_attempts + 1,
                reveals=reveals,
                enrichment_turns=enrichment_turns,
                rubric_met=met,
                misconception=matched_wrong,
                next_step=index,
                next_block_id=bid,
                next_block_state=state,
                block_results=results,
                mark_known=False,
                mark_fragile=True,
                redirect=True,
                unit_complete=True,
                advance_block=False,
                passed=False,
            )
        attempts = move_attempts + 1
        bumped = _next_tier(tier)
        if bumped == "reveal":
            bumped = "scaffold"
        return BlockResolution(
            decision="stay",
            hint_tier=bumped,
            move_attempts=attempts,
            reveals=reveals,
            enrichment_turns=enrichment_turns,
            rubric_met=met,
            misconception=matched_wrong,
            next_step=index,
            next_block_id=bid,
            next_block_state=state,
            block_results=results,
            mark_known=False,
            mark_fragile=False,
            redirect=False,
            unit_complete=False,
            advance_block=False,
            passed=False,
        )

    ev_id = block_evidence_id(block, index, substep)
    proposed = decision if decision in {"stay", "advance", "complete", "redirect"} else "stay"
    if proposed == "redirect":
        proposed = "stay"

    # Deterministic MCQ grading on the choice substep
    if btype == "mcq" and substep == "choice":
        mcq_state = dict(state.get("mcq") or {})
        choices = mcq_state.get("choices")
        if not isinstance(choices, list) or not choices:
            raw_choices = data.get("choices") if isinstance(data.get("choices"), list) else []
            choices = [
                {"id": str(c.get("id") or chr(ord("a") + i)), "text": str(c.get("text") or "")}
                for i, c in enumerate(raw_choices)
                if isinstance(c, dict)
            ]
            correct_idx = next(
                (i for i, c in enumerate(raw_choices) if isinstance(c, dict) and c.get("is_correct")),
                0,
            )
            mcq_state = {
                "question_stem": str(data.get("question_stem") or ""),
                "choices": choices,
                "correct_index": correct_idx,
                "eliminated_indices": list(mcq_state.get("eliminated_indices") or []),
            }
        correct_idx = int(mcq_state.get("correct_index") or 0)
        picked_idx = match_mcq_choice_index(answer, choices)
        is_correct = picked_idx == correct_idx if picked_idx is not None else False
        if is_correct:
            confirm_mode = str(bcfg.get("confirm_why_on_correct") or "on_retry_only")
            need_why = confirm_mode == "always" or (confirm_mode == "on_retry_only" and move_attempts > 0)
            if ev_id not in met:
                met.append(ev_id)
            if need_why:
                state["substep"] = "awaiting_why"
                state["mcq"] = mcq_state
                return BlockResolution(
                    decision="stay",
                    hint_tier="nudge",
                    move_attempts=0,
                    reveals=reveals,
                    enrichment_turns=0,
                    rubric_met=met,
                    misconception="",
                    next_step=index,
                    next_block_id=bid,
                    next_block_state=state,
                    block_results=results,
                    mark_known=False,
                    mark_fragile=False,
                    redirect=False,
                    unit_complete=False,
                    advance_block=False,
                    passed=True,
                )
            substep_passed = True
            block_complete = True
            proposed = "complete" if index >= len(blocks) - 1 else "advance"
        else:
            elim = list(mcq_state.get("eliminated_indices") or [])
            if picked_idx is not None and picked_idx not in elim:
                elim.append(picked_idx)
            mcq_state["eliminated_indices"] = elim
            state["mcq"] = mcq_state
            substep_passed = False
            block_complete = False
            proposed = "stay"

    # Curiosity block: never penalizes wild guesses
    elif btype == "curiosity":
        max_wonder = int(bcfg.get("max_wonder_turns", 2) or 2)
        if substep_passed or block_complete or proposed in {"advance", "complete"} or dialogue_turns >= max_wonder:
            substep_passed = True
            block_complete = True
            if ev_id not in met:
                met.append(ev_id)
            proposed = "complete" if index >= len(blocks) - 1 else "advance"

    # Topic / Goal fragment self-explanation guard
    elif btype == "topic_goal":
        frag_guard = bool(bcfg.get("fragment_self_explanation", True))
        if fragment and frag_guard and move_attempts == 0 and not state.get("fragment_prompted"):
            state["fragment_prompted"] = True
            return BlockResolution(
                decision="stay",
                hint_tier=tier,
                move_attempts=move_attempts,
                reveals=reveals,
                enrichment_turns=enrichment_turns,
                rubric_met=met,
                misconception="",
                next_step=index,
                next_block_id=bid,
                next_block_state=state,
                block_results=results,
                mark_known=False,
                mark_fragile=False,
                redirect=False,
                unit_complete=False,
                advance_block=False,
                passed=False,
            )

    # Evaluate whether the active substep passed
    passed_substep = (
        substep_passed
        or block_complete
        or ev_id in met
        or bid in fresh
        or proposed in {"advance", "complete"}
    )
    if btype == "mcq" and substep == "choice" and proposed == "stay":
        passed_substep = False

    if passed_substep:
        if ev_id not in met:
            met.append(ev_id)
        if bid not in met:
            met.append(bid)

        # Check if there is a next substep within this block
        if btype == "socratic" and substep == "counterexample_probe":
            req_turns = int(bcfg.get("dialogue_depth_turns", 2) or 2)
            # Complete as soon as block_complete is True or synthesis is met
            can_finish_socratic = block_complete or proposed in {"advance", "complete"} or dialogue_turns >= req_turns
            if not can_finish_socratic:
                return BlockResolution(
                    decision="stay",
                    hint_tier="nudge",
                    move_attempts=0,
                    reveals=reveals,
                    enrichment_turns=0,
                    rubric_met=met,
                    misconception="",
                    next_step=index,
                    next_block_id=bid,
                    next_block_state=state,
                    block_results=results,
                    mark_known=False,
                    mark_fragile=False,
                    redirect=False,
                    unit_complete=False,
                    advance_block=False,
                    passed=True,
                )

        if btype == "teach_back" and substep == "initial_explanation":
            f_count = int(bcfg.get("follow_up_questions_count", 1) or 0)
            if f_count == 0 or block_complete:
                substeps = ["initial_explanation"]

        if btype == "retrieval_check" and substep == "recall" and block_complete:
            # Learner already explained the why in their recall answer
            substeps = ["recall"]

        if substep in substeps:
            sub_idx = substeps.index(substep)
            if sub_idx < len(substeps) - 1:
                next_sub = substeps[sub_idx + 1]
                state["substep"] = next_sub
                return BlockResolution(
                    decision="stay",
                    hint_tier="nudge",
                    move_attempts=0,
                    reveals=reveals,
                    enrichment_turns=0,
                    rubric_met=met,
                    misconception="",
                    next_step=index,
                    next_block_id=bid,
                    next_block_state=state,
                    block_results=results,
                    mark_known=False,
                    mark_fragile=False,
                    redirect=False,
                    unit_complete=False,
                    advance_block=False,
                    passed=True,
                )

        # Final substep of the active block is complete!
        outcome = "engaged" if btype == "curiosity" and not bool(bcfg.get("counts_toward_mastery_score", False)) else "known"
        results.append(
            {
                "block_id": bid,
                "block_type": btype,
                "title": _block_title(block, index),
                "attempts": move_attempts + 1,
                "hints_used": 0 if tier == "nudge" else 1,
                "outcome": outcome,
                "summary": f"Completed {btype} block",
            }
        )
        return _advance_or_close_component(
            blocks=blocks,
            index=index,
            results=results,
            met=met,
            reveals=reveals,
            cfg=cfg,
        )

    # Active substep did NOT pass -> increment attempts and step up hint ladder or reveal
    attempts = move_attempts + 1
    if attempts >= max_retries:
        # Reveal and advance (or close fragile if final block)
        new_reveals = reveals + 1
        counts_mastery = True
        if btype == "curiosity":
            counts_mastery = bool(bcfg.get("counts_toward_mastery_score", False))
        outcome = "fragile" if counts_mastery else "engaged"
        # If there is another substep (e.g. faded_step -> solo_solve), reveal faded_step and move to solo_solve
        if btype == "worked_example" and substep == "faded_step":
            state["substep"] = "solo_solve"
            state["faded_revealed"] = True
            return BlockResolution(
                decision="stay",
                hint_tier="reveal",
                move_attempts=0,
                reveals=new_reveals,
                enrichment_turns=0,
                rubric_met=met,
                misconception="",
                next_step=index,
                next_block_id=bid,
                next_block_state=state,
                block_results=results,
                mark_known=False,
                mark_fragile=True,
                redirect=False,
                unit_complete=False,
                advance_block=False,
                passed=False,
            )
        results.append(
            {
                "block_id": bid,
                "block_type": btype,
                "title": _block_title(block, index),
                "attempts": attempts,
                "hints_used": attempts,
                "outcome": outcome,
                "summary": f"Revealed {btype} after {attempts} attempts",
            }
        )
        return _advance_or_close_component(
            blocks=blocks,
            index=index,
            results=results,
            met=met,
            reveals=new_reveals,
            cfg=cfg,
            revealed_this_turn=counts_mastery,
        )

    bumped = _next_tier(tier)
    if bumped == "reveal":
        bumped = "scaffold"
    return BlockResolution(
        decision="stay",
        hint_tier=bumped,
        move_attempts=attempts,
        reveals=reveals,
        enrichment_turns=enrichment_turns,
        rubric_met=met,
        misconception="",
        next_step=index,
        next_block_id=bid,
        next_block_state=state,
        block_results=results,
        mark_known=False,
        mark_fragile=False,
        redirect=False,
        unit_complete=False,
        advance_block=False,
        passed=False,
    )


def _advance_or_close_component(
    *,
    blocks: list[dict],
    index: int,
    results: list[dict],
    met: list[str],
    reveals: int,
    cfg: dict,
    revealed_this_turn: bool = False,
) -> BlockResolution:
    has_fragile = revealed_this_turn or reveals > 0 or any(r.get("outcome") == "fragile" for r in results)
    if index < len(blocks) - 1:
        next_idx = index + 1
        next_blk = blocks[next_idx]
        next_id = str(next_blk.get("id") or f"blk_{next_idx + 1}").strip()
        next_state = {
            "substep": default_substep_for_block(next_blk, cfg),
            "dialogue_turns": 0,
        }
        return BlockResolution(
            decision="advance",
            hint_tier="nudge",
            move_attempts=0,
            reveals=reveals,
            enrichment_turns=0,
            rubric_met=met,
            misconception="",
            next_step=next_idx,
            next_block_id=next_id,
            next_block_state=next_state,
            block_results=results,
            mark_known=False,
            mark_fragile=revealed_this_turn,
            redirect=False,
            unit_complete=False,
            advance_block=True,
            passed=not revealed_this_turn,
        )

    # Last block finished -> complete unit
    return BlockResolution(
        decision="complete",
        hint_tier="reveal" if revealed_this_turn else "nudge",
        move_attempts=0,
        reveals=reveals,
        enrichment_turns=0,
        rubric_met=met,
        misconception="",
        next_step=index,
        next_block_id=str(blocks[index].get("id") or f"blk_{index + 1}").strip(),
        next_block_state={"substep": "done", "dialogue_turns": 0},
        block_results=results,
        mark_known=not has_fragile,
        mark_fragile=has_fragile,
        redirect=False,
        unit_complete=True,
        advance_block=False,
        passed=not has_fragile,
    )
