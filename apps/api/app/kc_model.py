"""Prompts and block schemas for the KC Course Creator and KC Creator model calls.

The course creator plans the subject, major ideas, and component list with
summaries, outlines, and initial topic-goal pairs.
The component creator drafts an ordered sequence of pedagogical blocks
restricted to the course's selected AI Block Scope (allowed_block_types).
"""

from __future__ import annotations

import copy
import re

from app.kc_syllabus import MAX_COMPONENTS, planned_reply, planning_context
from app.models import ALL_BLOCK_TYPES

DEEPSEEK_FLASH_MODEL = "~deepseek/deepseek-flash-latest"
LEGACY_DEEPSEEK_FLASH_MODEL = "deepseek/deepseek-flash-latest"
KC_CHAT_MODELS = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-6.1-sol",
    DEEPSEEK_FLASH_MODEL,
)
DEFAULT_KC_CHAT_MODEL = "gpt-4.1"
DESCRIPTION_SLICE = 25

BLOCK_LABELS: dict[str, str] = {
    "topic_goal": "Topic / Goal",
    "mcq": "Multiple Choice Question",
    "case_study": "Case Study / Contrasting Cases",
    "socratic": "Socratic Discussion",
    "curiosity": "Curiosity / Wonder Hook",
    "worked_example": "Worked Example + Faded Step",
    "spot_the_flaw": "Spot the Flaw / Buggy Rule",
    "teach_back": "Teach-Back / Feynman",
    "retrieval_check": "Retrieval & Elaborative Interrogation",
}

BLOCK_SHORT_LABELS: dict[str, str] = {
    "topic_goal": "Topic",
    "mcq": "MCQ",
    "case_study": "Case Study",
    "socratic": "Socratic",
    "curiosity": "Curiosity",
    "worked_example": "Worked Example",
    "spot_the_flaw": "Spot the Flaw",
    "teach_back": "Teach-Back",
    "retrieval_check": "Retrieval Check",
}

BLOCK_AUTHORING_RULES: dict[str, str] = {
    "topic_goal": (
        "- topic_goal (Topic / Goal): Provide topic (the single concept, step, or causal link to introduce), "
        "goal (what the learner must explain or justify in their own words), optional acceptance_criteria, "
        "and optional teaching_notes."
    ),
    "mcq": (
        "- mcq (Multiple Choice Question): mode is required, 'static' or 'dynamic'. "
        "Static requires question_stem and 2-5 choices ({ id, text, is_correct, optional distractor_rationale, "
        "optional misconception_code }) with exactly one is_correct true. correct_explanation is optional. "
        "Dynamic requires target_skill and distractor_guidance. difficulty ('foundation' | 'standard' | 'stretch'), "
        "num_choices (3-5), and stem_constraints are optional."
    ),
    "case_study": (
        "- case_study (Case Study / Contrasting Cases): Provide case_a, contrasting case_b, "
        "prediction_prompt, invariant_principle (the underlying rule), and optional transfer_prompt with transfer_expected."
    ),
    "socratic": (
        "- socratic (Socratic Discussion): Provide central_dilemma, initial_probe, "
        "1-3 counterexamples, and target_synthesis."
    ),
    "curiosity": (
        "- curiosity (Curiosity / Wonder Hook): Provide phenomenon_hook, prediction_question, "
        "bridge_to_unit, and optional wonder_branches."
    ),
    "worked_example": (
        "- worked_example (Worked Example + Faded Step): Provide problem_statement, "
        "2-6 steps ({ step_text required, rationale optional }), optional 0-based faded_step_index "
        "(the last step when omitted), solo_problem, and solo_expected_answer."
    ),
    "spot_the_flaw": (
        "- spot_the_flaw (Spot the Flaw / Buggy Rule): Provide rookie_work, flaw_description, "
        "underlying_misconception, and corrected_version."
    ),
    "teach_back": (
        "- teach_back (Teach-Back / Feynman Explanation): Provide peer_persona_prompt, "
        "1-4 required_concepts, and peer_follow_up_question."
    ),
    "retrieval_check": (
        "- retrieval_check (Retrieval & Elaborative Interrogation): Provide recall_prompt, "
        "expected_fact, elaborative_why_prompt, and expected_why_rationale."
    ),
}

COURSE_RULES = (
    "You are an expert curriculum maker. "
    "Name the subject from the course name and the course description. "
    "Then name the major ideas a strong course on that subject has to cover. "
    "Do not slice the description sentence into titles. "
    "Do not turn clauses of the description into component titles. "
    "Mastery is the fuller rigorous breakdown. "
    "Time boxed fits the minutes. "
    "Curiosity is a path through the subject. "
    'Honor a requested count. "minimum of 10" means at least 10 distinct components. '
    '"10 components" means 10 distinct components. '
    "A pasted title list is used as written. "
    "Only after the subject and the major ideas, return the component list. "
    "Each component has a short summary, a short outline, the key topics, the key goals, "
    "and recommended_blocks (2-5 ordered blocks with type and focus, using only the allowed block types). "
    "Include the recommended block sequence and block types in the component description "
    "(for example: 'Explains why free-fall acceleration is independent of mass. "
    "Recommended blocks: 1. Curiosity Hook (Apollo hammer vs. feather) -> 2. Case Study (vacuum vs. air) -> 3. Topic / Goal (force-to-mass ratio) -> 4. MCQ (heavier-falls-faster check).'). "
    "Each topic is one pair with its goal."
)
STUDIO_RULES = COURSE_RULES

