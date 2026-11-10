"""Knowledge-component courses, drafts, and the kid tutor loop.

A studio chat can draft. Nothing from that chat is stored until push.
An edit replaces one component. Kid chat, the catalog, and CreateCourse
do not call this module.
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.engine.choices import (
    HUMOR_MODES,
    INTEREST_WEAVING_MODES,
    METAPHORS,
    PERSONAS,
    SIDEKICKS,
    VOCABULARY_REGISTERS,
    VOICES,
)
from app.kc_loop import resolve_block_turn
from app.kc_prompt import (
    AFFECTS,
    DECISIONS,
    build_kc_prompt,
    block_step_label,
    block_uses_choice_widget,
    compute_turn_kind,
    default_substep_for_block,
    format_active_substep_label,
    is_fragment,
    labeled_choice,
    max_retries_for_block,
    on_screen_choice,
    stored_blocks,
    substeps_for_block,
    topic_goal,
)
from app.tutor_profile import (
    BLOCK_CONFIG_SPECS,
    effective_kc_tutor_config,
    effective_voice_settings,
    load_profile,
)
from app.kc_syllabus import component_fields, planning_context
from app.models import (
    ALL_BLOCK_TYPES,
    KcCreatorMessage,
    KcEdge,
    KcGoal,
    KcMessage,
    KcModelPrompt,
    KcNode,
    KcSession,
    KcState,
    Student,
    effective_child_profile,
)
from app.present import student_out

logger = logging.getLogger(__name__)

AUDIENCES = ("6-8", "9-11", "12-14", "15-17")
KINDS = ("mastery", "time_boxed", "curiosity")
KC_TYPES = ("factual", "procedural", "conceptual", "causal", "synthesis")
TYPE_KEYS = {
    "factual": ("fact", "retrieval_question"),
    "procedural": ("steps", "blanked_step", "solo_problem", "solo_check"),
    "conceptual": ("case_a", "case_b", "prediction", "rule", "transfer_case"),
    "causal": ("decision_point", "flawed_claim", "causal_chain", "counterfactual"),
    "synthesis": ("mixes", "faulty_plan"),
}
FINAL_STEP = {"factual": 0, "procedural": 2, "conceptual": 2, "causal": 2, "synthesis": 0}
ENCOMPASS_WEIGHT = 0.25
CARD_LABELS = {
    "fastest": "Fastest path",
    "patch": "Foundation patch",
    "stretch": "Stretch",
}
# Balances a later admin page can change. They stay in this module until that page exists.
OPEN_ANSWER_MIN = 2
PHRASE_WHOLE_WORD_MAX = 4
PHRASE_CONTAINED_MIN = 8
PHRASE_NUMBER_MAX_WORDS = 8
PHRASE_WORD_FLOOR = 3
PHRASE_ALL_WORDS_MIN = 3
PHRASE_SHARE = 0.6
NEGATION_WORDS = ("not", "never", "no", "isnt", "doesnt", "dont", "cannot", "cant")
KNOWN_STABILITY = 1.0
PASS_SCORE = 100
MISS_SCORE = 0
CARD_LIMIT = 3
SYNTHESIS_CONCEPTUAL_MIN = 2
BLANK_MARKER = "___"
EMPTY_FACT_QUESTION = "What is the fact?"
WORKED_LEAD = "Here is the worked example."
WORKED_ASK = "What did this example do?"
FADED_ASK = "Fill the blank step."
EMPTY_SOLO = "Solve it on your own."
CONTRAST_LEAD = "Look at the contrast."
CONTRAST_ASK = "What is different?"
RULE_ASK = "State the rule."
STAKE_ASK = "What is at stake?"
CLAIM_LEAD = "Mark this claim:"
DEFEND_ASK = "Defend the causal chain."
CAUSAL_PASS_PHRASES = ("wrong", "flawed", "false", "not true", "no")
CAUSAL_MARK_LABEL = "This claim is flawed"
CAUSAL_HOLD_LABEL = "This claim holds"
MIX_JOINER = " and "
EMPTY_MIX = "two earlier components"
ROOKIE_LEAD = "A rookie mixes"
ROOKIE_SAYS = "and says:"
ROOKIE_ASK = "Correct the plan."
FACTUAL_PASS = "Yes. {body}"
SYNTHESIS_PASS = "Yes. The plan that holds is: {body}"
OTHER_PASS = "That holds. {body}"
MISS_REPLY = "Not yet. {truth} That explanation is the one retry. Answer this same step again."
MISCONCEPTION_TAIL = "The next card opens that component."
SAVED_NOTE = "The draft was saved."
FIELD_LABELS = {
    "fact": "Fact",
    "retrieval_question": "Retrieval question",
    "steps": "Worked steps",
    "blanked_step": "Blanked step",
    "solo_problem": "Solo problem",
    "solo_check": "Solo check",
    "case_a": "Case one",
    "case_b": "Case two",
    "prediction": "Prediction",
    "rule": "Rule",
    "decision_point": "Decision point",
    "flawed_claim": "Flawed claim",
    "causal_chain": "Causal chain",
    "mixes": "Mixes",
    "faulty_plan": "Rookie's faulty plan",
    "transfer_case": "Transfer case",
    "counterfactual": "Counterfactual",
}
_EXPLICIT_TYPES = {
    "factual": "factual",
    "procedural": "procedural",
    "conceptual": "conceptual",
    "conceptual principle": "conceptual",
    "causal": "causal",
    "causal or historical": "causal",
    "synthesis": "synthesis",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def slug_code(title: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "component"
    code = base
    number = 2
    while code in taken:
        suffix = f"-{number}"
        code = f"{base[: 40 - len(suffix)]}{suffix}"
        number += 1
    return code


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _negated(text: str) -> bool:
    pattern = "|".join(re.escape(word) for word in NEGATION_WORDS)
    return bool(re.search(rf"\b({pattern})\b", text))


def matches_phrase(answer: str, phrase: str) -> bool:
    normalized_answer = _norm(answer)
    normalized_phrase = _norm(phrase)
    if not normalized_answer or not normalized_phrase:
        return False
    if len(normalized_phrase) <= PHRASE_WHOLE_WORD_MAX:
        return bool(re.search(rf"\b{re.escape(normalized_phrase)}\b", normalized_answer))
    if normalized_phrase in normalized_answer:
        return True
    if len(normalized_answer) >= PHRASE_CONTAINED_MIN and normalized_answer in normalized_phrase:
        return True
    phrase_numbers = re.findall(r"\d+", normalized_phrase)
    answer_numbers = re.findall(r"\d+", normalized_answer)
    if (
        phrase_numbers
        and set(phrase_numbers) <= set(answer_numbers)
        and len(normalized_answer.split()) <= PHRASE_NUMBER_MAX_WORDS
    ):
        return True
    answer_words = [word for word in normalized_answer.split() if len(word) > PHRASE_WORD_FLOOR]
    if len(answer_words) >= PHRASE_ALL_WORDS_MIN and all(word in normalized_phrase for word in answer_words):
        return True
    phrase_words = [word for word in normalized_phrase.split() if len(word) > PHRASE_WORD_FLOOR]
    if not phrase_words:
        return False
    hits = sum(1 for word in phrase_words if word in normalized_answer)
    return hits >= max(1, math.ceil(PHRASE_SHARE * len(phrase_words)))


def matches_wrong(answer: str, wrong_move: str) -> bool:
    normalized_answer = _norm(answer)
    wrong = _norm(wrong_move)
    if not normalized_answer or not wrong:
        return False
    if _negated(normalized_answer) and not _negated(wrong):
        return False
    if wrong in normalized_answer:
        return True
    words = wrong.split()
    if len(words) < 2:
        return False
    position = 0
    for word in words:
        found = normalized_answer.find(word, position)
        if found < 0:
            return False
        position = found + len(word)
    return True


def _clean_codes(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    codes: list[str] = []
    for item in values:
        code = str(item).strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def _clean_rubric(values: object) -> list[str]:
    if not isinstance(values, list):
        raise HTTPException(status_code=422, detail="Rubric checks are a list.")
    checks = [str(item).strip() for item in values if str(item).strip()]
    if len(checks) > 16:
        raise HTTPException(status_code=422, detail="A component has at most sixteen rubric checks.")
    return checks


def _clean_misconceptions(values: object) -> list[dict]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise HTTPException(status_code=422, detail="Misconceptions are a list.")
    signatures = []
    for item in values:
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail="A misconception needs a wrong move and a component.")
        wrong = str(item.get("wrong_move") or "").strip()
        broken = str(item.get("broken_kc") or "").strip()
        if not wrong and not broken:
            continue
        if not wrong:
            raise HTTPException(
                status_code=422,
                detail="A misconception needs a wrong move and the component that is broken.",
            )
        signatures.append({"wrong_move": wrong, "broken_kc": broken})
    return signatures


def _clean_type_fields(kc_type: str, raw: object) -> dict:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="Type fields have to match the component type.")
    keys = TYPE_KEYS[kc_type]
    fields: dict = {}
    for key in keys:
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if key in ("steps", "mixes"):
            if not isinstance(value, list):
                raise HTTPException(status_code=422, detail=f"{key} is a list.")
            fields[key] = [str(item).strip() for item in value if str(item).strip()]
        elif key == "blanked_step":
            try:
                fields[key] = int(value)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail="The blanked step is a number.") from exc
        else:
            fields[key] = str(value).strip()
    return fields


def _course_or_404(db: Session, course_id: uuid.UUID) -> KcGoal:
    goal = db.get(KcGoal, course_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="That course is not in the studio.")
    return goal


def _node_or_404(db: Session, node_id: uuid.UUID) -> KcNode:
    node = db.get(KcNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="That component is not on file.")
    return node


def _student_or_404(db: Session, student_id: uuid.UUID) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="That child is not on the roster.")
    return student


def _nodes_by_code(db: Session) -> dict[str, KcNode]:
    return {node.code: node for node in db.scalars(select(KcNode))}


def _target_ids(goal: KcGoal) -> list[str]:
    return [str(item) for item in (goal.target_kc_ids or [])]


def load_targets(db: Session, goal: KcGoal) -> list[KcNode]:
    nodes = []
    for item in _target_ids(goal):
        node = db.get(KcNode, _uuid(item))
        if node is not None:
            nodes.append(node)
    return nodes


def _referenced_codes(nodes: list[KcNode]) -> set[str]:
    codes: set[str] = set()
    for node in nodes:
        codes.update(_clean_codes(node.prerequisite_codes))
        codes.update(_clean_codes(node.encompasses_codes))
        for item in node.misconceptions or []:
            if isinstance(item, dict) and item.get("broken_kc"):
                codes.add(str(item["broken_kc"]))
        mixes = (node.type_fields or {}).get("mixes") or []
        if isinstance(mixes, list):
            codes.update(str(item) for item in mixes if str(item).strip())
    return codes


def load_patches(db: Session, targets: list[KcNode]) -> list[KcNode]:
    target_ids = {node.id for node in targets}
    by_code = _nodes_by_code(db)
    patches: list[KcNode] = []
    seen: set[uuid.UUID] = set()
    for code in _referenced_codes(targets):
        node = by_code.get(code)
        if node is None or node.id in target_ids or node.id in seen:
            continue
        seen.add(node.id)
        patches.append(node)
    if target_ids:
        edge_ids = set()
        edges = db.scalars(
            select(KcEdge).where(or_(KcEdge.from_kc.in_(target_ids), KcEdge.to_kc.in_(target_ids)))
        )
        for edge in edges:
            edge_ids.add(edge.from_kc)
            edge_ids.add(edge.to_kc)
        for node_id in edge_ids:
            if node_id in target_ids or node_id in seen:
                continue
            node = db.get(KcNode, node_id)
            if node is None:
                continue
            seen.add(node.id)
            patches.append(node)
    return patches


def _block_summary(blocks: list[dict]) -> str:
    from app.kc_model import block_summary_label

    return block_summary_label(blocks)


_BANNER_LABELS = {
    "topic_goal": "Topic + Goal",
    "mcq": "Multiple choice",
    "case_study": "Case study",
    "socratic": "Socratic",
    "curiosity": "Curiosity",
    "worked_example": "Worked example",
    "spot_the_flaw": "Spot the flaw",
    "teach_back": "Teach back",
    "retrieval_check": "Retrieval check",
}


def _public_blocks(node: KcNode | None) -> list[dict]:
    if node is None:
        return []
    blocks: list[dict] = []
    for item in node.blocks or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "")
        if kind not in ALL_BLOCK_TYPES:
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        blocks.append({"id": str(item.get("id") or ""), "type": kind, "data": dict(data)})
    return blocks


def _block_title(data: dict, fallback: str) -> str:
    for key in (
        "topic",
        "question_stem",
        "target_skill",
        "case_a",
        "central_dilemma",
        "phenomenon_hook",
        "problem_statement",
        "rookie_work",
        "peer_persona_prompt",
        "recall_prompt",
        "goal",
    ):
        text = str(data.get(key) or "").strip()
        if text:
            return text
    return fallback


def _summary(node: KcNode, *, target: bool) -> dict:
    return {
        "id": str(node.id),
        "code": node.code,
        "title": node.title,
        "kc_type": node.kc_type,
        "target": target,
    }


def _detail(node: KcNode, *, target: bool, codes: set[str]) -> dict:
    from app.kc_model import clean_pairs

    body = _summary(node, target=target)
    body.update(
        {
            "description": node.description or "",
            "outline": node.outline or "",
            "topics": clean_pairs(node.topics),
            "core_truth": node.core_truth or "",
            "rubric": list(node.rubric or []),
            "misconceptions": list(node.misconceptions or []),
            "prerequisite_codes": list(node.prerequisite_codes or []),
            "encompasses_codes": list(node.encompasses_codes or []),
            "type_fields": dict(node.type_fields or {}),
            "blocks": _public_blocks(node),
            "marked_complete": bool(node.marked_complete),
            "missing": gaps_for(node, codes),
            "history": node.history or "",
        }
    )
    return body


def node_out(db: Session, node: KcNode, *, target: bool = True) -> dict:
    return _detail(node, target=target, codes=set(_nodes_by_code(db)))


def course_out(db: Session, goal: KcGoal) -> dict:
    targets = load_targets(db, goal)
    patches = load_patches(db, targets)
    codes = set(_nodes_by_code(db))
    return {
        "id": str(goal.id),
        "code": goal.code,
        "title": goal.title,
        "description": goal.description or "",
        "audience": goal.audience,
        "kind": goal.kind,
        "minutes": goal.minutes,
        "allowed_block_types": list(goal.allowed_block_types or []),
        "ready": goal.ready,
        "history": goal.history or "",
        "updated_at": goal.updated_at.isoformat(),
        "components": [_detail(node, target=True, codes=codes) for node in targets],
        "patches": [_detail(node, target=False, codes=codes) for node in patches],
    }


def _has_text(value: object) -> bool:
    return bool(str(value or "").strip())


def _block_field_gaps(blocks: list[dict]) -> list[str]:
    """Readiness gaps for ordered blocks. Topic and goal live on a topic_goal block."""
    if not blocks:
        return ["no blocks"]
    gaps: list[str] = []
    for index, block in enumerate(blocks, start=1):
        kind = str(block.get("type") or "")
        data = block.get("data") if isinstance(block.get("data"), dict) else {}
        missing = _missing_block_fields(kind, data)
        if missing:
            gaps.append(f"block {index} {missing}")
    return gaps


def _filled_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if _has_text(item)]


def _missing_block_fields(kind: str, data: dict) -> str:
    """Catalog readiness. Only the field catalog keys count."""

    def text(key: str) -> bool:
        return _has_text(data.get(key))

    if kind == "topic_goal":
        if text("topic") and text("goal"):
            return ""
        return "needs a topic and a goal"
    if kind == "mcq":
        mode = str(data.get("mode") or "static").strip()
        if mode == "dynamic":
            if text("target_skill") and text("distractor_guidance"):
                return ""
            return "needs a target skill and distractor guidance"
        choices = data.get("choices") if isinstance(data.get("choices"), list) else []
        filled = [item for item in choices if isinstance(item, dict) and _has_text(item.get("text"))]
        correct = [item for item in filled if item.get("is_correct") is True]
        if text("question_stem") and len(filled) >= 2 and len(correct) == 1:
            return ""
        return "needs a question and at least two choices"
    if kind == "case_study":
        ready = text("case_a") and text("case_b") and text("prediction_prompt") and text("invariant_principle")
        if ready and text("transfer_prompt") and not text("transfer_expected"):
            return "needs the expected transfer"
        if ready:
            return ""
        return "needs both cases and the principle"
    if kind == "socratic":
        counters = _filled_strings(data.get("counterexamples"))
        if text("central_dilemma") and text("initial_probe") and counters and text("target_synthesis"):
            return ""
        return "needs a dilemma and a target synthesis"
    if kind == "curiosity":
        if text("phenomenon_hook") and text("prediction_question") and text("bridge_to_unit"):
            return ""
        return "needs a hook, a prediction, and a bridge"
    if kind == "worked_example":
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        filled_steps = [
            item for item in steps if isinstance(item, dict) and _has_text(item.get("step_text"))
        ]
        index = data.get("faded_step_index")
        index_ok = index is None or index == "" or (
            isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(steps)
        )
        if (
            text("problem_statement")
            and len(filled_steps) >= 2
            and index_ok
            and text("solo_problem")
            and text("solo_expected_answer")
        ):
            return ""
        return "needs a worked problem, steps, and a solo check"
    if kind == "spot_the_flaw":
        if (
            text("rookie_work")
            and text("flaw_description")
            and text("underlying_misconception")
            and text("corrected_version")
        ):
            return ""
        return "needs the flaw and the correction"
    if kind == "teach_back":
        concepts = _filled_strings(data.get("required_concepts"))
        if text("peer_persona_prompt") and 1 <= len(concepts) <= 4 and text("peer_follow_up_question"):
            return ""
        return "needs a prompt and the concepts to include"
    if kind == "retrieval_check":
        if (
            text("recall_prompt")
            and text("expected_fact")
            and text("elaborative_why_prompt")
            and text("expected_why_rationale")
        ):
            return ""
        return "needs a recall prompt and the expected fact"
    return ""


def gaps_for(node: KcNode, codes: set[str]) -> list[str]:
    missing: list[str] = []
    if not (node.outline or "").strip():
        missing.append("no outline")
    if not (node.core_truth or "").strip():
        missing.append("no truth")
    missing.extend(_block_field_gaps(_authored_blocks(node.blocks)))
    if any(code not in codes for code in _clean_codes(node.prerequisite_codes)):
        missing.append("a prerequisite that does not exist")
    if any(code not in codes for code in _clean_codes(node.encompasses_codes)):
        missing.append("an encompasses edge that does not exist")
    return missing


def readiness_problems(db: Session, goal: KcGoal) -> list[str]:
    targets = load_targets(db, goal)
    if not targets:
        return ["The course has no components."]
    codes = set(_nodes_by_code(db))
    problems = []
    for node in targets:
        for gap in gaps_for(node, codes):
            problems.append(f"{node.title}: {gap}")
    return problems


def _unready(db: Session, node_id: uuid.UUID) -> None:
    for goal in db.scalars(select(KcGoal)):
        if str(node_id) in _target_ids(goal) and goal.ready:
            goal.ready = False
            goal.updated_at = _now()


def _validate_course_fields(
    *,
    title: str,
    audience: str,
    kind: str,
    minutes: int | None,
) -> None:
    if not title.strip():
        raise HTTPException(status_code=422, detail="Name the course.")
    if audience not in AUDIENCES:
        raise HTTPException(status_code=422, detail="Audience is 6-8, 9-11, 12-14, or 15-17.")
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail="Kind is mastery, time_boxed, or curiosity.")
    if minutes is not None and minutes <= 0:
        raise HTTPException(status_code=422, detail="Minutes are a positive number or left blank.")


def create_course(
    db: Session,
    *,
    title: str,
    description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    code: str | None,
    allowed_block_types: list[str] | None = None,
) -> KcGoal:
    from app.kc_model import clean_allowed_block_types

    _validate_course_fields(title=title, audience=audience, kind=kind, minutes=minutes)
    taken = set(_nodes_by_code(db)) | {goal.code for goal in db.scalars(select(KcGoal))}
    chosen = (code or "").strip() or slug_code(title, taken)
    if db.scalar(select(KcGoal).where(KcGoal.code == chosen)) is not None:
        raise HTTPException(status_code=409, detail="A course already uses that code.")
    goal = KcGoal(
        code=chosen,
        title=title.strip(),
        description=(description or "").strip(),
        audience=audience,
        kind=kind,
        minutes=minutes,
        target_kc_ids=[],
        ready=False,
        allowed_block_types=clean_allowed_block_types(allowed_block_types),
    )
    db.add(goal)
    db.flush()
    return goal


def update_course(db: Session, goal: KcGoal, body: dict) -> KcGoal:
    title = str(body.get("title", goal.title))
    audience = str(body.get("audience", goal.audience))
    kind = str(body.get("kind", goal.kind))
    if "minutes" in body:
        minutes = body["minutes"]
    else:
        minutes = goal.minutes
    _validate_course_fields(title=title, audience=audience, kind=kind, minutes=minutes)
    goal.title = title.strip()
    goal.description = str(body.get("description", goal.description) or "").strip()
    goal.audience = audience
    goal.kind = kind
    goal.minutes = minutes
    if "allowed_block_types" in body:
        from app.kc_model import clean_allowed_block_types

        goal.allowed_block_types = clean_allowed_block_types(body.get("allowed_block_types"))
    goal.updated_at = _now()
    db.flush()
    return goal


def draft_course(goal: KcGoal, message: str) -> dict:
    """Return a component list. This does not write."""
    try:
        ctx = planning_context(
            title=goal.title,
            description=goal.description,
            kind=goal.kind,
            minutes=goal.minutes,
            message=message or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    taken: set[str] = set()
    components = []
    for title in ctx["titles"]:
        code = slug_code(title, taken)
        taken.add(code)
        components.append(
            {
                "code": code,
                "title": title,
                **component_fields(str(ctx["subject"]), title, str(ctx["kind"])),
            }
        )
    return {
        "reply": ctx["reply"],
        "draft": {"kind": "course", "components": components},
    }


def finish_model_course(
    goal: KcGoal, message: str, proposal: dict, allowed_block_types: list[str] | None = None
) -> dict:
    """Shape a model object into a draft. This does not write."""
    from app.kc_model import assemble_course

    try:
        assembled = assemble_course(
            title=goal.title,
            description=goal.description or "",
            kind=goal.kind,
            minutes=goal.minutes,
            message=message or "",
            proposal=proposal,
            allowed_block_types=allowed_block_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    taken: set[str] = set()
    components = []
    for item in assembled["components"]:
        code = slug_code(str(item["title"]), taken)
        taken.add(code)
        components.append(
            {
                "code": code,
                "title": item["title"],
                "description": item.get("description") or "",
                "outline": item.get("outline") or "",
                "topics": item.get("topics") or [],
            }
        )
    return {
        "reply": assembled["reply"],
        "draft": {"kind": "course", "components": components},
    }


def course_prompt_for(
    goal: KcGoal, message: str, model: str, allowed_block_types: list[str] | None = None
) -> dict:
    from app.kc_model import course_bundle

    try:
        return course_bundle(
            title=goal.title,
            description=goal.description or "",
            audience=goal.audience,
            kind=goal.kind,
            minutes=goal.minutes,
            message=message or "",
            model=model,
            allowed_block_types=allowed_block_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def description_prompts_for(
    goal: KcGoal,
    message: str,
    model: str,
    titles: list[str],
    subject: str = "",
    major_ideas: list[str] | None = None,
    allowed_block_types: list[str] | None = None,
) -> dict:
    from app.kc_model import description_plan

    try:
        return description_plan(
            title=goal.title,
            description=goal.description or "",
            audience=goal.audience,
            kind=goal.kind,
            minutes=goal.minutes,
            message=message or "",
            model=model,
            titles=titles,
            subject=subject,
            major_ideas=major_ideas,
            allowed_block_types=allowed_block_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def push_course(db: Session, goal: KcGoal, components: list[dict]) -> KcGoal:
    if not components:
        raise HTTPException(status_code=422, detail="Push a list of components.")
    by_code = _nodes_by_code(db)
    on_course = set(_target_ids(goal))
    ordered: list[str] = []
    for item in components:
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail="Each component needs a title.")
        title = str(item.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail="Each component needs a title.")
        requested = str(item.get("code") or "").strip()
        code = requested or slug_code(title, set(by_code))
        node = by_code.get(code)
        if node is not None and str(node.id) not in on_course and (node.kc_type or (node.core_truth or "").strip()):
            code = slug_code(title, set(by_code))
            node = None
        description, outline, topics, write_fields = _course_topic_fields(item)
        if node is None:
            node = KcNode(
                code=code,
                title=title,
                description=description,
                outline=outline,
                topics=topics,
                blocks=_blocks_from_pairs(topics),
            )
            db.add(node)
            db.flush()
            by_code[code] = node
        else:
            node.title = title
            if description:
                node.description = description
            if write_fields:
                node.outline = outline
                node.topics = topics
            node.updated_at = _now()
        _ensure_topic_blocks(node)
        if str(node.id) not in ordered:
            ordered.append(str(node.id))
    goal.target_kc_ids = ordered
    goal.ready = False
    goal.updated_at = _now()
    db.flush()
    return goal


def add_component(db: Session, goal: KcGoal, title: str) -> KcNode:
    cleaned = title.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Name the component.")
    by_code = _nodes_by_code(db)
    node = KcNode(code=slug_code(cleaned, set(by_code)), title=cleaned)
    db.add(node)
    db.flush()
    goal.target_kc_ids = [*_target_ids(goal), str(node.id)]
    goal.ready = False
    goal.updated_at = _now()
    db.flush()
    return node


def rename_component(db: Session, node: KcNode, title: str) -> KcNode:
    cleaned = title.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Name the component.")
    node.title = cleaned
    node.updated_at = _now()
    db.flush()
    return node


def reorder_course(db: Session, goal: KcGoal, ids: list[str]) -> KcGoal:
    current = _target_ids(goal)
    if sorted(ids) != sorted(current) or len(ids) != len(current):
        raise HTTPException(status_code=422, detail="Reorder uses the components already on the course.")
    goal.target_kc_ids = list(ids)
    goal.updated_at = _now()
    db.flush()
    return goal


def delete_node(db: Session, node: KcNode) -> None:
    code = node.code
    for other in db.scalars(select(KcNode).where(KcNode.id != node.id)):
        prerequisites = [item for item in _clean_codes(other.prerequisite_codes) if item != code]
        encompasses = [item for item in _clean_codes(other.encompasses_codes) if item != code]
        if prerequisites != _clean_codes(other.prerequisite_codes) or encompasses != _clean_codes(other.encompasses_codes):
            other.prerequisite_codes = prerequisites
            other.encompasses_codes = encompasses
            other.updated_at = _now()
            _sync_edges(db, other)
    node_id = str(node.id)
    for goal in db.scalars(select(KcGoal)):
        remaining = [item for item in _target_ids(goal) if item != node_id]
        if remaining != _target_ids(goal):
            goal.target_kc_ids = remaining
            goal.ready = False
            goal.updated_at = _now()
    db.delete(node)
    db.flush()


def _check_delete_password(password: str) -> None:
    """The same password the quest-course delete page already uses."""
    import hmac

    from app.studio import DELETE_PASSWORD

    if not isinstance(password, str) or not hmac.compare_digest(password, DELETE_PASSWORD):
        raise HTTPException(status_code=422, detail="The password is wrong.")


def _ids_on_other_courses(db: Session, goal_id: uuid.UUID) -> set[uuid.UUID]:
    found: set[uuid.UUID] = set()
    for other in db.scalars(select(KcGoal).where(KcGoal.id != goal_id)):
        other_targets = load_targets(db, other)
        for node in other_targets + load_patches(db, other_targets):
            found.add(node.id)
    return found


def delete_kc_course(db: Session, goal: KcGoal, password: str) -> None:
    """Delete one KC course and the components that belong only to it."""
    _check_delete_password(password)
    targets = load_targets(db, goal)
    patches = load_patches(db, targets)
    keep = _ids_on_other_courses(db, goal.id)
    for node in [*targets, *patches]:
        if node.id not in keep:
            delete_node(db, node)
    db.delete(goal)
    db.flush()


def _sync_edges(db: Session, node: KcNode) -> None:
    db.execute(
        delete(KcEdge).where(
            or_(
                and_(KcEdge.to_kc == node.id, KcEdge.kind == "prerequisite_of"),
                and_(KcEdge.from_kc == node.id, KcEdge.kind == "encompasses"),
            )
        )
    )
    db.flush()
    by_code = _nodes_by_code(db)
    for code in _clean_codes(node.prerequisite_codes):
        other = by_code.get(code)
        if other is None or other.id == node.id:
            continue
        db.add(KcEdge(from_kc=other.id, to_kc=node.id, kind="prerequisite_of", weight=1))
    for code in _clean_codes(node.encompasses_codes):
        other = by_code.get(code)
        if other is None or other.id == node.id:
            continue
        db.add(
            KcEdge(from_kc=node.id, to_kc=other.id, kind="encompasses", weight=ENCOMPASS_WEIGHT)
        )
    db.flush()


def _authored_blocks(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    kept: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "") in ("", "_legacy"):
            continue
        kept.append(item)
    return kept


def _blocks_from_pairs(pairs: object) -> list[dict]:
    """Topic and goal are stored on a topic_goal block, not as a lesson field of their own."""
    from app.kc_model import clean_pairs

    blocks: list[dict] = []
    for index, item in enumerate(clean_pairs(pairs), start=1):
        blocks.append(
            {
                "id": f"blk_{index}",
                "type": "topic_goal",
                "data": {"topic": item["topic"], "goal": item["goal"]},
            }
        )
    return blocks


def _ensure_topic_blocks(node: KcNode) -> None:
    if _authored_blocks(node.blocks):
        return
    seeded = _blocks_from_pairs(node.topics)
    if seeded:
        node.blocks = seeded


def apply_component(db: Session, node: KcNode, body: dict) -> KcNode:
    """Replace this component and the edges it owns. Other components stay."""
    from app.kc_model import derive_rubric_from_blocks
    from app.models import ALL_BLOCK_TYPES

    real_blocks = [
        item for item in _authored_blocks(body.get("blocks")) if str(item.get("type") or "") in ALL_BLOCK_TYPES
    ]
    if not real_blocks:
        real_blocks = _blocks_from_pairs(body.get("topics"))
    if "title" in body and str(body.get("title") or "").strip():
        node.title = str(body["title"]).strip()
    _assign_topic_fields(node, body)
    if real_blocks:
        node.blocks = real_blocks
        node.rubric = _clean_rubric(derive_rubric_from_blocks(real_blocks))
    elif body.get("rubric") is not None:
        node.rubric = _clean_rubric(body.get("rubric") or [])
    node.core_truth = str(body.get("core_truth") or "").strip()
    node.misconceptions = _clean_misconceptions(body.get("misconceptions") or [])
    node.prerequisite_codes = _clean_codes(body.get("prerequisite_codes") or [])
    node.encompasses_codes = _clean_codes(body.get("encompasses_codes") or [])
    node.marked_complete = False
    node.updated_at = _now()
    _sync_edges(db, node)
    _unready(db, node.id)
    db.flush()
    return node


def _first_sentence(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    return re.split(r"(?<=[.])\s+", cleaned, maxsplit=1)[0].strip()


def draft_component(goal: KcGoal, node: KcNode, ordered: list[KcNode], message: str) -> dict:
    """Draft this component only. This does not write."""
    del message
    earlier = []
    for item in ordered:
        if item.id == node.id:
            break
        earlier.append(item)
    previous = earlier[-1] if earlier else None
    summary, outline, pairs = _topic_fields(goal, node)
    blocks = _authored_blocks(node.blocks) or _blocks_from_pairs(pairs)
    if not blocks:
        goal_text = _first_sentence(goal.description) or f"Explain {node.title}."
        blocks = [{"id": "blk_1", "type": "topic_goal", "data": {"topic": node.title, "goal": goal_text}}]
        pairs = [{"topic": node.title, "goal": goal_text}]
    truth = _first_sentence(goal.description) or f"The core idea of {node.title}."
    from app.kc_model import derive_rubric_from_blocks

    rubric = derive_rubric_from_blocks(blocks) or [f"States the idea of {node.title}"]
    draft = {
        "kind": "component",
        "id": str(node.id),
        "code": node.code,
        "title": node.title,
        "description": summary,
        "outline": outline,
        "topics": pairs,
        "blocks": blocks,
        "core_truth": truth,
        "rubric": rubric,
        "misconceptions": [],
        "prerequisite_codes": [previous.code] if previous else [],
        "encompasses_codes": [],
    }
    return {
        "reply": f"Draft for {node.title} only. Other components stay as they are. Nothing is saved until you push it.",
        "draft": draft,
    }


def structure(db: Session, goal: KcGoal) -> dict:
    targets = load_targets(db, goal)
    codes = set(_nodes_by_code(db))
    rows = []
    for position, node in enumerate(targets, start=1):
        blocks = _public_blocks(node)
        rows.append(
            {
                "id": str(node.id),
                "code": node.code,
                "title": node.title,
                "description": node.description or "",
                "blocks": blocks,
                "summary": _block_summary(blocks),
                "position": position,
                "missing": gaps_for(node, codes),
                "marked_complete": bool(node.marked_complete),
            }
        )
    return {"course_id": str(goal.id), "groups": [{"components": rows}] if rows else []}


def network(db: Session, goal: KcGoal) -> dict:
    targets = load_targets(db, goal)
    patches = load_patches(db, targets)
    shown = targets + patches
    target_ids = {node.id for node in targets}
    ids = [node.id for node in shown]
    edges = []
    if ids:
        for edge in db.scalars(select(KcEdge).where(KcEdge.from_kc.in_(ids), KcEdge.to_kc.in_(ids))):
            source = db.get(KcNode, edge.from_kc)
            dest = db.get(KcNode, edge.to_kc)
            if source is None or dest is None:
                continue
            edges.append({"from_code": source.code, "to_code": dest.code, "kind": edge.kind})
    return {
        "nodes": [
            _summary(node, target=node.id in target_ids) | {"patch": node.id not in target_ids}
            for node in shown
        ],
        "edges": edges,
    }


def mark_ready(db: Session, goal: KcGoal) -> KcGoal:
    problems = readiness_problems(db, goal)
    if problems:
        raise HTTPException(status_code=422, detail=problems)
    goal.ready = True
    goal.updated_at = _now()
    db.flush()
    return goal


def tutor_courses(db: Session) -> list[dict]:
    goals = db.scalars(select(KcGoal).where(KcGoal.ready.is_(True)).order_by(KcGoal.title))
    return [
        {
            "id": str(goal.id),
            "code": goal.code,
            "title": goal.title,
            "description": goal.description or "",
            "audience": goal.audience,
            "kind": goal.kind,
            "minutes": goal.minutes if goal.kind == "time_boxed" else None,
        }
        for goal in goals
    ]


def _state_map(db: Session, student_id: uuid.UUID, node_ids: list[uuid.UUID]) -> dict[uuid.UUID, KcState]:
    if not node_ids:
        return {}
    rows = db.scalars(
        select(KcState).where(KcState.student_id == student_id, KcState.kc_id.in_(node_ids))
    )
    return {row.kc_id: row for row in rows}


def _is_known(states: dict[uuid.UUID, KcState], node: KcNode) -> bool:
    row = states.get(node.id)
    return row is not None and row.status == "known"


def _is_settled(states: dict[uuid.UUID, KcState], node: KcNode) -> bool:
    """Known or fragile. Fragile stays fragile; it is still finished for the next course."""
    row = states.get(node.id)
    return row is not None and row.status in {"known", "fragile"}


def _ring_status(states: dict[uuid.UUID, KcState], node: KcNode) -> str:
    row = states.get(node.id)
    if row is None or row.status == "unknown":
        return "not_started"
    return row.status


def _percent(known: int, total: int) -> int:
    if total <= 0:
        return 0
    return (known * 100 + total // 2) // total


def _rubric_line(block: dict, cfg: dict) -> str:
    """One rubric line for this block. Curiosity adds none unless that block counts."""
    if not isinstance(block, dict):
        return ""
    kind = str(block.get("type") or "").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    if kind == "curiosity":
        curiosity = ((cfg or {}).get("blocks") or {}).get("curiosity") or {}
        if not bool(curiosity.get("counts_toward_mastery_score", False)):
            return ""
        return str(data.get("bridge_to_unit") or data.get("prediction_question") or "").strip()
    from app.kc_model import derive_rubric_from_blocks

    lines = derive_rubric_from_blocks([block])
    return lines[0] if lines else ""


def _stored_block_rows(
    node: KcNode, session: KcSession | None, cfg: dict, *, include_active: bool
) -> list[dict]:
    """Finished blocks, and the active block when the walk is still open. Empty fields stay off."""
    blocks = stored_blocks(node)
    results = session.block_results if session is not None and isinstance(session.block_results, list) else []
    by_id: dict[str, dict] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or item.get("block_id") or "").strip()
        if key:
            by_id[key] = item
    active_index = None
    if include_active and session is not None and blocks:
        active_index = min(max(int(session.step or 0), 0), len(blocks) - 1)
    rows: list[dict] = []
    for index, block in enumerate(blocks):
        key = _block_key(block, index)
        stored = by_id.get(key)
        finished = stored is not None
        active = active_index == index and not finished
        if not finished and not active:
            continue
        kind = str(block.get("type") or "").strip()
        row: dict = {
            "id": key,
            "type": kind,
            "type_label": _BANNER_LABELS.get(kind, kind or "Block"),
            "status": "completed" if finished else "active",
        }
        if stored is not None:
            outcome = str(stored.get("outcome") or "").strip()
            if outcome in {"passed", "revealed"}:
                row["outcome"] = outcome
            if stored.get("attempts") is not None:
                row["attempts"] = int(stored.get("attempts") or 0)
        line = _rubric_line(block, cfg)
        if line:
            row["rubric"] = line
        rows.append(row)
    return rows


def _next_ready_course(db: Session, goal: KcGoal) -> dict | None:
    ready = db.scalars(select(KcGoal).where(KcGoal.ready.is_(True)).order_by(KcGoal.title, KcGoal.code))
    seen = False
    for item in ready:
        if seen and item.id != goal.id:
            return {"id": str(item.id), "code": item.code, "title": item.title}
        if item.id == goal.id:
            seen = True
    return None


def _sessions_for(
    db: Session, student_id: uuid.UUID, goal_id: uuid.UUID, node_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[KcSession]]:
    if not node_ids:
        return {}
    grouped: dict[uuid.UUID, list[KcSession]] = {}
    rows = db.scalars(
        select(KcSession).where(
            KcSession.student_id == student_id,
            KcSession.goal_id == goal_id,
            KcSession.kc_id.in_(node_ids),
        )
    )
    for row in rows:
        grouped.setdefault(row.kc_id, []).append(row)
    return grouped


def _block_key(block: dict, index: int) -> str:
    return str(block.get("id") or f"blk_{index + 1}").strip() or f"blk_{index + 1}"


def _result_ids(results: object) -> set[str]:
    found: set[str] = set()
    if not isinstance(results, list):
        return found
    for item in results:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or item.get("block_id") or "").strip()
        if key:
            found.add(key)
    return found


def _last_block_finished(node: KcNode | None, session: KcSession) -> bool:
    blocks = stored_blocks(node)
    if not blocks:
        return False
    last = len(blocks) - 1
    return _block_key(blocks[last], last) in _result_ids(session.block_results)


def _walk_fragile(blocks: list[dict], results: object, cfg: dict) -> bool:
    """A required block was revealed or never passed. Curiosity counts only when that setting is on."""
    by_id: dict[str, dict] = {}
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                key = str(item.get("id") or item.get("block_id") or "").strip()
                if key:
                    by_id[key] = item
    counted = False
    fragile = False
    for index, block in enumerate(blocks):
        counts = True
        if str(block.get("type") or "").strip() == "curiosity":
            curiosity = ((cfg or {}).get("blocks") or {}).get("curiosity") or {}
            counts = bool(curiosity.get("counts_toward_mastery_score", False))
        if not counts:
            continue
        counted = True
        row = by_id.get(_block_key(block, index))
        if row is None or row.get("outcome") != "passed":
            fragile = True
    if not counted:
        return False
    return fragile


def _close_finished_walk(
    db: Session,
    session: KcSession,
    node: KcNode,
    reply: str = "",
    body: dict | None = None,
) -> None:
    """A finished block walk must not stay open. Known or fragile is written with the close."""
    if session.status == "completed":
        return
    blocks = stored_blocks(node)
    if not _last_block_finished(node, session):
        return
    cfg = effective_kc_tutor_config(load_profile(db))
    state = _get_state(db, session.student_id, node.id)
    if state.status not in {"known", "fragile"}:
        if _walk_fragile(blocks, session.block_results, cfg):
            _mark_fragile(db, session, node)
        else:
            _mark_known(db, session, node)
    session.status = "completed"
    session.updated_at = _now()
    _save_component_result(db, session, node, body or {}, reply)


def _unit_status(state: KcState | None, node: KcNode, sessions: list[KcSession]) -> str:
    """Finished work is completed. In progress is only an open session before the last block."""
    if state is not None and state.status in {"known", "fragile"}:
        return "completed"
    if any(row.status == "completed" for row in sessions):
        return "completed"
    if any(row.status == "in_progress" and _last_block_finished(node, row) for row in sessions):
        return "completed"
    if any(row.status == "in_progress" and not _last_block_finished(node, row) for row in sessions):
        return "in_progress"
    return "not_started"


def _count_session(node: KcNode, sessions: list[KcSession]) -> KcSession | None:
    unfinished = [
        row for row in sessions if row.status == "in_progress" and not _last_block_finished(node, row)
    ]
    chosen = unfinished or sessions
    if not chosen:
        return None
    return max(chosen, key=lambda row: row.updated_at or row.created_at or _now())


def _block_counts(node: KcNode, session: KcSession | None) -> tuple[int, int]:
    blocks = stored_blocks(node)
    if session is None:
        return 0, len(blocks)
    done_ids = _result_ids(session.block_results)
    done = sum(1 for index, block in enumerate(blocks) if _block_key(block, index) in done_ids)
    return done, len(blocks)


def _mastery_label(state: KcState | None, node: KcNode, sessions: list[KcSession], cfg: dict) -> str:
    if state is not None and state.status in {"known", "fragile"}:
        return state.status
    finished = [
        row
        for row in sessions
        if row.status == "completed" or (row.status == "in_progress" and _last_block_finished(node, row))
    ]
    if not finished:
        return ""
    latest = max(finished, key=lambda row: row.updated_at or row.created_at or _now())
    if not _result_ids(latest.block_results):
        return ""
    if _walk_fragile(stored_blocks(node), latest.block_results, cfg):
        return "fragile"
    return "known"


def _latest_redirect(db: Session, student_id: uuid.UUID, goal_id: uuid.UUID) -> KcNode | None:
    session = db.scalar(
        select(KcSession)
        .where(
            KcSession.student_id == student_id,
            KcSession.goal_id == goal_id,
            KcSession.redirect_kc_id.is_not(None),
        )
        .order_by(KcSession.updated_at.desc())
    )
    if session is None or session.redirect_kc_id is None:
        return None
    return db.get(KcNode, session.redirect_kc_id)


def progress(db: Session, goal: KcGoal, student: Student) -> dict:
    if not goal.ready:
        raise HTTPException(status_code=422, detail="This course is not ready.")
    targets = load_targets(db, goal)
    patches = load_patches(db, targets)
    by_code = {node.code: node for node in targets + patches}
    everyone = targets + patches
    target_ids = {node.id for node in targets}
    states = _state_map(db, student.id, [node.id for node in everyone])
    sessions = _sessions_for(db, student.id, goal.id, [node.id for node in everyone])
    cfg = effective_kc_tutor_config(load_profile(db))
    known = sum(1 for node in targets if _is_known(states, node))
    conceptual_known = sum(
        1 for node in targets if node.kc_type == "conceptual" and _is_known(states, node)
    )

    def prerequisites_ready(node: KcNode) -> bool:
        for code in _clean_codes(node.prerequisite_codes):
            other = by_code.get(code) or _nodes_by_code(db).get(code)
            if other is None or not _is_settled(states, other):
                return False
        return True

    def offered(node: KcNode) -> bool:
        if _is_settled(states, node):
            return False
        if not prerequisites_ready(node):
            return False
        if node.kc_type == "synthesis" and conceptual_known < SYNTHESIS_CONCEPTUAL_MIN:
            return False
        return True

    available = [node for node in targets if offered(node)]
    fastest = available[0] if available else None
    redirect = _latest_redirect(db, student.id, goal.id)
    patch = None
    if redirect is not None and not _is_known(states, redirect):
        patch = redirect
    else:
        for node in targets:
            if _is_known(states, node):
                continue
            for code in _clean_codes(node.prerequisite_codes):
                other = by_code.get(code)
                if other is None or other.id in {item.id for item in targets}:
                    continue
                if not _is_known(states, other):
                    patch = other
                    break
            if patch is not None:
                break
    stretch = None
    if fastest is not None:
        synthesis = next(
            (node for node in available if node.kc_type == "synthesis" and node.id != fastest.id),
            None,
        )
        if synthesis is not None:
            stretch = synthesis
        else:
            later = [node for node in available if node.id != fastest.id]
            stretch = later[-1] if later else None

    cards = []
    if fastest is not None:
        cards.append(
            {
                "role": "fastest",
                "label": CARD_LABELS["fastest"],
                "id": str(fastest.id),
                "code": fastest.code,
                "title": fastest.title,
                "kc_type": fastest.kc_type,
                "reason": "Prerequisites are finished, and this is the next component on the course.",
            }
        )
    if patch is not None and (fastest is None or patch.id != fastest.id):
        reason = "A foundation component that is not a target."
        if redirect is not None and patch.id == redirect.id:
            reason = "The last answer matched a misconception. This is the component that is actually broken."
        cards.append(
            {
                "role": "patch",
                "label": CARD_LABELS["patch"],
                "id": str(patch.id),
                "code": patch.code,
                "title": patch.title,
                "kc_type": patch.kc_type,
                "reason": reason,
            }
        )
    if stretch is not None:
        reason = "A later component whose prerequisites are finished."
        if stretch.kc_type == "synthesis":
            reason = (
                "A synthesis component. It waits until "
                f"{SYNTHESIS_CONCEPTUAL_MIN} conceptual components are known."
            )
        cards.append(
            {
                "role": "stretch",
                "label": CARD_LABELS["stretch"],
                "id": str(stretch.id),
                "code": stretch.code,
                "title": stretch.title,
                "kc_type": stretch.kc_type,
                "reason": reason,
            }
        )
    from app.kc_model import derive_rubric_from_blocks

    course_complete = bool(targets) and all(_is_settled(states, node) for node in targets)

    def unit_row(node: KcNode) -> dict:
        node_sessions = sessions.get(node.id, [])
        state = states.get(node.id)
        chosen = _count_session(node, node_sessions)
        done, total = _block_counts(node, chosen)
        status = _unit_status(state, node, node_sessions)
        return {
            "id": str(node.id),
            "code": node.code,
            "title": node.title,
            "kc_type": None,
            "summary": _block_summary(_public_blocks(node)),
            "patch": node.id not in target_ids,
            "status": status,
            "mastery": _mastery_label(state, node, node_sessions, cfg),
            "finished_blocks": done,
            "total_blocks": total,
            "blocks": _stored_block_rows(node, chosen, cfg, include_active=status == "in_progress"),
            "rubric": derive_rubric_from_blocks(stored_blocks(node)),
            "result": None if state is None else state.result,
        }

    return {
        "course_id": str(goal.id),
        "title": goal.title,
        "kind": goal.kind,
        "minutes": goal.minutes if goal.kind == "time_boxed" else None,
        "known": known,
        "total": len(targets),
        "percent": _percent(known, len(targets)),
        "count_label": f"{known} of {len(targets)}",
        "course_complete": course_complete,
        "next_course": _next_ready_course(db, goal) if course_complete else None,
        "units": [unit_row(node) for node in everyone],
        "ring": [
            {
                "id": str(node.id),
                "code": node.code,
                "title": node.title,
                "kc_type": node.kc_type,
                "status": _ring_status(states, node),
            }
            for node in targets
        ],
        "cards": cards[:CARD_LIMIT],
    }


def restart_course(db: Session, goal: KcGoal, student: Student) -> dict:
    """Clear this child's progress on the course so it can begin from the first component."""
    if not goal.ready:
        raise HTTPException(status_code=422, detail="This course is not ready.")
    targets = load_targets(db, goal)
    component_ids = [node.id for node in targets]
    if component_ids:
        db.execute(
            delete(KcState).where(
                KcState.student_id == student.id,
                KcState.kc_id.in_(component_ids),
            )
        )
    sessions = list(
        db.scalars(
            select(KcSession).where(
                KcSession.student_id == student.id,
                KcSession.goal_id == goal.id,
            )
        )
    )
    # An in-progress session would resume mid-component. Drop those, and drop leftover
    # redirects, so the next open starts at the first step of the first component.
    drop_ids = [row.id for row in sessions if row.status == "in_progress"]
    for row in sessions:
        if row.status != "in_progress" and row.redirect_kc_id is not None:
            row.redirect_kc_id = None
    if drop_ids:
        db.execute(delete(KcModelPrompt).where(KcModelPrompt.session_id.in_(drop_ids)))
        db.execute(delete(KcMessage).where(KcMessage.session_id.in_(drop_ids)))
        db.execute(delete(KcSession).where(KcSession.id.in_(drop_ids)))
    db.flush()
    db.expire_all()
    return progress(db, goal, student)


