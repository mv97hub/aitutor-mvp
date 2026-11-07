"""Seven-layer prompt for one knowledge-component move.

The bundle is the system prompt, the response schema, and the temperature.
The model writes the reply. The app owns the type, the edges, and the score.
The quest prompt builder is a different module and is not imported here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.choices import METAPHORS, PERSONAS, SIDEKICKS, VOICES
from app.models import KcGoal, KcNode, Student, TutorProfile

TEMPERATURE = 0.4
HINTS = ("nudge", "analogy", "scaffold", "reveal")
DECISIONS = ("stay", "advance", "complete", "redirect")
AFFECTS = ("engaged", "stuck", "guessing", "frustrated")
CONFIDENCE = ("low", "ok", "high")

RECIPE_NAME = {
    "factual": "retrieval",
    "procedural": "worked-example",
    "conceptual": "contrasting-cases",
    "causal": "decision-point",
    "synthesis": "rookie-correction",
}

_EXPLAIN = {
    1: "Open on the question. Almost no explanation first.",
    2: "Give one short line, then the question.",
    3: "Name the goal, then ask.",
    4: "Explain the idea, then ask one question.",
    5: "Teach a little more first, then ask one question.",
}

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": "The only text the child sees. Include the unit close and the course outro when this turn ends the unit.",
        },
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "rubric_met": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ids of the evidence points this move listed. Empty when the move is not checked.",
        },
        "misconception": {
            "type": ["string", "null"],
            "description": "A stored wrong move, or null.",
        },
        "hint_tier": {"type": "string", "enum": list(HINTS)},
        "help_requested": {"type": "boolean"},
        "off_course": {"type": "boolean"},
        "affect": {"type": "string", "enum": list(AFFECTS)},
        "confidence": {"type": "string", "enum": list(CONFIDENCE)},
    },
    "required": [
        "reply",
        "decision",
        "rubric_met",
        "misconception",
        "hint_tier",
        "help_requested",
        "off_course",
        "affect",
        "confidence",
    ],
}


@dataclass(frozen=True)
class Move:
    key: str
    name: str
    evidence: tuple[str, ...]
    choice: bool


def recipe_name(kc_type: str | None) -> str:
    return RECIPE_NAME.get(kc_type or "", "unset")


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


def self_explanation_on(profile: TutorProfile) -> bool:
    value = getattr(profile, "self_explanation", True)
    return True if value is None else bool(value)


def stored_enrichment(profile: TutorProfile) -> str:
    value = str(getattr(profile, "enrichment", "") or "on_request")
    if value not in {"direct", "on_request", "offer"}:
        return "on_request"
    return value


def effective_window_name(profile: TutorProfile, goal: KcGoal | None) -> str:
    if goal is not None and goal.kind == "time_boxed":
        return "minimum"
    stored = (profile.struggle_window or "standard").strip().lower()
    if stored in {"short", "minimum"}:
        return "minimum"
    if stored in {"long", "wide"}:
        return "wide"
    return "standard"


def struggle_tries(name: str) -> int:
    if name in {"short", "minimum"}:
        return 1
    if name in {"long", "wide"}:
        return 3
    return 2


def effective_enrichment(profile: TutorProfile, goal: KcGoal | None) -> str:
    if goal is not None and goal.kind == "time_boxed":
        return "direct"
    return stored_enrichment(profile)


def is_fragment(answer: str, fact: str) -> bool:
    """A short retrieval against a longer fact. Not a pass rule."""
    fact_words = [word for word in (fact or "").split() if word.strip()]
    answer_words = [word for word in (answer or "").split() if word.strip()]
    if len(fact_words) <= 3:
        return False
    return 0 < len(answer_words) <= 3


def moves_for(
    node: KcNode,
    profile: TutorProfile,
    goal: KcGoal | None,
    *,
    fragment: bool = False,
) -> list[Move]:
    """The move sequence for this type. Intro and the closes are not steps."""
    kind = node.kc_type or ""
    fields = node.type_fields or {}
    explain = self_explanation_on(profile)
    sequence: list[Move] = []
    if kind == "factual":
        sequence.append(Move("retrieve", "Retrieve", ("fact",), False))
        if explain and fragment:
            sequence.append(Move("restate", "Restate", ("restatement",), False))
    elif kind == "procedural":
        sequence.append(Move("worked", "Worked example", (), False))
        sequence.append(Move("faded", "Faded step", ("blanked_step",), False))
        sequence.append(Move("solo", "Solo", ("solo_check",), False))
        if explain:
            sequence.append(Move("why_order", "Why this order", ("why_order",), False))
    elif kind == "conceptual":
        sequence.append(Move("predict", "Predict", (), True))
        sequence.append(Move("contrast", "Contrast", (), False))
        sequence.append(Move("rule", "State the rule", ("rule",), False))
        if str(fields.get("transfer_case") or "").strip():
            sequence.append(Move("transfer", "Transfer", ("transfer",), False))
    elif kind == "causal":
        sequence.append(Move("stake", "What is at stake", (), False))
        sequence.append(Move("mark", "Mark the claim", ("mark",), True))
        sequence.append(Move("defend", "Defend the chain", ("causal_chain",), False))
        if explain and str(fields.get("counterfactual") or "").strip():
            sequence.append(Move("counterfactual", "Counterfactual", ("counterfactual",), False))
    elif kind == "synthesis":
        sequence.append(Move("faulty", "Faulty plan", (), False))
        sequence.append(Move("correct", "Correct the plan", ("core_truth",), False))
        sequence.append(Move("which_job", "Which job", ("which_job",), False))
    else:
        sequence.append(Move("this", "This step", (), False))
    if goal is not None and goal.kind == "curiosity":
        sequence.append(Move("extra_why", "Extra why", (), False))
    return sequence


def step_labels(kc_type: str | None) -> list[str]:
    """Default names for a type, before optional fields and a fragment are known."""
    node = KcNode(code="label", title="Label", kc_type=kc_type)
    profile = TutorProfile(
        id="default",
        instructive=3,
        persona="curious-co-explorer",
        lexicon="middle-grade-vivid",
        metaphors="playground-sports",
        sidekick="bumbling-partner",
        self_explanation=True,
        enrichment="on_request",
        misconception_policy="retry_once",
    )
    return [move.name for move in moves_for(node, profile, None)]


def asks_why(profile: TutorProfile, move: Move) -> bool:
    if not self_explanation_on(profile):
        return False
    return move.key in {"restate", "why_order", "counterfactual", "extra_why", "which_job"}


def _field(node: KcNode, key: str) -> str:
    value = (node.type_fields or {}).get(key)
    if isinstance(value, list):
        return " ".join(str(item) for item in value if str(item).strip())
    return str(value or "").strip()


def move_material(node: KcNode, move: Move) -> str:
    fields = node.type_fields or {}
    if move.key == "retrieve":
        return str(fields.get("retrieval_question") or "What is the fact?")
    if move.key == "restate":
        return "Ask for the fact in a full sentence. The earlier answer was only a fragment."
    if move.key == "worked":
        steps = [str(item) for item in (fields.get("steps") or [])]
        shown = " ".join(f"{index + 1}. {text}" for index, text in enumerate(steps))
        return f"Worked steps: {shown}".strip()
    if move.key == "faded":
        steps = [str(item) for item in (fields.get("steps") or [])]
        blank = int(fields.get("blanked_step") or 0)
        shown = []
        for index, text in enumerate(steps):
            shown.append(f"{index + 1}. ___" if index == blank else f"{index + 1}. {text}")
        return "Faded steps: " + " ".join(shown)
    if move.key == "solo":
        return str(fields.get("solo_problem") or "Solve it on your own.")
    if move.key == "why_order":
        return "Ask why the steps go in this order."
    if move.key == "predict":
        return (
            f"Case one: {fields.get('case_a') or ''} "
            f"Case two: {fields.get('case_b') or ''} "
            f"{fields.get('prediction') or ''}"
        ).strip()
    if move.key == "contrast":
        return f"Case one: {fields.get('case_a') or ''} Case two: {fields.get('case_b') or ''}".strip()
    if move.key == "rule":
        return "Ask the child to state the rule."
    if move.key == "transfer":
        return f"Transfer case: {fields.get('transfer_case') or ''}".strip()
    if move.key == "stake":
        return f"Decision point: {fields.get('decision_point') or ''}".strip()
    if move.key == "mark":
        return f"Flawed claim: {fields.get('flawed_claim') or ''}".strip()
    if move.key == "defend":
        return "Ask the child to defend the causal chain."
    if move.key == "counterfactual":
        return f"Counterfactual: {fields.get('counterfactual') or ''}".strip()
    if move.key == "faulty":
        mixes = fields.get("mixes") or []
        joined = " and ".join(str(item) for item in mixes) or "two earlier components"
        return f"A rookie mixes {joined} and says: {fields.get('faulty_plan') or ''}".strip()
    if move.key == "correct":
        return "Ask the child to correct the plan."
    if move.key == "which_job":
        return "Ask which component does which job."
    if move.key == "extra_why":
        return "One extra why. The unit is already known. This does not change the score."
    return node.core_truth or node.title


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _close_length(level: int, kind: str) -> str:
    if kind == "time_boxed" or level <= 2:
        return "One or two sentences."
    return "Restate the idea in the child's words, then the status line."


def build_kc_prompt(
    *,
    student: Student,
    profile: TutorProfile,
    node: KcNode,
    goal: KcGoal,
    step: int,
    moves: list[Move],
    opening: bool,
    choice_on_screen: bool,
    prerequisite_status: str,
    support_band: str,
    course_position: str,
    unit_complete: bool,
    course_complete: bool,
    attempts: int,
    hint_tier: str,
    reveals: int,
    off_course_count: int,
    affect: str,
    enrichment_turns: int,
    help_requested: bool,
    minutes_used: int,
    component_status: str,
    stability: str,
    last_answer: str,
    last_misconception: str,
    last_messages: str,
    rubric_met: list[str],
    redirect_pending: bool,
    fragment: bool,
    others_known: bool,
) -> dict:
    """The bundle for this turn: prompt, schema, and temperature."""
    labels = moves or [Move("this", "This step", (), False)]
    index = min(max(step, 0), len(labels) - 1)
    move = labels[index]
    level = min(5, max(1, int(profile.instructive)))
    window_name = effective_window_name(profile, goal)
    enrichment = effective_enrichment(profile, goal)
    explain = self_explanation_on(profile)
    interests = ", ".join(str(item) for item in (student.interests or []) if str(item).strip()) or "none named"
    rubric = [str(item) for item in (node.rubric or []) if str(item).strip()]
    wrongs = []
    for item in node.misconceptions or []:
        if not isinstance(item, dict):
            continue
        wrong = str(item.get("wrong_move") or "").strip()
        broken = str(item.get("broken_kc") or "").strip()
        if wrong:
            wrongs.append(f"{wrong} -> {broken}" if broken else wrong)
    evidence = ", ".join(move.evidence) if move.evidence else "none (this move is not checked)"
    kind = goal.kind or "mastery"
    core = node.core_truth or "none yet"
    if profile.anti_spoiler:
        core_line = (
            f"Core truth, for grading only. Do not say it before a reveal or a unit close after a real pass: {core}"
        )
    else:
        core_line = f"Core truth: {core}."
    lines = [
        "You are the knowledge-component tutor.",
        "Settings do not change the type, the edges, or the score.",
        "The reply is the only text the child sees. Do not set the type, the edges, the score, or the step index.",
        "",
        "Layer 1, Component",
        f"Course title: {goal.title}.",
        f"Course description: {goal.description or 'none'}.",
        f"Audience: {goal.audience}. Keep the wording inside this age band.",
        f"Kind: {kind}.",
        f"Minutes: {goal.minutes if goal.minutes is not None else 'none'}. Minutes used: {minutes_used}.",
        f"Component: {node.title} ({node.code}).",
        f"Component description: {node.description or 'none'}.",
        f"Type: {node.kc_type or 'unset'}. Recipe: {recipe_name(node.kc_type)}.",
        core_line,
        "Rubric lines: " + ("; ".join(rubric) if rubric else "none") + ".",
        "Misconceptions: " + ("; ".join(wrongs) if wrongs else "none") + ".",
        f"Prerequisite codes: {', '.join(str(item) for item in (node.prerequisite_codes or [])) or 'none'}.",
        f"Encompass codes: {', '.join(str(item) for item in (node.encompasses_codes or [])) or 'none'}.",
        f"Prerequisite status: {prerequisite_status or 'none'}.",
        f"Course position: {course_position or 'none'}.",
        f"Move index: {index + 1} of {len(labels)}.",
        f"Move name: {move.name}.",
        f"Evidence: {evidence}.",
        f"Choice widget on screen: {_yes(choice_on_screen)}.",
        f"Material for this move: {move_material(node, move)}",
        f"Transfer case: {_field(node, 'transfer_case') or 'none'}.",
        f"Counterfactual: {_field(node, 'counterfactual') or 'none'}.",
        "",
        "Layer 2, Child",
        f"Display name: {student.display_name}. Speak to this name.",
        f"Age: {student.age if student.age is not None else 'unset'}.",
        f"Reading level: {student.reading_level or 'unset'}. An early level uses shorter sentences.",
        f"Modality: {student.modality or 'unset'}.",
        f"Interests: {interests}.",
        f"Attempts on this move: {attempts}.",
        f"Hint tier already given: {hint_tier or 'nudge'}.",
        f"Component status: {component_status or 'unknown'}. Stability: {stability or '0'}.",
        f"Last answer: {last_answer or 'none'}.",
        f"Last misconception: {last_misconception or 'none'}.",
        f"Support band: {support_band}.",
        "",
        "Layer 3, Voice",
        f"Persona: {labeled_choice(PERSONAS, profile.persona)}.",
        f"Lexicon: {labeled_choice(VOICES, profile.lexicon)}.",
        f"Metaphors: {labeled_choice(METAPHORS, profile.metaphors)}.",
        f"Sidekick: {labeled_choice(SIDEKICKS, profile.sidekick)}.",
        (
            "Use interests: yes. One interest may be the example."
            if profile.use_interests
            else "Use interests: no. Keep examples inside the subject."
        ),
        "Use that voice in the reply, including the intro, the unit close, and the course outro.",
        "Voice does not change the move, the expected answer, or the score.",
        "",
        "Layer 4, Guidance",
        f"Instructive: {instructive_value(level)}",
        f"Struggle window: {profile.struggle_window}. Effective struggle window: {window_name} ({struggle_tries(window_name)} tries before the next hint).",
        f"Stay on course: {_yes(profile.stay_on_course)}.",
        f"Anti-spoiler: {_yes(profile.anti_spoiler)}.",
        f"One question: {_yes(profile.one_question)}.",
        f"Misconception policy: {getattr(profile, 'misconception_policy', None) or 'retry_once'}.",
        f"Enrichment: {enrichment}. Stored enrichment: {stored_enrichment(profile)}.",
        "Hint ladder: nudge, analogy, scaffold, reveal. Analogy uses an interest only when use interests is on.",
        "A reveal states the expected point, marks the unit fragile, and the reply includes the fragile unit close.",
        "",
        "Layer 5, Encouragement",
        (
            "Growth-mindset praise: yes. Name the move the child made, including in the unit close. "
            "No generic praise and no person praise. If the child is stuck or guessing, add one calm line and continue the move. Do not reveal the answer in that line."
            if profile.growth_praise
            else "Growth-mindset praise: no. Praise may name a correct result."
        ),
        "",
        "Layer 6, Metacognition",
        f"Self-explanation: {_yes(explain)}.",
        f"Asks why on this move: {_yes(asks_why(profile, move))}.",
        "A passed move still gets one sentence that says what held, in the child's words where possible, then the next question. The unit close is that sentence when the move is the last one.",
        "",
        "Layer 7, Feedback loop",
        f"Reveals used: {reveals}. Off-course count: {off_course_count}. Enrichment turns on this move: {enrichment_turns}.",
        f"Rubric points already met: {', '.join(rubric_met) if rubric_met else 'none'}.",
        f"Affect: {affect or 'unset'}. Help requested: {_yes(help_requested)}.",
        f"Last four messages: {last_messages or 'none'}.",
        f"Redirect pending: {_yes(redirect_pending)}.",
        f"Unit close required this turn: {_yes(unit_complete)}.",
        f"Course outro required this turn: {_yes(course_complete)}.",
        f"Other target components already known: {_yes(others_known)}.",
        "",
        "Move contract",
        _sequence_line(node.kc_type),
        f"This turn is move {index + 1} of {len(labels)}: {move.name}.",
        *_contract(
            opening=opening,
            move=move,
            level=level,
            kind=kind,
            use_interests=bool(profile.use_interests),
            anti_spoiler=bool(profile.anti_spoiler),
            one_question=bool(profile.one_question),
            stay_on_course=bool(profile.stay_on_course),
            enrichment=enrichment,
            support_band=support_band,
            modality=student.modality or "",
            fragment=fragment,
            explain=explain,
            others_known=others_known,
            choice_on_screen=choice_on_screen,
        ),
    ]
    return {
        "system_prompt": "\n".join(lines),
        "response_schema": RESPONSE_SCHEMA,
        "temperature": TEMPERATURE,
    }


def _sequence_line(kc_type: str | None) -> str:
    lines = {
        "factual": "Factual: intro, retrieve with evidence fact, an optional restatement when self-explanation is on and the retrieval was only a fragment, then the unit close.",
        "procedural": "Procedural: intro names the goal of the procedure, worked example, faded step with evidence blanked_step, solo with evidence solo_check, why this order only when self-explanation is on, then the unit close.",
        "conceptual": "Conceptual: intro does not name the rule, predict the two cases, contrast, state the rule with evidence rule, transfer on transfer_case when that field is present, then the unit close.",
        "causal": "Causal: intro of the decision, what is at stake, mark the flawed claim, defend the chain with evidence causal_chain, counterfactual when that field is present and self-explanation is on, then the unit close.",
        "synthesis": "Synthesis: intro names the mixed components and the job, the rookie's faulty plan, correct it with evidence core_truth, say which component does which job, then the unit close.",
    }
    return lines.get(kc_type or "", "This component has no move sequence yet.")


def _contract(
    *,
    opening: bool,
    move: Move,
    level: int,
    kind: str,
    use_interests: bool,
    anti_spoiler: bool,
    one_question: bool,
    stay_on_course: bool,
    enrichment: str,
    support_band: str,
    modality: str,
    fragment: bool,
    explain: bool,
    others_known: bool,
    choice_on_screen: bool,
) -> list[str]:
    lines = []
    if opening:
        lines.append(
            "This is the intro, the first turn of the component. Say what this piece is, why it sits in this course, and what the child will do, then one question. Do not give the core truth."
        )
        lines.append(f"Intro shape: {_EXPLAIN[level]}")
        if kind == "time_boxed":
            lines.append("Time boxed: the intro is one sentence.")
        if use_interests:
            lines.append("An interest may be the example in the intro.")
        else:
            lines.append("Do not use an interest as the example.")
    if kind == "time_boxed":
        lines.append("Time boxed forces the struggle window to minimum and enrichment to direct. The close is one or two sentences.")
    if kind == "curiosity" and move.key == "extra_why":
        lines.append("Curiosity allows this one extra why after the unit is known. It does not change the score.")
    if support_band == "hold":
        lines.append("Support band hold: name the missing prerequisite and the patch card. Do not teach that other component in this chat.")
    elif support_band == "stretch":
        lines.append("Support band stretch: one prerequisite is fragile. Stay on this component.")
    if modality.strip().lower() == "visual" and move.key in {"predict", "contrast", "worked", "faded"}:
        lines.append("Modality is visual. You may ask for a described picture because this component already has cases or steps.")
    if choice_on_screen:
        lines.append("A choice widget is on screen. The child picks. Do not add a second question beside it.")
    if move.evidence:
        lines.append(
            f"This move is checked. Put these ids in rubric_met only when the reply's answer holds them: {', '.join(move.evidence)}."
        )
        lines.append("Do not advance on an empty evidence list.")
    else:
        lines.append("This move is not checked. Advance when the child has done what the move asked.")
    if fragment and explain and move.key == "retrieve":
        lines.append("The retrieval was only a fragment. Decision is advance, not complete, and the reply asks for a restatement.")
    if enrichment == "direct":
        lines.append("Enrichment is direct. Move on as soon as the move is passed.")
    elif enrichment == "offer":
        lines.append("Enrichment is offer. After a passed move you may ask once whether the child wants one more look. Two turns is the cap.")
    else:
        lines.append("Enrichment is on request. Stay when the child asks to keep going on this component. Two turns is the cap.")
    lines.append("A stay for enrichment is still this component. It does not change the score and it does not gate being known.")
    if stay_on_course:
        lines.append("Stay on course. A tangent gets a short answer, then return to this move.")
    else:
        lines.append("Stay on course is off. You may follow a tangent. The score still comes only from this component.")
    if anti_spoiler:
        lines.append("Anti-spoiler is on. Do not say the core truth before a reveal or a real pass.")
    if one_question:
        lines.append("One question is on. A learning reply ends with a single question. A unit close or a course outro asks no new question.")
    lines.append(f"Unit close length: {_close_length(level, kind)}")
    lines.append(
        "When your decision ends the unit, the reply says outright that this unit is complete if it is known. "
        "Name the component and what the child can now do. A fragile unit says this unit is paused and still needs another look, and names the patch when there is one. Do not call a fragile unit finished work."
    )
    if others_known:
        lines.append(
            "If this unit ends known, every other target is already known. Append the course outro after the unit close: the course is complete, name the course, and recap the ideas the child now holds."
        )
    else:
        lines.append("A target is still unknown or fragile. Do not write a course outro. The unit close may point at the next card.")
    lines.append(
        "decision is stay, advance, complete, or redirect. stay is also the enrichment hold. "
        "redirect only names a stored wrong move. The app decides whether a redirect is allowed."
    )
    return lines
