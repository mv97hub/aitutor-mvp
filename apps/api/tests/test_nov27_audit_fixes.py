"""Regression tests for the three state-machine and prompt bugs exposed by run a32a728f."""

from copy import deepcopy
from uuid import UUID, uuid4

from app.block_score import score_supported_turn
from app.database import SessionLocal
from app.kc_loop import forecast_this_turn, resolve_block_turn
from app.models import KcSession, Student, default_kc_tutor_config
from app.studio import DELETE_PASSWORD
from tests.test_kc import _ready, _spec, client
from tests.test_kc_prompt import _node, _section, _student, _text

BALCONY = {
    "id": "balcony-scene-topic",
    "type": "passage_ela",
    "data": {
        "passage_title": "Romeo and Juliet, Act 2, scene 2 · Capulet’s orchard",
        "passage_genre": "literary",
        "passage_text": (
            "Juliet speaks above the orchard while Romeo listens below.\n\n"
            "JULIET\nDeny thy father and refuse thy name,\n’Tis but thy name that is my enemy."
        ),
        "central_idea_question": "What separates these two people, besides where they are standing?",
        "expected_central_idea": "Romeo and Juliet love each other, but their feuding family names stand between them.",
        "distractor_detail": "Romeo is below Juliet.",
        "evidence_prompt": "Quote a line that shows the family name is the problem.",
        "verbatim_evidence_quotes": [
            "Deny thy father and refuse thy name,",
            "’Tis but thy name that is my enemy.",
        ],
        "analysis_focus": "symbolism",
        "analysis_question": "How does the space between them show the name problem?",
        "expected_analysis": "The physical space mirrors the family barrier keeping them apart.",
    },
}

FRIAR = {
    "id": "juliet-paris-topic",
    "type": "passage_ela",
    "data": {
        "passage_title": "Romeo and Juliet, Act 4, scene 1 · Friar Lawrence’s cell",
        "passage_genre": "literary",
        "passage_text": (
            "PARIS\nDo not deny to him that you love me.\n\n"
            "JULIET\nI will confess to you that I love him."
        ),
        "central_idea_question": "Why can Juliet’s reply sound different to Paris and to the audience?",
        "expected_central_idea": "Juliet avoids saying she loves Paris while speaking truthfully about Romeo.",
        "distractor_detail": "The Friar is present.",
        "evidence_prompt": "Which wording lets Juliet avoid declaring love for Paris?",
        "verbatim_evidence_quotes": ["I will confess to you that I love him."],
        "analysis_focus": "dramatic irony",
        "analysis_question": "Why does Juliet hide her meaning in front of the Friar?",
        "expected_analysis": "So Paris thinks she agrees while she stays true to Romeo.",
    },
}

DESIGN_SOCRATIC = {
    "id": "socratic-1",
    "type": "socratic",
    "data": {
        "central_dilemma": "Is good design just about making things look nice, or is there more to it?",
        "counterexample_prompts": [
            "What if a phone looks cool but is confusing to use?",
            "What if a website has sparkly pictures but hidden buttons?",
        ],
        "target_synthesis": "Good design balances appearance with usability and function.",
    },
}

DESIGN_SOCRATIC_2 = {
    "id": "socratic-2",
    "type": "socratic",
    "data": {
        "central_dilemma": "Why did Apple's simple design make its products popular?",
        "counterexample_prompts": [
            "What if a device had more features hidden inside a confusing menu?",
            "What if a plain screen still had a confusing layout?",
        ],
        "target_synthesis": "Simplicity made products intuitive so more people could use them confidently.",
    },
}

WORKED_GDP = {
    "id": "worked-example-1",
    "type": "worked_example",
    "data": {
        "problem_statement": "Identify the four phases on a ten-year real GDP graph.",
        "steps": [
            {"step_text": "Rising GDP is expansion and the top is the peak.", "rationale": "Output grows to a high point."},
            {"step_text": "The lowest point at the bottom is the trough.", "rationale": "GDP stops falling before rising."},
        ],
        "faded_step_index": 1,
        "solo_problem": "Identify expansion, peak, contraction, and trough on a new graph.",
        "solo_expected_answer": "Expansion rises, peak tops out, contraction falls, and trough is the lowest point.",
    },
}

