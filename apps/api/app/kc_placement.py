"""Feature 5 (F5): Jargon-free cold-start DAG placement & Bjork memory decay warmups.

Design invariants:
- Cold-start placement activates for unstarted ready courses with >= 4 target components.
- Binary search over topological order (`kc_edges` kind='prerequisite_of' + fallback
  `node.prerequisite_codes`) converges in at most `min(4, ceil(log2(N)))` everyday
  scenario probes, always offering a zero-shame "Not sure yet — teach me this!" option.
- Passing a probe surmise-propagates `status='known'`, `stability=0.75`,
  `result={'source': 'placement_surmise', ...}` onto `v_med` and all transitive
  prerequisites `Anc(v_med)`. Missing narrows to the lower half without penalty.
- Hint-weighted initial storage strength (`SS_k`):
    1.00 = Attempt-1 independent pass
    0.70 = Attempt-2 / nudge-assisted pass
    0.45 = Attempt-3+ / scaffold-assisted pass
- Wall-clock Bjork retrieval strength:
    `RS_k(t) = exp(-days_elapsed / (7.0 * SS_k))`
  When a `"known"` node decays below `0.65`, a 2-minute `retrieval_check` warmup is
  surfaced; passing boosts `SS_k <- round(1.8 * SS_k + 0.5, 2)` and resets `last_practiced`.
- Harness / test children (`student.is_test == True`) never write `learner_course_state`.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KcEdge, KcGoal, KcNode, KcSession, KcState, LearnerCourseState, Student

PLACEMENT_MIN_COMPONENTS = 4
PLACEMENT_MAX_PROBES_CAP = 4
PLACEMENT_SURMISE_STABILITY = 0.75

STABILITY_ATTEMPT_1 = 1.0
STABILITY_ATTEMPT_2 = 0.70
STABILITY_ATTEMPT_3 = 0.45

BJORK_SCALE_DAYS = 7.0
WARMUP_RS_THRESHOLD = 0.65

UNSURE_CHOICE_ID = "unsure"
UNSURE_CHOICE_TEXT = "Not sure yet — teach me this!"

_PARTICIPATION_BLOCK_TYPES = frozenset({"curiosity", "explanation"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Part A: Hint-weighted Storage Strength (SS_k) & Bjork Forgetting Curve (RS)
# ---------------------------------------------------------------------------


def initial_stability_for_session(session: KcSession | None) -> float:
    """Weight initial Storage Strength (SS_k) by attempt & hint independence.

    - Attempt-1 independent pass: 1.00
    - Attempt-2 or nudge-assisted pass: 0.70
    - Attempt-3+ or scaffold/analogy-assisted pass: 0.45
    """
    if session is None:
        return STABILITY_ATTEMPT_1
    results = session.block_results if isinstance(session.block_results, list) else []
    assessed_rows: list[dict] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        btype = str(row.get("block_type") or row.get("type") or "").strip()
        outcome = str(row.get("outcome") or "").strip()
        if btype in _PARTICIPATION_BLOCK_TYPES or outcome in {"fast_tracked", "engaged"}:
            continue
        assessed_rows.append(row)

    if not assessed_rows:
        # Legacy single-step or empty block_results fallback.
        attempts = max(1, int(getattr(session, "move_attempts", 0) or 0))
        tier = str(getattr(session, "hint_tier", "") or "").strip().lower()
        if attempts >= 3 or tier in {"analogy", "scaffold"}:
            return STABILITY_ATTEMPT_3
        if attempts == 2:
            return STABILITY_ATTEMPT_2
        return STABILITY_ATTEMPT_1

    worst_tier = 1  # 1 -> 1.00, 2 -> 0.70, 3 -> 0.45
    for row in assessed_rows:
        attempts = int(row.get("attempts") or 1)
        hint_tier = str(row.get("hint_tier") or "").strip().lower()
        reqs = row.get("requirements") if isinstance(row.get("requirements"), list) else []
        req_assisted = any(
            isinstance(r, dict)
            and str(r.get("role") or "") == "assessed"
            and str(r.get("observation") or "") == "assisted"
            for r in reqs
        )
        req_max_attempts = max(
            (
                int(r.get("attempts") or 0)
                for r in reqs
                if isinstance(r, dict) and str(r.get("role") or "") == "assessed"
            ),
            default=0,
        )
        effective_attempts = max(attempts, req_max_attempts, 1)
        if effective_attempts >= 3 or hint_tier in {"analogy", "scaffold"}:
            worst_tier = max(worst_tier, 3)
        elif effective_attempts == 2 or req_assisted:
            worst_tier = max(worst_tier, 2)

    if worst_tier >= 3:
        return STABILITY_ATTEMPT_3
    if worst_tier == 2:
        return STABILITY_ATTEMPT_2
    return STABILITY_ATTEMPT_1


def retrieval_strength(
    stability: float | None,
    last_practiced: datetime | None,
    *,
    status: str = "known",
    now: datetime | None = None,
) -> float | None:
    """Compute live Bjork retrieval strength RS_k(t) = exp(-days / (7.0 * SS_k)).

    Returns None when the component is not yet `"known"` or has no practice timestamp.
    """
    if status != "known":
        return None
    ss = float(stability or 0.0)
    practiced_utc = _as_utc(last_practiced)
    if ss <= 0.0 or practiced_utc is None:
        return None
    current = _as_utc(now) or _utcnow()
    days_elapsed = max(0.0, (current - practiced_utc).total_seconds() / 86400.0)
    rs = math.exp(-days_elapsed / (BJORK_SCALE_DAYS * ss))
    return round(max(0.0, min(1.0, rs)), 4)


def days_since_practice(last_practiced: datetime | None, *, now: datetime | None = None) -> float | None:
    practiced_utc = _as_utc(last_practiced)
    if practiced_utc is None:
        return None
    current = _as_utc(now) or _utcnow()
    return round(max(0.0, (current - practiced_utc).total_seconds() / 86400.0), 1)


def boosted_stability_on_warmup_pass(stability: float | None) -> float:
    """Apply Bjork spacing boost: SS_k <- 1.8 * SS_k + 0.5."""
    base = max(float(stability or 0.0), STABILITY_ATTEMPT_3)
    return round(1.8 * base + 0.5, 2)


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _deterministic_order(items: list[dict], seed_key: str) -> list[dict]:
    """Deterministically shuffle choices so the correct answer is not always first."""
    return sorted(
        items,
        key=lambda item: hashlib.sha256(f"{seed_key}:{item['id']}".encode("utf-8")).hexdigest(),
    )


def _extract_node_check(node: KcNode, *, for_warmup: bool = False) -> dict:
    """Extract a jargon-free check (choices or open recall) from a component's own content.

    Includes private server-only grading keys (`expected_choice_id`, `expected_phrases`,
    `expected_summary`); always strip via `_public_check()` before returning to clients.
    """
    blocks = node.blocks if isinstance(node.blocks, list) else []

    # 1. For warmups, prefer an authored retrieval_check block first.
    if for_warmup:
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") != "retrieval_check":
                continue
            data = block.get("data") if isinstance(block.get("data"), dict) else {}
            prompt = _clean_text(data.get("recall_prompt"))
            expected = _clean_text(data.get("expected_fact"))
            if prompt and expected:
                return {
                    "prompt": prompt,
                    "input_mode": "open",
                    "choices": [],
                    "expected_choice_id": None,
                    "expected_phrases": [p for p in (expected, _clean_text(node.core_truth)) if p],
                    "expected_summary": expected,
                    "source_block_type": "retrieval_check",
                }

    # 2. Static MCQ block with valid choices and one correct answer.
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "mcq":
            continue
        data = block.get("data") if isinstance(block.get("data"), dict) else {}
        if _clean_text(data.get("mode") or "static") != "static":
            continue
        stem = _clean_text(data.get("question_stem"))
        raw_choices = data.get("choices") if isinstance(data.get("choices"), list) else []
        cleaned_choices: list[dict] = []
        correct_id: str | None = None
        correct_text = ""
        for idx, item in enumerate(raw_choices):
            if not isinstance(item, dict):
                continue
            text = _clean_text(item.get("text"))
            if not text:
                continue
            cid = _clean_text(item.get("id")) or f"opt_{idx + 1}"
            cleaned_choices.append({"id": cid, "text": text})
            if item.get("is_correct") is True and correct_id is None:
                correct_id = cid
                correct_text = text
        if stem and len(cleaned_choices) >= 2 and correct_id is not None:
            return {
                "prompt": stem,
                "input_mode": "choice",
                "choices": cleaned_choices,
                "expected_choice_id": correct_id,
                "expected_phrases": [p for p in (correct_text, _clean_text(node.core_truth)) if p],
                "expected_summary": correct_text or _clean_text(node.core_truth),
                "source_block_type": "mcq",
            }

    # 3. Synthesize a jargon-free scenario check from retrieval_check / case_study / spot_the_flaw / core_truth.
    prompt = ""
    expected = _clean_text(node.core_truth)
    source_type = "core_truth"
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = _clean_text(block.get("type"))
        data = block.get("data") if isinstance(block.get("data"), dict) else {}
        if btype == "retrieval_check" and _clean_text(data.get("recall_prompt")):
            prompt = _clean_text(data.get("recall_prompt"))
            expected = _clean_text(data.get("expected_fact")) or expected
            source_type = "retrieval_check"
            break
        if btype == "case_study" and _clean_text(data.get("prediction_prompt")):
            case_a = _clean_text(data.get("case_a"))
            pred = _clean_text(data.get("prediction_prompt"))
            prompt = f"{case_a} {pred}".strip() if case_a else pred
            expected = _clean_text(data.get("invariant_principle")) or expected
            source_type = "case_study"
            break
        if btype == "spot_the_flaw" and _clean_text(data.get("rookie_work")):
            prompt = f"Someone says: \"{_clean_text(data.get('rookie_work'))}\" What is the better way to explain this?"
            expected = _clean_text(data.get("corrected_version")) or _clean_text(data.get("flaw_description")) or expected
            source_type = "spot_the_flaw"
            break
        if btype == "topic_goal" and _clean_text(data.get("goal")):
            prompt = f"In your own words, what is the big idea behind {node.title}?"
            source_type = "topic_goal"
            break

    if not prompt:
        prompt = f"Which statement best describes {node.title}?"

    # If we have a clear core idea + at least one misconception wrong_move, offer clean choices.
    distractors: list[str] = []
    for item in node.misconceptions or []:
        if not isinstance(item, dict):
            continue
        wrong = _clean_text(item.get("wrong_move"))
        if wrong and wrong.lower() != expected.lower() and wrong not in distractors:
            distractors.append(wrong)
        if len(distractors) >= 2:
            break

    if expected and distractors and not for_warmup:
        choice_rows = [{"id": "core", "text": expected}]
        for idx, wrong in enumerate(distractors, start=1):
            choice_rows.append({"id": f"dist_{idx}", "text": wrong})
        ordered = _deterministic_order(choice_rows, f"{node.code}:{node.id}")
        return {
            "prompt": f"Quick check on {node.title}: which idea fits best?",
            "input_mode": "choice",
            "choices": ordered,
            "expected_choice_id": "core",
            "expected_phrases": [p for p in (expected, _clean_text(node.core_truth)) if p],
            "expected_summary": expected,
            "source_block_type": source_type,
        }

    return {
        "prompt": prompt,
        "input_mode": "open",
        "choices": [],
        "expected_choice_id": None,
        "expected_phrases": [p for p in (expected, _clean_text(node.core_truth), node.title) if p],
        "expected_summary": expected or node.title,
        "source_block_type": source_type,
    }


def _public_check(check: dict, *, include_unsure: bool = False) -> dict:
    choices = [dict(item) for item in (check.get("choices") or [])]
    if include_unsure and not any(c.get("id") == UNSURE_CHOICE_ID for c in choices):
        choices.append({"id": UNSURE_CHOICE_ID, "text": UNSURE_CHOICE_TEXT})
    return {
        "prompt": str(check.get("prompt") or ""),
        "input_mode": str(check.get("input_mode") or "open"),
        "choices": choices,
        "unsure_choice_id": UNSURE_CHOICE_ID if include_unsure else None,
        "unsure_label": UNSURE_CHOICE_TEXT if include_unsure else None,
        "source_block_type": str(check.get("source_block_type") or ""),
    }


def _grade_check(check: dict, *, choice_id: str | None = None, answer: str = "") -> bool:
    from app.kc import matches_phrase

    expected_cid = check.get("expected_choice_id")
    cleaned_cid = _clean_text(choice_id)
    if cleaned_cid == UNSURE_CHOICE_ID:
        return False
    if expected_cid and cleaned_cid:
        return cleaned_cid == expected_cid

    cleaned_answer = _clean_text(answer)
    if not cleaned_answer:
        return False
    if expected_cid:
        for item in check.get("choices") or []:
            if item.get("id") == expected_cid and matches_phrase(cleaned_answer, str(item.get("text") or "")):
                return True
    for phrase in check.get("expected_phrases") or []:
        if phrase and matches_phrase(cleaned_answer, str(phrase)):
            return True
    return False


def build_warmup_item(
    node: KcNode,
    state: KcState | None,
    *,
    now: datetime | None = None,
) -> dict | None:
    """Return a 2-minute Bjork warmup card when a known node's RS < 0.65."""
    if state is None or state.status != "known":
        return None
    rs = retrieval_strength(
        state.stability,
        state.last_practiced,
        status=state.status,
        now=now,
    )
    if rs is None or rs >= WARMUP_RS_THRESHOLD:
        return None
    check = _extract_node_check(node, for_warmup=True)
    pub = _public_check(check, include_unsure=False)
    return {
        "kc_id": str(node.id),
        "code": node.code,
        "title": node.title,
        "stability": round(float(state.stability or 0.0), 2),
        "retrieval_strength": rs,
        "days_since_practice": days_since_practice(state.last_practiced, now=now),
        "estimated_minutes": 2,
        **pub,
    }


