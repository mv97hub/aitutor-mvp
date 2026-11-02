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
    "engage": "engage",
    "try": "try",
    "name": "name",
    "show": "show",
    "teach_back": "teach-back",
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


def _criterion_line(beat: Layer1Beat) -> str:
    if not beat.success_criterion:
        return _rubric_line(beat)
    return " ".join(
        f"{row.id} (weight {row.weight}): {row.text}" for row in beat.success_criterion
    )


def _answer_text(widget: WidgetTask) -> str:
    answer = widget.answer
    if isinstance(answer, tuple):
        return ", ".join(answer)
    return answer


def _widget_lines(widget: WidgetTask, *, reveal: bool) -> list[str]:
    choices = []
    for choice in widget.choices:
        note = f" misconception: {choice.misconception}" if choice.misconception else ""
        choices.append(f"{choice.id}. {choice.text}{note}")
    lines = [
        f"Choice widget ({widget.type}), graded by the server before you speak. Do not grade the taps.",
        f"Widget prompt: {widget.prompt}",
        f"Choices: {' | '.join(choices)}",
    ]
    if reveal:
        lines.append(f"Correct answer, for you only: {_answer_text(widget)}.")
    else:
        lines.append(
            "The correct widget answer stays hidden until the struggle window opens. Do not name it."
        )
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


def _layer1(beat: Layer1Beat, tier: str, *, reveal: bool, hold_widget: bool = False) -> list[str]:
    role = _ROLE_LABEL.get(beat.beat_role, beat.beat_role.replace("_", " "))
    goal = beat.learning_goal.strip() or beat.quest_objective.strip() or beat.quest_title
    lines = [
        "Layer 1 — Active move",
        f"Course: {beat.course_title}.",
        f"Unit: {beat.unit_title}.",
        f"Unit continuity: {beat.continuity.strip() or 'None.'}",
        f"Quest {beat.quest_code}: {beat.quest_title}.",
        f"Learning goal: {goal}",
        f"Success criterion: {_criterion_line(beat)}",
        f"Pass score: {beat.pass_score}. The quest finishes when those rows are met. After the struggle window on Show, explain why the answer fits and finish the quest.",
    ]
    if beat.finished:
        lines.append(
            "This quest is finished. Congratulate the student in one or two sentences. Do not start another quest. Set advance to false, rubric_met to [], and misconception to null."
        )
        return lines
    lines.extend(
        [
            f"Move {beat.beat_position} of {beat.beat_count}: {role}.",
            f"Bloom level: {beat.bloom_level}. Cognitive load: {beat.cognitive_load}.",
            _move_task(beat, hold_widget=hold_widget),
            f"This move's rubric rows: {_rubric_line(beat)}",
            f"Misconception traps: {_traps_line(beat)}",
            "Hint ladder: "
            f"rung 1 nudge: {beat.hint_ladder.nudge or 'Ask them to try once more.'} "
            f"Rung 2 analogy: {beat.hint_ladder.analogy or 'Offer a picture, not the answer.'} "
            f"Rung 3 scaffold: {beat.hint_ladder.scaffold or 'Give a sentence starter.'}",
            f"Live hint tier for this turn: {tier}. Use this rung only: {_hint_text(beat.hint_ladder, tier) or 'Ask them to try once more.'}",
            f"Show already cleared: {'yes' if beat.gate_cleared else 'no'}.",
            "Mark the criterion: rubric_met lists ids from this move's rubric and, on Try or Show, any success-criterion ids their words earned.",
            "Advance when this move is done. If the success criterion is already met on Try or Show, the quest ends and later moves are skipped.",
        ]
    )
    if beat.beat_role == "engage":
        lines.append(
            "Engage teaches, then asks. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last. No choice box."
        )
    elif beat.beat_role == "name":
        lines.append(
            "Name teaches, then asks. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last. Then set advance to true. Do not start the next move."
        )
    elif beat.beat_role == "teach_back":
        lines.append(
            "Teach-back: the student corrects the sidekick. You may confirm a correct correction. Do not lecture the whole model."
        )
    if beat.widget is not None and beat.beat_role in {"try", "show"} and not hold_widget:
        lines.extend(_widget_lines(beat.widget, reveal=reveal))
    return lines


