"""Prompt for one knowledge-component move.

The bundle is the system prompt, the response schema, and the temperature.
The prompt is seven instruction sections. Each setting is one behavior.
The debug panel, not this text, groups the stored settings into seven layers.
The model writes the reply. The app owns the type, the edges, and the score.
The quest prompt builder is a different module and is not imported here.
"""

from __future__ import annotations

import re
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


_LINK_SPLIT = re.compile(r"\s*(?:\n+|;|(?<=[.!?])\s+|\s+so\s+)\s*", re.IGNORECASE)


def stored_outline(node: KcNode) -> str:
    return str(getattr(node, "outline", "") or "").strip()


def stored_pairs(node: KcNode) -> list[tuple[str, str]]:
    """Topic and goal pairs. A pair missing either side is skipped."""
    raw = getattr(node, "topics", None)
    pairs: list[tuple[str, str]] = []
    if not isinstance(raw, list):
        return pairs
    for item in raw:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        goal = str(item.get("goal") or "").strip()
        if topic and goal:
            pairs.append((topic, goal))
    return pairs


def _has_text(value: object) -> bool:
    return bool(str(value or "").strip())


def _norm_text(value: str) -> str:
    return " ".join(value.lower().split())


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _chain_links(chain: str) -> list[str]:
    text = (chain or "").strip()
    if not text:
        return []
    parts = [part.strip(" \t.;,") for part in _LINK_SPLIT.split(text)]
    return [part for part in parts if part] or [text]


def _with_fallback(pairs: list[tuple[str, str]], fallback: list[str]) -> list[tuple[str, str]]:
    """Stored pairs, then any fallback field that is not already a topic."""
    source = list(pairs)
    seen = {_norm_text(topic) for topic, _goal in pairs}
    for item in fallback:
        key = _norm_text(item)
        if key and key not in seen:
            source.append((item, ""))
            seen.add(key)
    return source


def _walk_pairs(node: KcNode) -> list[tuple[str, str]]:
    """The topic turns for this type. The description is not read."""
    kind = node.kc_type or ""
    fields = node.type_fields or {}
    pairs = stored_pairs(node)
    named = [topic for topic, _goal in pairs]
    if kind == "procedural":
        fallback = _string_list(fields.get("steps"))
    elif kind == "causal":
        fallback = [] if named else _chain_links(str(fields.get("causal_chain") or ""))
    elif kind == "synthesis":
        fallback = [] if named else _string_list(fields.get("mixes"))
    else:
        fallback = []
    return _with_fallback(pairs, fallback)


def topic_goal(node: KcNode, index: int) -> str:
    pairs = _walk_pairs(node)
    if 0 <= index < len(pairs):
        return pairs[index][1]
    return ""


def _topic_moves(pairs: list[tuple[str, str]]) -> list[Move]:
    moves: list[Move] = []
    for index, (text, goal) in enumerate(pairs, start=1):
        evidence = (f"goal-{index}",) if goal else ()
        moves.append(Move(f"topic-{index}", text, evidence, False))
    return moves


