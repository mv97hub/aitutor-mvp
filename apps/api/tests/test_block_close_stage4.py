"""Stage 4. The other seven block types use the same requirement score.

No model call and no database. Each assessed block has a clean path, an assisted
path, and a turn that does not grade.
"""

from copy import deepcopy

from app.block_score import freeze_requirements, score_supported_turn, scoring_version_for_blocks
from app.kc_loop import forecast_this_turn, resolve_block_turn, rubric_covers_substep
from app.kc_prompt import initial_block_state, substeps_for_block, teach_back_task_steps
from app.learn_stars import stars_from_units
from app.models import ALL_BLOCK_TYPES, default_kc_tutor_config
from app.parents import session_star_unit

CFG = default_kc_tutor_config()
CONTINUE = "No final questions — let's continue!"
MOVE_ON = "Got it - move on"
QUESTION = "What does this part mean?"

TOPIC = {
    "id": "river",
    "type": "topic_goal",
    "data": {
        "topic": "Rivers",
        "goal": "Say the river is blue.",
        "acceptance_criteria": "The river is blue.",
    },
}
GOAL_ANSWER = "The river is blue because it reflects the sky."

MCQ = {
    "id": "quiz",
    "type": "mcq",
    "data": {
        "mode": "static",
        "question_stem": "Which color is the river?",
        "correct_explanation": "The river is blue because it reflects the sky.",
        "choices": [
            {"id": "a", "text": "Blue water", "is_correct": True},
            {"id": "b", "text": "Red paint"},
        ],
    },
}
WHY = "The river is blue because it reflects the sky."

CASE = {
    "id": "case",
    "type": "case_study",
    "data": {
        "case_a": "Maya checks the long bus record before she decides.",
        "case_b": "Jon trusts one dramatic delay and ignores the record.",
        "invariant_principle": "A long record is steadier than one memorable trip.",
        "transfer_prompt": "Who is more reliable when checking lock codes?",
        "transfer_expected": "Jon is more reliable because he checks many codes.",
    },
}

TALK = {
    "id": "talk",
    "type": "socratic",
    "data": {
        "central_dilemma": "Does a river always look blue?",
        "target_synthesis": "The river looks blue when the sky is clear.",
        "counterexamples": [
            "A muddy river looks brown after the rain.",
            "A river at night looks black without the sky.",
        ],
    },
}
THESIS = "The river looks blue when the sky is clear and open."

FLAW = {
    "id": "flaw",
    "type": "spot_the_flaw",
    "data": {
        "rookie_work": "One delay proves the buses are late.",
        "flaw_description": "The student counted one delay as the whole record.",
        "corrected_version": "A long record of on-time buses is steadier than one dramatic delay.",
    },
}
FOUND = "The student counted one delay as the whole record."
FIXED = "A long record of on-time buses is steadier than one dramatic delay."

TEACH = {
    "id": "teach1",
    "type": "teach_back",
    "data": {
        "peer_persona_prompt": "Explain to a friend why scarcity affects everyone",
        "required_concepts": ["Scarcity means limited resources", "People have to make choices"],
        "peer_follow_up_question": "Can you give one example from this week?",
    },
}
TAUGHT = "Scarcity means limited resources, so people have to make choices."

PASSAGE = {
    "id": "read",
    "type": "passage_ela",
    "data": {
        "passage_title": "River roads",
        "passage_text": (
            "Rivers carry fresh water from the hills to the sea.\n\n"
            "Towns grow beside rivers because boats can move food and people."
        ),
        "expected_central_idea": "Rivers help towns because they move water, food, and people.",
        "verbatim_evidence_quotes": [
            "Rivers carry fresh water from the hills to the sea.",
            "Towns grow beside rivers because boats can move food and people.",
        ],
        "expected_analysis": "A town far from a river would have a harder time moving food and people.",
        "distractor_detail": "A heron stood in the reeds at dawn.",
    },
}
CENTRAL = "Rivers help towns because they move water, food, and people."
QUOTE = "Rivers carry fresh water from the hills to the sea."
ANALYSIS = "A town far from a river would have a harder time moving food and people."


def _cfg(**blocks: dict) -> dict:
    cfg = deepcopy(CFG)
    for kind, patch in blocks.items():
        cfg["blocks"][kind].update(patch)
    return cfg


