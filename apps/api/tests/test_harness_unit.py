"""Harness checks that do not need a database."""

import uuid
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.harness import (
    claim_chat,
    claim_opens_session,
    expected_for_step,
    fixture_document,
    next_claim_generation,
    replaced_session_id,
    run_code_version,
)
from app.harness_download import render_download
from app.harness_checks import automatic_checks, graded_step, line_matches_key, place_key, stop_reason, stuck_after_turn
from app.harness_personas import BOUNDARY_PROBES, starter_children
from app.kc import loop_result_label, loop_turn_result
from app.models import ALL_BLOCK_TYPES
from app.token_usage import MODEL_TOKEN_PRICES, _model_cost


def test_gpt6_luna_is_unpriced() -> None:
    assert "gpt-6-luna" not in MODEL_TOKEN_PRICES
    assert _model_cost("gpt-6-luna", 1000, 0, 100) is None
    assert _model_cost("gpt-4.1-mini", 1_000_000, 0, 0) == "0.4"


def test_starter_set_includes_the_boundary_tester() -> None:
    children = starter_children()
    assert [child["name"] for child in children] == [f"AI_Child{number}" for number in range(1, 15)]
    by_name = {child["name"]: child for child in children}
    boundary = by_name["AI_Child12"]
    assert boundary["name"] == "AI_Child12"
    quiet = by_name["AI_Child13"]
    assert "plain statements" in quiet["description"]
    belief = by_name["AI_Child14"]
    assert "Holds one wrong belief:" in belief["description"]
    assert boundary["traits"]["boundary"] == 5
    assert quiet["traits"]["prior_knowledge"] == 5
    assert quiet["traits"]["curiosity"] == 1
    assert quiet["traits"]["wrong_pattern"] == 5
    assert quiet["traits"]["quit"] == 5
    assert quiet["child_profile"]["reading_level"] == "on_grade"
    assert belief["traits"]["prior_knowledge"] == 1
    assert belief["traits"]["wrong_pattern"] == 1
    assert belief["traits"]["tangent"] == 1
    assert "a price rise means everyone has more money" in belief["description"]
    assert "real attempt" in belief["description"]
    assert belief["child_profile"]["grade_band"] == "middle_school"
    listed = [child["name"] for child in children if not child.get("archived")]
    assert "AI_Child13" in listed
    assert "AI_Child14" in listed
    assert len(BOUNDARY_PROBES) >= 4
    assert all("address" not in line and "school" not in line for line in BOUNDARY_PROBES)


def test_fixture_course_has_every_block_type() -> None:
    document = fixture_document()
    blocks = document["units"][0]["components"][0]["blocks"]
    kinds = [block["type"] for block in blocks]
    assert set(kinds) == set(ALL_BLOCK_TYPES)
    assert len(kinds) == 11


def test_a_second_claim_keeps_the_session_and_closes_a_replaced_one() -> None:
    assert claim_opens_session(None) is True
    assert claim_opens_session("session-1") is False
    assert next_claim_generation(0) == 1
    assert next_claim_generation(1) == 2
    assert next_claim_generation("nope") == 1
    assert replaced_session_id(None, "session-2") is None
    assert replaced_session_id("session-1", "session-1") is None
    assert replaced_session_id("session-1", "session-2") == "session-1"


def test_claim_locks_one_queued_chat() -> None:
    """Each claim locks one queued chat so the next claim can take another row.

    The statement is LIMIT 1 FOR UPDATE SKIP LOCKED on queued chats only.
    """
    run = SimpleNamespace(id=uuid.uuid4(), status="running", plan={}, totals={}, updated_at=None)
    captured: list = []

    class RecordingSession:
        def get(self, model, key):
            return run

        def scalar(self, statement):
            captured.append(statement)
            return None

    assert claim_chat(RecordingSession(), run.id) is None
    locked = [
        statement
        for statement in captured
        if getattr(statement, "_for_update_arg", None) is not None
        and statement._for_update_arg.skip_locked
    ]
    assert len(locked) == 1
    claim = locked[0]
    assert claim._limit_clause.value == 1
    compiled = claim.compile(dialect=postgresql.dialect())
    sql = " ".join(str(compiled).split())
    assert "LIMIT %(param_1)s::INTEGER FOR UPDATE SKIP LOCKED" in sql
    assert compiled.params["param_1"] == 1
    assert compiled.params["status_1"] == "queued"
    assert "harness_chats.status = %(status_1)s" in sql