def _add_message(db: Session, session: KcSession, role: str, content: str) -> KcMessage:
    current = db.scalar(select(func.max(KcMessage.seq)).where(KcMessage.session_id == session.id)) or 0
    message = KcMessage(session_id=session.id, role=role, content=content, seq=int(current) + 1)
    db.add(message)
    db.flush()
    return message


def step_text(node: KcNode, step: int) -> str:
    fields = node.type_fields or {}
    kind = node.kc_type
    if kind == "factual":
        if step <= 0:
            return str(fields.get("retrieval_question") or EMPTY_FACT_QUESTION)
        return FACTUAL_PASS.format(body=fields.get("fact") or node.core_truth)
    if kind == "procedural":
        steps = [str(item) for item in (fields.get("steps") or [])]
        blank = int(fields.get("blanked_step") or 0)
        if step <= 0:
            lines = " ".join(f"{index + 1}. {text}" for index, text in enumerate(steps))
            return f"{WORKED_LEAD} {lines} {WORKED_ASK}"
        if step == 1:
            shown = []
            for index, text in enumerate(steps):
                shown.append(f"{index + 1}. {BLANK_MARKER}" if index == blank else f"{index + 1}. {text}")
            return f"{FADED_ASK} " + " ".join(shown)
        return str(fields.get("solo_problem") or EMPTY_SOLO)
    if kind == "conceptual":
        if step <= 0:
            return (
                f"Case one: {fields.get('case_a')} "
                f"Case two: {fields.get('case_b')} "
                f"{fields.get('prediction')}"
            )
        if step == 1:
            return (
                f"{CONTRAST_LEAD} Case one: {fields.get('case_a')} "
                f"Case two: {fields.get('case_b')} {CONTRAST_ASK}"
            )
        return RULE_ASK
    if kind == "causal":
        if step <= 0:
            return f"Decision point: {fields.get('decision_point')} {STAKE_ASK}"
        if step == 1:
            return f"{CLAIM_LEAD} {fields.get('flawed_claim')}"
        return DEFEND_ASK
    if kind == "synthesis":
        mixes = fields.get("mixes") or []
        joined = MIX_JOINER.join(str(item) for item in mixes) or EMPTY_MIX
        if step <= 0:
            return f"{ROOKIE_LEAD} {joined} {ROOKIE_SAYS} {fields.get('faulty_plan')} {ROOKIE_ASK}"
        return SYNTHESIS_PASS.format(body=node.core_truth)
    return node.core_truth or node.title


