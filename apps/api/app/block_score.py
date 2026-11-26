"""One verdict for a finished component, read by the learner and the parent.

The legacy loop still chooses the next step. This module records what that
step proved, and it is the only place a known, fragile, or unassessed
verdict is decided. An open session has no verdict.

forecast_this_turn stays a preview. It does not call this module.
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.kc_loop import (
    BlockResolution,
    _gives_up,
    explain_step_turn,
    learner_ready_to_proceed,
    mcq_payload,
    passage_elaboration_request,
    passage_example_reply,
    resolve_block_turn,
    summary_explicit_move_on,
    summary_needs_learner_question,
    summary_ready_signal,
    tutor_asked_to_continue,
    tutor_gave_away_answer,
    worked_continue_answer,
)

LEGACY_SCORE = 1
REQUIREMENT_SCORE = 2
SUPPORTED = frozenset(
    {
        "retrieval_check",
        "worked_example",
        "explanation",
        "curiosity",
        "topic_goal",
        "mcq",
        "case_study",
        "socratic",
        "spot_the_flaw",
        "teach_back",
        "passage_ela",
    }
)
LEGACY_OUTCOMES = frozenset({"passed", "revealed", "engaged"})
CONTINUE_LABEL = "No final questions — let's continue!"
TELL_ME_MORE = "Tell me more"
MOVE_ON = "Got it - move on"

_PHRASE = {
    "recall": {
        "assisted": "Recall was assisted.",
        "independent": "Recall was independent.",
        "insufficient": "Recall was not shown.",
    },
    "elaborate_why": {
        "assisted": "The reason was assisted.",
        "independent": "The reason was independent.",
        "insufficient": "The reason was not shown.",
    },
    "faded_step": {
        "assisted": "The faded step was assisted.",
        "independent": "The faded step was independent.",
        "insufficient": "The faded step was not shown.",
    },
    "solo_solve": {
        "assisted": "The solo problem was assisted.",
        "independent": "The solo problem was independent.",
        "insufficient": "The solo problem was not shown.",
    },
    "goal": {
        "assisted": "The goal was assisted.",
        "independent": "The goal was independent.",
        "insufficient": "The goal was not shown.",
    },
    "choice": {
        "assisted": "The choice was assisted.",
        "independent": "The choice was independent.",
        "insufficient": "The choice was not shown.",
    },
    "why": {
        "assisted": "The reason for the choice was assisted.",
        "independent": "The reason for the choice was independent.",
        "insufficient": "The reason for the choice was not shown.",
    },
    "predict": {
        "assisted": "The prediction was assisted.",
        "independent": "The prediction was independent.",
        "insufficient": "The prediction was not shown.",
    },
    "rule": {
        "assisted": "The rule was assisted.",
        "independent": "The rule was independent.",
        "insufficient": "The rule was not shown.",
    },
    "transfer": {
        "assisted": "The transfer was assisted.",
        "independent": "The transfer was independent.",
        "insufficient": "The transfer was not shown.",
    },
    "initial_thesis": {
        "assisted": "The thesis was assisted.",
        "independent": "The thesis was independent.",
        "insufficient": "The thesis was not shown.",
    },
    "identify": {
        "assisted": "The flaw identification was assisted.",
        "independent": "The flaw identification was independent.",
        "insufficient": "The flaw was not identified.",
    },
    "repair": {
        "assisted": "The repair was assisted.",
        "independent": "The repair was independent.",
        "insufficient": "The repair was not shown.",
    },
    "initial_explanation": {
        "assisted": "The explanation was assisted.",
        "independent": "The explanation was independent.",
        "insufficient": "The explanation was not shown.",
    },
    "peer_follow_up": {
        "assisted": "The follow-up was assisted.",
        "independent": "The follow-up was independent.",
        "insufficient": "The follow-up was not shown.",
    },
    "peer_follow_up_1": {
        "assisted": "Follow-up 1 was assisted.",
        "independent": "Follow-up 1 was independent.",
        "insufficient": "Follow-up 1 was not shown.",
    },
    "peer_follow_up_2": {
        "assisted": "Follow-up 2 was assisted.",
        "independent": "Follow-up 2 was independent.",
        "insufficient": "Follow-up 2 was not shown.",
    },
    "central_idea": {
        "assisted": "The central idea was assisted.",
        "independent": "The central idea was independent.",
        "insufficient": "The central idea was not shown.",
    },
    "cite_evidence": {
        "assisted": "The citation was assisted.",
        "independent": "The citation was independent.",
        "insufficient": "The citation was not shown.",
    },
    "craft_or_inference": {
        "assisted": "The interpretation was assisted.",
        "independent": "The interpretation was independent.",
        "insufficient": "The interpretation was not shown.",
    },
}


def scoring_version_for_blocks(blocks: list[dict] | None) -> int:
    """New sessions use the requirement score only when every block is supported.

    The supported set is the eleven block types. A component that includes a
    type outside that set stays on the legacy score. An empty walk does too.
    A session keeps the version it opened with.
    """
    rows = [block for block in (blocks or []) if isinstance(block, dict)]
    if not rows:
        return LEGACY_SCORE
    kinds = {str(block.get("type") or "").strip() for block in rows}
    if kinds and kinds <= SUPPORTED:
        return REQUIREMENT_SCORE
    return LEGACY_SCORE


def freeze_requirements(block: dict, cfg: dict | None) -> list[dict]:
    """The requirements this block can prove, all still open."""
    kind = str((block or {}).get("type") or "").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    bcfg = ((cfg or {}).get("blocks") or {}).get(kind) or {}
    if kind == "retrieval_check":
        rows = [_requirement("recall", "Recall", "assessed", 0)]
        if bool(bcfg.get("require_elaborative_why", True)):
            rows.append(_requirement("elaborate_why", "Reason", "assessed", 1))
        return rows
    if kind == "worked_example":
        return [
            _requirement("faded_step", "Faded step", "assessed", 0),
            _requirement("solo_solve", "Solo problem", "assessed", 1),
        ]
    if kind == "explanation":
        label = str(data.get("block_title") or "Explanation").strip() or "Explanation"
        return [_requirement("participation", label, "participation", 0)]
    if kind == "curiosity":
        return [_requirement("participation", "Curiosity", "participation", 0)]
    if kind == "topic_goal":
        return [_requirement("goal", "Goal", "assessed", 0)]
    if kind == "mcq":
        rows = [_requirement("choice", "Choice", "assessed", 0)]
        if str(bcfg.get("confirm_why_on_correct") or "on_retry_only") == "always":
            rows.append(_requirement("why", "Why", "assessed", 1))
        return rows
    if kind == "case_study":
        return _case_requirements(block, cfg)
    if kind == "socratic":
        return _socratic_requirements(block, cfg)
    if kind == "spot_the_flaw":
        rows = [_requirement("identify", "Identify the flaw", "assessed", 0)]
        if str(bcfg.get("critique_depth") or "identify_and_correct") != "identify_only":
            rows.append(_requirement("repair", "Repair", "assessed", 1))
        return rows
    if kind == "teach_back":
        from app.kc_prompt import teach_back_follow_up_count, teach_back_task_steps

        labels = {
            "initial_explanation": "Explanation",
            "peer_follow_up": "Follow-up",
            "peer_follow_up_1": "Follow-up 1",
            "peer_follow_up_2": "Follow-up 2",
        }
        steps = teach_back_task_steps(teach_back_follow_up_count(cfg))
        return [_requirement(step, labels.get(step, step), "assessed", index) for index, step in enumerate(steps)]
    if kind == "passage_ela":
        return [
            _requirement("central_idea", "Central idea", "assessed", 0),
            _requirement("cite_evidence", "Citation", "assessed", 1),
            _requirement("craft_or_inference", "Interpretation", "assessed", 2),
        ]
    return []


def _case_requirements(block: dict, cfg: dict | None) -> list[dict]:
    from app.kc_prompt import substeps_for_block

    labels = {"predict": "Prediction", "contrast_and_rule": "Rule", "transfer": "Transfer"}
    keys = {"predict": "predict", "contrast_and_rule": "rule", "transfer": "transfer"}
    rows: list[dict] = []
    for step in substeps_for_block(block, cfg):
        if step not in keys:
            continue
        rows.append(_requirement(keys[step], labels[step], "assessed", len(rows)))
    return rows


def _socratic_requirements(block: dict, cfg: dict | None) -> list[dict]:
    bcfg = ((cfg or {}).get("blocks") or {}).get("socratic") or {}
    try:
        depth = int(bcfg.get("dialogue_depth_turns", 2) or 2)
    except (TypeError, ValueError):
        depth = 2
    depth = max(1, depth)
    rows = [_requirement("initial_thesis", "Thesis", "assessed", 0)]
    for index in range(depth):
        rows.append(_requirement(f"counterexample_{index + 1}", f"Counterexample {index + 1}", "assessed", index + 1))
    return rows


def _requirement(key: str, label: str, role: str, ordinal: int) -> dict:
    return {
        "key": key,
        "label": label,
        "role": role,
        "observation": "open",
        "attempts": 0,
        "gave_up": False,
        "ordinal": ordinal,
    }


def verdict_from_requirements(requirements: list[dict] | None, *, finished: bool) -> str | None:
    """Known, fragile, or unassessed. An open walk has no verdict.

    Known means every required assessment was shown independently.
    Fragile means the walk finished with help, or a required assessment was
    still short. Unassessed means the learner only took part.
    """
    if not finished:
        return None
    assessed = [row for row in _rows(requirements) if row.get("role") == "assessed"]
    if not assessed:
        return "unassessed"
    observations = {str(row.get("observation") or "open") for row in assessed}
    if observations <= {"independent"}:
        return "known"
    return "fragile"


def verdict_from_results(results: list[dict] | None) -> str | None:
    """The component verdict is the same function over every sealed requirement."""
    gathered: list[dict] = []
    for item in results or []:
        if isinstance(item, dict):
            gathered.extend(_rows(item.get("requirements")))
    if not gathered and not results:
        return None
    return verdict_from_requirements(gathered, finished=True)


def first_try_block(requirements: list[dict] | None) -> bool:
    """Every assessed requirement was independent on its first scored try."""
    assessed = [row for row in _rows(requirements) if row.get("role") == "assessed"]
    if not assessed:
        return False
    for row in assessed:
        try:
            attempts = int(row.get("attempts") or 0)
        except (TypeError, ValueError):
            attempts = 0
        if str(row.get("observation") or "") != "independent" or attempts > 1 or bool(row.get("gave_up")):
            return False
    return True


def _observation_phrase(row: dict) -> str:
    key = str(row.get("key") or "")
    observation = str(row.get("observation") or "")
    phrase = _PHRASE.get(key, {}).get(observation)
    if phrase:
        return phrase
    if key.startswith("counterexample_"):
        number = key.rsplit("_", 1)[-1]
        words = {
            "assisted": "assisted",
            "independent": "independent",
            "insufficient": "not shown",
        }
        word = words.get(observation)
        if word:
            return f"Counterexample {number} was {word}."
    return ""


def parent_text(verdict: str | None, results: list[dict] | None) -> str:
    """Parent wording. Help and participation stay different even when the stars match."""
    rows = [item for item in (results or []) if isinstance(item, dict)]
    kinds = {str(item.get("block_type") or "") for item in rows}
    requirements: list[dict] = []
    for item in rows:
        requirements.extend(_rows(item.get("requirements")))
    if verdict == "unassessed":
        if kinds == {"curiosity"}:
            return "Finished the curiosity hook."
        return "Finished the explanation."
    if verdict == "fragile":
        parts = ["Finished with help."]
        for row in requirements:
            if row.get("role") != "assessed":
                continue
            phrase = _observation_phrase(row)
            if phrase:
                parts.append(phrase)
        return " ".join(parts)
    if verdict == "known":
        return "Known."
    return ""


def offered_actions(
    *,
    scoring_version: int,
    block_type: str,
    substep: str,
    status: str,
    needs_speech: bool,
) -> list[str] | None:
    """Buttons for a requirement-score session. Legacy sessions keep their own buttons."""
    if int(scoring_version or LEGACY_SCORE) < REQUIREMENT_SCORE:
        return None
    if status != "in_progress" or needs_speech:
        return []
    kind = str(block_type or "")
    step = str(substep or "")
    if kind == "explanation" and step != "summary_check":
        return [TELL_ME_MORE, MOVE_ON]
    if step == "summary_check" and kind in SUPPORTED:
        return [CONTINUE_LABEL]
    return []


def stored_block_revealed(stored: dict | None) -> bool:
    return bool(stored and (stored.get("outcome") == "revealed" or stored.get("revealed") is True))


def classify_stored_outcome(stored: dict, scoring_version: int = LEGACY_SCORE) -> tuple[str | None, bool]:
    """Map a stored block row to an outcome and a first-try flag.

    Passed, revealed, and engaged keep today's meaning. An unfamiliar outcome
    is not passed and does not earn the first-try bonus.
    """
    raw = str((stored or {}).get("outcome") or "").strip()
    verdict = str((stored or {}).get("verdict") or "").strip()
    try:
        attempts = int((stored or {}).get("attempts") or 0)
    except (TypeError, ValueError):
        attempts = 0
    explicit = (stored or {}).get("passed_on_first_try")
    if scoring_version >= REQUIREMENT_SCORE and not verdict and (not raw or raw in LEGACY_OUTCOMES):
        # An interrupted modern write may have a legacy loop outcome and no verdict yet.
        requirements = _rows(stored.get("requirements"))
        verdict = verdict_from_requirements(requirements, finished=True)
        explicit = first_try_block(requirements)
    if verdict in {"known", "fragile", "unassessed"} or raw in {"known", "fragile", "unassessed"}:
        if verdict == "unassessed" or raw == "unassessed":
            outcome = "unassessed"
        elif verdict == "fragile" or raw == "fragile":
            outcome = "fragile"
        else:
            outcome = "passed"
        if isinstance(explicit, bool):
            return outcome, bool(explicit) and outcome == "passed"
        return outcome, outcome == "passed" and attempts <= 1
    if raw in {"", "passed", "engaged"}:
        return "passed", attempts <= 1
    if raw == "revealed":
        return "revealed", False
    return raw or None, False


def uses_requirement_score(rows: list) -> bool:
    """True when a session's stored rows must not use the legacy passed fallback."""
    for item in rows:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("outcome") or "").strip()
        verdict = str(item.get("verdict") or "").strip()
        if verdict in {"known", "fragile", "unassessed"} or raw in {"known", "fragile", "unassessed"}:
            return True
        if raw and raw not in LEGACY_OUTCOMES:
            return True
    return False


