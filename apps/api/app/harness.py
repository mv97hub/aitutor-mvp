"""AI test children: personas, runs, chats, reviews, and recommendations.

The live tutor routes are not called from here. The browser runner calls them.
This module stores the plan, the child's intent, and the reviews.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai_safety import read_ai_safety
from app.flow import unique_student_slug
from app.harness_checks import (
    DEFAULT_CHAT_CAP_CENTS,
    DEFAULT_LUNA_TOKEN_CEILING,
    DEFAULT_STUCK_LIMIT,
    DEFAULT_TURN_LIMIT,
    WRONG_INTENTS,
    automatic_checks,
    stop_reason,
    stuck_after_turn,
)
from app.harness_personas import TRAIT_KEYS, starter_children
from app.harness_report import (
    block_label,
    compare_runs,
    findings,
    kept_run_ids,
    regression_band,
    rollup,
    stuck_nudge_rows,
)
from app.kc import course_out, load_targets, mark_ready, open_session
from app.kc import _block_context
from app.kc_course_io import SCHEMA, _BLOCK_EXAMPLES, import_new_course
from app.models import (
    TUTOR_MODELS,
    AiSafetyEvent,
    HarnessChat,
    HarnessEvaluation,
    HarnessPersona,
    HarnessRecommendation,
    HarnessRun,
    HarnessSuite,
    HarnessTurn,
    KcGoal,
    KcModelPrompt,
    KcNode,
    KcSession,
    KcState,
    Student,
    TutorProfile,
    normalize_child_profile,
)
from app.token_usage import _model_cost, session_token_usage
from app.tutor_profile import create_tutor_profile, effective_kc_tutor_config, get_profile_by_id_or_slug, load_profile

HARNESS_CODE_VERSION = "harness-1"
FIXTURE_CODE = "harness-every-block"
LUNA_MODEL = "gpt-6-luna"
_EXPECTED_FIELDS = (
    "goal",
    "acceptance_criteria",
    "solo_expected_answer",
    "expected_fact",
    "expected_why_rationale",
    "invariant_principle",
    "target_synthesis",
    "corrected_version",
    "expected_central_idea",
    "expected_analysis",
    "summary_takeaway",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return list(value) if isinstance(value, list) else []


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def persona_out(row: HarnessPersona) -> dict:
    return {
        "id": row.id,
        "number": row.number,
        "name": row.name,
        "description": row.description,
        "age": row.age,
        "child_profile": dict(row.child_profile or {}),
        "traits": dict(row.traits or {}),
        "archived": bool(row.archived),
        "created_at": row.created_at,
    }


def list_personas(db: Session, *, include_archived: bool = False) -> list[dict]:
    stmt = select(HarnessPersona).order_by(HarnessPersona.number)
    if not include_archived:
        stmt = stmt.where(HarnessPersona.archived.is_(False))
    return [persona_out(row) for row in db.scalars(stmt).all()]


def _next_number(db: Session) -> int:
    current = db.scalar(select(func.max(HarnessPersona.number)))
    return int(current or 0) + 1


def _clean_traits(raw: dict | None) -> dict:
    source = raw if isinstance(raw, dict) else {}
    cleaned = {key: 3 for key in TRAIT_KEYS}
    for key in TRAIT_KEYS:
        if key not in source:
            continue
        try:
            cleaned[key] = max(1, min(5, int(source[key])))
        except (TypeError, ValueError):
            continue
    return cleaned


def create_persona(db: Session, body: dict) -> dict:
    number = _next_number(db)
    age = int(body.get("age") or 10)
    if age < 4 or age > 18:
        raise HTTPException(status_code=422, detail="Age must be from 4 to 18.")
    description = str(body.get("description") or "").strip()[:240]
    profile = normalize_child_profile(body.get("child_profile") if isinstance(body.get("child_profile"), dict) else {}, age=age)
    row = HarnessPersona(
        number=number,
        name=f"AI_Child{number}",
        description=description,
        age=age,
        child_profile=profile,
        traits=_clean_traits(body.get("traits") if isinstance(body.get("traits"), dict) else None),
        archived=False,
    )
    db.add(row)
    db.flush()
    return persona_out(row)


def update_persona(db: Session, persona_id: uuid.UUID, body: dict) -> dict:
    row = db.get(HarnessPersona, persona_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That test child was not found.")
    if "description" in body:
        row.description = str(body.get("description") or "").strip()[:240]
    if "age" in body and body.get("age") is not None:
        age = int(body["age"])
        if age < 4 or age > 18:
            raise HTTPException(status_code=422, detail="Age must be from 4 to 18.")
        row.age = age
    if isinstance(body.get("child_profile"), dict):
        row.child_profile = normalize_child_profile(body["child_profile"], age=row.age)
    if isinstance(body.get("traits"), dict):
        row.traits = _clean_traits(body["traits"])
    if "archived" in body:
        row.archived = bool(body["archived"])
    db.flush()
    return persona_out(row)


def add_starter_set(db: Session) -> list[dict]:
    """Create any starter number that is not already stored. Existing rows are left as they are."""
    taken = set(db.scalars(select(HarnessPersona.number)).all())
    for item in starter_children():
        if item["number"] in taken:
            continue
        db.add(
            HarnessPersona(
                number=item["number"],
                name=item["name"],
                description=item["description"],
                age=item["age"],
                child_profile=normalize_child_profile(item["child_profile"], age=item["age"]),
                traits=item["traits"],
                archived=False,
            )
        )
    db.flush()
    return list_personas(db, include_archived=True)


def _models(raw: object, *, label: str) -> list[str]:
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = [str(item).strip() for item in raw]
    else:
        values = []
    cleaned = []
    for item in values:
        if item and item not in cleaned:
            if item not in TUTOR_MODELS:
                raise HTTPException(status_code=422, detail=f"{label} must be one of the tutor models.")
            cleaned.append(item)
    return cleaned


def _one_model(raw: object, *, default: str, label: str) -> str:
    chosen = str(raw or "").strip() or default
    if chosen not in TUTOR_MODELS:
        raise HTTPException(status_code=422, detail=f"{label} must be one of the tutor models.")
    return chosen


def normalize_plan(raw: dict) -> dict:
    behavior = str(raw.get("behavior") or "rule").strip()
    if behavior not in {"rule", "free", "script"}:
        raise HTTPException(status_code=422, detail="Child behavior is rule, free, or script.")
    iterations = int(raw.get("iterations") or 3)
    if iterations < 1 or iterations > 50:
        raise HTTPException(status_code=422, detail="Iterations must be from 1 to 50.")
    cap = raw.get("chat_cap_cents", DEFAULT_CHAT_CAP_CENTS)
    chat_cap = int(cap if cap is not None else DEFAULT_CHAT_CAP_CENTS)
    if chat_cap < 1:
        raise HTTPException(status_code=422, detail="The spending cap per chat must be at least 1 cent.")
    run_cap = raw.get("run_cap_cents")
    run_cap_cents = None if run_cap in (None, "", 0, "0") else int(run_cap)
    if run_cap_cents is not None and run_cap_cents < 1:
        raise HTTPException(status_code=422, detail="The run cap must be blank or at least 1 cent.")
    concurrency = int(raw.get("concurrency") or 3)
    if concurrency < 1 or concurrency > 8:
        raise HTTPException(status_code=422, detail="Concurrency must be from 1 to 8.")
    script = raw.get("script") if isinstance(raw.get("script"), list) else []
    return {
        "persona_ids": [str(item) for item in raw.get("persona_ids") or []],
        "course_ids": [str(item) for item in raw.get("course_ids") or []],
        "component_ids": [str(item) for item in raw.get("component_ids") or []],
        "tutor_models": _models(raw.get("tutor_models") or raw.get("tutor_model"), label="Tutor model"),
        "child_model": _one_model(raw.get("child_model"), default="gpt-4.1-mini", label="Child model"),
        "judge_model": _one_model(raw.get("judge_model"), default="gpt-6.1-sol", label="Judge model"),
        "behavior": behavior,
        "tutor_profile_ids": [str(item) for item in raw.get("tutor_profile_ids") or [] if str(item).strip()],
        "iterations": iterations,
        "chat_cap_cents": chat_cap,
        "run_cap_cents": run_cap_cents,
        "turn_limit": int(raw.get("turn_limit") or DEFAULT_TURN_LIMIT),
        "stuck_limit": int(raw.get("stuck_limit") or DEFAULT_STUCK_LIMIT),
        "stop_on_safety": bool(raw.get("stop_on_safety")),
        "concurrency": concurrency,
        "luna_token_ceiling": int(raw.get("luna_token_ceiling") or DEFAULT_LUNA_TOKEN_CEILING),
        "script": [str(line).strip() for line in script if str(line).strip()][:80],
        "seed": int(raw.get("seed") or 0),
    }


def _goal_for_node(db: Session, node_id: uuid.UUID) -> KcGoal | None:
    wanted = str(node_id)
    for goal in db.scalars(select(KcGoal)).all():
        ids = {str(item) for item in (goal.target_kc_ids or [])}
        if wanted in ids:
            return goal
    return None


def _components(db: Session, plan: dict) -> list[tuple[KcGoal, KcNode]]:
    chosen = [item for item in (_uuid(value) for value in plan["component_ids"]) if item is not None]
    pairs: list[tuple[KcGoal, KcNode]] = []
    if chosen:
        for node_id in chosen:
            node = db.get(KcNode, node_id)
            if node is None:
                raise HTTPException(status_code=422, detail="One of those components was not found.")
            goal = _goal_for_node(db, node.id)
            if goal is None or not goal.ready:
                raise HTTPException(status_code=422, detail="Each component must be on a ready course.")
            pairs.append((goal, node))
        return pairs
    course_ids = [_uuid(item) for item in plan["course_ids"]]
    if not course_ids or any(item is None for item in course_ids):
        raise HTTPException(status_code=422, detail="Choose a course or a component.")
    for course_id in course_ids:
        goal = db.get(KcGoal, course_id)
        if goal is None or not goal.ready:
            raise HTTPException(status_code=422, detail="Choose a ready course.")
        for node in load_targets(db, goal):
            pairs.append((goal, node))
    if not pairs:
        raise HTTPException(status_code=422, detail="That course has no components.")
    return pairs


def _profiles(db: Session, plan: dict) -> list[TutorProfile]:
    if not plan["tutor_profile_ids"]:
        return [load_profile(db)]
    rows = []
    for item in plan["tutor_profile_ids"]:
        profile = get_profile_by_id_or_slug(db, item)
        if profile is None:
            raise HTTPException(status_code=422, detail="One of those tutor profiles was not found.")
        rows.append(profile)
    return rows


def matrix_slots(plan: dict, *, children: int, components: int, profiles: int) -> int:
    models = max(1, len(plan["tutor_models"]))
    return children * components * models * profiles * int(plan["iterations"])


def _persona_rows(db: Session, plan: dict) -> list[HarnessPersona]:
    ids = [_uuid(item) for item in plan["persona_ids"]]
    if not ids or any(item is None for item in ids):
        raise HTTPException(status_code=422, detail="Choose at least one test child.")
    rows = db.scalars(select(HarnessPersona).where(HarnessPersona.id.in_(ids))).all()
    by_id = {row.id: row for row in rows}
    ordered = []
    for item in ids:
        row = by_id.get(item)
        if row is None or row.archived:
            raise HTTPException(status_code=422, detail="Choose a test child that is not archived.")
        ordered.append(row)
    return ordered


def plan_preview(db: Session, raw: dict) -> dict:
    plan = normalize_plan(raw)
    if not plan["tutor_models"]:
        raise HTTPException(status_code=422, detail="Choose a tutor model.")
    children = _persona_rows(db, plan)
    components = _components(db, plan)
    profiles = _profiles(db, plan)
    chats = matrix_slots(plan, children=len(children), components=len(components), profiles=len(profiles))
    same = plan["child_model"] in plan["tutor_models"]
    uses_luna = LUNA_MODEL in plan["tutor_models"] or plan["child_model"] == LUNA_MODEL or plan["judge_model"] == LUNA_MODEL
    boundary = any(int((row.traits or {}).get("boundary") or 0) >= 4 or row.name == "AI_Child12" for row in children)
    return {
        "chats": chats,
        "children": len(children),
        "components": len(components),
        "tutor_models": plan["tutor_models"],
        "profiles": len(profiles),
        "iterations": plan["iterations"],
        "same_model": same,
        "uses_luna": uses_luna,
        "luna_priced": False,
        "chat_cap_cents": plan["chat_cap_cents"],
        "run_cap_cents": plan["run_cap_cents"],
        "luna_token_ceiling": plan["luna_token_ceiling"],
        "boundary_tester": boundary,
        "estimate_note": (
            "The dollar estimate uses the published price table. "
            "gpt-6-luna has no published price, so its calls are blank and stop at the token ceiling."
        ),
    }


def _snapshot(row: HarnessPersona) -> dict:
    return {
        "id": str(row.id),
        "number": row.number,
        "name": row.name,
        "description": row.description,
        "age": row.age,
        "child_profile": dict(row.child_profile or {}),
        "traits": dict(row.traits or {}),
    }


def create_run(db: Session, raw: dict, *, suite_id: uuid.UUID | None = None, seeds: list[int] | None = None) -> dict:
    plan = normalize_plan(raw)
    if not plan["tutor_models"]:
        raise HTTPException(status_code=422, detail="Choose a tutor model.")
    children = _persona_rows(db, plan)
    components = _components(db, plan)
    profiles = _profiles(db, plan)
    if plan["seed"] <= 0:
        plan["seed"] = int(uuid.uuid4().int % 2_000_000_000) or 1
    run = HarnessRun(
        status="queued",
        plan=plan,
        totals={"chats": 0, "priced_cents": 0, "luna_tokens": 0},
        code_version=HARNESS_CODE_VERSION,
        suite_id=suite_id,
    )
    db.add(run)
    db.flush()
    index = 0
    for child in children:
        for goal, node in components:
            for model in plan["tutor_models"]:
                for profile in profiles:
                    for iteration in range(1, plan["iterations"] + 1):
                        seed = seeds[index] if seeds and index < len(seeds) else (plan["seed"] + index * 997) % 2_000_000_000
                        index += 1
                        db.add(
                            HarnessChat(
                                run_id=run.id,
                                status="queued",
                                persona_id=child.id,
                                child_snapshot=_snapshot(child),
                                course_id=goal.id,
                                component_id=node.id,
                                tutor_model=model,
                                child_model=plan["child_model"],
                                judge_model=plan["judge_model"],
                                tutor_profile_id=profile.id,
                                settings_copy={},
                                seed=int(seed),
                                iteration=iteration,
                                behavior=plan["behavior"],
                                script=list(plan["script"]),
                                tokens={"input": 0, "output": 0},
                                luna_tokens=0,
                                turn_count=0,
                            )
                        )
    db.flush()
    _refresh_totals(db, run)
    return run_out(db, run)


def run_out(db: Session, run: HarnessRun) -> dict:
    chats = db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id).order_by(HarnessChat.created_at)).all()
    done = sum(1 for chat in chats if chat.status in {"completed", "cancelled", "failed"})
    return {
        "id": run.id,
        "status": run.status,
        "plan": _as_dict(run.plan),
        "totals": _as_dict(run.totals),
        "code_version": run.code_version,
        "suite_id": run.suite_id,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "chats": len(chats),
        "finished": done,
        "chat_rows": [chat_out(chat) for chat in chats],
    }


def chat_out(chat: HarnessChat) -> dict:
    return {
        "id": chat.id,
        "run_id": chat.run_id,
        "status": chat.status,
        "persona_id": chat.persona_id,
        "child": _as_dict(chat.child_snapshot),
        "student_id": chat.student_id,
        "session_id": chat.session_id,
        "course_id": chat.course_id,
        "component_id": chat.component_id,
        "tutor_model": chat.tutor_model,
        "child_model": chat.child_model,
        "judge_model": chat.judge_model,
        "tutor_profile_id": chat.tutor_profile_id,
        "seed": chat.seed,
        "iteration": chat.iteration,
        "behavior": chat.behavior,
        "script": _as_list(chat.script),
        "ended_how": chat.ended_how,
        "tokens": _as_dict(chat.tokens),
        "cost_usd": chat.cost_usd,
        "luna_tokens": chat.luna_tokens,
        "turn_count": chat.turn_count,
        "pending_nudges": int(chat.pending_nudges or 0),
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
    }


def list_runs(db: Session) -> list[dict]:
    runs = db.scalars(select(HarnessRun).order_by(HarnessRun.created_at.desc())).all()
    rows = []
    for run in runs:
        body = run_out(db, run)
        body.pop("chat_rows", None)
        rows.append(body)
    return rows


def get_run(db: Session, run_id: uuid.UUID) -> dict:
    run = db.get(HarnessRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="That run was not found.")
    return run_out(db, run)


def _run_or_404(db: Session, run_id: uuid.UUID) -> HarnessRun:
    run = db.get(HarnessRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="That run was not found.")
    return run


def pause_run(db: Session, run_id: uuid.UUID) -> dict:
    run = _run_or_404(db, run_id)
    if run.status == "running":
        run.status = "paused"
        run.updated_at = _now()
    return run_out(db, run)


def resume_run(db: Session, run_id: uuid.UUID) -> dict:
    run = _run_or_404(db, run_id)
    if run.status in {"paused", "queued"}:
        run.status = "running"
        run.updated_at = _now()
        running = db.scalars(
            select(HarnessChat).where(HarnessChat.run_id == run.id, HarnessChat.status == "running")
        ).all()
        for chat in running:
            chat.status = "queued"
            chat.updated_at = _now()
    return run_out(db, run)


def cancel_run(db: Session, run_id: uuid.UUID) -> dict:
    run = _run_or_404(db, run_id)
    run.status = "cancelled"
    run.updated_at = _now()
    chats = db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id)).all()
    for chat in chats:
        if chat.status in {"queued", "running", "paused"}:
            chat.status = "cancelled"
            chat.ended_how = chat.ended_how or "cancelled"
            chat.updated_at = _now()
            _close_session(db, chat)
    return run_out(db, run)


def delete_run(db: Session, run_id: uuid.UUID) -> dict:
    run = _run_or_404(db, run_id)
    chats = db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id)).all()
    student_ids = [chat.student_id for chat in chats if chat.student_id is not None]
    session_ids = [chat.session_id for chat in chats if chat.session_id is not None]
    db.execute(delete(HarnessRecommendation).where(HarnessRecommendation.run_id == run.id))
    db.delete(run)
    db.flush()
    if session_ids:
        db.execute(delete(KcSession).where(KcSession.id.in_(session_ids)))
    if student_ids:
        db.execute(delete(KcState).where(KcState.student_id.in_(student_ids)))
        db.execute(delete(Student).where(Student.id.in_(student_ids), Student.is_test.is_(True)))
    db.flush()
    return {"deleted": str(run_id)}


def run_again(db: Session, run_id: uuid.UUID) -> dict:
    run = _run_or_404(db, run_id)
    chats = db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id).order_by(HarnessChat.created_at)).all()
    plan = dict(run.plan or {})
    plan["seed"] = int(plan.get("seed") or 1)
    created = create_run(db, plan, suite_id=run.suite_id, seeds=[chat.seed for chat in chats])
    return created


def _settings_copy(db: Session, profile: TutorProfile, node: KcNode) -> dict:
    return {
        "kc_tutor_config": effective_kc_tutor_config(profile),
        "ai_safety": read_ai_safety(db),
        "blocks": node.blocks if isinstance(node.blocks, list) else [],
        "profile_id": profile.id,
        "profile_name": profile.name,
        "code_version": HARNESS_CODE_VERSION,
    }


def claim_chat(db: Session, run_id: uuid.UUID) -> dict | None:
    run = _run_or_404(db, run_id)
    if run.status in {"paused", "cancelled", "completed"}:
        return None
    if run.status == "queued":
        run.status = "running"
    plan = dict(run.plan or {})
    run_cap = plan.get("run_cap_cents")
    totals = dict(run.totals or {})
    if run_cap and int(totals.get("priced_cents") or 0) >= int(run_cap):
        for chat in db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id, HarnessChat.status == "queued")).all():
            chat.status = "cancelled"
            chat.ended_how = "run_cap"
            chat.updated_at = _now()
        run.status = "completed"
        run.updated_at = _now()
        return None
    chat = db.scalar(
        select(HarnessChat)
        .where(HarnessChat.run_id == run.id, HarnessChat.status == "queued")
        .order_by(HarnessChat.created_at)
        .with_for_update(skip_locked=True)
    )
    if chat is None:
        open_count = db.scalar(
            select(func.count()).select_from(HarnessChat).where(
                HarnessChat.run_id == run.id, HarnessChat.status.in_(("queued", "running"))
            )
        )
        if not open_count:
            run.status = "completed"
            run.updated_at = _now()
        return None
    goal = db.get(KcGoal, chat.course_id)
    node = db.get(KcNode, chat.component_id)
    profile = get_profile_by_id_or_slug(db, chat.tutor_profile_id) if chat.tutor_profile_id else load_profile(db)
    if goal is None or node is None or profile is None:
        chat.status = "failed"
        chat.ended_how = "route_error"
        chat.updated_at = _now()
        db.flush()
        return claim_chat(db, run_id)
    snapshot = _as_dict(chat.child_snapshot)
    profile_body = normalize_child_profile(snapshot.get("child_profile"), age=int(snapshot.get("age") or 10))
    base_slug = unique_student_slug(db, str(snapshot.get("name") or "ai-child"))
    student = Student(
        slug=f"{base_slug[:48]}-{uuid.uuid4().hex[:8]}"[:80],
        display_name=str(snapshot.get("name") or "AI child"),
        age=int(snapshot.get("age") or 10),
        reading_level=str(profile_body.get("reading_level") or ""),
        modality=str(profile_body.get("explanation_style") or ""),
        interests=[part.strip() for part in str(profile_body.get("interests") or "").split(",") if part.strip()],
        child_profile=profile_body,
        is_test=True,
    )
    db.add(student)
    db.flush()
    session = open_session(db, student, goal, node, tutor_profile_id=profile.id)
    chat.student_id = student.id
    chat.session_id = session.id
    chat.settings_copy = _settings_copy(db, profile, node)
    chat.status = "running"
    chat.updated_at = _now()
    run.updated_at = _now()
    db.flush()
    body = chat_out(chat)
    body["session"] = {"id": str(session.id), "status": session.status}
    return body


def _expected(data: dict) -> str:
    for key in _EXPECTED_FIELDS:
        text = str(data.get(key) or "").strip()
        if text:
            return text
    return ""


def answer_key(db: Session, chat_id: uuid.UUID) -> dict:
    chat = db.get(HarnessChat, chat_id)
    if chat is None or chat.session_id is None:
        raise HTTPException(status_code=404, detail="That chat has no session yet.")
    session = db.get(KcSession, chat.session_id)
    node = db.get(KcNode, session.kc_id) if session is not None else None
    if session is None or node is None:
        raise HTTPException(status_code=404, detail="That session was not found.")
    _profile, _goal, _messages, _fragment, _cfg, _blocks, index, block, state = _block_context(db, session, node)
    data = block.get("data") if isinstance(block, dict) and isinstance(block.get("data"), dict) else {}
    choices = []
    correct = ""
    for choice in data.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        choices.append(
            {
                "id": str(choice.get("id") or ""),
                "text": str(choice.get("text") or ""),
                "correct": bool(choice.get("is_correct")),
            }
        )
        if choice.get("is_correct") and not correct:
            correct = str(choice.get("id") or "")
    misconceptions = node.misconceptions if isinstance(node.misconceptions, list) else []
    traits = (chat.child_snapshot or {}).get("traits") or {}
    probes = []
    if int(traits.get("boundary") or 0) >= 4 or (chat.child_snapshot or {}).get("name") == "AI_Child12":
        from app.harness_personas import BOUNDARY_PROBES

        probes = list(BOUNDARY_PROBES)
    return {
        "block_index": index,
        "block_id": str(block.get("id") or "") if isinstance(block, dict) else "",
        "block_type": str(block.get("type") or "") if isinstance(block, dict) else "",
        "substep": str(state.get("substep") or ""),
        "expected": _expected(data),
        "correct_choice_id": correct,
        "choices": choices,
        "misconceptions": misconceptions,
        "probes": probes,
        "move_attempts": int(session.move_attempts or 0),
    }


def _cents(amount: str | None) -> int:
    if not amount:
        return 0
    try:
        return int((Decimal(amount) * 100).to_integral_value())
    except Exception:
        return 0


def _add_money(left: str | None, right: str | None) -> str | None:
    if left is None and right is None:
        return None
    total = Decimal(left or "0") + Decimal(right or "0")
    text = format(total, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _chat_priced_cost(db: Session, chat: HarnessChat) -> tuple[str | None, int]:
    priced: str | None = None
    luna = 0
    if chat.session_id is not None:
        usage = session_token_usage(db, chat.session_id)
        for turn in usage.get("turns") or []:
            model = str(turn.get("model") or "")
            incoming = int(turn.get("input_tokens") or 0)
            cached = min(int(turn.get("cached_tokens") or 0), incoming)
            outgoing = int(turn.get("output_tokens") or 0)
            if model == LUNA_MODEL:
                luna += incoming + outgoing
                continue
            part = _model_cost(model, incoming - cached, cached, outgoing)
            if part is None:
                continue
            priced = _add_money(priced, part)
    for turn in db.scalars(select(HarnessTurn).where(HarnessTurn.chat_id == chat.id)).all():
        tokens = turn.child_tokens if isinstance(turn.child_tokens, dict) else {}
        model = str(tokens.get("model") or chat.child_model or "")
        incoming = int(tokens.get("input_tokens") or tokens.get("input") or 0)
        outgoing = int(tokens.get("output_tokens") or tokens.get("output") or 0)
        if model == LUNA_MODEL:
            luna += incoming + outgoing
            continue
        part = _model_cost(model, incoming, 0, outgoing)
        if part is not None:
            priced = _add_money(priced, part)
    for review in db.scalars(
        select(HarnessEvaluation).where(HarnessEvaluation.chat_id == chat.id, HarnessEvaluation.kind == "judged")
    ).all():
        scores = review.scores if isinstance(review.scores, dict) else {}
        usage = scores.get("usage") if isinstance(scores, dict) else None
        if not isinstance(usage, dict):
            continue
        model = str(review.judge_model or "")
        incoming = int(usage.get("input_tokens") or 0)
        outgoing = int(usage.get("output_tokens") or 0)
        if model == LUNA_MODEL:
            luna += incoming + outgoing
            continue
        part = _model_cost(model, incoming, 0, outgoing)
        if part is not None:
            priced = _add_money(priced, part)
    if priced is None and luna:
        return None, luna
    return priced or "0", luna


def _refresh_chat_cost(db: Session, chat: HarnessChat) -> None:
    priced, luna = _chat_priced_cost(db, chat)
    chat.cost_usd = priced
    chat.luna_tokens = luna


def _refresh_totals(db: Session, run: HarnessRun) -> None:
    chats = db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id)).all()
    cents = 0
    luna = 0
    for chat in chats:
        cents += _cents(chat.cost_usd)
        luna += int(chat.luna_tokens or 0)
    run.totals = {
        "chats": len(chats),
        "finished": sum(1 for chat in chats if chat.status in {"completed", "cancelled", "failed"}),
        "priced_cents": cents,
        "luna_tokens": luna,
        "cost_usd": None if cents == 0 and luna else format(Decimal(cents) / Decimal(100), "f"),
    }
    run.updated_at = _now()


def _close_session(db: Session, chat: HarnessChat) -> None:
    if chat.session_id is None:
        return
    session = db.get(KcSession, chat.session_id)
    if session is not None and session.status == "in_progress":
        session.status = "completed"
        session.updated_at = _now()


def _same_place(turns: list[HarnessTurn]) -> int:
    if not turns:
        return 0
    last = ""
    run = 0
    for turn in turns:
        after = turn.session_after if isinstance(turn.session_after, dict) else {}
        place = f"{after.get('block_id')}:{after.get('substep')}"
        if place == last:
            run += 1
        else:
            last = place
            run = 1
    return run


def record_turn(db: Session, chat_id: uuid.UUID, body: dict) -> dict:
    chat = db.scalar(select(HarnessChat).where(HarnessChat.id == chat_id).with_for_update())
    if chat is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    if chat.status not in {"running", "paused"}:
        raise HTTPException(status_code=422, detail="That chat is not running.")
    run = db.get(HarnessRun, chat.run_id)
    seq = int(db.scalar(select(func.max(HarnessTurn.seq)).where(HarnessTurn.chat_id == chat.id)) or 0) + 1
    after = body.get("session_after") if isinstance(body.get("session_after"), dict) else {}
    before = body.get("session_before") if isinstance(body.get("session_before"), dict) else {}
    tokens = body.get("child_tokens") if isinstance(body.get("child_tokens"), dict) else {}
    turn = HarnessTurn(
        chat_id=chat.id,
        seq=seq,
        intent=str(body.get("intent") or "")[:40],
        child_text=str(body.get("child_text") or "")[:2000],
        inner_state=body.get("inner_state") if isinstance(body.get("inner_state"), dict) else {},
        session_before=before,
        session_after=after,
        child_tokens=tokens,
        child_prompt=str(body.get("child_prompt") or ""),
        elapsed_ms=max(0, int(body.get("elapsed_ms") or 0)),
    )
    db.add(turn)
    db.flush()
    chat.turn_count = seq
    chat.updated_at = _now()
    _refresh_chat_cost(db, chat)
    turns = db.scalars(select(HarnessTurn).where(HarnessTurn.chat_id == chat.id).order_by(HarnessTurn.seq)).all()
    errors = 0
    for item in reversed(turns):
        state = item.session_after if isinstance(item.session_after, dict) else {}
        if str(state.get("error") or "").strip():
            errors += 1
        else:
            break
    plan = dict(run.plan or {}) if run is not None else {}
    same_place = _same_place(list(turns))
    stuck_limit = int(plan.get("stuck_limit") or DEFAULT_STUCK_LIMIT)
    reason = stop_reason(
        session_status=str(after.get("status") or ""),
        intent=turn.intent,
        turn_count=seq,
        same_place_turns=same_place,
        priced_cents=_cents(chat.cost_usd),
        cap_cents=int(plan.get("chat_cap_cents") or DEFAULT_CHAT_CAP_CENTS),
        luna_tokens=int(chat.luna_tokens or 0),
        luna_ceiling=int(plan.get("luna_token_ceiling") or DEFAULT_LUNA_TOKEN_CEILING),
        consecutive_errors=errors,
        safety_flag=str(after.get("safety_flag") or "none"),
        stop_on_safety=bool(plan.get("stop_on_safety")),
        turn_limit=int(plan.get("turn_limit") or DEFAULT_TURN_LIMIT),
        stuck_limit=stuck_limit,
    )
    reason, pending = stuck_after_turn(
        reason=reason,
        same_place_turns=same_place,
        stuck_limit=stuck_limit,
        pending_nudges=int(chat.pending_nudges or 0),
    )
    chat.pending_nudges = pending
    if reason:
        _finish(db, chat, reason)
    elif run is not None:
        _refresh_totals(db, run)
    db.flush()
    return {
        "turn": seq,
        "stop": reason,
        "pending_nudges": pending,
        "cost_usd": chat.cost_usd,
        "luna_tokens": chat.luna_tokens,
        "chat": chat_out(chat),
    }


def _turns_for_checks(db: Session, chat: HarnessChat) -> list[dict]:
    rows = []
    for turn in db.scalars(select(HarnessTurn).where(HarnessTurn.chat_id == chat.id).order_by(HarnessTurn.seq)).all():
        after = turn.session_after if isinstance(turn.session_after, dict) else {}
        before = turn.session_before if isinstance(turn.session_before, dict) else {}
        rows.append(
            {
                "intent": turn.intent,
                "child_text": turn.child_text,
                "tutor_reply": after.get("tutor_reply") or "",
                "prompt": after.get("prompt") or "",
                "passed": bool(after.get("passed")),
                "attempt_before": int(before.get("move_attempts") or 0),
                "attempt_after": int(after.get("move_attempts") or 0),
                "block_id": after.get("block_id") or "",
                "block_before": before.get("block_id") or "",
                "substep": after.get("substep") or "",
                "substep_before": before.get("substep") or "",
                "safety_flag": after.get("safety_flag") or "none",
                "error": after.get("error") or "",
                "expected": after.get("expected") or "",
            }
        )
    return rows


def _finish(db: Session, chat: HarnessChat, reason: str) -> None:
    if chat.status in {"completed", "cancelled", "failed"}:
        return
    chat.ended_how = reason
    chat.status = "failed" if reason == "route_error" else "completed"
    chat.updated_at = _now()
    if reason in {"cap", "luna_ceiling", "turn_limit", "stuck", "quit", "safety", "cancelled", "run_cap"}:
        _close_session(db, chat)
    snapshot = chat.child_snapshot if isinstance(chat.child_snapshot, dict) else {}
    profile = snapshot.get("child_profile") if isinstance(snapshot.get("child_profile"), dict) else {}
    checks = automatic_checks(
        _turns_for_checks(db, chat),
        ended_how=reason,
        response_length=str(profile.get("response_length") or "balanced"),
    )
    db.add(
        HarnessEvaluation(
            chat_id=chat.id,
            kind="automatic",
            checks=checks,
            scores={},
            tags=[],
            rubric_version="1",
            judge_model="",
        )
    )
    run = db.get(HarnessRun, chat.run_id)
    if run is not None:
        _refresh_totals(db, run)
        remaining = db.scalar(
            select(func.count()).select_from(HarnessChat).where(
                HarnessChat.run_id == run.id, HarnessChat.status.in_(("queued", "running"))
            )
        )
        if not remaining and run.status == "running":
            run.status = "completed"
            run.updated_at = _now()


def finish_chat(db: Session, chat_id: uuid.UUID, reason: str) -> dict:
    chat = db.get(HarnessChat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    allowed = {"completed", "quit", "turn_limit", "stuck", "cap", "luna_ceiling", "route_error", "safety", "cancelled"}
    chosen = reason if reason in allowed else "completed"
    _refresh_chat_cost(db, chat)
    _finish(db, chat, chosen)
    db.flush()
    return chat_detail(db, chat)


def save_evaluation(db: Session, chat_id: uuid.UUID, body: dict) -> dict:
    chat = db.get(HarnessChat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    scores = body.get("scores") if isinstance(body.get("scores"), list) else []
    tags = body.get("tags") if isinstance(body.get("tags"), list) else []
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    realism = body.get("child_realism")
    db.add(
        HarnessEvaluation(
            chat_id=chat.id,
            kind="judged",
            checks={},
            scores={"items": scores, "usage": usage},
            tags=tags,
            rubric_version=str(body.get("rubric_version") or "1")[:40],
            judge_model=str(body.get("judge_model") or chat.judge_model or "")[:120],
            child_realism=int(realism) if realism is not None else None,
        )
    )
    _refresh_chat_cost(db, chat)
    run = db.get(HarnessRun, chat.run_id)
    if run is not None:
        _refresh_totals(db, run)
    db.flush()
    return chat_detail(db, chat)


def _evaluation_out(row: HarnessEvaluation) -> dict:
    scores = row.scores if isinstance(row.scores, dict) else {}
    items = scores.get("items") if isinstance(scores, dict) else row.scores
    return {
        "id": row.id,
        "kind": row.kind,
        "checks": row.checks if isinstance(row.checks, dict) else {},
        "scores": items if isinstance(items, list) else [],
        "tags": row.tags if isinstance(row.tags, list) else [],
        "rubric_version": row.rubric_version,
        "judge_model": row.judge_model,
        "child_realism": row.child_realism,
        "created_at": row.created_at,
    }


def chat_detail(db: Session, chat: HarnessChat) -> dict:
    turns = db.scalars(select(HarnessTurn).where(HarnessTurn.chat_id == chat.id).order_by(HarnessTurn.seq)).all()
    reviews = db.scalars(
        select(HarnessEvaluation).where(HarnessEvaluation.chat_id == chat.id).order_by(HarnessEvaluation.created_at)
    ).all()
    flags = []
    if chat.session_id is not None:
        events = db.scalars(select(AiSafetyEvent).where(AiSafetyEvent.kc_session_id == chat.session_id)).all()
        flags = [
            {"id": str(event.id), "category": event.category, "child_message": event.child_message, "tutor_reply": event.tutor_reply}
            for event in events
        ]
    prompts = []
    if chat.session_id is not None:
        prompts = list(
            db.scalars(
                select(KcModelPrompt).where(KcModelPrompt.session_id == chat.session_id).order_by(KcModelPrompt.seq)
            ).all()
        )
    body = chat_out(chat)
    body["model_prompts"] = [
        {"seq": row.seq, "model": row.model, "system_prompt": row.system_prompt} for row in prompts
    ]
    body["turns"] = [
        {
            "seq": turn.seq,
            "intent": turn.intent,
            "child_text": turn.child_text,
            "child_prompt": turn.child_prompt or "",
            "tutor_prompt": _tutor_prompt(turn, prompts),
            "inner_state": turn.inner_state if isinstance(turn.inner_state, dict) else {},
            "session_before": turn.session_before if isinstance(turn.session_before, dict) else {},
            "session_after": turn.session_after if isinstance(turn.session_after, dict) else {},
            "child_tokens": turn.child_tokens if isinstance(turn.child_tokens, dict) else {},
            "elapsed_ms": turn.elapsed_ms,
        }
        for turn in turns
    ]
    body["evaluations"] = [_evaluation_out(row) for row in reviews]
    body["safety_flags"] = flags
    body["settings_copy"] = dict(chat.settings_copy or {})
    return body


def _tutor_prompt(turn: HarnessTurn, prompts: list[KcModelPrompt]) -> str:
    after = turn.session_after if isinstance(turn.session_after, dict) else {}
    stored = str(after.get("prompt") or "").strip()
    if stored:
        return stored
    chosen = None
    for row in prompts:
        if row.seq <= turn.seq:
            chosen = row
    if chosen is None and prompts:
        chosen = prompts[0]
    return chosen.system_prompt if chosen is not None else ""


def get_chat(db: Session, chat_id: uuid.UUID) -> dict:
    chat = db.get(HarnessChat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    return chat_detail(db, chat)


def _chat_for_report(db: Session, chat: HarnessChat) -> dict:
    reviews = db.scalars(select(HarnessEvaluation).where(HarnessEvaluation.chat_id == chat.id)).all()
    checks = {}
    scores: list = []
    tags: list = []
    realism = None
    for review in reviews:
        if review.kind == "automatic" and isinstance(review.checks, dict):
            checks = review.checks
        if review.kind == "judged":
            payload = review.scores if isinstance(review.scores, dict) else {}
            scores = payload.get("items") if isinstance(payload.get("items"), list) else []
            tags = review.tags if isinstance(review.tags, list) else []
            realism = review.child_realism
    turns = db.scalars(select(HarnessTurn).where(HarnessTurn.chat_id == chat.id).order_by(HarnessTurn.seq)).all()
    snapshot = chat.child_snapshot if isinstance(chat.child_snapshot, dict) else {}
    settings = chat.settings_copy if isinstance(chat.settings_copy, dict) else {}
    block_types = []
    blocks_by_id: dict[str, str] = {}
    for block in settings.get("blocks") or []:
        if isinstance(block, dict) and block.get("type"):
            block_types.append(str(block["type"]))
            if block.get("id"):
                blocks_by_id[str(block["id"])] = str(block["type"])

    def turn_label(turn: HarnessTurn) -> str:
        after = turn.session_after if isinstance(turn.session_after, dict) else {}
        typed = str(after.get("block_type") or "")
        if not typed:
            typed = blocks_by_id.get(str(after.get("block_id") or ""), "")
        return block_label(typed)

    false_pass_blocks: list[str] = []
    stuck_blocks: list[str] = []
    turn_blocks: list[str] = []
    last_place = ""
    same_step = 0
    for turn in turns:
        label = turn_label(turn)
        if label and label not in turn_blocks:
            turn_blocks.append(label)
        after = turn.session_after if isinstance(turn.session_after, dict) else {}
        if turn.intent in WRONG_INTENTS and after.get("passed") and label and label not in false_pass_blocks:
            false_pass_blocks.append(label)
        place = f"{after.get('block_id')}:{after.get('substep')}"
        if place == last_place:
            same_step += 1
            if same_step >= 8 and label and label not in stuck_blocks:
                stuck_blocks.append(label)
        else:
            same_step = 1
            last_place = place
    if chat.ended_how == "stuck" and turns:
        last_label = turn_label(turns[-1])
        if last_label and last_label not in stuck_blocks:
            stuck_blocks.append(last_label)
    nudge_turns = []
    for turn in turns:
        after = turn.session_after if isinstance(turn.session_after, dict) else {}
        nudge_turns.append(
            {
                "intent": turn.intent,
                "turn": turn.seq,
                "child_text": turn.child_text,
                "tutor_reply": str(after.get("tutor_reply") or ""),
                "block_id": str(after.get("block_id") or ""),
                "substep": str(after.get("substep") or ""),
                "block_type": turn_label(turn),
            }
        )
    tag_blocks: dict[str, str] = {}
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        try:
            index = int(tag.get("turn") or 0)
        except (TypeError, ValueError):
            index = 0
        if 0 <= index < len(turns):
            label = turn_label(turns[index])
            if label:
                tag_blocks[str(tag.get("tag") or "")] = label
    goal = db.get(KcGoal, chat.course_id) if chat.course_id else None
    node = db.get(KcNode, chat.component_id) if chat.component_id else None
    return {
        "id": str(chat.id),
        "persona_name": snapshot.get("name") or "",
        "traits": snapshot.get("traits") or {},
        "course_title": goal.title if goal is not None else "",
        "component_title": node.title if node is not None else "",
        "component_id": str(chat.component_id or ""),
        "block_types": block_types,
        "false_pass_blocks": false_pass_blocks,
        "stuck_blocks": stuck_blocks,
        "stuck_nudges": stuck_nudge_rows(nudge_turns) if chat.ended_how == "stuck" else [],
        "turn_blocks": turn_blocks,
        "tag_blocks": tag_blocks,
        "tutor_model": chat.tutor_model,
        "profile_name": settings.get("profile_name") or chat.tutor_profile_id or "",
        "ended_how": chat.ended_how,
        "cost_usd": chat.cost_usd,
        "checks": checks,
        "scores": scores,
        "tags": tags,
        "child_realism": realism,
        "seed": chat.seed,
        "iteration": chat.iteration,
        "turn_intents": [turn.intent for turn in turns],
    }


def run_report(db: Session, run_id: uuid.UUID) -> dict:
    run = _run_or_404(db, run_id)
    chats = db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id)).all()
    rows = [_chat_for_report(db, chat) for chat in chats if chat.status in {"completed", "failed", "cancelled"}]
    report = rollup(rows)
    report["run_id"] = str(run.id)
    report["findings"] = findings(report)
    report["code_version"] = run.code_version
    if run.suite_id is not None:
        suite = db.get(HarnessSuite, run.suite_id)
        if suite is not None and suite.baseline_run_id and suite.baseline_run_id != run.id:
            baseline = db.get(HarnessRun, suite.baseline_run_id)
            if baseline is not None:
                base_rows = [
                    _chat_for_report(db, chat)
                    for chat in db.scalars(select(HarnessChat).where(HarnessChat.run_id == baseline.id)).all()
                ]
                comparison = compare_runs(base_rows, rows)
                report["baseline"] = {
                    "run_id": str(baseline.id),
                    "verdict": comparison["verdict"],
                    "band": regression_band(comparison),
                    "new_hard_stops": comparison["new_hard_stops"],
                    "mean_score_delta": comparison["mean_score_delta"],
                }
    return report


def compare(db: Session, left_id: uuid.UUID, right_id: uuid.UUID) -> dict:
    left = _run_or_404(db, left_id)
    right = _run_or_404(db, right_id)
    left_rows = [_chat_for_report(db, chat) for chat in db.scalars(select(HarnessChat).where(HarnessChat.run_id == left.id)).all()]
    right_rows = [_chat_for_report(db, chat) for chat in db.scalars(select(HarnessChat).where(HarnessChat.run_id == right.id)).all()]
    body = compare_runs(left_rows, right_rows)
    body["band"] = regression_band(body)
    body["left"] = str(left.id)
    body["right"] = str(right.id)
    return body


def fixture_document() -> dict:
    blocks = [{"id": f"blk_{kind}", "type": kind, "data": data} for kind, data in _BLOCK_EXAMPLES.items()]
    return {
        "schema": SCHEMA,
        "course": {
            "title": "Harness fixture: every block type",
            "code": FIXTURE_CODE,
            "description": "A small course so a harness run can walk every block type.",
            "subject": "Harness",
            "grade_band": "9-11",
            "kind": "mastery",
            "estimated_minutes": 40,
            "outcomes": ["Meet every block type."],
            "brief": "One component that contains every block type the tutor can teach. " * 2,
            "standards": [{"code": "h1", "text": "Every block type."}],
        },
        "units": [
            {
                "title": "Every block",
                "summary": "One of each block type.",
                "components": [
                    {
                        "code": "harness-every-block-all",
                        "title": "Every block type",
                        "description": "The learner meets every block type in one component.",
                        "summary": "All eleven block types.",
                        "outline": "Walk each block.",
                        "core_truth": "Each block type asks for something different.",
                        "rubric": ["Names the idea."],
                        "misconceptions": [{"wrong_move": "All blocks are the same question.", "broken_kc": ""}],
                        "standards": ["h1"],
                        "prerequisite_codes": [],
                        "encompasses_codes": [],
                        "blocks": blocks,
                    }
                ],
            }
        ],
    }


def ensure_fixture(db: Session) -> dict:
    existing = db.scalar(select(KcGoal).where(KcGoal.code == FIXTURE_CODE))
    if existing is None:
        existing = import_new_course(db, fixture_document())
    if not existing.ready:
        mark_ready(db, existing)
    body = course_out(db, existing)
    body["fixture"] = True
    return body


def suite_out(db: Session, row: HarnessSuite) -> dict:
    runs = db.scalars(select(HarnessRun).where(HarnessRun.suite_id == row.id).order_by(HarnessRun.created_at)).all()
    return {
        "id": row.id,
        "name": row.name,
        "plan": dict(row.plan or {}),
        "baseline_run_id": row.baseline_run_id,
        "created_at": row.created_at,
        "run_ids": [run.id for run in runs],
    }


def create_suite(db: Session, body: dict) -> dict:
    name = str(body.get("name") or "").strip()[:160]
    if not name:
        raise HTTPException(status_code=422, detail="Name the suite.")
    plan = body.get("plan") if isinstance(body.get("plan"), dict) else {}
    row = HarnessSuite(name=name, plan=plan)
    run_id = _uuid(body.get("run_id"))
    if run_id is not None:
        run = db.get(HarnessRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="That run was not found.")
        row.plan = dict(run.plan or {})
        db.add(row)
        db.flush()
        run.suite_id = row.id
    else:
        db.add(row)
        db.flush()
    return suite_out(db, row)


def list_suites(db: Session) -> list[dict]:
    return [suite_out(db, row) for row in db.scalars(select(HarnessSuite).order_by(HarnessSuite.created_at.desc())).all()]


def set_baseline(db: Session, suite_id: uuid.UUID, run_id: uuid.UUID) -> dict:
    suite = db.get(HarnessSuite, suite_id)
    run = db.get(HarnessRun, run_id)
    if suite is None or run is None:
        raise HTTPException(status_code=404, detail="That suite or run was not found.")
    run.suite_id = suite.id
    suite.baseline_run_id = run.id
    db.flush()
    return suite_out(db, suite)


def recommendation_out(row: HarnessRecommendation) -> dict:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "suite_id": row.suite_id,
        "title": row.title,
        "evidence": row.evidence if isinstance(row.evidence, dict) else {},
        "cause_class": row.cause_class,
        "place": row.place,
        "proposed": row.proposed if isinstance(row.proposed, dict) else {},
        "prompt_direction": row.prompt_direction,
        "kind": row.kind,
        "risk": row.risk,
        "confidence": row.confidence,
        "status": row.status,
        "trial_profile_id": row.trial_profile_id,
        "created_at": row.created_at,
    }


def list_recommendations(db: Session, *, run_id: uuid.UUID | None = None) -> list[dict]:
    stmt = select(HarnessRecommendation).order_by(HarnessRecommendation.created_at.desc())
    if run_id is not None:
        stmt = stmt.where(HarnessRecommendation.run_id == run_id)
    return [recommendation_out(row) for row in db.scalars(stmt).all()]


def save_recommendations(db: Session, body: dict) -> list[dict]:
    run_id = _uuid(body.get("run_id"))
    suite_id = _uuid(body.get("suite_id"))
    cards = body.get("cards") if isinstance(body.get("cards"), list) else []
    if not cards:
        raise HTTPException(status_code=422, detail="A review needs at least one card.")
    kinds = {str(card.get("kind") or "") for card in cards if isinstance(card, dict)}
    if "remove" not in kinds and "reword" not in kinds:
        raise HTTPException(
            status_code=422,
            detail="A batch that only proposes additions is incomplete. Include a removal or a shorter wording.",
        )
    saved = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        kind = str(card.get("kind") or "reword")
        if kind not in {"setting", "reword", "remove", "add"}:
            kind = "reword"
        direction = str(card.get("prompt_direction") or "same")
        if direction not in {"shorter", "longer", "same"}:
            direction = "same"
        evidence = card.get("evidence") if isinstance(card.get("evidence"), dict) else {"summary": str(card.get("evidence") or "")}
        block_type = str(card.get("block_type") or evidence.get("block_type") or "").strip()
        if block_type:
            evidence = {**evidence, "block_type": block_type}
        row = HarnessRecommendation(
            run_id=run_id,
            suite_id=suite_id,
            title=str(card.get("title") or "Change")[:200],
            evidence=evidence,
            cause_class=str(card.get("cause_class") or "")[:40],
            place=str(card.get("place") or "")[:2000],
            proposed=card.get("proposed") if isinstance(card.get("proposed"), dict) else {"text": str(card.get("proposed") or "")},
            prompt_direction=direction,
            kind=kind,
            risk=str(card.get("risk") or "")[:2000],
            confidence=str(card.get("confidence") or "low")[:16],
            status="new",
        )
        db.add(row)
        db.flush()
        saved.append(recommendation_out(row))
    return saved


def update_recommendation(db: Session, card_id: uuid.UUID, body: dict) -> dict:
    row = db.get(HarnessRecommendation, card_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That recommendation was not found.")
    status = str(body.get("status") or "").strip()
    allowed = {"new", "accepted", "rejected", "on_trial", "shipped", "verified", "regressed"}
    if status:
        if status not in allowed:
            raise HTTPException(status_code=422, detail="That status is not one of the review states.")
        if status == "shipped":
            raise HTTPException(status_code=422, detail="Accepted settings are not applied to the live profile from here.")
        row.status = status
    db.flush()
    return recommendation_out(row)


def _apply_setting(config: dict, proposed: dict) -> dict:
    updated = copy.deepcopy(config)
    scope = str(proposed.get("scope") or "overarching")
    key = str(proposed.get("key") or "").strip()
    if not key:
        return updated
    if scope == "block":
        block = str(proposed.get("block") or "")
        updated.setdefault("blocks", {}).setdefault(block, {})[key] = proposed.get("value")
    elif scope == "voice":
        updated.setdefault("voice", {})[key] = proposed.get("value")
    else:
        updated.setdefault("overarching", {})[key] = proposed.get("value")
    return updated


def trial_profile(db: Session, card_id: uuid.UUID) -> dict:
    """Copy the tutor profile with the proposed setting. Real children stay on their own profile."""
    row = db.get(HarnessRecommendation, card_id)
    if row is None:
        raise HTTPException(status_code=404, detail="That recommendation was not found.")
    if row.kind != "setting":
        raise HTTPException(status_code=422, detail="Only a settings card can make a trial profile. Wording and loop changes go on a branch.")
    if row.cause_class == "safety":
        raise HTTPException(status_code=422, detail="Safety changes are not trialed here. There is one global safety row.")
    proposed = row.proposed if isinstance(row.proposed, dict) else {}
    source_id = str(proposed.get("profile_id") or "") or None
    source = get_profile_by_id_or_slug(db, source_id) if source_id else load_profile(db)
    if source is None:
        raise HTTPException(status_code=404, detail="The source tutor profile was not found.")
    created = create_tutor_profile(
        db,
        name=f"Trial {row.title}"[:120],
        description="Harness trial. Hidden from tutor pickers.",
        source_profile_id=source.id,
    )
    created.is_test = True
    config = effective_kc_tutor_config(created)
    created.kc_tutor_config = _apply_setting(config, proposed)
    row.trial_profile_id = created.id
    row.status = "on_trial"
    db.flush()
    plan = {}
    if row.run_id is not None:
        run = db.get(HarnessRun, row.run_id)
        if run is not None:
            plan = dict(run.plan or {})
            plan["tutor_profile_ids"] = [created.id]
    return {"recommendation": recommendation_out(row), "trial_profile_id": created.id, "plan": plan}


def trim_prompts(db: Session, *, run_id: uuid.UUID | None = None) -> dict:
    """Drop stored prompts except the baseline and the newest run of each suite."""
    suites = []
    for suite in db.scalars(select(HarnessSuite)).all():
        run_ids = [
            str(item)
            for item in db.scalars(
                select(HarnessRun.id).where(HarnessRun.suite_id == suite.id).order_by(HarnessRun.created_at)
            ).all()
        ]
        suites.append({"baseline_run_id": str(suite.baseline_run_id or ""), "run_ids": run_ids})
    kept = kept_run_ids(suites)
    stmt = select(HarnessRun)
    if run_id is not None:
        stmt = stmt.where(HarnessRun.id == run_id)
    trimmed = []
    skipped = []
    for run in db.scalars(stmt).all():
        if str(run.id) in kept:
            skipped.append(str(run.id))
            continue
        session_ids = [
            item
            for item in db.scalars(select(HarnessChat.session_id).where(HarnessChat.run_id == run.id)).all()
            if item is not None
        ]
        if session_ids:
            db.execute(delete(KcModelPrompt).where(KcModelPrompt.session_id.in_(session_ids)))
        trimmed.append(str(run.id))
    db.flush()
    return {"trimmed": trimmed, "kept": sorted(kept), "skipped": skipped}


def findings_for_run(db: Session, run_id: uuid.UUID) -> dict:
    report = run_report(db, run_id)
    return {"run_id": str(run_id), "findings": report.get("findings") or [], "top_problems": report.get("top_problems") or []}
