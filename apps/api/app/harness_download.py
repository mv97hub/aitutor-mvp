"""One markdown file for a harness chat or a whole run.

The file is meant to be opened later. It keeps every stored turn, including a
blank or failed tutor call, plus the checks, scores, and the model record.
"""

from __future__ import annotations

import json
from collections import Counter

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
    places = []
    for turn in turns:
        before = _dict(turn.get("session_before"))
        places.append(before if _block_key(before) else _dict(turn.get("session_after")))
    for index, (turn, place) in enumerate(zip(turns, places, strict=True)):
        key = _block_key(place)
        if not key:
            continue
        next_key = _block_key(places[index + 1]) if index + 1 < len(places) else ""
        if key != previous:
            marks.append({"seq": turn.get("seq"), "edge": "start", "label": _mark_label(place)})
        if next_key and next_key != key:
            marks.append({"seq": turn.get("seq"), "edge": "end", "label": _mark_label(place)})
        previous = key
    return marks


def reply_message_id(before: dict, after: dict) -> str:
    before, after = _dict(before), _dict(after)
    message_id = _text(after.get("tutor_message_id"))
    if (after.get("error") or not _text(after.get("tutor_reply"))
            or after.get("tutor_call_kind") == "speak" or message_id == _text(before.get("tutor_message_id"))):
        return ""
    return message_id


def _tokens(row: dict) -> str:
    incoming = row.get("input_tokens")
    outgoing = row.get("output_tokens")
    if incoming is None and outgoing is None:
        return "not stored"
    return f"{int(incoming or 0)} in, {int(outgoing or 0)} out"


def _cost(value: object) -> str:
    text = _text(value)
    return text if text else "blank"


def _llm_lines(call: dict | None, *, child_prompt: str, child_tokens: dict) -> list[str]:
    model = _text((call or {}).get("model")) or "unknown"
    system_prompt = _text((call or {}).get("system_prompt"))
    lines = [
        "LLM record:",
        f"- Model: {model}",
        f"- Tutor message ID: {_text((call or {}).get('message_id')) or 'unknown'}",
        f"- Prompt record ID: {_text((call or {}).get('prompt_id')) or 'not stored'}",
        f"- Usage record ID: {_text((call or {}).get('usage_id')) or 'not stored'}",
        f"- Call kind: {_text((call or {}).get('kind')) or 'unknown'}",
        f"- System prompt: {system_prompt or 'not stored'}",
        f"- Child prompt: {child_prompt or 'not stored'}",
        f"- Tutor tokens: {_tokens(call or {})}",
        f"- Child tokens: {_tokens(child_tokens)}",
        f"- Cost: {_cost((call or {}).get('cost_usd'))}",
    ]
    return lines