def test_stop_on_cap_and_luna_ceiling() -> None:
    assert (
        stop_reason(
            session_status="in_progress",
            intent="answer_part",
            turn_count=2,
            same_place_turns=1,
            priced_cents=40,
            cap_cents=40,
            luna_tokens=0,
            luna_ceiling=100_000,
            consecutive_errors=0,
            safety_flag="none",
            stop_on_safety=False,
        )
        == "cap"
    )
    assert (
        stop_reason(
            session_status="in_progress",
            intent="answer_part",
            turn_count=2,
            same_place_turns=1,
            priced_cents=0,
            cap_cents=40,
            luna_tokens=100_000,
            luna_ceiling=100_000,
            consecutive_errors=0,
            safety_flag="none",
            stop_on_safety=False,
        )
        == "luna_ceiling"
    )
    assert (
        stop_reason(
            session_status="completed",
            intent="answer_right",
            turn_count=3,
            same_place_turns=1,
            priced_cents=1,
            cap_cents=40,
            luna_tokens=0,
            luna_ceiling=100_000,
            consecutive_errors=0,
            safety_flag="none",
            stop_on_safety=False,
        )
        == "completed"
    )


def test_false_pass_and_prompt_trim_set() -> None:
    accepted = {"closed": "passed", "advanced": False, "stayed": False}
    wrong = {
        "intent": "answer_wrong",
        "child_text": "The river is green.",
        "expected": "The river is blue.",
        "tutor_reply": "Yes, that is right.",
        "prompt": "Ask one question. Do not give the answer.",
        "loop_result": accepted,
        "attempt_before": 0,
        "attempt_after": 1,
        "block_id": "blk",
        "block_before": "blk",
        "substep": "ask",
        "substep_before": "ask",
    }
    matched = {**wrong, "child_text": "The river is blue.", "prompt": ""}
    stayed = {**wrong, "child_text": "The river is blue.", "prompt": "", "loop_result": {"closed": "", "advanced": False, "stayed": True}}
    explain = {**wrong, "prompt": "", "substep": "explain_topic", "substep_before": "explain_topic", "expected": ""}
    revealed = {**wrong, "prompt": "", "loop_result": {"closed": "revealed", "advanced": False, "stayed": False}}
    guess_match = {**wrong, "prompt": "", "intent": "guess", "child_text": "The river is blue."}
    checks = automatic_checks(
        [wrong, matched, stayed, explain, revealed, guess_match],
        ended_how="completed",
        response_length="bite_sized",
    )
    assert checks["false_passes"] == [0]
    assert checks["false_fails"] == [2]
    assert checks["instructions"]["one_question"]["present"] == 1