def course_warmups(
    targets: list[KcNode],
    states: dict[uuid.UUID, KcState],
    *,
    now: datetime | None = None,
) -> list[dict]:
    """All decayed known target components (`RS < 0.65`), ordered most decayed first."""
    items: list[dict] = []
    for node in targets:
        item = build_warmup_item(node, states.get(node.id), now=now)
        if item is not None:
            items.append(item)
    items.sort(key=lambda row: (float(row["retrieval_strength"]), row["title"]))
    return items


def submit_warmup_check(
    db: Session,
    *,
    goal: KcGoal,
    student: Student,
    node: KcNode,
    answer: str = "",
    choice_id: str | None = None,
) -> dict:
    """Grade a 2-minute Bjork retrieval warmup and boost SS_k <- 1.8 * SS_k + 0.5 on pass."""
    target_ids = {str(item) for item in (goal.target_kc_ids or [])}
    if str(node.id) not in target_ids:
        raise HTTPException(status_code=404, detail="That topic is not part of this course.")

    state = db.scalar(
        select(KcState).where(KcState.student_id == student.id, KcState.kc_id == node.id)
    )
    if state is None or state.status != "known":
        raise HTTPException(
            status_code=422,
            detail="Warmups are only available for topics you have already learned.",
        )

    check = _extract_node_check(node, for_warmup=True)
    passed = _grade_check(check, choice_id=choice_id, answer=answer)
    old_stability = round(float(state.stability or STABILITY_ATTEMPT_1), 2)
    expected_summary = str(check.get("expected_summary") or node.core_truth or node.title)

    if passed:
        new_stability = boosted_stability_on_warmup_pass(old_stability)
        state.stability = new_stability
        state.last_practiced = _utcnow()
        db.flush()
        return {
            "kc_id": str(node.id),
            "code": node.code,
            "title": node.title,
            "passed": True,
            "old_stability": old_stability,
            "new_stability": new_stability,
            "retrieval_strength": 1.0,
            "expected_summary": expected_summary,
            "feedback": f"Nice recall! Your memory of {node.title} is refreshed and stronger now.",
        }

    rs_now = retrieval_strength(state.stability, state.last_practiced, status=state.status)
    return {
        "kc_id": str(node.id),
        "code": node.code,
        "title": node.title,
        "passed": False,
        "old_stability": old_stability,
        "new_stability": old_stability,
        "retrieval_strength": rs_now,
        "expected_summary": expected_summary,
        "feedback": f"Good try — quick refresher: {expected_summary}",
    }


