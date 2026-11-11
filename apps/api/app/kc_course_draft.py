"""Database side of the KC Course Creator pipeline.

app/kc_pipeline.py holds the prompts and checkers. This module reads and writes
the course row: the brief, the blueprint, and the draft state. The model call
itself runs in the web app, one stage at a time.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.kc import (
    _nodes_by_code,
    _now,
    _sync_edges,
    clear_course_components,
    load_targets,
    slug_code,
)
from app.kc_model import checked_model
from app.kc_pipeline import (
    apply_review,
    assemble_blueprint,
    blueprint_bundle,
    brief_bundle,
    chat_bundle,
    clean_blueprint_edit,
    clean_brief,
    INTAKE_TEXT_FIELDS,
    clean_intake,
    clean_unit,
    component_range,
    components_of,
    interpret_chat,
    is_matched_curriculum,
    missing_intake,
    pipeline_state,
    review_bundle,
    unit_bundle,
)
from app.kc_standards import (
    clean_statements,
    paste_count,
    read_statements,
    standard_label,
    statements_from_intake,
    syllabus_requested,
    syllabus_statements,
)
from app.models import KcNode
from app.models import KcGoal

STAGES = ("brief", "blueprint", "unit", "review")


def _course(goal: KcGoal) -> dict:
    return {
        "title": goal.title,
        "description": goal.description or "",
        "audience": goal.audience,
        "kind": goal.kind,
        "minutes": goal.minutes,
        "intake": clean_intake(goal.intake),
        "statements": read_statements(goal.standards),
    }


def _drafting(goal: KcGoal) -> dict:
    return dict(goal.drafting) if isinstance(goal.drafting, dict) else {}


def _blueprint(goal: KcGoal) -> dict:
    return goal.blueprint if isinstance(goal.blueprint, dict) else {}


def _fail(status: int, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


def _statement_course(intake: dict, statements: list) -> bool:
    pasted = bool(statements) or bool(syllabus_requested(intake) and (intake.get("standard_text") or intake.get("source_text")))
    return bool(intake.get("standard") or pasted)


def pipeline_out(goal: KcGoal) -> dict:
    intake = clean_intake(goal.intake)
    statements = read_statements(goal.standards)
    state = pipeline_state(
        brief=goal.brief or "",
        blueprint=_blueprint(goal),
        drafting=_drafting(goal),
        standards=statements,
        standard_chosen=_statement_course(intake, statements),
    )
    state["missing"] = missing_intake(
        title=goal.title,
        description=goal.description or "",
        audience=goal.audience,
        intake=intake,
    )
    return state


def _checked(stage: str) -> str:
    if stage not in STAGES:
        raise _fail(404, "That stage does not exist.")
    return stage


def _model(model: str) -> str:
    try:
        return checked_model(model)
    except ValueError as exc:
        raise _fail(422, str(exc)) from exc


def stage_prompt(db: Session, goal: KcGoal, stage: str, model: str, unit: int | None) -> dict:
    """The prompt bundle for one stage. Raises 409 when the stage is not next."""
    del db
    stage = _checked(stage)
    chosen = _model(model)
    course = _course(goal)
    drafting = _drafting(goal)
    blueprint = _blueprint(goal)
    brief = goal.brief or ""
    state = pipeline_out(goal)
    if stage == "brief":
        if state["missing"]:
            raise _fail(422, "Fill in " + ", ".join(state["missing"]) + " before drafting.")
        return brief_bundle(course=course, answers=list(drafting.get("answers") or []), model=chosen)
    if not brief or state["questions"]:
        raise _fail(409, "Write the brief and answer its follow-ups first.")
    if stage == "blueprint":
        if _statement_course(course["intake"], course["statements"]) and not drafting.get("standards_confirmed"):
            raise _fail(409, "Check the standard statements before the blueprint.")
        try:
            return blueprint_bundle(course=course, brief=brief, model=chosen)
        except ValueError as exc:
            raise _fail(422, str(exc)) from exc
    units = blueprint.get("units") or []
    if not units or not drafting.get("approved"):
        raise _fail(409, "Approve the blueprint first.")
    descriptions = dict(drafting.get("units") or {})
    done = int(drafting.get("units_done") or 0)
    if stage == "unit":
        index = done if unit is None else unit
        if index != done or index >= len(units):
            raise _fail(409, f"Unit {done + 1} is the next unit to write.")
        return unit_bundle(
            course=course,
            brief=brief,
            blueprint=blueprint,
            descriptions=descriptions,
            unit_index=index,
            model=chosen,
        )
    if done < len(units):
        raise _fail(409, "Write every unit before the review.")
    return review_bundle(course=course, brief=brief, blueprint=blueprint, descriptions=descriptions, model=chosen)


def store_stage(db: Session, goal: KcGoal, stage: str, result: object, unit: int | None) -> dict:
    """Check one stage result and store it. Raises 422 with a message the model can act on."""
    stage = _checked(stage)
    drafting = _drafting(goal)
    blueprint = _blueprint(goal)
    taken = set(_nodes_by_code(db))
    try:
        if stage == "brief":
            answers = list(drafting.get("answers") or [])
            intake = clean_intake(goal.intake)
            brief, questions = clean_brief(result, answered=bool(answers))
            pasted = statements_from_intake(intake)
            recall = bool(intake["standard"]) and not pasted
            if recall:
                raw_statements = result.get("statements") if isinstance(result, dict) else None
                if not raw_statements:
                    raise ValueError("Recall the statements for this standard and grade. Return at least one.")
                statements = clean_statements(raw_statements)
                source = "recalled"
            elif pasted:
                statements = pasted
                source = "pasted"
            else:
                statements = []
                source = ""
            if intake["standard"]:
                label = standard_label(intake["standard"], intake.get("standard_name") or "")
                note = f"The standard is {label}, {intake['standard_grade']}."
                if note not in brief:
                    brief = f"{brief} {note}"
                if source == "recalled" and "should be checked" not in brief:
                    brief = f"{brief} The statement list is recalled and should be checked."
            goal.brief = brief
            goal.standards = statements
            goal.blueprint = {}
            goal.drafting = {
                "questions": questions,
                "answers": answers,
                "standards_confirmed": not _statement_course(intake, statements),
                "standards_source": source,
            }
        elif stage == "blueprint":
            intake = clean_intake(goal.intake)
            if _statement_course(intake, read_statements(goal.standards)) and not drafting.get("standards_confirmed"):
                raise _fail(409, "Check the standard statements before the blueprint.")
            statements = read_statements(goal.standards)
            bounds = component_range(
                kind=goal.kind,
                minutes=goal.minutes,
                intake=intake,
                statements=statements,
            )
            goal.blueprint = assemble_blueprint(
                result,
                bounds=bounds,
                taken=taken,
                make_code=slug_code,
                statements=statements,
                matched=is_matched_curriculum(intake, statements),
                intake=intake,
            )
            goal.drafting = {
                "questions": [],
                "answers": list(drafting.get("answers") or []),
                "approved": False,
                "standards_confirmed": True,
                "standards_source": drafting.get("standards_source") or "",
            }
        elif stage == "unit":
            units = blueprint.get("units") or []
            done = int(drafting.get("units_done") or 0)
            index = done if unit is None else unit
            if not drafting.get("approved") or index != done or index >= len(units):
                raise _fail(409, f"Unit {done + 1} is the next unit to write.")
            codes = [item["code"] for item in units[index]["components"]]
            written = clean_unit(result, codes)
            drafting["units"] = {**dict(drafting.get("units") or {}), **written}
            drafting["units_done"] = done + 1
            goal.drafting = drafting
        else:
            if int(drafting.get("units_done") or 0) < len(blueprint.get("units") or []):
                raise _fail(409, "Write every unit before the review.")
            statements = read_statements(goal.standards)
            fixed, notes, review = apply_review(
                result,
                blueprint=blueprint,
                descriptions=dict(drafting.get("units") or {}),
                taken=taken,
                make_code=slug_code,
                statements=statements,
                matched=is_matched_curriculum(clean_intake(goal.intake), statements),
            )
            goal.blueprint = fixed
            drafting["units"] = notes
            drafting["review"] = review
            goal.drafting = drafting
    except ValueError as exc:
        raise _fail(422, str(exc)) from exc
    db.flush()
    return pipeline_out(goal)


def save_blueprint(db: Session, goal: KcGoal, raw: object, approve: bool) -> dict:
    """The author's edited blueprint. Descriptions written for the old one are dropped."""
    if not goal.brief:
        raise _fail(409, "Write the brief first.")
    drafting = _drafting(goal)
    intake = clean_intake(goal.intake)
    if _statement_course(intake, read_statements(goal.standards)) and not drafting.get("standards_confirmed"):
        raise _fail(409, "Check the standard statements before the blueprint.")
    previous = {row["code"] for row in components_of(_blueprint(goal))}
    try:
        statements = read_statements(goal.standards)
        edited = clean_blueprint_edit(
            raw,
            taken=set(_nodes_by_code(db)),
            make_code=slug_code,
            statements=statements,
            matched=is_matched_curriculum(intake, statements),
        )
    except ValueError as exc:
        raise _fail(422, str(exc)) from exc
    drafting = _drafting(goal)
    goal.blueprint = edited
    removed = previous - {row["code"] for row in components_of(edited)}
    if removed:
        clear_course_components(db, goal, removed)
    goal.drafting = {
        "questions": [],
        "answers": list(drafting.get("answers") or []),
        "approved": bool(approve),
        "standards_confirmed": True,
        "standards_source": drafting.get("standards_source") or "",
    }
    db.flush()
    return pipeline_out(goal)


