"""Passage leak, a clean mid-component close, and no second explanation.

A psychology or "How AI works" component gets no passage. An ELA component
still gets one. A clean pass in the middle of a component opens the next
block. A topic and goal that follows an explanation asks the goal.
"""

from types import SimpleNamespace

from app.kc import clean_model_component
from app.kc_loop import forecast_this_turn, resolve_block_turn
from app.kc_model import creator_bundle, passage_draft_allowed
from app.kc_prompt import initial_block_state
from app.models import default_allowed_block_types, default_kc_tutor_config
from tests.test_kc_prompt import _goal, _node, _profile, _section, _student, _text

CFG = default_kc_tutor_config()
TOPIC = {
    "id": "topic",
    "type": "topic_goal",
    "data": {
        "topic": "River color",
        "goal": "The river is blue.",
        "acceptance_criteria": "The river is blue.",
    },
}
NEXT = {"id": "next", "type": "mcq", "data": {"mode": "static", "question_stem": "Which color?"}}
EXPLAIN = {
    "id": "explain",
    "type": "explanation",
    "data": {
        "block_title": "Rivers",
        "topics": [
            {
                "id": "top_1",
                "title": "Rivers",
                "explanation": "A river moves rock and carves a valley.",
                "key_points": "Moving rock.",
            }
        ],
    },
}
GOAL = {
    "id": "goal",
    "type": "topic_goal",
    "data": {
        "topic": "Rivers",
        "goal": "Say how a river carves a valley.",
        "acceptance_criteria": "A river moves rock.",
    },
}


def _component(title: str, description: str, *, archetype: str = ""):
    node = SimpleNamespace(id="n1", code="idea", title=title, description=description, archetype=archetype)
    draft = {
        "title": title,
        "description": "A short summary of the component.",
        "outline": "Teach the idea, then check it.",
        "core_truth": "The idea holds.",
        "blocks": [
            {
                "id": "blk_goal",
                "type": "topic_goal",
                "data": {"topic": title, "goal": "Say the idea in your own words."},
            }
        ],
        "misconceptions": [],
        "prerequisite_codes": [],
        "encompasses_codes": [],
    }
    shaped, _repairs, _mix = clean_model_component(
        node,
        draft,
        [],
        default_allowed_block_types(),
        audience="12-14",
        course_title=title,
        course_description=description,
        archetype=archetype,
    )
    return shaped


def _turn(blocks: list[dict], answer: str, state: dict, *, substep_passed: bool = True, prior_tutor: str = ""):
    return resolve_block_turn(
        decision="advance" if substep_passed else "stay",
        substep_passed=substep_passed,
        block_complete=False,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=blocks,
        step=0,
        active_block_state=dict(state),
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer=answer,
        prior_tutor=prior_tutor,
    )


def _forecast(blocks: list[dict], answer: str, state: dict, *, prior_tutor: str = ""):
    return forecast_this_turn(
        blocks=blocks,
        step=0,
        active_block_state=dict(state),
        block_results=[],
        answer=answer,
        cfg=CFG,
        goal=None,
        stored_rubric=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        prior_tutor=prior_tutor,
    )


def test_psychology_and_how_ai_works_get_no_passage_and_ela_still_does() -> None:
    for title, description in (
        ("Psychology", "How memory and attention work in the mind."),
        ("How AI works", "How a model turns a prompt into a reply."),
    ):
        shaped = _component(title, description)
        assert [block["type"] for block in shaped["blocks"]] == ["topic_goal"]
        assert "brass key" not in str(shaped).lower()
        assert passage_draft_allowed(title, description) is False
        bundle = creator_bundle(
            course_title=title,
            course_description=description,
            audience="12-14",
            kind="mastery",
            minutes=None,
            node_title=title,
            node_code="idea",
            node_description=description,
            siblings=[],
            previous=None,
            message="Create Draft",
            model="gpt-4.1",
        )
        assert "exactly one passage_ela" not in bundle["system_prompt"]
        assert "brass key" not in bundle["system_prompt"].lower()

    ela = _component("Grade 7 ELA", "Reading comprehension of informational text.")
    assert any(block["type"] == "passage_ela" for block in ela["blocks"])
    assert "brass key" in str(ela).lower()

    textual = _component(
        "Psychology",
        "How memory and attention work in the mind.",
        archetype="textual_interpretive",
    )
    assert any(block["type"] == "passage_ela" for block in textual["blocks"])


