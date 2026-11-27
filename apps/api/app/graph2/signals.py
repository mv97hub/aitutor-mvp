"""Deterministic Graph-2 signals: opportunity gate, caps, biomarkers, and child end card.

Runs synchronously on component close with zero database writes and zero model calls.
Must never import `app.kc_prompt`, `app.kc_loop`, `app.kc`, or `app.block_score`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.block_catalog import SKILL_KEYS
from app.mastery import actionable_spec, claim_ids_of, claim_skills

PRIOR_SCORE = 0.50
MIN_OBSERVATIONS_FOR_RADAR = 3
REVEAL_CAP = 0.20
OVERLAP_CAP = 0.40
OVERLAP_THRESHOLD = 0.65
OWN_WORDS_OVERLAP_MAX = 0.20
MAX_END_CARD_ITEMS = 3

SKILL_LABELS: dict[str, str] = {
    "evidence": "Evidence",
    "perspectives": "Perspectives",
    "causes": "Causes",
    "inquiry": "Inquiry",
    "errors": "Errors",
    "transfer": "Transfer",
    "explaining": "Explaining",
    "calibration": "Calibration",
}

# Canonical block-type -> permitted skill keys (before claim intersection & special gates).
# `topic_goal` and `summary_check` are strictly excluded (never graded for the eight).
BLOCK_CAPABILITY_MATRIX: dict[str, frozenset[str]] = {
    "passage_ela": frozenset({"evidence"}),
    "retrieval_check": frozenset({"evidence", "calibration"}),
    "case_study": frozenset({"evidence", "perspectives", "causes", "transfer"}),
    "socratic": frozenset({"perspectives", "inquiry"}),
    "curiosity": frozenset({"inquiry", "causes"}),
    "explanation": frozenset({"causes"}),
    "spot_the_flaw": frozenset({"errors"}),
    "worked_example": frozenset({"errors", "transfer"}),
    "teach_back": frozenset({"explaining", "transfer"}),
    "mcq": frozenset({"evidence"}),
    "topic_goal": frozenset(),
}

# Substep-specific skill restrictions for multi-substep blocks.
WORKED_EXAMPLE_SUBSTEP_SKILLS: dict[str, frozenset[str]] = {
    "faded_step": frozenset({"errors"}),
    "solo_solve": frozenset({"transfer"}),
}

GRADED_BLOCK_TYPES = frozenset(
    {
        "passage_ela",
        "retrieval_check",
        "case_study",
        "socratic",
        "curiosity",
        "explanation",
        "spot_the_flaw",
        "worked_example",
        "teach_back",
        "mcq",
    }
)

EARLY_HARD_SUBSTEPS = frozenset(
    {"faded_step", "contrast_and_rule", "identify", "central_idea", "initial_thesis", "recall"}
)
LATER_HARD_SUBSTEPS = frozenset(
    {"solo_solve", "transfer", "repair", "craft_or_inference", "counterexample_probe", "elaborate_why"}
)

_NON_SUBSTANTIVE_NAV = frozenset(
    {
        "yes",
        "no",
        "ok",
        "okay",
        "sure",
        "ready",
        "next",
        "done",
        "skip",
        "got it",
        "move on",
        "next part",
        "next topic",
        "tell me more",
        "got it move on",
        "no final questions lets continue",
        "no final questions",
        "continue",
        "close",
    }
)

_CALIBRATION_CLAIM_RE = re.compile(
    r"\b(?:how sure|certain|certainty|confiden\w*|change\s+(?:their|your|his|her)\s+mind|"
    r"revise|rethink|calibrat\w*|unsure|doubt|what\s+evidence\s+would)\b",
    re.IGNORECASE,
)

_MCQ_FACT_CLAIM_RE = re.compile(
    r"\b(?:given\s+(?:fact|line|text|data|number|evidence|case|table|passage)|"
    r"from\s+(?:the\s+)?(?:text|passage|data|fact|table|chart|case|evidence|source)|"
    r"follow\s+from|rest\w*\s+on|based\s+on\s+(?:the\s+)?(?:fact|evidence|data|text|case)|"
    r"cite|justify|support\w*\s+(?:with|by)\s+(?:a\s+)?(?:fact|evidence|line|number|data))\b",
    re.IGNORECASE,
)

_TEACH_BACK_TRANSFER_CLAIM_RE = re.compile(
    r"\b(?:new\s+(?:audience|case|situation|example|context|scenario)|"
    r"different\s+(?:audience|case|situation|context)|another\s+(?:case|situation|audience)|"
    r"younger|beginner|someone\s+else|transfer|apply\s+to)\b",
    re.IGNORECASE,
)

_INQUIRY_QUESTION_RE = re.compile(
    r"(?:\bwhy\b|\bwhat\s+if\b|\bwhat\s+would\s+happen\s+if\b|\bhow\s+come\b|\bwhat\s+about\s+if\b)",
    re.IGNORECASE,
)

_END_CARD_SENTENCES: dict[str, str] = {
    "evidence": "You grounded your answer in real details from the material.",
    "perspectives": "You looked carefully at more than one point of view.",
    "causes": "You traced what caused the change and why it happened.",
    "inquiry": "You asked sharp questions to test the idea further.",
    "errors": "You spotted where the reasoning broke down.",
    "transfer": "You carried the idea into a brand-new situation.",
    "explaining": "You explained the idea clearly in your own words.",
    "calibration": "You checked how sure you were and what would change your mind.",
}


@dataclass(frozen=True)
class SubstepEvidence:
    block_id: str
    block_index: int
    block_type: str
    substep: str
    child_lines: tuple[str, ...]
    tutor_lines: tuple[str, ...]
    passed: bool
    revealed: bool
    giveaway: bool
    attempts: int
    hint_tier: str
    on_topic_questions: tuple[str, ...] = ()
    required_quote: bool = False


@dataclass(frozen=True)
class EligibleSkillEvidence:
    skill: str
    claim_id: str
    claim_statement: str
    block_id: str
    block_type: str
    substeps: tuple[str, ...]
    child_lines: tuple[str, ...]
    tutor_lines: tuple[str, ...]
    on_topic_questions: tuple[str, ...]
    cap: float | None
    cap_reason: str | None
    max_overlap: float
    revealed_or_giveaway: bool
    independent_pass: bool
    best_quote: str


@dataclass(frozen=True)
class CloseAnalysis:
    actionable: bool
    eligible_skills: dict[str, EligibleSkillEvidence] = field(default_factory=dict)
    biomarkers: dict[str, bool] = field(default_factory=dict)
    block_affinity_deltas: dict[str, dict[str, int]] = field(default_factory=dict)
    hint_uptake_deltas: dict[str, int] = field(default_factory=dict)
    expression_sample: dict[str, float | int] = field(default_factory=dict)
    misconceptions: list[str] = field(default_factory=list)
    analogies_worked: list[str] = field(default_factory=list)
    end_card: dict | None = None


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _is_nav_only(text: str) -> bool:
    norm = " ".join(_tokens(text))
    if not norm:
        return True
    return norm in _NON_SUBSTANTIVE_NAV


def _substantive_lines(lines: list[str] | tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for raw in lines:
        cleaned = " ".join(str(raw or "").split()).strip()
        if cleaned and not _is_nav_only(cleaned):
            out.append(cleaned)
    return out


def three_gram_overlap(child_text: str, tutor_texts: list[str] | tuple[str, ...]) -> float:
    """Fraction of the child's word 3-grams that appear in prior tutor lines for the block."""
    child_toks = _tokens(child_text)
    if len(child_toks) < 3:
        return 0.0
    child_grams = {tuple(child_toks[i : i + 3]) for i in range(len(child_toks) - 2)}
    if not child_grams:
        return 0.0
    tutor_grams: set[tuple[str, str, str]] = set()
    for line in tutor_texts:
        t_toks = _tokens(line)
        if len(t_toks) >= 3:
            for i in range(len(t_toks) - 2):
                tutor_grams.add((t_toks[i], t_toks[i + 1], t_toks[i + 2]))
    if not tutor_grams:
        return 0.0
    return round(len(child_grams & tutor_grams) / len(child_grams), 4)


