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


def topic_goal_follows_explanation(block: dict, previous: dict | None) -> bool:
    """True when this topic and goal sits immediately after an explanation on the same component."""
    if str((block or {}).get("type") or "").strip() != "topic_goal":
        return False
    return str((previous or {}).get("type") or "").strip() == "explanation"


def initial_block_state(block: dict, cfg: dict | None = None, *, previous: dict | None = None) -> dict:
    """State written when a block is entered."""
    state = {"substep": default_substep_for_block(block, cfg), "dialogue_turns": 0}
    if str(block.get("type") or "").strip() == "explanation":
        state["topic_index"] = 0
        state["elaboration_turns"] = 0
    if topic_goal_follows_explanation(block, previous):
        # The explanation already taught the concept. Open on the goal question.
        state["substep"] = "main"
    return state


def _explanation_depth(cfg: dict | None) -> int:
    bcfg = ((cfg or {}).get("blocks") or {}).get("explanation") or {}
    try:
        depth = int(bcfg.get("explanation_depth", 4) or 4)
    except (TypeError, ValueError):
        depth = 4
    return min(5, max(1, depth))


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


READY_FIELD = "ready_to_move_on"


def _schema_with_ready(schema: dict) -> dict:
    """Put the ready flag first, so the model settles it before it writes the reply."""
    ready = {
        "type": "boolean",
        "description": (
            "True when the learner's message means they are ready to go on to the goal question, "
            "such as What's next?, ok, I get it, or let's go. False for a question, a remark, or a request for more."
        ),
    }
    copied = dict(schema)
    copied["properties"] = {READY_FIELD: ready, **schema["properties"]}
    copied["required"] = [READY_FIELD, *schema["required"]]
    return copied


def turn_response_schema(
    *,
    presenting_dynamic_mcq: bool = False,
    needs_dynamic_mcq: bool = False,
    ready_check: bool = False,
) -> dict:
    """Include generated_mcq only when this turn presents one or is the last substep before one.

    ready_to_move_on is included only on an opening-explanation turn that asks for it.
    """
    include = bool(presenting_dynamic_mcq or needs_dynamic_mcq)
    schema = RESPONSE_SCHEMA if include else _schema_without_generated_mcq(RESPONSE_SCHEMA)
    if presenting_dynamic_mcq:
        schema = _dynamic_mcq_schema(schema)
    if ready_check:
        schema = _schema_with_ready(schema)
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


def _teach_back_misconception_guard(node: KcNode) -> str:
    """Name this node's wrong move, or a domain-neutral guard when none is stored."""
    wrongs = _wrong_moves(node)
    if wrongs:
        named = "; ".join(wrongs)
        return (
            f"Misconception guard: do not tag \"{named}\" "
            "when the learner's explanation shows the idea still applies, "
            "or when the learner is answering the follow-up example prompt. "
            "An example that answers the follow-up is the explanation they were asked for, not that misconception."
        )
    return (
        "Misconception guard: do not tag a stored wrong move "
        "when the learner's explanation shows the idea still applies, "
        "or when the learner is answering the follow-up example prompt. "
        "An example that answers the follow-up is the explanation they were asked for."
    )


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
    last_answer: str = "",
) -> list[str]:
    del cfg, active_block_state, last_answer
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

    if passage_reprint:
        parts.append(
            "The response_length sentence cap applies ONLY to your coaching and question below the passage, "
            "never to the passage text itself."
        )
    else:
        parts.append(_RESPONSE_LENGTH_LINES.get(cp["response_length"], _RESPONSE_LENGTH_LINES["balanced"]))
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


def _agreement_close(summary_begin: bool, worked_close: str, last_answer: str) -> bool:
    """A passed block, and the child line is only yes or let's move on."""
    if not summary_begin or worked_close == "affirm":
        return False
    from app.kc_loop import move_on_agreement

    return move_on_agreement(last_answer)


def _close_summary_sentence(close_depth: str, kind: str) -> str:
    if kind == "time_boxed" or close_depth == "concise":
        return "Keep the unit close to one or two concise sentences."
    return "Close in one sentence. Do not praise. Do not recap."


def _close_body() -> str:
    return (
        "A known unit says the unit is complete, and names this component. "
        "A fragile unit says the unit is paused and still needs another look, and names the patch when there is one. "
        "Do not call a fragile unit finished work. Do not add a second congratulations."
    )


def _outro_sentence(others_known: bool, course_title: str, *, required: bool) -> str:
    if others_known:
        if required:
            return f"Then add the course outro: {course_title} is complete."
        return (
            "If this unit ends known or fragile, every other target is already known or fragile. "
            f"After the close, add the course outro: {course_title} is complete."
        )
    return "Another target is not known or fragile yet. Do not write a course outro. The close may point at the next card."


_SUMMARY_NO_PRAISE = (
    "Asking a question, asking for background, or asking to move on is not noteworthy work. "
    "Do not say Great question, Nice work, Great job, or any congratulation on those turns. "
    "A warm tone does not add praise."
)
_WORKED_AFFIRM = (
    "Worked close: This solo answer is correct. Reply with a short affirmation of that answer. "
    "Do not ask Ready for the next challenge. Do not summarize this part and do not ask whether to discuss or move on. "
    "Set substep_passed=true and block_complete=true. Ask no question. Do not open the next part."
)
_WORKED_CONTINUE = (
    "Worked close: The learner is answering a continue question. "
    "Reply with one short closing line and no question. Do not restate the summary. Do not ask again. "
    "Set block_complete=true. Do not open the next part."
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
    "Goal start: The learner is still on the explanation. Explain this same topic in two or three sentences, "
    "from a fresh angle. Ask no question."
)
_GOAL_START_CLARIFY = (
    "Goal start: The learner asked a question. Answer that question first, in a sentence or two, "
    "then return to this topic. Set help_requested=true. Do not ask the goal question. "
    "Do not ask a question applies only to your own reply, so do not quiz. "
    "It does not mean ignore the question they typed."
)
_GOAL_START_ASIDE = (
    "Goal start: The learner typed a side remark. It is not an attempt and it is not a request to learn more. "
    "Answer it inside the safety rules, in one or two sentences, then one line back to the active lesson. "
    "Do not start a new explanation of this topic. "
    "Do not ask the goal question. "
    "Do not ask a question applies to your lesson text, not to the student. "
    "It does not mean ignore the question they typed. "
    "Do not score this reply. Do not say Nice connection. "
    "Set help_requested=true, substep_passed=false, and block_complete=false. "
    "Do not call this reply partial, a close, or a good start."
)
_GOAL_START_READY = (
    "Ready check: If the learner's message means they are ready to go on, such as What's next?, ok, I get it, "
    "or let's go, set ready_to_move_on=true and ask the opening question for this goal instead. "
    "One question, and it comes last. Do not answer it. "
    "That reply replaces every line here that holds the goal question back. "
    "Otherwise set ready_to_move_on=false."
)
_GOAL_START_NO_TURN = (
    "Do not tell the learner it is their turn, and do not ask them to put the idea in their own words, "
    "unless this reply asks the goal question."
)
_GOAL_START_CAP = (
    "Goal question: The learner has had two extra turns on this explanation, so you ask the goal question now. "
    "If their last message was a question or a remark, answer it in one sentence first. "
    "Do not explain the topic again. "
    "Ask the opening question for this goal. One question, and it comes last. Do not answer it."
)
_GOAL_EARLY_ANSWER = (
    "Goal answer: The learner answered during the explanation, before the goal question was asked. "
    "Count that answer as their attempt at this goal and score it. "
    "If it does not pass, acknowledge what they said, then ask the opening question for this goal. "
    "One question, and it comes last."
)
_EXPLANATION_CAP = (
    "The learner has had two extra turns on this topic, so the lesson moves on now. "
    "If their last message was a question or a remark, answer it in one sentence first. "
    "Then follow the move-on instruction in What to teach in this same reply: teach the next topic, "
    "or close when this was the last topic. Do not quiz."
)
_LAST_TOPIC_CLOSE = (
    "The close is one or two sentences: what this part was, and that they are done. "
    "Do not restate each topic. Do not ask whether to move on. Never say the word block."
)
_LAST_TOPIC_ANSWER = (
    "Answer the question in one or two sentences, then close. "
    "The close is one or two sentences: what this part was, and that they are done. "
    "Do not restate each topic. Do not ask whether to move on. Never say the word block."
)
_LAST_TOPIC_NEXT = (
    "Ask no question. Do not open the next part in this reply. "
    "The next part arrives in its own message. Set block_complete=true."
)
_LAST_TOPIC_END = (
    "This was the last part. Ask no question. Set block_complete=true. Do not open the next part."
)
_SIDE_STAY = (
    "Stay on course: this is not an attempt at the goal. "
    "Answer it inside the safety rules, in one or two sentences, then repeat the active question "
    "and ask the goal again. Set substep_passed=false and block_complete=false. "
    "Do not offer to move on and do not offer another example. "
    "Stay on this step and this substep. "
    "Do not call this reply partial, a close, or a good start."
)
_SIDE_FOLLOW = (
    "Stay on course is off. You may follow this tangent. Do not force a return to the question. "
    "The score still comes only from this step."
)
_SIDE_EXPLAIN = (
    "The learner typed a side request, not an attempt at the goal. "
    "Answer it inside the safety rules, in one or two sentences, then return to this topic. "
    "Do not ask a question applies only to your own reply, so do not quiz. "
    "It does not mean ignore what they typed. "
    "Do not call this reply partial, a close, or a good start."
)
_GOAL_START_ASK = (
    "Goal question: The learner moved on. Ask the opening question for this goal. "
    "One question, and it comes last. Do not answer it."
)
_SUMMARY_CONGRATULATE = "Congratulate the learner once."
_NEVER_SAY_BLOCK = "Never say the word block to the learner."
_SUMMARY_CHOICE = (
    "Do not offer one more example. Do not ask the goal again. "
    "Ask one question only: move on, or ask one more question."
)
_SUMMARY_REMINDER = (
    "If they ask one further question, answer it, then close. "
    "Do not ask move on, or one more question, again. "
    "Set block_complete=true. Ask no question. "
    "Do not return to the goal, the explain step, or another summary."
)
_SUMMARY_MOVE_ON = (
    "If they choose to move on, set block_complete=true. Ask no question and do not open the next part in this reply."
)
_SUMMARY_BEGIN = (
    "Close in one sentence. Ask no question. Do not praise. Do not recap. "
    f"{_NEVER_SAY_BLOCK} Do not open the next part in this reply. "
    "The next part arrives in its own message. Set block_complete=true."
)
_SUMMARY_BEGIN_LAST = (
    "Close in one sentence. Ask no question. Do not praise. Do not recap. "
    f"{_NEVER_SAY_BLOCK} This was the last part. "
    "Do not open another part. Set block_complete=true."
)
_OPENING_ASK = (
    "Opening message: This is the only message that opens this step. "
    "Ask the question and nothing else. Give no cue and no example before the first try. "
    "Do not praise what came before. Never say the word block to the learner."
)
_OPENING_HOLD = (
    "Opening message: This is the only message that opens this step. "
    "Do not praise what came before. Give no cue before the first try. "
    "Never say the word block to the learner."
)
_SUMMARY_ELABORATE = (
    "The learner asked to elaborate on the recap. Elaborate on the summary in this reply. "
    "Set substep_passed=false and block_complete=false. Do not complete this part and do not advance. "
    "Do not close with a brief affirmation. Do not open the next part. "
    "Then ask the same single choice: move on, or ask one more question. "
    "Do not return to the goal, the explain step, or another summary. "
    "Only an explicit move-on, such as got it - move on, no final questions, let's continue, "
    "let's go, move on, next, or yes, may complete this part."
)


