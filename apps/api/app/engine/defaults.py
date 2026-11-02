"""Age-band defaults for layer 2 and for the tutor-agent settings in layers 3 and 4."""

from __future__ import annotations

from dataclasses import dataclass

AGE_BANDS = ("6-8", "9-11", "12-14", "15-17")


def age_band_for(age: int | None) -> str:
    if age is None or age <= 8:
        return "6-8"
    if age <= 11:
        return "9-11"
    if age <= 14:
        return "12-14"
    return "15-17"


@dataclass(frozen=True)
class AgeProfile:
    age_band: str
    reading_level: str
    modality: str
    persona: str
    lexicon: str
    metaphors: str
    sidekick: str
    socratic_strictness: str = "balanced"
    struggle_window: str = "minimum"
    anti_spoiler: bool = True
    pacing: str = "short-turns-one-question"


PROFILES: dict[str, AgeProfile] = {
    "6-8": AgeProfile(
        age_band="6-8",
        reading_level="early-reader",
        modality="hands-on",
        persona="Curious Co-Explorer",
        lexicon="early-grade concrete",
        metaphors="playground rules and familiar objects",
        sidekick="a sidekick with a clear flaw",
    ),
    "9-11": AgeProfile(
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        persona="Curious Co-Explorer",
        lexicon="vivid middle-grade",
        metaphors="sports-team captain and playground rules",
        sidekick="a sidekick with a clear flaw",
    ),
    "12-14": AgeProfile(
        age_band="12-14",
        reading_level="grade-level",
        modality="visual",
        persona="Tactical Engineering Commander",
        lexicon="precise visual-spatial",
        metaphors="bridge truss, robotics hinge, and laser grid",
        sidekick="a rookie who treats a picture as a proof",
    ),
    "15-17": AgeProfile(
        age_band="15-17",
        reading_level="high-school",
        modality="verbal",
        persona="Spirited FOMC Debate Moderator",
        lexicon="analytical high-school; the student is a decision maker who must give multi-step causal chains",
        metaphors="policy levers and multi-step causal chains",
        sidekick="a pundit who skips the causal chain",
    ),
}


def profile_for_age(age: int | None) -> AgeProfile:
    return PROFILES[age_band_for(age)]


def profile_for_band(age_band: str) -> AgeProfile:
    return PROFILES.get(age_band, PROFILES["9-11"])
