"""End-to-end tests for F6: Parent Co-Pilot digests, course policy locks, and revocable Teacher Share snapshots."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.graph2.state import copy_note_for_session_open
from app.kc import _run_graph2_sync_close
from app.main import app
from app.models import (
    BlindExam,
    BlindExamAttempt,
    KcGoal,
    KcNode,
    KcSession,
    KcState,
    LearnerCourseState,
    Parent,
    ParentSessionDigest,
    ParentStudent,
    Student,
    StudentEducationalState,
    TeacherShareToken,
    TutorProfile,
)
from app.parent_copilot import format_parent_locks_note
from app.tutor_profile import DEFAULT_PROFILE


def _seed_parent_and_child(*, is_test: bool = False, display_name: str = "Maya Patel"):
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]
    student = Student(
        slug=f"f6-{tag}",
        display_name=display_name,
        age=10,
        interests=["dogs", "soccer"],
        is_test=is_test,
        child_profile={"grade_band": "upper_elementary"},
    )
    parent = Parent(name=f"Parent {tag}")
    other_parent = Parent(name=f"Other Parent {tag}")
    tutor = TutorProfile(
        id=f"tutor-{tag}",
        slug=f"tutor-{tag}",
        name=f"Tutor {tag}",
        description="Shared tutor preset",
        persona=str(DEFAULT_PROFILE["persona"]),
        lexicon=str(DEFAULT_PROFILE["lexicon"]),
        metaphors=str(DEFAULT_PROFILE["metaphors"]),
        sidekick=str(DEFAULT_PROFILE["sidekick"]),
    )
    node1 = KcNode(
        code=f"F6-N1-{tag}",
        title="War Guilt Clause",
        description="Article 231 placed responsibility on Germany.",
        core_truth="Article 231 made Germany legally responsible for starting WWI.",
        blocks=[{"id": "b1", "type": "topic_goal", "data": {"topic": "War Guilt", "goal": "Explain Article 231"}}],
        mastery_spec={},
    )
    node2 = KcNode(
        code=f"F6-N2-{tag}",
        title="League of Nations",
        description="International peace organization.",
        core_truth="The League lacked its own army to enforce decisions.",
        blocks=[{"id": "b2", "type": "topic_goal", "data": {"topic": "League", "goal": "Explain its limits"}}],
        mastery_spec={},
    )
    db.add_all([student, parent, other_parent, tutor, node1, node2])
    db.flush()
    goal = KcGoal(
        code=f"F6-G-{tag}",
        title=f"Treaty of Versailles {tag}",
        description="Post-WWI peace settlement.",
        audience="9-11",
        kind="mastery",
        target_kc_ids=[str(node1.id), str(node2.id)],
        standards=["HIST.5.1", "HIST.5.2"],
        ready=True,
        catalog_tier="core",
        default_archetype="historical_causation",
    )
    db.add(goal)
    db.flush()
    if not is_test:
        db.add(ParentStudent(parent_id=parent.id, student_id=student.id))
    db.commit()
    ids = {
        "student_id": student.id,
        "parent_id": parent.id,
        "other_parent_id": other_parent.id,
        "tutor_id": tutor.id,
        "goal_id": goal.id,
        "node1_id": node1.id,
        "node2_id": node2.id,
    }
    db.close()
    return ids


def test_component_close_auto_persists_digest_for_real_child_and_skips_harness() -> None:
    real = _seed_parent_and_child(is_test=False)
    harness = _seed_parent_and_child(is_test=True, display_name="AI_Child_Test")

    with SessionLocal() as db:
        student = db.get(Student, real["student_id"])
        goal = db.get(KcGoal, real["goal_id"])
        node1 = db.get(KcNode, real["node1_id"])
        assert student and goal and node1

        db.add(KcState(student_id=student.id, kc_id=node1.id, status="known"))
        session = KcSession(
            student_id=student.id,
            goal_id=goal.id,
            kc_id=node1.id,
            status="completed",
            verdict="known",
            reveals=0,
            block_results=[{"block_id": "b1", "outcome": "passed", "verdict": "known"}],
        )
        db.add(session)
        db.flush()

        _run_graph2_sync_close(db, session, node1, list(node1.blocks or []))
        # Second call stays idempotent (one digest per session_id).
        _run_graph2_sync_close(db, session, node1, list(node1.blocks or []))
        db.commit()

        digests = db.scalars(
            select(ParentSessionDigest).where(ParentSessionDigest.student_id == student.id)
        ).all()
        assert len(digests) == 1
        d = digests[0]
        assert d.trajectory_state in {"flourishing", "steady_progress", "needs_reinforcement", "struggling", "returning"}
        assert "Maya" in d.summary
        assert len(d.talking_points) == 3
        assert any("War Guilt Clause" in p for p in d.talking_points)

        # Harness / test child must NEVER persist ParentSessionDigest.
        h_student = db.get(Student, harness["student_id"])
        h_goal = db.get(KcGoal, harness["goal_id"])
        h_node = db.get(KcNode, harness["node1_id"])
        assert h_student and h_goal and h_node
        h_session = KcSession(
            student_id=h_student.id,
            goal_id=h_goal.id,
            kc_id=h_node.id,
            status="completed",
            verdict="known",
        )
        db.add(h_session)
        db.flush()
        _run_graph2_sync_close(db, h_session, h_node, list(h_node.blocks or []))
        db.commit()
        h_digests = db.scalars(
            select(ParentSessionDigest).where(ParentSessionDigest.student_id == h_student.id)
        ).all()
        assert h_digests == []


def test_parent_interventions_write_only_course_state_freeze_active_sessions_and_flow_to_next() -> None:
    ids = _seed_parent_and_child()
    client = TestClient(app)

    # Create an active in-progress session BEFORE parent applies locks.
    with SessionLocal() as db:
        open_session = KcSession(
            student_id=ids["student_id"],
            goal_id=ids["goal_id"],
            kc_id=ids["node1_id"],
            tutor_profile_id=ids["tutor_id"],
            status="in_progress",
            frozen_tutor_note="Original frozen note.",
        )
        db.add(open_session)
        db.commit()
        open_session_id = open_session.id

    # Unlinked parent -> 403
    denied = client.post(
        f"/parents/{ids['other_parent_id']}/children/{ids['student_id']}/interventions/apply",
        json={"course_id": str(ids["goal_id"]), "locks": {"more_guided_examples": True}},
    )
    assert denied.status_code == 403

    # Unknown lock key -> 422
    bad_key = client.post(
        f"/parents/{ids['parent_id']}/children/{ids['student_id']}/interventions/apply",
        json={"course_id": str(ids["goal_id"]), "locks": {"bypass_safety": True}},
    )
    assert bad_key.status_code == 422

    # Valid apply -> persists on LearnerCourseState without mutating TutorProfile or open session
    ok = client.post(
        f"/parents/{ids['parent_id']}/children/{ids['student_id']}/interventions/apply",
        json={
            "course_id": str(ids["goal_id"]),
            "course_mode": "exam_prep",
            "locks": {"more_guided_examples": True, "anchor_in_interest": "dogs"},
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["course_mode"] == "exam_prep"
    assert body["parent_policy_locks"] == {"more_guided_examples": True, "anchor_in_interest": "dogs"}
    assert "guided examples" in body["next_session_guidance"]
    assert "dogs" in body["next_session_guidance"]

    with SessionLocal() as db:
        # Shared TutorProfile untouched
        tutor = db.get(TutorProfile, ids["tutor_id"])
        assert tutor is not None and tutor.persona == str(DEFAULT_PROFILE["persona"])

        # Active in-progress session note stayed frozen
        still_open = db.get(KcSession, open_session_id)
        assert still_open is not None and still_open.frozen_tutor_note == "Original frozen note."

        # Next component open picks up the plain-language parent guidance line (with no numbers)
        student = db.get(Student, ids["student_id"])
        goal = db.get(KcGoal, ids["goal_id"])
        node2 = db.get(KcNode, ids["node2_id"])
        assert student and goal and node2
        next_note = copy_note_for_session_open(db, student=student, goal=goal, node=node2)
        assert "Parent guidance:" in next_note
        assert "dogs" in next_note
        assert "0.50" not in next_note

    # Clearing locks returns guidance to empty string
    cleared = client.post(
        f"/parents/{ids['parent_id']}/children/{ids['student_id']}/interventions/apply",
        json={
            "course_id": str(ids["goal_id"]),
            "course_mode": "mastery",
            "locks": {"more_guided_examples": False, "anchor_in_interest": ""},
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["parent_policy_locks"] == {}
    assert cleared.json()["next_session_guidance"] == ""
    with SessionLocal() as db:
        cstate = db.scalar(
            select(LearnerCourseState).where(
                LearnerCourseState.student_id == ids["student_id"],
                LearnerCourseState.goal_id == ids["goal_id"],
            )
        )
        assert format_parent_locks_note(cstate) == ""


def test_teacher_share_sha256_read_only_privacy_and_instant_revocation() -> None:
    ids = _seed_parent_and_child(display_name="Maya Patel")
    client = TestClient(app)

    # Seed mastery, misconception, radar state, and F2 blind exam gain
    with SessionLocal() as db:
        db.add(KcState(student_id=ids["student_id"], kc_id=ids["node1_id"], status="known"))
        db.add(KcState(student_id=ids["student_id"], kc_id=ids["node2_id"], status="fragile"))
        db.add(
            LearnerCourseState(
                student_id=ids["student_id"],
                goal_id=ids["goal_id"],
                misconceptions=[{"text": "All countries were punished equally.", "resolved": False}],
                parent_policy_locks={"more_guided_examples": True},
            )
        )
        db.add(
            StudentEducationalState(
                student_id=ids["student_id"],
                biomarkers={
                    "own_words_pass": 3,
                    "hard_recovery_pass": 1,
                    "on_topic_inquiry_before_known": 2,
                    "multi_perspective_synthesis": 0,
                },
            )
        )
        pre_exam = BlindExam(goal_id=ids["goal_id"], phase="pre", version=1, spec_fingerprint="abc", items=[], rubric_key={})
        post_exam = BlindExam(goal_id=ids["goal_id"], phase="post", version=1, spec_fingerprint="abc", items=[], rubric_key={})
        db.add_all([pre_exam, post_exam])
        db.flush()
        pre_att = BlindExamAttempt(
            exam_id=pre_exam.id,
            goal_id=ids["goal_id"],
            student_id=ids["student_id"],
            phase="pre",
            mode="human",
            status="graded",
            raw_score=0.4,
            submitted_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(pre_att)
        db.flush()
        post_att = BlindExamAttempt(
            exam_id=post_exam.id,
            goal_id=ids["goal_id"],
            student_id=ids["student_id"],
            phase="post",
            mode="human",
            status="graded",
            raw_score=0.7,
            paired_pre_attempt_id=pre_att.id,
            paired_pre_score=0.4,
            hake_g=0.5,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(post_att)
        db.commit()

    # 1. Copilot endpoint returns full dual-graph summary for linked parent
    cop = client.get(f"/parents/{ids['parent_id']}/children/{ids['student_id']}/copilot")
    assert cop.status_code == 200
    cop_json = cop.json()
    assert cop_json["biomarkers"]["own_words_pass"] == 3
    assert len(cop_json["radar"]["spokes"]) == 8
    course_card = next(c for c in cop_json["courses"] if c["course_id"] == str(ids["goal_id"]))
    assert course_card["known_count"] == 1
    assert course_card["fragile_count"] == 1
    assert course_card["blind_exam"]["hake_g"] == 0.5

    # 2. Create scoped revocable Teacher Share token
    created = client.post(
        f"/parents/{ids['parent_id']}/children/{ids['student_id']}/teacher-shares",
        json={"course_id": str(ids["goal_id"]), "label": "Ms. Lee — 5th Grade", "expires_in_days": 14},
    )
    assert created.status_code == 200
    share = created.json()
    raw_token = share["share_token"]
    assert raw_token and share["share_path"] == f"/teacher/share/{raw_token}"

    # Verify DB stores ONLY SHA-256 hash, never raw token
    with SessionLocal() as db:
        row = db.get(TeacherShareToken, uuid.UUID(share["id"]))
        assert row is not None
        assert row.token_hash != raw_token
        assert row.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Listing shares never returns raw token or token_hash
    listed = client.get(f"/parents/{ids['parent_id']}/children/{ids['student_id']}/teacher-shares")
    assert listed.status_code == 200
    assert all("share_token" not in item and "token_hash" not in item for item in listed.json())

    # 3. Resolve public read-only Teacher Snapshot
    snap_res = client.get(f"/teacher/share/{raw_token}")
    assert snap_res.status_code == 200
    snap = snap_res.json()
    assert snap["learner"]["first_name"] == "Maya"
    assert "Patel" not in str(snap)  # last name minimized out
    assert "messages" not in snap and "prompts" not in snap
    assert len(snap["courses"]) == 1  # course-scoped
    c0 = snap["courses"][0]
    assert "parent_policy_locks" not in c0
    assert c0["known_topics"] == ["War Guilt Clause"]
    assert c0["fragile_topics"] == ["League of Nations"]
    assert c0["active_misconceptions"] == ["All countries were punished equally."]
    assert c0["standards"] == ["HIST.5.1", "HIST.5.2"]
    assert c0["blind_exam"]["hake_g"] == 0.5
    # Under-3-observation spokes stay hollow (never leaking 0.50 prior)
    assert all(sp["hollow"] is True and sp["score"] is None for sp in snap["radar"]["spokes"])

    # 4. Revoke token -> immediate 404
    rev = client.delete(f"/parents/{ids['parent_id']}/children/{ids['student_id']}/teacher-shares/{share['id']}")
    assert rev.status_code == 200
    assert rev.json()["status"] == "revoked"
    after_revoke = client.get(f"/teacher/share/{raw_token}")
    assert after_revoke.status_code == 404

    # 5. Unknown/forged token -> 404
    assert client.get("/teacher/share/not-a-real-token-xyz").status_code == 404
