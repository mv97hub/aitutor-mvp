"""Mastery claims for one component, and the blocks a recipe drafts from them.

Claims are observable statements. target_level is an integer from 0 to 3.
An empty spec means the component keeps today's block list.
"""

from __future__ import annotations

import re

from app.block_catalog import ARCHETYPES, ARCHETYPE_RECIPES, SKILL_KEYS, recipe_block_types

TARGET_LEVELS = (0, 1, 2, 3)
_CLAIM_ID = 80
_CLAIM_TEXT = 1000

DEFAULT_SKILLS: dict[str, tuple[str, ...]] = {
    "procedural_conceptual": ("transfer", "errors"),
    "causal_systems": ("causes", "explaining"),
    "textual_interpretive": ("evidence", "inquiry"),
    "factual_terminological": ("explaining", "calibration"),
    "normative_synthesis": ("perspectives", "inquiry"),
}

_TEXTUAL = re.compile(
    r"\bela\b|english language arts|reading comprehension|informational text|"
    r"close reading|\bliterature\b|\bpoem\b|\bpassage\b",
    re.IGNORECASE,
)
_FACTUAL = re.compile(r"\bvocabulary\b|\bdefinition\b|\bterminology\b|\bglossary\b|\bdefine\b", re.IGNORECASE)
_PROCEDURAL = re.compile(
    r"\bprocedure\b|\balgorithm\b|\bequation\b|\bcalculate\b|\bsolve\b|\bworked example\b",
    re.IGNORECASE,
)
_NORMATIVE = re.compile(r"\bethic|\bshould\b|\bdebate\b|\bpolicy\b|\bsynthesis\b|\bcapstone\b|\bargue\b", re.IGNORECASE)

_CLAIM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "statement": {"type": "string"},
    },
    "required": ["id", "statement"],
}

MASTERY_SPEC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "description": "Assigned before blocks. Claims are observable statements. target_level is 0 to 3.",
    "properties": {
        "archetype": {"type": "string", "enum": list(ARCHETYPES)},
        "claims": {"type": "array", "minItems": 2, "maxItems": 3, "items": _CLAIM_SCHEMA},
        "target_level": {"type": "integer", "minimum": 0, "maximum": 3},
        "skills": {"type": "array", "items": {"type": "string", "enum": list(SKILL_KEYS)}},
    },
    "required": ["archetype", "claims", "target_level", "skills"],
}


def _recipe_sentence() -> str:
    parts = [f"{name} uses {', '.join(kinds)}" for name, kinds in ARCHETYPE_RECIPES.items()]
    return (
        "Before any block is chosen, assign mastery_spec on each component. "
        f"archetype is one of: {', '.join(ARCHETYPES)}. "
        "claims are two or three observable statements of what the learner can do. "
        "Each claim has an id and a statement. "
        "target_level is an integer from 0 to 3. That is the only level. "
        f"skills lists which of these eight keys the component can feed: {', '.join(SKILL_KEYS)}. "
        "Recipes are applied after the claims and filtered by the course's allowed block types: "
        + "; ".join(parts)
        + ". "
        "Do not return a block list. Blocks are drafted from the recipe after the claims."
    )


PLAN_RULES = _recipe_sentence()

UNIT_MASTERY_RULES = (
    "Confirm or revise mastery_spec before any block is chosen. "
    "A claim is an observable statement. target_level is an integer from 0 to 3. That is the only level. "
    "Do not write the block list in the description. Blocks are drafted from the archetype recipe after the claims."
)


