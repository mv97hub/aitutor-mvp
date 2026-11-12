"""Tutor token counts reported by the model provider."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import KcMessage, KcSession, Student, TutorTokenUsage, effective_child_profile


def _count(value: object) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _day_bounds(start: date | None, end: date | None, *, all_time: bool) -> tuple[date | None, date | None]:
    if all_time:
        return None, None
    today = datetime.now(timezone.utc).date()
    if start is None and end is None:
        return today - timedelta(days=29), today
    if start is None and end is not None:
        start = end - timedelta(days=29)
    if end is None and start is not None:
        end = today
    if start is not None and end is not None and start > end:
        start, end = end, start
    return start, end


def _apply_window(stmt, start: date | None, end: date | None):
    if start is not None:
        start_at = datetime.combine(start, time.min, tzinfo=timezone.utc)
        stmt = stmt.where(TutorTokenUsage.created_at >= start_at)
    if end is not None:
        end_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        stmt = stmt.where(TutorTokenUsage.created_at < end_at)
    return stmt


def _totals(row) -> dict:
    return {
        "input_tokens": int(row.input_tokens or 0),
        "output_tokens": int(row.output_tokens or 0),
        "cached_tokens": int(row.cached_tokens or 0),
        "total_tokens": int(row.total_tokens or 0),
    }


def record_token_usage(
    db: Session,
    session: KcSession,
    *,
    kind: str,
    model: str,
    input_tokens: object,
    output_tokens: object,
    cached_tokens: object,
    message_id: uuid.UUID | None = None,
) -> TutorTokenUsage:
    if kind not in {"speak", "answer"}:
        raise HTTPException(status_code=422, detail="kind must be speak or answer.")
    linked = None
    if message_id is not None:
        linked = db.get(KcMessage, message_id)
        if linked is None or linked.session_id != session.id:
            raise HTTPException(status_code=400, detail="That message is not part of this chat.")
    incoming = _count(input_tokens)
    outgoing = _count(output_tokens)
    cached = _count(cached_tokens)
    stored_model = (model or "").strip()
    if not stored_model:
        student = db.get(Student, session.student_id)
        stored_model = effective_child_profile(student)["tutor_model"]
    row = TutorTokenUsage(
        student_id=session.student_id,
        session_id=session.id,
        course_id=session.goal_id,
        message_id=linked.id if linked is not None else None,
        kind=kind,
        model=stored_model,
        input_tokens=incoming,
        output_tokens=outgoing,
        cached_tokens=cached,
        total_tokens=incoming + outgoing,
    )
    db.add(row)
    db.flush()
    return row


def usage_out(row: TutorTokenUsage) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "student_id": row.student_id,
        "session_id": row.session_id,
        "course_id": row.course_id,
        "message_id": row.message_id,
        "kind": row.kind,
        "model": row.model,
        **_totals(row),
    }


def session_token_usage(db: Session, session_id: uuid.UUID) -> dict:
    rows = db.scalars(
        select(TutorTokenUsage)
        .where(TutorTokenUsage.session_id == session_id)
        .order_by(TutorTokenUsage.created_at, TutorTokenUsage.id)
    ).all()
    turns = [usage_out(row) for row in rows]
    total = {
        "input_tokens": sum(item["input_tokens"] for item in turns),
        "output_tokens": sum(item["output_tokens"] for item in turns),
        "cached_tokens": sum(item["cached_tokens"] for item in turns),
        "total_tokens": sum(item["total_tokens"] for item in turns),
    }
    return {"total": total, "turns": turns}


# USD per 1,000,000 tokens: (input, cached input, output).
# Used only by this report. Rates are the provider's published standard prices,
# checked 2026-11-12. OpenAI models use the short-context rate on
# https://developers.openai.com/api/docs/pricing. This report has no per-call
# context length, so gpt-6.1-sol stays on that short-context rate.
# DeepSeek Flash is called through OpenRouter. Both stored ids use the price
# OpenRouter publishes for ~deepseek/deepseek-flash-latest
# (https://openrouter.ai/api/v1/models). A stored model with no row here still
# appears, with tokens and a blank cost.
_MILLION = Decimal("1000000")
_USD_QUANTUM = Decimal("0.00000001")
MODEL_TOKEN_PRICES: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.075"), Decimal("0.60")),
    "gpt-4o": (Decimal("2.50"), Decimal("1.25"), Decimal("10")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("0.10"), Decimal("1.60")),
    "gpt-4.1": (Decimal("2"), Decimal("0.50"), Decimal("8")),
    "gpt-6.1-sol": (Decimal("2"), Decimal("0.10"), Decimal("10")),
    "~deepseek/deepseek-flash-latest": (Decimal("0.022"), Decimal("0.004"), Decimal("0.40")),
    "deepseek/deepseek-flash-latest": (Decimal("0.022"), Decimal("0.004"), Decimal("0.40")),
}


def _clean_model(model: str | None) -> str | None:
    cleaned = (model or "").strip()
    return cleaned or None


def _money(amount: Decimal) -> str:
    quantized = amount.quantize(_USD_QUANTUM, rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _model_cost(model: str, uncached_input: int, billed_cached: int, output_tokens: int) -> str | None:
    rates = MODEL_TOKEN_PRICES.get(model)
    if rates is None:
        return None
    input_rate, cached_rate, output_rate = rates
    amount = (
        Decimal(uncached_input) * input_rate
        + Decimal(billed_cached) * cached_rate
        + Decimal(output_tokens) * output_rate
    ) / _MILLION
    return _money(amount)


def _page_cost(rows: list[dict]) -> tuple[str | None, list[str]]:
    unpriced = [row["model"] for row in rows if row["cost_usd"] is None]
    priced = [Decimal(row["cost_usd"]) for row in rows if row["cost_usd"] is not None]
    if not priced:
        return (None, unpriced) if unpriced else ("0", [])
    return _money(sum(priced, Decimal(0))), unpriced


def _scope(stmt, student_id: uuid.UUID | None, start: date | None, end: date | None, model: str | None):
    if student_id is not None:
        stmt = stmt.where(TutorTokenUsage.student_id == student_id)
    stmt = _apply_window(stmt, start, end)
    if model is not None:
        stmt = stmt.where(TutorTokenUsage.model == model)
    return stmt


def usage_report(
    db: Session,
    *,
    student_id: uuid.UUID | None = None,
    start: date | None = None,
    end: date | None = None,
    all_time: bool = False,
    model: str | None = None,
) -> dict:
    if student_id is not None and db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="That child was not found.")
    chosen = _clean_model(model)
    start, end = _day_bounds(start, end, all_time=all_time)
    day = func.date(func.timezone("UTC", TutorTokenUsage.created_at))
    billed_cached = func.least(TutorTokenUsage.cached_tokens, TutorTokenUsage.input_tokens)
    uncached_input = TutorTokenUsage.input_tokens - billed_cached
    totals_stmt = select(
        func.coalesce(func.sum(TutorTokenUsage.input_tokens), 0),
        func.coalesce(func.sum(TutorTokenUsage.output_tokens), 0),
        func.coalesce(func.sum(TutorTokenUsage.cached_tokens), 0),
        func.coalesce(func.sum(TutorTokenUsage.total_tokens), 0),
    )
    child_stmt = (
        select(
            TutorTokenUsage.student_id,
            Student.display_name,
            func.coalesce(func.sum(TutorTokenUsage.input_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.output_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.cached_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.total_tokens), 0),
            func.count(TutorTokenUsage.id),
        )
        .join(Student, Student.id == TutorTokenUsage.student_id)
        .group_by(TutorTokenUsage.student_id, Student.display_name)
        .order_by(func.sum(TutorTokenUsage.total_tokens).desc(), Student.display_name)
    )
    day_stmt = (
        select(
            day,
            func.coalesce(func.sum(TutorTokenUsage.input_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.output_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.cached_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.total_tokens), 0),
        )
        .group_by(day)
        .order_by(day)
    )
    model_stmt = (
        select(
            TutorTokenUsage.model,
            func.coalesce(func.sum(TutorTokenUsage.input_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.output_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.cached_tokens), 0),
            func.coalesce(func.sum(TutorTokenUsage.total_tokens), 0),
            func.count(TutorTokenUsage.id),
            func.coalesce(func.sum(uncached_input), 0),
            func.coalesce(func.sum(billed_cached), 0),
        )
        .group_by(TutorTokenUsage.model)
    )
    totals_stmt = _scope(totals_stmt, student_id, start, end, chosen)
    child_stmt = _scope(child_stmt, student_id, start, end, chosen)
    day_stmt = _scope(day_stmt, student_id, start, end, chosen)
    model_stmt = _scope(model_stmt, student_id, start, end, None)
    totals = db.execute(totals_stmt).one()
    children = [
        {
            "student_id": row[0],
            "display_name": row[1],
            "input_tokens": int(row[2] or 0),
            "output_tokens": int(row[3] or 0),
            "cached_tokens": int(row[4] or 0),
            "total_tokens": int(row[5] or 0),
            "calls": int(row[6] or 0),
        }
        for row in db.execute(child_stmt)
    ]
    days = [
        {
            "day": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
            "input_tokens": int(row[1] or 0),
            "output_tokens": int(row[2] or 0),
            "cached_tokens": int(row[3] or 0),
            "total_tokens": int(row[4] or 0),
        }
        for row in db.execute(day_stmt)
    ]
    by_model = [
        {
            "model": row[0],
            "input_tokens": int(row[1] or 0),
            "output_tokens": int(row[2] or 0),
            "cached_tokens": int(row[3] or 0),
            "total_tokens": int(row[4] or 0),
            "calls": int(row[5] or 0),
            "cost_usd": _model_cost(row[0], int(row[6] or 0), int(row[7] or 0), int(row[2] or 0)),
        }
        for row in db.execute(model_stmt)
    ]
    by_model.sort(key=lambda row: (-row["total_tokens"], row["model"]))
    priced_rows = by_model
    if chosen is not None:
        priced_rows = [row for row in by_model if row["model"] == chosen]
    cost_usd, unpriced_models = _page_cost(priced_rows)
    return {
        "all_time": all_time,
        "start": start.isoformat() if start is not None else None,
        "end": end.isoformat() if end is not None else None,
        "model": chosen,
        "totals": {
            "input_tokens": int(totals[0] or 0),
            "output_tokens": int(totals[1] or 0),
            "cached_tokens": int(totals[2] or 0),
            "total_tokens": int(totals[3] or 0),
        },
        "cost_usd": cost_usd,
        "unpriced_models": unpriced_models,
        "by_child": children,
        "by_day": days,
        "by_model": by_model,
    }