def _walk(block: dict, turns: list[tuple[str, bool]], *, cfg: dict | None = None, state: dict | None = None):
    active_cfg = cfg or CFG
    active = dict(state or initial_block_state(block, active_cfg))
    if "requirements" not in active:
        active["requirements"] = freeze_requirements(block, active_cfg)
    resolution = None
    results: list[dict] = []
    move = 0
    reveals = 0
    rubric: list[str] = []
    prior = ""
    for answer, passed in turns:
        resolution = score_supported_turn(
            decision="stay",
            substep_passed=passed,
            block_complete=False,
            rubric_met=[],
            stored_rubric=list(rubric),
            matched_wrong="",
            blocks=[dict(block)],
            step=0,
            active_block_state=dict(active),
            block_results=list(results),
            move_attempts=move,
            hint_tier="nudge",
            reveals=reveals,
            enrichment_turns=0,
            cfg=active_cfg,
            goal=None,
            last_misconception="",
            answer=answer,
            prior_tutor=prior,
        )
        active = dict(resolution.next_block_state)
        results = list(resolution.block_results)
        move = resolution.move_attempts
        reveals = resolution.reveals
        rubric = list(resolution.rubric_met)
        prior = ""
    assert resolution is not None
    return active, resolution


def _by_key(rows: list[dict]) -> dict[str, dict]:
    return {str(row.get("key")): row for row in rows}


def _sealed(resolution) -> dict[str, dict]:
    return _by_key(resolution.block_results[-1]["requirements"])


def _stars(resolution) -> dict:
    unit = session_star_unit("completed", resolution.block_results, resolution.reveals)
    return stars_from_units([unit])


def test_scoring_version_covers_the_full_set_and_stops_at_an_unknown_type() -> None:
    supported = [{"id": str(index), "type": kind, "data": {}} for index, kind in enumerate(ALL_BLOCK_TYPES)]
    assert set(ALL_BLOCK_TYPES) == {
        "retrieval_check",
        "worked_example",
        "explanation",
        "curiosity",
        "topic_goal",
        "mcq",
        "case_study",
        "socratic",
        "spot_the_flaw",
        "teach_back",
        "passage_ela",
    }
    assert scoring_version_for_blocks(supported) == 2
    assert scoring_version_for_blocks([*supported, {"id": "x", "type": "made_up", "data": {}}]) == 1
    assert scoring_version_for_blocks([]) == 1
    assert scoring_version_for_blocks(None) == 1


def test_forecast_does_not_commit_a_verdict() -> None:
    state = initial_block_state(PASSAGE, CFG)
    state["requirements"] = freeze_requirements(PASSAGE, CFG)
    state["substep"] = "craft_or_inference"
    results: list[dict] = []
    before_state = deepcopy(state)
    before_results = deepcopy(results)
    forecast = forecast_this_turn(
        blocks=[dict(PASSAGE)],
        step=0,
        active_block_state=state,
        block_results=results,
        answer=ANALYSIS,
        cfg=CFG,
        goal=None,
        stored_rubric=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
    )
    assert state == before_state
    assert results == before_results
    assert not hasattr(forecast, "verdict")
    scored = score_supported_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(PASSAGE)],
        step=0,
        active_block_state=deepcopy(before_state),
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer=ANALYSIS,
        prior_tutor="",
    )
    assert scored.block_results[-1]["verdict"] == "fragile"
    assert scored.next_block_state.get("component_verdict") == "fragile"


def test_topic_goal_clean_assisted_and_ungraded() -> None:
    _state, clean = _walk(TOPIC, [("Tell me more", False), (MOVE_ON, False), (GOAL_ANSWER, False), (CONTINUE, False)])
    assert clean.mark_known is True
    assert _sealed(clean)["goal"]["observation"] == "independent"
    assert _sealed(clean)["goal"]["attempts"] == 1
    assert _stars(clean)["stars"] == 55

    told, _held = _walk(TOPIC, [("Tell me more", False)])
    assert _by_key(told["requirements"])["goal"]["observation"] == "open"
    assert _by_key(told["requirements"])["goal"]["attempts"] == 0
    assert int(told.get("block_attempts") or 0) == 0

    _moved, assisted = _walk(TOPIC, [(MOVE_ON, False), (MOVE_ON, False)])
    assert assisted.block_results[-1]["verdict"] == "fragile"
    assert _sealed(assisted)["goal"]["observation"] == "assisted"
    assert _stars(assisted)["stars"] == 35

    asked, _open = _walk(TOPIC, [(MOVE_ON, False), (QUESTION, False)])
    assert asked["substep"] == "main"
    assert _by_key(asked["requirements"])["goal"]["attempts"] == 0
    assert _by_key(asked["requirements"])["goal"]["observation"] == "open"


