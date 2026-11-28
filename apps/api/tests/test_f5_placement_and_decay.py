"""Comprehensive tests for F5: Cold-Start DAG Placement & Bjork Memory Decay Warmups."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.kc import _mark_known, progress, restart_course, start_course, tutor_courses
from app.main import app
from app.kc_placement import (
    BJORK_SCALE_DAYS,
    PLACEMENT_SURMISE_STABILITY,
    STABILITY_ATTEMPT_1,
    STABILITY_ATTEMPT_2,
    STABILITY_ATTEMPT_3,
    UNSURE_CHOICE_ID,
    WARMUP_RS_THRESHOLD,
    answer_placement_probe,
    boosted_stability_on_warmup_pass,
    build_course_dag,
    course_warmups,
    initial_stability_for_session,
    retrieval_strength,
    skip_placement,
    start_placement,
    submit_warmup_check,
)
from app.models import KcEdge, KcGoal, KcNode, KcSession, KcState, LearnerCourseState, Student


def _mcq_block(stem: str, right: str, wrong: str) -> dict:
    return {
        "id": f"blk_{uuid.uuid4().hex[:8]}",
        "type": "mcq",
        "data": {
            "mode": "static",
            "question_stem": stem,
            "choices": [
                {"id": "opt_right", "text": right, "is_correct": True},
                {"id": "opt_wrong", "text": wrong, "is_correct": False},
            ],
        },
    }


def _retrieval_block(prompt: str, expected: str) -> dict:
    return {
        "id": f"blk_{uuid.uuid4().hex[:8]}",
        "type": "retrieval_check",
        "data": {
            "recall_prompt": prompt,
            "expected_fact": expected,
            "elaborative_why_prompt": "Why does that happen?",
            "expected_why_rationale": expected,
        },
    }


def _seed_dag_course(db, *, count: int = 6, with_edges: bool = True) -> tuple[KcGoal, list[KcNode]]:
    """Seed a ready N-node prerequisite chain course (c0 -> c1 -> ... -> c{N-1})."""
    suffix = uuid.uuid4().hex[:6]
    nodes: list[KcNode] = []
    for idx in range(count):
        code = f"f5-{suffix}-n{idx}"
        prereq = [nodes[idx - 1].code] if idx > 0 else []
        node = KcNode(
            code=code,
            title=f"Topic {idx + 1}: Concept {idx}",
            outline=f"Outline for concept {idx}",
            core_truth=f"Core truth {idx} explains step {idx}",
            prerequisite_codes=prereq,
            blocks=[
                _mcq_block(
                    stem=f"Everyday scenario for concept {idx}?",
                    right=f"Right explanation {idx}",
                    wrong=f"Common trap {idx}",
                ),
                _retrieval_block(
                    prompt=f"Quick recall for concept {idx}?",
                    expected=f"Core truth {idx} explains step {idx}",
                ),
            ],
        )
        db.add(node)
        db.flush()
        nodes.append(node)

    if with_edges:
        for idx in range(1, count):
            db.add(
                KcEdge(
                    from_kc=nodes[idx - 1].id,
                    to_kc=nodes[idx].id,
                    kind="prerequisite_of",
                    weight=1.0,
                )
            )

    goal = KcGoal(
        code=f"f5-course-{suffix}",
        title=f"F5 Course {suffix}",
        description="Structured prerequisite chain course.",
        audience="9-11",
        kind="mastery",
        target_kc_ids=[str(node.id) for node in nodes],
        ready=True,
    )
    db.add(goal)
    db.flush()
    return goal, nodes


def _seed_student(db, *, name: str = "Maya", is_test: bool = False) -> Student:
    student = Student(
        slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}",
        display_name=name,
        age=10,
        is_test=is_test,
    )
    db.add(student)
    db.flush()
    return student


# ---------------------------------------------------------------------------
# Part A: Hint-Weighted Stability (SS_k) & Bjork Decay (RS_k) Warmups
# ---------------------------------------------------------------------------


def test_hint_weighted_initial_stability_tiers() -> None:
    s1 = SimpleNamespace(
        block_results=[{"block_type": "mcq", "outcome": "passed", "attempts": 1}],
        move_attempts=1,
        hint_tier="nudge",
    )
    s2 = SimpleNamespace(
        block_results=[{"block_type": "mcq", "outcome": "passed", "attempts": 2}],
        move_attempts=2,
        hint_tier="nudge",
    )
    s3 = SimpleNamespace(
        block_results=[
            {"block_type": "mcq", "outcome": "passed", "attempts": 1},
            {"block_type": "socratic", "outcome": "passed", "attempts": 3, "hint_tier": "scaffold"},
        ],
        move_attempts=3,
        hint_tier="scaffold",
    )
    # Fast-tracked and curiosity blocks do not penalize independent stability.
    s_ft = SimpleNamespace(
        block_results=[
            {"block_type": "curiosity", "outcome": "engaged", "attempts": 3},
            {"block_type": "teach_back", "outcome": "passed", "attempts": 1},
            {"block_type": "mcq", "outcome": "fast_tracked", "attempts": 0},
        ],
        move_attempts=1,
        hint_tier="nudge",
    )
    assert initial_stability_for_session(s1) == STABILITY_ATTEMPT_1 == 1.0
    assert initial_stability_for_session(s2) == STABILITY_ATTEMPT_2 == 0.70
    assert initial_stability_for_session(s3) == STABILITY_ATTEMPT_3 == 0.45
    assert initial_stability_for_session(s_ft) == STABILITY_ATTEMPT_1 == 1.0


def test_mark_known_persists_hint_weighted_stability() -> None:
    db = SessionLocal()
    try:
        goal, nodes = _seed_dag_course(db, count=4)
        student = _seed_student(db)

        sess_attempt2 = KcSession(
            student_id=student.id,
            goal_id=goal.id,
            kc_id=nodes[0].id,
            block_results=[{"block_type": "mcq", "outcome": "passed", "attempts": 2}],
        )
        db.add(sess_attempt2)
        db.flush()
        _mark_known(db, sess_attempt2, nodes[0])

        st0 = db.scalar(select(KcState).where(KcState.student_id == student.id, KcState.kc_id == nodes[0].id))
        assert st0 is not None
        assert st0.status == "known"
        assert st0.stability == 0.70

        sess_attempt3 = KcSession(
            student_id=student.id,
            goal_id=goal.id,
            kc_id=nodes[1].id,
            block_results=[{"block_type": "topic_goal", "outcome": "passed", "attempts": 3, "hint_tier": "scaffold"}],
        )
        db.add(sess_attempt3)
        db.flush()
        _mark_known(db, sess_attempt3, nodes[1])

        st1 = db.scalar(select(KcState).where(KcState.student_id == student.id, KcState.kc_id == nodes[1].id))
        assert st1 is not None
        assert st1.stability == 0.45
    finally:
        db.rollback()
        db.close()


def test_bjork_decay_formula_and_warmup_boost() -> None:
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    # Exact Bjork formula check: exp(-days / (7.0 * SS_k))
    assert retrieval_strength(1.0, now, status="known", now=now) == 1.0
    five_days_ago = now - timedelta(days=5)
    expected_rs = round(math.exp(-5.0 / (BJORK_SCALE_DAYS * 1.0)), 4)
    assert retrieval_strength(1.0, five_days_ago, status="known", now=now) == expected_rs
    assert expected_rs < WARMUP_RS_THRESHOLD  # ~0.4895 < 0.65 -> warmup due!

    # Unknown / fragile nodes never trigger decay warmups.
    assert retrieval_strength(1.0, five_days_ago, status="fragile", now=now) is None
    assert retrieval_strength(0.0, five_days_ago, status="known", now=now) is None

    db = SessionLocal()
    try:
        # End-to-end warmup surfacing in progress() + submit boost SS_k <- 1.8 * SS_k + 0.5
        goal, nodes = _seed_dag_course(db, count=4)
        student = _seed_student(db)
        old_time = datetime.now(timezone.utc) - timedelta(days=6)
        db.add(
            KcState(
                student_id=student.id,
                kc_id=nodes[0].id,
                status="known",
                stability=0.70,
                last_practiced=old_time,
            )
        )
        db.add(
            KcState(
                student_id=student.id,
                kc_id=nodes[1].id,
                status="known",
                stability=1.0,
                last_practiced=datetime.now(timezone.utc) - timedelta(hours=2),
            )
        )
        db.flush()

        prog = progress(db, goal, student)
        assert len(prog["warmups"]) == 1
        warmup = prog["warmups"][0]
        assert warmup["kc_id"] == str(nodes[0].id)
        assert warmup["retrieval_strength"] < WARMUP_RS_THRESHOLD
        # Public warmup payload must never leak answer-key fields.
        assert "expected_choice_id" not in warmup
        assert "expected_phrases" not in warmup
        assert "expected_summary" not in warmup

        # Course card reports warmup_count cleanly.
        cards = tutor_courses(db, student_id=student.id)
        matching = next(c for c in cards if c["id"] == str(goal.id))
        assert matching["warmup_count"] == 1

        # Zero-shame miss: does not reduce stability or demote status.
        missed = submit_warmup_check(
            db,
            goal=goal,
            student=student,
            node=nodes[0],
            answer="completely unrelated guess",
        )
        assert missed["passed"] is False
        assert missed["old_stability"] == 0.70
        assert missed["new_stability"] == 0.70
        assert "refresher" in missed["feedback"].lower()

        # Pass boosts stability = round(1.8 * 0.70 + 0.5, 2) = 1.76 and clears warmup!
        passed = submit_warmup_check(
            db,
            goal=goal,
            student=student,
            node=nodes[0],
            answer="Core truth 0 explains step 0",
        )
        assert passed["passed"] is True
        assert passed["new_stability"] == boosted_stability_on_warmup_pass(0.70) == 1.76
        assert passed["retrieval_strength"] == 1.0

        prog_after = progress(db, goal, student)
        assert prog_after["warmups"] == []
        unit0 = next(u for u in prog_after["units"] if u["id"] == str(nodes[0].id))
        assert unit0["stability"] == 1.76
        assert unit0["needs_warmup"] is False
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# Part B: Cold-Start Topological Median DAG Placement
# ---------------------------------------------------------------------------


def test_build_course_dag_topological_order_and_ancestors() -> None:
    db = SessionLocal()
    try:
        goal, nodes = _seed_dag_course(db, count=5, with_edges=True)
        # Pass targets in scrambled order to verify topological depth sorts prerequisites first.
        dag = build_course_dag(db, list(reversed(nodes)))
        assert dag.ordered_ids == [node.id for node in nodes]
        assert dag.depth_by_id[nodes[0].id] == 0
        assert dag.depth_by_id[nodes[4].id] == 4
        assert dag.ancestors_by_id[nodes[3].id] == {nodes[0].id, nodes[1].id, nodes[2].id}
        assert dag.descendants_by_id[nodes[1].id] == {nodes[2].id, nodes[3].id, nodes[4].id}
    finally:
        db.rollback()
        db.close()


def test_placement_binary_search_surmise_and_zpd_fringe() -> None:
    """6-node chain: child passes n3 (median), misses n5 & n4 -> surmises {n0..n3} and starts at n4."""
    db = SessionLocal()
    try:
        goal, nodes = _seed_dag_course(db, count=6, with_edges=True)
        student = _seed_student(db)

        prog_before = progress(db, goal, student)
        assert prog_before["placement"]["eligible"] is True
        assert prog_before["placement"]["max_probes"] == 3  # ceil(log2(6)) = 3

        started = start_placement(db, goal, student)
        assert started["status"] == "in_progress"
        probe1 = started["probe"]
        assert probe1 is not None
        # Median of 6 items [0,1,2,3,4,5] is index 3 (nodes[3]).
        assert probe1["kc_id"] == str(nodes[3].id)
        assert probe1["unsure_choice_id"] == UNSURE_CHOICE_ID
        assert any(c["id"] == UNSURE_CHOICE_ID for c in probe1["choices"])
        assert "expected_choice_id" not in probe1

        # Child answers probe 1 correctly -> narrows to upper half [nodes[4], nodes[5]].
        step2 = answer_placement_probe(
            db,
            goal=goal,
            student=student,
            kc_id=nodes[3].id,
            choice_id="opt_right",
        )
        assert step2["status"] == "in_progress"
        assert step2["last_passed"] is True
        assert step2["probe"]["kc_id"] == str(nodes[5].id)  # median of [4, 5] is index 1 -> nodes[5]

        # Child clicks zero-shame "Not sure yet" on nodes[5] -> narrows to [nodes[4]].
        step3 = answer_placement_probe(
            db,
            goal=goal,
            student=student,
            kc_id=nodes[5].id,
            choice_id=UNSURE_CHOICE_ID,
            unsure=True,
        )
        assert step3["status"] == "in_progress"
        assert step3["last_passed"] is False
        assert step3["probe"]["kc_id"] == str(nodes[4].id)

        # Child misses nodes[4] -> converges cleanly in 3 probes!
        done = answer_placement_probe(
            db,
            goal=goal,
            student=student,
            kc_id=nodes[4].id,
            choice_id="opt_wrong",
        )
        assert done["status"] == "completed"
        assert done["probes_used"] == 3
        assert done["surmised_count"] == 4
        assert done["surmised_kc_ids"] == [str(nodes[i].id) for i in range(4)]
        assert done["starting_component"]["id"] == str(nodes[4].id)

        # Verify persisted KcState rows have stability=0.75 and source='placement_surmise'.
        for idx in range(4):
            st = db.scalar(select(KcState).where(KcState.student_id == student.id, KcState.kc_id == nodes[idx].id))
            assert st is not None
            assert st.status == "known"
            assert st.stability == PLACEMENT_SURMISE_STABILITY == 0.75
            assert st.result["source"] == "placement_surmise"
        assert db.scalar(select(KcState).where(KcState.student_id == student.id, KcState.kc_id == nodes[4].id)) is None

        # Verify LearnerCourseState recorded placement_status = 'completed'.
        cstate = db.scalar(
            select(LearnerCourseState).where(
                LearnerCourseState.student_id == student.id,
                LearnerCourseState.goal_id == goal.id,
            )
        )
        assert cstate is not None
        assert cstate.placement_status == "completed"

        # Starting the course automatically opens ZPD frontier nodes[4]!
        sess = start_course(db, student, goal)
        assert sess.kc_id == nodes[4].id

        # Restarting the course resets placement_status back to 'not_started' & re-enables entry card.
        restarted = restart_course(db, goal, student)
        assert restarted["placement"]["status"] == "not_started"
        assert restarted["placement"]["eligible"] is True
    finally:
        db.rollback()
        db.close()


def test_placement_ineligible_under_4_and_harness_isolated_and_skip() -> None:
    db = SessionLocal()
    client = TestClient(app)
    small_goal_id = big_goal_id = real_id = harness_id = None
    node_ids: list[uuid.UUID] = []
    try:
        small_goal, small_nodes = _seed_dag_course(db, count=3)
        big_goal, nodes = _seed_dag_course(db, count=5)
        real_student = _seed_student(db, name="Leo", is_test=False)
        harness_student = _seed_student(db, name="AI_Child99", is_test=True)
        small_goal_id, big_goal_id = small_goal.id, big_goal.id
        real_id, harness_id = real_student.id, harness_student.id
        node_ids = [n.id for n in small_nodes] + [n.id for n in nodes]
        db.commit()

        # Course with < 4 components is not eligible.
        r_small = client.get(f"/kc/tutor/courses/{small_goal_id}/placement?student_id={real_id}")
        assert r_small.status_code == 200
        assert r_small.json()["eligible"] is False

        # Harness / test child cannot write placement to learner_course_state.
        r_harness = client.post(
            f"/kc/tutor/courses/{big_goal_id}/placement/start",
            json={"student_id": str(harness_id)},
        )
        assert r_harness.status_code == 422
        assert (
            db.scalar(
                select(LearnerCourseState).where(
                    LearnerCourseState.student_id == harness_id,
                    LearnerCourseState.goal_id == big_goal_id,
                )
            )
            is None
        )

        # Real student skips placement ("Start from the beginning").
        r_skip = client.post(
            f"/kc/tutor/courses/{big_goal_id}/placement/skip",
            json={"student_id": str(real_id)},
        )
        assert r_skip.status_code == 200
        assert r_skip.json()["status"] == "skipped"

        r_after = client.get(f"/kc/tutor/courses/{big_goal_id}/placement?student_id={real_id}")
        assert r_after.status_code == 200
        assert r_after.json()["status"] == "skipped"
        assert r_after.json()["eligible"] is False

        # HTTP warmup submit endpoint works end-to-end too.
        db.add(
            KcState(
                student_id=real_id,
                kc_id=nodes[0].id,
                status="known",
                stability=0.75,
                last_practiced=datetime.now(timezone.utc) - timedelta(days=5),
            )
        )
        db.commit()
        r_warmup = client.post(
            f"/kc/tutor/courses/{big_goal_id}/warmups/{nodes[0].id}/submit",
            json={"student_id": str(real_id), "answer": "Core truth 0 explains step 0"},
        )
        assert r_warmup.status_code == 200
        body = r_warmup.json()
        assert body["passed"] is True
        assert body["new_stability"] == round(1.8 * 0.75 + 0.5, 2) == 1.85
    finally:
        # Clean up committed test rows cleanly.
        db.rollback()
        for gid in (small_goal_id, big_goal_id):
            if gid is not None:
                row = db.get(KcGoal, gid)
                if row is not None:
                    db.delete(row)
        for nid in node_ids:
            row = db.get(KcNode, nid)
            if row is not None:
                db.delete(row)
        for sid in (real_id, harness_id):
            if sid is not None:
                row = db.get(Student, sid)
                if row is not None:
                    db.delete(row)
        db.commit()
        db.close()
