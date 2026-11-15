"""Harness checks that do not need a database."""

from fastapi import HTTPException

from app.harness import fixture_document, save_recommendations
from app.harness_checks import automatic_checks, stop_reason, stuck_after_turn
from app.harness_report import stuck_nudge_rows
from app.harness_personas import BOUNDARY_PROBES, starter_children
from app.harness_prompt_source import block_label_from_prompt, example_from_turn, prompt_builder_excerpts, prompt_sections, select_turns
from app.harness_report import compare_runs, findings, kept_run_ids, rollup, run_summary
from app.models import ALL_BLOCK_TYPES
from app.token_usage import MODEL_TOKEN_PRICES, _model_cost


def test_gpt6_luna_is_unpriced() -> None:
    assert "gpt-6-luna" not in MODEL_TOKEN_PRICES
    assert _model_cost("gpt-6-luna", 1000, 0, 100) is None
    assert _model_cost("gpt-4.1-mini", 1_000_000, 0, 0) == "0.4"


def test_starter_set_includes_the_boundary_tester() -> None:
    children = starter_children()
    assert [child["name"] for child in children] == [f"AI_Child{number}" for number in range(1, 13)]
    boundary = children[-1]
    assert boundary["name"] == "AI_Child12"
    assert boundary["traits"]["boundary"] == 5
    assert len(BOUNDARY_PROBES) >= 4
    assert all("address" not in line and "school" not in line for line in BOUNDARY_PROBES)


def test_fixture_course_has_every_block_type() -> None:
    document = fixture_document()
    blocks = document["units"][0]["components"][0]["blocks"]
    kinds = [block["type"] for block in blocks]
    assert set(kinds) == set(ALL_BLOCK_TYPES)
    assert len(kinds) == 11


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
    checks = automatic_checks(
        [
            {
                "intent": "answer_wrong",
                "tutor_reply": "Yes, that is right.",
                "prompt": "Ask one question. Do not give the answer.",
                "passed": True,
                "attempt_before": 0,
                "attempt_after": 1,
                "block_id": "blk",
                "block_before": "blk",
                "substep": "ask",
                "substep_before": "ask",
            }
        ],
        ended_how="completed",
        response_length="bite_sized",
    )
    assert checks["false_passes"] == [0]
    assert checks["instructions"]["one_question"]["present"] == 1
    kept = kept_run_ids(
        [
            {"baseline_run_id": "base", "run_ids": ["old", "base", "newest"]},
            {"baseline_run_id": "", "run_ids": ["only"]},
        ]
    )
    assert kept == {"base", "newest", "only"}


def test_small_score_gap_is_no_clear_difference() -> None:
    def chat(score: float, ended: str = "completed") -> dict:
        return {
            "persona_name": "AI_Child1",
            "component_id": "c",
            "component_title": "Rivers",
            "tutor_model": "gpt-4.1",
            "seed": 1,
            "iteration": 1,
            "ended_how": ended,
            "scores": [{"dimension": "teaching_quality", "score": score}],
            "checks": {},
            "block_types": ["topic_goal"],
            "tags": [],
        }

    report = rollup([chat(2), dict(chat(4, "stuck"), stuck_blocks=["Topic / Goal"])])
    assert report["usable_chats"] == 2
    found = findings(report)
    stuck = next(item for item in found if item["tag"] == "stuck")
    assert stuck["block_label"] == "Topic / Goal"
    assert "Topic / Goal" in stuck["title"]
    comparison = compare_runs([chat(3.1)], [chat(3.2)])
    assert comparison["verdict"] == "no clear difference"
    hard = compare_runs([chat(3)], [dict(chat(3), ended_how="stuck", checks={"stuck_spans": 1})])
    assert hard["verdict"] == "worse"
    assert hard["new_hard_stops"]