def test_mcq_clean_assisted_frozen_key_and_ungraded() -> None:
    _state, clean = _walk(MCQ, [("Blue water", False), (CONTINUE, False)])
    assert clean.mark_known is True
    assert list(_sealed(clean)) == ["choice"]
    assert _sealed(clean)["choice"]["observation"] == "independent"
    assert _stars(clean)["stars"] == 55

    always = _cfg(mcq={"confirm_why_on_correct": "always"})
    _state, with_why = _walk(MCQ, [("Blue water", False), (WHY, True), (CONTINUE, False)], cfg=always)
    assert with_why.mark_known is True
    assert _sealed(with_why)["choice"]["observation"] == "independent"
    assert _sealed(with_why)["why"]["observation"] == "independent"

    _state, revealed = _walk(MCQ, [("Red paint", False), ("Red paint", False), (CONTINUE, False)])
    assert revealed.block_results[-1]["verdict"] == "fragile"
    assert _sealed(revealed)["choice"]["observation"] == "assisted"
    assert "why" not in _sealed(revealed)

    wide = dict(MCQ)
    wide["data"] = {
        **MCQ["data"],
        "choices": [
            {"id": "a", "text": "Alpha water", "is_correct": True},
            {"id": "b", "text": "Beta paint"},
            {"id": "c", "text": "Gamma ink"},
        ],
    }
    _state, eliminated = _walk(
        wide,
        [("Beta paint", False), ("Gamma ink", False), ("Alpha water", False), (WHY, True), (CONTINUE, False)],
        cfg=_cfg(mcq={"max_retry_attempts": 3}),
    )
    assert _sealed(eliminated)["choice"]["observation"] == "assisted"
    assert _sealed(eliminated)["why"]["observation"] == "independent"
    assert eliminated.block_results[-1]["verdict"] == "fragile"

    seeded = initial_block_state(MCQ, CFG)
    seeded["requirements"] = freeze_requirements(MCQ, CFG)
    seeded["mcq"] = {"frozen_key": 1}
    _state, frozen = _walk(MCQ, [("Red paint", False), (CONTINUE, False)], state=seeded)
    assert frozen.mark_known is True
    assert _sealed(frozen)["choice"]["observation"] == "independent"

    parked = initial_block_state(MCQ, _cfg(mcq={"confirm_why_on_correct": "never"}))
    parked["requirements"] = [
        {"key": "choice", "label": "Choice", "role": "assessed", "observation": "open", "attempts": 0, "gave_up": False, "ordinal": 0},
        {"key": "why", "label": "Why", "role": "assessed", "observation": "open", "attempts": 0, "gave_up": False, "ordinal": 1},
    ]
    _state, unasked = _walk(
        MCQ,
        [("Blue water", False), (CONTINUE, False)],
        cfg=_cfg(mcq={"confirm_why_on_correct": "never"}),
        state=parked,
    )
    assert unasked.mark_known is True
    assert list(_sealed(unasked)) == ["choice"]

    held, _open = _walk(MCQ, [(QUESTION, False)])
    assert _by_key(held["requirements"])["choice"]["attempts"] == 0
    assert _by_key(held["requirements"])["choice"]["observation"] == "open"


def test_case_study_keeps_prediction_rule_and_transfer_separate() -> None:
    _state, clean = _walk(
        CASE,
        [
            ("Maya checks the long bus record before she decides.", False),
            ("A long record is steadier than one memorable trip.", False),
            ("Jon is more reliable because he checks many codes.", True),
            (CONTINUE, False),
        ],
    )
    assert clean.mark_known is True
    rows = _sealed(clean)
    assert rows["predict"]["observation"] == "independent"
    assert rows["rule"]["observation"] == "independent"
    assert rows["transfer"]["observation"] == "independent"
    assert _stars(clean)["stars"] == 55

    _state, helped = _walk(
        CASE,
        [
            ("idk", False),
            ("idk", False),
            ("idk", False),
            ("A long record is steadier than one memorable trip.", False),
            ("Jon is more reliable because he checks many codes.", True),
            (CONTINUE, False),
        ],
    )
    rows = _sealed(helped)
    assert rows["predict"]["observation"] == "assisted"
    assert rows["rule"]["observation"] == "independent"
    assert rows["transfer"]["observation"] == "independent"
    assert helped.block_results[-1]["verdict"] == "fragile"
    assert "The prediction was assisted." in helped.block_results[-1]["summary"]
    assert "The rule was independent." in helped.block_results[-1]["summary"]
    assert _stars(helped)["stars"] == 35

    held, _open = _walk(CASE, [(QUESTION, False)])
    assert held["substep"] == "predict"
    assert _by_key(held["requirements"])["predict"]["attempts"] == 0