def _trim_quote(text: str, limit: int = 180) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _claim_asks_calibration(claim: dict) -> bool:
    statement = str(claim.get("statement") or "")
    return bool(_CALIBRATION_CLAIM_RE.search(statement))


def _mcq_claim_grounded_in_fact(claim: dict, block: dict) -> bool:
    statement = str(claim.get("statement") or "")
    if _MCQ_FACT_CLAIM_RE.search(statement):
        return True
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    stem = str(data.get("question_stem") or "")
    target_skill = str(data.get("target_skill") or "")
    if _MCQ_FACT_CLAIM_RE.search(f"{stem} {target_skill}") and "evidence" in (
        claim.get("skills") if isinstance(claim.get("skills"), list) else []
    ):
        return True
    return False


def _teach_back_allows_transfer(claim: dict) -> bool:
    explicit = claim.get("skills")
    if isinstance(explicit, list):
        return "transfer" in [str(item).strip().lower() for item in explicit]
    return bool(_TEACH_BACK_TRANSFER_CLAIM_RE.search(str(claim.get("statement") or "")))


def _skill_allowed_for_block_substep(
    *,
    skill: str,
    block: dict,
    substep: str,
    claim: dict,
    child_lines: list[str],
) -> bool:
    btype = str(block.get("type") or "").strip()
    if btype in {"", "topic_goal"} or substep == "summary_check":
        return False

    # Calibration is cross-cutting, ONLY when the claim explicitly asks certainty or what would change their mind.
    if skill == "calibration":
        if btype not in GRADED_BLOCK_TYPES:
            return False
        return _claim_asks_calibration(claim)

    allowed = BLOCK_CAPABILITY_MATRIX.get(btype, frozenset())
    if skill not in allowed:
        return False

    if btype == "worked_example":
        allowed_sub = WORKED_EXAMPLE_SUBSTEP_SKILLS.get(substep, frozenset())
        return skill in allowed_sub

    if btype == "mcq":
        if skill != "evidence":
            return False
        return _mcq_claim_grounded_in_fact(claim, block)

    if btype == "teach_back" and skill == "transfer":
        return _teach_back_allows_transfer(claim)

    if btype == "explanation":
        # Child must actually articulate a causal explanation (not just click move-on buttons).
        return bool(_substantive_lines(child_lines))

    return True


