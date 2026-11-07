"""Apply a model decision to one knowledge-component move.

The model proposes. This module decides what the app will write. It does not
import the quest assembler, and it does not phrase-match a pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kc_prompt import HINTS, Move

ENRICHMENT_CAP = 2


@dataclass(frozen=True)
class Resolution:
    decision: str
    hint_tier: str
    move_attempts: int
    reveals: int
    enrichment_turns: int
    rubric_met: list[str]
    misconception: str
    mark_known: bool
    mark_fragile: bool
    redirect: bool
    unit_complete: bool
    advance: bool
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


def resolve_decision(
    *,
    decision: str,
    rubric_met: list[str],
    stored_rubric: list[str],
    matched_wrong: str,
    move: Move,
    step: int,
    moves: list[Move],
    move_attempts: int,
    hint_tier: str,
    reveals: int,
    enrichment_turns: int,
    enrichment: str,
    window_tries: int,
    last_misconception: str,
    fragment: bool,
    self_explanation: bool,
) -> Resolution:
    """Return the state change the app is allowed to write."""
    tier = hint_tier if hint_tier in HINTS else "nudge"
    met = _clean_ids([*stored_rubric, *rubric_met])
    evidence = set(move.evidence)
    checked = bool(evidence)
    proposed = decision if decision in {"stay", "advance", "complete", "redirect"} else "stay"
    last_index = len(moves) - 1
    mastery_index = last_index - 1 if moves and moves[-1].key == "extra_why" else last_index
    evidence_met = evidence <= set(met) if checked else proposed in {"advance", "complete"} or bool(met)

    if matched_wrong and last_misconception == matched_wrong:
        return Resolution(
            decision="redirect",
            hint_tier=tier,
            move_attempts=move_attempts,
            reveals=reveals,
            enrichment_turns=enrichment_turns,
            rubric_met=met,
            misconception=matched_wrong,
            mark_known=False,
            mark_fragile=True,
            redirect=True,
            unit_complete=True,
            advance=False,
            passed=False,
        )

    if matched_wrong:
        attempts = move_attempts + 1
        bumped = tier
        if attempts >= window_tries:
            bumped = _next_tier(tier)
            attempts = 0
            if bumped == "reveal":
                bumped = "scaffold"
        return Resolution(
            decision="stay",
            hint_tier=bumped,
            move_attempts=attempts,
            reveals=reveals,
            enrichment_turns=enrichment_turns,
            rubric_met=met,
            misconception=matched_wrong,
            mark_known=False,
            mark_fragile=False,
            redirect=False,
            unit_complete=False,
            advance=False,
            passed=False,
        )

    if proposed == "redirect":
        proposed = "stay"
    if checked and proposed in {"advance", "complete"} and not evidence_met:
        proposed = "stay"
    if (
        move.key == "retrieve"
        and fragment
        and self_explanation
        and proposed == "complete"
        and evidence_met
    ):
        proposed = "advance"
    if proposed == "complete" and step < last_index:
        proposed = "advance" if evidence_met or not checked else "stay"
    if proposed == "advance" and step >= last_index:
        proposed = "complete" if evidence_met or not checked else "stay"

    if proposed == "stay" and evidence_met:
        if enrichment == "direct" or enrichment_turns >= ENRICHMENT_CAP:
            proposed = "complete" if step >= last_index else "advance"
        else:
            return Resolution(
                decision="stay",
                hint_tier=tier,
                move_attempts=move_attempts,
                reveals=reveals,
                enrichment_turns=enrichment_turns + 1,
                rubric_met=met,
                misconception="",
                mark_known=False,
                mark_fragile=False,
                redirect=False,
                unit_complete=False,
                advance=False,
                passed=False,
            )

    if proposed == "stay":
        attempts = move_attempts + 1
        bumped = tier
        if attempts >= window_tries:
            bumped = _next_tier(tier)
            attempts = 0
        if bumped == "reveal":
            return Resolution(
                decision="stay",
                hint_tier="reveal",
                move_attempts=0,
                reveals=reveals + 1,
                enrichment_turns=enrichment_turns,
                rubric_met=met,
                misconception="",
                mark_known=False,
                mark_fragile=True,
                redirect=False,
                unit_complete=True,
                advance=False,
                passed=False,
            )
        return Resolution(
            decision="stay",
            hint_tier=bumped,
            move_attempts=attempts,
            reveals=reveals,
            enrichment_turns=enrichment_turns,
            rubric_met=met,
            misconception="",
            mark_known=False,
            mark_fragile=False,
            redirect=False,
            unit_complete=False,
            advance=False,
            passed=False,
        )

    mark_known = step == mastery_index or proposed == "complete"
    if proposed == "advance":
        return Resolution(
            decision="advance",
            hint_tier="nudge",
            move_attempts=0,
            reveals=reveals,
            enrichment_turns=0,
            rubric_met=[],
            misconception="",
            mark_known=mark_known,
            mark_fragile=False,
            redirect=False,
            unit_complete=False,
            advance=True,
            passed=mark_known,
        )
    return Resolution(
        decision="complete",
        hint_tier=tier,
        move_attempts=move_attempts,
        reveals=reveals,
        enrichment_turns=enrichment_turns,
        rubric_met=met,
        misconception="",
        mark_known=True,
        mark_fragile=False,
        redirect=False,
        unit_complete=True,
        advance=False,
        passed=True,
    )
