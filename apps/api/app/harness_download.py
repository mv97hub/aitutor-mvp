"""One markdown file for a harness chat or a whole run.

The file is meant to be opened later. It keeps every stored turn, including a
blank or failed tutor call, plus the checks, scores, and the model record.
"""

from __future__ import annotations

import json

from app.harness_report import block_label


def _text(value: object) -> str:
    return str(value or "").strip()


def _dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: object) -> list:
    return list(value) if isinstance(value, list) else []


def _block_key(after: dict) -> str:
    block_id = _text(after.get("block_id"))
    if block_id:
        return f"id:{block_id}"
    block_type = _text(after.get("block_type"))
    if block_type:
        return f"type:{block_type}"
    return ""


def _mark_label(after: dict) -> str:
    kind = block_label(after.get("block_type"))
    title = _text(after.get("block_title"))
    if kind and title:
        return f"{kind} — {title}"
    return kind or "Block"


def block_marks(turns: list[dict]) -> list[dict]:
    """First turn of a block, and the last turn before the next block."""
    marks: list[dict] = []
    previous = ""
    for index, turn in enumerate(turns):
        after = _dict(turn.get("session_after"))
        key = _block_key(after)
        if not key:
            continue
        nxt = turns[index + 1] if index + 1 < len(turns) else None
        next_key = _block_key(_dict(nxt.get("session_after"))) if isinstance(nxt, dict) else ""
        if key != previous:
            marks.append({"seq": turn.get("seq"), "edge": "start", "label": _mark_label(after)})
        if nxt is not None and next_key and next_key != key:
            marks.append({"seq": turn.get("seq"), "edge": "end", "label": _mark_label(after)})
        previous = key
    return marks


def _pair_calls(turns: list[dict], calls: list[dict]) -> tuple[list[dict], list[dict | None]]:
    """Opening tutor calls come before the child turns. Later calls follow the turns."""
    if not calls:
        return [], [None] * len(turns)
    if len(calls) > len(turns):
        opening = calls[: len(calls) - len(turns)]
        matched = calls[len(calls) - len(turns) :]
    else:
        opening = []
        matched = calls
    paired: list[dict | None] = []
    for index in range(len(turns)):
        paired.append(matched[index] if index < len(matched) else None)
    return opening, paired


def _tokens(row: dict) -> str:
    incoming = row.get("input_tokens")
    outgoing = row.get("output_tokens")
    if incoming is None and outgoing is None:
        return "not stored"
    return f"{int(incoming or 0)} in, {int(outgoing or 0)} out"


def _cost(value: object) -> str:
    text = _text(value)
    return text if text else "blank"


def _llm_lines(call: dict | None, *, child_prompt: str, child_tokens: dict, fallback_model: str) -> list[str]:
    model = _text((call or {}).get("model")) or fallback_model or "unknown"
    system_prompt = _text((call or {}).get("system_prompt"))
    lines = [
        "LLM record:",
        f"- Model: {model}",
        f"- System prompt: {system_prompt or 'not stored'}",
        f"- Child prompt: {child_prompt or 'not stored'}",
        f"- Tutor tokens: {_tokens(call or {})}",
        f"- Child tokens: {_tokens(child_tokens)}",
        f"- Cost: {_cost((call or {}).get('cost_usd'))}",
    ]
    return lines


def _turn_lines(turn: dict, marks: list[dict], call: dict | None, tutor_model: str) -> list[str]:
    seq = turn.get("seq")
    after = _dict(turn.get("session_after"))
    reply = _text(after.get("tutor_reply"))
    error = _text(after.get("error"))
    lines = [f"### Turn {seq}", ""]
    for mark in marks:
        if mark.get("seq") != seq:
            continue
        edge = "Start of block" if mark.get("edge") == "start" else "End of block"
        lines.append(f"{edge}: {mark.get('label')}")
    lines.append(f"Intent: {_text(turn.get('intent')) or 'not stored'}")
    lines.append(f"Child: {turn.get('child_text') or ''}")
    lines.append(f"Tutor: {reply}")
    if error or not reply:
        lines.append(f"Error: {error or 'The tutor did not write a reply.'}")
    loop = after.get("loop_result")
    if not isinstance(loop, dict):
        loop = {}
    decision = _text(turn.get("loop_decision") or after.get("loop_decision"))
    lines.append(f"Loop decision: {decision or 'not stored'}")
    lines.append(f"Loop result: {json.dumps(loop, default=str)}")
    lines.extend(
        _llm_lines(
            call,
            child_prompt=_text(turn.get("child_prompt")),
            child_tokens=_dict(turn.get("child_tokens")),
            fallback_model=tutor_model,
        )
    )
    lines.append("")
    return lines