def _expects(node: KcNode, step: int) -> list[str] | None:
    fields = node.type_fields or {}
    kind = node.kc_type
    if kind == "factual" and step == 0:
        return [str(fields.get("fact") or node.core_truth)]
    if kind == "procedural":
        if step == 0:
            return None
        if step == 1:
            steps = list(fields.get("steps") or [])
            index = int(fields.get("blanked_step") or 0)
            if 0 <= index < len(steps):
                return [str(steps[index])]
            return []
        if step == 2:
            return [str(fields.get("solo_check") or node.core_truth)]
    if kind == "conceptual":
        if step < 2:
            return None
        return [str(fields.get("rule") or node.core_truth)]
    if kind == "causal":
        if step == 0:
            return None
        if step == 1:
            return list(CAUSAL_PASS_PHRASES)
        return [str(fields.get("causal_chain") or node.core_truth)]
    if kind == "synthesis" and step == 0:
        return [node.core_truth]
    return None


def _step_passes(node: KcNode, step: int, answer: str) -> bool:
    expects = _expects(node, step)
    if expects is None:
        return len(_norm(answer)) >= OPEN_ANSWER_MIN
    return any(matches_phrase(answer, phrase) for phrase in expects)


def _matched_signature(node: KcNode, answer: str) -> dict | None:
    for item in node.misconceptions or []:
        if isinstance(item, dict) and matches_wrong(answer, str(item.get("wrong_move") or "")):
            return item
    return None