def requirement_star_unit(status: str, block_results: list, reveals: int, scoring_version: int = LEGACY_SCORE) -> dict:
    """Stars for a requirement-score session. Unfamiliar rows are not passes."""
    del reveals
    rows = [item for item in block_results if isinstance(item, dict)]
    completed = 0
    first_try = 0
    revealed = 0
    verdicts: list[str] = []
    for item in rows:
        raw = str(item.get("outcome") or "").strip()
        verdict = str(item.get("verdict") or "").strip()
        if raw and raw not in LEGACY_OUTCOMES and raw not in {"known", "fragile", "unassessed"} and not verdict:
            continue
        outcome, is_first = classify_stored_outcome(item, scoring_version)
        if outcome in {"passed", "fragile", "unassessed", "revealed"}:
            completed += 1
        if stored_block_revealed(item):
            revealed += 1
        if is_first:
            first_try += 1
        if verdict in {"known", "fragile", "unassessed"}:
            verdicts.append(verdict)
        elif outcome == "fragile":
            verdicts.append("fragile")
        elif outcome == "unassessed":
            verdicts.append("unassessed")
        elif outcome == "passed":
            verdicts.append("known")
    finished = status == "completed"
    mastery = ""
    if finished and verdicts:
        if "fragile" in verdicts:
            mastery = "fragile"
        elif "known" in verdicts:
            mastery = "known"
        elif all(item == "unassessed" for item in verdicts):
            mastery = "unassessed"
    return {
        "patch": False,
        "status": "completed" if finished else ("in_progress" if rows else "not_started"),
        "mastery": mastery,
        "completed_blocks": completed,
        "first_try_blocks_count": first_try,
        "revealed_blocks_count": revealed,
    }


