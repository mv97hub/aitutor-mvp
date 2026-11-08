"""Prompts for the KC Course Creator and KC Creator model calls.

The syllabus still chooses a careful title list. The model names the subject
and the major ideas, then writes each component's outline, topics, and goals.
A long list is titles first, then descriptions in slices. A pasted title list
stays as written. Scoring is not part of this module.
"""

from __future__ import annotations

import copy
import re

from app.kc_syllabus import MAX_COMPONENTS, planned_reply, planning_context

# The original CreateCourse menu, then a capable default, then the strongest
# chat model id the app's OpenAI client accepts (openai(), @ai-sdk/openai 4.0.106).
# DeepSeek Flash is last. OpenRouter's alias has a leading tilde. The web app
# calls that alias. A saved deepseek/deepseek-flash-latest id is sent as it.
DEEPSEEK_FLASH_MODEL = "~deepseek/deepseek-flash-latest"
LEGACY_DEEPSEEK_FLASH_MODEL = "deepseek/deepseek-flash-latest"
KC_CHAT_MODELS = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-6.1-sol",
    DEEPSEEK_FLASH_MODEL,
)
DEFAULT_KC_CHAT_MODEL = "gpt-4.1"
DESCRIPTION_SLICE = 25

COURSE_RULES = (
    "You are an expert curriculum maker. "
    "Name the subject from the course name and the course description. "
    "Then name the major ideas a strong course on that subject has to cover. "
    "Do not slice the description sentence into titles. "
    "Do not turn clauses of the description into component titles. "
    "Mastery is the fuller rigorous breakdown. "
    "Time boxed fits the minutes. "
    "Curiosity is a path through the subject. "
    'Honor a requested count. "minimum of 10" means at least 10 distinct components. '
    '"10 components" means 10 distinct components. '
    "A pasted title list is used as written. "
    "Only after the subject and the major ideas, return the component list. "
    "Each component description has a short outline, the key topics, and the key goals."
)

CREATOR_RULES = (
    "You are an expert curriculum maker for this knowledge component and the course kind. "
    "The description is the brief: the outline, the key topics, and the key goals. "
    "Use that brief. Recommend every field that can be entered: "
    "description, title, type, the fields for that type, core truth, rubric checks, "
    "misconceptions, prerequisites, and encompasses. "
    "Use the course kind. Mastery is the fuller rigorous breakdown. "
    "Time boxed fits the minutes. Curiosity is a path through the subject. "
    "Go into the topic before you fill the type, the core truth, the rubric, and the checks. "
    "Do not change how an answer is scored. "
    "Other components stay as they are."
)

_COMPONENT_FIELDS = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "outline": {"type": "string"},
        "topics": {"type": "array", "items": {"type": "string"}},
        "goals": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "outline", "topics", "goals"],
}

COURSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "subject": {"type": "string"},
        "major_ideas": {"type": "array", "items": {"type": "string"}},
        "components": {"type": "array", "items": _COMPONENT_FIELDS},
    },
    "required": ["subject", "major_ideas", "components"],
}

TITLES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "subject": {"type": "string"},
        "major_ideas": {"type": "array", "items": {"type": "string"}},
        "titles": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject", "major_ideas", "titles"],
}

SLICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "components": {"type": "array", "items": _COMPONENT_FIELDS},
    },
    "required": ["components"],
}

_MISCONCEPTION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "wrong_move": {"type": "string"},
        "broken_kc": {"type": "string"},
    },
    "required": ["wrong_move", "broken_kc"],
}

