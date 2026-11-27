"""AI test children: personas, runs, chats, reviews, and recommendations.

The live tutor routes are not called from here. The browser runner calls them.
This module stores the plan, the child's intent, and the reviews.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai_safety import read_ai_safety
from app.block_score import LEGACY_OUTCOMES, REQUIREMENT_SCORE, classify_stored_outcome
from app.flow import unique_student_slug
from app.harness_download import render_download, reply_message_id
from app.harness_checks import (
    CHECKS_VERSION,
    DEFAULT_CHAT_CAP_CENTS,
    DEFAULT_LUNA_TOKEN_CEILING,
    DEFAULT_STUCK_LIMIT,
    DEFAULT_TURN_LIMIT,
    WRONG_INTENTS,
    automatic_checks,
    chat_budget_stop,
    place_key,
    side_action_checks,
    stop_reason,
    stuck_after_turn,
)
from app.harness_personas import TRAIT_KEYS, starter_children
from app.harness_scenario_fixture import SCENARIO_FIXTURE_CODE, scenario_fixture_document
from app.kc_blocks import passage_paragraphs
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
    KcTurnReceipt,
    Student,
    TutorProfile,
    normalize_child_profile,
)
from app.token_usage import _model_cost, session_token_usage
from app.tutor_profile import create_tutor_profile, effective_kc_tutor_config, get_profile_by_id_or_slug, load_profile

HARNESS_CODE_VERSION = "harness-1"


def deployed_commit() -> str:
    """The build that served this process. Empty when the host did not set one."""
    for key in ("RENDER_GIT_COMMIT", "GIT_COMMIT", "SOURCE_VERSION"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def run_code_version() -> str:
    commit = deployed_commit()
    if not commit:
        return HARNESS_CODE_VERSION
    return f"{HARNESS_CODE_VERSION} {commit.split()[0][:40]}"[:80]
FIXTURE_CODE = "harness-every-block"
LUNA_MODEL = "gpt-6-luna"
MAX_LUNA_TOKENS = 2**31 - 1  # The largest value the chat's PostgreSQL INTEGER can record.
_UNGRADED_STEPS = {"explain", "explain_topic", "summary_check"}


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
        "pair_tutor_seeds": raw.get("pair_tutor_seeds") is True,
        "scenario": str(raw.get("scenario") or "")[:100],
        "scenario_group": str(raw.get("scenario_group") or "")[:100],
        "seed_from_run": str(raw.get("seed_from_run") or ""),
        "seed_from_profile": str(raw.get("seed_from_profile") or ""),
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




def scenario_seed(run_seed: int, persona, course, component, model: str, profile: str,
                  iteration: int, *, scenario: str = "", group: str = "", paired: bool = False) -> int:
    """Reordering the run grid cannot change a learner's scenario or shift its turn stream."""
    parts = [int(run_seed), str(persona), str(course), str(component), int(iteration)]
    parts.append(group if paired and group else scenario)
    if not paired:
        parts.extend([model, profile])
    payload = json.dumps(parts, separators=(",", ":")).encode()
    return int.from_bytes(hashlib.blake2s(payload, digest_size=8).digest(), "big") % 2_000_000_000


def _recorded_seeds(db: Session, run_id, *, source_profile=None, target_profile=None) -> dict:
    stmt = select(HarnessChat).where(HarnessChat.run_id == run_id)
    if source_profile:
        stmt = stmt.where(HarnessChat.tutor_profile_id == source_profile)
    return {(c.persona_id, c.course_id, c.component_id, c.tutor_model, target_profile or c.tutor_profile_id, c.iteration): c.seed
            for c in db.scalars(stmt)}


def _snapshot(row: HarnessPersona, behavior: str, scenario: str) -> dict:
    role = "script" if behavior == "script" else "learner"
    if behavior == "rule" and row.number in (13, 14):
        role = "answer_key_control"
    child_profile = dict(row.child_profile or {})
    reader_lengths = {"river-example-practice": "bite_sized", "reread-short": "bite_sized", "reread-detail": "detailed"}
    if role == "script" and row.number in (2, 8) and scenario in reader_lengths:
        child_profile["response_length"] = reader_lengths[scenario]
    return {
        "id": str(row.id),
        "number": row.number,
        "name": row.name,
        "description": row.description,
        "age": row.age,
        "child_profile": child_profile,
        "traits": dict(row.traits or {}),
        "simulation_role": role,
        "policy_version": "visible-v1",
    }