def test_prompt_builder_excerpts_name_the_section_and_function() -> None:
    rows = prompt_builder_excerpts()
    aside = next(row for row in rows if row["symbol"] == "_GOAL_START_ASIDE")
    assert aside["section"] == "This turn"
    assert aside["function"] == "_this_turn"
    assert "side remark" in aside["source"]
    assert any("side remark" in line for line in aside["literals"])
    teach = next(row for row in rows if row["symbol"] == "_how_to_teach")
    assert teach["section"] == "How to teach"
    assert teach["function"] == "_how_to_teach"
    ladder = next(row for row in rows if row["symbol"] == "_block_config_rules")
    assert any("nudge" in line for line in ladder["literals"])
    named = {
        "_GOAL_START_DEEPEN": "still on the explanation",
        "_GOAL_START_READY": "ready to go on",
        "_GOAL_START_NO_TURN": "it is their turn",
        "_GOAL_START_CAP": "two extra turns on this explanation",
        "_GOAL_EARLY_ANSWER": "answered during the explanation",
        "_EXPLANATION_CAP": "two extra turns on this topic",
    }
    for symbol, phrase in named.items():
        row = next(item for item in rows if item["symbol"] == symbol)
        assert row["section"] == "This turn"
        assert row["function"] == "_this_turn"
        assert any(phrase in line for line in row["literals"])


def test_example_turn_keeps_the_reply_and_the_turn_block() -> None:
    row = example_from_turn(
        "chat",
        {
            "seq": 3,
            "child_text": "What does govern mean?",
            "tutor_prompt": "This turn\nActive step: Block 2 of 6: Explanatory Walkthrough. The child will type.\nGoal start: explain the topic.\n",
            "session_after": {
                "tutor_reply": "The river kept its name.",
                "substep": "explain_topic",
                "block_id": "b2",
                "block_type": "explanation",
            },
        },
        block_title="How a river cuts rock",
    )
    assert row is not None
    assert row["tutor_reply"] == "The river kept its name."
    assert row["child_text"] == "What does govern mean?"
    assert row["block_label"] == "Explanatory Walkthrough"
    assert row["block_title"] == "How a river cuts rock"
    assert row["substep"] == "explain_topic"


def test_stored_prompt_sections_and_example_turns() -> None:
    prompt = (
        "Safety\nBe kind.\n\nThis turn\n"
        "Active step: Block 1 of 6: Topic / Goal. The child will type.\n"
        "Goal start: Explain what this topic is.\n\n"
        "How to teach\nWhen the learner is stuck, start with a nudge.\n"
    )
    sections = prompt_sections(prompt)
    assert "Explain what this topic is." in sections["This turn"]
    assert "nudge" in sections["How to teach"]
    assert block_label_from_prompt(prompt) == "Topic / Goal"
    turns = [{"seq": index + 1} for index in range(8)]
    chosen = select_turns(turns, {4, 7, 8})
    seqs = [turn["seq"] for turn in chosen]
    assert seqs[0] == 1
    assert 8 in seqs
    assert 4 in seqs or 5 in seqs


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


def test_stuck_finding_keeps_both_nudges_on_the_block() -> None:
    rows = stuck_nudge_rows(
        [
            {"intent": "answer_right", "turn": 8, "child_text": "earls", "tutor_reply": "Yes.", "block_id": "b1", "substep": "explain", "block_type": "Topic / Goal"},
            {"intent": "nudge", "turn": 9, "child_text": "What's next?", "tutor_reply": "Let's keep going.", "block_id": "b1", "substep": "explain", "block_type": "Topic / Goal"},
            {"intent": "nudge", "turn": 10, "child_text": "What should we do next?", "tutor_reply": "We are still here.", "block_id": "b1", "substep": "explain", "block_type": "Topic / Goal"},
        ]
    )
    assert [row["asked"] for row in rows] == ["What's next?", "What should we do next?"]
    assert rows[0]["answered"] == "Let's keep going."
    assert rows[1]["block_type"] == "Topic / Goal"
    assert rows[1]["block_id"] == "b1"
    assert rows[1]["substep"] == "explain"
    report = {
        "by_child": [{"name": "AI_Child1", "chats": 1, "false_passes": 0, "stuck": 1}],
        "instructions": [],
        "top_problems": [],
        "issue_blocks": {"false_pass": {}, "stuck": {"AI_Child1": ["Topic / Goal"]}, "instructions": {}},
        "stuck_nudges": [
            {**rows[0], "child": "AI_Child1"},
            {**rows[1], "child": "AI_Child1"},
        ],
    }
    stuck = next(item for item in findings(report) if item["tag"] == "stuck")
    assert stuck["block_label"] == "Topic / Goal"
    assert len(stuck["nudges"]) == 2
    assert stuck["nudges"][0]["asked"] == "What's next?"
    assert stuck["nudges"][1]["answered"] == "We are still here."


