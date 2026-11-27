"""F6: Active Parent Co-Pilot digests, course policy locks, and revocable Teacher Share snapshots.

Standing invariants:
- Harness / test children (`is_harness_student_or_session`) NEVER write digests or teacher shares.
- Parent interventions write ONLY to `learner_course_state.parent_policy_locks` / `course_mode`,
  NEVER mutating shared `tutor_profiles` or active in-progress `kc_sessions`.
- Teacher Share stores ONLY the SHA-256 hash of each generated token (`token_hash`), returns the
  raw token once on creation, immediately 404s revoked or expired tokens, and NEVER exposes raw
  chat messages, model prompts, or token usage.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blind_evaluator import course_exam_summary
from app.graph2.state import (
    _get_or_create_course_state,
    build_radar_payload,
    is_harness_student_or_session,
)
from app.models import (
    KcGoal,
    KcNode,
    KcSession,
    KcState,
    LearnerCourseState,
    ParentSessionDigest,
    Student,
    StudentEducationalState,
    TeacherShareToken,
)
from app.parents import require_linked_child

TRAJECTORY_STATES = (
    "flourishing",
    "steady_progress",
    "needs_reinforcement",
    "struggling",
    "returning",
)

COURSE_MODES = ("explore", "mastery", "exam_prep")

TRAJECTORY_META: dict[str, dict[str, str]] = {
    "flourishing": {
        "label": "Flourishing",
        "description": "Independent mastery with strong own-words explanations and curiosity.",
    },
    "steady_progress": {
        "label": "Steady Progress",
        "description": "Moving reliably through topics with healthy challenge.",
    },
    "needs_reinforcement": {
        "label": "Needs Reinforcement",
        "description": "Building understanding; a couple of ideas would benefit from another pass.",
    },
    "struggling": {
        "label": "Extra Support Needed",
        "description": "Hit repeated hints or reveals recently — gentler pacing or more examples can help.",
    },
    "returning": {
        "label": "Welcome Back",
        "description": "Returning after a break — light warm-up review helps lock prior ideas back in.",
    },
}

DEFAULT_SHARE_TTL_DAYS = 30
MAX_SHARE_TTL_DAYS = 180
MAX_INTEREST_LEN = 80
ALLOWED_LOCK_KEYS = {
    "more_guided_examples",
    "gentler_socratic",
    "stretch_challenge",
    "anchor_in_interest",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def hash_share_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _first_name(display_name: str | None) -> str:
    parts = (display_name or "").strip().split()
    return parts[0] if parts else "Learner"


def _course_or_404(db: Session, course_id: uuid.UUID) -> KcGoal:
    goal = db.get(KcGoal, course_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="That course was not found.")
    return goal


def _goal_kc_uuids(goal: KcGoal) -> list[uuid.UUID]:
    raw = goal.target_kc_ids if isinstance(goal.target_kc_ids, list) else []
    out: list[uuid.UUID] = []
    for item in raw:
        try:
            uid = uuid.UUID(str(item))
            if uid not in out:
                out.append(uid)
        except ValueError:
            continue
    return out


def normalize_parent_locks(raw: dict | None, existing: dict | None = None) -> dict:
    """Validate and merge parent policy lock overrides (rejecting unknown keys)."""
    if raw is None:
        return dict(existing or {})
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="locks must be an object.")
    unknown = [k for k in raw.keys() if k not in ALLOWED_LOCK_KEYS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported policy lock key(s): {', '.join(sorted(unknown))}.")
    merged = {k: v for k, v in (existing or {}).items() if k in ALLOWED_LOCK_KEYS}
    for key in ("more_guided_examples", "gentler_socratic", "stretch_challenge"):
        if key in raw:
            val = raw[key]
            if not isinstance(val, bool):
                raise HTTPException(status_code=422, detail=f"{key} must be a boolean.")
            if val:
                merged[key] = True
            else:
                merged.pop(key, None)
    if "anchor_in_interest" in raw:
        val = raw["anchor_in_interest"]
        if val is None or str(val).strip() == "":
            merged.pop("anchor_in_interest", None)
        else:
            cleaned = " ".join(str(val).split())[:MAX_INTEREST_LEN]
            merged["anchor_in_interest"] = cleaned
    return merged


def format_parent_locks_note(course_state: LearnerCourseState | None) -> str:
    """Compose at most one plain-language line for the next component's frozen tutor note.

    Returns "" when no parent locks and default mastery mode are active. Never includes
    numbers or radar scores.
    """
    if course_state is None:
        return ""
    locks = course_state.parent_policy_locks if isinstance(course_state.parent_policy_locks, dict) else {}
    mode = str(course_state.course_mode or "mastery").strip()
    clauses: list[str] = []
    if locks.get("more_guided_examples"):
        clauses.append("use extra step-by-step guided examples before asking for solo answers")
    if locks.get("gentler_socratic"):
        clauses.append("keep Socratic follow-ups gentle and reassuring")
    if locks.get("stretch_challenge"):
        clauses.append("offer a concise stretch application once the main idea clicks")
    anchor = str(locks.get("anchor_in_interest") or "").strip()
    if anchor:
        clauses.append(f"weave in {anchor} when an analogy fits naturally")
    if mode == "explore":
        clauses.append("prioritize curiosity and intuition over exam-style drilling")
    elif mode == "exam_prep":
        clauses.append("check precision and transfer on exam-style prompts")
    if not clauses:
        return ""
    return "Parent guidance: " + "; ".join(clauses) + "."


def compute_trajectory_state(
    *,
    known_count: int,
    fragile_count: int,
    biomarkers: dict | None,
    recent_reveals: int,
    active_misconceptions: int,
    days_since_prev_session: float | None = None,
    current_verdict: str = "",
) -> str:
    """Deterministic 5-state trajectory classifier for parent Co-Pilot."""
    if days_since_prev_session is not None and days_since_prev_session >= 10.0:
        return "returning"
    bio = biomarkers if isinstance(biomarkers, dict) else {}
    bio_total = sum(int(bio.get(k) or 0) for k in (
        "own_words_pass",
        "hard_recovery_pass",
        "on_topic_inquiry_before_known",
        "multi_perspective_synthesis",
    ))
    total = known_count + fragile_count
    if recent_reveals >= 2 or (total >= 2 and fragile_count > known_count):
        return "struggling"
    if current_verdict == "fragile" or fragile_count > 0 or active_misconceptions > 0:
        if known_count >= 3 and fragile_count == 0 and recent_reveals == 0 and bio_total >= 2:
            return "flourishing"
        return "needs_reinforcement"
    if known_count >= 1 and recent_reveals == 0 and bio_total >= 2:
        return "flourishing"
    return "steady_progress"


def _build_talking_points(
    *,
    student: Student,
    node: KcNode,
    goal: KcGoal | None,
    verdict: str,
    biomarkers: dict,
    misconceptions: list[dict],
) -> list[str]:
    name = _first_name(student.display_name)
    topic = (node.title or "today's topic").strip()
    core = " ".join((node.core_truth or "").split())
    course_title = (goal.title or "").strip() if goal is not None else ""
    points: list[str] = []

    if core:
        short_core = core if len(core) <= 130 else core[:127].rstrip() + "..."
        points.append(
            f'Ask {name} to teach you "{topic}" in one minute — listen for the core idea ({short_core}).'
        )
    else:
        points.append(f'Ask {name} to explain "{topic}" in their own words as if you had never heard of it.')

    active_misc = [
        str(m.get("text") or "").strip()
        for m in misconceptions
        if isinstance(m, dict) and not m.get("resolved") and str(m.get("text") or "").strip()
    ]
    if active_misc:
        points.append(
            f'Try a playful "what if?" check around a tricky spot: "{active_misc[-1]}" — ask {name} why that trap does not quite hold.'
        )
    elif verdict == "fragile":
        points.append(
            f'Revisit "{topic}" with a low-pressure everyday example at dinner and ask what part still felt tricky.'
        )
    else:
        points.append(
            f'Ask {name} to invent a real-world example of "{topic}" from daily life'
            + (f" or connect it to {course_title}." if course_title else ".")
        )

    if int(biomarkers.get("on_topic_inquiry_before_known") or 0) > 0:
        points.append(
            f'Celebrate {name}\'s curiosity — ask what "why" or "what-if" question they still wonder about next.'
        )
    elif int(biomarkers.get("hard_recovery_pass") or 0) > 0:
        points.append(
            f"Praise {name}'s persistence for working through a tough step unaided — ask what helped it click."
        )
    else:
        points.append(
            f'Ask {name}: "What surprised you most about {topic}, and what would you like to explore next?"'
        )
    return points[:3]


def _build_recommended_interventions(
    *,
    student: Student,
    trajectory_state: str,
    recent_reveals: int,
    active_locks: dict,
) -> list[dict]:
    recs: list[dict] = []
    if (trajectory_state in {"struggling", "needs_reinforcement"} or recent_reveals >= 1) and not active_locks.get(
        "more_guided_examples"
    ):
        recs.append(
            {
                "key": "more_guided_examples",
                "label": "More guided examples",
                "reason": "Adds extra step-by-step scaffolding before asking for solo answers on upcoming topics.",
                "payload": {"more_guided_examples": True},
            }
        )
    if trajectory_state == "struggling" and not active_locks.get("gentler_socratic"):
        recs.append(
            {
                "key": "gentler_socratic",
                "label": "Gentler Socratic challenge",
                "reason": "Keeps pushback warm and low-pressure while confidence rebuilds.",
                "payload": {"gentler_socratic": True},
            }
        )
    interests = [str(item).strip() for item in (student.interests or []) if str(item).strip()]
    if interests and not active_locks.get("anchor_in_interest"):
        first_interest = interests[0][:MAX_INTEREST_LEN]
        recs.append(
            {
                "key": "anchor_in_interest",
                "label": f"Anchor in {first_interest}",
                "reason": f"Encourages analogies drawn from {first_interest} on the next lesson.",
                "payload": {"anchor_in_interest": first_interest},
            }
        )
    if trajectory_state == "flourishing" and not active_locks.get("stretch_challenge"):
        recs.append(
            {
                "key": "stretch_challenge",
                "label": "Add stretch challenge",
                "reason": "Invites a concise transfer problem once core ideas land smoothly.",
                "payload": {"stretch_challenge": True},
            }
        )
    return recs[:3]


def record_parent_session_digest(
    db: Session,
    *,
    session: KcSession,
    student: Student,
    goal: KcGoal | None,
    node: KcNode,
) -> ParentSessionDigest | None:
    """Auto-persist one parent-safe digest at component close (no model call, zero harness writes)."""
    if is_harness_student_or_session(db, student=student, session=session):
        return None

    edu = db.get(StudentEducationalState, student.id)
    biomarkers = dict(edu.biomarkers or {}) if edu is not None else {
        "own_words_pass": 0,
        "hard_recovery_pass": 0,
        "on_topic_inquiry_before_known": 0,
        "multi_perspective_synthesis": 0,
    }

    cstate = (
        db.scalar(
            select(LearnerCourseState).where(
                LearnerCourseState.student_id == student.id,
                LearnerCourseState.goal_id == goal.id,
            )
        )
        if goal is not None
        else None
    )
    misconceptions = list(cstate.misconceptions or []) if cstate is not None else []
    active_locks = dict(cstate.parent_policy_locks or {}) if cstate is not None else {}

    # Inspect course mastery counts
    target_ids = _goal_kc_uuids(goal) if goal is not None else [node.id]
    states = db.scalars(
        select(KcState).where(KcState.student_id == student.id, KcState.kc_id.in_(target_ids))
    ).all() if target_ids else []
    known_count = sum(1 for row in states if row.status == "known")
    fragile_count = sum(1 for row in states if row.status == "fragile")

    # Days since previous completed session for this student
    prev_session = db.scalar(
        select(KcSession)
        .where(
            KcSession.student_id == student.id,
            KcSession.status == "completed",
            KcSession.id != session.id,
        )
        .order_by(KcSession.updated_at.desc())
        .limit(1)
    )
    days_since_prev: float | None = None
    if prev_session is not None and prev_session.updated_at is not None:
        now_dt = _utcnow()
        prev_dt = _aware(prev_session.updated_at)
        if prev_dt is not None:
            days_since_prev = max(0.0, (now_dt - prev_dt).total_seconds() / 86400.0)

    verdict = str(session.verdict or "")
    if not verdict:
        cur_state = next((row for row in states if row.kc_id == node.id), None)
        verdict = cur_state.status if cur_state is not None else ""
    reveals = int(session.reveals or 0)
    active_misc_count = sum(
        1 for m in misconceptions if isinstance(m, dict) and not m.get("resolved") and str(m.get("text") or "").strip()
    )

    trajectory = compute_trajectory_state(
        known_count=known_count,
        fragile_count=fragile_count,
        biomarkers=biomarkers,
        recent_reveals=reveals,
        active_misconceptions=active_misc_count,
        days_since_prev_session=days_since_prev,
        current_verdict=verdict,
    )
    talking_points = _build_talking_points(
        student=student,
        node=node,
        goal=goal,
        verdict=verdict,
        biomarkers=biomarkers,
        misconceptions=misconceptions,
    )
    recs = _build_recommended_interventions(
        student=student,
        trajectory_state=trajectory,
        recent_reveals=reveals,
        active_locks=active_locks,
    )

    name = _first_name(student.display_name)
    topic = (node.title or "a lesson").strip()
    if verdict == "known":
        summary = f"{name} completed {topic} independently and demonstrated solid understanding."
    elif verdict == "fragile":
        summary = f"{name} finished {topic} with some support and is ready for light reinforcement next time."
    else:
        summary = f"{name} wrapped up {topic}."

    existing = db.scalar(
        select(ParentSessionDigest).where(ParentSessionDigest.session_id == session.id)
    )
    if existing is None:
        digest = ParentSessionDigest(
            student_id=student.id,
            session_id=session.id,
            goal_id=goal.id if goal is not None else None,
            kc_id=node.id,
            trajectory_state=trajectory,
            summary=summary,
            talking_points=talking_points,
            biomarkers_snapshot=biomarkers,
            recommended_interventions=recs,
        )
        db.add(digest)
    else:
        digest = existing
        digest.trajectory_state = trajectory
        digest.summary = summary
        digest.talking_points = talking_points
        digest.biomarkers_snapshot = biomarkers
        digest.recommended_interventions = recs
    db.flush()
    return digest


def apply_parent_intervention(
    db: Session,
    *,
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    goal_id: uuid.UUID,
    locks: dict | None = None,
    course_mode: str | None = None,
) -> dict:
    """Apply parent-level course overrides to `learner_course_state` without touching `tutor_profiles`."""
    student = require_linked_child(db, parent_id, student_id)
    if is_harness_student_or_session(db, student=student):
        raise HTTPException(status_code=422, detail="Cannot apply parent policies to a test child.")
    goal = _course_or_404(db, goal_id)
    if course_mode is not None and course_mode not in COURSE_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"course_mode must be one of: {', '.join(COURSE_MODES)}.",
        )
    cstate = _get_or_create_course_state(db, student.id, goal.id)
    cstate.parent_policy_locks = normalize_parent_locks(locks, cstate.parent_policy_locks)
    if course_mode is not None:
        cstate.course_mode = course_mode
    cstate.updated_at = _utcnow()
    db.flush()
    return {
        "student_id": str(student.id),
        "course_id": str(goal.id),
        "course_title": goal.title,
        "course_mode": cstate.course_mode,
        "parent_policy_locks": dict(cstate.parent_policy_locks or {}),
        "next_session_guidance": format_parent_locks_note(cstate),
        "updated_at": cstate.updated_at.isoformat(),
    }


def _serialize_share_meta(row: TeacherShareToken, course_titles: dict[uuid.UUID, str]) -> dict:
    now = _utcnow()
    exp = _aware(row.expires_at)
    expired = bool(exp is not None and exp <= now)
    revoked = row.revoked_at is not None
    status = "revoked" if revoked else ("expired" if expired else "active")
    return {
        "id": str(row.id),
        "token_prefix": row.token_prefix,
        "label": row.label,
        "goal_id": str(row.goal_id) if row.goal_id else None,
        "course_title": course_titles.get(row.goal_id) if row.goal_id else None,
        "status": status,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def create_teacher_share_token(
    db: Session,
    *,
    parent_id: uuid.UUID,
    student_id: uuid.UUID,
    goal_id: uuid.UUID | None = None,
    label: str = "",
    expires_in_days: int = DEFAULT_SHARE_TTL_DAYS,
) -> dict:
    """Create a revocable SHA-256 teacher share link. Raw token is returned ONCE."""
    student = require_linked_child(db, parent_id, student_id)
    if is_harness_student_or_session(db, student=student):
        raise HTTPException(status_code=422, detail="Cannot create a teacher share for a test child.")
    goal: KcGoal | None = None
    if goal_id is not None:
        goal = _course_or_404(db, goal_id)

    ttl = max(1, min(MAX_SHARE_TTL_DAYS, int(expires_in_days or DEFAULT_SHARE_TTL_DAYS)))
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_share_token(raw_token)
    clean_label = " ".join((label or "").split())[:120]
    expires_at = _utcnow() + timedelta(days=ttl)

    row = TeacherShareToken(
        token_hash=token_hash,
        token_prefix=raw_token[:10],
        parent_id=parent_id,
        student_id=student.id,
        goal_id=goal.id if goal is not None else None,
        label=clean_label or (f"{goal.title} snapshot" if goal is not None else "Progress snapshot"),
        expires_at=expires_at,
    )
    db.add(row)
    db.flush()
    course_titles = {goal.id: goal.title} if goal is not None else {}
    return {
        **_serialize_share_meta(row, course_titles),
        "share_token": raw_token,
        "share_path": f"/teacher/share/{raw_token}",
    }


def list_teacher_share_tokens(
    db: Session, *, parent_id: uuid.UUID, student_id: uuid.UUID
) -> list[dict]:
    require_linked_child(db, parent_id, student_id)
    rows = db.scalars(
        select(TeacherShareToken)
        .where(
            TeacherShareToken.parent_id == parent_id,
            TeacherShareToken.student_id == student_id,
        )
        .order_by(TeacherShareToken.created_at.desc())
    ).all()
    goal_ids = {r.goal_id for r in rows if r.goal_id is not None}
    goals = db.scalars(select(KcGoal).where(KcGoal.id.in_(goal_ids))).all() if goal_ids else []
    titles = {g.id: g.title for g in goals}
    return [_serialize_share_meta(r, titles) for r in rows]


def revoke_teacher_share_token(
    db: Session, *, parent_id: uuid.UUID, student_id: uuid.UUID, share_id: uuid.UUID
) -> dict:
    require_linked_child(db, parent_id, student_id)
    row = db.get(TeacherShareToken, share_id)
    if row is None or row.parent_id != parent_id or row.student_id != student_id:
        raise HTTPException(status_code=404, detail="That teacher share link was not found.")
    if row.revoked_at is None:
        row.revoked_at = _utcnow()
        db.flush()
    titles: dict[uuid.UUID, str] = {}
    if row.goal_id is not None:
        g = db.get(KcGoal, row.goal_id)
        if g is not None:
            titles[g.id] = g.title
    return _serialize_share_meta(row, titles)


def _course_snapshot_rows(
    db: Session,
    *,
    student: Student,
    scoped_goal_id: uuid.UUID | None = None,
    include_locks: bool = True,
) -> list[dict]:
    if scoped_goal_id is not None:
        goal = db.get(KcGoal, scoped_goal_id)
        goals = [goal] if goal is not None else []
    else:
        goals = db.scalars(select(KcGoal).where(KcGoal.ready.is_(True)).order_by(KcGoal.title)).all()
    if not goals:
        return []

    goal_ids = [g.id for g in goals]
    cstates = db.scalars(
        select(LearnerCourseState).where(
            LearnerCourseState.student_id == student.id,
            LearnerCourseState.goal_id.in_(goal_ids),
        )
    ).all()
    cstate_by_goal = {c.goal_id: c for c in cstates}

    all_kc_ids: set[uuid.UUID] = set()
    kc_ids_by_goal: dict[uuid.UUID, list[uuid.UUID]] = {}
    for g in goals:
        ids = _goal_kc_uuids(g)
        kc_ids_by_goal[g.id] = ids
        all_kc_ids.update(ids)

    nodes = db.scalars(select(KcNode).where(KcNode.id.in_(all_kc_ids))).all() if all_kc_ids else []
    node_by_id = {n.id: n for n in nodes}
    states = (
        db.scalars(
            select(KcState).where(
                KcState.student_id == student.id,
                KcState.kc_id.in_(all_kc_ids),
            )
        ).all()
        if all_kc_ids
        else []
    )
    state_by_kc = {s.kc_id: s for s in states}

    out: list[dict] = []
    for g in goals:
        ids = kc_ids_by_goal[g.id]
        known_titles: list[str] = []
        fragile_titles: list[str] = []
        in_progress_titles: list[str] = []
        for kid in ids:
            st = state_by_kc.get(kid)
            node = node_by_id.get(kid)
            title = node.title if node is not None else str(kid)
            if st is None:
                continue
            if st.status == "known":
                known_titles.append(title)
            elif st.status == "fragile":
                fragile_titles.append(title)
            else:
                in_progress_titles.append(title)

        cstate = cstate_by_goal.get(g.id)
        active_misc = [
            str(m.get("text") or "").strip()
            for m in (cstate.misconceptions if cstate is not None else [])
            if isinstance(m, dict) and not m.get("resolved") and str(m.get("text") or "").strip()
        ]
        try:
            exam_sum = course_exam_summary(db, goal_id=g.id, student_id=student.id)
        except ValueError:
            exam_sum = None

        row: dict = {
            "course_id": str(g.id),
            "code": g.code,
            "title": g.title,
            "audience": g.audience,
            "catalog_tier": getattr(g, "catalog_tier", "core") or "core",
            "default_archetype": getattr(g, "default_archetype", None),
            "standards": list(g.standards or []),
            "total_components": len(ids),
            "known_count": len(known_titles),
            "fragile_count": len(fragile_titles),
            "in_progress_count": len(in_progress_titles),
            "known_topics": known_titles,
            "fragile_topics": fragile_titles,
            "active_misconceptions": active_misc,
            "blind_exam": {
                "latest_pre_score": exam_sum["latest_pre"]["raw_score"] if exam_sum and exam_sum.get("latest_pre") else None,
                "latest_post_score": exam_sum["latest_post"]["raw_score"] if exam_sum and exam_sum.get("latest_post") else None,
                "hake_g": exam_sum.get("hake_g") if exam_sum else None,
            },
        }
        if include_locks:
            row["course_mode"] = cstate.course_mode if cstate is not None else "mastery"
            row["parent_policy_locks"] = dict(cstate.parent_policy_locks or {}) if cstate is not None else {}
        out.append(row)
    # Show started / active courses first
    out.sort(
        key=lambda item: (
            0 if (item["known_count"] + item["fragile_count"] + item["in_progress_count"] > 0) else 1,
            item["title"].lower(),
        )
    )
    return out


def get_parent_copilot_summary(db: Session, *, parent_id: uuid.UUID, student_id: uuid.UUID) -> dict:
    """Full F6 Parent Co-Pilot view combining Graph 1 mastery, Graph 2 radar, F2 gain, digests, locks & shares."""
    student = require_linked_child(db, parent_id, student_id)
    edu = db.get(StudentEducationalState, student.id)
    biomarkers = dict(edu.biomarkers or {}) if edu is not None else {
        "own_words_pass": 0,
        "hard_recovery_pass": 0,
        "on_topic_inquiry_before_known": 0,
        "multi_perspective_synthesis": 0,
    }
    radar = build_radar_payload(db, student.id)
    courses = _course_snapshot_rows(db, student=student, include_locks=True)

    digest_rows = db.scalars(
        select(ParentSessionDigest)
        .where(ParentSessionDigest.student_id == student.id)
        .order_by(ParentSessionDigest.created_at.desc())
        .limit(5)
    ).all()
    kc_ids = {d.kc_id for d in digest_rows}
    goal_ids = {d.goal_id for d in digest_rows if d.goal_id is not None}
    nodes = db.scalars(select(KcNode).where(KcNode.id.in_(kc_ids))).all() if kc_ids else []
    goals = db.scalars(select(KcGoal).where(KcGoal.id.in_(goal_ids))).all() if goal_ids else []
    node_titles = {n.id: n.title for n in nodes}
    goal_titles = {g.id: g.title for g in goals}

    digests = [
        {
            "id": str(d.id),
            "session_id": str(d.session_id),
            "course_id": str(d.goal_id) if d.goal_id else None,
            "course_title": goal_titles.get(d.goal_id, "") if d.goal_id else "",
            "kc_id": str(d.kc_id),
            "kc_title": node_titles.get(d.kc_id, ""),
            "trajectory_state": d.trajectory_state,
            "summary": d.summary,
            "talking_points": list(d.talking_points or []),
            "biomarkers_snapshot": dict(d.biomarkers_snapshot or {}),
            "recommended_interventions": list(d.recommended_interventions or []),
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in digest_rows
    ]

    if digests:
        trajectory_state = digests[0]["trajectory_state"]
    else:
        total_known = sum(c["known_count"] for c in courses)
        total_fragile = sum(c["fragile_count"] for c in courses)
        total_misc = sum(len(c["active_misconceptions"]) for c in courses)
        trajectory_state = compute_trajectory_state(
            known_count=total_known,
            fragile_count=total_fragile,
            biomarkers=biomarkers,
            recent_reveals=0,
            active_misconceptions=total_misc,
        )

    shares = list_teacher_share_tokens(db, parent_id=parent_id, student_id=student.id)

    return {
        "student_id": str(student.id),
        "display_name": student.display_name,
        "interests": [str(i) for i in (student.interests or []) if str(i).strip()],
        "trajectory_state": trajectory_state,
        "trajectory_meta": TRAJECTORY_META.get(trajectory_state, TRAJECTORY_META["steady_progress"]),
        "biomarkers": biomarkers,
        "radar": radar,
        "digests": digests,
        "courses": courses,
        "teacher_shares": shares,
    }


def resolve_teacher_snapshot(db: Session, raw_token: str) -> dict:
    """Resolve a revocable SHA-256 share token into a strictly read-only Teacher Snapshot.

    Returns 404 for unknown, revoked, or expired tokens. Never returns raw chat messages,
    prompts, token usage, or parent private controls.
    """
    cleaned = (raw_token or "").strip()
    if not cleaned or len(cleaned) > 128:
        raise HTTPException(status_code=404, detail="This teacher share link is invalid or has been revoked.")

    token_hash = hash_share_token(cleaned)
    row = db.scalar(select(TeacherShareToken).where(TeacherShareToken.token_hash == token_hash))
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=404, detail="This teacher share link is invalid or has been revoked.")
    exp = _aware(row.expires_at)
    if exp is not None and exp <= _utcnow():
        raise HTTPException(status_code=404, detail="This teacher share link has expired.")

    student = db.get(Student, row.student_id)
    if student is None or is_harness_student_or_session(db, student=student):
        raise HTTPException(status_code=404, detail="This teacher share link is no longer available.")

    edu = db.get(StudentEducationalState, student.id)
    biomarkers = dict(edu.biomarkers or {}) if edu is not None else {
        "own_words_pass": 0,
        "hard_recovery_pass": 0,
        "on_topic_inquiry_before_known": 0,
        "multi_perspective_synthesis": 0,
    }
    radar = build_radar_payload(db, student.id)
    courses = _course_snapshot_rows(
        db,
        student=student,
        scoped_goal_id=row.goal_id,
        include_locks=False,
    )

    latest_digest = db.scalar(
        select(ParentSessionDigest)
        .where(ParentSessionDigest.student_id == student.id)
        .order_by(ParentSessionDigest.created_at.desc())
        .limit(1)
    )
    if latest_digest is not None:
        trajectory_state = latest_digest.trajectory_state
    else:
        trajectory_state = compute_trajectory_state(
            known_count=sum(c["known_count"] for c in courses),
            fragile_count=sum(c["fragile_count"] for c in courses),
            biomarkers=biomarkers,
            recent_reveals=0,
            active_misconceptions=sum(len(c["active_misconceptions"]) for c in courses),
        )

    profile = student.child_profile if isinstance(student.child_profile, dict) else {}
    grade_band = str(profile.get("grade_band") or getattr(student, "grade_band", "") or "")

    return {
        "share_label": row.label,
        "scoped_course_id": str(row.goal_id) if row.goal_id else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "generated_at": _utcnow().isoformat(),
        "learner": {
            "first_name": _first_name(student.display_name),
            "grade_band": grade_band,
        },
        "trajectory_state": trajectory_state,
        "trajectory_meta": TRAJECTORY_META.get(trajectory_state, TRAJECTORY_META["steady_progress"]),
        "biomarkers": biomarkers,
        "radar": radar,
        "courses": courses,
    }