BUSINESS_GOAL = {
    "id": "topic-goal-1",
    "type": "topic_goal",
    "data": {
        "topic": "Phases of the Business Cycle",
        "goal": "Describe expansion, peak, contraction, and trough.",
        "acceptance_criteria": "Student names and explains expansion, peak, contraction, and trough.",
        "teaching_notes": "Keep it concrete.",
    },
}


def test_bug1a_passage_paraphrase_passes_and_if_correct_never_reveals() -> None:
    """Chat 2 Turn 3: misspelled/paraphrased central idea must not trigger 'If correct: Give the answer'."""
    cfg = default_kc_tutor_config()
    state = {"substep": "central_idea", "dialogue_turns": 2, "block_attempts": 1}
    answer = "Their famly names keep them apart."

    forecast = forecast_this_turn(
        blocks=[deepcopy(BALCONY)],
        step=0,
        active_block_state=state,
        block_results=[],
        answer=answer,
        cfg=cfg,
        goal=None,
        stored_rubric=[],
        move_attempts=1,
        hint_tier="analogy",
        reveals=0,
        enrichment_turns=0,
        opening=False,
    )
    assert forecast.depends_on_model is True
    assert forecast.if_correct is not None
    assert forecast.if_correct.speech == "advance"
    assert forecast.if_correct.revealed is False

    prompt = _text(
        node=_node(blocks=[deepcopy(BALCONY)]),
        opening=False,
        attempts=1,
        hint_tier="analogy",
        reveals=0,
        last_answer=answer,
        active_block_state=state,
    )
    this_turn = _section(prompt, "This turn")
    assert "If correct: advance." in this_turn
    if_correct_line = next(line for line in this_turn.splitlines() if line.startswith("If correct:"))
    assert "Give the answer" not in if_correct_line

    resolved = resolve_block_turn(
        decision="advance",
        substep_passed=True,
        block_complete=False,
        rubric_met=["balcony-scene-topic:central_idea"],
        stored_rubric=[],
        matched_wrong="",
        blocks=[deepcopy(BALCONY)],
        step=0,
        active_block_state=state,
        block_results=[],
        move_attempts=1,
        hint_tier="analogy",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception="",
        answer=answer,
    )
    assert resolved.next_block_state["substep"] == "cite_evidence"
    assert resolved.reveals == 0
    assert resolved.hint_tier == "nudge"

    # Control: distractor detail alone must still be rejected even if the model sets substep_passed=True.
    distractor = resolve_block_turn(
        decision="advance",
        substep_passed=True,
        block_complete=False,
        rubric_met=["balcony-scene-topic:central_idea"],
        stored_rubric=[],
        matched_wrong="",
        blocks=[deepcopy(BALCONY)],
        step=0,
        active_block_state={"substep": "central_idea", "dialogue_turns": 0},
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception="",
        answer="Romeo is below Juliet.",
    )
    assert distractor.next_block_state["substep"] == "central_idea"
    assert distractor.move_attempts == 1


def test_bug1b_prior_block_reveals_do_not_force_reveal_turn_kind_on_new_block() -> None:
    """Chat 2 Turn 12: reveals from Block 1 must not mark Block 3 as Active turn kind: reveal."""
    prompt = _text(
        node=_node(blocks=[deepcopy(BALCONY), deepcopy(FRIAR)]),
        step=1,
        opening=False,
        attempts=1,
        hint_tier="analogy",
        reveals=2,
        last_answer="Paris thinks she means him, but she means Romeo.",
        active_block_state={"substep": "central_idea", "dialogue_turns": 1},
    )
    this_turn = _section(prompt, "This turn")
    assert "Active turn kind: reveal." not in this_turn
    assert "Attempt tier: reveal." not in this_turn

    # Control: when THIS block is genuinely in reveal state, reveal stays active.
    revealed_prompt = _text(
        node=_node(blocks=[deepcopy(BALCONY), deepcopy(FRIAR)]),
        step=1,
        opening=False,
        attempts=1,
        hint_tier="reveal",
        reveals=2,
        last_answer="idk",
        active_block_state={"substep": "central_idea", "dialogue_turns": 2, "revealed_substep": True},
    )
    assert "Active turn kind: reveal." in _section(revealed_prompt, "This turn")