# ---------------------------------------------------------------------------
# Part B: Jargon-Free Cold-Start Topological Median DAG Placement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CourseDag:
    ordered_ids: list[uuid.UUID]
    depth_by_id: dict[uuid.UUID, int]
    ancestors_by_id: dict[uuid.UUID, set[uuid.UUID]]
    descendants_by_id: dict[uuid.UUID, set[uuid.UUID]]
    nodes_by_id: dict[uuid.UUID, KcNode]


def build_course_dag(db: Session, targets: list[KcNode]) -> CourseDag:
    """Compute topological ordering, depth, and transitive prerequisite sets for a course."""
    nodes_by_id: dict[uuid.UUID, KcNode] = {node.id: node for node in targets}
    nodes_by_code: dict[str, KcNode] = {node.code: node for node in targets}
    order_index: dict[uuid.UUID, int] = {node.id: idx for idx, node in enumerate(targets)}
    target_set = set(nodes_by_id.keys())

    prereqs: dict[uuid.UUID, set[uuid.UUID]] = {nid: set() for nid in target_set}
    dependents: dict[uuid.UUID, set[uuid.UUID]] = {nid: set() for nid in target_set}

    if target_set:
        edges = db.scalars(
            select(KcEdge).where(
                KcEdge.kind == "prerequisite_of",
                KcEdge.from_kc.in_(target_set),
                KcEdge.to_kc.in_(target_set),
            )
        ).all()
        for edge in edges:
            if edge.from_kc != edge.to_kc:
                prereqs[edge.to_kc].add(edge.from_kc)
                dependents[edge.from_kc].add(edge.to_kc)

    # Also honor JSON `prerequisite_codes` in case edges were not explicitly materialized.
    for node in targets:
        raw_codes = node.prerequisite_codes if isinstance(node.prerequisite_codes, list) else []
        for code in raw_codes:
            other = nodes_by_code.get(_clean_text(code))
            if other is not None and other.id != node.id:
                prereqs[node.id].add(other.id)
                dependents[other.id].add(node.id)

    # Kahn topological sort with deterministic tie-breaking by (depth, course_order).
    in_degree: dict[uuid.UUID, int] = {nid: len(prereqs[nid]) for nid in target_set}
    depth: dict[uuid.UUID, int] = {nid: 0 for nid in target_set}
    ready = sorted((nid for nid, deg in in_degree.items() if deg == 0), key=lambda nid: order_index[nid])
    ordered: list[uuid.UUID] = []

    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for nxt in sorted(dependents[current], key=lambda nid: order_index[nid]):
            depth[nxt] = max(depth[nxt], depth[current] + 1)
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                ready.append(nxt)
                ready.sort(key=lambda nid: (depth[nid], order_index[nid]))

    # Cycle-safe fallback: append any remaining nodes in course order.
    if len(ordered) < len(targets):
        seen = set(ordered)
        for node in targets:
            if node.id not in seen:
                ordered.append(node.id)

    # Transitive ancestors & descendants via BFS (cycle-safe).
    ancestors: dict[uuid.UUID, set[uuid.UUID]] = {}
    descendants: dict[uuid.UUID, set[uuid.UUID]] = {}
    for nid in ordered:
        anc: set[uuid.UUID] = set()
        queue: deque[uuid.UUID] = deque(prereqs[nid])
        while queue:
            cur = queue.popleft()
            if cur in anc or cur == nid:
                continue
            anc.add(cur)
            queue.extend(prereqs[cur] - anc)
        ancestors[nid] = anc

        desc: set[uuid.UUID] = set()
        queue = deque(dependents[nid])
        while queue:
            cur = queue.popleft()
            if cur in desc or cur == nid:
                continue
            desc.add(cur)
            queue.extend(dependents[cur] - desc)
        descendants[nid] = desc

    return CourseDag(
        ordered_ids=ordered,
        depth_by_id=depth,
        ancestors_by_id=ancestors,
        descendants_by_id=descendants,
        nodes_by_id=nodes_by_id,
    )