def _get_state(db: Session, student_id: uuid.UUID, node_id: uuid.UUID) -> KcState:
    row = db.scalar(select(KcState).where(KcState.student_id == student_id, KcState.kc_id == node_id))
    if row is None:
        row = KcState(student_id=student_id, kc_id=node_id, status="unknown", stability=0)
        db.add(row)
        db.flush()
    return row


def _bump_encompassed(db: Session, student_id: uuid.UUID, node: KcNode) -> None:
    edges = db.scalars(
        select(KcEdge).where(KcEdge.from_kc == node.id, KcEdge.kind == "encompasses")
    )
    for edge in edges:
        state = _get_state(db, student_id, edge.to_kc)
        state.stability = round(float(state.stability or 0) + float(edge.weight or ENCOMPASS_WEIGHT), 2)
        if state.status == "unknown":
            state.status = "fragile"
        state.last_practiced = _now()


def _pass_reply(node: KcNode) -> str:
    fields = node.type_fields or {}
    if node.kc_type == "factual":
        return FACTUAL_PASS.format(body=fields.get("fact") or node.core_truth)
    if node.kc_type == "synthesis":
        return SYNTHESIS_PASS.format(body=node.core_truth)
    return OTHER_PASS.format(body=node.core_truth)


def choice_for(node: KcNode, move) -> dict | None:
    """The two closed picks. Every other move is typed."""
    if not getattr(move, "choice", False):
        return None
    fields = node.type_fields or {}
    if move.key in {"predict_a", "predict_b"}:
        case_key = "case_a" if move.key == "predict_a" else "case_b"
        case = str(fields.get(case_key) or "").strip()
        question = str(fields.get("prediction") or "What do you predict?").strip()
        return {
            "prompt": f"{question} {case}".strip(),
            "choices": [
                {"id": "holds", "text": "This holds"},
                {"id": "not", "text": "This does not hold"},
            ],
        }
    if move.key == "predict":
        return {
            "prompt": str(fields.get("prediction") or ""),
            "choices": [
                {"id": "case-a", "text": str(fields.get("case_a") or "")},
                {"id": "case-b", "text": str(fields.get("case_b") or "")},
            ],
        }
    if move.key == "mark":
        return {
            "prompt": f"{CLAIM_LEAD} {fields.get('flawed_claim') or ''}".strip(),
            "choices": [
                {"id": "mark", "text": CAUSAL_MARK_LABEL},
                {"id": "holds", "text": CAUSAL_HOLD_LABEL},
            ],
        }
    return None


def _session_messages(db: Session, session: KcSession) -> list[KcMessage]:
    return list(
        db.scalars(select(KcMessage).where(KcMessage.session_id == session.id).order_by(KcMessage.seq))
    )


def _needs_speech(session: KcSession, messages: list[KcMessage]) -> bool:
    """The opening intro has not been stored yet."""
    if session.status != "in_progress":
        return False
    return not any(message.role == "assistant" for message in messages)


def _block_context(db: Session, session: KcSession, node: KcNode | None):
    """The active block, its substep, and whether a short answer still needs a full sentence."""
    profile = load_profile(db)
    goal = db.get(KcGoal, session.goal_id)
    messages = _session_messages(db, session)
    cfg = effective_kc_tutor_config(profile)
    blocks = stored_blocks(node)
    index = min(max(int(session.step or 0), 0), len(blocks) - 1) if blocks else 0
    block = blocks[index] if blocks else None
    state = dict(session.active_block_state or {})
    if block is not None and not str(state.get("substep") or "").strip():
        state["substep"] = default_substep_for_block(block, cfg)
    data = block.get("data") if isinstance(block, dict) and isinstance(block.get("data"), dict) else {}
    required = str(data.get("acceptance_criteria") or data.get("goal") or "")
    first = next((message.content for message in messages if message.role == "user"), "")
    fragment = bool(block and block.get("type") == "topic_goal" and is_fragment(first, required))
    return profile, goal, messages, fragment, cfg, blocks, index, block, state


def _session_block_progress(node: KcNode | None, session: KcSession) -> dict:
    blocks = _public_blocks(node)
    if not blocks or node is None:
        return {}
    total = len(blocks)
    active = min(max(int(session.step or 0), 0), total - 1)
    state = session.active_block_state if isinstance(session.active_block_state, dict) else {}
    substep = str(state.get("substep") or "").strip()
    results = session.block_results if isinstance(session.block_results, list) else []
    by_id = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or item.get("block_id") or "")
        if key:
            by_id[key] = item
    progress: list[dict] = []
    completed = 0
    for index, block in enumerate(blocks):
        bid = str(block.get("id") or f"blk_{index + 1}")
        if bid in by_id:
            status = "completed"
            completed += 1
        elif session.status == "in_progress" and index == active:
            status = "active"
        else:
            status = "upcoming"
        stored = by_id.get(bid) or {}
        data = block.get("data") if isinstance(block.get("data"), dict) else {}
        kind = str(block.get("type") or "topic_goal")
        progress.append(
            {
                "id": bid,
                "index": index,
                "type": kind,
                "type_label": _BANNER_LABELS.get(kind, kind),
                "title": _block_title(data, node.title),
                "status": status,
                "outcome": stored.get("outcome"),
                "attempts": int(stored.get("attempts") or 0),
            }
        )
    sub_label = ""
    if substep:
        from app.kc_prompt import format_active_substep_label

        sub_label = format_active_substep_label(blocks[active], substep)
    return {
        "total_blocks": total,
        "completed_blocks": completed,
        "completion_pct": round(100 * completed / total),
        "active_block_index": active,
        "active_substep_label": sub_label,
        "block_progress": progress,
    }


def session_out(db: Session, session: KcSession) -> dict:
    node = db.get(KcNode, session.kc_id)
    _profile, _goal, messages, _fragment, cfg, blocks, index, block, state = _block_context(db, session, node)
    needs_speech = _needs_speech(session, messages)
    substep = str(state.get("substep") or "")
    choice = None
    if block is not None and session.status == "in_progress" and not needs_speech:
        choice = on_screen_choice(block, substep, state, cfg)
    label = block_step_label(block, index, len(blocks), substep) if block is not None else "This step"
    redirect = db.get(KcNode, session.redirect_kc_id) if session.redirect_kc_id else None
    return {
        "id": str(session.id),
        "course_id": str(session.goal_id),
        "kc_id": str(session.kc_id),
        "code": node.code if node else "",
        "title": node.title if node else "",
        "kc_type": node.kc_type if node else None,
        "recipe": session.recipe,
        "step": session.step,
        "step_label": label,
        "status": session.status,
        "score": session.score,
        "needs_speech": needs_speech,
        "choice": choice,
        "redirect": None
        if redirect is None
        else {"id": str(redirect.id), "code": redirect.code, "title": redirect.title},
        "messages": [
            {"id": str(message.id), "role": message.role, "content": message.content, "seq": message.seq}
            for message in messages
        ],
        **_session_block_progress(node, session),
    }


def open_session(db: Session, student: Student, goal: KcGoal, node: KcNode) -> KcSession:
    if not goal.ready:
        raise HTTPException(status_code=422, detail="This course is not ready.")
    if not _authored_blocks(node.blocks):
        raise HTTPException(status_code=422, detail="This component has no blocks yet.")
    targets = load_targets(db, goal)
    allowed = {item.id for item in targets + load_patches(db, targets)}
    if node.id not in allowed:
        raise HTTPException(status_code=422, detail="That component is not on this course.")
    existing = db.scalar(
        select(KcSession).where(
            KcSession.student_id == student.id,
            KcSession.goal_id == goal.id,
            KcSession.kc_id == node.id,
            KcSession.status == "in_progress",
        )
    )
    if existing is not None:
        if _last_block_finished(node, existing):
            _close_finished_walk(db, existing, node)
        return existing
    blocks = stored_blocks(node)
    cfg = effective_kc_tutor_config(load_profile(db))
    substep = default_substep_for_block(blocks[0], cfg) if blocks else "main"
    session = KcSession(
        student_id=student.id,
        goal_id=goal.id,
        kc_id=node.id,
        recipe="block_walk",
        step=0,
        status="in_progress",
        active_block_state={"substep": substep, "dialogue_turns": 0},
    )
    db.add(session)
    db.flush()
    return session


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    return str(value)


def _csv(values: object) -> str:
    if not isinstance(values, list):
        return ""
    return ", ".join(part for part in (_text(item).strip() for item in values) if part)


def _misconceptions(values: object) -> str:
    if not isinstance(values, list):
        return ""
    lines: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        wrong = str(item.get("wrong_move") or "").strip()
        broken = str(item.get("broken_kc") or "").strip()
        if wrong or broken:
            lines.append(f"{wrong} -> {broken}")
    return "\n".join(lines)


_LAYER_1 = "Layer 1, Component"
_LAYER_2 = "Layer 2, Child"
_LAYER_3 = "Layer 3, Voice"
_LAYER_4 = "Layer 4, Guidance"
_LAYER_5 = "Layer 5, Encouragement"
_LAYER_6 = "Layer 6, Metacognition"
_LAYER_7 = "Layer 7, Feedback loop"

_CATALOG_FIELDS: dict[str, list[tuple[str, str]]] = {
    "topic_goal": [
        ("topic", "Topic"),
        ("goal", "Goal"),
        ("acceptance_criteria", "Acceptance criteria"),
        ("teaching_notes", "Teaching notes"),
    ],
    "mcq": [
        ("mode", "Mode"),
        ("question_stem", "Question stem"),
        ("choices", "Choices"),
        ("correct_explanation", "Correct explanation"),
        ("target_skill", "Target skill"),
        ("difficulty", "Difficulty"),
        ("num_choices", "Number of choices"),
        ("distractor_guidance", "Distractor guidance"),
        ("stem_constraints", "Stem constraints"),
    ],
    "case_study": [
        ("case_a", "Case A"),
        ("case_b", "Case B"),
        ("prediction_prompt", "Prediction prompt"),
        ("invariant_principle", "Invariant principle"),
        ("transfer_prompt", "Transfer prompt"),
        ("transfer_expected", "Transfer expected"),
    ],
    "socratic": [
        ("central_dilemma", "Central dilemma"),
        ("initial_probe", "Opening probe"),
        ("counterexamples", "Counterexamples"),
        ("target_synthesis", "Target synthesis"),
    ],
    "curiosity": [
        ("phenomenon_hook", "Phenomenon hook"),
        ("prediction_question", "Prediction question"),
        ("bridge_to_unit", "Bridge to unit"),
        ("wonder_branches", "Wonder branches"),
    ],
    "worked_example": [
        ("problem_statement", "Problem statement"),
        ("steps", "Steps"),
        ("faded_step_index", "Faded step"),
        ("solo_problem", "Solo problem"),
        ("solo_expected_answer", "Solo expected answer"),
    ],
    "spot_the_flaw": [
        ("rookie_work", "Rookie work"),
        ("flaw_description", "Flaw description"),
        ("underlying_misconception", "Underlying misconception"),
        ("corrected_version", "Corrected version"),
    ],
    "teach_back": [
        ("peer_persona_prompt", "Peer prompt"),
        ("required_concepts", "Required concepts"),
        ("peer_follow_up_question", "Peer follow-up"),
    ],
    "retrieval_check": [
        ("recall_prompt", "Recall prompt"),
        ("expected_fact", "Expected fact"),
        ("elaborative_why_prompt", "Elaborative why prompt"),
        ("expected_why_rationale", "Expected why rationale"),
    ],
}

_MCQ_STATIC = {"mode", "question_stem", "choices", "correct_explanation"}
_MCQ_DYNAMIC = {
    "mode",
    "target_skill",
    "difficulty",
    "num_choices",
    "distractor_guidance",
    "stem_constraints",
}

_SETTING_LABELS = {
    "explanation_depth": "Explanation depth",
    "max_retries_before_reveal": "Retries before reveal",
    "hint_ladder_style": "Hint ladder",
    "goal_evaluation_strictness": "Goal evaluation",
    "fragment_self_explanation": "Ask for a full sentence",
    "enrichment_mode": "Enrichment",
    "max_retry_attempts": "Retry attempts",
    "wrong_answer_explanation_depth": "Wrong-answer depth",
    "disable_eliminated_choices": "Disable eliminated choices",
    "confirm_why_on_correct": "Ask why it is correct",
    "correct_pass_explanation_depth": "Pass explanation",
    "case_presentation": "Case presentation",
    "require_transfer_application": "Require transfer",
    "dialogue_depth_turns": "Dialogue depth",
    "challenge_intensity": "Challenge intensity",
    "hint_when_stuck": "Hint when stuck",
    "max_wonder_turns": "Wonder turns",
    "require_initial_prediction": "Require a prediction",
    "counts_toward_mastery_score": "Counts toward mastery",
    "hook_framing_style": "Hook framing",
    "fading_level": "Fading level",
    "require_step_self_explanation": "Require a why",
    "wrong_step_explanation_depth": "Wrong-step depth",
    "critique_depth": "Critique depth",
    "show_misconception_why": "Name why the trap is tempting",
    "peer_confusion_level": "Peer confusion",
    "follow_up_questions_count": "Follow-up questions",
    "evaluation_strictness": "Evaluation",
    "cue_scaffolding": "Cue scaffolding",
    "require_elaborative_why": "Ask why",
    "accept_paraphrase": "Accept a paraphrase",
}


