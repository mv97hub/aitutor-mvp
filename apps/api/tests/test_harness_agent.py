"""Agent run status and the one-row-per-child file. No database and no model call."""

from app.harness_agent import block_verdict_label, child_file, present_job


def _chat(**overrides):
    body = {
        "status": "completed",
        "ended_how": "completed",
        "child": "AI_Child1",
        "number": 1,
        "component": "Prices",
        "outcome": "known",
        "block_verdicts": [{"title": "Recall", "outcome": "passed"}],
        "cost": "0.10",
    }
    body.update(overrides)
    return body


def test_a_completed_course_is_finished_and_one_row_per_child():
    body = present_job(
        "completed",
        [
            _chat(),
            _chat(
                child="AI_Child2",
                number=2,
                component="Taxes",
                outcome="fragile",
                block_verdicts=[{"title": "Quiz", "outcome": "fragile"}],
                cost="0.02",
            ),
        ],
    )
    assert body["status"] == "finished"
    assert body["stop_reason"] == ""
    assert [row["child"] for row in body["children"]] == ["AI_Child1", "AI_Child2"]
    assert body["file"].splitlines() == [
        "child,outcome,block_verdicts,stop_reason,cost",
        "AI_Child1,known,Recall: passed,completed,0.10",
        "AI_Child2,fragile,Quiz: fragile,completed,0.02",
    ]


def test_a_turn_limit_says_stopped_not_finished():
    body = present_job("completed", [_chat(status="completed", ended_how="turn_limit", outcome="unfinished")])
    assert body["status"] == "stopped"
    assert body["status"] != "finished"
    assert body["status"] != "completed"
    assert body["stop_reason"] == "turn_limit"
    assert body["children"] == [
        {
            "child": "AI_Child1",
            "outcome": "unfinished",
            "block_verdicts": "Recall: passed",
            "stop_reason": "turn_limit",
            "cost": "0.10",
        }
    ]
    assert "turn_limit" in body["file"]
    assert body["file"].count("\n") == 2


def test_a_chat_cap_or_run_cap_says_stopped_for_cost():
    cap = present_job("completed", [_chat(ended_how="cap", outcome="unfinished")])
    assert cap["status"] == "stopped"
    assert cap["stop_reason"] == "cost_limit"
    assert cap["children"][0]["stop_reason"] == "cap"
    reached = present_job("completed", [_chat()], run_cap_reached=True)
    assert reached["status"] == "stopped"
    assert reached["stop_reason"] == "cost_limit"
    assert reached["children"][0]["stop_reason"] == "completed"
    run_cap = present_job("completed", [_chat(status="cancelled", ended_how="run_cap", outcome="unfinished")])
    assert run_cap["status"] == "stopped"
    assert run_cap["stop_reason"] == "cost_limit"
    assert run_cap["children"][0]["stop_reason"] == "run_cap"


def test_two_components_for_one_child_stay_one_row():
    body = present_job(
        "completed",
        [
            _chat(component="Prices", outcome="known", cost="0.10"),
            _chat(
                component="Taxes",
                outcome="unfinished",
                ended_how="turn_limit",
                block_verdicts=[{"title": "Quiz, retake", "outcome": "revealed", "revealed": True}],
                cost="0.05",
            ),
        ],
    )
    assert body["status"] == "stopped"
    assert body["stop_reason"] == "turn_limit"
    assert len(body["children"]) == 1
    row = body["children"][0]
    assert row["child"] == "AI_Child1"
    assert row["outcome"] == "Prices: known; Taxes: unfinished"
    assert row["block_verdicts"] == "Prices — Recall: passed; Taxes — Quiz, retake: revealed"
    assert row["stop_reason"] == "turn_limit"
    assert row["cost"] == "0.15"
    assert body["file"].splitlines()[1].startswith('"AI_Child1"') or "Quiz, retake" in body["file"]
    assert body["file"].splitlines() == [
        "child,outcome,block_verdicts,stop_reason,cost",
        'AI_Child1,Prices: known; Taxes: unfinished,"Prices — Recall: passed; Taxes — Quiz, retake: revealed",turn_limit,0.15',
    ]


def test_a_running_or_paused_run_has_no_result_file():
    running = present_job("running", [_chat(status="running", ended_how="", outcome="unfinished", cost=None)])
    assert running["status"] == "running"
    assert "file" not in running
    assert running["children"][0]["stop_reason"] == ""
    assert running["children"][0]["cost"] == ""
    paused = present_job("paused", [_chat(status="paused", ended_how="")])
    assert paused["status"] == "paused"
    assert "file" not in paused
    queued = present_job("queued", [_chat(status="queued", ended_how="", outcome="unfinished")])
    assert queued["status"] == "queued"
    assert "file" not in queued


def test_block_verdict_label_matches_the_download_line():
    assert block_verdict_label({"title": "Recall", "outcome": "passed"}) == "Recall: passed"
    assert (
        block_verdict_label({"title": "Saved reveal", "outcome": "fragile", "revealed": True})
        == "Saved reveal: fragile (answer revealed)"
    )