def answer_follow_ups(db: Session, goal: KcGoal, answers: list[dict], skip: bool) -> dict:
    drafting = _drafting(goal)
    if skip:
        drafting["questions"] = []
        drafting["answers"] = []
    else:
        kept = [
            {"question": str(item.get("question") or "").strip(), "answer": str(item.get("answer") or "").strip()}
            for item in answers
        ]
        kept = [item for item in kept if item["question"] and item["answer"]]
        if not kept:
            raise _fail(422, "Answer at least one question, or skip them.")
        drafting["answers"] = kept
    goal.drafting = drafting
    db.flush()
    return pipeline_out(goal)


def save_statements(db: Session, goal: KcGoal, raw: object, confirm: bool) -> dict:
    """The author edits the statement list before the blueprint."""
    if not (goal.brief or "").strip():
        raise _fail(409, "Write the brief first.")
    try:
        statements = clean_statements(raw)
    except ValueError as exc:
        raise _fail(422, str(exc)) from exc
    intake = clean_intake(goal.intake)
    if confirm and intake["standard"] and not statements:
        raise _fail(422, "Add the statements this course should cover, or set the standard to None.")
    drafting = _drafting(goal)
    goal.standards = statements
    goal.blueprint = {}
    goal.drafting = {
        "questions": [],
        "answers": list(drafting.get("answers") or []),
        "standards_confirmed": bool(confirm),
        "standards_source": drafting.get("standards_source") or ("pasted" if intake["standard_text"] else "recalled"),
    }
    db.flush()
    return pipeline_out(goal)


