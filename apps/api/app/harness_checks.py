"""Automatic checks for one finished harness chat. No model call."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.kc_blocks import passage_paragraphs

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
    stuck_answers: int = 0,
    intent: str = "",
) -> tuple[str, int, int]:
    """Stop reason, pending nudges, and answers given before those nudges.

    Hitting the stuck limit arms two nudges instead of closing. A turn that
    answers the tutor does not spend a nudge. A nudge spends one. The chat
    closes as stuck only when both nudges are spent and the place is still
    unchanged. A move clears both counts. Quit, the turn limit, and the
    spending cap are unchanged.
    """
    pending = max(0, int(pending_nudges or 0))
    answers = max(0, int(stuck_answers or 0))
    if reason != "stuck":
        if same_place_turns < stuck_limit and (pending or answers):
            return reason, 0, 0
        return reason, pending, answers
    if pending > 0 and intent != "nudge":
        return "", pending, answers + 1
    if pending > 0:
        remaining = pending - 1
        if remaining > 0:
            return "", remaining, answers
        return "stuck", 0, 0
    return "", STUCK_NUDGE_COUNT, 0


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

_LEAK = re.compile(r"\b(blocks?|substep|blk_[a-z0-9]+)\b", re.I)
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


def place_key(block_id: object, substep: object, topic: object = None) -> str:
    """Block, substep, and topic. Walking three explanatory topics is not one place."""
    base = f"{_text(block_id)}:{_text(substep)}"
    if topic is None or topic == "":
        return base
    return f"{base}:{topic}"


def turn_place(turn: dict) -> str:
    topic = turn.get("topic_index") if "topic_index" in turn else None
    return place_key(turn.get("block_id"), turn.get("substep"), topic)


# A summary close and an explanation have nothing to grade.
_UNGRADED_SUBSTEPS = {"explain", "explain_topic", "summary_check"}

# Task verbs and frame words are how the key is asked, not words the child says.
_TASK = frozenset({
    "explain", "determine", "describe", "identify", "state", "name", "compare",
    "list", "tell", "give", "show",
})
_FRAME = frozenset({"difference", "generally", "between"})
_FUNCTION = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "from",
    "by", "at", "as", "is", "are", "was", "were", "be", "been", "being",
    "it", "its", "their", "they", "them", "this", "that", "these", "those",
    "who", "what", "which", "when", "where", "how", "why", "than", "then",
    "into", "about", "because", "also", "just", "like", "very", "do", "does",
    "did", "can", "could", "would", "should", "will", "your", "you", "our",
    "his", "her", "there", "here", "if", "so", "but", "have", "has", "had",
    "we", "i", "me", "my", "even", "still", "much", "many", "some", "any",
    "each", "both", "other", "such", "same", "over", "out", "off", "too",
    "due",
})
_NEGATORS = frozenset({
    "not", "no", "never", "without", "neither", "nor", "cannot", "nobody", "nothing", "none",
})
_UP_WORDS = frozenset({
    "up", "increase", "increases", "increased", "rise", "rises", "rising", "rose", "higher",
})
_DOWN_WORDS = frozenset({
    "down", "decrease", "decreases", "decreased", "fall", "falls", "falling", "fell", "lower",
    "drop", "drops", "dropped",
})
_TOPICS = frozenset({
    "wage", "price", "inflation", "raise", "money", "cost", "rate", "worker", "borrower", "menu", "move",
})
_COMPARE_NOUNS = frozenset({"raise", "wage", "inflation", "price", "money", "cost", "rate"})
_OPPOSITE = {"help": "harm", "harm": "help", "benefit": "harm", "up": "down", "down": "up"}
_CANON = {
    "anticipated": "expected",
    "anticipate": "expected",
    "anticipates": "expected",
    "unanticipated": "surprise",
    "unexpected": "surprise",
    "surprised": "surprise",
    "surprises": "surprise",
    "harmful": "harm",
    "hurts": "harm",
    "hurt": "harm",
    "messes": "harm",
    "messed": "harm",
    "benefits": "benefit",
    "benfits": "benefit",
    "gains": "benefit",
    "gain": "benefit",
    "borrowed": "borrower",
    "borrowing": "borrower",
    "borrows": "borrower",
    "helps": "help",
    "helped": "help",
    "everyone": "people",
    "everybody": "people",
    "changing": "change",
    "changed": "change",
    "changes": "change",
    "costs": "cost",
    "expense": "cost",
    "expenses": "cost",
    "prices": "price",
    "wages": "wage",
    "decreases": "down",
    "decreased": "down",
    "decrease": "down",
    "falls": "down",
    "falling": "down",
    "fell": "down",
    "fall": "down",
    "drops": "down",
    "dropped": "down",
    "drop": "down",
    "lower": "down",
    "increases": "up",
    "increased": "up",
    "increase": "up",
    "rises": "up",
    "rising": "up",
    "rose": "up",
    "rise": "up",
    "higher": "up",
    "pays": "pay",
    "paid": "pay",
    "workers": "worker",
    "loses": "lose",
    "lost": "lose",
    "fewer": "less",
    "smaller": "less",
}
_CONTRACTIONS = (
    ("won't", "will not"),
    ("can't", "can not"),
    ("don't", "do not"),
    ("doesn't", "does not"),
    ("isn't", "is not"),
    ("aren't", "are not"),
    ("wasn't", "was not"),
    ("weren't", "were not"),
    ("didn't", "did not"),
    ("haven't", "have not"),
    ("hasn't", "has not"),
    ("wouldn't", "would not"),
    ("shouldn't", "should not"),
    ("couldn't", "could not"),
    ("it's", "it is"),
    ("that's", "that is"),
)
_PURPOSE_RE = re.compile(
    r"\b(?:to|when\s+(?:they|firms|businesses|stores|people|you))\s+"
    r"([a-z]+)\s+(?:(?:its|their|the|a|an|those)\s+)?([a-z]+)"
)
_HARM_RE = re.compile(
    r"\b(?:harm\w*|hurt\w*|worse|mess(?:es|ed)?\s+up|can not plan|cannot plan|no time to)\b"
)
_SURPRISE_RE = re.compile(r"\b(?:surprises?|surprised|unanticipated|unexpected)\b")
_EXPECTED_RE = re.compile(r"\b(?:expected|anticipated|anticipate|anticipates)\b")


def _normalize(text: str) -> str:
    raw = _text(text).lower().replace("\u2019", "'")
    for src, dst in _CONTRACTIONS:
        raw = raw.replace(src, dst)
    raw = re.sub(r"[^a-z0-9]+", " ", raw)
    raw = re.sub(r"\bteh\b", "the", raw)
    return " ".join(raw.split())


def _canon(word: str) -> str:
    if word in _CANON:
        return _CANON[word]
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        base = word[:-1]
        return _CANON.get(base, base)
    return word


def _keep(word: str) -> bool:
    return word.isdigit() or word in {"up", "down"} or len(word) > 3


def _negation_spans(tokens: list[str]) -> tuple[set[int], set[str]]:
    """Tokens inside a negation, and the concept the negation is aimed at."""
    blocked: set[int] = set()
    heads: set[str] = set()
    for index, token in enumerate(tokens):
        if token not in _NEGATORS:
            continue
        for cursor in range(index + 1, min(len(tokens), index + 5)):
            blocked.add(cursor)
        for cursor in range(index + 1, min(len(tokens), index + 5)):
            if tokens[cursor] in _FUNCTION or tokens[cursor] in _NEGATORS:
                continue
            heads.add(_canon(tokens[cursor]))
            break
    return blocked, heads


def _polarity(tokens: list[str]) -> tuple[dict[str, bool], set[int], set[str]]:
    blocked, heads = _negation_spans(tokens)
    affirmed: set[str] = set()
    denied: set[str] = set()
    for index, token in enumerate(tokens):
        if token in _FUNCTION or token in _NEGATORS:
            continue
        canon = _canon(token)
        if not _keep(canon):
            continue
        if index in blocked:
            denied.add(canon)
        else:
            affirmed.add(canon)
    polarity = {word: True for word in affirmed}
    for word in denied | heads:
        if word not in affirmed and _keep(word):
            polarity[word] = False
    return polarity, blocked, heads


def _phrase_concepts(text: str) -> set[str]:
    found: set[str] = set()
    if re.search(r"\bprices?\s+(?:rise|rises|rose|go up|went up|increase|increases|increased)\b", text):
        found.add("inflation")
    if re.search(r"\b(?:rising|higher)\s+prices\b", text):
        found.add("inflation")
    if re.search(r"\b(?:can not|cannot)\s+plan\b", text) or re.search(r"\bmess(?:es|ed)?\s+up\b", text):
        found.add("harm")
    if re.search(r"\bno time to\b", text):
        found.add("harm")
    return found


def _affirmed(tokens: list[str], text: str) -> set[str]:
    blocked, _heads = _negation_spans(tokens)
    found: set[str] = set()
    for index, token in enumerate(tokens):
        if index in blocked or token in _FUNCTION or token in _NEGATORS:
            continue
        canon = _canon(token)
        if _keep(canon):
            found.add(canon)
    return found | _phrase_concepts(text)


def _dir_kind(token: str) -> str | None:
    if token in _UP_WORDS or _canon(token) == "up":
        return "up"
    if token in _DOWN_WORDS or _canon(token) == "down":
        return "down"
    return None


def _directions(tokens: list[str], blocked: set[int]) -> set[str]:
    found: set[str] = set()
    for index, token in enumerate(tokens):
        kind = _dir_kind(token)
        if kind is None:
            continue
        if index in blocked:
            kind = "down" if kind == "up" else "up"
        found.add(kind)
    return found


def _topics(tokens: list[str]) -> set[str]:
    found: set[str] = set()
    for token in tokens:
        canon = _canon(token)
        if canon in _TOPICS:
            found.add(canon)
    return found


def _harm_case(text: str) -> str | None:
    """Which inflation case the line treats as the harmful one.

    Words after "than" are the comparison, not the case being called harmful.
    "Expected inflation hurts more than a surprise" names the expected case.
    """
    harms = [match.start() for match in _HARM_RE.finditer(text)]
    if not harms:
        return None
    harm_at = harms[-1]
    after = text[harm_at:]
    than = re.search(r"\bthan\b", after)
    cutoff = harm_at + than.start() if than else len(text)

    def nearest_before(pattern: re.Pattern[str]) -> int | None:
        spots = [match.start() for match in pattern.finditer(text) if match.start() < cutoff]
        spots = [spot for spot in spots if spot < harm_at or than is None]
        if not spots:
            return None
        return min(abs(harm_at - spot) for spot in spots)

    surprise = nearest_before(_SURPRISE_RE)
    expected = nearest_before(_EXPECTED_RE)
    if surprise is None and expected is None:
        return None
    if surprise is None:
        return "expected"
    if expected is None:
        return "surprise"
    if surprise == expected:
        return None
    return "surprise" if surprise < expected else "expected"


def _comparison(text: str) -> str | None:
    if re.search(r"\b(?:more|greater|higher)\s+than\b", text):
        return "more"
    if re.search(r"\b(?:less|fewer|lower|smaller)\s+than\b", text):
        return "less"
    return None


def _contradicts(child: str, key: str, child_tokens: list[str], key_tokens: list[str]) -> bool:
    """A negation or the opposite direction is not the key, even when other words match."""
    child_polarity, child_blocked, _child_heads = _polarity(child_tokens)
    key_polarity, key_blocked, key_heads = _polarity(key_tokens)
    for concept, affirmed in child_polarity.items():
        if not affirmed and key_polarity.get(concept) is True:
            return True
    for concept in key_heads:
        if child_polarity.get(concept) is True:
            return True
    child_dirs = _directions(child_tokens, child_blocked)
    key_dirs = _directions(key_tokens, key_blocked)
    if len(child_dirs) == 1 and len(key_dirs) == 1 and child_dirs != key_dirs:
        if _topics(child_tokens) & _topics(key_tokens):
            return True
    child_compare = _comparison(child)
    key_compare = _comparison(key)
    if child_compare and key_compare and child_compare != key_compare:
        child_nouns = {_canon(token) for token in child_tokens} & _COMPARE_NOUNS
        key_nouns = {_canon(token) for token in key_tokens} & _COMPARE_NOUNS
        if child_nouns & key_nouns:
            return True
    child_case = _harm_case(child)
    key_case = _harm_case(key)
    return bool(child_case and key_case and child_case != key_case)


def _is_instruction(tokens: list[str]) -> bool:
    for token in tokens:
        if token in _FUNCTION:
            continue
        return token in _TASK
    return False


def _required(tokens: list[str], instructional: bool) -> list[str]:
    required: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in _FUNCTION or token in _NEGATORS:
            continue
        if instructional and token in _TASK:
            continue
        canon = _canon(token)
        if instructional and canon in _FRAME:
            continue
        if not _keep(canon) or canon in seen:
            continue
        seen.add(canon)
        required.append(canon)
    return required


def _covered(concept: str, have: set[str], negated_heads: set[str]) -> bool:
    if concept in have:
        return concept not in negated_heads
    opposite = _OPPOSITE.get(concept)
    return bool(concept in negated_heads and opposite and opposite in have)


def _purpose_match(key: str, have: set[str]) -> bool:
    for verb, noun in _PURPOSE_RE.findall(key):
        verb_c = _canon(verb)
        noun_c = _canon(noun)
        if verb_c in _FUNCTION or noun_c in _FUNCTION or not _keep(verb_c) or not _keep(noun_c):
            continue
        if verb_c in have and noun_c in have:
            return True
    return False


def line_matches_key(child: str, expected: str) -> bool:
    """The child's words against the answer key. The intent label is not consulted.

    A short factual key has to be complete, so "the river is green" does not
    match "the river is blue". An instruction and a longer key match on the
    gist, including a paraphrase that never says the task verb. A negation
    does not match a key that says the opposite.
    """
    left = _normalize(child)
    right = _normalize(expected)
    if not left or not right:
        return False
    child_tokens = left.split()
    key_tokens = right.split()
    if _contradicts(left, right, child_tokens, key_tokens):
        return False
    if right in left:
        prefix = left[: left.find(right)].split()
        if not any(word in _NEGATORS for word in prefix[-3:]):
            return True
    have = _affirmed(child_tokens, left)
    if _purpose_match(right, have):
        return True
    instructional = _is_instruction(key_tokens)
    required = _required(key_tokens, instructional)
    if not required:
        return left == right
    key_heads = _polarity(key_tokens)[2]
    if "expected" in required and "surprise" in required:
        if "expected" not in have or "surprise" not in have:
            return False
    hits = sum(1 for concept in required if _covered(concept, have, key_heads))
    if len(required) <= 4 and not instructional:
        return hits == len(required)
    return hits * 2 >= len(required)


def graded_step(turn: dict) -> bool:
    """False when this step has no answer key. Those turns are not passes or fails."""
    substep = _text(turn.get("substep_before") or turn.get("substep"))
    if substep in _UNGRADED_SUBSTEPS:
        return False
    return bool(_text(turn.get("expected")))


def loop_accepted(turn: dict) -> bool:
    """The loop took the step as passed, and it did not reveal the answer."""
    loop = turn.get("loop_result")
    if not isinstance(loop, dict) or not loop:
        return False
    closed = _text(loop.get("closed"))
    if closed == "revealed":
        return False
    if closed == "passed":
        return True
    return bool(loop.get("advanced"))


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
        attempt_before = int(turn.get("attempt_before") or 0)
        attempt_after = int(turn.get("attempt_after") or 0)
        place = turn_place(turn)
        before_topic = turn.get("topic_before") if "topic_before" in turn else None
        before_place = place_key(turn.get("block_before"), turn.get("substep_before"), before_topic)
        moved = place != before_place and index > 0
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
            # Exclude only text actually printed from the assigned passage. A
            # paraphrase or additional explanation still counts as tutor coaching.
            coaching = reply
            passage = _text(turn.get("passage_text"))
            if passage:
                for paragraph in passage_paragraphs(passage):
                    coaching = coaching.replace(paragraph, "", 1)
            sentences = re.split(r"""[.!?]+["'”’)]*(?:\s+|$)""", coaching.strip())
            over_sentence_cap = response_length == "bite_sized" and sum(bool(part.strip()) for part in sentences) > 2
            if len(coaching.strip()) > limit or over_sentence_cap:
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
        # The intent is the plan the child was given. The verdict is the text against the key.
        if graded_step(turn):
            matched = line_matches_key(_text(turn.get("child_text")), _text(turn.get("expected")))
            accepted = loop_accepted(turn)
            if not matched and accepted:
                false_passes.append(index)
            if matched and not accepted:
                false_fails.append(index)
        passed = loop_accepted(turn)
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