def _typed_side_request(
    block: dict,
    substep: str,
    answer: str,
    state: dict | None,
    cfg: dict | None,
) -> bool:
    """A question, "tell me", or a side story that is not a goal attempt."""
    if not str(answer or "").strip():
        return False
    from app.kc_loop import unscored_side_request

    return unscored_side_request(
        block,
        substep,
        answer,
        state if isinstance(state, dict) else {},
        cfg,
    )


def _goal_start_mode(
    block: dict,
    substep: str,
    *,
    opening: bool,
    last_answer: str,
    cfg: dict | None = None,
    state: dict | None = None,
) -> str:
    """explain, deepen, aside, clarify, ask, cap, or attempt on the opening explanation.

    Empty once the question is open. After the opening turn this is the same
    reading the loop uses, so the reply and the step change agree.
    """
    if str(block.get("type") or "") != "topic_goal" or substep != "explain":
        return ""
    from app.kc_loop import explain_step_turn, stay_on_course_enabled, unanswered_side_turn

    if opening:
        if (
            str(last_answer or "").strip()
            and stay_on_course_enabled(cfg)
            and unanswered_side_turn(block, substep, last_answer, state, cfg)
        ):
            return "aside"
        return "explain"
    return explain_step_turn(block, last_answer, state, cfg)


_GOAL_START_HOLDS = {"explain", "deepen", "clarify", "aside"}


def _ready_check(
    block: dict,
    substep: str,
    *,
    opening: bool,
    last_answer: str,
    cfg: dict | None = None,
    state: dict | None = None,
) -> bool:
    """This turn asks the model whether the learner is ready for the goal question."""
    if opening or not str(last_answer or "").strip():
        return False
    mode = _goal_start_mode(
        block, substep, opening=opening, last_answer=last_answer, cfg=cfg, state=state
    )
    from app.kc_loop import model_ready_counts

    return model_ready_counts(mode, last_answer)


def _explanation_capped(substep: str, state: dict | None) -> bool:
    from app.kc_loop import explanation_topic_capped

    return explanation_topic_capped(substep, state)


def _summary_elaboration(block: dict, substep: str, last_answer: str) -> bool:
    if str(block.get("type") or "") != "explanation" or substep != "summary_check":
        return False
    from app.kc_loop import learner_wants_recap_elaboration

    return learner_wants_recap_elaboration(last_answer)


def _side_question_reply(answer: str) -> str:
    asked = " ".join((answer or "").split())
    return (
        "Side question: The learner asked a question instead of answering the active step. "
        f"Their question: {asked}. "
        "Do not score this message. Set help_requested=true, substep_passed=false, and block_complete=false. "
        "Answer that question in one or two sentences. "
        "If they ask what something is or who someone is, define it. "
        "Then repeat the active question unchanged. "
        "Do not say the reply was partial, close, or a good start."
    )


def _prompts_side_question(
    block: dict,
    substep: str,
    last_answer: str,
    *,
    opening: bool,
    cfg: dict | None = None,
    state: dict | None = None,
) -> bool:
    """True when this turn should answer a side question and then re-ask.

    The topic-goal explain step and explanatory blocks already have their own lines.
    """
    if str(block.get("type") or "") == "explanation":
        return False
    from app.kc_loop import summary_ready_signal

    if str(substep or "") == "summary_check" and summary_ready_signal(last_answer):
        return False
    if _goal_start_mode(
        block,
        substep,
        opening=opening,
        last_answer=last_answer,
        cfg=cfg,
        state=state,
    ) in _GOAL_START_HOLDS | {"cap"}:
        return False
    from app.kc_loop import learner_side_question

    return learner_side_question(last_answer, block)


