"""The passage_ela block is a separate reading type. The other block types stay as they are."""

from copy import deepcopy

from app.block_catalog import BLOCK_AUTHORING_RULES, BLOCK_DATA_SCHEMAS, BLOCK_FIELDS, PASSAGE_LENGTH_GUIDELINES
from app.kc_blocks import (
    PASSAGE_CAP_RULE,
    PASSAGE_TEXT_LIMIT,
    clean_passage_ela_data,
    learner_asks_for_passage,
    passage_ela_gap,
)
from app.kc_course_io import normalize_blocks
from app.kc_loop import resolve_block_turn
from app.kc_model import creator_bundle
from app.kc_pipeline import course_is_ela, passage_ela_generation_lines
from app.kc_prompt import build_kc_prompt, substeps_for_block
from app.models import ALL_BLOCK_TYPES, default_kc_tutor_config
from tests.test_kc_model import GEOMETRY, _sib
from tests.test_kc_prompt import _goal, _node, _profile, _student, _text

PASSAGE = (
    "Rivers carry fresh water from the hills to the sea.\n\n"
    "Towns grow beside rivers because boats can move food and people.\n\n"
    "A heron stood in the reeds at dawn."
)

BLOCK = {
    "id": "blk_passage",
    "type": "passage_ela",
    "data": {
        "passage_title": "River roads",
        "passage_genre": "informational",
        "passage_text": PASSAGE,
        "central_idea_question": "What is the central idea of the passage?",
        "expected_central_idea": "Rivers help towns because they move water, food, and people.",
        "distractor_detail": "A heron stood in the reeds at dawn.",
        "evidence_prompt": "Cite two sentences that support the central idea.",
        "verbatim_evidence_quotes": [
            "Rivers carry fresh water from the hills to the sea.",
            "Towns grow beside rivers because boats can move food and people.",
        ],
        "analysis_focus": "inference",
        "analysis_question": "What can a reader infer about a town far from a river?",
        "expected_analysis": "A town far from a river would have a harder time moving food and people.",
    },
}


def test_passage_ela_is_the_eleventh_catalog_type_and_the_others_keep_their_fields() -> None:
    assert ALL_BLOCK_TYPES[-1] == "passage_ela"
    assert len(ALL_BLOCK_TYPES) == 11
    assert set(BLOCK_FIELDS) == set(ALL_BLOCK_TYPES)
    topic = BLOCK_DATA_SCHEMAS["topic_goal"]
    assert topic["required"] == ["topic", "goal", "acceptance_criteria", "teaching_notes"]
    assert "passage_text" not in topic["properties"]
    worked = BLOCK_DATA_SCHEMAS["worked_example"]["properties"]
    assert "solo_problem" in worked
    assert "passage_text" not in worked
    passage = BLOCK_DATA_SCHEMAS["passage_ela"]
    assert passage["properties"]["passage_title"]["maxLength"] == 160
    assert passage["properties"]["passage_text"]["maxLength"] == 4000
    assert passage["properties"]["verbatim_evidence_quotes"]["minItems"] == 2
    assert passage["properties"]["verbatim_evidence_quotes"]["maxItems"] == 3
    rule = BLOCK_AUTHORING_RULES["passage_ela"]
    assert "100 to 180" in rule
    assert "200 to 320" in rule
    assert "320 to 450" in rule
    assert "verbatim" in rule
    assert PASSAGE_LENGTH_GUIDELINES in rule
    assert "topic_goal" not in rule


