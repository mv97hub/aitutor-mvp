"""Phase B: one This turn branch from a local dry run of the loop.

A known move-on, a known stay, and a model-dependent turn each produce one
consistent branch. A stored prompt does not hold both congratulate and never
congratulate.
"""

from app.kc_loop import forecast_this_turn
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _node, _section, _text

TOPIC = {
    "id": "topic",
    "type": "topic_goal",
    "data": {
        "topic": "River color",
        "goal": "The river is blue.",
        "acceptance_criteria": "The river is blue.",
    },
}
NEXT = {"id": "next", "type": "topic_goal", "data": {"topic": "Next", "goal": "Explain the next idea."}}
PRAISE = "congratulate the learner once"
NEVER = "never say congratulations"


def _course():
    return _node(blocks=[dict(TOPIC), dict(NEXT)], misconceptions=[])


def _turn(answer: str, state: dict):
    text = _text(
        node=_course(),
        opening=False,
        attempts=0,
        last_answer=answer,
        last_messages=f"assistant: What color is the river? | user: {answer}",
        active_block_state=state,
        fragment=False,
    )
    return text, _section(text, "This turn")


def _forecast(answer: str, state: dict):
    return forecast_this_turn(
        blocks=[dict(TOPIC), dict(NEXT)],
        step=0,
        active_block_state=dict(state),
        block_results=[],
        answer=answer,
        cfg=default_kc_tutor_config(),
        goal=None,
        stored_rubric=[],
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        fragment=False,
        prior_tutor="What color is the river?",
        opening=False,
    )


def _consistent(text: str) -> None:
    low = text.lower()
    assert not (PRAISE in low and NEVER in low)


def test_move_on_stay_and_model_dependent_turns_each_have_one_branch() -> None:
    summary = {"substep": "summary_check", "last_task_substep": "main", "revealed_substep": False}
    moved_text, moved = _turn("move on", summary)
    moved_forecast = _forecast("move on", summary)
    assert moved_forecast.applies is True
    assert moved_forecast.depends_on_model is False
    assert moved_forecast.chosen is not None
    assert moved_forecast.chosen.speech == "close"
    assert moved.count("Decision: close.") == 1
    assert "If correct:" not in moved
    assert "If not:" not in moved
    assert "Close in one sentence." in moved
    assert "Begin the next block in this same reply." not in moved_text
    _consistent(moved_text)

    question = "Why is the river blue?"
    stayed_text, stayed = _turn(question, {"substep": "main"})
    stayed_forecast = _forecast(question, {"substep": "main"})
    assert stayed_forecast.applies is True
    assert stayed_forecast.depends_on_model is False
    assert stayed_forecast.chosen is not None
    assert stayed_forecast.chosen.speech == "stay"
    assert stayed.count("Decision: stay.") == 1
    assert "If correct:" not in stayed
    assert "If not:" not in stayed
    assert "ask the goal again" in stayed
    _consistent(stayed_text)

    guess = "The river is green when the plants grow thick along the bank."
    pending_text, pending = _turn(guess, {"substep": "main"})
    pending_forecast = _forecast(guess, {"substep": "main"})
    assert pending_forecast.applies is True
    assert pending_forecast.depends_on_model is True
    assert pending.count("If correct:") == 1
    assert pending.count("If not:") == 1
    assert "Decision: close." not in pending
    assert "Decision: stay." not in pending
    speeches = {pending_forecast.if_correct.speech, pending_forecast.if_not.speech}
    assert speeches == {"advance", "stay"}
    _consistent(pending_text)
