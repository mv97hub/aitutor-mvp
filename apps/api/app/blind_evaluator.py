"""Quarantined Blind Pre/Post Evaluator (F2 — V1 Proof Gate).

AST-ENFORCED QUARANTINE CONTRACT:
- Reads ONLY `KcGoal` (`id`, `code`, `title`, `description`, `audience`, `standards`,
  `target_kc_ids`) and `KcNode` (`id`, `code`, `title`, `description`, `core_truth`,
  `mastery_spec`), plus `BlindExam`, `BlindExamAttempt`, and `Student`.
- MUST NEVER import `kc_prompt`, `kc_loop`, `kc`, `block_score`, or `graph2`.
- MUST NEVER import or access `KcSession`, `KcMessage`, `KcModelPrompt`,
  `HarnessChat`, `HarnessTurn`, or node activity payloads.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BlindExam, BlindExamAttempt, KcGoal, KcNode, Student

VALID_PHASES = frozenset({"pre", "post"})
VALID_MODES = frozenset({"human", "epistemic_sandbox"})
VALID_ITEM_KINDS = frozenset({"scenario_mcq", "misconception_trap", "short_transfer"})
DEFAULT_EXAM_ITEM_COUNT = 10
HAKE_DENOMINATOR_FLOOR = 0.05
TRANSFER_MAX_POINTS = 2


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: object, limit: int = 800) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _word_tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(tok) >= 3}


def compute_hake_gain(pre: float, post: float) -> float:
    """Normalized Hake learning gain: g = (post - pre) / max(1.0 - pre, 0.05)."""
    pre_v = max(0.0, min(1.0, float(pre)))
    post_v = max(0.0, min(1.0, float(post)))
    denom = max(1.0 - pre_v, HAKE_DENOMINATOR_FLOOR)
    return round((post_v - pre_v) / denom, 4)


def blueprint_counts(total: int = DEFAULT_EXAM_ITEM_COUNT) -> dict[str, int]:
    """40% scenario_mcq, 30% misconception_trap, 30% short_transfer."""
    n = max(3, min(20, int(total or DEFAULT_EXAM_ITEM_COUNT)))
    n_mcq = max(1, round(n * 0.40))
    n_trap = max(1, round(n * 0.30))
    n_transfer = max(1, n - n_mcq - n_trap)
    # Keep exact total when rounding shifts sum.
    while n_mcq + n_trap + n_transfer > n and n_mcq > 1:
        n_mcq -= 1
    while n_mcq + n_trap + n_transfer < n:
        n_mcq += 1
    return {
        "scenario_mcq": n_mcq,
        "misconception_trap": n_trap,
        "short_transfer": n_transfer,
    }


def _quarantined_mastery_spec(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {}
    claims: list[dict] = []
    for item in raw.get("claims") if isinstance(raw.get("claims"), list) else []:
        if not isinstance(item, dict):
            continue
        cid = _clean_text(item.get("id"), 60)
        stmt = _clean_text(item.get("statement"), 300)
        if not stmt:
            continue
        skills = [
            _clean_text(s, 32).lower()
            for s in (item.get("skills") if isinstance(item.get("skills"), list) else [])
            if _clean_text(s, 32)
        ]
        claims.append({"id": cid or f"c{len(claims) + 1}", "statement": stmt, "skills": skills})
    return {
        "archetype": _clean_text(raw.get("archetype"), 60),
        "skills": [
            _clean_text(s, 32).lower()
            for s in (raw.get("skills") if isinstance(raw.get("skills"), list) else [])
            if _clean_text(s, 32)
        ],
        "claims": claims,
    }


def _quarantined_standards(raw: object) -> list[str]:
    out: list[str] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, dict):
            code = _clean_text(item.get("code"), 60)
            text = _clean_text(item.get("text"), 240)
            if code and text:
                out.append(f"{code}: {text}")
            elif text or code:
                out.append(text or code)
        elif isinstance(item, str) and item.strip():
            out.append(_clean_text(item, 240))
    return out


def load_quarantined_course_context(db: Session, goal_id: uuid.UUID) -> dict:
    """Read ONLY quarantined course & component curriculum metadata (never lesson activities or chats)."""
    goal = db.get(KcGoal, goal_id)
    if goal is None:
        raise ValueError("Course not found.")

    raw_ids = goal.target_kc_ids if isinstance(goal.target_kc_ids, list) else []
    ordered_ids: list[uuid.UUID] = []
    for entry in raw_ids:
        try:
            ordered_ids.append(uuid.UUID(str(entry)))
        except ValueError:
            continue

    nodes_by_id: dict[uuid.UUID, KcNode] = {}
    if ordered_ids:
        rows = db.scalars(select(KcNode).where(KcNode.id.in_(ordered_ids))).all()
        nodes_by_id = {row.id: row for row in rows}

    components: list[dict] = []
    for cid in ordered_ids:
        node = nodes_by_id.get(cid)
        if node is None:
            continue
        components.append(
            {
                "id": str(node.id),
                "code": _clean_text(node.code, 120),
                "title": _clean_text(node.title, 200),
                "description": _clean_text(node.description, 400),
                "core_truth": _clean_text(node.core_truth, 400),
                "mastery_spec": _quarantined_mastery_spec(node.mastery_spec),
            }
        )

    payload = {
        "goal_id": str(goal.id),
        "code": _clean_text(goal.code, 120),
        "title": _clean_text(goal.title, 200),
        "description": _clean_text(goal.description, 500),
        "audience": _clean_text(goal.audience, 40) or "9-11",
        "standards": _quarantined_standards(goal.standards),
        "components": components,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {**payload, "spec_fingerprint": fingerprint}


def build_exam_generation_bundle(
    context: dict,
    phase: str,
    *,
    num_items: int = DEFAULT_EXAM_ITEM_COUNT,
) -> dict:
    """Build the single quarantined exam-authoring prompt + strict JSON schema."""
    clean_phase = str(phase or "").strip().lower()
    if clean_phase not in VALID_PHASES:
        raise ValueError("Exam phase must be 'pre' or 'post'.")

    counts = blueprint_counts(num_items)
    total = sum(counts.values())
    comp_lines: list[str] = []
    for idx, comp in enumerate(context.get("components") or [], start=1):
        spec = comp.get("mastery_spec") if isinstance(comp.get("mastery_spec"), dict) else {}
        claims = spec.get("claims") if isinstance(spec.get("claims"), list) else []
        claim_text = "; ".join(
            f"{c.get('id')}: {c.get('statement')} (skills: {', '.join(c.get('skills') or []) or 'general'})"
            for c in claims
        )
        comp_lines.append(
            "\n".join(
                [
                    f"{idx}. [{comp['id']}] {comp['title']}",
                    f"   Description: {comp['description'] or '(none)'}",
                    f"   Core truth: {comp['core_truth'] or '(none)'}",
                    f"   Claims: {claim_text or '(derive from title, description, and core truth)'}",
                ]
            )
        )

    standards_block = "\n".join(f"- {s}" for s in (context.get("standards") or [])) or "- (none specified)"
    form_note = (
        "This is the PRE-TEST form (Form A). Use fresh, concrete everyday scenarios appropriate for ages "
        f"{context.get('audience', '9-11')} that test conceptual understanding before instruction."
        if clean_phase == "pre"
        else "This is the isomorphic POST-TEST form (Form B). Test the EXACT SAME concepts, claims, and difficulty "
        "level as Form A, but use DIFFERENT surface scenarios, numbers, and names so memorized examples do not work."
    )

    user_prompt = "\n\n".join(
        [
            f"Course: {context.get('title')} (audience ages {context.get('audience', '9-11')})",
            f"Course description: {context.get('description') or '(none)'}",
            f"Standards:\n{standards_block}",
            f"Components (quarantined curriculum targets only):\n" + ("\n".join(comp_lines) or "(general course targets)"),
            form_note,
            (
                f"Generate exactly {total} items with this exact blueprint:\n"
                f"- {counts['scenario_mcq']} items with kind='scenario_mcq' (4 choices a/b/c/d, exactly 1 correct)\n"
                f"- {counts['misconception_trap']} items with kind='misconception_trap' (4 choices a/b/c/d where distractors reflect common misconceptions, exactly 1 correct, include trap_rationale)\n"
                f"- {counts['short_transfer']} items with kind='short_transfer' (open-ended novel-scenario explanation with choices=[], correct_choice_id='', a concise rubric_key, and 2–3 concrete key_points worth up to 2 points total)\n"
                "Keep wording calm, clear, and age-appropriate. Never refer to lesson steps, blocks, or tutor chats."
            ),
        ]
    )

    system_prompt = (
        "You are an independent psychometric assessment author writing a blind Pre/Post exam strictly from "
        "course standards and learning targets. Never assume specific classroom examples. "
        "Return valid JSON matching the schema exactly."
    )

    response_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "minItems": total,
                "maxItems": total,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {"type": "string", "enum": ["scenario_mcq", "misconception_trap", "short_transfer"]},
                        "kc_id": {"type": "string"},
                        "skill": {"type": "string"},
                        "prompt": {"type": "string"},
                        "choices": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "id": {"type": "string", "enum": ["a", "b", "c", "d"]},
                                    "text": {"type": "string"},
                                },
                                "required": ["id", "text"],
                            },
                        },
                        "correct_choice_id": {"type": "string"},
                        "trap_rationale": {"type": "string"},
                        "rubric_key": {"type": "string"},
                        "key_points": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "id",
                        "kind",
                        "kc_id",
                        "skill",
                        "prompt",
                        "choices",
                        "correct_choice_id",
                        "trap_rationale",
                        "rubric_key",
                        "key_points",
                    ],
                },
            }
        },
        "required": ["items"],
    }

    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response_schema": response_schema,
        "target_counts": counts,
        "target_total": total,
        "temperature": 0.2,
    }


def build_deterministic_exam_items(
    context: dict,
    phase: str,
    *,
    num_items: int = DEFAULT_EXAM_ITEM_COUNT,
) -> list[dict]:
    """Deterministic zero-LLM exam generator from quarantined course/component metadata."""
    clean_phase = str(phase or "pre").strip().lower()
    if clean_phase not in VALID_PHASES:
        raise ValueError("Exam phase must be 'pre' or 'post'.")
    counts = blueprint_counts(num_items)
    components = list(context.get("components") or [])
    if not components:
        components = [
            {
                "id": context.get("goal_id") or "",
                "title": context.get("title") or "Course concept",
                "description": context.get("description") or "",
                "core_truth": context.get("description") or context.get("title") or "Apply the core idea accurately.",
                "mastery_spec": {},
            }
        ]

    form_tag = "Scenario Set A" if clean_phase == "pre" else "Scenario Set B"
    items: list[dict] = []
    cursor = 0

    def _next_comp() -> tuple[dict, str, str]:
        nonlocal cursor
        comp = components[cursor % len(components)]
        cursor += 1
        truth = comp.get("core_truth") or comp.get("description") or comp.get("title") or "the underlying principle"
        spec = comp.get("mastery_spec") if isinstance(comp.get("mastery_spec"), dict) else {}
        skills = spec.get("skills") if isinstance(spec.get("skills"), list) else []
        skill = skills[0] if skills else "transfer"
        return comp, str(truth), str(skill)

    # 1. 40% scenario_mcq
    for idx in range(counts["scenario_mcq"]):
        comp, truth, skill = _next_comp()
        correct_id = "b" if clean_phase == "post" else "a"
        distractors = [
            "Ignore the underlying mechanism and guess from surface appearances alone.",
            "Assume every outcome happens by chance with no causal pattern.",
            "Treat one unrelated detail as proof of the entire conclusion.",
        ]
        choice_ids = ["a", "b", "c", "d"]
        choices = []
        d_idx = 0
        for cid in choice_ids:
            if cid == correct_id:
                choices.append({"id": cid, "text": truth})
            else:
                choices.append({"id": cid, "text": distractors[d_idx]})
                d_idx += 1
        items.append(
            {
                "id": f"{clean_phase}_mcq_{idx + 1}",
                "kind": "scenario_mcq",
                "kc_id": comp["id"],
                "skill": skill,
                "prompt": f"({form_tag}) In a new situation involving {comp['title']}, which statement best applies the core idea?",
                "choices": choices,
                "correct_choice_id": correct_id,
                "trap_rationale": "",
                "rubric_key": "",
                "key_points": [],
            }
        )

    # 2. 30% misconception_trap
    for idx in range(counts["misconception_trap"]):
        comp, truth, skill = _next_comp()
        correct_id = "c" if clean_phase == "post" else "b"
        distractors = [
            f"A common shortcut claims {comp['title']} works without checking evidence or cause.",
            f"Only the biggest or loudest detail matters when reasoning about {comp['title']}.",
            f"Once you memorize a single label for {comp['title']}, new situations never change the rule.",
        ]
        choices = []
        d_idx = 0
        for cid in ("a", "b", "c", "d"):
            if cid == correct_id:
                choices.append({"id": cid, "text": f"Check the real reason: {truth}"})
            else:
                choices.append({"id": cid, "text": distractors[d_idx]})
                d_idx += 1
        items.append(
            {
                "id": f"{clean_phase}_trap_{idx + 1}",
                "kind": "misconception_trap",
                "kc_id": comp["id"],
                "skill": "errors",
                "prompt": f"({form_tag}) A friend makes a quick claim about {comp['title']}. Which response avoids the common misconception?",
                "choices": choices,
                "correct_choice_id": correct_id,
                "trap_rationale": f"Distractors rely on surface shortcuts instead of {truth}.",
                "rubric_key": "",
                "key_points": [],
            }
        )

    # 3. 30% short_transfer
    for idx in range(counts["short_transfer"]):
        comp, truth, skill = _next_comp()
        words = [w for w in re.findall(r"[a-zA-Z0-9]{4,}", truth)][:4]
        key_points = [truth] if truth else [comp["title"]]
        if len(words) >= 2:
            key_points.append(" ".join(words[:2]))
        items.append(
            {
                "id": f"{clean_phase}_transfer_{idx + 1}",
                "kind": "short_transfer",
                "kc_id": comp["id"],
                "skill": skill if skill != "errors" else "transfer",
                "prompt": (
                    f"({form_tag}) Imagine explaining {comp['title']} in a brand-new situation. "
                    "In 1–3 sentences, explain the core principle and why it holds."
                ),
                "choices": [],
                "correct_choice_id": "",
                "trap_rationale": "",
                "rubric_key": f"Awards 2 points for accurately applying and explaining: {truth}",
                "key_points": key_points,
            }
        )

    return items


def validate_exam_items(raw_items: list[dict]) -> tuple[list[dict], dict]:
    """Validate generated exam items and split out a frozen rubric_key snapshot."""
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Exam items must be a non-empty list.")

    cleaned: list[dict] = []
    rubric_key: dict[str, dict] = {}
    seen_ids: set[str] = set()

    for idx, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Exam item {idx} must be an object.")
        kind = _clean_text(raw.get("kind"), 32).lower()
        if kind not in VALID_ITEM_KINDS:
            raise ValueError(f"Exam item {idx} has invalid kind {kind!r}.")
        item_id = _clean_text(raw.get("id"), 64) or f"item_{idx}"
        if item_id in seen_ids:
            item_id = f"{item_id}_{idx}"
        seen_ids.add(item_id)

        prompt = _clean_text(raw.get("prompt"), 800)
        if not prompt:
            raise ValueError(f"Exam item {item_id!r} requires a non-empty prompt.")
        kc_id = _clean_text(raw.get("kc_id"), 64)
        skill = _clean_text(raw.get("skill"), 32).lower() or ("errors" if kind == "misconception_trap" else "transfer")

        if kind in {"scenario_mcq", "misconception_trap"}:
            raw_choices = raw.get("choices")
            if not isinstance(raw_choices, list) or len(raw_choices) < 2:
                raise ValueError(f"MCQ item {item_id!r} must provide at least 2 choices.")
            choices: list[dict] = []
            choice_ids: set[str] = set()
            for c_idx, ch in enumerate(raw_choices):
                if not isinstance(ch, dict):
                    continue
                cid = _clean_text(ch.get("id"), 16).lower() or chr(ord("a") + c_idx)
                ctext = _clean_text(ch.get("text"), 400)
                if not ctext or cid in choice_ids:
                    continue
                choice_ids.add(cid)
                choices.append({"id": cid, "text": ctext})
            correct_id = _clean_text(raw.get("correct_choice_id"), 16).lower()
            if correct_id not in choice_ids:
                raise ValueError(f"MCQ item {item_id!r} has invalid correct_choice_id {correct_id!r}.")
            trap_rationale = _clean_text(raw.get("trap_rationale"), 400)
            entry = {
                "id": item_id,
                "kind": kind,
                "kc_id": kc_id,
                "skill": skill,
                "prompt": prompt,
                "choices": choices,
                "correct_choice_id": correct_id,
                "trap_rationale": trap_rationale,
                "max_points": 1,
            }
            rubric_key[item_id] = {
                "kind": kind,
                "correct_choice_id": correct_id,
                "trap_rationale": trap_rationale,
                "max_points": 1,
            }
            cleaned.append(entry)
        else:
            rkey = _clean_text(raw.get("rubric_key"), 600)
            kpoints = [
                _clean_text(kp, 240)
                for kp in (raw.get("key_points") if isinstance(raw.get("key_points"), list) else [])
                if _clean_text(kp, 240)
            ]
            if not rkey and not kpoints:
                raise ValueError(f"Short transfer item {item_id!r} requires rubric_key or key_points.")
            entry = {
                "id": item_id,
                "kind": kind,
                "kc_id": kc_id,
                "skill": skill,
                "prompt": prompt,
                "choices": [],
                "rubric_key": rkey or "; ".join(kpoints),
                "key_points": kpoints or [rkey],
                "max_points": TRANSFER_MAX_POINTS,
            }
            rubric_key[item_id] = {
                "kind": kind,
                "rubric_key": entry["rubric_key"],
                "key_points": entry["key_points"],
                "max_points": TRANSFER_MAX_POINTS,
            }
            cleaned.append(entry)

    return cleaned, rubric_key


def public_exam_out(exam: BlindExam, *, course_title: str = "") -> dict:
    """Learner-safe exam representation: strips ALL answer keys and grading rubrics."""
    safe_items: list[dict] = []
    for item in exam.items if isinstance(exam.items, list) else []:
        if not isinstance(item, dict):
            continue
        safe_items.append(
            {
                "id": str(item.get("id") or ""),
                "kind": str(item.get("kind") or "scenario_mcq"),
                "kc_id": str(item.get("kc_id") or ""),
                "skill": str(item.get("skill") or ""),
                "prompt": str(item.get("prompt") or ""),
                "choices": [
                    {"id": str(c.get("id") or ""), "text": str(c.get("text") or "")}
                    for c in (item.get("choices") if isinstance(item.get("choices"), list) else [])
                    if isinstance(c, dict)
                ],
                "max_points": int(item.get("max_points") or (1 if item.get("kind") != "short_transfer" else TRANSFER_MAX_POINTS)),
            }
        )
    return {
        "id": str(exam.id),
        "goal_id": str(exam.goal_id),
        "course_title": course_title,
        "phase": exam.phase,
        "version": int(exam.version or 1),
        "spec_fingerprint": exam.spec_fingerprint,
        "model": exam.model,
        "item_count": len(safe_items),
        "items": safe_items,
        "created_at": exam.created_at.isoformat() if exam.created_at else None,
    }


def latest_exam_for_course(
    db: Session,
    *,
    goal_id: uuid.UUID,
    phase: str,
    spec_fingerprint: str | None = None,
) -> BlindExam | None:
    stmt = select(BlindExam).where(BlindExam.goal_id == goal_id, BlindExam.phase == phase)
    if spec_fingerprint:
        stmt = stmt.where(BlindExam.spec_fingerprint == spec_fingerprint)
    stmt = stmt.order_by(BlindExam.version.desc(), BlindExam.created_at.desc()).limit(1)
    return db.scalar(stmt)


def prepare_exam_prompt_or_cached(
    db: Session,
    *,
    goal_id: uuid.UUID,
    phase: str,
    num_items: int = DEFAULT_EXAM_ITEM_COUNT,
    force_regenerate: bool = False,
) -> dict:
    """Return cached learner-safe exam when up-to-date, else return the quarantined generation bundle."""
    clean_phase = str(phase or "").strip().lower()
    if clean_phase not in VALID_PHASES:
        raise ValueError("Exam phase must be 'pre' or 'post'.")
    ctx = load_quarantined_course_context(db, goal_id)
    if not force_regenerate:
        cached = latest_exam_for_course(
            db,
            goal_id=goal_id,
            phase=clean_phase,
            spec_fingerprint=ctx["spec_fingerprint"],
        )
        if cached is not None:
            return {
                "cached": True,
                "exam": public_exam_out(cached, course_title=ctx["title"]),
            }
    bundle = build_exam_generation_bundle(ctx, clean_phase, num_items=num_items)
    return {
        "cached": False,
        "goal_id": str(goal_id),
        "course_title": ctx["title"],
        "phase": clean_phase,
        "spec_fingerprint": ctx["spec_fingerprint"],
        **bundle,
    }


def validate_and_store_exam(
    db: Session,
    *,
    goal_id: uuid.UUID,
    phase: str,
    raw_items: list[dict] | None = None,
    spec_fingerprint: str | None = None,
    model: str | None = None,
    use_deterministic_fallback: bool = False,
    num_items: int = DEFAULT_EXAM_ITEM_COUNT,
) -> dict:
    """Validate and freeze a Pre or Post exam for a course."""
    clean_phase = str(phase or "").strip().lower()
    if clean_phase not in VALID_PHASES:
        raise ValueError("Exam phase must be 'pre' or 'post'.")
    ctx = load_quarantined_course_context(db, goal_id)
    fp = _clean_text(spec_fingerprint, 64) or ctx["spec_fingerprint"]

    items_source = raw_items
    used_model = _clean_text(model, 120) or None
    if (not items_source) and use_deterministic_fallback:
        items_source = build_deterministic_exam_items(ctx, clean_phase, num_items=num_items)
        used_model = used_model or "deterministic"

    cleaned_items, rubric_key = validate_exam_items(items_source or [])

    max_ver = db.scalar(
        select(func.max(BlindExam.version)).where(BlindExam.goal_id == goal_id, BlindExam.phase == clean_phase)
    )
    next_ver = int(max_ver or 0) + 1
    exam = BlindExam(
        goal_id=goal_id,
        phase=clean_phase,
        version=next_ver,
        spec_fingerprint=fp,
        items=cleaned_items,
        rubric_key=rubric_key,
        model=used_model,
    )
    db.add(exam)
    db.flush()
    return public_exam_out(exam, course_title=ctx["title"])


def _grade_deterministic_transfer(answer: str, key_points: list[str], rubric_key: str) -> tuple[int, str]:
    """Conservative deterministic fallback (0..2) when LLM transfer grader is unavailable."""
    ans_tokens = _word_tokens(answer)
    if len(ans_tokens) < 3:
        return 0, "Answer was too brief to demonstrate the principle."
    targets = [kp for kp in key_points if kp.strip()] or ([rubric_key] if rubric_key.strip() else [])
    if not targets:
        return 1, "Recorded substantive response."
    hit_ratios: list[float] = []
    for kp in targets:
        kp_tokens = _word_tokens(kp)
        if not kp_tokens:
            continue
        hit_ratios.append(len(ans_tokens & kp_tokens) / len(kp_tokens))
    best = max(hit_ratios) if hit_ratios else 0.0
    avg = (sum(hit_ratios) / len(hit_ratios)) if hit_ratios else 0.0
    if best >= 0.45 or avg >= 0.35:
        return 2, "Covered the core reasoning clearly."
    if best >= 0.20 or len(ans_tokens) >= 8:
        return 1, "Partially addressed the principle; key detail could be sharper."
    return 0, "Did not match the target explanation."


def build_transfer_grade_bundle(exam: BlindExam, answers: dict[str, str]) -> dict:
    """Build a single rubric-grading prompt + schema for all short_transfer items on an exam."""
    ans_map = {str(k): _clean_text(v, 1500) for k, v in (answers or {}).items()}
    transfer_items = [
        item
        for item in (exam.items if isinstance(exam.items, list) else [])
        if isinstance(item, dict) and item.get("kind") == "short_transfer"
    ]
    if not transfer_items:
        return {"has_transfer_items": False, "item_ids": []}

    item_ids = [str(item["id"]) for item in transfer_items]
    sections: list[str] = [
        "Grade each short transfer answer strictly against its frozen rubric key on an integer 0–2 scale:",
        "- 0 = incorrect, blank, off-topic, or repeats a misconception",
        "- 1 = partially right (touches part of the mechanism or misses key reasoning)",
        "- 2 = accurate, clear transfer explanation covering the key points in own words",
    ]
    for item in transfer_items:
        iid = str(item["id"])
        kps = item.get("key_points") if isinstance(item.get("key_points"), list) else []
        sections.append(
            "\n".join(
                [
                    f"### Item {iid}",
                    f"Question: {item.get('prompt')}",
                    f"Frozen rubric key: {item.get('rubric_key')}",
                    f"Key points: {'; '.join(str(k) for k in kps)}",
                    f"Learner answer: {ans_map.get(iid) or '(blank)'}",
                ]
            )
        )

    response_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "grades": {
                "type": "array",
                "minItems": len(item_ids),
                "maxItems": len(item_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "item_id": {"type": "string", "enum": item_ids},
                        "points": {"type": "integer", "minimum": 0, "maximum": TRANSFER_MAX_POINTS},
                        "feedback": {"type": "string"},
                    },
                    "required": ["item_id", "points", "feedback"],
                },
            }
        },
        "required": ["grades"],
    }

    return {
        "has_transfer_items": True,
        "exam_id": str(exam.id),
        "item_ids": item_ids,
        "system_prompt": (
            "You are a calm, strict educational grader scoring short transfer responses strictly against "
            "a frozen rubric key (0, 1, or 2 points). Return valid JSON matching the schema."
        ),
        "user_prompt": "\n\n".join(sections),
        "response_schema": response_schema,
        "temperature": 0.0,
    }


def build_epistemic_agent_bundle(exam: BlindExam, tutor_messages: list[str], *, course_title: str = "") -> dict:
    """Prompt bundle for a blank-slate epistemic-sandbox exam agent restricted strictly to tutor_messages."""
    safe = public_exam_out(exam, course_title=course_title)
    clean_msgs = [_clean_text(m, 1200) for m in (tutor_messages or []) if _clean_text(m, 1200)]
    transcript_block = "\n\n".join(f"Tutor message {i + 1}: {msg}" for i, msg in enumerate(clean_msgs)) or "(no tutor messages)"

    item_ids: list[str] = []
    q_blocks: list[str] = []
    for item in safe["items"]:
        iid = item["id"]
        item_ids.append(iid)
        if item["choices"]:
            ch_text = "\n".join(f"  {c['id']}) {c['text']}" for c in item["choices"])
            q_blocks.append(f"[{iid}] ({item['kind']}) {item['prompt']}\n{ch_text}\n  Answer with choice id (a/b/c/d) or 'unknown'.")
        else:
            q_blocks.append(f"[{iid}] (short_transfer) {item['prompt']}\n  Answer in 1–3 sentences using ONLY what the tutor taught, or 'unknown'.")

    response_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "answers": {
                "type": "array",
                "minItems": len(item_ids),
                "maxItems": len(item_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "item_id": {"type": "string", "enum": item_ids},
                        "answer": {"type": "string"},
                    },
                    "required": ["item_id", "answer"],
                },
            }
        },
        "required": ["answers"],
    }

    return {
        "exam_id": str(exam.id),
        "item_ids": item_ids,
        "system_prompt": (
            "You are a blank-slate learner taking a blind post-test. You know NOTHING about this topic "
            "except what is explicitly stated in the Tutor Messages below. Do not use outside knowledge. "
            "If the tutor never taught what is needed to answer an item, answer 'unknown'."
        ),
        "user_prompt": (
            f"=== TUTOR MESSAGES ONLY ===\n{transcript_block}\n\n"
            f"=== BLIND POST-TEST ITEMS ===\n" + "\n\n".join(q_blocks)
        ),
        "response_schema": response_schema,
        "temperature": 0.0,
    }


def _attempt_out(attempt: BlindExamAttempt) -> dict:
    return {
        "id": str(attempt.id),
        "exam_id": str(attempt.exam_id),
        "goal_id": str(attempt.goal_id),
        "student_id": str(attempt.student_id) if attempt.student_id else None,
        "harness_chat_id": str(attempt.harness_chat_id) if attempt.harness_chat_id else None,
        "phase": attempt.phase,
        "mode": attempt.mode,
        "status": attempt.status,
        "raw_score": attempt.raw_score,
        "mcq_score": attempt.mcq_score,
        "transfer_score": attempt.transfer_score,
        "paired_pre_attempt_id": str(attempt.paired_pre_attempt_id) if attempt.paired_pre_attempt_id else None,
        "paired_pre_score": attempt.paired_pre_score,
        "hake_g": attempt.hake_g,
        "item_grades": list(attempt.item_grades or []),
        "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
    }


def grade_and_record_attempt(
    db: Session,
    *,
    exam: BlindExam,
    answers: dict[str, str],
    transfer_grades: list[dict] | None = None,
    student_id: uuid.UUID | None = None,
    mode: str = "human",
    harness_chat_id: uuid.UUID | None = None,
) -> dict:
    """Deterministically grade MCQs/traps, merge validated transfer grades, compute Hake gain, and persist."""
    clean_mode = str(mode or "human").strip().lower()
    if clean_mode not in VALID_MODES:
        raise ValueError("Attempt mode must be 'human' or 'epistemic_sandbox'.")

    if student_id is not None:
        student = db.get(Student, student_id)
        if student is None:
            raise ValueError("Student not found.")
        # Never allow test/harness students to record human learner attempts.
        if clean_mode == "human" and bool(getattr(student, "is_test", False)):
            clean_mode = "epistemic_sandbox"

    ans_map = {str(k): _clean_text(v, 1500) for k, v in (answers or {}).items()}
    llm_grades_by_id: dict[str, dict] = {}
    for row in transfer_grades or []:
        if not isinstance(row, dict):
            continue
        iid = _clean_text(row.get("item_id"), 64)
        pts = row.get("points")
        if iid and not isinstance(pts, bool) and isinstance(pts, int) and 0 <= pts <= TRANSFER_MAX_POINTS:
            llm_grades_by_id[iid] = {
                "points": pts,
                "feedback": _clean_text(row.get("feedback"), 300),
            }

    mcq_earned = 0.0
    mcq_possible = 0.0
    transfer_earned = 0.0
    transfer_possible = 0.0
    item_grades: list[dict] = []

    for item in exam.items if isinstance(exam.items, list) else []:
        if not isinstance(item, dict):
            continue
        iid = str(item.get("id") or "")
        kind = str(item.get("kind") or "")
        given = ans_map.get(iid, "")

        if kind in {"scenario_mcq", "misconception_trap"}:
            correct_id = str(item.get("correct_choice_id") or "").strip().lower()
            is_correct = bool(given) and given.strip().lower() == correct_id
            earned = 1.0 if is_correct else 0.0
            mcq_earned += earned
            mcq_possible += 1.0
            item_grades.append(
                {
                    "item_id": iid,
                    "kind": kind,
                    "skill": str(item.get("skill") or ""),
                    "earned": earned,
                    "possible": 1.0,
                    "correct": is_correct,
                    "feedback": "Correct." if is_correct else (str(item.get("trap_rationale") or "") or "Not quite."),
                    "graded_by": "deterministic",
                }
            )
        elif kind == "short_transfer":
            max_pts = float(item.get("max_points") or TRANSFER_MAX_POINTS)
            transfer_possible += max_pts
            if iid in llm_grades_by_id:
                pts = float(llm_grades_by_id[iid]["points"])
                fb = llm_grades_by_id[iid]["feedback"]
                graded_by = "rubric_llm"
            else:
                kps = item.get("key_points") if isinstance(item.get("key_points"), list) else []
                pts_int, fb = _grade_deterministic_transfer(given, [str(k) for k in kps], str(item.get("rubric_key") or ""))
                pts = float(pts_int)
                graded_by = "deterministic_fallback"
            pts = max(0.0, min(max_pts, pts))
            transfer_earned += pts
            item_grades.append(
                {
                    "item_id": iid,
                    "kind": kind,
                    "skill": str(item.get("skill") or ""),
                    "earned": pts,
                    "possible": max_pts,
                    "correct": pts >= max_pts,
                    "feedback": fb,
                    "graded_by": graded_by,
                }
            )

    total_possible = mcq_possible + transfer_possible
    raw_score = round((mcq_earned + transfer_earned) / total_possible, 4) if total_possible > 0 else 0.0
    mcq_score = round(mcq_earned / mcq_possible, 4) if mcq_possible > 0 else None
    transfer_score = round(transfer_earned / transfer_possible, 4) if transfer_possible > 0 else None

    paired_pre_id: uuid.UUID | None = None
    paired_pre_score: float | None = None
    hake_g: float | None = None
    if exam.phase == "post" and clean_mode == "human" and student_id is not None:
        pre_attempt = db.scalar(
            select(BlindExamAttempt)
            .where(
                BlindExamAttempt.student_id == student_id,
                BlindExamAttempt.goal_id == exam.goal_id,
                BlindExamAttempt.phase == "pre",
                BlindExamAttempt.mode == "human",
                BlindExamAttempt.status == "graded",
                BlindExamAttempt.raw_score.is_not(None),
            )
            .order_by(BlindExamAttempt.submitted_at.desc(), BlindExamAttempt.started_at.desc())
            .limit(1)
        )
        if pre_attempt is not None and pre_attempt.raw_score is not None:
            paired_pre_id = pre_attempt.id
            paired_pre_score = float(pre_attempt.raw_score)
            hake_g = compute_hake_gain(paired_pre_score, raw_score)

    now = _utcnow()
    attempt = BlindExamAttempt(
        exam_id=exam.id,
        goal_id=exam.goal_id,
        student_id=student_id,
        harness_chat_id=harness_chat_id,
        phase=exam.phase,
        mode=clean_mode,
        status="graded",
        answers=ans_map,
        item_grades=item_grades,
        raw_score=raw_score,
        mcq_score=mcq_score,
        transfer_score=transfer_score,
        paired_pre_attempt_id=paired_pre_id,
        paired_pre_score=paired_pre_score,
        hake_g=hake_g,
        started_at=now,
        submitted_at=now,
    )
    db.add(attempt)
    db.flush()
    return _attempt_out(attempt)


def course_exam_summary(
    db: Session,
    *,
    goal_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
    phase: str | None = None,
) -> dict:
    """Read-only summary of cached Pre/Post exams and latest student scores + Hake gain."""
    ctx = load_quarantined_course_context(db, goal_id)
    pre_exam = latest_exam_for_course(db, goal_id=goal_id, phase="pre", spec_fingerprint=ctx["spec_fingerprint"])
    post_exam = latest_exam_for_course(db, goal_id=goal_id, phase="post", spec_fingerprint=ctx["spec_fingerprint"])

    latest_pre: BlindExamAttempt | None = None
    latest_post: BlindExamAttempt | None = None
    if student_id is not None:
        latest_pre = db.scalar(
            select(BlindExamAttempt)
            .where(
                BlindExamAttempt.student_id == student_id,
                BlindExamAttempt.goal_id == goal_id,
                BlindExamAttempt.phase == "pre",
                BlindExamAttempt.mode == "human",
                BlindExamAttempt.status == "graded",
            )
            .order_by(BlindExamAttempt.submitted_at.desc(), BlindExamAttempt.started_at.desc())
            .limit(1)
        )
        latest_post = db.scalar(
            select(BlindExamAttempt)
            .where(
                BlindExamAttempt.student_id == student_id,
                BlindExamAttempt.goal_id == goal_id,
                BlindExamAttempt.phase == "post",
                BlindExamAttempt.mode == "human",
                BlindExamAttempt.status == "graded",
            )
            .order_by(BlindExamAttempt.submitted_at.desc(), BlindExamAttempt.started_at.desc())
            .limit(1)
        )

    active_exam = None
    clean_phase = str(phase or "").strip().lower()
    if clean_phase == "pre" and pre_exam is not None:
        active_exam = public_exam_out(pre_exam, course_title=ctx["title"])
    elif clean_phase == "post" and post_exam is not None:
        active_exam = public_exam_out(post_exam, course_title=ctx["title"])

    pre_score = latest_pre.raw_score if latest_pre is not None else None
    post_score = latest_post.raw_score if latest_post is not None else None
    hake_g = (
        latest_post.hake_g
        if (latest_post is not None and latest_post.hake_g is not None)
        else (compute_hake_gain(pre_score, post_score) if (pre_score is not None and post_score is not None) else None)
    )

    return {
        "goal_id": str(goal_id),
        "course_title": ctx["title"],
        "spec_fingerprint": ctx["spec_fingerprint"],
        "has_pre_exam": pre_exam is not None,
        "has_post_exam": post_exam is not None,
        "exam": active_exam,
        "pre_attempt": _attempt_out(latest_pre) if latest_pre is not None else None,
        "post_attempt": _attempt_out(latest_post) if latest_post is not None else None,
        "pre_score": pre_score,
        "post_score": post_score,
        "hake_g": hake_g,
    }
