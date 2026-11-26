"""One verdict for a finished component, read by the learner and the parent.

The legacy loop still chooses the next step. This module records what that
step proved, and it is the only place a known, fragile, or unassessed
verdict is decided. An open session has no verdict.

forecast_this_turn stays a preview. It does not call this module.
"""

from __future__ import annotations

from dataclasses import replace

from app.kc_loop import (
    BlockResolution,
    _gives_up,
    learner_ready_to_proceed,
    resolve_block_turn,
    summary_explicit_move_on,
    summary_ready_signal,
    tutor_asked_to_continue,
    tutor_gave_away_answer,
    worked_continue_answer,
)

LEGACY_SCORE = 1
REQUIREMENT_SCORE = 2
SUPPORTED = frozenset({"retrieval_check", "worked_example", "explanation", "curiosity"})
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
}


def scoring_version_for_blocks(blocks: list[dict] | None) -> int:
    """New sessions use the requirement score only when every block is supported.

    A component that mixes in a topic, a question, or any other block stays on
    the score it already had. An empty walk stays on the legacy score too.
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
    return []


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
            phrase = _PHRASE.get(str(row.get("key") or ""), {}).get(str(row.get("observation") or ""))
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


def classify_stored_outcome(stored: dict) -> tuple[str | None, bool]:
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


def requirement_star_unit(status: str, block_results: list, reveals: int) -> dict:
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
        outcome, is_first = classify_stored_outcome(item)
        if outcome in {"passed", "fragile", "unassessed", "revealed"}:
            completed += 1
        if outcome == "revealed":
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
        )
    rubric = list(before_rubric) if continued else list(resolution.rubric_met)
    if new_rows:
        block_verdict = verdict_from_requirements(requirements, finished=True)
        first = first_try_block(requirements) if block_verdict == "known" else False
        outcome = {"known": "passed", "fragile": "fragile", "unassessed": "unassessed"}.get(
            block_verdict or "", "unassessed"
        )
        for row in new_rows:
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
) -> None:
    if kind in {"explanation", "curiosity"}:
        if sealed:
            for row in requirements:
                if row.get("role") == "participation":
                    row["observation"] = "participated"
        return
    before_sub = str(before_state.get("substep") or "")
    key = before_sub
    if before_sub == "summary_check":
        key = str(before_state.get("last_task_substep") or "")
        if not substep_passed:
            return
    target = next((row for row in requirements if row.get("key") == key), None)
    if target is None or target.get("role") != "assessed":
        return
    attempted = _attempted(before_state, after_state, before_move, resolution)
    if not attempted and not substep_passed:
        return
    giveaway = tutor_gave_away_answer(block, before_state, before_sub, prior_tutor)
    revealed = _revealed(kind, before_sub, before_state, after_state)
    if revealed or giveaway:
        observation = "assisted"
    elif _passed(kind, before_sub, before_state, after_state, substep_passed):
        observation = "independent"
    elif attempted:
        observation = "insufficient"
    else:
        return
    _record(target, observation, attempted=attempted or observation != "open", gave_up=_gives_up(answer))


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


def _revealed(kind: str, substep: str, before_state: dict, after_state: dict) -> bool:
    if kind == "retrieval_check" and substep == "recall":
        return bool(after_state.get("recall_revealed")) and not bool(before_state.get("recall_revealed"))
    if kind == "worked_example" and substep == "faded_step":
        return bool(after_state.get("revealed_substep")) and not bool(before_state.get("revealed_substep"))
    return False


def _passed(kind: str, substep: str, before_state: dict, after_state: dict, substep_passed: bool) -> bool:
    after_sub = str(after_state.get("substep") or "")
    if kind == "retrieval_check" and substep == "recall":
        return after_sub != "recall" and not bool(after_state.get("recall_revealed"))
    if substep_passed and after_sub != substep:
        return True
    if substep_passed and substep == "summary_check":
        return True
    return False


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
