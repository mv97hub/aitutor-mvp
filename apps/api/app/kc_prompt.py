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

from app.engine.choices import (
    HUMOR_MODES,
    INTEREST_WEAVING_MODES,
    METAPHORS,
    PERSONAS,
    SIDEKICKS,
    VOCABULARY_REGISTERS,
    VOICES,
)
from app.block_catalog import BLOCK_LABELS
from app.models import (
    ALL_BLOCK_TYPES,
    DEFAULT_TUTOR_DESCRIPTION,
    INTEREST_TAG_LABELS,
    KcGoal,
    KcNode,
    Student,
    TutorProfile,
    effective_child_profile,
)
from app.tutor_profile import effective_kc_tutor_config, effective_voice_settings

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
    "explain_topic": "Explain Topic",
    "explain": "",
    "summary_check": "Summary & Final Questions",
    "central_idea": "Central Idea",
    "cite_evidence": "Cite Evidence",
    "craft_or_inference": "Craft or Inference",
}


def explanation_topics(block: dict) -> list[dict]:
    """Ordered topic entries on an explanation block."""
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    raw = data.get("topics") if isinstance(data.get("topics"), list) else []
    topics: list[dict] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        topics.append(
            {
                "id": str(item.get("id") or f"top_{index}").strip() or f"top_{index}",
                "title": str(item.get("title") or "").strip(),
                "explanation": str(item.get("explanation") or "").strip(),
                "key_points": str(item.get("key_points") or "").strip(),
                "examples_or_analogies": str(item.get("examples_or_analogies") or "").strip(),
            }
        )
    return topics


def explanation_topic_index(block: dict, state: dict | None) -> int:
    topics = explanation_topics(block)
    if not topics:
        return 0
    try:
        index = int((state or {}).get("topic_index") or 0)
    except (TypeError, ValueError):
        index = 0
    return min(max(index, 0), len(topics) - 1)


def initial_block_state(block: dict, cfg: dict | None = None) -> dict:
    """State written when a block is entered."""
    state = {"substep": default_substep_for_block(block, cfg), "dialogue_turns": 0}
    if str(block.get("type") or "").strip() == "explanation":
        state["topic_index"] = 0
        state["elaboration_turns"] = 0
    return state


def _explanation_depth(cfg: dict | None) -> int:
    bcfg = ((cfg or {}).get("blocks") or {}).get("explanation") or {}
    try:
        depth = int(bcfg.get("explanation_depth", 4) or 4)
    except (TypeError, ValueError):
        depth = 4
    return min(5, max(1, depth))


def _topic_is_rich(block: dict, state: dict | None) -> bool:
    topics = explanation_topics(block)
    if not topics:
        return False
    topic = topics[explanation_topic_index(block, state)]
    return len(f"{topic['explanation']} {topic['key_points']}".strip()) >= 180


def explanation_length_override(
    block: dict,
    cfg: dict | None,
    *,
    response_length: str,
    reading_level: str,
    explanation_style: str,
    active_block_state: dict | None = None,
) -> str:
    """The cross-layer length sentence, or empty when this turn keeps response_length."""
    if str(block.get("type") or "").strip() != "explanation":
        return ""
    bcfg = ((cfg or {}).get("blocks") or {}).get("explanation") or {}
    if not bool(bcfg.get("allow_depth_override_student_length", True)):
        return ""
    depth = _explanation_depth(cfg)
    elaborating = int((active_block_state or {}).get("elaboration_turns") or 0) > 0
    if depth < 3 and not _topic_is_rich(block, active_block_state) and not elaborating:
        return ""
    return (
        "CROSS-LAYER LENGTH OVERRIDE FOR EXPLANATORY BLOCK: Because this is a dedicated Explanatory Block "
        f"at depth {depth}/5, do NOT truncate your explanation to fit the learner's general `response_length` "
        f"(`{response_length}`) when the topic requires more sentences to explain clearly and completely. "
        "Use as many sentences or short paragraphs as needed to explain the topic well, while still keeping "
        f"each individual sentence at the learner's reading level (`{reading_level}`) and using their preferred "
        f"explanation style (`{explanation_style}`)."
    )

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
        "safety_flag": {
            "type": "string",
            "enum": [
                "none",
                "distress",
                "inappropriate_content",
                "personal_info",
                "manipulation",
                "other",
            ],
            "description": "none when the turn stays inside the lesson. Otherwise the safety category for an adult to review.",
        },
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
        "safety_flag",
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
        return "explain"
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
    if btype == "explanation":
        return "explain_topic"
    if btype == "passage_ela":
        return "central_idea"
    return "main"


def _with_summary_check(steps: list[str]) -> list[str]:
    if steps and steps[-1] == "summary_check":
        return steps
    return [*steps, "summary_check"]


def substeps_for_block(block: dict, cfg: dict | None = None) -> list[str]:
    """Ordered substeps for a block under the active tutor configuration."""
    btype = str(block.get("type") or "topic_goal").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    bcfg = ((cfg or {}).get("blocks") or {}).get(btype) or {}
    if btype == "topic_goal":
        return _with_summary_check(["explain", "main"])
    if btype == "mcq":
        confirm = str(bcfg.get("confirm_why_on_correct") or "on_retry_only")
        if confirm == "always":
            return _with_summary_check(["choice", "awaiting_why"])
        return _with_summary_check(["choice"])
    if btype == "case_study":
        pres = str(bcfg.get("case_presentation") or "sequential_predict_then_contrast")
        has_transfer = bool(str(data.get("transfer_prompt") or "").strip()) and bool(
            bcfg.get("require_transfer_application", True)
        )
        steps = ["contrast_and_rule"] if pres == "side_by_side_single_turn" else ["predict", "contrast_and_rule"]
        if has_transfer:
            steps.append("transfer")
        return _with_summary_check(steps)
    if btype == "socratic":
        return _with_summary_check(["initial_thesis", "counterexample_probe"])
    if btype == "curiosity":
        return _with_summary_check(["hook_and_predict"])
    if btype == "worked_example":
        return _with_summary_check(["faded_step", "solo_solve"])
    if btype == "spot_the_flaw":
        return _with_summary_check(["critique"])
    if btype == "teach_back":
        follow_ups = int(bcfg.get("follow_up_questions_count", 1) or 0)
        if follow_ups > 0:
            return _with_summary_check(["initial_explanation", "peer_follow_up"])
        return _with_summary_check(["initial_explanation"])
    if btype == "retrieval_check":
        if bool(bcfg.get("require_elaborative_why", True)):
            return _with_summary_check(["recall", "elaborate_why"])
        return _with_summary_check(["recall"])
    if btype == "explanation":
        return ["explain_topic", "summary_check"]
    if btype == "passage_ela":
        return ["central_idea", "cite_evidence", "craft_or_inference"]
    return _with_summary_check(["main"])


def format_active_substep_label(
    block: dict,
    substep: str,
    cfg: dict | None = None,
    active_block_state: dict | None = None,
) -> str:
    """Human-readable label for multi-step blocks (e.g. 'Contrast & Rule · Substep 2 of 2')."""
    if not block or not isinstance(block, dict):
        return ""
    btype = str(block.get("type") or "topic_goal").strip()
    if btype == "explanation":
        topics = explanation_topics(block)
        if (substep or "explain_topic") == "summary_check":
            return "Block Summary & Final Questions"
        index = explanation_topic_index(block, active_block_state)
        total = max(len(topics), 1)
        title = topics[index]["title"] if topics else ""
        head = f"Topic {index + 1} of {total}"
        return f"{head}: {title}" if title else head
    substeps = substeps_for_block(block, cfg)
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


def block_step_label(
    block: dict,
    step_index: int,
    total_blocks: int,
    substep: str = "",
    active_block_state: dict | None = None,
) -> str:
    """Format 'Block {k} of {N}: {Block Type Label}' (with substep label when multi-part)."""
    btype = str(block.get("type") or "topic_goal").strip()
    type_label = BLOCK_LABELS.get(btype, btype)
    base = f"Block {step_index + 1} of {max(1, total_blocks)}: {type_label}"
    if btype == "explanation":
        detail = format_active_substep_label(block, substep or "explain_topic", None, active_block_state)
        return f"{base} · {detail}" if detail else base
    sub_label = SUBSTEP_LABELS.get(substep or "", "")
    if sub_label:
        return f"{base} · {sub_label}"
    return base


def _presenting_dynamic_mcq(block: dict, needs_dynamic_mcq: bool, active_block_state: dict | None) -> bool:
    """The reply on this turn is the one that first shows a dynamic multiple choice."""
    if not needs_dynamic_mcq:
        return False
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    return (
        str(block.get("type") or "") == "mcq"
        and str(data.get("mode") or "static") == "dynamic"
        and _cached_generated_mcq(active_block_state) is None
    )


def _dynamic_mcq_schema(schema: dict) -> dict:
    """Reply schema for the turn that presents a dynamic multiple choice."""
    reply = dict(schema["properties"]["reply"])
    reply["description"] = (
        "A short lead-in only. Do not include the question stem, the choices, "
        "or a request to type a letter. Those belong in generated_mcq. "
        "Include the unit close and the course outro when this turn ends the unit."
    )
    properties = dict(schema["properties"])
    properties["reply"] = reply
    copied = dict(schema)
    copied["properties"] = properties
    return copied


def _schema_without_generated_mcq(schema: dict) -> dict:
    properties = {key: value for key, value in schema["properties"].items() if key != "generated_mcq"}
    required = [key for key in schema["required"] if key != "generated_mcq"]
    copied = dict(schema)
    copied["properties"] = properties
    copied["required"] = required
    return copied


def turn_response_schema(*, presenting_dynamic_mcq: bool = False, needs_dynamic_mcq: bool = False) -> dict:
    """Include generated_mcq only when this turn presents one or is the last substep before one."""
    include = bool(presenting_dynamic_mcq or needs_dynamic_mcq)
    schema = RESPONSE_SCHEMA if include else _schema_without_generated_mcq(RESPONSE_SCHEMA)
    if presenting_dynamic_mcq:
        return _dynamic_mcq_schema(schema)
    return schema


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
    if str(substep or "") == "summary_check":
        return False
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
    if btype in {"curiosity", "explanation"}:
        return f"{bid}:engaged"
    if substep and substep not in {"main", "choice", "critique", "explain"}:
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
    if btype == "explanation":
        return 99
    if btype == "passage_ela":
        try:
            cap = int(bcfg.get("passage_ela_max_attempts_per_step", 2) or 2)
        except (TypeError, ValueError):
            cap = 2
        return min(4, max(1, cap))
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
    if btype == "explanation":
        topics = explanation_topics(block)
        first = topics[0]["title"] if topics else ""
        heading = str(data.get("block_title") or first or "Explanatory walkthrough").strip()
        return (
            f"Explanatory walkthrough: {heading}. Topic 1 of {max(len(topics), 1)}: {first or 'the first topic'}. "
            "Do not quiz."
        )
    if btype == "passage_ela":
        title = str(data.get("passage_title") or "ELA reading passage").strip()
        genre = str(data.get("passage_genre") or "informational").strip()
        return f"ELA reading passage: {title} ({genre})."
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


