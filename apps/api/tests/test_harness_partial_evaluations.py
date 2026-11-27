"""Saved judge evidence must agree across the operator's three reporting paths."""

import pytest

from app.database import SessionLocal
from app.harness import download_chat, get_chat, run_report, save_evaluation
from app.harness_report import compare_runs, rollup, run_summary
from app.models import HarnessChat, HarnessEvaluation, HarnessRun


@pytest.fixture
def saved_chat():
    with SessionLocal() as db:
        run = HarnessRun(status="completed")
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, status="completed")
        db.add(chat)
        db.flush()
        yield db, run, chat


def test_realism_only_and_tutor_only_are_partial_without_polluting_tutor_means():
    score = {"dimension": "teaching_quality", "score": 5}
    chats = [
        {"child_realism": 4, "scores": []},  # Saved declarative CPI case.
        {"child_realism": 4, "scores": [{"dimension": "child_realism", "score": 4}]},
        {"child_realism": None, "scores": [score]},
        {"child_realism": 4, "scores": [score]},
        {"child_realism": 2, "scores": [score]},
        {"child_realism": None, "scores": []},
        {"judge_error": "Judge failed", "child_realism": 4, "scores": [score]},
    ]
    report = rollup(chats)
    assert report["usable_chats"] == 1
    assert report["partial_evaluations"] == 3
    assert report["low_realism_left_out"] == 1
    assert report["not_judged"] == 2
    assert [(row["chats"], row["mean_score"]) for row in report["by_child"]] == [(1, 5)]
    summary = run_summary(chats)["text"]
    assert "2 chats have child realism only" in summary
    assert "1 chat has tutor scores only" in summary
    assert "withheld" not in run_summary([chats[3]])["text"]


def test_tutor_averages_only_use_saved_tutor_grades_in_groups_grid_and_paired_comparisons():
    full = {"child_realism": 5, "scores": [
        {"dimension": "teaching_quality", "score": 3},
        {"dimension": "child_realism", "score": 5},
        {"dimension": "pacing", "score": None},
    ]}
    report = rollup([full])
    assert report["by_child"][0]["mean_score"] == report["grid"][0]["score"] == 3
    assert "Pacing: mean not judged" in run_summary([full])["text"]
    for other in (dict(full, child_realism=None), dict(full, child_realism=2),
                  dict(full, child_realism=6), dict(full, judge_error="Failed")):
        comparison = compare_runs([full], [other])
        assert comparison["mean_score_delta"] is None
        assert comparison["dimension_deltas"] == []


def test_saved_partial_scorecard_survives_and_all_views_select_the_same_evidence(saved_chat):
    db, run, chat = saved_chat

    # Real usage can append attempts. Keep every row but show one scorecard.
    save_evaluation(db, chat.id, {
        "error": "Earlier failed attempt", "child_realism": 5,
        "scores": [{"dimension": "pacing", "score": 5}],
    })
    failed = download_chat(db, chat.id).split("### Judge scores")[1].split("### Block outcomes")[0]
    assert "Earlier failed attempt" in failed and "pacing" not in failed
    save_evaluation(db, chat.id, {"child_realism": 4, "scores": []})
    detail = get_chat(db, chat.id)
    selected, = [row for row in detail["evaluations"] if row.get("selected_for_report")]
    assert selected["child_realism"] == 4
    assert "No tutor scores were saved" in selected["partial_note"]
    report = run_report(db, run.id)
    assert (report["usable_chats"], report["partial_evaluations"], report["not_judged"]) == (0, 1, 0)
    assert "1 chat has child realism only" in report["summary"]["text"]
    section = download_chat(db, chat.id).split("### Judge scores")[1].split("### Block outcomes")[0]
    assert "Child realism 4/5" in section and selected["partial_note"] in section
    assert "not judged" not in section

    for grade in (3, 5):
        save_evaluation(db, chat.id, {
            "child_realism": 4, "scores": [{"dimension": "teaching_quality", "score": grade}],
        })
    save_evaluation(db, chat.id, {"child_realism": 2, "scores": []})
    save_evaluation(db, chat.id, {"error": "Later failed attempt"})
    selected, = [row for row in get_chat(db, chat.id)["evaluations"] if row.get("selected_for_report")]
    assert selected["scores"][0]["score"] == 5
    report = run_report(db, run.id)
    assert (report["usable_chats"], report["partial_evaluations"]) == (1, 0)
    assert report["by_child"][0]["mean_score"] == 5
    assert "teaching_quality: 5" in download_chat(db, chat.id)

    # Older imports can have a bare score list instead of an items/usage object.
    db.add(HarnessEvaluation(chat_id=chat.id, kind="judged", child_realism=4,
                             scores=[{"dimension": "pacing", "score": 3}]))
    db.flush()
    assert run_report(db, run.id)["by_child"][0]["mean_score"] == 3
    assert "pacing: 3" in download_chat(db, chat.id)