def test_cleaning_caps_the_passage_keeps_paragraph_breaks_and_aligns_quotes() -> None:
    long_text = ("A" * 3990) + "\n\n" + ("B" * 80)
    clipped = clean_passage_ela_data(
        {
            "passage_title": "T" * 180,
            "passage_genre": "not-a-genre",
            "passage_text": long_text,
            "analysis_focus": "nope",
            "central_idea_question": " What is it? ",
        }
    )
    assert len(clipped["passage_title"]) == 160
    assert len(clipped["passage_text"]) == PASSAGE_TEXT_LIMIT
    assert "\n\n" in clipped["passage_text"]
    assert clipped["passage_genre"] == "informational"
    assert clipped["analysis_focus"] == "inference"
    assert clipped["central_idea_question"] == "What is it?"
    cleaned = clean_passage_ela_data(
        {
            "passage_text": PASSAGE,
            "verbatim_evidence_quotes": [
                "rivers   carry fresh water from the hills to the sea.",
                "This sentence is not in the passage at all.",
                "Towns grow beside rivers because boats can move food and people.",
                "A heron stood in the reeds at dawn.",
            ],
        }
    )
    assert cleaned["verbatim_evidence_quotes"] == [
        "Rivers carry fresh water from the hills to the sea.",
        "Towns grow beside rivers because boats can move food and people.",
        "A heron stood in the reeds at dawn.",
    ]
    kept = normalize_blocks(
        [
            {
                "type": "passage_ela",
                "data": {
                    "passage_text": "Rivers carry fresh water from the hills to the sea.\n\nTowns grow beside rivers.",
                    "verbatim_evidence_quotes": ["Rivers carry   fresh water from the hills to the sea."],
                    "extra": "drop me",
                },
            }
        ]
    )
    assert "extra" not in kept[0]["data"]
    assert kept[0]["data"]["verbatim_evidence_quotes"] == ["Rivers carry fresh water from the hills to the sea."]
    assert "\n\n" in kept[0]["data"]["passage_text"]
    assert passage_ela_gap(BLOCK["data"]) == ""
    missing_quotes = dict(BLOCK["data"])
    missing_quotes["verbatim_evidence_quotes"] = ["not in the passage"]
    assert "copied from the passage" in passage_ela_gap(missing_quotes)


def test_a_passage_request_is_not_an_attempt_and_the_three_steps_advance() -> None:
    for phrase in ("show me the passage", "what passage?", "can I see the passage", "can I see paragraph 2 again?"):
        assert learner_asks_for_passage(phrase)
    assert learner_asks_for_passage("The central idea is that rivers help towns.") is False

    cfg = default_kc_tutor_config()
    state = {"substep": "central_idea", "dialogue_turns": 0}

    def turn(answer: str, block_state: dict, *, attempts: int = 0, passed: bool = False, mode: str | None = None):
        local = deepcopy(cfg)
        if mode:
            local["blocks"]["passage_ela"]["passage_ela_evidence_mode"] = mode
        return resolve_block_turn(
            decision="stay",
            substep_passed=passed,
            block_complete=False,
            rubric_met=[],
            stored_rubric=[],
            matched_wrong="",
            blocks=[deepcopy(BLOCK)],
            step=0,
            active_block_state=block_state,
            block_results=[],
            move_attempts=attempts,
            hint_tier="nudge",
            reveals=0,
            enrichment_turns=0,
            cfg=local,
            goal=None,
            last_misconception="",
            answer=answer,
        )

    reread = turn("show me the passage", state, attempts=1, passed=True)
    assert reread.decision == "stay"
    assert reread.move_attempts == 1
    assert reread.passed is False
    assert reread.advance_block is False
    assert reread.unit_complete is False
    assert reread.block_results == []
    assert reread.next_block_state["substep"] == "central_idea"
    assert int(reread.next_block_state.get("block_attempts") or 0) == 0

    detail = turn("A heron stood in the reeds at dawn.", state, passed=True)
    assert detail.next_block_state["substep"] == "central_idea"
    assert detail.move_attempts == 1

    central = turn(
        "Rivers help towns because they move water, food, and people.",
        state,
        passed=True,
    )
    assert central.decision == "stay"
    assert central.next_block_state["substep"] == "cite_evidence"
    assert central.move_attempts == 0
    assert central.unit_complete is False

    cited = turn(
        "The passage says towns grow beside rivers because boats can move food and people.",
        central.next_block_state,
        passed=True,
    )
    assert cited.next_block_state["substep"] == "craft_or_inference"
    exact = turn(
        "Towns use rivers, in my own words, without a quotation.",
        central.next_block_state,
        passed=True,
        mode="exact_quote_required",
    )
    assert exact.next_block_state["substep"] == "cite_evidence"
    assert exact.move_attempts == 1

    done = turn(
        "A town far from a river would have a harder time moving food and people.",
        cited.next_block_state,
        passed=True,
    )
    assert done.decision == "complete"
    assert done.unit_complete is True
    assert done.block_results[-1]["outcome"] == "passed"

    capped = turn("I do not know yet.", {"substep": "central_idea", "dialogue_turns": 1}, attempts=1)
    assert capped.decision == "stay"
    assert capped.next_block_state["substep"] == "cite_evidence"
    assert capped.move_attempts == 0
    assert capped.unit_complete is False
    assert substeps_for_block(BLOCK, cfg) == ["central_idea", "cite_evidence", "craft_or_inference"]


