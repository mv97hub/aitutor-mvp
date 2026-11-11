"""KC Course Creator pipeline: brief, blueprint, unit descriptions, review.

Each stage has a prompt bundle (system prompt, user prompt, schema) and a
checker that turns the model object into stored data or raises ValueError with
a message the model can act on. Nothing here touches the database. The model
call itself runs in the web app.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.kc_standards import (
    STANDARDS,
    component_standards,
    coverage_matrix,
    parse_syllabus,
    paste_count,
    standard_brief_lines,
    standard_label,
    statement_lines,
    statements_from_intake,
    syllabus_outcome,
    syllabus_requested,
    syllabus_units,
)

MAX_COMPONENTS = 100
MAX_FOLLOW_UPS = 2
MINUTES_PER_COMPONENT = 12
MAX_OUTCOMES = 8
MAX_PREREQUISITES = 4
PREREQUISITE_CEILING = 12
# One blueprint or review call under this size. A longer matched curriculum is one call per unit.
ONE_CALL_LIMIT = 12

DEPTHS: dict[str, tuple[str, int, int]] = {
    "intro": ("Quick intro", 4, 6),
    "standard": ("Standard", 8, 12),
    "deep": ("Deep dive", 15, 25),
    "curriculum": ("Match curriculum (1 component per topic/statement)", 2, MAX_COMPONENTS),
}
READING_LEVELS: dict[str, str] = {
    "easier": "Easier than the age band. Short sentences and common words.",
    "age": "Matches the age band.",
    "stronger": "A stronger reader than the age band.",
}
USES: dict[str, str] = {
    "": "",
    "enrichment": "Enrichment",
    "school_support": "School support",
    "test_prep": "Test prep",
}

_SHORT = 600
_LONG = 100_000
INTAKE_TEXT_FIELDS: dict[str, int] = {
    "starting_point": _SHORT,
    "must_cover": _SHORT,
    "must_avoid": _SHORT,
    "interests": _SHORT,
    "misconceptions_seen": _SHORT,
    "source_text": _LONG,
    "standard_grade": 80,
    "standard_name": 120,
    "standard_text": _LONG,
    "subject": 160,
}

CHECKS: tuple[str, ...] = ("gaps", "overlap", "jumps", "capstone", "outcomes", "reading_level")

INSTRUCTION_RULES = (
    "Instruction rules for this course:\n"
    "- One teachable idea per component, about 10 to 15 minutes.\n"
    "- Order from concrete to abstract. Teach a vocabulary word before any later component uses it.\n"
    "- Each idea has a route: a worked example, then guided practice, then independent practice. "
    "A component's idea has to be small enough for that route.\n"
    "- Every component builds on named earlier components and leads to later ones, "
    "so the course reads as one story and no step assumes something not yet taught.\n"
    "- Later components revisit earlier ideas. The course ends with a capstone that combines them.\n"
    "- Outcomes use observable verbs, so a check for understanding is possible."
)

BRIEF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "brief": {"type": "string"},
        "questions": {"type": "array", "maxItems": MAX_FOLLOW_UPS, "items": {"type": "string"}},
    },
    "required": ["brief", "questions"],
}

_BLUEPRINT_COMPONENT = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ref": {"type": "string"},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "prerequisites": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["ref", "title", "summary", "prerequisites"],
}

BLUEPRINT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "outcomes": {"type": "array", "items": {"type": "string"}},
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "components": {"type": "array", "items": _BLUEPRINT_COMPONENT},
                },
                "required": ["title", "summary", "components"],
            },
        },
    },
    "required": ["outcomes", "units"],
}


def _nullable(schema: dict) -> dict:
    return {**schema, "type": [schema["type"], "null"]}


_STRING = {"type": "string"}

REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string", "enum": list(CHECKS)},
                    "result": {"type": "string", "enum": ["ok", "fixed", "issue"]},
                    "note": _STRING,
                },
                "required": ["name", "result", "note"],
            },
        },
        "outcomes": _nullable({"type": "array", "items": _STRING}),
        "revisions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "code": _STRING,
                    "title": _nullable(_STRING),
                    "summary": _nullable(_STRING),
                    "description": _nullable(_STRING),
                    "prerequisites": _nullable({"type": "array", "items": _STRING}),
                },
                "required": ["code", "title", "summary", "description", "prerequisites"],
            },
        },
        "additions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "after_code": _STRING,
                    "title": _STRING,
                    "summary": _STRING,
                    "description": _STRING,
                    "prerequisites": {"type": "array", "items": _STRING},
                },
                "required": ["after_code", "title", "summary", "description", "prerequisites"],
            },
        },
    },
    "required": ["checks", "outcomes", "revisions", "additions"],
}


def unit_schema(codes: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "code": {"type": "string", "enum": list(codes)},
                        "description": _STRING,
                    },
                    "required": ["code", "description"],
                },
            }
        },
        "required": ["components"],
    }


BRIEF_RULES = (
    "You write the brief for a children's course from the author's intake. "
    "Write one paragraph of 4 to 7 sentences. "
    "State the topic, who the learner is (age band, reading level, starting point), "
    "what the child can do by the end, how deep the course goes, what must be covered and avoided, "
    "the interests to draw on, and how the course will be used. "
    "Use only what the author gave. Do not invent facts or sources. "
    f"If something important is too vague to plan from, ask at most {MAX_FOLLOW_UPS} short follow-up questions. "
    "When nothing is vague, return no questions."
)

BLUEPRINT_RULES = (
    "You plan the blueprint of a children's course from its brief. "
    "Return the course outcomes, then units, then the ordered components in each unit. "
    "Outcomes are 3 to 6 sentences that each begin with an observable verb. "
    "Group components into units of 3 to 8. "
    "Give each component a ref (c1, c2, c3 in course order), a title, "
    "a one-line summary, and prerequisites that name earlier refs only. "
    "The first component has no prerequisites. "
    "Name titles for the ideas themselves. Do not cut titles out of the author's sentences. "
    "End the last unit with a capstone component that combines earlier ideas. "
    "The capstone is one of the components in the total, not an extra component. "
    "Cover every must-cover item and none of the must-avoid items. "
    "Use the author's source text as the content when it is given."
)

UNIT_RULES = (
    "You write the description of each component in one unit of a children's course. "
    "Each description is plain text of 2 to 6 sentences: what the child will be able to do, "
    "the one core idea, and one common confusion. "
    "When the component has prerequisites, say what it builds on. Say what it leads to where that is natural. "
    "Write for the age band and reading level. "
    "Do not write a block list, an outline, topics, goals, headings, bullets, or line breaks. "
    "Do not repeat another component's description. "
    "Describe only the components listed for this unit, with the codes given."
)

REVIEW_RULES = (
    "You review a drafted children's course against its brief and fix what you find before the author sees it. "
    "Run these checks and return one entry for each, named exactly: "
    "gaps (an outcome or a needed step that no component teaches), "
    "overlap (two components teach the same idea), "
    "jumps (a component assumes something not yet taught or leaps too far from its prerequisites), "
    "capstone (the course ends with a component that combines earlier ideas), "
    "outcomes (each outcome uses an observable verb and can be checked), "
    "reading_level (the wording fits the age band and reading level). "
    "Use result ok when nothing is wrong, fixed when you changed it below, and issue when you could not fix it. "
    "Fix problems with revisions (rewrite a title, summary, description, or prerequisites of an existing component) "
    "and additions (a new component placed after an existing code). "
    "Set a revision field to null when it does not change. "
    "Return an empty revisions list and an empty additions list when nothing needs a fix. "
    "Return outcomes only when you rewrite them, otherwise null. "
    "Prerequisites name codes of components that come earlier in the course. "
    "A description is plain text of 2 to 6 sentences. "
    "Do not write block lists, outlines, topics, headings, bullets, or line breaks."
)


def clean_intake(raw: object) -> dict:
    """Keep the intake keys the form owns, with defaults and caps."""
    data = raw if isinstance(raw, dict) else {}
    reading = str(data.get("reading_level") or "age").strip()
    if reading not in READING_LEVELS:
        raise ValueError("Reading level is easier, age, or stronger.")
    depth = str(data.get("depth") or "standard").strip()
    if depth not in DEPTHS:
        raise ValueError("Depth is intro, standard, deep, or curriculum.")
    align_raw = data.get("align_syllabus")
    if isinstance(align_raw, str):
        align = align_raw.strip().lower() in {"1", "true", "yes", "on"}
    else:
        align = bool(align_raw)
    use = str(data.get("use") or "").strip()
    if use not in USES:
        raise ValueError("Use is enrichment, school_support, test_prep, or blank.")
    count_raw = data.get("component_count")
    count: int | None = None
    if count_raw not in (None, ""):
        try:
            count = int(count_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Component count is a whole number or blank.") from exc
        if count < 2 or count > MAX_COMPONENTS:
            raise ValueError(f"Component count is between 2 and {MAX_COMPONENTS}.")
    standard = str(data.get("standard") or "").strip()
    if standard not in STANDARDS:
        raise ValueError("Standard is none, a listed curriculum, or other.")
    cleaned: dict[str, Any] = {
        "reading_level": reading,
        "depth": depth,
        "component_count": count,
        "use": use,
        "standard": standard,
        "align_syllabus": align,
    }
    for key, cap in INTAKE_TEXT_FIELDS.items():
        raw = str(data.get(key) or "").strip()
        if key in {"source_text", "standard_text"}:
            cleaned[key] = raw[:cap]
            flag = data.get(f"{key}_cut")
            if isinstance(flag, str):
                already_cut = flag.strip().lower() in {"1", "true", "yes", "on"}
            else:
                already_cut = bool(flag)
            if len(raw) > cap:
                cleaned[f"{key}_cut"] = True
            elif len(raw) < cap:
                cleaned[f"{key}_cut"] = False
            else:
                cleaned[f"{key}_cut"] = already_cut
        else:
            cleaned[key] = raw[:cap]
    # A wiped syllabus stays marked so the blueprint does not fall back to a depth band.
    if not cleaned["source_text"] and not cleaned["standard_text"] and data.get("paste_missing"):
        cleaned["paste_missing"] = True
        try:
            cleaned["paste_topics"] = max(0, int(data.get("paste_topics") or 0))
        except (TypeError, ValueError):
            cleaned["paste_topics"] = 0
    return cleaned


def absorb_description_syllabus(description: str, intake: dict) -> tuple[str, dict]:
    """Copy a syllabus pasted into the outcome box into source text.

    A short note already in source text does not block that copy. Source text
    that is itself a longer syllabus stays. A paste of more than one topic
    leaves a short outcome sentence in the description.
    """
    text = str(description or "").strip()
    cleaned = clean_intake(intake)
    count = paste_count(text, syllabus=True)
    if count < 2:
        return text, cleaned
    source = str(cleaned.get("source_text") or "")
    if paste_count(source, syllabus=True) > count:
        return text, cleaned
    stored = clean_intake({**cleaned, "source_text": text})
    return syllabus_outcome(text), stored


def missing_intake(*, title: str, description: str, audience: str, intake: dict) -> list[str]:
    missing: list[str] = []
    if not (title or "").strip():
        missing.append("the topic")
    if not (audience or "").strip():
        missing.append("the age band")
    if not (intake.get("reading_level") or "").strip():
        missing.append("the reading level")
    if not (description or "").strip():
        missing.append('what the child can do by the end ("by the end the child can...")')
    if not (intake.get("depth") or "").strip():
        missing.append("the depth")
    if intake.get("standard"):
        if not (intake.get("standard_grade") or "").strip():
            missing.append("the grade or year")
        if intake.get("standard") == "other" and not (intake.get("standard_name") or "").strip():
            missing.append("the name of the standard")
    return missing


def _pasted_count(intake: dict, statements: list[dict] | None) -> int:
    """The larger of the stored statements and the intake paste.

    An empty stored list counts as nothing only when the intake has no paste.
    standard_text is statements. source_text counts when it is a syllabus.
    """
    stored = len(statements) if statements else 0
    standard = paste_count(str(intake.get("standard_text") or ""))
    source = paste_count(
        str(intake.get("source_text") or ""),
        syllabus=True,
        flat=syllabus_requested(intake),
    )
    return max(stored, standard, source)


def paste_overrides_depth(intake: dict, statements: list[dict] | None = None) -> bool:
    """True when a paste is longer than the depth band and sets the component count."""
    if intake.get("component_count"):
        return False
    _label, _low, high = DEPTHS[intake.get("depth") or "standard"]
    return _pasted_count(intake, statements) > high


def is_matched_curriculum(intake: dict, statements: list[dict] | None = None) -> bool:
    """One component per pasted unit or statement, including a paste that overrides the depth."""
    if intake.get("component_count"):
        return False
    if intake.get("depth") == "curriculum" or intake.get("align_syllabus"):
        return _pasted_count(intake, statements) > 0 or intake.get("depth") == "curriculum"
    return paste_overrides_depth(intake, statements)


def _has_paste_text(intake: dict) -> bool:
    return bool(str(intake.get("source_text") or "").strip() or str(intake.get("standard_text") or "").strip())


def _paste_locks(intake: dict, statements: list[dict] | None = None) -> bool:
    """True when source or standard text on the course is one component per topic."""
    if intake.get("component_count") or not _has_paste_text(intake):
        return False
    if _pasted_count(intake, statements) <= 0:
        return False
    if intake.get("depth") == "curriculum" or intake.get("align_syllabus"):
        return True
    return paste_overrides_depth(intake, statements)


def note_missing_paste(old: dict, new: dict) -> dict:
    """Remember a wiped syllabus so planning does not fall back to a depth band.

    Source text or standard text locks the course to one component per pasted
    topic. When that text is gone, the blueprint says the paste is missing
    instead of planning a Standard course.
    """
    fresh = {key: value for key, value in new.items() if key not in {"paste_missing", "paste_topics"}}
    if _has_paste_text(fresh):
        return fresh
    if new.get("paste_missing"):
        try:
            topics = int(new.get("paste_topics") or old.get("paste_topics") or 0)
        except (TypeError, ValueError):
            topics = 0
        fresh["paste_missing"] = True
        fresh["paste_topics"] = max(0, topics)
        return fresh
    if _paste_locks(old):
        fresh["paste_missing"] = True
        fresh["paste_topics"] = _pasted_count(old, None)
        return fresh
    return fresh


def outcome_limit(*, matched: bool, units: int) -> int:
    """Matched courses may have one outcome per unit. Fewer units keep the usual cap of 8."""
    if not matched:
        return MAX_OUTCOMES
    return max(MAX_OUTCOMES, units)


def prerequisite_limit(*, matched: bool) -> int:
    return PREREQUISITE_CEILING if matched else MAX_PREREQUISITES


def component_range(
    *,
    kind: str,
    minutes: int | None,
    intake: dict,
    statements: list[dict] | None = None,
) -> tuple[int, int]:
    """How many components the blueprint may have.

    An explicit count wins. Source text or standard text on the course stays
    one component per pasted topic. A wiped paste is named instead of planning
    the depth band. A short reply against that exact count is rejected.
    """
    count = intake.get("component_count")
    if count:
        return int(count), int(count)
    if intake.get("paste_missing"):
        raise ValueError("The pasted syllabus is missing from the saved course.")
    pasted = _pasted_count(intake, statements)
    match = intake.get("depth") == "curriculum" or bool(intake.get("align_syllabus"))
    if match and pasted:
        target = min(MAX_COMPONENTS, max(2, pasted))
        return target, target
    if match:
        return 2, MAX_COMPONENTS
    if kind == "time_boxed" and minutes and pasted <= 0:
        target = max(3, round(minutes / MINUTES_PER_COMPONENT))
        return max(2, target - 1), min(MAX_COMPONENTS, target + 1)
    _label, low, high = DEPTHS[intake.get("depth") or "standard"]
    if pasted > high:
        target = min(MAX_COMPONENTS, max(2, pasted))
        return target, target
    if kind == "time_boxed" and minutes:
        target = max(3, round(minutes / MINUTES_PER_COMPONENT))
        return max(2, target - 1), min(MAX_COMPONENTS, target + 1)
    return low, high


def locked_paste_count(
    intake: dict,
    statements: list[dict] | None = None,
    *,
    kind: str = "mastery",
    minutes: int | None = None,
) -> int | None:
    """The exact component count a paste locks, or None when a depth band still applies."""
    if intake.get("component_count") or intake.get("paste_missing"):
        return None
    try:
        low, high = component_range(kind=kind, minutes=minutes, intake=intake, statements=statements)
    except ValueError:
        return None
    if low != high or _pasted_count(intake, statements) <= 0:
        return None
    return low


def _count_text(low: int, high: int) -> str:
    if low == high:
        return (
            f"Return exactly {low} components total across all units "
            "(including the final capstone component)."
        )
    return (
        f"Return between {low} and {high} components total across all units "
        "(including the final capstone component)."
    )


def _soft_ceiling(low: int, high: int, intake: dict | None, statements: list[dict] | None) -> int:
    """How many components a blueprint may have.

    An exact range stays exact. That is an author-typed component count, or a
    paste that locked the course to one component per topic. A soft depth band
    may run a little past its high so a capstone is not rejected. A paste that
    did not lock the range may use the full component ceiling.
    """
    if low == high or intake is None or intake.get("component_count"):
        return high
    depth = str(intake.get("depth") or "standard")
    band = DEPTHS.get(depth)
    if band is None or depth not in {"intro", "standard", "deep"} or (low, high) != (band[1], band[2]):
        return high
    if _pasted_count(intake, statements) > 0:
        return MAX_COMPONENTS
    return min(MAX_COMPONENTS, high + 4)


def _kind_text(kind: str, minutes: int | None) -> str:
    if kind == "time_boxed" and minutes:
        return f"Time boxed, {minutes} minutes. Fit the course to the time."
    if kind == "time_boxed":
        return "Time boxed. Fit the course to the time."
    if kind == "curiosity":
        return "Curiosity. Make a path through the subject."
    return "Mastery. Give the fuller rigorous breakdown."


def _course_lines(course: dict) -> list[str]:
    intake = course["intake"]
    lines = [
        f"Course topic: {course['title']}",
        f"By the end the child can: {course['description'] or 'None given.'}",
        f"Age band: {course['audience']}",
        f"Reading level: {READING_LEVELS[intake['reading_level']]}",
        f"Kind: {_kind_text(course['kind'], course['minutes'])}",
        f"Depth: {DEPTHS[intake['depth']][0]}",
    ]
    for key, label in (
        ("starting_point", "Starting point"),
        ("must_cover", "Must cover"),
        ("must_avoid", "Must avoid"),
        ("interests", "Interests for real-world hooks"),
        ("misconceptions_seen", "Misconceptions the author has seen"),
    ):
        if intake.get(key):
            lines.append(f"{label}: {intake[key]}")
    if intake.get("use"):
        lines.append(f"How it will be used: {USES[intake['use']]}")
    if intake.get("source_text"):
        lines.extend(["Source text from the author:", intake["source_text"]])
    lines.extend(standard_brief_lines(intake, list(course.get("statements") or [])))
    return lines


def brief_schema(*, recall: bool) -> dict:
    if not recall:
        return BRIEF_SCHEMA
    statement = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"code": {"type": "string"}, "text": {"type": "string"}},
        "required": ["code", "text"],
    }
    return {
        **BRIEF_SCHEMA,
        "properties": {**BRIEF_SCHEMA["properties"], "statements": {"type": "array", "items": statement}},
        "required": ["brief", "questions", "statements"],
    }


def brief_bundle(*, course: dict, answers: list[dict], model: str) -> dict:
    lines = [BRIEF_RULES, *_course_lines(course)]
    answered = bool(answers)
    if answered:
        lines.append("Follow-up answers:")
        lines.extend(f"- {item['question']} {item['answer']}" for item in answers)
        lines.append("The follow-ups are answered. Return no questions.")
    locked = locked_paste_count(
        course["intake"],
        list(course.get("statements") or []),
        kind=str(course.get("kind") or "mastery"),
        minutes=course.get("minutes"),
    )
    if locked:
        lines.append(
            f"The pasted syllabus locks this course at exactly {locked} components, one per pasted topic. "
            f"Say that the course has {locked} components. Do not describe the course as 8 to 12 components."
        )
    recall = bool(course["intake"].get("standard")) and not course.get("statements")
    return {
        "model": model,
        "system_prompt": "\n".join(lines),
        "user_prompt": "Write the course brief.",
        "schema": brief_schema(recall=recall),
    }


def clean_brief(result: object, *, answered: bool) -> tuple[str, list[str]]:
    if not isinstance(result, dict):
        raise ValueError("The model reply could not be read.")
    brief = re.sub(r"\s+", " ", str(result.get("brief") or "")).strip()
    if len(brief) < 40:
        raise ValueError("Write the brief as one paragraph of 4 to 7 sentences.")
    questions: list[str] = []
    for item in result.get("questions") or []:
        text = re.sub(r"\s+", " ", str(item or "")).strip()
        if text and text.lower() not in {question.lower() for question in questions}:
            questions.append(text)
    if answered:
        questions = []
    return brief, questions[:MAX_FOLLOW_UPS]


def components_of(blueprint: dict) -> list[dict]:
    """Components in course order, each with its unit index, unit title, and position."""
    rows: list[dict] = []
    for unit_index, unit in enumerate(blueprint.get("units") or []):
        for item in unit.get("components") or []:
            rows.append(
                {
                    **item,
                    "unit_index": unit_index,
                    "unit": unit.get("title") or "",
                    "position": len(rows) + 1,
                }
            )
    return rows


def _blueprint_outline(blueprint: dict) -> str:
    lines: list[str] = []
    total = len(blueprint.get("units") or [])
    for index, unit in enumerate(blueprint.get("units") or [], start=1):
        lines.append(f"Unit {index} of {total}: {unit['title']} - {unit.get('summary') or ''}".rstrip(" -"))
        for item in unit["components"]:
            needs = ", ".join(item.get("prerequisites") or []) or "none"
            line = f"- {item['code']}: {item['title']} (needs: {needs}) - {item.get('summary') or ''}"
            lines.append(line.rstrip(" -") + _standard_mark(item))
    return "\n".join(lines)


def _outcome_lines(blueprint: dict) -> str:
    return "\n".join(f"- {item}" for item in blueprint.get("outcomes") or [])


def _blueprint_schema(statements: list[dict]) -> dict:
    if not statements:
        return BLUEPRINT_SCHEMA
    codes = [item["code"] for item in statements]
    component = {
        **_BLUEPRINT_COMPONENT,
        "properties": {
            **_BLUEPRINT_COMPONENT["properties"],
            "standards": {"type": "array", "items": {"type": "string", "enum": codes}},
        },
        "required": [*_BLUEPRINT_COMPONENT["required"], "standards"],
    }
    unit = BLUEPRINT_SCHEMA["properties"]["units"]["items"]
    return {
        **BLUEPRINT_SCHEMA,
        "properties": {
            **BLUEPRINT_SCHEMA["properties"],
            "units": {**BLUEPRINT_SCHEMA["properties"]["units"], "items": {**unit, "properties": {**unit["properties"], "components": {"type": "array", "items": component}}}},
        },
    }


def _one_to_one(low: int, high: int, statements: list[dict]) -> bool:
    return bool(statements) and low == high and low == min(MAX_COMPONENTS, len(statements))


def blueprint_bundle(*, course: dict, brief: str, model: str) -> dict:
    statements = list(course.get("statements") or [])
    low, high = component_range(
        kind=course["kind"], minutes=course["minutes"], intake=course["intake"], statements=statements
    )
    lines = [
        BLUEPRINT_RULES,
        INSTRUCTION_RULES,
        _count_text(low, high),
        (
            "A longer paste overrides the depth. Plan one component per pasted unit or statement."
            if paste_overrides_depth(course["intake"], statements)
            else ""
        ),
        (
            "A pasted course does not add a capstone beyond the pasted topics."
            if is_matched_curriculum(course["intake"], statements) and low == high
            else ""
        ),
        f"Course topic: {course['title']}",
        f"By the end the child can: {course['description']}",
        f"Age band: {course['audience']}",
        f"Reading level: {READING_LEVELS[course['intake']['reading_level']]}",
        f"Kind: {_kind_text(course['kind'], course['minutes'])}",
        "Course brief:",
        brief,
    ]
    matched = _one_to_one(low, high, statements)
    if matched:
        lines.append(
            "One component per statement, in the same order. "
            "Each component's standards list is exactly that one statement's code. "
            "Do not merge two statements into one component and do not add a component that covers nothing. "
            "Use the curriculum's units when they are listed. A unit may have more or fewer than 3 to 8 components."
        )
        groups = syllabus_units(course["intake"])
        if groups and sum(len(group["statements"]) for group in groups) == len(statements):
            lines.append("Curriculum units:")
            for index, group in enumerate(groups, start=1):
                lines.append(f"Unit {index}: {group['title']}")
                lines.extend(f"- {item['code']}: {item['text']}" for item in group["statements"])
    if statements:
        label = standard_label(course["intake"].get("standard") or "", course["intake"].get("standard_name") or "")
        if matched:
            lines.extend(["Standard statements:", statement_lines(statements)])
        else:
            lines.extend(
                [
                    f"Map every {label} statement onto one or more components. "
                    "Put the statement codes in that component's standards list. "
                    "A component that covers none is an extension, and its standards list is empty. "
                    "Do not invent codes. Do not leave a statement with no component.",
                    "Standard statements:",
                    statement_lines(statements),
                ]
            )
    intake = course["intake"]
    for key, label in (("must_cover", "Must cover"), ("must_avoid", "Must avoid"), ("starting_point", "Starting point")):
        if intake.get(key):
            lines.append(f"{label}: {intake[key]}")
    if intake.get("source_text"):
        lines.extend(["Source text from the author:", intake["source_text"]])
    bundle = {
        "model": model,
        "system_prompt": "\n".join(line for line in lines if line),
        "user_prompt": "Plan the course blueprint.",
        "schema": _blueprint_schema(statements),
    }
    calls = _blueprint_unit_calls(
        course=course, brief=brief, low=low, high=high, statements=statements, model=model
    )
    if len(calls) > 1:
        bundle["calls"] = calls
        bundle["combine"] = "blueprint"
    return bundle


def _safe_syllabus(text: str) -> dict:
    try:
        return parse_syllabus(text)
    except ValueError:
        return {"units": [], "statements": []}


def _curriculum_groups(intake: dict, statements: list[dict]) -> list[dict]:
    """Units to plan. Stored statement codes win when the paste has the same length."""
    source = str(intake.get("source_text") or "")
    standard = str(intake.get("standard_text") or "")
    parsed = {"units": [], "statements": []}
    if paste_count(source, syllabus=True):
        parsed = _safe_syllabus(source)
    if not parsed["units"] and not parsed["statements"] and standard.strip():
        parsed = _safe_syllabus(standard)
    units = list(parsed["units"])
    if units and statements:
        flat = [item for unit in units for item in unit.get("statements") or []]
        if len(flat) == len(statements):
            aligned = []
            index = 0
            for unit in units:
                count = len(unit.get("statements") or [])
                aligned.append({"title": unit["title"], "statements": statements[index : index + count]})
                index += count
            return [group for group in aligned if group["statements"]]
    if units and not statements:
        return [group for group in units if group.get("statements")]
    rows = list(statements) or list(parsed["statements"])
    return [
        {"title": str(item.get("text") or f"Topic {index}")[:80], "statements": [item]}
        for index, item in enumerate(rows, start=1)
    ]


def _unit_plan_schema(topics: list[dict], *, outcomes: bool) -> dict:
    component = {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(_BLUEPRINT_COMPONENT["properties"]),
        "required": list(_BLUEPRINT_COMPONENT["required"]),
    }
    codes = [str(item.get("code") or "") for item in topics if item.get("code")]
    if codes:
        component["properties"] = {
            **component["properties"],
            "standards": {"type": "array", "items": {"type": "string", "enum": codes}},
        }
        component["required"] = [*component["required"], "standards"]
    unit = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "components": {"type": "array", "items": component},
        },
        "required": ["title", "summary", "components"],
    }
    properties: dict[str, Any] = {"unit": unit}
    required = ["unit"]
    if outcomes:
        properties = {"outcomes": {"type": "array", "items": {"type": "string"}}, **properties}
        required = ["outcomes", *required]
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": required}


def _blueprint_unit_calls(
    *,
    course: dict,
    brief: str,
    low: int,
    high: int,
    statements: list[dict],
    model: str,
) -> list[dict]:
    """One model call per unit when a matched curriculum is too large for one blueprint call."""
    del model
    if low != high or high <= ONE_CALL_LIMIT or not is_matched_curriculum(course["intake"], statements):
        return []
    groups = _curriculum_groups(course["intake"], statements)
    planned = sum(len(group["statements"]) or 1 for group in groups)
    if planned != low:
        rows = [item for group in groups for item in group["statements"]]
        while len(rows) < low:
            rows.append({"code": "", "text": f"Topic {len(rows) + 1}"})
        groups = [
            {"title": str(rows[index].get("text") or f"Topic {index + 1}")[:80], "statements": [rows[index]]}
            for index in range(low)
        ]
    if len(groups) <= 1:
        return []
    known = bool(statements)
    calls: list[dict] = []
    ref = 1
    total = len(groups)
    for index, group in enumerate(groups, start=1):
        topics = list(group["statements"])
        count = len(topics) or 1
        refs = [f"c{ref + offset}" for offset in range(count)]
        earlier = [f"c{number}" for number in range(1, ref)]
        ref += count
        lines = [
            "You plan one unit of a children's course. The other units are planned in their own calls.",
            INSTRUCTION_RULES,
            f"Return exactly {count} {'component' if count == 1 else 'components'} in this unit.",
            f"Course topic: {course['title']}",
            f"By the end the child can: {course['description']}",
            f"Age band: {course['audience']}",
            f"Reading level: {READING_LEVELS[course['intake']['reading_level']]}",
            "Course brief:",
            brief,
            f"This is unit {index} of {total}: {group['title']}.",
            "Component refs for this unit, in order: " + ", ".join(refs) + ".",
            (
                "Earlier refs a prerequisite may name: " + ", ".join(earlier) + "."
                if earlier
                else "This is the first unit. Its first component has no prerequisites."
            ),
        ]
        if index == 1:
            lines.append(
                f"Also return the course outcomes: at least two, and at most {max(MAX_OUTCOMES, total)}. "
                "Each outcome begins with an observable verb."
            )
        lines.append("Topics in this unit:")
        for topic, name in zip(topics, refs):
            code = str(topic.get("code") or "")
            text = topic.get("text") or group["title"]
            lines.append(f"- {name} covers {code + ': ' if code and known else ''}{text}")
        if known:
            lines.append(
                "Each component's standards list is the code of the statement it covers. "
                "Do not merge two statements into one component."
            )
        else:
            lines.append("Do not invent curriculum codes.")
        if index == total:
            lines.append(
                "A pasted course does not add a capstone beyond the pasted topics. "
                "Do not add a component beyond the count above."
            )
        calls.append(
            {
                "label": f"Blueprint unit {index} of {total}",
                "system_prompt": "\n".join(lines),
                "user_prompt": f"Plan unit {index} of {total}: {group['title']}.",
                "schema": _unit_plan_schema(topics if known else [], outcomes=index == 1),
            }
        )
    return calls


def _standard_mark(item: dict) -> str:
    if item.get("extension"):
        return " [extension]"
    codes = [str(code) for code in (item.get("standards") or []) if str(code).strip()]
    if codes:
        return " [covers " + ", ".join(codes) + "]"
    return ""


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _prompt_text(value: object) -> str:
    """Chat text with its line breaks. A pasted syllabus stays one topic per line."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in str(value or "").splitlines()]
    return "\n".join(line for line in lines if line)