def _squash(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def is_blank_spec(raw: object) -> bool:
    if raw is None or raw == {}:
        return True
    if not isinstance(raw, dict):
        return False
    if raw.get("archetype") or raw.get("claims"):
        return False
    if raw.get("skills"):
        return False
    level = raw.get("target_level")
    return level in (None, "")


def actionable_spec(spec: object) -> bool:
    """A spec that can draft a recipe. An empty object is not one."""
    if not isinstance(spec, dict):
        return False
    if spec.get("archetype") not in ARCHETYPES:
        return False
    claims = spec.get("claims")
    if not isinstance(claims, list) or not 2 <= len(claims) <= 3:
        return False
    if any(not isinstance(item, dict) or not _squash(item.get("statement")) for item in claims):
        return False
    return spec.get("target_level") in TARGET_LEVELS


def infer_archetype(title: str, summary: str = "", course_text: str = "", *, capstone: bool = False) -> str:
    """A deterministic archetype when the model left it out. No model call."""
    from app.kc_pipeline import course_is_ela

    blob = " ".join(str(part or "") for part in (title, summary, course_text))
    if course_is_ela(title, summary, course_text) or _TEXTUAL.search(blob):
        return "textual_interpretive"
    if _FACTUAL.search(blob):
        return "factual_terminological"
    if _PROCEDURAL.search(blob):
        return "procedural_conceptual"
    if capstone or _NORMATIVE.search(blob):
        return "normative_synthesis"
    return "causal_systems"


def _default_claims(title: str, summary: str) -> list[dict]:
    subject = _squash(title) or "this idea"
    return [
        {"id": "c1", "statement": f"Explain {subject} in their own words."},
        {"id": "c2", "statement": f"Use {subject} on a new example."},
    ]


def _claim_rows(raw: object, *, repair: bool, title: str, summary: str) -> list[dict]:
    rows: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                statement = _squash(item.get("statement") if item.get("statement") is not None else item.get("text"))
                if len(statement) > _CLAIM_TEXT:
                    if not repair:
                        raise ValueError("A mastery claim is too long.")
                    statement = statement[:_CLAIM_TEXT].rstrip()
                if not statement:
                    if repair:
                        continue
                    raise ValueError("Each mastery claim needs a statement.")
                rows.append({"id": _squash(item.get("id"))[:_CLAIM_ID], "statement": statement})
            elif isinstance(item, str) and repair:
                statement = _squash(item)[:_CLAIM_TEXT].rstrip()
                if statement:
                    rows.append({"id": "", "statement": statement})
            elif not repair:
                raise ValueError("Each mastery claim needs an id and a statement.")
    if repair:
        if len(rows) > 3:
            rows = rows[:3]
        used = {row["statement"].lower() for row in rows}
        for extra in _default_claims(title, summary):
            if len(rows) >= 2:
                break
            if extra["statement"].lower() not in used:
                rows.append(dict(extra))
                used.add(extra["statement"].lower())
        if len(rows) < 2:
            rows = _default_claims(title, summary)
    elif len(rows) < 2 or len(rows) > 3:
        raise ValueError("A component has two or three mastery claims.")
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        cid = row["id"]
        if repair:
            if not cid or cid in seen:
                cid = f"c{index}"
                while cid in seen:
                    cid = f"{cid}-x"
        elif not cid or cid in seen:
            raise ValueError("Each mastery claim needs its own id.")
        seen.add(cid)
        row["id"] = cid
    return rows


def _level(raw: object, *, repair: bool) -> int:
    value = raw.get("target_level") if isinstance(raw, dict) and "target_level" in raw else None
    if isinstance(value, bool) or not isinstance(value, int) or value not in TARGET_LEVELS:
        if repair:
            return 2
        raise ValueError("target_level is 0, 1, 2, or 3.")
    return value


def _skills(raw: object, archetype: str, *, repair: bool) -> list[str]:
    if not isinstance(raw, dict) or "skills" not in raw or raw.get("skills") is None:
        if repair:
            return list(DEFAULT_SKILLS[archetype])
        raise ValueError("mastery_spec names the skills this component can feed.")
    value = raw.get("skills")
    if not isinstance(value, list):
        if repair:
            return list(DEFAULT_SKILLS[archetype])
        raise ValueError("skills is a list of the eight skill keys.")
    kept: list[str] = []
    for item in value:
        key = _squash(item).lower().replace(" ", "_")
        if key in SKILL_KEYS and key not in kept:
            kept.append(key)
            continue
        if key and not repair:
            raise ValueError(f"{item!r} is not one of the eight skill keys.")
    if not kept and value and repair:
        return list(DEFAULT_SKILLS[archetype])
    return kept


def _named_archetype(raw: object) -> str:
    if not isinstance(raw, dict):
        return ""
    return _squash(raw.get("archetype"))


def parse_mastery_spec(raw: object) -> dict:
    """Keep a stored spec as it was written. A missing spec stays empty."""
    if is_blank_spec(raw):
        if raw is None or raw == {} or (isinstance(raw, dict) and not raw):
            return {}
        if isinstance(raw, dict):
            return {}
        raise ValueError("mastery_spec is an object.")
    if not isinstance(raw, dict):
        raise ValueError("mastery_spec is an object.")
    archetype = _named_archetype(raw)
    if archetype not in ARCHETYPES:
        raise ValueError("archetype is one of the five component archetypes.")
    return {
        "archetype": archetype,
        "claims": _claim_rows(raw.get("claims"), repair=False, title="", summary=""),
        "target_level": _level(raw, repair=False),
        "skills": _skills(raw, archetype, repair=False),
    }


def assign_mastery_spec(
    raw: object,
    *,
    title: str,
    summary: str = "",
    course_text: str = "",
    capstone: bool = False,
) -> dict:
    """The spec blueprint and unit generation store before any block list."""
    archetype = _named_archetype(raw)
    if archetype not in ARCHETYPES:
        archetype = infer_archetype(title, summary, course_text, capstone=capstone)
    claims_raw = raw.get("claims") if isinstance(raw, dict) else None
    return {
        "archetype": archetype,
        "claims": _claim_rows(claims_raw, repair=True, title=title, summary=summary),
        "target_level": _level(raw, repair=True),
        "skills": _skills(raw, archetype, repair=True),
    }


def spec_for_draft(raw: object, stored: object) -> dict:
    """The spec already assigned on the draft or the node. Never invent one here."""
    for candidate in (raw, stored):
        try:
            parsed = parse_mastery_spec(candidate)
        except ValueError:
            continue
        if actionable_spec(parsed):
            return parsed
    return {}


def claim_ids_of(block: object) -> list[str]:
    if not isinstance(block, dict):
        return []
    raw = block.get("claim_ids")
    if not isinstance(raw, list):
        return []
    kept: list[str] = []
    for item in raw:
        text = _squash(item)[:_CLAIM_ID]
        if text and text not in kept:
            kept.append(text)
    return kept


def _tag_claims(kinds: list[str], claim_ids: list[str]) -> list[list[str]]:
    if not kinds:
        return []
    if not claim_ids:
        return [[] for _ in kinds]
    tags = [[claim_ids[index % len(claim_ids)]] for index in range(len(kinds))]
    covered = {cid for group in tags for cid in group}
    missing = [cid for cid in claim_ids if cid not in covered]
    if missing:
        tags[-1] = list(dict.fromkeys([*tags[-1], *missing]))
    return tags


def _skeleton(kind: str, statement: str) -> dict:
    text = statement.strip() or "The idea."
    if kind == "curiosity":
        return {
            "phenomenon_hook": text,
            "prediction_question": "What do you expect to happen?",
            "bridge_to_unit": text,
        }
    if kind == "explanation":
        return {
            "block_title": text[:80],
            "topics": [{"id": "t1", "title": "The idea", "explanation": text}],
            "summary_takeaway": text,
        }
    if kind == "worked_example":
        return {
            "problem_statement": text,
            "steps": [
                {"step_text": "Name the idea.", "rationale": text},
                {"step_text": "Use it on the example.", "rationale": ""},
            ],
            "faded_step_index": 1,
            "solo_problem": "Use the same idea on a new example.",
            "solo_expected_answer": text,
        }
    if kind == "spot_the_flaw":
        return {
            "rookie_work": "A version that misses the idea.",
            "flaw_description": text,
            "underlying_misconception": "The idea is treated as something else.",
            "corrected_version": text,
        }
    if kind == "mcq":
        return {
            "mode": "static",
            "question_stem": text,
            "choices": [
                {"id": "a", "text": "The claim holds.", "is_correct": True},
                {"id": "b", "text": "A near miss.", "is_correct": False},
            ],
            "correct_explanation": text,
        }
    if kind == "case_study":
        return {
            "case_a": text,
            "case_b": "A contrasting case of the same idea.",
            "prediction_prompt": "What stays the same?",
            "invariant_principle": text,
        }
    if kind == "teach_back":
        return {
            "peer_persona_prompt": "Explain it to a classmate.",
            "required_concepts": [text[:120]],
            "peer_follow_up_question": "Why does that hold?",
        }
    if kind == "socratic":
        return {
            "central_dilemma": text,
            "initial_probe": "What would you say first?",
            "counterexamples": ["A case that challenges the first answer."],
            "target_synthesis": text,
        }
    if kind == "retrieval_check":
        return {
            "recall_prompt": text,
            "expected_fact": text,
            "elaborative_why_prompt": "Why is that true?",
            "expected_why_rationale": text,
        }
    return {}


def _statement_for(spec: dict, claim_ids: list[str]) -> str:
    by_id = {str(item.get("id")): str(item.get("statement") or "") for item in spec.get("claims") or []}
    texts = [by_id[cid] for cid in claim_ids if by_id.get(cid)]
    return texts[0] if texts else ""


def draft_recipe_blocks(
    spec: dict,
    *,
    description: str = "",
    audience: str = "",
    allowed: list[str] | None = None,
    course_title: str = "",
    course_description: str = "",
    incoming: list[dict] | None = None,
) -> list[dict]:
    """Blocks in recipe order, each tagged with the claim ids it teaches or checks.

    An empty result means the allowed types left nothing to draft, and the caller
    keeps today's block list.
    """
    from app.kc_model import clean_allowed_block_types, draft_passage_ela_block, passage_draft_allowed

    if not actionable_spec(spec):
        return []
    archetype = str(spec.get("archetype") or "")
    allowed_list = clean_allowed_block_types(allowed)
    kinds = recipe_block_types(archetype, allowed_list)
    if "passage_ela" in kinds and not passage_draft_allowed(
        course_title,
        course_description,
        description,
        archetype=archetype,
    ):
        kinds = [kind for kind in kinds if kind != "passage_ela"]
    if not kinds:
        return []
    claim_ids = [str(item.get("id")) for item in spec.get("claims") or [] if isinstance(item, dict) and item.get("id")]
    tags = _tag_claims(kinds, claim_ids)
    pools: dict[str, list[dict]] = {}
    for block in incoming or []:
        if isinstance(block, dict):
            pools.setdefault(str(block.get("type") or ""), []).append(block)
    drafted: list[dict] = []
    seen: set[str] = set()
    for index, (kind, tagged) in enumerate(zip(kinds, tags), start=1):
        source = pools.get(kind) or []
        used = source.pop(0) if source else None
        block_id = str((used or {}).get("id") or "").strip() or f"blk_{index}"
        if block_id in seen:
            block_id = f"{block_id}-{index}"
        seen.add(block_id)
        data = (used or {}).get("data") if isinstance((used or {}).get("data"), dict) else None
        if kind == "passage_ela":
            from app.kc_model import _ready_passage

            ready = _ready_passage(used, audience) if isinstance(used, dict) else None
            if ready is None:
                data = draft_passage_ela_block(description or course_description or course_title, audience, block_id)["data"]
            else:
                data = ready["data"]
        elif not isinstance(data, dict) or not data:
            data = _skeleton(kind, _statement_for(spec, tagged))
        else:
            data = dict(data)
        drafted.append({"id": block_id, "type": kind, "claim_ids": list(tagged), "data": data})
    return drafted


def blocks_for_draft(
    spec: object,
    incoming: list[dict] | None,
    *,
    regenerate: bool,
    description: str = "",
    audience: str = "",
    allowed: list[str] | None = None,
    course_title: str = "",
    course_description: str = "",
    archetype: str = "",
) -> list[dict]:
    """Recipe blocks for a new or regenerated component that has a spec.

    A stored list that is not being regenerated is returned in the same order.
    An empty spec uses today's block derivation.
    """
    rows = [block for block in (incoming or []) if isinstance(block, dict)]
    if not regenerate:
        return rows
    chosen = spec if actionable_spec(spec) else {}
    if not chosen:
        from app.kc_model import draft_scoped_blocks

        return draft_scoped_blocks(
            description,
            audience,
            allowed,
            rows,
            course_title=course_title,
            course_description=course_description,
            archetype=archetype,
        )
    drafted = draft_recipe_blocks(
        chosen,
        description=description,
        audience=audience,
        allowed=allowed,
        course_title=course_title,
        course_description=course_description,
        incoming=rows,
    )
    if drafted:
        return drafted
    from app.kc_model import draft_scoped_blocks

    return draft_scoped_blocks(
        description,
        audience,
        allowed,
        rows,
        course_title=course_title,
        course_description=course_description,
        archetype=archetype,
    )


def mastery_prompt_lines(spec: object, allowed: list[str] | None = None) -> list[str]:
    """Creator lines placed before the block list. Empty when the spec is empty."""
    if not actionable_spec(spec):
        return []
    assert isinstance(spec, dict)
    kinds = recipe_block_types(str(spec.get("archetype") or ""), allowed)
    claims = "\n".join(
        f"- {item['id']}: {item['statement']}" for item in spec.get("claims") or [] if isinstance(item, dict)
    )
    skills = ", ".join(str(item) for item in spec.get("skills") or []) or "none"
    return [
        "Mastery claims are already assigned. Fill the blocks after these claims.",
        f"Archetype: {spec.get('archetype')}. Target level: {spec.get('target_level')} on the scale from 0 to 3.",
        f"Skills this component can feed: {skills}.",
        "Claims:",
        claims,
        "Draft the blocks in this recipe order: " + ", ".join(kinds) + ".",
        "Tag each block with the claim ids it teaches or checks.",
    ]


def stored_spec(node: object) -> dict:
    raw = getattr(node, "mastery_spec", None)
    try:
        return parse_mastery_spec(raw)
    except ValueError:
        return {}