# An option can be named without repeating any of the authored option text.
# Match affirmative statements; a question, negation or menu is not a disclosure.
_CHOICE_LABEL = re.compile(
    r"^(?:(?:the (?:correct |right )?(?:answer|choice|option) is|"
    r"it(?:'s| is)) (?:option |choice )?\(?([a-z0-9_-]+)"
    r"(?=\)|\s*[:,.!—–]|\s+because\b|$)|(?:option |choice )?\(?([a-z0-9_-]+)\)? is (?:correct|right)"
    r"(?=\s*[:,.!—–]|\s+because\b|$))",
    re.I,
)
_REVEAL_AND_REPEAT = re.compile(
    r"(?:here(?:'s| is) the (?:reveal|answer)|the answer is)\s*:"
    r"\s*\S.+?\b(?:say (?:it|that) back|repeat (?:it|that)|put (?:it|that) in your own words)\b",
    re.I | re.S,
)
_DENIES_EXPLANATION = re.compile(
    r"\b(?:not true that|(?:wrong|incorrect|false) (?:that|to (?:say|think))|"
    r"(?:does not|doesn't) mean that|not because)\b", re.I,
)


def remember_tutor_disclosures(block: dict, state: dict, reply: str) -> dict:
    """Keep supplied evidence on the open item without counting a learner attempt."""
    kind = block.get("type")
    step = state.get("substep")
    disclosed = dict(state.get("tutor_disclosures") or {})
    reply = reply.replace("’", "'")
    if kind == "topic_goal" and step == "main" and _REVEAL_AND_REPEAT.search(reply):
        disclosed["goal"] = True
    elif kind == "mcq" and step in {"choice", "awaiting_why"}:
        choices, correct = mcq_payload(block, state)
        correct = (state.get("mcq") or {}).get("frozen_key", correct)
        if not isinstance(correct, int) or not 0 <= correct < len(choices):
            return state
        choice_id = choices[correct]["id"]
        labels = {choice_id.casefold()}
        ordinal = chr(ord("a") + correct)
        if all(choice["id"].casefold() != ordinal for i, choice in enumerate(choices) if i != correct):
            labels.add(ordinal)
        correct_text = choices[correct]["text"].strip().casefold().replace("’", "'").rstrip(".")
        generated = state.get("generated_mcq") or {}
        reason = str(generated.get("correct_explanation") or block.get("data", {}).get("correct_explanation") or "")
        offered_texts = [choice["text"].casefold().replace("’", "'").rstrip(".") for choice in choices]
        menu = len(offered_texts) > 1 and all(text and text in reply.casefold() for text in offered_texts)
        statements = []
        explains = False
        for sentence in re.split(r"(?<=[.!?])\s+", reply):
            line = sentence.strip().strip("*")
            if not line or line.endswith("?") or re.match(r"^(?:think|consider|imagine|try|ask yourself)\b", line, re.I):
                continue
            # "I'm giving you the answer now: it's d) ..." is an explicit label too.
            statement = re.sub(r"^(?:here(?:'s| is) the answer|I'm giving you the answer(?: now)?)[:,]\s*", "", line, flags=re.I)
            match = _CHOICE_LABEL.match(statement)
            names_choice = bool(match and (match.group(1) or match.group(2)).casefold() in labels)
            if correct_text:
                wording, prefix = re.subn(r"^the (?:correct |right )?(?:answer|option|choice) is ", "", statement.casefold())
                names_choice |= wording.rstrip(".!") == correct_text and bool(prefix or statement != line or not menu)
            if menu and not names_choice and any(text in line.casefold() for text in offered_texts):
                continue
            if names_choice and step == "choice":
                disclosed["choice"] = choice_id
            # The option itself is evidence for the choice only. Keep any
            # explanation after the label/option, even in the same sentence.
            rationale = line
            if names_choice:
                explains = True
                rationale = statement[match.end():] if match else ""
                rationale = rationale.lstrip(") :,.—–-").casefold().removeprefix(correct_text)
            if not rationale.strip(" .,!:") or _DENIES_EXPLANATION.search(rationale):
                continue
            statements.append(rationale)
            explains |= bool(re.search(r"\bbecause\b|^the reason is\b", rationale, re.I))
        # A full explanation can span sentences. Ignore questions, coaching
        # prompts and a bare label when comparing it with the authored reason.
        stated = " ".join(statements)
        if reason and stated:
            from app.kc import matches_phrase

            verbatim = reason.casefold().replace("’", "'").rstrip(".") in stated.casefold()
            # matches_phrase normally accepts the right numbers alone. Those
            # establish a result, while a separately assessed reason needs words.
            words = re.sub(r"\d+", " ", stated)
            reason_words = re.sub(r"\d+", " ", reason)
            if verbatim or (explains and matches_phrase(words, reason_words)):
                disclosed["why"] = True
    if not disclosed:
        return state
    updated = {**state, "tutor_disclosures": disclosed}
    if isinstance(state.get("requirements"), list):
        updated["requirements"] = _rows(state["requirements"])
        _tag_disclosed_requirements(updated["requirements"], disclosed)
    return updated