def test_bug1c_one_word_or_taps_does_not_demand_full_sentence() -> None:
    """AI_Child2 has expression_style=one_word_or_taps; prompt must not contradict it with full-sentence demands."""
    young = _student(
        display_name="AI_Child2",
        age=6,
        reading_level="emerging",
        child_profile={
            "reading_level": "emerging",
            "response_length": "bite_sized",
            "expression_style": "one_word_or_taps",
        },
    )
    prompt = _text(
        student=young,
        node=_node(blocks=[deepcopy(BUSINESS_GOAL)]),
        opening=False,
        fragment=True,
        attempts=0,
        last_answer="Trough!",
        active_block_state={"substep": "main", "dialogue_turns": 1},
    )
    assert "one-word replies or taps" in prompt
    assert "ask for the idea in a full sentence" not in prompt.lower()
    assert "1-2 word fragment" not in prompt

    # Control: older learner with default expression_style still gets full-sentence prompt when enabled.
    older = _student(
        display_name="Ada",
        age=12,
        reading_level="middle-grade",
        child_profile={"expression_style": "short_sentences"},
    )
    older_prompt = _text(
        student=older,
        node=_node(blocks=[deepcopy(BUSINESS_GOAL)]),
        opening=False,
        fragment=True,
        attempts=0,
        last_answer="Trough!",
        active_block_state={"substep": "main", "dialogue_turns": 1},
    )
    assert "ask for the idea in a full sentence" in older_prompt.lower()


