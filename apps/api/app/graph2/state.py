"""Dual-plane Graph-2 persistence, slow EMA, observation ledger, frozen note, and radar.

Standing rules enforced here:
- Harness / test children (`student.is_test == True` or `HarnessChat` linkage) are
  NEVER written into `student_educational_state`, `learner_course_state`, or `skill_observation`.
- One scale (0-3 -> y = grade / 3 -> caps -> slow EMA from 0.50).
- A revealed/giveaway block can NEVER raise a spoke.
- Spokes with fewer than 3 observations remain hollow and labeled "not enough yet";
  the starting 0.50 is never returned as a drawable radar value.
- Never imports `app.kc_prompt`, `app.kc_loop`, `app.kc`, or `app.block_score`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.block_catalog import SKILL_KEYS
from app.graph2.digest import compose_tutor_note
from app.graph2.judge import build_judge_bundle, validate_judge_output
from app.graph2.signals import (
    MIN_OBSERVATIONS_FOR_RADAR,
    PRIOR_SCORE,
    SKILL_LABELS,
    CloseAnalysis,
    analyze_component_close,
)
from app.mastery import actionable_spec, spec_requested_skills, stored_spec
from app.models import (
    HarnessChat,
    KcGoal,
    KcMessage,
    KcNode,
    KcSession,
    KcState,
    LearnerCourseState,
    SkillObservation,
    Student,
    StudentEducationalState,
)

EMA_ALPHA_FLOOR = 0.08
_MAX_COURSE_MISCONCEPTIONS = 20
_MAX_UNLOCK_NOTES = 25


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_skills_map() -> dict[str, dict]:
    return {
        skill: {
            "score": PRIOR_SCORE,
            "count": 0,
            "last_evidence": None,
            "last_observed_at": None,
        }
        for skill in SKILL_KEYS
    }


def _normalized_skills_map(raw: object) -> dict[str, dict]:
    base = _default_skills_map()
    if not isinstance(raw, dict):
        return base
    for skill in SKILL_KEYS:
        item = raw.get(skill)
        if not isinstance(item, dict):
            continue
        try:
            score = float(item.get("score", PRIOR_SCORE))
        except (TypeError, ValueError):
            score = PRIOR_SCORE
        try:
            count = max(0, int(item.get("count", 0)))
        except (TypeError, ValueError):
            count = 0
        base[skill] = {
            "score": round(max(0.0, min(1.0, score)), 4),
            "count": count,
            "last_evidence": item.get("last_evidence"),
            "last_observed_at": item.get("last_observed_at"),
        }
    return base


def slow_ema_step(score: float, count: int, y: float, *, revealed_or_giveaway: bool = False) -> tuple[float, float]:
    """Compute (alpha, new_score) using alpha = max(0.08, 1 / (n + 3)).

    Guarantees a revealed/giveaway block can never raise a spoke even if score < 0.20.
    """
    n = max(0, int(count))
    alpha = max(EMA_ALPHA_FLOOR, 1.0 / (n + 3))
    updated = (1.0 - alpha) * float(score) + alpha * float(y)
    if revealed_or_giveaway:
        updated = min(updated, float(score))
    updated = round(max(0.0, min(1.0, updated)), 4)
    return round(alpha, 6), updated


def is_harness_student_or_session(
    db: Session,
    student: Student | None = None,
    session: KcSession | None = None,
) -> bool:
    """True when the learner or session belongs to the test harness."""
    if student is not None and bool(getattr(student, "is_test", False)):
        return True
    if session is not None:
        if student is None:
            stud = db.get(Student, session.student_id)
            if stud is not None and bool(getattr(stud, "is_test", False)):
                return True
        linked = db.scalar(select(HarnessChat.id).where(HarnessChat.session_id == session.id).limit(1))
        if linked is not None:
            return True
    return False


def _get_or_create_edu_state(db: Session, student_id: uuid.UUID) -> StudentEducationalState:
    row = db.get(StudentEducationalState, student_id)
    if row is None:
        row = StudentEducationalState(
            student_id=student_id,
            skills=_default_skills_map(),
            hint_uptake={"independent": 0, "assisted": 0, "revealed": 0, "attempts": 0},
            block_affinity={},
            expression_stats={"sessions": 0, "turns": 0, "total_words": 0, "questions": 0},
            biomarkers={
                "own_words_pass": 0,
                "hard_recovery_pass": 0,
                "on_topic_inquiry_before_known": 0,
                "multi_perspective_synthesis": 0,
            },
            tutor_note="",
        )
        db.add(row)
        db.flush()
    return row


def _get_or_create_course_state(
    db: Session, student_id: uuid.UUID, goal_id: uuid.UUID
) -> LearnerCourseState:
    row = db.scalar(
        select(LearnerCourseState).where(
            LearnerCourseState.student_id == student_id,
            LearnerCourseState.goal_id == goal_id,
        )
    )
    if row is None:
        row = LearnerCourseState(
            student_id=student_id,
            goal_id=goal_id,
            misconceptions=[],
            unlock_notes=[],
            analogies_worked=[],
        )
        db.add(row)
        db.flush()
    return row


def _next_component_in_course(db: Session, student_id: uuid.UUID, goal: KcGoal | None, current_kc_id: uuid.UUID) -> KcNode | None:
    if goal is None:
        return None
    raw_ids = goal.target_kc_ids if isinstance(goal.target_kc_ids, list) else []
    target_uuids: list[uuid.UUID] = []
    for item in raw_ids:
        try:
            target_uuids.append(uuid.UUID(str(item)))
        except ValueError:
            continue
    if not target_uuids:
        return None
    # Prefer the first component after current_kc_id in course order that is not yet known.
    known_ids = set(
        db.scalars(
            select(KcState.kc_id).where(
                KcState.student_id == student_id,
                KcState.kc_id.in_(target_uuids),
                KcState.status == "known",
            )
        ).all()
    )
    start_idx = 0
    if current_kc_id in target_uuids:
        start_idx = target_uuids.index(current_kc_id) + 1
    ordered = [*target_uuids[start_idx:], *target_uuids[:start_idx]]
    for cid in ordered:
        if cid != current_kc_id and cid not in known_ids:
            node = db.get(KcNode, cid)
            if node is not None:
                return node
    return None


def _session_messages_dicts(db: Session, session_id: uuid.UUID) -> list[dict]:
    rows = db.scalars(
        select(KcMessage).where(KcMessage.session_id == session_id).order_by(KcMessage.seq)
    ).all()
    return [
        {"role": msg.role, "content": msg.content, "step": int(msg.step or 0), "seq": int(msg.seq or 0)}
        for msg in rows
    ]


def copy_note_for_session_open(
    db: Session,
    *,
    student: Student,
    goal: KcGoal,
    node: KcNode,
) -> str:
    """Return the frozen 3-line tutor note to copy onto a newly opened session.

    Harness children receive "". If an existing note on `student_educational_state`
    was already generated for this exact component, copy it verbatim; otherwise
    compose the note from stored skill averages and course misconceptions for
    this component's requested claims.
    """
    if is_harness_student_or_session(db, student=student):
        return ""
    edu = db.get(StudentEducationalState, student.id)
    if edu is None:
        return ""
    if edu.tutor_note_component_id == node.id and edu.tutor_note_course_id == goal.id:
        return str(edu.tutor_note or "")
    course_state = db.scalar(
        select(LearnerCourseState).where(
            LearnerCourseState.student_id == student.id,
            LearnerCourseState.goal_id == goal.id,
        )
    )
    spec = stored_spec(node)
    requested = spec_requested_skills(spec)
    return compose_tutor_note(
        skills_state=_normalized_skills_map(edu.skills),
        next_component_skills=requested,
        course_misconceptions=course_state.misconceptions if course_state is not None else [],
    )


def apply_sync_close(
    db: Session,
    *,
    session: KcSession,
    student: Student,
    goal: KcGoal | None,
    node: KcNode,
    blocks: list[dict],
    messages: list[dict] | None = None,
) -> dict:
    """Synchronous component-close step (no model call).

    Updates biomarkers (3 sync), hint uptake, block affinity, expression stats,
    and misconceptions; persists the child's end card and marks whether the
    post-reply batch judge should run. Harness children are a strict no-op.
    """
    if is_harness_student_or_session(db, student=student, session=session):
        session.close_end_card = None
        session.graph2_judge_status = "skipped"
        return {"end_card": None, "judge_pending": False}

    # Idempotency guard: if sync close already ran for this session, return stored snapshot.
    if session.graph2_judge_status in {"pending", "completed", "failed", "skipped"}:
        return {
            "end_card": session.close_end_card,
            "judge_pending": session.graph2_judge_status == "pending",
        }

    edu = _get_or_create_edu_state(db, student.id)
    prior_skills = _normalized_skills_map(edu.skills)
    msg_list = messages if messages is not None else _session_messages_dicts(db, session.id)
    spec = stored_spec(node)
    verdict = str(session.verdict or "")
    if not verdict:
        state_row = db.scalar(
            select(KcState).where(KcState.student_id == student.id, KcState.kc_id == node.id)
        )
        verdict = state_row.status if state_row is not None else ""

    analysis: CloseAnalysis = analyze_component_close(
        mastery_spec=spec,
        blocks=blocks,
        block_results=list(session.block_results or []),
        messages=msg_list,
        component_verdict=verdict,
        last_misconception=str(session.last_misconception or ""),
        off_course_count=int(session.off_course_count or 0),
        prior_skills=prior_skills,
    )

    now_iso = _utcnow().isoformat()

    # 1. Update hint uptake
    uptake = dict(edu.hint_uptake or {})
    for key, delta in analysis.hint_uptake_deltas.items():
        uptake[key] = int(uptake.get(key) or 0) + int(delta)
    edu.hint_uptake = uptake

    # 2. Update block affinity
    affinity = {k: dict(v) for k, v in (edu.block_affinity or {}).items() if isinstance(v, dict)}
    for btype, deltas in analysis.block_affinity_deltas.items():
        slot = affinity.setdefault(btype, {"completed": 0, "independent": 0, "revealed": 0})
        for field_name, delta in deltas.items():
            slot[field_name] = int(slot.get(field_name) or 0) + int(delta)
    edu.block_affinity = affinity

    # 3. Update expression stats
    expr = dict(edu.expression_stats or {})
    expr["sessions"] = int(expr.get("sessions") or 0) + 1
    expr["turns"] = int(expr.get("turns") or 0) + int(analysis.expression_sample.get("turns") or 0)
    expr["total_words"] = int(expr.get("total_words") or 0) + int(analysis.expression_sample.get("total_words") or 0)
    expr["questions"] = int(expr.get("questions") or 0) + int(analysis.expression_sample.get("questions") or 0)
    expr["avg_words"] = round(expr["total_words"] / expr["turns"], 2) if expr["turns"] > 0 else 0.0
    edu.expression_stats = expr

    # 4. Update synchronous biomarkers (3 sync biomarkers; 4th comes only from judge)
    bio = dict(edu.biomarkers or {})
    for key in ("own_words_pass", "hard_recovery_pass", "on_topic_inquiry_before_known"):
        if analysis.biomarkers.get(key):
            bio[key] = int(bio.get(key) or 0) + 1
    bio.setdefault("multi_perspective_synthesis", int(bio.get("multi_perspective_synthesis") or 0))
    edu.biomarkers = bio
    edu.updated_at = _utcnow()

    # 5. Update course-scoped misconceptions & unlock notes
    if goal is not None:
        cstate = _get_or_create_course_state(db, student.id, goal.id)
        existing_misc = [dict(m) for m in (cstate.misconceptions or []) if isinstance(m, dict)]
        existing_texts = {str(m.get("text") or "").strip().lower() for m in existing_misc if not m.get("resolved")}
        for text in analysis.misconceptions:
            if text.strip().lower() not in existing_texts:
                existing_misc.append(
                    {
                        "text": text[:240],
                        "kc_id": str(node.id),
                        "session_id": str(session.id),
                        "seen_at": now_iso,
                        "resolved": False,
                    }
                )
                existing_texts.add(text.strip().lower())
        cstate.misconceptions = existing_misc[-_MAX_COURSE_MISCONCEPTIONS:]

        fired_sync = [k for k, v in analysis.biomarkers.items() if v]
        if fired_sync:
            unlocks = [dict(u) for u in (cstate.unlock_notes or []) if isinstance(u, dict)]
            unlocks.append(
                {
                    "kc_id": str(node.id),
                    "session_id": str(session.id),
                    "biomarkers": fired_sync,
                    "recorded_at": now_iso,
                }
            )
            cstate.unlock_notes = unlocks[-_MAX_UNLOCK_NOTES:]
        cstate.updated_at = _utcnow()

    session.close_end_card = analysis.end_card
    judge_pending = bool(analysis.actionable and analysis.eligible_skills)
    session.graph2_judge_status = "pending" if judge_pending else "skipped"
    db.flush()
    return {"end_card": analysis.end_card, "judge_pending": judge_pending}


def prepare_judge_request(db: Session, session: KcSession) -> dict:
    """Return the single batch-judge prompt + schema for a closed session, or skipped=True."""
    student = db.get(Student, session.student_id)
    if student is None or is_harness_student_or_session(db, student=student, session=session):
        return {"skipped": True, "reason": "harness_or_missing"}
    if session.status != "completed":
        return {"skipped": True, "reason": "session_not_completed"}
    if session.graph2_judge_status == "completed":
        return {"skipped": True, "reason": "already_completed"}

    node = db.get(KcNode, session.kc_id)
    if node is None:
        return {"skipped": True, "reason": "missing_component"}
    spec = stored_spec(node)
    if not actionable_spec(spec):
        session.graph2_judge_status = "skipped"
        db.flush()
        return {"skipped": True, "reason": "empty_mastery_spec"}

    blocks = [b for b in (node.blocks or []) if isinstance(b, dict)]
    messages = _session_messages_dicts(db, session.id)
    analysis = analyze_component_close(
        mastery_spec=spec,
        blocks=blocks,
        block_results=list(session.block_results or []),
        messages=messages,
        component_verdict=str(session.verdict or ""),
        last_misconception=str(session.last_misconception or ""),
        off_course_count=int(session.off_course_count or 0),
    )
    if not analysis.eligible_skills:
        session.graph2_judge_status = "skipped"
        db.flush()
        return {"skipped": True, "reason": "no_eligible_skills"}

    bundle = build_judge_bundle(
        component_title=node.title,
        eligible_skills=analysis.eligible_skills,
    )
    return {
        "skipped": False,
        "session_id": str(session.id),
        **bundle,
    }


def apply_judge_results(db: Session, session: KcSession, raw_output: dict) -> dict:
    """Validate batch judge grades, apply caps + slow EMA, log observations, and write next note.

    Idempotent per `(session_id, skill)`: duplicate submissions do not double-count.
    Harness children are never written.
    """
    student = db.get(Student, session.student_id)
    if student is None or is_harness_student_or_session(db, student=student, session=session):
        return {"applied": False, "reason": "harness_or_missing", "observations": []}
    if session.status != "completed":
        raise ValueError("Cannot apply judge results to an in-progress session.")

    existing_obs = db.scalars(
        select(SkillObservation).where(SkillObservation.session_id == session.id)
    ).all()
    if session.graph2_judge_status == "completed" or existing_obs:
        session.graph2_judge_status = "completed"
        db.flush()
        return {
            "applied": False,
            "already_applied": True,
            "observations": [
                {
                    "skill": row.skill,
                    "rubric_grade": row.rubric_grade,
                    "capped_y": row.capped_y,
                    "score_after": row.score_after,
                    "quote": row.quote,
                }
                for row in existing_obs
            ],
        }

    node = db.get(KcNode, session.kc_id)
    if node is None:
        raise ValueError("Component not found for session.")
    spec = stored_spec(node)
    if not actionable_spec(spec):
        session.graph2_judge_status = "skipped"
        db.flush()
        return {"applied": False, "reason": "empty_mastery_spec", "observations": []}

    blocks = [b for b in (node.blocks or []) if isinstance(b, dict)]
    messages = _session_messages_dicts(db, session.id)
    analysis = analyze_component_close(
        mastery_spec=spec,
        blocks=blocks,
        block_results=list(session.block_results or []),
        messages=messages,
        component_verdict=str(session.verdict or ""),
        last_misconception=str(session.last_misconception or ""),
        off_course_count=int(session.off_course_count or 0),
    )
    validated = validate_judge_output(raw_output, analysis.eligible_skills)

    edu = _get_or_create_edu_state(db, student.id)
    skills_map = _normalized_skills_map(edu.skills)
    now = _utcnow()
    now_iso = now.isoformat()

    created_rows: list[dict] = []
    for graded in validated.grades:
        ev = analysis.eligible_skills[graded.skill]
        slot = skills_map[graded.skill]
        score_before = float(slot["score"])
        obs_count = int(slot["count"])
        _alpha, score_after = slow_ema_step(
            score_before,
            obs_count,
            graded.capped_y,
            revealed_or_giveaway=ev.revealed_or_giveaway,
        )
        obs_row = SkillObservation(
            student_id=student.id,
            session_id=session.id,
            goal_id=session.goal_id,
            kc_id=node.id,
            block_id=ev.block_id,
            block_type=ev.block_type,
            claim_id=ev.claim_id,
            skill=graded.skill,
            rubric_grade=graded.rubric_grade,
            raw_y=graded.raw_y,
            cap_applied=graded.cap_applied,
            capped_y=graded.capped_y,
            score_before=score_before,
            score_after=score_after,
            obs_index=obs_count + 1,
            quote=graded.quote,
        )
        db.add(obs_row)
        skills_map[graded.skill] = {
            "score": score_after,
            "count": obs_count + 1,
            "last_evidence": {
                "quote": graded.quote,
                "component_id": str(node.id),
                "component_title": node.title,
                "block_id": ev.block_id,
                "block_type": ev.block_type,
                "rubric_grade": graded.rubric_grade,
                "capped_y": graded.capped_y,
                "cap_applied": graded.cap_applied,
            },
            "last_observed_at": now_iso,
        }
        created_rows.append(
            {
                "skill": graded.skill,
                "rubric_grade": graded.rubric_grade,
                "raw_y": graded.raw_y,
                "cap_applied": graded.cap_applied,
                "capped_y": graded.capped_y,
                "score_before": score_before,
                "score_after": score_after,
                "obs_index": obs_count + 1,
                "quote": graded.quote,
            }
        )

    edu.skills = skills_map
    if validated.multi_perspective_synthesis:
        bio = dict(edu.biomarkers or {})
        bio["multi_perspective_synthesis"] = int(bio.get("multi_perspective_synthesis") or 0) + 1
        edu.biomarkers = bio

    # Compose and store the three-line note for the following component (does NOT touch any open session!).
    goal = db.get(KcGoal, session.goal_id) if session.goal_id else None
    next_node = _next_component_in_course(db, student.id, goal, node.id)
    next_skills = spec_requested_skills(stored_spec(next_node)) if next_node is not None else []
    course_state = (
        db.scalar(
            select(LearnerCourseState).where(
                LearnerCourseState.student_id == student.id,
                LearnerCourseState.goal_id == session.goal_id,
            )
        )
        if session.goal_id
        else None
    )
    next_note = compose_tutor_note(
        skills_state=skills_map,
        next_component_skills=next_skills,
        course_misconceptions=course_state.misconceptions if course_state is not None else [],
    )
    edu.tutor_note = next_note
    edu.tutor_note_component_id = next_node.id if next_node is not None else None
    edu.tutor_note_course_id = goal.id if goal is not None else None
    edu.updated_at = now
    session.graph2_judge_status = "completed"
    db.flush()

    return {
        "applied": True,
        "observations": created_rows,
        "multi_perspective_synthesis": validated.multi_perspective_synthesis,
        "next_note": next_note,
    }


def mark_judge_failed(db: Session, session: KcSession) -> dict:
    """Record judge failure cleanly. Sync biomarkers, end card, and prior note remain untouched."""
    if session.graph2_judge_status != "completed":
        session.graph2_judge_status = "failed"
        db.flush()
    return {"status": session.graph2_judge_status}


def build_radar_payload(db: Session, student_id: uuid.UUID) -> dict:
    """One shared eight-spoke radar payload for both parent dashboard and child progress.

    Spokes with fewer than 3 real observations are hollow (`score: None`,
    `hollow: True`, `status_label: "not enough yet"`). The starting 0.50 is NEVER drawn.
    """
    edu = db.get(StudentEducationalState, student_id)
    skills_map = _normalized_skills_map(edu.skills if edu is not None else None)
    spokes: list[dict] = []
    for skill in SKILL_KEYS:
        slot = skills_map[skill]
        count = int(slot.get("count") or 0)
        ready = count >= MIN_OBSERVATIONS_FOR_RADAR
        last_ev = slot.get("last_evidence") if isinstance(slot.get("last_evidence"), dict) else None
        spokes.append(
            {
                "skill": skill,
                "label": SKILL_LABELS.get(skill, skill.title()),
                "count": count,
                "ready": ready,
                "hollow": not ready,
                "score": round(float(slot["score"]), 4) if ready else None,
                "status_label": None if ready else "not enough yet",
                "last_quote": str(last_ev.get("quote") or "") if (ready and last_ev) else None,
                "last_observed_at": slot.get("last_observed_at"),
            }
        )
    return {
        "student_id": str(student_id),
        "min_observations": MIN_OBSERVATIONS_FOR_RADAR,
        "spokes": spokes,
    }
