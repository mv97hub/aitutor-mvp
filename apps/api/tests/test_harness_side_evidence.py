"""The simulation plan, delivered child answer, and charged attempt are separate facts."""

import json

import pytest

from app.database import SessionLocal
from app.harness import _chat_for_report, download_chat, get_chat
from app.harness_checks import automatic_checks
from app.models import HarnessChat, HarnessEvaluation, HarnessRun, HarnessTurn


# AI_Child12, CPI, chat decf5052, turn 13. The per-substep counter reset on advance.
CPI_ANSWER = "The inflation rate is 62.5%, because the basket costs 62.5% more than in the base year."
CPI_KEY = "Calculate the inflation rate: [(CPI current year - CPI base year) / CPI base year] × 100 = [(162.5 - 100) / 100] × 100 = 62.5%."
ANSWER_TURN = {
    "intent": "on_topic_question", "child_text": CPI_ANSWER, "expected": CPI_KEY,
    "tutor_reply": "Exactly right — you took the percent change from the base year.",
    "block_before": "cpi", "block_id": "cpi", "substep_before": "faded_step", "substep": "solo_solve",
    "attempt_before": 0, "attempt_after": 0,
    "loop_result": {"advanced": True, "attempt_counted": True, "stayed": False, "closed": ""},
}


def checks_for(turn):
    return automatic_checks([turn], ended_how="completed", response_length="balanced")


def test_correct_answer_despite_planned_question_isnt_a_side_or_a_misread():
    checks = checks_for(ANSWER_TURN)
    assert checks["side"] == []
    assert checks["misread"] == []
    assert checks["false_passes"] == []


def test_a_tentative_correct_answer_can_also_differ_from_the_plan():
    turn = dict(ANSWER_TURN, expected="carbon dioxide", child_text="Is it carbon dioxide?")
    assert checks_for(turn)["side"] == []


@pytest.mark.parametrize("question", ["How do I find the inflation rate?", "What does carbon dioxide mean?",
                                      "Can you explain carbon dioxide", "My notes say carbon dioxide. What does that mean?"])
@pytest.mark.parametrize("charged", [True, False])
def test_genuine_question_retains_the_explicit_charge_even_when_counters_disagree(question, charged):
    turn = dict(ANSWER_TURN, child_text=question, expected="carbon dioxide", attempt_after=int(not charged),
                loop_result={"advanced": False, "stayed": True, "attempt_counted": charged})
    checks = checks_for(turn)
    assert checks["side"] == [{"turn": 0, "answered": True, "attempt_held": not charged}]
    assert checks["misread"] == ([0] if charged else [])


def test_legacy_counter_reset_does_not_assert_that_an_attempt_was_held():
    turn = dict(ANSWER_TURN, child_text="What does an index mean?", loop_result={}, attempt_before=2)
    assert checks_for(turn)["side"][0]["attempt_held"] is None
    # An older counter still provides evidence on an unchanged substep.
    turn.update(substep="faded_step", attempt_before=0, attempt_after=1)
    assert checks_for(turn)["side"][0]["attempt_held"] is False


def test_historical_views_use_the_saved_turn_evidence_and_preserve_the_original_review():
    with SessionLocal() as db:
        run = HarnessRun(status="completed")
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, status="completed", ended_how="completed")
        db.add(chat)
        db.flush()
        db.add(HarnessTurn(chat_id=chat.id, seq=1, intent=ANSWER_TURN["intent"], child_text=CPI_ANSWER,
                           session_before={"expected": CPI_KEY, "substep": "faded_step", "move_attempts": 0},
                           session_after={"loop_result": ANSWER_TURN["loop_result"], "substep": "solo_solve",
                                          "move_attempts": 0, "tutor_reply": ANSWER_TURN["tutor_reply"]}))
        original = {"version": "1", "turns": 1, "side": [{"turn": 0, "answered": True, "attempt_held": True}],
                    "misread": [0], "instruction_history": "original"}
        automatic = HarnessEvaluation(chat_id=chat.id, kind="automatic", checks=original)
        judged = HarnessEvaluation(chat_id=chat.id, kind="judged", tags=[{"tag": "ignored_question", "turn": 1}])
        db.add_all([automatic, judged]); db.flush()
        detail = get_chat(db, chat.id)
        checks = next(row["checks"] for row in detail["evaluations"] if row["kind"] == "automatic")
        assert checks["side"] == checks["misread"] == []
        assert checks["instruction_history"] == "original"
        assert detail["turns"][0]["intent"] == "on_topic_question"
        assert _chat_for_report(db, chat)["checks"] == checks
        section = download_chat(db, chat.id).split("### Automatic checks")[1].split("### Judge scores")[0]
        assert json.loads(section.strip()) == checks
        db.expire_all()
        assert automatic.checks == original and judged.tags == [{"tag": "ignored_question", "turn": 1}]