def _summary_close_lines(
    *,
    phase: str,
    revealed: bool,
    opening: bool,
    block_type: str = "",
    last_answer: str = "",
    side_question: bool = False,
    moving_on: bool = False,
    has_next: bool = False,
) -> list[str]:
    """How to speak on the summary check, and how to answer a learner who is already there."""
    if phase == "check" and moving_on:
        if revealed:
            begun = (
                "The learner chose to move on. Do not congratulate. "
                "Close in one sentence. Ask no question. Do not praise. Do not recap. "
                f"{_NEVER_SAY_BLOCK} Do not open the next part in this reply. "
                "The next part arrives in its own message. Set block_complete=true."
                if has_next
                else (
                    "The learner chose to move on. Do not congratulate. "
                    "Close in one sentence. Ask no question. Do not praise. Do not recap. "
                    f"{_NEVER_SAY_BLOCK} Do not ask the goal again. Set block_complete=true."
                )
            )
            return [begun]
        return [_SUMMARY_BEGIN if has_next else _SUMMARY_BEGIN_LAST]
    if phase == "task" and block_type == "topic_goal" and _ready_to_move_on(last_answer):
        return [
            (
                "Summary close: The learner asked to move on or to go to the next part. "
                "Set block_complete=true and close with a brief statement only. "
                "Do not ask a new question and do not ask again. Do not open the next part."
            ),
            _SUMMARY_NO_PRAISE,
        ]
    if side_question and phase in {"task", "check"}:
        if phase == "check" and not revealed:
            from app.kc_loop import learner_wants_recap_elaboration

            asked = " ".join((last_answer or "").split())
            if learner_wants_recap_elaboration(last_answer):
                return [
                    (
                        "This part is already finished. "
                        f"Their question: {asked}. "
                        "Do not score this message. Set help_requested=true, substep_passed=false, and block_complete=false. "
                        "Answer that question in one or two sentences. "
                        "If they ask what something is or who someone is, define it. "
                        "Then ask the same single choice: move on, or ask one more question. "
                        "Do not return to the goal, the explain step, or another summary. "
                        "Do not repeat the goal question. "
                        "Do not say the reply was partial, close, or a good start. "
                        "Do not open the next part."
                    ),
                    _SUMMARY_NO_PRAISE,
                ]
            return [
                (
                    "This part is already finished. "
                    f"Their question: {asked}. "
                    "Answer that question in one or two sentences. "
                    "If they ask what something is or who someone is, define it. "
                    "Then close. Do not ask move on, or one more question, again. "
                    "Set block_complete=true. Ask no question. "
                    "Do not repeat the goal question. "
                    "Do not open the next part."
                ),
                _SUMMARY_NO_PRAISE,
            ]
        lines = [_side_question_reply(last_answer)]
        if phase == "task" and block_type == "topic_goal":
            lines.append(
                "Then ask the goal again. Do not summarize this part, do not offer to move on, and do not offer another example."
            )
        lines.append(_SUMMARY_NO_PRAISE)
        return lines
    if phase == "task":
        lines = []
        if block_type == "topic_goal":
            lines.append(
                "Summary close: If the learner asked a question or for background and has not answered the goal, "
                "answer it and ask the goal again. Set substep_passed=false and block_complete=false. "
                "Do not summarize this part, do not offer to move on, and do not offer another example."
            )
        if block_type == "worked_example":
            begun = _SUMMARY_BEGIN if has_next else _SUMMARY_BEGIN_LAST
            satisfy = (
                "Summary close: If this answer satisfies the substep, set substep_passed=true and block_complete=true. "
                f"{begun}"
            )
        else:
            satisfy = (
                "Summary close: If this answer satisfies the substep, set substep_passed=true and block_complete=false. "
                f"{_SUMMARY_CONGRATULATE} {_SUMMARY_CHOICE} Do not open the next part."
            )
        lines.extend(
            [
                satisfy,
                (
                    "Summary close on the attempt limit: If this is the last allowed try and the answer still misses the goal, "
                    "set substep_passed=false and block_complete=false. Highlight that the learner reached the attempt limit "
                    "and did not finish this part yet. Never say congratulations and do not praise them as if they passed. "
                    "Briefly summarize the key takeaway they missed. Ask whether they want to keep trying or discussing the goal, "
                    "which can still complete this part, or move on to the next part anyway."
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
                "Summary close: The learner reached the attempt limit and did not finish this part yet. "
                "Highlight that. Never say congratulations and do not praise them as if they passed. "
                "Briefly summarize the key takeaway they missed. Ask whether they want to keep trying or discussing the goal, "
                "which can still complete this part, or move on to the next part anyway."
            )
        ]
    else:
        lines = [
            (
                "Summary close: The learner finished this part. "
                f"{_SUMMARY_CONGRATULATE} {_NEVER_SAY_BLOCK} {_SUMMARY_CHOICE}"
            )
        ]
    if opening:
        lines.append(_SUMMARY_NO_PRAISE)
        return lines
    lines.append(
        "Summary reply: If the learner had not completed the block and this reply now demonstrates the goal, "
        "set substep_passed=true and block_complete=false, affirm that they have now completed the block, "
        f"{_SUMMARY_CONGRATULATE} {_SUMMARY_CHOICE}"
    )
    lines.append(f"Summary reply: {_SUMMARY_REMINDER} Do not open the next part.")
    closing = (
        "Summary reply: If they choose to close and move on, set block_complete=true and reply with a brief "
        "closing statement only. Ask no question and do not open the next part."
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
    side_question: bool = False,
    omit_recap: bool = False,
) -> str:
    if summary_stay and side_question and not unit_complete and not course_complete:
        return (
            "Close Contract: Answer this one further question, then close. "
            "Do not ask move on, or one more question, again. "
            "Set block_complete=true. Ask no question. Do not return to the goal."
        )
    if summary_stay and not unit_complete and not course_complete:
        length = _close_summary_sentence(close_depth, kind)
        outro = _outro_sentence(others_known, course_title, required=False)
        return " ".join(
            (
                "Close Contract: If block_complete=true on this summary, include the unit close and ask no new question. "
                "If block_complete=false, ask one question only: move on, or ask one more question.",
                length,
                _close_body(),
                outro,
            )
        )
    if not is_final_block_and_substep and not unit_complete and not course_complete:
        return (
            "Mid-Unit Contract: Advance the substep or the next part when satisfied. "
            "The unit is not finished. This reply must NEVER say the unit is complete. "
            "Do not say this component is finished."
        )
    length = _close_summary_sentence(close_depth, kind)
    close = _close_body()
    summary = ""
    if not omit_recap:
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
    if summary:
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
    early_answer: bool = False,
    summary_begin: bool = False,
    has_next: bool = False,
    forecast: object | None = None,
    ready_check: bool = False,
    ask_goal_now: bool = False,
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
    goal_start = _goal_start_mode(
        block,
        substep,
        opening=opening,
        last_answer=last_answer,
        cfg=cfg,
        state=active_block_state,
    )
    side_question = _prompts_side_question(
        block,
        substep,
        last_answer,
        opening=opening,
        cfg=cfg,
        state=active_block_state,
    )
    if ask_goal_now:
        lines.append(
            "Goal question: This concept was just taught. Ask the opening question for this goal. "
            "Do not teach the concept again. One question, and it comes last. Do not answer it."
        )
    elif goal_start == "explain":
        lines.append(_GOAL_START_EXPLAIN)
        if opening and step_index == 0 and outline:
            lines.append(
                f"Component outline to weave into that explanation, not as a question: {_finish(outline)}"
            )
    elif goal_start == "deepen":
        lines.append(_GOAL_START_DEEPEN)
    elif goal_start == "aside":
        lines.append(_GOAL_START_ASIDE)
    elif goal_start == "clarify":
        lines.append(_GOAL_START_CLARIFY)
    elif goal_start == "ask":
        lines.append(_GOAL_START_ASK)
        if _proceed_text_is_yes(last_answer) and "?" not in (last_answer or ""):
            lines.append(
                "A bare yes does not start a new lesson. Do not explain the topic. "
                "Ask the opening question only."
            )
    elif goal_start == "cap":
        lines.append(_GOAL_START_CAP)
    if early_answer:
        lines.append(_GOAL_EARLY_ANSWER)
    if _ready_check(
        block,
        substep,
        opening=opening,
        last_answer=last_answer,
        cfg=cfg,
        state=active_block_state,
    ):
        lines.append(_GOAL_START_READY)
    if goal_start in _GOAL_START_HOLDS:
        lines.append(_GOAL_START_NO_TURN)
    from app.kc_loop import stay_on_course_enabled

    side = _typed_side_request(block, substep, last_answer, active_block_state, cfg)
    stay_on = stay_on_course_enabled(cfg)
    if goal_start in {"aside", "cap"}:
        pass
    elif side and goal_start in {"explain", "deepen"}:
        lines.append(_SIDE_EXPLAIN)
    elif (
        side
        and stay_on
        and goal_start != "clarify"
        and substep != "summary_check"
        and str(block.get("type") or "") != "explanation"
    ):
        lines.append(_SIDE_STAY)
    elif side and not stay_on and substep != "summary_check":
        lines.append(_SIDE_FOLLOW)
    if not goal_start and opening and step_index == 0:
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
            f"This reply opens {label} only. Do not praise what came before. "
            "Do not ask a question about what came before."
        )
    agreement = _agreement_close(summary_begin, worked_close, last_answer)
    if presenting and turn_kind in {"orient", "ask"}:
        lines.append(
            "Turn Stance: Give a short lead-in for the choice card. Do not ask the multiple-choice question in the reply."
        )
    elif ask_goal_now:
        lines.append("Ask the opening question for this goal. Do not teach the concept again.")
    elif opening and not presenting:
        if str(block.get("type") or "") in {"retrieval_check", "mcq"}:
            lines.append(_OPENING_ASK)
        elif str(block.get("type") or "") != "explanation":
            lines.append(_OPENING_HOLD)
    elif turn_kind in {"orient", "ask"} and goal_start not in {"explain", "deepen", "clarify", "aside"} and not agreement:
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
    elif (
        turn_kind in {"nudge", "scaffold"}
        and not side_question
        and not agreement
        and not _worked_reveal_known(forecast)
    ):
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
    if turn_kind in {"nudge", "scaffold", "reveal"} and not side_question and not agreement:
        lines.append(
            "Humor guardrail: suppress jokes and banter on this turn "
            "(an incorrect attempt (nudge/scaffold/reveal)); stay clear, earnest, and supportive."
        )
    topic_feedback_here = (
        str(block.get("type") or "") == "topic_goal" and turn_kind in {"ask", "nudge", "scaffold"}
    )
    if (
        not opening
        and not side_question
        and not topic_feedback_here
        and not agreement
        and turn_kind in {"pass", "nudge", "scaffold"}
    ):
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
    elif needs_dynamic_mcq and not _forecast_known_close(forecast):
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
        and not summary_begin
        and goal_start not in _GOAL_START_HOLDS | {"cap"}
        and not side
        and not side_question
    ):
        lines.append(
            "The learner answered with a 1-2 word fragment. Ask one follow-up to state the idea in a complete sentence before completing this block."
        )
    if choice_on_screen:
        pick = "The child picks the choice on screen. Do not add a separate question beside it."
        if is_final_block_and_substep or unit_complete or course_complete:
            pick += " A unit close or course outro asks no new question."
        lines.append(pick)
    from app.kc_loop import learner_wants_recap_elaboration

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
            side_question=(
                side_question and stay_on and not learner_wants_recap_elaboration(last_answer)
            ),
            omit_recap=agreement,
        )
    )
    elaborating = _summary_elaboration(block, substep, last_answer)
    if close_block_only and not elaborating and not summary_begin and not _forecast_applies(forecast):
        lines.append(
            "If block_complete=true, this reply only affirms and closes this part. "
            "Ask no question. Do not open the next part. "
            "If block_complete=false, ask one question that stays on the active step."
        )
    if str(block.get("type") or "") == "explanation":
        if opening:
                lines.append(
                    "This is the opening of this explanation. Explain only the current topic, "
                    "inside the learner's response_length. "
                    "Then ask if the learner has questions or wants you to elaborate. Do not quiz, and do not start the next topic yet. "
                    "Do not praise what came before."
                )
        elif substep == "summary_check":
            if elaborating:
                lines.append(_SUMMARY_ELABORATE)
            elif summary_begin:
                lines.append(_SUMMARY_BEGIN if has_next else _SUMMARY_BEGIN_LAST)
                lines.append("Do not quiz.")
            else:
                lines.append(
                    "The learner is on the summary. When this part's work is done, "
                    f"{_SUMMARY_CONGRATULATE} {_SUMMARY_CHOICE} {_SUMMARY_REMINDER} {_SUMMARY_MOVE_ON} Do not quiz."
                )
        elif _last_topic_close_now(block, active_block_state, last_answer):
            lines.append(_last_topic_close_line(block, active_block_state, last_answer, has_next=has_next))
        elif _explanation_capped(substep, active_block_state):
            lines.append(_EXPLANATION_CAP)
        else:
            from app.kc_loop import (
                explanation_on_last_topic,
                explanation_restates_topic,
                explanation_side_remark,
                learner_wants_recap_elaboration,
            )

            if explanation_side_remark(block, last_answer, active_block_state, cfg):
                lines.append(
                    "Answer the side remark in one or two sentences, then one line back to the active lesson. "
                    "Do not start a new explanation of this topic. Do not quiz."
                )
            elif explanation_restates_topic(block, active_block_state, last_answer):
                lines.append(
                    "The learner already restated this point. Name anything missed in one sentence. "
                    "Do not re-teach the whole topic. Then follow the move-on instruction in What to teach "
                    "and teach the next topic, or close in one or two sentences when this was the last topic. "
                    "Do not restate each topic and do not ask whether to move on. Do not quiz."
                )
            elif explanation_on_last_topic(block, active_block_state) and learner_wants_recap_elaboration(last_answer):
                lines.append(
                    "The learner asked to elaborate on this last topic. Elaborate this topic only. "
                    "Do not restate the other topics. Do not close yet. Do not quiz."
                )
            else:
                if not _forecast_applies(forecast):
                    lines.append(
                        "The learner has replied on the current topic. If they have a question or want elaboration, stay on this topic and answer. "
                        "If they are ready, follow the move-on instruction in What to teach and teach the next topic, "
                        "or close in one or two sentences when this was the last topic. "
                        "Do not restate each topic and do not ask whether to move on. Do not quiz."
                    )
    if worked_close == "affirm" and not (
        _forecast_applies(forecast) and getattr(forecast, "depends_on_model", False)
    ):
        lines.append(_SUMMARY_BEGIN if has_next else _SUMMARY_BEGIN_LAST)
    elif worked_close == "continue":
        lines.append(_WORKED_CONTINUE)
        lines.append(_SUMMARY_NO_PRAISE)
    elif str(block.get("type") or "") != "explanation":
        if worked_close == "bare_yes" and not summary_begin:
            lines.append(_WORKED_BARE_YES)
        force_side_question = side_question and stay_on
        # A side story stays via _SIDE_STAY. Stay off does not force a return.
        # A passed summary does not use that line: it would ask the goal again.
        if not (side and (not stay_on or not side_question)) or summary_begin or substep == "summary_check":
            lines.extend(
                _summary_close_lines(
                    phase=summary_phase,
                    revealed=bool((active_block_state or {}).get("revealed_substep")),
                    opening=opening,
                    block_type=str(block.get("type") or ""),
                    last_answer=last_answer,
                    side_question=force_side_question and not summary_begin,
                    moving_on=summary_begin,
                    has_next=has_next,
                )
            )
        if force_side_question and summary_phase not in {"task", "check"}:
            lines.append(_side_question_reply(last_answer))
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
    return _align_this_turn(lines, forecast, ready_check=ready_check)