def reset_pipeline(db: Session, goal: KcGoal, *, clear_components: bool = False) -> dict:
    goal.brief = ""
    goal.blueprint = {}
    goal.drafting = {}
    goal.standards = statements_from_intake(clean_intake(goal.intake))
    if clear_components:
        clear_course_components(db, goal)
    db.flush()
    return pipeline_out(goal)


def delete_unit(db: Session, goal: KcGoal, unit_index: int) -> dict:
    """Remove one blueprint unit and the pushed components that belong to it."""
    blueprint = _blueprint(goal)
    units = [dict(unit) for unit in (blueprint.get("units") or [])]
    if unit_index < 0 or unit_index >= len(units):
        raise _fail(404, "That unit is not on the course.")
    if len(units) < 2:
        raise _fail(422, "A course keeps at least one unit. Start over to clear the course.")
    removed = units.pop(unit_index)
    dropped = {str(item.get("code") or "") for item in (removed.get("components") or []) if item.get("code")}
    for unit in units:
        components = []
        for item in unit.get("components") or []:
            row = dict(item)
            row["prerequisites"] = [code for code in (row.get("prerequisites") or []) if code not in dropped]
            components.append(row)
        unit["components"] = components
    goal.blueprint = {**blueprint, "units": units}
    drafting = _drafting(goal)
    notes = dict(drafting.get("units") or {})
    for code in dropped:
        notes.pop(code, None)
    done = 0
    for unit in units:
        codes = [item.get("code") for item in unit.get("components") or []]
        if codes and all(notes.get(code) for code in codes):
            done += 1
            continue
        break
    drafting["units"] = notes
    drafting["units_done"] = done
    if done < len(units):
        drafting.pop("review", None)
    goal.drafting = drafting
    if dropped:
        clear_course_components(db, goal, dropped)
    db.flush()
    return pipeline_out(goal)


def _chat_brief(goal: KcGoal, blueprint: dict) -> str:
    count = len(components_of(blueprint))
    ending = goal.description or "use the ideas in the blueprint"
    return (
        f"This course is {goal.title} for ages {goal.audience}. "
        f"By the end the child can {ending}. "
        f"The blueprint has {count} components. "
        "The author is editing the course in chat."
    )


def _sync_chat_components(db: Session, goal: KcGoal, blueprint: dict, descriptions: dict[str, str], changed: set[str]) -> None:
    """Create nodes for new components and update only the components the chat changed."""
    by_code = {node.code: node for node in load_targets(db, goal)}
    ordered: list[str] = []
    seen: set[str] = set()
    for row in components_of(blueprint):
        code = row["code"]
        node = by_code.get(code)
        if node is None:
            node = KcNode(
                code=code,
                title=row["title"],
                description=descriptions.get(code, ""),
                standards=list(row.get("standards") or []),
                prerequisite_codes=list(row.get("prerequisites") or []),
            )
            db.add(node)
            db.flush()
            by_code[code] = node
            _sync_edges(db, node)
        elif code in changed:
            node.title = row["title"]
            if descriptions.get(code):
                node.description = descriptions[code]
            node.standards = list(row.get("standards") or [])
            node.prerequisite_codes = list(row.get("prerequisites") or [])
            node.updated_at = _now()
            _sync_edges(db, node)
        seen.add(code)
        if str(node.id) not in ordered:
            ordered.append(str(node.id))
    removed = {code for code in by_code if code not in seen}
    if removed:
        clear_course_components(db, goal, removed)
    extras = [item for item in (goal.target_kc_ids or []) if item not in ordered]
    goal.target_kc_ids = [*ordered, *extras]
    goal.updated_at = _now()


