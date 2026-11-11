"""Database side of the KC Course Creator pipeline.

app/kc_pipeline.py holds the prompts and checkers. This module reads and writes
the course row: the brief, the blueprint, and the draft state. The model call
itself runs in the web app, one stage at a time.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.kc import _nodes_by_code, slug_code
from app.kc_model import checked_model
from app.kc_pipeline import (
    apply_review,
    assemble_blueprint,
    blueprint_bundle,
    brief_bundle,
    clean_blueprint_edit,
    clean_brief,
    clean_intake,
    clean_unit,
    component_range,
    missing_intake,
    pipeline_state,
    review_bundle,
    unit_bundle,
)
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
    }


def _drafting(goal: KcGoal) -> dict:
    return dict(goal.drafting) if isinstance(goal.drafting, dict) else {}


def _blueprint(goal: KcGoal) -> dict:
    return goal.blueprint if isinstance(goal.blueprint, dict) else {}


def _fail(status: int, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


def pipeline_out(goal: KcGoal) -> dict:
    state = pipeline_state(brief=goal.brief or "", blueprint=_blueprint(goal), drafting=_drafting(goal))
    state["missing"] = missing_intake(
        title=goal.title,
        description=goal.description or "",
        audience=goal.audience,
        intake=clean_intake(goal.intake),
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
        return blueprint_bundle(course=course, brief=brief, model=chosen)
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
            brief, questions = clean_brief(result, answered=bool(answers))
            goal.brief = brief
            goal.blueprint = {}
            goal.drafting = {"questions": questions, "answers": answers}
        elif stage == "blueprint":
            bounds = component_range(kind=goal.kind, minutes=goal.minutes, intake=clean_intake(goal.intake))
            goal.blueprint = assemble_blueprint(result, bounds=bounds, taken=taken, make_code=slug_code)
            goal.drafting = {"questions": [], "answers": list(drafting.get("answers") or []), "approved": False}
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
            fixed, notes, review = apply_review(
                result,
                blueprint=blueprint,
                descriptions=dict(drafting.get("units") or {}),
                taken=taken,
                make_code=slug_code,
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
    try:
        edited = clean_blueprint_edit(raw, taken=set(_nodes_by_code(db)), make_code=slug_code)
    except ValueError as exc:
        raise _fail(422, str(exc)) from exc
    drafting = _drafting(goal)
    goal.blueprint = edited
    goal.drafting = {
        "questions": [],
        "answers": list(drafting.get("answers") or []),
        "approved": bool(approve),
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


def reset_pipeline(db: Session, goal: KcGoal) -> dict:
    goal.brief = ""
    goal.blueprint = {}
    goal.drafting = {}
    db.flush()
    return pipeline_out(goal)
