"""Offline replays from the 26 November harness through prompt assembly and requirement scoring."""

import pytest

from app.block_score import score_supported_turn
from app.kc_loop import forecast_this_turn
from app.models import default_kc_tutor_config
from tests.test_kc_prompt import _node, _section, _text

CPI = {
    "id": "retrieval-check-1",
    "type": "retrieval_check",
    "data": {
        "recall_prompt": "What is the formula for calculating the inflation rate using the CPI?",
        "expected_fact": "[(CPI in current year - CPI in previous year) / CPI in previous year] × 100",
        "elaborative_why_prompt": "Why do economists use the CPI to calculate inflation instead of just looking at the price of one good?",
        "expected_why_rationale": "The basket reflects changes in the prices of many goods.",
    },
}
IDENTITY = {
    "id": "social-emotional-guided-cases",
    "type": "case_study",
    "data": {
        "invariant_principle": "Commitment without exploration is foreclosure.",
        "transfer_prompt": "Later, Nia compares several careers and makes a considered choice. What status would fit that occupational decision? Would this settle her identity in every domain?",
        "transfer_expected": "Achievement fits commitment following exploration. It describes the occupational decision at that time, not permanent completion of every aspect of identity.",
    },
}
CPI_ANSWERS = [
    "Is it (new CPI − old CPI) ÷ old CPI × 100?",
    "Is it the change in CPI divided by the old CPI, times 100? I want to make sure I get it right.",
    "Is it the new CPI minus the old CPI, divided by the old CPI, then times 100?",
    "This year’s CPI minus last year’s CPI, divided by last year’s CPI, times 100?",
    "Is it CPI chnge divded by old CPI × 100?",
    "Is it current CPI over the prior CPI, subtract one, then multiply by 100?",
    "Is it the change divided by the starting index, expressed as a percentage?",
]
IDENTITY_ANSWER = "Would that be identity achievement, and could she still be unsure about other parts of who she is?"


def _replay(block, step, answer, passed, *, rubric=(), stored=()):
    prior = block["data"].get("recall_prompt") or block["data"]["transfer_prompt"]
    common = dict(
        blocks=[block],
        step=0,
        active_block_state={"substep": step},
        block_results=[],
        answer=answer,
        cfg=default_kc_tutor_config(),
        goal=None,
        stored_rubric=list(stored),
        move_attempts=0,
        hint_tier="nudge",
        reveals=0,
        enrichment_turns=0,
        prior_tutor=prior,
    )
    forecast = forecast_this_turn(**common)
    result = score_supported_turn(
        **common,
        decision="advance" if passed else "stay",
        substep_passed=passed,
        block_complete=False,
        rubric_met=list(rubric),
        matched_wrong="",
        last_misconception="",
    )
    text = _text(
        node=_node(blocks=[block], misconceptions=[]),
        opening=False,
        attempts=0,
        last_answer=answer,
        last_messages=f"assistant: {prior} | user: {answer}",
        active_block_state={"substep": step},
        fragment=False,
        help_requested=False,
        rubric_met=list(stored),
    )
    reqs = {row["key"]: row for row in result.next_block_state["requirements"]}
    return text, forecast, result, reqs


@pytest.mark.parametrize("answer", CPI_ANSWERS + ["The change in CPI divided by the old CPI, times 100."])
def test_complete_recall_gets_one_independent_attempt(answer):
    text, forecast, result, reqs = _replay(CPI, "recall", answer, True)
    assert forecast.if_correct.next_substep == result.next_block_state["substep"] == "elaborate_why"
    assert (reqs["recall"]["observation"], reqs["recall"]["attempts"]) == ("independent", 1)
    assert reqs["elaborate_why"]["observation"] == "open"
    assert "This typed line is unscored help" not in text
    assert "Do not score this message" not in text
    assert "The child has asked for help." not in text
    instructions = _section(text, "This turn").splitlines()
    assert any(line.startswith("If correct: advance.") for line in instructions)
    repeats = [line for line in instructions if "repeat the active question" in line.lower()]
    assert all(line.startswith("If not: stay.") for line in repeats)


@pytest.mark.parametrize("answer", [
    "Is it new CPI minus old CPI?",
    "New CPI minus old CPI.",
    "[(CPI in current year - CPI in previous year) / CPI in current year] × 100.",
    "Is it [(CPI in current year - CPI in previous year) / CPI in current year] × 100?",
])
def test_incomplete_or_wrong_formula_spends_one_attempt(answer):
    text, forecast, result, reqs = _replay(
        CPI, "recall", answer, False, rubric=["other:recall"], stored=["retrieval-check-1:recall"]
    )
    assert forecast.if_not.next_substep == result.next_block_state["substep"] == "recall"
    assert result.move_attempts == 1
    assert (reqs["recall"]["observation"], reqs["recall"]["attempts"]) == ("insufficient", 1)
    assert "This typed line is unscored help" not in text
    assert "missing part" in _section(text, "This turn").lower()