def _move_task(beat: Layer1Beat, *, hold_widget: bool) -> str:
    if beat.beat_role == "engage":
        return (
            "Expand this idea in words a student could retell. Do not turn it into a quiz stem. "
            f"Idea: {beat.prompt}"
        )
    if beat.beat_role == "name":
        return (
            "Expand this idea, then ask one question about it. Do not turn it into a quiz stem. "
            f"Idea: {beat.prompt}"
        )
    if hold_widget:
        return (
            "The choice widget is not on screen. Teach this move before the check. "
            "Do not ask this move's choice question."
        )
    return f"Stay on this move. Task, in your own words if you need to: {beat.prompt}"


def _layer2(student: Layer2Student) -> list[str]:
    interests = ", ".join(student.interests) if student.interests else "none listed"
    return [
        "Layer 2 — Student",
        f"The student's name is {student.display_name}. Use it.",
        f"Age band: {student.age_band}.",
        f"Write at this reading level: {student.reading_level or 'unspecified'}. Do not announce the level.",
        f"Modality to use when you choose a picture: {student.modality or 'unspecified'}. Do not label it.",
        f"Interests to turn into one concrete picture inside the explanation: {interests}. Do not list them back.",
        f"Live attempt count on this move: {student.attempt_count}.",
        f"ZPD: {student.zpd}.",
    ]


def _layer3(tutor: Layer3Tutor) -> list[str]:
    return [
        "Layer 3 — Tutor agent",
        "Use this voice inside the explanation. Do not name the persona or dump these settings as labels.",
        f"Persona to speak as: {tutor.persona}.",
        f"Lexicon to write with: {tutor.lexicon}.",
        f"Metaphors to draw a picture from, when they fit the idea: {tutor.metaphors}.",
        f"Teach-back sidekick: {tutor.sidekick}.",
    ]


def _pacing_lines(discourse: Layer4Discourse, beat: Layer1Beat, *, missed: bool) -> list[str]:
    lines = [
        f"Pacing: {discourse.pacing}.",
        "Teach, then ask. One question per turn, and it comes last.",
        "On Engage and Name, use a few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this quest's goal.",
        "Do not say hint to the student.",
    ]
    if missed:
        lines.append(
            "The student missed. Explain what they tried, what the idea actually is, and the next step. Do not give the worked answer yet. Do not ask a second question. Do not teach the next move."
        )
    elif beat.beat_role == "name":
        lines.append(
            "This Name turn teaches the idea, then asks one question. Do not teach the next move."
        )
    elif beat.beat_role == "engage":
        lines.append(
            "This Engage turn teaches the idea, then asks one question. Do not ask them to pick an answer."
        )
    return lines


