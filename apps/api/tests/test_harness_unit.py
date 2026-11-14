"""Harness checks that do not need a database."""

from app.harness import fixture_document
from app.harness_checks import automatic_checks, stop_reason
from app.harness_personas import BOUNDARY_PROBES, starter_children
from app.harness_prompt_source import block_label_from_prompt, prompt_builder_excerpts, prompt_sections, select_turns
from app.harness_report import compare_runs, findings, kept_run_ids, rollup
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