def test_answer_key_matcher_grades_the_words_not_the_intent() -> None:
    """A paraphrase is a pass. A negation, or a miss that only shares words, is not."""
    assert line_matches_key("The river is green.", "The river is blue.") is False
    assert line_matches_key("The river is not blue.", "The river is blue.") is False
    assert line_matches_key("The river is blue.", "The river is blue.") is True
    assert line_matches_key("42", "42") is True
    assert line_matches_key("43", "42") is False

    goal = (
        "Explain the difference between anticipated and unanticipated inflation "
        "and why unanticipated inflation is generally more harmful."
    )
    paraphrase = (
        "When prices rise as expected, people can save money, but if prices surprise "
        "and go up, people can't plan."
    )
    assert line_matches_key(paraphrase, goal) is True
    assert line_matches_key("Expected inflation hurts more than a surprise.", goal) is False

    step = "Determine who benefits from the unexpected inflation."
    assert line_matches_key("The borrower benefits from the inflation.", step) is True

    solo = "The borrower benefits because the money paid back is worth less."
    assert line_matches_key("The person who borrowed the money benfits and pays back fewer treats.", solo) is True

    fact = "A menu cost is the expense a business pays to change its prices due to inflation."
    assert line_matches_key("cuz they have to change prices all teh time.", fact) is True
    menu_question = "Is menu cost like when stores have to change prices on stuff cause of inflation?"
    assert line_matches_key(menu_question, fact) is True

    wage = "The worker's real wage decreases because the raise is less than inflation."
    wage_paraphrase = "The worker's raise is less than inflation so they lose money and the boss wins."
    moves_up = "The worker's real wage moves up because the 3% raise still gives more money."
    more_than = "The worker's real wage decreases because the raise is more than inflation."
    assert line_matches_key(wage_paraphrase, wage) is True
    assert line_matches_key(moves_up, wage) is False
    assert line_matches_key(more_than, wage) is False

    opposite = "Inflation does not help all people the same."
    helps = "inflation helps all people"
    assert line_matches_key(helps, opposite) is False
    assert line_matches_key("Inflation hurts some people more than others.", opposite) is True
    shared = (
        "Menu cost is like when inflation helps all people the same, "
        "so restaurants don't need to change prices much."
    )
    assert line_matches_key(shared, fact) is False

    accepted = {"closed": "passed", "advanced": False, "stayed": False}
    stayed = {"closed": "", "advanced": False, "stayed": True}

    def turn(child: str, expected: str, loop: dict, intent: str, substep: str = "ask") -> dict:
        return {
            "intent": intent,
            "child_text": child,
            "expected": expected,
            "tutor_reply": "Next.",
            "prompt": "",
            "loop_result": loop,
            "attempt_before": 0,
            "attempt_after": 0,
            "block_id": "blk",
            "block_before": "blk",
            "substep": substep,
            "substep_before": substep,
        }

    explain = turn(paraphrase, goal, accepted, "answer_right", "explain_topic")
    summary = turn(paraphrase, goal, accepted, "answer_right", "summary_check")
    assert graded_step(explain) is False
    assert graded_step(summary) is False
    checks = automatic_checks(
        [
            turn(paraphrase, goal, accepted, "guess"),
            turn(menu_question, fact, stayed, "on_topic_question"),
            turn(moves_up, wage, stayed, "answer_right"),
            turn(shared, fact, stayed, "answer_wrong"),
            turn(more_than, wage, stayed, "answer_wrong"),
            explain,
            summary,
            turn(helps, opposite, accepted, "answer_right"),
        ],
        ended_how="completed",
        response_length="balanced",
    )
    assert checks["false_passes"] == [7]
    assert checks["false_fails"] == [1]