CREATOR_RULES = (
    "You are an expert curriculum maker for this knowledge component and the course kind. "
    "The description is a short summary of the component. "
    "Use that summary. Recommend every field that can be entered: "
    "description, title, outline, core_truth, an ordered blocks[] sequence, "
    "misconceptions, prerequisites, and encompasses. "
    "Use the course kind. Mastery is the fuller rigorous breakdown. "
    "Time boxed fits the minutes. Curiosity is a path through the subject. "
    "Go into the topic before you fill the outline, the core truth, the blocks, and the links. "
    "Do not change how an answer is scored. "
    "Other components stay as they are."
)

_TOPIC_PAIR = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "topic": {"type": "string"},
        "goal": {"type": "string"},
    },
    "required": ["topic", "goal"],
}

_RECOMMENDED_BLOCK = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": list(ALL_BLOCK_TYPES)},
        "focus": {"type": "string"},
    },
    "required": ["type", "focus"],
}


def clean_allowed_block_types(values: object) -> list[str]:
    """Validate and normalize the course's allowed AI block types. At least 1 remains."""
    if not isinstance(values, list):
        return list(ALL_BLOCK_TYPES)
    chosen: list[str] = []
    for item in values:
        btype = str(item or "").strip()
        if btype in ALL_BLOCK_TYPES and btype not in chosen:
            chosen.append(btype)
    return chosen or ["topic_goal"]


def _recommended_block_schema(allowed_types: list[str] | None = None) -> dict:
    allowed = clean_allowed_block_types(allowed_types)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {"type": "string", "enum": list(allowed)},
            "focus": {"type": "string"},
        },
        "required": ["type", "focus"],
    }


def _component_fields_schema(allowed_types: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "outline": {"type": "string"},
            "topics": {"type": "array", "items": _TOPIC_PAIR},
            "recommended_blocks": {
                "type": "array",
                "items": _recommended_block_schema(allowed_types),
            },
        },
        "required": ["title", "description", "outline", "topics", "recommended_blocks"],
    }


_COMPONENT_FIELDS = _component_fields_schema(list(ALL_BLOCK_TYPES))

COURSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "subject": {"type": "string"},
        "major_ideas": {"type": "array", "items": {"type": "string"}},
        "components": {"type": "array", "items": _COMPONENT_FIELDS},
    },
    "required": ["subject", "major_ideas", "components"],
}
_STUDIO_SCHEMA = COURSE_SCHEMA

TITLES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "subject": {"type": "string"},
        "major_ideas": {"type": "array", "items": {"type": "string"}},
        "titles": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject", "major_ideas", "titles"],
}

SLICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "components": {"type": "array", "items": _COMPONENT_FIELDS},
    },
    "required": ["components"],
}


def _course_schema(allowed_types: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "subject": {"type": "string"},
            "major_ideas": {"type": "array", "items": {"type": "string"}},
            "components": {"type": "array", "items": _component_fields_schema(allowed_types)},
        },
        "required": ["subject", "major_ideas", "components"],
    }


def _slice_schema(allowed_types: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "components": {"type": "array", "items": _component_fields_schema(allowed_types)},
        },
        "required": ["components"],
    }

_MISCONCEPTION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "wrong_move": {"type": "string"},
        "broken_kc": {"type": "string"},
    },
    "required": ["wrong_move", "broken_kc"],
}