def _tag_disclosed_requirements(requirements: list[dict], disclosed: dict) -> None:
    for row in requirements:
        key = row.get("key")
        if disclosed.get(key):
            row["tutor_disclosed"] = True
            if key == "choice":
                row["disclosed_choice_id"] = disclosed[key]


def score_supported_turn(**kwargs) -> BlockResolution:
    """Run the legacy step, then record requirements on that same outcome.

    Navigation stays the legacy resolution. The verdict replaces the legacy
    known flag when the component finishes.
    """
    before_state = dict(kwargs.get("active_block_state") or {})
    before_results = [dict(row) for row in (kwargs.get("block_results") or []) if isinstance(row, dict)]
    before_rubric = [str(item) for item in (kwargs.get("stored_rubric") or [])]
    resolution = resolve_block_turn(**kwargs)
    return _overlay(
        resolution,
        blocks=list(kwargs.get("blocks") or []),
        step=int(kwargs.get("step") or 0),
        before_state=before_state,
        before_results=before_results,
        before_rubric=before_rubric,
        before_move=int(kwargs.get("move_attempts") or 0),
        answer=str(kwargs.get("answer") or ""),
        substep_passed=bool(kwargs.get("substep_passed")),
        prior_tutor=str(kwargs.get("prior_tutor") or ""),
        cfg=kwargs.get("cfg") or {},
    )