_PERSONA_DESCRIPTIONS = {
    "socratic_mentor": "a calm, respectful academic mentor (thoughtful Socratic guide without theatrical roleplay)",
    "coach": "a warm coach",
    "detective": "a curious detective",
    "explorer": "a field explorer",
    "storyteller": "a narrative storyteller",
    "sibling": "an encouraging older sibling",
    "wizard": "a playful wizard",
}

_VOCABULARY_REGISTER_RULES = {
    "adaptive_to_child": (
        "vocabulary_register is adaptive_to_child: match disciplinary terminology to the child's reading level and grade band."
    ),
    "everyday_conversational": (
        "vocabulary_register is everyday_conversational: use plain everyday words first and introduce technical terms only after the concept clicks."
    ),
    "academic_precision": (
        "vocabulary_register is academic_precision: use exact disciplinary vocabulary early, always paired with a brief kid-friendly gloss."
    ),
    "story_rich_expressive": (
        "vocabulary_register is story_rich_expressive: use vivid, expressive phrasing while still respecting the child's sentence-length cap."
    ),
}

_INTEREST_WEAVING_RULES = {
    "subtle_natural": (
        "interest_weaving is subtle_natural: one personal interest in the hook or one example when it fits. Do not force a hobby into every turn."
    ),
    "frequent_thematic": (
        "interest_weaving is frequent_thematic: frame examples, scenarios, and word problems around the child's personal interests whenever possible."
    ),
    "off": (
        "interest_weaving is off: do not pull from the child's personal interests; use neutral curriculum examples or the fallback metaphors domain."
    ),
}

_SIDEKICK_RULES = {
    "barnaby": "Barnaby the Badger may voice at most one short line on hooks or hints and never asks a second competing question.",
    "pixel": "Pixel the Robot may voice at most one short line on hooks or hints and never asks a second competing question.",
    "spark": "Spark the Dragon may voice at most one short line on hooks or hints and never asks a second competing question.",
}


def compute_turn_kind(
    *,
    opening: bool,
    unit_complete: bool,
    course_complete: bool,
    transition_from_block: dict | None,
    attempts: int,
    hint_tier: str,
    reveals: int,
) -> str:
    """Derive the active turn kind (orient, ask, pass, nudge, scaffold, reveal, close)."""
    if unit_complete or course_complete:
        return "close"
    if transition_from_block is not None:
        return "pass"
    if opening:
        return "orient"
    tier = (hint_tier or "nudge").strip().lower()
    if tier == "reveal" or int(reveals or 0) > 0 and int(attempts or 0) > 0:
        return "reveal"
    if int(attempts or 0) >= 2 or tier in {"analogy", "scaffold"}:
        return "scaffold"
    if int(attempts or 0) == 1:
        return "nudge"
    return "ask"


def _voice_paragraph(profile: TutorProfile) -> str:
    voice = effective_voice_settings(profile)
    persona_key = str(voice.get("persona") or profile.persona or "coach")
    persona = _PERSONA_DESCRIPTIONS.get(persona_key) or _a(_label(PERSONAS, persona_key))
    raw_lex = str(profile.lexicon or voice.get("vocabulary_register") or "")
    lexicon = _lower_first(_label(VOICES, raw_lex)) or _lower_first(_label(VOCABULARY_REGISTERS, str(voice.get("vocabulary_register") or ""))) or "plain"
    meta_key = str(voice.get("metaphors") or profile.metaphors or "everyday")
    if meta_key == "none":
        images = "plain language and no borrowed image"
    else:
        metaphor = _lower_first(_label(METAPHORS, meta_key))
        images = f"{metaphor} images" if metaphor else "plain language"
    side_key = str(voice.get("sidekick") or profile.sidekick or "none")
    if side_key in {"", "off", "none"}:
        company = ""
    else:
        company = f", and with {_a(_label(SIDEKICKS, side_key))}"
    return (
        f"Write as {persona}, in {lexicon} words, with {images}{company}. "
        "That voice does not change the block, the expected answer, or the score."
    )


def _how_to_sound(
    *,
    profile: TutorProfile,
    student: Student | None = None,
    turn_kind: str = "ask",
) -> list[str]:
    """Assemble Layer 3 ('How to sound') with the 6 orthogonal settings and cross-layer precedence contract."""
    voice = effective_voice_settings(profile)
    cp = effective_child_profile(student) if student is not None else {}
    persona_key = str(voice.get("persona") or "coach")
    vocab_reg = str(voice.get("vocabulary_register") or "adaptive_to_child")
    weaving = str(voice.get("interest_weaving") or "subtle_natural")
    meta_key = str(voice.get("metaphors") or "everyday")
    humor_key = str(voice.get("humor_and_wit") or "light_warm")
    sidekick_key = str(voice.get("sidekick") or "none")

    persona_label = _PERSONA_DESCRIPTIONS.get(persona_key) or _lower_first(_label(PERSONAS, persona_key))
    meta_label = _lower_first(_label(METAPHORS, meta_key)) or meta_key
    tone = str(cp.get("communication_tone") or "warm_and_encouraging")
    support = str(cp.get("learning_support") or "none")
    anxiety_or_gentle = support == "math_or_test_anxiety" or tone == "calm_and_gentle"
    # A miss rewrites humor in This turn, so this section stays byte-identical across turns.
    del turn_kind

    lines: list[str] = [_voice_paragraph(profile)]
    tutor_name = str(getattr(profile, "name", "") or "").strip()
    tutor_desc = str(getattr(profile, "description", "") or "").strip()
    if (tutor_name and tutor_name not in {"Default", "prompt-tester"}) or (
        tutor_desc and tutor_desc != DEFAULT_TUTOR_DESCRIPTION
    ):
        label = tutor_name or "Default"
        if tutor_desc:
            lines.append(f"Active tutor profile ({label}): {tutor_desc}")
        else:
            lines.append(f"Active tutor profile: {label}.")
    lines.append(
        f"Persona ({persona_label}) is the frame. communication_tone ({tone}) sets emotional intensity."
    )
    lines.append(
        "The child profile (reading_level, response_length, learning_support) exclusively owns sentence length, reading complexity, and paragraph length. "
        + _VOCABULARY_REGISTER_RULES.get(vocab_reg, _VOCABULARY_REGISTER_RULES["adaptive_to_child"])
    )
    lines.append(
        _INTEREST_WEAVING_RULES.get(weaving, _INTEREST_WEAVING_RULES["subtle_natural"])
        + f" Fallback analogy domain ({meta_label}): use it when interest_weaving is off, the child has no interests, or an interest does not fit."
    )

    if anxiety_or_gentle or humor_key == "none_straightforward":
        reason = (
            "math_or_test_anxiety or calm_and_gentle tone"
            if anxiety_or_gentle
            else "humor_and_wit is none_straightforward"
        )
        lines.append(
            f"Humor guardrail ({humor_key}): suppress jokes and banter on this turn ({reason}); stay clear, earnest, and supportive."
        )
    elif humor_key == "playful_banter":
        lines.append(
            "Humor & wit (playful_banter): witty energy on hooks and passes. No jokes on a nudge, scaffold, or reveal."
        )
    else:
        lines.append(
            "Humor & wit (light_warm): occasional warm wit on hooks and passes. No jokes on a nudge, scaffold, or reveal."
        )

    if sidekick_key in _SIDEKICK_RULES:
        lines.append(f"Sidekick ({sidekick_key}): {_SIDEKICK_RULES[sidekick_key]}")
    elif sidekick_key not in {"", "none", "off"}:
        sidekick_label = _lower_first(_label(SIDEKICKS, sidekick_key)) or sidekick_key
        lines.append(
            f"Sidekick ({sidekick_label}): at most one short line on a hook or hint, and never a second question."
        )
    else:
        lines.append("Sidekick (none): do not include a sidekick character.")

    return lines


_GRADE_BAND_LABELS = {
    "early_elementary": "Early elementary (Grades K-2)",
    "upper_elementary": "Upper elementary (Grades 3-5)",
    "middle_school": "Middle school (Grades 6-8)",
    "high_school": "High school (Grades 9-12)",
}

_READING_LEVEL_LINES = {
    "emerging": "Reading level emerging: very short sentences, sight words, and define new terms immediately.",
    "early_fluent": "Reading level early fluent: concrete sentences, one clause at a time.",
    "on_grade": "Reading level on grade: natural grade-level words and flow.",
    "advanced": "Reading level advanced: precise terms and richer sentences.",
}

_RESPONSE_LENGTH_LINES = {
    "bite_sized": "Keep response length bite-sized: 1 to 2 short sentences.",
    "balanced": "Keep response length balanced: 2 to 4 sentences.",
    "detailed": "Keep response length detailed: fuller explanations when a connection needs them.",
}

_EXPRESSION_STYLE_LINES = {
    "one_word_or_taps": "Expression style one-word replies or taps: on 1 to 3 words, validate the idea and model a full sentence.",
    "short_phrases": "Expression style short phrases: brief phrases or one sentence, and crisp follow-ups.",
    "conversational": "Expression style conversational: invite thinking out loud.",
    "analytical": "Expression style analytical: welcome fuller reasoning and precise pushback.",
}

_EXPLANATION_STYLE_LINES = {
    "concrete_examples": "Explanations use concrete examples from familiar objects and situations.",
    "step_by_step": "Explanations go step by step, one piece at a time.",
    "visual_spatial": "Explanations use visual-spatial framing: pictures, layouts, and described diagrams.",
    "story_and_analogy": "Explanations use a short story or an imagine-if comparison.",
    "pattern_and_rule": "Explanations state the rule first, then apply it.",
}

_CHALLENGE_APPETITE_LINES = {
    "needs_reassurance": "Challenge appetite needs reassurance: normalize mistakes and keep stakes low.",
    "steady": "Challenge appetite steady: normal scaffolding and pace.",
    "loves_a_challenge": "Challenge appetite loves a challenge: brisk pace, stretch prompts, few hints before they try.",
}

_COMMUNICATION_TONE_LINES = {
    "calm_and_gentle": "Tone calm and gentle: patient, low stimulation, no pressure.",
    "warm_and_encouraging": "Tone warm and encouraging: friendly and upbeat.",
    "playful_and_curious": "Tone playful and curious: light humor and wonder.",
    "direct_and_matter_of_fact": "Tone direct and matter-of-fact: the concept, without fluff.",
}

