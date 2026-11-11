"""The one catalog of block types: labels, authoring rules, field lists, and data schemas."""

from __future__ import annotations

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
    "explanation": "Explanatory Walkthrough",
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
    "explanation": "Explanation",
}

BLOCK_BANNER_LABELS = {
    "topic_goal": "Topic + Goal",
    "mcq": "Multiple choice",
    "case_study": "Case study",
    "socratic": "Socratic",
    "curiosity": "Curiosity",
    "worked_example": "Worked example",
    "spot_the_flaw": "Spot the flaw",
    "teach_back": "Teach back",
    "retrieval_check": "Retrieval check",
    "explanation": "Explanatory walkthrough",
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
    "explanation": (
        "- explanation (Explanatory Walkthrough): Provide 1 to 8 topics. Each topic needs id, title, "
        "and explanation. key_points and examples_or_analogies are optional. "
        "block_title and summary_takeaway are optional. Do not write a quiz, a correct answer, or a score."
    ),
}


BLOCK_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "topic_goal": (
        ("topic", "Topic"),
        ("goal", "Goal"),
        ("acceptance_criteria", "Acceptance criteria"),
        ("teaching_notes", "Teaching notes"),
    ),
    "mcq": (
        ("mode", "Mode"),
        ("question_stem", "Question stem"),
        ("choices", "Choices"),
        ("correct_explanation", "Correct explanation"),
        ("target_skill", "Target skill"),
        ("difficulty", "Difficulty"),
        ("num_choices", "Number of choices"),
        ("distractor_guidance", "Distractor guidance"),
        ("stem_constraints", "Stem constraints"),
    ),
    "case_study": (
        ("case_a", "Case A"),
        ("case_b", "Case B"),
        ("prediction_prompt", "Prediction prompt"),
        ("invariant_principle", "Invariant principle"),
        ("transfer_prompt", "Transfer prompt"),
        ("transfer_expected", "Transfer expected"),
    ),
    "socratic": (
        ("central_dilemma", "Central dilemma"),
        ("initial_probe", "Opening probe"),
        ("counterexamples", "Counterexamples"),
        ("target_synthesis", "Target synthesis"),
    ),
    "curiosity": (
        ("phenomenon_hook", "Phenomenon hook"),
        ("prediction_question", "Prediction question"),
        ("bridge_to_unit", "Bridge to unit"),
        ("wonder_branches", "Wonder branches"),
    ),
    "worked_example": (
        ("problem_statement", "Problem statement"),
        ("steps", "Steps"),
        ("faded_step_index", "Faded step"),
        ("solo_problem", "Solo problem"),
        ("solo_expected_answer", "Solo expected answer"),
    ),
    "spot_the_flaw": (
        ("rookie_work", "Rookie work"),
        ("flaw_description", "Flaw description"),
        ("underlying_misconception", "Underlying misconception"),
        ("corrected_version", "Corrected version"),
    ),
    "teach_back": (
        ("peer_persona_prompt", "Peer prompt"),
        ("required_concepts", "Required concepts"),
        ("peer_follow_up_question", "Peer follow-up"),
    ),
    "retrieval_check": (
        ("recall_prompt", "Recall prompt"),
        ("expected_fact", "Expected fact"),
        ("elaborative_why_prompt", "Elaborative why prompt"),
        ("expected_why_rationale", "Expected why rationale"),
    ),
    "explanation": (
        ("block_title", "Block title"),
        ("topics", "Topics"),
        ("summary_takeaway", "Summary takeaway"),
    ),
}


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
    "explanation": "Explanations",
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
BLOCK_DATA_SCHEMAS: dict[str, dict] = {
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
    "explanation": _object_schema(
        {
            "block_title": _NULLABLE_STRING,
            "topics": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": _object_schema(
                    {
                        "id": _STRING,
                        "title": _STRING,
                        "explanation": _STRING,
                        "key_points": _NULLABLE_STRING,
                        "examples_or_analogies": _NULLABLE_STRING,
                    },
                ),
            },
            "summary_takeaway": _NULLABLE_STRING,
        },
    ),
}