def _overlay(
    resolution: BlockResolution,
    *,
    blocks: list[dict],
    step: int,
    before_state: dict,
    before_results: list[dict],
    before_rubric: list[str],
    before_move: int,
    answer: str,
    substep_passed: bool,
    prior_tutor: str,
    cfg: dict,
) -> BlockResolution:
    index = min(max(step, 0), max(len(blocks) - 1, 0))
    block = blocks[index] if blocks else {}
    kind = str(block.get("type") or "")
    requirements = _rows(before_state.get("requirements")) or freeze_requirements(block, cfg)
    requirements = [dict(row) for row in requirements]
    continued = _summary_continue(answer, before_state, prior_tutor)
    after = dict(resolution.next_block_state or {})
    produced = [dict(row) for row in (resolution.block_results or []) if isinstance(row, dict)]
    new_rows = produced[len(before_results) :] if len(produced) > len(before_results) else []
    if not continued:
        _advance(
            requirements,
            block=block,
            kind=kind,
            before_state=before_state,
            after_state=after,
            before_move=before_move,
            resolution=resolution,
            answer=answer,
            substep_passed=substep_passed,
            prior_tutor=prior_tutor,
            cfg=cfg,
            sealed=bool(new_rows),
            new_outcome=str(new_rows[-1].get("outcome") or "") if new_rows else "",
        )
        _ensure_why(requirements, block, cfg, after)
    # On retry-only MCQs the why row can first appear after its explanation was supplied.
    _tag_disclosed_requirements(requirements, before_state.get("tutor_disclosures") or {})
    rubric = list(before_rubric) if continued else list(resolution.rubric_met)
    if new_rows:
        _drop_unasked_why(requirements)
        block_verdict = verdict_from_requirements(requirements, finished=True)
        first = first_try_block(requirements) if block_verdict == "known" else False
        outcome = {"known": "passed", "fragile": "fragile", "unassessed": "unassessed"}.get(
            block_verdict or "", "unassessed"
        )
        for row in new_rows:
            if row.get("outcome") == "revealed":
                row["revealed"] = True
            row["requirements"] = [dict(item) for item in requirements]
            row["verdict"] = block_verdict
            row["outcome"] = outcome
            row["passed_on_first_try"] = first
            row["summary"] = parent_text(block_verdict, [row]) or row.get("summary") or ""
        produced = [*produced[: len(before_results)], *new_rows]
    if resolution.advance_block and blocks:
        next_index = min(max(int(resolution.next_step), 0), len(blocks) - 1)
        after["requirements"] = freeze_requirements(blocks[next_index], cfg)
    elif not resolution.unit_complete:
        after["requirements"] = [dict(item) for item in requirements]
    component = None
    mark_known = resolution.mark_known
    mark_fragile = resolution.mark_fragile
    passed = resolution.passed
    if resolution.unit_complete:
        component = verdict_from_results(produced)
        after = dict(after)
        after["component_verdict"] = component
        mark_known = component == "known"
        mark_fragile = component == "fragile"
        passed = component == "known"
    return replace(
        resolution,
        next_block_state=after,
        block_results=produced,
        rubric_met=rubric,
        mark_known=mark_known,
        mark_fragile=mark_fragile,
        passed=passed,
    )