def create_run(db: Session, raw: dict, *, suite_id: uuid.UUID | None = None, seeds: dict | None = None) -> dict:
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
        code_version=run_code_version(),
        suite_id=suite_id,
    )
    db.add(run)
    db.flush()
    if seeds is None and (source_run := _uuid(plan["seed_from_run"])) and len(profiles) == 1 and plan["seed_from_profile"]:
        seeds = _recorded_seeds(db, source_run, source_profile=plan["seed_from_profile"], target_profile=profiles[0].id)
    for child in children:
        for goal, node in components:
            for model in plan["tutor_models"]:
                for profile in profiles:
                    for iteration in range(1, plan["iterations"] + 1):
                        identity = child.id, goal.id, node.id, model, profile.id, iteration
                        seed = (seeds or {}).get(identity)
                        if seed is None:
                            seed = scenario_seed(
                                plan["seed"], *identity, scenario=plan["scenario"], group=plan["scenario_group"],
                                paired=plan["pair_tutor_seeds"],
                            )
                        db.add(
                            HarnessChat(
                                run_id=run.id,
                                status="queued",
                                persona_id=child.id,
                                child_snapshot={
                                    **_snapshot(child, plan["behavior"], plan["scenario"]), "scenario": plan["scenario"],
                                    "seed_profile": plan["seed_from_profile"] or profile.id,
                                    "paired_seeds": plan["pair_tutor_seeds"],
                                },
                                course_id=goal.id,
                                component_id=node.id,
                                tutor_model=model,
                                child_model=plan["child_model"],
                                judge_model="",
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


def _run_cap_reached(db: Session, run: HarnessRun, totals: dict | None = None) -> bool:
    cap = (run.plan or {}).get("run_cap_cents")
    if not cap:
        return False
    if totals is None:
        totals = run.totals or {}
        if totals.get("cost_precision") != "exact_usd":
            # Older cached totals rounded every chat to whole cents. Reconstruct
            # the estimate before admitting work, without writing on a GET.
            totals = _cost_totals(_cost_rows(db, run), totals)
    return _usd(totals.get("cost_usd")) * 100 >= int(cap)


def run_out(db: Session, run: HarnessRun) -> dict:
    chats = db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id).order_by(HarnessChat.created_at)).all()
    totals = _cost_totals(chats, run.totals or {})
    return {
        "id": run.id,
        "status": run.status,
        "plan": _as_dict(run.plan),
        "run_cap_reached": _run_cap_reached(db, run, totals),
        "totals": totals,
        "code_version": run.code_version,
        "suite_id": run.suite_id,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "chats": len(chats),
        "finished": totals["finished"],
        "chat_rows": [{**chat_out(chat), "chat_budget_stop": _chat_budget_stop(chat, run) or None} for chat in chats],
    }


def _nudge_counts(chat: HarnessChat) -> dict[str, int]:
    # Older terminal rows may still carry counts from the last stuck step.
    if chat.status in {"completed", "cancelled", "failed"}:
        return {"pending_nudges": 0, "stuck_answers": 0}
    return {"pending_nudges": int(chat.pending_nudges or 0), "stuck_answers": int(chat.stuck_answers or 0)}


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
        **_nudge_counts(chat),
        "claim_generation": int(chat.claim_generation or 0),
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
    }


def list_chats(db: Session) -> list[dict]:
    """Every stored test chat, newest first. Not only the latest run."""
    chats = db.scalars(select(HarnessChat).order_by(HarnessChat.created_at.desc())).all()
    return [chat_out(chat) for chat in chats]


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


def claim_opens_session(session_id: object) -> bool:
    """A chat that already has a tutor session does not open another one."""
    return session_id is None


def next_claim_generation(current: object) -> int:
    try:
        value = int(current or 0)
    except (TypeError, ValueError):
        value = 0
    return max(0, value) + 1


def replaced_session_id(previous: object, new: object) -> object | None:
    """The open session to close when a chat is pointed at a different one."""
    if previous is None or new is None or previous == new:
        return None
    return previous


