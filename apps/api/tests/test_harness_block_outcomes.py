"""Read mixed stored outcomes through the same paths as the harness screens."""

from app.database import SessionLocal
from app.harness import download_run, get_chat, run_report
from app.models import HarnessChat, HarnessRun, KcGoal, KcNode, KcSession, Student


def test_stored_block_outcomes_reach_chat_download_and_run_report() -> None:
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
            scoring_version=2,
            score=60,
            block_results=[
                {"title": "Recall", "verdict": "known", "outcome": "passed"},
                {"title": "Practice", "verdict": "fragile", "outcome": "fragile"},
                {"title": "Read", "outcome": "unassessed"},
                {"title": "Retry", "verdict": "fragile"},
                {"title": "Legacy reveal", "outcome": "revealed"},
                {"title": "Legacy engagement", "outcome": "engaged"},
                {"block_type": "mcq", "outcome": "passed"},
                {"title": "Future value", "outcome": "new-outcome"},
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
            ("mcq", "passed"),
            ("Future value", "unknown"),
            ("Missing value", "unknown"),
        ]
        detail = get_chat(db, chat.id)
        assert detail["component_score"] == 60
        assert [(row["title"], row["outcome"]) for row in detail["block_outcomes"]] == expected

        markdown = download_run(db, run.id)
        assert markdown.split("### Block outcomes\n\n")[1].splitlines() == [
            f"{title}: {outcome}" for title, outcome in expected
        ]
        scores = run_report(db, run.id)["summary"]["block_scores"]
        assert len(scores) == 1
        assert scores[0]["outcomes"] == ", ".join(f"{title} ({outcome})" for title, outcome in expected)