def _summary_continue(answer: str, before_state: dict, prior_tutor: str) -> bool:
    if str(before_state.get("substep") or "") != "summary_check":
        return False
    if summary_needs_learner_question(answer, prior_tutor):
        return True
    if learner_ready_to_proceed(answer, False) or summary_explicit_move_on(answer) or summary_ready_signal(answer):
        return True
    return bool(tutor_asked_to_continue(prior_tutor) and worked_continue_answer(answer))


def _advance(
    requirements: list[dict],
    *,
    block: dict,
    kind: str,
    before_state: dict,
    after_state: dict,
    before_move: int,
    resolution: BlockResolution,
    answer: str,
    substep_passed: bool,
    prior_tutor: str,
    cfg: dict,
    sealed: bool,
    new_outcome: str = "",
) -> None:
    if kind in {"explanation", "curiosity"}:
        if sealed:
            for row in requirements:
                if row.get("role") == "participation":
                    row["observation"] = "participated"
        return
    if kind == "spot_the_flaw":
        _advance_flaw(
            requirements,
            block=block,
            before_state=before_state,
            after_state=after_state,
            before_move=before_move,
            resolution=resolution,
            answer=answer,
            prior_tutor=prior_tutor,
        )
        return
    before_sub = str(before_state.get("substep") or "")
    if passage_elaboration_request(block, answer) or passage_example_reply(block, before_sub, before_state, answer):
        # The reveal tier can carry over from the previous passage step. Practice proves nothing on this one.
        return
    if kind == "topic_goal" and before_sub == "explain":
        # The loop grades a substantive goal answer given during the opening.
        # Readiness, requests for help and other opening turns carry no evidence.
        if explain_step_turn(block, answer, before_state, cfg) != "attempt":
            return
        before_sub = "main"
    if before_sub == "summary_check" and not substep_passed:
        return
    key = _active_key(kind, before_sub, before_state, after_state)
    target = next((row for row in requirements if row.get("key") == key), None)
    if target is None or target.get("role") != "assessed":
        return
    # Finishing the block replaces the state, so the attempt counter is not on it.
    attempted = _attempted(before_state, after_state, before_move, resolution) or sealed
    if not attempted and not substep_passed:
        return
    step_for_giveaway = before_sub
    if before_sub == "summary_check":
        step_for_giveaway = str(before_state.get("last_task_substep") or before_sub)
    if kind == "mcq":
        # A label supplied on the choice step does not answer the separate why.
        disclosure = remember_tutor_disclosures(block, before_state, prior_tutor)
        giveaway = bool((disclosure.get("tutor_disclosures") or {}).get(key))
    else:
        giveaway = bool((before_state.get("tutor_disclosures") or {}).get(key)) or tutor_gave_away_answer(
            block, before_state, step_for_giveaway, prior_tutor
        )
    accepted = _passed(kind, before_sub, before_state, after_state, substep_passed, new_outcome)
    # A sealed "revealed" is this step's help, except a worked solo that the loop
    # still labels revealed because the faded step was shown earlier.
    revealed = _revealed(kind, before_sub, before_state, after_state, new_outcome, resolution) or (
        new_outcome == "revealed" and not accepted
    )
    if revealed or giveaway:
        observation = "assisted"
    elif accepted:
        observation = "independent"
    elif attempted:
        observation = "insufficient"
    else:
        return
    _record(target, observation, attempted=attempted or observation != "open", gave_up=_gives_up(answer))