def test_bug2_socratic_counterexample_probe_progresses_and_does_not_loop_forever() -> None:
    """Chat 4 socratic-2: probe 1 must allow substep_passed=true, reset retries, and never trap after reveal."""
    cfg = default_kc_tutor_config()
    state = {
        "substep": "counterexample_probe",
        "thesis": "Easy one, big buttons!",
        "probe_turns": 0,
        "dialogue_turns": 4,
        "block_attempts": 3,
    }
    answer = "More people can use the plain screen easily."

    forecast = forecast_this_turn(
        blocks=[deepcopy(DESIGN_SOCRATIC), deepcopy(DESIGN_SOCRATIC_2)],
        step=1,
        active_block_state=state,
        block_results=[],
        answer=answer,
        cfg=cfg,
        goal=None,
        stored_rubric=["socratic-2:initial_thesis"],
        move_attempts=1,
        hint_tier="nudge",
        reveals=1,
        enrichment_turns=0,
        opening=False,
    )
    assert forecast.depends_on_model is True
    assert forecast.if_correct is not None

    prompt = _text(
        node=_node(blocks=[deepcopy(DESIGN_SOCRATIC), deepcopy(DESIGN_SOCRATIC_2)]),
        step=1,
        opening=False,
        attempts=1,
        hint_tier="nudge",
        reveals=1,
        last_answer=answer,
        active_block_state=state,
    )
    this_turn = _section(prompt, "This turn")
    assert "If correct:" in this_turn
    if_correct_line = next(line for line in this_turn.splitlines() if line.startswith("If correct:"))
    assert "Set substep_passed=false" not in if_correct_line

    # Passing probe 1 after earlier misses resets move_attempts for probe 2.
    after_probe_1 = resolve_block_turn(
        decision="stay",
        substep_passed=True,
        block_complete=False,
        rubric_met=[],
        stored_rubric=["socratic-2:initial_thesis"],
        matched_wrong="",
        blocks=[deepcopy(DESIGN_SOCRATIC), deepcopy(DESIGN_SOCRATIC_2)],
        step=1,
        active_block_state=state,
        block_results=[],
        move_attempts=2,
        hint_tier="scaffold",
        reveals=1,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception="",
        answer=answer,
    )
    assert after_probe_1.next_block_state["probe_turns"] == 1
    assert after_probe_1.move_attempts == 0
    assert after_probe_1.hint_tier == "nudge"

    # Passing probe 2 advances cleanly to summary_check (on the final block).
    after_probe_2 = resolve_block_turn(
        decision="advance",
        substep_passed=True,
        block_complete=False,
        rubric_met=[],
        stored_rubric=["socratic-2:initial_thesis"],
        matched_wrong="",
        blocks=[deepcopy(DESIGN_SOCRATIC), deepcopy(DESIGN_SOCRATIC_2)],
        step=1,
        active_block_state=after_probe_1.next_block_state,
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=1,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception="",
        answer="Clear labels make a plain screen easier to understand.",
    )
    assert after_probe_2.next_block_state["substep"] == "summary_check"

    # If the block was already revealed, an addressed probe exits to summary_check instead of looping.
    after_reveal = resolve_block_turn(
        decision="stay",
        substep_passed=True,
        block_complete=False,
        rubric_met=[],
        stored_rubric=["socratic-2:initial_thesis"],
        matched_wrong="",
        blocks=[deepcopy(DESIGN_SOCRATIC), deepcopy(DESIGN_SOCRATIC_2)],
        step=1,
        active_block_state={**state, "revealed_substep": True},
        block_results=[],
        move_attempts=2,
        hint_tier="reveal",
        reveals=1,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception="",
        answer=answer,
    )
    assert after_reveal.next_block_state["substep"] == "summary_check"


def test_bug3_off_topic_remark_never_closes_block_fragile_on_echoed_misconception() -> None:
    """Chat 4 Turn 5: 'My dog likes biskits!' must stay unscored even if the model echoes last_misconception."""
    cfg = default_kc_tutor_config()
    misconception = "Thinking that design is only about how a product looks, not how it works."
    state = {
        "substep": "counterexample_probe",
        "thesis": "My dog toy is fun cuz it squeeks!",
        "dialogue_turns": 4,
        "block_attempts": 3,
    }

    res = score_supported_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=["socratic-1:initial_thesis"],
        matched_wrong=misconception,
        blocks=[deepcopy(DESIGN_SOCRATIC), deepcopy(DESIGN_SOCRATIC_2)],
        step=0,
        active_block_state=state,
        block_results=[],
        move_attempts=3,
        hint_tier="scaffold",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception=misconception,
        answer="My dog likes biskits!",
    )
    assert res.decision == "stay"
    assert res.advance_block is False
    assert res.block_results == []
    assert res.move_attempts == 3
    assert int(res.next_block_state.get("block_attempts") or 0) == 3

    # Prompt on that same off-topic turn tells the model not to echo a misconception.
    prompt = _text(
        node=_node(blocks=[deepcopy(DESIGN_SOCRATIC), deepcopy(DESIGN_SOCRATIC_2)]),
        step=0,
        opening=False,
        attempts=3,
        hint_tier="scaffold",
        last_misconception=misconception,
        last_answer="My dog likes biskits!",
        active_block_state=state,
    )
    assert "misconception=null" in _section(prompt, "This turn")

    # Control: an actual on-topic repeated misconception still triggers the reveal redirect.
    real_repeat = resolve_block_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=["socratic-1:initial_thesis"],
        matched_wrong=misconception,
        blocks=[deepcopy(DESIGN_SOCRATIC), deepcopy(DESIGN_SOCRATIC_2)],
        step=0,
        active_block_state=state,
        block_results=[],
        move_attempts=1,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception=misconception,
        answer="Good design is only about how a product looks.",
    )
    assert real_repeat.advance_block is True
    assert real_repeat.block_results[-1]["outcome"] == "revealed"

    # One-word off-topic remark flagged off_course=True (Chat 1 Turn 17: 'Puppys!') stays unscored.
    one_word_off = resolve_block_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[deepcopy(WORKED_GDP)],
        step=0,
        active_block_state={"substep": "faded_step", "dialogue_turns": 0, "block_attempts": 0},
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=cfg,
        goal=None,
        last_misconception="",
        answer="Puppys!",
        off_course=True,
    )
    assert one_word_off.decision == "stay"
    assert one_word_off.move_attempts == 0
    assert int(one_word_off.next_block_state.get("block_attempts") or 0) == 0