def _clean_outcomes(value: object, *, limit: int = MAX_OUTCOMES) -> list[str]:
    outcomes = [_clean_text(item) for item in value] if isinstance(value, list) else []
    outcomes = [item for item in outcomes if item]
    if len(outcomes) < 2:
        raise ValueError("Write at least two course outcomes.")
    if len(outcomes) > limit:
        raise ValueError(f"Write at most {limit} course outcomes.")
    return outcomes


_SECTION_PREFIX = re.compile(r"^(?:\d+(?:\.\d+)+|\d+[.)])\s+")


def _slug_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _name_forms(value: str) -> set[str]:
    """Case-insensitive title, the title without a leading section number, and its slug."""
    cleaned = _clean_text(value)
    if not cleaned:
        return set()
    forms = {cleaned.casefold()}
    stripped = _SECTION_PREFIX.sub("", cleaned).strip()
    if stripped and stripped.casefold() != cleaned.casefold():
        forms.add(stripped.casefold())
    for item in (cleaned, stripped):
        slug = _slug_key(item)
        if slug:
            forms.add(slug)
    return forms


def _match_earlier(key: str, earlier: list[dict]) -> str:
    """The code of an earlier component named by ref, code, title, or slug.

    `1.1 Scarcity` and `Scarcity` name the same component. A slug of the title
    matches the stored code or the slug of that title.
    """
    wanted = _name_forms(key)
    if not wanted:
        return ""
    for item in earlier:
        code = _clean_text(item.get("code"))
        if not code:
            continue
        names: set[str] = set()
        for field in ("ref", "code", "title"):
            names |= _name_forms(str(item.get(field) or ""))
        if wanted & names:
            return code
    return ""