def _ensure_why(requirements: list[dict], block: dict, cfg: dict, state: dict) -> None:
    """A why that appears only after a retry is still its own requirement."""
    if str(block.get("type") or "") != "mcq":
        return
    if str(state.get("substep") or "") != "awaiting_why":
        return
    if any(row.get("key") == "why" for row in requirements):
        return
    bcfg = ((cfg or {}).get("blocks") or {}).get("mcq") or {}
    if str(bcfg.get("confirm_why_on_correct") or "on_retry_only") == "never":
        return
    requirements.append(_requirement("why", "Why", "assessed", len(requirements)))


def _drop_unasked_why(requirements: list[dict]) -> None:
    """A why frozen at open but never asked does not keep a first-try pass from known."""
    requirements[:] = [
        row
        for row in requirements
        if not (row.get("key") == "why" and str(row.get("observation") or "") == "open")
    ]


def _active_key(kind: str, substep: str, before_state: dict, after_state: dict) -> str | None:
    step = substep
    if step == "summary_check":
        step = str(before_state.get("last_task_substep") or "")
    if kind == "socratic" and step == "counterexample_probe":
        before_n = _as_int(before_state.get("probe_turns"))
        after_n = _as_int(after_state.get("probe_turns"))
        number = after_n if after_n > before_n else before_n + 1
        return f"counterexample_{number}"
    mapping = {
        "topic_goal": {"main": "goal"},
        "mcq": {"choice": "choice", "awaiting_why": "why"},
        "case_study": {"predict": "predict", "contrast_and_rule": "rule", "transfer": "transfer"},
        "socratic": {"initial_thesis": "initial_thesis"},
        "retrieval_check": {"recall": "recall", "elaborate_why": "elaborate_why"},
        "worked_example": {"faded_step": "faded_step", "solo_solve": "solo_solve"},
        "teach_back": {
            "initial_explanation": "initial_explanation",
            "peer_follow_up": "peer_follow_up",
            "peer_follow_up_1": "peer_follow_up_1",
            "peer_follow_up_2": "peer_follow_up_2",
        },
        "passage_ela": {
            "central_idea": "central_idea",
            "cite_evidence": "cite_evidence",
            "craft_or_inference": "craft_or_inference",
        },
    }
    return mapping.get(kind, {}).get(step)