def resume_run(db: Session, run_id: uuid.UUID) -> dict:
    run = _run_or_404(db, run_id)
    if run.status in {"paused", "queued", "running"}:
        run.status = "running"
        run.updated_at = _now()
        running = db.scalars(
            select(HarnessChat).where(HarnessChat.run_id == run.id, HarnessChat.status.in_(("running", "paused")))
        ).all()
        for chat in running:
            # Queue the chat so the open tab can continue it. Do not clear session_id.
            # claim_chat keeps that session and does not call open_session again.
            # A second claim only bumps claim_generation, which stops the old loop.
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
    plan = dict(run.plan or {})
    plan["seed"] = int(plan.get("seed") or 1)
    return create_run(db, plan, suite_id=run.suite_id, seeds=_recorded_seeds(db, run.id))


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
    queued = select(HarnessChat).where(HarnessChat.run_id == run.id, HarnessChat.status == "queued")
    if _run_cap_reached(db, run):
        # Never open a fresh session at the cap. A previously submitted answer can
        # still settle after its HTTP request timed out, so keep those chats claimable.
        unused = db.scalars(queued.where(HarnessChat.pending_turn.is_(None)).with_for_update(skip_locked=True)).all()
        for chat in unused:
            chat.status = "cancelled"
            chat.ended_how = "run_cap"
            chat.updated_at = _now()
            _close_session(db, chat)
        if unused:
            _refresh_totals(db, run)
            db.flush()
        queued = queued.where(HarnessChat.pending_turn.is_not(None))
    # LIMIT 1 so each parallel claim locks a different queued chat.
    chat = db.scalar(
        queued
        .order_by(HarnessChat.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if chat is None:
        _settle_inactive_run(db, run)
        return None
    if not claim_opens_session(chat.session_id):
        existing = db.get(KcSession, chat.session_id)
        if existing is not None:
            chat.claim_generation = next_claim_generation(chat.claim_generation)
            chat.status = "running"
            chat.updated_at = _now()
            run.updated_at = _now()
            db.flush()
            body = chat_out(chat)
            body["session"] = {"id": str(existing.id), "status": existing.status}
            body["pending_turn"] = chat.pending_turn
            last = db.scalar(select(HarnessTurn).where(HarnessTurn.chat_id == chat.id)
                             .order_by(HarnessTurn.seq.desc()).limit(1))
            if last is not None:
                after = _as_dict(last.session_after)
                body["last_inner_state"] = last.inner_state
                body["last_place"] = place_key(after.get("block_id"), after.get("substep"), after.get("topic_index"))
            return body
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
    previous = replaced_session_id(chat.session_id, session.id)
    if previous is not None:
        _close_open_session(db, previous)
    chat.student_id = student.id
    chat.session_id = session.id
    chat.claim_generation = next_claim_generation(chat.claim_generation)
    chat.settings_copy = _settings_copy(db, profile, node)
    chat.status = "running"
    chat.updated_at = _now()
    run.updated_at = _now()
    db.flush()
    body = chat_out(chat)
    body["session"] = {"id": str(session.id), "status": session.status}
    return body


def _stored_block_title(data: dict) -> str:
    """Title already stored on the block. Empty when the block has no title."""
    titled = str(data.get("block_title") or "").strip()
    if titled:
        return titled
    topics = data.get("topics")
    if isinstance(topics, list) and topics and isinstance(topics[0], dict):
        topic = str(topics[0].get("title") or "").strip()
        if topic:
            return topic
    for key in ("topic", "passage_title", "question_stem"):
        text = str(data.get(key) or "").strip()
        if text:
            return text
    return ""


def _first_text(data: dict, *keys: str) -> str:
    for key in keys:
        text = str(data.get(key) or "").strip()
        if text:
            return text
    return ""


def expected_for_step(block_type: str, substep: str, data: dict) -> str:
    """The answer key for this step. A later step's answer is not used here.

    Explanation and the summary close have nothing to grade.
    """
    kind = (block_type or "").strip()
    step = (substep or "").strip()
    if step in _UNGRADED_STEPS:
        return ""
    if kind == "topic_goal" and step == "main":
        return _first_text(data, "goal", "acceptance_criteria")
    if kind == "worked_example" and step == "faded_step":
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        try:
            index = int(data.get("faded_step_index") or 0)
        except (TypeError, ValueError):
            index = 0
        if 0 <= index < len(steps):
            row = steps[index]
            if isinstance(row, dict):
                return str(row.get("step_text") or "").strip()
            return str(row or "").strip()
        return ""
    if kind == "worked_example" and step == "solo_solve":
        return str(data.get("solo_expected_answer") or "").strip()
    if kind == "retrieval_check" and step == "recall":
        return str(data.get("expected_fact") or "").strip()
    if kind == "retrieval_check" and step in {"elaborate_why", "why"}:
        return str(data.get("expected_why_rationale") or "").strip()
    if kind == "mcq" and step in {"choice", "awaiting_why"}:
        for choice in data.get("choices") or []:
            if isinstance(choice, dict) and choice.get("is_correct"):
                return str(choice.get("text") or choice.get("id") or "").strip()
        return ""
    if kind == "spot_the_flaw":
        return _first_text(data, "flaw_description", "corrected_version")
    if kind == "case_study" and step == "contrast_and_rule":
        return str(data.get("invariant_principle") or "").strip()
    if kind == "case_study" and step == "transfer":
        return _first_text(data, "transfer_expected", "invariant_principle")
    if kind == "socratic" and step == "counterexample_probe":
        return str(data.get("target_synthesis") or "").strip()
    if kind == "passage_ela" and step == "central_idea":
        return str(data.get("expected_central_idea") or "").strip()
    if kind == "passage_ela" and step == "craft_or_inference":
        return str(data.get("expected_analysis") or "").strip()
    if kind == "teach_back":
        return _first_text(data, "goal", "summary_takeaway")
    return ""


def _topic_number(state: dict | None) -> int | None:
    if not isinstance(state, dict) or "topic_index" not in state:
        return None
    try:
        return int(state.get("topic_index") or 0)
    except (TypeError, ValueError):
        return None


def seen_passage(text: str, messages, block_index: int) -> str:
    """Only repeat authored paragraphs the tutor has actually displayed in this block."""
    shown = [" ".join(message.content.split()) for message in messages
             if message.step == block_index and message.role == "assistant"]
    paragraphs = passage_paragraphs(text)
    return "\n\n".join(p for p in paragraphs if any(" ".join(p.split()) in line for line in shown))


def answer_key(db: Session, chat_id: uuid.UUID) -> dict:
    chat = db.get(HarnessChat, chat_id)
    if chat is None or chat.session_id is None:
        raise HTTPException(status_code=404, detail="That chat has no session yet.")
    session = db.get(KcSession, chat.session_id)
    node = db.get(KcNode, session.kc_id) if session is not None else None
    if session is None or node is None:
        raise HTTPException(status_code=404, detail="That session was not found.")
    _profile, _goal, messages, _fragment, _cfg, _blocks, index, block, state = _block_context(db, session, node)
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
        "revision": int(session.revision or 0),
        "block_index": index,
        "block_id": str(block.get("id") or "") if isinstance(block, dict) else "",
        "block_type": str(block.get("type") or "") if isinstance(block, dict) else "",
        "block_title": _stored_block_title(data),
        "substep": str(state.get("substep") or ""),
        "topic_index": _topic_number(state),
        "expected": expected_for_step(
            str(block.get("type") or "") if isinstance(block, dict) else "",
            str(state.get("substep") or ""),
            data,
        ),
        "visible_passage": seen_passage(str(data.get("passage_text") or ""), messages, index)
        if block and block.get("type") == "passage_ela" else "",
        "correct_choice_id": correct,
        "choices": choices,
        "misconceptions": misconceptions,
        "probes": probes,
        "move_attempts": int(session.move_attempts or 0),
    }


def _usd(amount: str | int | None) -> Decimal:
    try:
        value = Decimal(amount or "0")
        return value if value.is_finite() else Decimal(0)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def _add_money(left: str | None, right: str | None) -> str | None:
    if left is None and right is None:
        return None
    total = Decimal(left or "0") + Decimal(right or "0")
    text = format(total, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _judge_usage(value: object) -> dict[str, int]:
    usage = _as_dict(value)
    counts = {}
    for key in ("input_tokens", "output_tokens"):
        count = usage.get(key)
        if isinstance(count, str) and len(count) <= 19 and count.isascii() and count.isdigit():
            count = int(count)
        if type(count) is int and 0 <= count < 2**63:
            counts[key] = count
    return counts


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
    # Generation is billed even if the tutor never receives the child's answer.
    child_usage = list(db.scalars(select(HarnessTurn.child_tokens).where(HarnessTurn.chat_id == chat.id)))
    for checkpoint in (chat.pending_turn, _as_dict(chat.tokens).get("unsent_child")):
        if checkpoint:
            child_usage.append(checkpoint.get("child_tokens"))
    for usage in child_usage:
        tokens = _as_dict(usage)
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
        usage = _judge_usage(scores.get("usage"))
        if not usage:
            continue
        model = str(review.judge_model or "")
        incoming = usage.get("input_tokens", 0)
        outgoing = usage.get("output_tokens", 0)
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
    run = _run_or_404(db, chat.run_id)
    stored = run.totals or {}
    if stored.get("cost_precision") != "exact_usd" and _stored_usd(stored) > 0:
        # Preserve any historical spend that has no chat price before the first
        # new price changes which part of the old aggregate can be reconstructed.
        _refresh_totals(db, run)
    priced, luna = _chat_priced_cost(db, chat)
    chat.cost_usd = priced
    chat.luna_tokens = min(luna, MAX_LUNA_TOKENS)


def refresh_harness_session_cost(db: Session, session_id: uuid.UUID) -> None:
    # A retried provider call can report usage after the harness records its
    # final turn. Use the same chat-then-run lock order as the turn recorder.
    chat = db.scalar(select(HarnessChat).where(HarnessChat.session_id == session_id).with_for_update())
    if chat is not None:
        _refresh_chat_cost(db, chat)
        _refresh_totals(db, _run_or_404(db, chat.run_id))


def _cost_rows(db: Session, run: HarnessRun):
    return db.execute(
        select(HarnessChat.status, HarnessChat.cost_usd, HarnessChat.luna_tokens).where(HarnessChat.run_id == run.id)
    ).all()


def _stored_usd(totals: dict) -> Decimal:
    return _usd(totals.get("cost_usd")) or _usd(totals.get("priced_cents")) / 100


def _cost_totals(chats, stored: dict) -> dict:
    priced = sum((_usd(chat.cost_usd) for chat in chats), Decimal(0))
    carry = _usd(stored.get("unallocated_usd"))
    if stored.get("cost_precision") != "exact_usd" and _stored_usd(stored) > 0:
        if not chats or any(chat.cost_usd is None for chat in chats):
            # Before exact pricing, each known chat contributed its rounded
            # cents to the aggregate. Keep only the part those rows cannot explain.
            known_cents = sum((_usd(chat.cost_usd) * 100).to_integral_value() for chat in chats)
            carry = max(Decimal(0), _stored_usd(stored) - known_cents / Decimal(100))
    priced += carry
    luna = sum(int(chat.luna_tokens or 0) for chat in chats) if chats else int(stored.get("luna_tokens") or 0)
    return {
        "chats": len(chats),
        "finished": sum(1 for chat in chats if chat.status in {"completed", "cancelled", "failed"}),
        "priced_cents": int((priced * 100).to_integral_value()),
        "luna_tokens": luna,
        "cost_usd": None if not priced and luna else format(priced, "f"),
        **({"unallocated_usd": format(carry, "f")} if carry else {}),
    }


def _refresh_totals(db: Session, run: HarnessRun) -> None:
    # Flush chat usage first, then serialize the aggregate. Selecting columns
    # reads committed sibling costs even if an earlier query cached their objects.
    db.flush()
    stored = db.scalar(select(HarnessRun.totals).where(HarnessRun.id == run.id).with_for_update())
    run.totals = {**_cost_totals(_cost_rows(db, run), stored or {}), "cost_precision": "exact_usd"}
    run.updated_at = _now()


def _settle_inactive_run(db: Session, run: HarnessRun) -> None:
    if run.status != "running":
        return
    if _run_cap_reached(db, run):
        # Two capped workers can pause their own chats at the same time. The
        # last one must see its sibling's commit before settling the run.
        stored_status = db.scalar(select(HarnessRun.status).where(HarnessRun.id == run.id).with_for_update())
        if stored_status != "running":
            return
    active = db.scalar(select(func.count()).select_from(HarnessChat).where(
        HarnessChat.run_id == run.id, HarnessChat.status.in_(("queued", "running"))
    ))
    if not active:
        paused = db.scalar(select(HarnessChat.id).where(
            HarnessChat.run_id == run.id, HarnessChat.status == "paused"
        ).limit(1))
        run.status = "paused" if paused else "completed"
        run.updated_at = _now()


def _close_open_session(db: Session, session_id: object) -> None:
    if session_id is None:
        return
    session = db.get(KcSession, session_id)
    if session is not None and session.status == "in_progress":
        session.status = "completed"
        session.updated_at = _now()


def _close_session(db: Session, chat: HarnessChat) -> None:
    _close_open_session(db, chat.session_id)


def _chat_budget_inputs(chat: HarnessChat, plan: dict) -> dict[str, int]:
    # The threshold is a whole number of cents. Truncating for this comparison
    # keeps a fractional cent below the threshold eligible.
    return {
        "priced_cents": int(_usd(chat.cost_usd) * 100),
        "cap_cents": int(plan.get("chat_cap_cents") or DEFAULT_CHAT_CAP_CENTS),
        "luna_tokens": int(chat.luna_tokens or 0),
        "luna_ceiling": min(int(plan.get("luna_token_ceiling") or DEFAULT_LUNA_TOKEN_CEILING), MAX_LUNA_TOKENS),
    }


def _chat_budget_stop(chat: HarnessChat, run: HarnessRun) -> str:
    return chat_budget_stop(**_chat_budget_inputs(chat, run.plan or {}))


def _dispatch_budget_stop(db: Session, chat: HarnessChat, run: HarnessRun) -> str:
    return "run_cap" if _run_cap_reached(db, run) else _chat_budget_stop(chat, run)


def _same_place(turns: list[HarnessTurn]) -> int:
    if not turns:
        return 0
    last = ""
    run = 0
    for turn in turns:
        after = turn.session_after if isinstance(turn.session_after, dict) else {}
        topic = after.get("topic_index") if "topic_index" in after else None
        place = place_key(after.get("block_id"), after.get("substep"), topic)
        if place == last:
            run += 1
        else:
            last = place
            run = 1
    return run


def _locked_chat(db: Session, chat_id: uuid.UUID) -> HarnessChat:
    chat = db.scalar(select(HarnessChat).where(HarnessChat.id == chat_id).with_for_update())
    if chat is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    return chat


def _check_turn_owner(chat: HarnessChat, body: dict) -> None:
    if body.get("claim_generation") != chat.claim_generation or chat.status != "running":
        raise HTTPException(status_code=409, detail="This worker no longer owns the chat.")


def prepare_harness_turn(db: Session, chat_id: uuid.UUID, body: dict) -> dict:
    """Checkpoint the exact generated move before the worker contacts the tutor."""
    chat = _locked_chat(db, chat_id)
    _check_turn_owner(chat, body)
    submission = _as_dict(body.get("submission"))
    seq = body.get("seq")
    turn_id = _uuid(submission.get("turn_id"))
    if turn_id is None or str(turn_id) != submission["turn_id"]:
        raise HTTPException(status_code=422, detail="A canonical turn UUID is required.")
    text = submission.get("child_text")
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise HTTPException(status_code=422, detail="The submitted answer must be 1–2000 characters.")
    if type(seq) is not int or submission.get("seq") != seq or seq != chat.turn_count + 1:
        raise HTTPException(status_code=409, detail="The next harness turn has changed.")
    pending = chat.pending_turn
    if pending:
        if pending != submission:
            raise HTTPException(status_code=409, detail="Another submission is already pending.")
        return {"submission": pending}
    if "dispatch_state" in submission and submission["dispatch_state"] != "prepared":
        raise HTTPException(status_code=422, detail="A new submission must start as prepared.")
    session = db.get(KcSession, chat.session_id) if chat.session_id else None
    if session is None or type(submission.get("revision")) is not int or submission["revision"] != session.revision:
        raise HTTPException(status_code=409, detail="The tutor session has changed.")
    if db.get(HarnessTurn, turn_id) is not None or _answer_receipt(db, chat, str(turn_id)) is not None:
        raise HTTPException(status_code=409, detail="This turn ID was already used.")
    chat.pending_turn = submission
    chat.updated_at = _now()
    db.flush()
    _refresh_chat_cost(db, chat)
    _refresh_totals(db, _run_or_404(db, chat.run_id))
    return {"submission": submission}


def _answer_receipt(db: Session, chat: HarnessChat, turn_id: str) -> KcTurnReceipt | None:
    return db.scalar(select(KcTurnReceipt).where(
        KcTurnReceipt.session_id == chat.session_id, KcTurnReceipt.route == "answer",
        KcTurnReceipt.client_turn_id == turn_id,
    ))


def pending_answer_result(db: Session, chat_id: uuid.UUID, turn_id: uuid.UUID) -> dict:
    """Read a saved decision without claiming the turn or contacting a model."""
    chat = db.get(HarnessChat, chat_id)
    if chat is None or (chat.pending_turn or {}).get("turn_id") != str(turn_id):
        raise HTTPException(status_code=409, detail="This submission is no longer pending.")
    receipt = _answer_receipt(db, chat, str(turn_id))
    return {"result": receipt.result if receipt and receipt.status == "committed" else None}


def dispatch_harness_turn(db: Session, chat_id: uuid.UUID, turn_id: uuid.UUID, generation: int | None) -> dict:
    """Authorize delivery before network I/O. A missing historical marker means delivery is uncertain."""
    chat = _locked_chat(db, chat_id)
    unsent = _as_dict(_as_dict(chat.tokens).get("unsent_child"))
    if (unsent.get("turn_id") == str(turn_id) and generation == chat.claim_generation
            and chat.ended_how in {"run_cap", "cap", "luna_ceiling"}):
        return {"action": "run_cap", "ended_how": chat.ended_how}
    _check_turn_owner(chat, {"claim_generation": generation})
    pending = _as_dict(chat.pending_turn)
    if pending.get("turn_id") != str(turn_id):
        raise HTTPException(status_code=409, detail="This submission is no longer pending.")
    run = db.scalar(select(HarnessRun).where(HarnessRun.id == chat.run_id).with_for_update()
                    .execution_options(populate_existing=True))
    if run.status != "running":
        return {"action": "paused"}
    prepared = pending.get("dispatch_state") == "prepared"
    budget_stop = _dispatch_budget_stop(db, chat, run)
    if budget_stop:
        if not prepared or _answer_receipt(db, chat, str(turn_id)) is not None:
            return {"action": "read_receipt"}
        # Closing this chat does not create a fictitious learner or harness turn.
        chat.tokens = {**_as_dict(chat.tokens), "unsent_child": {
            "turn_id": str(turn_id), "child_tokens": pending.get("child_tokens") or {},
        }}
        chat.pending_turn = None
        _finish(db, chat, budget_stop)
        # Older workers recognize this action as "finished without sending".
        return {"action": "run_cap", "ended_how": budget_stop}
    if prepared:
        chat.pending_turn = {**pending, "dispatch_state": "dispatched"}
        db.flush()
    return {"action": "send"}


def record_turn(db: Session, chat_id: uuid.UUID, body: dict) -> dict:
    chat = _locked_chat(db, chat_id)
    turn_id = _uuid(body.get("turn_id"))
    pending = chat.pending_turn
    after = _as_dict(body.get("session_after"))
    if "turn_id" in body or pending is not None:
        if turn_id is None:
            raise HTTPException(status_code=409, detail="The prepared turn ID is required.")
        stored = db.get(HarnessTurn, turn_id)
        if stored is not None:
            if stored.chat_id != chat_id or stored.seq != body.get("seq") or stored.child_text != body.get("child_text"):
                raise HTTPException(status_code=409, detail="This turn ID belongs to a different submission.")
            return {"turn": stored.seq, "stop": chat.ended_how, "replayed": True,
                    **_nudge_counts(chat),
                    "cost_usd": chat.cost_usd, "luna_tokens": chat.luna_tokens}
        matches = pending and all(body.get(key) == pending.get(key) for key in ("turn_id", "seq", "child_text"))
        if (matches and chat.status == "paused" and body.get("claim_generation") == chat.claim_generation
                and after.get("delivery_status") == "unknown"):
            return {"turn": body["seq"], "stop": "awaiting_retry", "pending": True}
        _check_turn_owner(chat, body)
        if not matches:
            raise HTTPException(status_code=409, detail="The result does not match the prepared submission.")
        receipt = _answer_receipt(db, chat, str(turn_id))
        committed = receipt is not None and receipt.status == "committed"
        if after.get("delivery_status") == "unknown":
            if committed and not body.get("defer"):
                return {"turn": body["seq"], "stop": "", "recover": True, "pending": True}
            # A timed-out request may still commit. Keep the move across Resume even if
            # no receipt was visible when this transaction inspected the tutor session.
            run = _run_or_404(db, chat.run_id)
            if _dispatch_budget_stop(db, chat, run):
                # Only this uncertain chat pauses. Other eligible chats can continue.
                chat.status = "paused"
                chat.updated_at = _now()
                db.flush()
                _settle_inactive_run(db, run)
            else:
                pause_run(db, chat.run_id)
            db.flush()
            return {"turn": body["seq"], "stop": "awaiting_retry", "pending": True}
        if not committed:
            raise HTTPException(status_code=409, detail="The tutor has not committed this submission.")
        if after.get("delivery_status") not in {"delivered", "recovered", "committed_empty"}:
            raise HTTPException(status_code=422, detail="The delivery status is missing.")
        # The preparation owns the learner input and its cost. Only the actual
        # reply and resulting state are supplied by a resumed worker.
        body = {**body, **{key: pending.get(key) for key in (
            "intent", "child_text", "child_prompt", "child_tokens", "session_before"
        )}}
        after = {**after, "turn_id": str(turn_id), "receipt_status": "committed"}
        chat.pending_turn = None
    if chat.status not in {"running", "paused"}:
        raise HTTPException(status_code=422, detail="That chat is not running.")
    run = db.get(HarnessRun, chat.run_id)
    seq = int(db.scalar(select(func.max(HarnessTurn.seq)).where(HarnessTurn.chat_id == chat.id)) or 0) + 1
    before = body.get("session_before") if isinstance(body.get("session_before"), dict) else {}
    tokens = body.get("child_tokens") if isinstance(body.get("child_tokens"), dict) else {}
    turn = HarnessTurn(
        id=turn_id or uuid.uuid4(),
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
        **_chat_budget_inputs(chat, plan),
        consecutive_errors=errors,
        safety_flag=str(after.get("safety_flag") or "none"),
        stop_on_safety=bool(plan.get("stop_on_safety")),
        turn_limit=int(plan.get("turn_limit") or DEFAULT_TURN_LIMIT),
        stuck_limit=stuck_limit,
    )
    reason, pending, answers = stuck_after_turn(
        reason=reason,
        same_place_turns=same_place,
        stuck_limit=stuck_limit,
        pending_nudges=int(chat.pending_nudges or 0),
        stuck_answers=int(chat.stuck_answers or 0),
        intent=turn.intent,
    )
    chat.pending_nudges = pending
    chat.stuck_answers = answers
    if run is not None and reason in {"", "stuck"}:
        _refresh_totals(db, run)
        if _run_cap_reached(db, run):
            reason = "run_cap"
    if reason:
        _finish(db, chat, reason)
    db.flush()
    return {
        "turn": seq,
        "stop": reason,
        **_nudge_counts(chat),
        "cost_usd": chat.cost_usd,
        "luna_tokens": chat.luna_tokens,
        "chat": chat_out(chat),
    }


def _turns_for_checks(chat: HarnessChat, turns: list[HarnessTurn]) -> list[dict]:
    passages = {
        block.get("id"): _as_dict(block.get("data")).get("passage_text")
        for block in _as_list(_as_dict(chat.settings_copy).get("blocks"))
        if isinstance(block, dict) and block.get("type") == "passage_ela" and block.get("id")
    }
    rows = []
    for turn in turns:
        after = turn.session_after if isinstance(turn.session_after, dict) else {}
        before = turn.session_before if isinstance(turn.session_before, dict) else {}
        rows.append(
            {
                "intent": turn.intent,
                "child_text": turn.child_text,
                "tutor_reply": after.get("tutor_reply") or "",
                "passage_text": passages.get(before.get("block_id")),
                "prompt": after.get("prompt") or "",
                "passed": bool(after.get("passed")),
                "loop_result": after.get("loop_result") if isinstance(after.get("loop_result"), dict) else {},
                "attempt_before": before.get("move_attempts"),
                "attempt_after": after.get("move_attempts"),
                "block_id": after.get("block_id") or "",
                "block_before": before.get("block_id") or "",
                "substep": after.get("substep") or "",
                "substep_before": before.get("substep") or "",
                "safety_flag": after.get("safety_flag") or "none",
                "error": after.get("error") or "",
                "expected": before.get("expected") or "",
            }
        )
        if "topic_index" in after:
            rows[-1]["topic_index"] = after.get("topic_index")
        if "topic_index" in before:
            rows[-1]["topic_before"] = before.get("topic_index")
    return rows


def _finish(db: Session, chat: HarnessChat, reason: str) -> None:
    if chat.status in {"completed", "cancelled", "failed"}:
        return
    chat.ended_how = reason
    chat.pending_nudges = 0
    chat.stuck_answers = 0
    chat.status = "failed" if reason == "route_error" else "completed"
    chat.updated_at = _now()
    if reason in {"scenario_not_reached", "cap", "luna_ceiling", "turn_limit", "stuck", "quit", "safety", "cancelled", "run_cap"}:
        _close_session(db, chat)
    snapshot = chat.child_snapshot if isinstance(chat.child_snapshot, dict) else {}
    profile = snapshot.get("child_profile") if isinstance(snapshot.get("child_profile"), dict) else {}
    checks = automatic_checks(
        _turns_for_checks(chat, _saved_turns(db, chat.id)),
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
        db.flush()
        _settle_inactive_run(db, run)


def finish_chat(db: Session, chat_id: uuid.UUID, reason: str, claim_generation: int | None = None) -> dict:
    chat = _locked_chat(db, chat_id)
    if claim_generation is not None:
        _check_turn_owner(chat, {"claim_generation": claim_generation})
    if chat.pending_turn:
        raise HTTPException(status_code=409, detail="Recover the pending submission before closing the chat.")
    allowed = {"scenario_not_reached", "completed", "quit", "turn_limit", "stuck", "cap", "luna_ceiling", "route_error", "safety", "cancelled", "run_cap"}
    chosen = reason if reason in allowed else "completed"
    _refresh_chat_cost(db, chat)
    _finish(db, chat, chosen)
    db.flush()
    return chat_detail(db, chat)






def _evaluation_out(row: HarnessEvaluation) -> dict:
    scores = row.scores if isinstance(row.scores, dict) else {}
    items = scores.get("items") if isinstance(row.scores, dict) else row.scores
    return {
        "id": row.id,
        "kind": row.kind,
        "checks": row.checks if isinstance(row.checks, dict) else {},
        "scores": items if isinstance(items, list) else [],
        "error": str(scores.get("error") or ""),
        "tags": row.tags if isinstance(row.tags, list) else [],
        "rubric_version": row.rubric_version,
        "judge_model": row.judge_model,
        "child_realism": row.child_realism,
        "usage": _judge_usage(scores.get("usage")),
        "created_at": row.created_at,
    }


def _saved_turns(db: Session, chat_id: uuid.UUID) -> list[HarnessTurn]:
    return list(db.scalars(select(HarnessTurn).where(HarnessTurn.chat_id == chat_id).order_by(HarnessTurn.seq)))


def _saved_evaluations(db: Session, chat: HarnessChat, turns: list[HarnessTurn]) -> list[dict]:
    rows = db.scalars(
        select(HarnessEvaluation)
        .where(HarnessEvaluation.chat_id == chat.id)
        .order_by(HarnessEvaluation.created_at, HarnessEvaluation.id)
    )
    reviews = [_evaluation_out(row) for row in rows]
    for review in reviews:
        checks = review["checks"]
        if (review["kind"] == "automatic" and checks.get("version") in ("1", "2")
                and checks.get("turns") == len(turns)):
            # Refresh only side-action diagnostics from that chat's saved
            # snapshots. Keep the stored review, model grades and original version.
            derived = side_action_checks(_turns_for_checks(chat, turns), checks.get("false_fails"))
            review["checks"] = {**checks, **derived,
                                "side_checks_version": CHECKS_VERSION}
    return reviews


def chat_detail(db: Session, chat: HarnessChat, *, include_run_cap: bool = True) -> dict:
    turns = _saved_turns(db, chat.id)
    reviews = _saved_evaluations(db, chat, turns)
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
    prompt_counts = Counter(str(row.message_id) for row in prompts if row.message_id)
    prompts_by_message = {str(row.message_id): row for row in prompts if prompt_counts[str(row.message_id)] == 1}
    reply_ids = [reply_message_id(turn.session_before, turn.session_after) for turn in turns]
    reply_counts = Counter(reply_ids)
    body = chat_out(chat)
    if include_run_cap:
        run = _run_or_404(db, chat.run_id)
        body["run_cap_reached"] = _run_cap_reached(db, run)
        body["judge_budget_reached"] = (
            body["run_cap_reached"] or chat.ended_how in {"cap", "luna_ceiling", "run_cap"}
            or bool(_chat_budget_stop(chat, run))
        )
    body["model_prompts"] = [
        {"id": str(row.id), "message_id": str(row.message_id) if row.message_id else None,
         "seq": row.seq, "model": row.model, "system_prompt": row.system_prompt} for row in prompts
    ]
    body["turns"] = []
    for turn, message_id in zip(turns, reply_ids, strict=True):
        prompt = prompts_by_message.get(message_id) if message_id and reply_counts[message_id] == 1 else None
        after = turn.session_after if isinstance(turn.session_after, dict) else {}
        decision = ""
        if not str(after.get("tutor_reply") or "").strip() or after.get("error"):
            after = {**after, "tutor_message_id": None, "tutor_call_kind": None, "prompt": "", "passed": False,
                     "loop_decision": "", "loop_result": None, "safety_flag": "none"}
        else:
            decision = after.get("loop_decision") or ""
            if not decision and prompt and isinstance(prompt.decision, dict):
                decision = prompt.decision.get("loop_decision") or ""
        body["turns"].append({
            "seq": turn.seq,
            "intent": turn.intent,
            "child_text": turn.child_text,
            "child_prompt": turn.child_prompt or "",
            "tutor_prompt": prompt.system_prompt if prompt else "",
            "inner_state": turn.inner_state if isinstance(turn.inner_state, dict) else {},
            "session_before": turn.session_before if isinstance(turn.session_before, dict) else {},
            "session_after": {**after, "prompt": prompt.system_prompt if prompt else ""},
            "child_tokens": turn.child_tokens if isinstance(turn.child_tokens, dict) else {},
            "elapsed_ms": turn.elapsed_ms,
            "loop_decision": decision,
        })
    body["evaluations"] = reviews
    body["safety_flags"] = flags
    body["settings_copy"] = dict(chat.settings_copy or {})
    if chat.session_id is not None:
        score, outcomes = _block_score(db, chat)
        body["component_score"] = score
        body["block_outcomes"] = outcomes
    return body


def get_chat(db: Session, chat_id: uuid.UUID) -> dict:
    chat = db.get(HarnessChat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    return chat_detail(db, chat)


def _llm_calls(db: Session, chat: HarnessChat, prompts: list[dict]) -> list[dict]:
    if chat.session_id is None:
        return []
    usage = session_token_usage(db, chat.session_id)["turns"]
    prompt_counts = Counter(prompt["message_id"] for prompt in prompts)
    usage_counts = Counter(str(row["message_id"]) for row in usage if row["message_id"])
    usage_by_message = {str(row["message_id"]): row for row in usage if row["message_id"]}

    def usage_fields(row: dict) -> dict:
        incoming, outgoing = row["input_tokens"], row["output_tokens"]
        billed = min(row["cached_tokens"], incoming)
        return {
            "usage_id": str(row["id"]), "message_id": str(row["message_id"]) if row["message_id"] else None,
            "model": row["model"], "kind": row["kind"], "input_tokens": incoming,
            "output_tokens": outgoing, "cached_tokens": row["cached_tokens"],
            "cost_usd": _model_cost(row["model"], incoming - billed, billed, outgoing),
        }

    calls = []
    linked_usage = set()
    for prompt in prompts:
        message_id = prompt["message_id"]
        call = {"prompt_id": prompt["id"], "message_id": message_id,
                "model": prompt["model"], "system_prompt": prompt["system_prompt"]}
        if message_id and prompt_counts[message_id] == usage_counts[message_id] == 1:
            row = usage_by_message[message_id]
            if not prompt["model"] or not row["model"] or prompt["model"] == row["model"]:
                call.update(usage_fields(row))
                call["model"] = row["model"] or prompt["model"]
                linked_usage.add(row["id"])
        calls.append(call)
    calls.extend(usage_fields(row) for row in usage if row["id"] not in linked_usage)
    return calls


def _download_payload(db: Session, chat: HarnessChat) -> dict:
    body = chat_detail(db, chat, include_run_cap=False)
    if chat.pending_turn:
        pending = chat.pending_turn
        receipt = _answer_receipt(db, chat, pending["turn_id"])
        body["pending_delivery"] = {
            "turn_id": pending["turn_id"], "seq": pending["seq"], "child_text": pending["child_text"],
            "receipt_status": receipt.status if receipt else "unknown",
        }
    body["llm_calls"] = _llm_calls(db, chat, body["model_prompts"])
    return body


def _run_stamp(run: HarnessRun) -> dict:
    plan = dict(run.plan or {})
    return {"id": str(run.id), "status": run.status, "code_version": run.code_version,
            "seed": plan.get("seed"), "pair_tutor_seeds": plan.get("pair_tutor_seeds")}


def download_chat(db: Session, chat_id: uuid.UUID) -> str:
    chat = db.get(HarnessChat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    run = _run_or_404(db, chat.run_id)
    return render_download(_run_stamp(run), [_download_payload(db, chat)])


def download_run(db: Session, run_id: uuid.UUID) -> str:
    run = _run_or_404(db, run_id)
    chats = db.scalars(select(HarnessChat).where(HarnessChat.run_id == run.id).order_by(HarnessChat.created_at)).all()
    return render_download(_run_stamp(run), [_download_payload(db, chat) for chat in chats])


def _block_score(db: Session, chat: HarnessChat) -> tuple[int | None, list[dict]]:
    """The component score and each block outcome stored on the session."""
    if chat.session_id is None:
        return None, []
    session = db.get(KcSession, chat.session_id)
    if session is None:
        return None, []
    modern = session.scoring_version >= REQUIREMENT_SCORE
    outcomes = []
    for row in session.block_results or []:
        if not isinstance(row, dict):
            continue
        stored = str(row.get("outcome") or "").strip()
        verdict = str(row.get("verdict") or "").strip()
        # An older loop label may survive an interrupted requirement-score write.
        # A raw pass needs independent evidence; bare engagement and reveal are observations.
        requirements = row.get("requirements")
        recover_verdict = modern and not verdict and (
            stored == "passed" or (
                stored in {"", "revealed", "engaged"} and isinstance(requirements, list) and bool(requirements)
            )
        )
        if (verdict or stored) in {"known", "fragile", "unassessed"} or recover_verdict:
            outcome, _ = classify_stored_outcome(row, session.scoring_version)
        elif not verdict and stored in LEGACY_OUTCOMES:
            outcome = stored
        else:
            outcome = "unknown"
        title = str(row.get("title") or row.get("block_type") or "block").strip() or "block"
        result = {"title": title, "outcome": outcome}
        if modern and stored in LEGACY_OUTCOMES and outcome not in {stored, "unknown"}:
            result["stored_outcome"] = stored
        if row.get("revealed") is True:
            result["revealed"] = True
        outcomes.append(result)
    return session.score, outcomes








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
    def load(code, document):
        course = db.scalar(select(KcGoal).where(KcGoal.code == code))
        if course is None:
            course = import_new_course(db, document())
        if not course.ready:
            mark_ready(db, course)
        return course

    base = load(FIXTURE_CODE, fixture_document)
    load(SCENARIO_FIXTURE_CODE, scenario_fixture_document)
    body = course_out(db, base)
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
    kept: set[str] = set()
    for suite in suites:
        baseline = str(suite.get("baseline_run_id") or "")
        if baseline:
            kept.add(baseline)
        if suite["run_ids"]:
            kept.add(suite["run_ids"][-1])
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


