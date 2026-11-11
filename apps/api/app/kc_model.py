"""Prompts and schemas for the KC Creator (one component at a time).

The component creator drafts an ordered sequence of pedagogical blocks
restricted to the course's selected AI Block Scope (allowed_block_types).
The course pipeline lives in app/kc_pipeline.py. The block catalog lives in
app/block_catalog.py.
"""

from __future__ import annotations

import copy
import re

from app.block_catalog import (
    BLOCK_AUTHORING_RULES,
    BLOCK_DATA_SCHEMAS,
    BLOCK_LABELS,
    PASSAGE_LENGTH_GUIDELINES,
)
from app.kc_blocks import clean_passage_ela_data, passage_ela_gap, passage_paragraphs
from app.kc_pipeline import passage_ela_generation_lines
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


CREATOR_RULES = (
    "You are an expert curriculum maker for one knowledge component of a course. "
    "Use the course brief, the course outcomes, this component's position, and its description. "
    "Fill every field that can be entered: title, description, outline, core_truth, "
    "an ordered blocks[] sequence, misconceptions, prerequisites, and encompasses. "
    "The description is a plain summary of 3 to 4 sentences. "
    "Do not fold the outline or the block list into it. "
    "Teach one idea in about 10 to 15 minutes. "
    "Move from a worked example to guided practice to independent practice. "
    "Do not use a word before this component or an earlier one has taught it. "
    "Use the course kind. Mastery is the fuller rigorous treatment. "
    "Time boxed fits the minutes. Curiosity is a step on a path through the subject. "
    "The discussion answers the latest user message. "
    "Do not change how an answer is scored. "
    "Other components stay as they are."
)


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


_MISCONCEPTION = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "wrong_move": {"type": "string"},
        "broken_kc": {"type": "string"},
    },
    "required": ["wrong_move", "broken_kc"],
}


def _block_variant(btype: str) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string"},
            "type": {
                "type": "string",
                "enum": [btype],
                "description": "Only block types in this course's AI Block Scope may be emitted.",
            },
            "data": copy.deepcopy(BLOCK_DATA_SCHEMAS[btype]),
        },
        "required": ["id", "type", "data"],
    }


def _block_item_schema(allowed_types: list[str]) -> dict:
    """One schema per allowed block type. Fields are not merged across types."""
    allowed = clean_allowed_block_types(allowed_types)
    variants = [_block_variant(btype) for btype in allowed if btype in BLOCK_DATA_SCHEMAS]
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
        elif btype == "explanation":
            criterion = ""
        elif btype == "passage_ela":
            criterion = str(data.get("expected_central_idea") or data.get("passage_title") or "").strip()
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


_BRIEF = re.compile(
    r"^Outline:\s*(.*?)\nTopics:\s*(.*?)\nGoals:\s*(.*)\s*\Z",
    re.DOTALL | re.IGNORECASE,
)


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


def _block_focus(bdata: dict) -> str:
    for key in (
        "topic",
        "question_stem",
        "target_skill",
        "prediction_prompt",
        "central_dilemma",
        "phenomenon_hook",
        "problem_statement",
        "rookie_work",
        "peer_persona_prompt",
        "recall_prompt",
        "block_title",
        "passage_title",
    ):
        if bdata.get(key):
            return str(bdata[key])
    topics = bdata.get("topics")
    if isinstance(topics, list) and topics and isinstance(topics[0], dict):
        return str(topics[0].get("title") or "")
    return ""


def _sibling_lines(siblings: list[dict]) -> str:
    rows = []
    for item in siblings:
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        rows.append(f"- {code}: {title}" + (f" - {summary}" if summary else ""))
    return "\n".join(rows) if rows else "- None."


def _link_line(label: str, items: list[dict]) -> str:
    shown = ", ".join(f"{item['code']} ({item.get('title') or ''})".replace(" ()", "") for item in items)
    return f"{label}: {shown or 'none'}"


_PASSAGE_PLACEHOLDER = re.compile(r"read the following passage\b", re.IGNORECASE)
_WORD = re.compile(r"\b[\w']+\b")
_ABOUT = re.compile(r"\b(?:about|on)\s+(.+)$", re.IGNORECASE)
_SUBJECT_STOP = re.compile(r"\s+\b(?:and|so that|while|by)\b", re.IGNORECASE)
_ARGUMENT = re.compile(r"\b(argument|argumentative|persuade|persuasive|editorial|opinion)\b", re.IGNORECASE)
_PRIMARY = re.compile(r"\b(primary source|historical document|diary|speech)\b", re.IGNORECASE)
_LITERARY = re.compile(r"\b(story|stories|character|poem|novel|fiction|narrative|literary)\b", re.IGNORECASE)

