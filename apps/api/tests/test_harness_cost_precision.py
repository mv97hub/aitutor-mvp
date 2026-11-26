"""Fractional-cent estimates must survive run roll-ups and admission decisions."""

from decimal import Decimal

import pytest

from app import harness
from app.database import SessionLocal
from app.models import HarnessChat, HarnessRun


@pytest.mark.parametrize(("last_cost", "reached"), [("0.00115", False), ("0.00116", True)])
def test_cap_uses_exact_sum_even_when_both_totals_round_to_one_cent(last_cost, reached):
    with SessionLocal() as db:
        run = HarnessRun(status="running", plan={"run_cap_cents": 1}, totals={"priced_cents": 0, "cost_usd": "0"})
        db.add(run)
        db.flush()
        costs = ["0.00221"] * 4 + [last_cost]
        db.add_all(HarnessChat(run_id=run.id, status="completed", cost_usd=cost) for cost in costs)
        fresh = HarnessChat(run_id=run.id, status="queued")
        db.add(fresh)
        db.flush()
        stored = dict(run.totals)
        exact = sum(map(Decimal, costs))
        result = harness.get_run(db, run.id)
        assert Decimal(result["totals"]["cost_usd"]) == exact
        assert result["totals"]["priced_cents"] == 1
        assert result["run_cap_reached"] is reached
        assert harness.get_chat(db, fresh.id)["run_cap_reached"] is reached
        assert run.totals == stored and not db.is_modified(run)
        if reached:
            assert harness.claim_chat(db, run.id) is None
            assert fresh.ended_how == "run_cap" and fresh.session_id is None
        harness._refresh_totals(db, run)
        assert Decimal(run.totals["cost_usd"]) == exact
        assert harness.get_chat(db, fresh.id)["run_cap_reached"] is reached


def test_historical_completed_run_exact_price_and_unpriced_luna_on_read():
    with SessionLocal() as db:
        run = HarnessRun(status="completed", totals={"priced_cents": 0, "cost_usd": None, "luna_tokens": 99})
        db.add(run)
        db.flush()
        luna = HarnessChat(run_id=run.id, status="completed", cost_usd=None, luna_tokens=99)
        db.add(luna)
        db.flush()
        assert harness.get_run(db, run.id)["totals"]["cost_usd"] is None
        paid = HarnessChat(run_id=run.id, status="completed", cost_usd="0.002176")
        db.add(paid)
        db.flush()
        totals = harness.get_run(db, run.id)["totals"]
        assert totals == {"chats": 2, "finished": 2, "priced_cents": 0, "cost_usd": "0.002176", "luna_tokens": 99}
        assert "Cost: 0.002176" in harness.download_run(db, run.id)
        assert run.totals["cost_usd"] is None and not db.is_modified(run)


def test_legacy_aggregate_without_chat_prices_keeps_its_only_cost_record():
    with SessionLocal() as db:
        run = HarnessRun(status="paused", plan={"run_cap_cents": 3}, totals={"priced_cents": 3})
        db.add(run)
        db.flush()
        db.add(HarnessChat(run_id=run.id, status="queued"))
        db.flush()
        result = harness.get_run(db, run.id)
        assert result["totals"]["cost_usd"] == "0.03" and result["run_cap_reached"]


def test_judge_usage_is_charged_on_save_and_public_counts_can_reconcile_old_prices():
    with SessionLocal() as db:
        run = HarnessRun(status="completed", plan={"run_cap_cents": 1})
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, status="completed", judge_model="gpt-4o-mini")
        db.add(chat)
        db.flush()
        counts = {"input_tokens": 50_000, "output_tokens": 5_000}
        detail = harness.save_evaluation(db, chat.id, {"usage": {**counts, "opaque_metadata": "private"}})
        assert Decimal(detail["cost_usd"]) == Decimal("0.0105")
        assert detail["run_cap_reached"]
        assert detail["evaluations"][0]["usage"] == counts
        assert Decimal(harness.get_run(db, run.id)["totals"]["cost_usd"]) == Decimal("0.0105")


@pytest.mark.parametrize(("input_tokens", "stop"), [(24_999, ""), (25_000, "cap")])
def test_chat_cap_uses_the_actual_fractional_cost(input_tokens, stop):
    with SessionLocal() as db:
        run = HarnessRun(status="running", plan={"chat_cap_cents": 1})
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, status="running", child_model="gpt-4.1-mini")
        db.add(chat)
        db.flush()
        result = harness.record_turn(db, chat.id, {
            "child_text": "I think so.", "intent": "answer_part", "child_tokens": {"input_tokens": input_tokens},
            "session_after": {"status": "in_progress"},
        })
        assert result["stop"] == stop
        assert Decimal(result["cost_usd"]) == Decimal(input_tokens) * Decimal("0.0000004")