CREATOR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "discussion": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "kc_type": {
            "type": "string",
            "enum": ["factual", "procedural", "conceptual", "causal", "synthesis"],
        },
        "core_truth": {"type": "string"},
        "rubric": {"type": "array", "items": {"type": "string"}},
        "misconceptions": {"type": "array", "items": _MISCONCEPTION},
        "prerequisite_codes": {"type": "array", "items": {"type": "string"}},
        "encompasses_codes": {"type": "array", "items": {"type": "string"}},
        "fact": {"type": "string"},
        "retrieval_question": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "blanked_step": {"type": "integer"},
        "solo_problem": {"type": "string"},
        "solo_check": {"type": "string"},
        "case_a": {"type": "string"},
        "case_b": {"type": "string"},
        "prediction": {"type": "string"},
        "rule": {"type": "string"},
        "decision_point": {"type": "string"},
        "flawed_claim": {"type": "string"},
        "causal_chain": {"type": "string"},
        "mix_a": {"type": "string"},
        "mix_b": {"type": "string"},
        "faulty_plan": {"type": "string"},
    },
    "required": [
        "discussion",
        "title",
        "description",
        "kc_type",
        "core_truth",
        "rubric",
        "misconceptions",
        "prerequisite_codes",
        "encompasses_codes",
        "fact",
        "retrieval_question",
        "steps",
        "blanked_step",
        "solo_problem",
        "solo_check",
        "case_a",
        "case_b",
        "prediction",
        "rule",
        "decision_point",
        "flawed_claim",
        "causal_chain",
        "mix_a",
        "mix_b",
        "faulty_plan",
    ],
}


def model_for_call(model: str) -> str:
    """The id sent to the provider. A saved row may still hold the id without the tilde."""
    chosen = (model or "").strip()
    if chosen == LEGACY_DEEPSEEK_FLASH_MODEL:
        return DEEPSEEK_FLASH_MODEL
    return chosen


def checked_model(model: str) -> str:
    chosen = model_for_call(model) or DEFAULT_KC_CHAT_MODEL
    if chosen not in KC_CHAT_MODELS:
        raise ValueError("That model is not allowed.")
    return chosen


def titles_are_sliced(description: str, titles: list[str]) -> bool:
    """True when every title is a phrase cut out of the description."""
    blob = re.sub(r"\s+", " ", description or "").lower()
    if len(titles) < 2 or len(blob) < 12:
        return False
    hits = 0
    for title in titles:
        cleaned = re.sub(r"\s+", " ", title).strip(" .").lower()
        if len(cleaned) >= 8 and cleaned in blob:
            hits += 1
    return hits == len(titles)