def _drop_forward_prerequisites(units: list[dict]) -> None:
    """Keep a prerequisite that names an earlier component, and drop the rest.

    A title or a code resolves to that earlier component. A name that is not
    earlier, including a later capstone, is removed so the review can finish.
    """
    earlier: list[dict] = []
    for unit in units:
        for item in unit.get("components") or []:
            kept: list[str] = []
            for needed in item.get("prerequisites") or []:
                found = _match_earlier(str(needed), earlier)
                if found and found not in kept:
                    kept.append(found)
            item["prerequisites"] = kept
            earlier.append({"ref": "", "code": item.get("code") or "", "title": item.get("title") or ""})


def _check_blueprint(blueprint: dict) -> None:
    """Order, uniqueness, and prerequisite rules. Raises ValueError."""
    rows = components_of(blueprint)
    if len(rows) < 2:
        raise ValueError("Return at least two components.")
    if len(rows) > MAX_COMPONENTS:
        raise ValueError(f"Return at most {MAX_COMPONENTS} components.")
    seen_titles: set[str] = set()
    seen_codes: set[str] = set()
    for row in rows:
        key = row["title"].lower()
        if key in seen_titles:
            raise ValueError(f"Two components are titled {row['title']!r}. Titles are distinct.")
        seen_titles.add(key)
        for prerequisite in row["prerequisites"]:
            if prerequisite == row["code"]:
                raise ValueError(f"{row['title']} cannot be its own prerequisite.")
            if prerequisite not in seen_codes:
                raise ValueError(
                    f"{row['title']} names {prerequisite!r} as a prerequisite. "
                    "A prerequisite is a component that comes earlier in the course."
                )
        seen_codes.add(row["code"])


