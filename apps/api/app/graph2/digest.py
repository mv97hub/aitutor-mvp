"""Frozen three-line tutor note composer.

Outputs at most three plain-English coaching lines for the next component:
1. Strength (highest skill with >= 3 observations that the next component asks for)
2. Focus (lowest skill with >= 3 observations that the next component asks for)
3. Misconception (latest unresolved course misconception, when one is on file)

Never outputs a number or references the radar. Never imports `kc_prompt`,
`kc_loop`, `kc`, or `block_score`.
"""

from __future__ import annotations

from app.block_catalog import SKILL_KEYS
from app.graph2.signals import MIN_OBSERVATIONS_FOR_RADAR

STRENGTH_DIRECTIVES: dict[str, str] = {
    "evidence": "Evidence is a strength: let the child cite their line or number and move on.",
    "perspectives": "Perspectives is a strength: ask for the contrast between viewpoints in one turn.",
    "causes": "Causes is a strength: accept one clear cause and its effect.",
    "inquiry": "Inquiry is a strength: leave one opening for the child to ask their own question.",
    "errors": "Errors is a strength: let the child name the broken step directly.",
    "transfer": "Transfer is a strength: pose one new case and accept a clean carry-over.",
    "explaining": "Explaining is a strength: ask for their plain-language explanation once.",
    "calibration": "Calibration is a strength: take one certainty check and move on.",
}

FOCUS_DIRECTIVES: dict[str, str] = {
    "evidence": "Focus on Evidence: ask which line or number supports the answer before accepting it.",
    "perspectives": "Focus on Perspectives: keep the child on what the other person would say before any verdict.",
    "causes": "Focus on Causes: ask what changes if that one cause is removed, and stop there.",
    "inquiry": "Focus on Inquiry: ask what is still unverified before closing the step.",
    "errors": (
        "Focus on Errors: point at the flawed step and ask where it fails, "
        "and do not supply the correction in that same line."
    ),
    "transfer": "Focus on Transfer: change the surface of the problem and ask which part of the old idea still applies.",
    "explaining": "Focus on Explaining: name the audience and ask for the explanation before adding anything.",
    "calibration": "Focus on Calibration: ask what evidence would make them revise; confidence is not correctness.",
}

_SINGLE_SKILL_STRENGTH_CUTOFF = 0.65


def _latest_unresolved_misconception(misconceptions: list | None) -> str:
    if not isinstance(misconceptions, list):
        return ""
    for item in reversed(misconceptions):
        if isinstance(item, dict):
            if item.get("resolved"):
                continue
            text = " ".join(str(item.get("text") or "").split()).strip()
            if text:
                return text[:200]
        elif isinstance(item, str):
            text = " ".join(item.split()).strip()
            if text:
                return text[:200]
    return ""


def compose_tutor_note(
    *,
    skills_state: dict | None,
    next_component_skills: list[str] | tuple[str, ...] | set[str],
    course_misconceptions: list | None = None,
) -> str:
    """Compose the frozen plain-text tutor note (<= 3 lines, zero numbers, no radar)."""
    skills_map = skills_state if isinstance(skills_state, dict) else {}
    requested = {str(s).strip().lower() for s in (next_component_skills or []) if str(s).strip().lower() in SKILL_KEYS}

    qualifying: list[tuple[str, float, int]] = []
    for idx, key in enumerate(SKILL_KEYS):
        if key not in requested:
            continue
        entry = skills_map.get(key)
        if not isinstance(entry, dict):
            continue
        try:
            count = int(entry.get("count") or 0)
            score = float(entry.get("score"))
        except (TypeError, ValueError):
            continue
        if count < MIN_OBSERVATIONS_FOR_RADAR:
            continue
        qualifying.append((key, score, idx))

    lines: list[str] = []
    if len(qualifying) >= 2:
        strength_key = max(qualifying, key=lambda item: (item[1], -item[2]))[0]
        remaining = [item for item in qualifying if item[0] != strength_key]
        focus_key = min(remaining, key=lambda item: (item[1], item[2]))[0]
        lines.append(STRENGTH_DIRECTIVES[strength_key])
        lines.append(FOCUS_DIRECTIVES[focus_key])
    elif len(qualifying) == 1:
        only_key, only_score, _ = qualifying[0]
        if only_score >= _SINGLE_SKILL_STRENGTH_CUTOFF:
            lines.append(STRENGTH_DIRECTIVES[only_key])
        else:
            lines.append(FOCUS_DIRECTIVES[only_key])

    misc = _latest_unresolved_misconception(course_misconceptions)
    if misc:
        lines.append(f"Earlier misconception to watch for: {misc}")

    return "\n".join(lines)
