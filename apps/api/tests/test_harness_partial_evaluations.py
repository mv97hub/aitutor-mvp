"""Saved judge evidence must agree across the operator's three reporting paths."""

from app.database import SessionLocal
from app.harness import download_chat, get_chat, run_report, save_evaluation
from app.harness_report import rollup, run_summary
from app.models import HarnessChat, HarnessRun


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


def test_saved_partial_scorecard_survives_and_all_views_select_the_same_evidence():
    with SessionLocal() as db:
        run = HarnessRun(status="completed")
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, status="completed")
        db.add(chat)
        db.flush()

        # Real usage can append attempts. Keep every row but show one scorecard.
        save_evaluation(db, chat.id, {"error": "Earlier failed attempt"})
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