def assemble_blueprint(
    result: object,
    *,
    bounds: tuple[int, int],
    taken: set[str],
    make_code: Callable[[str, set[str]], str],
    statements: list[dict] | None = None,
    matched: bool = False,
    intake: dict | None = None,
) -> dict:
    """Turn the model blueprint (refs) into the stored blueprint (codes)."""
    if not isinstance(result, dict):
        raise ValueError("The model reply could not be read.")
    raw_units = result.get("units")
    unit_count = len(raw_units) if isinstance(raw_units, list) else 0
    outcomes = _clean_outcomes(result.get("outcomes"), limit=outcome_limit(matched=matched, units=max(unit_count, 1)))
    prereq_cap = prerequisite_limit(matched=matched)
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError("Return at least one unit.")
    codes: dict[str, str] = {}
    taken_now = set(taken)
    units: list[dict] = []
    earlier: list[dict] = []
    for raw_unit in raw_units:
        if not isinstance(raw_unit, dict):
            raise ValueError("Each unit needs a title and components.")
        title = _clean_text(raw_unit.get("title"))
        raw_components = raw_unit.get("components")
        if not title or not isinstance(raw_components, list) or not raw_components:
            raise ValueError("Each unit needs a title and at least one component.")
        components: list[dict] = []
        for raw in raw_components:
            if not isinstance(raw, dict):
                raise ValueError("Each component needs a ref, a title, and a summary.")
            ref = _clean_text(raw.get("ref"))
            name = _clean_text(raw.get("title"))
            summary = _clean_text(raw.get("summary"))
            if not ref or not name or not summary:
                raise ValueError("Each component needs a ref, a title, and a summary.")
            if ref in codes:
                raise ValueError(f"The ref {ref!r} is used twice. Each component has its own ref.")
            prerequisites: list[str] = []
            for needed in raw.get("prerequisites") or []:
                key = _clean_text(needed)
                if not key:
                    continue
                found = _match_earlier(key, earlier)
                if not found:
                    continue
                if found not in prerequisites:
                    prerequisites.append(found)
            if len(prerequisites) > prereq_cap:
                raise ValueError(f"{name} has more than {prereq_cap} prerequisites.")
            code = make_code(name, taken_now)
            taken_now.add(code)
            codes[ref] = code
            earlier.append({"ref": ref, "code": code, "title": name})
            covered, extension = component_standards(raw.get("standards"), statements, name)
            components.append(
                {
                    "code": code,
                    "title": name,
                    "summary": summary,
                    "prerequisites": prerequisites,
                    "standards": covered,
                    "extension": extension,
                }
            )
        units.append({"title": title, "summary": _clean_text(raw_unit.get("summary")), "components": components})
    blueprint = {"outcomes": outcomes, "units": units}
    _check_blueprint(blueprint)
    total = len(components_of(blueprint))
    low, high = bounds
    ceiling = _soft_ceiling(low, high, intake, statements)
    if total < low or total > ceiling:
        raise ValueError(_count_text(low, high).replace("Return", f"You returned {total}. Return"))
    return blueprint