_ANALYSIS_FOR_GENRE = {
    "argumentative": "evaluate_argument",
    "literary": "author_purpose_structure",
    "historical_primary": "inference",
    "informational": "inference",
}


def passage_paragraph_bounds(audience: str) -> tuple[int, int]:
    """Paragraph count for a course audience, using the passage grade bands.

    Ages 6-11 follow Grades 3-5. Ages 12-14 follow Grades 6-8. Ages 15-17 follow Grades 9-12.
    """
    band = (audience or "").strip()
    if band == "15-17":
        return 3, 4
    if band == "12-14":
        return 2, 3
    return 1, 2


def passage_word_bounds(audience: str) -> tuple[int, int]:
    """Word count that goes with passage_paragraph_bounds for this audience."""
    _low, high = passage_paragraph_bounds(audience)
    if high <= 2:
        return 100, 180
    if high <= 3:
        return 200, 320
    return 320, 450


def _word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


def passage_subject(description: str) -> str:
    """A short topic phrase taken from the component description."""
    text = " ".join((description or "").split()).strip().rstrip(".")
    if not text:
        return "this idea"
    match = _ABOUT.search(text)
    if match:
        subject = _SUBJECT_STOP.split(match.group(1).strip(), maxsplit=1)[0]
        subject = subject.strip(" .,:;\"'")
        if subject:
            text = subject
    words = text.split()
    if len(words) > 8:
        words = words[:8]
    subject = " ".join(words).strip()
    if not subject:
        return "this idea"
    return subject[:1].lower() + subject[1:]


def passage_genre_for(description: str) -> str:
    """The passage genre named by the description, or informational."""
    text = description or ""
    if _ARGUMENT.search(text):
        return "argumentative"
    if _PRIMARY.search(text):
        return "historical_primary"
    if _LITERARY.search(text):
        return "literary"
    return "informational"


def _passage_title(subject: str) -> str:
    words = [word for word in subject.split() if word]
    if not words:
        return "Reading passage"
    return " ".join(word[:1].upper() + word[1:] for word in words)[:160]


def _passage_groups(subject: str) -> list[list[str]]:
    """Sentences for up to four paragraphs. The first sentence of each paragraph can be quoted."""
    name = subject[:1].upper() + subject[1:]
    lower = subject
    return [
        [
            f"{name} begins where a reader can point, in a place with a person and one clear action.",
            "A brass key sits on the table in the first scene.",
            "The key is real, and it is small.",
            "A reader who stops there knows a fact, not the idea the rest of the passage builds.",
            f"That opening keeps {lower} concrete, so the later scenes have something to return to.",
        ],
        [
            f"The next scene returns to {lower} in a new place.",
            "What stays the same is the idea, and what changes is the setting.",
            "A careful reader checks the first guess against this new scene.",
            "If the guess only fit the first object, it is too small to be the central idea.",
            "The passage keeps both scenes so the reader can tell a detail from the thread that runs through them.",
            "A second example arrives, then a third, and each one does the same kind of work.",
        ],
        [
            "By the middle of the passage, the same kind of work shows up again.",
            "The repeated work is the evidence, and it is not a list of unrelated events.",
            "Each return shows the idea holding, even when the surface looks different.",
            "A reader can cite those returns because the words sit on the page in full sentences.",
            "One moment is quiet, the next is busy, and both point back to the same cause.",
            "Seeing the pair together is what turns a single fact into a central idea.",
        ],
        [
            "The ending does not add a new topic.",
            f"The scenes, taken together, show {lower} at work.",
            "The first object is still true, and it is still minor next to the larger change.",
            "The central idea is the thread, not the key on the table.",
            "A reader who can say that thread in their own words has used the whole passage, not one line of it.",
            "The last picture is quiet: the people are still there, the action has finished, and the cause is the one named at the start.",
            "Nothing in the close asks the reader to leave the passage for a definition.",
            "The proof is the set of scenes, read in order, each one adding to the same point.",
        ],
    ]