_LEARNING_SUPPORT_LINES = {
    "adhd_focus_friendly": "Learning support (ADHD focus-friendly): keep turns extra-crisp with an immediate hook and never stack multi-part instructions.",
    "dyslexia_reading_friendly": "Learning support (dyslexia reading-friendly): use simple phonics-friendly words, short lines, and avoid dense paragraphs.",
    "ell_language_support": "Learning support (ELL language support): avoid idioms, explain figurative phrases, and pair new terms with simple synonyms.",
    "math_or_test_anxiety": "Learning support (math or test anxiety): frame checks as low-stakes puzzles and never mention tests or grades.",
}


def _who_you_are_talking_to(
    student: Student,
    profile: TutorProfile,
    block: dict,
    interests: str,
    cfg: dict | None = None,
    active_block_state: dict | None = None,
    passage_reprint: bool = False,
) -> list[str]:
    cp = effective_child_profile(student)
    parts = [f"Speak to {student.display_name}."]
    age = student.age
    raw_level = (student.reading_level or "").strip()
    read_lvl = cp["reading_level"]
    early = _early_reading(raw_level) or read_lvl == "emerging"
    young = age is not None and age <= 8
    grade_label = _GRADE_BAND_LABELS.get(cp["grade_band"], cp["grade_band"])
    if young and early:
        parts.append(
            f"Age {age} ({grade_label}) and an early reading level both mean shorter sentences and simpler examples."
        )
    elif young:
        parts.append(f"Age {age} ({grade_label}): shorter sentences and simpler examples.")
    elif age is not None:
        parts.append(f"Examples for a {age}-year-old in {grade_label}.")
    else:
        parts.append(f"No age is set ({grade_label}).")

    if early and not young:
        parts.append(
            "The reading level is early, so use shorter sentences, everyday sight words, and define any new term right away."
        )
    elif raw_level and raw_level not in _READING_LEVEL_LINES and not (early and young):
        parts.append(
            f"The reading level is {raw_level}. {_READING_LEVEL_LINES.get(read_lvl, _READING_LEVEL_LINES['on_grade'])}"
        )
    elif not raw_level and not (student.child_profile or {}).get("reading_level"):
        parts.append("No reading level is set.")
    elif not (early and young):
        parts.append(_READING_LEVEL_LINES.get(read_lvl, _READING_LEVEL_LINES["on_grade"]))

    length_override = explanation_length_override(
        block,
        cfg,
        response_length=str(cp["response_length"]),
        reading_level=str(cp["reading_level"]),
        explanation_style=str(cp["explanation_style"]),
        active_block_state=active_block_state,
    )
    if length_override:
        parts.append(length_override)
    elif passage_reprint:
        parts.append(
            "The response_length sentence cap applies ONLY to your coaching and question below the passage, "
            "never to the passage text itself."
        )
    else:
        parts.append(_RESPONSE_LENGTH_LINES.get(cp["response_length"], _RESPONSE_LENGTH_LINES["balanced"]))
        bcfg = ((cfg or {}).get("blocks") or {}).get("explanation") or {}
        if (
            str(block.get("type") or "").strip() == "explanation"
            and bool(bcfg.get("allow_depth_override_student_length", True))
        ):
            parts.append(
                "If the learner asks to elaborate, do NOT truncate that elaboration to fit "
                f"`response_length` (`{cp['response_length']}`). Keep each sentence at reading level "
                f"`{cp['reading_level']}` and use explanation style `{cp['explanation_style']}`."
            )
    parts.append(_EXPRESSION_STYLE_LINES.get(cp["expression_style"], _EXPRESSION_STYLE_LINES["short_phrases"]))

    raw_modality = (student.modality or "").strip()
    expl_style = cp["explanation_style"]
    btype = str(block.get("type") or "").strip()
    if raw_modality.lower() == "visual" or expl_style == "visual_spatial":
        if btype in {"case_study", "worked_example", "spot_the_flaw"}:
            parts.append(
                "You may ask for a described picture on this block because it already has cases or steps. "
                + _EXPLANATION_STYLE_LINES["visual_spatial"]
            )
        else:
            parts.append("Stay in words on this block. " + _EXPLANATION_STYLE_LINES["visual_spatial"])
    elif raw_modality and raw_modality not in _EXPLANATION_STYLE_LINES:
        parts.append(
            f"Examples come through {raw_modality}. Stay in words. "
            + _EXPLANATION_STYLE_LINES.get(expl_style, _EXPLANATION_STYLE_LINES["concrete_examples"])
        )
    elif not raw_modality and not (student.child_profile or {}).get("explanation_style"):
        parts.append("No modality is set. Stay in words.")
    else:
        parts.append(_EXPLANATION_STYLE_LINES.get(expl_style, _EXPLANATION_STYLE_LINES["concrete_examples"]))

    parts.append(_CHALLENGE_APPETITE_LINES.get(cp["challenge_appetite"], _CHALLENGE_APPETITE_LINES["steady"]))
    parts.append(_COMMUNICATION_TONE_LINES.get(cp["communication_tone"], _COMMUNICATION_TONE_LINES["warm_and_encouraging"]))

    support = cp["learning_support"]
    if support in _LEARNING_SUPPORT_LINES:
        parts.append(_LEARNING_SUPPORT_LINES[support])

    tag_labels = [INTEREST_TAG_LABELS.get(tag, tag) for tag in cp["interest_tags"]]
    specific = cp["interests"] or (interests if interests and interests != "none named" else "")
    interest_pieces: list[str] = []
    for piece in [*tag_labels, *([specific] if specific else [])]:
        if piece and piece not in interest_pieces:
            interest_pieces.append(piece)
    named = ", ".join(interest_pieces)
    voice = effective_voice_settings(profile)
    weaving = str(voice.get("interest_weaving") or ("subtle_natural" if profile.use_interests else "off"))
    if weaving != "off" and named:
        parts.append(f"When an example would help, use one of these interests: {named}.")
    elif named:
        parts.append(f"The child cares about {named}. Keep examples inside the subject.")
    else:
        parts.append("Keep examples inside the subject.")
    return [" ".join(parts)]


def _learner_sentence(
    student: Student,
    profile: TutorProfile,
    block: dict,
    interests: str,
    cfg: dict | None = None,
    active_block_state: dict | None = None,
) -> str:
    return " ".join(
        _who_you_are_talking_to(student, profile, block, interests, cfg, active_block_state)
    )


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
            "If this unit ends known or fragile, every other target is already known or fragile. "
            f"After the close, add the course outro: {course_title} is complete, "
            "and recap the ideas the child now holds."
        )
    return "Another target is not known or fragile yet. Do not write a course outro. The close may point at the next card."


_SUMMARY_NO_PRAISE = (
    "Asking a question, asking for background, or asking to move on is not noteworthy work. "
    "Do not say Great question, Nice work, Great job, or any congratulation on those turns. "
    "A warm tone does not add praise."
)
_WORKED_AFFIRM = (
    "Worked close: This solo answer is correct. Reply with a short affirmation of that answer. "
    "Do not ask Ready for the next challenge. Do not summarize the block and do not ask whether to discuss or move on. "
    "Set substep_passed=true and block_complete=true. Ask no question. Do not open the next block."
)
_WORKED_CONTINUE = (
    "Worked close: The learner is answering a continue question. "
    "Reply with one short closing line and no question. Do not restate the summary. Do not ask again. "
    "Set block_complete=true. Do not open the next block."
)
_WORKED_BARE_YES = (
    "Worked close: A bare yes is not a close on this worked step. "
    "The previous turn did not ask to continue or move on. "
    "Do not set block_complete=true for that yes."
)


def _ready_to_move_on(answer: str) -> bool:
    from app.kc_loop import learner_ready_to_proceed

    return learner_ready_to_proceed(answer, False)


_GOAL_START_EXPLAIN = (
    "Goal start: Explain what this topic is and why it matters. "
    "Write it as teaching, not a question. Do not ask the goal question. Do not ask any question."
)
_GOAL_START_DEEPEN = (
    "Goal start: The learner wants to keep learning. Explain this same topic more deeply, from a fresh angle. "
    "Write it as teaching, not a question. Do not ask the goal question. Do not ask any question."
)
_GOAL_START_CLARIFY = (
    "Goal start: The learner asked a question. Answer that question first, in a sentence or two, "
    "then return to this topic. Set help_requested=true. Do not ask the goal question."
)
_GOAL_START_ASK = (
    "Goal question: The learner moved on. Ask the opening question for this goal. "
    "One question, and it comes last. Do not answer it."
)
_SUMMARY_ELABORATE = (
    "The learner asked to elaborate on the recap. Elaborate on the summary in this reply. "
    "Set substep_passed=false and block_complete=false. Do not complete the block and do not advance. "
    "Do not close with a brief affirmation. Do not open the next block. "
    "Only an explicit move-on, such as got it - move on, no final questions, or let's continue, "
    "may complete the block."
)


def _goal_start_mode(block: dict, substep: str, *, opening: bool, last_answer: str) -> str:
    """explain, deepen, clarify, or ask on the opening explanation. Empty once the question is open."""
    if str(block.get("type") or "") != "topic_goal" or substep != "explain":
        return ""
    if opening:
        return "explain"
    from app.kc_loop import learner_asks_clarification, learner_done_with_explanation

    if learner_asks_clarification(last_answer):
        return "clarify"
    if learner_done_with_explanation(last_answer):
        return "ask"
    return "deepen"


def _summary_elaboration(block: dict, substep: str, last_answer: str) -> bool:
    if str(block.get("type") or "") != "explanation" or substep != "summary_check":
        return False
    from app.kc_loop import learner_wants_recap_elaboration

    return learner_wants_recap_elaboration(last_answer)


