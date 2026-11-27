"""End-to-end and unit tests for F2 Quarantined Blind Pre/Post Evaluator."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.blind_evaluator import (
    blueprint_counts,
    build_deterministic_exam_items,
    compute_hake_gain,
    load_quarantined_course_context,
)
from app.database import SessionLocal
from app.main import app
from app.models import (
    BlindExam,
    BlindExamAttempt,
    HarnessChat,
    HarnessPersona,
    HarnessRun,
    KcGoal,
    KcMessage,
    KcNode,
    KcSession,
    KcState,
    Parent,
    ParentStudent,
    Student,
)

client = TestClient(app)


def _create_sample_course(db) -> tuple[KcGoal, list[KcNode]]:
    suffix = uuid.uuid4().hex[:8]
    n1 = KcNode(
        code=f"f2-node-1-{suffix}",
        title="Causes of Inflation",
        description="Explain how rising money supply and supply shocks push up price levels.",
        core_truth="Inflation rises when aggregate demand outpaces supply or production costs jump.",
        mastery_spec={
            "archetype": "causal_explanation",
            "skills": ["causes", "evidence"],
            "claims": [
                {
                    "id": "c1",
                    "statement": "Identify what drives a sustained rise in the price level.",
                    "skills": ["causes"],
                }
            ],
        },
        # Secret lesson blocks that blind_evaluator MUST NEVER read or leak!
        blocks=[
            {
                "id": "blk_secret_lesson",
                "type": "explanation",
                "data": {"block_title": "SECRET_TUTOR_CANARY_999", "topics": []},
            }
        ],
    )
    n2 = KcNode(
        code=f"f2-node-2-{suffix}",
        title="Measuring CPI",
        description="Compute percentage change across a fixed market basket.",
        core_truth="Inflation rate equals ((CPI_new - CPI_old) / CPI_old) * 100.",
        mastery_spec={
            "archetype": "procedural_transfer",
            "skills": ["errors", "transfer"],
            "claims": [
                {
                    "id": "c2",
                    "statement": "Calculate inflation rate from two index values.",
                    "skills": ["transfer", "errors"],
                }
            ],
        },
        blocks=[],
    )
    db.add_all([n1, n2])
    db.flush()

    goal = KcGoal(
        code=f"f2-course-{suffix}",
        title=f"Inflation Proof Course {suffix}",
        description="Macroeconomics unit on inflation causes and CPI.",
        audience="12-14",
        standards=[{"code": "ECON-1", "text": "Explain causes and measurement of inflation."}],
        target_kc_ids=[str(n1.id), str(n2.id)],
        ready=True,
    )
    db.add(goal)
    db.flush()
    return goal, [n1, n2]


def _cleanup(db, *, goal_ids=(), node_ids=(), student_ids=(), parent_ids=(), run_ids=()) -> None:
    if run_ids:
        db.execute(delete(HarnessRun).where(HarnessRun.id.in_(run_ids)))
    if student_ids:
        db.execute(delete(KcState).where(KcState.student_id.in_(student_ids)))
        db.execute(delete(KcSession).where(KcSession.student_id.in_(student_ids)))
        db.execute(delete(BlindExamAttempt).where(BlindExamAttempt.student_id.in_(student_ids)))
    if goal_ids:
        db.execute(delete(BlindExam).where(BlindExam.goal_id.in_(goal_ids)))
        db.execute(delete(KcGoal).where(KcGoal.id.in_(goal_ids)))
    if node_ids:
        db.execute(delete(KcNode).where(KcNode.id.in_(node_ids)))
    if parent_ids:
        db.execute(delete(ParentStudent).where(ParentStudent.parent_id.in_(parent_ids)))
        db.execute(delete(Parent).where(Parent.id.in_(parent_ids)))
    if student_ids:
        db.execute(delete(Student).where(Student.id.in_(student_ids)))
    db.commit()


def test_hake_gain_formula_and_blueprint_split() -> None:
    assert compute_hake_gain(0.40, 0.70) == 0.5
    assert compute_hake_gain(0.0, 0.80) == 0.8
    # Floor at max(1 - pre, 0.05) avoids division by zero when pre == 1.0.
    assert compute_hake_gain(1.0, 1.0) == 0.0
    assert compute_hake_gain(0.98, 1.0) == 0.4

    counts = blueprint_counts(10)
    assert counts == {"scenario_mcq": 4, "misconception_trap": 3, "short_transfer": 3}
    assert sum(blueprint_counts(7).values()) == 7


def test_quarantined_context_never_leaks_lesson_blocks_and_caches_frozen_exam() -> None:
    goal_id = None
    node_ids: list = []
    try:
        with SessionLocal() as db:
            goal, nodes = _create_sample_course(db)
            goal_id = goal.id
            node_ids = [n.id for n in nodes]
            db.commit()

            ctx = load_quarantined_course_context(db, goal.id)
            assert "SECRET_TUTOR_CANARY_999" not in str(ctx)
            assert len(ctx["components"]) == 2
            assert ctx["spec_fingerprint"]

        # 1. First prompt call reports uncached and contains zero secret block text.
        p1 = client.post(f"/kc/tutor/courses/{goal_id}/exam/prompt", json={"phase": "pre"})
        assert p1.status_code == 200
        body1 = p1.json()
        assert body1["cached"] is False
        assert "SECRET_TUTOR_CANARY_999" not in body1["user_prompt"]
        assert body1["target_counts"] == {"scenario_mcq": 4, "misconception_trap": 3, "short_transfer": 3}

        # 2. Store deterministic Pre-Test and verify learner payload strips answer keys.
        stored = client.post(
            f"/kc/tutor/courses/{goal_id}/exam",
            json={"phase": "pre", "use_deterministic_fallback": True},
        )
        assert stored.status_code == 200
        exam_public = stored.json()
        assert exam_public["item_count"] == 10
        for item in exam_public["items"]:
            assert "correct_choice_id" not in item
            assert "trap_rationale" not in item
            assert "rubric_key" not in item
            assert "key_points" not in item

        # 3. Second prompt call returns cached frozen exam directly (zero LLM call).
        p2 = client.post(f"/kc/tutor/courses/{goal_id}/exam/prompt", json={"phase": "pre"})
        assert p2.status_code == 200
        assert p2.json()["cached"] is True
        assert p2.json()["exam"]["id"] == exam_public["id"]
    finally:
        with SessionLocal() as db:
            _cleanup(db, goal_ids=[goal_id] if goal_id else [], node_ids=node_ids)


def test_pre_post_grading_hake_gain_and_parent_read_only_access() -> None:
    goal_id = None
    node_ids: list = []
    student_id = None
    parent_id = None
    other_parent_id = None
    try:
        with SessionLocal() as db:
            goal, nodes = _create_sample_course(db)
            student = Student(slug=f"f2-ada-{uuid.uuid4().hex[:8]}", display_name="Ada", age=12, is_test=False)
            parent = Parent(name="Parent A")
            other_parent = Parent(name="Parent B")
            db.add_all([student, parent, other_parent])
            db.flush()
            db.add(ParentStudent(parent_id=parent.id, student_id=student.id))
            db.commit()
            goal_id = goal.id
            node_ids = [n.id for n in nodes]
            student_id = student.id
            parent_id = parent.id
            other_parent_id = other_parent.id

        # Create frozen Pre and Post forms.
        pre_exam = client.post(
            f"/kc/tutor/courses/{goal_id}/exam",
            json={"phase": "pre", "use_deterministic_fallback": True},
        ).json()
        post_exam = client.post(
            f"/kc/tutor/courses/{goal_id}/exam",
            json={"phase": "post", "use_deterministic_fallback": True},
        ).json()

        # Fetch internal answer keys from DB strictly for test assertion.
        with SessionLocal() as db:
            pre_row = db.get(BlindExam, uuid.UUID(pre_exam["id"]))
            post_row = db.get(BlindExam, uuid.UUID(post_exam["id"]))
            assert pre_row is not None and post_row is not None
            pre_items = list(pre_row.items)
            post_items = list(post_row.items)

        # Pre-test: child answers half MCQs right, blank short transfers -> low baseline score.
        pre_answers = {}
        for idx, item in enumerate(pre_items):
            if item["kind"] in {"scenario_mcq", "misconception_trap"}:
                pre_answers[item["id"]] = item["correct_choice_id"] if idx < 3 else "d"
            else:
                pre_answers[item["id"]] = ""
        pre_res = client.post(
            f"/kc/tutor/courses/{goal_id}/exam/attempts",
            json={"exam_id": pre_exam["id"], "student_id": str(student_id), "answers": pre_answers},
        )
        assert pre_res.status_code == 200
        pre_body = pre_res.json()
        assert pre_body["phase"] == "pre"
        assert pre_body["hake_g"] is None
        assert 0.0 < pre_body["raw_score"] < 0.5

        # Post-test: child answers all MCQs right + LLM transfer grades 2/2 -> strong positive Hake gain.
        post_answers = {}
        transfer_grades = []
        for item in post_items:
            if item["kind"] in {"scenario_mcq", "misconception_trap"}:
                post_answers[item["id"]] = item["correct_choice_id"]
            else:
                post_answers[item["id"]] = "Inflation rises when aggregate demand outpaces supply or production costs jump."
                transfer_grades.append({"item_id": item["id"], "points": 2, "feedback": "Clear transfer."})

        # Verify grade-prompt builds transfer rubric bundle cleanly.
        gp = client.post(
            f"/kc/tutor/courses/{goal_id}/exam/grade-prompt",
            json={"exam_id": post_exam["id"], "answers": post_answers},
        )
        assert gp.status_code == 200
        assert gp.json()["has_transfer_items"] is True
        assert len(gp.json()["item_ids"]) == 3

        post_res = client.post(
            f"/kc/tutor/courses/{goal_id}/exam/attempts",
            json={
                "exam_id": post_exam["id"],
                "student_id": str(student_id),
                "answers": post_answers,
                "transfer_grades": transfer_grades,
            },
        )
        assert post_res.status_code == 200
        post_body = post_res.json()
        assert post_body["raw_score"] == 1.0
        assert post_body["paired_pre_attempt_id"] == pre_body["id"]
        assert post_body["paired_pre_score"] == pre_body["raw_score"]
        assert post_body["hake_g"] == 1.0

        # Summary endpoint reflects paired Pre/Post + Hake gain.
        summary = client.get(f"/kc/tutor/courses/{goal_id}/exam?student_id={student_id}&phase=post")
        assert summary.status_code == 200
        assert summary.json()["pre_score"] == pre_body["raw_score"]
        assert summary.json()["post_score"] == 1.0
        assert summary.json()["hake_g"] == 1.0

        # Linked parent can read exam summary; unlinked parent is denied.
        parent_ok = client.get(f"/parents/{parent_id}/children/{student_id}/courses/{goal_id}/exam")
        assert parent_ok.status_code == 200
        assert parent_ok.json()["hake_g"] == 1.0

        parent_denied = client.get(f"/parents/{other_parent_id}/children/{student_id}/courses/{goal_id}/exam")
        assert parent_denied.status_code == 403
    finally:
        with SessionLocal() as db:
            _cleanup(
                db,
                goal_ids=[goal_id] if goal_id else [],
                node_ids=node_ids,
                student_ids=[student_id] if student_id else [],
                parent_ids=[p for p in (parent_id, other_parent_id) if p],
            )


def test_harness_epistemic_sandbox_uses_only_tutor_messages_and_quarantines_learner_state() -> None:
    goal_id = None
    node_ids: list = []
    test_student_id = None
    run_id = None
    try:
        with SessionLocal() as db:
            goal, nodes = _create_sample_course(db)
            test_student = Student(slug=f"f2-harness-{uuid.uuid4().hex[:8]}", display_name="HarnessChild", age=12, is_test=True)
            db.add(test_student)
            db.flush()
            session = KcSession(
                student_id=test_student.id,
                goal_id=goal.id,
                kc_id=nodes[0].id,
                status="completed",
            )
            db.add(session)
            db.flush()
            db.add_all(
                [
                    KcMessage(session_id=session.id, seq=1, role="assistant", content="TUTOR_TAUGHT_ONLY: Inflation rises when demand exceeds supply."),
                    KcMessage(session_id=session.id, seq=2, role="user", content="CHILD_PRIVATE_MSG_SHOULD_NOT_APPEAR"),
                    KcMessage(session_id=session.id, seq=3, role="assistant", content="TUTOR_TAUGHT_ONLY: CPI percent change uses old CPI as denominator."),
                ]
            )
            run = HarnessRun(status="completed", plan={"run_blind_post_test": True})
            db.add(run)
            db.flush()
            chat = HarnessChat(
                run_id=run.id,
                course_id=goal.id,
                component_id=nodes[0].id,
                student_id=test_student.id,
                session_id=session.id,
                status="completed",
            )
            db.add(chat)
            db.commit()
            goal_id = goal.id
            node_ids = [n.id for n in nodes]
            test_student_id = test_student.id
            run_id = run.id
            chat_id = chat.id

        # 1. Fetch epistemic-sandbox context (with deterministic post-test fallback).
        ctx_res = client.get(f"/kc/harness/chats/{chat_id}/epistemic-context?fallback=true")
        assert ctx_res.status_code == 200
        ctx_body = ctx_res.json()
        assert ctx_body["exam_needs_generation"] is False
        assert ctx_body["tutor_message_count"] == 2
        assert "TUTOR_TAUGHT_ONLY" in ctx_body["user_prompt"]
        assert "CHILD_PRIVATE_MSG_SHOULD_NOT_APPEAR" not in ctx_body["user_prompt"]

        # 2. Record epistemic post-test attempt -> stored as epistemic_sandbox with student_id=None.
        answers = {iid: "unknown" for iid in ctx_body["item_ids"]}
        rec = client.post(
            f"/kc/harness/chats/{chat_id}/blind-post-test",
            json={"exam_id": ctx_body["exam_id"], "answers": answers},
        )
        assert rec.status_code == 200
        rec_body = rec.json()
        assert rec_body["mode"] == "epistemic_sandbox"
        assert rec_body["student_id"] is None
        assert rec_body["harness_chat_id"] == str(chat_id)
        assert rec_body["raw_score"] == 0.0

        # Confirm zero human attempts exist for this course.
        with SessionLocal() as db:
            human_attempts = db.scalars(
                select(BlindExamAttempt).where(
                    BlindExamAttempt.goal_id == goal_id,
                    BlindExamAttempt.mode == "human",
                )
            ).all()
            assert human_attempts == []
    finally:
        with SessionLocal() as db:
            _cleanup(
                db,
                goal_ids=[goal_id] if goal_id else [],
                node_ids=node_ids,
                student_ids=[test_student_id] if test_student_id else [],
                run_ids=[run_id] if run_id else [],
            )



def test_run_epistemic_sandbox_stitches_multi_component_tutor_messages_in_course_order() -> None:
    """F2 multi-component rollup stitches tutor utterances across all completed components of one course."""
    client = TestClient(app)
    goal_id = None
    node_ids: list[uuid.UUID] = []
    test_student_id = None
    run_id = None
    try:
        with SessionLocal() as db:
            goal, nodes = _create_sample_course(db)
            test_student = Student(
                display_name="Harness Multi-Component Child",
                slug=f"harness-multi-{uuid.uuid4().hex[:8]}",
                age=12,
                is_test=True,
            )
            db.add(test_student)
            db.flush()

            sess_a = KcSession(student_id=test_student.id, goal_id=goal.id, kc_id=nodes[0].id, status="completed")
            sess_b = KcSession(student_id=test_student.id, goal_id=goal.id, kc_id=nodes[1].id, status="completed")
            db.add_all([sess_a, sess_b])
            db.flush()
            db.add_all(
                [
                    KcMessage(session_id=sess_a.id, seq=1, role="assistant", content="COMP_ONE_TUTOR: Inflation measures price rise."),
                    KcMessage(session_id=sess_a.id, seq=2, role="user", content="CHILD_SECRET_ONE"),
                    KcMessage(session_id=sess_b.id, seq=1, role="assistant", content="COMP_TWO_TUTOR: Real GDP adjusts for inflation."),
                    KcMessage(session_id=sess_b.id, seq=2, role="user", content="CHILD_SECRET_TWO"),
                ]
            )
            run = HarnessRun(status="completed", plan={"run_blind_post_test": True})
            db.add(run)
            db.flush()
            # Insert out of course order (node 1 then node 0) to verify course target_kc_ids ordering!
            chat_b = HarnessChat(
                run_id=run.id,
                course_id=goal.id,
                component_id=nodes[1].id,
                student_id=test_student.id,
                session_id=sess_b.id,
                status="completed",
            )
            chat_a = HarnessChat(
                run_id=run.id,
                course_id=goal.id,
                component_id=nodes[0].id,
                student_id=test_student.id,
                session_id=sess_a.id,
                status="completed",
            )
            db.add_all([chat_b, chat_a])
            db.commit()
            goal_id = goal.id
            node_ids = [n.id for n in nodes]
            test_student_id = test_student.id
            run_id = run.id

        ctx_res = client.get(f"/kc/harness/runs/{run_id}/epistemic-context?course_id={goal_id}&fallback=true")
        assert ctx_res.status_code == 200
        body = ctx_res.json()
        assert body["exam_needs_generation"] is False
        assert body["covered_components"] == 2
        assert body["total_components"] == len(node_ids)
        assert body["tutor_message_count"] == 2
        prompt = body["user_prompt"]
        assert "COMP_ONE_TUTOR" in prompt and "COMP_TWO_TUTOR" in prompt
        assert prompt.index("COMP_ONE_TUTOR") < prompt.index("COMP_TWO_TUTOR")
        assert "CHILD_SECRET_ONE" not in prompt and "CHILD_SECRET_TWO" not in prompt

        rec = client.post(
            f"/kc/harness/runs/{run_id}/blind-post-test",
            json={
                "exam_id": body["exam_id"],
                "course_id": str(goal_id),
                "primary_chat_id": body["primary_chat_id"],
                "answers": {iid: "unknown" for iid in body["item_ids"]},
            },
        )
        assert rec.status_code == 200
        rec_body = rec.json()
        assert rec_body["mode"] == "epistemic_sandbox"
        assert rec_body["student_id"] is None
        assert rec_body["covered_components"] == 2
        assert len(rec_body["chat_ids"]) == 2
    finally:
        with SessionLocal() as db:
            _cleanup(
                db,
                goal_ids=[goal_id] if goal_id else [],
                node_ids=node_ids,
                student_ids=[test_student_id] if test_student_id else [],
                run_ids=[run_id] if run_id else [],
            )
