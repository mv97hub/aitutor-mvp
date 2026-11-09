"""Modular Block Prompt Assembler for KC Tutor.

Assembles the seven instruction sections strictly for the currently active
block (`node.blocks[step]`) and its active `substep`:
1. This turn
2. What to teach
3. Who you are talking to
4. How to teach
5. How to sound
6. What just happened
7. What to return

Later blocks in `node.blocks` are never included in middle-turn prompts so the
model cannot bundle topics, jump ahead, or close the unit early.
"""

from __future__ import annotations

from app.engine.choices import METAPHORS, PERSONAS, SIDEKICKS, VOICES
from app.kc_model import BLOCK_LABELS
from app.models import ALL_BLOCK_TYPES, KcGoal, KcNode, Student, TutorProfile
from app.tutor_profile import effective_kc_tutor_config

TEMPERATURE = 0.4
HINTS = ("nudge", "analogy", "scaffold", "reveal")
DECISIONS = ("stay", "advance", "complete", "redirect")
AFFECTS = ("engaged", "stuck", "guessing", "frustrated")
CONFIDENCE = ("low", "ok", "high")

SUBSTEP_LABELS: dict[str, str] = {
    "main": "",
    "choice": "Choose Option",
    "awaiting_why": "Explain Why",
    "predict": "Predict",
    "contrast_and_rule": "Contrast & Rule",
    "transfer": "Transfer",
    "initial_thesis": "Initial Position",
    "counterexample_probe": "Counterexample Probe",
    "hook_and_predict": "Wonder & Predict",
    "faded_step": "Faded Step",
    "solo_solve": "Solo Problem",
    "critique": "Identify & Fix",
    "initial_explanation": "Peer Explanation",
    "peer_follow_up": "Peer Follow-Up",
    "recall": "Cued Recall",
    "elaborate_why": "Elaborative Why",
}

_GENERATED_MCQ_SCHEMA = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "properties": {
        "question_stem": {"type": "string"},
        "choices": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["id", "text"],
            },
        },
        "correct_index": {"type": "integer"},
        "distractor_rationales": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["question_stem", "choices", "correct_index", "distractor_rationales"],
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
        "substep_passed": {
            "type": "boolean",
            "description": "True when the learner's answer satisfies the active substep's acceptance criteria.",
        },
        "block_complete": {
            "type": "boolean",
            "description": "True when the active block's final substep is satisfied and ready to advance.",
        },
        "generated_mcq": _GENERATED_MCQ_SCHEMA,
        "rubric_met": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ids of the evidence points met on this block.",
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
        "score_justification": {"type": "string"},
        "what_was_strong": {"type": "string"},
        "what_to_work_on": {"type": "string"},
    },
    "required": [
        "reply",
        "decision",
        "substep_passed",
        "block_complete",
        "generated_mcq",
        "rubric_met",
        "misconception",
        "hint_tier",
        "help_requested",
        "off_course",
        "affect",
        "confidence",
        "score_justification",
        "what_was_strong",
        "what_to_work_on",
    ],
}

_EXPLAIN = {
    1: "Ask the question first with almost no preliminary explanation (Socratic).",
    2: "Give one short framing sentence, then ask the question.",
    3: "Give a balanced 2-3 sentence explanation with an example, then ask the question.",
    4: "Explain the concept and why it matters with a concrete example, then ask.",
    5: "Teach thoroughly with step-by-step scaffolding and an example before asking the question.",
}


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


def is_fragment(answer: str, target_text: str = "") -> bool:
    """True when the learner answered with a bare 1-2 word fragment."""
    answer_words = [word for word in (answer or "").split() if word.strip()]
    if not answer_words:
        return False
    if target_text:
        target_words = [word for word in target_text.split() if word.strip()]
        if len(target_words) <= 2:
            return False
    return 0 < len(answer_words) <= 2


def stored_outline(node: KcNode) -> str:
    return str(getattr(node, "outline", "") or "").strip()


def stored_blocks(node: KcNode | None) -> list[dict]:
    """Return normalized blocks for a component."""
    if node is None:
        return []
    raw = getattr(node, "blocks", None)
    if isinstance(raw, list) and raw:
        valid: list[dict] = []
        for idx, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                continue
            btype = str(item.get("type") or "").strip()
            if btype not in ALL_BLOCK_TYPES:
                continue
            bid = str(item.get("id") or f"blk_{idx}").strip() or f"blk_{idx}"
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            valid.append({"id": bid, "type": btype, "data": dict(data)})
        if valid:
            return valid
    return []


def default_substep_for_block(block: dict, cfg: dict | None = None) -> str:
    """Return the initial substep when entering a block."""
    btype = str(block.get("type") or "topic_goal").strip()
    bcfg = ((cfg or {}).get("blocks") or {}).get(btype) or {}
    if btype == "topic_goal":
        return "main"
    if btype == "mcq":
        return "choice"
    if btype == "case_study":
        pres = str(bcfg.get("case_presentation") or "sequential_predict_then_contrast")
        if pres == "side_by_side_single_turn":
            return "contrast_and_rule"
        return "predict"
    if btype == "socratic":
        return "initial_thesis"
    if btype == "curiosity":
        return "hook_and_predict"
    if btype == "worked_example":
        return "faded_step"
    if btype == "spot_the_flaw":
        return "critique"
    if btype == "teach_back":
        return "initial_explanation"
    if btype == "retrieval_check":
        return "recall"
    return "main"


def substeps_for_block(block: dict, cfg: dict | None = None) -> list[str]:
    """Ordered substeps for a block under the active tutor configuration."""
    btype = str(block.get("type") or "topic_goal").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    bcfg = ((cfg or {}).get("blocks") or {}).get(btype) or {}
    if btype == "topic_goal":
        return ["main"]
    if btype == "mcq":
        confirm = str(bcfg.get("confirm_why_on_correct") or "on_retry_only")
        if confirm == "always":
            return ["choice", "awaiting_why"]
        return ["choice"]
    if btype == "case_study":
        pres = str(bcfg.get("case_presentation") or "sequential_predict_then_contrast")
        has_transfer = bool(str(data.get("transfer_prompt") or "").strip()) and bool(
            bcfg.get("require_transfer_application", True)
        )
        steps = ["contrast_and_rule"] if pres == "side_by_side_single_turn" else ["predict", "contrast_and_rule"]
        if has_transfer:
            steps.append("transfer")
        return steps
    if btype == "socratic":
        return ["initial_thesis", "counterexample_probe"]
    if btype == "curiosity":
        return ["hook_and_predict"]
    if btype == "worked_example":
        return ["faded_step", "solo_solve"]
    if btype == "spot_the_flaw":
        return ["critique"]
    if btype == "teach_back":
        follow_ups = int(bcfg.get("follow_up_questions_count", 1) or 0)
        if follow_ups > 0:
            return ["initial_explanation", "peer_follow_up"]
        return ["initial_explanation"]
    if btype == "retrieval_check":
        if bool(bcfg.get("require_elaborative_why", True)):
            return ["recall", "elaborate_why"]
        return ["recall"]
    return ["main"]