def clean_blueprint_edit(
    raw: object,
    *,
    taken: set[str],
    make_code: Callable[[str, set[str]], str],
    statements: list[dict] | None = None,
    matched: bool = False,
) -> dict:
    """The blueprint as the author edited it. New rows have no code yet."""
    if not isinstance(raw, dict):
        raise ValueError("The blueprint could not be read.")
    raw_units = raw.get("units")
    present = 0
    if isinstance(raw_units, list):
        present = sum(1 for unit in raw_units if isinstance(unit, dict) and unit.get("components"))
    outcomes = _clean_outcomes(raw.get("outcomes"), limit=outcome_limit(matched=matched, units=max(present, 1)))
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError("Add at least one unit.")
    given = {
        _clean_text(item.get("code"))
        for unit in raw_units
        if isinstance(unit, dict)
        for item in (unit.get("components") or [])
        if isinstance(item, dict) and _clean_text(item.get("code"))
    }
    taken_now = set(taken) | given
    used: set[str] = set()
    units: list[dict] = []
    for raw_unit in raw_units:
        if not isinstance(raw_unit, dict):
            raise ValueError("Each unit needs a title and components.")
        title = _clean_text(raw_unit.get("title"))
        raw_components = raw_unit.get("components")
        if not isinstance(raw_components, list):
            raise ValueError("Each unit needs a title and at least one component.")
        if not raw_components:
            continue
        if not title:
            raise ValueError("Each unit needs a title and at least one component.")
        components: list[dict] = []
        for raw_item in raw_components:
            if not isinstance(raw_item, dict):
                raise ValueError("Each component needs a title.")
            name = _clean_text(raw_item.get("title"))
            if not name:
                raise ValueError("Each component needs a title.")
            code = _clean_text(raw_item.get("code"))
            if not code:
                code = make_code(name, taken_now)
                taken_now.add(code)
            if code in used:
                raise ValueError(f"The code {code!r} is used twice.")
            used.add(code)
            prerequisites = raw_item.get("prerequisites")
            if isinstance(prerequisites, str):
                prerequisites = re.split(r"[,\s]+", prerequisites)
            cleaned: list[str] = []
            for needed in prerequisites or []:
                key = _clean_text(needed)
                if key and key not in cleaned:
                    cleaned.append(key)
            covered, extension = component_standards(raw_item.get("standards"), statements, name)
            components.append(
                {
                    "code": code,
                    "title": name,
                    "summary": _clean_text(raw_item.get("summary")),
                    "prerequisites": cleaned,
                    "standards": covered,
                    "extension": extension,
                }
            )
        units.append({"title": title, "summary": _clean_text(raw_unit.get("summary")), "components": components})
    if not units:
        raise ValueError("Add at least one unit.")
    _drop_forward_prerequisites(units)
    blueprint = {"outcomes": outcomes, "units": units}
    _check_blueprint(blueprint)
    return blueprint


def unit_bundle(
    *,
    course: dict,
    brief: str,
    blueprint: dict,
    descriptions: dict[str, str],
    unit_index: int,
    model: str,
) -> dict:
    del descriptions  # Earlier descriptions are not repeated. The prompt carries titles only.
    units = blueprint["units"]
    unit = units[unit_index]
    now = [
        f"- {item['code']}: {item['title']} (needs: {', '.join(item['prerequisites']) or 'none'}) - {item['summary']}"
        + _standard_mark(item)
        for item in unit["components"]
    ]
    titles = "\n".join(f"{index}. {item['title']}" for index, item in enumerate(units, start=1))
    lines = [
        UNIT_RULES,
        INSTRUCTION_RULES,
        f"Course topic: {course['title']}",
        f"Age band: {course['audience']}",
        f"Reading level: {READING_LEVELS[course['intake']['reading_level']]}",
        "Course brief:",
        brief,
        "Course outcomes:",
        _outcome_lines(blueprint),
        "Unit titles:",
        titles,
        f"Write now: unit {unit_index + 1} of {len(units)}, {unit['title']}.",
        "Components to describe:",
        "\n".join(now),
    ]
    return {
        "model": model,
        "system_prompt": "\n".join(lines),
        "user_prompt": f"Write the descriptions for unit {unit_index + 1}: {unit['title']}.",
        "schema": unit_schema([item["code"] for item in unit["components"]]),
    }


_SENTENCE_BREAK = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")
_DECIMAL_GAP = re.compile(r"(?<=\d)\s*\.\s*(?=\d)")
_INITIAL = re.compile(r"\b([A-Z])\.(?=\s+[A-Z])")
_LIST_START = re.compile(r"^\s*(?:[-*•#]|\d+[.)])\s")


def sentence_count(text: str) -> int:
    """Sentences in plain text. A decimal (3.2 percent) or an initial (J. K. Rowling) is not a break."""
    protected = _DECIMAL_GAP.sub(".", text)
    previous = None
    while previous != protected:
        previous = protected
        protected = _INITIAL.sub(r"\1", protected)
    return len([part for part in _SENTENCE_BREAK.split(protected.strip()) if part.strip()])