def course_chat_prompt(db: Session, goal: KcGoal, model: str, messages: list[dict]) -> dict:
    """The prompt for one chat turn.

    A syllabus pasted in the chat is saved as source text when the course has
    none, so the reply can make one component per pasted topic.
    """
    chosen = _model(model)
    paste_limit = INTAKE_TEXT_FIELDS["source_text"]
    cleaned: list[dict] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        role = "user" if item.get("role") == "user" else "assistant"
        cleaned.append({"role": role, "content": content[:paste_limit]})
    if not any(item["role"] == "user" for item in cleaned):
        raise _fail(422, "Say what you want to change.")
    intake = clean_intake(goal.intake)
    if not str(intake.get("source_text") or "").strip():
        pasted = ""
        best = 0
        for item in cleaned:
            if item["role"] != "user":
                continue
            count = paste_count(item["content"], syllabus=True)
            if count >= 2 and count >= best:
                pasted = item["content"]
                best = count
        if pasted:
            intake = clean_intake({**intake, "source_text": pasted})
            goal.intake = intake
            statements = statements_from_intake(intake) or syllabus_statements(intake.get("source_text") or "")
            if statements:
                goal.standards = statements
            goal.updated_at = _now()
            db.flush()
    drafting = _drafting(goal)
    return chat_bundle(
        course=_course(goal),
        brief=goal.brief or "",
        blueprint=_blueprint(goal),
        descriptions=dict(drafting.get("units") or {}),
        statements=read_statements(goal.standards),
        components=[{"code": node.code, "title": node.title} for node in load_targets(db, goal)],
        messages=cleaned,
        model=chosen,
    )


def preview_chat(db: Session, goal: KcGoal, result: object) -> dict:
    """Describe a chat proposal without writing it."""
    drafting = _drafting(goal)
    try:
        statements = read_statements(goal.standards)
        proposal = interpret_chat(
            result,
            blueprint=_blueprint(goal),
            descriptions=dict(drafting.get("units") or {}),
            statements=statements,
            taken=set(_nodes_by_code(db)),
            make_code=slug_code,
            matched=is_matched_curriculum(clean_intake(goal.intake), statements),
        )
    except ValueError as exc:
        raise _fail(422, str(exc)) from exc
    return {
        "reply": proposal["reply"],
        "changes": proposal["changes"],
        "changed_codes": proposal["changed_codes"],
        "blueprint": proposal["blueprint"],
    }


def apply_chat(db: Session, goal: KcGoal, result: object) -> dict:
    """Store a chat proposal. Components the proposal did not change keep their descriptions."""
    drafting = _drafting(goal)
    try:
        statements = read_statements(goal.standards)
        proposal = interpret_chat(
            result,
            blueprint=_blueprint(goal),
            descriptions=dict(drafting.get("units") or {}),
            statements=statements,
            taken=set(_nodes_by_code(db)),
            make_code=slug_code,
            matched=is_matched_curriculum(clean_intake(goal.intake), statements),
        )
    except ValueError as exc:
        raise _fail(422, str(exc)) from exc
    goal.blueprint = proposal["blueprint"]
    if not (goal.brief or "").strip():
        goal.brief = _chat_brief(goal, proposal["blueprint"])
    notes = dict(proposal["descriptions"])
    units = proposal["blueprint"]["units"]
    done = 0
    for unit in units:
        codes = [item["code"] for item in unit["components"]]
        if codes and all(notes.get(code) for code in codes):
            done += 1
            continue
        break
    review = drafting.get("review") if done == len(units) else None
    goal.drafting = {
        "questions": [],
        "answers": list(drafting.get("answers") or []),
        "approved": True,
        "standards_confirmed": True,
        "standards_source": drafting.get("standards_source") or "",
        "units": notes,
        "units_done": done,
        "review": review,
        "pushed": True,
    }
    _sync_chat_components(db, goal, proposal["blueprint"], notes, set(proposal["changed_codes"]))
    db.flush()
    return {"pipeline": pipeline_out(goal), "reply": proposal["reply"], "changes": proposal["changes"]}