def _row(name: str, value: object, layer: str) -> dict[str, str]:
    return {"name": name, "value": "" if value is None else str(value), "layer": layer}


def _state_row(db: Session, student: Student | None, node: KcNode | None) -> KcState | None:
    if student is None or node is None:
        return None
    return db.scalar(select(KcState).where(KcState.student_id == student.id, KcState.kc_id == node.id))


def _prerequisite_status(db: Session, student: Student | None, node: KcNode | None) -> str:
    if node is None:
        return ""
    codes = [str(item) for item in (node.prerequisite_codes or []) if str(item).strip()]
    if not codes:
        return ""
    by_code = _nodes_by_code(db)
    parts = []
    for code in codes:
        other = by_code.get(code)
        if other is None or student is None:
            parts.append(f"{code}: unknown")
            continue
        state = _state_row(db, student, other)
        parts.append(f"{code}: {state.status if state is not None else 'unknown'}")
    return "; ".join(parts)


def _support_band(prerequisite_status: str) -> str:
    if ": unknown" in f"; {prerequisite_status}":
        return "hold"
    if ": fragile" in f"; {prerequisite_status}":
        return "stretch"
    return "ready" if prerequisite_status or True else "ready"


def _course_position(db: Session, goal: KcGoal | None, node: KcNode | None) -> str:
    if goal is None or node is None:
        return ""
    targets = load_targets(db, goal)
    ids = [item.id for item in targets]
    if node.id not in ids:
        return "Patch"
    index = ids.index(node.id)
    previous = targets[index - 1].title if index else ""
    nxt = targets[index + 1].title if index + 1 < len(targets) else ""
    return f"{index + 1} of {len(targets)}; previous: {previous or 'none'}; next: {nxt or 'none'}"


def _minutes_used(db: Session, student: Student | None, goal: KcGoal | None) -> str:
    if student is None or goal is None:
        return ""
    total = 0.0
    now = _now()
    rows = db.scalars(
        select(KcSession).where(KcSession.student_id == student.id, KcSession.goal_id == goal.id)
    )
    for row in rows:
        start = row.created_at or now
        end = row.updated_at or now
        total += max(0.0, (end - start).total_seconds() / 60.0)
    return str(int(round(total)))


def _others_known(db: Session, student: Student | None, goal: KcGoal | None, node: KcNode | None) -> bool:
    if student is None or goal is None:
        return False
    for target in load_targets(db, goal):
        if node is not None and target.id == node.id:
            continue
        state = _state_row(db, student, target)
        if state is None or state.status not in {"known", "fragile"}:
            return False
    return True


def _last_messages(messages: list[KcMessage], limit: int = 4) -> str:
    chosen = messages[-limit:]
    if not chosen:
        return ""
    return " | ".join(f"{message.role}: {message.content}" for message in chosen)


def _catalog_text(key: str, value: object) -> str:
    if key == "choices" and isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            letter = str(item.get("id") or "").strip()
            text = str(item.get("text") or "").strip()
            if not letter and not text:
                continue
            mark = " correct" if item.get("is_correct") else ""
            parts.append(f"{letter}. {text}{mark}".strip())
        return "; ".join(parts)
    if key == "steps" and isinstance(value, list):
        parts = []
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                text = str(item.get("step_text") or "").strip()
            else:
                text = str(item or "").strip()
            if text:
                parts.append(f"{index}. {text}")
        return "; ".join(parts)
    if isinstance(value, list):
        return "; ".join(str(item).strip() for item in value if str(item).strip() and not isinstance(item, (dict, list)))
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return ""
    return str(value).strip() if isinstance(value, str) else str(value)


def _active_catalog_rows(block: dict | None) -> list[tuple[str, str]]:
    """Catalog fields the active block's prompt reads. Empty fields stay."""
    if not isinstance(block, dict):
        return []
    btype = str(block.get("type") or "").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    fields = list(_CATALOG_FIELDS.get(btype, []))
    if btype == "mcq":
        keep = _MCQ_DYNAMIC if str(data.get("mode") or "static").strip() == "dynamic" else _MCQ_STATIC
        fields = [item for item in fields if item[0] in keep]
    return [(label, _catalog_text(key, data.get(key))) for key, label in fields]


def _active_setting_rows(block: dict | None, cfg: dict) -> list[tuple[str, str]]:
    if not isinstance(block, dict):
        return []
    btype = str(block.get("type") or "").strip()
    stored = ((cfg.get("blocks") or {}).get(btype) or {})
    rows: list[tuple[str, str]] = []
    for key in BLOCK_CONFIG_SPECS.get(btype, {}):
        value = stored.get(key)
        text = "yes" if value is True else "no" if value is False else "" if value is None else str(value)
        rows.append((_SETTING_LABELS.get(key, key), text))
    return rows


def _close_flags(
    block: dict | None,
    blocks: list[dict],
    index: int,
    substep: str,
    attempts: int,
    cfg: dict,
    *,
    unit_complete: bool,
    known: bool,
    others_known: bool,
) -> tuple[str, str]:
    """Whether this turn may end the component, and whether it may end the course."""
    if block is None:
        return "no", "no"
    substeps = substeps_for_block(block, cfg)
    btype = str(block.get("type") or "").strip()
    is_last_block = index >= len(blocks) - 1
    is_last_substep = substep == substeps[-1] if substeps else True
    if substep == "awaiting_why":
        is_last_substep = True
    confirm_why = str(((cfg.get("blocks") or {}).get("mcq") or {}).get("confirm_why_on_correct") or "on_retry_only")
    if btype == "mcq" and substep == "choice" and confirm_why == "on_retry_only" and attempts > 0:
        is_last_substep = False
    may_component = (is_last_block and is_last_substep) or unit_complete
    # Fragile is finished work. It does not block the course outro, and it is not rewritten to known.
    del known
    may_course = may_component and others_known
    return ("yes" if may_component else "no", "yes" if may_course else "no")


def _eliminated_choices(state: dict) -> str:
    mcq = state.get("mcq") if isinstance(state.get("mcq"), dict) else {}
    raw = mcq.get("eliminated_indices") if isinstance(mcq, dict) else []
    if not isinstance(raw, list) or not raw:
        return ""
    return ", ".join(str(item) for item in raw)


def _finished_block_text(results: object) -> str:
    if not isinstance(results, list):
        return ""
    lines: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("block_id") or "block").strip()
        outcome = str(item.get("outcome") or "").strip()
        lines.append(f"{title}: {outcome} after {item.get('attempts') or 0} tries")
    return "\n".join(lines)


