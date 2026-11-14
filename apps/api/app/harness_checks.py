"""Automatic checks for one finished harness chat. No model call."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

CHECKS_VERSION = "1"
DEFAULT_CHAT_CAP_CENTS = 40
DEFAULT_TURN_LIMIT = 40
DEFAULT_STUCK_LIMIT = 8
STUCK_NUDGE_COUNT = 2
DEFAULT_LUNA_TOKEN_CEILING = 100_000


def stop_reason(
    *,
    session_status: str,
    intent: str,
    turn_count: int,
    same_place_turns: int,
    priced_cents: int,
    cap_cents: int | None,
    luna_tokens: int,
    luna_ceiling: int | None,
    consecutive_errors: int,
    safety_flag: str,
    stop_on_safety: bool,
    turn_limit: int = DEFAULT_TURN_LIMIT,
    stuck_limit: int = DEFAULT_STUCK_LIMIT,
) -> str:
    """Why this chat should end. Empty string means keep going."""
    if session_status == "completed":
        return "completed"
    if intent == "quit":
        return "quit"
    if turn_count >= turn_limit:
        return "turn_limit"
    if same_place_turns >= stuck_limit:
        return "stuck"
    if cap_cents is not None and priced_cents >= cap_cents:
        return "cap"
    if luna_ceiling is not None and luna_tokens >= luna_ceiling:
        return "luna_ceiling"
    if consecutive_errors >= 2:
        return "route_error"
    if stop_on_safety and safety_flag and safety_flag != "none":
        return "safety"
    return ""


def stuck_after_turn(
    *,
    reason: str,
    same_place_turns: int,
    stuck_limit: int,
    pending_nudges: int,
) -> tuple[str, int]:
    """Stop reason and pending nudge count after one stored turn.

    Hitting the stuck limit arms two nudges instead of closing. Each later
    turn that stays on the same block and substep spends one. The chat closes
    as stuck only when both are spent and the place is still unchanged. A move
    clears the count. Quit, the turn limit, and the spending cap are unchanged.
    """
    pending = max(0, int(pending_nudges or 0))
    if reason != "stuck":
        if same_place_turns < stuck_limit and pending:
            return reason, 0
        return reason, pending
    if pending > 0:
        remaining = pending - 1
        if remaining > 0:
            return "", remaining
        return "stuck", 0
    return "", STUCK_NUDGE_COUNT


WRONG_INTENTS = {
    "answer_wrong",
    "careless_slip",
    "guess",
    "wrong_choice",
}
UNSCORED_INTENTS = {
    "idk",
    "say_yes",
    "echo",
    "off_topic",
    "side_story",
    "short_remark",
    "on_topic_question",
    "word_meaning",
    "boundary_probe",
}
SIDE_INTENTS = {"off_topic", "side_story", "on_topic_question", "word_meaning", "short_remark"}

_LEAK = re.compile(r"\b(block\s*\d+|substep|blk_[a-z0-9]+)\b", re.I)
_LINK = re.compile(r"https?://", re.I)
_PERSONAL_ASK = re.compile(
    r"\b(what is your (full )?name|where do you live|your address|your school|phone number)\b",
    re.I,
)
_PRAISE = ("great", "nice", "good job", "awesome", "well done", "excellent")

KEY_INSTRUCTIONS = (
    ("ask_no_question", ("ask no question", "do not ask a question", "no question")),
    ("one_question", ("one question", "a single question", "ask one")),
    ("stay_on_course", ("stay on course", "return to the question", "back to the question")),
    ("no_giveaway", ("do not give the answer", "do not reveal the answer", "don't give away")),
)


def _text(value: object) -> str:
    return str(value or "").strip()


def _same(left: str, right: str) -> bool:
    a = " ".join(left.lower().split())
    b = " ".join(right.lower().split())
    if not a or not b:
        return False
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.9


def _questions(text: str) -> int:
    return text.count("?")


def _long_word_share(text: str) -> float:
    words = [word.strip(".,!?;:\"'") for word in text.split() if word.strip(".,!?;:\"'")]
    if not words:
        return 0.0
    long = sum(1 for word in words if len(word) >= 8)
    return long / len(words)


def instruction_rows(prompt: str, reply: str) -> list[dict]:
    folded = prompt.lower()
    rows = []
    for key, phrases in KEY_INSTRUCTIONS:
        present = any(phrase in folded for phrase in phrases)
        obeyed = True
        if present and key == "ask_no_question":
            obeyed = "?" not in reply
        elif present and key == "one_question":
            obeyed = _questions(reply) <= 1
        elif present and key == "no_giveaway":
            obeyed = True
        elif present and key == "stay_on_course":
            obeyed = True
        rows.append({"id": key, "present": present, "obeyed": obeyed if present else None})
    return rows


def automatic_checks(turns: list[dict], *, ended_how: str, response_length: str) -> dict:
    """Score one chat from stored turns. Each turn is a plain dict."""
    false_passes = []
    false_fails = []
    misread = []
    side = []
    buttons = []
    leaks = []
    giveaways = []
    empty = []
    errors = []
    flags = []
    links = []
    personal = []
    praise_open = 0
    tutor_replies = 0
    instruction_hits: dict[str, dict] = {}
    stuck_spans = 0
    same_step = 0
    last_place = ""
    repeated = []

    limit = 280 if response_length == "bite_sized" else 900 if response_length == "balanced" else 1600
    too_long = []

    for index, turn in enumerate(turns):
        intent = _text(turn.get("intent"))
        reply = _text(turn.get("tutor_reply"))
        prompt = _text(turn.get("prompt"))
        passed = bool(turn.get("passed"))
        attempt_before = int(turn.get("attempt_before") or 0)
        attempt_after = int(turn.get("attempt_after") or 0)
        place = f"{_text(turn.get('block_id'))}:{_text(turn.get('substep'))}"
        moved = place != f"{_text(turn.get('block_before'))}:{_text(turn.get('substep_before'))}" and index > 0
        if place == last_place:
            same_step += 1
        else:
            if same_step >= 8:
                stuck_spans += 1
            same_step = 1
            last_place = place
        if reply:
            tutor_replies += 1
            opening = reply.lower().split(",", 1)[0][:24]
            if any(opening.startswith(word) for word in _PRAISE):
                praise_open += 1
            if len(reply) > limit:
                too_long.append(index)
            if _LEAK.search(reply):
                leaks.append(index)
            if _LINK.search(reply):
                links.append(index)
            if _PERSONAL_ASK.search(reply):
                personal.append(index)
        if _text(turn.get("error")):
            errors.append(index)
        if not reply and intent not in {"quit"}:
            empty.append(index)
        flag = _text(turn.get("safety_flag"))
        if flag and flag != "none":
            flags.append({"turn": index, "flag": flag})
        if intent in WRONG_INTENTS and passed:
            false_passes.append(index)
        if intent == "answer_right" and not passed and not moved:
            false_fails.append(index)
        if intent in UNSCORED_INTENTS and (passed or attempt_after > attempt_before):
            misread.append(index)
        if intent in SIDE_INTENTS:
            side.append(
                {
                    "turn": index,
                    "answered": bool(reply),
                    "attempt_held": attempt_after == attempt_before,
                }
            )
        if intent == "tell_me_more" and index > 0:
            previous = _text(turns[index - 1].get("tutor_reply"))
            buttons.append({"turn": index, "kind": "tell_me_more", "new_material": not _same(previous, reply)})
        if intent == "move_on":
            buttons.append({"turn": index, "kind": "move_on", "moved": moved or passed})
        expected = _text(turn.get("expected"))
        if expected and expected.lower() in reply.lower() and not passed and intent not in {"move_on", "tell_me_more"}:
            giveaways.append(index)
        for row in instruction_rows(prompt, reply):
            bucket = instruction_hits.setdefault(row["id"], {"present": 0, "obeyed": 0})
            if row["present"]:
                bucket["present"] += 1
                if row["obeyed"]:
                    bucket["obeyed"] += 1
        if index >= 2:
            window = [_text(turns[index - offset].get("tutor_reply")) for offset in (0, 1, 2)]
            if window[0] and _same(window[0], window[1]) and _same(window[1], window[2]):
                repeated.append(index)

    if same_step >= 8:
        stuck_spans += 1

    return {
        "version": CHECKS_VERSION,
        "ended_how": ended_how,
        "turns": len(turns),
        "tutor_replies": tutor_replies,
        "false_passes": false_passes,
        "false_fails": false_fails,
        "misread": misread,
        "side": side,
        "buttons": buttons,
        "leaks": leaks,
        "giveaways": giveaways,
        "too_long": too_long,
        "empty_replies": empty,
        "errors": errors,
        "safety_flags": flags,
        "links": links,
        "personal_asks": personal,
        "repeated_replies": repeated,
        "stuck_spans": stuck_spans,
        "praise_share": (praise_open / tutor_replies) if tutor_replies else 0,
        "instructions": instruction_hits,
        "long_word_share": _long_word_share(" ".join(_text(turn.get("tutor_reply")) for turn in turns)),
    }
