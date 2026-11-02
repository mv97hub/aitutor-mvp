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
) -> dict:
    return {
        "code": code,
        "title": title,
        "quest_type": quest_type,
        "prerequisite_codes": prereqs,
        "competency_tags": tags,
        "dinner_prompt": dinner,
        "beats": beats,
    }


def standard(
    code: str,
    title: str,
    quest_type: str,
    prereqs: list[str],
    tags: list[str],
    dinner: str,
    *,
    hook: str,
    hook_pair: tuple[tuple[str, str], tuple[str, str]],
    hook_hints: tuple[str, str, str],
    hook_trap: tuple[str, str, str],
    toy_prompt: str,
    choices: list[tuple[str, str, str]],
    answer: str,
    toy_trap: tuple[str, str, str],
    gate: str,
    gate_pair: tuple[tuple[str, str], tuple[str, str]],
    gate_hints: tuple[str, str, str],
    gate_trap: tuple[str, str, str],
    flip: str,
    flip_pair: tuple[tuple[str, str], tuple[str, str]],
    flip_hints: tuple[str, str, str],
    flip_trap: tuple[str, str, str],
    hook_bloom: str = "understand",
    toy_bloom: str = "apply",
    gate_bloom: str = "analyze",
    flip_bloom: str = "evaluate",
) -> dict:
    toy_note = next(text for choice_id, text, _note in choices if choice_id == answer)
    beats = [
        _beat(
            "mystery_hook",
            hook,
            half(*hook_pair),
            ladder(*hook_hints),
            traps(hook_trap),
            hook_bloom,
            "medium",
            None,
        ),
        _beat(
            "interactive_toy",
            toy_prompt,
            rubric(("choice", toy_note, 100)),
            ladder(
                "Which choice answers the question that was actually asked?",
                "Cross out the choice that brings in an outside power, a pile of money, or a look-alike.",
                "The correct choice is the one that matches the event in this quest, not a neighboring story.",
            ),
            traps(toy_trap),
            toy_bloom,
            "low",
            mcq(toy_prompt, choices, answer, misconception=toy_trap[1]),
        ),
        _beat(
            "diagnostic_gate",
            gate,
            half(*gate_pair),
            ladder(*gate_hints),
            traps(gate_trap),
            gate_bloom,
            "medium",
            None,
        ),
        _beat(
            "feynman_flip",
            flip,
            half(*flip_pair),
            ladder(*flip_hints),
            traps(flip_trap),
            flip_bloom,
            "high",
            None,
        ),
    ]
    return quest(code, title, quest_type, prereqs, tags, dinner, beats)


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