@pytest.mark.parametrize("answer", [
    "What does CPI mean?", "Can I have a hint?", "Is it possible to get a hint about CPI?",
    "Is CPI published every month?", "Would it be possible to explain why CPI changes?",
    "Is it true that CPI is published every month?", "Is it the CPI formula you want me to give?",
])
@pytest.mark.parametrize("passed", [False, True])
def test_genuine_questions_keep_the_recall_open_even_if_the_grader_passes(answer, passed):
    rubric = ["retrieval-check-1:recall"] if passed else []
    text, forecast, result, reqs = _replay(CPI, "recall", answer, passed, rubric=rubric)
    assert forecast.depends_on_model is False
    assert result.next_block_state["substep"] == "recall"
    assert result.move_attempts == 0
    assert (reqs["recall"]["observation"], reqs["recall"]["attempts"]) == ("open", 0)
    assert "This typed line is unscored help" in text


def test_transfer_answer_and_follow_up_use_the_current_transfer_requirement():
    text, forecast, result, reqs = _replay(
        IDENTITY, "transfer", IDENTITY_ANSWER, False, rubric=["social-emotional-guided-cases:transfer"],
    )
    assert forecast.if_correct.next_substep == result.next_block_state["substep"] == "summary_check"
    assert (reqs["transfer"]["observation"], reqs["transfer"]["attempts"]) == ("independent", 1)
    assert "Do not score this message" not in text


@pytest.mark.parametrize("answer", [
    "It sleeps all day and wakes up at night, right?",
    "It sleeps all day and wakes up at night?",
    "Is it a creature that is awake at night?",
])
def test_graded_paraphrase_can_use_entirely_different_words(answer):
    block = {
        "id": "recall",
        "type": "retrieval_check",
        "data": {
            "recall_prompt": "What does a nocturnal animal do?",
            "expected_fact": "Active after sunset.",
            "elaborative_why_prompt": "Why might that be useful?",
        },
    }
    text, forecast, result, reqs = _replay(block, "recall", answer, True)
    assert "This typed line is unscored help" not in text
    assert forecast.if_correct.next_substep == result.next_block_state["substep"] == "elaborate_why"
    assert (reqs["recall"]["observation"], reqs["recall"]["attempts"]) == ("independent", 1)


def test_verbatim_answer_can_stand_before_a_separate_follow_up():
    answer = CPI["data"]["expected_fact"] + ". Why do we use CPI?"
    text, forecast, result, reqs = _replay(CPI, "recall", answer, False)
    assert result.next_block_state["substep"] == "elaborate_why"
    assert reqs["recall"]["observation"] == "independent"
    assert "This typed line is unscored help" not in text


def test_a_short_proposed_symbol_can_be_graded_against_a_spelled_out_fact():
    block = {
        "id": "recall",
        "type": "retrieval_check",
        "data": {
            "recall_prompt": "Which gas do plants absorb?",
            "expected_fact": "Carbon dioxide",
            "elaborative_why_prompt": "How do plants use it?",
        },
    }
    text, forecast, result, reqs = _replay(block, "recall", "Is it CO2?", True)
    assert forecast.if_correct.next_substep == result.next_block_state["substep"] == "elaborate_why"
    assert reqs["recall"]["observation"] == "independent"
    assert "This typed line is unscored help" not in text

@pytest.mark.parametrize("answer", [
    "Can you explain what active means?",
    "Is it possible to have some help with the word active?",
    "Is it true that all wolves are active?",
])
@pytest.mark.parametrize("passed", [True, False])
def test_fact_background_questions_are_unscored_even_with_key_words(answer, passed):
    block = {
        "id": "recall", "type": "retrieval_check",
        "data": {"recall_prompt": "What does nocturnal mean?", "expected_fact": "Active after sunset.",
                 "elaborative_why_prompt": "Why might that help?"},
    }
    text, _, result, reqs = _replay(block, "recall", answer, passed)
    assert "This typed line is unscored help" in text
    assert result.next_block_state["substep"] == "recall"
    assert (reqs["recall"]["observation"], reqs["recall"]["attempts"]) == ("open", 0)
