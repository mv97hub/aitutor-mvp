"""Tutor token counts reported by the model provider."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import KcMessage, KcSession, Student, TutorTokenUsage


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
    row = TutorTokenUsage(
        student_id=session.student_id,
        session_id=session.id,
        course_id=session.goal_id,
        message_id=linked.id if linked is not None else None,
        kind=kind,
        model=(model or "").strip(),
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


def usage_report(
    db: Session,
    *,
    student_id: uuid.UUID | None = None,
    start: date | None = None,
    end: date | None = None,
    all_time: bool = False,
) -> dict:
    if student_id is not None and db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="That child was not found.")
    start, end = _day_bounds(start, end, all_time=all_time)
    day = func.date(func.timezone("UTC", TutorTokenUsage.created_at))
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
    if student_id is not None:
        totals_stmt = totals_stmt.where(TutorTokenUsage.student_id == student_id)
        child_stmt = child_stmt.where(TutorTokenUsage.student_id == student_id)
        day_stmt = day_stmt.where(TutorTokenUsage.student_id == student_id)
    totals_stmt = _apply_window(totals_stmt, start, end)
    child_stmt = _apply_window(child_stmt, start, end)
    day_stmt = _apply_window(day_stmt, start, end)
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
    return {
        "all_time": all_time,
        "start": start.isoformat() if start is not None else None,
        "end": end.isoformat() if end is not None else None,
        "totals": {
            "input_tokens": int(totals[0] or 0),
            "output_tokens": int(totals[1] or 0),
            "cached_tokens": int(totals[2] or 0),
            "total_tokens": int(totals[3] or 0),
        },
        "by_child": children,
        "by_day": days,
    }