def format_active_substep_label(block: dict, substep: str, cfg: dict | None = None) -> str:
    """Human-readable label for multi-step blocks (e.g. 'Contrast & Rule · Substep 2 of 2')."""
    if not block or not isinstance(block, dict):
        return ""
    substeps = substeps_for_block(block, cfg)
    btype = str(block.get("type") or "topic_goal").strip()
    if btype == "mcq" and substep == "awaiting_why" and "awaiting_why" not in substeps:
        eff_substeps = ["choice", "awaiting_why"]
    else:
        eff_substeps = substeps
    if len(eff_substeps) <= 1:
        return ""
    sub_name = SUBSTEP_LABELS.get(substep or "", substep or "")
    pos = eff_substeps.index(substep) + 1 if substep in eff_substeps else 1
    total_sub = len(eff_substeps)
    if sub_name:
        return f"{sub_name} · Substep {pos} of {total_sub}"
    return f"Substep {pos} of {total_sub}"


def block_step_label(block: dict, step_index: int, total_blocks: int, substep: str = "") -> str:
    """Format 'Block {k} of {N}: {Block Type Label}' (with substep label when multi-part)."""
    btype = str(block.get("type") or "topic_goal").strip()
    type_label = BLOCK_LABELS.get(btype, btype)
    sub_label = SUBSTEP_LABELS.get(substep or "", "")
    base = f"Block {step_index + 1} of {max(1, total_blocks)}: {type_label}"
    if sub_label:
        return f"{base} · {sub_label}"
    return base


def _cached_generated_mcq(active_block_state: dict | None) -> dict | None:
    """The dynamic question stored by speech or the previous decision."""
    if not isinstance(active_block_state, dict):
        return None
    for key in ("generated_mcq", "mcq"):
        raw = active_block_state.get(key)
        if isinstance(raw, dict) and raw.get("question_stem") and isinstance(raw.get("choices"), list) and raw.get("choices"):
            return raw
    return None


def block_uses_choice_widget(
    block: dict,
    substep: str,
    active_block_state: dict | None = None,
) -> bool:
    """True when this substep has choices the learner can pick on screen."""
    btype = str(block.get("type") or "").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    if btype == "mcq" and substep in {"", "choice"}:
        mode = str(data.get("mode") or "static").strip()
        if mode == "dynamic":
            return _cached_generated_mcq(active_block_state) is not None
        raw = data.get("choices") if isinstance(data.get("choices"), list) else []
        labeled = [
            item
            for item in raw
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
        return len(labeled) >= 2
    if btype == "case_study" and substep == "predict":
        return bool(str(data.get("case_a") or "").strip() and str(data.get("case_b") or "").strip())
    return False


def on_screen_choice(
    block: dict,
    substep: str,
    active_block_state: dict | None = None,
    cfg: dict | None = None,
) -> dict | None:
    """The choice card for the active block, or nothing when this substep is typed."""
    if not block_uses_choice_widget(block, substep, active_block_state):
        return None
    btype = str(block.get("type") or "").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    state = active_block_state if isinstance(active_block_state, dict) else {}
    bcfg = ((cfg or {}).get("blocks") or {}).get(btype) or {}
    if btype == "mcq":
        mode = str(data.get("mode") or "static").strip()
        if mode == "dynamic":
            generated = _cached_generated_mcq(state) or {}
            stem = str(generated.get("question_stem") or "").strip()
            raw = generated.get("choices") if isinstance(generated.get("choices"), list) else []
        else:
            stem = str(data.get("question_stem") or "").strip()
            raw = data.get("choices") if isinstance(data.get("choices"), list) else []
        eliminated: set[int] = set()
        mcq_state = state.get("mcq") if isinstance(state.get("mcq"), dict) else {}
        if bool(bcfg.get("disable_eliminated_choices", True)):
            for item in mcq_state.get("eliminated_indices") or []:
                try:
                    eliminated.add(int(item))
                except (TypeError, ValueError):
                    continue
        choices: list[dict] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict) or index in eliminated:
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            choices.append({"id": str(item.get("id") or chr(ord("a") + index)), "text": text})
        if len(choices) < 2 or not stem:
            return None
        return {"prompt": stem, "choices": choices}
    prompt = str(data.get("prediction_prompt") or "Which case fits?").strip()
    return {
        "prompt": prompt,
        "choices": [
            {"id": "case-a", "text": str(data.get("case_a") or "").strip()},
            {"id": "case-b", "text": str(data.get("case_b") or "").strip()},
        ],
    }


def block_evidence_id(block: dict, step_index: int, substep: str = "") -> str:
    bid = str(block.get("id") or f"blk_{step_index + 1}").strip()
    btype = str(block.get("type") or "topic_goal").strip()
    if btype == "curiosity":
        return f"{bid}:engaged"
    if substep and substep not in {"main", "choice", "critique"}:
        return f"{bid}:{substep}"
    return bid


def max_retries_for_block(block: dict, cfg: dict, goal: KcGoal | None = None) -> int:
    if goal is not None and goal.kind == "time_boxed":
        return 1
    btype = str(block.get("type") or "topic_goal").strip()
    bcfg = ((cfg or {}).get("blocks") or {}).get(btype) or {}
    if btype == "mcq":
        return max(1, int(bcfg.get("max_retry_attempts", 2) or 2))
    if btype == "curiosity":
        return max(1, int(bcfg.get("max_wonder_turns", 2) or 2))
    return max(1, int(bcfg.get("max_retries_before_reveal", 2) or 2))