def moves_for(
    node: KcNode,
    profile: TutorProfile,
    goal: KcGoal | None,
    *,
    fragment: bool = False,
) -> list[Move]:
    """One step per stored field that has a value. An empty field is skipped."""
    kind = node.kc_type or ""
    fields = node.type_fields or {}
    explain = self_explanation_on(profile)
    outline = stored_outline(node)
    topic_moves = _topic_moves(_walk_pairs(node))
    steps = _string_list(fields.get("steps"))
    mixes = _string_list(fields.get("mixes"))
    chain = str(fields.get("causal_chain") or "").strip()
    sequence: list[Move] = []
    if outline or (kind == "synthesis" and mixes):
        sequence.append(Move("orient", "Orient", (), False))
    if kind == "factual":
        sequence.extend(topic_moves)
        fact = str(fields.get("fact") or "").strip()
        question = str(fields.get("retrieval_question") or "").strip()
        if fact or question:
            sequence.append(Move("retrieve", "Retrieve", ("fact",) if fact else (), False))
            if explain and fragment:
                sequence.append(Move("restate", "Restate", ("restatement",), False))
    elif kind == "procedural":
        discussed = topic_moves
        sequence.extend(discussed)
        if discussed:
            sequence.append(Move("decide", "Decision point", (), False))
        if steps:
            sequence.append(Move("faded", "Faded step", ("blanked_step",), False))
        problem = str(fields.get("solo_problem") or "").strip()
        check = str(fields.get("solo_check") or "").strip()
        if problem or check:
            sequence.append(Move("solo", "Solo", ("solo_check",) if check else (), False))
        if explain and discussed:
            sequence.append(Move("why_order", "Why this order", ("why_order",), False))
    elif kind == "conceptual":
        sequence.extend(topic_moves)
        case_a = str(fields.get("case_a") or "").strip()
        case_b = str(fields.get("case_b") or "").strip()
        prediction = str(fields.get("prediction") or "").strip()
        rule = str(fields.get("rule") or "").strip()
        transfer = str(fields.get("transfer_case") or "").strip()
        if case_a:
            sequence.append(Move("predict_a", "Predict case one", (), True))
        if case_b:
            sequence.append(Move("predict_b", "Predict case two", (), True))
        if case_a and case_b:
            sequence.append(Move("contrast", "Contrast", (), False))
        elif prediction and not case_a and not case_b:
            sequence.append(Move("predict", "Predict", (), False))
        if rule:
            sequence.append(Move("rule", "State the rule", ("rule",), False))
        if transfer:
            sequence.append(Move("transfer", "Transfer", ("transfer",), False))
    elif kind == "causal":
        sequence.extend(topic_moves)
        if _has_text(fields.get("decision_point")):
            sequence.append(Move("stake", "What is at stake", (), False))
        if _has_text(fields.get("flawed_claim")):
            sequence.append(Move("mark", "Mark the claim", ("mark",), True))
        if chain:
            sequence.append(Move("defend", "Defend the chain", ("causal_chain",), False))
        if explain and _has_text(fields.get("counterfactual")):
            sequence.append(Move("counterfactual", "Counterfactual", ("counterfactual",), False))
    elif kind == "synthesis":
        sequence.extend(topic_moves)
        if _has_text(fields.get("faulty_plan")):
            sequence.append(Move("faulty", "Faulty plan", (), False))
        if _has_text(node.core_truth):
            sequence.append(Move("correct", "Correct the plan", ("core_truth",), False))
        if mixes:
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
    names = [move.name for move in moves_for(node, profile, None)]
    return names or ["This step"]


def asks_why(profile: TutorProfile, move: Move) -> bool:
    if not self_explanation_on(profile):
        return False
    return move.key in {"restate", "why_order", "counterfactual", "extra_why", "which_job"}


def _goal_text(node: KcNode, move: Move) -> str:
    if not move.key.startswith("topic-"):
        return ""
    try:
        index = int(move.key.split("-", 1)[1]) - 1
    except ValueError:
        return ""
    return topic_goal(node, index)


def _topic_count(moves: list[Move]) -> int:
    return sum(1 for item in moves if item.key.startswith("topic-"))


def _topic_number(moves: list[Move], move: Move) -> int:
    number = 0
    for item in moves:
        if item.key.startswith("topic-"):
            number += 1
            if item.key == move.key:
                return number
    return 0


def move_material(node: KcNode, move: Move) -> str:
    fields = node.type_fields or {}
    if move.key == "orient":
        outline = stored_outline(node)
        if outline:
            return f"Outline: {outline}"
        mixes = _string_list(fields.get("mixes"))
        if mixes:
            return "The two earlier components are " + " and ".join(mixes) + "."
        return "Outline: "
    if move.key.startswith("topic-"):
        goal = _goal_text(node, move)
        if goal:
            return f"Topic: {move.name}. Goal: {goal}"
        return f"Topic: {move.name}"
    if move.key == "retrieve":
        return str(fields.get("retrieval_question") or "What is the fact?")
    if move.key == "restate":
        return "Ask for the fact in a full sentence. The earlier answer was only a fragment."
    if move.key == "decide":
        return "Ask the child what to do next. Do not show the remaining steps."
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
    if move.key == "predict_a":
        return f"Case one: {fields.get('case_a') or ''}. {fields.get('prediction') or ''}".strip()
    if move.key == "predict_b":
        return f"Case two: {fields.get('case_b') or ''}. {fields.get('prediction') or ''}".strip()
    if move.key == "predict":
        return str(fields.get("prediction") or "What do you predict?")
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
        return f"Causal chain: {fields.get('causal_chain') or ''}".strip()
    if move.key == "counterfactual":
        return f"Counterfactual: {fields.get('counterfactual') or ''}".strip()
    if move.key == "faulty":
        return f"Faulty plan: {fields.get('faulty_plan') or ''}".strip()
    if move.key == "correct":
        return "Ask the child to correct the plan."
    if move.key == "which_job":
        return "Ask which component does which job."
    if move.key == "extra_why":
        return "One extra why. The unit is already known. This does not change the score."
    return node.core_truth or node.title


_POSITION = re.compile(r"^(\d+) of (\d+); previous: (.*); next: (.*)$")

_PICTURE_MOVES = {"predict", "predict_a", "predict_b", "contrast", "faded"}


