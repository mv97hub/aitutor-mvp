"""Knowledge-component courses, drafts, and the kid tutor loop.

A studio chat can draft. Nothing from that chat is stored until push.
An edit replaces one component. Kid chat, the catalog, and CreateCourse
do not call this module.
"""

from __future__ import annotations

import json
import logging
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_, select

from app.ai_safety import (
    AiSafetyError,
    latest_safety_flag,
    normalize_safety_flag,
    read_ai_safety,
    record_safety_event,
    safety_counts,
    safety_text,
)
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
    initial_block_state,
    is_fragment,
    labeled_choice,
    max_retries_for_block,
    on_screen_choice,
    stored_blocks,
    substeps_for_block,
    topic_goal,
)
from app.learn_stars import child_status_label, empty_stars, explorer_progress, stars_from_units
from app.token_usage import session_token_usage
from app.tutor_profile import (
    BLOCK_CONFIG_SPECS,
    PROFILE_ID,
    effective_kc_tutor_config,
    effective_voice_settings,
    get_profile_by_id_or_slug,
    load_profile,
    normalize_avatar_preset,
    resolve_active_profile,
)
from app.kc_pipeline import absorb_description_syllabus, clean_intake, note_missing_paste
from app.kc_standards import component_standards, paste_count, read_statements, statements_from_intake, syllabus_statements
from app.block_catalog import BLOCK_BANNER_LABELS, BLOCK_FIELDS, BLOCK_LABELS, block_summary_label
from app.models import (
    ALL_BLOCK_TYPES,
    DEFAULT_TUTOR_DESCRIPTION,
    KcCreatorMessage,
    KcEdge,
    KcGoal,
    KcMessage,
    KcModelPrompt,
    KcNode,
    KcSession,
    KcState,
    Student,
    TutorProfile,
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
    return block_summary_label(blocks)

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


def _block_short_title(data: dict) -> str:
    titled = str(data.get("block_title") or "").strip()
    if titled:
        return titled
    topics = data.get("topics")
    if isinstance(topics, list) and topics and isinstance(topics[0], dict):
        return str(topics[0].get("title") or "").strip()
    return ""


def _block_title(data: dict, fallback: str) -> str:
    titled = str(data.get("block_title") or "").strip()
    if titled:
        return titled
    topics = data.get("topics")
    if isinstance(topics, list) and topics and isinstance(topics[0], dict):
        topic_title = str(topics[0].get("title") or "").strip()
        if topic_title:
            return topic_title
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
        "passage_title",
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
            "standards": [str(code) for code in (node.standards or []) if str(code).strip()],
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
        "intake": clean_intake(goal.intake),
        "brief": goal.brief or "",
        "standards": read_course_standards(goal),
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
    if kind == "explanation":
        topics = data.get("topics") if isinstance(data.get("topics"), list) else []
        if len(topics) > 8:
            return "needs at most 8 topics"
        if not topics:
            return "needs at least one topic"
        for item in topics:
            if not isinstance(item, dict) or not _has_text(item.get("title")) or not _has_text(item.get("explanation")):
                return "needs a title and explanation on every topic"
        return ""
    if kind == "passage_ela":
        from app.kc_blocks import passage_ela_gap

        return passage_ela_gap(data)
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


def _clean_course_intake(raw: object) -> dict:
    try:
        return clean_intake(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    intake: dict | None = None,
) -> KcGoal:
    from app.kc_model import clean_allowed_block_types

    _validate_course_fields(title=title, audience=audience, kind=kind, minutes=minutes)
    cleaned_intake = _clean_course_intake(intake)
    original = (description or "").strip()
    source_before = str(cleaned_intake.get("source_text") or "").strip()
    stored_description, cleaned_intake = absorb_description_syllabus(original, cleaned_intake)
    source_after = str(cleaned_intake.get("source_text") or "").strip()
    copied = (
        paste_count(original, syllabus=True) >= 2
        and source_after != source_before
        and paste_count(source_after, syllabus=True) >= 2
    )
    standards = statements_from_intake(cleaned_intake)
    if not standards and copied:
        filled = syllabus_statements(source_after)
        if filled:
            standards = filled
    taken = set(_nodes_by_code(db)) | {goal.code for goal in db.scalars(select(KcGoal))}
    chosen = (code or "").strip() or slug_code(title, taken)
    if db.scalar(select(KcGoal).where(KcGoal.code == chosen)) is not None:
        raise HTTPException(status_code=409, detail="A course already uses that code.")
    goal = KcGoal(
        code=chosen,
        title=title.strip(),
        description=stored_description,
        audience=audience,
        kind=kind,
        minutes=minutes,
        target_kc_ids=[],
        ready=False,
        allowed_block_types=clean_allowed_block_types(allowed_block_types),
        intake=cleaned_intake,
        standards=standards,
    )
    db.add(goal)
    db.flush()
    return goal


def _brief_signature(goal: KcGoal) -> str:
    """The intake the brief was written from. A change means the brief is out of date."""
    return json.dumps(
        [goal.title, goal.description or "", goal.audience, goal.kind, goal.minutes, clean_intake(goal.intake)],
        sort_keys=True,
    )


def update_course(db: Session, goal: KcGoal, body: dict) -> KcGoal:
    title = str(body.get("title", goal.title))
    audience = str(body.get("audience", goal.audience))
    kind = str(body.get("kind", goal.kind))
    if "minutes" in body:
        minutes = body["minutes"]
    else:
        minutes = goal.minutes
    _validate_course_fields(title=title, audience=audience, kind=kind, minutes=minutes)
    before = _brief_signature(goal)
    goal.title = title.strip()
    original = str(body.get("description", goal.description) or "").strip()
    goal.audience = audience
    goal.kind = kind
    goal.minutes = minutes
    if "intake" in body and body["intake"] is not None:
        incoming = body["intake"] if isinstance(body["intake"], dict) else {}
        current = goal.intake if isinstance(goal.intake, dict) else {}
        # A partial intake must not drop a saved paste the caller did not send.
        # A paste the caller clears is remembered, so the blueprint does not plan Standard.
        goal.intake = note_missing_paste(clean_intake(current), _clean_course_intake({**current, **incoming}))
    intake_now = clean_intake(goal.intake)
    source_before = str(intake_now.get("source_text") or "").strip()
    stored_description, intake_now = absorb_description_syllabus(original, intake_now)
    goal.description = stored_description
    goal.intake = intake_now
    source_after = str(intake_now.get("source_text") or "").strip()
    copied = (
        paste_count(original, syllabus=True) >= 2
        and source_after != source_before
        and paste_count(source_after, syllabus=True) >= 2
    )
    if _brief_signature(goal) != before and (goal.brief or goal.blueprint or goal.drafting or goal.standards):
        goal.brief = ""
        goal.blueprint = {}
        goal.drafting = {}
        goal.standards = statements_from_intake(clean_intake(goal.intake))
    if copied and not read_statements(goal.standards):
        filled = syllabus_statements(source_after)
        if filled:
            goal.standards = filled
    if "allowed_block_types" in body:
        from app.kc_model import clean_allowed_block_types

        goal.allowed_block_types = clean_allowed_block_types(body.get("allowed_block_types"))
    goal.updated_at = _now()
    db.flush()
    return goal


def read_course_standards(goal: KcGoal) -> list[dict]:
    return read_statements(goal.standards)


def _pushed_standards(goal: KcGoal, item: dict) -> list[str]:
    try:
        codes, _extension = component_standards(
            item.get("standards"), read_statements(goal.standards), str(item.get("title") or "A component")
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return codes


def push_course(db: Session, goal: KcGoal, components: list[dict]) -> KcGoal:
    if not components:
        raise HTTPException(status_code=422, detail="Push a list of components.")
    by_code = _nodes_by_code(db)
    on_course = set(_target_ids(goal))
    ordered: list[str] = []
    remap: dict[str, str] = {}
    pushed: list[tuple[KcNode, list[str] | None]] = []
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
                standards=_pushed_standards(goal, item),
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
            node.standards = _pushed_standards(goal, item)
            node.updated_at = _now()
        _ensure_topic_blocks(node)
        if requested:
            remap[requested] = code
        needs = item.get("prerequisite_codes")
        pushed.append((node, _clean_codes(needs) if isinstance(needs, list) else None))
        if str(node.id) not in ordered:
            ordered.append(str(node.id))
    for node, needs in pushed:
        if needs is None:
            continue
        node.prerequisite_codes = [remap.get(code, code) for code in needs if remap.get(code, code) != node.code]
        _sync_edges(db, node)
    goal.target_kc_ids = ordered
    goal.ready = False
    goal.updated_at = _now()
    drafting = dict(goal.drafting or {})
    if drafting:
        drafting["pushed"] = True
        goal.drafting = drafting
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



def _structure_row(node: KcNode, codes: set[str], position: int) -> dict:
    blocks = _public_blocks(node)
    return {
        "id": str(node.id),
        "code": node.code,
        "title": node.title,
        "description": node.description or "",
        "standards": [str(code) for code in (node.standards or []) if str(code).strip()],
        "blocks": blocks,
        "summary": _block_summary(blocks),
        "position": position,
        "missing": gaps_for(node, codes),
        "marked_complete": bool(node.marked_complete),
    }


def structure(db: Session, goal: KcGoal) -> dict:
    """Pushed components grouped by the blueprint unit that owns them."""
    targets = load_targets(db, goal)
    codes = set(_nodes_by_code(db))
    by_code = {node.code: node for node in targets}
    blueprint = goal.blueprint if isinstance(goal.blueprint, dict) else {}
    groups: list[dict] = []
    used: set[str] = set()
    position = 0
    for index, unit in enumerate(blueprint.get("units") or []):
        if not isinstance(unit, dict):
            continue
        rows = []
        for item in unit.get("components") or []:
            if not isinstance(item, dict):
                continue
            node = by_code.get(str(item.get("code") or ""))
            if node is None or str(node.id) in used:
                continue
            position += 1
            used.add(str(node.id))
            rows.append(_structure_row(node, codes, position))
        if rows:
            groups.append(
                {
                    "title": str(unit.get("title") or f"Unit {index + 1}"),
                    "unit_index": index,
                    "components": rows,
                }
            )
    extras = []
    for node in targets:
        if str(node.id) in used:
            continue
        position += 1
        extras.append(_structure_row(node, codes, position))
    if extras:
        groups.append({"title": "Components", "unit_index": None, "components": extras})
    return {"course_id": str(goal.id), "groups": groups}


def clear_course_components(db: Session, goal: KcGoal, codes: set[str] | None = None) -> None:
    """Drop this course's components. Unshared nodes are deleted. Shared nodes stay on their other course.

    codes limits the drop to those component codes. None clears every target on the course.
    """
    targets = load_targets(db, goal)
    chosen = [node for node in targets if codes is None or node.code in codes]
    extras = load_patches(db, targets) if codes is None else []
    keep = _ids_on_other_courses(db, goal.id)
    chosen_ids = {str(node.id) for node in chosen}
    if codes is None:
        goal.target_kc_ids = []
    else:
        goal.target_kc_ids = [item for item in _target_ids(goal) if item not in chosen_ids]
    for node in [*chosen, *extras]:
        if node.id in keep:
            continue
        delete_node(db, node)
    if codes is None:
        goal.target_kc_ids = []
    goal.ready = False
    goal.updated_at = _now()


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


def _iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.isoformat()


def _block_counts_toward_mastery(block: dict, cfg: dict) -> bool:
    if not isinstance(block, dict):
        return True
    kind = str(block.get("type") or "").strip()
    if kind in {"curiosity", "explanation"}:
        block_cfg = ((cfg or {}).get("blocks") or {}).get(kind) or {}
        return bool(block_cfg.get("counts_toward_mastery_score", False))
    return True


def _student_misconceptions_for(
    state: KcState | None, sessions: list[KcSession]
) -> list[str]:
    found: list[str] = []
    if state is not None and isinstance(state.result, dict):
        raw_list = state.result.get("misconceptions")
        if isinstance(raw_list, list):
            for item in raw_list:
                text = str(item or "").strip()
                if text and text not in found:
                    found.append(text)
        single = str(state.result.get("misconception") or "").strip()
        if single and single not in found:
            found.append(single)
    for row in sessions:
        last = str(row.last_misconception or "").strip()
        if last and last not in found:
            found.append(last)
    return found


def _build_block_details(
    node: KcNode,
    session: KcSession | None,
    cfg: dict,
    goal: KcGoal,
    *,
    unit_status: str,
) -> list[dict]:
    blocks = stored_blocks(node)
    results = (
        session.block_results
        if session is not None and isinstance(session.block_results, list)
        else []
    )
    by_id: dict[str, dict] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or item.get("block_id") or "").strip()
        if key:
            by_id[key] = item

    active_index = None
    if unit_status == "in_progress" and session is not None and blocks:
        active_index = min(max(int(session.step or 0), 0), len(blocks) - 1)

    state_dict = (
        session.active_block_state
        if session is not None and isinstance(session.active_block_state, dict)
        else {}
    )
    mcq_state = state_dict.get("mcq") if isinstance(state_dict.get("mcq"), dict) else {}
    raw_elim = mcq_state.get("eliminated_indices") if isinstance(mcq_state, dict) else []

    details: list[dict] = []
    for index, block in enumerate(blocks):
        key = _block_key(block, index)
        stored = by_id.get(key)
        kind = str(block.get("type") or "topic_goal").strip()
        data = block.get("data") if isinstance(block.get("data"), dict) else {}
        label = BLOCK_BANNER_LABELS.get(kind, kind or "Block")
        prompt_preview = _block_title(data, node.title)
        rubric_line = _rubric_line(block, cfg)
        counts = _block_counts_toward_mastery(block, cfg)
        max_ret = max_retries_for_block(block, cfg, goal)

        outcome: str | None = None
        attempts = 0
        if stored is not None:
            raw_out = str(stored.get("outcome") or "passed").strip()
            outcome = raw_out if raw_out in {"passed", "revealed"} else "passed"
            attempts = int(stored.get("attempts") or 0)
            b_status = outcome
        elif active_index == index:
            b_status = "active"
            attempts = int(session.move_attempts or 0) if session is not None else 0
        else:
            b_status = "upcoming"

        passed_first = bool(outcome == "passed" and attempts <= 1)

        elim_labels: list[str] = []
        if kind == "mcq":
            stored_elim = (
                stored.get("eliminated_choices")
                if isinstance(stored, dict) and isinstance(stored.get("eliminated_choices"), list)
                else (raw_elim if active_index == index and isinstance(raw_elim, list) else [])
            )
            choices = data.get("choices") if isinstance(data.get("choices"), list) else []
            for item in stored_elim or []:
                try:
                    c_idx = int(item)
                    if 0 <= c_idx < len(choices) and isinstance(choices[c_idx], dict):
                        cid = str(choices[c_idx].get("id") or chr(ord("a") + c_idx))
                        ctext = str(choices[c_idx].get("text") or "").strip()
                        elim_labels.append(f"{cid}: {ctext}" if ctext else cid)
                    else:
                        elim_labels.append(str(item))
                except (TypeError, ValueError):
                    elim_labels.append(str(item))

        details.append(
            {
                "index": index + 1,
                "block_id": key,
                "block_type": kind,
                "label": label,
                "prompt_preview": prompt_preview,
                "rubric_line": rubric_line,
                "counts_toward_mastery": counts,
                "status": b_status,
                "outcome": outcome,
                "attempts": attempts,
                "max_retries": max_ret,
                "passed_on_first_try": passed_first,
                "eliminated_choices": elim_labels,
            }
        )
    return details


def _synthesize_course_insights(
    units: list[dict],
) -> tuple[list[dict], list[dict]]:
    accomplishments: list[dict] = []
    opportunities: list[dict] = []
    unit_by_code = {u["code"]: u for u in units}

    for u in units:
        if u.get("patch"):
            continue
        cid = str(u["id"])
        ccode = str(u["code"])
        ctitle = str(u["title"])
        mastery = str(u.get("mastery") or "")
        status = str(u.get("status") or "not_started")
        strong = str(u.get("what_was_strong") or "").strip()
        work_on = str(u.get("what_to_work_on") or "").strip()
        core_truth = str(u.get("core_truth") or "").strip()
        b_details = u.get("block_details") or []

        # Accomplishments
        if strong and strong not in {"The finished blocks held.", "A required block was revealed.", "None stored."}:
            accomplishments.append(
                {
                    "component_id": cid,
                    "component_code": ccode,
                    "component_title": ctitle,
                    "kind": "strength",
                    "summary": strong,
                    "detail": core_truth or None,
                }
            )
        if mastery == "known" and int(u.get("revealed_blocks_count") or 0) == 0:
            first_try_cnt = int(u.get("first_try_blocks_count") or 0)
            total_b = int(u.get("total_blocks") or 0)
            accomplishments.append(
                {
                    "component_id": cid,
                    "component_code": ccode,
                    "component_title": ctitle,
                    "kind": "mastered",
                    "summary": f"Mastered {ctitle} with zero reveals ({first_try_cnt}/{total_b} blocks passed on first try).",
                    "detail": core_truth or None,
                }
            )
        if int(u.get("first_try_blocks_count") or 0) >= 2:
            accomplishments.append(
                {
                    "component_id": cid,
                    "component_code": ccode,
                    "component_title": ctitle,
                    "kind": "first_try_streak",
                    "summary": f"{u['first_try_blocks_count']} blocks passed on the first try in {ctitle}.",
                    "detail": None,
                }
            )

        # Opportunities
        if work_on and work_on not in {"Use this on the next piece.", "None stored."}:
            opportunities.append(
                {
                    "component_id": cid,
                    "component_code": ccode,
                    "component_title": ctitle,
                    "kind": "weakness",
                    "summary": work_on,
                    "detail": str(u.get("score_justification") or "") or None,
                }
            )
        for blk in b_details:
            if blk.get("outcome") == "revealed":
                opportunities.append(
                    {
                        "component_id": cid,
                        "component_code": ccode,
                        "component_title": ctitle,
                        "kind": "revealed_block",
                        "summary": f"Block {blk['index']} ({blk['label']}) was revealed after {blk['attempts']} attempts.",
                        "detail": blk.get("rubric_line") or blk.get("prompt_preview") or None,
                    }
                )
            elif blk.get("outcome") == "passed" and int(blk.get("attempts") or 0) >= 2:
                opportunities.append(
                    {
                        "component_id": cid,
                        "component_code": ccode,
                        "component_title": ctitle,
                        "kind": "revealed_block",
                        "summary": f"Block {blk['index']} ({blk['label']}) needed {blk['attempts']} attempts before passing.",
                        "detail": blk.get("rubric_line") or blk.get("prompt_preview") or None,
                    }
                )
        for misc in u.get("student_misconceptions") or []:
            opportunities.append(
                {
                    "component_id": cid,
                    "component_code": ccode,
                    "component_title": ctitle,
                    "kind": "misconception",
                    "summary": f"Captured misconception on {ctitle}: {misc}",
                    "detail": core_truth or None,
                }
            )
        for pcode in u.get("prerequisite_codes") or []:
            punit = unit_by_code.get(pcode)
            if punit and (punit.get("mastery") == "fragile" or punit.get("status") != "completed"):
                if punit.get("mastery") == "fragile":
                    opportunities.append(
                        {
                            "component_id": str(punit["id"]),
                            "component_code": str(punit["code"]),
                            "component_title": str(punit["title"]),
                            "kind": "fragile_prerequisite",
                            "summary": f"Prerequisite {punit['title']} is fragile and supports {ctitle}.",
                            "detail": str(punit.get("core_truth") or "") or None,
                        }
                    )
        if status == "in_progress":
            done_b = int(u.get("completed_blocks") or 0)
            tot_b = int(u.get("total_blocks") or 0)
            opportunities.append(
                {
                    "component_id": cid,
                    "component_code": ccode,
                    "component_title": ctitle,
                    "kind": "in_progress",
                    "summary": f"{ctitle} is in progress ({done_b} of {tot_b} blocks completed).",
                    "detail": str(u.get("outline") or u.get("description") or "") or None,
                }
            )

    return accomplishments, opportunities


def _course_shell(goal: KcGoal) -> dict:
    return {
        "id": str(goal.id),
        "code": goal.code,
        "title": goal.title,
        "description": goal.description or "",
        "audience": goal.audience,
        "kind": goal.kind,
        "minutes": goal.minutes if goal.kind == "time_boxed" else None,
    }


def _empty_course_card(goal: KcGoal, targets: list[KcNode]) -> dict:
    total_blocks = sum(len(stored_blocks(node)) for node in targets)
    card = _course_shell(goal)
    card.update(
        {
            "component_count": len(targets),
            "completed_count": 0,
            "known_count": 0,
            "fragile_count": 0,
            "in_progress_count": 0,
            "not_started_count": len(targets),
            "percent": 0,
            "known_percent": 0,
            "prerequisite_codes": [],
            "unlocked": True,
            "total_blocks_count": total_blocks,
            "completed_blocks_count": 0,
            "first_try_pass_count": 0,
            "last_active_at": None,
            "accomplishments_preview": [],
            "opportunities_preview": [],
            **empty_stars(),
            "course_complete": False,
            "started": False,
            "current_topic": None,
            "tutor": None,
        }
    )
    return card


@dataclass
class _CourseCardLoad:
    goals: list[KcGoal]
    targets: dict[uuid.UUID, list[KcNode]]
    patches: dict[uuid.UUID, list[KcNode]]
    nodes_by_code: dict[str, KcNode]
    states: dict[uuid.UUID, dict[uuid.UUID, KcState]]
    sessions_by_node: dict[tuple[uuid.UUID, uuid.UUID], dict[uuid.UUID, list[KcSession]]]
    sessions_by_goal: dict[tuple[uuid.UUID, uuid.UUID], list[KcSession]]
    profiles_by_id: dict[str, TutorProfile]
    profiles_by_slug: dict[str, TutorProfile]
    default_profile: TutorProfile


def _nodes_by_ids(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, KcNode]:
    unique = list(dict.fromkeys(ids))
    if not unique:
        return {}
    return {node.id: node for node in db.scalars(select(KcNode).where(KcNode.id.in_(unique)))}


def _nulls_first_desc(moment: datetime | None) -> datetime:
    """Match PostgreSQL ORDER BY column DESC, which sorts nulls first."""
    if moment is None:
        return datetime.max.replace(tzinfo=timezone.utc)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _session_sort_key(row: KcSession) -> tuple[datetime, datetime]:
    return (_nulls_first_desc(row.updated_at), _nulls_first_desc(row.created_at))


def _cached_profile(load: _CourseCardLoad, profile_id: object) -> TutorProfile | None:
    if profile_id is None:
        return None
    key = str(profile_id).strip()
    if not key:
        return None
    found = load.profiles_by_id.get(key) or load.profiles_by_slug.get(key)
    if found is not None:
        return found
    if key == "1":
        for row in load.profiles_by_id.values():
            if row.is_default:
                return row
        return load.profiles_by_id.get(PROFILE_ID)
    return None


def _resolve_cached_profile(
    load: _CourseCardLoad,
    student: Student,
    profile_id: object = None,
) -> TutorProfile:
    if profile_id is not None and str(profile_id).strip():
        found = _cached_profile(load, profile_id)
        if found is not None:
            return found
    preferred = getattr(student, "preferred_tutor_profile_id", None)
    if preferred:
        found = _cached_profile(load, preferred)
        if found is not None:
            return found
    return load.default_profile


def _card_tutor(load: _CourseCardLoad, student: Student, goal_id: uuid.UUID) -> dict:
    rows = [row for row in load.sessions_by_goal.get((student.id, goal_id), []) if row.tutor_profile_id]
    rows.sort(key=_session_sort_key, reverse=True)
    bound = str(rows[0].tutor_profile_id) if rows else ""
    if bound:
        profile = _resolve_cached_profile(load, student, bound)
        source = "course"
    else:
        profile = _resolve_cached_profile(load, student)
        source = "preferred" if getattr(student, "preferred_tutor_profile_id", None) else "default"
    return {**_tutor_public(profile), "source": source}


def _load_course_cards(db: Session, students: list[Student]) -> _CourseCardLoad:
    """Ready courses, their topics, and this roster's state, in a few queries."""
    goals = list(db.scalars(select(KcGoal).where(KcGoal.ready.is_(True)).order_by(KcGoal.title)))
    profiles = list(db.scalars(select(TutorProfile)))
    profiles_by_id = {row.id: row for row in profiles}
    profiles_by_slug = {row.slug: row for row in profiles if row.slug}
    default_profile = profiles_by_id.get(PROFILE_ID) or load_profile(db)
    empty = _CourseCardLoad(
        goals=[],
        targets={},
        patches={},
        nodes_by_code={},
        states={},
        sessions_by_node={},
        sessions_by_goal={},
        profiles_by_id=profiles_by_id,
        profiles_by_slug=profiles_by_slug,
        default_profile=default_profile,
    )
    if not goals:
        return empty
    target_ids: list[uuid.UUID] = []
    targets: dict[uuid.UUID, list[KcNode]] = {}
    nodes_by_id = _nodes_by_ids(
        db,
        [_uuid(item) for goal in goals for item in _target_ids(goal)],
    )
    for goal in goals:
        ordered: list[KcNode] = []
        for item in _target_ids(goal):
            node = nodes_by_id.get(_uuid(item))
            if node is not None:
                ordered.append(node)
                target_ids.append(node.id)
        targets[goal.id] = ordered
    codes: list[str] = []
    seen_codes: set[str] = set()
    for ordered in targets.values():
        for code in _referenced_codes(ordered):
            if code not in seen_codes:
                seen_codes.add(code)
                codes.append(code)
    if codes:
        for node in db.scalars(select(KcNode).where(KcNode.code.in_(codes))):
            nodes_by_id.setdefault(node.id, node)
    unique_targets = list(dict.fromkeys(target_ids))
    edges: list[KcEdge] = []
    if unique_targets:
        edges = list(
            db.scalars(
                select(KcEdge).where(
                    or_(KcEdge.from_kc.in_(unique_targets), KcEdge.to_kc.in_(unique_targets))
                )
            )
        )
        missing = [
            node_id
            for edge in edges
            for node_id in (edge.from_kc, edge.to_kc)
            if node_id not in nodes_by_id
        ]
        nodes_by_id.update(_nodes_by_ids(db, missing))
    nodes_by_code = {node.code: node for node in nodes_by_id.values()}
    patches: dict[uuid.UUID, list[KcNode]] = {}
    for goal in goals:
        goal_targets = targets.get(goal.id, [])
        target_set = {node.id for node in goal_targets}
        found: list[KcNode] = []
        seen: set[uuid.UUID] = set()
        for code in _referenced_codes(goal_targets):
            node = nodes_by_code.get(code)
            if node is None or node.id in target_set or node.id in seen:
                continue
            seen.add(node.id)
            found.append(node)
        edge_ids: list[uuid.UUID] = []
        seen_edge: set[uuid.UUID] = set()
        for edge in edges:
            if edge.from_kc not in target_set and edge.to_kc not in target_set:
                continue
            for node_id in (edge.from_kc, edge.to_kc):
                if node_id not in seen_edge:
                    seen_edge.add(node_id)
                    edge_ids.append(node_id)
        for node_id in edge_ids:
            if node_id in target_set or node_id in seen:
                continue
            node = nodes_by_id.get(node_id)
            if node is None:
                continue
            seen.add(node.id)
            found.append(node)
        patches[goal.id] = found
    student_ids = list(dict.fromkeys(student.id for student in students))
    node_ids = list(nodes_by_id)
    states: dict[uuid.UUID, dict[uuid.UUID, KcState]] = {}
    if student_ids and node_ids:
        for row in db.scalars(
            select(KcState).where(KcState.student_id.in_(student_ids), KcState.kc_id.in_(node_ids))
        ):
            states.setdefault(row.student_id, {})[row.kc_id] = row
    sessions_by_node: dict[tuple[uuid.UUID, uuid.UUID], dict[uuid.UUID, list[KcSession]]] = {}
    sessions_by_goal: dict[tuple[uuid.UUID, uuid.UUID], list[KcSession]] = {}
    goal_ids = [goal.id for goal in goals]
    if student_ids and goal_ids:
        for row in db.scalars(
            select(KcSession).where(KcSession.student_id.in_(student_ids), KcSession.goal_id.in_(goal_ids))
        ):
            key = (row.student_id, row.goal_id)
            sessions_by_goal.setdefault(key, []).append(row)
            sessions_by_node.setdefault(key, {}).setdefault(row.kc_id, []).append(row)
    empty.goals = goals
    empty.targets = targets
    empty.patches = patches
    empty.nodes_by_code = nodes_by_code
    empty.states = states
    empty.sessions_by_node = sessions_by_node
    empty.sessions_by_goal = sessions_by_goal
    return empty


def _prerequisites_ready(
    node: KcNode,
    course_by_code: dict[str, KcNode],
    nodes_by_code: dict[str, KcNode],
    states: dict[uuid.UUID, KcState],
) -> bool:
    for code in _clean_codes(node.prerequisite_codes):
        other = course_by_code.get(code) or nodes_by_code.get(code)
        if other is None or not _is_settled(states, other):
            return False
    return True


def _filled_justification(
    stored: str,
    *,
    mastery: str,
    status: str,
    passed_b: int,
    revealed_b: int,
    done: int,
    total: int,
) -> str:
    if stored:
        return stored
    if mastery == "known":
        if passed_b > 0:
            return f"Known — all {passed_b} counting block(s) passed without requiring a reveal."
        return "Known — every counting block in this component passed."
    if mastery == "fragile":
        if revealed_b > 0:
            return f"Fragile — {revealed_b} block(s) required a reveal after max retries."
        return "Fragile — a counting block was revealed during practice."
    if status == "in_progress":
        return f"In progress — {done} of {total} block(s) completed so far."
    return f"Not started — {total} block(s) queued in this component."


def _summary_unit(
    node: KcNode,
    *,
    patch: bool,
    goal: KcGoal,
    state: KcState | None,
    sessions: list[KcSession],
    cfg: dict,
    course_by_code: dict[str, KcNode],
    nodes_by_code: dict[str, KcNode],
    states: dict[uuid.UUID, KcState],
    everyone_codes: set[str],
) -> dict:
    status = _unit_status(state, node, sessions)
    mastery = _mastery_label(state, node, sessions, cfg)
    chosen = _count_session(node, sessions)
    touched = _iso(
        (chosen.updated_at if chosen is not None else None)
        or (state.last_practiced if state is not None else None)
    )
    if patch:
        return {
            "id": str(node.id),
            "code": node.code,
            "title": node.title,
            "patch": True,
            "status": status,
            "mastery": mastery,
            "core_truth": node.core_truth or "",
            "updated_at": touched,
        }
    done, total = _block_counts(node, chosen)
    details = _build_block_details(node, chosen, cfg, goal, unit_status=status)
    passed_b = sum(1 for block in details if block.get("outcome") == "passed")
    revealed_b = sum(1 for block in details if block.get("outcome") == "revealed")
    first_try_b = sum(1 for block in details if block.get("passed_on_first_try"))
    result = state.result if state is not None and isinstance(state.result, dict) else {}
    stored_just = str(result.get("justification") or "").strip()
    locked = status == "not_started" and not _prerequisites_ready(node, course_by_code, nodes_by_code, states)
    return {
        "id": str(node.id),
        "code": node.code,
        "title": node.title,
        "description": node.description or "",
        "outline": node.outline or "",
        "core_truth": node.core_truth or "",
        "patch": False,
        "status": status,
        "mastery": mastery,
        "child_status": child_status_label(status, mastery, locked=locked),
        "completed_blocks": done,
        "total_blocks": total,
        "first_try_blocks_count": first_try_b,
        "revealed_blocks_count": revealed_b,
        "what_was_strong": str(result.get("strong") or "").strip(),
        "what_to_work_on": str(result.get("work_on") or "").strip(),
        "score_justification": _filled_justification(
            stored_just,
            mastery=mastery,
            status=status,
            passed_b=passed_b,
            revealed_b=revealed_b,
            done=done,
            total=total,
        ),
        "student_misconceptions": _student_misconceptions_for(state, sessions),
        "prerequisite_codes": [code for code in _clean_codes(node.prerequisite_codes) if code in everyone_codes],
        "block_details": details,
        "updated_at": touched,
    }


def _course_card(
    load: _CourseCardLoad,
    student: Student,
    goal: KcGoal,
    states: dict[uuid.UUID, KcState],
    cfg: dict,
) -> dict:
    targets = load.targets.get(goal.id, [])
    patches = load.patches.get(goal.id, [])
    everyone = targets + patches
    course_by_code = {node.code: node for node in everyone}
    everyone_codes = set(course_by_code)
    node_sessions = load.sessions_by_node.get((student.id, goal.id), {})
    shared = {
        "goal": goal,
        "cfg": cfg,
        "course_by_code": course_by_code,
        "nodes_by_code": load.nodes_by_code,
        "states": states,
        "everyone_codes": everyone_codes,
    }
    units = [
        _summary_unit(
            node,
            patch=False,
            state=states.get(node.id),
            sessions=node_sessions.get(node.id, []),
            **shared,
        )
        for node in targets
    ]
    target_ids = {node.id for node in targets}
    units.extend(
        _summary_unit(
            node,
            patch=True,
            state=states.get(node.id),
            sessions=node_sessions.get(node.id, []),
            **shared,
        )
        for node in patches
        if node.id not in target_ids
    )
    target_units = [unit for unit in units if not unit.get("patch")]
    known = sum(1 for node in targets if _is_known(states, node))
    conceptual_known = sum(1 for node in targets if node.kc_type == "conceptual" and _is_known(states, node))
    fastest = next(
        (
            node
            for node in targets
            if not _is_settled(states, node)
            and _prerequisites_ready(node, course_by_code, load.nodes_by_code, states)
            and not (node.kc_type == "synthesis" and conceptual_known < SYNTHESIS_CONCEPTUAL_MIN)
        ),
        None,
    )
    cards = [{"role": "fastest", "id": str(fastest.id)}] if fastest is not None else []
    completed = sum(1 for unit in target_units if unit.get("status") == "completed")
    in_progress = sum(1 for unit in target_units if unit.get("status") == "in_progress")
    accomplishments, opportunities = _synthesize_course_insights(units)
    star_roll = stars_from_units(units)
    external: list[str] = []
    for node in targets:
        for code in _clean_codes(node.prerequisite_codes):
            if code not in everyone_codes and code not in external:
                external.append(code)
    timestamps = [
        unit["updated_at"]
        for unit in units
        if isinstance(unit.get("updated_at"), str) and unit["updated_at"]
    ]
    card = _course_shell(goal)
    card.update(
        {
            "component_count": len(target_units),
            "completed_count": completed,
            "known_count": sum(
                1 for unit in target_units if unit.get("status") == "completed" and unit.get("mastery") == "known"
            ),
            "fragile_count": sum(
                1 for unit in target_units if unit.get("status") == "completed" and unit.get("mastery") == "fragile"
            ),
            "in_progress_count": in_progress,
            "not_started_count": sum(1 for unit in target_units if unit.get("status") == "not_started"),
            "percent": _percent(completed, len(target_units)),
            "known_percent": _percent(known, len(targets)),
            "prerequisite_codes": external,
            "unlocked": True,
            "total_blocks_count": sum(int(unit.get("total_blocks") or 0) for unit in target_units),
            "completed_blocks_count": sum(int(unit.get("completed_blocks") or 0) for unit in target_units),
            "first_try_pass_count": sum(int(unit.get("first_try_blocks_count") or 0) for unit in target_units),
            "last_active_at": max(timestamps) if timestamps else None,
            "accomplishments_preview": accomplishments[:3],
            "opportunities_preview": opportunities[:3],
            **star_roll,
            "course_complete": bool(targets) and all(_is_settled(states, node) for node in targets),
            "started": completed + in_progress > 0,
            "current_topic": _current_topic({"units": units, "cards": cards}),
            "tutor": _card_tutor(load, student, goal.id),
        }
    )
    return card


def _ready_course_cards(db: Session, students: list[Student]) -> dict[uuid.UUID, list[dict]]:
    """Started, complete, and stars for every ready course, plus the child-home card fields."""
    if not students:
        return {}
    load = _load_course_cards(db, students)
    configs: dict[uuid.UUID, dict] = {}
    cards: dict[uuid.UUID, list[dict]] = {}
    for student in students:
        cfg = configs.get(student.id)
        if cfg is None:
            cfg = effective_kc_tutor_config(_resolve_cached_profile(load, student))
            configs[student.id] = cfg
        states = load.states.get(student.id, {})
        cards[student.id] = [_course_card(load, student, goal, states, cfg) for goal in load.goals]
    return cards


def tutor_courses(db: Session, *, student_id: uuid.UUID | None = None) -> list[dict]:
    """Ready-course cards. The same counts and stars as progress(), without that payload."""
    student = db.get(Student, student_id) if student_id is not None else None
    if student is None:
        student = db.scalar(select(Student).order_by(Student.created_at))
    if student is not None:
        return _ready_course_cards(db, [student]).get(student.id, [])
    goals = list(db.scalars(select(KcGoal).where(KcGoal.ready.is_(True)).order_by(KcGoal.title)))
    return [_empty_course_card(goal, load_targets(db, goal)) for goal in goals]


def _tutor_public(profile) -> dict:
    return {
        "id": str(profile.id),
        "name": str(getattr(profile, "name", None) or "Default"),
        "description": str(getattr(profile, "description", None) or ""),
        "avatar_preset": str(getattr(profile, "avatar_preset", None) or "default_circle"),
        "avatar_url": getattr(profile, "avatar_url", None),
        "is_default": bool(getattr(profile, "is_default", False)),
    }


def _course_tutor_id(db: Session, student_id: uuid.UUID, goal_id: uuid.UUID) -> str | None:
    """Tutor last stored on a session for this child and course."""
    row = db.scalar(
        select(KcSession)
        .where(
            KcSession.student_id == student_id,
            KcSession.goal_id == goal_id,
            KcSession.tutor_profile_id.is_not(None),
        )
        .order_by(KcSession.updated_at.desc(), KcSession.created_at.desc())
    )
    if row is None or not row.tutor_profile_id:
        return None
    return str(row.tutor_profile_id)


def course_tutor_choice(db: Session, student: Student, goal_id: uuid.UUID) -> dict:
    """Course binding wins. Otherwise the child's preferred tutor is the pre-selection."""
    bound = _course_tutor_id(db, student.id, goal_id)
    if bound:
        profile = resolve_active_profile(db, student=student, profile_id=bound)
        source = "course"
    else:
        profile = resolve_active_profile(db, student=student)
        source = "preferred" if getattr(student, "preferred_tutor_profile_id", None) else "default"
    return {**_tutor_public(profile), "source": source}


def _topic_snapshot(unit: dict | None) -> dict | None:
    if not unit:
        return None
    return {
        "id": unit["id"],
        "code": unit["code"],
        "title": unit["title"],
        "status": unit["status"],
        "child_status": unit.get("child_status") or "Up Next",
        "completed_blocks": int(unit.get("completed_blocks") or 0),
        "total_blocks": int(unit.get("total_blocks") or 0),
    }


def _current_topic(prog: dict) -> dict | None:
    units = [unit for unit in prog.get("units") or [] if not unit.get("patch")]
    active = next((unit for unit in units if unit.get("status") == "in_progress"), None)
    if active is not None:
        return _topic_snapshot(active)
    for card in prog.get("cards") or []:
        if card.get("role") == "fastest":
            match = next((unit for unit in units if unit.get("id") == card.get("id")), None)
            if match is not None:
                return _topic_snapshot(match)
    upcoming = next((unit for unit in units if unit.get("status") == "not_started"), None)
    return _topic_snapshot(upcoming)


def bind_course_tutor(
    db: Session,
    student: Student,
    goal: KcGoal,
    tutor_profile_id: str | int | None,
    *,
    update_preferred: bool = True,
):
    """Remember a tutor on this course's sessions. Other courses keep their own tutor."""
    if tutor_profile_id is None or not str(tutor_profile_id).strip():
        raise HTTPException(status_code=422, detail="Choose a tutor.")
    profile = get_profile_by_id_or_slug(db, tutor_profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Tutor profile not found")
    rows = list(
        db.scalars(
            select(KcSession).where(
                KcSession.student_id == student.id,
                KcSession.goal_id == goal.id,
            )
        )
    )
    for row in rows:
        row.tutor_profile_id = profile.id
    if update_preferred:
        student.preferred_tutor_profile_id = profile.id
    db.flush()
    return profile


def _start_component(db: Session, student: Student, goal: KcGoal, kc_id: uuid.UUID | None) -> KcNode:
    if kc_id is not None:
        node = db.get(KcNode, kc_id)
        if node is None:
            raise HTTPException(status_code=404, detail="That topic is not on this course.")
        return node
    prog = progress(db, goal, student)
    units = [unit for unit in prog.get("units") or [] if not unit.get("patch")]
    chosen_id = None
    for unit in units:
        if unit.get("status") == "in_progress":
            chosen_id = unit["id"]
            break
    if chosen_id is None:
        for card in prog.get("cards") or []:
            if card.get("role") == "fastest":
                chosen_id = card["id"]
                break
    if chosen_id is None and units:
        chosen_id = units[0]["id"]
    if chosen_id is None:
        raise HTTPException(status_code=422, detail="This course has no topics yet.")
    node = db.get(KcNode, uuid.UUID(str(chosen_id)))
    if node is None:
        raise HTTPException(status_code=404, detail="That topic is not on this course.")
    return node


def start_course(
    db: Session,
    student: Student,
    goal: KcGoal,
    *,
    tutor_profile_id: str | int | None = None,
    kc_id: uuid.UUID | None = None,
) -> KcSession:
    """Open the course on its current topic and remember the tutor for this course only."""
    if not goal.ready:
        raise HTTPException(status_code=422, detail="This course is not ready.")
    explicit = tutor_profile_id is not None and str(tutor_profile_id).strip()
    if explicit:
        profile = get_profile_by_id_or_slug(db, tutor_profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Tutor profile not found")
        update_preferred = True
    else:
        bound = _course_tutor_id(db, student.id, goal.id)
        profile = resolve_active_profile(db, student=student, profile_id=bound)
        update_preferred = False
    node = _start_component(db, student, goal, kc_id)
    session = open_session(db, student, goal, node, tutor_profile_id=profile.id)
    bind_course_tutor(db, student, goal, profile.id, update_preferred=update_preferred)
    return session


def learner_roster(db: Session) -> list[dict]:
    """Chooser cards: each child, courses in progress, and stars across ready courses."""
    students = list(db.scalars(select(Student)))
    students.sort(key=lambda student: (student.display_name or "").lower())
    cards = _ready_course_cards(db, students)
    roster: list[dict] = []
    for student in students:
        courses = cards.get(student.id, [])
        in_progress = sum(1 for course in courses if course.get("started") and not course.get("course_complete"))
        stars = sum(int(course.get("stars") or 0) for course in courses)
        roster.append(
            {
                "student": student_out(student).model_dump(mode="json"),
                "in_progress_course_count": in_progress,
                "stars": stars,
                **explorer_progress(stars),
            }
        )
    return roster


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
    if kind == "explanation":
        explanation = ((cfg or {}).get("blocks") or {}).get("explanation") or {}
        if not bool(explanation.get("counts_toward_mastery_score", False)):
            return ""
        return str(data.get("summary_takeaway") or data.get("block_title") or "").strip()
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
            "type_label": BLOCK_BANNER_LABELS.get(kind, kind or "Block"),
            "status": "completed" if finished else "active",
        }
        if stored is not None:
            outcome = str(stored.get("outcome") or "").strip()
            if outcome in {"passed", "revealed", "engaged"}:
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
        kind = str(block.get("type") or "").strip()
        if kind in {"curiosity", "explanation"}:
            block_cfg = ((cfg or {}).get("blocks") or {}).get(kind) or {}
            counts = bool(block_cfg.get("counts_toward_mastery_score", False))
        if not counts:
            continue
        counted = True
        row = by_id.get(_block_key(block, index))
        if row is None or str(row.get("outcome") or "") not in {"passed", "engaged"}:
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
    student = db.get(Student, session.student_id)
    cfg = effective_kc_tutor_config(resolve_active_profile(db, session=session, student=student))
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
    cfg = effective_kc_tutor_config(resolve_active_profile(db, student=student))
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
    everyone_codes = {node.code for node in everyone}
    dependents_by_code: dict[str, list[str]] = {node.code: [] for node in everyone}
    for node in everyone:
        for pcode in _clean_codes(node.prerequisite_codes):
            if pcode in dependents_by_code and node.code not in dependents_by_code[pcode]:
                dependents_by_code[pcode].append(node.code)

    net_data = network(db, goal)

    def unit_row(node: KcNode) -> dict:
        node_sessions = sessions.get(node.id, [])
        state = states.get(node.id)
        chosen = _count_session(node, node_sessions)
        done, total = _block_counts(node, chosen)
        status = _unit_status(state, node, node_sessions)
        mastery = _mastery_label(state, node, node_sessions, cfg)
        b_details = _build_block_details(node, chosen, cfg, goal, unit_status=status)
        passed_b = sum(1 for b in b_details if b.get("outcome") == "passed")
        revealed_b = sum(1 for b in b_details if b.get("outcome") == "revealed")
        first_try_b = sum(1 for b in b_details if b.get("passed_on_first_try"))
        total_attempts = sum(int(b.get("attempts") or 0) for b in b_details)
        if chosen is not None and int(chosen.attempts or 0) > total_attempts:
            total_attempts = int(chosen.attempts or 0)

        res_dict = state.result if state is not None and isinstance(state.result, dict) else {}
        strong_val = str(res_dict.get("strong") or "").strip()
        work_on_val = str(res_dict.get("work_on") or "").strip()
        just_val = str(res_dict.get("justification") or "").strip()
        close_txt = str(res_dict.get("reply") or "").strip()

        if not just_val:
            if mastery == "known":
                just_val = (
                    f"Known — all {passed_b} counting block(s) passed without requiring a reveal."
                    if passed_b > 0
                    else "Known — every counting block in this component passed."
                )
            elif mastery == "fragile":
                just_val = (
                    f"Fragile — {revealed_b} block(s) required a reveal after max retries."
                    if revealed_b > 0
                    else "Fragile — a counting block was revealed during practice."
                )
            elif status == "in_progress":
                just_val = f"In progress — {done} of {total} block(s) completed so far."
            else:
                just_val = f"Not started — {total} block(s) queued in this component."

        p_known_val = (
            round(max(float(state.stability or 0.0), 0.95), 2)
            if mastery == "known" and state is not None
            else (
                round(max(float(state.stability or 0.0), 0.45), 2)
                if mastery == "fragile" and state is not None
                else (0.25 if status == "in_progress" else 0.0)
            )
        )

        started_iso = _iso(chosen.created_at) if chosen is not None else None
        completed_iso = (
            _iso(chosen.updated_at if chosen is not None and chosen.status == "completed" else (state.last_practiced if state is not None and status == "completed" else None))
        )
        updated_iso = _iso(
            (chosen.updated_at if chosen is not None else None)
            or (state.last_practiced if state is not None else None)
        )
        prereqs_in_course = [c for c in _clean_codes(node.prerequisite_codes) if c in everyone_codes]
        locked = status == "not_started" and not prerequisites_ready(node)
        authored_misc = [
            {"wrong_move": str(m.get("wrong_move") or "").strip(), "broken_kc": str(m.get("broken_kc") or "").strip()}
            for m in (node.misconceptions or [])
            if isinstance(m, dict) and str(m.get("wrong_move") or "").strip()
        ]
        student_misc = _student_misconceptions_for(state, node_sessions)

        return {
            "id": str(node.id),
            "code": node.code,
            "title": node.title,
            "description": node.description or "",
            "outline": node.outline or "",
            "core_truth": node.core_truth or "",
            "kc_type": None,
            "summary": _block_summary(_public_blocks(node)),
            "patch": node.id not in target_ids,
            "status": status,
            "mastery": mastery,
            "child_status": child_status_label(status, mastery, locked=locked),
            "practice_bonus": status == "completed" and mastery != "known",
            "p_known": p_known_val,
            "finished_blocks": done,
            "completed_blocks": done,
            "total_blocks": total,
            "passed_blocks_count": passed_b,
            "revealed_blocks_count": revealed_b,
            "first_try_blocks_count": first_try_b,
            "total_attempts": total_attempts,
            "started_at": started_iso,
            "completed_at": completed_iso,
            "updated_at": updated_iso,
            "strengths": strong_val,
            "what_was_strong": strong_val,
            "weaknesses": work_on_val,
            "what_to_work_on": work_on_val,
            "close_text": close_txt,
            "score_justification": just_val,
            "prerequisite_codes": prereqs_in_course,
            "dependent_codes": dependents_by_code.get(node.code, []),
            "misconceptions": authored_misc,
            "student_misconceptions": student_misc,
            "blocks": _stored_block_rows(node, chosen, cfg, include_active=status == "in_progress"),
            "block_details": b_details,
            "rubric": derive_rubric_from_blocks(stored_blocks(node)),
            "result": None if state is None else state.result,
        }

    unit_rows = [unit_row(node) for node in everyone]
    target_units = [u for u in unit_rows if not u["patch"]]
    known_cnt = sum(1 for u in target_units if u["status"] == "completed" and u["mastery"] == "known")
    fragile_cnt = sum(1 for u in target_units if u["status"] == "completed" and u["mastery"] == "fragile")
    completed_cnt = sum(1 for u in target_units if u["status"] == "completed")
    in_progress_cnt = sum(1 for u in target_units if u["status"] == "in_progress")
    not_started_cnt = sum(1 for u in target_units if u["status"] == "not_started")
    total_cnt = len(target_units)
    completion_pct = _percent(completed_cnt, total_cnt)

    total_blocks_cnt = sum(int(u["total_blocks"] or 0) for u in target_units)
    completed_blocks_cnt = sum(int(u["completed_blocks"] or 0) for u in target_units)
    first_try_pass_cnt = sum(int(u["first_try_blocks_count"] or 0) for u in target_units)

    timestamps = [
        u["updated_at"]
        for u in unit_rows
        if isinstance(u.get("updated_at"), str) and u["updated_at"]
    ]
    last_active_iso = max(timestamps) if timestamps else None
    accomplishments, opportunities = _synthesize_course_insights(unit_rows)
    star_roll = stars_from_units(target_units)

    external_prereqs: list[str] = []
    for node in targets:
        for pcode in _clean_codes(node.prerequisite_codes):
            if pcode not in everyone_codes and pcode not in external_prereqs:
                external_prereqs.append(pcode)

    return {
        "course_id": str(goal.id),
        "title": goal.title,
        "description": goal.description or "",
        "audience": goal.audience,
        "kind": goal.kind,
        "minutes": goal.minutes if goal.kind == "time_boxed" else None,
        "course": {
            "id": str(goal.id),
            "code": goal.code,
            "title": goal.title,
            "description": goal.description or "",
            "audience": goal.audience,
            "kind": goal.kind,
            "minutes": goal.minutes if goal.kind == "time_boxed" else None,
        },
        "known": known,
        "total": len(targets),
        "total_count": total_cnt,
        "completed_count": completed_cnt,
        "known_count": known_cnt,
        "fragile_count": fragile_cnt,
        "in_progress_count": in_progress_cnt,
        "not_started_count": not_started_cnt,
        "percent": _percent(known, len(targets)),
        "completion_percent": completion_pct,
        "count_label": f"{known} of {len(targets)}",
        "course_complete": course_complete,
        "next_course": _next_ready_course(db, goal) if course_complete else None,
        "prerequisite_codes": external_prereqs,
        "unlocked": True,
        "total_blocks_count": total_blocks_cnt,
        "completed_blocks_count": completed_blocks_cnt,
        "first_try_pass_count": first_try_pass_cnt,
        **star_roll,
        "last_active_at": last_active_iso,
        "accomplishments": accomplishments,
        "opportunities": opportunities,
        "edges": net_data["edges"],
        "units": unit_rows,
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


def _add_message(
    db: Session,
    session: KcSession,
    role: str,
    content: str,
    *,
    step: int | None = None,
) -> KcMessage:
    current = db.scalar(select(func.max(KcMessage.seq)).where(KcMessage.session_id == session.id)) or 0
    message = KcMessage(
        session_id=session.id,
        role=role,
        content=content,
        seq=int(current) + 1,
        step=int(session.step if step is None else step),
    )
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


def choice_for(node: KcNode, move, substep: str = "") -> dict | None:
    """The two closed picks. Every other move is typed."""
    if str(substep or "") == "summary_check":
        return None
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


def _assistant_on_step(messages: list[KcMessage], step: int) -> bool:
    target = int(step or 0)
    return any(message.role == "assistant" and int(message.step or 0) == target for message in messages)


def _needs_speech(session: KcSession, messages: list[KcMessage]) -> bool:
    """The active block has not been spoken yet."""
    if session.status != "in_progress":
        return False
    return not _assistant_on_step(messages, int(session.step or 0))


def _block_context(db: Session, session: KcSession, node: KcNode | None):
    """The active block, its substep, and whether a short answer still needs a full sentence."""
    student = db.get(Student, session.student_id)
    profile = resolve_active_profile(db, session=session, student=student)
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
                "type_label": BLOCK_BANNER_LABELS.get(kind, kind),
                "title": _block_title(data, node.title),
                "short_title": _block_short_title(data),
                "status": status,
                "outcome": stored.get("outcome"),
                "attempts": int(stored.get("attempts") or 0),
            }
        )
    sub_label = ""
    if substep:
        from app.kc_prompt import format_active_substep_label

        sub_label = format_active_substep_label(blocks[active], substep, None, state)
    active_kind = str(blocks[active].get("type") or "")
    return {
        "total_blocks": total,
        "completed_blocks": completed,
        "completion_pct": round(100 * completed / total),
        "active_block_index": active,
        "active_block_type": active_kind,
        "active_substep": substep,
        "active_substep_label": sub_label,
        "block_progress": progress,
    }


def _tutor_meta_dict(profile) -> dict:
    return {
        "tutor_profile_id": str(getattr(profile, "id", None) or "default"),
        "tutor_name": str(getattr(profile, "name", None) or "Default"),
        "tutor_slug": str(getattr(profile, "slug", None) or getattr(profile, "id", None) or "default"),
        "tutor_description": str(
            profile.description
            if getattr(profile, "description", None) is not None
            else DEFAULT_TUTOR_DESCRIPTION
        ),
        "avatar_preset": normalize_avatar_preset(
            getattr(profile, "avatar_preset", "default_circle"),
            strict=False,
        ),
        "avatar_url": getattr(profile, "avatar_url", None),
    }


def session_out(db: Session, session: KcSession) -> dict:
    node = db.get(KcNode, session.kc_id)
    profile, _goal, messages, _fragment, cfg, blocks, index, block, state = _block_context(db, session, node)
    needs_speech = _needs_speech(session, messages)
    substep = str(state.get("substep") or "")
    choice = None
    if block is not None and session.status == "in_progress" and not needs_speech:
        choice = on_screen_choice(block, substep, state, cfg)
    label = block_step_label(block, index, len(blocks), substep, state) if block is not None else "This step"
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
            {
                "id": str(message.id),
                "role": message.role,
                "content": message.content,
                "seq": message.seq,
                "step": int(message.step or 0),
            }
            for message in messages
        ],
        **_tutor_meta_dict(profile),
        **_session_block_progress(node, session),
    }