def block_material_summary(block: dict, substep: str = "") -> str:
    """Readable summary of the active block's content for debug panel & preview."""
    btype = str(block.get("type") or "topic_goal").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    if btype == "topic_goal":
        topic = str(data.get("topic") or "").strip()
        goal = str(data.get("goal") or "").strip()
        return f"Topic: {topic} | Goal: {goal}".strip(" |")
    if btype == "mcq":
        mode = str(data.get("mode") or "static").strip()
        if mode == "dynamic":
            return f"Dynamic MCQ: {data.get('target_skill') or ''} ({data.get('difficulty') or 'standard'})"
        return f"Static MCQ: {data.get('question_stem') or ''}"
    if btype == "case_study":
        return (
            f"Case A: {data.get('case_a') or ''} | Case B: {data.get('case_b') or ''} | "
            f"Principle: {data.get('invariant_principle') or ''}"
        )
    if btype == "socratic":
        return f"Dilemma: {data.get('central_dilemma') or ''} | Synthesis: {data.get('target_synthesis') or ''}"
    if btype == "curiosity":
        return f"Hook: {data.get('phenomenon_hook') or ''} | Bridge: {data.get('bridge_to_unit') or ''}"
    if btype == "worked_example":
        return f"Problem: {data.get('problem_statement') or ''} | Solo: {data.get('solo_problem') or ''}"
    if btype == "spot_the_flaw":
        return f"Rookie work: {data.get('rookie_work') or ''} | Correction: {data.get('corrected_version') or ''}"
    if btype == "teach_back":
        return f"Peer prompt: {data.get('peer_persona_prompt') or ''}"
    if btype == "retrieval_check":
        return f"Recall: {data.get('recall_prompt') or ''} | Fact: {data.get('expected_fact') or ''}"
    return str(data)


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


def _finish(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


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
        "That voice does not change the block, the expected answer, or the score."
    )


