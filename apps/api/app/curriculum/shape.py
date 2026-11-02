"""Compact builders for a Tier 1 course file."""

from __future__ import annotations


def rubric(*rows: tuple[str, str, int]) -> list[dict]:
    return [{"id": row_id, "text": text, "weight": weight} for row_id, text, weight in rows]


def ladder(nudge: str, analogy: str, scaffold: str) -> dict:
    return {"nudge": nudge, "analogy": analogy, "scaffold": scaffold}


def traps(*items: tuple[str, str, str]) -> list[dict]:
    return [{"id": row_id, "trap": trap, "note": note} for row_id, trap, note in items]


def half(left: tuple[str, str], right: tuple[str, str]) -> list[dict]:
    return rubric((left[0], left[1], 50), (right[0], right[1], 50))


def mcq(
    prompt: str,
    choices: list[tuple[str, str, str]],
    answer: str,
    *,
    explain: bool = False,
    misconception: str = "",
) -> dict:
    return {
        "type": "single",
        "prompt": prompt,
        "choices": [
            {"id": choice_id, "text": text, "misconception": note}
            for choice_id, text, note in choices
        ],
        "answer": answer,
        "explain": explain,
        "misconception": misconception,
    }


def flaw(
    prompt: str,
    choices: list[tuple[str, str, str]],
    answer: str,
    *,
    explain: bool = True,
    misconception: str = "",
) -> dict:
    body = mcq(prompt, choices, answer, explain=explain, misconception=misconception)
    body["type"] = "flaw"
    return body


def multi(
    prompt: str,
    choices: list[tuple[str, str, str]],
    answer: list[str],
    *,
    explain: bool = False,
    misconception: str = "",
) -> dict:
    return {
        "type": "multi",
        "prompt": prompt,
        "choices": [
            {"id": choice_id, "text": text, "misconception": note}
            for choice_id, text, note in choices
        ],
        "answer": answer,
        "explain": explain,
        "misconception": misconception,
    }


def ordering(
    prompt: str,
    choices: list[tuple[str, str]],
    answer: list[str],
    *,
    explain: bool = True,
    misconception: str = "",
) -> dict:
    return {
        "type": "order",
        "prompt": prompt,
        "choices": [{"id": choice_id, "text": text, "misconception": ""} for choice_id, text in choices],
        "answer": answer,
        "explain": explain,
        "misconception": misconception,
    }


def _beat(
    role: str,
    prompt: str,
    rows: list[dict],
    hints: dict,
    trap: list[dict],
    bloom: str,
    load: str,
    widget: dict | None,
) -> dict:
    return {
        "role": role,
        "bloom_level": bloom,
        "cognitive_load": load,
        "prompt": prompt,
        "rubric": rows,
        "misconception_map": trap,
        "hint_ladder": hints,
        "widget": widget,
    }


def quest(
    code: str,
    title: str,
    quest_type: str,
    prereqs: list[str],
    tags: list[str],
    dinner: str,
    beats: list[dict],
    *,
    goal: str,
    criterion: list[dict],
    teach_back: bool = False,
) -> dict:
    return {
        "code": code,
        "title": title,
        "quest_type": quest_type,
        "prerequisite_codes": prereqs,
        "competency_tags": tags,
        "dinner_prompt": dinner,
        "learning_goal": goal,
        "success_criterion": criterion,
        "requires_teach_back": teach_back,
        "beats": beats,
    }


def mv(
    role: str,
    prompt: str,
    rows: list[dict],
    nudge: str,
    analogy: str,
    scaffold: str,
    trap: tuple[str, str, str],
    *,
    bloom: str = "understand",
    load: str = "medium",
    widget: dict | None = None,
    extra_traps: tuple[tuple[str, str, str], ...] = (),
) -> dict:
    return _beat(
        role,
        prompt,
        rows,
        ladder(nudge, analogy, scaffold),
        traps(trap, *extra_traps),
        bloom,
        load,
        widget,
    )


def unit(
    number: int,
    title: str,
    enduring: str,
    continuity: str,
    quests: list[dict],
    *,
    diagnostic: bool = False,
    capstone: bool = False,
) -> dict:
    return {
        "number": number,
        "title": title,
        "enduring_understanding": enduring,
        "continuity_summary": continuity,
        "is_diagnostic": diagnostic,
        "is_capstone": capstone,
        "quests": quests,
    }


def course(
    code: str,
    title: str,
    age_band: str,
    standards: str,
    competencies: list[tuple[str, str]],
    units: list[dict],
) -> dict:
    return {
        "code": code,
        "title": title,
        "age_band": age_band,
        "standards_alignment": standards,
        "competency_dictionary": [
            {"code": tag, "description": text} for tag, text in competencies
        ],
        "units": units,
    }
