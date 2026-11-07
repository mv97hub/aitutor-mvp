"""Prompt for one knowledge-component step.

The recipe comes from the component type. The tutor profile and the student
row change how that step is said. They do not change the type, the edges, or
the score. The quest prompt builder is a different module.
"""

from __future__ import annotations

from app.engine.choices import METAPHORS, PERSONAS, SIDEKICKS, VOICES
from app.models import KcGoal, KcNode, Student, TutorProfile

RECIPE_NAME = {
    "factual": "retrieval",
    "procedural": "worked-example",
    "conceptual": "contrasting-cases",
    "causal": "decision-point",
    "synthesis": "rookie-correction",
}

STEP_LABELS = {
    "factual": ["Retrieval question", "Short confirmation"],
    "procedural": ["Worked example", "Faded step", "Solo solve"],
    "conceptual": ["Predict two cases", "See the contrast", "State the rule"],
    "causal": ["Decision point", "Flawed claim", "Short defense"],
    "synthesis": ["Faulty plan", "Correct the plan"],
}

_EXPLAIN = {
    1: "Ask the question with almost no explanation first.",
    2: "Give one short line, then the question.",
    3: "Give a brief explanation, then one question.",
    4: "Explain the idea, then ask one question.",
    5: "Give a fuller explanation before the one question.",
}

# Fixed prompt sentences. A later admin page can change these values. This module keeps them.
PROMPT_ONE_STEP = "You are the knowledge-component tutor. One step of one component this turn."
PROMPT_SETTINGS = "Settings do not change the type, the edges, or the score."
PROMPT_NO_LATER = "Do not ask a later step, and do not ask a second kind of question."
PROMPT_EDGES = "Edges stay as stored."
PROMPT_WRONG = "A wrong answer is explained against the matching misconception, once, then retried or stepped down."
PROMPT_ONE_QUESTION = "One question at the end of the turn when this step asks something."

_RECIPE_LINE = {
    "factual": "Factual components use the short recipe: one retrieval question, then a short confirmation.",
    "procedural": "Procedural components use a worked example, then one faded step, then a solo solve.",
    "conceptual": "Conceptual principles use two cases to predict, then the contrast, then the rule.",
    "causal": "Causal or historical components use a decision point, a flawed claim to mark, then a short defense.",
    "synthesis": "Synthesis components have a rookie state a faulty plan that mixes two earlier components. The kid corrects it.",
}


def recipe_name(kc_type: str | None) -> str:
    return RECIPE_NAME.get(kc_type or "", "unset")


def step_labels(kc_type: str | None) -> list[str]:
    return list(STEP_LABELS.get(kc_type or "", ["This step"]))


def _label(options: tuple[tuple[str, str], ...], value: str) -> str:
    for key, text in options:
        if key == value:
            return text
    return value


def labeled_choice(options: tuple[tuple[str, str], ...], value: str) -> str:
    """The stored id, with the profile label the prompt also sends."""
    text = (value or "").strip()
    if not text:
        return ""
    label = _label(options, text)
    if label == text:
        return text
    return f"{text} ({label})"


def instructive_value(level: int) -> str:
    bounded = min(5, max(1, int(level)))
    return f"{bounded}. {_EXPLAIN[bounded]}"


def _codes(values: list | None) -> str:
    items = [str(item) for item in (values or []) if str(item).strip()]
    return ", ".join(items) if items else "none"


def build_kc_prompt(
    *,
    student: Student,
    profile: TutorProfile,
    node: KcNode,
    goal: KcGoal,
    step: int,
    step_text: str,
) -> str:
    """One system prompt for the current step of one component."""
    labels = step_labels(node.kc_type)
    index = min(max(step, 0), len(labels) - 1)
    label = labels[index]
    interests = ", ".join(str(item) for item in (student.interests or [])) or "none named"
    rubric = [str(item) for item in (node.rubric or []) if str(item).strip()]
    misconceptions = []
    for item in node.misconceptions or []:
        if not isinstance(item, dict):
            continue
        wrong = str(item.get("wrong_move") or "").strip()
        broken = str(item.get("broken_kc") or "").strip()
        if wrong and broken:
            misconceptions.append(f"{wrong} -> {broken}")
    stay = "yes" if profile.stay_on_course else "no"
    level = min(5, max(1, int(profile.instructive)))
    lines = [
        PROMPT_ONE_STEP,
        PROMPT_SETTINGS,
        f"Course: {goal.title}. {goal.description}".strip(),
        f"Component: {node.title} ({node.code}).",
        f"Type: {node.kc_type or 'unset'}.",
        f"Recipe: {recipe_name(node.kc_type)}.",
        _RECIPE_LINE.get(node.kc_type or "", "This component has no recipe yet."),
        f"This turn is step {index + 1} of {len(labels)}: {label}.",
        PROMPT_NO_LATER,
        f"Say this step: {step_text}",
        f"Core truth: {node.core_truth or 'none yet'}.",
        "Rubric checks: " + ("; ".join(rubric) if rubric else "none yet") + ".",
        "Misconceptions: " + ("; ".join(misconceptions) if misconceptions else "none") + ".",
        PROMPT_WRONG,
        f"Prerequisites: {_codes(node.prerequisite_codes)}.",
        f"Encompasses: {_codes(node.encompasses_codes)}.",
        PROMPT_EDGES,
        (
            f"Student: {student.display_name}. "
            f"Age: {student.age}. "
            f"Reading level: {student.reading_level or 'unset'}. "
            f"Modality: {student.modality or 'unset'}. "
            f"Interests: {interests}."
        ),
        f"Persona: {profile.persona} ({_label(PERSONAS, profile.persona)}).",
        f"Lexicon: {profile.lexicon} ({_label(VOICES, profile.lexicon)}).",
        f"Metaphors: {profile.metaphors} ({_label(METAPHORS, profile.metaphors)}).",
        f"Sidekick: {profile.sidekick} ({_label(SIDEKICKS, profile.sidekick)}).",
        f"Explain before the question: level {level}. {_EXPLAIN[level]}",
        f"Struggle window: {profile.struggle_window}.",
        f"Stay on course: {stay}.",
        (
            "Use the persona, lexicon, metaphors, and sidekick. "
            "Use the student's age and interests in how you say this step."
            if profile.use_interests
            else "Use the persona, lexicon, metaphors, and sidekick. Do not build the example around interests."
        ),
        PROMPT_ONE_QUESTION,
        PROMPT_SETTINGS,
    ]
    return "\n".join(lines)