def _summary_close_lines(
    *,
    phase: str,
    revealed: bool,
    opening: bool,
    block_type: str = "",
    last_answer: str = "",
) -> list[str]:
    """How to speak on the summary check, and how to answer a learner who is already there."""
    if phase == "task" and block_type == "topic_goal" and _ready_to_move_on(last_answer):
        return [
            (
                "Summary close: The learner asked to move on or to go to the next part. "
                "Set block_complete=true and close with a brief statement only. "
                "Do not ask a new question and do not ask again. Do not open the next block."
            ),
            _SUMMARY_NO_PRAISE,
        ]
    if phase == "task":
        lines = []
        if block_type == "topic_goal":
            lines.append(
                "Summary close: If the learner asked a question or for background and has not answered the goal, "
                "answer it and ask the goal again. Set substep_passed=false and block_complete=false. "
                "Do not summarize the block, do not offer to move on, and do not offer another example."
            )
        lines.extend(
            [
                (
                    "Summary close: If this answer satisfies the substep, set substep_passed=true and block_complete=false. "
                    "Give a short summary of what this block covered and ask whether the learner wants to continue discussing "
                    "or ask any questions, or close and move on. Do not open the next block."
                ),
                (
                    "Summary close on the attempt limit: If this is the last allowed try and the answer still misses the goal, "
                    "set substep_passed=false and block_complete=false. Highlight that the learner reached the attempt limit "
                    "and did not fully complete this block yet. Never say congratulations and do not praise them as if they passed. "
                    "Briefly summarize the key takeaway they missed. Ask whether they want to keep trying or discussing the goal, "
                    "which can still complete the block, or move on to the next block anyway."
                ),
                _SUMMARY_NO_PRAISE,
            ]
        )
        return lines
    if phase != "check":
        return []
    if revealed:
        lines = [
            (
                "Summary close: The learner reached the attempt limit and did not fully complete this block yet. "
                "Highlight that. Never say congratulations and do not praise them as if they passed. "
                "Briefly summarize the key takeaway they missed. Ask whether they want to keep trying or discussing the goal, "
                "which can still complete the block, or move on to the next block anyway."
            )
        ]
    else:
        lines = [
            (
                "Summary close: The learner completed this block. Give a short summary of what this block covered "
                "and ask whether the learner wants to continue discussing or ask any questions, or close and move on."
            )
        ]
    if opening:
        lines.append(_SUMMARY_NO_PRAISE)
        return lines
    lines.append(
        "Summary reply: If the learner had not completed the block and this reply now demonstrates the goal, "
        "set substep_passed=true and block_complete=false, affirm that they have now completed the block, "
        "and ask if they are ready to move on."
    )
    lines.append(
        "Summary reply: If they ask a question or want more discussion without completing it yet, "
        "set substep_passed=false and block_complete=false, answer helpfully, and ask again whether they want "
        "to keep discussing or trying, or move on."
    )
    closing = (
        "Summary reply: If they choose to close and move on, set block_complete=true and reply with a brief "
        "closing statement only. Do not ask a new question and do not open the next block."
    )
    if revealed:
        closing += " If the block is still incomplete, do not say congratulations."
    lines.append(closing)
    lines.append(_SUMMARY_NO_PRAISE)
    return lines


def _ending(
    *,
    close_depth: str,
    kind: str,
    unit_complete: bool,
    course_complete: bool,
    others_known: bool,
    course_title: str,
    is_final_block_and_substep: bool,
    summary_stay: bool = False,
) -> str:
    if summary_stay and not unit_complete and not course_complete:
        length = _close_summary_sentence(close_depth, kind)
        outro = _outro_sentence(others_known, course_title, required=False)
        return " ".join(
            (
                "Close Contract: If block_complete=true on this summary, include the unit close and ask no new question. "
                "If block_complete=false, ask whether the learner wants to keep discussing or move on.",
                length,
                _close_body(),
                outro,
            )
        )
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


def _topic_goal_earned_praise(encouragement_style: str) -> str:
    """Topic/goal replies are written before scoring, so the model has to withhold unearned praise itself."""
    if encouragement_style == "minimal":
        earned = "When the reply meets the goal, keep any acknowledgment to a few words. Do not add praise."
    elif encouragement_style == "matter_of_fact_confirm":
        earned = "When the reply meets the goal, confirm clearly and warmly without extra fanfare."
    else:
        earned = (
            "When the reply meets the goal, name the specific reasoning move the learner made. "
            "Do not use generic praise."
        )
    return (
        "Topic/goal feedback: Praise only a reply that meets the goal. "
        + earned
        + " Asking a question, asking for background, or asking to move on is not noteworthy work. "
        "Do not say Great question, Nice work, Great job, or any congratulation on those turns. "
        "A warm tone does not add praise. "
        "On a miss, nudge with no praise. "
        "Do not say the learner is on the right track or that it is a good start "
        "when the answer does not address the goal. "
        "This holds on the first reply to an answer and on later nudge and scaffold turns."
    )


def _passage_attempt_tier(turn_kind: str) -> str:
    if turn_kind in {"ask", "nudge", "scaffold", "reveal"}:
        return turn_kind
    return "ask"


def _passage_turn_lines(
    block: dict,
    substep: str,
    turn_kind: str,
    cfg: dict | None,
    *,
    opening: bool,
    last_answer: str,
) -> list[str]:
    """Substep and passage-print rules. Empty for every block that is not passage_ela."""
    if str(block.get("type") or "").strip() != "passage_ela":
        return []
    from app.kc_blocks import PASSAGE_CAP_RULE, PASSAGE_SUBSTEPS, clean_passage_ela_data, passage_paragraphs, passage_reprint_kind

    steps = list(PASSAGE_SUBSTEPS)
    current = substep if substep in steps else steps[0]
    pos = steps.index(current) + 1
    lines = [f"ELA substep {pos} of 3 ({current}). Attempt tier: {_passage_attempt_tier(turn_kind)}."]
    kind = passage_reprint_kind(block, cfg, opening=opening, last_answer=last_answer)
    if kind == "paragraph":
        cleaned = clean_passage_ela_data(block.get("data") if isinstance(block.get("data"), dict) else {})
        paragraphs = passage_paragraphs(cleaned["passage_text"])
        first = paragraphs[0] if paragraphs else ""
        lines.append(
            "Opening display is chunked by paragraph. Include Paragraph 1 verbatim before asking the question. "
            "Do not print later paragraphs on this opening turn."
        )
        if first:
            lines.append(f"Paragraph 1:\n{first}")
        lines.append(
            "The response_length sentence cap (2 to 4 sentences) applies ONLY to your coaching and question below the passage, never to the passage text itself."
        )
    elif kind == "full":
        lines.append(PASSAGE_CAP_RULE)
    return lines


def _passage_teach_lines(block: dict, substep: str) -> list[str]:
    from app.kc_blocks import PASSAGE_SUBSTEPS, clean_passage_ela_data

    data = clean_passage_ela_data(block.get("data") if isinstance(block.get("data"), dict) else {})
    steps = list(PASSAGE_SUBSTEPS)
    current = substep if substep in steps else steps[0]
    pos = steps.index(current) + 1
    lines = [
        "Block type: passage_ela (ELA Reading Passage)",
        f"Passage title: {data['passage_title']} ({data['passage_genre']})",
        "Passage text:",
        data["passage_text"],
        f"Active substep ({pos}/3 {current}):",
    ]
    if current == "cite_evidence":
        lines.append(f"Question: {data['evidence_prompt']}")
        quotes = data["verbatim_evidence_quotes"]
        if quotes:
            lines.append("Verbatim evidence quotes (withhold until pass or reveal):")
            lines.extend(f"- {quote}" for quote in quotes)
    elif current == "craft_or_inference":
        lines.append(f"Analysis focus: {data['analysis_focus']}")
        lines.append(f"Question: {data['analysis_question']}")
        lines.append(f"Expected analysis (withhold until pass or reveal): {data['expected_analysis']}")
    else:
        lines.append(f"Question: {data['central_idea_question']}")
        lines.append(f"Expected central idea (withhold until pass or reveal): {data['expected_central_idea']}")
        if data["distractor_detail"]:
            lines.append(f"Distractor detail (true, but not the central idea): {data['distractor_detail']}")
    return lines


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
    turn_kind: str = "ask",
    instructional_stance: str = "guided_discovery",
    scaffolding_escalation: str = "progressive_nudge_then_scaffold",
    misconception_policy: str = "explain_and_retry_once",
    prerequisite_support_policy: str = "inline_micro_recap",
    encouragement_style: str = "process_praise",
    challenge_appetite: str = "steady",
    learning_support: str = "none",
    communication_tone: str = "warm_and_encouraging",
    active_block_state: dict | None = None,
    close_block_only: bool = False,
    summary_phase: str = "",
    summary_stay: bool = False,
    last_answer: str = "",
    cfg: dict | None = None,
    worked_close: str = "",
) -> list[str]:
    label = block_step_label(block, step_index, total_blocks, substep, active_block_state)
    presenting = _presenting_dynamic_mcq(block, needs_dynamic_mcq, active_block_state)
    mode_note = "" if presenting else ("The child will pick on screen." if choice_on_screen else "The child will type.")
    step_line = f"Active step: {label}."
    if mode_note:
        step_line = f"{step_line} {mode_note}"
    lines = [
        "You are the knowledge-component tutor.",
        f"{step_line} Active turn kind: {turn_kind}.",
    ]
    outline = stored_outline(node)
    goal_start = _goal_start_mode(block, substep, opening=opening, last_answer=last_answer)
    if goal_start == "explain":
        lines.append(_GOAL_START_EXPLAIN)
        if opening and step_index == 0 and outline:
            lines.append(
                f"Component outline to weave into that explanation, not as a question: {_finish(outline)}"
            )
    elif goal_start == "deepen":
        lines.append(_GOAL_START_DEEPEN)
    elif goal_start == "clarify":
        lines.append(_GOAL_START_CLARIFY)
    elif goal_start == "ask":
        lines.append(_GOAL_START_ASK)
    elif opening and step_index == 0:
        if presenting:
            lines.append(
                "Turn 1 Zero Dead Turns: Open Block 1 with a short lead-in only. "
                "Do not put the question or the choices in the reply."
            )
        else:
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
            f"This reply opens {label} only. Do not ask a question about the finished block."
        )
    if presenting and turn_kind in {"orient", "ask"}:
        lines.append(
            "Turn Stance: Give a short lead-in for the choice card. Do not ask the multiple-choice question in the reply."
        )
    elif turn_kind in {"orient", "ask"} and goal_start not in {"explain", "deepen", "clarify"}:
        if instructional_stance == "direct_instruction_first":
            lines.append(
                "Turn Stance (direct_instruction_first): Model the key rule or idea concisely before asking the block question."
            )
        elif instructional_stance == "productive_challenge_first":
            lines.append(
                "Turn Stance (productive_challenge_first): Let the learner try the problem first and teach contingently from their attempt."
            )
        else:
            lines.append(
                "Turn Stance (guided_discovery): Pair a short concrete anchor with a guiding question."
            )
    elif turn_kind in {"nudge", "scaffold"}:
        if scaffolding_escalation == "socratic_probing":
            lines.append(
                "Turn Escalation (socratic_probing): Ask targeted diagnostic questions to help the learner spot the gap themselves."
            )
        elif scaffolding_escalation == "worked_example_on_first_miss":
            lines.append(
                "Turn Escalation (worked_example_on_first_miss): Show a brief parallel worked example or sub-step immediately on the first miss before asking them to retry."
            )
        else:
            lines.append(
                "Turn Escalation (progressive_nudge_then_scaffold): Give a brief nudge on the first miss, then a concrete breakdown or partial step on the next miss."
            )
        if challenge_appetite == "needs_reassurance":
            lines.append(
                "Reassurance on miss (challenge_appetite=needs_reassurance): Soften this miss transition, normalize the effort warmly, and keep stakes low."
            )
    if turn_kind in {"nudge", "scaffold", "reveal"}:
        lines.append(
            "Humor guardrail: suppress jokes and banter on this turn "
            "(an incorrect attempt (nudge/scaffold/reveal)); stay clear, earnest, and supportive."
        )
    topic_feedback_here = (
        str(block.get("type") or "") == "topic_goal" and turn_kind in {"ask", "nudge", "scaffold"}
    )
    if not topic_feedback_here and turn_kind in {"pass", "nudge", "scaffold"}:
        if encouragement_style == "matter_of_fact_confirm":
            lines.append(
                "Turn Feedback (matter_of_fact_confirm): Confirm clearly and warmly without extra fanfare."
            )
        elif encouragement_style == "minimal":
            lines.append(
                "Turn Feedback (minimal): Give a brief acknowledgment and move straight to the next step."
            )
        else:
            lines.append(
                "Turn Feedback (process_praise): Praise the specific strategy or reasoning move the learner used."
            )
    if presenting:
        lines.append(
            "Dynamic MCQ: reply is a short lead-in only. "
            "Put the question stem and the choices only in generated_mcq, "
            "with correct_index and distractor_rationales for this block's target_skill and distractor_guidance. "
            "Do not list the options in reply, and do not ask the child to type a letter. "
            "The choice card shows the stem and the choices."
        )
    elif needs_dynamic_mcq:
        lines.append(
            "Dynamic MCQ: If this reply opens the dynamic multiple choice, reply is a short lead-in only. "
            "Put the question stem and the choices only in generated_mcq, "
            "with correct_index and distractor_rationales for that block's target_skill and distractor_guidance. "
            "Do not list the options in reply, and do not ask the child to type a letter. "
            "The choice card shows the stem and the choices. "
            "If this reply stays on the current block, keep teaching that block."
        )
    if (
        fragment
        and fragment_self_explanation
        and str(block.get("type")) == "topic_goal"
        and not (unit_complete or course_complete)
        and not _ready_to_move_on(last_answer)
        and goal_start not in {"explain", "deepen", "clarify"}
    ):
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
            summary_stay=summary_stay,
        )
    )
    elaborating = _summary_elaboration(block, substep, last_answer)
    if close_block_only and not elaborating:
        lines.append(
            "If block_complete=true, this reply only affirms and closes the active block. "
            "Ask no question. Do not open the next block. "
            "If block_complete=false, ask one question that stays on the active block."
        )
    if str(block.get("type") or "") == "explanation":
        if opening:
            lines.append(
                "This is the opening of the explanatory block. Explain only the current topic in detail, "
                "then ask if the learner has questions or wants you to elaborate. Do not quiz, and do not start the next topic yet."
            )
        elif substep == "summary_check":
            if elaborating:
                lines.append(_SUMMARY_ELABORATE)
            else:
                lines.append(
                    "The learner is on the block summary. If they ask a final question, answer it and ask whether they have any other final questions about this block. "
                    "If they have no final questions or are ready to continue, complete the block. "
                    "That completing reply is a brief affirmation only. Do not ask whether they have any final questions, and do not open the next block. "
                    "Do not quiz."
                )
        else:
            lines.append(
                "The learner has replied on the current topic. If they have a question or want elaboration, stay on this topic and answer. "
                "If they are ready, follow the move-on instruction in What to teach and explain the next topic, or summarize when this was the last topic. "
                "Do not quiz."
            )
    if worked_close == "affirm":
        lines.append(_WORKED_AFFIRM)
    elif worked_close == "continue":
        lines.append(_WORKED_CONTINUE)
        lines.append(_SUMMARY_NO_PRAISE)
    elif str(block.get("type") or "") != "explanation":
        if worked_close == "bare_yes":
            lines.append(_WORKED_BARE_YES)
        lines.extend(
            _summary_close_lines(
                phase=summary_phase,
                revealed=bool((active_block_state or {}).get("revealed_substep")),
                opening=opening,
                block_type=str(block.get("type") or ""),
                last_answer=last_answer,
            )
        )
    del misconception_policy
    del prerequisite_support_policy
    del learning_support
    del communication_tone
    lines.extend(
        _passage_turn_lines(
            block,
            substep,
            turn_kind,
            cfg,
            opening=opening,
            last_answer=last_answer,
        )
    )
    return lines


