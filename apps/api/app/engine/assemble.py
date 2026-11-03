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
        "diagram": {
            "description": (
                "A picture of the idea being taught, and only when a picture makes that idea clearer. "
                "kind triangle is drawn in the geometry course. "
                "kind graph and kind map are named for a later pass and are not drawn. "
                "Null when no picture should appear. No HTML, no URL, and no free-form drawing prompt."
            ),
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "description": "A triangle the app draws from three sides and three angles.",
                    "properties": {
                        "kind": {"type": "string", "enum": ["triangle"]},
                        "sides": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": "Short plain text. No HTML and no URL.",
                                    },
                                    "length": {"type": "number"},
                                },
                                "required": ["label", "length"],
                            },
                            "description": "Sides a, b, and c, opposite angles A, B, and C.",
                        },
                        "angles": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": "Short plain text. No HTML and no URL.",
                                    },
                                    "degrees": {"type": "number"},
                                },
                                "required": ["label", "degrees"],
                            },
                            "description": "Angles A, B, and C, in degrees. They sum to 180.",
                        },
                        "right_angle": {
                            "type": ["boolean", "null"],
                            "description": "True to mark the right angle. Null when there is none.",
                        },
                    },
                    "required": ["kind", "sides", "angles", "right_angle"],
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "description": "graph and map are named for a later pass. The server drops them.",
                    "properties": {
                        "kind": {"type": "string", "enum": ["graph", "map"]},
                    },
                    "required": ["kind"],
                },
            ],
        },
    },
    "required": ["reply", "rubric_met", "misconception", "hint_tier", "advance", "diagram"],
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

    "short" is one miss. "standard" and "minimum" are two. "long" is three.
    A numeric window is that many unsuccessful tries. The ban must end.
    """
    text = (window or "").strip().lower()
    if text.isdigit():
        return int(text)
    if text == "short":
        return 1
    if text in {"extended", "long"}:
        return 3
    return 2


def instructive_level(value: int | None) -> int:
    try:
        level = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 3
    if level < 1:
        return 1
    if level > 5:
        return 5
    return level


def _diagram_rule(beat: Layer1Beat) -> str:
    """A picture is optional, and this pass draws a geometry triangle only."""
    shared = (
        "A diagram is for the idea being taught, and only when a picture makes that idea clearer. "
        "No HTML, no image URL, and no free-form drawing prompt. The app draws the picture."
    )
    if (beat.course_code or "").strip().lower() == "geometry":
        return (
            shared
            + " In this geometry course, diagram may be a triangle: kind \"triangle\", three sides "
            "(a short plain-text label and a length), three angles (a short plain-text label and degrees "
            "that sum to 180), and right_angle true only when one angle is a right angle. "
            "kind graph and kind map are named for a later pass and are not drawn. "
            "Set diagram to null when a picture would not help."
        )
    return (
        shared
        + " A triangle is only inside the geometry course. This course gets no picture. Set diagram to null."
    )


def _course_scope_rule(discourse: Layer4Discourse, beat: Layer1Beat) -> str | None:
    """Name the current course when the layer 4 switch is on.

    Depth inside that course, unit, and quest stays allowed. A different
    subject gets a short acknowledgment, then the turn returns. None leaves
    today's prompt unchanged, so a tangent can be followed.
    """
    if not discourse.stay_on_course:
        return None
    course = beat.course_title.strip() or "this course"
    unit = beat.unit_title.strip() or "this unit"
    quest = beat.quest_title.strip() or "this quest"
    return (
        f"Course scope: stay on {course}. "
        f"Go as deep as the student needs on {course}, unit {unit}, and quest {quest}, "
        "including closely related ideas that serve this learning goal. "
        "Do not follow a turn onto a different subject. "
        f"A short acknowledgment, then back to {course}."
    )


def _classic(discourse: Layer4Discourse) -> bool:
    """Level 3 with both default switches is today's teach-then-ask prompt."""
    return (
        instructive_level(discourse.instructive) == 3
        and discourse.one_question
        and discourse.use_interests
    )