def _chat_lines(chat: dict) -> list[str]:
    child = _dict(chat.get("child"))
    name = _text(child.get("name")) or "Test child"
    turns = [row for row in _list(chat.get("turns")) if isinstance(row, dict)]
    calls = [row for row in _list(chat.get("llm_calls")) if isinstance(row, dict)]
    marks = block_marks(turns)
    opening, paired = _pair_calls(turns, calls)
    lines = [
        f"## {name}",
        "",
        f"Chat: {chat.get('id') or ''}",
        f"Status: {_text(chat.get('status')) or 'unknown'}",
        f"Ended: {_text(chat.get('ended_how')) or 'still open'}",
        f"Tutor model: {_text(chat.get('tutor_model')) or 'unknown'}",
        f"Child model: {_text(chat.get('child_model')) or 'unknown'}",
        f"Cost: {_cost(chat.get('cost_usd'))}",
        f"Luna tokens: {int(chat.get('luna_tokens') or 0)}",
        "",
    ]
    for call in opening:
        lines.append("### Opening tutor call")
        lines.append("")
        lines.extend(
            _llm_lines(call, child_prompt="", child_tokens={}, fallback_model=_text(chat.get("tutor_model")))
        )
        lines.append("")
    if not turns:
        lines.extend(["No turns stored.", ""])
    for turn, call in zip(turns, paired, strict=False):
        system = _text(turn.get("tutor_prompt"))
        used = call
        if used is not None and system and not _text(used.get("system_prompt")):
            used = {**used, "system_prompt": system}
        elif used is None and system:
            used = {"system_prompt": system, "model": chat.get("tutor_model") or ""}
        lines.extend(_turn_lines(turn, marks, used, _text(chat.get("tutor_model"))))
    lines.extend(_review_lines(chat))
    return lines


def _review_lines(chat: dict) -> list[str]:
    lines = ["### Automatic checks", ""]
    checks: dict = {}
    scores: list = []
    judge_error = ""
    for review in _list(chat.get("evaluations")):
        if not isinstance(review, dict):
            continue
        if review.get("kind") == "automatic" and isinstance(review.get("checks"), dict):
            checks = review["checks"]
        if review.get("kind") == "judged":
            scores = review.get("scores") if isinstance(review.get("scores"), list) else []
            judge_error = _text(review.get("error"))
    lines.append(json.dumps(checks, indent=2, default=str) if checks else "{}")
    lines.extend(["", "### Judge scores", ""])
    if judge_error:
        lines.append(f"Judge error: {judge_error}")
    if scores:
        for row in scores:
            if not isinstance(row, dict):
                continue
            lines.append(f"{_text(row.get('dimension')) or 'score'}: {row.get('score')}")
    elif not judge_error:
        lines.append("not judged")
    lines.extend(["", "### Block outcomes", ""])
    outcomes = [row for row in _list(chat.get("block_outcomes")) if isinstance(row, dict)]
    if not outcomes:
        lines.append("none stored")
    for row in outcomes:
        lines.append(f"{_text(row.get('title')) or 'block'}: {_text(row.get('outcome'))}")
    lines.append("")
    return lines


def render_download(run: dict, chats: list[dict]) -> str:
    """One file. A single chat is the same shape as a run that holds that chat."""
    commit = _text(run.get("code_version")) or "unknown"
    lines = [
        f"# Harness run {run.get('id') or ''}",
        "",
        f"Commit: {commit}",
        f"Status: {_text(run.get('status')) or 'unknown'}",
        "",
    ]
    if not chats:
        lines.append("No chats stored.")
        lines.append("")
    for chat in chats:
        if isinstance(chat, dict):
            lines.extend(_chat_lines(chat))
    return "\n".join(lines).rstrip() + "\n"