def max_probes_for_course(component_count: int) -> int:
    if component_count <= 1:
        return 1
    return min(PLACEMENT_MAX_PROBES_CAP, max(1, math.ceil(math.log2(component_count))))


def _get_course_state(db: Session, student_id: uuid.UUID, goal_id: uuid.UUID) -> LearnerCourseState | None:
    return db.scalar(
        select(LearnerCourseState).where(
            LearnerCourseState.student_id == student_id,
            LearnerCourseState.goal_id == goal_id,
        )
    )


def _get_or_create_course_state(db: Session, student_id: uuid.UUID, goal_id: uuid.UUID) -> LearnerCourseState:
    row = _get_course_state(db, student_id, goal_id)
    if row is None:
        row = LearnerCourseState(
            student_id=student_id,
            goal_id=goal_id,
            misconceptions=[],
            unlock_notes=[],
            analogies_worked=[],
            course_mode="mastery",
            parent_policy_locks={},
            placement_status="not_started",
            placement_state={},
        )
        db.add(row)
        db.flush()
    return row


def _course_has_started(
    db: Session,
    *,
    student_id: uuid.UUID,
    goal_id: uuid.UUID,
    target_ids: list[uuid.UUID],
    states: dict[uuid.UUID, KcState] | None = None,
    sessions_by_node: dict[uuid.UUID, list[KcSession]] | None = None,
) -> bool:
    if states is not None:
        for tid in target_ids:
            st = states.get(tid)
            if st is not None and st.status in {"known", "fragile"}:
                return True
    else:
        existing_state = db.scalar(
            select(KcState.id)
            .where(
                KcState.student_id == student_id,
                KcState.kc_id.in_(target_ids),
                KcState.status.in_(("known", "fragile")),
            )
            .limit(1)
        )
        if existing_state is not None:
            return True

    if sessions_by_node is not None:
        return any(bool(sessions_by_node.get(tid)) for tid in target_ids)

    existing_sess = db.scalar(
        select(KcSession.id)
        .where(KcSession.student_id == student_id, KcSession.goal_id == goal_id)
        .limit(1)
    )
    return existing_sess is not None