def _learner_sentence(
    student: Student,
    profile: TutorProfile,
    block: dict,
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
    btype = str(block.get("type") or "").strip()
    if modality.lower() == "visual" and btype in {"case_study", "worked_example", "spot_the_flaw"}:
        parts.append("You may ask for a described picture on this block because it already has cases or steps.")
    elif modality.lower() == "visual":
        parts.append("Stay in words on this block.")
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


def _close_summary_sentence(close_depth: str, kind: str) -> str:
    if kind == "time_boxed" or close_depth == "concise":
        return "Keep the unit close to one or two concise sentences."
    if close_depth == "restate_in_learner_words":
        return "Restate the takeaway in the learner's own words, then state where the unit stands."
    return (
        "Restate the takeaway in the learner's words, name what was strong and what to work on next, "
        "and fill score_justification, what_was_strong, and what_to_work_on."
    )


def _close_body() -> str:
    return (
        "A known unit says the unit is complete, names this component, and says what the child can now do. "
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
    close_depth: str,
    kind: str,
    unit_complete: bool,
    course_complete: bool,
    others_known: bool,
    course_title: str,
    is_final_block_and_substep: bool,
) -> str:
    if not is_final_block_and_substep and not unit_complete and not course_complete:
        return (
            "Mid-Unit Contract: Advance substep or next block when satisfied. "
            "The unit is not finished. This reply must NEVER say the unit is complete. "
            "Do not say this component is finished."
        )
    length = _close_summary_sentence(close_depth, kind)
    close = _close_body()
    summary = (
        "Summarize what the learner can now do. Name what was strong and what to practice. "
        "Do not ask a new question."
    )
    if course_complete:
        lead = "Close Contract: End the unit and the course in this reply."
    elif unit_complete:
        lead = "Close Contract: End the unit in this reply."
    else:
        lead = "Close Contract: When the decision ends the unit on this final substep, include the unit close."
    close = " ".join((close, summary))
    outro = _outro_sentence(others_known, course_title, required=course_complete)
    return " ".join(part for part in (lead, length, close, outro) if part)


def _this_turn(
    *,
    node: KcNode,
    block: dict,
    step_index: int,
    total_blocks: int,
    substep: str,
    opening: bool,
    orient_framing: str,
    unit_complete: bool,
    course_complete: bool,
    choice_on_screen: bool,
    fragment: bool,
    fragment_self_explanation: bool,
    close_depth: str,
    kind: str,
    others_known: bool,
    course_title: str,
    is_final_block_and_substep: bool,
    transition_from_block: dict | None = None,
    needs_dynamic_mcq: bool = False,
) -> list[str]:
    label = block_step_label(block, step_index, total_blocks, substep)
    mode_note = "The child will pick on screen." if choice_on_screen else "The child will type."
    lines = [
        "You are the knowledge-component tutor.",
        f"Active step: {label}. {mode_note}",
    ]
    outline = stored_outline(node)
    if opening and step_index == 0:
        eff_orient = "brief_hook" if kind == "time_boxed" else orient_framing
        if outline and eff_orient == "elaborate_outline":
            lines.append(
                f"Turn 1 Zero Dead Turns: Begin with a 2-sentence elaboration of the component outline ({_finish(outline)}), "
                "and immediately open Block 1 in the same reply so Turn 1 ends with Block 1's question or choice prompt."
            )
        elif outline and eff_orient == "brief_hook":
            lines.append(
                f"Turn 1 Zero Dead Turns: Begin with a 1-sentence hook from the component outline ({_finish(outline)}), "
                "and immediately open Block 1 in the same reply."
            )
        else:
            lines.append("Turn 1 Zero Dead Turns: Open Block 1 directly with its question or choice prompt.")
    if transition_from_block is not None:
        prev_type = BLOCK_LABELS.get(str(transition_from_block.get("type") or ""), "previous block")
        lines.append(
            f"Block Transition: The learner just completed Block {step_index} ({prev_type}). "
            f"Briefly affirm their work on that block and immediately introduce {label} in this same reply."
        )
    if needs_dynamic_mcq:
        lines.append(
            "Dynamic MCQ Generation Required: Populate `generated_mcq` with a fresh question_stem, choices (a, b, c, ...), "
            "correct_index, and distractor_rationales matching the active MCQ block's target_skill and distractor_guidance."
        )
    if fragment and fragment_self_explanation and str(block.get("type")) == "topic_goal" and not (unit_complete or course_complete):
        lines.append(
            "The learner answered with a 1-2 word fragment. Ask one follow-up to state the idea in a complete sentence before completing this block."
        )
    if choice_on_screen:
        pick = "The child picks the choice on screen. Do not add a separate question beside it."
        if is_final_block_and_substep or unit_complete or course_complete:
            pick += " A unit close or course outro asks no new question."
        lines.append(pick)
    lines.append(
        _ending(
            close_depth=close_depth,
            kind=kind,
            unit_complete=unit_complete,
            course_complete=course_complete,
            others_known=others_known,
            course_title=course_title,
            is_final_block_and_substep=is_final_block_and_substep,
        )
    )
    return lines


def _what_to_teach(
    *,
    node: KcNode,
    block: dict,
    step_index: int,
    substep: str,
    active_block_state: dict,
    next_block: dict | None = None,
) -> list[str]:
    """Strict block isolation: injects ONLY the currently active block and its active substep."""
    btype = str(block.get("type") or "topic_goal").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    ev_id = block_evidence_id(block, step_index, substep)
    lines: list[str] = [f"Active block type: {btype} ({BLOCK_LABELS.get(btype, btype)})."]

    if btype == "topic_goal":
        topic = str(data.get("topic") or node.title).strip()
        goal = str(data.get("goal") or node.core_truth).strip()
        criteria = str(data.get("acceptance_criteria") or goal).strip()
        notes = str(data.get("teaching_notes") or "").strip()
        lines.append(f"Topic to introduce: {_finish(topic)}")
        lines.append(f"Learning goal the learner must explain in their own words: {_finish(goal)}")
        lines.append(f"Acceptance criteria to check ( withhold until pass or reveal ): {_finish(criteria)}")
        if notes:
            lines.append(f"Teaching notes: {_finish(notes)}")

    elif btype == "mcq":
        mode = str(data.get("mode") or "static").strip()
        cached_mcq = _cached_generated_mcq(active_block_state)
        if mode == "static":
            stem = str(data.get("question_stem") or "").strip()
            choices = data.get("choices") if isinstance(data.get("choices"), list) else []
            lines.append(f"Static MCQ stem: {_finish(stem)}")
            for idx, ch in enumerate(choices):
                if isinstance(ch, dict):
                    cid = ch.get("id") or chr(ord("a") + idx)
                    ctext = ch.get("text") or ""
                    corr = " (CORRECT - withhold until solved or max retries)" if ch.get("is_correct") else ""
                    rat = f" [Trap rationale: {ch.get('distractor_rationale')}]" if ch.get("distractor_rationale") else ""
                    lines.append(f"Option {cid}: {ctext}{corr}{rat}")
            if data.get("correct_explanation"):
                lines.append(f"Correct explanation takeaway: {_finish(str(data.get('correct_explanation')))}")
        else:
            skill = str(data.get("target_skill") or "").strip()
            diff = str(data.get("difficulty") or "standard").strip()
            n_choices = int(data.get("num_choices") or 4)
            guidance = str(data.get("distractor_guidance") or "").strip()
            constraints = str(data.get("stem_constraints") or "").strip()
            lines.append(f"Dynamic MCQ target skill: {_finish(skill)}")
            lines.append(f"Difficulty: {diff}. Number of choices: {n_choices}.")
            lines.append(f"Distractor guidance: {_finish(guidance)}")
            if constraints:
                lines.append(f"Stem constraints: {_finish(constraints)}")
            if isinstance(cached_mcq, dict) and cached_mcq.get("question_stem"):
                lines.append(f"Active generated stem: {_finish(str(cached_mcq.get('question_stem')))}")
        if substep == "awaiting_why":
            lines.append(
                "Active substep: awaiting_why. The learner picked the right option on a retry; "
                "ask them to explain in one sentence WHY that option works."
            )

    elif btype == "case_study":
        case_a = str(data.get("case_a") or "").strip()
        case_b = str(data.get("case_b") or "").strip()
        pred = str(data.get("prediction_prompt") or "").strip()
        principle = str(data.get("invariant_principle") or "").strip()
        t_prompt = str(data.get("transfer_prompt") or "").strip()
        t_exp = str(data.get("transfer_expected") or "").strip()
        lines.append(f"Case A: {_finish(case_a)}")
        lines.append(f"Case B: {_finish(case_b)}")
        if substep == "predict":
            lines.append(f"Active substep (predict): Present Case A and Case B with prediction prompt: {_finish(pred)}")
            lines.append(
                "Do not reveal the invariant principle yet. Once the learner predicts (substep_passed=true), "
                "ask them to contrast the two cases and state the underlying invariant principle."
            )
        elif substep == "transfer":
            lines.append(f"Active substep (transfer): Present transfer scenario: {_finish(t_prompt)}")
            lines.append(f"Expected transfer application: {_finish(t_exp or principle)}")
        else:
            lines.append(f"Prediction / comparison prompt: {_finish(pred)}")
            lines.append(
                f"Active substep (contrast_and_rule): Ask the learner to contrast the cases and articulate the invariant principle. "
                f"Target invariant principle (withhold until pass or reveal): {_finish(principle)}"
            )
            if t_prompt:
                lines.append(
                    f"If the learner satisfies the invariant principle on this turn (substep_passed=true) and transfer is enabled, "
                    f"introduce the transfer prompt: {_finish(t_prompt)}"
                )

    elif btype == "socratic":
        dilemma = str(data.get("central_dilemma") or "").strip()
        probe = str(data.get("initial_probe") or "").strip()
        counters = [str(c).strip() for c in (data.get("counterexamples") or []) if str(c).strip()]
        synthesis = str(data.get("target_synthesis") or "").strip()
        lines.append(f"Central dilemma: {_finish(dilemma)}")
        if substep == "initial_thesis":
            lines.append(f"Active substep (initial_thesis): Frame the dilemma and ask opening probe: {_finish(probe)}")
            lines.append(
                "Any substantive initial hypothesis passes this substep (substep_passed=true); "
                "in your reply, introduce the first counterexample from: " + "; ".join(counters)
            )
        else:
            lines.append(
                "Active substep (counterexample_probe): Pressure-test the learner's position using counterexample(s): "
                + "; ".join(counters)
            )
            lines.append(f"Target synthesis resolution (withhold until pass or reveal): {_finish(synthesis)}")

    elif btype == "curiosity":
        hook = str(data.get("phenomenon_hook") or "").strip()
        q = str(data.get("prediction_question") or "").strip()
        bridge = str(data.get("bridge_to_unit") or "").strip()
        branches = [str(b).strip() for b in (data.get("wonder_branches") or []) if str(b).strip()]
        lines.append(f"Phenomenon / mystery hook: {_finish(hook)}")
        lines.append(f"Initial prediction question: {_finish(q)}")
        lines.append(f"Bridge to unit insight (share after learner engages/guesses): {_finish(bridge)}")
        if branches:
            lines.append("Optional wonder branches: " + "; ".join(branches))

    elif btype == "worked_example":
        prob = str(data.get("problem_statement") or "").strip()
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        faded_idx = int(data.get("faded_step_index") or 0)
        solo_prob = str(data.get("solo_problem") or "").strip()
        solo_ans = str(data.get("solo_expected_answer") or "").strip()
        lines.append(f"Worked example problem: {_finish(prob)}")
        if substep == "faded_step":
            shown: list[str] = []
            target_step = ""
            for idx, st in enumerate(steps):
                st_text = st.get("step_text") if isinstance(st, dict) else str(st)
                st_rat = st.get("rationale") if isinstance(st, dict) else ""
                if idx == faded_idx:
                    shown.append(f"Step {idx + 1}: ___ (FADED)")
                    target_step = f"{st_text} (Rationale: {st_rat})" if st_rat else str(st_text)
                else:
                    shown.append(f"Step {idx + 1}: {st_text}" + (f" ({st_rat})" if st_rat else ""))
            lines.append("Worked steps: " + " | ".join(shown))
            lines.append(
                f"Active substep (faded_step): Ask the learner to supply the missing Step {faded_idx + 1}. "
                f"Expected missing step (withhold until pass or reveal): {_finish(target_step)}"
            )
            if solo_prob:
                lines.append(
                    f"When the faded step is solved (substep_passed=true) or revealed, present the solo problem in your reply: {_finish(solo_prob)}"
                )
        else:
            lines.append(f"Active substep (solo_solve): Ask the learner to solve solo problem: {_finish(solo_prob)}")
            lines.append(f"Expected solo answer (withhold until pass or reveal): {_finish(solo_ans)}")

    elif btype == "spot_the_flaw":
        rookie = str(data.get("rookie_work") or "").strip()
        flaw = str(data.get("flaw_description") or "").strip()
        misc = str(data.get("underlying_misconception") or "").strip()
        corr = str(data.get("corrected_version") or "").strip()
        lines.append(f"Rookie's flawed work / claim: {_finish(rookie)}")
        lines.append(f"Flaw description to identify (withhold until pass or reveal): {_finish(flaw)}")
        lines.append(f"Underlying misconception: {_finish(misc)}")
        lines.append(f"Corrected version (withhold until pass or reveal): {_finish(corr)}")

    elif btype == "teach_back":
        persona_prompt = str(data.get("peer_persona_prompt") or "").strip()
        reqs = [str(r).strip() for r in (data.get("required_concepts") or []) if str(r).strip()]
        follow = str(data.get("peer_follow_up_question") or "").strip()
        lines.append(f"Naive peer persona & confusion prompt: {_finish(persona_prompt)}")
        lines.append("Required concepts the learner must weave into their explanation: " + "; ".join(reqs))
        if substep == "peer_follow_up":
            lines.append(
                f"Active substep (peer_follow_up): Ask peer follow-up question or probe missing concepts: {_finish(follow)}"
            )
        else:
            lines.append(
                "Active substep (initial_explanation): Roleplay the confused peer and invite the learner's explanation. "
                f"If follow-up is needed after their first explanation, ask: {_finish(follow)}"
            )

    elif btype == "retrieval_check":
        recall_p = str(data.get("recall_prompt") or "").strip()
        exp_fact = str(data.get("expected_fact") or "").strip()
        why_p = str(data.get("elaborative_why_prompt") or "").strip()
        why_rat = str(data.get("expected_why_rationale") or "").strip()
        if substep == "elaborate_why":
            lines.append(f"Recalled fact already established: {_finish(exp_fact)}")
            lines.append(f"Active substep (elaborate_why): Ask elaborative why prompt: {_finish(why_p)}")
            lines.append(f"Expected why rationale (withhold until pass or reveal): {_finish(why_rat)}")
        else:
            lines.append(f"Active substep (recall): Ask cued-recall question: {_finish(recall_p)}")
            lines.append(f"Expected fact (withhold until pass or reveal): {_finish(exp_fact)}")
            if why_p:
                lines.append(
                    f"When the learner recalls the fact (substep_passed=true) and elaborative why is enabled, "
                    f"affirm the fact and ask: {_finish(why_p)}"
                )

    lines.append(f"Evidence id for this active step: {ev_id}. Include '{ev_id}' in rubric_met when satisfied.")
    if next_block is not None and isinstance(next_block, dict):
        nb_type = str(next_block.get("type") or "topic_goal").strip()
        nb_data = next_block.get("data") if isinstance(next_block.get("data"), dict) else {}
        lines.append(
            f"If the learner's response completes Block {step_index + 1} (block_complete=true), "
            f"affirm Block {step_index + 1} and open Block {step_index + 2} ({BLOCK_LABELS.get(nb_type, nb_type)}): "
            f"{block_material_summary(next_block)}."
        )
        if nb_type == "mcq" and str(nb_data.get("mode") or "static") == "dynamic":
            lines.append(
                f"For Block {step_index + 2} (dynamic MCQ), populate generated_mcq for target_skill="
                f"{_finish(str(nb_data.get('target_skill') or ''))} and distractor_guidance="
                f"{_finish(str(nb_data.get('distractor_guidance') or ''))}"
            )
    wrongs = _wrong_moves(node)
    if wrongs:
        lines.append("Component misconceptions to listen for: " + " | ".join(_finish(w) for w in wrongs))
    return lines


def _retry_sentence(count: int, subject: str) -> str:
    if count <= 1:
        return f"Reveal {subject} after one missed answer."
    return f"Reveal {subject} after {count} missed answers."


def _depth_sentence(depth: int) -> str:
    bounded = min(5, max(1, int(depth or 3)))
    return _EXPLAIN.get(bounded, _EXPLAIN[3])


def _block_config_rules(block: dict, substep: str, cfg: dict, goal: KcGoal) -> list[str]:
    """Plain instructions for the active block type. No setting names."""
    btype = str(block.get("type") or "topic_goal").strip()
    bcfg = ((cfg.get("blocks") or {}).get(btype)) or {}
    lines: list[str] = []
    timed = goal.kind == "time_boxed"

    if btype == "topic_goal":
        depth = int(bcfg.get("explanation_depth", 3) or 3)
        retries = 1 if timed else int(bcfg.get("max_retries_before_reveal", 3) or 3)
        ladder = str(bcfg.get("hint_ladder_style") or "progressive_nudge_analogy_scaffold")
        strictness = str(bcfg.get("goal_evaluation_strictness") or "conceptual_gist")
        frag_exp = bool(bcfg.get("fragment_self_explanation", True))
        enrich = "direct" if timed else str(bcfg.get("enrichment_mode") or "on_request")
        lines.append(f"How to explain this goal: {_depth_sentence(depth)}")
        ladders = {
            "socratic_questions_only": (
                "When the learner is stuck, ask another question. Do not explain the goal until you reveal it."
            ),
            "direct_scaffold": (
                "When the learner is stuck, give the next piece of the idea directly, then reveal the goal if they are still stuck."
            ),
        }
        lines.append(
            ladders.get(
                ladder,
                "When the learner is stuck, start with a nudge, then an analogy, then a scaffold, and reveal the goal only after those hints.",
            )
        )
        lines.append(_retry_sentence(retries, "the goal"))
        strict = {
            "precise_vocabulary": "Accept an answer only when it uses the important words of the goal.",
            "applied_transfer": "Accept an answer only when it uses the goal on a new case, not when it only repeats the goal.",
        }
        lines.append(
            strict.get(strictness, "Accept an answer that carries the idea of the goal, even when the wording is different.")
        )
        if frag_exp:
            lines.append(
                "If the answer is only one or two words, ask for the idea in a full sentence before this block can pass."
            )
        else:
            lines.append("A one or two word answer can pass when it already states the goal.")
        enrichments = {
            "direct": "When the goal is met, add a short enrichment in the same reply. Do not wait to be asked.",
            "offer": "After the goal is met, ask whether the learner wants one extra example, and wait for a yes.",
        }
        lines.append(enrichments.get(enrich, "Wait until the learner asks before you add anything beyond the goal."))

    elif btype == "mcq":
        retries = 1 if timed else int(bcfg.get("max_retry_attempts", 2) or 2)
        w_depth = int(bcfg.get("wrong_answer_explanation_depth", 2) or 2)
        disable_elim = bool(bcfg.get("disable_eliminated_choices", True))
        confirm_why = str(bcfg.get("confirm_why_on_correct") or "on_retry_only")
        pass_depth = str(bcfg.get("correct_pass_explanation_depth") or "reinforce_why")
        lines.append(_retry_sentence(retries, "the correct option"))
        wrongs = {
            1: "On a wrong pick, give a brief nudge about what to re-check. Do not explain why that option is wrong, and do not name the right option.",
            3: "On a wrong pick, contrast that option with the idea using a short example. Do not name the right option.",
        }
        lines.append(
            wrongs.get(
                w_depth,
                "On a wrong pick, say why that option is a trap. Do not give away the right option.",
            )
        )
        if disable_elim:
            lines.append("Take a wrong choice off the screen so the learner cannot pick it again.")
        else:
            lines.append("Leave a wrong choice on the screen. The learner may pick it again.")
        whys = {
            "never": "A correct pick ends this block. Do not ask why that option is right.",
            "always": "A correct pick must include why that option is right before this block ends.",
        }
        lines.append(
            whys.get(
                confirm_why,
                "If the first pick is correct, end this block. If the learner needed another try, ask why that option is right before the block ends.",
            )
        )
        if pass_depth == "brief_confirm":
            lines.append("When the pick is correct, confirm it in one short sentence.")
        else:
            lines.append("When the pick is correct, restate why that option fits.")
        if substep == "awaiting_why":
            lines.append("This turn is only the why. Do not ask the multiple choice again.")

    elif btype == "case_study":
        pres = str(bcfg.get("case_presentation") or "sequential_predict_then_contrast")
        depth = int(bcfg.get("explanation_depth", 3) or 3)
        retries = 1 if timed else int(bcfg.get("max_retries_before_reveal", 3) or 3)
        req_trans = bool(bcfg.get("require_transfer_application", True))
        if pres == "side_by_side_single_turn":
            lines.append("Show both cases in the same turn and ask for the rule that fits both.")
        else:
            lines.append("Show one case at a time. Ask for a prediction, then contrast the cases and ask for the rule.")
        lines.append(f"How to explain the contrast: {_depth_sentence(depth)}")
        lines.append(_retry_sentence(retries, "the principle"))
        if req_trans:
            lines.append("After the principle, ask the transfer question. This block is not done until that answer is in.")
        else:
            lines.append("Do not ask a transfer question. This block ends when the principle is stated.")

    elif btype == "socratic":
        turns = int(bcfg.get("dialogue_depth_turns", 2) or 2)
        intensity = str(bcfg.get("challenge_intensity") or "counterexample_entrapment")
        retries = 1 if timed else int(bcfg.get("max_retries_before_reveal", 3) or 3)
        hint_mode = str(bcfg.get("hint_when_stuck") or "highlight_contradiction")
        if turns <= 1:
            lines.append("Give one challenge turn, then this block can pass.")
        else:
            lines.append(f"Keep the challenge going for {turns} turns before this block can pass.")
        challenges = {
            "gentle_clarification": "Push gently. Ask the learner to make their claim clearer.",
            "devil_advocate": "Take the opposite side and make the learner defend the claim.",
        }
        lines.append(
            challenges.get(intensity, "Answer with a counterexample that makes a weak claim fail.")
        )
        lines.append(_retry_sentence(retries, "the synthesis"))
        if hint_mode == "give_analogy":
            lines.append("When the learner is stuck, give an analogy that points at the contradiction.")
        else:
            lines.append("When the learner is stuck, point at the contradiction in what they just said.")

    elif btype == "curiosity":
        w_turns = int(bcfg.get("max_wonder_turns", 2) or 2)
        req_pred = bool(bcfg.get("require_initial_prediction", True))
        counts = bool(bcfg.get("counts_toward_mastery_score", False))
        framing = str(bcfg.get("hook_framing_style") or "mystery_paradox")
        hooks = {
            "real_world_surprise": "Open with a real situation whose result is surprising.",
            "thought_experiment": "Open with a short thought experiment the learner can picture.",
        }
        lines.append(hooks.get(framing, "Open with a mystery that seems to contradict itself."))
        if w_turns <= 1:
            lines.append("Allow one wonder turn, then share the bridge and move on.")
        else:
            lines.append(f"Allow {w_turns} wonder turns, then share the bridge and move on.")
        if req_pred:
            lines.append("Ask for a prediction before you share the bridge.")
        else:
            lines.append("A prediction is optional. Share the bridge once the learner has engaged.")
        if counts:
            lines.append("This block counts toward whether the component is known or fragile.")
        else:
            lines.append("This block does not count toward known or fragile. A bold guess is not a miss.")

    elif btype == "worked_example":
        fading = str(bcfg.get("fading_level") or "single_blanked_step")
        req_why = bool(bcfg.get("require_step_self_explanation", True))
        retries = 1 if timed else int(bcfg.get("max_retries_before_reveal", 2) or 2)
        w_depth = int(bcfg.get("wrong_step_explanation_depth", 2) or 2)
        if fading == "two_steps":
            lines.append("Hide two steps of the worked solution and ask the learner to supply them.")
        else:
            lines.append("Hide one step of the worked solution and ask the learner to supply it.")
        if req_why:
            lines.append("The learner must explain why that step works, not only fill the blank.")
        else:
            lines.append("The learner only needs to fill the blank step.")
        lines.append(_retry_sentence(retries, "the missing step"))
        wrongs = {
            1: "On a wrong step, give a brief nudge and do not show the missing step.",
            3: "On a wrong step, walk through where the step went off, without showing the missing step.",
        }
        lines.append(wrongs.get(w_depth, "On a wrong step, say what to re-check. Do not show the missing step."))

    elif btype == "spot_the_flaw":
        c_depth = str(bcfg.get("critique_depth") or "identify_and_correct")
        w_depth = int(bcfg.get("wrong_answer_explanation_depth", 2) or 2)
        retries = 1 if timed else int(bcfg.get("max_retries_before_reveal", 2) or 2)
        show_why = bool(bcfg.get("show_misconception_why", True))
        if c_depth == "identify_only":
            lines.append("The learner only has to find the flaw. Do not require a correction.")
        else:
            lines.append("The learner must find the flaw and also correct it.")
        wrongs = {
            1: "On a miss, give a brief nudge toward the flaw. Do not name it.",
            3: "On a miss, contrast the rookie work with the idea. Do not hand over the correction.",
        }
        lines.append(wrongs.get(w_depth, "On a miss, point at the kind of mistake. Do not name the flaw."))
        lines.append(_retry_sentence(retries, "the flaw"))
        if show_why:
            lines.append("When you explain a miss, name the misconception that produced the flaw.")
        else:
            lines.append("When you explain a miss, stay with the flaw itself and do not name a misconception.")

    elif btype == "teach_back":
        confusion = str(bcfg.get("peer_confusion_level") or "curious_beginner")
        f_count = int(bcfg.get("follow_up_questions_count", 1) or 0)
        retries = 1 if timed else int(bcfg.get("max_retries_before_reveal", 2) or 2)
        strictness = str(bcfg.get("evaluation_strictness") or "plain_language_clarity")
        if confusion == "stubborn_misconception":
            lines.append("Play a peer who holds a wrong idea and will not drop it without a clear explanation.")
        else:
            lines.append("Play a peer who is new to the idea and asks from genuine confusion.")
        if f_count <= 0:
            lines.append("Do not ask a follow-up. The first explanation ends this block.")
        elif f_count == 1:
            lines.append("Ask one follow-up after the first explanation.")
        else:
            lines.append(f"Ask {f_count} follow-ups after the first explanation.")
        lines.append(_retry_sentence(retries, "a clear explanation"))
        if strictness == "all_required_concepts_exact":
            lines.append("Accept the explanation only when every required concept is in it.")
        else:
            lines.append("Accept a plain explanation that makes the idea clear, even if a term is missing.")

    elif btype == "retrieval_check":
        scaff = str(bcfg.get("cue_scaffolding") or "cued_hint_on_first_miss")
        req_why = bool(bcfg.get("require_elaborative_why", True))
        retries = 1 if timed else int(bcfg.get("max_retries_before_reveal", 2) or 2)
        paraphrase = bool(bcfg.get("accept_paraphrase", True))
        if scaff == "free_recall_first":
            lines.append("Ask for a free recall. Do not cue the first miss.")
        else:
            lines.append("On the first miss, give a cue and let the learner try again. Do not say the fact.")
        if req_why:
            lines.append("After the fact is recalled, ask why it is so. This block is not done until that why is in.")
        else:
            lines.append("This block ends when the fact is recalled. Do not ask why.")
        lines.append(_retry_sentence(retries, "the fact"))
        if paraphrase:
            lines.append("A paraphrase of the fact counts as a recall.")
        else:
            lines.append("The fact has to be stated in the stored words. A loose paraphrase does not count.")

    return lines


def _how_to_teach(
    *,
    node: KcNode,
    goal: KcGoal,
    block: dict,
    substep: str,
    cfg: dict,
    support_band: str,
    prerequisite_status: str,
    choice_on_screen: bool,
    minutes_used: int,
    has_misconceptions: bool,
    include_close: bool,
) -> list[str]:
    over = cfg.get("overarching") or {}
    stay_mode = str(over.get("stay_on_course") or "brief_answer_then_return")
    misc_policy = str(over.get("misconception_policy") or "explain_and_retry_once")
    praise_style = str(over.get("encouragement_style") or "process_praise")

    lines = _block_config_rules(block, substep, cfg, goal)

    if goal.kind == "time_boxed":
        budget = f" Budget: {goal.minutes} minutes ({minutes_used} used)." if goal.minutes is not None else ""
        lines.append(
            "Course kind is time_boxed: keep framing to one sentence, step hints after one miss, "
            "and advance immediately when the block passes." + budget
        )

    if stay_mode == "strict":
        lines.append(
            "Stay on this component. If the learner leaves the topic, bring them back in the same reply and do not answer the tangent."
        )
    elif stay_mode == "exploratory":
        lines.append("You may follow a short tangent, then come back to this block.")
    else:
        lines.append("Answer a tangent in one brief sentence, then return to this block.")

    if has_misconceptions:
        if misc_policy == "immediate_redirect":
            lines.append(
                "If a stored wrong move matches, name it on that same turn and set the decision to redirect."
            )
        else:
            lines.append(
                "the first time a stored wrong move matches, explain the trap and retry this block. The second time, redirect."
            )

    if support_band == "hold":
        lines.append(
            "Support band (hold): name the missing prerequisite idea and the patch card. Do not teach that other component in this chat."
        )
    elif support_band == "stretch":
        lines.append("Support band (stretch): stay on this component with extra scaffolding.")
    elif support_band == "ready" and (prerequisite_status or "").strip() not in {"", "none"}:
        lines.append("Prerequisites are known; teach this block directly.")

    if praise_style == "process_praise":
        lines.append(
            "When you encourage, name the specific reasoning move the learner made. Do not use generic praise."
        )
    else:
        lines.append("Keep any acknowledgment to a few words. Do not add praise.")

    if not choice_on_screen:
        q_line = "End a teaching or probing turn with a single clear question."
        if include_close:
            q_line += " A unit close or course outro asks no new question."
        lines.append(q_line)

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
    active_block_state: dict,
    block_results: list | None = None,
) -> list[str]:
    substep = str(active_block_state.get("substep") or "main")
    dialogue_turns = int(active_block_state.get("dialogue_turns") or 0)
    mcq_state = active_block_state.get("mcq") if isinstance(active_block_state.get("mcq"), dict) else {}
    eliminated = mcq_state.get("eliminated_indices") if isinstance(mcq_state, dict) else []
    lines = [
        "This is what already happened on the active block. Do not treat it as a new rule.",
        f"Active substep: {substep}.",
        f"Attempts on this block/substep so far: {attempts}.",
        f"Dialogue turns on this block: {dialogue_turns}.",
        f"The last answer was: {last_answer or 'none yet'}.",
        f"The hint tier already given is: {hint_tier or 'nudge'}.",
        f"Eliminated MCQ choice indices: {eliminated if eliminated else 'none'}.",
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
        f"Extra enrichment turns so far: {enrichment_turns}.",
        "Evidence points already met: " + (", ".join(rubric_met) if rubric_met else "none") + ".",
        "A redirect is already pending." if redirect_pending else "No redirect is pending.",
    ]
    if (component_status or "").strip():
        lines.append(f"This component status is {component_status}.")
    earlier = [item for item in (block_results or []) if isinstance(item, dict)]
    if earlier:
        lines.append("Earlier block assessments the learner already finished:")
        for item in earlier:
            title = str(item.get("title") or item.get("block_id") or "a block").strip()
            outcome = str(item.get("outcome") or "passed").strip()
            attempts = int(item.get("attempts") or 0)
            strong = str(item.get("strong") or "").strip() or "not noted"
            work_on = str(item.get("work_on") or "").strip() or "not noted"
            lines.append(
                f"{title}: {outcome} after {attempts} tries. What was strong: {strong}. What to work on: {work_on}."
            )
    else:
        lines.append("No earlier block has an assessment yet.")
    return lines


