"""Typed inputs for the seven prompt layers.

Layer 2 is the student. Layers 3 and 4 are tutor-agent settings. They are
separate objects so a later tutor profile can replace the columns that hold
them today without changing this assembler.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RubricCriterion:
    id: str
    text: str
    weight: int


@dataclass(frozen=True)
class MisconceptionTrap:
    id: str
    trap: str
    note: str


@dataclass(frozen=True)
class HintLadder:
    nudge: str
    analogy: str
    scaffold: str


@dataclass(frozen=True)
class WidgetChoice:
    id: str
    text: str
    misconception: str


@dataclass(frozen=True)
class WidgetGrade:
    correct: bool
    score: int
    passed: bool
    misconception: str | None
    choice_ids: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class WidgetTask:
    type: str
    prompt: str
    choices: tuple[WidgetChoice, ...]
    answer: str | tuple[str, ...]
    explain: bool
    grade: WidgetGrade | None


@dataclass(frozen=True)
class Layer1Beat:
    """Active Tier 4 beat, plus the unit continuity sentence."""

    course_title: str
    unit_title: str
    continuity: str
    quest_code: str
    quest_title: str
    beat_role: str
    beat_position: int
    beat_count: int
    bloom_level: str
    cognitive_load: str
    prompt: str
    rubric: tuple[RubricCriterion, ...]
    misconceptions: tuple[MisconceptionTrap, ...]
    hint_ladder: HintLadder
    widget: WidgetTask | None
    pass_score: int
    gate_cleared: bool
    finished: bool


@dataclass(frozen=True)
class Layer2Student:
    """Student traits. Attempt count and ZPD are computed at runtime."""

    display_name: str
    age_band: str
    reading_level: str
    modality: str
    interests: tuple[str, ...]
    attempt_count: int
    zpd: str


@dataclass(frozen=True)
class Layer3Tutor:
    """Tutor-agent voice. Not a student trait."""

    persona: str
    lexicon: str
    metaphors: str
    sidekick: str


@dataclass(frozen=True)
class Layer4Discourse:
    """Tutor-agent guardrails. Not a student trait."""

    socratic_strictness: str
    struggle_window: str
    anti_spoiler: bool
    pacing: str


@dataclass(frozen=True)
class Layer5Affect:
    praise: str


@dataclass(frozen=True)
class Layer6Metacognition:
    self_explanation: str


@dataclass(frozen=True)
class Layer7Memory:
    schedule: str


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    response_schema: dict
    temperature: float
