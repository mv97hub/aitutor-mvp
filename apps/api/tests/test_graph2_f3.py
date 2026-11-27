"""Comprehensive F3 tests: eight skills, biomarkers, caps, frozen note, harness isolation, and radar.

Verifies every standing rule and "Done when" criterion from the standalone F3 plan:
- Strict package boundary: `apps/api/app/graph2/` never imports `kc_prompt`, `kc_loop`, `kc`, or `block_score`.
- Single 0-3 scale -> y = grade / 3 -> caps (0.20 reveal/giveaway, 0.40 overlap >= 0.65, cite_evidence exempt) -> slow EMA.
- Revealed block cannot raise a spoke.
- Only skills asked for by a component's claims AND supported by the block type are graded.
- Empty mastery_spec produces zero skill updates.
- All 3 sync biomarkers + 4th judge-only biomarker.
- Child end card (<= 3 evidenced skills, 1 sentence + quote, no unasked skills).
- Frozen tutor note copied at component open; second turn in same component does not change the note; zero numbers/radar.
- Judge failure preserves sync biomarkers, end card, and prior tutor note.
- Harness children (`is_test=True` or `HarnessChat`) are never written into learner state.
- Shared eight-spoke radar keeps spokes < 3 observations hollow ("not enough yet") and never draws 0.50.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, select

from app.block_catalog import SKILL_KEYS
from app.database import SessionLocal, engine
from app.graph2 import (
    analyze_component_close,
    build_judge_bundle,
    compose_tutor_note,
    three_gram_overlap,
    validate_judge_output,
)
from app.graph2.state import slow_ema_step
from app.main import app
from app.models import (
    HarnessChat,
    HarnessRun,
    KcSession,
    KcState,
    LearnerCourseState,
    Parent,
    SkillObservation,
    Student,
    StudentEducationalState,
)
from app.studio import DELETE_PASSWORD

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Architectural boundary & migration checks
# ---------------------------------------------------------------------------


def test_graph2_package_never_imports_prompt_loop_or_kc() -> None:
    graph2_dir = Path(__file__).resolve().parents[1] / "app" / "graph2"
    forbidden = {"app.kc_prompt", "app.kc_loop", "app.kc", "app.block_score", "kc_prompt", "kc_loop", "block_score"}
    py_files = sorted(graph2_dir.glob("*.py"))
    assert len(py_files) >= 5, "Expected __init__, signals, judge, state, digest in app/graph2"
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden, f"{path.name} imported forbidden module {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert mod not in forbidden, f"{path.name} imported from forbidden module {mod}"
                for alias in node.names:
                    full = f"{mod}.{alias.name}" if mod else alias.name
                    assert full not in forbidden, f"{path.name} imported forbidden symbol {full}"


def test_migration_047_tables_and_columns_present() -> None:
    schema = inspect(engine)
    assert schema.has_table("student_educational_state")
    assert schema.has_table("learner_course_state")
    assert schema.has_table("skill_observation")
    sess_cols = {col["name"] for col in schema.get_columns("kc_sessions")}
    assert {"frozen_tutor_note", "close_end_card", "graph2_judge_status"} <= sess_cols


# ---------------------------------------------------------------------------
# 2. Pure unit tests: opportunity gate, 11 block types, caps, overlap, EMA, biomarkers
# ---------------------------------------------------------------------------


def _substep_result(
    bid: str,
    btype: str,
    substeps: list[dict],
    *,
    outcome: str = "passed",
    verdict: str = "known",
    revealed: bool = False,
) -> dict:
    return {
        "id": bid,
        "block_id": bid,
        "block_type": btype,
        "title": bid,
        "outcome": outcome,
        "verdict": verdict,
        "revealed": revealed,
        "attempts": 1,
        "substep_log": substeps,
    }


def test_empty_mastery_spec_and_unasked_skills_produce_no_updates() -> None:
    blocks = [{"id": "b1", "type": "spot_the_flaw", "claim_ids": ["c1"], "data": {}}]
    results = [
        _substep_result(
            "b1",
            "spot_the_flaw",
            [
                {
                    "substep": "identify",
                    "child_lines": ["Step 2 divided instead of multiplying."],
                    "tutor_lines": ["Look closely at step 2."],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                }
            ],
        )
    ]
    empty = analyze_component_close(
        mastery_spec={},
        blocks=blocks,
        block_results=results,
        messages=[],
        component_verdict="known",
    )
    assert empty.actionable is False
    assert empty.eligible_skills == {}
    assert empty.end_card is None

    # Explicit empty skills on claim -> scores nothing even if component skills lists errors.
    spec_empty_claim = {
        "archetype": "procedural_conceptual",
        "claims": [
            {"id": "c1", "statement": "Find the broken step.", "skills": []},
            {"id": "c2", "statement": "Apply to a new problem.", "skills": ["transfer"]},
        ],
        "target_level": 2,
        "skills": ["errors", "transfer"],
    }
    res = analyze_component_close(
        mastery_spec=spec_empty_claim,
        blocks=blocks,
        block_results=results,
        messages=[],
        component_verdict="known",
    )
    assert res.eligible_skills == {}
    assert res.end_card is None


def test_eleven_block_capability_matrix_and_special_gates() -> None:
    # 1. worked_example strict substep split: faded_step -> errors, solo_solve -> transfer
    we_spec = {
        "archetype": "procedural_conceptual",
        "claims": [
            {"id": "c1", "statement": "Catch the broken step and solve a new case.", "skills": ["errors", "transfer"]},
            {"id": "c2", "statement": "Justify from facts.", "skills": ["evidence"]},
        ],
        "target_level": 2,
        "skills": ["errors", "transfer", "evidence"],
    }
    we_block = {"id": "we1", "type": "worked_example", "claim_ids": ["c1"], "data": {}}
    # Only faded_step completed -> ONLY errors eligible, NOT transfer!
    only_faded = analyze_component_close(
        mastery_spec=we_spec,
        blocks=[we_block],
        block_results=[
            _substep_result(
                "we1",
                "worked_example",
                [
                    {
                        "substep": "faded_step",
                        "child_lines": ["The denominator should stay 4 instead of doubling."],
                        "tutor_lines": ["Check the missing step."],
                        "passed": True,
                        "revealed": False,
                        "giveaway": False,
                        "attempts": 1,
                        "hint_tier": "nudge",
                    }
                ],
            )
        ],
        messages=[],
        component_verdict="known",
    )
    assert set(only_faded.eligible_skills) == {"errors"}

    # Both faded_step and solo_solve completed -> BOTH errors and transfer eligible!
    both_we = analyze_component_close(
        mastery_spec=we_spec,
        blocks=[we_block],
        block_results=[
            _substep_result(
                "we1",
                "worked_example",
                [
                    {
                        "substep": "faded_step",
                        "child_lines": ["The denominator stays 4."],
                        "tutor_lines": ["Fill the missing step."],
                        "passed": True,
                        "revealed": False,
                        "giveaway": False,
                        "attempts": 2,
                        "hint_tier": "scaffold",
                    },
                    {
                        "substep": "solo_solve",
                        "child_lines": ["For 3/5 plus 1/5 I add the tops to get 4/5."],
                        "tutor_lines": ["Now try a brand new fraction sum."],
                        "passed": True,
                        "revealed": False,
                        "giveaway": False,
                        "attempts": 1,
                        "hint_tier": "nudge",
                    },
                ],
            )
        ],
        messages=[],
        component_verdict="known",
    )
    assert set(both_we.eligible_skills) == {"errors", "transfer"}
    assert both_we.biomarkers["hard_recovery_pass"] is True

    # 2. MCQ: bare option claim does NOT feed evidence; fact-grounded claim DOES feed evidence.
    mcq_bare_spec = {
        "archetype": "factual_terminological",
        "claims": [
            {"id": "c1", "statement": "Pick the correct definition.", "skills": ["evidence"]},
            {"id": "c2", "statement": "Recall the term.", "skills": []},
        ],
        "target_level": 1,
        "skills": ["evidence"],
    }
    mcq_fact_spec = {
        "archetype": "factual_terminological",
        "claims": [
            {"id": "c1", "statement": "Choose the option that follows from the given fact in the table.", "skills": ["evidence"]},
            {"id": "c2", "statement": "Recall the term.", "skills": []},
        ],
        "target_level": 2,
        "skills": ["evidence"],
    }
    mcq_blocks = [{"id": "m1", "type": "mcq", "claim_ids": ["c1"], "data": {"mode": "static", "question_stem": "Which matches?"}}]
    mcq_res = [
        _substep_result(
            "m1",
            "mcq",
            [
                {
                    "substep": "choice",
                    "child_lines": ["Option B because the table shows rainfall fell in July."],
                    "tutor_lines": ["Pick an option."],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                }
            ],
        )
    ]
    assert analyze_component_close(
        mastery_spec=mcq_bare_spec, blocks=mcq_blocks, block_results=mcq_res, messages=[], component_verdict="known"
    ).eligible_skills == {}
    assert set(
        analyze_component_close(
            mastery_spec=mcq_fact_spec, blocks=mcq_blocks, block_results=mcq_res, messages=[], component_verdict="known"
        ).eligible_skills
    ) == {"evidence"}

    # 3. Calibration: "I think" is NOT enough unless the claim asks how sure / what would change their mind.
    cal_no_ask = {
        "archetype": "factual_terminological",
        "claims": [
            {"id": "c1", "statement": "Recall why inflation raises menu costs.", "skills": ["calibration"]},
            {"id": "c2", "statement": "Explain simply.", "skills": []},
        ],
        "target_level": 2,
        "skills": ["calibration"],
    }
    cal_with_ask = {
        "archetype": "factual_terminological",
        "claims": [
            {"id": "c1", "statement": "State how sure you are and what evidence would change your mind.", "skills": ["calibration"]},
            {"id": "c2", "statement": "Explain simply.", "skills": []},
        ],
        "target_level": 2,
        "skills": ["calibration"],
    }
    ret_block = [{"id": "r1", "type": "retrieval_check", "claim_ids": ["c1"], "data": {}}]
    ret_res = [
        _substep_result(
            "r1",
            "retrieval_check",
            [
                {
                    "substep": "recall",
                    "child_lines": ["I think it is because menus cost money to reprint, and I would revise if prices were digital."],
                    "tutor_lines": ["How confident are you?"],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                }
            ],
        )
    ]
    assert analyze_component_close(
        mastery_spec=cal_no_ask, blocks=ret_block, block_results=ret_res, messages=[], component_verdict="known"
    ).eligible_skills == {}
    assert set(
        analyze_component_close(
            mastery_spec=cal_with_ask, blocks=ret_block, block_results=ret_res, messages=[], component_verdict="known"
        ).eligible_skills
    ) == {"calibration"}

    # 4. topic_goal and summary_check -> NEVER graded for any of the eight.
    tg_spec = {
        "archetype": "causal_systems",
        "claims": [
            {"id": "c1", "statement": "Explain why prices rise.", "skills": ["causes", "evidence"]},
            {"id": "c2", "statement": "Use on a new case.", "skills": ["transfer"]},
        ],
        "target_level": 2,
        "skills": ["causes", "evidence", "transfer"],
    }
    tg_blocks = [{"id": "tg1", "type": "topic_goal", "claim_ids": ["c1"], "data": {}}]
    tg_res = [
        _substep_result(
            "tg1",
            "topic_goal",
            [
                {
                    "substep": "main",
                    "child_lines": ["When supply drops sharply, buyers compete and prices climb."],
                    "tutor_lines": ["Explain what happens."],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                }
            ],
        )
    ]
    assert analyze_component_close(
        mastery_spec=tg_spec, blocks=tg_blocks, block_results=tg_res, messages=[], component_verdict="known"
    ).eligible_skills == {}

    # 5. socratic (perspectives + inquiry), curiosity (inquiry + causes), explanation (causes only when substantive),
    #    teach_back (explaining, and transfer when new audience/case), plus legacy F1 fallback (absent claim.skills).
    all_four_spec = {
        "archetype": "textual_interpretive",
        "claims": [
            {"id": "c1", "statement": "Weigh opposing viewpoints and test claims.", "skills": ["perspectives", "inquiry"]},
            {"id": "c2", "statement": "Explain what causes the result and teach a younger classmate.", "skills": ["causes", "explaining", "transfer"]},
        ],
        "target_level": 2,
        "skills": ["perspectives", "inquiry", "causes", "explaining", "transfer"],
    }
    combo_blocks = [
        {"id": "soc1", "type": "socratic", "claim_ids": ["c1"], "data": {}},
        {"id": "cur1", "type": "curiosity", "claim_ids": ["c1", "c2"], "data": {}},
        {"id": "exp1", "type": "explanation", "claim_ids": ["c2"], "data": {}},
        {"id": "tb1", "type": "teach_back", "claim_ids": ["c2"], "data": {}},
    ]
    combo_res = [
        _substep_result(
            "soc1",
            "socratic",
            [
                {
                    "substep": "counterexample_probe",
                    "child_lines": ["Shopkeepers worry about costs while families worry about rent, but why does that differ?"],
                    "tutor_lines": ["What would the other side argue?"],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                    "on_topic_questions": ["Why does that differ?"],
                }
            ],
        ),
        _substep_result(
            "cur1",
            "curiosity",
            [
                {
                    "substep": "hook_and_predict",
                    "child_lines": ["What if the bridge closed? Fewer deliveries would make food cost more."],
                    "tutor_lines": ["What do you predict?"],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                }
            ],
        ),
        # Explanation with nav-only click ("Got it - move on") should NOT trigger causes on its own
        _substep_result(
            "exp1",
            "explanation",
            [
                {
                    "substep": "explain_topic",
                    "child_lines": ["Got it - move on"],
                    "tutor_lines": ["Here is how supply works."],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                }
            ],
            outcome="engaged",
            verdict="unassessed",
        ),
        _substep_result(
            "tb1",
            "teach_back",
            [
                {
                    "substep": "initial_explanation",
                    "child_lines": ["Imagine telling a second grader: when toys are scarce, each toy trades for more."],
                    "tutor_lines": ["Teach it simply."],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                }
            ],
        ),
    ]
    combo_out = analyze_component_close(
        mastery_spec=all_four_spec, blocks=combo_blocks, block_results=combo_res, messages=[], component_verdict="known"
    )
    assert set(combo_out.eligible_skills) == {"perspectives", "inquiry", "causes", "explaining", "transfer"}
    # Child end card is strictly bounded to <= 3 skills even when 5 skills were eligible!
    assert combo_out.end_card is not None
    assert len(combo_out.end_card["items"]) == 3

    # 4th biomarker (multi_perspective_synthesis) comes ONLY from the judge.
    assert "multi_perspective_synthesis" not in combo_out.biomarkers
    judged_synth = validate_judge_output(
        {
            "grades": [
                {"skill": "perspectives", "grade": 3, "quote": "Shopkeepers worry about costs", "rationale": "Both views."},
                {"skill": "inquiry", "grade": 2, "quote": "What if the bridge closed?", "rationale": "Sharp question."},
                {"skill": "causes", "grade": 2, "quote": "Fewer deliveries would make food cost more.", "rationale": "Clear cause."},
                {"skill": "explaining", "grade": 3, "quote": "Imagine telling a second grader", "rationale": "Clear."},
                {"skill": "transfer", "grade": 2, "quote": "when toys are scarce", "rationale": "New case."},
            ],
            "multi_perspective_synthesis": True,
        },
        combo_out.eligible_skills,
    )
    assert judged_synth.multi_perspective_synthesis is True

    # Legacy F1 component (absent claim.skills) falls back to mastery_spec.skills intersected with block capability.
    legacy_f1_spec = {
        "archetype": "causal_systems",
        "claims": [
            {"id": "c1", "statement": "Explain the causal link."},
            {"id": "c2", "statement": "Teach it to someone else."},
        ],
        "target_level": 2,
        "skills": ["causes", "explaining"],
    }
    legacy_out = analyze_component_close(
        mastery_spec=legacy_f1_spec,
        blocks=[{"id": "tb1", "type": "teach_back", "claim_ids": ["c2"], "data": {}}],
        block_results=[combo_res[3]],
        messages=[],
        component_verdict="known",
    )
    # teach_back cannot feed `causes`, so intersection leaves ONLY `explaining`!
    assert set(legacy_out.eligible_skills) == {"explaining"}


def test_caps_overlap_quote_exemption_and_slow_ema() -> None:
    tutor_line = "Inflation happens when too much money chases too few goods in an economy"
    parroted = "Inflation happens when too much money chases too few goods in an economy today"
    own_words = "Prices climb fast because everyone wants snacks that the store ran out of"

    assert three_gram_overlap(parroted, [tutor_line]) >= 0.65
    assert three_gram_overlap(own_words, [tutor_line]) < 0.20

    spec = {
        "archetype": "textual_interpretive",
        "claims": [
            {"id": "c1", "statement": "Cite verbatim evidence from the passage.", "skills": ["evidence"]},
            {"id": "c2", "statement": "Explain the causal chain.", "skills": ["causes"]},
        ],
        "target_level": 2,
        "skills": ["evidence", "causes"],
    }
    blocks = [
        {"id": "p1", "type": "passage_ela", "claim_ids": ["c1"], "data": {}},
        {"id": "cs1", "type": "case_study", "claim_ids": ["c2"], "data": {}},
    ]
    results = [
        # Required quote on cite_evidence with 100% overlap MUST be exempt from 0.40 overlap cap!
        _substep_result(
            "p1",
            "passage_ela",
            [
                {
                    "substep": "cite_evidence",
                    "child_lines": [tutor_line],
                    "tutor_lines": [tutor_line],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                    "required_quote": True,
                }
            ],
        ),
        # Parroted answer on case_study MUST be capped at 0.40!
        _substep_result(
            "cs1",
            "case_study",
            [
                {
                    "substep": "contrast_and_rule",
                    "child_lines": [parroted],
                    "tutor_lines": [tutor_line],
                    "passed": True,
                    "revealed": False,
                    "giveaway": False,
                    "attempts": 1,
                    "hint_tier": "nudge",
                    "required_quote": False,
                }
            ],
        ),
    ]
    analysis = analyze_component_close(
        mastery_spec=spec, blocks=blocks, block_results=results, messages=[], component_verdict="known"
    )
    assert analysis.eligible_skills["evidence"].cap is None
    assert analysis.eligible_skills["causes"].cap == 0.40
    assert analysis.eligible_skills["causes"].cap_reason == "overlap"

    validated = validate_judge_output(
        {
            "grades": [
                {"skill": "evidence", "grade": 3, "quote": tutor_line, "rationale": "Exact citation."},
                {"skill": "causes", "grade": 3, "quote": parroted, "rationale": "Matches text."},
            ],
            "multi_perspective_synthesis": False,
        },
        analysis.eligible_skills,
    )
    by_skill = {g.skill: g for g in validated.grades}
    assert by_skill["evidence"].capped_y == 1.0
    assert by_skill["evidence"].cap_applied is None
    assert by_skill["causes"].capped_y == 0.40
    assert by_skill["causes"].cap_applied == "overlap"

    # Slow EMA math & revealed block can NEVER raise a spoke even when score < 0.20.
    alpha0, s1 = slow_ema_step(0.50, 0, 1.0)
    assert abs(alpha0 - (1 / 3)) < 1e-5
    assert abs(s1 - (0.50 * (2 / 3) + 1.0 * (1 / 3))) < 1e-4

    alpha_floor, _ = slow_ema_step(0.50, 20, 1.0)
    assert alpha_floor == 0.08

    _, after_reveal_low = slow_ema_step(0.15, 3, 0.20, revealed_or_giveaway=True)
    assert after_reveal_low <= 0.15


def test_digest_selects_strength_focus_misconception_with_no_numbers_or_radar() -> None:
    skills_state = {
        "evidence": {"score": 0.90, "count": 4},
        "perspectives": {"score": 0.35, "count": 3},
        "causes": {"score": 0.95, "count": 2},  # < 3 observations: MUST NOT qualify!
        "transfer": {"score": 0.60, "count": 5},
    }
    # Next component asks for evidence, perspectives, causes (NOT transfer)
    note = compose_tutor_note(
        skills_state=skills_state,
        next_component_skills=["evidence", "perspectives", "causes"],
        course_misconceptions=[{"text": "Confuses price level with inflation rate", "resolved": False}],
    )
    lines = note.splitlines()
    assert len(lines) == 3
    assert "Evidence is a strength:" in lines[0]
    assert "Focus on Perspectives:" in lines[1]
    assert "Confuses price level with inflation rate" in lines[2]
    assert "Transfer" not in note and "Causes" not in note
    assert "radar" not in note.lower()
    assert not any(ch.isdigit() for ch in lines[0] + lines[1])

    # When zero skills qualify (all < 3 obs), emit NO skill line (only misconception if present).
    note_none = compose_tutor_note(
        skills_state={"evidence": {"score": 0.90, "count": 2}},
        next_component_skills=["evidence"],
        course_misconceptions=[],
    )
    assert note_none == ""


# ---------------------------------------------------------------------------
# 3. Full PostgreSQL + FastAPI integration tests
# ---------------------------------------------------------------------------


def _make_student(*, is_test: bool = False) -> Student:
    db = SessionLocal()
    try:
        uid = uuid.uuid4().hex[:8]
        row = Student(
            slug=f"zz-f3-{uid}",
            display_name=f"ZZ F3 Learner {uid}",
            age=11,
            is_test=is_test,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def _cleanup_student_and_courses(student_id: uuid.UUID, *course_codes: str, parent_ids: list[str] = ()) -> None:
    for code in course_codes:
        for item in client.get("/kc/courses").json():
            if item["code"] == code:
                client.post(f"/kc/courses/{item['id']}/delete", json={"password": DELETE_PASSWORD})
    db = SessionLocal()
    try:
        if parent_ids:
            db.execute(delete(Parent).where(Parent.id.in_([uuid.UUID(p) for p in parent_ids])))
        db.execute(delete(SkillObservation).where(SkillObservation.student_id == student_id))
        db.execute(delete(LearnerCourseState).where(LearnerCourseState.student_id == student_id))
        db.execute(delete(StudentEducationalState).where(StudentEducationalState.student_id == student_id))
        db.execute(delete(KcSession).where(KcSession.student_id == student_id))
        db.execute(delete(KcState).where(KcState.student_id == student_id))
        db.execute(delete(Student).where(Student.id == student_id))
        db.commit()
    finally:
        db.close()


def _create_f3_course(code: str, components: list[dict]) -> tuple[str, list[str]]:
    created = client.post(
        "/kc/courses",
        json={
            "code": code,
            "title": f"ZZ F3 {code}",
            "description": "F3 integration test course.",
            "audience": "9-11",
            "kind": "mastery",
            "minutes": None,
        },
    )
    assert created.status_code == 200, created.text
    course_id = created.json()["id"]
    pushed = client.post(
        f"/kc/courses/{course_id}/push",
        json={"components": [{"code": f"{code}-c{i}", "title": item["title"]} for i, item in enumerate(components, 1)]},
    )
    assert pushed.status_code == 200, pushed.text
    node_ids = [item["id"] for item in pushed.json()["components"]]
    for node_id, item in zip(node_ids, components):
        saved = client.put(
            f"/kc/nodes/{node_id}",
            json={
                "title": item["title"],
                "outline": "Teach and check.",
                "core_truth": item.get("core_truth", "The principle holds."),
                "rubric": ["Shows the idea."],
                "misconceptions": item.get("misconceptions", []),
                "prerequisite_codes": [],
                "encompasses_codes": [],
                "mastery_spec": item.get("mastery_spec", {}),
                "blocks": item["blocks"],
            },
        )
        assert saved.status_code == 200, saved.text
    assert client.post(f"/kc/courses/{course_id}/ready").status_code == 200
    return course_id, node_ids


def _close_single_block_session(
    student_id: str,
    course_id: str,
    node_id: str,
    *,
    tutor_opening: str,
    child_answer: str,
    substep_passed: bool = True,
    decision: str = "advance",
    misconception: str | None = None,
    extra_turns: list[tuple[str, bool, str]] = (),
) -> tuple[str, dict]:
    opened = client.post(
        "/kc/tutor/sessions",
        json={"student_id": student_id, "course_id": course_id, "kc_id": node_id},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["id"]
    assert client.post(
        f"/kc/tutor/sessions/{session_id}/speech",
        json={"content": tutor_opening},
    ).status_code == 200

    for text, passed, dec in extra_turns:
        assert client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": text}).status_code == 200
        assert client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={
                "reply": "Good question! Now back to our main step.",
                "decision": dec,
                "substep_passed": passed,
                "block_complete": False,
                "help_requested": True,
                "off_course": False,
            },
        ).status_code == 200

    assert client.post(f"/kc/tutor/sessions/{session_id}/turn", json={"answer": child_answer}).status_code == 200
    dec_resp = client.post(
        f"/kc/tutor/sessions/{session_id}/decision",
        json={
            "reply": "Nice work! Ready to continue?",
            "decision": decision,
            "substep_passed": substep_passed,
            "block_complete": substep_passed,
            "misconception": misconception,
            "rubric_met": [],
        },
    )
    assert dec_resp.status_code == 200, dec_resp.text
    body = dec_resp.json()
    # If stopped on summary_check, send the continue confirmation to close the component.
    if body["status"] != "completed":
        assert client.post(
            f"/kc/tutor/sessions/{session_id}/turn",
            json={"answer": "No final questions — let's continue!"},
        ).status_code == 200
        dec_resp = client.post(
            f"/kc/tutor/sessions/{session_id}/decision",
            json={
                "reply": "Great finish!",
                "decision": "complete",
                "substep_passed": True,
                "block_complete": True,
                "ready_to_move_on": True,
            },
        )
        assert dec_resp.status_code == 200, dec_resp.text
        body = dec_resp.json()
    return session_id, body


def test_full_e2e_component_close_judge_radar_freeze_and_reveal_guard() -> None:
    student = _make_student(is_test=False)
    code = f"zz-f3-{uuid.uuid4().hex[:6]}"
    parent = client.post("/parents", json={"name": f"ZZ Parent {code}"}).json()
    assert client.put(f"/parents/{parent['id']}/students", json={"student_ids": [str(student.id)]}).status_code == 200

    spec_comp1 = {
        "archetype": "causal_systems",
        "claims": [
            {"id": "c1", "statement": "Explain the causal mechanism clearly.", "skills": ["causes"]},
            {"id": "c2", "statement": "Spot the flaw in a buggy step.", "skills": ["errors"]},
        ],
        "target_level": 2,
        "skills": ["causes", "errors"],
    }
    spec_comp2 = {
        "archetype": "causal_systems",
        "claims": [
            {"id": "c1", "statement": "Explain what happens if a cause is removed.", "skills": ["causes"]},
            {"id": "c2", "statement": "Find the broken step in rookie work.", "skills": ["errors"]},
        ],
        "target_level": 2,
        "skills": ["causes", "errors"],
    }

    components = [
        {
            "title": "Component One",
            "mastery_spec": spec_comp1,
            "blocks": [
                {
                    "id": "flaw1",
                    "type": "spot_the_flaw",
                    "claim_ids": ["c2"],
                    "data": {
                        "rookie_work": "Added denominators: 1/4 + 1/4 = 2/8.",
                        "flaw_description": "The rookie added the denominators instead of keeping 4.",
                        "underlying_misconception": "Adding denominators.",
                        "corrected_version": "1/4 + 1/4 = 2/4.",
                    },
                }
            ],
        },
        {
            "title": "Component Two",
            "mastery_spec": spec_comp2,
            "blocks": [
                {
                    "id": "flaw2",
                    "type": "spot_the_flaw",
                    "claim_ids": ["c2"],
                    "data": {
                        "rookie_work": "Multiplied instead of dividing.",
                        "flaw_description": "Used the wrong operation in step two.",
                        "underlying_misconception": "Wrong operation.",
                        "corrected_version": "Divide by 2 instead.",
                    },
                }
            ],
        },
    ]

    try:
        course_id, node_ids = _create_f3_course(code, components)

        # Before any observations: all 8 spokes on BOTH child and parent radar MUST be hollow ("not enough yet"), NO 0.50!
        child_radar_0 = client.get(f"/kc/students/{student.id}/radar").json()
        parent_radar_0 = client.get(f"/parents/{parent['id']}/children/{student.id}/radar").json()
        assert child_radar_0 == parent_radar_0
        assert [s["skill"] for s in child_radar_0["spokes"]] == list(SKILL_KEYS)
        assert all(s["hollow"] is True and s["score"] is None and s["status_label"] == "not enough yet" for s in child_radar_0["spokes"])

        # Run 3 sessions on Component 1 (to reach 3 observations on `errors`)
        child_quote = "The rookie mistakenly added the bottom denominators instead of keeping fourths; it should be 1/4 + 1/4 = 2/4."
        for run_idx in range(3):
            extra = [("What if the denominators were different?", False, "stay")] if run_idx == 0 else []
            sid, closed_body = _close_single_block_session(
                str(student.id),
                course_id,
                node_ids[0],
                tutor_opening="Check out this rookie work: 1/4 + 1/4 = 2/8. What went wrong?",
                child_answer=child_quote,
                extra_turns=extra,
            )
            assert closed_body["status"] == "completed"
            assert closed_body["verdict"] == "known"
            assert closed_body["graph2_judge_pending"] is True
            # Child end card returned synchronously with at most 3 evidenced skills & quote, NO unasked skills!
            assert closed_body["end_card"] is not None
            assert len(closed_body["end_card"]["items"]) == 1
            assert closed_body["end_card"]["items"][0]["skill"] == "errors"
            assert "denominators" in closed_body["end_card"]["items"][0]["quote"]

            # Post-reply batch judge prompt includes ONLY `errors` (not `causes` since block only had claim c2).
            jp = client.post(f"/kc/tutor/sessions/{sid}/graph2/judge-prompt").json()
            assert jp["skipped"] is False
            assert jp["eligible_skills"] == ["errors"]

            jr = client.post(
                f"/kc/tutor/sessions/{sid}/graph2/judge-result",
                json={
                    "grades": [{"skill": "errors", "grade": 3, "quote": child_quote, "rationale": "Spotted and repaired."}],
                    "multi_perspective_synthesis": False,
                },
            )
            assert jr.status_code == 200, jr.text
            assert jr.json()["applied"] is True

            # Idempotency: re-posting judge-result MUST NOT double-count!
            dup = client.post(
                f"/kc/tutor/sessions/{sid}/graph2/judge-result",
                json={
                    "grades": [{"skill": "errors", "grade": 0, "quote": child_quote, "rationale": "Duplicate."}],
                    "multi_perspective_synthesis": False,
                },
            )
            assert dup.status_code == 200
            assert dup.json().get("already_applied") is True

        # Check sync biomarkers recorded (own_words_pass & on_topic_inquiry_before_known)
        db = SessionLocal()
        try:
            edu = db.get(StudentEducationalState, student.id)
            assert edu is not None
            assert edu.biomarkers["own_words_pass"] >= 1
            assert edu.biomarkers["on_topic_inquiry_before_known"] >= 1
            score_after_3 = float(edu.skills["errors"]["score"])
            assert score_after_3 > 0.70
            assert edu.skills["errors"]["count"] == 3
            assert edu.skills["causes"]["count"] == 0
        finally:
            db.close()

        # Shared radar now draws `errors` (count=3, hollow=False) and keeps the other 7 hollow!
        radar_after_3 = client.get(f"/kc/students/{student.id}/radar").json()
        parent_after_3 = client.get(f"/parents/{parent['id']}/children/{student.id}/radar").json()
        assert radar_after_3 == parent_after_3
        by_key = {s["skill"]: s for s in radar_after_3["spokes"]}
        assert by_key["errors"]["hollow"] is False
        assert by_key["errors"]["score"] == score_after_3
        assert by_key["errors"]["last_quote"] == child_quote
        for other in SKILL_KEYS:
            if other != "errors":
                assert by_key[other]["hollow"] is True
                assert by_key[other]["score"] is None
                assert by_key[other]["status_label"] == "not enough yet"

        # Open Component 2 -> frozen note is copied onto the session and appears in "Who you are talking to"!
        sess2 = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(student.id), "course_id": course_id, "kc_id": node_ids[1]},
        ).json()
        sid2 = sess2["id"]
        prompt_turn_1 = client.get(f"/kc/tutor/sessions/{sid2}/prompt").json()["system_prompt"]
        assert "Errors is a strength:" in prompt_turn_1
        assert "radar" not in prompt_turn_1.lower()
        assert f"{score_after_3}" not in prompt_turn_1

        # Mutate student_educational_state behind the scenes (simulating a late async judge grade),
        # then take a second turn in Component 2: the frozen note MUST NOT change mid-lesson!
        db = SessionLocal()
        try:
            edu = db.get(StudentEducationalState, student.id)
            assert edu is not None
            edu.tutor_note = "Focus on Errors: completely different late note."
            edu.skills = {**edu.skills, "errors": {"score": 0.10, "count": 4, "last_evidence": None, "last_observed_at": None}}
            db.commit()
        finally:
            db.close()

        assert client.post(f"/kc/tutor/sessions/{sid2}/speech", json={"content": "Spot the mistake in step 2."}).status_code == 200
        assert client.post(f"/kc/tutor/sessions/{sid2}/turn", json={"answer": "Wait, let me check step 2."}).status_code == 200
        prompt_turn_2 = client.get(f"/kc/tutor/sessions/{sid2}/prompt").json()["system_prompt"]
        assert "Errors is a strength:" in prompt_turn_2
        assert "completely different late note" not in prompt_turn_2

        # Revealed block cannot raise a spoke: fail/reveal a new session on Component 1 and apply grade=3!
        sid_rev_opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(student.id), "course_id": course_id, "kc_id": node_ids[0]},
        ).json()["id"]
        assert client.post(f"/kc/tutor/sessions/{sid_rev_opened}/speech", json={"content": "Find the mistake."}).status_code == 200
        # Two misses + reveal on spot_the_flaw (max_retries=2)
        for miss in ("I don't know", "Still not sure, please tell me"):
            assert client.post(f"/kc/tutor/sessions/{sid_rev_opened}/turn", json={"answer": miss}).status_code == 200
            r = client.post(
                f"/kc/tutor/sessions/{sid_rev_opened}/decision",
                json={"reply": "Here is the answer: the rookie added denominators.", "decision": "stay", "substep_passed": False, "block_complete": False},
            ).json()
            if r["status"] == "completed":
                break
        # Close summary_check if still open
        st = client.get(f"/kc/tutor/sessions/{sid_rev_opened}").json()
        if st["status"] != "completed":
            assert client.post(f"/kc/tutor/sessions/{sid_rev_opened}/turn", json={"answer": "No final questions — let's continue!"}).status_code == 200
            client.post(
                f"/kc/tutor/sessions/{sid_rev_opened}/decision",
                json={"reply": "Moving on.", "decision": "complete", "substep_passed": False, "block_complete": True, "ready_to_move_on": True},
            )
        # Set current score low (0.15) to verify revealed block STILL cannot raise it even with grade=3!
        db = SessionLocal()
        try:
            edu = db.get(StudentEducationalState, student.id)
            edu.skills = {**edu.skills, "errors": {"score": 0.15, "count": 3, "last_evidence": None, "last_observed_at": None}}
            db.commit()
        finally:
            db.close()

        rev_jr = client.post(
            f"/kc/tutor/sessions/{sid_rev_opened}/graph2/judge-result",
            json={
                "grades": [{"skill": "errors", "grade": 3, "quote": "Still not sure", "rationale": "Model tried to give 3."}],
                "multi_perspective_synthesis": False,
            },
        )
        assert rev_jr.status_code == 200, rev_jr.text
        obs = rev_jr.json()["observations"][0]
        assert obs["capped_y"] <= 0.20
        assert obs["score_after"] <= 0.15  # Revealed block CANNOT raise the spoke!
    finally:
        _cleanup_student_and_courses(student.id, code, parent_ids=[parent["id"]])


def test_judge_failure_keeps_biomarkers_end_card_and_prior_note() -> None:
    student = _make_student(is_test=False)
    code = f"zz-f3-fail-{uuid.uuid4().hex[:6]}"
    spec = {
        "archetype": "causal_systems",
        "claims": [
            {"id": "c1", "statement": "Find the broken step.", "skills": ["errors"]},
            {"id": "c2", "statement": "Explain clearly.", "skills": ["explaining"]},
        ],
        "target_level": 2,
        "skills": ["errors", "explaining"],
    }
    components = [
        {
            "title": "Fail Resilience",
            "mastery_spec": spec,
            "blocks": [
                {
                    "id": "flaw1",
                    "type": "spot_the_flaw",
                    "claim_ids": ["c1"],
                    "data": {
                        "rookie_work": "1/3 + 1/3 = 2/6",
                        "flaw_description": "Added denominators.",
                        "underlying_misconception": "Adding denominators.",
                        "corrected_version": "2/3",
                    },
                }
            ],
        }
    ]
    try:
        course_id, node_ids = _create_f3_course(code, components)
        # Seed a prior note before this component closes
        db = SessionLocal()
        try:
            db.add(
                StudentEducationalState(
                    student_id=student.id,
                    skills={},
                    hint_uptake={},
                    block_affinity={},
                    expression_stats={},
                    biomarkers={},
                    tutor_note="Prior frozen note stays intact.",
                )
            )
            db.commit()
        finally:
            db.close()

        sid, closed_body = _close_single_block_session(
            str(student.id),
            course_id,
            node_ids[0],
            tutor_opening="Check this rookie work.",
            child_answer="They summed the bottom numbers instead of leaving thirds intact so it should be 2/3.",
        )
        assert closed_body["end_card"] is not None
        assert closed_body["graph2_judge_pending"] is True

        # Judge fails
        failed = client.post(f"/kc/tutor/sessions/{sid}/graph2/judge-failed")
        assert failed.status_code == 200
        assert failed.json()["status"] == "failed"

        # End card, biomarkers, and prior note MUST all still stand!
        reloaded = client.get(f"/kc/tutor/sessions/{sid}").json()
        assert reloaded["end_card"] == closed_body["end_card"]
        assert reloaded["graph2_judge_status"] == "failed"
        db = SessionLocal()
        try:
            edu = db.get(StudentEducationalState, student.id)
            assert edu is not None
            assert edu.tutor_note == "Prior frozen note stays intact."
            assert edu.biomarkers["own_words_pass"] >= 1
            assert db.scalars(select(SkillObservation).where(SkillObservation.student_id == student.id)).all() == []
        finally:
            db.close()
    finally:
        _cleanup_student_and_courses(student.id, code)


def test_harness_child_never_writes_learner_state_or_observations() -> None:
    test_student = _make_student(is_test=True)
    code = f"zz-f3-har-{uuid.uuid4().hex[:6]}"
    spec = {
        "archetype": "causal_systems",
        "claims": [
            {"id": "c1", "statement": "Find the broken step.", "skills": ["errors"]},
            {"id": "c2", "statement": "Explain clearly.", "skills": ["explaining"]},
        ],
        "target_level": 2,
        "skills": ["errors", "explaining"],
    }
    components = [
        {
            "title": "Harness Quarantine",
            "mastery_spec": spec,
            "blocks": [
                {
                    "id": "flaw1",
                    "type": "spot_the_flaw",
                    "claim_ids": ["c1"],
                    "data": {
                        "rookie_work": "1/3 + 1/3 = 2/6",
                        "flaw_description": "Added denominators.",
                        "underlying_misconception": "Adding denominators.",
                        "corrected_version": "2/3",
                    },
                }
            ],
        }
    ]
    try:
        course_id, node_ids = _create_f3_course(code, components)
        sid, closed_body = _close_single_block_session(
            str(test_student.id),
            course_id,
            node_ids[0],
            tutor_opening="Check this rookie work.",
            child_answer="They added the denominators instead of keeping thirds.",
        )
        assert closed_body["end_card"] is None
        assert closed_body["graph2_judge_pending"] is False

        jp = client.post(f"/kc/tutor/sessions/{sid}/graph2/judge-prompt").json()
        assert jp["skipped"] is True

        jr = client.post(
            f"/kc/tutor/sessions/{sid}/graph2/judge-result",
            json={"grades": [{"skill": "errors", "grade": 3, "quote": "They added", "rationale": "Ok"}]},
        ).json()
        assert jr["applied"] is False

        db = SessionLocal()
        try:
            assert db.get(StudentEducationalState, test_student.id) is None
            assert db.scalars(select(LearnerCourseState).where(LearnerCourseState.student_id == test_student.id)).all() == []
            assert db.scalars(select(SkillObservation).where(SkillObservation.student_id == test_student.id)).all() == []
        finally:
            db.close()

        # Even if a session belongs to a non-test student row, HarnessChat linkage still quarantines it!
        real_student = _make_student(is_test=False)
        run_id = uuid.uuid4()
        try:
            opened_h = client.post(
                "/kc/tutor/sessions",
                json={"student_id": str(real_student.id), "course_id": course_id, "kc_id": node_ids[0]},
            ).json()
            sid_h = uuid.UUID(opened_h["id"])
            db = SessionLocal()
            try:
                db.add(HarnessRun(id=run_id, status="running", plan={}, totals={}))
                db.flush()
                db.add(
                    HarnessChat(
                        run_id=run_id,
                        status="running",
                        student_id=real_student.id,
                        session_id=sid_h,
                        course_id=uuid.UUID(course_id),
                        component_id=uuid.UUID(node_ids[0]),
                    )
                )
                db.commit()
            finally:
                db.close()
            assert client.post(f"/kc/tutor/sessions/{sid_h}/speech", json={"content": "Check this."}).status_code == 200
            assert client.post(f"/kc/tutor/sessions/{sid_h}/turn", json={"answer": "They added denominators; 2/3."}).status_code == 200
            dec_h = client.post(
                f"/kc/tutor/sessions/{sid_h}/decision",
                json={"reply": "Done!", "decision": "advance", "substep_passed": True, "block_complete": True},
            ).json()
            if dec_h["status"] != "completed":
                assert client.post(f"/kc/tutor/sessions/{sid_h}/turn", json={"answer": "No final questions — let's continue!"}).status_code == 200
                dec_h = client.post(
                    f"/kc/tutor/sessions/{sid_h}/decision",
                    json={"reply": "Finished!", "decision": "complete", "substep_passed": True, "block_complete": True, "ready_to_move_on": True},
                ).json()
            assert dec_h["end_card"] is None
            assert dec_h["graph2_judge_pending"] is False
            db = SessionLocal()
            try:
                assert db.get(StudentEducationalState, real_student.id) is None
                db.execute(delete(HarnessRun).where(HarnessRun.id == run_id))
                db.commit()
            finally:
                db.close()
        finally:
            _cleanup_student_and_courses(real_student.id)
    finally:
        _cleanup_student_and_courses(test_student.id, code)


def test_judge_token_usage_kind_accepted() -> None:
    student = _make_student(is_test=False)
    code = f"zz-f3-tok-{uuid.uuid4().hex[:6]}"
    components = [
        {
            "title": "Token check",
            "blocks": [{"id": "b1", "type": "topic_goal", "data": {"topic": "T", "goal": "G"}}],
        }
    ]
    try:
        course_id, node_ids = _create_f3_course(code, components)
        sid = client.post(
            "/kc/tutor/sessions",
            json={"student_id": str(student.id), "course_id": course_id, "kc_id": node_ids[0]},
        ).json()["id"]
        saved = client.post(
            f"/kc/sessions/{sid}/token-usage",
            json={"kind": "judge", "model": "gpt-4.1", "input_tokens": 200, "output_tokens": 50, "cached_tokens": 0},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["kind"] == "judge"
    finally:
        _cleanup_student_and_courses(student.id, code)
