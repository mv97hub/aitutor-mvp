"""Grade a choice widget, and check a lesson diagram before it reaches the client.

The model never scores these taps. A diagram is a checked description the app draws.
The model never returns an image file, an image URL, or a free-form drawing prompt.
"""

from __future__ import annotations

import math
import re

HINT_TIERS = ("nudge", "analogy", "scaffold")

# Kinds the reply schema may name. This pass draws a triangle only.
NAMED_DIAGRAM_KINDS = frozenset({"triangle", "graph", "map"})
_TRIANGLE_KEYS = frozenset({"kind", "sides", "angles", "right_angle"})
_SIDE_KEYS = frozenset({"label", "length"})
_ANGLE_KEYS = frozenset({"label", "degrees"})
_GEOMETRY = "geometry"
_ANGLE_SUM = 180.0
_SUM_TOLERANCE = 1.0
_RIGHT_TOLERANCE = 1.0
_RATIO_TOLERANCE = 0.05
_MAX_LABEL = 24
_MAX_SIDE = 10_000.0
_MARKUP = re.compile(r"[<>&]|://|www\.|javascript:", re.IGNORECASE)


def hint_tier_for(failed_attempts: int) -> str:
    if failed_attempts <= 0:
        return "nudge"
    if failed_attempts == 1:
        return "analogy"
    return "scaffold"


def hint_text(ladder: dict | None, tier: str) -> str:
    if not isinstance(ladder, dict):
        return ""
    return str(ladder.get(tier) or "").strip()


def choice_ids(choice: str | list[str]) -> list[str]:
    if isinstance(choice, str):
        text = choice.strip()
        return [text] if text else []
    return [str(item).strip() for item in choice if str(item).strip()]


def grade_choice(quiz: dict, choice: str | list[str]) -> dict:
    """Return correct, score, misconception. Score is 100 or 0."""
    qtype = quiz.get("type")
    expected = quiz.get("answer")
    picked = choice_ids(choice)
    by_id = {
        str(item.get("id")): item
        for item in (quiz.get("choices") or [])
        if isinstance(item, dict)
    }
    known = set(by_id)
    if not picked or any(item not in known for item in picked):
        return {
            "correct": False,
            "score": 0,
            "misconception": str(quiz.get("misconception") or "").strip() or None,
        }
    if qtype in {"single", "flaw"}:
        correct = len(picked) == 1 and picked[0] == expected
        if correct:
            return {"correct": True, "score": 100, "misconception": None}
        item = by_id.get(picked[0], {})
        note = str(item.get("misconception") or quiz.get("misconception") or "").strip()
        return {"correct": False, "score": 0, "misconception": note or None}
    if qtype == "multi":
        expected_ids = set(expected if isinstance(expected, list) else [expected])
        correct = set(picked) == expected_ids
    elif qtype == "order":
        expected_ids = list(expected if isinstance(expected, list) else [expected])
        correct = picked == expected_ids
    else:
        correct = False
    if correct:
        return {"correct": True, "score": 100, "misconception": None}
    note = str(quiz.get("misconception") or "").strip()
    return {"correct": False, "score": 0, "misconception": note or None}


def public_quiz(quiz: dict | None) -> dict | None:
    """Kid-facing widget. Answers and stored misconceptions stay on the server."""
    if not isinstance(quiz, dict) or quiz.get("type") not in {"single", "multi", "flaw", "order"}:
        return None
    choices = []
    for item in quiz.get("choices") or []:
        if not isinstance(item, dict):
            continue
        choices.append({"id": str(item.get("id")), "text": str(item.get("text") or "")})
    if len(choices) < 2:
        return None
    return {
        "type": quiz["type"],
        "prompt": str(quiz.get("prompt") or ""),
        "choices": choices,
        "explain": bool(quiz.get("explain")),
    }


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _label(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or len(text) > _MAX_LABEL:
        return None
    if any(ord(char) < 32 for char in text):
        return None
    if _MARKUP.search(text):
        return None
    return text


def _pairs(value: object, keys: frozenset[str], number_key: str) -> list[tuple[str, float]] | None:
    if not isinstance(value, list) or len(value) != 3:
        return None
    pairs: list[tuple[str, float]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != keys:
            return None
        label = _label(item.get("label"))
        number = _finite(item.get(number_key))
        if label is None or number is None:
            return None
        pairs.append((label, number))
    return pairs


def _right_mark(value: object, angles: list[float]) -> bool | None:
    if value is None:
        marked = False
    elif isinstance(value, bool):
        marked = value
    else:
        return None
    if not marked:
        return False
    if any(abs(angle - 90.0) <= _RIGHT_TOLERANCE for angle in angles):
        return True
    return None


def _sides_match_angles(sides: list[float], angles: list[float]) -> bool:
    a, b, c = sides
    angle_a = math.radians(angles[0])
    placed_x = b * math.cos(angle_a)
    placed_y = b * math.sin(angle_a)
    placed = math.hypot(placed_x - c, placed_y)
    if placed <= 0 or abs(placed - a) / a > _RATIO_TOLERANCE:
        return False
    ratios: list[float] = []
    for side, angle in zip(sides, angles, strict=True):
        sine = math.sin(math.radians(angle))
        if sine <= 1e-6:
            return False
        ratios.append(side / sine)
    base = ratios[0]
    return all(abs(item - base) / base <= _RATIO_TOLERANCE for item in ratios)


def _triangle(diagram: dict) -> dict | None:
    if set(diagram) - _TRIANGLE_KEYS:
        return None
    sides = _pairs(diagram.get("sides"), _SIDE_KEYS, "length")
    angles = _pairs(diagram.get("angles"), _ANGLE_KEYS, "degrees")
    if sides is None or angles is None:
        return None
    lengths = [length for _, length in sides]
    degrees = [degree for _, degree in angles]
    if any(length <= 0 or length > _MAX_SIDE for length in lengths):
        return None
    if any(degree <= 0 or degree >= 180 for degree in degrees):
        return None
    if abs(sum(degrees) - _ANGLE_SUM) > _SUM_TOLERANCE:
        return None
    left, middle, right = lengths
    if left + middle <= right or left + right <= middle or middle + right <= left:
        return None
    if not _sides_match_angles(lengths, degrees):
        return None
    mark = _right_mark(diagram.get("right_angle"), degrees)
    if mark is None:
        return None
    return {
        "kind": "triangle",
        "sides": [{"label": label, "length": length} for label, length in sides],
        "angles": [{"label": label, "degrees": degree} for label, degree in angles],
        "right_angle": mark,
    }


def _checked_diagram(diagram: object, course_code: str) -> dict | None:
    """Return a triangle the app can draw, or None when the picture is refused."""
    if not isinstance(diagram, dict):
        return None
    kind = diagram.get("kind")
    if not isinstance(kind, str) or kind not in NAMED_DIAGRAM_KINDS:
        return None
    if kind != "triangle":
        return None
    if (course_code or "").strip().lower() != _GEOMETRY:
        return None
    return _triangle(diagram)


def guard_reply(turn: dict, course_code: str) -> dict:
    """Keep the text reply. Drop a diagram that fails the check.

    A failed picture does not fail the turn.
    """
    if not isinstance(turn, dict):
        return {"reply": ""}
    kept = {key: value for key, value in turn.items() if key != "diagram"}
    diagram = _checked_diagram(turn.get("diagram"), course_code)
    if diagram is not None:
        kept["diagram"] = diagram
    return kept