class _Saved:
    """Enough of a session for save_recommendations to store cards in memory."""

    def add(self, row: object) -> None:
        return None

    def flush(self) -> None:
        return None

    def execute(self, statement: object) -> None:
        return None


def _draft(body: dict) -> list[dict]:
    rejected = "A batch that only proposes additions is incomplete. Include a removal or a shorter wording."
    try:
        saved = save_recommendations(_Saved(), body)  # type: ignore[arg-type]
    except HTTPException as exc:
        assert exc.detail != rejected
        raise
    assert saved
    assert rejected not in str(saved)
    return saved


def test_additions_only_or_observations_only_batch_drafts() -> None:
    """A draft of additions or observations does not need a removal or shorter wording."""
    additions = _draft(
        {
            "cards": [
                {
                    "title": "Add a boredom line",
                    "kind": "add",
                    "prompt_direction": "longer",
                    "proposed": {"text": "Notice when the child is bored."},
                }
            ]
        }
    )
    observations = _draft(
        {
            "cards": [
                {
                    "title": "Turn 4: the tutor ignored the question",
                    "kind": "setting",
                    "prompt_direction": "same",
                    "proposed": {"text": "", "shorter": ""},
                    "evidence": {
                        "summary": "The child asked what govern means. The tutor moved on.",
                        "fault": "The tutor ignored the child's question.",
                    },
                }
            ]
        }
    )
    flagged = _draft(
        {
            "observations": True,
            "cards": [
                {
                    "title": "Turn 9: the step did not move",
                    "kind": "setting",
                    "prompt_direction": "same",
                    "proposed": {"text": "", "shorter": ""},
                }
            ],
        }
    )
    assert additions[0]["kind"] == "add"
    assert observations[0]["kind"] == "setting"
    assert observations[0]["proposed"] == {"text": "", "shorter": ""}
    assert "replacement" not in observations[0]["evidence"]
    assert flagged[0]["proposed"]["shorter"] == ""
    assert flagged[0]["proposed"]["text"] == ""


def _tone(name: str, natural: int, engagement: int, age: int, pacing: int, feedback: int, realism: int | None = 5) -> dict:
    scores = [
        {"dimension": "natural_conversation", "score": natural},
        {"dimension": "engagement", "score": engagement},
        {"dimension": "age_fit", "score": age},
        {"dimension": "pacing", "score": pacing},
        {"dimension": "feedback", "score": feedback},
    ]
    body: dict = {"scores": scores}
    if realism is not None:
        body["child_realism"] = realism
    body["persona_name"] = name
    return body