def _extract_substeps_for_block(
    *,
    block: dict,
    block_index: int,
    result_row: dict,
    messages: list[dict],
) -> list[SubstepEvidence]:
    bid = str(block.get("id") or result_row.get("id") or result_row.get("block_id") or f"blk_{block_index + 1}")
    btype = str(block.get("type") or result_row.get("block_type") or "").strip()
    outcome = str(result_row.get("outcome") or "").strip()
    block_revealed = bool(
        result_row.get("revealed") is True
        or outcome == "revealed"
        or result_row.get("answer_given_away") is True
    )
    block_giveaway = bool(result_row.get("giveaway") is True or result_row.get("answer_given_away") is True)

    # Prefer the structured substep_log sealed onto block_results by kc_loop/kc.
    raw_log = result_row.get("substep_log")
    if isinstance(raw_log, list) and raw_log:
        rows: list[SubstepEvidence] = []
        for entry in raw_log:
            if not isinstance(entry, dict):
                continue
            substep = str(entry.get("substep") or "").strip()
            if not substep or substep == "summary_check":
                continue
            child_lines = tuple(str(x) for x in (entry.get("child_lines") or []) if str(x).strip())
            tutor_lines = tuple(str(x) for x in (entry.get("tutor_lines") or []) if str(x).strip())
            side_qs = tuple(str(x) for x in (entry.get("on_topic_questions") or []) if str(x).strip())
            revealed = bool(entry.get("revealed")) or block_revealed
            giveaway = bool(entry.get("giveaway")) or block_giveaway
            passed = bool(entry.get("passed")) and not revealed and not giveaway
            required_quote = bool(entry.get("required_quote")) or (
                btype == "passage_ela" and substep == "cite_evidence"
            )
            rows.append(
                SubstepEvidence(
                    block_id=bid,
                    block_index=block_index,
                    block_type=btype,
                    substep=substep,
                    child_lines=child_lines,
                    tutor_lines=tutor_lines,
                    passed=passed,
                    revealed=revealed,
                    giveaway=giveaway,
                    attempts=int(entry.get("attempts") or 0),
                    hint_tier=str(entry.get("hint_tier") or "nudge"),
                    on_topic_questions=side_qs,
                    required_quote=required_quote,
                )
            )
        if rows:
            return rows

    # Fallback reconstruction from stored messages (step == block_index) + requirements.
    block_msgs = [msg for msg in messages if int(msg.get("step", -1)) == block_index]
    user_lines = tuple(str(msg.get("content") or "") for msg in block_msgs if msg.get("role") == "user")
    tutor_lines = tuple(str(msg.get("content") or "") for msg in block_msgs if msg.get("role") == "assistant")
    side_qs = tuple(line for line in user_lines if _is_inquiry_question(line))
    reqs = [row for row in (result_row.get("requirements") or []) if isinstance(row, dict)]
    if reqs:
        out: list[SubstepEvidence] = []
        for req in reqs:
            key = str(req.get("key") or "").strip()
            if not key:
                continue
            substep = _requirement_key_to_substep(btype, key)
            obs = str(req.get("observation") or "open")
            disclosed = bool(req.get("tutor_disclosed"))
            gave_up = bool(req.get("gave_up"))
            revealed = block_revealed or disclosed or gave_up or obs == "insufficient"
            giveaway = block_giveaway or disclosed
            passed = (obs in {"independent", "participated"}) and not revealed and not giveaway
            out.append(
                SubstepEvidence(
                    block_id=bid,
                    block_index=block_index,
                    block_type=btype,
                    substep=substep,
                    child_lines=user_lines,
                    tutor_lines=tutor_lines,
                    passed=passed,
                    revealed=revealed,
                    giveaway=giveaway,
                    attempts=int(req.get("attempts") or 0),
                    hint_tier="reveal" if revealed else ("scaffold" if obs == "assisted" else "nudge"),
                    on_topic_questions=side_qs,
                    required_quote=(btype == "passage_ela" and substep == "cite_evidence"),
                )
            )
        if out:
            return out

    # Legacy result row with neither substep_log nor requirements.
    default_sub = _default_substep_name(btype)
    return [
        SubstepEvidence(
            block_id=bid,
            block_index=block_index,
            block_type=btype,
            substep=default_sub,
            child_lines=user_lines,
            tutor_lines=tutor_lines,
            passed=(outcome in {"passed", "engaged"}) and not block_revealed and not block_giveaway,
            revealed=block_revealed,
            giveaway=block_giveaway,
            attempts=int(result_row.get("attempts") or 0),
            hint_tier="reveal" if block_revealed else "nudge",
            on_topic_questions=side_qs,
            required_quote=(btype == "passage_ela" and default_sub == "cite_evidence"),
        )
    ]