def _forecast_applies(forecast: object | None) -> bool:
    return bool(forecast is not None and getattr(forecast, "applies", False))


def _forecast_known_close(forecast: object | None) -> bool:
    if not _forecast_applies(forecast) or getattr(forecast, "depends_on_model", False):
        return False
    chosen = getattr(forecast, "chosen", None)
    return bool(chosen is not None and chosen.speech == "close")


def _turn_reveal_stop(turn: object | None) -> bool:
    return bool(getattr(turn, "reveal_stop", False))


def _worked_reveal_stop(forecast: object | None) -> bool:
    """A miss on this turn reveals the faded step and does not open the solo problem."""
    if not _forecast_applies(forecast):
        return False
    if getattr(forecast, "depends_on_model", False):
        return _turn_reveal_stop(getattr(forecast, "if_not", None))
    return _turn_reveal_stop(getattr(forecast, "chosen", None))


def _worked_reveal_known(forecast: object | None) -> bool:
    return _worked_reveal_stop(forecast) and not getattr(forecast, "depends_on_model", False)


def _decision_sentence(turn: object, label: str) -> str:
    """One reply instruction. The order matches the speech.

    An advance says advance and does not say stay. A stay says stay and does
    not say advance. Close keeps its own order.
    """
    speech = str(getattr(turn, "speech", "stay"))
    prefix = f"{label}: " if label else "Decision: "
    if _turn_reveal_stop(turn):
        body = (
            "This is the last allowed try. Give the answer and say plainly that you gave it. "
            "Ask no question. Do not open the next step."
        )
        return f"{prefix}stay. Set decision to stay. {body}"
    if getattr(turn, "unit_complete", False):
        order = "Set decision to complete."
        body = "This reply ends the unit. Close it. Ask no question. Do not open the next part."
    elif speech == "close":
        order = "Set decision to advance." if getattr(turn, "advance_block", False) else "Set decision to complete."
        if getattr(turn, "revealed", False):
            body = (
                "Close in one sentence. Ask no question. Say plainly that you gave the answer. "
                f"Do not praise. Do not recap. {_NEVER_SAY_BLOCK} "
                "Do not open the next part in this reply. The next part arrives in its own message. "
                "Set block_complete=true."
            )
        else:
            body = (
                "Close in one sentence. Ask no question. Do not praise. Do not recap. "
                f"{_NEVER_SAY_BLOCK} "
                "Do not open the next part in this reply. The next part arrives in its own message. "
                "Set block_complete=true."
            )
    elif speech == "advance":
        order = "Set decision to advance."
        if getattr(turn, "revealed", False):
            body = (
                "This is the last allowed try. Give the answer and say plainly that you gave it. "
                "The reply then moves to the next step of this block."
            )
        elif str(getattr(turn, "next_substep", "")) == "summary_check":
            body = (
                "If this answer satisfies the substep, set substep_passed=true and block_complete=false. "
                f"{_SUMMARY_CONGRATULATE} "
                "Ask one question only: move on, or ask one more question. "
                f"{_NEVER_SAY_BLOCK} Do not open the next part in this reply."
            )
        else:
            body = "The reply does the next step of this block. Do not ask the step this reply is leaving."
    else:
        speech = "stay"
        order = "Set decision to stay."
        body = "Stay on this step. Set substep_passed=false and block_complete=false."
    return f"{prefix}{speech}. {order} {body}"


def _repeats_the_question(line: str) -> bool:
    """A stay-on-course line that tells the model to ask the step again."""
    lowered = line.lower()
    return line.startswith("Stay on course:") or "repeat the active question" in lowered


def _summary_future(line: str) -> bool:
    return line.startswith("Summary close") or line.startswith("Summary reply")


def _future_matches(line: str, turn: object) -> bool:
    low = line.lower()
    never = "never say congratulations" in low
    praise = "congratulate the learner once" in low
    revealed = bool(getattr(turn, "revealed", False))
    speech = str(getattr(turn, "speech", "stay"))
    if speech == "stay":
        return False
    if revealed and praise:
        return False
    if revealed and never:
        return True
    if never:
        return False
    return True


def _speech_of(turn: object | None) -> str:
    return str(getattr(turn, "speech", "") or "")


