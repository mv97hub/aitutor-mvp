"""CreateCourse studio: preferences, the typed patch, and the model row.

The tutor seed does not import this module. Patches are checked before they
are written. A model reply can describe a change, and the tree stays as it
is until the creator confirms that change in the chat.
"""

from __future__ import annotations

import copy
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.models import (
    StudioCourse,
    StudioMessage,
    StudioMove,
    StudioQuest,
    StudioQuestClose,
    StudioQuestGoal,
    StudioSettings,
)
from app.schemas import (
    StudioCloseOut,
    StudioCourseOut,
    StudioCourseSummary,
    StudioMessageOut,
    StudioMoveOut,
    StudioPhaseOut,
    StudioGoalOut,
    StudioQuestOut,
    StudioStripOut,
    StudioViewOut,
)

logger = logging.getLogger(__name__)

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
KINDS = ("course", "quest", "move")
OPS = ("add", "update", "remove")
PARENT_KIND = {"move": "quest"}
DEFAULT_QUEST_COUNT = 10
DEFAULT_GOALS_PER_QUEST = 3
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
            "questions": {
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
        "required": ["close_style", "answer_style", "choice_mode", "items", "questions", "intent"],
    }


def _operation_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "op": {"type": "string", "enum": ["add", "update", "remove"]},
            "kind": {"type": "string", "enum": ["course", "quest", "move"]},
            "code": {"type": "string"},
            "parent": {
                "type": ["string", "null"],
                "description": (
                    "Parent code when adding a move. Quests sit on the course, so parent is null. "
                    "Null on update. An update names the item by its own code and must not send a parent."
                ),
            },
            "title": {"type": ["string", "null"]},
            "learning_goal": {"type": ["string", "null"]},
            "success_criterion": {"type": ["string", "null"]},
            "goals": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "learning_goal": {"type": "string"},
                                "success_criterion": {"type": "string"},
                                "position": {"type": "integer"},
                            },
                            "required": ["learning_goal", "success_criterion", "position"],
                        },
                    },
                ]
            },
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
            "goals",
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


def _plain_error(field: str, message: str) -> str:
    """One sentence for the chat. No raw field path such as `close_style:`."""
    labels = {
        "close_style": "Close style",
        "answer_style": "Answer style",
        "choice_mode": "Choice mode",
        "learning_goal": "The learning goal",
        "success_criterion": "The success criterion",
        "close_default": "The close default",
        "content": "The message",
        "proposal": "The proposal",
        "message": "The message",
        "model": "The model",
        "patch": "The patch",
        "op": "The operation",
        "kind": "The kind",
        "code": "The code",
        "parent": "The parent",
        "title": "The title",
        "items": "The items",
        "questions": "The questions",
        "goals": "The goals",
        "intent": "The intent",
        "close": "The close",
        "position": "The position",
        "audience": "The audience",
        "focus": "The focus",
        "theme": "The theme",
        "sources": "The sources",
        "depth": "Detail",
        "phase": "The phase",
        "ready": "Ready",
        "password": "The password",
    }
    if field == "parent":
        return message if message.endswith(".") else f"The parent {message}."
    if message[:1].isupper():
        return message if message.endswith(".") else f"{message}."
    label = labels.get(field, "This value")
    if message.startswith("dynamic "):
        return "Dynamic choices store the intent, not the items."
    if message.startswith("each "):
        return f"{message[0].upper()}{message[1:]}."
    return f"{label} {message}."


class StudioError(Exception):
    def __init__(self, field: str, message: str, status: int = 422, plain: str | None = None) -> None:
        self.field = field
        self.message = message
        self.status = status
        self.plain = plain if plain is not None else _plain_error(field, message)
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
        "questions": [],
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
        "quest_count": DEFAULT_QUEST_COUNT,
        "goals_per_quest": DEFAULT_GOALS_PER_QUEST,
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
        raise StudioError(field, f"must be a short stable code such as {course_code}-Q1")
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


