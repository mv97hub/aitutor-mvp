"""Closed choices for the one default tutor profile.

The assembler understands these ids. Free text is not a profile value.
"""

from __future__ import annotations

PERSONAS: tuple[tuple[str, str], ...] = (
    ("curious-co-explorer", "Curious co-explorer"),
    ("tactical-coach", "Tactical coach"),
    ("debate-moderator", "Debate moderator"),
    ("patient-explainer", "Patient explainer"),
)

VOICES: tuple[tuple[str, str], ...] = (
    ("early-concrete", "Early concrete"),
    ("middle-grade-vivid", "Middle-grade vivid"),
    ("precise-visual", "Precise visual"),
    ("analytical-high-school", "Analytical high-school"),
)

METAPHORS: tuple[tuple[str, str], ...] = (
    ("playground-sports", "Playground and sports"),
    ("buildings-machines", "Buildings and machines"),
    ("policy-cause", "Policy and cause-and-effect"),
    ("none", "None (plain language only)"),
)

SIDEKICKS: tuple[tuple[str, str], ...] = (
    ("bumbling-partner", "Bumbling partner"),
    ("rookie-picture", "Rookie who trusts a picture"),
    ("pundit", "Pundit who skips the chain"),
    ("off", "Off"),
)

STRUGGLE_WINDOWS: tuple[tuple[str, str], ...] = (
    ("short", "Short (1 miss)"),
    ("standard", "Standard (2)"),
    ("long", "Long (3)"),
)

# Reading voice follows the persona unless the profile overrides it.
PERSONA_VOICE: dict[str, str] = {
    "curious-co-explorer": "middle-grade-vivid",
    "tactical-coach": "precise-visual",
    "debate-moderator": "analytical-high-school",
    "patient-explainer": "early-concrete",
}

_STRICTNESS = {
    1: "socratic",
    2: "mostly-socratic",
    3: "balanced",
    4: "mostly-instructive",
    5: "instructive",
}

_PACING = {
    1: "one-short-question",
    2: "short-question",
    3: "short-turns-one-question",
    4: "fact-then-question",
    5: "fuller-lesson-then-question",
}


def ids(options: tuple[tuple[str, str], ...]) -> set[str]:
    return {item[0] for item in options}


def strictness_for(level: int) -> str:
    return _STRICTNESS[min(5, max(1, level))]


def pacing_for(level: int) -> str:
    return _PACING[min(5, max(1, level))]
