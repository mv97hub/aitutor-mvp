"""Closed choices for the one default tutor profile.

The assembler understands these ids. Free text is not a profile value.
"""

from __future__ import annotations

PERSONAS: tuple[tuple[str, str], ...] = (
    ("socratic_mentor", "Calm, respectful academic mentor"),
    ("coach", "Warm coach"),
    ("detective", "Curious detective"),
    ("explorer", "Field explorer"),
    ("storyteller", "Narrative storyteller"),
    ("sibling", "Older sibling"),
    ("wizard", "Playful wizard"),
    ("curious-co-explorer", "Curious co-explorer"),
    ("tactical-coach", "Tactical coach"),
    ("debate-moderator", "Debate moderator"),
    ("patient-explainer", "Patient explainer"),
)

VOCABULARY_REGISTERS: tuple[tuple[str, str], ...] = (
    ("adaptive_to_child", "Adaptive to child (Match Layer 2 reading level & grade band)"),
    ("everyday_conversational", "Everyday conversational (Plain words first, technical terms after)"),
    ("academic_precision", "Academic precision (Exact terms early with a brief kid-friendly gloss)"),
    ("story_rich_expressive", "Story-rich expressive (Vivid phrasing within sentence-length cap)"),
)

INTEREST_WEAVING_MODES: tuple[tuple[str, str], ...] = (
    ("subtle_natural", "Subtle & natural (Hook or 1 example when it fits naturally)"),
    ("frequent_thematic", "Frequent thematic (Frame scenarios around child interests)"),
    ("off", "Off (Neutral curriculum examples or fallback metaphor domain)"),
)

HUMOR_MODES: tuple[tuple[str, str], ...] = (
    ("light_warm", "Light & warm (Occasional gentle wit)"),
    ("playful_banter", "Playful banter (Witty energy on hooks and passes)"),
    ("none_straightforward", "None / straightforward (Zero jokes; earnest throughout)"),
)

VOICES: tuple[tuple[str, str], ...] = (
    ("adaptive_to_child", "Adaptive to child"),
    ("everyday_conversational", "Everyday conversational"),
    ("academic_precision", "Academic precision"),
    ("story_rich_expressive", "Story-rich expressive"),
    ("early-concrete", "Early concrete"),
    ("middle-grade-vivid", "Middle-grade vivid"),
    ("precise-visual", "Precise visual"),
    ("analytical-high-school", "Analytical high-school"),
)

METAPHORS: tuple[tuple[str, str], ...] = (
    ("everyday", "Everyday life"),
    ("games", "Video games & quests"),
    ("nature", "Nature & animals"),
    ("sports", "Sports & motion"),
    ("cooking", "Cooking & recipes"),
    ("scifi", "Space & sci-fi"),
    ("playground-sports", "Playground and sports"),
    ("buildings-machines", "Buildings and machines"),
    ("policy-cause", "Policy and cause-and-effect"),
    ("none", "None (plain language only)"),
)

SIDEKICKS: tuple[tuple[str, str], ...] = (
    ("none", "No sidekick"),
    ("barnaby", "Barnaby the Badger"),
    ("pixel", "Pixel the Robot"),
    ("spark", "Spark the Dragon"),
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
    "socratic_mentor": "academic_precision",
    "coach": "adaptive_to_child",
    "detective": "adaptive_to_child",
    "explorer": "adaptive_to_child",
    "storyteller": "story_rich_expressive",
    "sibling": "everyday_conversational",
    "wizard": "story_rich_expressive",
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