def test_socratic_thesis_and_each_counterexample_stay_separate() -> None:
    assert substeps_for_block(TALK, CFG) == ["initial_thesis", "counterexample_probe", "summary_check"]
    _state, clean = _walk(
        TALK,
        [
            (THESIS, False),
            ("A muddy river looks brown after the rain.", False),
            ("A river at night looks black without the sky.", False),
            (CONTINUE, False),
        ],
    )
    rows = _sealed(clean)
    assert rows["initial_thesis"]["observation"] == "independent"
    assert rows["counterexample_1"]["observation"] == "independent"
    assert rows["counterexample_2"]["observation"] == "independent"
    assert clean.mark_known is True

    repeated, _open = _walk(TALK, [(THESIS, False), (THESIS, True)])
    assert int(repeated.get("probe_turns") or 0) == 0
    assert repeated["substep"] == "counterexample_probe"
    probe = _by_key(repeated["requirements"])["counterexample_1"]
    assert probe["observation"] != "independent"

    asked, _open = _walk(TALK, [(QUESTION, False)])
    assert asked["substep"] == "initial_thesis"
    assert _by_key(asked["requirements"])["initial_thesis"]["attempts"] == 0


def test_spot_the_flaw_identification_survives_a_supplied_repair() -> None:
    both = f"{FOUND} {FIXED}"
    _state, clean = _walk(FLAW, [(both, True), (CONTINUE, False)])
    rows = _sealed(clean)
    assert rows["identify"]["observation"] == "independent"
    assert rows["repair"]["observation"] == "independent"
    assert rows["identify"]["attempts"] == 1
    assert rows["repair"]["attempts"] == 1
    assert clean.mark_known is True
    assert _stars(clean)["stars"] == 55

    _state, helped = _walk(FLAW, [(FOUND, False), ("idk", False), (CONTINUE, False)])
    rows = _sealed(helped)
    assert rows["identify"]["observation"] == "independent"
    assert rows["repair"]["observation"] == "assisted"
    assert helped.block_results[-1]["verdict"] == "fragile"
    assert "The flaw identification was independent." in helped.block_results[-1]["summary"]
    assert "The repair was assisted." in helped.block_results[-1]["summary"]

    given = score_supported_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(FLAW)],
        step=0,
        active_block_state={
            "substep": "critique",
            "requirements": [
                {
                    "key": "identify",
                    "label": "Identify the flaw",
                    "role": "assessed",
                    "observation": "independent",
                    "attempts": 1,
                    "gave_up": False,
                    "ordinal": 0,
                },
                {
                    "key": "repair",
                    "label": "Repair",
                    "role": "assessed",
                    "observation": "open",
                    "attempts": 0,
                    "gave_up": False,
                    "ordinal": 1,
                },
            ],
            "flaw_identified": True,
        },
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer=FIXED,
        prior_tutor=f"The answer is {FIXED}. Say it back.",
    )
    rows = _by_key(given.next_block_state["requirements"])
    assert rows["identify"]["observation"] == "independent"
    assert rows["repair"]["observation"] == "assisted"

    held, _open = _walk(FLAW, [(QUESTION, False)])
    assert _by_key(held["requirements"])["identify"]["attempts"] == 0
    assert _by_key(held["requirements"])["repair"]["observation"] == "open"


