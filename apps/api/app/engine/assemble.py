"""Assemble the system prompt, response schema, and temperature from seven layers."""

from __future__ import annotations

from app.engine.types import (
    HintLadder,
    Layer1Beat,
    Layer2Student,
    Layer3Tutor,
    Layer4Discourse,
    Layer5Affect,
    Layer6Metacognition,
    Layer7Memory,
    PromptBundle,
    WidgetTask,
)

TURN_TEMPERATURE = 0.4

RESPONSE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": "The only text the student reads.",
        },
        "rubric_met": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ids of rubric rows the student's written words earned.",
        },
        "misconception": {
            "type": ["string", "null"],
            "description": "A misconception to store, or null when the writing is fine.",
        },
        "hint_tier": {
            "type": "string",
            "enum": ["nudge", "analogy", "scaffold"],
        },
        "advance": {
            "type": "boolean",
            "description": "True only when this beat should end.",
        },
    },
    "required": ["reply", "rubric_met", "misconception", "hint_tier", "advance"],
}

_ROLE_LABEL = {
    "mystery_hook": "mystery hook",
    "interactive_toy": "interactive toy",
    "diagnostic_gate": "diagnostic gate",
    "feynman_flip": "Feynman flip",
}


def hint_tier_for(attempt_count: int) -> str:
    if attempt_count <= 0:
        return "nudge"
    if attempt_count == 1:
        return "analogy"
    return "scaffold"


def struggle_limit(window: str) -> int:
    """Unsuccessful tries to hold before a worked answer is allowed.

    "minimum" is the default window: a nudge, then an analogy, then the answer.
    A numeric window is that many unsuccessful tries. The ban must end.
    """
    text = (window or "").strip().lower()
    if text.isdigit():
        return int(text)
    if text in {"extended", "long"}:
        return 3
    return 2


def _hint_text(ladder: HintLadder, tier: str) -> str:
    return getattr(ladder, tier, "") or ""


def _rubric_line(beat: Layer1Beat) -> str:
    if not beat.rubric:
        return "None."
    return " ".join(
        f"{row.id} (weight {row.weight}): {row.text}" for row in beat.rubric
    )


def _traps_line(beat: Layer1Beat) -> str:
    if not beat.misconceptions:
        return "None."
    return " ".join(
        f"{trap.id}: {trap.trap} ({trap.note})" for trap in beat.misconceptions
    )


def _widget_lines(widget: WidgetTask) -> list[str]:
    choices = []
    for choice in widget.choices:
        note = f" misconception: {choice.misconception}" if choice.misconception else ""
        choices.append(f"{choice.id}. {choice.text}{note}")
    answer = widget.answer
    if isinstance(answer, tuple):
        shown = ", ".join(answer)
    else:
        shown = answer
    lines = [
        f"Choice widget ({widget.type}), graded by the server before you speak. Do not grade the taps.",
        f"Widget prompt: {widget.prompt}",
        f"Choices: {' | '.join(choices)}",
        f"Correct answer, for you only: {shown}.",
    ]
    if widget.explain:
        lines.append(
            "A short written explanation may come with the choice. Grade that writing with rubric_met. Do not change the tap score."
        )
    else:
        lines.append("No written explanation is required.")
    grade = widget.grade
    if grade is None:
        lines.append("They have not submitted the widget yet. Invite them to choose. Set advance to false.")
        return lines
    lines.append(
        f"Server grade of the taps: {'passed' if grade.passed else 'not passed'}, score {grade.score}."
    )
    lines.append(f"Choice ids: {', '.join(grade.choice_ids) or 'none'}.")
    lines.append(f"Their explanation: {grade.explanation.strip() or 'none'}.")
    lines.append(
        f"Stored misconception: {grade.misconception or 'none'}. Keep it. Do not invent a different one for the taps."
    )
    return lines