def _align_this_turn(lines: list[str], forecast: object | None, *, ready_check: bool) -> list[str]:
    """Keep the one branch the dry run chose. A ready check stays as written.

    A line that says to repeat the question belongs on a stay branch. It does
    not sit beside an advance. A known stay does not tell the model to advance.
    """
    if not _forecast_applies(forecast) or ready_check:
        return lines
    depends = bool(getattr(forecast, "depends_on_model", False))
    chosen = getattr(forecast, "chosen", None)
    if_correct = getattr(forecast, "if_correct", None)
    if_not = getattr(forecast, "if_not", None)
    if depends:
        advance_branch = _speech_of(if_correct) == "advance" or _speech_of(if_not) == "advance"
    else:
        advance_branch = _speech_of(chosen) == "advance"
    known_stay = (not depends) and _speech_of(chosen) == "stay"
    held_stay: list[str] = []
    kept: list[str] = []
    for line in lines:
        if advance_branch and _repeats_the_question(line):
            held_stay.append(line)
            continue
        if known_stay and line.startswith("Mid-Unit Contract"):
            line = line.replace("Advance the substep or the next part when satisfied. ", "", 1)
        if _summary_future(line):
            if depends or chosen is None or not _future_matches(line, chosen):
                continue
        if (
            not depends
            and chosen is not None
            and str(getattr(chosen, "speech", "")) == "close"
            and "congratulate" in line.lower()
        ):
            continue
        if (
            not depends
            and chosen is not None
            and chosen.unit_complete
            and ("NEVER say the unit is complete" in line or line.startswith("Mid-Unit Contract"))
        ):
            continue
        if depends and ("NEVER say the unit is complete" in line or line.startswith("Mid-Unit Contract")):
            ends = {
                bool(getattr(getattr(forecast, "if_correct", None), "unit_complete", False)),
                bool(getattr(getattr(forecast, "if_not", None), "unit_complete", False)),
            }
            if True in ends:
                continue
        kept.append(line)

    def _branch(turn: object, label: str) -> str:
        sentence = _decision_sentence(turn, label)
        if held_stay and _speech_of(turn) == "stay":
            sentence = f"{sentence} {' '.join(held_stay)}"
        return sentence

    if depends:
        branch = [
            _branch(if_correct, "If correct"),
            _branch(if_not, "If not"),
        ]
    else:
        branch = [_branch(chosen, "")]
    insert_at = 2 if len(kept) >= 2 else len(kept)
    return kept[:insert_at] + branch + kept[insert_at:]


def _teach_outcome(turn: object) -> str:
    if _turn_reveal_stop(turn):
        return "State the answer and ask no question. Do not open the next step."
    if getattr(turn, "unit_complete", False):
        return "This reply ends the unit. Close it. Ask no question."
    if str(getattr(turn, "speech", "")) == "close":
        return (
            "This reply closes in one sentence and asks no question. "
            "Do not praise. Do not recap. Never say the word block. "
            "The next part arrives in its own message. Do not open it here."
        )
    if str(getattr(turn, "speech", "")) == "stay":
        return "Ask one question that stays on this step."
    return "The reply moves to the next step of this block."


def _drop_praise_conflict(
    sections: list[tuple[str, list[str]]],
    forecast: object | None,
) -> list[tuple[str, list[str]]]:
    """A stored prompt does not hold both congratulate and never congratulate."""
    blob = "\n".join(line for _, lines in sections for line in lines).lower()
    praise = "congratulate the learner once" in blob
    never = "never say congratulations" in blob
    if not (praise and never):
        return sections
    drop = "never say congratulations"
    chosen = getattr(forecast, "chosen", None) if forecast is not None else None
    if (
        _forecast_applies(forecast)
        and not getattr(forecast, "depends_on_model", False)
        and chosen is not None
        and chosen.revealed
        and chosen.speech != "stay"
    ):
        drop = "congratulate the learner once"
    cleaned: list[tuple[str, list[str]]] = []
    for title, lines in sections:
        cleaned.append((title, [line for line in lines if drop not in line.lower()]))
    return cleaned


def _last_topic_close_now(block: dict, state: dict | None, answer: str) -> bool:
    """This reply ends the last explanatory topic. Local check, no model call."""
    from app.kc_loop import last_topic_closes_block

    return last_topic_closes_block(block, state, answer)


def _last_topic_close_line(block: dict, state: dict | None, answer: str, *, has_next: bool) -> str:
    """The spoken close for the last topic. A question is answered first."""
    from app.kc_loop import last_topic_question_close

    body = _LAST_TOPIC_ANSWER if last_topic_question_close(block, state, answer) else _LAST_TOPIC_CLOSE
    tail = _LAST_TOPIC_NEXT if has_next else _LAST_TOPIC_END
    return f"{body} {tail} Do not quiz."