def _early_reading(level: str) -> bool:
    text = (level or "").strip().lower()
    return bool(text) and ("early" in text or text in {"beginning", "beginner", "pre-reader"})


def _a(label: str) -> str:
    text = (label or "").strip()
    if not text:
        return "the stored voice"
    lowered = text[0].lower() + text[1:]
    if lowered.startswith(("a ", "an ", "the ")):
        return lowered
    article = "an" if lowered[:1] in "aeiou" else "a"
    return f"{article} {lowered}"


def _lower_first(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    return cleaned[0].lower() + cleaned[1:]


def _wrong_moves(node: KcNode) -> list[str]:
    found: list[str] = []
    for item in node.misconceptions or []:
        if not isinstance(item, dict):
            continue
        wrong = str(item.get("wrong_move") or "").strip()
        if wrong:
            found.append(wrong)
    return found


def _prompt_material(node: KcNode, move: Move) -> str:
    """Move content for the model. Component codes stay in the debug panel."""
    fields = node.type_fields or {}
    if move.key == "faulty":
        plan = str(fields.get("faulty_plan") or "").strip()
        return f"A rookie mixes earlier pieces and says: {plan}".strip()
    if move.key == "transfer":
        case = str(fields.get("transfer_case") or "").strip()
        return f"Ask the child to use this third case: {case}".strip()
    if move.key == "counterfactual":
        case = str(fields.get("counterfactual") or "").strip()
        return f"Ask what would change: {case}".strip()
    return move_material(node, move)


def _finish(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def _core_sentence(core: str, anti_spoiler: bool) -> str:
    truth = _finish(core) or "Nothing is stored yet."
    if anti_spoiler:
        return (
            f"Grade the answer against this core truth: {truth} "
            "Say it only when a reveal or a passed close allows it."
        )
    return f"Grade the answer against this core truth: {truth} You may say it while you teach."


def _position_sentence(course_position: str) -> str:
    text = (course_position or "").strip()
    if not text:
        return ""
    if text == "Patch":
        return "This piece is a patch beside the course, not one of the targets."
    match = _POSITION.match(text)
    if match is None:
        return ""
    index, total, previous, nxt = (part.strip() for part in match.groups())
    sentence = f"This is piece {index} of {total} in the course."
    if previous == "none":
        sentence += " Nothing in this course comes before it."
    else:
        sentence += f" The child has already come through {previous}."
    if nxt == "none":
        sentence += " Nothing in this course comes after it."
    else:
        sentence += f" {nxt} comes next."
    return sentence


def _prereq_sentence(prerequisite_status: str) -> str:
    text = (prerequisite_status or "").strip()
    if not text or text == "none":
        return "This piece does not depend on an earlier component."
    states: list[str] = []
    for part in text.split(";"):
        piece = part.strip()
        if not piece:
            continue
        states.append(piece.split(":", 1)[1].strip().lower() if ":" in piece else piece.lower())
    if not states:
        return "This piece does not depend on an earlier component."
    bits: list[str] = []
    known = states.count("known")
    fragile = states.count("fragile")
    unknown = states.count("unknown")
    if known:
        bits.append(
            "The child already knows the earlier idea this piece needs."
            if known == 1
            else "The child already knows the earlier ideas this piece needs."
        )
    if fragile:
        bits.append(
            "An earlier idea this piece needs is still shaky."
            if fragile == 1
            else "Some earlier ideas this piece needs are still shaky."
        )
    if unknown:
        bits.append(
            "An earlier idea this piece needs is still unknown."
            if unknown == 1
            else "Some earlier ideas this piece needs are still unknown."
        )
    return " ".join(bits)


def _path_sentence(node: KcNode) -> str:
    kind = node.kc_type or ""
    if kind == "factual":
        return "The path is the opening, then the retrieval, then the close."
    if kind == "procedural":
        return "The path is the opening, a worked example, a faded step, then the solo."
    if kind == "conceptual":
        return (
            "The path is the opening, a prediction, a contrast, then the rule. "
            "The opening does not name the rule."
        )
    if kind == "causal":
        return "The path is the opening, what is at stake, the flawed claim, then the chain."
    if kind == "synthesis":
        return "The path is the opening, the rookie's faulty plan, the correction, then which piece does which job."
    return "This component has no move sequence yet."


def _later_case(node: KcNode, move: Move) -> str:
    fields = node.type_fields or {}
    if move.key != "transfer":
        transfer = str(fields.get("transfer_case") or "").strip()
        if transfer:
            return (
                "A later move asks the child to use this third case. "
                f"Do not invent a different one: {transfer}."
            )
    if move.key != "counterfactual":
        counter = str(fields.get("counterfactual") or "").strip()
        if counter:
            return (
                "A later move asks what would change. "
                f"Do not invent a different one: {counter}."
            )
    return ""


def _learner_sentence(
    student: Student,
    profile: TutorProfile,
    move: Move,
    interests: str,
) -> str:
    parts = [f"Speak to {student.display_name}."]
    age = student.age
    level = (student.reading_level or "").strip()
    early = _early_reading(level)
    young = age is not None and age <= 8
    if young and early:
        parts.append(f"Age {age} and an early reading level both mean shorter sentences and simpler examples.")
    elif young:
        parts.append(f"Age {age} means shorter sentences and simpler examples.")
    elif age is not None:
        parts.append(f"Keep the examples right for a {age}-year-old.")
    else:
        parts.append("No age is set.")
    if early and not young:
        parts.append("The reading level is early, so use shorter sentences.")
    elif level and not (early and young):
        parts.append(f"The reading level is {level}.")
    elif not level:
        parts.append("No reading level is set.")
    modality = (student.modality or "").strip()
    if modality.lower() == "visual" and move.key in _PICTURE_MOVES:
        parts.append("You may ask for a described picture on this move, because it already has cases or steps.")
    elif modality.lower() == "visual":
        parts.append("Stay in words on this move. It has no cases or steps to picture.")
    elif modality:
        parts.append(f"This child takes an example in through {modality}, so stay in words.")
    else:
        parts.append("No modality is set, so stay in words.")
    named = interests if interests and interests != "none named" else ""
    if profile.use_interests and named:
        parts.append(f"When an example would help, use one of these interests: {named}.")
    elif named:
        parts.append(f"The child cares about {named}. Keep examples inside the subject.")
    else:
        parts.append("Keep examples inside the subject.")
    return " ".join(parts)


def _window_sentence(name: str) -> str:
    tries = struggle_tries(name)
    if tries == 1:
        return "Give the next hint after one miss."
    if tries == 3:
        return "Give the next hint after three tries."
    return "Give the next hint after two tries."


def _enrichment_sentence(enrichment: str) -> str:
    if enrichment == "direct":
        return "Move on as soon as the move is passed."
    if enrichment == "offer":
        return (
            "After a passed move, you may ask once whether the child wants one more look. "
            "Two turns is the cap. A stay is still this component and does not change the score."
        )
    return (
        "Stay when the child asks to keep going on this component. "
        "Two turns is the cap. A stay is still this component and does not change the score."
    )


def _voice_paragraph(profile: TutorProfile) -> str:
    persona = _a(_label(PERSONAS, profile.persona or ""))
    lexicon = _lower_first(_label(VOICES, profile.lexicon or "")) or "plain"
    if (profile.metaphors or "").strip() == "none":
        images = "plain language and no borrowed image"
    else:
        metaphor = _lower_first(_label(METAPHORS, profile.metaphors or ""))
        images = f"{metaphor} images" if metaphor else "plain language"
    if (profile.sidekick or "").strip() in {"", "off"}:
        company = ""
    else:
        company = f", and with {_a(_label(SIDEKICKS, profile.sidekick))}"
    return (
        f"Write as {persona}, in {lexicon} words, with {images}{company}. "
        "That voice does not change the move, the expected answer, or the score."
    )


def _close_length_sentence(level: int) -> str:
    if level <= 2:
        return "Keep the close to one or two sentences."
    return "Restate the idea in the child's words, then say where the unit stands."


def _close_body() -> str:
    return (
        "A known unit says the unit is complete, names this piece, and says what the child can now do. "
        "A fragile unit says the unit is paused and still needs another look, and names the patch when there is one. "
        "Do not call a fragile unit finished work."
    )


def _outro_sentence(others_known: bool, course_title: str, *, required: bool) -> str:
    if others_known:
        if required:
            return (
                f"Then add the course outro: {course_title} is complete, "
                "and recap the ideas the child now holds."
            )
        return (
            "If this unit ends known, every other target is already known. "
            f"After the close, add the course outro: {course_title} is complete, "
            "and recap the ideas the child now holds."
        )
    return "Another target is not known yet. Do not write a course outro. The close may point at the next card."


def _ending(
    *,
    level: int,
    kind: str,
    unit_complete: bool,
    course_complete: bool,
    others_known: bool,
    course_title: str,
    last_move: bool,
) -> str:
    if not last_move and not unit_complete and not course_complete:
        return "The unit is not finished. This reply must not say it is complete."
    length = "" if kind == "time_boxed" else _close_length_sentence(level)
    close = _close_body()
    if course_complete:
        lead = "End the unit and the course in this reply."
    elif unit_complete:
        lead = "End the unit in this reply."
    else:
        lead = "When the decision ends the unit, the reply includes the close."
    outro = _outro_sentence(others_known, course_title, required=course_complete)
    return " ".join(part for part in (lead, length, close, outro) if part)


def _step_intro(move: Move, moves: list[Move]) -> str:
    if move.key.startswith("topic-"):
        number = _topic_number(moves, move)
        total = _topic_count(moves)
        return f"This step is topic {number} of {total}: {move.name}. The child will type."
    if move.choice:
        return f"This step is {move.name}. The child will pick on screen."
    return f"This step is {move.name}. The child will type."


def _this_turn(
    *,
    node: KcNode,
    move: Move,
    moves: list[Move],
    index: int,
    total: int,
    opening: bool,
    unit_complete: bool,
    course_complete: bool,
    choice_on_screen: bool,
    fragment: bool,
    explain: bool,
    level: int,
    kind: str,
    others_known: bool,
    course_title: str,
) -> list[str]:
    # The orient move replaced the old opening script. The flag stays for callers.
    del opening
    del node
    lines = [
        "You are the knowledge-component tutor.",
        _step_intro(move, moves),
    ]
    closing = unit_complete or course_complete
    last_move = index >= total - 1
    include_close = last_move or closing
    if fragment and explain and move.key == "retrieve" and not closing:
        lines.append(
            "The retrieval was only a fragment. Advance, and ask for the fact in a full sentence. "
            "Do not complete the unit on that fragment."
        )
    elif move.key == "extra_why" and not closing:
        lines.append("This move is the one extra why. The unit is already known. Leave the score as it is.")
    if move.choice or choice_on_screen:
        pick = "The child picks the choice on screen. Do not add a question beside it."
        if include_close:
            pick += " A unit close or a course outro asks no new question."
        lines.append(pick)
    lines.append(
        _ending(
            level=level,
            kind=kind,
            unit_complete=unit_complete,
            course_complete=course_complete,
            others_known=others_known,
            course_title=course_title,
            last_move=last_move,
        )
    )
    return lines


def _withheld(label: str, text: str, anti_spoiler: bool) -> str:
    sentence = _finish(text)
    if anti_spoiler:
        return (
            f"Grade the answer against this {label}: {sentence} "
            "Say it only when a reveal or a passed close allows it."
        )
    return f"The {label} is: {sentence} You may say it while you teach."


def _practice_lines(node: KcNode, move: Move, anti_spoiler: bool) -> list[str]:
    """The one field this practice step walks. Other fields stay out."""
    fields = node.type_fields or {}
    if move.key == "retrieve":
        lines = [f"The retrieval question is: {fields.get('retrieval_question') or 'What is the fact?'}"]
        fact = str(fields.get("fact") or "").strip()
        if fact:
            lines.append(_withheld("fact", fact, anti_spoiler))
        return lines
    if move.key == "restate":
        fact = str(fields.get("fact") or node.core_truth or "").strip()
        lines = ["Ask for the fact in a full sentence."]
        if fact:
            lines.append(_withheld("fact", fact, anti_spoiler))
        return lines
    if move.key == "decide":
        return ["Ask the child what to do next. Do not show the remaining steps."]
    if move.key == "faded":
        return [move_material(node, move)]
    if move.key == "solo":
        lines = [f"The solo problem is: {fields.get('solo_problem') or 'Solve it on your own.'}"]
        check = str(fields.get("solo_check") or "").strip()
        if check:
            lines.append(_withheld("solo check", check, True))
        return lines
    if move.key == "why_order":
        return ["Ask why the steps go in this order."]
    if move.key == "predict_a":
        lines = [f"Case one: {fields.get('case_a') or ''}"]
        prediction = str(fields.get("prediction") or "").strip()
        if prediction:
            lines.append(f"Prediction: {prediction}")
        return lines
    if move.key == "predict_b":
        lines = [f"Case two: {fields.get('case_b') or ''}"]
        prediction = str(fields.get("prediction") or "").strip()
        if prediction:
            lines.append(f"Prediction: {prediction}")
        return lines
    if move.key == "predict":
        return [f"Prediction: {fields.get('prediction') or 'What do you predict?'}"]
    if move.key == "contrast":
        return [
            f"Case one: {fields.get('case_a') or ''}",
            f"Case two: {fields.get('case_b') or ''}",
        ]
    if move.key == "rule":
        rule = str(fields.get("rule") or "").strip()
        lines = ["Ask the child to state the rule."]
        if rule:
            lines.append(_withheld("rule", rule, True))
        return lines
    if move.key == "transfer":
        return [f"Transfer case: {fields.get('transfer_case') or ''}"]
    if move.key == "stake":
        return [f"Decision point: {fields.get('decision_point') or ''}"]
    if move.key == "mark":
        return [f"Flawed claim: {fields.get('flawed_claim') or ''}"]
    if move.key == "defend":
        chain = str(fields.get("causal_chain") or "").strip()
        lines = ["Ask the child to defend the causal chain."]
        if chain:
            lines.append(_withheld("causal chain", chain, anti_spoiler))
        return lines
    if move.key == "counterfactual":
        return [f"Counterfactual: {fields.get('counterfactual') or ''}"]
    if move.key == "faulty":
        return [f"Faulty plan: {fields.get('faulty_plan') or ''}"]
    if move.key == "correct":
        truth = str(node.core_truth or "").strip()
        lines = ["Ask the child to correct the plan."]
        if truth:
            lines.append(_withheld("core truth", truth, True))
        return lines
    if move.key == "which_job":
        mixes = _string_list(fields.get("mixes"))
        if mixes:
            return ["Ask which component does which job: " + " and ".join(mixes) + "."]
        return ["Ask which component does which job."]
    if move.key == "extra_why":
        return ["One extra why. The unit is already known. This does not change the score."]
    return [move_material(node, move)]


def _what_to_teach(
    *,
    node: KcNode,
    goal: KcGoal,
    move: Move,
    anti_spoiler: bool,
    prerequisite_status: str,
    course_position: str,
) -> list[str]:
    # Course description, position, and prerequisites stay off this section.
    del goal
    del prerequisite_status
    del course_position
    if move.key.startswith("topic-"):
        lines = [f"The topic is {move.name}."]
        goal_text = _goal_text(node, move)
        if goal_text:
            lines.append(f"The goal is {goal_text}.")
        return lines
    if move.key == "orient":
        outline = stored_outline(node)
        if outline:
            return [f"The outline is {outline}."]
        mixes = _string_list((node.type_fields or {}).get("mixes"))
        if mixes:
            return ["The two earlier components are " + " and ".join(mixes) + "."]
        return ["No outline is stored."]
    lines = _practice_lines(node, move, anti_spoiler)
    if move.evidence:
        lines.append(
            "On this move, count these ids only when the answer holds them: "
            + ", ".join(move.evidence)
            + "."
        )
    else:
        lines.append("This move is not checked. Advance when the child has done what the move asked.")
    return lines


def _step_rule(
    node: KcNode,
    move: Move,
    moves: list[Move],
    *,
    anti_spoiler: bool,
) -> str:
    fields = node.type_fields or {}
    kind = node.kc_type or ""
    if move.choice:
        return (
            f"This step is {move.name}. The child picks on screen. "
            "Do not add a second question."
        )
    if move.key == "orient":
        if kind == "procedural":
            rule = (
                "This step is Orient. The child will type. "
                "Elaborate the outline and name the goal of the procedure. "
                "Do not show the steps or the goals."
            )
        elif kind == "conceptual":
            rule = (
                "This step is Orient. The child will type. "
                "Elaborate the outline. Do not name the rule, and do not open the topics."
            )
        elif kind == "causal":
            decision = str(fields.get("decision_point") or "").strip()
            named = f" Name this decision: {decision}." if decision else ""
            rule = (
                "This step is Orient. The child will type. "
                "Elaborate the outline and name the decision as the situation."
                f"{named} Do not give the chain, the topics, or the goals."
            )
        elif kind == "synthesis":
            mixes = _string_list(fields.get("mixes"))
            named = " and ".join(mixes) if mixes else "the two earlier components"
            rule = (
                "This step is Orient. The child will type. "
                f"Name the job of this piece and the two earlier components it mixes: {named}. "
                "Do not open the topics or correct the rookie."
            )
        else:
            withheld = " Do not state the fact." if anti_spoiler else ""
            rule = (
                "This step is Orient. The child will type. "
                "Elaborate the outline and say where this piece sits. "
                f"Do not open the topics or the goals.{withheld}"
            )
        return rule
    if move.key.startswith("topic-"):
        number = _topic_number(moves, move)
        total = _topic_count(moves)
        goal_text = _goal_text(node, move)
        sentence = (
            f"This turn is topic {number} of {total}: {move.name}. "
        )
        if goal_text:
            point = move.evidence[0] if move.evidence else ""
            count = f" Count {point} when the answer holds the goal." if point else ""
            sentence += (
                f"The goal that belongs to it is {goal_text}. "
                "Discuss that topic and look for the goal inside the discussion. "
                "If the goal was not met, ask about the goal directly and stay on this topic."
                f"{count}"
            )
        else:
            sentence += "Discuss that topic. Do not open a later topic."
        if kind == "procedural":
            sentence += " The child says what that step did. Do not show a later step."
        return sentence
    if move.key == "extra_why":
        return "This step is Extra why. The child will type."
    rules = {
        "retrieve": "Ask the retrieval question.",
        "restate": "Ask for the fact in a full sentence.",
        "decide": "Ask what to do next. Do not show the remaining steps.",
        "faded": "Ask for the blanked step.",
        "solo": "Ask the child to solve the solo problem.",
        "why_order": "Ask why the steps go in this order.",
        "predict": "Ask for the prediction.",
        "contrast": "Ask the child to contrast the two cases.",
        "rule": "Ask the child to state the rule. Do not say the rule first.",
        "transfer": "Ask the child to use the transfer case.",
        "stake": "Ask what is at stake.",
        "defend": "Ask the child to defend the causal chain.",
        "counterfactual": "Ask what would change.",
        "faulty": "Show the rookie's faulty plan.",
        "correct": "Ask the child to correct the plan.",
        "which_job": "Ask which component does which job.",
    }
    detail = rules.get(move.key, "Do this step.")
    return f"This step is {move.name}. The child will type. {detail}"


def _how_to_teach(
    *,
    profile: TutorProfile,
    node: KcNode,
    goal: KcGoal,
    move: Move,
    moves: list[Move],
    level: int,
    window_name: str,
    enrichment: str,
    support_band: str,
    prerequisite_status: str,
    choice_on_screen: bool,
    minutes_used: int,
    has_misconceptions: bool,
    anti_spoiler: bool,
    include_close: bool,
) -> list[str]:
    lines = [
        _step_rule(node, move, moves, anti_spoiler=anti_spoiler),
        _EXPLAIN[level],
    ]
    wrongs = _wrong_moves(node) if has_misconceptions else []
    kind = goal.kind or "mastery"
    if kind == "time_boxed":
        budget = ""
        if goal.minutes is not None:
            budget = (
                f" The budget is {goal.minutes} minutes and {minutes_used} have been used. "
                "Stay inside what is left."
            )
        lines.append(
            "This course is short on time. Keep the opening to one sentence, "
            "give the next hint after one miss, move on as soon as the move is passed, "
            "and keep the close to one or two sentences."
            + budget
        )
    else:
        lines.append(_window_sentence(window_name))
        lines.append(_enrichment_sentence(enrichment))
        if kind == "curiosity" and move.key != "extra_why":
            lines.append("After the unit is known, one extra why is allowed. Leave the score as it is.")
    lines.append(
        "Help in this order: a nudge, then an analogy, then a scaffold, then a reveal. "
        "A reveal states the expected point, marks the unit fragile, and the reply includes the fragile close."
    )
    if profile.stay_on_course:
        lines.append("A tangent gets a short answer, then come back to this move.")
    else:
        lines.append("You may follow a tangent. The score still comes only from this component.")
    if has_misconceptions:
        lines.append(
            "The first time a stored wrong move matches, explain that mistake and ask the same move again. "
            "The second time, redirect, and this unit ends fragile."
        )
        if wrongs:
            lines.append(" ".join(f"Wrong move: {_finish(wrong)}" for wrong in wrongs))
    if support_band == "hold":
        lines.append(
            "Name the missing earlier idea and the patch card. Do not teach that other component in this chat."
        )
    elif support_band == "stretch":
        lines.append("Stay on this component.")
    elif support_band == "ready" and (prerequisite_status or "").strip() not in {"", "none"}:
        lines.append("The earlier ideas are in place, so teach this component.")
    if profile.one_question and not choice_on_screen:
        question = "End a learning reply with a single question."
        if include_close:
            question += " A unit close or a course outro asks no new question."
        lines.append(question)
    if profile.growth_praise:
        lines.append(
            "When you praise, name the move the child made, including in the close. "
            "No generic praise and no praise of the person. "
            "If the child is stuck or guessing, add one calm line and keep going. Do not reveal the answer in that line."
        )
    lines.append(
        "After a passed move that does not end the unit, say what held in the child's words, then continue."
    )
    return lines


def _what_happened(
    *,
    attempts: int,
    hint_tier: str,
    reveals: int,
    off_course_count: int,
    affect: str,
    enrichment_turns: int,
    help_requested: bool,
    component_status: str,
    last_answer: str,
    last_misconception: str,
    last_messages: str,
    rubric_met: list[str],
    redirect_pending: bool,
) -> list[str]:
    lines = [
        "This is what already happened. Do not treat it as a new rule.",
        f"Tries on this move so far: {attempts}.",
        f"The last answer was: {last_answer or 'none yet'}.",
        f"The hint already given is {hint_tier or 'nudge'}.",
        f"The child seems {affect}." if affect else "No affect is recorded yet.",
        "The child has asked for help." if help_requested else "The child has not asked for help.",
        f"Off-course turns so far: {off_course_count}.",
        f"Recent messages: {last_messages or 'none yet'}.",
        (
            f"The last matched wrong move was: {last_misconception}."
            if last_misconception
            else "No wrong move has matched yet."
        ),
        f"Reveals used so far: {reveals}.",
        f"Extra turns on this move so far: {enrichment_turns}.",
        "Points already counted: " + (", ".join(rubric_met) if rubric_met else "none") + ".",
        "A redirect is already pending." if redirect_pending else "No redirect is pending.",
    ]
    if (component_status or "").strip():
        lines.append(f"This component is {component_status}.")
    return lines


def _what_to_return() -> list[str]:
    return [
        "Return reply, decision, rubric_met, misconception, hint_tier, help_requested, off_course, affect, and confidence.",
        "reply is the text the child reads.",
        (
            "decision is stay, advance, complete, or redirect. "
            "stay keeps this component, including when the child talks further after a pass. "
            "advance goes to the next move. complete ends the unit. "
            "redirect only names a stored wrong move. The app decides whether a redirect is allowed."
        ),
        "rubric_met lists the point ids named above, and only the ones the answer holds. Leave it empty when this move is not checked.",
        "misconception is the stored wrong move that matched, or null.",
        "hint_tier is the hint this reply used: nudge, analogy, scaffold, or reveal.",
        "help_requested is true when the child asked for help. off_course is true when the answer left this component.",
        "affect is engaged, stuck, guessing, or frustrated. confidence is low, ok, or high.",
        "You do not set the type, the edges, the score, or the step index.",
    ]


def _blocks(sections: list[tuple[str, list[str]]]) -> str:
    chunks: list[str] = []
    for title, lines in sections:
        body = [line.strip() for line in lines if line and line.strip()]
        chunks.append("\n".join([title, *body]))
    return "\n\n".join(chunks)


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
    # Stability stays on the debug panel. It is not a rule for this reply.
    del stability
    labels = moves or [Move("this", "This step", (), False)]
    index = min(max(step, 0), len(labels) - 1)
    move = labels[index]
    include_close = index >= len(labels) - 1 or unit_complete or course_complete
    level = min(5, max(1, int(profile.instructive)))
    window_name = effective_window_name(profile, goal)
    enrichment = effective_enrichment(profile, goal)
    explain = self_explanation_on(profile)
    interests = ", ".join(str(item) for item in (student.interests or []) if str(item).strip()) or "none named"
    prompt = _blocks(
        [
            (
                "This turn",
                _this_turn(
                    node=node,
                    move=move,
                    moves=labels,
                    index=index,
                    total=len(labels),
                    opening=opening,
                    unit_complete=unit_complete,
                    course_complete=course_complete,
                    choice_on_screen=choice_on_screen or move.choice,
                    fragment=fragment,
                    explain=explain,
                    level=level,
                    kind=goal.kind or "mastery",
                    others_known=others_known,
                    course_title=goal.title,
                ),
            ),
            (
                "What to teach",
                _what_to_teach(
                    node=node,
                    goal=goal,
                    move=move,
                    anti_spoiler=bool(profile.anti_spoiler),
                    prerequisite_status=prerequisite_status,
                    course_position=course_position,
                ),
            ),
            ("Who you are talking to", [_learner_sentence(student, profile, move, interests)]),
            (
                "How to teach",
                _how_to_teach(
                    profile=profile,
                    node=node,
                    goal=goal,
                    move=move,
                    moves=labels,
                    level=level,
                    window_name=window_name,
                    enrichment=enrichment,
                    support_band=support_band,
                    prerequisite_status=prerequisite_status,
                    choice_on_screen=choice_on_screen or move.choice,
                    minutes_used=minutes_used,
                    has_misconceptions=bool(_wrong_moves(node)),
                    anti_spoiler=bool(profile.anti_spoiler),
                    include_close=include_close,
                ),
            ),
            ("How to sound", [_voice_paragraph(profile)]),
            (
                "What just happened",
                _what_happened(
                    attempts=attempts,
                    hint_tier=hint_tier,
                    reveals=reveals,
                    off_course_count=off_course_count,
                    affect=affect,
                    enrichment_turns=enrichment_turns,
                    help_requested=help_requested,
                    component_status=component_status,
                    last_answer=last_answer,
                    last_misconception=last_misconception,
                    last_messages=last_messages,
                    rubric_met=rubric_met,
                    redirect_pending=redirect_pending,
                ),
            ),
            ("What to return", _what_to_return()),
        ]
    )
    return {
        "system_prompt": prompt,
        "response_schema": RESPONSE_SCHEMA,
        "temperature": TEMPERATURE,
    }