def open_session(
    db: Session,
    student: Student,
    goal: KcGoal,
    node: KcNode,
    *,
    tutor_profile_id: str | int | None = None,
) -> KcSession:
    if not goal.ready:
        raise HTTPException(status_code=422, detail="This course is not ready.")
    if not _authored_blocks(node.blocks):
        raise HTTPException(status_code=422, detail="This component has no blocks yet.")
    targets = load_targets(db, goal)
    allowed = {item.id for item in targets + load_patches(db, targets)}
    if node.id not in allowed:
        raise HTTPException(status_code=422, detail="That component is not on this course.")
    active_profile = resolve_active_profile(db, student=student, profile_id=tutor_profile_id)
    existing = db.scalar(
        select(KcSession).where(
            KcSession.student_id == student.id,
            KcSession.goal_id == goal.id,
            KcSession.kc_id == node.id,
            KcSession.status == "in_progress",
        )
    )
    if existing is not None:
        if tutor_profile_id is not None and str(tutor_profile_id).strip():
            existing.tutor_profile_id = active_profile.id
            db.flush()
        elif not existing.tutor_profile_id and student.preferred_tutor_profile_id:
            existing.tutor_profile_id = active_profile.id
            db.flush()
        if _last_block_finished(node, existing):
            _close_finished_walk(db, existing, node)
        return existing
    blocks = stored_blocks(node)
    cfg = effective_kc_tutor_config(active_profile)
    substep = default_substep_for_block(blocks[0], cfg) if blocks else "main"
    session = KcSession(
        student_id=student.id,
        goal_id=goal.id,
        kc_id=node.id,
        tutor_profile_id=active_profile.id if active_profile is not None else None,
        recipe="block_walk",
        step=0,
        status="in_progress",
        active_block_state=initial_block_state(blocks[0], cfg) if blocks else {"substep": substep, "dialogue_turns": 0},
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
    "explanation": [
        ("block_title", "Block title"),
        ("topics", "Topics"),
        ("summary_takeaway", "Summary takeaway"),
    ],
    "passage_ela": [
        ("passage_title", "Passage title"),
        ("passage_genre", "Passage genre"),
        ("passage_text", "Passage text"),
        ("central_idea_question", "Central idea question"),
        ("expected_central_idea", "Expected central idea"),
        ("distractor_detail", "Distractor detail"),
        ("evidence_prompt", "Evidence prompt"),
        ("verbatim_evidence_quotes", "Verbatim evidence quotes"),
        ("analysis_focus", "Analysis focus"),
        ("analysis_question", "Analysis question"),
        ("expected_analysis", "Expected analysis"),
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
    "allow_depth_override_student_length": "Allow depth to override length",
    "elaboration_style_on_question": "Elaboration style",
    "check_in_prompt_style": "Check-in style",
    "end_of_block_summary_style": "End-of-block summary",
    "passage_ela_display_mode": "Passage display",
    "passage_ela_evidence_mode": "Evidence mode",
    "passage_ela_scaffold_style": "Passage scaffold",
    "passage_ela_max_attempts_per_step": "Attempts per step",
    "passage_ela_reread_policy": "Reread policy",
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
    tutor_profile_id: str | int | None = None,
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
    profile = resolve_active_profile(db, session=session, student=student, profile_id=tutor_profile_id)
    messages: list[KcMessage] = []
    cfg = effective_kc_tutor_config(profile)
    blocks = stored_blocks(node)
    index = 0
    block = None
    block_state: dict = {}
    if session is not None and node is not None:
        profile, _goal, messages, _fragment, cfg, blocks, index, block, block_state = _block_context(
            db, session, node
        )
        if tutor_profile_id is not None and str(tutor_profile_id).strip():
            profile = resolve_active_profile(db, session=session, student=student, profile_id=tutor_profile_id)
            cfg = effective_kc_tutor_config(profile)
    elif blocks:
        block = blocks[0]
        block_state = {"substep": default_substep_for_block(block, cfg)}
    substep = str(block_state.get("substep") or "")
    if block is not None and not substep:
        substep = default_substep_for_block(block, cfg)
    from app.kc_model import derive_rubric_from_blocks

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
    opening_turn = session is None or not _assistant_on_step(messages, index)
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
    all_blocks_summary = " | ".join(
        f"{bt}: " + ", ".join(f"{k}={v}" for k, v in ((cfg.get("blocks") or {}).get(bt) or {}).items())
        for bt in ALL_BLOCK_TYPES
    )
    max_retries_val = (
        str(max_retries_for_block(block, cfg, goal)) if block is not None else ""
    )

    tutor_meta = _tutor_meta_dict(profile)
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
            _row("Tutor profile", f"{tutor_meta['tutor_name']} ({tutor_meta['tutor_slug']})", _LAYER_3),
            _row("Tutor description", tutor_meta["tutor_description"], _LAYER_3),
            _row("Tutor avatar", tutor_meta["avatar_preset"], _LAYER_3),
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
            _row(f"All {len(ALL_BLOCK_TYPES)} block configs", all_blocks_summary, _LAYER_4),
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
            _row(
                "Topic index",
                "" if session is None else str(int(block_state.get("topic_index") or 0)),
                _LAYER_1,
            ),
            _row(
                "Elaboration turns",
                "" if session is None else str(int(block_state.get("elaboration_turns") or 0)),
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
    age = student.age if student is not None and isinstance(student.age, int) else None
    safety = read_ai_safety(db)
    latest = latest_safety_flag(db, session.id) if session is not None else "none"
    return [
        _row("Safety text", safety_text(safety, age=age), "Safety"),
        _row("Latest safety flag", latest, "Safety"),
        *rows,
    ]


def prompt_for(db: Session, session: KcSession) -> dict:
    student = _student_or_404(db, session.student_id)
    goal = _course_or_404(db, session.goal_id)
    node = _node_or_404(db, session.kc_id)
    profile, _goal, messages, fragment, _cfg, blocks, index, block, block_state = _block_context(db, session, node)
    substep = str(block_state.get("substep") or "")
    state = _state_row(db, student, node)
    opening = not _assistant_on_step(messages, index)
    others = _others_known(db, student, goal, node)
    settled = state is not None and state.status in {"known", "fragile"}
    unit_complete = session.status == "completed"
    course_complete = unit_complete and settled and others
    prereq = _prerequisite_status(db, student, node)
    transition = None
    if opening and block is not None and index > 0:
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
        safety=read_ai_safety(db),
    )
    bundle["recipe"] = session.recipe
    bundle["step"] = session.step
    bundle["step_label"] = block_step_label(active, index, max(len(blocks), 1), substep, block_state)
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


def _choice_answer_text(answer: str, choice: dict) -> str:
    """Selected label on the first line, then the options that were on screen.

    Grading reads only the first line. Chats already stored are left unchanged.
    """
    selected = answer.splitlines()[0].strip()
    trailing = [line.strip() for line in answer.splitlines()[1:] if line.strip()]
    options: list[str] = []
    for item in choice.get("choices") or []:
        if not isinstance(item, dict):
            continue
        letter = str(item.get("id") or "").strip()
        text = str(item.get("text") or "").strip()
        if letter and text:
            options.append(f"{letter}. {text}")
        elif text:
            options.append(text)
    if not options:
        return answer
    return "\n".join([selected, *options, *trailing])


def turn(db: Session, session: KcSession, answer: str) -> dict:
    """Store the child's answer and return the layer bundle. Scoring waits for the decision."""
    if session.status == "completed":
        raise HTTPException(status_code=422, detail="This component session is already finished.")
    cleaned = answer.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Write an answer first.")
    node = db.get(KcNode, session.kc_id)
    _profile, _goal, messages, _fragment, cfg, _blocks, _index, block, state = _block_context(db, session, node)
    substep = str(state.get("substep") or "")
    choice = None
    if block is not None and not _needs_speech(session, messages):
        choice = on_screen_choice(block, substep, state, cfg)
    content = _choice_answer_text(cleaned, choice) if choice else cleaned
    _add_message(db, session, "user", content)
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
    try:
        safety_flag = normalize_safety_flag(body.get("safety_flag", "none"))
    except AiSafetyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
    if safety_flag != "none":
        stored = _add_message(db, session, "assistant", reply, step=index)
        record_safety_event(
            db,
            student_id=session.student_id,
            kc_session_id=session.id,
            kc_message_id=stored.id,
            course_id=session.goal_id,
            node_id=session.kc_id,
            tutor_profile_id=session.tutor_profile_id,
            category=safety_flag,
            child_message=answer,
            tutor_reply=reply,
        )
        session.updated_at = _now()
        result = session_out(db, session)
        result["reply"] = reply
        result["passed"] = False
        result["unit_complete"] = False
        result["course_complete"] = False
        result["safety_flag"] = safety_flag
        return result
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
    if isinstance(generated, dict) and generated.get("choices") and resolution.next_step == index:
        next_state["generated_mcq"] = generated
    session.active_block_state = next_state
    session.block_results = list(resolution.block_results)
    if resolution.unit_complete:
        session.status = "completed"
        _save_component_result(db, session, node, body, reply)
    elif _last_block_finished(node, session):
        _close_finished_walk(db, session, node, reply, body)
    session.updated_at = _now()
    _add_message(db, session, "assistant", reply, step=index)
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


def _chat_step_label(
    node: KcNode | None,
    step: int,
    goal: KcGoal | None = None,
    active_block_state: dict | None = None,
) -> str:
    del goal
    blocks = stored_blocks(node)
    if not blocks:
        return "This step"
    index = min(max(step, 0), len(blocks) - 1)
    state = active_block_state if isinstance(active_block_state, dict) else {}
    substep = str(state.get("substep") or "").strip() or default_substep_for_block(
        blocks[index], effective_kc_tutor_config(None)
    )
    return block_step_label(blocks[index], index, len(blocks), substep, state)


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


def _chat_summary(
    session: KcSession,
    *,
    safety_event_count: int = 0,
    unreviewed_safety_count: int = 0,
) -> dict:
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
        "step_label": _chat_step_label(node, session.step, session.goal, session.active_block_state),
        "status": session.status,
        "score": session.score,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(session.messages),
        "safety_event_count": safety_event_count,
        "unreviewed_safety_count": unreviewed_safety_count,
    }


def kc_chat_summaries(db: Session, student_id: uuid.UUID | None) -> list[dict]:
    stmt = select(KcSession).options(*_chat_load_options()).order_by(KcSession.updated_at.desc())
    if student_id is not None:
        stmt = stmt.where(KcSession.student_id == student_id)
    rows = db.scalars(stmt).unique().all()
    counts = safety_counts(db, [row.id for row in rows])
    summaries = []
    for row in rows:
        total, unreviewed = counts.get(row.id, (0, 0))
        summaries.append(
            _chat_summary(row, safety_event_count=total, unreviewed_safety_count=unreviewed)
        )
    return summaries


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
        "step_label": _chat_step_label(node, session.step, session.goal, session.active_block_state),
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
        "token_usage": session_token_usage(db, session.id),
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
    db: Session,
    session: KcSession,
    content: str,
    generated_mcq: dict | None = None,
    safety_flag: str = "none",
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
    try:
        flag = normalize_safety_flag(safety_flag)
    except AiSafetyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    stored = _add_message(db, session, "assistant", text)
    child_message = next((message.content for message in reversed(messages) if message.role == "user"), "")
    if flag != "none":
        record_safety_event(
            db,
            student_id=session.student_id,
            kc_session_id=session.id,
            kc_message_id=stored.id,
            course_id=session.goal_id,
            node_id=session.kc_id,
            tutor_profile_id=session.tutor_profile_id,
            category=flag,
            child_message=child_message,
            tutor_reply=text,
        )
    session.updated_at = _now()
    result = session_out(db, session)
    result["safety_flag"] = flag
    return result


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



def _catalog_field_lines(key: str, label: str, value: object) -> list[str]:
    """One catalog field, omitted when Push draft would write it empty."""
    if key == "choices":
        return _choice_lines(value)
    if key == "steps":
        return _step_lines(value)
    if key == "topics":
        return _topic_lines(value)
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


def _topic_lines(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        points = str(item.get("key_points") or "").strip()
        examples = str(item.get("examples_or_analogies") or "").strip()
        head = title or f"Topic {index}"
        rows.append(f"{index}. {head}")
        if explanation:
            rows.append(f"Explanation: {explanation}")
        if points:
            rows.append(f"Key points: {points}")
        if examples:
            rows.append(f"Examples: {examples}")
    return ["Topics:", *rows] if rows else []


def _block_field_lines(raw: object) -> list[str]:
    """Each block, in order, with its type label and the filled catalog fields."""
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
        for key, label in BLOCK_FIELDS.get(kind, ()):
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



def _creator_standard_codes(goal: KcGoal, node: KcNode) -> list[str] | None:
    """None when the course has no standard. An empty list marks an extension."""
    if not read_statements(goal.standards):
        return None
    return [str(code) for code in (node.standards or []) if str(code).strip()]


def creator_prompt_for(
    db: Session,
    node: KcNode,
    message: str,
    model: str,
    allowed_block_types: list[str] | None = None,
) -> dict:
    from app.kc_model import creator_bundle
    from app.kc_pipeline import position_text

    goal, ordered = course_of_node(db, node)
    siblings = _sibling_rows(db, goal, node, ordered)
    by_code = {item["code"]: item for item in siblings}
    previous = _latest_draft(_creator_rows(db, node.id))
    blueprint = goal.blueprint if isinstance(goal.blueprint, dict) else {}
    builds_on = [by_code[code] for code in _clean_codes(node.prerequisite_codes) if code in by_code]
    leads_to = [item for item in siblings if node.code in item["prerequisite_codes"]]
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
            siblings=siblings,
            course_brief=goal.brief or "",
            outcomes=list(blueprint.get("outcomes") or []),
            standard_codes=_creator_standard_codes(goal, node),
            position=position_text(blueprint, node.code) if blueprint else "",
            builds_on=builds_on,
            leads_to=leads_to,
            previous=previous,
            message=message,
            model=model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _sibling_rows(db: Session, goal: KcGoal, node: KcNode, ordered: list[KcNode]) -> list[dict]:
    """The other components with their codes, titles, and one-line summaries."""
    from app.kc_pipeline import components_of

    blueprint = goal.blueprint if isinstance(goal.blueprint, dict) else {}
    planned = {item["code"]: item.get("summary") or "" for item in components_of(blueprint)} if blueprint else {}
    patches = load_patches(db, ordered)
    rows: list[dict] = []
    for item in [*ordered, *patches]:
        if item.id == node.id:
            continue
        rows.append(
            {
                "code": item.code,
                "title": item.title,
                "summary": planned.get(item.code) or _first_sentence(item.description or ""),
                "prerequisite_codes": _clean_codes(item.prerequisite_codes),
            }
        )
    return rows


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
