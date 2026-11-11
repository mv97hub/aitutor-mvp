"""Apply a model decision to the active block and substep in a KC session.

Deterministic grading is used strictly for MCQ option index matching
(`picked_index == correct_index`). Open-ended substeps use the model's
structured evaluation (`substep_passed`, `block_complete`, `rubric_met`).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kc_moves import Move
from app.kc_prompt import (
    HINTS,
    block_evidence_id,
    default_substep_for_block,
    explanation_topic_index,
    explanation_topics,
    initial_block_state,
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


def _words(text: str) -> list[str]:
    return [word for word in "".join(ch.lower() if ch.isalnum() else " " for ch in (text or "")).split() if word]


def _matches(answer: str, phrase: str) -> bool:
    from app.kc import matches_phrase

    return matches_phrase(answer, phrase)


def _substantive(answer: str, minimum_words: int = 2) -> bool:
    return len((answer or "").split()) >= minimum_words


def _precise(answer: str, phrase: str) -> bool:
    needed = [word for word in _words(phrase) if len(word) > 3]
    if not needed:
        return _matches(answer, phrase)
    have = set(_words(answer))
    return all(word in have for word in needed)


def _strict_fact(answer: str, phrase: str) -> bool:
    left = " ".join(_words(answer))
    right = " ".join(_words(phrase))
    return bool(left and right and (right in left or left in right))


def _data(block: dict) -> dict:
    raw = block.get("data")
    return raw if isinstance(raw, dict) else {}


def _bcfg(block: dict, cfg: dict) -> dict:
    btype = str(block.get("type") or "topic_goal").strip()
    found = ((cfg or {}).get("blocks") or {}).get(btype)
    return found if isinstance(found, dict) else {}


def mcq_payload(block: dict, state: dict | None) -> tuple[list[dict], int]:
    """Choices and the correct index. Dynamic items come from generated_mcq."""
    data = _data(block)
    mode = str(data.get("mode") or "static").strip()
    stored = state if isinstance(state, dict) else {}
    if mode == "dynamic":
        generated = stored.get("generated_mcq") if isinstance(stored.get("generated_mcq"), dict) else None
        if not generated:
            return [], 0
        raw = generated.get("choices") if isinstance(generated.get("choices"), list) else []
        choices = [
            {"id": str(item.get("id") or chr(ord("a") + index)), "text": str(item.get("text") or "")}
            for index, item in enumerate(raw)
            if isinstance(item, dict)
        ]
        return choices, int(generated.get("correct_index") or 0)
    raw = data.get("choices") if isinstance(data.get("choices"), list) else []
    choices: list[dict] = []
    correct = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("is_correct"):
            correct = len(choices)
        choices.append(
            {"id": str(item.get("id") or chr(ord("a") + len(choices))), "text": str(item.get("text") or "")}
        )
    return choices, correct


_PROCEED_EXACT = {
    "good to proceed",
    "no questions",
    "no question",
    "next topic",
    "next",
    "got it",
    "ready",
    "move on",
    "move on anyway",
    "lets continue",
    "continue to next",
    "close",
    "close and move on",
    "done",
    "skip",
    "no final questions",
    "no final questions lets continue",
    "got it ready for the next topic",
}


def _proceed_text(answer: str) -> str:
    text = (answer or "").lower().replace("—", " ").replace("–", " ").replace("'", "")
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(text.split())


def learner_ready_to_proceed(answer: str, flagged: bool) -> bool:
    """True when the learner wants the next topic or the block summary to finish."""
    if flagged:
        return True
    raw = answer or ""
    lowered = raw.lower()
    if "?" in raw or "elaborat" in lowered:
        return False
    text = _proceed_text(raw)
    if not text:
        return False
    if text in _PROCEED_EXACT:
        return True
    words = text.split()
    if len(words) > 14:
        return False
    if words[0] in {"what", "why", "how", "when", "where", "who", "can", "could", "would", "explain", "tell"}:
        return False
    if any(token in words for token in ("not", "wrong", "dont", "confused")):
        return False
    for phrase in (
        "good to proceed",
        "no questions",
        "no question",
        "no final questions",
        "next topic",
        "move on",
        "move on anyway",
        "lets continue",
        "continue to next",
        "close and move on",
        "next part",
        "got it ready for the next topic",
    ):
        if phrase in text:
            return True
    if text in {"ready", "next"} or text.endswith(" ready"):
        return True
    if "got it" in text:
        return True
    return False


def learner_asks_question_or_background(answer: str) -> bool:
    """A question or a request for background, not an attempt at the goal."""
    raw = answer or ""
    if not raw.strip() or learner_ready_to_proceed(raw, False):
        return False
    lowered = raw.lower()
    if "?" in raw or "elaborat" in lowered:
        return True
    text = _proceed_text(raw)
    if not text:
        return False
    words = text.split()
    if words[0] in {"what", "why", "how", "when", "where", "who", "can", "could", "would", "explain", "tell"}:
        return True
    return "background" in text or "more context" in text or "some context" in text


def answer_addresses_substep(
    block: dict,
    substep: str,
    answer: str,
    state: dict | None,
    cfg: dict | None,
) -> bool:
    """The learner's words cover this substep. A model flag is not enough."""
    btype = str(block.get("type") or "topic_goal").strip()
    data = _data(block)
    bcfg = _bcfg(block, cfg or {})
    stored = state if isinstance(state, dict) else {}
    if btype == "mcq" and substep == "choice":
        choices, correct = mcq_payload(block, stored)
        if not choices:
            return False
        picked = match_mcq_choice_index(answer, choices)
        return picked is not None and picked == correct
    if btype == "mcq" and substep == "awaiting_why":
        explanation = str(data.get("correct_explanation") or "").strip()
        if explanation:
            return _matches(answer, explanation)
        return _substantive(answer, 4)
    if btype == "topic_goal":
        required = str(data.get("acceptance_criteria") or data.get("goal") or "").strip()
        if not required:
            return _substantive(answer)
        strictness = str(bcfg.get("goal_evaluation_strictness") or "conceptual_gist")
        if strictness == "precise_vocabulary":
            return _precise(answer, required)
        if strictness == "applied_transfer":
            return _matches(answer, required) and len((answer or "").split()) >= len(required.split()) + 3
        return _matches(answer, required)
    if btype == "case_study" and substep == "predict":
        lowered = (answer or "").strip().lower()
        if lowered in {"case-a", "case-b"}:
            return True
        return _matches(answer, str(data.get("case_a") or "")) or _matches(answer, str(data.get("case_b") or ""))
    if btype == "case_study" and substep == "contrast_and_rule":
        return _matches(answer, str(data.get("invariant_principle") or ""))
    if btype == "case_study" and substep == "transfer":
        expected = str(data.get("transfer_expected") or data.get("invariant_principle") or "")
        return _matches(answer, expected)
    if btype == "socratic" and substep == "initial_thesis":
        return _substantive(answer)
    if btype == "socratic" and substep == "counterexample_probe":
        return _matches(answer, str(data.get("target_synthesis") or ""))
    if btype == "curiosity":
        minimum = 2 if bool(bcfg.get("require_initial_prediction", True)) else 1
        return _substantive(answer, minimum)
    if btype == "worked_example" and substep == "faded_step":
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        index = int(data.get("faded_step_index") or 0)
        step = steps[index] if 0 <= index < len(steps) else ""
        text = step.get("step_text") if isinstance(step, dict) else str(step)
        if not str(text or "").strip():
            return _substantive(answer)
        ok = _matches(answer, str(text))
        if ok and bool(bcfg.get("require_step_self_explanation", True)):
            return _substantive(answer, 4)
        return ok
    if btype == "worked_example" and substep == "solo_solve":
        expected = str(data.get("solo_expected_answer") or "")
        return _matches(answer, expected) if expected else _substantive(answer)
    if btype == "spot_the_flaw":
        flaw = str(data.get("flaw_description") or "")
        corrected = str(data.get("corrected_version") or "")
        found = _matches(answer, flaw) if flaw else _substantive(answer)
        if str(bcfg.get("critique_depth") or "identify_and_correct") == "identify_only":
            return found
        fixed = _matches(answer, corrected) if corrected else found
        return found and fixed
    if btype == "teach_back":
        required = [str(item).strip() for item in (data.get("required_concepts") or []) if str(item).strip()]
        if not required:
            return _substantive(answer)
        hits = sum(1 for item in required if _matches(answer, item))
        if str(bcfg.get("evaluation_strictness") or "") == "all_required_concepts_exact":
            return hits == len(required)
        return hits >= max(1, (len(required) + 1) // 2)
    if btype == "retrieval_check" and substep == "recall":
        fact = str(data.get("expected_fact") or "")
        if not fact:
            return _substantive(answer)
        if bool(bcfg.get("accept_paraphrase", True)):
            return _matches(answer, fact)
        return _strict_fact(answer, fact)
    if btype == "retrieval_check" and substep == "elaborate_why":
        rationale = str(data.get("expected_why_rationale") or "")
        return _matches(answer, rationale) if rationale else _substantive(answer)
    if btype == "explanation":
        return False
    return _substantive(answer)


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
    if btype == "explanation":
        title = str(data.get("block_title") or "").strip()
        if title:
            return title
        topics = data.get("topics") if isinstance(data.get("topics"), list) else []
        if topics and isinstance(topics[0], dict):
            topic_title = str(topics[0].get("title") or "").strip()
            if topic_title:
                return topic_title
    return f"Block {step_index + 1}"


def _explanation_stay(
    *,
    state: dict,
    index: int,
    bid: str,
    results: list[dict],
    met: list[str],
    reveals: int,
    move_attempts: int,
    enrichment_turns: int,
) -> BlockResolution:
    return BlockResolution(
        decision="stay",
        hint_tier="nudge",
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


def _resolve_explanation_turn(
    *,
    answer: str,
    substep_passed: bool,
    block_complete: bool,
    block: dict,
    blocks: list[dict],
    index: int,
    bid: str,
    state: dict,
    substep: str,
    results: list[dict],
    met: list[str],
    reveals: int,
    move_attempts: int,
    cfg: dict,
    strong_text: str,
    work_text: str,
    enrichment_turns: int = 0,
) -> BlockResolution:
    """Walk topics, then the summary. Questions stay. Ready moves on. Never quizzes."""
    topics = explanation_topics(block)
    topic_index = explanation_topic_index(block, state)
    if substep not in {"explain_topic", "summary_check"}:
        substep = "explain_topic"
    state["substep"] = substep
    state["topic_index"] = topic_index
    ready = learner_ready_to_proceed(answer, bool(substep_passed) or bool(block_complete))
    if not ready:
        state["elaboration_turns"] = int(state.get("elaboration_turns") or 0) + 1
        return _explanation_stay(
            state=state,
            index=index,
            bid=bid,
            results=results,
            met=met,
            reveals=reveals,
            move_attempts=move_attempts,
            enrichment_turns=enrichment_turns,
        )
    tries = int(state.get("block_attempts") or 0) + 1
    state["block_attempts"] = tries
    state["elaboration_turns"] = 0
    if substep == "explain_topic" and topics and topic_index < len(topics) - 1:
        state["topic_index"] = topic_index + 1
        state["substep"] = "explain_topic"
        return _explanation_stay(
            state=state,
            index=index,
            bid=bid,
            results=results,
            met=met,
            reveals=reveals,
            move_attempts=0,
            enrichment_turns=enrichment_turns,
        )
    if substep == "explain_topic":
        state["substep"] = "summary_check"
        return _explanation_stay(
            state=state,
            index=index,
            bid=bid,
            results=results,
            met=met,
            reveals=reveals,
            move_attempts=0,
            enrichment_turns=enrichment_turns,
        )
    title = _block_title(block, index)
    ev_id = block_evidence_id(block, index, "summary_check")
    if ev_id not in met:
        met.append(ev_id)
    results.append(
        {
            "id": bid,
            "block_id": bid,
            "block_type": "explanation",
            "title": title,
            "outcome": "engaged",
            "attempts": tries,
            "strong": strong_text or title,
            "work_on": work_text,
            "summary": f"engaged explanation after {tries} tries",
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
    strong: str = "",
    work_on: str = "",
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
    if btype == "explanation":
        return _resolve_explanation_turn(
            answer=answer,
            substep_passed=substep_passed,
            block_complete=block_complete,
            block=block,
            blocks=blocks,
            index=index,
            bid=bid,
            state=state,
            substep=substep,
            results=results,
            met=met,
            reveals=reveals,
            move_attempts=move_attempts,
            cfg=cfg,
            strong_text=(strong or "").strip(),
            work_text=(work_on or "").strip(),
            enrichment_turns=enrichment_turns,
        )
    max_retries = max_retries_for_block(block, cfg, goal)

    # Misconception handling
    if matched_wrong:
        should_redirect = misc_policy == "immediate_redirect" or last_misconception == matched_wrong
        if should_redirect:
            results.append(
                {
                    "id": bid,
                    "block_id": bid,
                    "block_type": btype,
                    "title": _block_title(block, index),
                    "attempts": move_attempts + 1,
                    "outcome": "revealed",
                    "strong": "",
                    "work_on": matched_wrong,
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

    strong_text = (strong or "").strip()
    work_text = (work_on or "").strip()
    addressed = answer_addresses_substep(block, substep, answer, state, cfg)

    def note_try() -> int:
        total = int(state.get("block_attempts") or 0) + 1
        state["block_attempts"] = total
        return total

    def stay(attempts: int, hint: str, *, reveals_now: int | None = None) -> BlockResolution:
        return BlockResolution(
            decision="stay",
            hint_tier=hint if hint in HINTS else "nudge",
            move_attempts=attempts,
            reveals=reveals if reveals_now is None else reveals_now,
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

    def finish(outcome: str, attempts: int, reveals_now: int) -> BlockResolution:
        title = _block_title(block, index)
        noted_strong = strong_text or (title if outcome == "passed" else "")
        noted_work = work_text or ("" if outcome == "passed" else f"Look again at {title}.")
        evidence_substep = substep
        if evidence_substep == "summary_check":
            evidence_substep = str(state.get("last_task_substep") or substep)
        evidence_id = block_evidence_id(block, index, evidence_substep)
        results.append(
            {
                "id": bid,
                "block_id": bid,
                "block_type": btype,
                "title": title,
                "outcome": outcome,
                "attempts": attempts,
                "strong": noted_strong,
                "work_on": noted_work,
                "summary": f"{outcome} {btype} after {attempts} tries",
            }
        )
        if evidence_id not in met:
            met.append(evidence_id)
        return _advance_or_close_component(
            blocks=blocks,
            index=index,
            results=results,
            met=met,
            reveals=reveals_now,
            cfg=cfg,
        )

    if btype == "topic_goal" and substep == "main" and learner_ready_to_proceed(answer, False):
        tries = note_try()
        if addressed and not state.get("revealed_substep"):
            return finish("passed", tries, reveals)
        return finish("revealed", tries, reveals + 1)

    if btype == "topic_goal" and substep == "main" and learner_asks_question_or_background(answer):
        opening = _proceed_text(answer).split()[:1]
        opens_as_question = bool(opening) and opening[0] in {
            "what",
            "why",
            "how",
            "when",
            "where",
            "who",
            "can",
            "could",
            "would",
            "explain",
            "tell",
        }
        if not addressed or opens_as_question:
            return stay(move_attempts, tier)

    if (
        btype == "topic_goal"
        and bool(bcfg.get("fragment_self_explanation", True))
        and fragment
        and not state.get("fragment_prompted")
    ):
        state["fragment_prompted"] = True
        return stay(move_attempts, tier)

    task_steps = substeps[:-1] if substeps and substeps[-1] == "summary_check" else list(substeps)
    on_last_task = bool(task_steps) and bool(substeps) and substeps[-1] == "summary_check" and (
        substep == task_steps[-1] or (btype == "mcq" and substep == "awaiting_why")
    )

    def _summary_outcome() -> str:
        if state.get("revealed_substep"):
            return "revealed"
        if btype == "curiosity" and not _counts_toward_mastery(block, cfg):
            return "engaged"
        return "passed"

    def _enter_summary(*, revealed: bool) -> BlockResolution:
        state["last_task_substep"] = substep
        state["substep"] = "summary_check"
        if revealed:
            state["revealed_substep"] = True
            return stay(0, "reveal", reveals_now=reveals + 1)
        return stay(0, "nudge")

    def _resolve_summary_check() -> BlockResolution:
        stored_task = str(state.get("last_task_substep") or "").strip()
        task_substep = stored_task or (substeps[-2] if len(substeps) >= 2 else substep)
        demonstrated = bool(substep_passed) and answer_addresses_substep(
            block, task_substep, answer, state, cfg
        )
        move_phrase = learner_ready_to_proceed(answer, False)
        if state.get("revealed_substep") and demonstrated and not move_phrase:
            state["revealed_substep"] = False
            note_try()
            if block_complete:
                return finish(_summary_outcome(), int(state.get("block_attempts") or 1), reveals)
            return stay(0, "nudge")
        if demonstrated and state.get("revealed_substep"):
            state["revealed_substep"] = False
        ready = learner_ready_to_proceed(answer, bool(substep_passed) or bool(block_complete))
        if not ready:
            return stay(move_attempts + 1, "nudge")
        tries = int(state.get("block_attempts") or 0) or 1
        return finish(_summary_outcome(), tries, reveals)

    if btype == "mcq" and substep == "choice":
        choices, correct_idx = mcq_payload(block, state)
        if not choices:
            return stay(move_attempts, tier)
        picked = match_mcq_choice_index(answer, choices)
        mcq_state = dict(state.get("mcq") or {})
        mcq_state["choices"] = choices
        mcq_state["correct_index"] = correct_idx
        if picked is not None and picked == correct_idx:
            note_try()
            confirm_mode = str(bcfg.get("confirm_why_on_correct") or "on_retry_only")
            need_why = confirm_mode == "always" or (confirm_mode == "on_retry_only" and move_attempts > 0)
            state["mcq"] = mcq_state
            if need_why:
                state["substep"] = "awaiting_why"
                return stay(0, "nudge")
            return _enter_summary(revealed=False)
        eliminated = list(mcq_state.get("eliminated_indices") or [])
        if picked is not None and picked not in eliminated:
            eliminated.append(picked)
        mcq_state["eliminated_indices"] = eliminated
        state["mcq"] = mcq_state
        note_try()
        if move_attempts + 1 >= max_retries:
            return _enter_summary(revealed=True)
        bumped = _next_tier(tier)
        if bumped == "reveal":
            bumped = "scaffold"
        return stay(move_attempts + 1, bumped)

    if substep == "summary_check":
        return _resolve_summary_check()

    if btype == "socratic" and substep == "counterexample_probe" and addressed:
        depth = max(1, int(bcfg.get("dialogue_depth_turns", 2) or 2))
        probes = int(state.get("probe_turns") or 0) + 1
        state["probe_turns"] = probes
        if probes < depth:
            note_try()
            return stay(move_attempts, "nudge")

    satisfied = addressed and bool(substep_passed) and not (decision == "stay" and not substep_passed)
    if on_last_task and satisfied:
        note_try()
        return _enter_summary(revealed=False)

    if addressed:
        note_try()
        if substep in task_steps:
            position = task_steps.index(substep)
            if position < len(task_steps) - 1:
                state["substep"] = task_steps[position + 1]
                state["probe_turns"] = 0
                return stay(0, "nudge")
        if on_last_task:
            if move_attempts + 1 >= max_retries:
                return _enter_summary(revealed=True)
            return stay(move_attempts + 1, tier)
        if decision == "stay" and not block_complete and move_attempts + 1 < max_retries:
            return stay(move_attempts + 1, tier)
        outcome = "revealed" if state.get("revealed_substep") else "passed"
        return finish(outcome, int(state.get("block_attempts") or 1), reveals)

    tries = note_try()
    if move_attempts + 1 >= max_retries:
        if btype == "worked_example" and substep == "faded_step" and "solo_solve" in substeps:
            state["substep"] = "solo_solve"
            state["revealed_substep"] = True
            return stay(0, "reveal", reveals_now=reveals + 1)
        if on_last_task:
            return _enter_summary(revealed=True)
        return finish("revealed", tries, reveals + 1)
    bumped = _next_tier(tier)
    if bumped == "reveal":
        bumped = "scaffold"
    return stay(move_attempts + 1, bumped)


def _counts_toward_mastery(block: dict, cfg: dict) -> bool:
    kind = str(block.get("type") or "").strip()
    if kind not in {"curiosity", "explanation"}:
        return True
    bcfg = ((cfg or {}).get("blocks") or {}).get(kind) or {}
    return bool(bcfg.get("counts_toward_mastery_score", False))


def _outcome_succeeded(row: dict | None) -> bool:
    if not isinstance(row, dict):
        return False
    return str(row.get("outcome") or "") in {"passed", "engaged"}


def _advance_or_close_component(
    *,
    blocks: list[dict],
    index: int,
    results: list[dict],
    met: list[str],
    reveals: int,
    cfg: dict,
) -> BlockResolution:
    if index < len(blocks) - 1:
        next_idx = index + 1
        next_blk = blocks[next_idx]
        next_id = str(next_blk.get("id") or f"blk_{next_idx + 1}").strip()
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
            next_block_state=initial_block_state(next_blk, cfg),
            block_results=results,
            mark_known=False,
            mark_fragile=False,
            redirect=False,
            unit_complete=False,
            advance_block=True,
            passed=False,
        )

    by_id = {
        str(row.get("id") or row.get("block_id") or ""): row
        for row in results
        if isinstance(row, dict)
    }
    fragile = False
    counted = False
    for position, block in enumerate(blocks):
        if not _counts_toward_mastery(block, cfg):
            continue
        counted = True
        key = str(block.get("id") or f"blk_{position + 1}").strip()
        row = by_id.get(key)
        if not _outcome_succeeded(row):
            fragile = True
    if not counted:
        fragile = False
    return BlockResolution(
        decision="complete",
        hint_tier="reveal" if fragile else "nudge",
        move_attempts=0,
        reveals=reveals,
        enrichment_turns=0,
        rubric_met=met,
        misconception="",
        next_step=index,
        next_block_id=str(blocks[index].get("id") or f"blk_{index + 1}").strip(),
        next_block_state={"substep": "done", "dialogue_turns": 0},
        block_results=results,
        mark_known=not fragile,
        mark_fragile=fragile,
        redirect=False,
        unit_complete=True,
        advance_block=False,
        passed=not fragile,
    )
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
    fresh = _clean_ids(list(rubric_met))
    met = _clean_ids([*stored_rubric, *fresh])
    evidence = set(move.evidence)
    checked = bool(evidence)
    proposed = decision if decision in {"stay", "advance", "complete", "redirect"} else "stay"
    last_index = len(moves) - 1
    mastery_index = last_index - 1 if moves and moves[-1].key == "extra_why" else last_index
    # Earlier points stay on the component. They do not pass an unchecked move by themselves.
    evidence_met = evidence <= set(met) if checked else proposed in {"advance", "complete"} or bool(fresh)

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
            rubric_met=met,
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
