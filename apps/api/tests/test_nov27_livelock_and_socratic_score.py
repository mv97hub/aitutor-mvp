"""Regression tests for live Nov 27 Run 2 findings:
1. Middle Socratic block clean pass wrongly downgraded to fragile in block_score._passed().
2. Narrow scaffold reply ("Weakest, I guess.") misclassified as off-topic in _short_off_topic_remark().
3. Uncapped disengaged stall turns ("k", "yes", "What's next?") creating a stuck livelock.
4. Prompt/loop alignment when the stall cap triggers a reveal.
"""

from __future__ import annotations

from app.block_score import score_supported_turn
from app.kc_loop import resolve_block_turn
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _node, _section, _text

CFG = default_kc_tutor_config()

SOCRATIC_1 = {
    "id": "socratic-1",
    "type": "socratic",
    "data": {
        "central_dilemma": "Is good design just about making things look nice, or is there more to it?",
        "opening_probe": "Think about a device or app you enjoy using. Is it only how it looks?",
        "counterexamples": [
            "A phone that looks cool but is confusing to use.",
            "A website with fancy graphics but hard-to-find buttons.",
        ],
        "target_synthesis": "Good design balances appearance with usability.",
    },
}

SOCRATIC_2 = {
    "id": "socratic-2",
    "type": "socratic",
    "data": {
        "central_dilemma": "Why did Apple's focus on user experience help its products become so popular?",
        "opening_probe": "Would you pick a simple phone or a confusing phone with extra features?",
        "counterexamples": [
            "Some buyers want many features even if menus are complex.",
            "A plain-looking phone that lets beginners finish tasks quickly.",
        ],
        "target_synthesis": "Usable design lets more people succeed without frustration.",
    },
}

AP_MACRO_GOAL = {
    "id": "topic-goal-1",
    "type": "topic_goal",
    "data": {
        "topic": "Phases of the Business Cycle",
        "goal": "Explain the four phases of the business cycle: expansion, peak, contraction, and trough.",
        "acceptance_criteria": "Describe expansion, peak, contraction, and trough in order.",
    },
}

NEXT_GOAL = {
    "id": "topic-goal-2",
    "type": "topic_goal",
    "data": {
        "topic": "Next topic",
        "goal": "Explain the next topic.",
    },
}

GCSE_CASE = {
    "id": "case-study-contrasting",
    "type": "case_study",
    "data": {
        "block_title": "Condition and readiness of an army",
        "scenario_a": "Stamford Bridge: Harold surprises the Vikings after marching north.",
        "scenario_b": "Hastings: Harold arrives worn out against a rested Norman army.",
        "invariant_principle": "Exhaustion from forced marches weakens an army's effectiveness in battle.",
        "transfer_prompt": "Apply that rule to another battle.",
        "transfer_expected": "A rested army has an advantage over an exhausted one.",
    },
}


def test_middle_socratic_block_clean_pass_records_known_not_fragile() -> None:
    """Passing both probes on socratic-1 (followed by socratic-2) must seal known, not fragile."""
    blocks = [SOCRATIC_1, SOCRATIC_2]
    state: dict = {"substep": "initial_thesis", "dialogue_turns": 0}
    results: list[dict] = []
    rubric: list[str] = []
    step = 0
    move_attempts = 0
    hint_tier = "nudge"
    reveals = 0

    def send(answer: str, *, passed: bool = True, met: list[str] | None = None):
        nonlocal state, results, rubric, step, move_attempts, hint_tier, reveals
        res = score_supported_turn(
            decision="stay",
            substep_passed=passed,
            block_complete=False,
            rubric_met=list(met or []),
            stored_rubric=rubric,
            matched_wrong="",
            blocks=blocks,
            step=step,
            active_block_state=state,
            block_results=results,
            move_attempts=move_attempts,
            hint_tier=hint_tier,
            reveals=reveals,
            enrichment_turns=0,
            cfg=CFG,
            goal=None,
            last_misconception="",
            answer=answer,
        )
        state = dict(res.next_block_state or {})
        results = list(res.block_results or [])
        rubric = list(res.rubric_met or [])
        step = res.next_step
        move_attempts = res.move_attempts
        hint_tier = res.hint_tier
        reveals = res.reveals
        return res

    # Block 1 (socratic-1): thesis -> probe 1 -> probe 2 -> clean mid-pass to socratic-2
    r1 = send("Easy to find tools matters, not just nice colors.", met=["socratic-1:initial_thesis"])
    assert r1.advance_block is False
    assert state["substep"] == "counterexample_probe"

    r2 = send("A cool phone that is confusing fails usability.", met=["socratic-1:counterexample_probe"])
    assert r2.advance_block is False
    assert state["substep"] == "counterexample_probe"
    assert state["probe_turns"] == 1

    r3 = send("Fancy graphics cannot rescue a website with hidden buttons.", met=["socratic-1:counterexample_probe"])
    assert r3.advance_block is True
    assert step == 1
    assert len(results) == 1
    assert results[0]["verdict"] == "known"
    assert results[0]["outcome"] == "passed"
    reqs = {row["key"]: row["observation"] for row in results[0]["requirements"]}
    assert reqs == {
        "initial_thesis": "independent",
        "counterexample_1": "independent",
        "counterexample_2": "independent",
    }

    # Block 2 (socratic-2): thesis -> probe 1 -> probe 2 -> summary_check -> unit complete known
    send("The simple phone is better because I can use it right away.", met=["socratic-2:initial_thesis"])
    send("Tech fans might still buy complex phones, but most people prefer clarity.", met=["socratic-2:counterexample_probe"])
    send("A plain phone that works fast lets more people finish tasks easily.", met=["socratic-2:counterexample_probe"])
    done = send("No final questions — let's continue!", passed=False)
    assert done.unit_complete is True
    assert done.mark_known is True
    assert done.mark_fragile is False