def clean_description(value: object, label: str = "A description") -> str:
    """Plain text, 2 to 6 sentences, no block line, no list."""
    raw = str(value or "")
    if re.search(r"(?m)^\s*(?:[-*•]|\d+[.)])\s", raw):
        raise ValueError(f"{label} is plain sentences, not a list.")
    text = _clean_text(raw)
    if not text:
        raise ValueError(f"{label} is empty.")
    if re.search(r"recommended blocks?\s*:", text, flags=re.IGNORECASE):
        raise ValueError(f"{label} does not list blocks. Describe the idea in plain sentences.")
    if _LIST_START.match(text):
        raise ValueError(f"{label} is plain sentences, not a list.")
    count = sentence_count(text)
    if count < 2 or count > 6:
        raise ValueError(f"{label} is 2 to 6 sentences. This one has {count}.")
    if len(text) > 1200:
        raise ValueError(f"{label} is too long. Keep it to 2 to 6 sentences.")
    return text


def clean_unit(result: object, codes: list[str]) -> dict[str, str]:
    if not isinstance(result, dict):
        raise ValueError("The model reply could not be read.")
    rows = result.get("components")
    if not isinstance(rows, list):
        raise ValueError("Return the components for this unit.")
    found: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _clean_text(row.get("code"))
        if code not in codes:
            raise ValueError(f"{code!r} is not a component in this unit. Use only {', '.join(codes)}.")
        if code in found:
            raise ValueError(f"{code} appears twice.")
        found[code] = clean_description(row.get("description"), f"The description for {code}")
    missing = [code for code in codes if code not in found]
    if missing:
        raise ValueError(f"Describe every component in this unit. Missing: {', '.join(missing)}.")
    return found


def _review_schema(statements: list[dict]) -> dict:
    if not statements:
        return REVIEW_SCHEMA
    codes = [item["code"] for item in statements]
    standards = {"type": "array", "items": {"type": "string", "enum": codes}}
    revision = REVIEW_SCHEMA["properties"]["revisions"]["items"]
    addition = REVIEW_SCHEMA["properties"]["additions"]["items"]
    return {
        **REVIEW_SCHEMA,
        "properties": {
            **REVIEW_SCHEMA["properties"],
            "revisions": {
                **REVIEW_SCHEMA["properties"]["revisions"],
                "items": {
                    **revision,
                    "properties": {**revision["properties"], "standards": _nullable(standards)},
                    "required": [*revision["required"], "standards"],
                },
            },
            "additions": {
                **REVIEW_SCHEMA["properties"]["additions"],
                "items": {
                    **addition,
                    "properties": {**addition["properties"], "standards": standards},
                    "required": [*addition["required"], "standards"],
                },
            },
        },
    }


def review_bundle(*, course: dict, brief: str, blueprint: dict, descriptions: dict[str, str], model: str) -> dict:
    drafted = [
        f"- {item['code']}: {item['title']} (unit {item['unit_index'] + 1}, needs: "
        f"{', '.join(item['prerequisites']) or 'none'}) - {descriptions.get(item['code'], '')}"
        for item in components_of(blueprint)
    ]
    lines = [
        REVIEW_RULES,
        INSTRUCTION_RULES,
        f"Course topic: {course['title']}",
        f"Age band: {course['audience']}",
        f"Reading level: {READING_LEVELS[course['intake']['reading_level']]}",
        "Course brief:",
        brief,
        "Course outcomes:",
        _outcome_lines(blueprint),
        "Units:",
        "\n".join(f"{index}. {unit['title']}" for index, unit in enumerate(blueprint["units"], start=1)),
        "Drafted components:",
        "\n".join(drafted),
    ]
    statements = list(course.get("statements") or [])
    if statements:
        lines.extend(
            [
                "Coverage of the standard statements:",
                "Every statement is on at least one component. A statement on only one component is touched lightly "
                "and has no later review; add its code to a later component when that component honestly revisits it. "
                "Close a missing statement by adding its code to a component's standards list, or by adding a component. "
                "An empty standards list marks an extension. Do not invent codes. "
                "Set a revision's standards to null when the codes do not change.",
                "Standard statements:",
                statement_lines(statements),
            ]
        )
    bundle = {
        "model": model,
        "system_prompt": "\n".join(lines),
        "user_prompt": "Review the drafted course and fix what you find.",
        "schema": _review_schema(statements),
    }
    calls = _review_unit_calls(
        course=course, brief=brief, blueprint=blueprint, descriptions=descriptions, statements=statements
    )
    if len(calls) > 1:
        bundle["calls"] = calls
        bundle["combine"] = "review"
    return bundle


def _review_unit_calls(
    *,
    course: dict,
    brief: str,
    blueprint: dict,
    descriptions: dict[str, str],
    statements: list[dict],
) -> list[dict]:
    """One review call per unit when the course is too large for one response."""
    rows = components_of(blueprint)
    units = list(blueprint.get("units") or [])
    if len(rows) <= ONE_CALL_LIMIT or len(units) <= 1:
        return []
    titles = "\n".join(f"{index}. {unit['title']}" for index, unit in enumerate(units, start=1))
    calls: list[dict] = []
    total = len(units)
    for index, unit in enumerate(units):
        drafted = [
            f"- {item['code']}: {item['title']} (needs: {', '.join(item.get('prerequisites') or []) or 'none'})"
            f" - {descriptions.get(item['code'], '')}"
            for item in unit.get("components") or []
        ]
        codes = [item["code"] for item in unit.get("components") or []]
        lines = [
            REVIEW_RULES,
            "Review this unit only. The other units are reviewed separately and stored as one combined check.",
            INSTRUCTION_RULES,
            f"Course topic: {course['title']}",
            f"Age band: {course['audience']}",
            f"Reading level: {READING_LEVELS[course['intake']['reading_level']]}",
            "Course brief:",
            brief,
            "Course outcomes:",
            _outcome_lines(blueprint),
            "Unit titles:",
            titles,
            f"Review now: unit {index + 1} of {total}, {unit['title']}.",
            "Components in this unit:",
            "\n".join(drafted),
            "Revise or add components only in this unit. "
            f"Codes in this unit: {', '.join(codes)}.",
        ]
        if statements:
            lines.extend(
                [
                    "Close a missing statement by adding its code to a component in this unit, or by adding a component here. "
                    "Do not invent codes. Set a revision's standards to null when the codes do not change.",
                    "Standard statements:",
                    statement_lines(statements),
                ]
            )
        calls.append(
            {
                "label": f"Review unit {index + 1} of {total}",
                "system_prompt": "\n".join(lines),
                "user_prompt": f"Review unit {index + 1}: {unit['title']}.",
                "schema": _review_schema(statements),
            }
        )
    return calls