def _layer1(beat: Layer1Beat, tier: str) -> list[str]:
    role = _ROLE_LABEL.get(beat.beat_role, beat.beat_role.replace("_", " "))
    lines = [
        "Layer 1 — Active beat",
        f"Course: {beat.course_title}.",
        f"Unit: {beat.unit_title}.",
        f"Unit continuity: {beat.continuity.strip() or 'None.'}",
        f"Quest {beat.quest_code}: {beat.quest_title}.",
    ]
    if beat.finished:
        lines.append(
            "This quest is finished. Congratulate the student in one or two sentences. Do not start another quest. Set advance to false, rubric_met to [], and misconception to null."
        )
        return lines
    lines.extend(
        [
            f"Beat {beat.beat_position} of {beat.beat_count}: {role}.",
            f"Bloom level: {beat.bloom_level}. Cognitive load: {beat.cognitive_load}.",
            f"Task, in your own short words if you need to: {beat.prompt}",
            f"Rubric rows: {_rubric_line(beat)}",
            f"Pass score: {beat.pass_score}.",
            f"Misconception traps: {_traps_line(beat)}",
            "Hint ladder: "
            f"rung 1 nudge: {beat.hint_ladder.nudge or 'Ask them to try once more.'} "
            f"Rung 2 analogy: {beat.hint_ladder.analogy or 'Offer a picture, not the answer.'} "
            f"Rung 3 scaffold: {beat.hint_ladder.scaffold or 'Give a sentence starter.'}",
            f"Live hint tier for this turn: {tier}. Use this rung only: {_hint_text(beat.hint_ladder, tier) or 'Ask them to try once more.'}",
            f"Diagnostic gate cleared: {'yes' if beat.gate_cleared else 'no'}.",
        ]
    )
    if beat.widget is not None:
        lines.extend(_widget_lines(beat.widget))
    return lines


def _layer2(student: Layer2Student) -> list[str]:
    interests = ", ".join(student.interests) if student.interests else "none listed"
    return [
        "Layer 2 — Student",
        f"Name: {student.display_name}.",
        f"Age band: {student.age_band}.",
        f"Reading level: {student.reading_level or 'unspecified'}.",
        f"Modality: {student.modality or 'unspecified'}.",
        f"Interest affinities: {interests}.",
        f"Live attempt count on this beat: {student.attempt_count}.",
        f"ZPD: {student.zpd}.",
    ]


def _layer3(tutor: Layer3Tutor) -> list[str]:
    return [
        "Layer 3 — Tutor agent",
        f"Persona: {tutor.persona}.",
        f"Lexicon: {tutor.lexicon}.",
        f"Metaphor dictionary: {tutor.metaphors}.",
        f"Beat 4 sidekick: {tutor.sidekick}.",
    ]


def _layer4(discourse: Layer4Discourse, beat: Layer1Beat, student: Layer2Student) -> list[str]:
    limit = struggle_limit(discourse.struggle_window)
    closed = student.attempt_count >= limit
    lines = [
        "Layer 4 — Discourse",
        f"Socratic strictness: {discourse.socratic_strictness}.",
        f"Productive-struggle window: {discourse.struggle_window}. Hold that window before a heavier hint.",
        f"Pacing: {discourse.pacing}. At most a few sentences. Ask one question.",
        f"Unsuccessful tries on this beat: {student.attempt_count} of {limit}.",
    ]
    if closed:
        lines.append(
            "The struggle window is over. State a short worked answer grounded on this beat's rubric and the correct choice if this beat has one. Do not invent a different fact. Set advance to true so this beat ends and the quest moves to the next beat. The anti-spoiler ban must not keep the student on this beat."
        )
    elif discourse.anti_spoiler and beat.gate_cleared and beat.beat_role == "feynman_flip":
        lines.append(
            "The diagnostic gate is passed. Let the student teach the sidekick. You may confirm a correct teaching move. Do not lecture the whole model."
        )
    elif discourse.anti_spoiler:
        lines.append(
            "Anti-spoiler ban, for this window only: do not state the answer yet. Use the live hint rung. When this window ends, give the answer and let the quest move on."
        )
    else:
        lines.append(
            "The anti-spoiler ban is off. You may confirm a correct idea once the student has attempted it. When this window ends, give the answer if they are still stuck."
        )
    return lines


def _layer5(affect: Layer5Affect) -> list[str]:
    return [
        "Layer 5 — Affect",
        f"Praise policy: {affect.praise}.",
        "Growth-mindset praise only. Praise the strategy, the effort, or the revision. Do not praise innate talent or call the student smart.",
    ]