def _question_rule(one_question: bool) -> str:
    if one_question:
        return "One question per turn, and it comes last. Do not ask a second question."
    return "A second question is allowed in the same turn when it helps the idea."


def _picture(use_interests: bool) -> str:
    if use_interests:
        return "a concrete picture from their interests"
    return "a concrete picture from the subject, not from their hobbies"


def _opening_sentence(discourse: Layer4Discourse) -> str:
    """Reply length for this instructive setting."""
    level = instructive_level(discourse.instructive)
    picture = _picture(discourse.use_interests)
    if level <= 1:
        return "One short question. Almost no explanation until they try."
    if level == 2:
        return "Ask one short question. At most one sentence of setup. Do not teach a lesson yet."
    if level == 3:
        return (
            f"A short explanation, then one question. A few sentences the student could retell: "
            f"the fact, {picture}, and why it matters."
        )
    if level == 4:
        return (
            f"Teach the fact and why it matters for this goal, using {picture}, then one question. "
            "A miss gets this longer explanation right away."
        )
    return (
        f"A fuller lesson first: the fact, {picture}, why it matters for this goal, then one question. "
        "Stuck students get the longer explanation on the first miss."
    )


def _miss_sentence(discourse: Layer4Discourse, attempt_count: int) -> str | None:
    """How soon a miss gets a real explanation. None means keep the opening shape."""
    level = instructive_level(discourse.instructive)
    question = _question_rule(discourse.one_question)
    picture = _picture(discourse.use_interests)
    if level <= 1:
        if attempt_count <= 0:
            return None
        return (
            "They have tried. Still almost no explanation. Ask one short question about what they tried. "
            "A real explanation waits until the struggle window. "
            + question
        )
    if level == 2:
        if attempt_count < 2:
            if attempt_count <= 0:
                return None
            return (
                "They missed once. Ask one short question. Do not give a real explanation yet. "
                + question
            )
        return (
            "They have missed twice. Give a short explanation of the idea, then stop before the passing answer. "
            + question
        )
    if level == 3:
        if attempt_count <= 0:
            return None
        return (
            "The student missed. Explain what they tried, what the idea actually is, and the next step. "
            "Do not give the worked answer yet. Do not teach the next move. "
            + question
        )
    if level == 4:
        if attempt_count <= 0:
            return None
        return (
            f"The student missed. Give the longer explanation now: the fact, {picture}, and why it matters, "
            "then the next step. Do not wait for another miss. Do not state the passing answer yet. "
            "Do not teach the next move. "
            + question
        )
    if attempt_count <= 0:
        return None
    return (
        f"The student is stuck. Give the longer explanation on this miss: the fact, {picture}, "
        "why it matters, and what they tried. Do not wait. Do not state the passing answer yet. "
        "Do not teach the next move. "
        + question
    )


_PERSONA_LINE = {
    "curious-co-explorer": "Speak as a curious co-explorer. Wonder alongside the student and explore the idea with them.",
    "tactical-coach": "Speak as a tactical coach. Be direct, concrete, and focused on the next move.",
    "debate-moderator": "Speak as a debate moderator. Ask for the chain of causes before the verdict.",
    "patient-explainer": "Speak as a patient explainer. Go slowly and make sure the last sentence landed.",
}

_LEXICON_LINE = {
    "early-concrete": "Write with an early concrete voice: short words and things they can point at.",
    "middle-grade-vivid": "Write with a middle-grade vivid voice: clear sentences and a picture they can see.",
    "precise-visual": "Write with a precise visual voice: shapes, positions, and exact relations.",
    "analytical-high-school": "Write with an analytical high-school voice. The student gives a multi-step chain.",
}

_METAPHOR_LINE = {
    "playground-sports": "When a picture helps, draw it from playground and sports.",
    "buildings-machines": "When a picture helps, draw it from buildings and machines.",
    "policy-cause": "When a picture helps, draw it from policy and cause-and-effect.",
    "none": "Use plain language only. Do not add a metaphor.",
}