def _passage_prompt(**overrides: object) -> str:
    student = _student(child_profile={"response_length": "bite_sized", "reading_level": "on_grade"})
    profile = overrides.pop("profile", _profile())
    values: dict[str, object] = {
        "student": student,
        "profile": profile,
        "node": _node(blocks=[deepcopy(BLOCK)]),
        "goal": _goal(),
        "step": 0,
        "opening": True,
        "choice_on_screen": False,
        "prerequisite_status": "",
        "support_band": "ready",
        "course_position": "1 of 1",
        "unit_complete": False,
        "course_complete": False,
        "attempts": 0,
        "hint_tier": "nudge",
        "reveals": 0,
        "off_course_count": 0,
        "affect": "",
        "enrichment_turns": 0,
        "help_requested": False,
        "minutes_used": 0,
        "component_status": "unknown",
        "stability": "0",
        "last_answer": "",
        "last_misconception": "",
        "last_messages": "",
        "rubric_met": [],
        "redirect_pending": False,
        "fragment": False,
        "others_known": False,
        "active_block_state": {"substep": "central_idea", "dialogue_turns": 0},
    }
    values.update(overrides)
    return build_kc_prompt(**values)["system_prompt"]


def test_the_opening_prompt_prints_the_passage_and_other_blocks_do_not() -> None:
    other = _text()
    assert "passage_ela" not in other
    assert "Passage text:" not in other
    assert PASSAGE_CAP_RULE not in other
    assert "reprint the passage" not in other

    text = _passage_prompt()
    assert PASSAGE_CAP_RULE in text
    assert PASSAGE in text.split("What to teach", 1)[1]
    assert "Active substep (1/3 central_idea):" in text
    assert "Keep response length bite-sized" not in text
    assert "ELA substep 1 of 3 (central_idea). Attempt tier: ask." in text
    how = text.split("How to teach", 1)[1].split("What to return", 1)[0]
    assert "reprint the passage text verbatim" in how
    assert "Do not count that turn as an attempt." in how

    later = _passage_prompt(
        opening=False,
        last_answer="Rivers help towns.",
        active_block_state={"substep": "cite_evidence", "dialogue_turns": 2},
        attempts=0,
    )
    assert PASSAGE_CAP_RULE not in later
    assert "Active substep (2/3 cite_evidence):" in later
    assert "Keep response length bite-sized" in later
    assert "Rivers carry fresh water from the hills to the sea." in later

    asked = _passage_prompt(
        opening=False,
        last_answer="what passage?",
        active_block_state={"substep": "cite_evidence", "dialogue_turns": 2},
    )
    assert PASSAGE_CAP_RULE in asked

    profile = _profile()
    cfg = default_kc_tutor_config()
    cfg["blocks"]["passage_ela"]["passage_ela_display_mode"] = "chunked_by_paragraph"
    cfg["blocks"]["passage_ela"]["passage_ela_evidence_mode"] = "exact_quote_required"
    profile.kc_tutor_config = cfg
    chunked = _passage_prompt(profile=profile)
    assert "Do not print later paragraphs" in chunked
    assert "Paragraph 1:\nRivers carry fresh water from the hills to the sea." in chunked
    assert "quote_or_close_paraphrase" not in chunked
    assert "quotes words or a sentence from the passage" in chunked
    assert PASSAGE_CAP_RULE not in chunked


def test_ela_courses_get_passage_guidance_and_other_courses_do_not() -> None:
    assert course_is_ela("Grade 7 ELA", "reading comprehension")
    assert course_is_ela("British literature")
    assert course_is_ela(GEOMETRY) is False
    lines = passage_ela_generation_lines("Grade 6 ELA", "Reading comprehension of informational text")
    assert lines
    assert "100 to 180" in lines[0]
    assert "verbatim_evidence_quotes" in lines[0]
    assert passage_ela_generation_lines("Euclidean geometry", GEOMETRY) == []

    ela = creator_bundle(
        course_title="Grade 6 ELA",
        course_description="Reading comprehension of informational text.",
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Central idea",
        node_code="central-idea",
        node_description="The learner can state the central idea of a short passage.",
        siblings=_sib([]),
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )
    assert "Include passage_ela blocks" in ela["system_prompt"]
    math = creator_bundle(
        course_title="Euclidean geometry",
        course_description=GEOMETRY,
        audience="12-14",
        kind="mastery",
        minutes=None,
        node_title="Triangle angle sum",
        node_code="angle-sum",
        node_description="The interior angles add to a straight line.",
        siblings=_sib(["missing-angle"]),
        previous=None,
        message="Draft this component.",
        model="gpt-4.1",
    )
    assert "Include passage_ela blocks" not in math["system_prompt"]
    variants = ela["schema"]["properties"]["blocks"]["items"]["anyOf"]
    assert "passage_ela" in [item["properties"]["type"]["enum"][0] for item in variants]
