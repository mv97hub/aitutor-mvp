import inspect
from pathlib import Path

from app.engine.assemble import RESPONSE_SCHEMA, TURN_TEMPERATURE, assemble, hint_tier_for, struggle_limit
from app.engine.defaults import age_band_for, profile_for_age
from app.engine.placeholders import affect_layer, memory_layer, metacognition_layer
from app.engine.types import (
    HintLadder,
    Layer1Beat,
    Layer2Student,
    Layer3Tutor,
    Layer4Discourse,
    MisconceptionTrap,
    RubricCriterion,
)


def _beat(**overrides) -> Layer1Beat:
    base = dict(
        course_title="Ancient Rome",
        unit_title="The Republic",
        continuity="King Tarquin abused solo lifetime power. The Republic answered with two consuls.",
        quest_code="ROM-U2-Q1",
        quest_title="The Two-Captain Rule",
        beat_role="mystery_hook",
        beat_position=1,
        beat_count=4,
        bloom_level="analyze",
        cognitive_load="medium",
        prompt="What is one advantage and one problem of two consuls?",
        rubric=(
            RubricCriterion("advantage", "Stops one bully.", 50),
            RubricCriterion("problem", "Names deadlock.", 50),
        ),
        misconceptions=(
            MisconceptionTrap("solo", "One boss is always safer.", "The veto is the check."),
        ),
        hint_ladder=HintLadder("Ask about an attack.", "Two kids, one controller.", "Fill in the blank."),
        widget=None,
        pass_score=70,
        gate_cleared=False,
        finished=False,
    )
    base.update(overrides)
    return Layer1Beat(**base)


def _layers():
    return (
        _beat(),
        Layer2Student(
            display_name="Storm",
            age_band="9-11",
            reading_level="middle-grade",
            modality="story",
            interests=("weather",),
            attempt_count=0,
            zpd="on-level",
        ),
        Layer3Tutor(
            persona="Curious Co-Explorer",
            lexicon="vivid middle-grade",
            metaphors="sports-team captain and playground rules",
            sidekick="a sidekick with a clear flaw",
        ),
        Layer4Discourse(
            socratic_strictness="balanced",
            struggle_window="minimum",
            anti_spoiler=True,
            pacing="short-turns-one-question",
        ),
        affect_layer(),
        metacognition_layer(),
        memory_layer(),
    )


def test_assemble_takes_seven_separate_layers() -> None:
    names = [name for name, param in inspect.signature(assemble).parameters.items() if param.kind is param.POSITIONAL_OR_KEYWORD]
    assert names == [
        "beat",
        "student",
        "tutor",
        "discourse",
        "affect",
        "metacognition",
        "memory",
    ]


def test_engine_package_does_not_import_the_database() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "engine"
    text = "\n".join(path.read_text() for path in root.glob("*.py"))
    assert "sqlalchemy" not in text
    assert "app.models" not in text
    assert "app.database" not in text


def test_prompt_includes_all_seven_layers_and_keeps_tutor_settings_apart() -> None:
    bundle = assemble(*_layers())
    text = bundle.system_prompt
    assert bundle.temperature == TURN_TEMPERATURE
    assert bundle.response_schema == RESPONSE_SCHEMA
    assert bundle.response_schema["required"] == [
        "reply",
        "rubric_met",
        "misconception",
        "hint_tier",
        "advance",
    ]
    for heading in (
        "Layer 1 — Active beat",
        "Layer 2 — Student",
        "Layer 3 — Tutor agent",
        "Layer 4 — Discourse",
        "Layer 5 — Affect",
        "Layer 6 — Metacognition",
        "Layer 7 — Memory",
    ):
        assert heading in text
    student = text.split("Layer 2 — Student", 1)[1].split("Layer 3 — Tutor agent", 1)[0]
    tutor = text.split("Layer 3 — Tutor agent", 1)[1].split("Layer 4 — Discourse", 1)[0]
    assert "weather" in student
    assert "Curious Co-Explorer" not in student
    assert "Curious Co-Explorer" in tutor
    assert "weather" not in tutor
    assert "Growth-mindset praise only" in text
    assert "one self-explanation line" in text
    assert "No live Leitner scheduling" in text
    assert "do not state the answer yet" in text.lower()
    assert "worked answer" not in text.lower()
    assert "At most a few sentences" in text
    assert "Ask one question" in text
    assert "King Tarquin abused solo lifetime power" in text
    assert "advantage (weight 50)" in text
    assert "Live hint tier for this turn: nudge" in text


def test_attempt_count_selects_the_hint_rung() -> None:
    layers = list(_layers())
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=2,
        zpd="support",
    )
    text = assemble(*layers).system_prompt
    assert hint_tier_for(2) == "scaffold"
    assert "Live hint tier for this turn: scaffold" in text
    assert "Fill in the blank." in text


def test_struggle_window_then_worked_answer() -> None:
    assert struggle_limit("minimum") == 2
    layers = list(_layers())
    layers[1] = Layer2Student(
        display_name="Storm",
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        interests=(),
        attempt_count=2,
        zpd="support",
    )
    text = assemble(*layers).system_prompt
    assert "The struggle window is over" in text
    assert "worked answer" in text.lower()
    assert "Set advance to true" in text
    assert "do not state the answer yet" not in text.lower()


def test_kickoff_summarizes_the_quest_objectives() -> None:
    layers = list(_layers())
    layers[0] = _beat(
        quest_objective="Sharing power and writing laws in public protects regular citizens.",
        beat_objectives=(
            "Mystery hook: What is one advantage and one problem of two consuls?",
            "Interactive toy: How did Plebeians peacefully win fair rights?",
        ),
    )
    text = assemble(*layers, kickoff=True).system_prompt
    assert "short summary of what this quest will teach" in text
    assert "Do not invent a different topic" in text
    assert "Sharing power and writing laws in public protects regular citizens." in text
    assert "How did Plebeians peacefully win fair rights?" in text
    assert "advance to false" in text


def test_age_band_defaults() -> None:
    assert age_band_for(10) == "9-11"
    assert age_band_for(13) == "12-14"
    assert age_band_for(16) == "15-17"
    assert "Co-Explorer" in profile_for_age(10).persona
    assert "Commander" in profile_for_age(13).persona
    assert "Moderator" in profile_for_age(16).persona
    assert profile_for_age(16).socratic_strictness == "balanced"
    assert profile_for_age(13).anti_spoiler is True
    assert profile_for_age(10).pacing == "short-turns-one-question"