def apply_review(
    result: object,
    *,
    blueprint: dict,
    descriptions: dict[str, str],
    taken: set[str],
    make_code: Callable[[str, set[str]], str],
    statements: list[dict] | None = None,
    matched: bool = False,
) -> tuple[dict, dict[str, str], dict]:
    """Apply the review fixes. Returns the new blueprint, descriptions, and the review record."""
    if not isinstance(result, dict):
        raise ValueError("The model reply could not be read.")
    checks: list[dict] = []
    for item in result.get("checks") or []:
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name"))
        outcome = _clean_text(item.get("result"))
        if name not in CHECKS or outcome not in ("ok", "fixed", "issue"):
            raise ValueError(f"A check needs one of these names: {', '.join(CHECKS)}, and a result of ok, fixed, or issue.")
        if any(entry["name"] == name for entry in checks):
            raise ValueError(f"The check {name} appears twice.")
        checks.append({"name": name, "result": outcome, "note": _clean_text(item.get("note"))})
    absent = [name for name in CHECKS if not any(entry["name"] == name for entry in checks)]
    if absent:
        raise ValueError(f"Return every check. Missing: {', '.join(absent)}.")
    checks.sort(key=lambda entry: CHECKS.index(entry["name"]))

    units = [
        {**unit, "components": [dict(item) for item in unit["components"]]} for unit in blueprint["units"]
    ]
    by_code = {item["code"]: item for unit in units for item in unit["components"]}
    notes = dict(descriptions)
    outcomes = list(blueprint["outcomes"])
    outcomes_changed = False
    if result.get("outcomes") is not None:
        limit = outcome_limit(matched=matched, units=max(len(blueprint.get("units") or []), 1))
        outcomes = _clean_outcomes(result.get("outcomes"), limit=limit)
        outcomes_changed = outcomes != list(blueprint["outcomes"])

    revised: list[str] = []
    for item in result.get("revisions") or []:
        if not isinstance(item, dict):
            continue
        code = _clean_text(item.get("code"))
        target = by_code.get(code)
        if target is None:
            raise ValueError(f"A revision names {code!r}, which is not a component. Use a code from the list.")
        changed = False
        title = _clean_text(item.get("title"))
        if title and title != target["title"]:
            target["title"] = title
            changed = True
        summary = _clean_text(item.get("summary"))
        if summary and summary != target["summary"]:
            target["summary"] = summary
            changed = True
        if item.get("description") is not None and _clean_text(item.get("description")):
            text = clean_description(item.get("description"), f"The revised description for {code}")
            if text != notes.get(code):
                notes[code] = text
                changed = True
        if item.get("prerequisites") is not None:
            needed: list[str] = []
            for entry in item["prerequisites"]:
                key = _clean_text(entry)
                if key and key not in needed:
                    needed.append(key)
            if needed != target["prerequisites"]:
                target["prerequisites"] = needed
                changed = True
        if item.get("standards") is not None:
            covered, extension = component_standards(item.get("standards"), statements, target["title"])
            if covered != list(target.get("standards") or []):
                target["standards"] = covered
                target["extension"] = extension
                changed = True
        if changed and code not in revised:
            revised.append(code)

    added: list[str] = []
    taken_now = set(taken) | set(by_code)
    for item in result.get("additions") or []:
        if not isinstance(item, dict):
            continue
        after = _clean_text(item.get("after_code"))
        title = _clean_text(item.get("title"))
        summary = _clean_text(item.get("summary"))
        if after not in by_code:
            raise ValueError(f"An addition goes after {after!r}, which is not a component. Use a code from the list.")
        if not title or not summary:
            raise ValueError("Each addition needs a title and a summary.")
        code = make_code(title, taken_now)
        taken_now.add(code)
        notes[code] = clean_description(item.get("description"), f"The description for the new component {title}")
        covered, extension = component_standards(item.get("standards"), statements, title)
        entry = {
            "code": code,
            "title": title,
            "summary": summary,
            "prerequisites": [_clean_text(needed) for needed in item.get("prerequisites") or [] if _clean_text(needed)],
            "standards": covered,
            "extension": extension,
        }
        for unit in units:
            codes = [row["code"] for row in unit["components"]]
            if after in codes:
                unit["components"].insert(codes.index(after) + 1, entry)
                break
        by_code[code] = entry
        added.append(code)

    fixed = {"outcomes": outcomes, "units": units}
    _drop_forward_prerequisites(units)
    _check_blueprint(fixed)
    missing = [row["code"] for row in components_of(fixed) if row["code"] not in notes]
    if missing:
        raise ValueError(f"Every component keeps a description. Missing: {', '.join(missing)}.")
    review = {
        "checks": checks,
        "revised": revised,
        "added": added,
        "outcomes_changed": outcomes_changed,
        "coverage": coverage_matrix(statements or [], fixed),
    }
    return fixed, notes, review


def final_components(blueprint: dict, descriptions: dict[str, str]) -> list[dict]:
    return [
        {
            "code": row["code"],
            "title": row["title"],
            "description": descriptions.get(row["code"], ""),
            "prerequisite_codes": list(row["prerequisites"]),
            "standards": list(row.get("standards") or []),
            "extension": bool(row.get("extension")),
            "unit": row["unit"],
            "position": row["position"],
        }
        for row in components_of(blueprint)
    ]


def _chat_schema(statements: list[dict]) -> dict:
    standards: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
    if statements:
        standards = {"type": "array", "items": {"type": "string", "enum": [item["code"] for item in statements]}}
    component = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "code": {"type": "string"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "prerequisites": {"type": "array", "items": {"type": "string"}},
            "standards": standards,
            "description": _nullable(_STRING),
        },
        "required": ["code", "title", "summary", "prerequisites", "standards", "description"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reply": {"type": "string"},
            "changed_codes": {"type": "array", "items": {"type": "string"}},
            "outcomes": {"type": "array", "items": {"type": "string"}},
            "units": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "components": {"type": "array", "items": component},
                    },
                    "required": ["title", "summary", "components"],
                },
            },
        },
        "required": ["reply", "changed_codes", "outcomes", "units"],
    }


CHAT_RULES = (
    "You edit the course the author already has. "
    "The reply is one or two plain sentences that say what changed. "
    "Return only the units you changed. Do not return the whole blueprint. "
    "Include every component of a unit you change. Leave out units you did not change. "
    "To remove a unit, return that unit with an empty components list. "
    "Keep the code of every component you keep. An added component has an empty code. "
    "Set description to null on every component you did not change. "
    "Write a new description, 2 to 6 plain sentences, only for a component you add or change. "
    "Put the code of each changed component in changed_codes. Leave a new component out of that list. "
    "Do not rewrite, reorder, or drop anything the author did not ask about. "
    "Prerequisites name codes of components that come earlier. "
    "Do not invent curriculum statements."
)


def _blueprint_summary(blueprint: dict, descriptions: dict[str, str]) -> str:
    units = (blueprint or {}).get("units") or []
    if not units:
        return "No blueprint yet."
    lines = ["Outcomes:", _outcome_lines(blueprint), _blueprint_outline(blueprint)]
    written = [f"- {row['code']}: {descriptions[row['code']]}" for row in components_of(blueprint) if descriptions.get(row["code"])]
    if written:
        lines.extend(["Descriptions:", *written])
    return "\n".join(lines)


def syllabus_prompt_line(intake: dict | None) -> str:
    """Tell the chat to make one component per pasted topic."""
    source = str((intake or {}).get("source_text") or "")
    count = paste_count(source, syllabus=True)
    if count < 2:
        return ""
    units = len(_safe_syllabus(source).get("units") or [])
    if units:
        return (
            f"The author pasted a syllabus with {units} units and {count} topics. "
            f"Make one component per pasted topic: {count} components across the {units} units. "
            "Do not plan a shorter course."
        )
    return (
        f"The author pasted a syllabus with {count} topics. "
        "Make one component per pasted topic. Do not plan a shorter course."
    )


def chat_bundle(
    *,
    course: dict,
    brief: str,
    blueprint: dict,
    descriptions: dict[str, str],
    statements: list[dict],
    components: list[dict],
    messages: list[dict],
    model: str,
) -> dict:
    """Prompt for one chat turn. It proposes a change and does not write the course."""
    lines = [
        CHAT_RULES,
        "Course schema:",
        "outcomes: sentences.",
        "units: title, summary, components.",
        "component: code, title, summary, prerequisites, standards, description.",
        f"Course topic: {course['title']}",
        f"Age band: {course['audience']}",
        f"By the end the child can: {course['description'] or 'None given.'}",
        "Brief:",
        brief or "None yet.",
        "Blueprint:",
        _blueprint_summary(blueprint, descriptions),
    ]
    note = syllabus_prompt_line(course.get("intake"))
    if note:
        lines.append(note)
    source = str((course.get("intake") or {}).get("source_text") or "")
    if paste_count(source, syllabus=True) >= 2:
        lines.extend(["Pasted syllabus:", _prompt_text(source)])
    intake = course.get("intake") or {}
    locked = locked_paste_count(
        intake,
        statements,
        kind=str(course.get("kind") or "mastery"),
        minutes=course.get("minutes"),
    )
    stored = len(components_of(blueprint or {}))
    if locked and locked > 12 and stored != locked:
        lines.append(
            f"The stored blueprint has {stored} components. Replace it with the full course. "
            f"Return every unit and all {locked} components. Do not keep the shorter blueprint."
        )
    if statements:
        lines.extend(["Curriculum statements:", statement_lines(statements)])
    if components:
        lines.append("Pushed components:")
        lines.extend(f"- {item.get('code')}: {item.get('title')}" for item in components)
    if messages:
        lines.append("Chat:")
        for item in messages:
            who = "Author" if item.get("role") == "user" else "Editor"
            text = _prompt_text(item.get("content"))
            if text:
                lines.append(f"{who}: {text}")
    latest = ""
    for item in reversed(messages):
        if item.get("role") == "user":
            latest = _prompt_text(item.get("content"))
            if latest:
                break
    return {
        "model": model,
        "system_prompt": "\n".join(lines),
        "user_prompt": latest or "Say what you want to change.",
        "schema": _chat_schema(statements),
    }


def _raw_components(result: dict) -> list[dict]:
    rows: list[dict] = []
    for unit in result.get("units") or []:
        if not isinstance(unit, dict):
            continue
        components = unit.get("components")
        if isinstance(components, list) and components:
            rows.extend(item for item in components if isinstance(item, dict))
    return rows


