"""Import and export one KC course, including every component's blocks.

The file is KcCourseExportV1. A unit-sized file can merge into a course.
Nothing is written until import, and block data is limited to the fields
in the block catalog.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.block_catalog import BLOCK_AUTHORING_RULES, BLOCK_FIELDS
from app.kc_blocks import clean_passage_ela_data
from app.kc_pipeline import passage_ela_generation_lines
from app.kc import (
    _clean_misconceptions,
    _clean_rubric,
    _nodes_by_code,
    _now,
    _public_blocks,
    _sync_edges,
    clear_course_components,
    create_course,
    load_targets,
    slug_code,
)
from app.kc_pipeline import clean_intake
from app.kc_standards import clean_statements, read_statements
from app.models import KcGoal, KcNode

SCHEMA = "KcCourseExportV1"
_AUDIENCES = ("6-8", "9-11", "12-14", "15-17")
_KINDS = ("mastery", "time_boxed", "curiosity")

_BLOCK_EXAMPLES: dict[str, dict] = {
    "topic_goal": {"topic": "One idea", "goal": "Say it in your own words", "acceptance_criteria": None, "teaching_notes": None},
    "explanation": {
        "block_title": "Why it works",
        "topics": [{"id": "t1", "title": "The idea", "explanation": "One short explanation.", "key_points": None, "examples_or_analogies": None}],
        "summary_takeaway": "The idea in one sentence.",
    },
    "worked_example": {
        "problem_statement": "A small problem.",
        "steps": [{"step_text": "First step.", "rationale": "Why."}, {"step_text": "Second step.", "rationale": None}],
        "faded_step_index": 1,
        "solo_problem": "A matching problem.",
        "solo_expected_answer": "The answer.",
    },
    "mcq": {
        "mode": "static",
        "question_stem": "Which one fits?",
        "choices": [
            {"id": "a", "text": "The fitting one", "is_correct": True, "distractor_rationale": None, "misconception_code": None},
            {"id": "b", "text": "A near miss", "is_correct": False, "distractor_rationale": "It swaps the idea.", "misconception_code": None},
        ],
        "correct_explanation": "Why the fitting one is right.",
    },
    "socratic": {
        "central_dilemma": "A choice with no easy side.",
        "initial_probe": "What would you do first?",
        "counterexamples": ["A case that challenges the first answer."],
        "target_synthesis": "The idea the talk should reach.",
    },
    "case_study": {
        "case_a": "One case.",
        "case_b": "A contrasting case.",
        "prediction_prompt": "What stays the same?",
        "invariant_principle": "The rule both cases share.",
        "transfer_prompt": None,
        "transfer_expected": None,
    },
    "spot_the_flaw": {
        "rookie_work": "A wrong solution.",
        "flaw_description": "What is wrong.",
        "underlying_misconception": "The idea that caused it.",
        "corrected_version": "The fixed solution.",
    },
    "teach_back": {
        "peer_persona_prompt": "Explain it to a classmate.",
        "required_concepts": ["The core idea"],
        "peer_follow_up_question": "Why does that work?",
    },
    "retrieval_check": {
        "recall_prompt": "What was the idea?",
        "expected_fact": "The idea, in short.",
        "elaborative_why_prompt": "Why is that true?",
        "expected_why_rationale": "The reason.",
    },
    "curiosity": {
        "phenomenon_hook": "Something surprising.",
        "prediction_question": "What do you think happens?",
        "bridge_to_unit": "How this leads into the idea.",
        "wonder_branches": None,
    },
    "passage_ela": {
        "passage_title": "River roads",
        "passage_genre": "informational",
        "passage_text": (
            "Rivers carry fresh water from the hills to the sea.\n\n"
            "Towns grow beside rivers because boats can move food and people."
        ),
        "central_idea_question": "What is the central idea of the passage?",
        "expected_central_idea": "Rivers help towns because they move water, food, and people.",
        "distractor_detail": "Boats can move food and people.",
        "evidence_prompt": "Cite two sentences from the passage that support the central idea.",
        "verbatim_evidence_quotes": [
            "Rivers carry fresh water from the hills to the sea.",
            "Towns grow beside rivers because boats can move food and people.",
        ],
        "analysis_focus": "inference",
        "analysis_question": "What can a reader infer about a town far from a river?",
        "expected_analysis": "A town far from a river would have a harder time moving food and people.",
    },
}


def normalize_blocks(raw: object) -> list[dict]:
    """Keep catalog fields for known block types. Unknown types are rejected."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("Blocks are a list.")
    cleaned: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Block {index} needs a type and data.")
        kind = str(item.get("type") or "").strip()
        if kind not in BLOCK_FIELDS:
            known = ", ".join(BLOCK_FIELDS)
            raise ValueError(f"Block {index} has unknown type {kind!r}. Use one of: {known}.")
        data = item.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"Block {index} needs a data object.")
        allowed = {key for key, _label in BLOCK_FIELDS[kind]}
        kept = {key: data[key] for key in data if key in allowed}
        if kind == "passage_ela":
            kept = clean_passage_ela_data(kept)
        block_id = str(item.get("id") or "").strip() or f"blk_{index}"
        if block_id in seen:
            block_id = f"{block_id}-{index}"
        seen.add(block_id)
        cleaned.append({"id": block_id, "type": kind, "data": kept})
    return cleaned