def _what_to_return(*, needs_dynamic_mcq: bool = False) -> list[str]:
    lines = [
        "Return reply, decision, substep_passed, block_complete, generated_mcq, rubric_met, misconception, hint_tier, help_requested, off_course, affect, confidence, score_justification, what_was_strong, and what_to_work_on.",
        "reply is the only text the child reads.",
        (
            "decision is stay, advance, complete, or redirect. "
            "Set substep_passed=true when the learner's answer satisfies the active substep. "
            "Set block_complete=true when the active block's final substep is satisfied."
        ),
        "rubric_met lists the active block evidence id when the learner's response satisfies the criteria.",
        "misconception is the stored wrong move that matched, or null.",
        "hint_tier is nudge, analogy, scaffold, or reveal.",
        "affect is engaged, stuck, guessing, or frustrated. confidence is low, ok, or high.",
        "On unit close, populate score_justification, what_was_strong, and what_to_work_on; otherwise return empty strings for those three fields.",
        "You do not set the block order, the edges, or the final mastery score.",
    ]
    if needs_dynamic_mcq:
        lines.append(
            "Because the active block is a dynamic MCQ without a cached question, you MUST populate generated_mcq with question_stem, choices, correct_index, and distractor_rationales."
        )
    else:
        lines.append("Set generated_mcq to null when not generating a new dynamic MCQ.")
    return lines