def _probe_payload(node: KcNode, *, probe_number: int, max_probes: int) -> dict:
    check = _extract_node_check(node, for_warmup=False)
    pub = _public_check(check, include_unsure=True)
    return {
        "kc_id": str(node.id),
        "code": node.code,
        "title": node.title,
        "probe_number": probe_number,
        "max_probes": max_probes,
        **pub,
    }


def placement_summary(
    db: Session,
    goal: KcGoal,
    student: Student,
    *,
    targets: list[KcNode] | None = None,
    states: dict[uuid.UUID, KcState] | None = None,
    sessions_by_node: dict[uuid.UUID, list[KcSession]] | None = None,
) -> dict:
    """Return placement eligibility, current status, and active probe (if in progress)."""
    from app.kc import load_targets

    target_nodes = targets if targets is not None else load_targets(db, goal)
    target_ids = [node.id for node in target_nodes]
    component_count = len(target_nodes)
    max_probes = max_probes_for_course(component_count)

    if bool(getattr(student, "is_test", False)):
        return {
            "eligible": False,
            "status": "skipped",
            "min_components": PLACEMENT_MIN_COMPONENTS,
            "component_count": component_count,
            "max_probes": max_probes,
            "probes_used": 0,
            "surmised_count": 0,
            "starting_kc_id": None,
            "active_probe": None,
        }

    course_state = _get_course_state(db, student.id, goal.id)
    status = str(getattr(course_state, "placement_status", "not_started") or "not_started")
    pstate = course_state.placement_state if (course_state is not None and isinstance(course_state.placement_state, dict)) else {}

    started = _course_has_started(
        db,
        student_id=student.id,
        goal_id=goal.id,
        target_ids=target_ids,
        states=states,
        sessions_by_node=sessions_by_node,
    )
    eligible = (
        bool(goal.ready)
        and component_count >= PLACEMENT_MIN_COMPONENTS
        and not started
        and status in {"not_started", "in_progress"}
    )

    active_probe: dict | None = None
    if status == "in_progress" and eligible:
        cur_id = _clean_text(pstate.get("current_kc_id"))
        if cur_id:
            try:
                cur_uuid = uuid.UUID(cur_id)
                cur_node = next((n for n in target_nodes if n.id == cur_uuid), None)
                if cur_node is not None:
                    history = pstate.get("history") if isinstance(pstate.get("history"), list) else []
                    active_probe = _probe_payload(
                        cur_node,
                        probe_number=len(history) + 1,
                        max_probes=int(pstate.get("max_probes") or max_probes),
                    )
            except ValueError:
                active_probe = None

    surmised_ids = pstate.get("surmised_kc_ids") if isinstance(pstate.get("surmised_kc_ids"), list) else []
    history = pstate.get("history") if isinstance(pstate.get("history"), list) else []
    return {
        "eligible": eligible,
        "status": status,
        "min_components": PLACEMENT_MIN_COMPONENTS,
        "component_count": component_count,
        "max_probes": int(pstate.get("max_probes") or max_probes),
        "probes_used": len(history),
        "surmised_count": len(surmised_ids),
        "starting_kc_id": _clean_text(pstate.get("starting_kc_id")) or None,
        "active_probe": active_probe,
    }