_SIDEKICK_LINE = {
    "bumbling-partner": "On teach-back only, the sidekick is a bumbling partner who gets the idea wrong.",
    "rookie-picture": "On teach-back only, the sidekick is a rookie who trusts a picture.",
    "pundit": "On teach-back only, the sidekick is a pundit who skips the chain.",
    "off": "Teach-back sidekick is off. Do not invent a partner. The student explains the idea.",
}


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


def _layer1(
    beat: Layer1Beat,
    tier: str,
    *,
    reveal: bool,
    hold_widget: bool = False,
    discourse: Layer4Discourse | None = None,
) -> list[str]:
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
        if discourse is None or _classic(discourse):
            lines.append(
                "Engage teaches, then asks. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last. No choice box."
            )
        else:
            lines.append(f"Engage. {_opening_sentence(discourse)} {_question_rule(discourse.one_question)} No choice box.")
    elif beat.beat_role == "name":
        if discourse is None or _classic(discourse):
            lines.append(
                "Name teaches, then asks. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last. Then set advance to true. Do not start the next move."
            )
        else:
            lines.append(
                f"Name. {_opening_sentence(discourse)} {_question_rule(discourse.one_question)} "
                "Then set advance to true. Do not start the next move."
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


def _layer2(student: Layer2Student, *, use_interests: bool = True) -> list[str]:
    interests = ", ".join(student.interests) if student.interests else "none listed"
    if use_interests:
        interest_line = (
            f"Interests to turn into one concrete picture inside the explanation: {interests}. Do not list them back."
        )
    else:
        interest_line = (
            f"Recorded interests: {interests}. Examples stay on the subject. Do not use those hobbies as the picture."
        )
    return [
        "Layer 2 — Student",
        f"The student's name is {student.display_name}. Use it.",
        f"Age band: {student.age_band}.",
        f"Write at this reading level: {student.reading_level or 'unspecified'}. Do not announce the level.",
        f"Modality to use when you choose a picture: {student.modality or 'unspecified'}. Do not label it.",
        interest_line,
        f"Live attempt count on this move: {student.attempt_count}.",
        f"ZPD: {student.zpd}.",
    ]


def _layer3(tutor: Layer3Tutor) -> list[str]:
    persona = _PERSONA_LINE.get(tutor.persona)
    lexicon = _LEXICON_LINE.get(tutor.lexicon)
    metaphors = _METAPHOR_LINE.get(tutor.metaphors)
    sidekick = _SIDEKICK_LINE.get(tutor.sidekick)
    if persona is None and lexicon is None and metaphors is None and sidekick is None:
        return [
            "Layer 3 — Tutor agent",
            "Use this voice inside the explanation. Do not name the persona or dump these settings as labels.",
            f"Persona to speak as: {tutor.persona}.",
            f"Lexicon to write with: {tutor.lexicon}.",
            f"Metaphors to draw a picture from, when they fit the idea: {tutor.metaphors}.",
            f"Teach-back sidekick: {tutor.sidekick}.",
        ]
    return [
        "Layer 3 — Tutor agent",
        "Use this voice inside the explanation. Do not name the persona or dump these settings as labels.",
        persona or f"Persona to speak as: {tutor.persona}.",
        lexicon or f"Lexicon to write with: {tutor.lexicon}.",
        metaphors or f"Metaphors to draw a picture from, when they fit the idea: {tutor.metaphors}.",
        sidekick or f"Teach-back sidekick: {tutor.sidekick}.",
    ]


def _pacing_lines(
    discourse: Layer4Discourse,
    beat: Layer1Beat,
    *,
    missed: bool,
    attempt_count: int = 0,
) -> list[str]:
    if _classic(discourse):
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
    lines = [
        f"Pacing: {discourse.pacing}.",
        _opening_sentence(discourse),
        _question_rule(discourse.one_question),
        "Do not say hint to the student.",
    ]
    if missed:
        sentence = _miss_sentence(discourse, attempt_count)
        if sentence:
            lines.append(sentence)
    elif beat.beat_role == "name":
        lines.append(f"This Name turn follows that length. {_question_rule(discourse.one_question)} Do not teach the next move.")
    elif beat.beat_role == "engage":
        lines.append(
            f"This Engage turn follows that length. {_question_rule(discourse.one_question)} Do not ask them to pick an answer."
        )
    return lines


def _window_sentence(window: str) -> str:
    known = {
        "short": "short (1 miss). Hold that window before stating the passing answer.",
        "standard": "standard (2 misses). Hold that window before stating the passing answer.",
        "long": "long (3 misses). Hold that window before stating the passing answer.",
    }
    text = (window or "").strip().lower()
    if text in known:
        return f"Productive-struggle window: {known[text]}"
    return (
        f"Productive-struggle window: {window}. Hold that window before stating the passing answer."
    )


def _layer4(
    discourse: Layer4Discourse,
    beat: Layer1Beat,
    student: Layer2Student,
    tutor: Layer3Tutor | None = None,
    *,
    reveal: bool,
) -> list[str]:
    limit = struggle_limit(discourse.struggle_window)
    closed = reveal
    missed = student.attempt_count > 0 and not closed
    lines = [
        "Layer 4 — Discourse",
        f"Socratic strictness: {discourse.socratic_strictness}.",
        _window_sentence(discourse.struggle_window),
        *_pacing_lines(discourse, beat, missed=missed, attempt_count=student.attempt_count),
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
        if _classic(discourse):
            lines.append(
                "This turn teaches the idea before the question. Do not give a later move's answer."
            )
        else:
            lines.append(f"{_opening_sentence(discourse)} Do not give a later move's answer.")
    elif discourse.anti_spoiler and beat.beat_role == "teach_back":
        if tutor is not None and tutor.sidekick.strip().lower() in {"off", "none"}:
            lines.append(
                "Sidekick is off. The student explains the idea in their own words. Do not invent a partner, and do not state the answer before they try."
            )
        else:
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
    scope = _course_scope_rule(discourse, beat)
    if scope:
        lines.append(scope)
    return lines


def _layer5(affect: Layer5Affect) -> list[str]:
    lines = [
        "Layer 5 — Affect",
        f"Praise policy: {affect.praise}.",
    ]
    if affect.praise == "growth-mindset-only":
        lines.append(
            "Growth-mindset praise only. Praise the strategy, the effort, or the revision. Do not praise innate talent or call the student smart."
        )
    else:
        lines.append(
            "Growth-mindset praise is off. You may praise a correct result as well as the effort. Do not infer a mood, and do not schedule a memory."
        )
    return lines


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


def _rules(
    student: Layer2Student,
    beat: Layer1Beat,
    tier: str,
    discourse: Layer4Discourse,
    *,
    reveal: bool,
    missed: bool,
) -> list[str]:
    classic = _classic(discourse)
    lines = [
        "Rules:",
        "- Stay on the active move. If they wander off, answer in one sentence and come back.",
        "- Do not dump the whole quest or teach a later move.",
    ]
    scope = _course_scope_rule(discourse, beat)
    if scope:
        lines.append(f"- {scope}")
    if classic:
        lines.append("- Teach, then ask. One question per turn, and it comes last. Do not ask a second question.")
    else:
        lines.append(f"- {_opening_sentence(discourse)}")
        lines.append(f"- {_question_rule(discourse.one_question)}")
    lines.extend(
        [
            "- Do not say hint to the student.",
            "- Do not grade taps. A choice widget is already scored before you speak.",
            "- rubric_met lists the rubric row ids their written words earned. On Try or Show, include success-criterion ids they earned. Use [] when there is no writing to grade or the writing missed.",
            "- misconception is null when the writing is fine. On a wrong tap, the stored misconception is already set. You may repeat it in the reply. Do not clear it.",
            f"- hint_tier must be {tier}. The student never sees this field.",
        ]
    )
    if beat.beat_role in {"engage", "name"} and not reveal:
        if classic:
            lines.append(
                "- Teach, then ask. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last."
            )
        else:
            lines.append(f"- {_opening_sentence(discourse)} {_question_rule(discourse.one_question)}")
    if beat.beat_role == "name" and not reveal:
        lines.append("- After that question, set advance to true. Do not teach the next move.")
    if missed:
        if classic:
            lines.append(
                "- The student missed. Explain what they tried, what the idea actually is, and the next step. Do not give the worked answer yet. Do not ask a second question. Do not teach the next move."
            )
        else:
            sentence = _miss_sentence(discourse, student.attempt_count)
            if sentence:
                lines.append(f"- {sentence}")
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
            f"- {_diagram_rule(beat)}",
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
    grade_writing: bool = False,
    widget_offer: str | None = None,
    withhold_answer: bool = False,
) -> PromptBundle:
    tier = hint_tier_for(student.attempt_count)
    reveal = (
        student.attempt_count >= struggle_limit(discourse.struggle_window)
        and not withhold_answer
    )
    missed = student.attempt_count > 0 and not reveal
    lines: list[str] = [
        f"You are the tutor for {student.display_name}.",
        "The reply field is the only text the student reads. The other fields are the turn score.",
    ]
    lines.extend(_layer1(beat, tier, reveal=reveal, hold_widget=hold_widget, discourse=discourse))
    lines.extend(_layer2(student, use_interests=discourse.use_interests))
    lines.extend(_layer3(tutor))
    lines.extend(_layer4(discourse, beat, student, tutor, reveal=reveal))
    lines.extend(_layer5(affect))
    lines.extend(_layer6(metacognition))
    lines.extend(_layer7(memory))
    lines.append("\n".join(_rules(student, beat, tier, discourse, reveal=reveal, missed=missed)))
    if kickoff and not beat.finished:
        goal = beat.learning_goal.strip() or beat.quest_objective.strip() or beat.quest_title
        done = _criterion_line(beat)
        idea = beat.opening_idea.strip() or goal
        if _classic(discourse):
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
        else:
            lines.append(
                "\n".join(
                    [
                        f"{student.display_name} just opened this quest. The first reply follows the instructive setting.",
                        f"Quest: {beat.quest_code} {beat.quest_title}.",
                        f"Learning goal: {goal}",
                        f"Done looks like: {done}",
                        f"First idea to teach: {idea}",
                        _opening_sentence(discourse),
                        _question_rule(discourse.one_question),
                        "Use only that goal and that idea. Do not invent a different topic, event, or skill.",
                        "Do not preview later moves or give away later answers.",
                        "Do not ask them to pick an answer. The choice widget is not on screen.",
                        "Set rubric_met to [], misconception to null, and advance to false.",
                    ]
                )
            )
    elif hold_widget and not beat.finished:
        if grade_writing:
            closing = (
                "They have replied in their own words. Mark rubric_met from those words. "
                "Do not advance. Do not state the answer."
            )
        else:
            closing = "Set rubric_met to [], misconception to null, and advance to false."
        if _classic(discourse):
            teach = "Explain the idea, then ask one question. Do not list choices or ask them to pick."
        else:
            teach = "\n".join(
                [
                    _opening_sentence(discourse),
                    _question_rule(discourse.one_question),
                    "Do not list choices or ask them to pick.",
                ]
            )
        lines.append(
            "\n".join(
                [
                    "The choice widget is not on screen yet. This reply teaches the move.",
                    teach,
                    "The choices stay off this turn. They appear later, only to check an idea the student has explained in their own words, or to give one structured try before the answer if they are stuck.",
                    closing,
                ]
            )
        )
    elif widget_offer == "unstick" and not beat.finished:
        lines.append(
            "\n".join(
                [
                    "The choices are one message in the chat. They are stuck, and the struggle window is about to open.",
                    "This is one structured try before you state the answer. Invite them to choose. Do not name the correct choice.",
                    "Set advance to false until they submit.",
                ]
            )
        )
    elif widget_offer == "check" and not beat.finished:
        lines.append(
            "\n".join(
                [
                    "The choices are one message in the chat, to check the idea they explained in their own words.",
                    "Invite them to choose. Do not teach a new idea. Do not state the correct choice.",
                    "Set advance to false until they submit.",
                ]
            )
        )
    return PromptBundle(
        system_prompt="\n\n".join(lines),
        response_schema=RESPONSE_SCHEMA,
        temperature=TURN_TEMPERATURE,
    )