def test_teach_back_follow_ups_do_not_share_an_evidence_id() -> None:
    assert teach_back_task_steps(0) == ["initial_explanation"]
    assert teach_back_task_steps(1) == ["initial_explanation", "peer_follow_up"]
    assert teach_back_task_steps(2) == ["initial_explanation", "peer_follow_up_1", "peer_follow_up_2"]
    assert substeps_for_block(TEACH, CFG) == ["initial_explanation", "peer_follow_up", "summary_check"]
    assert substeps_for_block(TEACH, _cfg(teach_back={"follow_up_questions_count": 0})) == [
        "initial_explanation",
        "summary_check",
    ]
    assert substeps_for_block(TEACH, _cfg(teach_back={"follow_up_questions_count": 2})) == [
        "initial_explanation",
        "peer_follow_up_1",
        "peer_follow_up_2",
        "summary_check",
    ]
    assert rubric_covers_substep(TEACH, 0, "peer_follow_up", ["teach1:initial_explanation"]) is False
    assert rubric_covers_substep(TEACH, 0, "peer_follow_up", ["teach1:follow_up_question"]) is True
    assert rubric_covers_substep(TEACH, 0, "peer_follow_up_2", ["teach1:peer_follow_up_1"]) is False
    assert rubric_covers_substep(TEACH, 0, "peer_follow_up_1", ["teach1:peer_follow_up_2"]) is False
    assert rubric_covers_substep(TEACH, 0, "peer_follow_up_2", ["teach1:peer_follow_up_2"]) is True

    _state, one = _walk(TEACH, [(TAUGHT, True), (TAUGHT, True), (CONTINUE, False)])
    rows = _sealed(one)
    assert list(rows) == ["initial_explanation", "peer_follow_up"]
    assert rows["initial_explanation"]["observation"] == "independent"
    assert rows["peer_follow_up"]["observation"] == "independent"
    assert one.mark_known is True

    _state, two = _walk(
        TEACH,
        [(TAUGHT, True), (TAUGHT, True), (TAUGHT, True), (CONTINUE, False)],
        cfg=_cfg(teach_back={"follow_up_questions_count": 2}),
    )
    rows = _sealed(two)
    assert list(rows) == ["initial_explanation", "peer_follow_up_1", "peer_follow_up_2"]
    assert {row["observation"] for row in rows.values()} == {"independent"}

    _state, none = _walk(
        TEACH,
        [(TAUGHT, True), (CONTINUE, False)],
        cfg=_cfg(teach_back={"follow_up_questions_count": 0}),
    )
    assert list(_sealed(none)) == ["initial_explanation"]
    assert none.mark_known is True

    capped = resolve_block_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=["teach1:initial_explanation"],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(TEACH)],
        step=0,
        active_block_state={"substep": "peer_follow_up"},
        block_results=[],
        move_attempts=1,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer="idk",
    )
    assert capped.advance_block is False
    assert capped.reveals == 1
    assert capped.next_block_state["substep"] == "summary_check"
    assert capped.next_block_state["revealed_substep"] is True

    missed = resolve_block_turn(
        decision="stay",
        substep_passed=False,
        block_complete=False,
        rubric_met=["teach1:peer_follow_up_1"],
        stored_rubric=["teach1:initial_explanation"],
        matched_wrong="",
        blocks=[dict(TEACH)],
        step=0,
        active_block_state={"substep": "peer_follow_up_2"},
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=_cfg(teach_back={"follow_up_questions_count": 2}),
        goal=None,
        last_misconception="",
        answer="idk",
    )
    assert missed.next_block_state["substep"] == "peer_follow_up_2"
    assert missed.advance_block is False

    held, _open = _walk(TEACH, [(QUESTION, False)])
    assert held["substep"] == "initial_explanation"
    assert _by_key(held["requirements"])["initial_explanation"]["attempts"] == 0
    assert _by_key(held["requirements"])["peer_follow_up"]["observation"] == "open"


def test_passage_quote_pointing_and_reread() -> None:
    exact = _cfg(passage_ela={"passage_ela_evidence_mode": "exact_quote_required"})
    _state, clean = _walk(PASSAGE, [(CENTRAL, False), (QUOTE, False), (ANALYSIS, False)], cfg=exact)
    rows = _sealed(clean)
    assert rows["central_idea"]["observation"] == "independent"
    assert rows["cite_evidence"]["observation"] == "independent"
    assert rows["craft_or_inference"]["observation"] == "independent"
    assert clean.mark_known is True
    assert _stars(clean)["stars"] == 55

    _state, pointed = _walk(
        PASSAGE,
        [(CENTRAL, False), ("Please reread the passage", False), ("Look at that sentence.", False), (ANALYSIS, False)],
        cfg=exact,
    )
    rows = _sealed(pointed)
    assert rows["central_idea"]["observation"] == "independent"
    assert rows["cite_evidence"]["observation"] == "assisted"
    assert rows["cite_evidence"]["attempts"] == 1
    assert rows["craft_or_inference"]["observation"] == "independent"
    assert pointed.block_results[-1]["verdict"] == "fragile"
    assert "The citation was assisted." in pointed.block_results[-1]["summary"]
    assert "The central idea was independent." in pointed.block_results[-1]["summary"]
    assert _stars(pointed)["stars"] == 35

    held, _open = _walk(PASSAGE, [("Please reread the passage", False)], cfg=exact)
    assert held["substep"] == "central_idea"
    assert int(held.get("block_attempts") or 0) == 0
    assert _by_key(held["requirements"])["central_idea"]["attempts"] == 0
    assert _by_key(held["requirements"])["cite_evidence"]["observation"] == "open"