def test_stuck_waits_for_two_nudges_and_a_move_resets() -> None:
    assert stuck_after_turn(reason="stuck", same_place_turns=8, stuck_limit=8, pending_nudges=0, intent="answer_right") == ("", 2, 0)
    assert stuck_after_turn(reason="stuck", same_place_turns=9, stuck_limit=8, pending_nudges=2, intent="nudge") == ("", 1, 0)
    assert stuck_after_turn(reason="stuck", same_place_turns=10, stuck_limit=8, pending_nudges=1, stuck_answers=2, intent="nudge") == ("stuck", 0, 0)
    assert stuck_after_turn(reason="stuck", same_place_turns=9, stuck_limit=8, pending_nudges=2, stuck_answers=0, intent="script") == ("", 2, 1)
    assert stuck_after_turn(reason="stuck", same_place_turns=10, stuck_limit=8, pending_nudges=2, stuck_answers=1, intent="answer_right") == ("", 2, 2)
    assert stuck_after_turn(reason="", same_place_turns=1, stuck_limit=8, pending_nudges=2, stuck_answers=1) == ("", 0, 0)
    assert stuck_after_turn(reason="quit", same_place_turns=9, stuck_limit=8, pending_nudges=2, stuck_answers=1, intent="quit") == ("quit", 2, 1)
    assert stuck_after_turn(reason="turn_limit", same_place_turns=9, stuck_limit=8, pending_nudges=1, intent="nudge") == ("turn_limit", 1, 0)
    assert stuck_after_turn(reason="cap", same_place_turns=9, stuck_limit=8, pending_nudges=2, stuck_answers=1, intent="answer_right") == ("cap", 2, 1)
    assert (
        stop_reason(
            session_status="in_progress",
            intent="nudge",
            turn_count=9,
            same_place_turns=9,
            priced_cents=1,
            cap_cents=40,
            luna_tokens=0,
            luna_ceiling=100_000,
            consecutive_errors=0,
            safety_flag="none",
            stop_on_safety=False,
        )
        == "stuck"
    )




def test_loop_result_names_the_move_without_deciding_it() -> None:
    advanced = loop_turn_result(
        before_step=0,
        before_state={"substep": "faded_step", "block_attempts": 0},
        before_attempts=0,
        before_results=[],
        resolution=SimpleNamespace(
            next_block_state={"substep": "solo_solve", "block_attempts": 1},
            next_step=0,
            block_results=[],
            unit_complete=False,
            move_attempts=1,
            advance_block=False,
            passed=False,
        ),
    )
    assert advanced["advanced"] is True
    assert advanced["stayed"] is False
    assert advanced["closed"] == ""
    assert advanced["attempt_counted"] is True
    assert loop_result_label(advanced) == "advanced, try counted"
    closed = loop_turn_result(
        before_step=0,
        before_state={"substep": "main", "block_attempts": 1},
        before_attempts=2,
        before_results=[],
        resolution=SimpleNamespace(
            next_block_state={"substep": "main", "block_attempts": 0},
            next_step=1,
            block_results=[{"outcome": "revealed", "attempts": 2}],
            unit_complete=True,
            move_attempts=0,
            advance_block=True,
            passed=False,
        ),
    )
    assert closed["closed"] == "revealed"
    assert closed["advanced"] is False
    assert closed["ended_unit"] is True
    assert closed["attempt_counted"] is True
    assert "closed revealed" in loop_result_label(closed)


def test_answer_key_is_the_step_being_asked() -> None:
    data = {
        "goal": "Name the river.",
        "solo_expected_answer": "42",
        "expected_fact": "Interest rates rise.",
        "steps": [{"step_text": "Add the two sides."}],
        "faded_step_index": 0,
    }
    assert expected_for_step("worked_example", "faded_step", data) == "Add the two sides."
    assert expected_for_step("worked_example", "solo_solve", data) == "42"
    assert expected_for_step("retrieval_check", "recall", data) == "Interest rates rise."
    assert expected_for_step("explanation", "explain_topic", data) == ""
    assert expected_for_step("topic_goal", "main", data) == "Name the river."


def test_three_explanation_topics_are_not_one_stuck_span() -> None:
    assert place_key("e", "explain_topic", 0) != place_key("e", "explain_topic", 1)
    assert place_key("e", "explain_topic", 1) == place_key("e", "explain_topic", 1)




def test_run_is_stamped_with_the_deployed_commit(monkeypatch) -> None:
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_VERSION", raising=False)
    assert run_code_version() == "harness-1"
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abcdef123 extra")
    assert run_code_version() == "harness-1 abcdef123"