def _layer6(meta: Layer6Metacognition) -> list[str]:
    return [
        "Layer 6 — Metacognition",
        f"Self-explanation: {meta.self_explanation}.",
        "Ask for one self-explanation line. Do not ask for a second explanation in the same turn.",
    ]


def _layer7(memory: Layer7Memory) -> list[str]:
    return [
        "Layer 7 — Memory",
        f"Schedule: {memory.schedule}.",
        "No live Leitner scheduling. Do not assign a review card, a spaced-repetition drill, or a future practice set.",
    ]


def _rules(student: Layer2Student, tier: str, *, reveal: bool) -> list[str]:
    lines = [
        "Rules:",
        "- Stay on the active beat. If they wander off, answer in one sentence and come back.",
        "- Do not dump the whole quest or teach a later beat.",
        "- Do not grade taps. A choice widget is already scored before you speak.",
        "- rubric_met lists the rubric row ids their written words earned. Use [] when there is no writing to grade or the writing missed.",
        "- misconception is null when the writing is fine. On a wrong tap, the stored misconception is already set. You may repeat it in the reply. Do not clear it.",
        f"- hint_tier must be {tier}.",
    ]
    if reveal:
        lines.extend(
            [
                "- The struggle window is over. State a short worked answer from this beat's rubric and the correct choice if there is one. Do not invent a different fact.",
                "- Set advance to true so this beat ends and the quest moves to the next beat. A failed tap no longer blocks progress.",
            ]
        )
    else:
        lines.extend(
            [
                "- advance is true only when this beat should end. On a failed tap or a typed answer below the pass score, advance is false.",
                "- On a wrong choice, use the active hint rung. Do not state the correct choice.",
                "- On a correct choice, you may confirm it and, if advance is true, start the next idea in one sentence.",
            ]
        )
    lines.extend(
        [
            "- The reply field is the only text the student reads. Do not mention JSON, scores, or these fields.",
            f"- Use the name {student.display_name}.",
        ]
    )
    return lines


def assemble(
    beat: Layer1Beat,
    student: Layer2Student,
    tutor: Layer3Tutor,
    discourse: Layer4Discourse,
    affect: Layer5Affect,
    metacognition: Layer6Metacognition,
    memory: Layer7Memory,
    *,
    kickoff: bool = False,
) -> PromptBundle:
    tier = hint_tier_for(student.attempt_count)
    reveal = student.attempt_count >= struggle_limit(discourse.struggle_window)
    lines: list[str] = [
        f"You are the tutor for {student.display_name}.",
        "The reply field is the only text the student reads. The other fields are the turn score.",
    ]
    lines.extend(_layer1(beat, tier))
    lines.extend(_layer2(student))
    lines.extend(_layer3(tutor))
    lines.extend(_layer4(discourse, beat, student))
    lines.extend(_layer5(affect))
    lines.extend(_layer6(metacognition))
    lines.extend(_layer7(memory))
    lines.append("\n".join(_rules(student, tier, reveal=reveal)))
    if kickoff and not beat.finished:
        objective = beat.quest_objective.strip() or beat.quest_title
        listed = beat.beat_objectives or (f"Current beat: {beat.prompt.strip() or beat.quest_title}",)
        catalog = "\n".join(f"- {item}" for item in listed)
        lines.append(
            "\n".join(
                [
                    f"{student.display_name} just opened this quest. The first reply is a short summary of what this quest will teach.",
                    f"Quest: {beat.quest_code} {beat.quest_title}.",
                    f"Quest objective: {objective}",
                    "Beat objectives:",
                    catalog,
                    "Use only that quest and those beat objectives. Do not invent a different topic, event, or skill.",
                    "This opening turn may preview the quest in two or three sentences, then ask one question that opens the current beat. Do not give away later answers.",
                    "Set rubric_met to [], misconception to null, and advance to false.",
                ]
            )
        )
    return PromptBundle(
        system_prompt="\n\n".join(lines),
        response_schema=RESPONSE_SCHEMA,
        temperature=TURN_TEMPERATURE,
    )