def test_invalid_overall_realism_is_preserved_as_raw_evidence_and_excluded_from_the_report(saved_chat):
    db, run, chat = saved_chat
    save_evaluation(db, chat.id, {
        "child_realism": 6, "scores": [{"dimension": "teaching_quality", "score": 3}],
    })
    report = run_report(db, run.id)
    assert (report["usable_chats"], report["partial_evaluations"]) == (0, 1)
    selected, = [row for row in get_chat(db, chat.id)["evaluations"] if row.get("selected_for_report")]
    assert selected["child_realism"] == 6
    assert selected["reported_child_realism"] is None
    assert "No valid overall child realism score" in selected["partial_note"]
    markdown = download_chat(db, chat.id)
    assert selected["partial_note"] in markdown and "teaching_quality: 3" in markdown
    assert "6/5" not in markdown


def test_out_of_range_missing_and_malformed_grade_rows_stay_in_raw_evidence_only(saved_chat):
    db, run, chat = saved_chat
    invalid = [
        None, "legacy", {"dimension": "pacing", "score": 9}, {"dimension": "safety", "score": 3.5},
        {"dimension": "feedback", "score": None},
    ]
    save_evaluation(db, chat.id, {"child_realism": 4, "scores": invalid})
    selected, = [row for row in get_chat(db, chat.id)["evaluations"] if row.get("selected_for_report")]
    assert selected["scores"] == invalid
    assert selected["reported_scores"] == []
    markdown = download_chat(db, chat.id)
    assert selected["partial_note"] in markdown and "Child realism 4/5" in markdown
    assert "pacing: 9" not in markdown and "feedback: None" not in markdown

    grade = {"dimension": "teaching_quality", "score": 3, "quote": "Prices rise.", "turn": 1}
    save_evaluation(db, chat.id, {"child_realism": 4, "scores": [*invalid, grade]})
    selected, = [row for row in get_chat(db, chat.id)["evaluations"] if row.get("selected_for_report")]
    assert selected["reported_scores"] == [grade]
    markdown = download_chat(db, chat.id)
    assert "teaching_quality: 3. Turn 1. “Prices rise.”" in markdown
    assert "pacing: 9" not in markdown


def test_partial_matches_count_for_automatic_checks_but_do_not_pad_score_verdicts():
    partial = {"child_realism": 4, "scores": []}
    before = [dict(partial, seed=index) for index in (1, 2, 3)]
    after = [dict(partial, seed=index) for index in (1, 2, 3)]
    before[0]["scores"] = [{"dimension": "pacing", "score": 1}]
    after[0]["scores"] = [{"dimension": "pacing", "score": 5}]
    comparison = compare_runs(before, after)
    assert comparison["verdict"] == "no clear difference"
    assert (comparison["matched"], comparison["scored_pairs"], comparison["mean_score_delta"]) == (3, 1, 4)
    after[1]["checks"] = {"false_passes": [0]}
    assert compare_runs(before, after)["verdict"] == "worse"