def format_description(outline: object, topics: object, goals: object) -> str:
    def parts(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [part.strip() for part in re.split(r"[;\n]", value) if part.strip()]
        return []

    outline_text = str(outline or "").strip()
    topic_line = "; ".join(parts(topics))
    goal_line = "; ".join(parts(goals))
    if not outline_text or not topic_line or not goal_line:
        return ""
    return f"Outline: {outline_text}\nTopics: {topic_line}\nGoals: {goal_line}"


def _kind_line(ctx: dict) -> str:
    kind = ctx["kind"]
    if kind == "time_boxed" and ctx["minutes"]:
        return f"Kind: Time boxed. Fit the list to {ctx['minutes']} minutes."
    if kind == "time_boxed":
        return "Kind: Time boxed. Fit the list to the time."
    if kind == "curiosity":
        return "Kind: Curiosity. Make a path through the subject."
    return "Kind: Mastery. Give the fuller rigorous breakdown."


def _count_line(ctx: dict) -> str:
    count = ctx["count"]
    if not count:
        return "No count was requested. Use as many distinct components as the kind needs."
    mode, number = count
    if mode == "min":
        return f'The author asked for a minimum of {number}. Return at least {min(number, MAX_COMPONENTS)} distinct components.'
    return f'The author asked for {number} components. Return {min(number, MAX_COMPONENTS)} distinct components.'


def _draft_width(ctx: dict) -> int:
    if ctx["pasted"]:
        return len(ctx["titles"])
    count = ctx["count"]
    if count:
        return min(int(count[1]), MAX_COMPONENTS)
    return len(ctx["titles"])


def _course_setup(
    *,
    title: str,
    description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    message: str,
    model: str,
) -> tuple[str, dict, list[str]]:
    chosen = checked_model(model)
    ctx = planning_context(
        title=title,
        description=description,
        kind=kind,
        minutes=minutes,
        message=message,
    )
    listed = "\n".join(f"- {item}" for item in ctx["titles"])
    if ctx["pasted"]:
        title_rule = "The author pasted a title list. Use those titles as written, in this order. Do not rename them."
    else:
        title_rule = (
            "A careful syllabus for this subject and kind already uses the titles below. "
            "You may use them. If you choose others, they are distinct parts of the subject, "
            "not clauses cut from the description."
        )
    lines = [
        COURSE_RULES,
        f"Course name: {title}",
        f"Course description: {description or 'None yet.'}",
        f"Audience: {audience}",
        _kind_line(ctx),
        _count_line(ctx),
        title_rule,
        "Syllabus titles:",
        listed or "- None",
    ]
    return chosen, ctx, lines


def course_bundle(
    *,
    title: str,
    description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    message: str,
    model: str,
) -> dict:
    chosen, ctx, lines = _course_setup(
        title=title,
        description=description,
        audience=audience,
        kind=kind,
        minutes=minutes,
        message=message,
        model=model,
    )
    if _draft_width(ctx) > DESCRIPTION_SLICE:
        lines.append(
            "Return the subject, the major ideas, and the titles only. "
            "Do not write outlines, topics, or goals in this reply."
        )
        schema = TITLES_SCHEMA
        phase = "titles"
    else:
        lines.append(
            "Return the subject, the major ideas, and then the components. "
            "Each component has a title, a short outline, key topics, and key goals."
        )
        schema = COURSE_SCHEMA
        phase = "full"
    return {
        "model": chosen,
        "system_prompt": "\n".join(lines),
        "user_prompt": (message or "").strip() or "Draft the component list.",
        "schema": schema,
        "pass": phase,
        "slice_size": DESCRIPTION_SLICE,
    }


def _plain_titles(titles: list[str]) -> list[str]:
    chosen: list[str] = []
    for item in titles:
        title = str(item or "").strip()
        if title:
            chosen.append(title)
    return chosen


def _groups(titles: list[str], size: int) -> list[list[str]]:
    return [titles[start : start + size] for start in range(0, len(titles), size)]


def _description_bundle(
    *,
    model: str,
    ctx: dict,
    title: str,
    description: str,
    audience: str,
    message: str,
    titles: list[str],
    subject: str,
    major_ideas: list[str],
) -> dict:
    listed = "\n".join(f"- {item}" for item in titles)
    ideas = "; ".join(major_ideas) if major_ideas else subject
    system = "\n".join(
        [
            COURSE_RULES,
            f"Course name: {title}",
            f"Course description: {description or 'None yet.'}",
            f"Audience: {audience}",
            _kind_line(ctx),
            _count_line(ctx),
            f"Subject: {subject}",
            f"Major ideas: {ideas}",
            "These titles are already chosen. Write a short outline, the key topics, and the key goals for each one.",
            "Do not add a title, drop a title, or rename a title. Keep this order.",
            "Titles:",
            listed,
            "Return only these components.",
        ]
    )
    return {
        "model": model,
        "system_prompt": system,
        "user_prompt": (message or "").strip() or "Write the descriptions for these titles.",
        "schema": SLICE_SCHEMA,
        "titles": list(titles),
    }


def description_plan(
    *,
    title: str,
    description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    message: str,
    model: str,
    titles: list[str],
    subject: str = "",
    major_ideas: list[str] | None = None,
) -> dict:
    """Description calls for one slice of titles at a time. The full list is checked first."""
    chosen, ctx, _lines = _course_setup(
        title=title,
        description=description,
        audience=audience,
        kind=kind,
        minutes=minutes,
        message=message,
        model=model,
    )
    chosen_titles = list(ctx["titles"]) if ctx["pasted"] else _plain_titles(titles)
    _check_titles(description, chosen_titles, ctx)
    subject_text = (subject or "").strip() or str(ctx["subject"])
    ideas = [str(item).strip() for item in (major_ideas or []) if str(item).strip()] or list(ctx["ideas"])
    slices = [
        _description_bundle(
            model=chosen,
            ctx=ctx,
            title=title,
            description=description,
            audience=audience,
            message=message,
            titles=group,
            subject=subject_text,
            major_ideas=ideas,
        )
        for group in _groups(chosen_titles, DESCRIPTION_SLICE)
    ]
    return {"slice_size": DESCRIPTION_SLICE, "slices": slices}


def _model_rows(proposal: dict) -> list[dict]:
    rows = proposal.get("components")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _descriptions_for(rows: list[dict], titles: list[str]) -> list[str]:
    by_title: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("title") or "").strip().lower()
        if key and key not in by_title:
            by_title[key] = row
    written: list[str] = []
    for index, title in enumerate(titles):
        row = by_title.get(title.lower())
        if row is None and index < len(rows):
            row = rows[index]
        if row is None:
            written.append("")
            continue
        written.append(format_description(row.get("outline"), row.get("topics"), row.get("goals")))
    return written