def merge_chat_patch(blueprint: dict, result: dict, *, locked_count: int | None = None) -> dict:
    """Fold a chat patch onto the stored blueprint.

    Units the reply leaves out stay as they are. A returned unit replaces the
    stored unit that shares a component code or the same title. An empty
    components list removes that unit. A paste locked above 12 replaces a
    shorter stored blueprint, so those old units are not kept.
    """
    stored_units = [
        {**unit, "components": [dict(item) for item in (unit.get("components") or []) if isinstance(item, dict)]}
        for unit in (blueprint.get("units") or [])
        if isinstance(unit, dict)
    ]
    patch_units = result.get("units") if isinstance(result.get("units"), list) else []
    stored_count = sum(len(unit["components"]) for unit in stored_units)
    if locked_count is not None and locked_count > 12 and stored_count != locked_count and patch_units:
        outcomes = result.get("outcomes") if isinstance(result.get("outcomes"), list) and result.get("outcomes") else blueprint.get("outcomes")
        return {"outcomes": list(outcomes or []), "units": [unit for unit in patch_units if isinstance(unit, dict)]}
    if not patch_units:
        outcomes = result.get("outcomes") if isinstance(result.get("outcomes"), list) and result.get("outcomes") else blueprint.get("outcomes")
        return {"outcomes": list(outcomes or []), "units": stored_units}
    index_by_code: dict[str, int] = {}
    for index, unit in enumerate(stored_units):
        for item in unit["components"]:
            code = _clean_text(item.get("code"))
            if code:
                index_by_code[code] = index
    replaced: dict[int, dict] = {}
    removed: set[int] = set()
    appended: list[dict] = []
    for raw in patch_units:
        if not isinstance(raw, dict):
            continue
        components = raw.get("components")
        title = _clean_text(raw.get("title"))
        if isinstance(components, list) and not components:
            for index, unit in enumerate(stored_units):
                if title and _clean_text(unit.get("title")) == title:
                    removed.add(index)
            continue
        found: int | None = None
        if isinstance(components, list):
            for item in components:
                if not isinstance(item, dict):
                    continue
                code = _clean_text(item.get("code"))
                if code and code in index_by_code:
                    found = index_by_code[code]
                    break
        if found is None and title:
            for index, unit in enumerate(stored_units):
                if index not in replaced and _clean_text(unit.get("title")) == title:
                    found = index
                    break
        if found is None:
            appended.append(raw)
        else:
            replaced[found] = raw
    units: list[dict] = []
    for index, unit in enumerate(stored_units):
        if index in removed:
            continue
        units.append(replaced.get(index, unit))
    units.extend(appended)
    outcomes = result.get("outcomes") if isinstance(result.get("outcomes"), list) and result.get("outcomes") else blueprint.get("outcomes")
    return {"outcomes": list(outcomes or []), "units": units}


def interpret_chat(
    result: object,
    *,
    blueprint: dict,
    descriptions: dict[str, str],
    statements: list[dict] | None,
    taken: set[str],
    make_code: Callable[[str, set[str]], str],
    matched: bool = False,
    locked_count: int | None = None,
) -> dict:
    """The proposed course. A partial reply is merged. Unchanged descriptions stay.

    A locked paste rejects a proposal whose component count is not that count.
    """
    if not isinstance(result, dict):
        raise ValueError("The model reply could not be read.")
    reply = _clean_text(result.get("reply"))
    if len(reply) < 2:
        raise ValueError("Say what changed, in plain language.")
    listed: list[str] = []
    for code in result.get("changed_codes") or []:
        key = _clean_text(code)
        if key and key not in listed:
            listed.append(key)
    merged = merge_chat_patch(blueprint or {}, result, locked_count=locked_count)
    raw_rows = _raw_components(merged)
    proposed = clean_blueprint_edit(merged, taken=taken, make_code=make_code, statements=statements, matched=matched)
    cleaned_rows = components_of(proposed)
    if len(raw_rows) != len(cleaned_rows):
        raise ValueError("Each component needs a title.")
    if locked_count is not None and len(cleaned_rows) != locked_count:
        total = len(cleaned_rows)
        raise ValueError(_count_text(locked_count, locked_count).replace("Return", f"You returned {total}. Return"))
    old_rows = {row["code"]: row for row in components_of(blueprint or {})}
    old_notes = dict(descriptions or {})
    had_notes = any(str(text or "").strip() for text in old_notes.values())
    notes: dict[str, str] = {}
    rewritten: list[str] = []
    structural_codes: list[str] = []
    for raw, row in zip(raw_rows, cleaned_rows, strict=True):
        code = row["code"]
        previous = old_rows.get(code)
        structural = previous is None or any(previous.get(key) != row.get(key) for key in ("title", "summary", "prerequisites", "standards"))
        if structural:
            structural_codes.append(code)
        untouched = previous is not None and not structural and code not in listed
        model_text = raw.get("description")
        if untouched:
            if code in old_notes:
                notes[code] = old_notes[code]
            continue
        if model_text not in (None, ""):
            notes[code] = clean_description(model_text, f"The description for {row['title']}")
            if notes[code] != old_notes.get(code):
                rewritten.append(code)
        elif code in old_notes and not structural:
            notes[code] = old_notes[code]
        elif had_notes:
            raise ValueError(f"Write the description for {row['title']}. Leave every unchanged description null.")
    changes = _chat_changes(blueprint or {}, proposed, old_rows, structural_codes, rewritten)
    return {
        "reply": reply,
        "blueprint": proposed,
        "descriptions": notes,
        "changed_codes": structural_codes + [code for code in rewritten if code not in structural_codes],
        "changes": changes,
    }


def _chat_changes(
    before: dict,
    after: dict,
    old_rows: dict[str, dict],
    structural_codes: list[str],
    rewritten: list[str],
) -> list[str]:
    old_titles = [str(unit.get("title") or "") for unit in before.get("units") or []]
    new_titles = [str(unit.get("title") or "") for unit in after.get("units") or []]
    new_rows = {row["code"]: row for row in components_of(after)}
    lines: list[str] = []
    for title in old_titles:
        if title and title not in new_titles:
            lines.append(f"Removed unit {title}.")
    for title in new_titles:
        if title and title not in old_titles:
            lines.append(f"Added unit {title}.")
    for code, row in old_rows.items():
        if code not in new_rows:
            lines.append(f"Removed {row['title']}.")
    for code in structural_codes:
        row = new_rows.get(code)
        if row is None:
            continue
        if code not in old_rows:
            lines.append(f"Added {row['title']}.")
        else:
            lines.append(f"Updated {row['title']}.")
    for code in rewritten:
        if code in structural_codes or code not in old_rows:
            continue
        lines.append(f"Rewrote the description of {old_rows[code]['title']}.")
    return lines


def position_text(blueprint: dict, code: str) -> str:
    rows = components_of(blueprint)
    for row in rows:
        if row["code"] == code:
            units = len(blueprint["units"])
            return (
                f"component {row['position']} of {len(rows)}, "
                f"unit {row['unit_index'] + 1} of {units} ({row['unit']})"
            )
    return ""


def pipeline_state(
    *,
    brief: str,
    blueprint: dict,
    drafting: dict,
    standards: list[dict] | None = None,
    standard_chosen: bool = False,
) -> dict:
    """Where the course draft stands and which stage runs next. The stored data decides."""
    units = (blueprint or {}).get("units") or []
    descriptions = dict(drafting.get("units") or {})
    done = int(drafting.get("units_done") or 0)
    questions = list(drafting.get("questions") or [])
    answers = list(drafting.get("answers") or [])
    approved = bool(drafting.get("approved"))
    review = drafting.get("review")
    statements = list(standards or [])
    confirmed = bool(drafting.get("standards_confirmed")) or not standard_chosen
    if not brief:
        stage, nxt = "brief", {"stage": "brief", "unit": None}
    elif questions and not answers:
        stage, nxt = "questions", None
    elif questions:
        stage, nxt = "questions", {"stage": "brief", "unit": None}
    elif not confirmed:
        stage, nxt = "standards", None
    elif not units:
        stage, nxt = "blueprint", {"stage": "blueprint", "unit": None}
    elif not approved:
        stage, nxt = "edit_blueprint", None
    elif done < len(units):
        stage, nxt = "units", {"stage": "unit", "unit": done}
    elif not review:
        stage, nxt = "review", {"stage": "review", "unit": None}
    else:
        stage, nxt = "draft", None
    return {
        "stage": stage,
        "next": nxt,
        "brief": brief or "",
        "questions": questions,
        "answers": list(drafting.get("answers") or []),
        "blueprint": blueprint if units else None,
        "approved": approved,
        "units_total": len(units),
        "units_done": done,
        "descriptions": descriptions,
        "review": review,
        "standards": statements,
        "standards_source": str(drafting.get("standards_source") or ""),
        "coverage": coverage_matrix(statements, blueprint) if statements and units else None,
        "pushed": bool(drafting.get("pushed")),
        "draft": (
            {"kind": "course", "components": final_components(blueprint, descriptions)}
            if stage == "draft"
            else None
        ),
    }