def _explanation_teach_lines(
    block: dict,
    substep: str,
    state: dict,
    *,
    opening: bool,
    last_answer: str = "",
) -> list[str]:
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    topics = explanation_topics(block)
    total = max(len(topics), 1)
    index = explanation_topic_index(block, state)
    lines = [
        "Do NOT quiz or test the learner on this block. Never ask them to solve, recall for a grade, or prove they know it.",
        "Explain the topic clearly, then ask if they have any questions or would like you to elaborate.",
    ]
    title = str(data.get("block_title") or "").strip()
    if title:
        lines.append(f"Block title: {_finish(title)}")
    covered = [item["title"] for item in topics[:index] if item["title"]]
    if substep == "summary_check":
        lines.append(
            "Active substep: summary_check. The learner has finished every topic and is ready for the block summary."
        )
        lines.append("Covered topics:")
        if topics:
            for position, topic in enumerate(topics, start=1):
                detail = topic["explanation"] or "Synthesize from the title."
                if topic["key_points"]:
                    detail = f"{detail} Key points: {topic['key_points']}."
                lines.append(f"{position}. {topic['title'] or 'Untitled'}: {detail}")
        else:
            lines.append("No topic entries were stored. Synthesize the block title.")
        takeaway = str(data.get("summary_takeaway") or "").strip()
        if takeaway:
            lines.append(f"Summary takeaway to anchor the recap: {_finish(takeaway)}")
        else:
            lines.append("No stored summary takeaway. Synthesize across the topic titles and explanations.")
        if opening:
            lines.append(
                "Give a cohesive summary of every topic discussed in this block, then ask if the learner has any final questions. "
                "If they ask a final question, set substep_passed=false, answer it, and ask again. "
                "If they have no final questions or are ready to continue, set substep_passed=true and block_complete=true. "
                "That completing reply is a brief affirmation only. Do not ask whether they have any final questions, and do not open the next block."
            )
        else:
            if _summary_elaboration(block, substep, last_answer):
                lines.append(_SUMMARY_ELABORATE)
            else:
                lines.append(
                    "The learner has responded on the summary. "
                    "If they ask a final question, set substep_passed=false and block_complete=false, answer it, "
                    "and you may ask whether they have any other questions about this block. "
                    "If they have no final questions or are ready to continue, set substep_passed=true and block_complete=true. "
                    "That completing reply is a brief affirmation and the takeaway only. "
                    "Do not ask whether they have any final questions. Do not ask any question. Do not open or mention the next block."
                )
        return lines
    topic = topics[index] if topics else {
        "title": "",
        "explanation": "",
        "key_points": "",
        "examples_or_analogies": "",
    }
    lines.append(
        f"Active substep: explain_topic. Topic {index + 1} of {total}: {topic['title'] or 'this topic'}."
    )
    if covered:
        lines.append("Already covered topic titles: " + "; ".join(covered) + ".")
    if topic["explanation"]:
        lines.append(f"Explain this topic from: {_finish(topic['explanation'])}")
    if topic["key_points"]:
        lines.append(f"Key points to weave in: {_finish(topic['key_points'])}")
    if topic["examples_or_analogies"]:
        lines.append(f"Example or analogy to use: {_finish(topic['examples_or_analogies'])}")
    if opening:
        lines.append(
            "This is the opening turn. Explain only this topic at the configured depth, then ask if they have questions or want elaboration. "
            "Do not start a later topic yet."
        )
        return lines
    lines.append(
        "If the learner asks a question or wants elaboration, set substep_passed=false, stay on this topic, "
        "answer with a fresh angle, and check in again. Do not move on while they still have questions."
    )
    if topics and index < len(topics) - 1:
        nxt = topics[index + 1]
        lines.append(
            "If the learner is good to proceed, set substep_passed=true and, in this same reply, explain the next topic: "
            f"Topic {index + 2} of {total}: {nxt['title'] or 'the next topic'}. {_finish(nxt['explanation'])}"
        )
        if nxt["key_points"]:
            lines.append(f"Next topic key points: {_finish(nxt['key_points'])}")
        if nxt["examples_or_analogies"]:
            lines.append(f"Next topic example or analogy: {_finish(nxt['examples_or_analogies'])}")
        lines.append("After that explanation, ask if they have questions or want elaboration. Do not quiz.")
        return lines
    takeaway = str(data.get("summary_takeaway") or "").strip()
    lines.append(
        "This is the last topic. If the learner is good to proceed, set substep_passed=true and, in this same reply, "
        "summarize every topic in the block and ask if they have any final questions. Do not quiz."
    )
    if takeaway:
        lines.append(f"Summary takeaway: {_finish(takeaway)}")
    if topics:
        lines.append("Topics to include in that summary:")
        for position, item in enumerate(topics, start=1):
            lines.append(f"{position}. {item['title'] or 'Untitled'}: {item['explanation']}")
    return lines