def _model_titles(rows: list[dict]) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for row in rows:
        title = str(row.get("title") or "").strip()
        key = title.lower()
        if not title or key in seen:
            continue
        seen.add(key)
        titles.append(title)
    return titles


def _check_titles(description: str, titles: list[str], ctx: dict) -> None:
    if len(titles) < 2:
        raise ValueError("Return at least two distinct components.")
    if len(titles) > MAX_COMPONENTS:
        raise ValueError(f"Return at most {MAX_COMPONENTS} distinct components.")
    if len({title.lower() for title in titles}) != len(titles):
        raise ValueError("Honor the requested count with distinct components.")
    if not ctx["pasted"] and titles_are_sliced(description, titles):
        raise ValueError("Do not slice the description sentence into titles.")
    count = ctx["count"]
    if not count:
        return
    mode, number = count
    expected = min(number, MAX_COMPONENTS)
    if mode == "min" and len(titles) < expected:
        raise ValueError(f"Honor the requested count. Return at least {expected} distinct components.")
    if mode == "exact" and len(titles) != expected:
        raise ValueError(f"Honor the requested count. Return {expected} distinct components.")


def _ideas_from(proposal: dict, description: str, fallback: list[str]) -> list[str]:
    raw = proposal.get("major_ideas")
    ideas: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text and text.lower() not in {idea.lower() for idea in ideas}:
                ideas.append(text)
    ideas = ideas[:8]
    if not ideas:
        return list(fallback)
    if titles_are_sliced(description, ideas):
        raise ValueError("Name the major ideas of the subject. Do not slice the description into ideas.")
    return ideas


def assemble_course(
    *,
    title: str,
    description: str,
    kind: str,
    minutes: int | None,
    message: str,
    proposal: dict,
) -> dict:
    """Turn a model object into a reply and a component list. This does not write."""
    if not isinstance(proposal, dict):
        raise ValueError("The model reply could not be read.")
    ctx = planning_context(
        title=title,
        description=description,
        kind=kind,
        minutes=minutes,
        message=message,
    )
    rows = _model_rows(proposal)
    if ctx["pasted"]:
        titles = list(ctx["titles"])
    else:
        titles = _model_titles(rows)
    _check_titles(description, titles, ctx)
    descriptions = _descriptions_for(rows, titles)
    if any(not item for item in descriptions):
        raise ValueError("Each component needs a short outline, the key topics, and the key goals.")
    subject = str(proposal.get("subject") or "").strip() or str(ctx["subject"])
    if description and subject.lower() == description.strip().lower():
        subject = str(ctx["subject"])
    ideas = _ideas_from(proposal, description, list(ctx["ideas"]))
    reply = planned_reply(
        subject=subject,
        ideas=ideas,
        kind=str(ctx["kind"]),
        minutes=ctx["minutes"],
        titles=titles,
        count=ctx["count"],
        sized_to_minutes=bool(ctx["sized_to_minutes"]),
        pasted=bool(ctx["pasted"]),
    )
    return {
        "reply": reply,
        "components": [
            {"title": component_title, "description": text}
            for component_title, text in zip(titles, descriptions, strict=True)
        ],
    }