def draft_passage_ela_block(description: str, audience: str, block_id: str = "blk_passage") -> dict:
    """One filled passage_ela block written from the topic description."""
    subject = passage_subject(description)
    genre = passage_genre_for(description)
    count = passage_paragraph_bounds(audience)[1]
    groups = _passage_groups(subject)[:count]
    paragraphs = [" ".join(group) for group in groups]
    passage_text = "\n\n".join(paragraphs)
    quotes = [groups[0][0], groups[-1][0]]
    focus = _ANALYSIS_FOR_GENRE.get(genre, "inference")
    data = clean_passage_ela_data(
        {
            "passage_title": _passage_title(subject),
            "passage_genre": genre,
            "passage_text": passage_text,
            "central_idea_question": "What is the central idea of this passage?",
            "expected_central_idea": (
                f"The central idea is that {subject} ties the scenes together, "
                "and the brass key is only a minor detail."
            ),
            "distractor_detail": "A brass key sits on the table in the first scene.",
            "evidence_prompt": "Cite two sentences from the passage that support the central idea.",
            "verbatim_evidence_quotes": quotes,
            "analysis_focus": focus,
            "analysis_question": f"What can a reader infer about {subject} from the way the passage ends?",
            "expected_analysis": (
                f"The ending shows that {subject} holds the scenes together, "
                "so the central idea is that thread rather than the brass key."
            ),
        }
    )
    return {"id": block_id or "blk_passage", "type": "passage_ela", "data": data}


def _ready_passage(block: dict, audience: str) -> dict | None:
    """A model passage that already has the text, the quotes, and the three questions."""
    data = block.get("data") if isinstance(block.get("data"), dict) else {}
    text = str(data.get("passage_text") or "")
    if _PASSAGE_PLACEHOLDER.search(text) or _word_count(text) < 40:
        return None
    cleaned = clean_passage_ela_data(data)
    if passage_ela_gap(cleaned):
        return None
    low, high = passage_paragraph_bounds(audience)
    count = len(passage_paragraphs(cleaned["passage_text"]))
    if count < low or count > high:
        return None
    block_id = str(block.get("id") or "").strip() or "blk_passage"
    return {"id": block_id, "type": "passage_ela", "data": cleaned}


def draft_scoped_blocks(
    description: str,
    audience: str,
    allowed_block_types: list[str] | None,
    blocks: list[dict] | None = None,
) -> list[dict]:
    """Keep the other blocks. Add one passage_ela block when that type is in scope."""
    allowed = clean_allowed_block_types(allowed_block_types)
    incoming = [block for block in (blocks or []) if isinstance(block, dict)]
    if "passage_ela" not in allowed:
        return [block for block in incoming if str(block.get("type") or "") != "passage_ela"]
    kept: list[dict] = []
    placed = False
    fallback_id = "blk_passage"
    seen_passage = False
    for block in incoming:
        if str(block.get("type") or "") != "passage_ela":
            kept.append(block)
            continue
        if not seen_passage:
            fallback_id = str(block.get("id") or "").strip() or fallback_id
            seen_passage = True
        if placed:
            continue
        ready = _ready_passage(block, audience)
        if ready is None:
            continue
        kept.append(ready)
        placed = True
    if not placed:
        kept.append(draft_passage_ela_block(description, audience, fallback_id))
    return kept