def _what_to_teach(
    *,
    node: KcNode,
    block: dict,
    step_index: int,
    substep: str,
    active_block_state: dict,
    next_block: dict | None = None,
    opening: bool = False,
    last_answer: str = "",
    worked_close: str = "",
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
        phase = _goal_start_mode(block, substep, opening=opening, last_answer=last_answer)
        if phase == "ask":
            lines.append("Ask the opening question for this goal now. Do not give the answer.")
        elif phase == "clarify":
            lines.append(
                "Answer the learner's question first, in a sentence or two, then return to this topic. "
                "Set help_requested=true. Do not ask the learner to state the goal yet."
            )
        elif phase in {"explain", "deepen"}:
            lines.append(
                "Explain what this topic is and why it matters. Do not ask the learner to state the goal yet."
            )

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
        if worked_close == "continue":
            lines.append(
                "The learner is answering a continue question. "
                "One short closing line. Do not restate the summary. Do not ask a question."
            )
        elif substep == "faded_step":
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
        elif worked_close == "affirm":
            lines.append(
                "The learner just gave the correct solo answer. "
                "Affirm that answer. Do not ask them to solve it again."
            )
            lines.append(f"Solo answer they gave: {_finish(solo_ans)}")
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
        lines.append(
            "Misconception guard: do not tag \"Thinking scarcity only applies to money or poor people\" "
            "when the learner is explaining why rich people or everyone are affected, including through prices or inflation, "
            "or when the learner is answering the follow-up example prompt. "
            "A money example that shows the idea still applies to wealthy people is not that misconception, "
            "and a follow-up example such as time, kids, or hobbies is the explanation they were asked for."
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

    elif btype == "explanation":
        lines.extend(
            _explanation_teach_lines(
                block,
                substep,
                active_block_state,
                opening=opening,
                last_answer=last_answer,
            )
        )

    elif btype == "passage_ela":
        lines.extend(_passage_teach_lines(block, substep))

    lines.append(f"Evidence id for this active step: {ev_id}. Include '{ev_id}' in rubric_met when satisfied.")
    if next_block is not None and isinstance(next_block, dict):
        if worked_close == "continue":
            lines.append(
                "This reply is one short closing line and no question. "
                "Do not restate the summary. Do not mention the next block and do not open it."
            )
        elif worked_close == "affirm":
            lines.append(
                "This reply is a short affirmation of the correct answer and no question. "
                "Do not summarize the block. Do not mention the next block and do not open it."
            )
        else:
            lines.append(
                f"If the learner's response completes Block {step_index + 1} (block_complete=true), "
                f"close Block {step_index + 1} with a brief affirmation and the takeaway only. "
                "Ask no question. Do not mention the next block and do not open it. "
                "The next block arrives in its own message. "
                "If the response does not complete the block (block_complete=false), "
                "ask one question that stays on this block."
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
            "never": "A correct pick moves to the summary check. Do not ask why that option is right.",
            "always": "A correct pick must include why that option is right before the summary check.",
        }
        lines.append(
            whys.get(
                confirm_why,
                "If the first pick is correct, move to the summary check. If the learner needed another try, ask why that option is right before the summary check.",
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

    elif btype == "explanation":
        depth = _explanation_depth(cfg)
        allow_override = bool(bcfg.get("allow_depth_override_student_length", True))
        elaboration = str(bcfg.get("elaboration_style_on_question") or "fresh_analogy_and_example")
        check_in = str(bcfg.get("check_in_prompt_style") or "questions_or_elaborate")
        summary_style = str(bcfg.get("end_of_block_summary_style") or "bulleted_recap_with_takeaway")
        counts = bool(bcfg.get("counts_toward_mastery_score", False))
        lines.append(
            "This block is a guided explanation, not a quiz. There is no miss, no retry, and no reveal. "
            "Ignore miss, retry, scaffold, and reveal instructions."
        )
        lines.append(_explanation_depth_line(depth))
        if allow_override and depth >= 3:
            lines.append(
                "Length override is on. Do not cut the explanation down to the learner's response_length "
                "when the topic needs more sentences. Still match their reading level and explanation style."
            )
        elif allow_override:
            lines.append(
                "Stay inside the learner's response_length unless they ask you to elaborate. "
                "An elaboration request may run longer, still at their reading level and explanation style."
            )
        else:
            lines.append(
                "Stay strictly inside the learner's response_length. Use a later elaboration turn if they ask for more."
            )
        elaborations = {
            "step_by_step_breakdown": (
                "When the learner asks a question or wants elaboration, break the topic into a new step-by-step sequence. "
                "Do not repeat the same paragraph."
            ),
            "zoom_out_big_picture": (
                "When the learner asks a question or wants elaboration, zoom out to the big picture and how this topic fits the block. "
                "Do not repeat the same paragraph."
            ),
            "adaptive_to_question": (
                "When the learner asks a question or wants elaboration, answer the question they actually asked, from a new angle. "
                "Do not repeat the same paragraph."
            ),
        }
        lines.append(
            elaborations.get(
                elaboration,
                "When the learner asks a question or wants elaboration, answer with a fresh analogy and a new example. "
                "Do not repeat the same paragraph.",
            )
        )
        check_ins = {
            "curiosity_invitation": (
                "Close each topic by inviting a curiosity or what-if question, and also offer to elaborate or move on."
            ),
            "brief_ready_check": (
                "Close each topic with a short check-in: Any questions on this part, or are you ready for the next topic?"
            ),
        }
        lines.append(
            check_ins.get(
                check_in,
                "Close each topic by asking whether they have any questions, or would like you to elaborate before the next part.",
            )
        )
        summaries = {
            "connected_narrative_synthesis": (
                "On the summary step, summarize every topic as one connected narrative that shows how they fit together."
            ),
            "concise_takeaway_only": (
                "On the summary step, give one concise takeaway that covers every topic."
            ),
        }
        lines.append(
            summaries.get(
                summary_style,
                "On the summary step, recap every topic in short bullets and add one takeaway sentence.",
            )
        )
        if substep == "summary_check":
            lines.append(
                "You are on the summary step. "
                "Ask whether they have any final questions only when you are staying on this block. "
                "If block_complete=true, the reply is a brief affirmation and the takeaway only. "
                "Do not ask if there are any final questions, do not ask any question, and do not open the next block."
            )
        if counts:
            lines.append(
                "Completing this walkthrough counts toward whether the component is known. "
                "It still never marks the component fragile, because the learner is not quizzed."
            )
        else:
            lines.append(
                "This block does not count toward known or fragile. Completing the walkthrough is engaged, never a miss."
            )

    elif btype == "passage_ela":
        data = block.get("data") if isinstance(block.get("data"), dict) else {}
        display = str(bcfg.get("passage_ela_display_mode") or "full_on_open")
        evidence = str(bcfg.get("passage_ela_evidence_mode") or "quote_or_close_paraphrase")
        scaffold = str(bcfg.get("passage_ela_scaffold_style") or "point_to_paragraph")
        try:
            attempts = int(bcfg.get("passage_ela_max_attempts_per_step", 2) or 2)
        except (TypeError, ValueError):
            attempts = 2
        attempts = 1 if timed else min(4, max(1, attempts))
        if display == "chunked_by_paragraph":
            lines.append(
                "On the opening turn, print Paragraph 1 only, then ask the central-idea question. "
                "Reveal a later paragraph when the learner needs it."
            )
        else:
            lines.append(
                "On the opening turn, print the passage title and the full passage text verbatim, "
                "keeping the blank lines between paragraphs, then ask the central-idea question."
            )
        evidence_rules = {
            "exact_quote_required": (
                "Cite evidence counts only when the learner quotes words or a sentence from the passage."
            ),
            "paragraph_reference": (
                "Cite evidence counts when the learner names the paragraph number and the key detail in it."
            ),
        }
        lines.append(
            evidence_rules.get(
                evidence,
                "Cite evidence counts when the learner quotes the passage or gives a close paraphrase of it.",
            )
        )
        distractor = str(data.get("distractor_detail") or "").strip()
        if scaffold == "contrast_main_vs_detail":
            detail = f" The minor detail to contrast is: {distractor}" if distractor else ""
            lines.append(
                "On a miss about the central idea, contrast that one-paragraph detail with what the whole passage is about. "
                f"Do not give the central idea away.{detail}"
            )
        elif scaffold == "sentence_starter":
            lines.append(
                "On a miss, offer a sentence frame such as: The author's central claim is ___, "
                "which is supported where the text states '___'."
            )
        else:
            lines.append(
                "On a miss, point to the paragraph to re-read and ask what happens there. Do not give the answer away."
            )
        lines.append(_retry_sentence(attempts, "this close-reading step"))
        lines.append(
            "When the attempt cap is reached, model the close-reading move, quote the evidence from the passage, and advance."
        )
        lines.append(
            "If the learner asks to see or re-read the passage, reprint the passage text verbatim and repeat the current question. "
            "Set decision to stay, substep_passed to false, and block_complete to false. Do not count that turn as an attempt."
        )

    return lines


def _explanation_depth_line(depth: int) -> str:
    lines = {
        1: "Explanation depth 1 of 5 (Concise Overview): use 2 to 3 clear sentences that hit the core idea. Strictly obey response_length.",
        2: "Explanation depth 2 of 5 (Focused Explanation): use one short paragraph of 3 to 4 sentences with one quick example. Respect response_length.",
        3: "Explanation depth 3 of 5 (Balanced Explanation + Example): give a clear explanation plus a concrete example in 4 to 6 sentences. You may exceed bite_sized by 1 or 2 sentences when clarity needs it.",
        4: "Explanation depth 4 of 5 (Detailed Multi-Angle Walkthrough): explain the topic in 1 to 2 well-structured paragraphs (5 to 8 sentences) with an example and why-it-works intuition.",
        5: "Explanation depth 5 of 5 (Comprehensive Deep Dive): give a rich multi-paragraph breakdown with intuition, the step-by-step mechanism, and a real-world example or analogy. Never cut a complex topic short.",
    }
    return lines.get(depth, lines[4])


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
    student: Student | None = None,
    presenting_dynamic_mcq: bool = False,
    close_block_only: bool = False,
    last_answer: str = "",
    opening: bool = False,
    worked_close: str = "",
) -> list[str]:
    over = cfg.get("overarching") or {}
    orient_mode = str(over.get("orient_framing") or "elaborate_outline")
    stance = str(over.get("instructional_stance") or "guided_discovery")
    escalation = str(over.get("scaffolding_escalation") or "progressive_nudge_then_scaffold")
    stay_mode = str(over.get("stay_on_course") or "brief_answer_then_return")
    misc_policy = str(over.get("misconception_policy") or "explain_and_retry_once")
    prereq_policy = str(over.get("prerequisite_support_policy") or "inline_micro_recap")
    praise_style = str(over.get("encouragement_style") or "process_praise")
    close_depth = str(over.get("close_summary_depth") or "diagnostic_strengths_and_gaps")
    cp = effective_child_profile(student) if student is not None else {}
    expl_style = str(cp.get("explanation_style") or "concrete_examples")
    challenge_appetite = str(cp.get("challenge_appetite") or "steady")

    lines = _block_config_rules(block, substep, cfg, goal)
    if _summary_elaboration(block, substep, last_answer):
        lines = [line for line in lines if not line.startswith("You are on the summary step.")]
    goal_start = _goal_start_mode(block, substep, opening=opening, last_answer=last_answer)
    move_on_close = str(block.get("type") or "") == "topic_goal" and substep == "main" and _ready_to_move_on(last_answer)
    if move_on_close:
        lines = [line for line in lines if "ask for the idea in a full sentence" not in line]

    lines.append(
        f"Representation harmony: when you explain, scaffold, or reveal, use explanation_style ({expl_style})."
    )

    if worked_close in {"affirm", "continue"}:
        lines.append("On this worked-example close the stance does not ask. Do not add a guiding question.")
    elif stance == "direct_instruction_first":
        lines.append(
            "Instructional stance (direct_instruction_first): model the key rule briefly, then ask."
        )
    elif stance == "productive_challenge_first":
        lines.append(
            "Instructional stance (productive_challenge_first): the learner tries first; teach from that attempt."
        )
    else:
        lines.append(
            "Instructional stance (guided_discovery): one short concrete anchor, then a guiding question."
        )
    if goal_start in {"explain", "deepen"}:
        lines.append("On this goal-start turn that stance does not ask. Teach only. Do not ask yet.")
    elif goal_start == "clarify":
        lines.append(
            "On this goal-start turn, answer the learner's question first, in a sentence or two, then return to the topic. "
            "Set help_requested=true."
        )

    if escalation == "socratic_probing":
        lines.append(
            "Scaffolding escalation (socratic_probing): on misses, ask targeted diagnostic questions to help the learner spot the gap themselves."
        )
    elif escalation == "worked_example_on_first_miss":
        lines.append(
            "Scaffolding escalation (worked_example_on_first_miss): show a brief parallel worked example or sub-step immediately on the first miss before asking them to retry."
        )
    else:
        lines.append(
            "Scaffolding escalation (progressive_nudge_then_scaffold): a nudge on the first miss, then a concrete partial step."
        )

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
        lines.append("Answer a tangent in one sentence, then return to this block.")

    if has_misconceptions:
        if misc_policy == "immediate_redirect":
            lines.append(
                "If a stored wrong move matches, name it on that same turn and set the decision to redirect."
            )
        elif misc_policy == "nudge_without_naming":
            lines.append(
                "If a stored wrong move matches, guide the learner away with a contrasting question without naming the misconception; if it repeats, redirect."
            )
        else:
            lines.append(
                "the first time a stored wrong move matches, explain the trap and retry once. The second time, redirect."
            )
    else:
        if misc_policy == "nudge_without_naming":
            lines.append(
                "Misconception policy (nudge_without_naming): guide the learner away from traps with a contrasting question without naming the misconception."
            )
        elif misc_policy == "immediate_redirect":
            lines.append(
                "Misconception policy (immediate_redirect): directly name and correct any misconception right away."
            )
        else:
            lines.append(
                "Misconception policy (explain_and_retry_once): say why the trap tempts, then one retry."
            )

    if prereq_policy == "scaffold_heavily":
        lines.append(
            "Prerequisite support policy (scaffold_heavily): proactively break down steps that depend on fragile or missing prerequisites."
        )
    elif prereq_policy == "no_special_adjustment":
        lines.append(
            "Prerequisite support policy (no_special_adjustment): treat prerequisites normally unless the student asks."
        )
    else:
        lines.append(
            "Prerequisite support policy (inline_micro_recap): one sentence on a fragile prerequisite when it matters."
        )

    if support_band == "hold":
        lines.append(
            "Support band (hold): name the missing prerequisite idea and the patch card. Do not teach that other component in this chat."
        )
    elif support_band == "stretch":
        lines.append("Support band (stretch): stay on this component with extra scaffolding.")
    elif support_band == "ready" and (prerequisite_status or "").strip() not in {"", "none"}:
        lines.append("Prerequisites are known; teach this block directly.")

    reassurance_note = (
        " Respect challenge_appetite (needs_reassurance) by normalizing effort warmly on any miss."
        if challenge_appetite == "needs_reassurance"
        else ""
    )
    if praise_style == "process_praise":
        lines.append(
            "When you encourage, name the specific reasoning move. No generic praise."
            + reassurance_note
        )
    elif praise_style == "matter_of_fact_confirm":
        lines.append(
            "Encouragement style (matter_of_fact_confirm): confirm clearly and warmly without extra fanfare."
            + reassurance_note
        )
    else:
        lines.append(
            "Keep any acknowledgment to a few words. Do not add praise."
            + reassurance_note
        )

    if str(block.get("type") or "") == "topic_goal":
        lines.append(_topic_goal_earned_praise(praise_style))

    if str(block.get("type") or "") == "explanation":
        lines.append(
            "Explanatory block override: do not quiz, score, or reveal an answer. "
            "While the block is still open, the only questions you ask are whether the learner has questions, wants elaboration, or is ready to continue. "
            "When block_complete=true, ask no question, including no check-in about final questions, and do not open the next block."
        )
        if _summary_elaboration(block, substep, last_answer):
            lines.append(_SUMMARY_ELABORATE)
    elif worked_close in {"affirm", "continue"}:
        lines.append("This worked-example turn closes the block. Ask no question.")
    elif close_block_only and not choice_on_screen and not presenting_dynamic_mcq:
        lines.append(
            "If block_complete=true, close this block with a brief affirmation only. "
            "Ask no question, and do not open the next block. "
            "If block_complete=false, end with one question that stays on this block."
        )
    elif not choice_on_screen and not presenting_dynamic_mcq:
        if move_on_close:
            lines.append(
                "The learner already asked to move on. Close this block with a brief statement only. Do not ask a question."
            )
        elif goal_start in {"explain", "deepen"}:
            lines.append("Do not end this turn with a question. The goal question waits until the learner moves on.")
        elif goal_start == "clarify":
            lines.append(
                "Answer the learner's question before teaching onward. The goal question waits until the learner moves on."
            )
        elif goal_start == "ask":
            lines.append(
                "Ask the opening question for this goal. One question, and it comes last. Do not answer it."
            )
            lines.append("End a teaching or probing turn with a single clear question.")
        else:
            q_line = "End a teaching or probing turn with a single clear question."
            if include_close:
                q_line += " A unit close or course outro asks no new question."
            lines.append(q_line)

    del orient_mode
    del close_depth
    return lines


def _previous_tutor_text(last_messages: str, last_answer: str) -> str:
    """The tutor line before the learner's latest answer."""
    recent = _recent_without_last_answer(last_messages, last_answer)
    parts = [part.strip() for part in recent.split("|") if part.strip()]
    for part in reversed(parts):
        if part.lower().startswith("assistant:"):
            return part.split(":", 1)[1].strip()
    return ""


def _worked_close_kind(
    block: dict,
    substep: str,
    last_answer: str,
    last_messages: str,
    active_block_state: dict | None,
    cfg: dict | None,
) -> str:
    """affirm, continue, or bare_yes. Empty on every other turn."""
    if str(block.get("type") or "") != "worked_example":
        return ""
    from app.kc_loop import answer_addresses_substep, tutor_asked_to_continue, worked_continue_answer

    prior = _previous_tutor_text(last_messages, last_answer)
    if tutor_asked_to_continue(prior) and worked_continue_answer(last_answer):
        return "continue"
    if substep == "solo_solve" and answer_addresses_substep(
        block, substep, last_answer, active_block_state, cfg
    ):
        return "affirm"
    if worked_continue_answer(last_answer) and _proceed_text_is_yes(last_answer):
        return "bare_yes"
    return ""


def _proceed_text_is_yes(answer: str) -> bool:
    from app.kc_loop import _proceed_text

    return _proceed_text(answer) == "yes"


def _recent_without_last_answer(last_messages: str, last_answer: str) -> str:
    """Drop the newest user line when The last answer already states it."""
    text = (last_messages or "").strip()
    answer = (last_answer or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split("|") if part.strip()]
    if answer and parts and parts[-1] == f"user: {answer}":
        parts = parts[:-1]
    return " | ".join(parts)


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
    ]
    if int(attempts or 0):
        lines.append(f"Attempts on this block/substep so far: {attempts}.")
    lines.append(f"Dialogue turns on this block: {dialogue_turns}.")
    if substep in {"explain_topic", "summary_check"}:
        lines.append(f"Topic index: {int(active_block_state.get('topic_index') or 0)}.")
        lines.append(
            f"Elaboration turns on this topic: {int(active_block_state.get('elaboration_turns') or 0)}."
        )
    lines.append(f"The last answer was: {last_answer or 'none yet'}.")
    tier = (hint_tier or "").strip()
    if tier and tier != "none":
        lines.append(f"The hint tier already given is: {tier}.")
    if eliminated:
        lines.append(f"Eliminated MCQ choice indices: {eliminated}.")
    if (affect or "").strip():
        lines.append(f"The child seems {affect}.")
    lines.append("The child has asked for help." if help_requested else "The child has not asked for help.")
    lines.append(f"Off-course turns so far: {off_course_count}.")
    recent = _recent_without_last_answer(last_messages, last_answer)
    lines.append(f"Recent messages: {recent or 'none yet'}.")
    lines.append(
        f"The last matched wrong move was: {last_misconception}."
        if last_misconception
        else "No wrong move has matched yet."
    )
    if int(reveals or 0):
        lines.append(f"Reveals used so far: {reveals}.")
    lines.append(f"Extra enrichment turns so far: {enrichment_turns}.")
    if rubric_met:
        lines.append("Evidence points already met: " + ", ".join(rubric_met) + ".")
    lines.append("A redirect is already pending." if redirect_pending else "No redirect is pending.")
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


def _what_to_return(
    *,
    needs_dynamic_mcq: bool = False,
    presenting_dynamic_mcq: bool = False,
    block_type: str = "",
    safety: dict | None = None,
    close_block_only: bool = False,
    summary_elaborate: bool = False,
    clarify_help: bool = False,
) -> list[str]:
    if presenting_dynamic_mcq:
        reply_line = (
            "reply is a short lead-in only. "
            "Put the question stem and the choices only in generated_mcq. "
            "Do not list the options in reply, and do not ask the child to type a letter."
        )
    else:
        reply_line = "reply is the only text the child reads."
    lines = [
        "Return reply, decision, substep_passed, block_complete, generated_mcq, rubric_met, misconception, hint_tier, help_requested, off_course, affect, confidence, score_justification, what_was_strong, and what_to_work_on.",
        reply_line,
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
    if block_type == "explanation":
        if summary_elaborate:
            lines.append(
                "On this summary turn, set substep_passed=false and block_complete=false. "
                "Elaborate on the recap. Do not set block_complete=true."
            )
        else:
            lines.append(
                "On an explanation block, set substep_passed=false when the learner asks a question or wants elaboration, "
                "and substep_passed=true when they are ready to proceed. "
                "Set block_complete=true only on the summary check when they have no final questions. "
                "When block_complete=true, reply is a brief affirmation only, with no question. Never quiz."
            )
    if clarify_help:
        lines.append("Set help_requested=true. The learner asked a question.")
    if close_block_only and not summary_elaborate:
        lines.append(
            "When block_complete=true, reply affirms this block only and asks no question. "
            "Do not describe the next block. Set generated_mcq to null."
        )
    if presenting_dynamic_mcq:
        lines.append(
            "You MUST populate generated_mcq with question_stem, choices, correct_index, and distractor_rationales."
        )
    elif needs_dynamic_mcq:
        lines.append(
            "If this reply opens the next dynamic MCQ, you MUST populate generated_mcq with question_stem, choices, correct_index, and distractor_rationales. "
            "Otherwise set generated_mcq to null."
        )
    else:
        lines.append("Set generated_mcq to null when not generating a new dynamic MCQ.")
    from app.ai_safety import safety_return_line

    lines.append(safety_return_line(safety))
    return lines


_SECTION_ORDER = (
    "Safety",
    "Who you are talking to",
    "How to sound",
    "How to teach",
    "What to return",
    "What to teach",
    "This turn",
    "What just happened",
)

_RETURN_SCHEMA_RESTATE = (
    "Return reply, decision,",
    "reply is the only text the child reads.",
    "reply is a short lead-in only.",
    "decision is stay,",
    "rubric_met lists",
    "misconception is the stored",
    "hint_tier is nudge",
    "affect is engaged",
)

_SUMMARY_CHECKIN_PREFIXES = (
    "Explain the topic clearly, then ask if they have any questions",
    "The learner is on the block summary.",
    "Close each topic",
    "On the summary step,",
    "You are on the summary step",
)

_MISS_LADDER_PREFIXES = (
    "Scaffolding escalation",
    "Answer a tangent",
    "You may follow a short tangent",
    "Stay on this component. If the learner leaves",
    "Misconception policy",
    "If a stored wrong move matches",
    "the first time a stored wrong move matches",
)

_COMPLETING_REPLY = (
    "That completing reply is a brief affirmation only. "
    "Ask no question. Do not open the next block."
)


def _line_starts(line: str, prefixes: tuple[str, ...]) -> bool:
    text = line.strip()
    return any(text.startswith(prefix) for prefix in prefixes)


def _fit_prompt_sections(
    sections: list[tuple[str, list[str]]],
    *,
    include_generated_mcq: bool,
) -> list[tuple[str, list[str]]]:
    """Drop repeated rules and put the byte-stable sections first."""
    by_title = {title: [line for line in lines if line and str(line).strip()] for title, lines in sections}
    teach = by_title.get("What to teach") or []
    explanation = any(line.startswith("Active block type: explanation") for line in teach)
    summary = explanation and any("summary_check" in line for line in teach)

    returned: list[str] = []
    for line in by_title.get("What to return", []):
        if _line_starts(line, _RETURN_SCHEMA_RESTATE):
            continue
        if not include_generated_mcq and line.strip() == "Set generated_mcq to null when not generating a new dynamic MCQ.":
            continue
        if not include_generated_mcq and "set generated_mcq to null" in line.lower():
            line = line.replace(" Otherwise set generated_mcq to null.", "")
            line = line.replace("Set generated_mcq to null.", "")
            line = line.strip()
            if not line:
                continue
        returned.append(line)
    by_title["What to return"] = returned

    by_title["This turn"] = [
        line for line in by_title.get("This turn", []) if not line.startswith("Turn Stance (")
    ]

    if explanation:
        kept_teach: list[str] = []
        for line in by_title.get("How to teach", []):
            if _line_starts(line, _MISS_LADDER_PREFIXES):
                continue
            if line.startswith("Explanatory block override:") and "do not open the next block" not in line.lower():
                line = (
                    f"{line.rstrip()} When block_complete=true, ask no question, "
                    "including no check-in about final questions, and do not open the next block."
                )
            kept_teach.append(line)
        by_title["How to teach"] = kept_teach

    if summary:
        for title in ("What to teach", "This turn", "How to teach"):
            kept: list[str] = []
            for line in by_title.get(title, []):
                lowered = line.lower()
                if _line_starts(line, _SUMMARY_CHECKIN_PREFIXES) and "do not ask" not in lowered and "ask no question" not in lowered:
                    continue
                if ", affirm Block" in line and "open Block" in line:
                    head = line.split(", affirm", 1)[0]
                    line = (
                        f"{head}, close that block with a brief affirmation only. "
                        "Ask no question. Do not mention the next block and do not open it."
                    )
                if line.startswith("For Block") and "populate generated_mcq" in line:
                    continue
                if line.startswith("Give a cohesive summary") and "do not open the next block" not in line.lower():
                    line = f"{line.rstrip()} {_COMPLETING_REPLY}"
                kept.append(line)
            by_title[title] = kept

    ordered: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for title in _SECTION_ORDER:
        if title in by_title:
            ordered.append((title, by_title[title]))
            seen.add(title)
    for title, lines in sections:
        if title not in seen:
            ordered.append((title, by_title.get(title, lines)))
    return ordered


def _blocks_text(sections: list[tuple[str, list[str]]]) -> str:
    include_generated_mcq = any(
        "populate generated_mcq" in line for _, lines in sections for line in lines
    )
    sections = _fit_prompt_sections(sections, include_generated_mcq=include_generated_mcq)
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
    safety: dict | None = None,
) -> dict:
    """Assemble the prompt for the active block (`node.blocks[step]`). Safety comes first."""
    del stability
    del moves
    del course_position
    from app.ai_safety import normalize_ai_safety, safety_lines

    safety_cfg = normalize_ai_safety(safety, strict=False)
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
    confirm_why = str(((cfg.get("blocks") or {}).get("mcq") or {}).get("confirm_why_on_correct") or "on_retry_only")
    pending_why = (
        btype == "mcq"
        and substep == "choice"
        and confirm_why == "on_retry_only"
        and int(attempts or 0) > 0
    )
    if pending_why:
        is_last_substep = False
    summary_phase = ""
    if btype != "explanation" and substeps and substeps[-1] == "summary_check":
        if substep == "summary_check":
            summary_phase = "check"
            is_last_substep = False
        elif len(substeps) >= 2 and (
            substep == substeps[-2] or (btype == "mcq" and substep == "awaiting_why")
        ):
            summary_phase = "task"
    is_final_block_and_substep = is_last_block and is_last_substep

    data = active_block.get("data") if isinstance(active_block.get("data"), dict) else {}
    presenting_dynamic_mcq = (
        btype == "mcq"
        and str(data.get("mode") or "static") == "dynamic"
        and _cached_generated_mcq(state_dict) is None
    )
    needs_dynamic_mcq = presenting_dynamic_mcq
    close_block_only = (not opening) and is_last_substep and index + 1 < len(blocks)
    if summary_phase == "check" and not opening and index + 1 < len(blocks):
        close_block_only = True
    widget_on = choice_on_screen or block_uses_choice_widget(active_block, substep, state_dict)
    include_close = is_final_block_and_substep or unit_complete or course_complete or (
        summary_phase == "check" and is_last_block
    )
    frag_self_exp = bool(((cfg.get("blocks") or {}).get("topic_goal") or {}).get("fragment_self_explanation", True))
    interests = ", ".join(str(item) for item in (student.interests or []) if str(item).strip()) or "none named"
    cp = effective_child_profile(student)
    turn_kind = compute_turn_kind(
        opening=opening,
        unit_complete=unit_complete,
        course_complete=course_complete,
        transition_from_block=transition_from_block,
        attempts=int(attempts or 0),
        hint_tier=hint_tier or "nudge",
        reveals=int(reveals or 0),
    )
    from app.kc_blocks import passage_reprint_kind

    passage_reprint = bool(
        passage_reprint_kind(active_block, cfg, opening=opening, last_answer=last_answer or "")
    )
    worked_close = _worked_close_kind(
        active_block,
        substep,
        last_answer or "",
        last_messages or "",
        state_dict,
        cfg,
    )
    if worked_close in {"affirm", "continue"} and index + 1 < len(blocks):
        close_block_only = True
    if worked_close in {"affirm", "continue"} and is_last_block:
        is_final_block_and_substep = True
        include_close = True
    from app.kc_loop import learner_asks_clarification

    clarify_help = bool(
        btype == "topic_goal" and substep == "explain" and learner_asks_clarification(last_answer or "")
    )
    summary_elaborate = _summary_elaboration(active_block, substep, last_answer or "")

    prompt = _blocks_text(
        [
            (
                "Safety",
                safety_lines(safety_cfg, age=student.age if isinstance(student.age, int) else None),
            ),
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
                    turn_kind=turn_kind,
                    instructional_stance=str(over.get("instructional_stance") or "guided_discovery"),
                    scaffolding_escalation=str(
                        over.get("scaffolding_escalation") or "progressive_nudge_then_scaffold"
                    ),
                    misconception_policy=str(over.get("misconception_policy") or "explain_and_retry_once"),
                    prerequisite_support_policy=str(
                        over.get("prerequisite_support_policy") or "inline_micro_recap"
                    ),
                    encouragement_style=str(over.get("encouragement_style") or "process_praise"),
                    challenge_appetite=str(cp.get("challenge_appetite") or "steady"),
                    learning_support=str(cp.get("learning_support") or "none"),
                    communication_tone=str(cp.get("communication_tone") or "warm_and_encouraging"),
                    active_block_state=state_dict,
                    close_block_only=close_block_only,
                    summary_phase=summary_phase,
                    summary_stay=summary_phase == "check" and is_last_block,
                    last_answer=last_answer,
                    cfg=cfg,
                    worked_close=worked_close,
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
                next_block=blocks[index + 1] if close_block_only else None,
                opening=opening,
                last_answer=last_answer,
                worked_close=worked_close,
            ),
            ),
            (
                "Who you are talking to",
                _who_you_are_talking_to(
                    student,
                    profile,
                    active_block,
                    interests,
                    cfg,
                    state_dict,
                    passage_reprint=passage_reprint,
                ),
            ),
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
                    student=student,
                    presenting_dynamic_mcq=presenting_dynamic_mcq,
                    close_block_only=close_block_only,
                    last_answer=last_answer,
                    opening=opening,
                    worked_close=worked_close,
                ),
            ),
            ("How to sound", _how_to_sound(profile=profile, student=student, turn_kind=turn_kind)),
            (
                "What just happened",
                _what_happened(
                    attempts=attempts,
                    hint_tier=hint_tier,
                    reveals=reveals,
                    off_course_count=off_course_count,
                    affect=affect,
                    enrichment_turns=enrichment_turns,
                    help_requested=bool(help_requested) or clarify_help,
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
            (
                "What to return",
                _what_to_return(
                    needs_dynamic_mcq=needs_dynamic_mcq,
                    presenting_dynamic_mcq=presenting_dynamic_mcq,
                    block_type=btype,
                    safety=safety_cfg,
                    close_block_only=close_block_only,
                    summary_elaborate=summary_elaborate,
                    clarify_help=clarify_help,
                ),
            ),
        ]
    )
    return {
        "system_prompt": prompt,
        "response_schema": turn_response_schema(
            presenting_dynamic_mcq=presenting_dynamic_mcq,
            needs_dynamic_mcq=needs_dynamic_mcq,
        ),
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
