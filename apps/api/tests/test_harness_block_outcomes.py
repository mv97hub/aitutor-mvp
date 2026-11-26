"""Read mixed stored outcomes through the same paths as the harness screens."""

import pytest

from app.database import SessionLocal
from app.harness import download_run, get_chat, run_report
from app.models import HarnessChat, HarnessRun, KcGoal, KcNode, KcSession, Student


@pytest.mark.parametrize("version", [1, 2])
def test_stored_block_outcomes_reach_chat_download_and_run_report(version: int) -> None:
    with SessionLocal() as db:
        student = Student(slug="harness-outcomes-test", display_name="Test learner")
        goal = KcGoal(code="harness-outcomes-test", title="Test course")
        component = KcNode(code="harness-outcomes-test", title="Test component")
        run = HarnessRun(status="completed")
        db.add_all([student, goal, component, run])
        db.flush()
        session = KcSession(
            student_id=student.id,
            goal_id=goal.id,
            kc_id=component.id,
            scoring_version=version,
            score=60,
            block_results=[
                {"title": "Recall", "verdict": "known", "outcome": "passed"},
                {"title": "Practice", "verdict": "fragile", "outcome": "fragile"},
                {"title": "Read", "outcome": "unassessed"},
                {"title": "Retry", "verdict": "fragile"},
                {"title": "Legacy reveal", "outcome": "revealed"},
                {"title": "Legacy engagement", "outcome": "engaged"},
                {"block_type": "mcq", "outcome": "passed"},
                {"title": "Assisted recall", "outcome": "passed", "requirements": [
                    {"role": "assessed", "observation": "assisted", "attempts": 1},
                ]},
                {"title": "Independent recall", "outcome": "passed", "requirements": [
                    {"role": "assessed", "observation": "independent", "attempts": 1},
                ]},
                {"title": "Observed reveal", "outcome": "revealed", "requirements": [
                    {"role": "assessed", "observation": "assisted", "attempts": 1},
                ]},
                {"title": "Saved reveal", "verdict": "fragile", "outcome": "fragile", "revealed": True},
                {"title": "Reading", "outcome": "engaged", "requirements": [
                    {"role": "participation", "observation": "participated"},
                ]},
                {"title": "Missing loop result", "requirements": [
                    {"role": "assessed", "observation": "independent", "attempts": 1},
                ]},
                {"title": "Future value", "outcome": "new-outcome"},
                {"title": "Future verdict", "verdict": "future", "outcome": "passed"},
                {"title": "Missing value"},
            ],
        )
        db.add(session)
        db.flush()
        chat = HarnessChat(run_id=run.id, session_id=session.id, status="completed")
        db.add(chat)
        db.flush()

        expected = [
            ("Recall", "passed"),
            ("Practice", "fragile"),
            ("Read", "unassessed"),
            ("Retry", "fragile"),
            ("Legacy reveal", "revealed"),
            ("Legacy engagement", "engaged"),
            ("mcq", "passed" if version == 1 else "unassessed"),
            ("Assisted recall", "passed" if version == 1 else "fragile"),
            ("Independent recall", "passed"),
            ("Observed reveal", "revealed" if version == 1 else "fragile"),
            ("Saved reveal", "fragile"),
            ("Reading", "engaged" if version == 1 else "unassessed"),
            ("Missing loop result", "unknown" if version == 1 else "passed"),
            ("Future value", "unknown"),
            ("Future verdict", "unknown"),
            ("Missing value", "unknown"),
        ]
        detail = get_chat(db, chat.id)
        assert detail["component_score"] == 60
        assert [(row["title"], row["outcome"]) for row in detail["block_outcomes"]] == expected
        if version == 2:
            saved = {row["title"]: row.get("stored_outcome") for row in detail["block_outcomes"]}
            assert saved["mcq"] == saved["Assisted recall"] == "passed"
            assert saved["Observed reveal"] == "revealed"

        markdown = download_run(db, run.id)
        evidence = {}
        if version == 2:
            evidence = {"mcq": "passed", "Assisted recall": "passed", "Observed reveal": "revealed", "Reading": "engaged"}
        lines = []
        for title, outcome in expected:
            line = f"{title}: {outcome}"
            if title in evidence:
                line += f" (stored loop outcome: {evidence[title]})"
            if title == "Saved reveal":
                line += " (answer revealed)"
            lines.append(line)
        assert markdown.split("### Block outcomes\n\n")[1].splitlines() == lines
        scores = run_report(db, run.id)["summary"]["block_scores"]
        assert len(scores) == 1
        annotations = {"Saved reveal": ", answer revealed"}
        if version == 2:
            annotations.update({"Observed reveal": ", answer revealed", "Reading": ", participated"})
        assert scores[0]["outcomes"] == ", ".join(
            f"{title} ({outcome}{annotations.get(title, '')})" for title, outcome in expected
        )
