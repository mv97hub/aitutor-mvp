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

MAX_COMPONENTS = 250
MAX_FOLLOW_UPS = 2
MINUTES_PER_COMPONENT = 12
MAX_OUTCOMES = 8
MAX_PREREQUISITES = 4

DEPTHS: dict[str, tuple[str, int, int]] = {
    "intro": ("Quick intro", 4, 6),
    "standard": ("Standard", 8, 12),
    "deep": ("Deep dive", 15, 25),
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
_LONG = 20000
INTAKE_TEXT_FIELDS: dict[str, int] = {
    "starting_point": _SHORT,
    "must_cover": _SHORT,
    "must_avoid": _SHORT,
    "interests": _SHORT,
    "misconceptions_seen": _SHORT,
    "source_text": _LONG,
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
    "Use only what the author gave. Do not invent facts, sources, or standards. "
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
    "Cover every must-cover item and none of the must-avoid items. "
    "Use the author's source text as the content when it is given."
)

UNIT_RULES = (
    "You write the description of each component in one unit of a children's course. "
    "Each description is plain text of 3 to 4 sentences: what the child will be able to do, "
    "the one core idea, and one common confusion. "
    "When the component has prerequisites, say what it builds on. Say what it leads to where that is natural. "
    "Write for the age band and reading level. "
    "Do not write a block list, an outline, topics, goals, headings, bullets, or line breaks. "
    "Do not repeat or contradict the descriptions already written. "
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
    "A description is plain text of 3 to 4 sentences. "
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
        raise ValueError("Depth is intro, standard, or deep.")
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
    cleaned: dict[str, Any] = {
        "reading_level": reading,
        "depth": depth,
        "component_count": count,
        "use": use,
    }
    for key, cap in INTAKE_TEXT_FIELDS.items():
        cleaned[key] = str(data.get(key) or "").strip()[:cap]
    return cleaned


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
    return missing


def component_range(*, kind: str, minutes: int | None, intake: dict) -> tuple[int, int]:
    count = intake.get("component_count")
    if count:
        return int(count), int(count)
    if kind == "time_boxed" and minutes:
        target = max(3, round(minutes / MINUTES_PER_COMPONENT))
        return max(2, target - 1), min(MAX_COMPONENTS, target + 1)
    _label, low, high = DEPTHS[intake.get("depth") or "standard"]
    return low, high


def _count_text(low: int, high: int) -> str:
    if low == high:
        return f"Return exactly {low} components."
    return f"Return between {low} and {high} components."


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
    return lines


def brief_bundle(*, course: dict, answers: list[dict], model: str) -> dict:
    lines = [BRIEF_RULES, *_course_lines(course)]
    answered = bool(answers)
    if answered:
        lines.append("Follow-up answers:")
        lines.extend(f"- {item['question']} {item['answer']}" for item in answers)
        lines.append("The follow-ups are answered. Return no questions.")
    return {
        "model": model,
        "system_prompt": "\n".join(lines),
        "user_prompt": "Write the course brief.",
        "schema": BRIEF_SCHEMA,
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
            lines.append(line.rstrip(" -"))
    return "\n".join(lines)


def _outcome_lines(blueprint: dict) -> str:
    return "\n".join(f"- {item}" for item in blueprint.get("outcomes") or [])


def blueprint_bundle(*, course: dict, brief: str, model: str) -> dict:
    low, high = component_range(kind=course["kind"], minutes=course["minutes"], intake=course["intake"])
    lines = [
        BLUEPRINT_RULES,
        INSTRUCTION_RULES,
        _count_text(low, high),
        f"Course topic: {course['title']}",
        f"By the end the child can: {course['description']}",
        f"Age band: {course['audience']}",
        f"Reading level: {READING_LEVELS[course['intake']['reading_level']]}",
        f"Kind: {_kind_text(course['kind'], course['minutes'])}",
        "Course brief:",
        brief,
    ]
    intake = course["intake"]
    for key, label in (("must_cover", "Must cover"), ("must_avoid", "Must avoid"), ("starting_point", "Starting point")):
        if intake.get(key):
            lines.append(f"{label}: {intake[key]}")
    if intake.get("source_text"):
        lines.extend(["Source text from the author:", intake["source_text"]])
    return {
        "model": model,
        "system_prompt": "\n".join(lines),
        "user_prompt": "Plan the course blueprint.",
        "schema": BLUEPRINT_SCHEMA,
    }


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_outcomes(value: object) -> list[str]:
    outcomes = [_clean_text(item) for item in value] if isinstance(value, list) else []
    outcomes = [item for item in outcomes if item]
    if len(outcomes) < 2:
        raise ValueError("Write at least two course outcomes.")
    if len(outcomes) > MAX_OUTCOMES:
        raise ValueError(f"Write at most {MAX_OUTCOMES} course outcomes.")
    return outcomes


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
) -> dict:
    """Turn the model blueprint (refs) into the stored blueprint (codes)."""
    if not isinstance(result, dict):
        raise ValueError("The model reply could not be read.")
    outcomes = _clean_outcomes(result.get("outcomes"))
    raw_units = result.get("units")
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError("Return at least one unit.")
    codes: dict[str, str] = {}
    taken_now = set(taken)
    units: list[dict] = []
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
                if key not in codes:
                    raise ValueError(
                        f"{name} names {key!r} as a prerequisite. "
                        "A prerequisite is the ref of a component that comes earlier."
                    )
                if codes[key] not in prerequisites:
                    prerequisites.append(codes[key])
            if len(prerequisites) > MAX_PREREQUISITES:
                raise ValueError(f"{name} has more than {MAX_PREREQUISITES} prerequisites.")
            code = make_code(name, taken_now)
            taken_now.add(code)
            codes[ref] = code
            components.append(
                {"code": code, "title": name, "summary": summary, "prerequisites": prerequisites}
            )
        units.append({"title": title, "summary": _clean_text(raw_unit.get("summary")), "components": components})
    blueprint = {"outcomes": outcomes, "units": units}
    _check_blueprint(blueprint)
    total = len(components_of(blueprint))
    low, high = bounds
    if total < low or total > high:
        raise ValueError(_count_text(low, high).replace("Return", f"You returned {total}. Return"))
    return blueprint


def clean_blueprint_edit(
    raw: object,
    *,
    taken: set[str],
    make_code: Callable[[str, set[str]], str],
) -> dict:
    """The blueprint as the author edited it. New rows have no code yet."""
    if not isinstance(raw, dict):
        raise ValueError("The blueprint could not be read.")
    outcomes = _clean_outcomes(raw.get("outcomes"))
    raw_units = raw.get("units")
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
        if not title or not isinstance(raw_components, list) or not raw_components:
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
            components.append(
                {
                    "code": code,
                    "title": name,
                    "summary": _clean_text(raw_item.get("summary")),
                    "prerequisites": cleaned,
                }
            )
        units.append({"title": title, "summary": _clean_text(raw_unit.get("summary")), "components": components})
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
    units = blueprint["units"]
    unit = units[unit_index]
    written = [
        f"- {item['code']}: {descriptions[item['code']]}"
        for item in components_of(blueprint)
        if item["code"] in descriptions
    ]
    now = [
        f"- {item['code']}: {item['title']} (needs: {', '.join(item['prerequisites']) or 'none'}) - {item['summary']}"
        for item in unit["components"]
    ]
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
        "Blueprint:",
        _blueprint_outline(blueprint),
        "Descriptions already written:",
        "\n".join(written) if written else "- None yet.",
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
_LIST_START = re.compile(r"^\s*(?:[-*•#]|\d+[.)])\s")


def sentence_count(text: str) -> int:
    return len([part for part in _SENTENCE_BREAK.split(text.strip()) if part.strip()])


def clean_description(value: object, label: str = "A description") -> str:
    """Plain text, 3 to 4 sentences (5 is tolerated), no block line, no list."""
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
    if count < 3 or count > 5:
        raise ValueError(f"{label} is 3 to 4 sentences. This one has {count}.")
    if len(text) > 1200:
        raise ValueError(f"{label} is too long. Keep it to 3 to 4 sentences.")
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
    return {
        "model": model,
        "system_prompt": "\n".join(lines),
        "user_prompt": "Review the drafted course and fix what you find.",
        "schema": REVIEW_SCHEMA,
    }


def apply_review(
    result: object,
    *,
    blueprint: dict,
    descriptions: dict[str, str],
    taken: set[str],
    make_code: Callable[[str, set[str]], str],
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
        outcomes = _clean_outcomes(result.get("outcomes"))
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
        entry = {
            "code": code,
            "title": title,
            "summary": summary,
            "prerequisites": [_clean_text(needed) for needed in item.get("prerequisites") or [] if _clean_text(needed)],
        }
        for unit in units:
            codes = [row["code"] for row in unit["components"]]
            if after in codes:
                unit["components"].insert(codes.index(after) + 1, entry)
                break
        by_code[code] = entry
        added.append(code)

    fixed = {"outcomes": outcomes, "units": units}
    _check_blueprint(fixed)
    missing = [row["code"] for row in components_of(fixed) if row["code"] not in notes]
    if missing:
        raise ValueError(f"Every component keeps a description. Missing: {', '.join(missing)}.")
    review = {
        "checks": checks,
        "revised": revised,
        "added": added,
        "outcomes_changed": outcomes_changed,
    }
    return fixed, notes, review


def final_components(blueprint: dict, descriptions: dict[str, str]) -> list[dict]:
    return [
        {
            "code": row["code"],
            "title": row["title"],
            "description": descriptions.get(row["code"], ""),
            "prerequisite_codes": list(row["prerequisites"]),
            "unit": row["unit"],
            "position": row["position"],
        }
        for row in components_of(blueprint)
    ]


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


def pipeline_state(*, brief: str, blueprint: dict, drafting: dict) -> dict:
    """Where the course draft stands and which stage runs next. The stored data decides."""
    units = (blueprint or {}).get("units") or []
    descriptions = dict(drafting.get("units") or {})
    done = int(drafting.get("units_done") or 0)
    questions = list(drafting.get("questions") or [])
    approved = bool(drafting.get("approved"))
    review = drafting.get("review")
    if not brief:
        stage, nxt = "brief", {"stage": "brief", "unit": None}
    elif questions:
        stage, nxt = "questions", None
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
        "pushed": bool(drafting.get("pushed")),
        "draft": (
            {"kind": "course", "components": final_components(blueprint, descriptions)}
            if stage == "draft"
            else None
        ),
    }
