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
    assert checks["side"] == [{"turn": 0, "reply_delivered": True, "answered": None, "attempt_held": not charged}]
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
        for seq, child in ((2, "What does carbon dioxide mean?"), (3, "Carbon dioxide")):
            db.add(HarnessTurn(chat_id=chat.id, seq=seq, intent="word_meaning", child_text=child,
                               session_before={"expected": "carbon dioxide", "substep": "recall"},
                               session_after={"loop_result": {"stayed": True, "attempt_counted": False},
                                              "substep": "recall", "tutor_reply": "Let’s try this one again."}))
        original = {"version": "1", "turns": 3, "false_fails": [1, 2], "side": [{"turn": 0, "answered": True, "attempt_held": True}],
                    "misread": [0], "instruction_history": "original"}
        automatic = HarnessEvaluation(chat_id=chat.id, kind="automatic", checks=original)
        judged = HarnessEvaluation(chat_id=chat.id, kind="judged", tags=[{"tag": "ignored_question", "turn": 1}])
        db.add_all([automatic, judged])
        db.flush()
        detail = get_chat(db, chat.id)
        checks = next(row["checks"] for row in detail["evaluations"] if row["kind"] == "automatic")
        assert [row["turn"] for row in checks["side"]] == [1, 2]
        assert checks["misread"] == [] and checks["answers_despite_side_plan"] == [0]
        assert checks["false_fails"] == [2]
        assert checks["instruction_history"] == "original"
        assert detail["turns"][0]["intent"] == "on_topic_question"
        assert _chat_for_report(db, chat)["checks"] == checks
        section = download_chat(db, chat.id).split("### Automatic checks")[1].split("### Judge scores")[0]
        assert json.loads(section.strip()) == checks
        db.expire_all()
        assert automatic.checks == original and judged.tags == [{"tag": "ignored_question", "turn": 1}]


def test_progress_without_any_graded_attempt_does_not_prove_the_learner_answered():
    turn = dict(ANSWER_TURN, loop_result={"advanced": True, "attempt_counted": False, "closed": "unassessed"})
    checks = checks_for(turn)
    assert checks["answers_despite_side_plan"] == []
    assert checks["side"][0]["attempt_held"] is True
    assert checks["misread"] == []


@pytest.mark.parametrize("text", ["I need a hint about carbon dioxide.", "Help me understand carbon dioxide.",
                                  "I still don't understand carbon dioxide.", "Please explain carbon dioxide."])
def test_a_graded_hint_or_clarification_request_still_flags_the_tutor(text):
    turn = dict(ANSWER_TURN, child_text=text, expected="carbon dioxide")
    checks = checks_for(turn)
    assert checks["answers_despite_side_plan"] == []
    assert checks["misread"] == [0]


@pytest.mark.parametrize("text", ["I’m confused about carbon dioxide.", "I have a question about carbon dioxide.",
                                  "We talked about carbon dioxide in science.", "My goldfish is called Carbon Dioxide."])
def test_mentioning_the_key_does_not_demonstrate_an_answer(text):
    checks = checks_for(dict(ANSWER_TURN, child_text=text, expected="carbon dioxide"))
    assert checks["answers_despite_side_plan"] == []
    assert checks["side"] and checks["misread"] == [0]


@pytest.mark.parametrize("text", ["Carbon dioxide.", "My answer is carbon dioxide.", "I think it’s carbon dioxide."])
def test_a_direct_answer_is_supported_by_a_short_saved_key(text):
    checks = checks_for(dict(ANSWER_TURN, child_text=text, expected="carbon dioxide"))
    assert checks["answers_despite_side_plan"] == [0]
    assert checks["side"] == checks["misread"] == []


def test_an_explicit_free_clarification_quoting_the_key_is_not_a_rejected_correct_answer():
    turn = dict(ANSWER_TURN, child_text="What does carbon dioxide mean?", expected="carbon dioxide",
                loop_result={"attempt_counted": False, "stayed": True})
    checks = checks_for(turn)
    assert checks["side"][0]["attempt_held"] is True and checks["false_fails"] == []
    for answer in ("Carbon dioxide", "Is it carbon dioxide?"):
        assert checks_for(dict(turn, child_text=answer))["false_fails"] == [0]
    assert checks_for(dict(turn, loop_result={"stayed": True}))["false_fails"] == [0]


@pytest.mark.parametrize("text", ["How do I know? My answer is carbon dioxide.",
                                  "Can you explain? I think it’s carbon dioxide."])
def test_a_mixed_clarification_and_answer_keeps_its_grading_evidence(text):
    turn = dict(ANSWER_TURN, child_text=text, expected="carbon dioxide",
                loop_result={"attempt_counted": False, "stayed": True})
    assert checks_for(turn)["false_fails"] == [0]


@pytest.mark.parametrize("subject", ["base year", "current year", "CPI"])
def test_a_worked_quantity_must_be_the_result_requested_by_the_key(subject):
    turn = dict(ANSWER_TURN, child_text=f"The {subject} is 62.5%.")
    assert checks_for(turn)["answers_despite_side_plan"] == []


def test_delivered_reply_does_not_certify_that_the_side_question_was_answered():
    turn = dict(ANSWER_TURN, child_text="What does CPI mean?", tutor_reply="Look at the next example.",
                loop_result={"attempt_counted": False, "stayed": True})
    assert checks_for(turn)["side"] == [{"turn": 0, "answered": None, "reply_delivered": True, "attempt_held": True}]
    absent = checks_for(dict(turn, tutor_reply=""))["side"][0]
    assert absent["answered"] is False and absent["reply_delivered"] is False