def _object_schema(properties: dict) -> dict:
    """Strict structured output lists every property in required."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def _nullable(schema: dict) -> dict:
    """A catalog-optional field stays required and may be null."""
    spec = dict(schema)
    kind = spec.get("type")
    if isinstance(kind, str):
        spec["type"] = [kind, "null"]
    enum = spec.get("enum")
    if isinstance(enum, list) and None not in enum:
        spec["enum"] = [*enum, None]
    return spec


_STRING = {"type": "string"}
_NULLABLE_STRING = _nullable(_STRING)

_MCQ_CHOICE_SCHEMA = _object_schema(
    {
        "id": _STRING,
        "text": _STRING,
        "is_correct": {"type": "boolean"},
        "distractor_rationale": _NULLABLE_STRING,
        "misconception_code": _NULLABLE_STRING,
    },
)

_WORKED_STEP_SCHEMA = _object_schema(
    {"step_text": _STRING, "rationale": _NULLABLE_STRING},
)

_MCQ_STATIC_SCHEMA = _object_schema(
    {
        "mode": {"type": "string", "enum": ["static"]},
        "question_stem": _STRING,
        "choices": {"type": "array", "minItems": 2, "maxItems": 5, "items": _MCQ_CHOICE_SCHEMA},
        "correct_explanation": _NULLABLE_STRING,
    },
)

_MCQ_DYNAMIC_SCHEMA = _object_schema(
    {
        "mode": {"type": "string", "enum": ["dynamic"]},
        "target_skill": _STRING,
        "distractor_guidance": _STRING,
        "difficulty": _nullable({"type": "string", "enum": ["foundation", "standard", "stretch"]}),
        "num_choices": _nullable({"type": "integer", "minimum": 3, "maximum": 5}),
        "stem_constraints": _NULLABLE_STRING,
    },
)

# One data object per block type. Every property is required.
# Catalog-optional fields are nullable. Catalog-required fields are not.
_BLOCK_DATA_SCHEMAS: dict[str, dict] = {
    "topic_goal": _object_schema(
        {
            "topic": _STRING,
            "goal": _STRING,
            "acceptance_criteria": _NULLABLE_STRING,
            "teaching_notes": _NULLABLE_STRING,
        },
    ),
    "mcq": {"anyOf": [_MCQ_STATIC_SCHEMA, _MCQ_DYNAMIC_SCHEMA]},
    "case_study": _object_schema(
        {
            "case_a": _STRING,
            "case_b": _STRING,
            "prediction_prompt": _STRING,
            "invariant_principle": _STRING,
            "transfer_prompt": _NULLABLE_STRING,
            "transfer_expected": _NULLABLE_STRING,
        },
    ),
    "socratic": _object_schema(
        {
            "central_dilemma": _STRING,
            "initial_probe": _STRING,
            "counterexamples": {"type": "array", "minItems": 1, "maxItems": 3, "items": _STRING},
            "target_synthesis": _STRING,
        },
    ),
    "curiosity": _object_schema(
        {
            "phenomenon_hook": _STRING,
            "prediction_question": _STRING,
            "bridge_to_unit": _STRING,
            "wonder_branches": _nullable({"type": "array", "maxItems": 3, "items": _STRING}),
        },
    ),
    "worked_example": _object_schema(
        {
            "problem_statement": _STRING,
            "steps": {"type": "array", "minItems": 2, "maxItems": 6, "items": _WORKED_STEP_SCHEMA},
            "faded_step_index": _nullable({"type": "integer", "minimum": 0}),
            "solo_problem": _STRING,
            "solo_expected_answer": _STRING,
        },
    ),
    "spot_the_flaw": _object_schema(
        {
            "rookie_work": _STRING,
            "flaw_description": _STRING,
            "underlying_misconception": _STRING,
            "corrected_version": _STRING,
        },
    ),
    "teach_back": _object_schema(
        {
            "peer_persona_prompt": _STRING,
            "required_concepts": {"type": "array", "minItems": 1, "maxItems": 4, "items": _STRING},
            "peer_follow_up_question": _STRING,
        },
    ),
    "retrieval_check": _object_schema(
        {
            "recall_prompt": _STRING,
            "expected_fact": _STRING,
            "elaborative_why_prompt": _STRING,
            "expected_why_rationale": _STRING,
        },
    ),
}


def _block_variant(btype: str) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "id": _STRING,
            "type": {
                "type": "string",
                "enum": [btype],
                "description": "Only block types in this course's AI Block Scope may be emitted.",
            },
            "data": copy.deepcopy(_BLOCK_DATA_SCHEMAS[btype]),
        },
        "required": ["id", "type", "data"],
    }


def _block_item_schema(allowed_types: list[str]) -> dict:
    """One schema per allowed block type. Fields are not merged across types."""
    allowed = clean_allowed_block_types(allowed_types)
    variants = [_block_variant(btype) for btype in allowed if btype in _BLOCK_DATA_SCHEMAS]
    if len(variants) == 1:
        return variants[0]
    return {"anyOf": variants}


CREATOR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "discussion": {"type": "string"},
        "title": {"type": "string"},
        "description": {
            "type": "string",
            "description": "A short summary of the component. Not the outline and not the block list.",
        },
        "outline": {"type": "string"},
        "core_truth": {"type": "string"},
        "blocks": {
            "type": "array",
            "items": _block_item_schema(list(ALL_BLOCK_TYPES)),
        },
        "misconceptions": {"type": "array", "items": _MISCONCEPTION},
        "prerequisite_codes": {"type": "array", "items": {"type": "string"}},
        "encompasses_codes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "discussion",
        "title",
        "description",
        "outline",
        "core_truth",
        "blocks",
        "misconceptions",
        "prerequisite_codes",
        "encompasses_codes",
    ],
}


def derive_rubric_from_blocks(blocks: list[dict]) -> list[str]:
    """Compute component rubric criteria in block order from blocks[]."""
    rubric: list[str] = []
    for blk in blocks or []:
        if not isinstance(blk, dict):
            continue
        btype = str(blk.get("type") or "").strip()
        data = blk.get("data") if isinstance(blk.get("data"), dict) else {}
        criterion = ""
        if btype == "topic_goal":
            criterion = str(data.get("goal") or data.get("acceptance_criteria") or "").strip()
        elif btype == "mcq":
            mode = str(data.get("mode") or "static").strip()
            if mode == "dynamic":
                criterion = str(data.get("target_skill") or "").strip()
            else:
                criterion = str(data.get("question_stem") or data.get("correct_explanation") or "").strip()
        elif btype == "case_study":
            criterion = str(data.get("invariant_principle") or "").strip()
        elif btype == "socratic":
            criterion = str(data.get("target_synthesis") or "").strip()
        elif btype == "worked_example":
            criterion = str(data.get("solo_expected_answer") or data.get("problem_statement") or "").strip()
        elif btype == "spot_the_flaw":
            criterion = str(data.get("corrected_version") or data.get("flaw_description") or "").strip()
        elif btype == "teach_back":
            reqs = data.get("required_concepts")
            if isinstance(reqs, list):
                cleaned = [str(r).strip() for r in reqs if str(r).strip()]
                criterion = "; ".join(cleaned)
        elif btype == "retrieval_check":
            criterion = str(data.get("expected_fact") or "").strip()
        if criterion and criterion not in rubric:
            rubric.append(criterion)
    return rubric[:16]


def model_for_call(model: str) -> str:
    """The id sent to the provider. A saved row may still hold the id without the tilde."""
    chosen = (model or "").strip()
    if chosen == LEGACY_DEEPSEEK_FLASH_MODEL:
        return DEEPSEEK_FLASH_MODEL
    return chosen


def checked_model(model: str) -> str:
    chosen = model_for_call(model) or DEFAULT_KC_CHAT_MODEL
    if chosen not in KC_CHAT_MODELS:
        raise ValueError("That model is not allowed.")
    return chosen


def titles_are_sliced(description: str, titles: list[str]) -> bool:
    """True when every title is a phrase cut out of the description."""
    blob = re.sub(r"\s+", " ", description or "").lower()
    if len(titles) < 2 or len(blob) < 12:
        return False
    hits = 0
    for title in titles:
        cleaned = re.sub(r"\s+", " ", title).strip(" .").lower()
        if len(cleaned) >= 8 and cleaned in blob:
            hits += 1
    return hits == len(titles)


_BRIEF = re.compile(
    r"^Outline:\s*(.*?)\nTopics:\s*(.*?)\nGoals:\s*(.*)\s*\Z",
    re.DOTALL | re.IGNORECASE,
)


def clean_recommended_blocks(
    value: object,
    allowed_block_types: list[str] | None = None,
    fallback_pairs: list[dict] | None = None,
    title: str = "",
) -> list[dict]:
    """Normalize recommended_blocks against allowed_block_types (2-5 blocks when possible)."""
    allowed = clean_allowed_block_types(allowed_block_types)
    allowed_set = set(allowed)
    default_type = allowed[0]
    cleaned: list[dict] = []
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            btype = str(item.get("type") or "").strip()
            focus = str(item.get("focus") or "").strip()
            if not focus:
                continue
            if btype not in allowed_set:
                btype = default_type
            cleaned.append({"type": btype, "focus": focus})
    if not cleaned and fallback_pairs:
        for idx, pair in enumerate(fallback_pairs):
            if isinstance(pair, dict) and str(pair.get("topic") or "").strip():
                btype = allowed[idx % len(allowed)]
                cleaned.append({"type": btype, "focus": str(pair["topic"]).strip()})
    if not cleaned and title:
        cleaned.append({"type": default_type, "focus": title})
    return cleaned[:6]


BLOCK_PLURAL_SHORT_LABELS: dict[str, str] = {
    "topic_goal": "Topics",
    "mcq": "MCQs",
    "case_study": "Case Studies",
    "socratic": "Socratic",
    "curiosity": "Curiosity",
    "worked_example": "Worked Examples",
    "spot_the_flaw": "Spot the Flaw",
    "teach_back": "Teach-Backs",
    "retrieval_check": "Retrieval Checks",
}


def block_summary_label(blocks: list[dict]) -> str:
    """Readable block summary pill (e.g. '1 Curiosity · 2 Topics · 1 Case Study · 1 MCQ')."""
    if not isinstance(blocks, list) or not blocks:
        return "No blocks yet"
    runs: list[tuple[str, int]] = []
    for item in blocks:
        if not isinstance(item, dict):
            continue
        btype = str(item.get("type") or "topic_goal").strip()
        if runs and runs[-1][0] == btype:
            runs[-1] = (btype, runs[-1][1] + 1)
        else:
            runs.append((btype, 1))
    if not runs:
        return "No blocks yet"
    parts: list[str] = []
    for btype, count in runs:
        label = (
            BLOCK_SHORT_LABELS.get(btype, btype)
            if count == 1
            else BLOCK_PLURAL_SHORT_LABELS.get(btype, f"{BLOCK_SHORT_LABELS.get(btype, btype)}s")
        )
        parts.append(f"{count} {label}")
    return " · ".join(parts)


def format_recommended_blocks_summary(recommended_blocks: list[dict]) -> str:
    """Format 'Recommended blocks: 1. Type Label (focus) -> 2. ...'."""
    if not recommended_blocks:
        return ""
    parts: list[str] = []
    for idx, item in enumerate(recommended_blocks, start=1):
        if not isinstance(item, dict):
            continue
        btype = str(item.get("type") or "topic_goal").strip()
        label = BLOCK_LABELS.get(btype, btype)
        focus = str(item.get("focus") or "").strip()
        if focus:
            parts.append(f"{idx}. {label} ({focus})")
        else:
            parts.append(f"{idx}. {label}")
    if not parts:
        return ""
    return "Recommended blocks: " + " -> ".join(parts) + "."


def ensure_description_with_recommended_blocks(summary: str, recommended_blocks: list[dict]) -> str:
    """Ensure description includes the readable Recommended blocks breakdown."""
    text = (summary or "").strip()
    rec_line = format_recommended_blocks_summary(recommended_blocks)
    if not rec_line:
        return text
    stripped = re.sub(r"\s*Recommended blocks:\s*.*\Z", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    if not stripped:
        return rec_line
    sep = "" if stripped.endswith((".", "!", "?")) else "."
    return f"{stripped}{sep} {rec_line}"


def seed_skeleton_blocks_from_recommendations(
    recommended_blocks: list[dict],
    pairs: list[dict] | None = None,
    title: str = "",
) -> list[dict]:
    """Create initial skeleton blocks on a newly created/empty component from recommended_blocks."""
    cleaned_pairs = clean_pairs(pairs or [])
    recs = clean_recommended_blocks(recommended_blocks, None, cleaned_pairs, title)
    blocks: list[dict] = []
    for idx, rec in enumerate(recs, start=1):
        btype = str(rec.get("type") or "topic_goal").strip()
        focus = str(rec.get("focus") or title or f"Part {idx}").strip()
        pair_goal = ""
        if idx - 1 < len(cleaned_pairs):
            pair_goal = str(cleaned_pairs[idx - 1].get("goal") or "").strip()
        if btype == "topic_goal":
            data = {
                "topic": focus,
                "goal": pair_goal or f"Explain {focus} in your own words.",
                "acceptance_criteria": "",
                "teaching_notes": "",
            }
        elif btype == "mcq":
            data = {
                "mode": "static",
                "question_stem": f"Which statement best describes {focus}?",
                "choices": [
                    {
                        "id": "a",
                        "text": pair_goal or f"Core principle of {focus}",
                        "is_correct": True,
                        "distractor_rationale": "",
                        "misconception_code": "",
                    },
                    {
                        "id": "b",
                        "text": f"Common misconception about {focus}",
                        "is_correct": False,
                        "distractor_rationale": f"Confuses surface features of {focus}.",
                        "misconception_code": "",
                    },
                ],
                "correct_explanation": pair_goal or f"Applies {focus}.",
            }
        elif btype == "case_study":
            data = {
                "case_a": f"Case A illustrating {focus}",
                "case_b": f"Contrasting Case B for {focus}",
                "prediction_prompt": f"How do Case A and Case B differ on {focus}?",
                "invariant_principle": pair_goal or f"Underlying rule for {focus}.",
                "transfer_prompt": "",
                "transfer_expected": "",
            }
        elif btype == "socratic":
            data = {
                "central_dilemma": f"Why does {focus} hold even in edge cases?",
                "initial_probe": f"What is your initial hypothesis about {focus}?",
                "counterexamples": [f"What if a boundary condition in {focus} changes?"],
                "target_synthesis": pair_goal or f"Synthesized principle for {focus}.",
            }
        elif btype == "curiosity":
            data = {
                "phenomenon_hook": f"Surprising observation about {focus}",
                "prediction_question": f"What do you think explains {focus}?",
                "bridge_to_unit": pair_goal or f"Connects {focus} to the core concept.",
                "wonder_branches": [],
            }
        elif btype == "worked_example":
            data = {
                "problem_statement": f"Worked example for {focus}",
                "steps": [
                    {"step_text": f"Set up {focus}.", "rationale": "Identifies the given quantities."},
                    {"step_text": f"Solve {focus}.", "rationale": "Applies the rule to reach the result."},
                ],
                "faded_step_index": 1,
                "solo_problem": f"Solve a parallel problem on {focus}.",
                "solo_expected_answer": pair_goal or f"Expected solution for {focus}.",
            }
        elif btype == "spot_the_flaw":
            data = {
                "rookie_work": f"A student's flawed attempt at {focus}.",
                "flaw_description": f"The specific mistake in {focus}.",
                "underlying_misconception": f"Conceptual trap behind {focus}.",
                "corrected_version": pair_goal or f"Corrected reasoning for {focus}.",
            }
        elif btype == "teach_back":
            data = {
                "peer_persona_prompt": f"How would you explain {focus} to a younger student?",
                "required_concepts": [pair_goal or focus],
                "peer_follow_up_question": f"Why does {focus} work that way?",
            }
        elif btype == "retrieval_check":
            data = {
                "recall_prompt": f"What is the key fact or relationship in {focus}?",
                "expected_fact": pair_goal or focus,
                "elaborative_why_prompt": f"Why does {focus} make sense?",
                "expected_why_rationale": pair_goal or f"Causal explanation for {focus}.",
            }
        else:
            btype = "topic_goal"
            data = {
                "topic": focus,
                "goal": pair_goal or f"Explain {focus}.",
                "acceptance_criteria": "",
                "teaching_notes": "",
            }
        blocks.append({"id": f"blk_{idx}", "type": btype, "data": data})
    return blocks


def clean_pairs(value: object) -> list[dict]:
    """Keep pairs that have both a topic and a goal. Drop the rest."""
    if not isinstance(value, list):
        return []
    pairs: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        goal = str(item.get("goal") or "").strip()
        if topic and goal:
            pairs.append({"topic": topic, "goal": goal})
    return pairs


def split_brief(description: str) -> dict | None:
    """Split a stored three-line description once.

    A description that is not that form stays a summary, with no pairs.
    A topic without a goal, or a goal without a topic, is dropped.
    The outline sentence becomes the summary.
    """
    match = _BRIEF.match((description or "").strip())
    if match is None:
        return None
    outline = match.group(1).strip()
    topics = [part.strip() for part in match.group(2).split(";") if part.strip()]
    goals = [part.strip() for part in match.group(3).split(";") if part.strip()]
    pairs: list[dict] = []
    for index in range(max(len(topics), len(goals))):
        topic = topics[index] if index < len(topics) else ""
        goal = goals[index] if index < len(goals) else ""
        if topic and goal:
            pairs.append({"topic": topic, "goal": goal})
    if not outline or not pairs:
        return None
    return {"description": outline, "outline": outline, "topics": pairs}


def _kind_line(ctx: dict) -> str:
    kind = ctx["kind"]
    if kind == "time_boxed" and ctx["minutes"]:
        return f"Kind: Time boxed. Fit the list to {ctx['minutes']} minutes."
    if kind == "time_boxed":
        return "Kind: Time boxed. Fit the list to the time."
    if kind == "curiosity":
        return "Kind: Curiosity. Make a path through the subject."
    return "Kind: Mastery. Give the fuller rigorous breakdown."


def _count_line(ctx: dict) -> str:
    count = ctx["count"]
    if not count:
        return "No count was requested. Use as many distinct components as the kind needs."
    mode, number = count
    if mode == "min":
        return f'The author asked for a minimum of {number}. Return at least {min(number, MAX_COMPONENTS)} distinct components.'
    return f'The author asked for {number} components. Return {min(number, MAX_COMPONENTS)} distinct components.'


def _draft_width(ctx: dict) -> int:
    if ctx["pasted"]:
        return len(ctx["titles"])
    count = ctx["count"]
    if count:
        return min(int(count[1]), MAX_COMPONENTS)
    return len(ctx["titles"])


def _course_setup(
    *,
    title: str,
    description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    message: str,
    model: str,
    allowed_block_types: list[str] | None = None,
) -> tuple[str, dict, list[str], list[str]]:
    chosen = checked_model(model)
    allowed = clean_allowed_block_types(allowed_block_types)
    ctx = planning_context(
        title=title,
        description=description,
        kind=kind,
        minutes=minutes,
        message=message,
    )
    listed = "\n".join(f"- {item}" for item in ctx["titles"])
    if ctx["pasted"]:
        title_rule = "The author pasted a title list. Use those titles as written, in this order. Do not rename them."
    else:
        title_rule = (
            "A careful syllabus for this subject and kind already uses the titles below. "
            "You may use them. If you choose others, they are distinct parts of the subject, "
            "not clauses cut from the description."
        )
    allowed_labels = ", ".join(f"{b} ({BLOCK_LABELS.get(b, b)})" for b in allowed)
    lines = [
        COURSE_RULES,
        f"Course name: {title}",
        f"Course description: {description or 'None yet.'}",
        f"Audience: {audience}",
        _kind_line(ctx),
        _count_line(ctx),
        f"Allowed block types for recommended_blocks: {allowed_labels}",
        "You may ONLY recommend block types from this allowed list.",
        title_rule,
        "Syllabus titles:",
        listed or "- None",
    ]
    return chosen, ctx, lines, allowed


def course_bundle(
    *,
    title: str,
    description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    message: str,
    model: str,
    allowed_block_types: list[str] | None = None,
) -> dict:
    chosen, ctx, lines, allowed = _course_setup(
        title=title,
        description=description,
        audience=audience,
        kind=kind,
        minutes=minutes,
        message=message,
        model=model,
        allowed_block_types=allowed_block_types,
    )
    if _draft_width(ctx) > DESCRIPTION_SLICE:
        lines.append(
            "Return the subject, the major ideas, and the titles only. "
            "Do not write outlines, topics, or goals in this reply."
        )
        schema = TITLES_SCHEMA
        phase = "titles"
    else:
        lines.append(
            "Return the subject, the major ideas, and then the components. "
            "Each component has a title, a short summary (including 'Recommended blocks: 1. ... -> 2. ...'), "
            "a short outline, key topics, key goals, and recommended_blocks (2-5 blocks with type and focus). "
            "Each topic is paired with its goal."
        )
        schema = _course_schema(allowed)
        phase = "full"
    return {
        "model": chosen,
        "system_prompt": "\n".join(lines),
        "user_prompt": (message or "").strip() or "Draft the component list.",
        "schema": schema,
        "pass": phase,
        "slice_size": DESCRIPTION_SLICE,
    }


studio_bundle = course_bundle


def _plain_titles(titles: list[str]) -> list[str]:
    chosen: list[str] = []
    for item in titles:
        title = str(item or "").strip()
        if title:
            chosen.append(title)
    return chosen


def _groups(titles: list[str], size: int) -> list[list[str]]:
    return [titles[start : start + size] for start in range(0, len(titles), size)]


def _description_bundle(
    *,
    model: str,
    ctx: dict,
    title: str,
    description: str,
    audience: str,
    message: str,
    titles: list[str],
    subject: str,
    major_ideas: list[str],
    allowed_block_types: list[str] | None = None,
) -> dict:
    allowed = clean_allowed_block_types(allowed_block_types)
    listed = "\n".join(f"- {item}" for item in titles)
    ideas = "; ".join(major_ideas) if major_ideas else subject
    allowed_labels = ", ".join(f"{b} ({BLOCK_LABELS.get(b, b)})" for b in allowed)
    system = "\n".join(
        [
            COURSE_RULES,
            f"Course name: {title}",
            f"Course description: {description or 'None yet.'}",
            f"Audience: {audience}",
            _kind_line(ctx),
            _count_line(ctx),
            f"Subject: {subject}",
            f"Major ideas: {ideas}",
            f"Allowed block types for recommended_blocks: {allowed_labels}",
            "These titles are already chosen. Write a short summary (with Recommended blocks), a short outline, "
            "the key topics, the key goals, and recommended_blocks for each one. "
            "Each topic keeps the goal that belongs to it.",
            "Do not add a title, drop a title, or rename a title. Keep this order.",
            "Titles:",
            listed,
            "Return only these components.",
        ]
    )
    return {
        "model": model,
        "system_prompt": system,
        "user_prompt": (message or "").strip() or "Write the descriptions for these titles.",
        "schema": _slice_schema(allowed),
        "titles": list(titles),
    }


def description_plan(
    *,
    title: str,
    description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    message: str,
    model: str,
    titles: list[str],
    subject: str = "",
    major_ideas: list[str] | None = None,
    allowed_block_types: list[str] | None = None,
) -> dict:
    """Description calls for one slice of titles at a time. The full list is checked first."""
    chosen, ctx, _lines, allowed = _course_setup(
        title=title,
        description=description,
        audience=audience,
        kind=kind,
        minutes=minutes,
        message=message,
        model=model,
        allowed_block_types=allowed_block_types,
    )
    chosen_titles = list(ctx["titles"]) if ctx["pasted"] else _plain_titles(titles)
    _check_titles(description, chosen_titles, ctx)
    subject_text = (subject or "").strip() or str(ctx["subject"])
    ideas = [str(item).strip() for item in (major_ideas or []) if str(item).strip()] or list(ctx["ideas"])
    slices = [
        _description_bundle(
            model=chosen,
            ctx=ctx,
            title=title,
            description=description,
            audience=audience,
            message=message,
            titles=group,
            subject=subject_text,
            major_ideas=ideas,
            allowed_block_types=allowed,
        )
        for group in _groups(chosen_titles, DESCRIPTION_SLICE)
    ]
    return {"slice_size": DESCRIPTION_SLICE, "slices": slices}


def _model_rows(proposal: dict) -> list[dict]:
    rows = proposal.get("components")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _brief_fields(
    rows: list[dict],
    titles: list[str],
    allowed_block_types: list[str] | None = None,
) -> list[tuple[str, str, list[dict], list[dict]]]:
    by_title: dict[str, dict] = {}
    for row in rows:
        key = str(row.get("title") or "").strip().lower()
        if key and key not in by_title:
            by_title[key] = row
    written: list[tuple[str, str, list[dict], list[dict]]] = []
    for index, title in enumerate(titles):
        row = by_title.get(title.lower())
        if row is None and index < len(rows):
            row = rows[index]
        if row is None:
            written.append(("", "", [], []))
            continue
        outline = str(row.get("outline") or "").strip()
        pairs = clean_pairs(row.get("topics"))
        recs = clean_recommended_blocks(
            row.get("recommended_blocks"),
            allowed_block_types=allowed_block_types,
            fallback_pairs=pairs,
            title=title,
        )
        raw_summary = str(row.get("description") or "").strip() or outline
        summary = ensure_description_with_recommended_blocks(raw_summary, recs)
        written.append((summary, outline, pairs, recs))
    return written


def _model_titles(rows: list[dict]) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for row in rows:
        title = str(row.get("title") or "").strip()
        key = title.lower()
        if not title or key in seen:
            continue
        seen.add(key)
        titles.append(title)
    return titles


def _check_titles(description: str, titles: list[str], ctx: dict) -> None:
    if len(titles) < 2:
        raise ValueError("Return at least two distinct components.")
    if len(titles) > MAX_COMPONENTS:
        raise ValueError(f"Return at most {MAX_COMPONENTS} distinct components.")
    if len({title.lower() for title in titles}) != len(titles):
        raise ValueError("Honor the requested count with distinct components.")
    if not ctx["pasted"] and titles_are_sliced(description, titles):
        raise ValueError("Do not slice the description sentence into titles.")
    count = ctx["count"]
    if not count:
        return
    mode, number = count
    expected = min(number, MAX_COMPONENTS)
    if mode == "min" and len(titles) < expected:
        raise ValueError(f"Honor the requested count. Return at least {expected} distinct components.")
    if mode == "exact" and len(titles) != expected:
        raise ValueError(f"Honor the requested count. Return {expected} distinct components.")


def _ideas_from(proposal: dict, description: str, fallback: list[str]) -> list[str]:
    raw = proposal.get("major_ideas")
    ideas: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text and text.lower() not in {idea.lower() for idea in ideas}:
                ideas.append(text)
    ideas = ideas[:8]
    if not ideas:
        return list(fallback)
    if titles_are_sliced(description, ideas):
        raise ValueError("Name the major ideas of the subject. Do not slice the description into ideas.")
    return ideas


def assemble_course(
    *,
    title: str,
    description: str,
    kind: str,
    minutes: int | None,
    message: str,
    proposal: dict,
    allowed_block_types: list[str] | None = None,
) -> dict:
    """Turn a model object into a reply and a component list. This does not write."""
    if not isinstance(proposal, dict):
        raise ValueError("The model reply could not be read.")
    ctx = planning_context(
        title=title,
        description=description,
        kind=kind,
        minutes=minutes,
        message=message,
    )
    rows = _model_rows(proposal)
    if ctx["pasted"]:
        titles = list(ctx["titles"])
    else:
        titles = _model_titles(rows)
    _check_titles(description, titles, ctx)
    fields = _brief_fields(rows, titles, allowed_block_types=allowed_block_types)
    if any(not outline or not pairs for _summary, outline, pairs, _recs in fields):
        raise ValueError("Each component needs a short outline, the key topics, and the key goals.")
    subject = str(proposal.get("subject") or "").strip() or str(ctx["subject"])
    if description and subject.lower() == description.strip().lower():
        subject = str(ctx["subject"])
    ideas = _ideas_from(proposal, description, list(ctx["ideas"]))
    reply = planned_reply(
        subject=subject,
        ideas=ideas,
        kind=str(ctx["kind"]),
        minutes=ctx["minutes"],
        titles=titles,
        count=ctx["count"],
        sized_to_minutes=bool(ctx["sized_to_minutes"]),
        pasted=bool(ctx["pasted"]),
    )
    return {
        "reply": reply,
        "components": [
            {
                "title": component_title,
                "description": summary,
                "outline": outline,
                "topics": pairs,
                "recommended_blocks": recs,
            }
            for component_title, (summary, outline, pairs, recs) in zip(titles, fields, strict=True)
        ],
    }


def _creator_schema(other_codes: list[str], allowed_block_types: list[str] | None = None) -> dict:
    """The creator schema for this call, restricted to allowed_block_types."""
    allowed = clean_allowed_block_types(allowed_block_types)
    schema = copy.deepcopy(CREATOR_SCHEMA)
    schema["properties"]["blocks"] = {
        "type": "array",
        "description": (
            "Ordered blocks. Emit only types in this course's AI Block Scope. "
            "Each type has its own data fields. Do not fill another type's fields."
        ),
        "items": _block_item_schema(allowed),
    }
    if other_codes:
        schema["properties"]["misconceptions"] = {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "wrong_move": {"type": "string"},
                    "broken_kc": {
                        "type": "string",
                        "enum": list(other_codes),
                        "description": (
                            "Copy one code from this list. "
                            "Not a description and not this component's code."
                        ),
                    },
                },
                "required": ["wrong_move", "broken_kc"],
            },
        }
    else:
        schema["properties"]["misconceptions"] = {
            "type": "array",
            "maxItems": 0,
            "items": {"type": "string"},
        }
    return schema


def _creator_links(other_codes: list[str]) -> str:
    if not other_codes:
        return (
            "This course has no other component. Return an empty misconceptions array. "
            "Do not ask for a broken_kc. "
            "Prerequisite codes and encompasses codes stay empty."
        )
    broken = (
        "Copy one code from the other component codes into broken_kc. "
        "It is not a description and not this component's code. "
    )
    links = (
        "Prerequisite codes and encompasses codes "
        "have to be chosen from the other component codes. "
        "Use an empty list for prerequisites or encompasses when none of those links fit."
    )
    return broken + links


def creator_bundle(
    *,
    course_title: str,
    course_description: str,
    audience: str,
    kind: str,
    minutes: int | None,
    node_title: str,
    node_code: str,
    node_description: str,
    node_outline: str = "",
    node_topics: list | None = None,
    node_blocks: list | None = None,
    allowed_block_types: list[str] | None = None,
    other_codes: list[str],
    previous: dict | None,
    message: str,
    model: str,
) -> dict:
    chosen = checked_model(model)
    allowed = clean_allowed_block_types(allowed_block_types)
    if kind == "time_boxed" and minutes:
        kind_line = f"Kind: Time boxed, {minutes} minutes. Fit this component to that time."
    elif kind == "time_boxed":
        kind_line = "Kind: Time boxed. Fit this component to the time."
    elif kind == "curiosity":
        kind_line = "Kind: Curiosity. Treat this component as a step on a path through the subject."
    else:
        kind_line = "Kind: Mastery. Give the fuller rigorous treatment of this component."
    brief = (node_description or "").strip() or "This component has no description yet. Use the title and the course."
    pair_lines = [f"- {item['topic']}: {item['goal']}" for item in clean_pairs(node_topics or [])]
    stored_topics = "\n".join(pair_lines) if pair_lines else "- None yet."
    block_lines: list[str] = []
    for idx, blk in enumerate(node_blocks or [], start=1):
        if not isinstance(blk, dict):
            continue
        btype = str(blk.get("type") or "topic_goal")
        bdata = blk.get("data") if isinstance(blk.get("data"), dict) else {}
        focus = (
            bdata.get("topic")
            or bdata.get("question_stem")
            or bdata.get("target_skill")
            or bdata.get("prediction_prompt")
            or bdata.get("central_dilemma")
            or bdata.get("phenomenon_hook")
            or bdata.get("problem_statement")
            or bdata.get("rookie_work")
            or bdata.get("peer_persona_prompt")
            or bdata.get("recall_prompt")
            or ""
        )
        block_lines.append(f"- Block {idx}: {btype} ({BLOCK_LABELS.get(btype, btype)}) — {focus}".rstrip(" —"))
    stored_blocks = "\n".join(block_lines) if block_lines else "- None yet."
    previous_line = "There is no draft yet. Go into the topic, then fill the fields."
    if previous:
        prev_blocks = previous.get("blocks") or []
        prev_summary = ", ".join(str(b.get("type")) for b in prev_blocks if isinstance(b, dict)) or "none"
        previous_line = (
            "A draft is already in the thread. Revise it. Still go into the topic before the fields. "
            f"Current blocks: {prev_summary}. "
            f"Current core truth: {previous.get('core_truth') or 'none'}."
        )
    codes = ", ".join(other_codes) if other_codes else "none"
    allowed_rules = "\n".join(BLOCK_AUTHORING_RULES[btype] for btype in allowed if btype in BLOCK_AUTHORING_RULES)
    scope_instruction = (
        f"You may ONLY generate blocks whose `type` is in this allowed list: {allowed}. "
        "Do not generate any other block type."
    )
    system = "\n".join(
        [
            CREATOR_RULES,
            f"Course: {course_title}. {course_description}".strip(),
            f"Audience: {audience}",
            kind_line,
            f"Component: {node_title} ({node_code})",
            "Brief:",
            brief,
            f"Outline: {(node_outline or '').strip() or 'None yet.'}",
            "Stored topics:",
            stored_topics,
            "Seeded block blueprint (populate and enrich this sequence if present):",
            stored_blocks,
            f"Other component codes: {codes}",
            previous_line,
            scope_instruction,
            "Allowed block type specifications:",
            allowed_rules,
            "The discussion comes first and goes into the topic. "
            "Then recommend every enterable field from the brief. "
            "The description is a short summary. Do not fold the outline or the blocks into it. "
            "Return the outline in the outline field. "
            "Return an ordered blocks[] array of 1 to 6 blocks using only the allowed block types, "
            "the core_truth, misconceptions, prerequisites, and encompasses.",
            _creator_links(other_codes),
        ]
    )
    return {
        "model": chosen,
        "system_prompt": system,
        "user_prompt": (message or "").strip(),
        "schema": _creator_schema(other_codes, allowed),
    }


def checked_discussion(discussion: str, title: str) -> str:
    text = (discussion or "").strip()
    if len(text) < 80:
        raise ValueError(
            "Go into the topic before you fill the outline, the core truth, the blocks, and the checks."
        )
    if text.lower().startswith("title:"):
        raise ValueError("Go into the topic before you fill the fields.")
    if title and title.lower() not in text.lower() and len(text) < 160:
        raise ValueError(f"Go into {title} before you fill the fields.")
    return text