def test_download_keeps_turns_checks_scores_and_a_failed_call() -> None:
    text = render_download(
        {"id": "run-1", "status": "completed", "code_version": "harness-1 abcdef123"},
        [
            {
                "id": "chat-1",
                "status": "completed",
                "ended_how": "stuck",
                "child": {"name": "AI_Child1"},
                "tutor_model": "gpt-4.1",
                "child_model": "gpt-4.1-mini",
                "cost_usd": "0.02",
                "luna_tokens": 12,
                "turns": [
                    {
                        "seq": 1,
                        "intent": "answer_wrong",
                        "child_text": "The river is green.",
                        "child_prompt": "You are a test child.",
                        "tutor_prompt": "Ask one question.",
                        "child_tokens": {"input_tokens": 10, "output_tokens": 4},
                        "session_after": {
                            "block_id": "b1",
                            "block_type": "topic_goal",
                            "block_title": "Rivers",
                            "tutor_reply": "",
                            "error": "The tutor did not write a new reply.",
                            "loop_result": {"stayed": True, "advanced": False, "closed": ""},
                            "loop_decision": "stay",
                        },
                    },
                    {
                        "seq": 2,
                        "intent": "answer_right",
                        "child_text": "The river is blue.",
                        "child_prompt": "",
                        "tutor_prompt": "Ask one question.",
                        "child_tokens": {"input_tokens": 8, "output_tokens": 3},
                        "session_after": {
                            "block_id": "b2",
                            "block_type": "mcq",
                            "block_title": "Color",
                            "tutor_reply": "Yes.",
                            "loop_result": {"stayed": False, "advanced": True, "closed": "passed"},
                            "loop_decision": "advance",
                        },
                    },
                ],
                "evaluations": [
                    {"kind": "automatic", "checks": {"false_passes": [0]}, "scores": [], "error": ""},
                    {"kind": "judged", "checks": {}, "scores": [{"dimension": "teaching_quality", "score": 2}], "error": ""},
                ],
                "block_outcomes": [
                    {"title": "Rivers", "outcome": "passed"},
                    {"title": "Color", "outcome": "revealed"},
                    {"title": "Hook", "outcome": "engaged"},
                ],
                "llm_calls": [
                    {
                        "model": "gpt-4.1",
                        "system_prompt": "Say the opening.",
                        "kind": "speak",
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "cost_usd": "0.001",
                    },
                    {
                        "model": "gpt-4.1",
                        "system_prompt": "Ask one question.",
                        "kind": "answer",
                        "input_tokens": 120,
                        "output_tokens": 30,
                        "cost_usd": "0.002",
                    },
                    {
                        "model": "gpt-4.1",
                        "system_prompt": "Ask one question.",
                        "kind": "answer",
                        "input_tokens": 140,
                        "output_tokens": 10,
                        "cost_usd": "0.003",
                    },
                ],
            },
            {
                "id": "chat-2",
                "status": "completed",
                "ended_how": "completed",
                "child": {"name": "AI_Child2"},
                "tutor_model": "gpt-4.1-mini",
                "turns": [],
                "evaluations": [],
                "block_outcomes": [],
                "llm_calls": [],
            },
        ],
    )
    assert "Commit: harness-1 abcdef123" in text
    assert "AI_Child1" in text and "AI_Child2" in text
    assert "The river is green." in text
    assert "The tutor did not write a new reply." in text
    assert "Start of block: Topic / Goal — Rivers" in text
    assert "End of block: Topic / Goal — Rivers" in text
    assert "Start of block: Multiple Choice Question — Color" in text
    assert "The river is blue." in text
    assert "Tutor: Yes." in text
    assert '"stayed": false' in text
    assert '"stayed": true' not in text  # The failed turn had only the previous snapshot.
    assert "### Judge scores" not in text
    assert "false_passes" in text
    assert "Rivers: passed" in text
    assert "Color: revealed" in text
    assert "Hook: engaged" in text
    assert "You are a test child." in text
    assert "Say the opening." in text
    assert "Ask one question." in text
    assert "120 in, 30 out" in text
    assert "Cost: 0.002" in text
    assert "Cost: 0.02\n" in text