def _turn_lines(turn: dict, marks: list[dict], call: dict | None) -> list[str]:
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
    for label, place in (("before", _dict(turn.get("session_before"))), ("after", after)):
        if _block_key(place):
            lines.append(f"Block {label}: {_mark_label(place)} ({_block_key(place)})")
    lines.append(f"Intent: {_text(turn.get('intent')) or 'not stored'}")
    before = _dict(turn.get("session_before"))
    if before.get("simulation_role"):
        lines.append(f"Simulation role: {before['simulation_role']}")
        lines.append(f"Planned action: {_text(before.get('planned_intent')) or 'unknown'}")
        lines.append(f"Observed tutor outcome: {_text(after.get('learner_observation')) or 'unknown'}")
        if isinstance(before.get("scenario_exercised"), bool):
            lines.append("Scripted scenario: " + ("exercised" if before["scenario_exercised"] else "setup"))
        if before.get("choice_fallback"):
            lines.append("The generated choice was invalid. The runner selected a displayed option.")
    lines.append(f"Child: {turn.get('child_text') or ''}")
    lines.append(f"Tutor: {reply}")
    if after.get("turn_id") and after.get("receipt_status") and after.get("delivery_status"):
        lines.extend([f"Submission: {after['turn_id']}", f"Tutor receipt: {after['receipt_status']}",
                      f"Delivery: {after['delivery_status']}"])
    if error or not reply:
        lines.append(f"Error: {error or 'The tutor did not write a reply.'}")
    loop = after.get("loop_result") if reply and not error else None
    if not isinstance(loop, dict):
        loop = {}
    decision = _text(turn.get("loop_decision") or after.get("loop_decision")) if reply and not error else ""
    lines.append(f"Loop decision: {decision or 'not stored'}")
    lines.append(f"Loop result: {json.dumps(loop, default=str)}")
    if call is None:
        lines.append("Tutor call association: unknown")
        call = {"message_id": reply_message_id(turn.get("session_before"), after)}
    lines.extend(
        _llm_lines(
            call,
            child_prompt=_text(turn.get("child_prompt")),
            child_tokens=_dict(turn.get("child_tokens")),
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
    call_counts = Counter(_text(call.get("message_id")) for call in calls)
    by_message = {
        message_id: index for index, call in enumerate(calls)
        if (message_id := _text(call.get("message_id"))) and call_counts[message_id] == 1
    }
    answer_ids = [reply_message_id(turn.get("session_before"), turn.get("session_after")) for turn in turns]
    answer_counts = Counter(answer_ids)
    rendered = set()
    lines = [
        f"## {name}",
        "",
        f"Chat: {chat.get('id') or ''}",
        f"Status: {_text(chat.get('status')) or 'unknown'}",
        f"Ended: {_text(chat.get('ended_how')) or 'still open'}",
        f"Tutor model: {_text(chat.get('tutor_model')) or 'unknown'}",
        f"Child model: {_text(chat.get('child_model')) or 'unknown'}",
        f"Simulation role: {_text(child.get('simulation_role')) or 'historical mode unknown'}",
        f"Scenario: {_text(child.get('scenario')) or 'unspecified'}",
        f"Policy: {_text(child.get('policy_version')) or 'historical version unknown'}",
        f"Behavior: {_text(chat.get('behavior')) or 'unknown'}",
        f"Chat seed: {chat.get('seed') if chat.get('seed') is not None else 'unknown'}",
        f"Iteration: {chat.get('iteration') or 'unknown'}",
        f"Cost: {_cost(chat.get('cost_usd'))}",
        f"Luna tokens: {int(chat.get('luna_tokens') or 0)}",
        "",
    ]
    if not turns:
        lines.extend(["No turns stored.", ""])
    for turn, answer_id in zip(turns, answer_ids, strict=True):
        before = _dict(turn.get("session_before"))
        before_id = _text(before.get("tutor_message_id"))
        opening = by_message.get(before_id)
        if (opening is not None and opening not in rendered and before_id not in answer_counts
                and before.get("tutor_call_kind") != "answer" and calls[opening].get("kind") != "answer"
                and "speak" in (calls[opening].get("kind"), before.get("tutor_call_kind"))):
            lines.extend([f"### Opening tutor call before turn {turn.get('seq')}", ""])
            lines.extend(_llm_lines({**calls[opening], "kind": "speak"}, child_prompt="", child_tokens={}))
            lines.append("")
            rendered.add(opening)
        index = by_message.get(answer_id)
        call = None
        if index is not None and answer_counts[answer_id] == 1 and calls[index].get("kind") != "speak":
            call = {**calls[index], "kind": "answer"}
            rendered.add(index)
        lines.extend(_turn_lines(turn, marks, call))
    pending = _dict(chat.get("pending_delivery"))
    unsent = _dict(_dict(chat.get("tokens")).get("unsent_child"))
    if unsent:
        lines.extend(["### Child response stopped before submission", "",
                      "The run reached its spending cap before the tutor was contacted.",
                      f"Submission: {unsent['turn_id']}",
                      f"Child tokens: {_tokens(_dict(unsent.get('child_tokens')))}", ""])
    if pending:
        lines.extend([f"### Pending submission for turn {pending['seq']}", "",
                      f"Child: {pending['child_text']}", f"Submission: {pending['turn_id']}",
                      f"Tutor receipt: {pending['receipt_status']}", "Delivery: unconfirmed", ""])
    remaining = [call for index, call in enumerate(calls) if index not in rendered]
    if remaining:
        lines.extend(["### Tutor records without a verified turn", "",
                      "Turn association is unknown for these stored records.", ""])
        for call in remaining:
            lines.extend(_llm_lines(call, child_prompt="", child_tokens={}))
            lines.append("")
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
    if run.get("seed") is not None:
        lines.extend([f"Run seed: {run['seed']}", ""])
    if isinstance(run.get("pair_tutor_seeds"), bool):
        paired = "shared within explicit pairs" if run["pair_tutor_seeds"] else "independent"
        lines.extend([f"Scenario seeds: {paired}", ""])
    if not chats:
        lines.append("No chats stored.")
        lines.append("")
    for chat in chats:
        if isinstance(chat, dict):
            lines.extend(_chat_lines(chat))
    return "\n".join(lines).rstrip() + "\n"