def tutor_variables(
    db: Session,
    *,
    student_id: uuid.UUID | None = None,
    course_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> list[dict[str, str]]:
    """Named inputs for the current KC chat, grouped under the seven layers."""
    session = db.get(KcSession, session_id) if session_id is not None else None
    if session_id is not None and session is None:
        raise HTTPException(status_code=404, detail="That session is not open.")
    if session is not None:
        student = _student_or_404(db, session.student_id)
        goal = _course_or_404(db, session.goal_id)
        node = _node_or_404(db, session.kc_id)
    else:
        student = _student_or_404(db, student_id) if student_id is not None else None
        goal = _course_or_404(db, course_id) if course_id is not None else None
        node = None
    profile = load_profile(db)
    messages: list[KcMessage] = []
    cfg = effective_kc_tutor_config(profile)
    blocks = stored_blocks(node)
    index = 0
    block = None
    block_state: dict = {}
    if session is not None and node is not None:
        _profile, _goal, messages, _fragment, cfg, blocks, index, block, block_state = _block_context(
            db, session, node
        )
    elif blocks:
        block = blocks[0]
        block_state = {"substep": default_substep_for_block(block, cfg)}
    substep = str(block_state.get("substep") or "")
    if block is not None and not substep:
        substep = default_substep_for_block(block, cfg)
    from app.kc_model import BLOCK_LABELS, derive_rubric_from_blocks

    state = _state_row(db, student, node)
    prereq = _prerequisite_status(db, student, node)
    band = _support_band(prereq) if node is not None else ""
    others = _others_known(db, student, goal, node)
    known = state is not None and state.status == "known"
    unit_complete = bool(session is not None and session.status == "completed")
    attempts = int(session.move_attempts or 0) if session is not None else 0
    close_component, close_course = _close_flags(
        block,
        blocks,
        index,
        substep,
        attempts,
        cfg,
        unit_complete=unit_complete,
        known=known,
        others_known=others,
    )
    redirect = ""
    if session is not None and session.redirect_kc_id is not None:
        target = db.get(KcNode, session.redirect_kc_id)
        if target is not None:
            redirect = f"{target.title} ({target.code})"
    interests = ""
    cp = effective_child_profile(student) if student is not None else None
    if student is not None and cp is not None:
        interests = cp["interests"] or ", ".join(
            str(item).strip() for item in (student.interests or []) if str(item).strip()
        )
    over = cfg.get("overarching") or {}
    block_type = ""
    derived = ""
    if block is not None:
        kind = str(block.get("type") or "").strip()
        label = BLOCK_LABELS.get(kind, kind)
        block_type = kind if not label or label == kind else f"{kind} ({label})"
        derived = "\n".join(derive_rubric_from_blocks([block]))
    outline = str(getattr(node, "outline", "") or "") if node is not None else ""
    rows: list[dict[str, str]] = [
        _row("Course title", goal.title if goal is not None else "", _LAYER_1),
        _row("Course description", (goal.description or "") if goal is not None else "", _LAYER_1),
        _row("Audience", goal.audience if goal is not None else "", _LAYER_1),
        _row("Kind", goal.kind if goal is not None else "", _LAYER_1),
        _row("Minutes", "" if goal is None or goal.minutes is None else str(goal.minutes), _LAYER_1),
        _row("Component title", node.title if node is not None else "", _LAYER_1),
        _row("Component code", node.code if node is not None else "", _LAYER_1),
        _row("Outline", outline, _LAYER_1),
        _row("Core truth", (node.core_truth or "") if node is not None else "", _LAYER_1),
        _row("Derived rubric", derived, _LAYER_1),
        _row("Misconceptions", _misconceptions(node.misconceptions if node is not None else []), _LAYER_1),
        _row("Prerequisite codes", _csv(node.prerequisite_codes if node is not None else []), _LAYER_1),
        _row("Encompass codes", _csv(node.encompasses_codes if node is not None else []), _LAYER_1),
        _row("Prerequisite status", prereq, _LAYER_1),
        _row("Block index", f"{index + 1} of {len(blocks)}" if block is not None else "", _LAYER_1),
        _row("Block type", block_type, _LAYER_1),
        _row("Substep", substep if block is not None else "", _LAYER_1),
        _row(
            "Choice on screen",
            ("yes" if block_uses_choice_widget(block, substep, block_state) else "no") if block is not None else "",
            _LAYER_1,
        ),
    ]
    for name, value in _active_catalog_rows(block):
        rows.append(_row(name, value, _LAYER_1))
    voice = effective_voice_settings(profile)
    persona_val = str(voice.get("persona") or profile.persona or "coach")
    vocab_reg = str(voice.get("vocabulary_register") or "adaptive_to_child")
    weaving_val = str(voice.get("interest_weaving") or "subtle_natural")
    meta_val = str(voice.get("metaphors") or profile.metaphors or "everyday")
    humor_val = str(voice.get("humor_and_wit") or "light_warm")
    sidekick_val = str(voice.get("sidekick") or profile.sidekick or "none")

    has_child_interests = bool(
        (cp and (cp.get("interest_tags") or cp.get("interests"))) or interests
    )
    eff_analogy_source = (
        "child_interests" if weaving_val != "off" and has_child_interests else "fallback_metaphors"
    )
    read_lvl_val = str(cp["reading_level"]) if cp is not None else "on_grade"
    resp_len_val = str(cp["response_length"]) if cp is not None else "balanced"
    support_val = str(cp["learning_support"]) if cp is not None else "none"
    tone_val = str(cp["communication_tone"]) if cp is not None else "warm_and_encouraging"
    eff_vocab_rule = (
        f"{vocab_reg} terminology + Layer 2 reading_level={read_lvl_val}, response_length={resp_len_val}"
        + (f", learning_support={support_val}" if support_val != "none" else "")
    )
    opening_turn = session is None or not any(message.role == "assistant" for message in messages)
    turn_kind_val = (
        compute_turn_kind(
            opening=opening_turn,
            unit_complete=unit_complete,
            course_complete=close_course == "yes" and unit_complete,
            transition_from_block=None,
            attempts=attempts,
            hint_tier=session.hint_tier or "nudge" if session is not None else "nudge",
            reveals=int(session.reveals or 0) if session is not None else 0,
        )
        if session is not None or block is not None
        else "orient"
    )
    if turn_kind_val in {"nudge", "scaffold", "reveal"}:
        eff_humor_rule = f"suppressed (missed attempt: {turn_kind_val})"
    elif support_val == "math_or_test_anxiety" or tone_val == "calm_and_gentle":
        eff_humor_rule = f"suppressed (Layer 2 {support_val if support_val == 'math_or_test_anxiety' else tone_val})"
    elif humor_val == "none_straightforward":
        eff_humor_rule = "none_straightforward (disabled)"
    else:
        eff_humor_rule = f"{humor_val} (active on hooks and passes)"

    orient_raw = str(over.get("orient_framing") or "elaborate_outline")
    eff_orient = (
        "brief_hook (time_boxed override)"
        if goal is not None and goal.kind == "time_boxed" and orient_raw != "brief_hook"
        else orient_raw
    )
    close_raw = str(over.get("close_summary_depth") or "diagnostic_strengths_and_gaps")
    eff_close_depth = (
        "concise (time_boxed override)"
        if goal is not None and goal.kind == "time_boxed" and close_raw != "concise"
        else close_raw
    )
    active_bcfg_summary = ""
    if block is not None:
        btype_key = str(block.get("type") or "topic_goal").strip()
        bcfg_dict = (cfg.get("blocks") or {}).get(btype_key) or {}
        active_bcfg_summary = ", ".join(f"{k}={v}" for k, v in bcfg_dict.items())
    nine_blocks_summary = " | ".join(
        f"{bt}: " + ", ".join(f"{k}={v}" for k, v in ((cfg.get("blocks") or {}).get(bt) or {}).items())
        for bt in ALL_BLOCK_TYPES
    )
    max_retries_val = (
        str(max_retries_for_block(block, cfg, goal)) if block is not None else ""
    )

    rows.extend(
        [
            _row("Display name", student.display_name if student is not None else "", _LAYER_2),
            _row("Age", "" if student is None or student.age is None else str(student.age), _LAYER_2),
            _row("Grade band", "" if cp is None else str(cp["grade_band"]), _LAYER_2),
            _row("Reading level", "" if cp is None else str(cp["reading_level"]), _LAYER_2),
            _row("Response length", "" if cp is None else str(cp["response_length"]), _LAYER_2),
            _row("Expression style", "" if cp is None else str(cp["expression_style"]), _LAYER_2),
            _row("Explanation style", "" if cp is None else str(cp["explanation_style"]), _LAYER_2),
            _row("Challenge appetite", "" if cp is None else str(cp["challenge_appetite"]), _LAYER_2),
            _row("Communication tone", "" if cp is None else str(cp["communication_tone"]), _LAYER_2),
            _row("Learning support", "" if cp is None else str(cp["learning_support"]), _LAYER_2),
            _row("Interest tags", "" if cp is None else _csv(list(cp["interest_tags"] or [])), _LAYER_2),
            _row("Interests", interests, _LAYER_2),
            _row("Hint tier already given", "" if session is None else (session.hint_tier or "nudge"), _LAYER_2),
            _row("Component status", "" if state is None else state.status, _LAYER_2),
            _row(
                "Last answer",
                next((message.content for message in reversed(messages) if message.role == "user"), ""),
                _LAYER_2,
            ),
            _row("Last misconception", "" if session is None else (session.last_misconception or ""), _LAYER_2),
            _row("Minutes used", _minutes_used(db, student, goal), _LAYER_2),
            _row("Support band", band, _LAYER_2),
            _row("Persona", labeled_choice(PERSONAS, persona_val), _LAYER_3),
            _row("Vocabulary register", labeled_choice(VOCABULARY_REGISTERS, vocab_reg), _LAYER_3),
            _row("Interest weaving", labeled_choice(INTEREST_WEAVING_MODES, weaving_val), _LAYER_3),
            _row("Metaphors", labeled_choice(METAPHORS, meta_val), _LAYER_3),
            _row("Humor and wit", labeled_choice(HUMOR_MODES, humor_val), _LAYER_3),
            _row("Sidekick", labeled_choice(SIDEKICKS, sidekick_val), _LAYER_3),
            _row("Effective analogy source", eff_analogy_source, _LAYER_3),
            _row("Effective vocabulary rule", eff_vocab_rule, _LAYER_3),
            _row("Effective humor rule", eff_humor_rule, _LAYER_3),
            _row("Orient framing", eff_orient, _LAYER_4),
            _row("Instructional stance", str(over.get("instructional_stance") or "guided_discovery"), _LAYER_4),
            _row(
                "Scaffolding escalation",
                str(over.get("scaffolding_escalation") or "progressive_nudge_then_scaffold"),
                _LAYER_4,
            ),
            _row("Stay on course", str(over.get("stay_on_course") or ""), _LAYER_4),
            _row("Misconception policy", str(over.get("misconception_policy") or ""), _LAYER_4),
            _row(
                "Prerequisite support policy",
                str(over.get("prerequisite_support_policy") or "inline_micro_recap"),
                _LAYER_4,
            ),
            _row("Active block config", active_bcfg_summary, _LAYER_4),
            _row("All 9 block configs", nine_blocks_summary, _LAYER_4),
        ]
    )
    for name, value in _active_setting_rows(block, cfg):
        rows.append(_row(name, value, _LAYER_4))
    rows.extend(
        [
            _row("Encouragement style", str(over.get("encouragement_style") or ""), _LAYER_5),
            _row("Close summary depth", eff_close_depth, _LAYER_6),
            _row("Turn kind", "" if session is None and block is None else turn_kind_val, _LAYER_7),
            _row("Attempts", "" if session is None else str(attempts), _LAYER_7),
            _row("Max retries", max_retries_val, _LAYER_7),
            _row(
                "Dialogue turns",
                "" if session is None else str(int(block_state.get("dialogue_turns") or 0)),
                _LAYER_7,
            ),
            _row("Eliminated choices", _eliminated_choices(block_state) if session is not None else "", _LAYER_7),
            _row(
                "Finished blocks",
                _finished_block_text(session.block_results) if session is not None else "",
                _LAYER_7,
            ),
            _row("Reveals used", "" if session is None else str(session.reveals or 0), _LAYER_7),
            _row("Off-course count", "" if session is None else str(session.off_course_count or 0), _LAYER_7),
            _row("Rubric points met", "" if session is None else _csv(list(session.rubric_met or [])), _LAYER_7),
            _row("Last four messages", _last_messages(messages), _LAYER_7),
            _row("Affect", "" if session is None else (session.affect or ""), _LAYER_7),
            _row("Help requested", "" if session is None else ("yes" if session.help_requested else "no"), _LAYER_7),
            _row("Redirect pending", "yes" if redirect else "no", _LAYER_7),
            _row("Enrichment turns", "" if session is None else str(session.enrichment_turns or 0), _LAYER_7),
            _row("Close component", close_component, _LAYER_7),
            _row("Close course", close_course, _LAYER_7),
        ]
    )
    return rows


def prompt_for(db: Session, session: KcSession) -> dict:
    student = _student_or_404(db, session.student_id)
    goal = _course_or_404(db, session.goal_id)
    node = _node_or_404(db, session.kc_id)
    profile, _goal, messages, fragment, _cfg, blocks, index, block, block_state = _block_context(db, session, node)
    substep = str(block_state.get("substep") or "")
    state = _state_row(db, student, node)
    opening = not any(message.role == "assistant" for message in messages)
    others = _others_known(db, student, goal, node)
    settled = state is not None and state.status in {"known", "fragile"}
    unit_complete = session.status == "completed"
    course_complete = unit_complete and settled and others
    prereq = _prerequisite_status(db, student, node)
    transition = None
    if block is not None and index > 0:
        previous = blocks[index - 1]
        previous_id = str(previous.get("id") or "")
        finished = {
            str(item.get("id") or item.get("block_id") or "")
            for item in (session.block_results or [])
            if isinstance(item, dict)
        }
        if previous_id and previous_id in finished:
            transition = previous
    active = block or {"id": "blk_1", "type": "topic_goal", "data": {}}
    bundle = build_kc_prompt(
        student=student,
        profile=profile,
        node=node,
        goal=goal,
        step=index,
        opening=opening,
        choice_on_screen=block_uses_choice_widget(active, substep, block_state),
        prerequisite_status=prereq,
        support_band=_support_band(prereq),
        course_position=_course_position(db, goal, node),
        unit_complete=unit_complete,
        course_complete=course_complete,
        attempts=int(session.move_attempts or 0),
        hint_tier=session.hint_tier or "nudge",
        reveals=int(session.reveals or 0),
        off_course_count=int(session.off_course_count or 0),
        affect=session.affect or "",
        enrichment_turns=int(session.enrichment_turns or 0),
        help_requested=bool(session.help_requested),
        minutes_used=int(_minutes_used(db, student, goal) or 0),
        component_status="" if state is None else state.status,
        stability="" if state is None else str(state.stability),
        last_answer=next((message.content for message in reversed(messages) if message.role == "user"), ""),
        last_misconception=session.last_misconception or "",
        last_messages=_last_messages(messages),
        rubric_met=[str(item) for item in (session.rubric_met or [])],
        redirect_pending=session.redirect_kc_id is not None,
        fragment=fragment,
        others_known=others,
        active_block_state=block_state,
        transition_from_block=transition,
        block_results=list(session.block_results or []),
    )
    bundle["recipe"] = session.recipe
    bundle["step"] = session.step
    bundle["step_label"] = block_step_label(active, index, max(len(blocks), 1), substep)
    return bundle


def _stored_wrong(node: KcNode, answer: str, reported: str | None) -> str:
    items = [item for item in (node.misconceptions or []) if isinstance(item, dict)]
    text = (reported or "").strip()
    if text:
        for item in items:
            wrong = str(item.get("wrong_move") or "").strip()
            if wrong and (_norm(wrong) == _norm(text) or matches_wrong(text, wrong)):
                return wrong
    signature = _matched_signature(node, answer)
    if signature is None:
        return ""
    return str(signature.get("wrong_move") or "").strip()


def _mark_known(db: Session, session: KcSession, node: KcNode) -> None:
    state = _get_state(db, session.student_id, node.id)
    if state.status != "known":
        state.status = "known"
        state.stability = round(max(float(state.stability or 0), KNOWN_STABILITY), 2)
        state.last_practiced = _now()
        _bump_encompassed(db, session.student_id, node)
        session.score = PASS_SCORE
        return
    state.last_practiced = _now()
    if session.score is None:
        session.score = PASS_SCORE


def _point_label(node: KcNode, point_id: str) -> str:
    if point_id.startswith("goal-"):
        try:
            index = int(point_id.split("-", 1)[1]) - 1
        except ValueError:
            return point_id
        goal_text = topic_goal(node, index)
        if goal_text:
            return goal_text
    return point_id


def _save_component_result(db: Session, session: KcSession, node: KcNode, body: dict, reply: str = "") -> None:
    """Known or fragile, the closing reply, and what was strong. Not a course score."""
    state = _get_state(db, session.student_id, node.id)
    status = state.status if state.status in {"known", "fragile"} else "fragile"
    met = [str(item).strip() for item in (session.rubric_met or []) if str(item).strip()]
    last = {}
    results = session.block_results if isinstance(session.block_results, list) else []
    if results and isinstance(results[-1], dict):
        last = results[-1]
    justification = str(body.get("score_justification") or body.get("justification") or "").strip()
    strong = str(body.get("what_was_strong") or body.get("strong") or last.get("strong") or "").strip()
    work_on = str(body.get("what_to_work_on") or body.get("work_on") or last.get("work_on") or "").strip()
    spoken = (reply or "").strip()
    if not justification:
        justification = spoken or ("Known." if status == "known" else "Fragile.")
    if not strong:
        strong = "The finished blocks held." if status == "known" else "A required block was revealed."
    if not work_on:
        work_on = "Use this on the next piece." if status == "known" else "Look at this component again."
    state.result = {
        "status": status,
        "rubric_met": met,
        "justification": justification,
        "strong": strong,
        "work_on": work_on,
        "reply": spoken or justification,
    }


def _mark_fragile(db: Session, session: KcSession, node: KcNode) -> None:
    state = _get_state(db, session.student_id, node.id)
    state.status = "fragile"
    state.last_practiced = _now()
    session.score = MISS_SCORE


def turn(db: Session, session: KcSession, answer: str) -> dict:
    """Store the child's answer and return the layer bundle. Scoring waits for the decision."""
    if session.status == "completed":
        raise HTTPException(status_code=422, detail="This component session is already finished.")
    cleaned = answer.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Write an answer first.")
    _add_message(db, session, "user", cleaned)
    session.updated_at = _now()
    body = session_out(db, session)
    body.update(prompt_for(db, session))
    body["reply"] = ""
    body["passed"] = False
    body["unit_complete"] = False
    body["course_complete"] = False
    return body


def apply_decision(db: Session, session: KcSession, body: dict) -> dict:
    """Check the model's decision and write mastery, edges, and the reply."""
    if session.status == "completed":
        raise HTTPException(status_code=422, detail="This component session is already finished.")
    node = _node_or_404(db, session.kc_id)
    if _last_block_finished(node, session):
        _close_finished_walk(db, session, node)
        db.commit()
        raise HTTPException(status_code=422, detail="This component session is already finished.")
    reply = str(body.get("reply") or "").strip()
    if not reply:
        raise HTTPException(status_code=422, detail="The tutor did not write a reply.")
    decision = str(body.get("decision") or "").strip()
    if decision not in DECISIONS:
        raise HTTPException(status_code=422, detail="The decision is stay, advance, complete, or redirect.")
    affect = str(body.get("affect") or "engaged").strip()
    if affect not in AFFECTS:
        affect = "engaged"
    _profile, goal, messages, fragment, cfg, blocks, index, _block, block_state = _block_context(db, session, node)
    if goal is None:
        goal = _course_or_404(db, session.goal_id)
    if not blocks:
        raise HTTPException(status_code=422, detail="This component has no blocks yet.")
    if not any(message.role == "user" for message in messages):
        raise HTTPException(status_code=422, detail="Write an answer first.")
    answer = next(message.content for message in reversed(messages) if message.role == "user")
    reported = body.get("misconception")
    matched = _stored_wrong(node, answer, None if reported is None else str(reported))
    rubric = [str(item).strip() for item in (body.get("rubric_met") or []) if str(item).strip()]
    resolution = resolve_block_turn(
        decision=decision,
        substep_passed=bool(body.get("substep_passed")),
        block_complete=bool(body.get("block_complete")),
        rubric_met=rubric,
        stored_rubric=[str(item) for item in (session.rubric_met or [])],
        matched_wrong=matched,
        blocks=blocks,
        step=index,
        active_block_state=block_state,
        block_results=list(session.block_results or []),
        move_attempts=int(session.move_attempts or 0),
        hint_tier=session.hint_tier or "nudge",
        reveals=int(session.reveals or 0),
        enrichment_turns=int(session.enrichment_turns or 0),
        cfg=cfg,
        goal=goal,
        last_misconception=session.last_misconception or "",
        answer=answer,
        fragment=fragment,
        strong=str(body.get("what_was_strong") or body.get("strong") or ""),
        work_on=str(body.get("what_to_work_on") or body.get("work_on") or ""),
    )
    if resolution.mark_fragile:
        _mark_fragile(db, session, node)
        if resolution.redirect:
            broken_code = ""
            for item in node.misconceptions or []:
                if isinstance(item, dict) and str(item.get("wrong_move") or "").strip() == resolution.misconception:
                    broken_code = str(item.get("broken_kc") or "")
            broken = _nodes_by_code(db).get(broken_code)
            session.redirect_kc_id = broken.id if broken is not None else None
    if resolution.mark_known:
        _mark_known(db, session, node)
    session.hint_tier = resolution.hint_tier
    session.move_attempts = resolution.move_attempts
    session.reveals = resolution.reveals
    session.enrichment_turns = resolution.enrichment_turns
    session.rubric_met = list(resolution.rubric_met)
    session.last_misconception = resolution.misconception
    session.affect = affect
    session.help_requested = bool(body.get("help_requested"))
    if bool(body.get("off_course")):
        session.off_course_count = int(session.off_course_count or 0) + 1
    session.attempts = int(session.attempts or 0) + 1
    session.step = resolution.next_step
    next_state = dict(resolution.next_block_state or {})
    generated = body.get("generated_mcq")
    if isinstance(generated, dict) and generated.get("choices"):
        next_state["generated_mcq"] = generated
    session.active_block_state = next_state
    session.block_results = list(resolution.block_results)
    if resolution.unit_complete:
        session.status = "completed"
        _save_component_result(db, session, node, body, reply)
    elif _last_block_finished(node, session):
        _close_finished_walk(db, session, node, reply, body)
    session.updated_at = _now()
    _add_message(db, session, "assistant", reply)
    student = _student_or_404(db, session.student_id)
    state = _state_row(db, student, node)
    settled = state is not None and state.status in {"known", "fragile"}
    unit_complete = session.status == "completed"
    course_complete = bool(unit_complete and settled and _others_known(db, student, goal, node))
    result = session_out(db, session)
    result["reply"] = reply
    result["passed"] = resolution.passed
    result["unit_complete"] = unit_complete
    result["course_complete"] = course_complete
    return result


def _chat_step_label(node: KcNode | None, step: int, goal: KcGoal | None = None) -> str:
    del goal
    blocks = stored_blocks(node)
    if not blocks:
        return "This step"
    index = min(max(step, 0), len(blocks) - 1)
    substep = default_substep_for_block(blocks[index], effective_kc_tutor_config(None))
    return block_step_label(blocks[index], index, len(blocks), substep)


def _chat_load_options():
    return (
        selectinload(KcSession.messages),
        selectinload(KcSession.prompts),
        selectinload(KcSession.student),
        selectinload(KcSession.goal),
        selectinload(KcSession.component),
    )


def kc_prompt_out(row: KcModelPrompt) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "message_id": row.message_id,
        "seq": row.seq,
        "system_prompt": row.system_prompt,
        "messages": list(row.messages or []),
        "model": row.model,
        "rubric_met": [str(item) for item in (row.rubric_met or [])],
        "misconception": row.misconception,
        "created_at": row.created_at,
    }


def _chat_summary(session: KcSession) -> dict:
    node = session.component
    goal = session.goal
    return {
        "id": session.id,
        "student_id": session.student_id,
        "student_display_name": session.student.display_name,
        "course_id": session.goal_id,
        "course_code": goal.code if goal is not None else "",
        "course_title": goal.title if goal is not None else "",
        "kc_id": session.kc_id,
        "kc_code": node.code if node is not None else "",
        "kc_title": node.title if node is not None else "",
        "kc_type": node.kc_type if node is not None else None,
        "recipe": session.recipe,
        "step": session.step,
        "step_label": _chat_step_label(node, session.step, session.goal),
        "status": session.status,
        "score": session.score,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(session.messages),
    }


def kc_chat_summaries(db: Session, student_id: uuid.UUID | None) -> list[dict]:
    stmt = select(KcSession).options(*_chat_load_options()).order_by(KcSession.updated_at.desc())
    if student_id is not None:
        stmt = stmt.where(KcSession.student_id == student_id)
    return [_chat_summary(row) for row in db.scalars(stmt).unique().all()]


def kc_chat_detail(db: Session, session_id: uuid.UUID) -> dict:
    session = db.scalar(
        select(KcSession).options(*_chat_load_options()).where(KcSession.id == session_id)
    )
    if session is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    node = session.component
    goal = session.goal
    return {
        "id": session.id,
        "status": session.status,
        "recipe": session.recipe,
        "step": session.step,
        "step_label": _chat_step_label(node, session.step, session.goal),
        "score": session.score,
        "attempts": session.attempts,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "student": student_out(session.student).model_dump(),
        "course": {
            "id": session.goal_id,
            "code": goal.code if goal is not None else "",
            "title": goal.title if goal is not None else "",
        },
        "component": {
            "id": session.kc_id,
            "code": node.code if node is not None else "",
            "title": node.title if node is not None else "",
            "kc_type": node.kc_type if node is not None else None,
        },
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "seq": message.seq,
                "created_at": message.created_at,
            }
            for message in session.messages
        ],
        "prompts": [kc_prompt_out(row) for row in session.prompts],
    }