def _explanation_teach_lines(
    block: dict,
    substep: str,
    state: dict,
    *,
    opening: bool,
    last_answer: str = "",
    summary_begin: bool = False,
    has_next: bool = False,
) -> list[str]:
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    topics = explanation_topics(block)
    total = max(len(topics), 1)
    index = explanation_topic_index(block, state)
    lines = [
        "Do NOT quiz or test the learner on this block. Never ask them to solve, recall for a grade, or prove they know it.",
    ]
    from app.kc_loop import (
        explanation_move_on_reply,
        explanation_restates_topic,
        explanation_side_remark,
        explanation_topic_taught,
        last_topic_question_close,
    )

    if (not opening) and _last_topic_close_now(block, state, last_answer):
        title = str(data.get("block_title") or "").strip()
        if title:
            lines.append(f"Block title: {_finish(title)}")
        topic = topics[index] if topics else {"title": "", "explanation": ""}
        lines.append(
            f"Active substep: explain_topic. Topic {index + 1} of {total}: {topic.get('title') or 'this topic'}."
        )
        if last_topic_question_close(block, state, last_answer) and topic.get("explanation"):
            lines.append(
                "Topic point, for the one-or-two-sentence answer only: "
                f"{_finish(str(topic.get('explanation') or ''))}"
            )
        lines.append(_last_topic_close_line(block, state, last_answer, has_next=has_next))
        return lines

    aside = (not opening) and explanation_side_remark(block, last_answer, state, None)
    restated = (not opening) and (not aside) and explanation_restates_topic(block, state, last_answer)
    moving = (not opening) and explanation_move_on_reply(block, state, last_answer)
    if not aside and not restated and not moving:
        lines.append(
            "Explain the topic clearly, then ask if they have any questions or would like you to elaborate."
        )
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
                "Give a cohesive summary of every topic discussed. "
                f"{_SUMMARY_CONGRATULATE} {_SUMMARY_CHOICE} "
                f"{_SUMMARY_REMINDER} {_SUMMARY_MOVE_ON}"
            )
        else:
            if _summary_elaboration(block, substep, last_answer):
                lines.append(_SUMMARY_ELABORATE)
            elif summary_begin:
                lines.append(_SUMMARY_BEGIN if has_next else _SUMMARY_BEGIN_LAST)
            else:
                lines.append(
                    "The learner has responded on the summary. "
                    f"{_SUMMARY_REMINDER} {_SUMMARY_MOVE_ON} Do not mention the next part."
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
    if aside:
        lines.append(
            "Answer the side remark in one or two sentences, then one line back to the active lesson. "
            "Do not start a new explanation of this topic."
        )
        return lines
    if restated:
        lines.append(
            "The learner already restated this point. Name anything missed in one sentence. "
            "Do not re-teach the whole topic."
        )
        if topic["explanation"]:
            lines.append(
                "Topic point, already said, for the one-sentence gap only: "
                f"{_finish(topic['explanation'])}"
            )
    else:
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
    if _explanation_capped(substep, state):
        proceed = "The learner has used the two extra turns on this topic. Set substep_passed=true"
    elif restated:
        proceed = "Set substep_passed=true"
    else:
        lines.append(
            "If the learner asks a question or wants elaboration, set substep_passed=false, stay on this topic, "
            "answer with a fresh angle, and check in again. Do not move on while they still have questions."
        )
        proceed = (
            "If the learner is good to proceed, for example What's next?, ok, I get it, or let's go, "
            "set substep_passed=true"
        )
    if not explanation_topic_taught(state):
        lines.append(
            "This topic has not been taught yet. Teach it in this reply from the text above. "
            "A request to move on does not skip it. Do not only name the title. Do not quiz."
        )
        return lines
    if topics and index < len(topics) - 1:
        nxt = topics[index + 1]
        body = str(nxt.get("explanation") or "").strip()
        points = str(nxt.get("key_points") or "").strip()
        taught = body
        if points:
            taught = f"{body} Key points: {points}." if body else f"Key points: {points}."
        lesson = _finish(taught) if taught else "what the title means"
        lines.append(
            f"{proceed} and, in this same reply, teach the next topic in full: "
            f"Topic {index + 2} of {total}: {nxt['title'] or 'the next topic'}. "
            f"Teach it from: {lesson}. "
            "Do not only name the title. Do not quiz."
        )
        return lines
    lines.append(
        "This is the last topic. Stay on this topic. "
        "Do not restate the other topics. Do not summarize this part. Do not close yet."
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
    opening: bool = False,
    last_answer: str = "",
    worked_close: str = "",
    cfg: dict | None = None,
    active_state: dict | None = None,
    summary_begin: bool = False,
    has_next: bool = False,
    forecast: object | None = None,
    ask_goal_now: bool = False,
) -> list[str]:
    """Strict block isolation: injects ONLY the currently active block and its active substep."""
    btype = str(block.get("type") or "topic_goal").strip()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    ev_id = block_evidence_id(block, step_index, substep)
    lines: list[str] = [f"Active block type: {btype} ({BLOCK_LABELS.get(btype, btype)})."]

    if _agreement_close(summary_begin, worked_close, last_answer):
        lines.append(
            "The learner agreed to move on. Close in one sentence. "
            "Do not teach a new lesson. Do not praise. Do not recap. Do not ask a question."
        )
    elif btype == "topic_goal":
        topic = str(data.get("topic") or node.title).strip()
        goal = str(data.get("goal") or node.core_truth).strip()
        criteria = str(data.get("acceptance_criteria") or goal).strip()
        notes = str(data.get("teaching_notes") or "").strip()
        if ask_goal_now:
            lines.append(f"Topic, already taught: {_finish(topic)}")
            lines.append(f"Learning goal to ask now: {_finish(goal)}")
        else:
            lines.append(f"Topic to introduce: {_finish(topic)}")
            lines.append(f"Learning goal the learner must explain in their own words: {_finish(goal)}")
        lines.append(f"Acceptance criteria to check ( withhold until pass or reveal ): {_finish(criteria)}")
        if notes and not ask_goal_now:
            lines.append(f"Teaching notes: {_finish(notes)}")
        phase = _goal_start_mode(
            block,
            substep,
            opening=opening,
            last_answer=last_answer,
            cfg=cfg,
            state=active_state if active_state is not None else active_block_state,
        )
        if ask_goal_now:
            lines.append(
                "Ask the opening question for this goal now. Do not teach the concept again. Do not give the answer."
            )
        elif phase in {"ask", "cap"}:
            lines.append("Ask the opening question for this goal now. Do not give the answer.")
            if phase == "ask" and _proceed_text_is_yes(last_answer) and "?" not in (last_answer or ""):
                lines.append("A bare yes does not start a new lesson. Do not explain the topic.")
        elif phase == "aside":
            lines.append(
                "Answer the learner's side remark in one or two sentences, then one line back to this lesson. "
                "Do not start a new explanation of this topic. Do not ask the learner to state the goal yet. "
                "Do not score this reply."
            )
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
            if _worked_reveal_known(forecast):
                lines.append(
                    f"Active substep (faded_step): State the missing Step {faded_idx + 1}. "
                    f"The missing step is: {_finish(target_step)} "
                    "Ask no question. Do not present the solo problem."
                )
            else:
                lines.append(
                    f"Active substep (faded_step): Ask the learner to supply the missing Step {faded_idx + 1}. "
                    f"Expected missing step (withhold until pass or reveal): {_finish(target_step)}"
                )
                if solo_prob:
                    lines.append(
                        "When the faded step is solved (substep_passed=true), "
                        f"present the solo problem in your reply: {_finish(solo_prob)}"
                    )
                if _worked_reveal_stop(forecast):
                    lines.append(
                        "When this turn reveals the faded step, state the missing step and ask no question. "
                        "Do not present the solo problem."
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
        lines.append(_teach_back_misconception_guard(node))

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
            if opening:
                lines.append(
                    f"Active substep (recall): Ask only this question: {_finish(recall_p)} "
                    "Do not give a cue, an example, or a second question."
                )
            else:
                lines.append(f"Active substep (recall): Ask cued-recall question: {_finish(recall_p)}")
            lines.append(f"Expected fact (withhold until pass or reveal): {_finish(exp_fact)}")
            if why_p and not opening:
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
                summary_begin=summary_begin,
                has_next=has_next,
            )
        )

    elif btype == "passage_ela":
        lines.extend(_passage_teach_lines(block, substep))

    lines.append(f"Evidence id for this active step: {ev_id}. Include '{ev_id}' in rubric_met when satisfied.")
    if next_block is not None and isinstance(next_block, dict):
        if worked_close == "continue":
            lines.append(
                "This reply is one short closing line and no question. "
                "Do not restate the summary. Do not mention the next part and do not open it."
            )
        elif worked_close == "affirm" and has_next and isinstance(next_block, dict):
            lines.append(
                "This reply closes in one sentence and asks no question. "
                "Do not praise. Do not recap. Never say the word block. "
                "The next part arrives in its own message. Do not open it here."
            )
        elif summary_begin and has_next:
            lines.append(
                "This reply closes in one sentence and asks no question. "
                "Do not praise. Do not recap. Never say the word block. "
                "The next part arrives in its own message. Do not open it here."
            )
        elif _last_topic_close_now(block, active_block_state, last_answer) and has_next:
            lines.append(
                "This reply closes in one sentence and asks no question. "
                "Do not praise. Do not recap. Never say the word block. "
                "The next part arrives in its own message. Do not open it here."
            )
        elif _forecast_applies(forecast) and not getattr(forecast, "depends_on_model", False):
            lines.append(_teach_outcome(getattr(forecast, "chosen")))
        elif _forecast_applies(forecast):
            lines.append(
                "If correct: "
                + _teach_outcome(getattr(forecast, "if_correct"))
                + " If not: "
                + _teach_outcome(getattr(forecast, "if_not"))
            )
        else:
            lines.append(
                "If the learner's response finishes this part (block_complete=true), "
                "close in one sentence. Ask no question. Do not praise. Do not recap. "
                "Never say the word block. Do not open the next part in this reply. "
                "The next part arrives in its own message. "
                "If the response does not finish this part (block_complete=false), "
                "ask one question that stays on this step."
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


def _check_in_line(style: str) -> str:
    lines = {
        "curiosity_invitation": (
            "Check-in style (curiosity_invitation): after each topic, invite a curiosity or what-if question, "
            "and offer to elaborate or move on."
        ),
        "brief_ready_check": (
            "Check-in style (brief_ready_check): after each topic, ask a short check-in. "
            "Any questions on this part, or are you ready for the next topic?"
        ),
    }
    return lines.get(
        style,
        "Check-in style (questions_or_elaborate): after each topic, ask whether they have questions "
        "or would like you to elaborate before the next part.",
    )


def _summary_style_line(style: str) -> str:
    lines = {
        "connected_narrative_synthesis": (
            "End-of-block summary (connected_narrative_synthesis): on the summary step, "
            "weave the topics into one connected narrative, then ask if they have any final questions."
        ),
        "concise_takeaway_only": (
            "End-of-block summary (concise_takeaway_only): on the summary step, "
            "give only the takeaway in a sentence or two, then ask if they have any final questions."
        ),
    }
    return lines.get(
        style,
        "End-of-block summary (bulleted_recap_with_takeaway): on the summary step, "
        "recap the topics as short bullets with one takeaway, then ask if they have any final questions.",
    )


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
        lines.append(_check_in_line(check_in))
        lines.append(_summary_style_line(summary_style))
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
    active_block_state: dict | None = None,
    summary_begin: bool = False,
    has_next: bool = False,
    forecast: object | None = None,
    ask_goal_now: bool = False,
) -> list[str]:
    if _agreement_close(summary_begin, worked_close, last_answer):
        return ["Do not teach a new lesson. Do not praise. Do not recap."]

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
    if _worked_reveal_stop(forecast):
        rewritten: list[str] = []
        for line in lines:
            lowered = line.lower()
            if lowered.startswith("hide one step") or lowered.startswith("hide two steps"):
                if _worked_reveal_known(forecast):
                    rewritten.append(
                        "The faded step is revealed on this turn. State the missing step. Ask no question."
                    )
                else:
                    rewritten.append(
                        line
                        + " If this turn reveals the faded step, state the missing step instead of asking for it."
                    )
                continue
            if "missing step" in lowered and ("do not show" in lowered or "without showing" in lowered):
                rewritten.append(
                    "On a wrong step before the last try, do not show the missing step. "
                    "When this turn reveals the faded step, state the missing step and ask no question. "
                    "Do not present the solo problem."
                )
            else:
                rewritten.append(line)
        lines = rewritten
    known_reveal = _worked_reveal_known(forecast)
    steps = substeps_for_block(block, cfg)
    on_summary_step = bool(steps) and steps[-1] == "summary_check" and (
        substep == "summary_check"
        or (len(steps) >= 2 and substep == steps[-2])
        or (str(block.get("type") or "") == "mcq" and substep == "awaiting_why")
    )
    if on_summary_step:
        lines = [line for line in lines if "one extra example" not in line.lower()]
    if summary_begin:
        lines = [
            line
            for line in lines
            if "do not open the next part" not in line.lower()
            and "any congratulation on those turns" not in line
            and "one extra example" not in line.lower()
        ]
    if _summary_elaboration(block, substep, last_answer):
        lines = [line for line in lines if not line.startswith("You are on the summary step.")]
    goal_start = _goal_start_mode(
        block, substep, opening=opening, last_answer=last_answer, cfg=cfg, state=active_block_state
    )
    from app.kc_loop import (
        explanation_move_on_reply,
        explanation_on_last_topic,
        explanation_restates_topic,
        explanation_side_remark,
        learner_wants_deeper_explanation,
        learner_wants_recap_elaboration,
        stay_on_course_enabled,
    )

    side = _typed_side_request(block, substep, last_answer, active_block_state, cfg)
    stay_on = stay_on_course_enabled(cfg)
    aside = explanation_side_remark(block, last_answer, active_block_state, cfg)
    restated = explanation_restates_topic(block, active_block_state, last_answer)
    moving = (not opening) and explanation_move_on_reply(block, active_block_state, last_answer)
    closing = (not opening) and _last_topic_close_now(block, active_block_state, last_answer)
    elaborating_last = (
        (not opening)
        and (not closing)
        and explanation_on_last_topic(block, active_block_state)
        and learner_wants_recap_elaboration(last_answer)
    )
    if aside or restated or moving or closing:
        lecture_bits = (
            "explanation depth",
            "when the learner asks a question or wants elaboration",
            "length override is on",
            "an elaboration request may run longer",
            "unless they ask you to elaborate",
            "do not cut the explanation",
            "as many sentences",
            "comprehensive deep dive",
            "detailed multi-angle",
            "close each topic",
            "on the summary step",
            "recap every topic",
            "summarize every topic",
        )
        lines = [line for line in lines if not any(bit in line.lower() for bit in lecture_bits)]
    elif elaborating_last:
        lines = [
            line
            for line in lines
            if "on the summary step" not in line.lower()
            and "recap every topic" not in line.lower()
            and "summarize every topic" not in line.lower()
        ]
    if aside:
        lines = [line for line in lines if not line.lower().startswith("close each topic")]
    deeper = learner_wants_deeper_explanation(last_answer) or learner_wants_recap_elaboration(last_answer)
    if str(block.get("type") or "") == "explanation" and not (aside or closing):
        if deeper and not restated and not moving:
            lines.append(
                "They asked to hear more. This elaboration may run longer than their response_length. "
                "Keep each sentence at their reading level."
            )
        else:
            first_teaching_bits = (
                "length override is on",
                "do not cut the explanation",
                "an elaboration request may run longer",
                "unless they ask you to elaborate",
                "you may exceed bite_sized",
                "5 to 8 sentences",
                "never cut a complex topic short",
                "comprehensive deep dive",
                "detailed multi-angle",
                "as many sentences",
            )
            lines = [line for line in lines if not any(bit in line.lower() for bit in first_teaching_bits)]
            lines.append(
                "The first teaching of this topic stays inside the learner's response_length. "
                "Do not write the long version until they ask to hear more."
            )
    side_question = _prompts_side_question(
        block, substep, last_answer, opening=opening, cfg=cfg, state=active_block_state
    )
    move_on_close = str(block.get("type") or "") == "topic_goal" and substep == "main" and _ready_to_move_on(last_answer)
    if move_on_close or side or side_question:
        lines = [line for line in lines if "ask for the idea in a full sentence" not in line]

    lines.append(
        f"Representation harmony: when you explain, scaffold, or reveal, use explanation_style ({expl_style})."
    )

    if goal_start == "aside":
        lines.append(
            "On this goal-start turn, answer the side remark in one or two sentences, then one line back to the lesson. "
            "Do not start a new explanation."
        )
    elif closing:
        lines.append(
            "On this last-topic close the stance does not ask. "
            + _last_topic_close_line(block, active_block_state, last_answer, has_next=has_next)
        )
    elif aside:
        lines.append(
            "Answer the side remark in one or two sentences, then one line back to the active lesson. "
            "Do not start a new explanation of this topic."
        )
    elif restated or moving:
        lines.append(
            "The learner already restated this point. Name anything missed in one sentence. "
            "Do not re-teach the whole topic."
        )
    elif ask_goal_now:
        lines.append(
            "This concept was just taught. Ask the opening question for this goal. Do not teach the concept again."
        )
    elif worked_close in {"affirm", "continue"}:
        lines.append("On this worked-example close the stance does not ask. Do not add a guiding question.")
    elif known_reveal:
        lines.append(
            "On this faded-step reveal the stance does not ask. State the missing step. "
            "Do not add a guiding question."
        )
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
    if _worked_reveal_stop(forecast) and not known_reveal:
        lines.append(
            "If this turn reveals the faded step, do not add that question. "
            "State the missing step and stop."
        )
    if goal_start in {"explain", "deepen"}:
        lines.append("On this goal-start turn that stance does not ask. Teach only. Do not ask yet.")
    elif goal_start == "clarify":
        lines.append(
            "On this goal-start turn, answer the learner's question first, in a sentence or two, then return to the topic. "
            "Set help_requested=true."
        )

    if not side_question and not aside and not restated and not moving and not closing and not known_reveal:
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

    if goal_start in {"aside", "cap"} or aside:
        pass
    elif side and not stay_on and not aside:
        lines.append(_SIDE_FOLLOW)
    elif side and goal_start in {"explain", "deepen", "clarify"}:
        pass
    elif side and not aside:
        lines.append(
            "Answer that request inside the safety rules, in one or two sentences, then repeat the active question. "
            "Do not call the reply partial, a close, or a good start."
        )
    elif side_question and stay_on:
        lines.append(
            "Answer the learner's side question in one or two sentences, then repeat the active question. Do not skip it."
        )
    elif stay_mode == "strict":
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
    if goal_start == "aside":
        lines.append(
            "Do not praise this reply. It is not a connection to the lesson and it is not noteworthy work. "
            "Do not say Nice connection, Great question, Nice work, or Great job."
        )
    else:
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

        if str(block.get("type") or "") == "topic_goal" and not summary_begin:
            lines.append(_topic_goal_earned_praise(praise_style))

    if str(block.get("type") or "") == "explanation":
        lines.append("Do not quiz, score, or reveal an answer on an explanation.")
        if aside:
            lines.append(
                "Answer the side remark in one or two sentences, then one line back to the lesson. "
                "Do not re-teach this topic."
            )
        elif restated or moving:
            lines.append("Name anything missed in one sentence. Do not re-teach the whole topic.")
        elif elaborating_last:
            lines.append("Elaborate this topic only. Do not restate the other topics.")
    elif not choice_on_screen and not presenting_dynamic_mcq:
        if summary_begin or worked_close in {"affirm", "continue"} or move_on_close or known_reveal:
            pass
        elif _worked_reveal_stop(forecast):
            lines.append(
                "End a teaching or probing turn with a single clear question, "
                "except when this turn reveals the faded step. "
                "A faded-step reveal states the answer and asks no question."
            )
        elif goal_start == "aside":
            lines.append(
                "Answer the side remark in one or two sentences, then one line back to the active lesson. "
                "Do not start a new explanation of this topic. "
                "The goal question waits until the learner moves on."
            )
        elif goal_start in {"explain", "deepen"}:
            lines.append("Do not end this turn with a question. The goal question waits until the learner moves on.")
        elif goal_start == "clarify":
            lines.append(
                "Answer the learner's question before teaching onward. The goal question waits until the learner moves on."
            )
        elif goal_start in {"ask", "cap"}:
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
    if substep == "summary_check":
        from app.kc_loop import summary_ready_signal

        if summary_ready_signal(last_answer):
            return ""
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