def test_http_one_word_profile_and_off_course_stay_unscored_end_to_end() -> None:
    """Exercise /kc/tutor/sessions turn + decision end-to-end against PostgreSQL."""
    slug = f"zz-child-{uuid4().hex[:8]}"
    code = f"zz-audit-{uuid4().hex[:8]}"
    student_id = None
    course_id = None
    try:
        with SessionLocal() as db:
            student = Student(
                slug=slug,
                display_name="Young Reader",
                age=6,
                reading_level="emerging",
                modality="story",
                interests=["dogs"],
                child_profile={
                    "reading_level": "emerging",
                    "response_length": "bite_sized",
                    "expression_style": "one_word_or_taps",
                },
            )
            db.add(student)
            db.commit()
            db.refresh(student)
            student_id = str(student.id)

        created = client.post(
            "/kc/courses",
            json={
                "code": code,
                "title": "Audit Course",
                "description": "Verify short expression and off-course replies.",
                "audience": "6-8",
                "kind": "mastery",
            },
        )
        assert created.status_code == 200, created.text
        course_id = created.json()["id"]
        course = _ready(created.json(), [_spec(f"{code}-1", "Business Cycle", blocks=[deepcopy(BUSINESS_GOAL)])])
        kc_id = course["components"][0]["id"]

        opened = client.post(
            "/kc/tutor/sessions",
            json={"student_id": student_id, "course_id": course_id, "kc_id": kc_id},
        )
        assert opened.status_code == 200, opened.text
        sid = opened.json()["id"]
        path = f"/kc/tutor/sessions/{sid}"
        assert client.post(f"{path}/speech", json={"content": "Let's learn the four phases."}).status_code == 200

        # Move from explain -> main
        assert client.post(f"{path}/turn", json={"answer": "Got it - move on"}).status_code == 200
        moved = client.post(
            f"{path}/decision",
            json={"decision": "stay", "substep_passed": False, "block_complete": False, "reply": "Name a phase."},
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["active_substep"] == "main"

        # One-word off-course reply ("Puppys!") marked off_course=True must spend zero attempts
        turn_off = client.post(f"{path}/turn", json={"answer": "Puppys!"})
        assert turn_off.status_code == 200, turn_off.text
        assert "ask for the idea in a full sentence" not in turn_off.json()["system_prompt"].lower()
        dec_off = client.post(
            f"{path}/decision",
            json={
                "decision": "stay",
                "substep_passed": False,
                "block_complete": False,
                "off_course": True,
                "reply": "Puppies are fun! Back to the phases.",
            },
        )
        assert dec_off.status_code == 200, dec_off.text
        assert dec_off.json()["loop_result"]["attempt_counted"] is False
        with SessionLocal() as db:
            saved = db.get(KcSession, UUID(sid))
            assert saved is not None
            assert saved.move_attempts == 0
    finally:
        if student_id:
            with SessionLocal() as db:
                db.query(KcSession).filter(KcSession.student_id == student_id).delete()
                row = db.get(Student, student_id)
                if row is not None:
                    db.delete(row)
                db.commit()
        if course_id:
            client.request("DELETE", f"/kc/courses/{course_id}", json={"password": DELETE_PASSWORD})