def append_kc_model_prompt(
    db: Session,
    session: KcSession,
    system_prompt: str,
    messages: list,
    model: str,
    message_id: uuid.UUID | None = None,
    rubric_met: list | None = None,
    misconception: str | None = None,
) -> KcModelPrompt:
    linked = None
    if message_id is not None:
        linked = db.get(KcMessage, message_id)
        if linked is None or linked.session_id != session.id:
            raise HTTPException(status_code=400, detail="That message is not part of this chat.")
    seq = db.scalar(select(func.max(KcModelPrompt.seq)).where(KcModelPrompt.session_id == session.id))
    row = KcModelPrompt(
        session_id=session.id,
        message_id=linked.id if linked is not None else None,
        seq=(seq or 0) + 1,
        system_prompt=system_prompt,
        messages=messages,
        model=model.strip(),
        rubric_met=[str(item) for item in (rubric_met or []) if str(item).strip()],
        misconception=(misconception or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def record_speech(
    db: Session, session: KcSession, content: str, generated_mcq: dict | None = None
) -> dict:
    """Store the model's wording of the current step. Scoring stays in turn."""
    if session.status != "in_progress":
        raise HTTPException(status_code=422, detail="This component session is already finished.")
    text = content.strip()
    if not text:
        raise HTTPException(status_code=422, detail="The tutor did not say this step.")
    if isinstance(generated_mcq, dict) and generated_mcq:
        state = dict(session.active_block_state or {})
        state["generated_mcq"] = generated_mcq
        session.active_block_state = state
    messages = _session_messages(db, session)
    if not _needs_speech(session, messages):
        return session_out(db, session)
    _add_message(db, session, "assistant", text)
    session.updated_at = _now()
    return session_out(db, session)


def mark_node_complete(db: Session, node: KcNode) -> KcNode:
    gaps = gaps_for(node, set(_nodes_by_code(db)))
    if gaps:
        raise HTTPException(status_code=422, detail=gaps)
    node.marked_complete = True
    node.updated_at = _now()
    db.flush()
    return node


def course_of_node(db: Session, node: KcNode) -> tuple[KcGoal, list[KcNode]]:
    for candidate in db.scalars(select(KcGoal)):
        targets = load_targets(db, candidate)
        if any(item.id == node.id for item in targets) or any(
            item.id == node.id for item in load_patches(db, targets)
        ):
            return candidate, targets
    raise HTTPException(status_code=422, detail="Draft a component that is on a course.")


def describe_component(
    *,
    title: str,
    kc_type: str | None,
    core_truth: str,
    rubric: list,
    misconceptions: list,
    prerequisite_codes: list,
    encompasses_codes: list,
    type_fields: dict,
) -> str:
    checks = [str(item) for item in (rubric or []) if str(item).strip()]
    wrongs = []
    for item in misconceptions or []:
        if not isinstance(item, dict):
            continue
        wrong = str(item.get("wrong_move") or "").strip()
        broken = str(item.get("broken_kc") or "").strip()
        if wrong or broken:
            wrongs.append(f"{wrong} ({broken})" if broken else wrong)
    lines = [
        f"Title: {title}",
        f"Core truth: {(core_truth or '').strip() or 'none'}",
        "Rubric: " + ("; ".join(checks) if checks else "none"),
        "Wrong moves: " + ("; ".join(wrongs) if wrongs else "none"),
        "Prerequisites: " + (", ".join(_clean_codes(prerequisite_codes)) or "none"),
        "Encompasses: " + (", ".join(_clean_codes(encompasses_codes)) or "none"),
    ]
    fields = type_fields or {}
    for key in TYPE_KEYS.get(kc_type or "", ()):
        label = FIELD_LABELS.get(key, key)
        value = fields.get(key)
        if isinstance(value, list):
            shown = ", ".join(str(item) for item in value if str(item).strip()) or "none"
        elif value is None or str(value).strip() == "":
            shown = "none"
        else:
            shown = str(value)
        lines.append(f"{label}: {shown}")
    return "\n".join(lines)


def mirror_text(node: KcNode) -> str:
    return describe_component(
        title=node.title,
        kc_type=node.kc_type,
        core_truth=node.core_truth or "",
        rubric=list(node.rubric or []),
        misconceptions=list(node.misconceptions or []),
        prerequisite_codes=list(node.prerequisite_codes or []),
        encompasses_codes=list(node.encompasses_codes or []),
        type_fields=dict(node.type_fields or {}),
    )


def _course_topic_fields(item: dict) -> tuple[str, str, list, bool]:
    """Summary, outline, pairs, and whether this payload names the new fields."""
    from app.kc_model import clean_pairs, split_brief

    description = str(item.get("description") or "").strip()
    sent_outline = "outline" in item and item.get("outline") is not None
    sent_topics = "topics" in item and item.get("topics") is not None
    if not sent_outline and not sent_topics:
        split = split_brief(description)
        if split is not None:
            return split["description"], split["outline"], split["topics"], True
        return description, "", [], False
    outline = str(item.get("outline") or "").strip() if sent_outline else ""
    topics = clean_pairs(item.get("topics")) if sent_topics else []
    return description, outline, topics, True


def _assign_topic_fields(node: KcNode, body: dict) -> None:
    """Store the summary, the outline, and the pairs.

    A three-line description is split once when the new fields were not sent.
    A description that does not match stays the summary.
    """
    from app.kc_model import clean_pairs, split_brief

    sent_outline = "outline" in body and body.get("outline") is not None
    sent_topics = "topics" in body and body.get("topics") is not None
    if "description" in body and body.get("description") is not None:
        node.description = str(body.get("description") or "").strip()
    if sent_outline:
        node.outline = str(body.get("outline") or "").strip()
    if sent_topics:
        node.topics = clean_pairs(body.get("topics"))
    if sent_outline or sent_topics:
        return
    split = split_brief(node.description or "")
    if split is None:
        return
    node.description = split["description"]
    node.outline = split["outline"]
    node.topics = split["topics"]


def _topic_fields(goal: KcGoal, node: KcNode) -> tuple[str, str, list]:
    """Summary, outline, and pairs already stored, or a short fallback."""
    from app.kc_model import clean_pairs, split_brief

    description = (node.description or "").strip()
    outline = (node.outline or "").strip()
    pairs = clean_pairs(node.topics)
    if outline or pairs:
        return description or outline, outline, pairs
    split = split_brief(description)
    if split is not None:
        return split["description"], split["outline"], split["topics"]
    summary = description or f"How {node.title} fits {goal.title}."
    return summary, summary, [{"topic": node.title, "goal": f"Use {node.title}."}]


_BLOCK_CATALOG_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "topic_goal": (
        ("topic", "Topic"),
        ("goal", "Goal"),
        ("acceptance_criteria", "Acceptance criteria"),
        ("teaching_notes", "Teaching notes"),
    ),
    "mcq": (
        ("mode", "Mode"),
        ("question_stem", "Question stem"),
        ("choices", "Choices"),
        ("correct_explanation", "Correct explanation"),
        ("target_skill", "Target skill"),
        ("difficulty", "Difficulty"),
        ("num_choices", "Number of choices"),
        ("distractor_guidance", "Distractor guidance"),
        ("stem_constraints", "Stem constraints"),
    ),
    "case_study": (
        ("case_a", "Case A"),
        ("case_b", "Case B"),
        ("prediction_prompt", "Prediction prompt"),
        ("invariant_principle", "Invariant principle"),
        ("transfer_prompt", "Transfer prompt"),
        ("transfer_expected", "Transfer expected"),
    ),
    "socratic": (
        ("central_dilemma", "Central dilemma"),
        ("initial_probe", "Opening probe"),
        ("counterexamples", "Counterexamples"),
        ("target_synthesis", "Target synthesis"),
    ),
    "curiosity": (
        ("phenomenon_hook", "Phenomenon hook"),
        ("prediction_question", "Prediction question"),
        ("bridge_to_unit", "Bridge to unit"),
        ("wonder_branches", "Wonder branches"),
    ),
    "worked_example": (
        ("problem_statement", "Problem statement"),
        ("steps", "Steps"),
        ("faded_step_index", "Faded step"),
        ("solo_problem", "Solo problem"),
        ("solo_expected_answer", "Solo expected answer"),
    ),
    "spot_the_flaw": (
        ("rookie_work", "Rookie work"),
        ("flaw_description", "Flaw description"),
        ("underlying_misconception", "Underlying misconception"),
        ("corrected_version", "Corrected version"),
    ),
    "teach_back": (
        ("peer_persona_prompt", "Peer prompt"),
        ("required_concepts", "Required concepts"),
        ("peer_follow_up_question", "Peer follow-up"),
    ),
    "retrieval_check": (
        ("recall_prompt", "Recall prompt"),
        ("expected_fact", "Expected fact"),
        ("elaborative_why_prompt", "Elaborative why prompt"),
        ("expected_why_rationale", "Expected why rationale"),
    ),
}


def _catalog_field_lines(key: str, label: str, value: object) -> list[str]:
    """One catalog field, omitted when Push draft would write it empty."""
    if key == "choices":
        return _choice_lines(value)
    if key == "steps":
        return _step_lines(value)
    if isinstance(value, list):
        items = [
            str(item).strip()
            for item in value
            if item is not None and not isinstance(item, (dict, list)) and str(item).strip()
        ]
        return [f"{label}: {'; '.join(items)}"] if items else []
    if isinstance(value, bool):
        return [f"{label}: {'yes' if value else 'no'}"]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [f"{label}: {value}"]
    if value is None:
        return []
    text = str(value).strip()
    return [f"{label}: {text}"] if text else []


def _choice_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        letter = str(item.get("id") or "").strip()
        text = str(item.get("text") or "").strip()
        if letter and text:
            head = f"{letter}. {text}"
        elif text:
            head = text
        elif letter:
            head = letter
        else:
            continue
        notes: list[str] = []
        if item.get("is_correct") is True:
            notes.append("correct")
        trap = str(item.get("distractor_rationale") or "").strip()
        if trap:
            notes.append(f"trap: {trap}")
        code = str(item.get("misconception_code") or "").strip()
        if code:
            notes.append(f"misconception: {code}")
        rows.append(f"- {head}" + (f" ({'; '.join(notes)})" if notes else ""))
    return ["Choices:", *rows] if rows else []


def _step_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get("step_text") or "").strip()
        why = str(item.get("rationale") or "").strip()
        if text and why:
            rows.append(f"- {text} ({why})")
        elif text:
            rows.append(f"- {text}")
        elif why:
            rows.append(f"- {why}")
    return ["Steps:", *rows] if rows else []


def _block_field_lines(raw: object) -> list[str]:
    """Each block, in order, with its type label and the filled catalog fields."""
    from app.kc_model import BLOCK_LABELS

    if not isinstance(raw, list) or not raw:
        return ["Blocks: none"]
    lines: list[str] = []
    shown = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "").strip()
        if not kind:
            continue
        shown += 1
        lines.append(f"{shown}. {BLOCK_LABELS.get(kind, kind)}")
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        for key, label in _BLOCK_CATALOG_FIELDS.get(kind, ()):
            if key not in data:
                continue
            lines.extend(_catalog_field_lines(key, label, data.get(key)))
    return lines or ["Blocks: none"]


def _draft_reply(draft: dict) -> str:
    """The block fields Push draft writes. The topic list and type fields stay out."""
    title = str(draft.get("title") or "").strip() or "this component"
    lines = [f"Draft for {title} only. Other components stay as they are."]
    description = str(draft.get("description") or "").strip()
    if description:
        lines.append(f"Description: {description}")
    outline = str(draft.get("outline") or "").strip()
    lines.append(f"Outline: {outline or 'none'}")
    lines.extend(_block_field_lines(draft.get("blocks")))
    lines.append(f"Core truth: {str(draft.get('core_truth') or '').strip() or 'none'}")
    wrongs: list[str] = []
    for item in draft.get("misconceptions") or []:
        if not isinstance(item, dict):
            continue
        wrong = str(item.get("wrong_move") or "").strip()
        broken = str(item.get("broken_kc") or "").strip()
        if wrong or broken:
            wrongs.append(f"{wrong} ({broken})" if broken else wrong)
    lines.append("Misconceptions: " + ("; ".join(wrongs) if wrongs else "none"))
    lines.append(
        "Prerequisites: " + (", ".join(_clean_codes(draft.get("prerequisite_codes") or [])) or "none")
    )
    lines.append(
        "Encompasses: " + (", ".join(_clean_codes(draft.get("encompasses_codes") or [])) or "none")
    )
    lines.append("Nothing is saved until you push it.")
    return "\n".join(lines)


_LABEL_MAP = {
    "title": ("title", "title"),
    "description": ("description", "description"),
    "type": ("type", "kc_type"),
    "core truth": ("truth", "core_truth"),
    "fact": ("field", "fact"),
    "retrieval question": ("field", "retrieval_question"),
    "worked steps": ("steps", "steps"),
    "blanked step": ("int", "blanked_step"),
    "solo problem": ("field", "solo_problem"),
    "solo check": ("field", "solo_check"),
    "case one": ("field", "case_a"),
    "case two": ("field", "case_b"),
    "prediction": ("field", "prediction"),
    "rule": ("field", "rule"),
    "decision point": ("field", "decision_point"),
    "flawed claim": ("field", "flawed_claim"),
    "causal chain": ("field", "causal_chain"),
    "faulty plan": ("field", "faulty_plan"),
    "rookie's faulty plan": ("field", "faulty_plan"),
    "first component it mixes": ("mix", "mix_a"),
    "second component it mixes": ("mix", "mix_b"),
    "rubric": ("rubric", "rubric"),
    "prerequisites": ("codes", "prerequisite_codes"),
    "prerequisite": ("codes", "prerequisite_codes"),
    "encompasses": ("codes", "encompasses_codes"),
    "wrong move": ("wrong", "misconception"),
}


def _explicit_type(text: str) -> str | None:
    return _EXPLICIT_TYPES.get(text.strip().lower())


def _requested_type(message: str) -> str | None:
    lowered = message.strip().lower()
    named = _explicit_type(lowered)
    if named:
        return named
    match = re.search(r"\b(?:make it|change (?:the )?type to|switch to)\s+([a-z ]+)$", lowered)
    if not match:
        return None
    return _explicit_type(match.group(1).strip())


def _labeled_updates(message: str) -> dict:
    updates: dict = {"fields": {}}
    mixes: dict[str, str] = {}
    for raw in message.splitlines():
        if ":" not in raw:
            continue
        label, value = raw.split(":", 1)
        spec = _LABEL_MAP.get(label.strip().lower())
        if spec is None:
            continue
        kind, name = spec
        value = value.strip()
        if kind == "title":
            updates["title"] = value
        elif kind == "description":
            updates["description"] = value
        elif kind == "truth":
            updates["core_truth"] = value
        elif kind == "rubric":
            updates["rubric"] = [part.strip() for part in re.split(r"[;]", value) if part.strip()]
        elif kind == "codes":
            updates[name] = [part.strip() for part in re.split(r"[,;]", value) if part.strip()]
        elif kind == "wrong":
            if "->" in value:
                wrong, broken = value.split("->", 1)
            elif "(" in value and value.endswith(")"):
                wrong, broken = value[:-1].rsplit("(", 1)
            else:
                continue
            updates.setdefault("misconception", []).append(
                {"wrong_move": wrong.strip(), "broken_kc": broken.strip()}
            )
        elif kind == "steps":
            updates["fields"]["steps"] = [part.strip() for part in re.split(r"[;\n]", value) if part.strip()]
        elif kind == "int":
            updates["fields"]["blanked_step"] = value
        elif kind == "mix":
            mixes[name] = value
        elif kind == "field":
            updates["fields"][name] = value
    if mixes:
        updates["fields"]["mixes"] = [mixes.get("mix_a", ""), mixes.get("mix_b", "")]
    return updates


def _revise_draft(previous: dict, message: str, goal: KcGoal, node: KcNode) -> dict:
    draft = {
        "kind": "component",
        "id": previous.get("id") or str(node.id),
        "code": previous.get("code") or node.code,
        "title": previous.get("title") or node.title,
        "description": str(previous.get("description") or node.description or ""),
        "outline": str(previous.get("outline") or node.outline or ""),
        "topics": list(previous.get("topics") if previous.get("topics") is not None else (node.topics or [])),
        "blocks": list(previous.get("blocks") or _authored_blocks(node.blocks)),
        "core_truth": previous.get("core_truth") or "",
        "rubric": list(previous.get("rubric") or []),
        "misconceptions": [
            dict(item) for item in (previous.get("misconceptions") or []) if isinstance(item, dict)
        ],
        "prerequisite_codes": list(previous.get("prerequisite_codes") or []),
        "encompasses_codes": list(previous.get("encompasses_codes") or []),
    }
    labels = _labeled_updates(message)
    if str(labels.get("title") or "").strip():
        draft["title"] = str(labels["title"]).strip()
    if "description" in labels:
        draft["description"] = str(labels["description"]).strip()
    if "core_truth" in labels:
        draft["core_truth"] = str(labels["core_truth"]).strip()
    elif not _label_present(labels):
        sentence = _first_sentence(message)
        if len(_norm(sentence)) >= OPEN_ANSWER_MIN:
            draft["core_truth"] = sentence
    if "rubric" in labels:
        draft["rubric"] = _clean_rubric(labels["rubric"])
    if "prerequisite_codes" in labels:
        draft["prerequisite_codes"] = _clean_codes(labels["prerequisite_codes"])
    if "encompasses_codes" in labels:
        draft["encompasses_codes"] = _clean_codes(labels["encompasses_codes"])
    if "misconception" in labels:
        draft["misconceptions"] = _clean_misconceptions(labels["misconception"])
    return draft


