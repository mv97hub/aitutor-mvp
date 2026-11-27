"""Agent view of a harness run.

The stored run, the background loop, and the stop rules are unchanged.
This module only reads them. A run that ended because a limit was hit is
reported as stopped, even when the stored row says completed.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.harness import _block_score, _run_cap_reached, _run_or_404
from app.models import HarnessChat, KcNode, KcSession

COST_STOPS = {"cap", "luna_ceiling", "run_cap"}
CLEAN_STOPS = {"completed", "quit"}
_STOP_RANK = (
    "run_cap",
    "cap",
    "luna_ceiling",
    "turn_limit",
    "stuck",
    "safety",
    "route_error",
    "scenario_not_reached",
    "cancelled",
    "quit",
    "completed",
)


def _decimal(value: str) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError):
        return Decimal(0)
    return number if number.is_finite() else Decimal(0)


def _trim_money(total: Decimal) -> str:
    text = format(total, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _reason(chat: dict) -> str:
    reason = str(chat.get("ended_how") or "").strip()
    if reason:
        return reason
    if chat.get("status") == "completed":
        return "completed"
    return ""


def job_status(run_status: str, chats: list[dict], *, run_cap_reached: bool = False) -> tuple[str, str]:
    """Status an agent polls, and why a terminal run stopped.

    queued, running, and paused are not done. finished means every child
    completed the component or quit. A turn limit or a cost limit is stopped,
    including when the stored run status is completed.
    """
    statuses = [str(chat.get("status") or "") for chat in chats]
    if any(status in {"queued", "running"} for status in statuses) or run_status in {"queued", "running"}:
        if run_status == "queued" and not any(status == "running" for status in statuses):
            return "queued", ""
        return "running", ""
    if run_status == "paused" or any(status == "paused" for status in statuses):
        return "paused", ""
    reasons = [_reason(chat) for chat in chats]
    cost = run_cap_reached or any(reason in COST_STOPS for reason in reasons)
    turn = any(reason == "turn_limit" for reason in reasons)
    if (
        run_status == "completed"
        and reasons
        and not cost
        and not turn
        and all(reason in CLEAN_STOPS for reason in reasons)
    ):
        return "finished", ""
    if cost:
        return "stopped", "cost_limit"
    if turn:
        return "stopped", "turn_limit"
    if run_status == "cancelled":
        return "stopped", "cancelled"
    other = next((reason for reason in reasons if reason not in CLEAN_STOPS), "")
    return "stopped", other or "stopped"


def block_verdict_label(row: dict) -> str:
    """Same block line the run download prints."""
    title = str(row.get("title") or "block").strip() or "block"
    outcome = str(row.get("outcome") or "").strip()
    line = f"{title}: {outcome}"
    stored = str(row.get("stored_outcome") or "").strip()
    if stored:
        line += f" (stored loop outcome: {stored})"
    if row.get("revealed") is True and "revealed" not in {stored, outcome}:
        line += " (answer revealed)"
    return line


def _combined_stop(reasons: list[str]) -> str:
    present = set(reasons)
    for reason in _STOP_RANK:
        if reason in present:
            return reason
    return next((reason for reason in reasons if reason), "")


def _fold_cost(costs: list[str | None]) -> str:
    priced = [cost for cost in costs if cost not in (None, "")]
    if not priced:
        return ""
    if len(priced) == 1 and len(costs) == 1:
        return str(priced[0])
    return _trim_money(sum((_decimal(cost) for cost in priced), Decimal(0)))


def fold_children(chats: list[dict]) -> list[dict]:
    """One row per child. Component chats fold into that row."""
    groups: dict[tuple[int, str], list[dict]] = {}
    for chat in chats:
        try:
            number = int(chat.get("number") or 0)
        except (TypeError, ValueError):
            number = 0
        name = str(chat.get("child") or "").strip() or "Test child"
        groups.setdefault((number, name), []).append(chat)
    rows = []
    for (number, name), group in sorted(groups.items(), key=lambda item: item[0]):
        many = len(group) > 1
        open_chat = any(str(chat.get("status") or "") in {"queued", "running", "paused"} for chat in group)
        labels = []
        outcomes = []
        for chat in group:
            component = str(chat.get("component") or "").strip()
            outcome = str(chat.get("outcome") or "unfinished")
            outcomes.append(f"{component}: {outcome}" if many and component else outcome)
            for verdict in chat.get("block_verdicts") or []:
                if not isinstance(verdict, dict):
                    continue
                label = block_verdict_label(verdict)
                if many and component:
                    label = f"{component} — {label}"
                labels.append(label)
        rows.append(
            {
                "child": name,
                "outcome": "; ".join(outcomes),
                "block_verdicts": "; ".join(labels),
                "stop_reason": "" if open_chat else _combined_stop([_reason(chat) for chat in group]),
                "cost": _fold_cost([chat.get("cost") for chat in group]),
                "_number": number,
            }
        )
    for row in rows:
        row.pop("_number", None)
    return rows


def _csv_cell(value: str) -> str:
    if any(mark in value for mark in ",\"\r\n"):
        return '"' + value.replace('"', '""') + '"'
    return value


def child_file(rows: list[dict]) -> str:
    """One CSV file. The header plus one row per child."""
    lines = ["child,outcome,block_verdicts,stop_reason,cost"]
    for row in rows:
        lines.append(
            ",".join(
                _csv_cell(str(row.get(key) or ""))
                for key in ("child", "outcome", "block_verdicts", "stop_reason", "cost")
            )
        )
    return "\n".join(lines) + "\n"


def present_job(run_status: str, chats: list[dict], *, run_cap_reached: bool = False) -> dict:
    status, stop_reason = job_status(run_status, chats, run_cap_reached=run_cap_reached)
    body = {
        "status": status,
        "stop_reason": stop_reason,
        "children": fold_children(chats),
    }
    if status in {"finished", "stopped"}:
        body["file"] = child_file(body["children"])
    return body


def _session_outcome(session: KcSession | None) -> str:
    if session is None or session.status != "completed":
        return "unfinished"
    verdict = str(session.verdict or "").strip()
    if verdict in {"known", "fragile", "unassessed"}:
        return verdict
    return "unassessed"


def _chat_fact(db: Session, chat: HarnessChat) -> dict:
    snapshot = chat.child_snapshot if isinstance(chat.child_snapshot, dict) else {}
    try:
        number = int(snapshot.get("number") or 0)
    except (TypeError, ValueError):
        number = 0
    node = db.get(KcNode, chat.component_id) if chat.component_id else None
    verdicts: list[dict] = []
    if chat.session_id is not None:
        _score, verdicts = _block_score(db, chat)
        session = db.get(KcSession, chat.session_id)
        outcome = _session_outcome(session)
    else:
        outcome = "unfinished"
    cost = None if chat.cost_usd in (None, "") else str(chat.cost_usd)
    return {
        "child": str(snapshot.get("name") or "").strip() or "Test child",
        "number": number,
        "component": node.title if node is not None else "",
        "outcome": outcome,
        "block_verdicts": verdicts,
        "stop_reason": str(chat.ended_how or ""),
        "ended_how": str(chat.ended_how or ""),
        "cost": cost,
        "status": chat.status,
    }


def agent_run_view(db: Session, run_id: uuid.UUID) -> dict:
    """Read a run for an agent. Does not claim a chat or start the loop."""
    run = _run_or_404(db, run_id)
    chats = db.scalars(
        select(HarnessChat).where(HarnessChat.run_id == run.id).order_by(HarnessChat.created_at, HarnessChat.id)
    ).all()
    body = present_job(
        run.status,
        [_chat_fact(db, chat) for chat in chats],
        run_cap_reached=_run_cap_reached(db, run),
    )
    return {"id": str(run.id), **body}