def current_child_line(last_answer: str) -> str:
    """The child line just sent.

    Checks grade this string, and the recent transcript ends on it.
    An empty answer stays empty: the summary and the opening have no new line.
    """
    return (last_answer or "").strip()


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


def _recent_ending_on_child(last_messages: str, last_answer: str) -> str:
    """Recent transcript whose last user message is the child line just sent."""
    answer = (last_answer or "").strip()
    parts = [part.strip() for part in (last_messages or "").split("|") if part.strip()]
    if answer:
        tail = f"user: {answer}"
        if not parts or parts[-1] != tail:
            parts.append(tail)
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
    child = current_child_line(last_answer)
    lines.append(f"The last answer was: {child or 'none yet'}.")
    tier = (hint_tier or "").strip()
    if tier and tier != "none":
        lines.append(f"The hint tier already given is: {tier}.")
    if eliminated:
        lines.append(f"Eliminated MCQ choice indices: {eliminated}.")
    if (affect or "").strip():
        lines.append(f"The child seems {affect}.")
    lines.append("The child has asked for help." if help_requested else "The child has not asked for help.")
    lines.append(f"Off-course turns so far: {off_course_count}.")
    recent = _recent_ending_on_child(last_messages, child)
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
            lines.append(f"{title}: {outcome}.")
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
    side_hold: bool = False,
    side_follow: bool = False,
    explanation_capped: bool = False,
    summary_done: bool = False,
    summary_begin: bool = False,
    has_next: bool = False,
    last_topic_close: str = "",
    explanation_short: bool = False,
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
            "decision is the move for this reply. "
            "Set substep_passed=true when the learner's answer satisfies the active substep. "
            "Set block_complete=true when the active substep is finished."
        ),
        "rubric_met lists the active block evidence id when the learner's response satisfies the criteria.",
        "misconception is the stored wrong move that matched, or null.",
        "hint_tier is nudge, analogy, scaffold, or reveal.",
        "affect is engaged, stuck, guessing, or frustrated. confidence is low, ok, or high.",
        "On unit close, populate score_justification, what_was_strong, and what_to_work_on; otherwise return empty strings for those three fields.",
        "You do not set the block order, the edges, or the final mastery score.",
    ]
    del summary_elaborate, last_topic_close, summary_begin, summary_done
    del close_block_only, has_next, explanation_short
    if explanation_capped:
        lines.append("On this turn set substep_passed=true.")
    if block_type == "explanation":
        lines.append(
            "On an explanation, substep_passed is false when the learner asks a question or wants elaboration, "
            "and true when they are ready to proceed."
        )
    if clarify_help:
        lines.append("Set help_requested=true. The learner asked a question.")
    if side_hold:
        lines.append(
            "This typed line is unscored help. Set substep_passed=false and block_complete=false."
        )
    elif side_follow:
        lines.append("A tangent is not the score. The score still comes only from this step.")
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
    "Ask no question. Do not open the next part."
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
            if (
                line.startswith("Explanatory block override:")
                and "do not open the next part" not in line.lower()
                and "begin the next block" not in line.lower()
            ):
                line = f"{line.rstrip()} {_SUMMARY_MOVE_ON}"
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
                        f"{head}, close this part with a brief affirmation only. "
                        "Ask no question. Do not mention the next part and do not open it."
                    )
                if line.startswith("For Block") and "populate generated_mcq" in line:
                    continue
                if (
                    line.startswith("Give a cohesive summary")
                    and "do not open the next part" not in line.lower()
                    and "begin the next block" not in line.lower()
                ):
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