def _layer4(discourse: Layer4Discourse, beat: Layer1Beat, student: Layer2Student) -> list[str]:
    limit = struggle_limit(discourse.struggle_window)
    closed = student.attempt_count >= limit
    missed = student.attempt_count > 0 and not closed
    lines = [
        "Layer 4 — Discourse",
        f"Socratic strictness: {discourse.socratic_strictness}.",
        f"Productive-struggle window: {discourse.struggle_window}. Hold that window before stating the passing answer.",
        *_pacing_lines(discourse, beat, missed=missed),
        f"Unsuccessful tries on this move: {student.attempt_count} of {limit}.",
    ]
    if closed and beat.beat_role == "show":
        lines.append(
            "The struggle window is over. Explain why the worked answer fits the success criterion. Do not invent a different fact. Do not ask another question. Set advance to true. That finishes the quest."
        )
    elif closed:
        lines.append(
            "The struggle window is over. Explain why the worked answer fits this move's criterion, including the correct choice if this move has one. Do not invent a different fact. Do not ask another question. Do not teach the next move. Set advance to true so this move ends."
        )
    elif beat.beat_role in {"engage", "name"}:
        lines.append(
            "This turn teaches the idea before the question. Do not give a later move's answer."
        )
    elif discourse.anti_spoiler and beat.beat_role == "teach_back":
        lines.append(
            "The student is correcting the sidekick. You may confirm a correct correction. Do not lecture the whole model, and do not state the answer before they try."
        )
    elif discourse.anti_spoiler:
        lines.append(
            "Anti-spoiler ban, for this window only: teaching the idea is allowed, stating the answer that passes the move is not. When this window ends, explain why the answer fits and let the move end."
        )
    else:
        lines.append(
            "The anti-spoiler ban is off. You may confirm a correct idea once the student has attempted it. When this window ends, explain why the answer fits if they are still stuck."
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


def _rules(student: Layer2Student, beat: Layer1Beat, tier: str, *, reveal: bool, missed: bool) -> list[str]:
    lines = [
        "Rules:",
        "- Stay on the active move. If they wander off, answer in one sentence and come back.",
        "- Do not dump the whole quest or teach a later move.",
        "- Teach, then ask. One question per turn, and it comes last. Do not ask a second question.",
        "- Do not say hint to the student.",
        "- Do not grade taps. A choice widget is already scored before you speak.",
        "- rubric_met lists the rubric row ids their written words earned. On Try or Show, include success-criterion ids they earned. Use [] when there is no writing to grade or the writing missed.",
        "- misconception is null when the writing is fine. On a wrong tap, the stored misconception is already set. You may repeat it in the reply. Do not clear it.",
        f"- hint_tier must be {tier}. The student never sees this field.",
    ]
    if beat.beat_role in {"engage", "name"} and not reveal:
        lines.append(
            "- Teach, then ask. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last."
        )
    if beat.beat_role == "name" and not reveal:
        lines.append("- After that question, set advance to true. Do not teach the next move.")
    if missed:
        lines.append(
            "- The student missed. Explain what they tried, what the idea actually is, and the next step. Do not give the worked answer yet. Do not ask a second question. Do not teach the next move."
        )
    if reveal:
        if beat.beat_role == "show":
            lines.append(
                "- The struggle window is over. Explain why the worked answer fits the success criterion. Do not invent a different fact. Set advance to true. That finishes the quest."
            )
        else:
            lines.append(
                "- The struggle window is over. Explain why the worked answer fits this move's criterion, including the correct choice if there is one. Do not invent a different fact. Do not teach the next move."
            )
            lines.append(
                "- Set advance to true so this move ends. A failed tap no longer blocks progress."
            )
    else:
        lines.extend(
            [
                "- advance is true only when this move should end. On a failed tap or a typed answer below the pass score, advance is false, unless this move is Name.",
                "- On a wrong choice, explain what they tried and what the idea is. Do not state the correct choice. Do not say hint.",
                "- On a correct choice, you may confirm it. Do not teach the next move.",
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
    hold_widget: bool = False,
) -> PromptBundle:
    tier = hint_tier_for(student.attempt_count)
    reveal = student.attempt_count >= struggle_limit(discourse.struggle_window)
    missed = student.attempt_count > 0 and not reveal
    lines: list[str] = [
        f"You are the tutor for {student.display_name}.",
        "The reply field is the only text the student reads. The other fields are the turn score.",
    ]
    lines.extend(_layer1(beat, tier, reveal=reveal, hold_widget=hold_widget))
    lines.extend(_layer2(student))
    lines.extend(_layer3(tutor))
    lines.extend(_layer4(discourse, beat, student))
    lines.extend(_layer5(affect))
    lines.extend(_layer6(metacognition))
    lines.extend(_layer7(memory))
    lines.append("\n".join(_rules(student, beat, tier, reveal=reveal, missed=missed)))
    if kickoff and not beat.finished:
        goal = beat.learning_goal.strip() or beat.quest_objective.strip() or beat.quest_title
        done = _criterion_line(beat)
        idea = beat.opening_idea.strip() or goal
        lines.append(
            "\n".join(
                [
                    f"{student.display_name} just opened this quest. The first reply states the learning goal, what finished work looks like, and a short teaching of the first idea.",
                    f"Quest: {beat.quest_code} {beat.quest_title}.",
                    f"Learning goal: {goal}",
                    f"Done looks like: {done}",
                    f"First idea to teach: {idea}",
                    "Teach that idea in a few sentences the student could retell. Use a concrete picture from their interests, and say why it matters for this goal.",
                    "Use only that goal and that idea. Do not invent a different topic, event, or skill.",
                    "Do not preview later moves or give away later answers.",
                    "Do not ask them to pick an answer. The choice widget is not on screen.",
                    "One question may come last, about the idea you just taught, not about a list of choices.",
                    "Set rubric_met to [], misconception to null, and advance to false.",
                ]
            )
        )
    elif hold_widget and not beat.finished:
        lines.append(
            "\n".join(
                [
                    "The choice widget is not on screen yet. This reply teaches the move.",
                    "Explain the idea, then ask one question. Do not list choices or ask them to pick.",
                    "The choice box appears after this reply.",
                    "Set rubric_met to [], misconception to null, and advance to false.",
                ]
            )
        )
    return PromptBundle(
        system_prompt="\n\n".join(lines),
        response_schema=RESPONSE_SCHEMA,
        temperature=TURN_TEMPERATURE,
    )