def _advance_flaw(
    requirements: list[dict],
    *,
    block: dict,
    before_state: dict,
    after_state: dict,
    before_move: int,
    resolution: BlockResolution,
    answer: str,
    prior_tutor: str,
) -> None:
    """Identify and repair are separate. Supplying the repair leaves a found flaw intact."""
    from app.kc_loop import _data, _matches

    data = _data(block)
    flaw = str(data.get("flaw_description") or "")
    corrected = str(data.get("corrected_version") or "")
    found = bool(flaw) and _matches(answer, flaw)
    fixed = bool(corrected) and _matches(answer, corrected)
    attempted = _attempted(before_state, after_state, before_move, resolution)
    revealed = bool(after_state.get("revealed_substep")) and not bool(before_state.get("revealed_substep"))
    giveaway = tutor_gave_away_answer(block, before_state, "critique", prior_tutor)
    gave_up = _gives_up(answer)
    identify = next((row for row in requirements if row.get("key") == "identify"), None)
    repair = next((row for row in requirements if row.get("key") == "repair"), None)
    if identify is not None and str(identify.get("observation") or "") != "independent":
        if found and attempted:
            # Finding the flaw stands even when this same turn also supplies the repair.
            _record(identify, "independent", attempted=True, gave_up=gave_up)
        elif revealed:
            _record(identify, "assisted", attempted=attempted, gave_up=gave_up)
        elif attempted and not giveaway:
            _record(identify, "insufficient", attempted=True, gave_up=gave_up)
    if repair is None or str(repair.get("observation") or "") == "independent":
        return
    if fixed and attempted and not giveaway:
        _record(repair, "independent", attempted=True, gave_up=gave_up)
    elif (revealed or giveaway) and (attempted or revealed or giveaway):
        _record(repair, "assisted", attempted=attempted or revealed, gave_up=gave_up)


def _attempted(before_state: dict, after_state: dict, before_move: int, resolution: BlockResolution) -> bool:
    try:
        before_block = int(before_state.get("block_attempts") or 0)
    except (TypeError, ValueError):
        before_block = 0
    try:
        after_block = int(after_state.get("block_attempts") or 0)
    except (TypeError, ValueError):
        after_block = 0
    if after_block > before_block:
        return True
    return int(resolution.move_attempts) > int(before_move)


def _revealed(
    kind: str,
    substep: str,
    before_state: dict,
    after_state: dict,
    new_outcome: str,
    resolution: BlockResolution,
) -> bool:
    if kind == "retrieval_check" and substep == "recall":
        return bool(after_state.get("recall_revealed")) and not bool(before_state.get("recall_revealed"))
    if kind == "worked_example" and substep == "faded_step":
        return bool(after_state.get("revealed_substep")) and not bool(before_state.get("revealed_substep"))
    if kind == "case_study" and substep == "predict":
        return bool(after_state.get("prediction_supplied")) and not bool(before_state.get("prediction_supplied"))
    if kind == "case_study" and substep == "contrast_and_rule":
        return bool(after_state.get("rule_supplied")) and not bool(before_state.get("rule_supplied"))
    if kind == "passage_ela" and substep == "cite_evidence":
        if bool(after_state.get("citation_assisted")) and not bool(before_state.get("citation_assisted")):
            return True
    if kind == "passage_ela" and resolution.hint_tier == "reveal":
        return True
    if kind == "mcq" and substep == "choice" and after_state.get("choice_assisted") and not before_state.get("choice_assisted"):
        return True
    if kind == "topic_goal" and substep in {"main", "summary_check"} and new_outcome == "revealed":
        return True
    return bool(after_state.get("revealed_substep")) and not bool(before_state.get("revealed_substep"))


def _passed(
    kind: str,
    substep: str,
    before_state: dict,
    after_state: dict,
    substep_passed: bool,
    new_outcome: str,
) -> bool:
    after_sub = str(after_state.get("substep") or "")
    if kind == "retrieval_check" and substep == "recall":
        return after_sub != "recall" and not bool(after_state.get("recall_revealed"))
    if kind == "socratic" and substep == "counterexample_probe":
        return _as_int(after_state.get("probe_turns")) > _as_int(before_state.get("probe_turns"))
    if kind == "socratic" and substep == "initial_thesis" and after_sub not in {"", substep} and new_outcome != "revealed":
        return True
    if kind == "mcq" and substep == "choice" and after_sub not in {"", "choice"}:
        return True
    if kind == "passage_ela" and after_sub not in {"", substep} and not after_state.get("citation_assisted"):
        return True
    if kind == "case_study" and after_sub not in {"", substep} and new_outcome != "revealed":
        return True
    if kind == "teach_back" and after_sub not in {"", substep} and new_outcome != "revealed":
        return True
    if kind == "topic_goal" and substep == "main" and after_sub not in {"", "main"} and new_outcome != "revealed":
        return True
    if kind == "topic_goal" and substep in {"main", "summary_check"} and new_outcome == "passed":
        return True
    if substep_passed and after_sub != substep:
        return True
    if substep_passed and substep == "summary_check":
        return True
    return False


def _as_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _record(target: dict, observation: str, *, attempted: bool, gave_up: bool) -> None:
    current = str(target.get("observation") or "open")
    if attempted:
        try:
            target["attempts"] = int(target.get("attempts") or 0) + 1
        except (TypeError, ValueError):
            target["attempts"] = 1
    if gave_up:
        target["gave_up"] = True
    if current == "assisted":
        return
    if current == "independent" and observation != "independent":
        return
    if current == "independent" and observation == "independent":
        return
    target["observation"] = observation


def _rows(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]