def test_run_summary_groups_checks_and_leaves_out_whats_next_on_an_open_goal() -> None:
    chats = [
        {
            "id": "wrong",
            "persona_name": "AI_Child1",
            "tutor_model": "gpt-4.1",
            "ended_how": "completed",
            "checks": {},
            "turns": [
                {
                    "intent": "on_topic_question",
                    "child_text": "Did steve jobs have a favorite animal?",
                    "tutor_reply": "I don't know a favorite animal.",
                    "block_type": "explanation",
                    "block_id": "b1",
                    "block_before": "b1",
                    "substep": "explain_topic",
                    "substep_before": "explain_topic",
                },
                {
                    "intent": "on_topic_question",
                    "child_text": "Wait, how did they sell the computers if they started in a garage?",
                    "tutor_reply": "Steve Jobs liked soccer and design.",
                    "block_type": "explanation",
                    "block_id": "b1",
                    "block_before": "b1",
                    "substep": "explain_topic",
                    "substep_before": "explain_topic",
                },
            ],
            **_tone("AI_Child1", 2, 2, 3, 4, 5),
        },
        {
            "id": "praised",
            "persona_name": "AI_Child3",
            "tutor_model": "gpt-4.1",
            "ended_how": "completed",
            "checks": {"false_passes": [], "false_fails": []},
            "turns": [
                {
                    "intent": "answer_right",
                    "child_text": "When the government borrows more money, interest rates go up, so a business holds off on a tractor.",
                    "tutor_reply": "Yes, that's the chain. Now put it in your own words: what happens to interest rates?",
                    "block_type": "topic_goal",
                    "block_id": "g",
                    "block_before": "g",
                    "substep": "main",
                    "substep_before": "main",
                    "passed": False,
                }
            ],
            **_tone("AI_Child3", 5, 4, 5, 5, 4),
        },
        {
            "id": "same",
            "persona_name": "AI_Child7",
            "tutor_model": "gpt-4.1",
            "ended_how": "completed",
            "checks": {},
            "turns": [
                {
                    "intent": "guess",
                    "child_text": "I am guessing.",
                    "tutor_reply": "Bad computers and no money are the two problems.",
                    "block_type": "mcq",
                    "block_id": "m",
                    "block_before": "m",
                    "substep": "choice",
                    "substep_before": "choice",
                },
                {
                    "intent": "guess",
                    "child_text": "Was one problem bad computers and the other like no money?",
                    "tutor_reply": "Bad computers and no money are the two problems.",
                    "block_type": "mcq",
                    "block_id": "m",
                    "block_before": "m",
                    "substep": "choice",
                    "substep_before": "choice",
                },
            ],
            **_tone("AI_Child7", 4, 5, 2, 2, 2),
        },
        {
            "id": "empty",
            "persona_name": "AI_Child1",
            "tutor_model": "gpt-4.1",
            "ended_how": "completed",
            "checks": {"empty_replies": [1], "false_passes": [], "false_fails": []},
            "turns": [
                {
                    "intent": "answer_right",
                    "child_text": "Blue.",
                    "tutor_reply": "The river is blue.",
                    "block_type": "worked_example",
                    "block_id": "w",
                    "block_before": "w",
                    "substep": "step",
                    "substep_before": "step",
                },
                {
                    "intent": "answer_right",
                    "child_text": "I said blue.",
                    "tutor_reply": "",
                    "error": "The tutor did not write a new reply.",
                    "block_type": "worked_example",
                    "block_id": "w",
                    "block_before": "w",
                    "substep": "step",
                    "substep_before": "step",
                },
            ],
        },
        {
            "id": "checks",
            "persona_name": "AI_Child1",
            "tutor_model": "gpt-4.1",
            "ended_how": "completed",
            "checks": {"false_passes": [0], "false_fails": [1]},
            "turns": [
                {
                    "intent": "answer_wrong",
                    "child_text": "The river is green.",
                    "tutor_reply": "Yes, that is right.",
                    "passed": True,
                    "block_type": "worked_example",
                    "block_id": "w2",
                    "block_before": "w2",
                    "substep": "step",
                    "substep_before": "step",
                },
                {
                    "intent": "answer_right",
                    "child_text": "The river is blue.",
                    "tutor_reply": "Not quite.",
                    "passed": False,
                    "block_type": "spot_the_flaw",
                    "block_id": "s",
                    "block_before": "s",
                    "substep": "main",
                    "substep_before": "main",
                },
            ],
        },
        {
            "id": "stuck",
            "persona_name": "AI_Child3",
            "tutor_model": "deepseek-flash",
            "ended_how": "stuck",
            "checks": {"stuck_spans": 1},
            "turns": [
                {
                    "intent": "answer_wrong",
                    "child_text": "I already said the chain about interest rates and the tractor.",
                    "tutor_reply": "Add the interest rates.",
                    "block_type": "topic_goal",
                    "block_id": "g2",
                    "block_before": "g2",
                    "substep": "main",
                    "substep_before": "main",
                    "passed": False,
                },
                {
                    "intent": "nudge",
                    "child_text": "What's next?",
                    "tutor_reply": "We are still on the goal.",
                    "block_type": "topic_goal",
                    "block_id": "g2",
                    "block_before": "g2",
                    "substep": "main",
                    "substep_before": "main",
                },
            ],
        },
        {
            "id": "open-goal",
            "persona_name": "AI_Child7",
            "tutor_model": "gpt-4.1",
            "ended_how": "completed",
            "checks": {"false_passes": [0]},
            "turns": [
                {
                    "intent": "nudge",
                    "child_text": "What's next?",
                    "tutor_reply": "Yes, that's the chain. What happens next?",
                    "passed": True,
                    "block_type": "topic_goal",
                    "block_id": "g3",
                    "block_before": "g3",
                    "substep": "main",
                    "substep_before": "main",
                }
            ],
        },
        {
            "id": "low",
            "persona_name": "AI_Child12",
            "tutor_model": "gpt-4.1",
            "ended_how": "completed",
            "child_realism": 2,
            "checks": {"false_passes": [0]},
            "turns": [
                {
                    "intent": "answer_wrong",
                    "child_text": "Jobs cause the cycle.",
                    "tutor_reply": "Yes, that is the whole story.",
                    "passed": True,
                    "block_type": "socratic",
                    "block_id": "so",
                    "block_before": "so",
                    "substep": "ask",
                    "substep_before": "ask",
                }
            ],
            "scores": [{"dimension": "natural_conversation", "score": 1}],
        },
    ]
    # _tone() also sets persona_name, so the explicit name above is overwritten by the spread
    # when **_tone comes last. The calls above put **_tone last, which is what we want.
    summary = run_summary(chats)
    groups = {(row["id"], row["block_type"]): row for row in summary["groups"]}
    assert summary["chats"] == 8
    assert summary["stuck"] == 1
    assert summary["tutor_models"] == ["deepseek-flash", "gpt-4.1"]
    assert groups[("wrong_line", "Explanatory Walkthrough")]["count"] == 1
    assert "garage" in groups[("wrong_line", "Explanatory Walkthrough")]["child"]
    assert "soccer" in groups[("wrong_line", "Explanatory Walkthrough")]["tutor"]
    assert groups[("praised_again", "Topic / Goal")]["count"] == 1
    assert "tractor" in groups[("praised_again", "Topic / Goal")]["child"]
    assert groups[("unchanged_reply", "Multiple Choice Question")]["count"] == 1
    assert groups[("unchanged_reply", "Worked Example + Faded Step")]["tutor"] == ""
    assert groups[("false_pass", "Worked Example + Faded Step")]["child"] == "The river is green."
    assert groups[("false_fail", "Spot the Flaw / Buggy Rule")]["count"] == 1
    assert groups[("false_pass", "Socratic Discussion")]["count"] == 1
    assert groups[("stuck", "Topic / Goal")]["child"] == "I already said the chain about interest rates and the tractor."
    assert "What's next?" not in summary["text"]
    assert "scoring fairness" not in summary["text"].lower()
    assert "getting stuck" not in summary["text"].lower()
    natural = summary["tone"][0]
    assert natural["dimension"] == "natural_conversation"
    assert natural["mean"] == 3.67
    assert [item["child"] for item in natural["lowest"]] == ["AI_Child1", "AI_Child7", "AI_Child3"]
    assert all(item["child"] != "AI_Child12" for row in summary["tone"] for item in row["lowest"])
    assert "Answered the wrong line — 1 chat — Explanatory Walkthrough" in summary["text"]
    assert "Tone" in summary["text"]
    assert summary["text"].startswith("Run: 8 chats,")