def _creator_schema(other_codes: list[str]) -> dict:
    """The creator schema for this call.

    When the course has other components, broken_kc is one of those codes.
    When it has none, the misconceptions array is empty and broken_kc is not a field.
    History is not a field on this schema.
    """
    schema = copy.deepcopy(CREATOR_SCHEMA)
    if other_codes:
        schema["properties"]["misconceptions"] = {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "wrong_move": {"type": "string"},
                    "broken_kc": {
                        "type": "string",
                        "enum": list(other_codes),
                        "description": (
                            "Copy one code from this list. "
                            "Not a description and not this component's code."
                        ),
                    },
                },
                "required": ["wrong_move", "broken_kc"],
            },
        }
        return schema
    schema["properties"]["misconceptions"] = {
        "type": "array",
        "maxItems": 0,
        "items": {"type": "string"},
    }
    return schema


def _creator_links(other_codes: list[str]) -> str:
    if not other_codes:
        return (
            "This course has no other component. Return an empty misconceptions array. "
            "Do not ask for a broken_kc. "
            "Prerequisite codes, encompasses codes, and synthesis mixes stay empty."
        )
    return (
        "Copy one code from the other component codes into broken_kc. "
        "It is not a description and not this component's code. "
        "Prerequisite codes, encompasses codes, and synthesis mixes "
        "have to be chosen from the other component codes. "
        "Use an empty list for prerequisites, encompasses, or mixes when none of those links fit."
    )


def creator_bundle(
    *,
    course_title: str,
    course_description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    node_title: str,
    node_code: str,
    node_description: str,
    other_codes: list[str],
    previous: dict | None,
    message: str,
    model: str,
) -> dict:
    chosen = checked_model(model)
    if kind == "time_boxed" and minutes:
        kind_line = f"Kind: Time boxed, {minutes} minutes. Fit this component to that time."
    elif kind == "time_boxed":
        kind_line = "Kind: Time boxed. Fit this component to the time."
    elif kind == "curiosity":
        kind_line = "Kind: Curiosity. Treat this component as a step on a path through the subject."
    else:
        kind_line = "Kind: Mastery. Give the fuller rigorous treatment of this component."
    brief = (node_description or "").strip() or "This component has no description yet. Use the title and the course."
    previous_line = "There is no draft yet. Go into the topic, then fill the fields."
    if previous:
        previous_line = (
            "A draft is already in the thread. Revise it. Still go into the topic before the fields. "
            f"Current type: {previous.get('kc_type') or 'unset'}. "
            f"Current core truth: {previous.get('core_truth') or 'none'}."
        )
    codes = ", ".join(other_codes) if other_codes else "none"
    system = "\n".join(
        [
            CREATOR_RULES,
            f"Course: {course_title}. {course_description}".strip(),
            f"Audience: {audience}",
            kind_line,
            f"Component: {node_title} ({node_code})",
            "Brief:",
            brief,
            f"Other component codes: {codes}",
            previous_line,
            "The discussion comes first and goes into the topic. "
            "Then recommend every enterable field from the brief. "
            "Write description as three lines: Outline, Topics, and Goals. "
            "Fill title, one type, the fields for that type, the core truth, "
            "one rubric line for each topic goal, then the practice checks, "
            "misconceptions, prerequisites, and encompasses. "
            "Leave the fields of the other types empty. ",
            _creator_links(other_codes),
        ]
    )
    return {
        "model": chosen,
        "system_prompt": system,
        "user_prompt": (message or "").strip(),
        "schema": _creator_schema(other_codes),
    }


def checked_discussion(discussion: str, title: str) -> str:
    text = (discussion or "").strip()
    if len(text) < 80:
        raise ValueError(
            "Go into the topic before you fill the type, the core truth, the rubric, and the checks."
        )
    if text.lower().startswith("title:"):
        raise ValueError("Go into the topic before you fill the fields.")
    if title and title.lower() not in text.lower() and len(text) < 160:
        raise ValueError(f"Go into {title} before you fill the fields.")
    return text