def _require_real_student(student: Student) -> None:
    if bool(getattr(student, "is_test", False)):
        raise HTTPException(
            status_code=422,
            detail="Course placement is only available for real learner profiles.",
        )


def start_placement(db: Session, goal: KcGoal, student: Student) -> dict:
    """Initialize (or resume) topological median binary search over a course DAG."""
    from app.kc import load_targets

    _require_real_student(student)
    if not goal.ready:
        raise HTTPException(status_code=422, detail="This course is not ready.")

    targets = load_targets(db, goal)
    if len(targets) < PLACEMENT_MIN_COMPONENTS:
        raise HTTPException(
            status_code=422,
            detail=f"Placement is offered on courses with at least {PLACEMENT_MIN_COMPONENTS} topics.",
        )

    course_state = _get_or_create_course_state(db, student.id, goal.id)
    if course_state.placement_status == "completed":
        pstate = course_state.placement_state if isinstance(course_state.placement_state, dict) else {}
        return {
            "status": "completed",
            "probes_used": len(pstate.get("history") or []),
            "max_probes": int(pstate.get("max_probes") or max_probes_for_course(len(targets))),
            "surmised_count": len(pstate.get("surmised_kc_ids") or []),
            "surmised_kc_ids": list(pstate.get("surmised_kc_ids") or []),
            "starting_component": pstate.get("starting_component"),
            "probe": None,
            "message": "Placement is already finished for this course.",
        }

    if _course_has_started(db, student_id=student.id, goal_id=goal.id, target_ids=[n.id for n in targets]):
        raise HTTPException(
            status_code=422,
            detail="This course is already underway. Restart the course to take placement again.",
        )

    dag = build_course_dag(db, targets)
    max_probes = max_probes_for_course(len(dag.ordered_ids))

    # Resume existing in-progress placement if valid.
    existing = course_state.placement_state if isinstance(course_state.placement_state, dict) else {}
    if course_state.placement_status == "in_progress" and existing.get("current_kc_id"):
        try:
            cur_uuid = uuid.UUID(str(existing["current_kc_id"]))
            cur_node = dag.nodes_by_id.get(cur_uuid)
            if cur_node is not None:
                history = list(existing.get("history") or [])
                return {
                    "status": "in_progress",
                    "probes_used": len(history),
                    "max_probes": int(existing.get("max_probes") or max_probes),
                    "probe": _probe_payload(
                        cur_node,
                        probe_number=len(history) + 1,
                        max_probes=int(existing.get("max_probes") or max_probes),
                    ),
                }
        except ValueError:
            pass

    candidates = list(dag.ordered_ids)
    mid = len(candidates) // 2
    median_id = candidates[mid]
    median_node = dag.nodes_by_id[median_id]

    course_state.placement_status = "in_progress"
    course_state.placement_state = {
        "ordered_ids": [str(nid) for nid in dag.ordered_ids],
        "candidate_ids": [str(nid) for nid in candidates],
        "known_ids": [],
        "unknown_ids": [],
        "current_kc_id": str(median_id),
        "max_probes": max_probes,
        "history": [],
        "started_at": _utcnow().isoformat(),
    }
    course_state.updated_at = _utcnow()
    db.flush()

    return {
        "status": "in_progress",
        "probes_used": 0,
        "max_probes": max_probes,
        "probe": _probe_payload(median_node, probe_number=1, max_probes=max_probes),
    }