def _label_present(labels: dict) -> bool:
    if labels.get("fields"):
        return True
    return any(
        key in labels
        for key in (
            "title",
            "description",
            "core_truth",
            "rubric",
            "prerequisite_codes",
            "encompasses_codes",
            "misconception",
        )
    )


def _creator_rows(db: Session, node_id: uuid.UUID) -> list[KcCreatorMessage]:
    return list(
        db.scalars(
            select(KcCreatorMessage)
            .where(KcCreatorMessage.node_id == node_id)
            .order_by(KcCreatorMessage.seq)
        )
    )


def _latest_draft(messages: list[KcCreatorMessage]) -> dict | None:
    for message in reversed(messages):
        if message.role == "assistant" and message.draft and not message.applied:
            return dict(message.draft)
    return None


def _creator_out(message: KcCreatorMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "seq": message.seq,
        "draft": message.draft,
        "applied": message.applied,
    }


def creator_thread(db: Session, node: KcNode) -> dict:
    messages = _creator_rows(db, node.id)
    return {
        "node_id": str(node.id),
        "mirror": mirror_text(node),
        "messages": [_creator_out(message) for message in messages],
        "draft": _latest_draft(messages),
    }


def _add_creator_message(
    db: Session,
    node: KcNode,
    role: str,
    content: str,
    *,
    draft: dict | None = None,
    applied: bool = False,
) -> KcCreatorMessage:
    current = db.scalar(
        select(func.max(KcCreatorMessage.seq)).where(KcCreatorMessage.node_id == node.id)
    ) or 0
    message = KcCreatorMessage(
        node_id=node.id,
        role=role,
        content=content,
        seq=int(current) + 1,
        draft=draft,
        applied=applied,
    )
    db.add(message)
    db.flush()
    return message


def expert_opening(goal: KcGoal, node: KcNode) -> str:
    """The brief, before any type field."""
    brief = (node.description or "").strip() or f"{node.title} belongs to {goal.title}."
    if goal.kind == "time_boxed" and goal.minutes:
        kind_line = f"Time boxed fits {goal.minutes} minutes."
    elif goal.kind == "time_boxed":
        kind_line = "Time boxed fits the minutes."
    elif goal.kind == "curiosity":
        kind_line = "Curiosity is a path through the subject."
    else:
        kind_line = "Mastery is the fuller rigorous breakdown."
    return f"Expert on {node.title}. {kind_line}\n{brief}\nThe topic, before the fields:"


def post_creator_turn(db: Session, node: KcNode, message: str) -> dict:
    cleaned = message.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Write a message first.")
    goal, ordered = course_of_node(db, node)
    previous = _latest_draft(_creator_rows(db, node.id))
    if previous is None:
        draft = draft_component(goal, node, ordered, cleaned)["draft"]
    else:
        draft = _revise_draft(previous, cleaned, goal, node)
    _add_creator_message(db, node, "user", cleaned)
    _add_creator_message(
        db,
        node,
        "assistant",
        f"{expert_opening(goal, node)}\n\n{_draft_reply(draft)}",
        draft=draft,
        applied=False,
    )
    return creator_thread(db, node)


def creator_prompt_for(
    db: Session,
    node: KcNode,
    message: str,
    model: str,
    allowed_block_types: list[str] | None = None,
) -> dict:
    from app.kc_model import creator_bundle

    goal, ordered = course_of_node(db, node)
    others = _other_codes(db, node, ordered)
    previous = _latest_draft(_creator_rows(db, node.id))
    try:
        return creator_bundle(
            course_title=goal.title,
            course_description=goal.description or "",
            audience=goal.audience,
            kind=goal.kind,
            minutes=goal.minutes,
            node_title=node.title,
            node_code=node.code,
            node_description=node.description or "",
            node_outline=node.outline or "",
            node_topics=list(node.topics or []),
            node_blocks=[
                block
                for block in (node.blocks or [])
                if not (isinstance(block, dict) and block.get("type") == "_legacy")
            ],
            allowed_block_types=allowed_block_types,
            other_codes=others,
            previous=previous,
            message=message,
            model=model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _other_codes(db: Session, node: KcNode, ordered: list[KcNode]) -> list[str]:
    patches = load_patches(db, ordered)
    return [item.code for item in [*ordered, *patches] if item.id != node.id]


@dataclass(frozen=True)
class BrokenKcRepair:
    """One misconception whose broken_kc was not a code on this course."""

    rejected: str
    allowed: tuple[str, ...]
    dropped: bool


@dataclass(frozen=True)
class MixRepair:
    """A synthesis mix that was not two different other-component codes.

    kept is the other-component codes that stay. An empty kept means the mix
    was cleared. A sibling the model did not name is never added.
    """

    mix_a: str
    mix_b: str
    allowed: tuple[str, ...]
    kept: tuple[str, ...]


def _et_stamp(moment: datetime | None = None) -> str:
    """A clock time in America/New_York, labeled ET."""
    current = moment or _now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S ET")


def append_history(record: KcNode | KcGoal, line: str) -> None:
    """Add one line. Earlier lines stay."""
    text = line.strip()
    if not text:
        return
    current = str(record.history or "").strip()
    record.history = f"{current}\n{text}" if current else text


def _repair_line(repair: BrokenKcRepair, stamp: str) -> str:
    allowed = ", ".join(repair.allowed) if repair.allowed else "none"
    issue = (
        f'broken_kc "{repair.rejected}" is not another component on this course. '
        f"Allowed codes: {allowed}."
    )
    if repair.dropped:
        change = (
            f'Changed broken_kc from "{repair.rejected}" to removed '
            "(that misconception was dropped because a code is required)"
        )
    else:
        change = f'Changed broken_kc from "{repair.rejected}" to ""'
    return f"{stamp} Warning: {issue} {change} so creation could continue."


def _mix_repair_line(repair: MixRepair, stamp: str) -> str:
    allowed = ", ".join(repair.allowed) if repair.allowed else "none"
    issue = (
        f'mix_a "{repair.mix_a}" and mix_b "{repair.mix_b}" are not two different other components. '
        f"Allowed codes: {allowed}."
    )
    if repair.kept:
        kept = " and ".join(f'"{code}"' for code in repair.kept)
        change = f'Changed mixes from "{repair.mix_a}" and "{repair.mix_b}" to {kept}'
    else:
        change = (
            f'Changed mixes from "{repair.mix_a}" and "{repair.mix_b}" to cleared (kept nothing)'
        )
    return f"{stamp} Warning: {issue} {change} so creation could continue."


def _log_mix(action: str, node_id: str, mix_a: str, mix_b: str, other_codes: list[str]) -> None:
    """Log a mix rejection or repair. Codes and the node id only."""
    allowed = ", ".join(other_codes) if other_codes else "none"
    logger.warning(
        "kc mix %s node_id=%s mix_a=%r mix_b=%r allowed=%s",
        action,
        node_id,
        mix_a,
        mix_b,
        allowed,
    )


def _mix_rejection_detail(mix_a: str, mix_b: str, other_codes: list[str]) -> str:
    allowed = ", ".join(other_codes) if other_codes else "none"
    return (
        "Recommend two different components for the mix. "
        f'Rejected: "{mix_a}" and "{mix_b}". Allowed codes: {allowed}.'
    )


def record_repairs(
    node: KcNode,
    goal: KcGoal,
    repairs: list[BrokenKcRepair],
    mix_repair: MixRepair | None = None,
) -> None:
    if not repairs and mix_repair is None:
        return
    stamp = _et_stamp()
    for repair in repairs:
        line = _repair_line(repair, stamp)
        append_history(node, line)
        append_history(goal, line)
    if mix_repair is not None:
        line = _mix_repair_line(mix_repair, stamp)
        append_history(node, line)
        append_history(goal, line)


def record_ai_push(db: Session, node: KcNode) -> None:
    """The creator push wrote an AI draft onto this component."""
    goal, _ordered = course_of_node(db, node)
    line = f"{_et_stamp()} Push from AI."
    append_history(node, line)
    append_history(goal, line)


def _repair_broken_kc(
    items: list[dict], other_codes: list[str]
) -> tuple[list[dict], list[BrokenKcRepair]]:
    """Keep a code the model chose. Clear or drop one it did not.

    A required code (the course has other components) cannot be stored blank,
    so that misconception is dropped. Otherwise broken_kc is cleared to "".
    A sibling code is never substituted.
    """
    allowed = set(other_codes)
    requires_code = bool(other_codes)
    kept: list[dict] = []
    repairs: list[BrokenKcRepair] = []
    for item in items:
        broken = str(item.get("broken_kc") or "")
        wrong = str(item.get("wrong_move") or "")
        if broken in allowed:
            kept.append({"wrong_move": wrong, "broken_kc": broken})
            continue
        if not broken and not requires_code:
            kept.append({"wrong_move": wrong, "broken_kc": ""})
            continue
        repairs.append(
            BrokenKcRepair(rejected=broken, allowed=tuple(other_codes), dropped=requires_code)
        )
        if requires_code:
            continue
        kept.append({"wrong_move": wrong, "broken_kc": ""})
    return kept, repairs


def _repair_mixes(
    mix_a: object, mix_b: object, other_codes: list[str]
) -> tuple[list[str], MixRepair | None]:
    """Keep two different other codes the model named. Do not invent a sibling.

    Drop a repeated code, a title, this component's code, or any other value
    that is not an other-component code. When two different other codes exist,
    a pair is kept only from codes the model actually named. If those names
    are not two different allowed codes, the mix is cleared. When fewer than
    two other components exist, a pair is not required: invalid values are
    dropped and any allowed code the model named is kept. Empty mixes are valid.
    """
    submitted_a = "" if mix_a is None else str(mix_a).strip()
    submitted_b = "" if mix_b is None else str(mix_b).strip()
    allowed = set(other_codes)

    def valid(code: str) -> bool:
        return bool(code) and code in allowed

    chosen: list[str] = []
    for code in (submitted_a, submitted_b):
        if valid(code) and code not in chosen:
            chosen.append(code)

    if len(other_codes) >= 2:
        if len(chosen) >= 2:
            return chosen[:2], None
        if not submitted_a and not submitted_b:
            return [], None
        return [], MixRepair(
            mix_a=submitted_a,
            mix_b=submitted_b,
            allowed=tuple(other_codes),
            kept=(),
        )

    if all(not code or valid(code) for code in (submitted_a, submitted_b)):
        return [code for code in (submitted_a, submitted_b) if code], None
    return chosen, MixRepair(
        mix_a=submitted_a,
        mix_b=submitted_b,
        allowed=tuple(other_codes),
        kept=tuple(chosen),
    )


def _clean_model_blocks(raw: object, allowed: list[str]) -> list[dict]:
    """Copy creator blocks whose type is in the course scope. Reject anything else."""
    if not isinstance(raw, list) or not raw:
        raise HTTPException(status_code=422, detail="Recommend at least one block.")
    allowed_set = set(allowed)
    kept: list[dict] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail="Recommend at least one block.")
        kind = str(item.get("type") or "").strip()
        if kind not in allowed_set:
            names = ", ".join(allowed) if allowed else "none"
            raise HTTPException(
                status_code=422,
                detail=(
                    "Recommend at least one block whose type is allowed for this course. "
                    f"Allowed: {names}."
                ),
            )
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        block_id = str(item.get("id") or "").strip() or f"blk_{index}"
        kept.append({"id": block_id, "type": kind, "data": dict(data)})
    return kept


def clean_model_component(
    node: KcNode,
    raw: dict,
    other_codes: list[str] | None = None,
    allowed_block_types: list[str] | None = None,
) -> tuple[dict, list[BrokenKcRepair], MixRepair | None]:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="The model reply could not be read.")
    from app.kc_model import clean_allowed_block_types, derive_rubric_from_blocks

    title = str(raw.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="Recommend a title.")
    allowed = clean_allowed_block_types(allowed_block_types)
    blocks = _clean_model_blocks(raw.get("blocks"), allowed)
    shaped = {
        "kind": "component",
        "id": str(node.id),
        "code": node.code,
        "title": title,
        "description": str(raw.get("description") or "").strip(),
        "outline": str(raw.get("outline") or "").strip(),
        "core_truth": str(raw.get("core_truth") or "").strip(),
        "blocks": blocks,
        "rubric": derive_rubric_from_blocks(blocks),
        "prerequisite_codes": _clean_codes(raw.get("prerequisite_codes") or []),
        "encompasses_codes": _clean_codes(raw.get("encompasses_codes") or []),
    }
    codes = list(other_codes or [])
    misconceptions, repairs = _repair_broken_kc(
        _clean_misconceptions(raw.get("misconceptions") or []),
        codes,
    )
    shaped["misconceptions"] = misconceptions
    _require_recommendation(
        shaped,
        codes,
        repaired=bool(repairs),
        allowed_block_types=allowed,
    )
    return shaped, repairs, None


def _require_recommendation(
    draft: dict,
    other_codes: list[str],
    *,
    repaired: bool = False,
    allowed_block_types: list[str] | None = None,
) -> None:
    """A creator draft needs a summary, an outline, a core truth, and allowed blocks."""
    from app.kc_model import clean_allowed_block_types

    if not str(draft.get("outline") or "").strip():
        raise HTTPException(status_code=422, detail="Recommend an outline.")
    if not str(draft.get("description") or "").strip():
        raise HTTPException(status_code=422, detail="Recommend a short summary.")
    if not str(draft.get("core_truth") or "").strip():
        raise HTTPException(status_code=422, detail="Recommend a core truth.")
    allowed = clean_allowed_block_types(allowed_block_types)
    allowed_set = set(allowed)
    blocks = [item for item in (draft.get("blocks") or []) if isinstance(item, dict)]
    if not blocks or any(str(item.get("type") or "") not in allowed_set for item in blocks):
        names = ", ".join(allowed) if allowed else "none"
        raise HTTPException(
            status_code=422,
            detail=(
                "Recommend at least one block whose type is allowed for this course. "
                f"Allowed: {names}."
            ),
        )
    linked_codes = set(other_codes)
    linked = list(draft["prerequisite_codes"]) + list(draft["encompasses_codes"])
    if any(code not in linked_codes for code in linked):
        raise HTTPException(
            status_code=422,
            detail="Prerequisite and encompasses codes have to be other components on this course.",
        )
    misconceptions = list(draft["misconceptions"])
    rejected = [
        str(item["broken_kc"])
        for item in misconceptions
        if str(item["broken_kc"]) and str(item["broken_kc"]) not in linked_codes
    ]
    if rejected:
        codes = ", ".join(other_codes) if other_codes else "none"
        shown = ", ".join(repr(item) for item in rejected)
        raise HTTPException(
            status_code=422,
            detail=(
                "A misconception names another component on this course. "
                f"Rejected: {shown}. Allowed codes: {codes}."
            ),
        )
    if linked_codes and not misconceptions and not repaired:
        raise HTTPException(
            status_code=422,
            detail="Recommend a misconception: a wrong move and the component that is broken.",
        )


def accept_model_turn(
    db: Session,
    node: KcNode,
    message: str,
    discussion: str,
    draft: dict,
    allowed_block_types: list[str] | None = None,
) -> dict:
    """Store a model draft. This does not write the component until push."""
    from app.kc_model import checked_discussion

    cleaned = message.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Write a message first.")
    try:
        depth = checked_discussion(discussion, node.title)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    from app.kc_model import clean_allowed_block_types

    goal, ordered = course_of_node(db, node)
    scope = allowed_block_types if allowed_block_types is not None else goal.allowed_block_types
    shaped, repairs, mix_repair = clean_model_component(
        node,
        draft,
        _other_codes(db, node, ordered),
        clean_allowed_block_types(scope),
    )
    record_repairs(node, goal, repairs, mix_repair)
    _add_creator_message(db, node, "user", cleaned)
    _add_creator_message(
        db,
        node,
        "assistant",
        f"{depth}\n\n{_draft_reply(shaped)}",
        draft=shaped,
        applied=False,
    )
    return creator_thread(db, node)


def note_component_saved(db: Session, node: KcNode) -> None:
    for message in _creator_rows(db, node.id):
        if message.draft and not message.applied:
            message.applied = True
    _add_creator_message(db, node, "assistant", SAVED_NOTE, applied=True)