def _text(value: object) -> str:
    return str(value or "").strip()


def _string_list(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    if not isinstance(value, list):
        raise ValueError(f"{label} is a list.")
    rows: list[str] = []
    for item in value:
        text = _text(item)
        if text and text not in rows:
            rows.append(text)
    return rows


def _clean_component(raw: object, statements: list[dict[str, str]]) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Each component needs a title.")
    title = _text(raw.get("title"))
    if not title:
        raise ValueError("Each component needs a title.")
    standards = _string_list(raw.get("standards"), f"{title} standards")
    known = {item["code"] for item in statements}
    if known:
        unknown = [code for code in standards if code not in known]
        if unknown:
            raise ValueError(f"{title} names {unknown[0]!r}, which is not one of the course statements.")
    return {
        "code": _text(raw.get("code")),
        "title": title,
        "description": _text(raw.get("description")),
        "summary": _text(raw.get("summary")) or _text(raw.get("description"))[:240],
        "outline": _text(raw.get("outline")),
        "core_truth": _text(raw.get("core_truth")),
        "rubric": _clean_rubric(raw.get("rubric") or []),
        "misconceptions": _clean_misconceptions(raw.get("misconceptions") or []),
        "standards": standards,
        "prerequisite_codes": _string_list(raw.get("prerequisite_codes"), f"{title} prerequisites"),
        "encompasses_codes": _string_list(raw.get("encompasses_codes"), f"{title} encompasses"),
        "blocks": normalize_blocks(raw.get("blocks")),
    }


def _clean_unit(raw: object, statements: list[dict[str, str]]) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Each unit needs a title and components.")
    title = _text(raw.get("title"))
    components_raw = raw.get("components")
    if not title or not isinstance(components_raw, list) or not components_raw:
        raise ValueError("Each unit needs a title and at least one component.")
    return {
        "title": title,
        "summary": _text(raw.get("summary")),
        "components": [_clean_component(item, statements) for item in components_raw],
    }


def _course_standards(course: dict | None) -> list[dict[str, str]]:
    if not course:
        return []
    raw = course.get("standards") or []
    if not raw:
        return []
    return clean_statements(raw)


def parse_course_document(raw: object) -> dict[str, Any]:
    """A full course file, a units list, or one unit from a unit-by-unit reply."""
    if not isinstance(raw, dict):
        raise ValueError("The course file could not be read.")
    course = raw.get("course") if isinstance(raw.get("course"), dict) else None
    statements = _course_standards(course)
    if isinstance(raw.get("unit"), dict) and not isinstance(raw.get("units"), list):
        return {"course": course, "units": [_clean_unit(raw["unit"], statements)], "partial": True}
    units_raw = raw.get("units")
    if not isinstance(units_raw, list) or not units_raw:
        raise ValueError("The file needs at least one unit.")
    units = [_clean_unit(item, statements) for item in units_raw]
    seen: set[str] = set()
    for unit in units:
        for item in unit["components"]:
            if item["code"] and item["code"] in seen:
                raise ValueError(f"The code {item['code']!r} is used twice.")
            if item["code"]:
                seen.add(item["code"])
    return {"course": course, "units": units, "partial": course is None}


def preview_document(raw: object) -> dict:
    """Counts for the import screen. Nothing is written."""
    parsed = parse_course_document(raw)
    units = []
    components = 0
    blocks = 0
    for unit in parsed["units"]:
        unit_blocks = sum(len(item["blocks"]) for item in unit["components"])
        units.append({"title": unit["title"], "components": len(unit["components"]), "blocks": unit_blocks})
        components += len(unit["components"])
        blocks += unit_blocks
    course = parsed["course"] or {}
    standards = _course_standards(parsed["course"])
    return {
        "partial": parsed["partial"],
        "title": _text(course.get("title")),
        "units": units,
        "component_count": components,
        "block_count": blocks,
        "standards": standards,
    }


def _audience(value: object) -> str:
    text = _text(value)
    if text in _AUDIENCES:
        return text
    raise ValueError("grade_band is 6-8, 9-11, 12-14, or 15-17.")


def _kind(value: object) -> str:
    text = _text(value) or "mastery"
    if text not in _KINDS:
        raise ValueError("kind is mastery, time_boxed, or curiosity.")
    return text


def _minutes(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("estimated_minutes is a positive number or blank.") from exc
    if minutes <= 0:
        raise ValueError("estimated_minutes is a positive number or blank.")
    return minutes


def _outcomes(course: dict | None, goal: KcGoal | None) -> list[str]:
    raw = (course or {}).get("outcomes")
    if isinstance(raw, list):
        rows = [_text(item) for item in raw if _text(item)]
        if len(rows) >= 2:
            return rows[:8]
    if goal is not None and isinstance(goal.blueprint, dict):
        existing = [_text(item) for item in (goal.blueprint.get("outcomes") or []) if _text(item)]
        if len(existing) >= 2:
            return existing
    return [
        "Explain the ideas in this course in their own words.",
        "Use the ideas on a new example.",
    ]


def _blueprint(units: list[dict], outcomes: list[str], statements: list[dict]) -> dict:
    known = {item["code"] for item in statements}
    built = []
    for unit in units:
        components = []
        for item in unit["components"]:
            components.append(
                {
                    "code": item["code"],
                    "title": item["title"],
                    "summary": item["summary"] or item["title"],
                    "prerequisites": list(item["prerequisite_codes"]),
                    "standards": list(item["standards"]),
                    "extension": bool(known) and not item["standards"],
                }
            )
        built.append({"title": unit["title"], "summary": unit["summary"], "components": components})
    return {"outcomes": outcomes, "units": built}


def _descriptions(units: list[dict]) -> dict[str, str]:
    notes = {}
    for unit in units:
        for item in unit["components"]:
            if item["code"] and item["description"]:
                notes[item["code"]] = item["description"]
    return notes


def _assign_codes(db: Session, units: list[dict]) -> None:
    taken = set(_nodes_by_code(db))
    for unit in units:
        for item in unit["components"]:
            if item["code"]:
                taken.add(item["code"])
    for unit in units:
        for item in unit["components"]:
            if item["code"]:
                continue
            item["code"] = slug_code(item["title"], taken)
            taken.add(item["code"])


def _check_links(units: list[dict], extra: set[str]) -> None:
    codes = {item["code"] for unit in units for item in unit["components"]} | extra
    for unit in units:
        for item in unit["components"]:
            for code in [*item["prerequisite_codes"], *item["encompasses_codes"]]:
                if code not in codes:
                    raise ValueError(f"{item['title']} names {code!r}, which is not a component in this course.")


def _write_node(db: Session, item: dict, by_code: dict[str, KcNode], on_course: set[str]) -> KcNode:
    node = by_code.get(item["code"])
    if node is not None and str(node.id) not in on_course and (node.core_truth or node.blocks or node.description):
        taken = set(by_code)
        item["code"] = slug_code(item["title"], taken)
        node = None
    if node is None:
        node = KcNode(code=item["code"], title=item["title"])
        db.add(node)
        db.flush()
        by_code[item["code"]] = node
    node.title = item["title"]
    node.description = item["description"]
    node.outline = item["outline"]
    node.core_truth = item["core_truth"]
    node.rubric = item["rubric"]
    node.misconceptions = item["misconceptions"]
    node.standards = item["standards"]
    node.prerequisite_codes = list(item["prerequisite_codes"])
    node.encompasses_codes = list(item["encompasses_codes"])
    node.blocks = item["blocks"]
    node.updated_at = _now()
    return node


def _merge_units(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = [
        {**unit, "components": [dict(item) for item in unit.get("components") or []]}
        for unit in existing
        if isinstance(unit, dict)
    ]
    by_title = {str(unit.get("title") or "").strip().lower(): unit for unit in merged}
    for unit in incoming:
        key = unit["title"].strip().lower()
        current = by_title.get(key)
        if current is None:
            merged.append({"title": unit["title"], "summary": unit["summary"], "components": list(unit["components"])})
            by_title[key] = merged[-1]
            continue
        if unit["summary"]:
            current["summary"] = unit["summary"]
        by_code = {item.get("code"): item for item in current["components"]}
        for item in unit["components"]:
            if item["code"] in by_code:
                by_code[item["code"]].update(item)
            else:
                current["components"].append(item)
    return merged


def _apply_course_fields(db: Session, goal: KcGoal, course: dict) -> None:
    if _text(course.get("title")):
        goal.title = _text(course.get("title"))
    if "description" in course:
        goal.description = _text(course.get("description"))
    if course.get("grade_band") or course.get("audience"):
        goal.audience = _audience(course.get("grade_band") or course.get("audience"))
    if course.get("kind"):
        goal.kind = _kind(course.get("kind"))
    if "estimated_minutes" in course or "minutes" in course:
        goal.minutes = _minutes(course.get("estimated_minutes", course.get("minutes")))
    intake_raw = course.get("intake") if isinstance(course.get("intake"), dict) else {}
    intake = clean_intake({**clean_intake(goal.intake), **intake_raw})
    subject = _text(course.get("subject"))
    if subject:
        intake["subject"] = subject[:160]
    goal.intake = intake
    if "brief" in course:
        goal.brief = _text(course.get("brief"))
    if "standards" in course:
        goal.standards = clean_statements(course.get("standards") or [])


def _store_graph(db: Session, goal: KcGoal, units: list[dict], *, replace: bool) -> None:
    _assign_codes(db, units)
    existing_nodes = load_targets(db, goal)
    existing_codes = {node.code for node in existing_nodes}
    on_course = {str(node.id) for node in existing_nodes}
    _check_links(units, set() if replace else existing_codes)
    by_code = _nodes_by_code(db)
    ordered: list[str] = []
    for unit in units:
        for item in unit["components"]:
            node = _write_node(db, item, by_code, on_course)
            on_course.add(str(node.id))
            _sync_edges(db, node)
            if str(node.id) not in ordered:
                ordered.append(str(node.id))
    if replace:
        incoming = {item["code"] for unit in units for item in unit["components"]}
        clear_course_components(db, goal, existing_codes - incoming)
        goal.target_kc_ids = ordered
    else:
        current = [str(item) for item in (goal.target_kc_ids or [])]
        for item in ordered:
            if item not in current:
                current.append(item)
        goal.target_kc_ids = current
    goal.ready = False
    goal.updated_at = _now()


def _store_draft(goal: KcGoal, units: list[dict], outcomes: list[str], statements: list[dict]) -> None:
    blueprint_units = _blueprint(units, outcomes, statements)["units"]
    goal.blueprint = {"outcomes": outcomes, "units": blueprint_units}
    notes = _descriptions(units)
    complete = all(
        item["code"] in notes
        for unit in blueprint_units
        for item in unit["components"]
    )
    goal.drafting = {
        "questions": [],
        "answers": [],
        "approved": True,
        "standards_confirmed": True,
        "standards_source": "imported",
        "units": notes,
        "units_done": len(blueprint_units) if complete else 0,
        "pushed": True,
    }


def import_new_course(db: Session, raw: object) -> KcGoal:
    parsed = parse_course_document(raw)
    course = parsed["course"]
    if parsed["partial"] or course is None or not _text(course.get("title")):
        raise ValueError("A new course needs the full course file, including a title.")
    audience = _audience(course.get("grade_band") or course.get("audience") or "12-14")
    intake = course.get("intake") if isinstance(course.get("intake"), dict) else {}
    if _text(course.get("subject")):
        intake = {**intake, "subject": _text(course.get("subject"))}
    goal = create_course(
        db,
        title=_text(course.get("title")),
        description=_text(course.get("description")),
        audience=audience,
        kind=_kind(course.get("kind")),
        minutes=_minutes(course.get("estimated_minutes", course.get("minutes"))),
        code=_text(course.get("code")) or None,
        intake=intake,
    )
    _apply_course_fields(db, goal, course)
    statements = read_statements(goal.standards)
    _store_graph(db, goal, parsed["units"], replace=True)
    _store_draft(goal, parsed["units"], _outcomes(course, None), statements)
    db.flush()
    return goal


def _known_statement_codes(statements: list[dict]) -> set[str]:
    return {item["code"] for item in statements}


def _reject_unknown_standards(units: list[dict], statements: list[dict]) -> None:
    known = _known_statement_codes(statements)
    if not known:
        return
    for unit in units:
        for item in unit["components"]:
            unknown = [code for code in item["standards"] if code not in known]
            if unknown:
                raise ValueError(f"{item['title']} names {unknown[0]!r}, which is not one of the course statements.")


def _merge_blueprint(goal: KcGoal, units: list[dict], outcomes: list[str], statements: list[dict]) -> None:
    blueprint = goal.blueprint if isinstance(goal.blueprint, dict) else {}
    existing = [unit for unit in (blueprint.get("units") or []) if isinstance(unit, dict)]
    incoming = _blueprint(units, outcomes, statements)["units"]
    merged = _merge_units(existing, incoming)
    goal.blueprint = {"outcomes": outcomes, "units": merged}
    drafting = dict(goal.drafting) if isinstance(goal.drafting, dict) else {}
    notes = dict(drafting.get("units") or {})
    for unit in units:
        for item in unit["components"]:
            if item["code"] and item["description"]:
                notes[item["code"]] = item["description"]
    done = 0
    for unit in merged:
        codes = [item.get("code") for item in unit.get("components") or []]
        if codes and all(notes.get(code) for code in codes):
            done += 1
            continue
        break
    drafting.update(
        {
            "units": notes,
            "approved": bool(merged),
            "standards_confirmed": True,
            "standards_source": drafting.get("standards_source") or "imported",
            "units_done": done,
            "pushed": True,
        }
    )
    goal.drafting = drafting


def import_into_course(db: Session, goal: KcGoal, raw: object, mode: str) -> KcGoal:
    if mode not in {"replace", "merge"}:
        raise ValueError("Mode is replace or merge.")
    parsed = parse_course_document(raw)
    if parsed["partial"] and mode == "replace":
        raise ValueError("A unit-by-unit file merges into the course. Import the full course to replace it.")
    if mode == "replace":
        if parsed["course"]:
            _apply_course_fields(db, goal, parsed["course"])
        statements = read_statements(goal.standards)
        _reject_unknown_standards(parsed["units"], statements)
        _store_graph(db, goal, parsed["units"], replace=True)
        _store_draft(goal, parsed["units"], _outcomes(parsed["course"], None), statements)
        db.flush()
        return goal
    if parsed["course"]:
        fields = {key: value for key, value in parsed["course"].items() if key != "standards"}
        if fields:
            _apply_course_fields(db, goal, fields)
        if parsed["course"].get("standards"):
            current = {item["code"]: item for item in read_statements(goal.standards)}
            for item in clean_statements(parsed["course"]["standards"]):
                current[item["code"]] = item
            goal.standards = list(current.values())
    statements = read_statements(goal.standards)
    _reject_unknown_standards(parsed["units"], statements)
    _store_graph(db, goal, parsed["units"], replace=False)
    _merge_blueprint(goal, parsed["units"], _outcomes(parsed["course"], goal), statements)
    db.flush()
    return goal


def export_course(db: Session, goal: KcGoal) -> dict:
    intake = clean_intake(goal.intake)
    statements = read_statements(goal.standards)
    blueprint = goal.blueprint if isinstance(goal.blueprint, dict) else {}
    drafting = goal.drafting if isinstance(goal.drafting, dict) else {}
    notes = dict(drafting.get("units") or {})
    by_code = {node.code: node for node in load_targets(db, goal)}
    units: list[dict] = []
    seen: set[str] = set()
    for unit in blueprint.get("units") or []:
        if not isinstance(unit, dict):
            continue
        components = []
        for item in unit.get("components") or []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "")
            node = by_code.get(code)
            components.append(_export_component(item, node, notes.get(code, "")))
            if node is not None:
                seen.add(str(node.id))
        if components:
            units.append(
                {"title": str(unit.get("title") or ""), "summary": str(unit.get("summary") or ""), "components": components}
            )
    extras = [node for node in load_targets(db, goal) if str(node.id) not in seen]
    if extras:
        units.append(
            {
                "title": "Components",
                "summary": "",
                "components": [_export_component({}, node, node.description or "") for node in extras],
            }
        )
    return {
        "schema": SCHEMA,
        "course": {
            "title": goal.title,
            "code": goal.code,
            "description": goal.description or "",
            "subject": intake.get("subject") or "",
            "grade_band": goal.audience,
            "kind": goal.kind,
            "estimated_minutes": goal.minutes,
            "outcomes": list(blueprint.get("outcomes") or []),
            "intake": intake,
            "brief": goal.brief or "",
            "standards": statements,
        },
        "units": units,
    }


def _export_component(item: dict, node: KcNode | None, description: str) -> dict:
    standards = list(node.standards or []) if node is not None else list(item.get("standards") or [])
    prerequisites = list(node.prerequisite_codes or []) if node is not None else list(item.get("prerequisites") or item.get("prerequisite_codes") or [])
    return {
        "code": node.code if node is not None else str(item.get("code") or ""),
        "title": node.title if node is not None else str(item.get("title") or ""),
        "description": (node.description if node is not None and node.description else description or ""),
        "summary": str(item.get("summary") or ""),
        "outline": node.outline if node is not None else "",
        "core_truth": node.core_truth if node is not None else "",
        "rubric": list(node.rubric or []) if node is not None else [],
        "misconceptions": list(node.misconceptions or []) if node is not None else [],
        "standards": [str(code) for code in standards if str(code).strip()],
        "prerequisite_codes": [str(code) for code in prerequisites if str(code).strip()],
        "encompasses_codes": [str(code) for code in ((node.encompasses_codes if node is not None else []) or []) if str(code).strip()],
        "blocks": _public_blocks(node),
    }


def external_course_prompt(*, title: str, grade: str, audience: str, curriculum: str, block_notes: str) -> str:
    """A prompt another model can follow to emit KcCourseExportV1 JSON."""
    example = {
        "schema": SCHEMA,
        "course": {
            "title": title or "Course title",
            "code": "",
            "description": "By the end the learner can do one observable thing.",
            "subject": title or "",
            "grade_band": audience if audience in _AUDIENCES else "15-17",
            "kind": "mastery",
            "estimated_minutes": None,
            "outcomes": ["Explain the first idea.", "Use it on a new case."],
            "intake": {},
            "brief": "",
            "standards": [{"code": "s1", "text": "The first topic."}],
        },
        "units": [
            {
                "title": "Unit title",
                "summary": "What this unit is for.",
                "components": [
                    {
                        "code": "topic-1",
                        "title": "Topic title",
                        "description": "Three or four sentences on what the learner can do.",
                        "summary": "One line.",
                        "outline": "",
                        "core_truth": "The one idea.",
                        "rubric": ["Names the idea."],
                        "misconceptions": [{"wrong_move": "A common miss.", "broken_kc": ""}],
                        "standards": ["s1"],
                        "prerequisite_codes": [],
                        "encompasses_codes": [],
                        "blocks": [
                            {"id": "blk_1", "type": "topic_goal", "data": _BLOCK_EXAMPLES["topic_goal"]},
                            {"id": "blk_2", "type": "explanation", "data": _BLOCK_EXAMPLES["explanation"]},
                        ],
                    }
                ],
            }
        ],
    }
    lines = [
        "Write a children's course as JSON. The schema name is KcCourseExportV1.",
        "Use only the block types listed below. Each block is {id, type, data}. Data uses the fields in that type's example.",
        "One teachable idea per component. Order topics so a later one can name earlier codes in prerequisite_codes.",
        "grade_band is one of 6-8, 9-11, 12-14, 15-17. kind is mastery, time_boxed, or curiosity.",
        "standards on a component are codes from course.standards. An empty list means the component is an extension.",
        "If the course has more than 8 units or more than 40 components, do not send the whole course in one reply.",
        "First send the course header as JSON: {\"schema\":\"KcCourseExportV1\",\"course\":{...},\"unit_count\":N} with no units.",
        "Then send one unit per reply as JSON: {\"schema\":\"KcCourseExportV1\",\"unit_index\":1,\"unit\":{title, summary, components}}.",
        "A smaller course is one JSON object with course and units, as in the example.",
        f"Title: {title or 'Use a title that names the subject.'}",
        f"Grade or year: {grade or 'Not specified.'}",
        f"Age band: {audience or '15-17'}",
        "Curriculum, one topic per line. One component per topic, grouped into the curriculum's units:",
        curriculum.strip() or "No curriculum was pasted. Ask for one before you write the course.",
        "Block preferences:",
        block_notes.strip() or "Every component includes a topic_goal, an explanation, a worked_example, and one mcq.",
        *passage_ela_generation_lines(title, grade, curriculum, block_notes),
        "Block types and one example of data for each:",
    ]
    for kind, rule in BLOCK_AUTHORING_RULES.items():
        lines.append(rule)
        lines.append(json.dumps({"type": kind, "data": _BLOCK_EXAMPLES[kind]}, ensure_ascii=False))
    lines.extend(["Example of the full file:", json.dumps(example, ensure_ascii=False)])
    return "\n".join(lines)