def _finalize_placement(
    db: Session,
    *,
    goal: KcGoal,
    student: Student,
    course_state: LearnerCourseState,
    dag: CourseDag,
    known_ids: set[uuid.UUID],
    unknown_ids: set[uuid.UUID],
    history: list[dict],
    max_probes: int,
) -> dict:
    """Persist placement surmise onto KcState and select the ZPD outer-fringe starting node."""
    now = _utcnow()
    ordered_known = [nid for nid in dag.ordered_ids if nid in known_ids]

    for nid in ordered_known:
        state = db.scalar(
            select(KcState).where(KcState.student_id == student.id, KcState.kc_id == nid)
        )
        if state is None:
            state = KcState(
                student_id=student.id,
                kc_id=nid,
                status="known",
                stability=PLACEMENT_SURMISE_STABILITY,
                last_practiced=now,
            )
            db.add(state)
        else:
            state.status = "known"
            state.stability = round(max(float(state.stability or 0.0), PLACEMENT_SURMISE_STABILITY), 2)
            state.last_practiced = now
        state.result = {
            "status": "known",
            "source": "placement_surmise",
            "justification": "Surmised known during quick course placement check-in.",
            "strong": "Already comfortable with this idea.",
            "work_on": "Start right at the next frontier topic.",
        }

    # ZPD outer fringe O(K_0): first non-known node in topological order whose ancestors are all known.
    starting_node: KcNode | None = None
    for nid in dag.ordered_ids:
        if nid in known_ids:
            continue
        if dag.ancestors_by_id.get(nid, set()) <= known_ids:
            starting_node = dag.nodes_by_id[nid]
            break
    if starting_node is None and dag.ordered_ids:
        # Every node was surmised known: start at the capstone/final component for stretch mastery.
        starting_node = dag.nodes_by_id[dag.ordered_ids[-1]]

    starting_info = (
        {"id": str(starting_node.id), "code": starting_node.code, "title": starting_node.title}
        if starting_node is not None
        else None
    )

    surmised_str_ids = [str(nid) for nid in ordered_known]
    course_state.placement_status = "completed"
    course_state.placement_state = {
        "ordered_ids": [str(nid) for nid in dag.ordered_ids],
        "candidate_ids": [],
        "known_ids": surmised_str_ids,
        "unknown_ids": [str(nid) for nid in dag.ordered_ids if nid in unknown_ids],
        "surmised_kc_ids": surmised_str_ids,
        "current_kc_id": None,
        "starting_kc_id": starting_info["id"] if starting_info else None,
        "starting_component": starting_info,
        "max_probes": max_probes,
        "history": history,
        "completed_at": now.isoformat(),
    }
    course_state.updated_at = now
    db.flush()

    surmised_count = len(surmised_str_ids)
    if surmised_count == 0:
        msg = (
            f"Perfect — let's start right from the beginning with {starting_info['title']}!"
            if starting_info
            else "Perfect — let's start from the beginning!"
        )
    elif surmised_count == len(dag.ordered_ids):
        msg = (
            f"Awesome — you already know the big ideas here! Let's jump straight to {starting_info['title']}."
            if starting_info
            else "Awesome — you already know these ideas!"
        )
    else:
        msg = (
            f"Nice! You can skip {surmised_count} earlier topic"
            f"{'s' if surmised_count != 1 else ''} and jump straight into {starting_info['title']}."
            if starting_info
            else f"Nice! You can skip {surmised_count} earlier topics."
        )

    return {
        "status": "completed",
        "probes_used": len(history),
        "max_probes": max_probes,
        "surmised_count": surmised_count,
        "surmised_kc_ids": surmised_str_ids,
        "starting_component": starting_info,
        "probe": None,
        "message": msg,
    }