def test_a_clean_mid_component_pass_skips_summary_and_the_forecast_matches() -> None:
    blocks = [dict(TOPIC), dict(NEXT)]
    state = {"substep": "main"}
    answer = "The river is blue."
    closed = _turn(blocks, answer, state)
    forecast = _forecast(blocks, answer, state)
    assert closed.advance_block is True
    assert closed.next_step == 1
    assert closed.block_results[-1]["outcome"] == "passed"
    assert closed.next_block_state.get("substep") != "summary_check"
    assert forecast.if_correct is not None
    assert forecast.if_correct.advance_block is True
    assert forecast.if_correct.speech == "close"
    assert forecast.if_correct.next_substep == closed.next_block_state["substep"]

    revealed = _turn(blocks, answer, {"substep": "main", "revealed_substep": True})
    revealed_forecast = _forecast(blocks, answer, {"substep": "main", "revealed_substep": True})
    assert revealed.advance_block is False
    assert revealed.next_block_state["substep"] == "summary_check"
    assert revealed_forecast.if_correct is not None
    assert revealed_forecast.if_correct.next_substep == "summary_check"
    assert revealed_forecast.if_correct.advance_block is False

    given = _turn(
        blocks,
        answer,
        {"substep": "main"},
        prior_tutor="The river is blue. Now say it back.",
    )
    given_forecast = _forecast(blocks, answer, {"substep": "main"}, prior_tutor="The river is blue. Now say it back.")
    assert given.advance_block is False
    assert given.next_block_state["substep"] == "summary_check"
    assert given_forecast.if_correct is not None
    assert given_forecast.if_correct.next_substep == "summary_check"

    last = _turn([dict(TOPIC)], answer, state)
    last_forecast = _forecast([dict(TOPIC)], answer, state)
    assert last.advance_block is False
    assert last.next_block_state["substep"] == "summary_check"
    assert last_forecast.if_correct is not None
    assert last_forecast.if_correct.next_substep == "summary_check"
    assert last_forecast.if_correct.speech == "advance"


def test_topic_goal_after_an_explanation_asks_the_goal() -> None:
    opened = initial_block_state(GOAL, CFG, previous=EXPLAIN)
    assert opened["substep"] == "main"
    assert initial_block_state(GOAL, CFG)["substep"] == "explain"
    assert initial_block_state(GOAL, CFG, previous=NEXT)["substep"] == "explain"

    finished = resolve_block_turn(
        decision="stay",
        substep_passed=True,
        block_complete=True,
        rubric_met=[],
        stored_rubric=[],
        matched_wrong="",
        blocks=[dict(EXPLAIN), dict(GOAL)],
        step=0,
        active_block_state={"substep": "explain_topic", "topic_index": 0, "topic_taught": True, "dialogue_turns": 1},
        block_results=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        cfg=CFG,
        goal=None,
        last_misconception="",
        answer="Got it - move on",
    )
    assert finished.advance_block is True
    assert finished.next_step == 1
    assert finished.next_block_id == "goal"
    assert finished.next_block_state["substep"] == "main"

    text = _text(
        student=_student(),
        profile=_profile(),
        node=_node(blocks=[dict(EXPLAIN), dict(GOAL)], misconceptions=[]),
        goal=_goal(),
        step=1,
        opening=True,
        last_answer="",
        attempts=0,
        active_block_state={"substep": "main", "dialogue_turns": 0},
    )
    turn = _section(text, "This turn")
    teach = _section(text, "What to teach")
    assert "Ask the opening question for this goal." in turn
    assert "Do not teach the concept again." in turn
    assert "Do not teach the concept again." in teach
    assert "Goal start: Explain what this topic is" not in text
    assert "Do not ask the goal question." not in text
    assert "Topic to introduce:" not in teach