def _blocks_text(sections: list[tuple[str, list[str]]], forecast: object | None = None) -> str:
    include_generated_mcq = any(
        "populate generated_mcq" in line for _, lines in sections for line in lines
    )
    sections = _fit_prompt_sections(sections, include_generated_mcq=include_generated_mcq)
    sections = _drop_praise_conflict(sections, forecast)
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
    # Every check below, and the last user message, use the child line just sent.
    last_answer = current_child_line(last_answer)
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
    ready_check = _ready_check(
        active_block, substep, opening=opening, last_answer=last_answer or "", cfg=cfg, state=state_dict
    )
    early_answer = (
        not opening
        and _goal_start_mode(
            active_block, substep, opening=opening, last_answer=last_answer or "", cfg=cfg, state=state_dict
        )
        == "attempt"
    )
    if early_answer:
        # The loop scores this answer as the first try on the goal, so the prompt is the goal-question prompt.
        substep = "main"
        state_dict["substep"] = substep
        fragment = False
    previous_block = blocks[index - 1] if index > 0 else None
    ask_goal_now = bool(
        opening
        and substep == "main"
        and topic_goal_follows_explanation(active_block, previous_block)
    )
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
    from app.kc_loop import (
        explanation_move_on_reply,
        explanation_restates_topic,
        explanation_side_remark,
        learner_asks_clarification,
        stay_on_course_enabled,
        summary_ready_signal,
        unanswered_side_turn,
    )

    clarify_help = bool(
        btype == "topic_goal" and substep == "explain" and learner_asks_clarification(last_answer or "")
    )
    summary_elaborate = _summary_elaboration(active_block, substep, last_answer or "")
    has_next = index + 1 < len(blocks)
    last_topic_close = ""
    if not opening and _last_topic_close_now(active_block, state_dict, last_answer or ""):
        last_topic_close = _last_topic_close_line(
            active_block, state_dict, last_answer or "", has_next=has_next
        )
    summary_begin = (
        not opening
        and not summary_elaborate
        and worked_close != "continue"
        and (
            worked_close == "affirm"
            or (
                substep == "summary_check"
                and not state_dict.get("revealed_substep")
                and summary_ready_signal(last_answer or "")
            )
        )
    )
    if (summary_begin or bool(last_topic_close)) and has_next:
        nxt = blocks[index + 1]
        nxt_data = nxt.get("data") if isinstance(nxt.get("data"), dict) else {}
        if str(nxt.get("type") or "") == "mcq" and str(nxt_data.get("mode") or "static") == "dynamic":
            needs_dynamic_mcq = True
    side_request = _typed_side_request(active_block, substep, last_answer or "", state_dict, cfg)
    course_stay = stay_on_course_enabled(cfg)
    aside_help = bool(
        course_stay
        and btype == "topic_goal"
        and substep == "explain"
        and unanswered_side_turn(active_block, substep, last_answer or "", state_dict, cfg)
    )
    side_help = (
        _prompts_side_question(
            active_block,
            substep,
            last_answer or "",
            opening=opening,
            cfg=cfg,
            state=state_dict,
        )
        and course_stay
    )
    from app.kc_loop import forecast_this_turn

    forecast = forecast_this_turn(
        blocks=blocks,
        step=index,
        active_block_state=state_dict,
        block_results=list(block_results or []),
        answer=last_answer or "",
        cfg=cfg,
        goal=goal,
        stored_rubric=list(rubric_met or []),
        move_attempts=int(attempts or 0),
        hint_tier=hint_tier or "nudge",
        reveals=int(reveals or 0),
        enrichment_turns=int(enrichment_turns or 0),
        fragment=bool(fragment),
        prior_tutor=_previous_tutor_text(last_messages or "", last_answer or ""),
        opening=opening,
    )
    ends_unit = (
        _forecast_applies(forecast)
        and not forecast.depends_on_model
        and forecast.chosen is not None
        and forecast.chosen.unit_complete
    )
    teach_substep = substep
    teach_state = state_dict
    if (
        not opening
        and btype == "worked_example"
        and substep == "faded_step"
        and bool(state_dict.get("revealed_substep"))
    ):
        # The answer was given last turn. This reply asks the solo problem.
        teach_substep = "solo_solve"
        teach_state = dict(state_dict)
        teach_state["substep"] = "solo_solve"
        teach_state["revealed_substep"] = False
        turn_kind = "ask"

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
                    substep=teach_substep,
                    opening=opening,
                    orient_framing=str(over.get("orient_framing") or "elaborate_outline"),
                    unit_complete=unit_complete or ends_unit,
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
                    active_block_state=teach_state,
                    close_block_only=close_block_only,
                    summary_phase=summary_phase,
                    summary_stay=summary_phase == "check" and is_last_block,
                    last_answer=last_answer,
                    cfg=cfg,
                    worked_close=worked_close,
                    early_answer=early_answer,
                    summary_begin=summary_begin,
                    has_next=has_next,
                    forecast=forecast,
                    ready_check=ready_check,
                    ask_goal_now=ask_goal_now,
                ),
            ),
            (
            "What to teach",
            _what_to_teach(
                node=node,
                block=active_block,
                step_index=index,
                substep=teach_substep,
                active_block_state=teach_state,
                next_block=blocks[index + 1] if (close_block_only or summary_begin or bool(last_topic_close)) and has_next else None,
                opening=opening,
                last_answer=last_answer,
                worked_close=worked_close,
                cfg=cfg,
                active_state=state_dict,
                summary_begin=summary_begin,
                has_next=has_next,
                forecast=forecast,
                ask_goal_now=ask_goal_now,
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
                    last_answer=last_answer or "",
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
                    active_block_state=state_dict,
                    summary_begin=summary_begin,
                    has_next=has_next,
                    forecast=forecast,
                    ask_goal_now=ask_goal_now,
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
                    help_requested=bool(help_requested) or clarify_help or side_help or aside_help,
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
                    clarify_help=clarify_help or aside_help,
                    side_hold=(side_request and course_stay) or aside_help,
                    side_follow=side_request and not course_stay,
                    explanation_capped=btype == "explanation" and _explanation_capped(substep, state_dict),
                    summary_done=(
                        btype != "explanation"
                        and substep == "summary_check"
                        and not state_dict.get("revealed_substep")
                        and worked_close not in {"affirm", "continue"}
                        and not summary_begin
                    ),
                    summary_begin=summary_begin,
                    has_next=has_next,
                    last_topic_close=last_topic_close,
                    explanation_short=bool(
                        btype == "explanation"
                        and (
                            explanation_side_remark(active_block, last_answer or "", state_dict, cfg)
                            or explanation_restates_topic(active_block, state_dict, last_answer or "")
                            or explanation_move_on_reply(active_block, state_dict, last_answer or "")
                            or bool(last_topic_close)
                        )
                    ),
                ),
            ),
        ],
        forecast,
    )
    return {
        "system_prompt": prompt,
        "response_schema": turn_response_schema(
            presenting_dynamic_mcq=presenting_dynamic_mcq,
            needs_dynamic_mcq=needs_dynamic_mcq,
            ready_check=ready_check,
        ),
        "temperature": TEMPERATURE,
        "user_message": last_answer,
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