def answer_placement_probe(
    db: Session,
    *,
    goal: KcGoal,
    student: Student,
    kc_id: uuid.UUID,
    choice_id: str | None = None,
    answer: str = "",
    unsure: bool = False,
) -> dict:
    """Grade one median probe, update binary-search bounds, and converge or serve next probe."""
    from app.kc import load_targets

    _require_real_student(student)
    targets = load_targets(db, goal)
    dag = build_course_dag(db, targets)
    course_state = _get_course_state(db, student.id, goal.id)
    if course_state is None or course_state.placement_status != "in_progress":
        raise HTTPException(status_code=409, detail="Start placement before answering a question.")

    pstate = dict(course_state.placement_state or {})
    current_id_str = _clean_text(pstate.get("current_kc_id"))
    if current_id_str != str(kc_id):
        raise HTTPException(status_code=409, detail="That placement question is no longer active.")

    node = dag.nodes_by_id.get(kc_id)
    if node is None:
        raise HTTPException(status_code=404, detail="That topic is not part of this course.")

    candidates = [uuid.UUID(cid) for cid in (pstate.get("candidate_ids") or []) if uuid.UUID(cid) in dag.nodes_by_id]
    known_ids = {uuid.UUID(cid) for cid in (pstate.get("known_ids") or []) if uuid.UUID(cid) in dag.nodes_by_id}
    unknown_ids = {uuid.UUID(cid) for cid in (pstate.get("unknown_ids") or []) if uuid.UUID(cid) in dag.nodes_by_id}
    history = list(pstate.get("history") or [])
    max_probes = int(pstate.get("max_probes") or max_probes_for_course(len(dag.ordered_ids)))

    is_unsure = bool(unsure) or _clean_text(choice_id) == UNSURE_CHOICE_ID
    check = _extract_node_check(node, for_warmup=False)
    passed = False if is_unsure else _grade_check(check, choice_id=choice_id, answer=answer)

    mid = candidates.index(kc_id) if kc_id in candidates else (len(candidates) // 2)

    if passed:
        # Surmise-propagate known onto v_med and all transitive prerequisites Anc(v_med).
        newly_known = {kc_id} | dag.ancestors_by_id.get(kc_id, set())
        known_ids |= newly_known
        # Search strictly the upper half (topics beyond v_med not already settled).
        next_candidates = [cid for cid in candidates[mid + 1 :] if cid not in known_ids and cid not in unknown_ids]
        step_feedback = "Nice — you already have a solid feel for that!"
    else:
        # Zero-shame narrowing to the lower half; v_med and its descendants still need teaching.
        unknown_ids |= {kc_id} | dag.descendants_by_id.get(kc_id, set())
        next_candidates = [cid for cid in candidates[:mid] if cid not in known_ids and cid not in unknown_ids]
        step_feedback = "No problem at all — we'll explore that together!"

    history.append(
        {
            "kc_id": str(kc_id),
            "code": node.code,
            "passed": passed,
            "unsure": is_unsure,
            "at": _utcnow().isoformat(),
        }
    )

    if not next_candidates or len(history) >= max_probes:
        final = _finalize_placement(
            db,
            goal=goal,
            student=student,
            course_state=course_state,
            dag=dag,
            known_ids=known_ids,
            unknown_ids=unknown_ids,
            history=history,
            max_probes=max_probes,
        )
        final["last_passed"] = passed
        final["step_feedback"] = step_feedback
        return final

    next_mid = len(next_candidates) // 2
    next_id = next_candidates[next_mid]
    next_node = dag.nodes_by_id[next_id]

    course_state.placement_status = "in_progress"
    course_state.placement_state = {
        "ordered_ids": [str(nid) for nid in dag.ordered_ids],
        "candidate_ids": [str(nid) for nid in next_candidates],
        "known_ids": [str(nid) for nid in dag.ordered_ids if nid in known_ids],
        "unknown_ids": [str(nid) for nid in dag.ordered_ids if nid in unknown_ids],
        "current_kc_id": str(next_id),
        "max_probes": max_probes,
        "history": history,
        "started_at": pstate.get("started_at") or _utcnow().isoformat(),
    }
    course_state.updated_at = _utcnow()
    db.flush()

    return {
        "status": "in_progress",
        "last_passed": passed,
        "step_feedback": step_feedback,
        "probes_used": len(history),
        "max_probes": max_probes,
        "probe": _probe_payload(next_node, probe_number=len(history) + 1, max_probes=max_probes),
    }


def skip_placement(db: Session, *, goal: KcGoal, student: Student) -> dict:
    """Record that the child chose 'Start from the beginning' instead of placement."""
    _require_real_student(student)
    if not goal.ready:
        raise HTTPException(status_code=422, detail="This course is not ready.")
    course_state = _get_or_create_course_state(db, student.id, goal.id)
    course_state.placement_status = "skipped"
    course_state.placement_state = {"skipped_at": _utcnow().isoformat()}
    course_state.updated_at = _utcnow()
    db.flush()
    return {"status": "skipped", "course_id": str(goal.id)}


def reset_course_placement(db: Session, student_id: uuid.UUID, goal_id: uuid.UUID) -> None:
    """Clear F5 placement state when a child restarts a course."""
    row = _get_course_state(db, student_id, goal_id)
    if row is not None:
        row.placement_status = "not_started"
        row.placement_state = {}
        row.updated_at = _utcnow()
        db.flush()