def _questions(value) -> list[dict]:
    """A close may list no questions. One or more is ordinary, and empty still saves."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise StudioError("questions", "must be a list")
    cleaned = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            text = item["text"].strip()
        else:
            raise StudioError("questions", "each question needs text")
        if not text or len(text) > 500:
            raise StudioError("questions", "each question needs short text")
        cleaned.append({"text": text})
    return cleaned


def normalize_goals(value) -> list[dict]:
    """Goal rows for one quest. Position 1 is stored on the quest columns."""
    if not isinstance(value, list):
        raise StudioError("goals", "must be a list")
    cleaned = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise StudioError("goals", "each goal needs text")
        goal_raw = item.get("learning_goal")
        criterion_raw = item.get("success_criterion")
        goal = _text("learning_goal", goal_raw if isinstance(goal_raw, str) else "")
        criterion = _text("success_criterion", criterion_raw if isinstance(criterion_raw, str) else "")
        position = item.get("position", index)
        if position is None:
            position = index
        cleaned.append(
            {
                "position": _position(position),
                "learning_goal": goal,
                "success_criterion": criterion,
            }
        )
    cleaned.sort(key=lambda row: row["position"])
    return [
        {"position": number, "learning_goal": row["learning_goal"], "success_criterion": row["success_criterion"]}
        for number, row in enumerate(cleaned, start=1)
    ]


def _target_count(value, default: int, field: str, plain: str) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 200:
        raise StudioError(field, "must be a whole number from 1 to 200", plain=plain)
    return value


def quest_count_of(course: StudioCourse) -> int:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    stored = raw.get("quest_count") if isinstance(raw, dict) else None
    try:
        return _target_count(stored, DEFAULT_QUEST_COUNT, "quest_count", "Number of quests must be a whole number from 1 to 200.")
    except StudioError:
        return DEFAULT_QUEST_COUNT


def goals_per_quest_of(course: StudioCourse) -> int:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    stored = raw.get("goals_per_quest") if isinstance(raw, dict) else None
    try:
        return _target_count(
            stored,
            DEFAULT_GOALS_PER_QUEST,
            "goals_per_quest",
            "Goals per quest must be a whole number from 1 to 200.",
        )
    except StudioError:
        return DEFAULT_GOALS_PER_QUEST


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
    questions = _questions(value.get("questions"))
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
            "questions": questions,
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
            "questions": questions,
            "intent": "",
        }
    if items:
        raise StudioError("items", "dynamic choices store only the intent")
    # A blank close can name dynamic choices before anyone writes an intent.
    return {
        "close_style": style,
        "answer_style": answer,
        "choice_mode": "dynamic",
        "items": [],
        "questions": questions,
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


_STRUCTURAL = ("op", "kind", "code")
_CLOSE_FIELDS = frozenset({"close_style", "answer_style", "choice_mode", "items", "questions", "intent"})
# Parent is accepted on an add only. On an update it is redundant and dropped.
_TIER_FIELDS = {
    "course": frozenset(COURSE_FIELDS),
    "unit": frozenset(NODE_FIELDS),
    "quest": frozenset(NODE_FIELDS) | {"close", "goals"},
    "move": frozenset(NODE_FIELDS),
}


def _log_drop(field: str, kind, code) -> None:
    logger.info("studio patch dropped %s on %s %s", field, kind, code)


def _sanitize_close(value, kind, code):
    if not isinstance(value, dict):
        return value
    for key, item in value.items():
        if key not in _CLOSE_FIELDS and item is not None:
            _log_drop(f"close.{key}", kind, code)
    return {key: value[key] for key in _CLOSE_FIELDS if key in value}


def _keep_tier_fields(raw: dict, op_name: str) -> dict:
    """Keep the fields this tier accepts. Anything else is logged and dropped."""
    kind = raw.get("kind")
    code = raw.get("code")
    allowed = set(_TIER_FIELDS.get(kind, ()))
    if op_name == "add" and kind in ("unit", "quest", "move"):
        allowed.add("parent")
    cleaned = {key: raw[key] for key in _STRUCTURAL if key in raw}
    for key, value in raw.items():
        if key in _STRUCTURAL:
            continue
        if key == "parent" and op_name != "add":
            if value is not None:
                _log_drop("parent", kind, code)
            continue
        if key not in allowed:
            if value is not None:
                _log_drop(str(key), kind, code)
            continue
        if key in ("close", "close_default") and isinstance(value, dict):
            value = _sanitize_close(value, kind, code)
        cleaned[key] = value
    return cleaned


def _phase_only(course: StudioCourse, phase: str) -> str:
    listed = ", ".join(viewed_phase(course)["codes"]) or "the open quests"
    if phase == "goals":
        return f"Goals only updates learning goals for {listed}."
    return f"Close only updates the close for {listed}."


def _outside_phase(course: StudioCourse, op_name: str, kind: str, code) -> str | None:
    """Goals and Close only touch the quests listed for that wave. Quests stays on the list."""
    view = viewed_phase(course)
    phase = view["name"]
    codes = {str(item).upper() for item in view["codes"]}
    code_text = str(code or "").strip().upper()
    if phase == "quests":
        if kind == "course":
            return "Quests only changes quests and moves."
        if kind == "unit":
            return "A unit is not part of this course."
        return None
    if phase == "goals":
        if kind == "quest" and code_text in codes and op_name in ("add", "update"):
            return None
        return _phase_only(course, "goals")
    if phase == "close":
        if kind == "quest" and code_text in codes and op_name in ("add", "update"):
            return None
        return _phase_only(course, "close")
    if op_name == "add" and code_text not in codes:
        return "This course is ready. New items are not added from a patch."
    return None


def _nodes_for(course: StudioCourse) -> dict[str, _Node]:
    nodes = {course.code: _Node("course", course.code, None, 0)}
    for quest in course.quests:
        nodes[quest.code] = _Node("quest", quest.code, course.code, quest.position)
        for move in quest.moves:
            nodes[move.code] = _Node("move", move.code, quest.code, move.position)
    return nodes


def _parent_from_code(course_code: str, kind: str, code: str) -> str | None:
    if kind != "move" or "-" not in code or not code.startswith(f"{course_code}-"):
        return None
    return code.rsplit("-", 1)[0]


def _with_inferred_parent(course_code: str, raw: dict) -> dict:
    """A move code supplies its quest when the patch left parent empty. Quests have no parent."""
    if raw.get("op") != "add" or raw.get("kind") != "move":
        return raw
    code = raw.get("code")
    if not isinstance(code, str) or not code.strip():
        return raw
    parent = raw.get("parent")
    if isinstance(parent, str) and parent.strip():
        candidate = parent.strip().upper()
        if NODE_CODE.fullmatch(candidate) and candidate.startswith(f"{course_code}-"):
            return raw
    inferred = _parent_from_code(course_code, "move", code.strip().upper())
    if not inferred:
        return raw
    copied = dict(raw)
    copied["parent"] = inferred
    return copied


def _write_rank(op) -> int:
    """Quests, then goals, then closes. Moves follow the quest they belong to."""
    if not isinstance(op, dict):
        return 9
    kind = op.get("kind")
    name = op.get("op")
    if name == "add" and kind == "quest":
        return 0
    if name == "add" and kind == "move":
        return 1
    has_goal = any(op.get(key) is not None for key in ("goals", "learning_goal", "success_criterion"))
    has_close = isinstance(op.get("close"), dict)
    if has_goal and not has_close:
        return 2
    if has_close:
        return 3
    if name == "remove":
        return 5
    return 4


def _order_writes(ops: list) -> list:
    """A confirm writes quests, then goals, then closes."""
    return sorted(list(ops), key=_write_rank)


def split_patch(course: StudioCourse, patch) -> tuple[list[dict], list[str], list[dict]]:
    """Plan each operation. A bad sibling is skipped. Nothing is written."""
    nodes = _nodes_for(course)
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
    skipped: list[str] = []
    kept: list[dict] = []
    phase = viewed_phase(course)["name"]
    for raw in _order_writes(_operations(patch)):
        try:
            if not isinstance(raw, dict):
                raise StudioError("patch", "each change must be an object")
            raw = _with_inferred_parent(course.code, raw)
            op_name = raw.get("op")
            kind = raw.get("kind")
            if op_name not in OPS:
                raise StudioError("op", "must be add, update, or remove")
            if kind == "unit":
                raise StudioError(
                    "kind",
                    "a unit is not part of this course",
                    plain="A unit is not part of this course.",
                )
            if kind not in KINDS:
                raise StudioError("kind", "must be course, quest, or move")
            blocked = _outside_phase(course, op_name, kind, raw.get("code"))
            if blocked:
                raise StudioError("phase", blocked, plain=blocked)
            cleaned = _keep_tier_fields(raw, op_name)
            if phase == "goals":
                cleaned.pop("close", None)
                cleaned.pop("title", None)
                cleaned.pop("position", None)
                if (
                    _field(cleaned, "learning_goal") is _MISSING
                    and _field(cleaned, "success_criterion") is _MISSING
                    and _field(cleaned, "goals") is _MISSING
                ):
                    raise StudioError("phase", "goals", plain=_phase_only(course, "goals"))
            elif phase == "close":
                cleaned.pop("learning_goal", None)
                cleaned.pop("success_criterion", None)
                cleaned.pop("goals", None)
                cleaned.pop("title", None)
                cleaned.pop("position", None)
                if _field(cleaned, "close") is _MISSING:
                    raise StudioError("phase", "close", plain=_phase_only(course, "close"))
            if op_name == "add":
                step = _plan_add(course.code, cleaned, nodes, state)
            elif op_name == "update":
                step = _plan_update(course.code, cleaned, nodes, state)
            else:
                step = _plan_remove(course.code, cleaned, nodes)
        except StudioError as exc:
            if exc.plain not in skipped:
                skipped.append(exc.plain)
            continue
        if step is not None:
            planned.append(step)
            kept.append(raw)
    return planned, skipped, kept


def plan_patch(course: StudioCourse, patch) -> list[dict]:
    """Check a patch against this course. Nothing is written."""
    planned, skipped, _kept = split_patch(course, patch)
    if not planned:
        plain = " ".join(skipped) if skipped else "That change had nothing to save."
        raise StudioError("patch", "needs at least one add, update, or remove", plain=plain)
    if skipped:
        raise StudioError("patch", "has a change that was skipped", plain=" ".join(skipped))
    return planned


def _siblings(nodes: dict[str, _Node], parent: str, kind: str) -> list[_Node]:
    return [node for node in nodes.values() if node.parent == parent and node.kind == kind]


def _plan_add(course_code: str, raw: dict, nodes: dict[str, _Node], state: dict) -> dict:
    kind = raw["kind"]
    if kind == "course":
        raise StudioError("op", "the course already exists")
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
    if kind == "quest":
        parent_code = course_code
    else:
        parent_code = normalize_node_code(raw.get("parent"), course_code, "parent")
        parent = nodes.get(parent_code)
        if parent is None:
            raise StudioError(
                "parent",
                f"{parent_code} is not in this course yet",
                plain=f"The parent {parent_code} is not in this course yet.",
            )
        if parent.kind != PARENT_KIND[kind]:
            raise StudioError("parent", f"{code} must be added under a {PARENT_KIND[kind]}")
    title = _text("title", raw.get("title"), required=True)
    goal = ""
    criterion = ""
    goals = None
    if kind == "quest" and _field(raw, "goals") is not _MISSING:
        goals = normalize_goals(raw.get("goals"))
        if goals:
            goal = goals[0]["learning_goal"]
            criterion = goals[0]["success_criterion"]
    else:
        if _field(raw, "learning_goal") is not _MISSING:
            goal = _text("learning_goal", raw.get("learning_goal"))
        if _field(raw, "success_criterion") is not _MISSING:
            criterion = _text("success_criterion", raw.get("success_criterion"))
    close = None
    if kind == "quest" and _field(raw, "close") is not _MISSING:
        close = normalize_close(raw.get("close"))
    row = _Node(kind, code, parent_code, 0)
    group = _siblings(nodes, parent_code, kind)
    position = len(group) + 1 if _field(raw, "position") is _MISSING else _position(raw.get("position"))
    _slot(group, row, position)
    nodes[code] = row
    planned = {
        "op": "add",
        "kind": kind,
        "code": code,
        "parent": parent_code if kind != "quest" else None,
        "title": title,
        "learning_goal": goal,
        "success_criterion": criterion,
        "position": row.position,
    }
    if kind == "quest":
        planned["close"] = close
        if goals is not None:
            planned["goals"] = goals
    return planned


def _plan_update(course_code: str, raw: dict, nodes: dict[str, _Node], state: dict) -> dict | None:
    kind = raw["kind"]
    if kind == "course":
        code = normalize_course_code(raw.get("code"))
        if code != course_code:
            raise StudioError("code", "does not match this course")
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
            return None
        return planned

    code = normalize_node_code(raw.get("code"), course_code)
    node = nodes.get(code)
    if node is None:
        raise StudioError("code", f"{code} is not in this course")
    if node.kind != kind:
        raise StudioError("kind", f"{code} is a {node.kind}")
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
    if kind == "quest" and _field(raw, "goals") is not _MISSING:
        goals = normalize_goals(raw.get("goals"))
        planned["goals"] = goals
        if goals:
            planned["learning_goal"] = goals[0]["learning_goal"]
            planned["success_criterion"] = goals[0]["success_criterion"]
        else:
            planned["learning_goal"] = ""
            planned["success_criterion"] = ""
    if kind == "quest" and _field(raw, "close") is not _MISSING:
        planned["close"] = normalize_close(raw.get("close"))
    if len(planned) == 3:
        return None
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


def _pack_items(items: list, questions: list):
    """Keep a choice list as a list. Questions share that JSON column."""
    if questions:
        return {"choices": list(items), "questions": list(questions)}
    return list(items)


def _unpack_items(stored) -> tuple[list, list]:
    if isinstance(stored, dict):
        choices = stored.get("choices") if isinstance(stored.get("choices"), list) else []
        questions = stored.get("questions") if isinstance(stored.get("questions"), list) else []
        return choices, questions
    if isinstance(stored, list):
        return list(stored), []
    return [], []


def goal_rows(quest: StudioQuest) -> list[dict]:
    """Goal 1 is the quest columns. Later rows are studio_quest_goals."""
    extras = sorted(quest.goals, key=lambda row: row.position)
    has_first = bool(str(quest.learning_goal or "").strip() or str(quest.success_criterion or "").strip())
    if not has_first and not extras:
        return []
    rows = [
        {
            "position": 1,
            "learning_goal": quest.learning_goal or "",
            "success_criterion": quest.success_criterion or "",
        }
    ]
    for extra in extras:
        rows.append(
            {
                "position": extra.position,
                "learning_goal": extra.learning_goal or "",
                "success_criterion": extra.success_criterion or "",
            }
        )
    return rows


def _goals_incomplete(quest: StudioQuest) -> bool:
    rows = goal_rows(quest)
    if not rows:
        return True
    return any(
        not str(row["learning_goal"] or "").strip() or not str(row["success_criterion"] or "").strip()
        for row in rows
    )


def _replace_goals(quest: StudioQuest, goals: list[dict]) -> None:
    """Write the goal list. Flush removed extras before the new rows, so positions do not collide."""
    session = object_session(quest)
    if not goals:
        quest.learning_goal = ""
        quest.success_criterion = ""
    else:
        quest.learning_goal = goals[0]["learning_goal"]
        quest.success_criterion = goals[0]["success_criterion"]
    for extra in list(quest.goals):
        if session is not None:
            session.delete(extra)
    quest.goals.clear()
    if session is not None:
        session.flush()
    for row in goals[1:]:
        quest.goals.append(
            StudioQuestGoal(
                position=row["position"],
                learning_goal=row["learning_goal"],
                success_criterion=row["success_criterion"],
            )
        )


def _fill_close(quest: StudioQuest, close: dict) -> None:
    row = quest.close
    if row is None:
        row = StudioQuestClose()
        quest.close = row
        session = object_session(quest)
        if session is not None:
            session.add(row)
    items = close.get("items") or []
    questions = list(close.get("questions") or [])
    if isinstance(items, dict):
        unpacked, unpacked_questions = _unpack_items(items)
        items = unpacked
        if not questions:
            questions = unpacked_questions
    row.close_style = close["close_style"]
    row.answer_style = close["answer_style"]
    row.choice_mode = close.get("choice_mode")
    row.items = _pack_items(list(items), questions)
    row.intent = close.get("intent") or ""


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
    if kind == "quest":
        row = StudioQuest(
            course_id=course.id,
            code=step["code"],
            position=step["position"],
            title=step["title"],
            learning_goal=step["learning_goal"],
            success_criterion=step["success_criterion"],
        )
        course.quests.append(row)
        _slot(list(course.quests), row, step["position"])
        if step.get("goals") is not None:
            _replace_goals(row, step["goals"])
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
    if step["kind"] == "quest":
        row = _quest(course, step["code"])
        _assign_node(row, step)
        if "position" in step:
            _slot(list(course.quests), row, step["position"])
        if "goals" in step:
            _replace_goals(row, step["goals"])
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
    if step["kind"] == "quest":
        row = _quest(course, step["code"])
        course.quests.remove(row)
        _compact(list(course.quests))
        return
    row = _move(course, step["code"])
    quest = row.quest
    quest.moves.remove(row)
    _compact(list(quest.moves))


def _quest(course: StudioCourse, code: str) -> StudioQuest:
    for quest in course.quests:
        if quest.code == code:
            return quest
    raise StudioError("code", f"{code} is not in this course")


def _move(course: StudioCourse, code: str) -> StudioMove:
    for quest in course.quests:
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
    for quest in course.quests:
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
        preferences=_preferences_without_undo(source),
        schema_version=source.schema_version,
        ready=source.ready,
    )
    db.add(course)
    db.flush()
    for quest in sorted(source.quests, key=lambda row: (row.position, row.code)):
        new_quest = StudioQuest(
            course_id=course.id,
            code=_retarget_code(quest.code, source.code, code),
            position=quest.position,
            title=quest.title,
            learning_goal=quest.learning_goal,
            success_criterion=quest.success_criterion,
        )
        course.quests.append(new_quest)
        db.flush()
        for extra in sorted(quest.goals, key=lambda row: row.position):
            new_quest.goals.append(
                StudioQuestGoal(
                    position=extra.position,
                    learning_goal=extra.learning_goal,
                    success_criterion=extra.success_criterion,
                )
            )
        if quest.close is not None:
            _copy_close(new_quest, quest.close)
        for move in sorted(quest.moves, key=lambda row: (row.position, row.code)):
            new_quest.moves.append(
                StudioMove(
                    course_id=course.id,
                    code=_retarget_code(move.code, source.code, code),
                    position=move.position,
                    title=move.title,
                    learning_goal=move.learning_goal,
                    success_criterion=move.success_criterion,
                )
            )
    db.flush()
    return course


def update_preferences(course: StudioCourse, body: dict) -> None:
    course.title = _text("title", body.get("title"), required=True)
    course.audience = normalize_audience(body.get("audience", ""))
    course.focus = _text("focus", body.get("focus", ""))
    theme_value = body.get("theme", None)
    if not isinstance(theme_value, str) or not theme_value.strip():
        described = body.get("description", "")
        if isinstance(described, str) and described.strip():
            theme_value = described
    theme = _text("theme", theme_value or "")
    if theme.lower() in {"none", "no theme"}:
        theme = ""
    course.theme = theme
    course.depth = normalize_depth(body.get("depth"))
    course.quiz_minutes = normalize_quiz_minutes(body.get("quiz_minutes", course.quiz_minutes))
    course.sources = normalize_sources(body.get("sources", ""))
    close = normalize_close(body.get("close_default"), "close_default")
    quest_count = _target_count(
        body.get("quest_count", DEFAULT_QUEST_COUNT),
        DEFAULT_QUEST_COUNT,
        "quest_count",
        "Number of quests must be a whole number from 1 to 200.",
    )
    goals_per_quest = _target_count(
        body.get("goals_per_quest", DEFAULT_GOALS_PER_QUEST),
        DEFAULT_GOALS_PER_QUEST,
        "goals_per_quest",
        "Goals per quest must be a whole number from 1 to 200.",
    )
    prefs = dict(course.preferences or {})
    prefs["close_default"] = close
    prefs["depth"] = course.depth
    prefs["quiz_minutes"] = course.quiz_minutes
    prefs["audience"] = course.audience
    prefs["theme"] = course.theme
    prefs["sources"] = course.sources
    prefs["quest_count"] = quest_count
    prefs["goals_per_quest"] = goals_per_quest
    course.preferences = prefs
    course.schema_version = SCHEMA_VERSION
    course.updated_at = _now()


def load_course(db: Session, course_id) -> StudioCourse | None:
    return db.scalar(
        select(StudioCourse)
        .where(StudioCourse.id == course_id)
        .options(
            selectinload(StudioCourse.quests).selectinload(StudioQuest.moves),
            selectinload(StudioCourse.quests).selectinload(StudioQuest.close),
            selectinload(StudioCourse.quests).selectinload(StudioQuest.goals),
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
        _planned, skipped, kept = split_patch(course, proposal)
        if not kept:
            plain = " ".join(skipped) if skipped else "That change had nothing to save."
            raise StudioError("patch", "needs at least one add, update, or remove", plain=plain)
        phase = _phase_name(proposal.get("phase")) if isinstance(proposal, dict) else None
        if phase is None:
            phase = viewed_phase(course)["name"]
        stored = {"operations": copy.deepcopy(kept), "phase": phase}
        if skipped:
            text = text.rstrip() + "\n" + "\n".join(skipped)
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


_CONFIRM_EXACT = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "ok",
        "okay",
        "sure",
        "confirm",
        "do it",
        "go ahead",
        "write it",
        "write that",
        "save that",
        "add them",
        "add those",
        "add it",
        "add that",
    }
)
_CONFIRM_BLOCK = re.compile(r"\b(?:but|except|change|instead|don't|do not|wait|not yet)\b", re.IGNORECASE)
_THIN_DESCRIPTION = frozenset({"", "none", "no theme", "no description"})


def _confirm_text(text: str) -> str | None:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if not collapsed or "?" in collapsed or _CONFIRM_BLOCK.search(collapsed):
        return None
    return collapsed.rstrip(".!").strip().lower()


def is_explicit_confirm(text: str) -> bool:
    """A short yes that writes the held proposal. A question or a change request does not."""
    normalized = _confirm_text(text)
    if normalized is None:
        return False
    if normalized in _CONFIRM_EXACT:
        return True
    if re.match(r"^(?:yes|ok|okay|sure)[,.]?\s+(?:add|commit|save|move)\b", normalized):
        return True
    if re.match(r"^add those\b", normalized):
        return True
    return re.match(r"^(?:please\s+)?(?:commit|save them|save those|move on)\b", normalized) is not None


def _wants_next_stage(text: str) -> bool:
    normalized = _confirm_text(text)
    if normalized is None:
        return False
    return re.search(r"\b(?:move on|next stage|next phase)\b", normalized) is not None


def _stage_reply(course: StudioCourse, *, wrote: bool) -> str:
    """Talk about the stage on screen. Do not ask the confirm question again."""
    phase = course_phase(course)
    per_quest = goals_per_quest_of(course)
    quest_count = quest_count_of(course)
    if phase["name"] == "goals":
        lead = "Goals/Success Criteria is the stage on screen."
        detail = (
            "A quest can hold several goals, each with its own success criterion. "
            f"I can draft {per_quest} goals for each open quest."
        )
    elif phase["name"] == "close":
        lead = "Close is the stage on screen."
        detail = (
            "I can offer one close per quest, normally at least one question. "
            "An empty question list is saved when you ask for it."
        )
    elif phase["name"] == "ready":
        lead = "Ready is the stage on screen."
        detail = "Mark ready can be turned on."
    else:
        lead = "Quests is still the stage on screen."
        detail = (
            "A quest is one piece of the course. "
            f"I can draft {quest_count} quests around the course description."
        )
    if wrote:
        return f"Those changes are now in the course. {lead} {detail} You can undo this write."
    return f"{lead} {detail}"


def description_is_specific(theme: str) -> bool:
    text = (theme or "").strip()
    if text.lower() in _THIN_DESCRIPTION:
        return False
    return len(re.findall(r"[A-Za-z0-9']+", text)) >= 8


def _quest_titles(theme: str, count: int) -> list[str]:
    count = max(1, min(count, 40))
    parts = [part.strip(" .") for part in re.split(r"\s*,\s*|\s+\band\b\s+", theme, flags=re.IGNORECASE)]
    parts = [part[: TEXT_LIMITS["title"]] for part in parts if part]
    titles: list[str] = []
    for part in parts:
        if len(titles) >= count:
            break
        titles.append(part)
    short = theme.strip()
    if len(short) > 60:
        short = short[:60].rstrip()
    stems = ("opening", "practice", "close")
    number = 1
    while len(titles) < count:
        if number <= len(stems):
            titles.append(f"{short}: {stems[number - 1]}"[: TEXT_LIMITS["title"]])
        else:
            titles.append(f"{short}: quest {number}"[: TEXT_LIMITS["title"]])
        number += 1
    return titles[:count]


def _opening_text(course: StudioCourse) -> str:
    count = quest_count_of(course)
    per_quest = goals_per_quest_of(course)
    return (
        "This studio builds one course with you. "
        "Nothing is written into the tree until you confirm it in the chat.\n"
        "A quest is one piece of the course the learner works through. "
        f"Quests asks whether to draft {count} quests around the course description.\n"
        "Goals/Success Criteria says a quest can hold several goals, each with its own criterion. "
        f"That phase can offer {per_quest} goals per quest.\n"
        "Close offers one close per quest, normally at least one question, and an empty list when you ask for it.\n"
        "Ready is when those three are filled and you say the draft is complete."
    )


def opening_for(course: StudioCourse) -> tuple[str, dict | None]:
    """The first assistant message. A thin description does not carry a quest patch."""
    intro = _opening_text(course)
    theme = (course.theme or "").strip()
    if course.quests:
        return (
            f"{intro}\n"
            "Quests is already started. Tell me what you want to change in the phase on screen.",
            None,
        )
    if not description_is_specific(theme):
        return (
            f"{intro}\n"
            "The course description is still thin, so I will not propose quests yet. "
            "What is the topic, who is the audience, and what should the course cover?",
            None,
        )
    count = min(quest_count_of(course), 40)
    titles = _quest_titles(theme, count)
    listed = "\n".join(f"{index}. {title}" for index, title in enumerate(titles, start=1))
    operations = [
        {
            "op": "add",
            "kind": "quest",
            "code": f"{course.code}-Q{index}",
            "parent": None,
            "title": title,
            "position": index,
        }
        for index, title in enumerate(titles, start=1)
    ]
    return (
        f"{intro}\n"
        f"The course description is specific enough to draft {count} quests. "
        f"I would add these quests:\n{listed}\n"
        "What would you change, or should I write these quests?",
        {"operations": operations, "phase": "quests"},
    )


def seed_opening(db: Session, course: StudioCourse) -> list[StudioMessage]:
    existing = list_messages(db, course)
    if existing:
        return existing
    content, proposal = opening_for(course)
    add_message(db, course, role="assistant", content=content, proposal=proposal)
    return list_messages(db, course)


def _pending_proposals(messages: list[StudioMessage]) -> list[StudioMessage]:
    return [
        message
        for message in messages
        if message.role == "assistant" and message.proposal and not message.applied
    ]


def confirm_turn(db: Session, course: StudioCourse, content: str) -> dict | None:
    """Write the held proposal when the chat message is an explicit confirm.

    A second confirm, with nothing left to write, answers about the stage on
    screen. It does not ask the confirm question again.
    """
    text = content.strip()
    if not text:
        raise StudioError("content", "is required")
    if len(text) > 20000:
        raise StudioError("content", "is too long")
    if not is_explicit_confirm(text):
        return None
    pending = _pending_proposals(list_messages(db, course))
    user = add_message(db, course, role="user", content=text, proposal=None)
    wrote = False
    if pending:
        ops: list[dict] = []
        for message in pending:
            ops.extend(_proposal_ops(message))
        _remember_writes(course, pending)
        apply_patch(db, course, {"operations": ops})
        for message in pending:
            message.applied = True
        if course_phase(course)["name"] != "ready":
            course.ready = False
        course.updated_at = _now()
        db.flush()
        wrote = True
    fresh = load_course(db, course.id) or course
    if _wants_next_stage(text):
        set_phase_view(fresh, course_phase(fresh)["name"])
    assistant = add_message(db, fresh, role="assistant", content=_stage_reply(fresh, wrote=wrote), proposal=None)
    fresh = load_course(db, course.id) or fresh
    return {"wrote": wrote, "handled": True, "user": user, "assistant": assistant, "course": fresh}


_UNDO = "_undo"


def _preferences_without_undo(course: StudioCourse) -> dict:
    prefs = copy.deepcopy(course.preferences or {})
    if isinstance(prefs, dict):
        prefs.pop(_UNDO, None)
    return prefs if isinstance(prefs, dict) else {}


def has_undo(course: StudioCourse) -> bool:
    prefs = course.preferences if isinstance(course.preferences, dict) else {}
    undo = prefs.get(_UNDO)
    return isinstance(undo, dict) and isinstance(undo.get("course"), dict)


def _phase_name(name) -> str | None:
    """Stored phase id structure opens on Quests."""
    if name == "structure":
        return "quests"
    if name in ("quests", "goals", "close", "ready"):
        return name
    return None


def _proposal_phase(proposal) -> str | None:
    if isinstance(proposal, dict):
        return _phase_name(proposal.get("phase"))
    return None


def _proposal_ops(message: StudioMessage) -> list[dict]:
    proposal = message.proposal if isinstance(message.proposal, dict) else None
    ops = proposal.get("operations") if proposal else None
    if not isinstance(ops, list) or not ops:
        raise StudioError("proposal", "there is nothing to accept")
    return list(ops)


def _pick_indexes(count: int, indexes: list[int] | None) -> list[int]:
    if indexes is None:
        return list(range(count))
    if not indexes:
        raise StudioError("items", "choose at least one", plain="Choose at least one change.")
    chosen: list[int] = []
    for index in indexes:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= count or index in chosen:
            raise StudioError("items", "is not in this proposal", plain="That change is not in this proposal.")
        chosen.append(index)
    return chosen


def _store_ops(ops: list[dict], phase: str | None) -> dict:
    stored: dict = {"operations": ops}
    if phase:
        stored["phase"] = phase
    return stored


def _close_snapshot(quest: StudioQuest) -> dict | None:
    if quest.close is None:
        return None
    items, questions = _unpack_items(quest.close.items)
    return {
        "close_style": quest.close.close_style,
        "answer_style": quest.close.answer_style,
        "choice_mode": quest.close.choice_mode,
        "items": copy.deepcopy(items),
        "questions": copy.deepcopy(questions),
        "intent": quest.close.intent or "",
    }


def _course_snapshot(course: StudioCourse) -> dict:
    quests = []
    for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
        quests.append(
            {
                "code": quest.code,
                "position": quest.position,
                "title": quest.title,
                "learning_goal": quest.learning_goal,
                "success_criterion": quest.success_criterion,
                "goals": goal_rows(quest),
                "close": _close_snapshot(quest),
                "moves": [
                    {
                        "code": move.code,
                        "position": move.position,
                        "title": move.title,
                        "learning_goal": move.learning_goal,
                        "success_criterion": move.success_criterion,
                    }
                    for move in sorted(quest.moves, key=lambda row: (row.position, row.code))
                ],
            }
        )
    return {
        "title": course.title,
        "audience": course.audience,
        "focus": course.focus,
        "theme": course.theme,
        "depth": course.depth,
        "quiz_minutes": course.quiz_minutes,
        "sources": course.sources,
        "ready": bool(course.ready),
        "schema_version": course.schema_version,
        "preferences": _preferences_without_undo(course),
        "quests": quests,
    }


def _snapshot_quests(snap: dict) -> list[dict]:
    """New snapshots store quests. An older snapshot stored them under units."""
    if isinstance(snap.get("quests"), list):
        rows = [dict(item) for item in snap["quests"] if isinstance(item, dict)]
    else:
        rows = []
        for unit in snap.get("units") or []:
            if not isinstance(unit, dict):
                continue
            for quest in unit.get("quests") or []:
                if isinstance(quest, dict):
                    rows.append(dict(quest))
    rows.sort(key=lambda item: (item.get("position") or 0, str(item.get("code") or "")))
    for index, item in enumerate(rows, start=1):
        item["position"] = index
    return rows


def _message_undo(message: StudioMessage) -> dict:
    return {
        "id": str(message.id),
        "applied": bool(message.applied),
        "proposal": copy.deepcopy(message.proposal),
    }


def _remember_undo(course: StudioCourse, message: StudioMessage | None) -> None:
    prefs = _preferences_without_undo(course)
    prefs[_UNDO] = {
        "message_id": str(message.id) if message is not None else None,
        "applied": bool(message.applied) if message is not None else None,
        "proposal": copy.deepcopy(message.proposal) if message is not None else None,
        "messages": [_message_undo(message)] if message is not None else [],
        "course": _course_snapshot(course),
    }
    course.preferences = prefs


def _remember_writes(course: StudioCourse, messages: list[StudioMessage]) -> None:
    """One undo covers every proposal a confirm writes."""
    prefs = _preferences_without_undo(course)
    last = messages[-1] if messages else None
    prefs[_UNDO] = {
        "message_id": str(last.id) if last is not None else None,
        "applied": bool(last.applied) if last is not None else None,
        "proposal": copy.deepcopy(last.proposal) if last is not None else None,
        "messages": [_message_undo(message) for message in messages],
        "course": _course_snapshot(course),
    }
    course.preferences = prefs


def _restore_course(db: Session, course: StudioCourse, snap: dict) -> None:
    for key in ("title", "audience", "focus", "theme", "depth", "quiz_minutes", "sources", "ready", "schema_version"):
        setattr(course, key, snap[key])
    course.preferences = dict(snap.get("preferences") or {})
    for quest in list(course.quests):
        db.delete(quest)
    course.quests.clear()
    db.flush()
    db.expire(course, ["quests"])
    for quest_data in _snapshot_quests(snap):
        quest = StudioQuest(
            course_id=course.id,
            code=quest_data["code"],
            position=quest_data["position"],
            title=quest_data["title"],
            learning_goal=quest_data.get("learning_goal") or "",
            success_criterion=quest_data.get("success_criterion") or "",
        )
        course.quests.append(quest)
        db.flush()
        goals = quest_data.get("goals")
        if isinstance(goals, list) and goals:
            _replace_goals(
                quest,
                [
                    {
                        "position": item.get("position") or index,
                        "learning_goal": item.get("learning_goal") or "",
                        "success_criterion": item.get("success_criterion") or "",
                    }
                    for index, item in enumerate(goals, start=1)
                    if isinstance(item, dict)
                ],
            )
        close = quest_data.get("close")
        if isinstance(close, dict):
            _fill_close(quest, close)
        for move_data in quest_data.get("moves") or []:
            quest.moves.append(
                StudioMove(
                    course_id=course.id,
                    code=move_data["code"],
                    position=move_data["position"],
                    title=move_data["title"],
                    learning_goal=move_data.get("learning_goal") or "",
                    success_criterion=move_data.get("success_criterion") or "",
                )
            )
    db.flush()


def accept_proposal(
    db: Session, course: StudioCourse, message: StudioMessage, indexes: list[int] | None = None
) -> None:
    if message.course_id != course.id:
        raise StudioError("message", "is not part of this course", status=404)
    if message.applied:
        raise StudioError("proposal", "that change is already saved", status=409)
    ops = _proposal_ops(message)
    chosen = _pick_indexes(len(ops), indexes)
    selected = [ops[index] for index in chosen]
    _remember_undo(course, message)
    apply_patch(db, course, {"operations": selected})
    chosen_set = set(chosen)
    remaining = [op for index, op in enumerate(ops) if index not in chosen_set]
    if remaining:
        message.proposal = _store_ops(remaining, _proposal_phase(message.proposal))
        message.applied = False
    else:
        message.applied = True
    if course_phase(course)["name"] != "ready":
        course.ready = False
    course.updated_at = _now()
    db.flush()


def dismiss_proposal(course: StudioCourse, message: StudioMessage, indexes: list[int] | None = None) -> None:
    if message.course_id != course.id:
        raise StudioError("message", "is not part of this course", status=404)
    if message.applied:
        raise StudioError("proposal", "that change is already saved", status=409)
    ops = _proposal_ops(message)
    if indexes is None:
        message.proposal = None
    else:
        chosen = set(_pick_indexes(len(ops), indexes))
        remaining = [op for index, op in enumerate(ops) if index not in chosen]
        message.proposal = _store_ops(remaining, _proposal_phase(message.proposal)) if remaining else None
    course.updated_at = _now()


def edit_item(
    db: Session,
    course: StudioCourse,
    *,
    kind: str,
    code: str,
    title: str | None,
    learning_goal: str | None,
    success_criterion: str | None,
) -> None:
    if kind == "unit":
        raise StudioError("kind", "a unit is not part of this course", plain="A unit is not part of this course.")
    if kind not in ("quest", "move"):
        raise StudioError("kind", "must be a quest or move", plain="Edit a quest or a move.")
    raw: dict = {"op": "update", "kind": kind, "code": code}
    if title is not None:
        raw["title"] = title
    if learning_goal is not None:
        raw["learning_goal"] = learning_goal
    if success_criterion is not None:
        raw["success_criterion"] = success_criterion
    cleaned = _keep_tier_fields(raw, "update")
    step = _plan_update(course.code, cleaned, _nodes_for(course), {})
    if step is None:
        raise StudioError("patch", "needs a change", plain="That change had nothing to save.")
    _remember_undo(course, None)
    _apply(course, [step])
    if course_phase(course)["name"] != "ready":
        course.ready = False
    course.updated_at = _now()
    db.flush()


def undo_last(db: Session, course: StudioCourse) -> None:
    prefs = course.preferences if isinstance(course.preferences, dict) else {}
    undo = prefs.get(_UNDO) if isinstance(prefs, dict) else None
    if not isinstance(undo, dict) or not isinstance(undo.get("course"), dict):
        raise StudioError("proposal", "nothing to undo", plain="There is nothing to undo.")
    message = None
    message_id = undo.get("message_id")
    if message_id:
        message = db.get(StudioMessage, UUID(str(message_id)))
        if message is None or message.course_id != course.id:
            raise StudioError("message", "that undo is no longer available", plain="That undo is no longer available.")
    _restore_course(db, course, undo["course"])
    rows = undo.get("messages")
    if isinstance(rows, list) and rows:
        for item in rows:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            row = db.get(StudioMessage, UUID(str(item["id"])))
            if row is None or row.course_id != course.id:
                continue
            row.proposal = copy.deepcopy(item.get("proposal"))
            row.applied = bool(item.get("applied"))
    elif message is not None:
        message.proposal = copy.deepcopy(undo.get("proposal"))
        message.applied = bool(undo.get("applied"))
    course.updated_at = _now()
    db.flush()


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
    quests = sorted(course.quests, key=lambda row: (row.position, row.code))
    if not quests:
        return {"name": "quests", "label": "Quests", "open_codes": [course.code]}
    missing_goals: list[str] = []
    missing_close: list[str] = []
    for quest in quests:
        if _goals_incomplete(quest):
            missing_goals.append(quest.code)
        style = quest.close.close_style if quest.close is not None else ""
        if not str(style or "").strip():
            missing_close.append(quest.code)
    if missing_goals:
        return {"name": "goals", "label": "Goals/Success Criteria", "open_codes": missing_goals}
    if missing_close:
        return {"name": "close", "label": "Close", "open_codes": missing_close}
    return {"name": "ready", "label": "Ready", "open_codes": []}


PHASES = (
    ("quests", "Quests"),
    ("goals", "Goals/Success Criteria"),
    ("close", "Close"),
    ("ready", "Ready"),
)
PHASE_ORDER = {name: index for index, (name, _label) in enumerate(PHASES)}
PHASE_LABELS = dict(PHASES)


def _stored_phase_view(course: StudioCourse) -> str | None:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    value = raw.get("phase_view") if isinstance(raw, dict) else None
    if value == "structure":
        value = "quests"
    if value in PHASE_ORDER:
        return str(value)
    return None


def _quest_codes(course: StudioCourse) -> list[str]:
    return [quest.code for quest in sorted(course.quests, key=lambda row: (row.position, row.code))]


def _codes_in_phase(course: StudioCourse, name: str) -> list[str]:
    if name == "quests":
        codes = _quest_codes(course)
        return codes or [course.code]
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
    if name == "structure":
        name = "quests"
    if name not in PHASE_ORDER:
        raise StudioError(
            "phase",
            "must be a course phase",
            plain="Choose Quests, Goals/Success Criteria, Close, or Ready.",
        )
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
                "A quest can hold several goals, each with its own criterion. "
                "Draft a criterion whenever you draft a goal. "
                "An update names that quest's code and sets parent to null. "
                "Do not wipe close style."
            )
        elif view["name"] == "quests":
            focus = (
                "Update these quests by code. Set parent to null. "
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
    count = quest_count_of(course)
    per_quest = goals_per_quest_of(course)
    if phase["name"] == "quests":
        focus = (
            f"A quest is one piece of the course. Ask whether to draft {count} quests around the course description. "
            "Add the missing quests. Empty learning goals are allowed."
        )
        later = (
            "Later phases, in one line: Goals/Success Criteria, then Close, then Ready. "
            "Do not fill learning goals or close style in this patch."
        )
    elif phase["name"] == "goals":
        focus = (
            "Offer a learning goal for each open quest, addressed by that quest's code. "
            f"A quest can hold several goals, each with its own criterion. Offer {per_quest} goals per quest. "
            "Draft a criterion whenever you draft a goal. "
            "An update names that quest's code and sets parent to null."
        )
        later = "Later phases, in one line: Close, then Ready. Do not fill close style in this patch."
    elif phase["name"] == "close":
        focus = (
            "Offer one close per quest, addressed by that quest's code. "
            "Normally include at least one question. An empty question list is saved when asked. "
            "An update names that code and sets parent to null."
        )
        later = "Later phase, in one line: Ready. Do not add new goals in this patch."
    else:
        focus = "Quests, learning goals, and close styles are in place. Mark ready can be turned on."
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
    for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
        rows = goal_rows(quest)
        if not rows or any(not str(row["learning_goal"] or "").strip() for row in rows):
            gaps.append(f"{quest.code}: no learning goal")
        elif any(not str(row["success_criterion"] or "").strip() for row in rows):
            gaps.append(f"{quest.code}: no success criterion")
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
        items=list(close.get("items") or []),
        questions=list(close.get("questions") or []),
        intent=close["intent"],
    )


def _row_close(row: StudioQuestClose | None) -> StudioCloseOut | None:
    if row is None:
        return None
    items, questions = _unpack_items(row.items)
    return StudioCloseOut(
        close_style=row.close_style,
        answer_style=row.answer_style,
        choice_mode=row.choice_mode,
        items=items,
        questions=questions,
        intent=row.intent or "",
    )


def course_out(course: StudioCourse) -> StudioCourseOut:
    quests = []
    for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
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
                goals=[StudioGoalOut(**row) for row in goal_rows(quest)],
                close=_row_close(quest.close),
                moves=moves,
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
        quests=quests,
        quest_count=quest_count_of(course),
        goals_per_quest=goals_per_quest_of(course),
        undo=has_undo(course),
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


def _goals_schema() -> dict:
    return {
        "anyOf": [
            {"type": "null"},
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "learning_goal": {"type": "string"},
                        "success_criterion": {"type": "string"},
                        "position": {"type": "integer"},
                    },
                    "required": ["learning_goal", "success_criterion", "position"],
                },
            },
        ]
    }


def _phase_operation_schema(phase: str) -> dict:
    if phase == "goals":
        properties = {
            "op": {"type": "string", "enum": ["update", "add"]},
            "kind": {"type": "string", "enum": ["quest"]},
            "code": {"type": "string"},
            "learning_goal": {"type": ["string", "null"]},
            "success_criterion": {"type": ["string", "null"]},
            "goals": _goals_schema(),
        }
    elif phase == "close":
        properties = {
            "op": {"type": "string", "enum": ["update", "add"]},
            "kind": {"type": "string", "enum": ["quest"]},
            "code": {"type": "string"},
            "close": {"anyOf": [{"type": "null"}, _close_schema()]},
        }
    elif phase == "ready":
        properties = {
            "op": {"type": "string", "enum": ["update", "remove"]},
            "kind": {"type": "string", "enum": ["quest", "move"]},
            "code": {"type": "string"},
            "title": {"type": ["string", "null"]},
            "learning_goal": {"type": ["string", "null"]},
            "success_criterion": {"type": ["string", "null"]},
            "goals": _goals_schema(),
            "position": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
            "close": {"anyOf": [{"type": "null"}, _close_schema()]},
        }
    else:
        properties = {
            "op": {"type": "string", "enum": ["add", "update", "remove"]},
            "kind": {"type": "string", "enum": ["quest", "move"]},
            "code": {"type": "string"},
            "parent": {"type": ["string", "null"]},
            "title": {"type": ["string", "null"]},
            "position": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def response_schema(course: StudioCourse) -> dict:
    """The only patch shape the model may emit for the phase on screen."""
    phase = viewed_phase(course)["name"]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reply": {
                "type": "string",
                "description": (
                    "What the creator reads. Talk through the suggestion for the phase on screen "
                    "and ask one clear question. Say which framework a suggestion comes from. "
                    "Do not say the course was saved. The tree changes only after a confirm in the chat."
                ),
            },
            "patch": {
                "description": "Null when nothing should change. Otherwise operations allowed in this phase.",
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "operations": {
                                "type": "array",
                                "maxItems": 40,
                                "items": _phase_operation_schema(phase),
                            }
                        },
                        "required": ["operations"],
                    },
                ],
            },
        },
        "required": ["reply", "patch"],
    }


def system_prompt(course: StudioCourse, messages: list[StudioMessage]) -> str:
    tree = course_out(course).model_dump(mode="json")
    pending = []
    for message in messages:
        if message.proposal and not message.applied:
            pending.append(message.proposal)
    pending_note = "There is no held patch."
    if pending:
        pending_note = (
            "These patches are held and are not part of the course JSON below. "
            "They are written only after the creator confirms in the chat:\n"
            + "\n".join(str(item) for item in pending)
        )
    description = course.theme.strip() if course.theme and course.theme.strip() else "none yet"
    return (
        "You are helping a person build one course in the CreateCourse studio.\n"
        f"Course description: {description}\n"
        "Quests, learning goals, and close items follow this course description.\n"
        "The creator states a focus. You propose the next slice for the phase on screen, "
        "talk through it, and ask one clear question about what to change.\n"
        "You may use widely known national curricula and standard texts as suggestions. "
        "You must say which framework a suggestion comes from. "
        "Label every curriculum idea as a suggestion.\n"
        "You have no web search and no document upload. Do not claim you searched the web or read an uploaded file.\n"
        "Nothing is written until the creator confirms in the chat, for example commit, yes, add those, save them, or move on. "
        "Until then the tree stays as it is. "
        "After a confirm, talk about the stage now on screen. Do not ask the same confirm question again. "
        "The server still checks. A rejected operation is skipped and the rest can be saved after a confirm. "
        "Do not say the course was saved, and do not say the structure was written.\n"
        "The response schema lists the only fields for this phase. "
        "Goals and Close refuse operations for any other code.\n"
        f"{phase_instructions(course)}"
        "Return a reply plus an optional patch. The patch is a list of operations. "
        "Each operation is add, update, or remove, and it names a code. "
        "Do not rewrite the whole tree in prose. The server ignores anything that is not a typed patch.\n"
        "Each add names these fields: code, parent code, title, position as an integer from 1, "
        "learning goal, success criterion, and quest-close choices. "
        "In the patch JSON those fields are code, parent, title, position, learning_goal, "
        "success_criterion, goals, and close.\n"
        "A quest can hold several goals. Each goal has its own success criterion. "
        "A success criterion is one observable action about this goal only, specific enough that the close can test it. "
        "It is not a quiz item. "
        "Example: goal “Understand that the angles of a triangle add to 180°”, "
        "criterion “States that the three angles add to 180° and uses that to find a missing angle.” "
        "Draft a criterion whenever you draft a goal. The tree changes only after a confirm in the chat.\n"
        "A position of 0 is invalid. Leave position null and the server fills the next free number. "
        "A position outside 1 to 200, or past the end of the list, is skipped and reported in one sentence. "
        "The other operations can still be saved.\n"
        "A missing learning goal or quest-close choice does not block the write. "
        "The course is a draft from the moment it is created. "
        "The tree marks a missing learning goal, a goal with no success criterion, and a missing close style. "
        "An empty question list is allowed and is not a gap. "
        "Those marks do not undo the draft. "
        "Mark ready only records that the creator says the draft is complete.\n"
        "The course close default is a preference in the header. "
        "Copy it into a quest's quest-close choices when you want that close. "
        "If close is null, the quest is stored with no close style. The server does not invent one.\n"
        "Normally offer at least one question on a close. Save an empty question list when the creator asks for it.\n"
        "To change an item, name its code and set parent to null. A parent sent on an update is ignored. "
        "An add of a code that is already in this course is saved as an update of that item. "
        "To add an item, choose a new short stable code "
        f"such as {course.code}-Q1 or {course.code}-Q1-M1 and name the parent code when the item is a move.\n"
        "On an add, a quest has no parent. A move parent is a quest code.\n"
        "Codes stay inside this course. Use null for a field you are not changing. An add requires a title.\n"
        "close_style is one or several. answer_style is multiple_choice, essay, or mixed. "
        "Essay stores neither items nor intent.\n"
        "depth, sources, audience, focus, and theme are course preferences. "
        "depth is survey, standard, or go_deep. "
        f"Number of quests is a target of {quest_count_of(course)}, and goals per quest is a target of {goals_per_quest_of(course)}. "
        "Neither number is a hard cap.\n"
        "The server drops course preferences copied onto a quest or move, and still saves the item.\n"
        "sources is the framework to honor, or none.\n"
        f"{pending_note}\n"
        "The course so far, read from the database:\n"
        f"{json.dumps(tree)}"
    )