def _requirement_key_to_substep(btype: str, key: str) -> str:
    if btype == "case_study" and key == "rule":
        return "contrast_and_rule"
    if btype == "socratic" and key.startswith("counterexample"):
        return "counterexample_probe"
    if btype == "spot_the_flaw" and key in {"identify", "repair"}:
        return key
    if btype == "mcq" and key == "why":
        return "awaiting_why"
    return key


def _default_substep_name(btype: str) -> str:
    defaults = {
        "worked_example": "solo_solve",
        "passage_ela": "cite_evidence",
        "retrieval_check": "recall",
        "case_study": "contrast_and_rule",
        "socratic": "counterexample_probe",
        "curiosity": "hook_and_predict",
        "explanation": "explain",
        "spot_the_flaw": "identify",
        "teach_back": "initial_explanation",
        "mcq": "choice",
        "topic_goal": "main",
    }
    return defaults.get(btype, "main")


def _is_inquiry_question(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned or _is_nav_only(cleaned):
        return False
    if _INQUIRY_QUESTION_RE.search(cleaned):
        return True
    return False


def _pick_best_quote(lines: list[str]) -> str:
    substantive = _substantive_lines(lines)
    if not substantive:
        return ""
    # Prefer the most substantial child utterance from the eligible substeps.
    best = max(substantive, key=lambda line: (len(_tokens(line)), len(line)))
    return _trim_quote(best)


def _compute_sync_biomarkers(
    *,
    all_substeps: list[SubstepEvidence],
    component_verdict: str,
    off_course_count: int,
) -> dict[str, bool]:
    # 1. Pass in the child's own words (3-gram overlap < 0.20, non-exempt graded step)
    own_words_pass = False
    for sub in all_substeps:
        if sub.block_type not in GRADED_BLOCK_TYPES or sub.required_quote:
            continue
        if not sub.passed or sub.revealed or sub.giveaway:
            continue
        substantive = _substantive_lines(sub.child_lines)
        if not substantive:
            continue
        joined = " ".join(substantive)
        if len(_tokens(joined)) >= 3 and three_gram_overlap(joined, sub.tutor_lines) < OWN_WORDS_OVERLAP_MAX:
            own_words_pass = True
            break

    # 2. Hard step passed unaided after a hard first step
    hard_recovery_pass = False
    saw_hard_first = False
    for sub in all_substeps:
        was_hard = sub.attempts >= 2 or sub.revealed or sub.giveaway or sub.hint_tier in {"analogy", "scaffold", "reveal"}
        if sub.substep in EARLY_HARD_SUBSTEPS and was_hard:
            saw_hard_first = True
        elif saw_hard_first and sub.substep in LATER_HARD_SUBSTEPS:
            if sub.passed and not sub.revealed and not sub.giveaway and sub.attempts <= 1 and sub.hint_tier == "nudge":
                hard_recovery_pass = True
                break
        elif was_hard and sub.block_type in GRADED_BLOCK_TYPES:
            saw_hard_first = True

    # 3. One on-topic why or what-if before a known close
    on_topic_inquiry_before_known = False
    if component_verdict == "known":
        for sub in all_substeps:
            if sub.on_topic_questions:
                on_topic_inquiry_before_known = True
                break
            if off_course_count == 0 and any(_is_inquiry_question(line) for line in sub.child_lines):
                on_topic_inquiry_before_known = True
                break

    return {
        "own_words_pass": own_words_pass,
        "hard_recovery_pass": hard_recovery_pass,
        "on_topic_inquiry_before_known": on_topic_inquiry_before_known,
    }


def _build_end_card(
    *,
    eligible_skills: dict[str, EligibleSkillEvidence],
    prior_skills: dict[str, dict] | None,
) -> dict | None:
    """Build the child's synchronous closing card (at most 3 skills, 1 sentence + quote).

    Only skills requested by this component AND with real evidence appear.
    Revealed/giveaway blocks and unasked skills stay off the card.
    """
    prior = prior_skills if isinstance(prior_skills, dict) else {}
    candidates: list[tuple[int, int, dict]] = []
    for order_idx, skill in enumerate(SKILL_KEYS):
        ev = eligible_skills.get(skill)
        if ev is None:
            continue
        if ev.revealed_or_giveaway:
            continue
        quote = ev.best_quote
        if not quote:
            continue
        prior_count = int((prior.get(skill) or {}).get("count") or 0)
        # Confirmed evidence: either clean independent pass in this component OR prior observations + clean evidence.
        if not ev.independent_pass and prior_count <= 0:
            continue
        # Prioritize clean independent passes from this component, then prior evidence depth.
        priority = (0 if ev.independent_pass else 1, -prior_count, order_idx)
        candidates.append(
            (
                priority[0],
                priority[1],
                {
                    "skill": skill,
                    "label": SKILL_LABELS.get(skill, skill.title()),
                    "sentence": _END_CARD_SENTENCES.get(skill, "You showed strong thinking on this step."),
                    "quote": quote,
                },
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    items = [entry for _, _, entry in candidates[:MAX_END_CARD_ITEMS]]
    return {"items": items}


def analyze_component_close(
    *,
    mastery_spec: dict | None,
    blocks: list[dict],
    block_results: list[dict],
    messages: list[dict],
    component_verdict: str,
    last_misconception: str = "",
    off_course_count: int = 0,
    prior_skills: dict[str, dict] | None = None,
) -> CloseAnalysis:
    """Run all synchronous close-time Graph-2 computations (0 DB, 0 LLM)."""
    results_by_id: dict[str, dict] = {}
    for row in block_results or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("id") or row.get("block_id") or "").strip()
        if key:
            results_by_id[key] = row

    all_substeps: list[SubstepEvidence] = []
    block_affinity_deltas: dict[str, dict[str, int]] = {}
    hint_uptake_deltas = {"independent": 0, "assisted": 0, "revealed": 0, "attempts": 0}
    misconceptions: list[str] = []

    for idx, block in enumerate(blocks or []):
        if not isinstance(block, dict):
            continue
        bid = str(block.get("id") or f"blk_{idx + 1}")
        btype = str(block.get("type") or "").strip()
        row = results_by_id.get(bid)
        if row is None:
            continue
        if str(row.get("outcome") or "").strip() == "fast_tracked" or row.get("fast_tracked") is True:
            continue

        # Block affinity + hint uptake deltas
        aff = block_affinity_deltas.setdefault(btype, {"completed": 0, "independent": 0, "revealed": 0})
        aff["completed"] += 1
        outcome = str(row.get("outcome") or "").strip()
        verdict = str(row.get("verdict") or "").strip()
        is_rev = bool(row.get("revealed") is True or outcome == "revealed")
        if is_rev:
            aff["revealed"] += 1
            hint_uptake_deltas["revealed"] += 1
        elif verdict == "known" or outcome == "passed":
            aff["independent"] += 1
            hint_uptake_deltas["independent"] += 1
        elif verdict == "fragile" or outcome == "fragile":
            hint_uptake_deltas["assisted"] += 1
        hint_uptake_deltas["attempts"] += int(row.get("attempts") or 0)

        work_on = str(row.get("work_on") or "").strip()
        if is_rev and work_on and "revealed after a repeated misconception:" in str(row.get("summary") or "").lower():
            if work_on not in misconceptions:
                misconceptions.append(work_on)

        substeps = _extract_substeps_for_block(
            block=block,
            block_index=idx,
            result_row=row,
            messages=messages or [],
        )
        all_substeps.extend(substeps)

    if last_misconception and last_misconception.strip() and last_misconception.strip() not in misconceptions:
        misconceptions.append(last_misconception.strip())

    # Expression stats across all user turns in this component
    user_texts = _substantive_lines([msg.get("content") or "" for msg in (messages or []) if msg.get("role") == "user"])
    word_counts = [len(_tokens(line)) for line in user_texts]
    question_count = sum(1 for line in user_texts if "?" in line or _is_inquiry_question(line))
    expression_sample: dict[str, float | int] = {
        "turns": len(user_texts),
        "total_words": sum(word_counts),
        "avg_words": round(sum(word_counts) / len(word_counts), 2) if word_counts else 0.0,
        "questions": question_count,
    }

    biomarkers = _compute_sync_biomarkers(
        all_substeps=all_substeps,
        component_verdict=component_verdict,
        off_course_count=off_course_count,
    )

    # Empty mastery_spec -> strictly no skill updates, no judge call, no end card.
    if not actionable_spec(mastery_spec):
        return CloseAnalysis(
            actionable=False,
            eligible_skills={},
            biomarkers=biomarkers,
            block_affinity_deltas=block_affinity_deltas,
            hint_uptake_deltas=hint_uptake_deltas,
            expression_sample=expression_sample,
            misconceptions=misconceptions,
            end_card=None,
        )

    assert isinstance(mastery_spec, dict)
    claims_by_id = {
        str(claim.get("id")): claim
        for claim in (mastery_spec.get("claims") or [])
        if isinstance(claim, dict) and claim.get("id")
    }

    # Accumulate eligible substeps per skill across finished blocks.
    buckets: dict[str, dict] = {}
    substeps_by_block: dict[str, list[SubstepEvidence]] = {}
    for sub in all_substeps:
        substeps_by_block.setdefault(sub.block_id, []).append(sub)

    for idx, block in enumerate(blocks or []):
        if not isinstance(block, dict):
            continue
        bid = str(block.get("id") or f"blk_{idx + 1}")
        if bid not in results_by_id:
            continue
        res_row = results_by_id[bid]
        if str(res_row.get("outcome") or "").strip() == "fast_tracked" or res_row.get("fast_tracked") is True:
            continue
        cids = claim_ids_of(block)
        if not cids:
            continue
        block_subs = substeps_by_block.get(bid) or []
        if not block_subs:
            continue

        for cid in cids:
            claim = claims_by_id.get(cid)
            if claim is None:
                continue
            c_skills = claim_skills(claim, mastery_spec)
            if not c_skills:
                continue
            for skill in c_skills:
                matched_subs = [
                    sub
                    for sub in block_subs
                    if _skill_allowed_for_block_substep(
                        skill=skill,
                        block=block,
                        substep=sub.substep,
                        claim=claim,
                        child_lines=list(sub.child_lines),
                    )
                ]
                if not matched_subs:
                    continue
                bucket = buckets.setdefault(
                    skill,
                    {
                        "claim_id": cid,
                        "claim_statement": str(claim.get("statement") or ""),
                        "block_id": bid,
                        "block_type": str(block.get("type") or ""),
                        "substeps": [],
                        "child_lines": [],
                        "tutor_lines": [],
                        "on_topic_questions": [],
                        "any_revealed": False,
                        "any_giveaway": False,
                        "any_independent": False,
                        "max_overlap": 0.0,
                        "overlap_capped": False,
                    },
                )
                for sub in matched_subs:
                    if sub.substep not in bucket["substeps"]:
                        bucket["substeps"].append(sub.substep)
                    for line in _substantive_lines(sub.child_lines):
                        if line not in bucket["child_lines"]:
                            bucket["child_lines"].append(line)
                    for line in sub.tutor_lines:
                        if line and line not in bucket["tutor_lines"]:
                            bucket["tutor_lines"].append(line)
                    for q in sub.on_topic_questions:
                        if q not in bucket["on_topic_questions"]:
                            bucket["on_topic_questions"].append(q)
                    if sub.revealed:
                        bucket["any_revealed"] = True
                    if sub.giveaway:
                        bucket["any_giveaway"] = True
                    if sub.passed and not sub.revealed and not sub.giveaway:
                        bucket["any_independent"] = True
                    if not sub.required_quote:
                        for line in _substantive_lines(sub.child_lines):
                            ov = three_gram_overlap(line, sub.tutor_lines)
                            if ov > bucket["max_overlap"]:
                                bucket["max_overlap"] = ov
                            if ov >= OVERLAP_THRESHOLD:
                                bucket["overlap_capped"] = True

    eligible: dict[str, EligibleSkillEvidence] = {}
    for skill in SKILL_KEYS:
        b = buckets.get(skill)
        if not b:
            continue
        # Must have at least one child line or question to judge (or revealed/giveaway substep)
        if not b["child_lines"] and not b["on_topic_questions"] and not b["any_revealed"] and not b["any_giveaway"]:
            continue
        cap: float | None = None
        cap_reason: str | None = None
        if b["any_giveaway"]:
            cap = REVEAL_CAP
            cap_reason = "giveaway"
        elif b["any_revealed"]:
            cap = REVEAL_CAP
            cap_reason = "revealed"
        elif b["overlap_capped"]:
            cap = OVERLAP_CAP
            cap_reason = "overlap"

        eligible[skill] = EligibleSkillEvidence(
            skill=skill,
            claim_id=b["claim_id"],
            claim_statement=b["claim_statement"],
            block_id=b["block_id"],
            block_type=b["block_type"],
            substeps=tuple(b["substeps"]),
            child_lines=tuple(b["child_lines"]),
            tutor_lines=tuple(b["tutor_lines"]),
            on_topic_questions=tuple(b["on_topic_questions"]),
            cap=cap,
            cap_reason=cap_reason,
            max_overlap=round(float(b["max_overlap"]), 4),
            revealed_or_giveaway=bool(b["any_revealed"] or b["any_giveaway"]),
            independent_pass=bool(b["any_independent"] and not b["any_revealed"] and not b["any_giveaway"]),
            best_quote=_pick_best_quote(b["child_lines"] or b["on_topic_questions"]),
        )

    end_card = _build_end_card(eligible_skills=eligible, prior_skills=prior_skills)

    return CloseAnalysis(
        actionable=True,
        eligible_skills=eligible,
        biomarkers=biomarkers,
        block_affinity_deltas=block_affinity_deltas,
        hint_uptake_deltas=hint_uptake_deltas,
        expression_sample=expression_sample,
        misconceptions=misconceptions,
        end_card=end_card,
    )
