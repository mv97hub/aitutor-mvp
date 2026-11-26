"""Fractional-cent estimates must survive run roll-ups and admission decisions."""

from decimal import Decimal

import pytest

from app import harness
from app.database import SessionLocal
from app.models import HarnessChat, HarnessEvaluation, HarnessRun


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


@pytest.mark.parametrize("invalid", ["bad", -5, True, 0.5, 10**100])
def test_invalid_judge_usage_cannot_reduce_cost_or_break_historical_reads(invalid):
    with SessionLocal() as db:
        run = HarnessRun(status="completed", plan={"run_cap_cents": 1})
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, status="completed", judge_model="gpt-4o-mini")
        db.add(chat)
        db.flush()
        # Old JSON could include arbitrary values and string representations of counts.
        usage = {"input_tokens": invalid, "output_tokens": "5000", "opaque_metadata": "private"}
        db.add(HarnessEvaluation(chat_id=chat.id, kind="judged", judge_model=chat.judge_model,
                                 scores={"usage": usage}))
        db.flush()
        detail = harness.save_evaluation(db, chat.id, {"usage": usage})
        assert [e["usage"] for e in detail["evaluations"]] == [{"output_tokens": 5000}] * 2
        assert Decimal(detail["cost_usd"]) == Decimal("0.006")
        assert not detail["run_cap_reached"]


def test_resumed_run_preserves_aggregate_only_spend_across_new_costs():
    with SessionLocal() as db:
        run = HarnessRun(status="running", plan={"run_cap_cents": 4}, totals={"priced_cents": 3})
        db.add(run)
        db.flush()
        historical = HarnessChat(run_id=run.id, status="completed")
        active = HarnessChat(run_id=run.id, status="running", child_model="gpt-4.1-mini")
        db.add_all([historical, active])
        db.flush()

        def add_turn(input_tokens):
            return harness.record_turn(db, active.id, {
                "child_text": "Maybe.", "intent": "answer_part", "child_tokens": {"input_tokens": input_tokens},
                "session_after": {"status": "in_progress"},
            })

        assert add_turn(5_000)["stop"] == ""  # $0.002
        assert Decimal(harness.get_run(db, run.id)["totals"]["cost_usd"]) == Decimal("0.032")
        assert add_turn(20_000)["stop"] == "run_cap"  # another $0.008
        assert Decimal(run.totals["cost_usd"]) == Decimal("0.040")


@pytest.mark.parametrize(("stored_cents", "expected"), [(2, "0.012"), (5, "0.042")])
def test_known_prices_are_not_counted_twice_in_a_partial_legacy_ledger(stored_cents, expected):
    with SessionLocal() as db:
        run = HarnessRun(status="paused", totals={"priced_cents": stored_cents})
        db.add(run)
        db.flush()
        # The old roll-up rounded both $0.006 chats up to $0.01 apiece.
        db.add_all(HarnessChat(run_id=run.id, status="completed", cost_usd=cost)
                   for cost in ("0.006", "0.006", None))
        db.flush()
        assert harness.get_run(db, run.id)["totals"]["cost_usd"] == expected
        assert run.totals == {"priced_cents": stored_cents}


def test_luna_usage_at_the_storage_limit_stays_unpriced_and_stops_the_chat():
    with SessionLocal() as db:
        run = HarnessRun(status="running", plan={"luna_token_ceiling": 2**40})
        db.add(run)
        db.flush()
        chat = HarnessChat(run_id=run.id, status="running", child_model="gpt-6-luna", judge_model="gpt-6-luna")
        db.add(chat)
        db.flush()
        raw = {"input_tokens": 2**31 - 1, "output_tokens": 2**31 - 1}
        judged = harness.save_evaluation(db, chat.id, {"usage": raw})
        assert judged["cost_usd"] is None and judged["luna_tokens"] == 2**31 - 1
        assert judged["evaluations"][0]["usage"] == raw
        result = harness.record_turn(db, chat.id, {
            "child_text": "Maybe.", "intent": "answer_part", "child_tokens": {"input_tokens": 1},
            "session_after": {"status": "in_progress"},
        })
        assert result["stop"] == "luna_ceiling" and result["cost_usd"] is None
        assert run.totals["luna_tokens"] == 2**31 - 1 and run.totals["priced_cents"] == 0