def test_direct_answer_to_tutor_scaffold_question_is_counted_not_off_topic() -> None:
    """Live 69721bf7 T7: 'Weakest, I guess.' directly answers 'strongest or weakest?'."""
    prior = (
        "Picture a game's score chart: the peak is the highest point on the line, "
        "the trough is the lowest. So at a peak, is the economy at its strongest or its weakest?"
    )
    res = resolve_block_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[AP_MACRO_GOAL, NEXT_GOAL],
        step=0,
        active_block_state={"substep": "main", "dialogue_turns": 5, "fragment_prompted": True},
        block_results=[],
        move_attempts=2,
        hint_tier="scaffold",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer="Weakest, I guess.",
        prior_tutor=prior,
    )
    # move_attempts=2 -> 3rd attempt hits max_retries=3 -> reveals into summary_check!
    assert res.next_block_state["substep"] == "summary_check"
    assert res.next_block_state.get("revealed_substep") is True
    assert res.reveals == 1


def test_repeated_stalls_on_topic_goal_and_case_study_terminate_without_livelock() -> None:
    """Live 64fd5c3c & 942a2046: first 2 stalls stay free; 3rd+ drains retries and reveals."""
    # 1. topic_goal:main (64fd5c3c pattern: k, k, k, What's next?, What should we do next?)
    state: dict = {"substep": "main", "dialogue_turns": 1, "fragment_prompted": True}
    move_attempts = 0
    hint_tier = "nudge"
    reveals = 0

    def step_goal(answer: str):
        nonlocal state, move_attempts, hint_tier, reveals
        res = resolve_block_turn(
            decision="stay",
            substep_passed=False,
            block_complete=False,
            rubric_met=[],
            stored_rubric=[],
            matched_wrong="",
            blocks=[AP_MACRO_GOAL, NEXT_GOAL],
            step=0,
            active_block_state=state,
            block_results=[],
            move_attempts=move_attempts,
            hint_tier=hint_tier,
            reveals=reveals,
            enrichment_turns=0,
            cfg=CFG,
            goal=None,
            last_misconception="",
            answer=answer,
        )
        state = dict(res.next_block_state or {})
        move_attempts = res.move_attempts
        hint_tier = res.hint_tier
        reveals = res.reveals
        return res

    # First two stalls stay free
    r1 = step_goal("k")
    assert r1.move_attempts == 0
    assert state["substep"] == "main"
    r2 = step_goal("k")
    assert r2.move_attempts == 0
    assert state["substep"] == "main"

    # Genuine content/hint question does NOT burn a stall or attempt
    r_hint = step_goal("Can I get a hint?")
    assert r_hint.move_attempts == 0
    assert state["substep"] == "main"

    # 3rd, 4th, 5th stalls drain attempts 1 -> 2 -> 3 (reveal to summary_check)
    r3 = step_goal("k")
    assert r3.move_attempts == 1
    r4 = step_goal("What's next?")
    assert r4.move_attempts == 2
    r5 = step_goal("What should we do next?")
    assert state["substep"] == "summary_check"
    assert state.get("revealed_substep") is True
    assert r5.reveals == 1

    # 2. case_study:contrast_and_rule (942a2046 pattern: yes, yes, yes, What's next?, What should we do next?)
    cstate: dict = {"substep": "contrast_and_rule", "dialogue_turns": 1}
    cmove = 0
    chint = "nudge"
    creveals = 0
    for ans in ("yes", "yes", "yes", "What's next?", "What should we do next?"):
        cres = resolve_block_turn(
            decision="stay",
            substep_passed=False,
            block_complete=False,
            rubric_met=[],
            stored_rubric=[],
            matched_wrong="",
            blocks=[GCSE_CASE, NEXT_GOAL],
            step=0,
            active_block_state=cstate,
            block_results=[],
            move_attempts=cmove,
            hint_tier=chint,
            reveals=creveals,
            enrichment_turns=0,
            cfg=CFG,
            goal=None,
            last_misconception="",
            answer=ans,
        )
        cstate = dict(cres.next_block_state or {})
        cmove = cres.move_attempts
        chint = cres.hint_tier
        creveals = cres.reveals
    assert cstate["substep"] == "transfer"
    assert cstate.get("rule_supplied") is True
    assert cstate.get("stall_turns", 0) == 0
    assert creveals == 1


def test_prompt_aligns_with_stall_cap_reveal() -> None:
    """When stall #3 triggers reveal at move_attempts=2, prompt must NOT emit _SIDE_STAY."""
    node = _node(blocks=[AP_MACRO_GOAL, NEXT_GOAL], misconceptions=[])
    prompt = _text(
        node=node,
        opening=False,
        last_answer="What's next?",
        attempts=2,
        hint_tier="scaffold",
        active_block_state={
            "substep": "main",
            "dialogue_turns": 5,
            "fragment_prompted": True,
            "stall_turns": 2,
        },
    )
    turn_sec = _section(prompt, "This turn")
    assert "Do not count this turn as an attempt." not in turn_sec
    assert "unscored help" not in prompt.lower()
    assert "Give the answer" in turn_sec