def _passage_scope_lines(allowed: list[str], audience: str) -> list[str]:
    if "passage_ela" not in allowed:
        return []
    low, high = passage_paragraph_bounds(audience)
    low_words, high_words = passage_word_bounds(audience)
    return [
        "passage_ela is in this course's AI Block Scope. "
        "Emit exactly one passage_ela block for this component. "
        "Write passage_text as an original passage from this component's description. "
        'It is not a placeholder such as "Read the following passage about...". '
        f"This course audience is {audience or 'unspecified'}. "
        f"Use {low} to {high} paragraphs (about {low_words} to {high_words} words), "
        "with a blank line between paragraphs. "
        f"{PASSAGE_LENGTH_GUIDELINES} "
        "Set passage_title and passage_genre from that description. "
        "passage_genre is informational, literary, argumentative, or historical_primary. "
        "Fill the three questions on that same block. "
        "Central idea: central_idea_question, expected_central_idea, and distractor_detail "
        "(a true but minor detail from one paragraph). "
        "Cite evidence: evidence_prompt and two or three verbatim_evidence_quotes copied exactly from passage_text. "
        "Craft or inference: analysis_focus, analysis_question, and expected_analysis. "
        "Do not put the reading in a worked example, and do not name a passage without writing it. "
        "Other allowed block types stay as they are."
    ]


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
    siblings: list[dict],
    course_brief: str = "",
    outcomes: list[str] | None = None,
    position: str = "",
    builds_on: list[dict] | None = None,
    leads_to: list[dict] | None = None,
    standard_codes: list[str] | None = None,
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
    description = (node_description or "").strip() or "This component has no description yet. Use the title and the course."
    other_codes = [str(item["code"]) for item in siblings if item.get("code")]
    pair_lines = [f"- {item['topic']}: {item['goal']}" for item in clean_pairs(node_topics or [])]
    block_lines: list[str] = []
    for idx, blk in enumerate(node_blocks or [], start=1):
        if not isinstance(blk, dict):
            continue
        btype = str(blk.get("type") or "topic_goal")
        bdata = blk.get("data") if isinstance(blk.get("data"), dict) else {}
        focus = _block_focus(bdata)
        block_lines.append(f"- Block {idx}: {btype} ({BLOCK_LABELS.get(btype, btype)}) - {focus}".rstrip(" -"))
    if previous:
        prev_blocks = previous.get("blocks") or []
        prev_summary = ", ".join(str(b.get("type")) for b in prev_blocks if isinstance(b, dict)) or "none"
        previous_line = (
            "A draft is already in the thread. This message is a follow-up. "
            "The discussion answers it: say what to add or change and why. "
            "Revise only the blocks that message is about. "
            "Still return the full draft so Push draft stays a straight copy. "
            f"Current blocks: {prev_summary}. "
            f"Current core truth: {previous.get('core_truth') or 'none'}."
        )
    else:
        previous_line = (
            "There is no draft yet. "
            "Go into the topic before you fill the outline, the core truth, the blocks, and the links."
        )
    allowed_rules = "\n".join(BLOCK_AUTHORING_RULES[btype] for btype in allowed if btype in BLOCK_AUTHORING_RULES)
    outcome_lines = "\n".join(f"- {item}" for item in (outcomes or []) if str(item).strip())
    lines = [
        CREATOR_RULES,
        f"Course: {course_title}. {course_description}".strip(),
        f"Audience: {audience}",
        kind_line,
    ]
    if (course_brief or "").strip():
        lines.extend(["Course brief:", course_brief.strip()])
    if outcome_lines:
        lines.extend(["Course outcomes:", outcome_lines])
    if "passage_ela" in allowed:
        lines.extend(passage_ela_generation_lines(course_title, course_description, audience))
    lines.append(f"Component: {node_title} ({node_code})")
    if (position or "").strip():
        lines.append(f"Position: {position.strip()}")
    lines.extend(
        [
            _link_line("Builds on", builds_on or []),
            _link_line("Leads to", leads_to or []),
            "Description:",
            description,
        ]
    )
    if standard_codes:
        lines.append("Standard codes this component covers: " + ", ".join(standard_codes) + ".")
    elif standard_codes is not None:
        lines.append("This component is an extension. It covers no standard statement.")
    lines.extend(
        [
            f"Outline: {(node_outline or '').strip() or 'None yet.'}",
        ]
    )
    if pair_lines:
        lines.extend(["Stored topics:", "\n".join(pair_lines)])
    lines.extend(
        [
            "Seeded blocks (populate and enrich this sequence if present):",
            "\n".join(block_lines) if block_lines else "- None yet.",
            "Other components in this course (link only to these codes):",
            _sibling_lines(siblings),
            previous_line,
            f"You may ONLY generate blocks whose `type` is in this allowed list: {allowed}. "
            "Do not generate any other block type.",
            "Allowed block type specifications:",
            allowed_rules,
            *_passage_scope_lines(allowed, audience),
            "Return an ordered blocks[] array of 1 to 6 blocks using only the allowed block types, "
            "the outline in the outline field, the core_truth, misconceptions, prerequisites, and encompasses.",
            _creator_links(other_codes),
        ]
    )
    return {
        "model": chosen,
        "system_prompt": "\n".join(lines),
        "user_prompt": (message or "").strip(),
        "schema": _creator_schema(other_codes, allowed),
    }


def checked_discussion(discussion: str, title: str) -> str:
    """Keep a real follow-up. Reject an empty reply and a reply that is only Title:."""
    del title
    text = (discussion or "").strip()
    if not text:
        raise ValueError("Answer the latest message.")
    if text.lower() == "title:":
        raise ValueError("Go into the topic before you fill the fields.")
    return text