def test_per_dimension_delta_and_a_new_failure_beats_a_rising_mean() -> None:
    def chat(teaching: float, engagement: float, **extra: object) -> dict:
        persona = extra.pop("persona_name", "AI_Child1")
        seed = extra.pop("seed", 1)
        body = {
            "persona_name": persona,
            "component_id": "c",
            "component_title": "Rivers",
            "tutor_model": "gpt-4.1",
            "seed": seed,
            "iteration": 1,
            "ended_how": "completed",
            "scores": [
                {"dimension": "teaching_quality", "score": teaching},
                {"dimension": "engagement", "score": engagement},
            ],
            "checks": {},
            "block_types": ["topic_goal"],
            "tags": [],
        }
        body.update(extra)
        return body

    left = [chat(3, 4, seed=index, persona_name=f"AI_Child{index}") for index in (1, 3, 7)]
    right = [chat(4, 4.1, seed=index, persona_name=f"AI_Child{index}") for index in (1, 3, 7)]
    report = compare_runs(left, right)
    by_dimension = {row["dimension"]: row for row in report["dimension_deltas"]}
    assert by_dimension["teaching_quality"]["delta"] == 1.0
    assert by_dimension["teaching_quality"]["clear"] is True
    assert by_dimension["engagement"]["delta"] == 0.1
    assert by_dimension["engagement"]["clear"] is False
    assert report["verdict"] == "better"
    assert report["mean_score_delta"] is not None
    assert abs(report["mean_score_delta"]) >= 0.3

    raised = compare_runs(
        [chat(3, 3, seed=index, persona_name=f"AI_Child{index}") for index in (1, 3, 7)],
        [
            chat(4, 4, seed=index, persona_name=f"AI_Child{index}", checks={"false_passes": [0] if index == 1 else []})
            for index in (1, 3, 7)
        ],
    )
    assert raised["mean_score_delta"] is not None and raised["mean_score_delta"] > 0.3
    assert raised["verdict"] == "worse"
    assert raised["new_false_passes"]

    empty = compare_runs(
        [chat(3, 3, seed=index, persona_name=f"AI_Child{index}") for index in (1, 3, 7)],
        [
            chat(4, 4, seed=index, persona_name=f"AI_Child{index}", checks={"empty_replies": [1] if index == 1 else []})
            for index in (1, 3, 7)
        ],
    )
    assert empty["verdict"] == "worse"
    assert empty["new_empty_replies"]

    stuck = compare_runs(
        [chat(3, 3, seed=index, persona_name=f"AI_Child{index}") for index in (1, 3, 7)],
        [
            chat(4, 4, seed=index, persona_name=f"AI_Child{index}", ended_how="stuck" if index == 1 else "completed")
            for index in (1, 3, 7)
        ],
    )
    assert stuck["mean_score_delta"] is not None and stuck["mean_score_delta"] > 0
    assert stuck["verdict"] == "worse"

    quiet = compare_runs(
        [chat(2, 2, child_realism=1), chat(3, 3, seed=2, persona_name="AI_Child3")],
        [chat(5, 5, child_realism=1), chat(3, 3, seed=2, persona_name="AI_Child3")],
    )
    quiet_dims = {row["dimension"]: row for row in quiet["dimension_deltas"]}
    assert quiet_dims["teaching_quality"]["delta"] == 0.0
    assert quiet_dims["teaching_quality"]["clear"] is False
