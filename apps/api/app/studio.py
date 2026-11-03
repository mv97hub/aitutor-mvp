"""CreateCourse studio: preferences, the typed patch, and the model row.

The tutor seed does not import this module. Patches are checked before they
are written. A model reply can describe a change, and the tree stays as it
is until that patch is accepted.
"""

from __future__ import annotations

import copy
import hmac
import json
import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.models import (
    StudioCourse,
    StudioMessage,
    StudioMove,
    StudioQuest,
    StudioQuestClose,
    StudioSettings,
    StudioUnit,
)
from app.schemas import (
    StudioCloseOut,
    StudioCourseOut,
    StudioCourseSummary,
    StudioMessageOut,
    StudioMoveOut,
    StudioPhaseOut,
    StudioQuestOut,
    StudioStripOut,
    StudioUnitOut,
    StudioViewOut,
)

CLOSE_STYLES = ("one", "several")
ANSWER_STYLES = ("multiple_choice", "essay", "mixed")
CHOICE_MODES = ("predefined", "dynamic")
DEPTHS = ("survey", "standard", "go_deep")
QUIZ_MINUTES = (2, 5, 10)
AGE_BANDS = ("6-8", "9-11", "12-14", "15-17")
STUDIO_MODELS = ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini")
DEFAULT_STUDIO_MODEL = "gpt-4o-mini"
SCHEMA_VERSION = 2
SETTINGS_ID = "default"
STUDIO_TEMPERATURE = 0.4
DELETE_PASSWORD = "BulmerGardens"

COURSE_CODE = re.compile(r"^[A-Z][A-Z0-9]{1,15}$")
NODE_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){1,6}$")
KINDS = ("course", "unit", "quest", "move")
OPS = ("add", "update", "remove")
PARENT_KIND = {"unit": "course", "quest": "unit", "move": "quest"}
TEXT_LIMITS = {
    "title": 240,
    "audience": 500,
    "focus": 2000,
    "theme": 240,
    "sources": 500,
    "learning_goal": 2000,
    "success_criterion": 2000,
    "intent": 2000,
}
COURSE_FIELDS = ("title", "audience", "focus", "theme", "depth", "sources", "close_default")
NODE_FIELDS = ("title", "learning_goal", "success_criterion", "position")

_MISSING = object()

def _close_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "close_style": {"type": "string", "enum": ["one", "several"]},
            "answer_style": {
                "type": "string",
                "enum": ["multiple_choice", "essay", "mixed"],
            },
            "choice_mode": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "enum": ["predefined", "dynamic"]},
                ]
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
            "intent": {"type": "string"},
        },
        "required": ["close_style", "answer_style", "choice_mode", "items", "intent"],
    }


def _operation_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "op": {"type": "string", "enum": ["add", "update", "remove"]},
            "kind": {"type": "string", "enum": ["course", "unit", "quest", "move"]},
            "code": {"type": "string"},
            "parent": {
                "type": ["string", "null"],
                "description": (
                    "Parent code when adding a unit, quest, or move. "
                    "Null on update. An update names the item by its own code and must not send a parent."
                ),
            },
            "title": {"type": ["string", "null"]},
            "learning_goal": {"type": ["string", "null"]},
            "success_criterion": {"type": ["string", "null"]},
            "position": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
            "audience": {"type": ["string", "null"]},
            "focus": {"type": ["string", "null"]},
            "theme": {"type": ["string", "null"]},
            "depth": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "enum": ["survey", "standard", "go_deep"]},
                ]
            },
            "sources": {"type": ["string", "null"]},
            "close": {"anyOf": [{"type": "null"}, _close_schema()]},
            "close_default": {"anyOf": [{"type": "null"}, _close_schema()]},
        },
        "required": [
            "op",
            "kind",
            "code",
            "parent",
            "title",
            "learning_goal",
            "success_criterion",
            "position",
            "audience",
            "focus",
            "theme",
            "depth",
            "sources",
            "close",
            "close_default",
        ],
    }


STUDIO_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": (
                "What the creator reads. Say which framework a suggestion comes from. "
                "Do not say the course was saved or that the structure was accepted."
            ),
        },
        "patch": {
            "description": "Null when nothing should change. Otherwise typed add, update, or remove operations.",
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "operations": {
                            "type": "array",
                            "maxItems": 40,
                            "items": _operation_schema(),
                        }
                    },
                    "required": ["operations"],
                },
            ],
        },
    },
    "required": ["reply", "patch"],
}


class StudioError(Exception):
    def __init__(self, field: str, message: str, status: int = 422, plain: str | None = None) -> None:
        self.field = field
        self.message = message
        self.status = status
        self.plain = plain if plain is not None else f"{field}: {message}"
        super().__init__(self.plain)


POSITION_REASON = "Position must be an integer from 1 to 200."


def rejection_reply(_model_reply: str, reason: str) -> str:
    """The chat shows this reason alone. The model's claim that it saved is dropped."""
    return reason.strip()


class _Node:
    def __init__(self, kind: str, code: str, parent: str | None, position: int) -> None:
        self.kind = kind
        self.code = code
        self.parent = parent
        self.position = position


def default_close() -> dict:
    return {
        "close_style": "one",
        "answer_style": "essay",
        "choice_mode": None,
        "items": [],
        "intent": "",
    }