def _blocks_text(sections: list[tuple[str, list[str]]]) -> str:
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
    active_block_state: dict | None = None,
    transition_from_block: dict | None = None,
    block_results: list | None = None,
    moves: object | None = None,
) -> dict:
    """Assemble the 7-section prompt for the active block (`node.blocks[step]`)."""
    del stability
    del moves
    del course_position
    cfg = effective_kc_tutor_config(profile)
    over = cfg.get("overarching") or {}
    blocks = stored_blocks(node)
    if not blocks:
        blocks = [
            {
                "id": "blk_1",
                "type": "topic_goal",
                "data": {
                    "topic": node.title or "Concept",
                    "goal": node.core_truth or f"Explain {node.title}.",
                },
            }
        ]
    index = min(max(int(step or 0), 0), len(blocks) - 1)
    active_block = blocks[index]
    btype = str(active_block.get("type") or "topic_goal").strip()
    state_dict = dict(active_block_state or {})
    substep = str(state_dict.get("substep") or default_substep_for_block(active_block, cfg))
    state_dict["substep"] = substep
    substeps = substeps_for_block(active_block, cfg)
    is_last_block = index >= len(blocks) - 1
    is_last_substep = substep == substeps[-1] if substeps else True
    if substep == "awaiting_why":
        is_last_substep = True
    confirm_why = str(((cfg.get("blocks") or {}).get("mcq") or {}).get("confirm_why_on_correct") or "on_retry_only")
    pending_why = (
        btype == "mcq"
        and substep == "choice"
        and confirm_why == "on_retry_only"
        and int(attempts or 0) > 0
    )
    if pending_why:
        is_last_substep = False
    is_final_block_and_substep = is_last_block and is_last_substep

    data = active_block.get("data") if isinstance(active_block.get("data"), dict) else {}
    needs_dynamic_mcq = (
        btype == "mcq"
        and str(data.get("mode") or "static") == "dynamic"
        and _cached_generated_mcq(state_dict) is None
    )
    if (
        not needs_dynamic_mcq
        and index + 1 < len(blocks)
        and str(blocks[index + 1].get("type") or "") == "mcq"
        and str((blocks[index + 1].get("data") or {}).get("mode") or "static") == "dynamic"
    ):
        needs_dynamic_mcq = True
    widget_on = choice_on_screen or block_uses_choice_widget(active_block, substep, state_dict)
    include_close = is_final_block_and_substep or unit_complete or course_complete
    frag_self_exp = bool(((cfg.get("blocks") or {}).get("topic_goal") or {}).get("fragment_self_explanation", True))
    interests = ", ".join(str(item) for item in (student.interests or []) if str(item).strip()) or "none named"

    prompt = _blocks_text(
        [
            (
                "This turn",
                _this_turn(
                    node=node,
                    block=active_block,
                    step_index=index,
                    total_blocks=len(blocks),
                    substep=substep,
                    opening=opening,
                    orient_framing=str(over.get("orient_framing") or "elaborate_outline"),
                    unit_complete=unit_complete,
                    course_complete=course_complete,
                    choice_on_screen=widget_on,
                    fragment=fragment,
                    fragment_self_explanation=frag_self_exp,
                    close_depth=str(over.get("close_summary_depth") or "diagnostic_strengths_and_gaps"),
                    kind=goal.kind or "mastery",
                    others_known=others_known,
                    course_title=goal.title,
                    is_final_block_and_substep=is_final_block_and_substep,
                    transition_from_block=transition_from_block,
                    needs_dynamic_mcq=needs_dynamic_mcq,
                ),
            ),
            (
            "What to teach",
            _what_to_teach(
                node=node,
                block=active_block,
                step_index=index,
                substep=substep,
                active_block_state=state_dict,
                next_block=blocks[index + 1] if (is_last_substep and index + 1 < len(blocks)) else None,
            ),
            ),
            ("Who you are talking to", [_learner_sentence(student, profile, active_block, interests)]),
            (
                "How to teach",
                _how_to_teach(
                    node=node,
                    goal=goal,
                    block=active_block,
                    substep=substep,
                    cfg=cfg,
                    support_band=support_band,
                    prerequisite_status=prerequisite_status,
                    choice_on_screen=widget_on,
                    minutes_used=minutes_used,
                    has_misconceptions=bool(_wrong_moves(node)),
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
                    active_block_state=state_dict,
                    block_results=block_results,
                ),
            ),
            ("What to return", _what_to_return(needs_dynamic_mcq=needs_dynamic_mcq)),
        ]
    )
    return {
        "system_prompt": prompt,
        "response_schema": RESPONSE_SCHEMA,
        "temperature": TEMPERATURE,
    }


from app.kc_moves import (  # noqa: E402  (move recipes the session loop still calls)
    Move,
    asks_why,
    effective_enrichment,
    effective_window_name,
    move_material,
    moves_for,
    recipe_name,
    self_explanation_on,
    step_labels,
    stored_enrichment,
    struggle_tries,
    topic_goal,
)
