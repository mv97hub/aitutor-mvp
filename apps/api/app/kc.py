"""Knowledge-component courses, drafts, and the kid tutor loop.

A studio chat can draft. Nothing from that chat is stored until push.
An edit replaces one component. Kid chat, the catalog, and CreateCourse
do not call this module.
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.kc_prompt import build_kc_prompt, recipe_name, step_labels
from app.models import (
    KcEdge,
    KcGoal,
    KcMessage,
    KcNode,
    KcSession,
    KcState,
    Student,
)
from app.tutor_profile import load_profile

AUDIENCES = ("6-8", "9-11", "12-14", "15-17")
KINDS = ("mastery", "time_boxed", "curiosity")
KC_TYPES = ("factual", "procedural", "conceptual", "causal", "synthesis")
TYPE_KEYS = {
    "factual": ("fact", "retrieval_question"),
    "procedural": ("steps", "blanked_step", "solo_problem", "solo_check"),
    "conceptual": ("case_a", "case_b", "prediction", "rule"),
    "causal": ("decision_point", "flawed_claim", "causal_chain"),
    "synthesis": ("mixes", "faulty_plan"),
}
FINAL_STEP = {"factual": 0, "procedural": 2, "conceptual": 2, "causal": 2, "synthesis": 0}
ENCOMPASS_WEIGHT = 0.25
COUNT_WORDS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
}
CARD_LABELS = {
    "fastest": "Fastest path",
    "patch": "Foundation patch",
    "stretch": "Stretch",
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
    return bool(re.search(r"\b(not|never|no|isnt|doesnt|dont|cannot|cant)\b", text))


def matches_phrase(answer: str, phrase: str) -> bool:
    normalized_answer = _norm(answer)
    normalized_phrase = _norm(phrase)
    if not normalized_answer or not normalized_phrase:
        return False
    if len(normalized_phrase) <= 4:
        return bool(re.search(rf"\b{re.escape(normalized_phrase)}\b", normalized_answer))
    if normalized_phrase in normalized_answer:
        return True
    if len(normalized_answer) >= 8 and normalized_answer in normalized_phrase:
        return True
    phrase_numbers = re.findall(r"\d+", normalized_phrase)
    answer_numbers = re.findall(r"\d+", normalized_answer)
    if phrase_numbers and set(phrase_numbers) <= set(answer_numbers) and len(normalized_answer.split()) <= 8:
        return True
    answer_words = [word for word in normalized_answer.split() if len(word) > 3]
    if len(answer_words) >= 3 and all(word in normalized_phrase for word in answer_words):
        return True
    phrase_words = [word for word in normalized_phrase.split() if len(word) > 3]
    if not phrase_words:
        return False
    hits = sum(1 for word in phrase_words if word in normalized_answer)
    return hits >= max(1, math.ceil(0.6 * len(phrase_words)))


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
    if len(checks) > 3:
        raise HTTPException(status_code=422, detail="A component has at most three rubric checks.")
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
        if not wrong or not broken:
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


def _summary(node: KcNode, *, target: bool) -> dict:
    return {
        "id": str(node.id),
        "code": node.code,
        "title": node.title,
        "kc_type": node.kc_type,
        "target": target,
    }


def _detail(node: KcNode, *, target: bool) -> dict:
    body = _summary(node, target=target)
    body.update(
        {
            "core_truth": node.core_truth or "",
            "rubric": list(node.rubric or []),
            "misconceptions": list(node.misconceptions or []),
            "prerequisite_codes": list(node.prerequisite_codes or []),
            "encompasses_codes": list(node.encompasses_codes or []),
            "type_fields": dict(node.type_fields or {}),
        }
    )
    return body


def course_out(db: Session, goal: KcGoal) -> dict:
    targets = load_targets(db, goal)
    patches = load_patches(db, targets)
    return {
        "id": str(goal.id),
        "code": goal.code,
        "title": goal.title,
        "description": goal.description or "",
        "audience": goal.audience,
        "kind": goal.kind,
        "minutes": goal.minutes,
        "ready": goal.ready,
        "updated_at": goal.updated_at.isoformat(),
        "components": [_detail(node, target=True) for node in targets],
        "patches": [_detail(node, target=False) for node in patches],
    }


def gaps_for(node: KcNode, codes: set[str]) -> list[str]:
    missing: list[str] = []
    if not node.kc_type:
        missing.append("no type")
    if not (node.core_truth or "").strip():
        missing.append("no truth")
    rubric = [item for item in (node.rubric or []) if str(item).strip()]
    if not rubric:
        missing.append("no rubric check")
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
) -> KcGoal:
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
    goal.updated_at = _now()
    db.flush()
    return goal


def _count_requested(message: str) -> int | None:
    lowered = message.lower()
    for word, count in COUNT_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            return count
    match = re.search(r"\b(\d{1,2})\b", lowered)
    if not match:
        return None
    count = int(match.group(1))
    if 2 <= count <= 12:
        return count
    return None


def _shorten(text: str) -> str:
    words = text.strip(" .").split()
    return " ".join(words[:8])[:80].strip()


def _titles_from_message(message: str) -> list[str]:
    titles = []
    for raw in message.splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", raw).strip()
        if line and len(line) <= 80:
            titles.append(line)
    if len(titles) >= 2:
        return titles[:12]
    return []


def _titles_from_description(description: str, title: str, count: int | None) -> list[str]:
    text = (description or "").strip() or (title or "Component")
    parts = [
        _shorten(part)
        for part in re.split(r"[.;]\s+|,\s+|\s+\band\b\s+", text)
        if len(part.strip()) > 2
    ]
    parts = [part for part in parts if part]
    if not parts:
        parts = [_shorten(title or "Component")]
    if count is None:
        return parts[:6]
    while len(parts) < count:
        parts.append(f"{_shorten(title or 'Component')} {len(parts) + 1}")
    return parts[:count]


def draft_course(goal: KcGoal, message: str) -> dict:
    """Return a component list. This does not write."""
    titles = _titles_from_message(message)
    if not titles:
        titles = _titles_from_description(goal.description, goal.title, _count_requested(message))
    taken: set[str] = set()
    components = []
    for title in titles:
        code = slug_code(title, taken)
        taken.add(code)
        components.append({"code": code, "title": title})
    return {
        "reply": "Draft component list. Nothing is saved until you push it.",
        "draft": {"kind": "course", "components": components},
    }


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
        if node is None:
            node = KcNode(code=code, title=title)
            db.add(node)
            db.flush()
            by_code[code] = node
        else:
            node.title = title
            node.updated_at = _now()
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


def apply_component(db: Session, node: KcNode, body: dict) -> KcNode:
    """Replace this component and the edges it owns. Other components stay."""
    kc_type = body.get("kc_type")
    if kc_type not in KC_TYPES:
        raise HTTPException(status_code=422, detail="Type is factual, procedural, conceptual, causal, or synthesis.")
    if "title" in body and str(body.get("title") or "").strip():
        node.title = str(body["title"]).strip()
    node.kc_type = kc_type
    node.core_truth = str(body.get("core_truth") or "").strip()
    node.rubric = _clean_rubric(body.get("rubric") or [])
    node.misconceptions = _clean_misconceptions(body.get("misconceptions") or [])
    node.prerequisite_codes = _clean_codes(body.get("prerequisite_codes") or [])
    node.encompasses_codes = _clean_codes(body.get("encompasses_codes") or [])
    node.type_fields = _clean_type_fields(kc_type, body.get("type_fields") or {})
    node.updated_at = _now()
    _sync_edges(db, node)
    _unready(db, node.id)
    db.flush()
    return node


def _infer_type(title: str, message: str) -> str:
    text = f"{title} {message}".lower()
    if any(word in text for word in ("synthesis", "mix", "rookie", "faulty plan")):
        return "synthesis"
    if any(word in text for word in ("why ", "because", "caused", "decision", "history")):
        return "causal"
    if any(word in text for word in ("step", "calculate", "solve", "find the", "procedure")):
        return "procedural"
    if any(word in text for word in ("versus", " vs", "contrast", "principle", "difference")):
        return "conceptual"
    if any(word in text for word in ("fact", "define", "what is", "recall")):
        return "factual"
    return "conceptual"


def _first_sentence(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    return re.split(r"(?<=[.])\s+", cleaned, maxsplit=1)[0].strip()


def _fields_for(kc_type: str, title: str, description: str, mixes: list[str]) -> dict:
    sentence = _first_sentence(description) or title
    if kc_type == "factual":
        return {
            "fact": sentence,
            "retrieval_question": f"What should you remember about {title}?",
        }
    if kc_type == "procedural":
        return {
            "steps": [f"Set up {title}.", f"Finish {title}."],
            "blanked_step": 1,
            "solo_problem": f"Solve a new case of {title} on your own.",
            "solo_check": sentence,
        }
    if kc_type == "conceptual":
        return {
            "case_a": f"A case that fits {title}.",
            "case_b": f"A case that does not fit {title}.",
            "prediction": f"Which case shows {title}?",
            "rule": sentence,
        }
    if kc_type == "causal":
        return {
            "decision_point": f"Someone is about to decide {title}.",
            "flawed_claim": f"{title} happens for the opposite reason.",
            "causal_chain": sentence,
        }
    return {
        "mixes": mixes[:2],
        "faulty_plan": f"A rookie mixes the earlier ideas and gets {title} backwards.",
    }


def draft_component(goal: KcGoal, node: KcNode, ordered: list[KcNode], message: str) -> dict:
    """Draft this component only. This does not write."""
    kc_type = _infer_type(node.title, message)
    earlier = []
    for item in ordered:
        if item.id == node.id:
            break
        earlier.append(item)
    previous = earlier[-1] if earlier else None
    mixes = [item.code for item in earlier[-2:]]
    if kc_type == "synthesis" and len(mixes) < 2:
        mixes = [item.code for item in ordered if item.id != node.id][:2]
    prerequisites = mixes if kc_type == "synthesis" else ([previous.code] if previous else [])
    encompasses = [previous.code] if previous and kc_type == "procedural" else []
    misconceptions = []
    if previous and kc_type in ("conceptual", "causal"):
        misconceptions.append(
            {
                "wrong_move": f"{node.title} is the opposite of the core idea",
                "broken_kc": previous.code,
            }
        )
    draft = {
        "kind": "component",
        "id": str(node.id),
        "code": node.code,
        "title": node.title,
        "kc_type": kc_type,
        "core_truth": _first_sentence(goal.description) or f"The core idea of {node.title}.",
        "rubric": [f"States the idea of {node.title}"],
        "misconceptions": misconceptions,
        "prerequisite_codes": prerequisites,
        "encompasses_codes": encompasses,
        "type_fields": _fields_for(kc_type, node.title, goal.description, mixes),
    }
    return {
        "reply": f"Draft for {node.title} only. Other components stay as they are. Nothing is saved until you push it.",
        "draft": draft,
    }


def structure(db: Session, goal: KcGoal) -> dict:
    targets = load_targets(db, goal)
    codes = set(_nodes_by_code(db))
    groups: dict[str, list[dict]] = {name: [] for name in (*KC_TYPES, "unset")}
    for position, node in enumerate(targets, start=1):
        row = {
            "id": str(node.id),
            "code": node.code,
            "title": node.title,
            "kc_type": node.kc_type,
            "position": position,
            "missing": gaps_for(node, codes),
        }
        groups[node.kc_type or "unset"].append(row)
    ordered = []
    for name in (*KC_TYPES, "unset"):
        if groups[name]:
            ordered.append({"kc_type": name, "components": groups[name]})
    return {"course_id": str(goal.id), "groups": ordered}


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


def _ring_status(states: dict[uuid.UUID, KcState], node: KcNode) -> str:
    row = states.get(node.id)
    if row is None or row.status == "unknown":
        return "not_started"
    return row.status


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
    states = _state_map(db, student.id, [node.id for node in everyone])
    known = sum(1 for node in targets if _is_known(states, node))
    conceptual_known = sum(
        1 for node in targets if node.kc_type == "conceptual" and _is_known(states, node)
    )

    def prerequisites_known(node: KcNode) -> bool:
        for code in _clean_codes(node.prerequisite_codes):
            other = by_code.get(code) or _nodes_by_code(db).get(code)
            if other is None or not _is_known(states, other):
                return False
        return True

    def offered(node: KcNode) -> bool:
        if _is_known(states, node):
            return False
        if not prerequisites_known(node):
            return False
        if node.kc_type == "synthesis" and conceptual_known < 2:
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
                "reason": "Prerequisites are known, and this is the next component on the course.",
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
        reason = "A later component whose prerequisites are known."
        if stretch.kc_type == "synthesis":
            reason = "A synthesis component. It waits until two conceptual components are known."
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
    return {
        "course_id": str(goal.id),
        "title": goal.title,
        "kind": goal.kind,
        "minutes": goal.minutes if goal.kind == "time_boxed" else None,
        "known": known,
        "total": len(targets),
        "count_label": f"{known} of {len(targets)}",
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
        "cards": cards[:3],
    }


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
            return str(fields.get("retrieval_question") or "What is the fact?")
        return f"Yes. {fields.get('fact') or node.core_truth}"
    if kind == "procedural":
        steps = [str(item) for item in (fields.get("steps") or [])]
        blank = int(fields.get("blanked_step") or 0)
        if step <= 0:
            lines = " ".join(f"{index + 1}. {text}" for index, text in enumerate(steps))
            return f"Here is the worked example. {lines} What did this example do?"
        if step == 1:
            shown = []
            for index, text in enumerate(steps):
                shown.append(f"{index + 1}. ___" if index == blank else f"{index + 1}. {text}")
            return "Fill the blank step. " + " ".join(shown)
        return str(fields.get("solo_problem") or "Solve it on your own.")
    if kind == "conceptual":
        if step <= 0:
            return (
                f"Case one: {fields.get('case_a')} "
                f"Case two: {fields.get('case_b')} "
                f"{fields.get('prediction')}"
            )
        if step == 1:
            return (
                f"Look at the contrast. Case one: {fields.get('case_a')} "
                f"Case two: {fields.get('case_b')} What is different?"
            )
        return "State the rule."
    if kind == "causal":
        if step <= 0:
            return f"Decision point: {fields.get('decision_point')} What is at stake?"
        if step == 1:
            return f"Mark this claim: {fields.get('flawed_claim')}"
        return "Defend the causal chain."
    if kind == "synthesis":
        mixes = fields.get("mixes") or []
        joined = " and ".join(str(item) for item in mixes) or "two earlier components"
        if step <= 0:
            return (
                f"A rookie mixes {joined} and says: {fields.get('faulty_plan')} "
                "Correct the plan."
            )
        return f"Yes. The plan that holds is: {node.core_truth}"
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
            return ["wrong", "flawed", "false", "not true", "no"]
        return [str(fields.get("causal_chain") or node.core_truth)]
    if kind == "synthesis" and step == 0:
        return [node.core_truth]
    return None


def _step_passes(node: KcNode, step: int, answer: str) -> bool:
    expects = _expects(node, step)
    if expects is None:
        return len(_norm(answer)) >= 2
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
        return f"Yes. {fields.get('fact') or node.core_truth}"
    if node.kc_type == "synthesis":
        return f"Yes. The plan that holds is: {node.core_truth}"
    return f"That holds. {node.core_truth}"


def session_out(db: Session, session: KcSession) -> dict:
    node = db.get(KcNode, session.kc_id)
    labels = step_labels(node.kc_type if node else None)
    index = min(session.step, len(labels) - 1)
    messages = db.scalars(
        select(KcMessage).where(KcMessage.session_id == session.id).order_by(KcMessage.seq)
    )
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
        "step_label": labels[index],
        "status": session.status,
        "score": session.score,
        "redirect": None
        if redirect is None
        else {"id": str(redirect.id), "code": redirect.code, "title": redirect.title},
        "messages": [
            {"id": str(message.id), "role": message.role, "content": message.content, "seq": message.seq}
            for message in messages
        ],
    }


def open_session(db: Session, student: Student, goal: KcGoal, node: KcNode) -> KcSession:
    if not goal.ready:
        raise HTTPException(status_code=422, detail="This course is not ready.")
    if not node.kc_type:
        raise HTTPException(status_code=422, detail="This component has no type yet.")
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
        return existing
    session = KcSession(
        student_id=student.id,
        goal_id=goal.id,
        kc_id=node.id,
        recipe=recipe_name(node.kc_type),
        step=0,
        status="in_progress",
    )
    db.add(session)
    db.flush()
    _add_message(db, session, "assistant", step_text(node, 0))
    return session


def prompt_for(db: Session, session: KcSession) -> dict:
    student = _student_or_404(db, session.student_id)
    goal = _course_or_404(db, session.goal_id)
    node = _node_or_404(db, session.kc_id)
    profile = load_profile(db)
    text = step_text(node, session.step)
    return {
        "system_prompt": build_kc_prompt(
            student=student,
            profile=profile,
            node=node,
            goal=goal,
            step=session.step,
            step_text=text,
        ),
        "recipe": session.recipe,
        "step": session.step,
        "step_label": step_labels(node.kc_type)[min(session.step, len(step_labels(node.kc_type)) - 1)],
    }


def turn(db: Session, session: KcSession, answer: str) -> dict:
    if session.status == "completed":
        raise HTTPException(status_code=422, detail="This component session is already finished.")
    cleaned = answer.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Write an answer first.")
    node = _node_or_404(db, session.kc_id)
    _add_message(db, session, "user", cleaned)
    signature = _matched_signature(node, cleaned)
    passed = False
    if signature is not None:
        broken = _nodes_by_code(db).get(str(signature.get("broken_kc") or ""))
        state = _get_state(db, session.student_id, node.id)
        state.status = "fragile"
        state.last_practiced = _now()
        session.score = 0
        session.status = "completed"
        session.redirect_kc_id = broken.id if broken is not None else None
        title = broken.title if broken is not None else str(signature.get("broken_kc") or "the earlier component")
        truth = broken.core_truth if broken is not None and broken.core_truth else ""
        reply = (
            f"That answer matches this wrong move: {signature.get('wrong_move')}. "
            f"The component that is actually broken is {title}. {truth} "
            "The next card opens that component."
        ).strip()
    elif _step_passes(node, session.step, cleaned):
        final = FINAL_STEP.get(node.kc_type or "", 0)
        if session.step >= final:
            state = _get_state(db, session.student_id, node.id)
            state.status = "known"
            state.stability = round(max(float(state.stability or 0), 1.0), 2)
            state.last_practiced = _now()
            _bump_encompassed(db, session.student_id, node)
            session.score = 100
            session.status = "completed"
            labels = step_labels(node.kc_type)
            session.step = min(session.step + 1, len(labels) - 1)
            passed = True
            reply = _pass_reply(node)
        else:
            session.step += 1
            reply = step_text(node, session.step)
    else:
        session.attempts += 1
        reply = (
            f"Not yet. {node.core_truth} "
            "That explanation is the one retry. Answer this same step again."
        ).strip()
    session.updated_at = _now()
    _add_message(db, session, "assistant", reply)
    body = session_out(db, session)
    body["reply"] = reply
    body["passed"] = passed
    return body