def default_preferences() -> dict:
    return {
        "close_default": default_close(),
        "depth": "standard",
        "quiz_minutes": 5,
        "audience": "",
        "theme": "",
        "sources": "",
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _field(op: dict, key: str):
    if key not in op or op[key] is None:
        return _MISSING
    return op[key]


def _text(field: str, value, *, required: bool = False, allow_blank: bool = True) -> str:
    if not isinstance(value, str):
        raise StudioError(field, "must be text")
    text = value.strip()
    if required and not text:
        raise StudioError(field, "is required")
    if not allow_blank and not text:
        raise StudioError(field, "is required")
    limit = TEXT_LIMITS[field]
    if len(text) > limit:
        raise StudioError(field, "is too long")
    return text


def _upper(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StudioError(field, "must be a short code")
    return value.strip().upper()


def normalize_course_code(value) -> str:
    code = _upper(value, "code")
    if not COURSE_CODE.fullmatch(code):
        raise StudioError("code", "must be a short code such as GEO")
    return code


def normalize_node_code(value, course_code: str, field: str = "code") -> str:
    code = _upper(value, field)
    prefix = f"{course_code}-"
    if not NODE_CODE.fullmatch(code) or len(code) > 40 or not code.startswith(prefix):
        raise StudioError(field, f"must be a short stable code such as {course_code}-U2")
    return code


def normalize_depth(value) -> str:
    if value not in DEPTHS:
        raise StudioError("depth", "must be survey, standard, or go_deep", plain="Detail must be survey, standard, or go deep.")
    return value


def normalize_quiz_minutes(value) -> int:
    if isinstance(value, bool) or value not in QUIZ_MINUTES:
        raise StudioError(
            "quiz_minutes",
            "must be 2, 5, or 10",
            plain="Minimum time before the closing quiz must be 2, 5, or 10 minutes.",
        )
    return value


def normalize_audience(value) -> str:
    if value not in AGE_BANDS:
        raise StudioError(
            "audience",
            "must be an age band",
            plain="Audience must be 6-8, 9-11, 12-14, or 15-17.",
        )
    return value


def normalize_sources(value) -> str:
    text = _text("sources", value)
    if text.lower() == "none":
        return ""
    return text


def _items(value) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StudioError("items", "must be a list of choices")
    cleaned = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            text = item["text"].strip()
        else:
            raise StudioError("items", "each choice needs text")
        if not text or len(text) > 240:
            raise StudioError("items", "each choice needs short text")
        cleaned.append({"text": text})
    return cleaned


def normalize_close(value, field: str = "close") -> dict:
    if not isinstance(value, dict):
        raise StudioError(field, "must say how the quest closes")
    style = value.get("close_style")
    if style not in CLOSE_STYLES:
        raise StudioError("close_style", "must be one or several")
    answer = value.get("answer_style")
    if answer not in ANSWER_STYLES:
        raise StudioError("answer_style", "must be multiple_choice, essay, or mixed")
    mode = value.get("choice_mode")
    if mode == "":
        mode = None
    intent = value.get("intent")
    if intent is None:
        intent = ""
    if not isinstance(intent, str):
        raise StudioError("intent", "must be text")
    intent = intent.strip()
    if len(intent) > TEXT_LIMITS["intent"]:
        raise StudioError("intent", "is too long")
    items = _items(value.get("items"))
    if answer == "essay":
        if mode is not None:
            raise StudioError("choice_mode", "is only for multiple choice")
        if items:
            raise StudioError("items", "are stored only for predefined choices")
        if intent:
            raise StudioError("intent", "is stored only for dynamic choices")
        return {
            "close_style": style,
            "answer_style": answer,
            "choice_mode": None,
            "items": [],
            "intent": "",
        }
    if mode not in CHOICE_MODES:
        raise StudioError("choice_mode", "must be predefined or dynamic")
    if mode == "predefined":
        if len(items) < 2 or len(items) > 8:
            raise StudioError("items", "needs two to eight choices")
        if intent:
            raise StudioError("intent", "is stored only for dynamic choices")
        return {
            "close_style": style,
            "answer_style": answer,
            "choice_mode": "predefined",
            "items": items,
            "intent": "",
        }
    if items:
        raise StudioError("items", "dynamic choices store only the intent")
    if not intent:
        raise StudioError("intent", "is required for dynamic choices")
    return {
        "close_style": style,
        "answer_style": answer,
        "choice_mode": "dynamic",
        "items": [],
        "intent": intent,
    }


def close_default_of(course: StudioCourse) -> dict:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    stored = raw.get("close_default") if isinstance(raw, dict) else None
    if not isinstance(stored, dict):
        return default_close()
    try:
        return normalize_close(stored, "close_default")
    except StudioError:
        return default_close()


def _position(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 200:
        raise StudioError("position", "must be an integer from 1 to 200", plain=POSITION_REASON)
    return value


def _slot(existing: list, row, position: int) -> None:
    others = sorted(
        [item for item in existing if item.code != row.code],
        key=lambda item: (item.position, item.code),
    )
    if position < 1 or position > len(others) + 1:
        raise StudioError(
            "position",
            "is past the end of this list",
            plain="Position is past the end of this list.",
        )
    ordered = others[: position - 1] + [row] + others[position - 1 :]
    for index, item in enumerate(ordered, start=1):
        item.position = index


def _compact(rows: list) -> None:
    ordered = sorted(rows, key=lambda item: (item.position, item.code))
    for index, item in enumerate(ordered, start=1):
        item.position = index


def _operations(patch) -> list:
    if isinstance(patch, list):
        raw = patch
    elif isinstance(patch, dict) and isinstance(patch.get("operations"), list):
        raw = patch["operations"]
    else:
        raise StudioError(
            "patch",
            "must be add, update, or remove operations addressed by code",
        )
    if not raw:
        raise StudioError("patch", "needs at least one add, update, or remove")
    if len(raw) > 40:
        raise StudioError("patch", "is too large")
    return raw


def _reject_foreign(op: dict, allowed: set[str], kind: str) -> None:
    for key in (
        "title",
        "learning_goal",
        "success_criterion",
        "position",
        "audience",
        "focus",
        "theme",
        "depth",
        "sources",
        "close",
        "close_default",
        "parent",
    ):
        if key in allowed:
            continue
        if _field(op, key) is _MISSING:
            continue
        raise StudioError(key, f"does not belong on a {kind}")


def plan_patch(course: StudioCourse, patch) -> list[dict]:
    """Check a patch against this course. Nothing is written."""
    nodes = {
        course.code: _Node("course", course.code, None, 0),
    }
    for unit in course.units:
        nodes[unit.code] = _Node("unit", unit.code, course.code, unit.position)
        for quest in unit.quests:
            nodes[quest.code] = _Node("quest", quest.code, unit.code, quest.position)
            for move in quest.moves:
                nodes[move.code] = _Node("move", move.code, quest.code, move.position)
    state = {
        "title": course.title,
        "audience": course.audience,
        "focus": course.focus,
        "theme": course.theme,
        "depth": course.depth,
        "sources": course.sources,
        "close_default": close_default_of(course),
    }
    planned: list[dict] = []
    for raw in _operations(patch):
        if not isinstance(raw, dict):
            raise StudioError("patch", "each change must be an object")
        op_name = raw.get("op")
        kind = raw.get("kind")
        if op_name not in OPS:
            raise StudioError("op", "must be add, update, or remove")
        if kind not in KINDS:
            raise StudioError("kind", "must be course, unit, quest, or move")
        if op_name == "add":
            planned.append(_plan_add(course.code, raw, nodes, state))
        elif op_name == "update":
            planned.append(_plan_update(course.code, raw, nodes, state))
        else:
            planned.append(_plan_remove(course.code, raw, nodes))
    return planned


def _siblings(nodes: dict[str, _Node], parent: str, kind: str) -> list[_Node]:
    return [node for node in nodes.values() if node.parent == parent and node.kind == kind]


def _plan_add(course_code: str, raw: dict, nodes: dict[str, _Node], state: dict) -> dict:
    kind = raw["kind"]
    if kind == "course":
        raise StudioError("op", "the course already exists")
    _reject_foreign(raw, {"title", "learning_goal", "success_criterion", "position", "parent", "close"}, kind)
    code = normalize_node_code(raw.get("code"), course_code)
    existing = nodes.get(code)
    if existing is not None:
        if existing.kind != kind:
            raise StudioError(
                "code",
                f"{code} is already a {existing.kind}",
                plain=f"{code} is already a {existing.kind}.",
            )
        return _plan_update(course_code, raw, nodes, state)
    if kind == "unit":
        parent_code = _upper(raw.get("parent"), "parent")
        if parent_code != course_code:
            raise StudioError("parent", f"{parent_code} is not this course")
    else:
        parent_code = normalize_node_code(raw.get("parent"), course_code, "parent")
    parent = nodes.get(parent_code)
    if parent is None:
        raise StudioError("parent", f"{parent_code} is not in this course")
    if parent.kind != PARENT_KIND[kind]:
        raise StudioError("parent", f"{code} must be added under a {PARENT_KIND[kind]}")
    title = _text("title", raw.get("title"), required=True)
    goal = ""
    criterion = ""
    if _field(raw, "learning_goal") is not _MISSING:
        goal = _text("learning_goal", raw.get("learning_goal"))
    if _field(raw, "success_criterion") is not _MISSING:
        criterion = _text("success_criterion", raw.get("success_criterion"))
    if kind == "quest":
        close = normalize_close(raw.get("close")) if _field(raw, "close") is not _MISSING else None
    elif _field(raw, "close") is not _MISSING:
        raise StudioError("close", "belongs on a quest")
    else:
        close = None
    row = _Node(kind, code, parent_code, 0)
    group = _siblings(nodes, parent_code, kind)
    position = len(group) + 1 if _field(raw, "position") is _MISSING else _position(raw.get("position"))
    _slot(group, row, position)
    nodes[code] = row
    planned = {
        "op": "add",
        "kind": kind,
        "code": code,
        "parent": parent_code,
        "title": title,
        "learning_goal": goal,
        "success_criterion": criterion,
        "position": row.position,
    }
    if kind == "quest":
        planned["close"] = close
    return planned


def _update_by_code_sentence(example: str) -> str:
    return f"To change an item, name its code, such as {example}."


def _parent_on_update(raw: dict, course_code: str, kind: str, example: str) -> str | None:
    """A parent on an update is only an echo of the current parent. Anything else is refused."""
    if _field(raw, "parent") is _MISSING:
        return None
    try:
        if kind in ("course", "unit"):
            return _upper(raw.get("parent"), "parent")
        return normalize_node_code(raw.get("parent"), course_code, "parent")
    except StudioError as exc:
        raise StudioError(
            "parent",
            "an update names the item's own code",
            plain=_update_by_code_sentence(example),
        ) from exc


def _plan_update(course_code: str, raw: dict, nodes: dict[str, _Node], state: dict) -> dict:
    kind = raw["kind"]
    if kind == "course":
        code = normalize_course_code(raw.get("code"))
        if code != course_code:
            raise StudioError("code", "does not match this course")
        if _parent_on_update(raw, course_code, kind, code) is not None:
            raise StudioError(
                "parent",
                "an update names the item's own code",
                plain=_update_by_code_sentence(code),
            )
        _reject_foreign(raw, set(COURSE_FIELDS), "course")
        planned: dict = {"op": "update", "kind": "course", "code": code}
        if _field(raw, "title") is not _MISSING:
            planned["title"] = _text("title", raw.get("title"), required=True)
            state["title"] = planned["title"]
        if _field(raw, "audience") is not _MISSING:
            planned["audience"] = _text("audience", raw.get("audience"))
            state["audience"] = planned["audience"]
        if _field(raw, "focus") is not _MISSING:
            planned["focus"] = _text("focus", raw.get("focus"))
            state["focus"] = planned["focus"]
        if _field(raw, "theme") is not _MISSING:
            planned["theme"] = _text("theme", raw.get("theme"))
            state["theme"] = planned["theme"]
        if _field(raw, "depth") is not _MISSING:
            planned["depth"] = normalize_depth(raw.get("depth"))
            state["depth"] = planned["depth"]
        if _field(raw, "sources") is not _MISSING:
            planned["sources"] = normalize_sources(raw.get("sources"))
            state["sources"] = planned["sources"]
        if _field(raw, "close_default") is not _MISSING:
            planned["close_default"] = normalize_close(raw.get("close_default"), "close_default")
            state["close_default"] = planned["close_default"]
        if len(planned) == 3:
            raise StudioError("patch", "an update needs a field to change")
        return planned

    _reject_foreign(
        raw,
        set(NODE_FIELDS) | {"parent"} | ({"close"} if kind == "quest" else set()),
        kind,
    )
    code = normalize_node_code(raw.get("code"), course_code)
    node = nodes.get(code)
    if node is None:
        raise StudioError("code", f"{code} is not in this course")
    if node.kind != kind:
        raise StudioError("kind", f"{code} is a {node.kind}")
    sent_parent = _parent_on_update(raw, course_code, kind, code)
    if sent_parent is not None and sent_parent != node.parent:
        raise StudioError(
            "parent",
            "an update names the item's own code",
            plain=_update_by_code_sentence(code),
        )
    planned = {"op": "update", "kind": kind, "code": code}
    if _field(raw, "title") is not _MISSING:
        planned["title"] = _text("title", raw.get("title"), required=True)
    if _field(raw, "learning_goal") is not _MISSING:
        planned["learning_goal"] = _text("learning_goal", raw.get("learning_goal"))
    if _field(raw, "success_criterion") is not _MISSING:
        planned["success_criterion"] = _text("success_criterion", raw.get("success_criterion"))
    if _field(raw, "position") is not _MISSING:
        position = _position(raw.get("position"))
        _slot(_siblings(nodes, node.parent or "", kind), node, position)
        planned["position"] = node.position
    if kind == "quest" and _field(raw, "close") is not _MISSING:
        planned["close"] = normalize_close(raw.get("close"))
    elif _field(raw, "close") is not _MISSING:
        raise StudioError("close", "belongs on a quest")
    if len(planned) == 3:
        raise StudioError("patch", "an update needs a field to change")
    return planned


def _plan_remove(course_code: str, raw: dict, nodes: dict[str, _Node]) -> dict:
    kind = raw["kind"]
    if kind == "course":
        raise StudioError("op", "the course is not removed from a patch")
    code = normalize_node_code(raw.get("code"), course_code)
    node = nodes.get(code)
    if node is None:
        raise StudioError("code", f"{code} is not in this course")
    if node.kind != kind:
        raise StudioError("kind", f"{code} is a {node.kind}")
    parent = node.parent
    _drop(nodes, code)
    _compact(_siblings(nodes, parent or "", kind))
    return {"op": "remove", "kind": kind, "code": code}


def _drop(nodes: dict[str, _Node], code: str) -> None:
    children = [node.code for node in nodes.values() if node.parent == code]
    for child in children:
        _drop(nodes, child)
    del nodes[code]


def _fill_close(quest: StudioQuest, close: dict) -> None:
    row = quest.close
    if row is None:
        row = StudioQuestClose()
        quest.close = row
        session = object_session(quest)
        if session is not None:
            session.add(row)
    row.close_style = close["close_style"]
    row.answer_style = close["answer_style"]
    row.choice_mode = close["choice_mode"]
    row.items = list(close["items"])
    row.intent = close["intent"]


def _apply(course: StudioCourse, planned: list[dict]) -> None:
    for step in planned:
        if step["op"] == "add":
            _apply_add(course, step)
        elif step["op"] == "update":
            _apply_update(course, step)
        else:
            _apply_remove(course, step)


def _apply_add(course: StudioCourse, step: dict) -> None:
    kind = step["kind"]
    if kind == "unit":
        row = StudioUnit(
            course_id=course.id,
            code=step["code"],
            position=step["position"],
            title=step["title"],
            learning_goal=step["learning_goal"],
            success_criterion=step["success_criterion"],
        )
        course.units.append(row)
        _slot(list(course.units), row, step["position"])
        return
    if kind == "quest":
        unit = _unit(course, step["parent"])
        row = StudioQuest(
            course_id=course.id,
            code=step["code"],
            position=step["position"],
            title=step["title"],
            learning_goal=step["learning_goal"],
            success_criterion=step["success_criterion"],
        )
        unit.quests.append(row)
        _slot(list(unit.quests), row, step["position"])
        if step.get("close") is not None:
            _fill_close(row, step["close"])
        return
    quest = _quest(course, step["parent"])
    row = StudioMove(
        course_id=course.id,
        code=step["code"],
        position=step["position"],
        title=step["title"],
        learning_goal=step["learning_goal"],
        success_criterion=step["success_criterion"],
    )
    quest.moves.append(row)
    _slot(list(quest.moves), row, step["position"])


def _apply_update(course: StudioCourse, step: dict) -> None:
    if step["kind"] == "course":
        for key in ("title", "audience", "focus", "theme", "depth", "sources"):
            if key in step:
                setattr(course, key, step[key])
        if "close_default" in step:
            prefs = dict(course.preferences or {})
            prefs["close_default"] = step["close_default"]
            course.preferences = prefs
        return
    if step["kind"] == "unit":
        row = _unit(course, step["code"])
        _assign_node(row, step)
        if "position" in step:
            _slot(list(course.units), row, step["position"])
        return
    if step["kind"] == "quest":
        row = _quest(course, step["code"])
        _assign_node(row, step)
        if "position" in step:
            _slot(list(row.unit.quests), row, step["position"])
        if "close" in step:
            _fill_close(row, step["close"])
        return
    row = _move(course, step["code"])
    _assign_node(row, step)
    if "position" in step:
        _slot(list(row.quest.moves), row, step["position"])


def _assign_node(row, step: dict) -> None:
    for key in ("title", "learning_goal", "success_criterion"):
        if key in step:
            setattr(row, key, step[key])


def _apply_remove(course: StudioCourse, step: dict) -> None:
    if step["kind"] == "unit":
        row = _unit(course, step["code"])
        course.units.remove(row)
        _compact(list(course.units))
        return
    if step["kind"] == "quest":
        row = _quest(course, step["code"])
        unit = row.unit
        unit.quests.remove(row)
        _compact(list(unit.quests))
        return
    row = _move(course, step["code"])
    quest = row.quest
    quest.moves.remove(row)
    _compact(list(quest.moves))


def _unit(course: StudioCourse, code: str) -> StudioUnit:
    for unit in course.units:
        if unit.code == code:
            return unit
    raise StudioError("code", f"{code} is not in this course")


def _quest(course: StudioCourse, code: str) -> StudioQuest:
    for unit in course.units:
        for quest in unit.quests:
            if quest.code == code:
                return quest
    raise StudioError("code", f"{code} is not in this course")


def _move(course: StudioCourse, code: str) -> StudioMove:
    for unit in course.units:
        for quest in unit.quests:
            for move in quest.moves:
                if move.code == code:
                    return move
    raise StudioError("code", f"{code} is not in this course")


def apply_patch(db: Session, course: StudioCourse, patch) -> None:
    planned = plan_patch(course, patch)
    _apply(course, planned)
    course.updated_at = _now()
    db.flush()


def create_course(db: Session, *, code: str, title: str) -> StudioCourse:
    normalized = normalize_course_code(code)
    label = _text("title", title, required=True)
    taken = db.scalar(select(StudioCourse.id).where(StudioCourse.code == normalized))
    if taken is not None:
        raise StudioError("code", "is already used", status=409)
    course = StudioCourse(
        code=normalized,
        title=label,
        audience="",
        focus="",
        theme="",
        depth="standard",
        quiz_minutes=5,
        sources="",
        preferences=default_preferences(),
        schema_version=SCHEMA_VERSION,
        ready=False,
    )
    db.add(course)
    db.flush()
    return course


def delete_studio_course(db: Session, course: StudioCourse, password: str) -> None:
    """Delete one studio course after the password. Tutor courses and kid chats stay."""
    if not isinstance(password, str) or not hmac.compare_digest(password, DELETE_PASSWORD):
        raise StudioError("password", "is wrong", plain="The password is wrong.")
    db.delete(course)
    db.flush()


def _node_codes(course: StudioCourse) -> list[str]:
    codes: list[str] = []
    for unit in course.units:
        codes.append(unit.code)
        for quest in unit.quests:
            codes.append(quest.code)
            for move in quest.moves:
                codes.append(move.code)
    return codes


def _retarget_code(code: str, old: str, new: str) -> str:
    prefix = f"{old}-"
    if code.startswith(prefix):
        return f"{new}-{code[len(prefix):]}"
    return code


def fresh_course_code(db: Session, source: StudioCourse) -> str:
    taken = set(db.scalars(select(StudioCourse.code)).all())
    nodes = _node_codes(source)
    for number in range(2, 1000):
        suffix = str(number)
        room = 16 - len(suffix)
        if room < 1:
            break
        candidate = f"{source.code[:room]}{suffix}"
        if candidate in taken or candidate == source.code or not COURSE_CODE.fullmatch(candidate):
            continue
        rewritten = [_retarget_code(code, source.code, candidate) for code in nodes]
        if any(len(code) > 40 or not NODE_CODE.fullmatch(code) for code in rewritten):
            continue
        return candidate
    raise StudioError("code", "a new code is not available", plain="Could not choose a new code.")


def _copy_close(quest: StudioQuest, source: StudioQuestClose) -> None:
    row = StudioQuestClose(
        close_style=source.close_style,
        answer_style=source.answer_style,
        choice_mode=source.choice_mode,
        items=copy.deepcopy(source.items or []),
        intent=source.intent or "",
    )
    quest.close = row
    session = object_session(quest)
    if session is not None:
        session.add(row)


def copy_studio_course(db: Session, source: StudioCourse, title: str) -> StudioCourse:
    """Copy the course under a new code and name. The creation chat is not copied."""
    label = _text("title", title, required=True)
    code = fresh_course_code(db, source)
    course = StudioCourse(
        code=code,
        title=label,
        audience=source.audience,
        focus=source.focus,
        theme=source.theme,
        depth=source.depth,
        quiz_minutes=source.quiz_minutes,
        sources=source.sources,
        preferences=copy.deepcopy(source.preferences or {}),
        schema_version=source.schema_version,
        ready=source.ready,
    )
    db.add(course)
    db.flush()
    for unit in sorted(source.units, key=lambda row: (row.position, row.code)):
        new_unit = StudioUnit(
            course_id=course.id,
            code=_retarget_code(unit.code, source.code, code),
            position=unit.position,
            title=unit.title,
            learning_goal=unit.learning_goal,
            success_criterion=unit.success_criterion,
        )
        course.units.append(new_unit)
        db.flush()
        for quest in sorted(unit.quests, key=lambda row: (row.position, row.code)):
            new_quest = StudioQuest(
                course_id=course.id,
                code=_retarget_code(quest.code, source.code, code),
                position=quest.position,
                title=quest.title,
                learning_goal=quest.learning_goal,
                success_criterion=quest.success_criterion,
            )
            new_unit.quests.append(new_quest)
            db.flush()
            if quest.close is not None:
                _copy_close(new_quest, quest.close)
            for move in sorted(quest.moves, key=lambda row: (row.position, row.code)):
                new_unit_move = StudioMove(
                    course_id=course.id,
                    code=_retarget_code(move.code, source.code, code),
                    position=move.position,
                    title=move.title,
                    learning_goal=move.learning_goal,
                    success_criterion=move.success_criterion,
                )
                new_quest.moves.append(new_unit_move)
    db.flush()
    return course


def update_preferences(course: StudioCourse, body: dict) -> None:
    course.title = _text("title", body.get("title"), required=True)
    course.audience = normalize_audience(body.get("audience", ""))
    course.focus = _text("focus", body.get("focus", ""))
    theme = _text("theme", body.get("theme", ""))
    if theme.lower() in {"none", "no theme"}:
        theme = ""
    course.theme = theme
    course.depth = normalize_depth(body.get("depth"))
    course.quiz_minutes = normalize_quiz_minutes(body.get("quiz_minutes", course.quiz_minutes))
    course.sources = normalize_sources(body.get("sources", ""))
    close = normalize_close(body.get("close_default"), "close_default")
    prefs = dict(course.preferences or {})
    prefs["close_default"] = close
    prefs["depth"] = course.depth
    prefs["quiz_minutes"] = course.quiz_minutes
    prefs["audience"] = course.audience
    prefs["theme"] = course.theme
    prefs["sources"] = course.sources
    course.preferences = prefs
    course.schema_version = SCHEMA_VERSION
    course.updated_at = _now()


def load_course(db: Session, course_id) -> StudioCourse | None:
    return db.scalar(
        select(StudioCourse)
        .where(StudioCourse.id == course_id)
        .options(
            selectinload(StudioCourse.units).selectinload(StudioUnit.quests).selectinload(StudioQuest.moves),
            selectinload(StudioCourse.units).selectinload(StudioUnit.quests).selectinload(StudioQuest.close),
        )
    )


def list_courses(db: Session) -> list[StudioCourse]:
    return list(
        db.scalars(select(StudioCourse).order_by(StudioCourse.updated_at.desc(), StudioCourse.title)).all()
    )


def list_messages(db: Session, course: StudioCourse) -> list[StudioMessage]:
    return list(
        db.scalars(
            select(StudioMessage).where(StudioMessage.course_id == course.id).order_by(StudioMessage.seq)
        ).all()
    )


def add_message(
    db: Session,
    course: StudioCourse,
    *,
    role: str,
    content: str,
    proposal: dict | None,
) -> StudioMessage:
    text = content.strip()
    if not text:
        raise StudioError("content", "is required")
    if len(text) > 20000:
        raise StudioError("content", "is too long")
    if role == "user" and proposal is not None:
        raise StudioError("proposal", "a creator message cannot carry a patch")
    stored = None
    if proposal is not None:
        plan_patch(course, proposal)
        stored = {"operations": copy.deepcopy(_operations(proposal))}
    seq = db.scalar(select(func.max(StudioMessage.seq)).where(StudioMessage.course_id == course.id))
    message = StudioMessage(
        course_id=course.id,
        role=role,
        content=text,
        seq=(seq or 0) + 1,
        proposal=stored,
        applied=False,
    )
    db.add(message)
    course.updated_at = _now()
    db.flush()
    return message


def accept_proposal(db: Session, course: StudioCourse, message: StudioMessage) -> None:
    if message.course_id != course.id:
        raise StudioError("message", "is not part of this course", status=404)
    if message.applied:
        raise StudioError("proposal", "that change is already saved", status=409)
    if not message.proposal:
        raise StudioError("proposal", "there is nothing to accept")
    apply_patch(db, course, message.proposal)
    message.applied = True
    if course_phase(course)["name"] != "ready":
        course.ready = False
    course.updated_at = _now()
    db.flush()


def dismiss_proposal(course: StudioCourse, message: StudioMessage) -> None:
    if message.course_id != course.id:
        raise StudioError("message", "is not part of this course", status=404)
    if message.applied:
        raise StudioError("proposal", "that change is already saved", status=409)
    if not message.proposal:
        raise StudioError("proposal", "there is nothing to dismiss")
    message.proposal = None
    course.updated_at = _now()


def ensure_settings(db: Session) -> StudioSettings:
    row = db.get(StudioSettings, SETTINGS_ID)
    if row is not None:
        return row
    row = StudioSettings(id=SETTINGS_ID, model=DEFAULT_STUDIO_MODEL)
    db.add(row)
    db.flush()
    return row


def set_model(db: Session, model: str) -> StudioSettings:
    if not isinstance(model, str) or model not in STUDIO_MODELS:
        raise StudioError("model", "must be gpt-4o-mini, gpt-4o, or gpt-4.1-mini")
    row = ensure_settings(db)
    row.model = model
    db.flush()
    return row


def course_phase(course: StudioCourse) -> dict:
    """The one wave still open. Later waves are not part of this result."""
    units = sorted(course.units, key=lambda row: (row.position, row.code))
    if not units:
        return {"name": "structure", "label": "Structure", "open_codes": [course.code]}
    bare_units = [unit.code for unit in units if not unit.quests]
    if bare_units:
        return {"name": "structure", "label": "Structure", "open_codes": bare_units}
    missing_goals: list[str] = []
    missing_close: list[str] = []
    for unit in units:
        for quest in sorted(unit.quests, key=lambda row: (row.position, row.code)):
            if not str(quest.learning_goal or "").strip():
                missing_goals.append(quest.code)
            style = quest.close.close_style if quest.close is not None else ""
            if not str(style or "").strip():
                missing_close.append(quest.code)
    if missing_goals:
        return {"name": "goals", "label": "Goals", "open_codes": missing_goals}
    if missing_close:
        return {"name": "close", "label": "Close", "open_codes": missing_close}
    return {"name": "ready", "label": "Ready", "open_codes": []}


PHASES = (
    ("structure", "Structure"),
    ("goals", "Goals"),
    ("close", "Close"),
    ("ready", "Ready"),
)
PHASE_ORDER = {name: index for index, (name, _label) in enumerate(PHASES)}
PHASE_LABELS = dict(PHASES)


def _stored_phase_view(course: StudioCourse) -> str | None:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    value = raw.get("phase_view") if isinstance(raw, dict) else None
    if value in PHASE_ORDER:
        return str(value)
    return None


def _quest_codes(course: StudioCourse) -> list[str]:
    codes = []
    for unit in sorted(course.units, key=lambda row: (row.position, row.code)):
        for quest in sorted(unit.quests, key=lambda row: (row.position, row.code)):
            codes.append(quest.code)
    return codes


def _codes_in_phase(course: StudioCourse, name: str) -> list[str]:
    if name == "structure":
        units = sorted(course.units, key=lambda row: (row.position, row.code))
        if not units:
            return [course.code]
        return [unit.code for unit in units]
    if name in ("goals", "close"):
        return _quest_codes(course)
    return []


def viewed_phase(course: StudioCourse) -> dict:
    """The phase the chat and the strip highlight. Earlier choices include filled items."""
    open_phase = course_phase(course)
    stored = _stored_phase_view(course)
    if stored is None or PHASE_ORDER[stored] >= PHASE_ORDER[open_phase["name"]]:
        return {
            "name": open_phase["name"],
            "label": open_phase["label"],
            "codes": list(open_phase["open_codes"]),
            "stepped_back": False,
        }
    return {
        "name": stored,
        "label": PHASE_LABELS[stored],
        "codes": _codes_in_phase(course, stored),
        "stepped_back": True,
    }


def phase_strip(course: StudioCourse) -> list[dict]:
    open_phase = course_phase(course)
    view = viewed_phase(course)
    open_index = PHASE_ORDER[open_phase["name"]]
    return [
        {
            "name": name,
            "label": label,
            "filled": (course.ready if name == "ready" else PHASE_ORDER[name] < open_index),
            "active": name == view["name"],
        }
        for name, label in PHASES
    ]


def set_phase_view(course: StudioCourse, name: str) -> None:
    """Point the chat at an earlier phase. Later rows stay as they are."""
    if name not in PHASE_ORDER:
        raise StudioError("phase", "must be a course phase", plain="Choose Structure, Goals, Close, or Ready.")
    open_phase = course_phase(course)
    if PHASE_ORDER[name] > PHASE_ORDER[open_phase["name"]]:
        raise StudioError(
            "phase",
            "is later than the open wave",
            plain=f"Finish {open_phase['label']} before opening {PHASE_LABELS[name]}.",
        )
    prefs = dict(course.preferences or {})
    if name == open_phase["name"]:
        prefs.pop("phase_view", None)
    else:
        prefs["phase_view"] = name
    course.preferences = prefs
    course.updated_at = _now()


def phase_instructions(course: StudioCourse) -> str:
    view = viewed_phase(course)
    if view["stepped_back"]:
        codes = ", ".join(view["codes"]) if view["codes"] else "none"
        open_label = course_phase(course)["label"]
        if view["name"] == "goals":
            focus = (
                "Offer a learning goal for each of these quests, including items already filled. "
                "An update names that quest's code and sets parent to null. "
                "Do not wipe close style."
            )
        elif view["name"] == "structure":
            focus = (
                "Update these units by code. Set parent to null. "
                "Do not wipe learning goals or close style."
            )
        else:
            focus = "An update names the item's code and sets parent to null. Do not wipe later work."
        return (
            f"Current phase: {view['label']}.\n"
            f"Codes in this phase: {codes}.\n"
            f"Patch only those codes. {focus}\n"
            f"The next unfinished wave is {open_label}. Later phases are not wiped.\n"
        )
    phase = course_phase(course)
    codes = ", ".join(phase["open_codes"]) if phase["open_codes"] else "none"
    if phase["name"] == "structure":
        focus = "Add the missing units and quests. Empty learning goals are allowed."
        later = (
            "Later phases, in one line: Goals, then Close, then Ready. "
            "Do not fill learning goals or close style in this patch."
        )
    elif phase["name"] == "goals":
        focus = (
            "Offer a learning goal for each open quest, addressed by that quest's code. "
            "An update names that code and sets parent to null."
        )
        later = "Later phases, in one line: Close, then Ready. Do not fill close style in this patch."
    elif phase["name"] == "close":
        focus = (
            "Offer a close style for each open quest, addressed by that quest's code. "
            "An update names that code and sets parent to null."
        )
        later = "Later phase, in one line: Ready. Do not add new goals in this patch."
    else:
        focus = "Units, quests, learning goals, and close styles are in place. Mark ready can be turned on."
        later = "There is no later phase. Do not send a patch unless the creator asks for a change."
    return (
        f"Current phase: {phase['label']}.\n"
        f"Codes still open in this phase: {codes}.\n"
        f"Patch only those codes. {focus}\n"
        f"{later}\n"
    )


def course_gaps(course: StudioCourse) -> list[str]:
    """Empty required fields on a saved item. These marks do not undo the draft."""
    gaps: list[str] = []
    for unit in sorted(course.units, key=lambda row: (row.position, row.code)):
        _goal_gap(gaps, unit.code, unit.learning_goal)
        for quest in sorted(unit.quests, key=lambda row: (row.position, row.code)):
            _goal_gap(gaps, quest.code, quest.learning_goal)
            style = quest.close.close_style if quest.close is not None else ""
            if not str(style or "").strip():
                gaps.append(f"{quest.code}: no close style")
            for move in sorted(quest.moves, key=lambda row: (row.position, row.code)):
                _goal_gap(gaps, move.code, move.learning_goal)
    return gaps


def _goal_gap(gaps: list[str], code: str, learning_goal: str | None) -> None:
    if not str(learning_goal or "").strip():
        gaps.append(f"{code}: no learning goal")


def mark_ready(course: StudioCourse) -> None:
    """Record that the creator says this draft is complete. Nothing is copied."""
    phase = course_phase(course)
    gaps = course_gaps(course)
    if phase["name"] != "ready":
        listed = "; ".join(gaps) if gaps else ", ".join(phase["open_codes"])
        raise StudioError(
            "ready",
            f"still has open gaps: {listed}",
            plain=f"These gaps are still open: {listed}.",
        )
    course.ready = True
    course.updated_at = _now()


def _close_out(close: dict | None) -> StudioCloseOut | None:
    if close is None:
        return None
    return StudioCloseOut(
        close_style=close["close_style"],
        answer_style=close["answer_style"],
        choice_mode=close["choice_mode"],
        items=list(close["items"]),
        intent=close["intent"],
    )


def _row_close(row: StudioQuestClose | None) -> StudioCloseOut | None:
    if row is None:
        return None
    return StudioCloseOut(
        close_style=row.close_style,
        answer_style=row.answer_style,
        choice_mode=row.choice_mode,
        items=list(row.items or []),
        intent=row.intent or "",
    )


def course_out(course: StudioCourse) -> StudioCourseOut:
    units = []
    for unit in sorted(course.units, key=lambda row: (row.position, row.code)):
        quests = []
        for quest in sorted(unit.quests, key=lambda row: (row.position, row.code)):
            moves = [
                StudioMoveOut(
                    id=move.id,
                    code=move.code,
                    position=move.position,
                    title=move.title,
                    learning_goal=move.learning_goal,
                    success_criterion=move.success_criterion,
                )
                for move in sorted(quest.moves, key=lambda row: (row.position, row.code))
            ]
            quests.append(
                StudioQuestOut(
                    id=quest.id,
                    code=quest.code,
                    position=quest.position,
                    title=quest.title,
                    learning_goal=quest.learning_goal,
                    success_criterion=quest.success_criterion,
                    close=_row_close(quest.close),
                    moves=moves,
                )
            )
        units.append(
            StudioUnitOut(
                id=unit.id,
                code=unit.code,
                position=unit.position,
                title=unit.title,
                learning_goal=unit.learning_goal,
                success_criterion=unit.success_criterion,
                quests=quests,
            )
        )
    default = close_default_of(course)
    return StudioCourseOut(
        id=course.id,
        code=course.code,
        title=course.title,
        audience=course.audience,
        focus=course.focus,
        theme=course.theme,
        depth=course.depth,
        quiz_minutes=course.quiz_minutes,
        sources=course.sources,
        schema_version=course.schema_version,
        close_default=_close_out(default),
        ready=bool(course.ready),
        gaps=course_gaps(course),
        phase=StudioPhaseOut(**course_phase(course)),
        strip=[StudioStripOut(**item) for item in phase_strip(course)],
        view=StudioViewOut(
            name=viewed_phase(course)["name"],
            label=viewed_phase(course)["label"],
            codes=viewed_phase(course)["codes"],
        ),
        units=units,
        updated_at=course.updated_at,
    )


def summary_out(course: StudioCourse) -> StudioCourseSummary:
    return StudioCourseSummary(
        id=course.id,
        code=course.code,
        title=course.title,
        updated_at=course.updated_at,
    )


def message_out(message: StudioMessage) -> StudioMessageOut:
    return StudioMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        seq=message.seq,
        proposal=message.proposal,
        applied=message.applied,
        created_at=message.created_at,
    )


def system_prompt(course: StudioCourse, messages: list[StudioMessage]) -> str:
    tree = course_out(course).model_dump(mode="json")
    pending = []
    for message in messages:
        if message.proposal and not message.applied:
            pending.append(message.proposal)
    pending_note = "There is no unaccepted patch."
    if pending:
        pending_note = (
            "These patches are not saved yet. They are not part of the course JSON below:\n"
            + "\n".join(str(item) for item in pending)
        )
    return (
        "You are helping a person build one course in the CreateCourse studio.\n"
        "The creator states a focus. You propose a short structure of units, quests, and moves.\n"
        "You may use widely known national curricula and standard texts as suggestions. "
        "You must say which framework a suggestion comes from. "
        "Label every curriculum idea as a suggestion.\n"
        "You have no web search and no document upload. Do not claim you searched the web or read an uploaded file.\n"
        "Nothing is saved until the creator accepts the patch. "
        "The server still checks. A rejected patch is not written. "
        "Do not say the course was saved, and do not say the structure was accepted.\n"
        f"{phase_instructions(course)}"
        "Return a reply plus an optional patch. The patch is a list of operations. "
        "Each operation is add, update, or remove, and it names a code. "
        "Do not rewrite the whole tree in prose. The server ignores anything that is not a typed patch.\n"
        "Each add names these fields: code, parent code, title, position as an integer from 1, "
        "learning goal, success criterion, and quest-close choices. "
        "In the patch JSON those fields are code, parent, title, position, learning_goal, "
        "success_criterion, and close.\n"
        "A position of 0 is invalid. Leave position null and the server fills the next free number. "
        "A position outside 1 to 200 rejects the whole patch and saves nothing.\n"
        "A missing learning goal or quest-close choice does not block the write. "
        "The course is a draft from the moment it is created. "
        "The tree marks a missing learning goal and a missing close style. "
        "Those marks do not undo the draft. "
        "Mark ready only records that the creator says the draft is complete.\n"
        "The course close default is a preference in the header. "
        "Copy it into a quest's quest-close choices when you want that close. "
        "If close is null, the quest is stored with no close style. The server does not invent one.\n"
        "To change an item, name its code and set parent to null. Do not send a parent on an update. "
        "An add of a code that is already in this course is saved as an update of that item. "
        "To add an item, choose a new short stable code "
        f"such as {course.code}-U2 or {course.code}-U2-Q3 and name the parent code.\n"
        "On an add, the unit parent is the course code, the quest parent is a unit code, "
        "and the move parent is a quest code.\n"
        "Codes stay inside this course. Use null for a field you are not changing. An add requires a title.\n"
        "close_style is one or several. answer_style is multiple_choice, essay, or mixed. "
        "Multiple choice choice_mode is predefined or dynamic. "
        "Predefined stores the items and no intent. Dynamic stores only the intent and no items. "
        "Essay stores neither items nor intent.\n"
        "depth is survey, standard, or go_deep. sources is the framework to honor, or none.\n"
        f"{pending_note}\n"
        "The course so far, read from the database:\n"
        f"{json.dumps(tree)}"
    )
